"""Exercise actual grants on fresh, disposable PostgreSQL databases."""
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_role_grants():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("requires disposable PostgreSQL")
    # The service runner owns this server. Never run against a developer catalog.
    if not os.environ.get("VERIFY_RUN_ID"):
        pytest.fail("grant test requires the isolated verification runner")
    params = conninfo_to_dict(url.replace("postgresql+psycopg://", "postgresql://"))
    if params.get("host") not in {"127.0.0.1", "::1"} or not params.get("dbname", "").startswith("r_"):
        pytest.fail("grant test requires the runner-owned loopback database")
    suffix = uuid4().hex[:12]
    databases = {name: f"t28_{name}_{suffix}" for name in ("rentals", "auth")}
    roles = {name: f"t28_{name}_{suffix}" for name in ("api", "auth", "indexer", "alerts", "dataflow")}
    registry = json.loads((ROOT / "infra/sql/migrations.json").read_text())
    with psycopg.connect(make_conninfo(**params), autocommit=True) as admin:
        try:
            for role in roles.values():
                admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
            for db in databases.values():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))
            for logical, database in databases.items():
                dbparams = {**params, "dbname": database}
                with psycopg.connect(make_conninfo(**dbparams), autocommit=True) as conn:
                    for migration in registry[logical]:
                        conn.execute((ROOT / "infra/sql" / migration["file"]).read_text())
                    grants = (ROOT / "infra/sql/grants.sql").read_text().split("\\connect " + logical + "\n", 1)[1].split("\\connect ", 1)[0]
                    grants = grants.replace("DATABASE " + logical, 'DATABASE "' + database + '"')
                    for role, name in roles.items():
                        grants = grants.replace(':"' + role + '_user"', '"' + name + '"')
                    conn.execute(grants)
                    statements = {
                        "rentals": [("api", "SELECT * FROM account_closures", True),
                                    ("api", "DELETE FROM listing_aliases WHERE false", True),
                                    ("indexer", "SELECT * FROM search_revisions FOR UPDATE", True),
                                    ("dataflow", "UPDATE email_deliveries SET status=status WHERE false", True),
                                    ("alerts", "SELECT * FROM account_closures", False),
                                    ("indexer", "SELECT * FROM account_closures", False),
                                    ("dataflow", "SELECT * FROM account_closures", False),
                                    ("auth", "SELECT * FROM listings", False)],
                        "auth": [("api", "SELECT * FROM users", False), ("auth", "SELECT * FROM users", True)],
                    }
                    for role, statement, allowed in statements[logical]:
                        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(roles[role])))
                        try:
                            conn.execute(statement)
                        except psycopg.errors.InsufficientPrivilege:
                            assert not allowed, (role, statement)
                        else:
                            assert allowed, (role, statement)
                        finally:
                            conn.execute("RESET ROLE")
        finally:
            for database in databases.values():
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
            for role in roles.values():
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
