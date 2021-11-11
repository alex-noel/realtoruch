"""Additive local upgrades. Production uses the numbered SQL migrations."""

import hashlib
import json
import os
import inspect as pyinspect
import re
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session


SQL_DIR = Path(os.environ.get("REALTORUCH_SQL_DIR", Path(__file__).resolve().parents[2] / "infra" / "sql"))
REGISTRY = SQL_DIR / "migrations.json"


def load_registry(path=REGISTRY):
    registry = json.loads(Path(path).read_text())
    if set(registry) != {"rentals", "auth"}:
        raise ValueError("Registry must contain rentals and auth")
    for database, entries in registry.items():
        versions = []
        for entry in entries:
            version, name = entry["version"], entry["file"]
            if not re.fullmatch(r"[0-9]{3}", version) or not re.fullmatch(version + r"_[a-z0-9_]+\.sql", name):
                raise ValueError(f"Invalid migration entry in {database}")
            versions.append(version)
        if versions != sorted(set(versions)):
            raise ValueError(f"Duplicate or out-of-order versions in {database}")
    return registry


def apply_postgres(connection, database, registry_path=REGISTRY):
    """Apply registry atomically using caller's transaction and schema search_path."""
    registry = load_registry(registry_path)
    if connection.dialect.name != "postgresql" or database not in registry:
        raise ValueError("PostgreSQL and a known database are required")
    entries = registry[database]
    files = [(entry, (SQL_DIR / entry["file"]).read_bytes()) for entry in entries]
    # Never infer baseline history from pre-existing tables, including legacy
    # schema_migrations. Adoption requires an operator-reviewed procedure.
    tables = set(inspect(connection).get_table_names())
    if tables and "realtoruch_migrations" not in tables:
        raise ValueError("Untracked PostgreSQL schema: back up and use a reviewed migration/adoption procedure; see docs/testing.md")
    connection.execute(text("CREATE TABLE IF NOT EXISTS realtoruch_migrations (database_name VARCHAR(20) NOT NULL, version VARCHAR(3) NOT NULL, checksum VARCHAR(64) NOT NULL, PRIMARY KEY (database_name, version))"))
    applied = dict(connection.execute(text("SELECT version, checksum FROM realtoruch_migrations WHERE database_name=:db"), {"db": database}).all())
    owned_tables = {name for _, data in files for name in re.findall(r"(?im)^CREATE TABLE (?:IF NOT EXISTS )?([a-z_][a-z0-9_]*)", data.decode())} - {"schema_migrations"}
    if not applied and tables & owned_tables:
        raise ValueError("Untracked PostgreSQL schema: back up and use a reviewed migration/adoption procedure; see docs/testing.md")
    expected = {e["version"]: hashlib.sha256(data).hexdigest() for e, data in files}
    if any(v not in expected or expected[v] != checksum for v, checksum in applied.items()):
        raise ValueError("Applied migration missing or checksum changed")
    if list(sorted(applied)) != [e["version"] for e in entries[:len(applied)]]:
        raise ValueError("Applied migrations are not a registry prefix")
    for entry, data in files:
        if entry["version"] not in applied:
            # Baseline SQL files include psql transaction wrappers. Keep their bytes
            # immutable for checksums but let the caller own the transaction.
            sql = data.decode()
            sql = re.sub(r"(?m)^BEGIN;[ \t]*$", "", sql, count=1)
            sql = re.sub(r"(?m)^COMMIT;[ \t]*$", "", sql, count=1)
            connection.exec_driver_sql(sql)
            connection.execute(text("INSERT INTO realtoruch_migrations VALUES (:db, :version, :checksum)"), {"db": database, "version": entry["version"], "checksum": expected[entry["version"]]})


def upgrade_local(engine, database="rentals"):
    """Run immutable versioned SQLite-only callbacks; never execute PostgreSQL DDL."""
    if engine.dialect.name != "sqlite" or database not in {"rentals", "auth"}:
        raise ValueError("SQLite and a known database are required")
    hooks = {"rentals": [("001", _baseline_local)], "auth": []}[database]
    versions = [version for version, _ in hooks]
    if versions != sorted(set(versions)):
        raise ValueError("Duplicate or out-of-order local hooks")
    expected = {version: hashlib.sha256(pyinspect.getsource(hook).encode()).hexdigest() for version, hook in hooks}
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS realtoruch_local_migrations (database_name VARCHAR(20) NOT NULL, version VARCHAR(3) NOT NULL, checksum VARCHAR(64) NOT NULL, PRIMARY KEY(database_name, version))"))
        applied = dict(connection.execute(text("SELECT version, checksum FROM realtoruch_local_migrations WHERE database_name=:db"), {"db": database}).all())
        if any(version not in expected or expected[version] != checksum for version, checksum in applied.items()):
            raise ValueError("Applied local migration missing or checksum changed")
        if sorted(applied) != versions[:len(applied)]:
            raise ValueError("Applied local migrations are not a hook prefix")
    for version, hook in hooks:
        if version not in applied:
            # Hooks must be idempotent: a crash can occur between the callback and recording it.
            hook(engine)
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO realtoruch_local_migrations VALUES (:db, :version, :checksum)"), {"db": database, "version": version, "checksum": expected[version]})


def _baseline_local(engine):
    inspector = inspect(engine)
    baseline_existing = "city_key" not in {c["name"] for c in inspector.get_columns("saved_searches")}
    additions = {
        "listings": ("hidden", "BOOLEAN NOT NULL DEFAULT false"),
        "favorites": ("price_floor", "INTEGER"),
        "saved_searches": ("city_key", "VARCHAR(100) NOT NULL DEFAULT ''"),
    }
    with engine.begin() as connection:
        for table, (column, sql_type) in additions.items():
            if table in inspector.get_table_names() and column not in {
                c["name"] for c in inspector.get_columns(table)
            }:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
    from .models import Favorite, Listing, Outbox, SavedSearch, SourceListing
    from .normalization import fold

    for table in (SavedSearch.__table__, SourceListing.__table__, Outbox.__table__):
        for index in table.indexes:
            index.create(engine, checkfirst=True)
    with Session(engine) as session, session.begin():
        for favorite in session.scalars(select(Favorite).where(Favorite.price_floor.is_(None))):
            home = session.get(Listing, favorite.listing_id)
            favorite.price_floor = home.rent_pln
        for search in session.scalars(select(SavedSearch).where(SavedSearch.city_key == "")):
            search.city_key = fold(search.filters.get("city", ""))
        if baseline_existing:
            from .alerts import baseline_search

            for search in session.scalars(select(SavedSearch)):
                baseline_search(session, search)


def main():
    import argparse
    from sqlalchemy import create_engine
    parser = argparse.ArgumentParser(description="Validate or apply the PostgreSQL migration registry")
    parser.add_argument("action", choices=["validate", "apply"])
    parser.add_argument("--database", choices=["rentals", "auth"])
    parser.add_argument("--url", help="Disposable database URL; prefer MIGRATION_DATABASE_URL")
    args = parser.parse_args()
    load_registry()
    if args.action == "apply":
        import os
        url = args.url or os.environ.get("MIGRATION_DATABASE_URL")
        if not url or not args.database:
            parser.error("apply needs --database and MIGRATION_DATABASE_URL")
        engine = create_engine(url)
        with engine.begin() as connection:
            apply_postgres(connection, args.database)
        engine.dispose()
    print("Registry valid" if args.action == "validate" else "Migrations applied")


if __name__ == "__main__":
    main()
