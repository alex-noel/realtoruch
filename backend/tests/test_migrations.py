from sqlalchemy import select, text

from realtoruch.ingest import ingest
from realtoruch.migrations import upgrade_local
from realtoruch.models import Favorite, SavedSearch, SearchMatch


def test_existing_sqlite_accounts_upgrade_without_flooding_alerts(session, record):
    listing_id = ingest(session, record)["listing_id"]
    session.add(Favorite(user_id="existing-user", listing_id=listing_id))
    session.add(
        SavedSearch(
            id="existing-search", user_id="existing-user", name="Old search", filters={"city": "Warszawa"}
        )
    )
    session.commit()
    with session.bind.begin() as connection:
        connection.execute(text("ALTER TABLE favorites DROP COLUMN price_floor"))
        connection.execute(text("DROP INDEX ix_saved_searches_city_key"))
        connection.execute(text("ALTER TABLE saved_searches DROP COLUMN city_key"))
    upgrade_local(session.bind)
    upgrade_local(session.bind)  # Startup is repeatable.
    session.expire_all()
    assert session.get(Favorite, ("existing-user", listing_id)).price_floor == record.rent_pln
    assert session.get(SavedSearch, "existing-search").city_key == "warszawa"
    assert len(session.scalars(select(SearchMatch)).all()) == 1
