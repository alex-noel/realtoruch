"""Additive local upgrades. Production uses the numbered SQL migrations."""

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session


def upgrade_local(engine):
    inspector = inspect(engine)
    baseline_existing = "city_key" not in {c["name"] for c in inspector.get_columns("saved_searches")}
    additions = {
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
