from datetime import timedelta
import json
from sqlalchemy import func, select
from realtoruch.ingest import ingest
from realtoruch.models import Listing, SourceListing, Observation, Outbox
from realtoruch.normalization import hash_phone, normalize
from realtoruch.query import market_history, search_db
from realtoruch.schemas import SearchFilters


def test_phone_normalization_is_keyed_and_never_public(session, record):
    assert hash_phone("700 100 101") == hash_phone("+48 700-100-101") == hash_phone("0048700100101")
    assert hash_phone("123") is None
    data = normalize(record)
    assert "phone" not in data
    assert "700100101" not in json.dumps(data)
    ingest(session, record)
    public = search_db(session, SearchFilters())
    assert "phone_hash" not in json.dumps(public)
    assert "700100101" not in json.dumps(public)


def test_duplicate_sources_become_one_home_and_keep_prices(session, record):
    one = ingest(session, record)
    two = ingest(session, record.model_copy(update={"source": "olx", "rent_pln": 3200}))
    assert one["listing_id"] == two["listing_id"]
    assert session.scalar(select(func.count()).select_from(Listing)) == 1
    result = search_db(session, SearchFilters())
    assert {s["rent_pln"] for s in result["items"][0]["sources"]} == {3000, 3200}


def test_shared_phone_alone_never_merges_homes_and_recalculates_all_risks(session, record):
    for i in range(3):
        ingest(
            session,
            record.model_copy(
                update={"external_id": str(i), "address": f"Different street {i + 1}", "lon": 21 + i * 0.02}
            ),
        )
    homes = session.scalars(select(Listing)).all()
    assert len(homes) == 3
    assert all(any(f["code"] == "frequent_contact" for f in home.risk_flags) for home in homes)


def test_same_building_different_floor_does_not_merge(session, record):
    one = ingest(session, record)
    two = ingest(session, record.model_copy(update={"external_id": "two", "floor": 5}))
    assert one["listing_id"] != two["listing_id"]


def test_incomplete_address_does_not_merge(session, record):
    one = ingest(session, record.model_copy(update={"address": "Mokotów"}))
    two = ingest(session, record.model_copy(update={"address": "Mokotów", "source": "olx"}))
    assert one["listing_id"] != two["listing_id"]


def test_retry_is_idempotent_and_old_observation_cannot_roll_back(session, record):
    result = ingest(session, record)
    assert ingest(session, record)["status"] == "duplicate_event"
    newer = record.model_copy(
        update={"observed_at": record.observed_at + timedelta(hours=1), "rent_pln": 3300}
    )
    ingest(session, newer)
    older = record.model_copy(
        update={"observed_at": record.observed_at - timedelta(hours=1), "rent_pln": 2500}
    )
    assert ingest(session, older)["status"] == "stale_event"
    assert session.get(Listing, result["listing_id"]).rent_pln == 3300
    assert session.scalar(select(func.count()).select_from(Observation)) == 2


def test_source_removal_keeps_property_active_until_last_source_is_removed(session, record):
    result = ingest(session, record)
    ingest(session, record.model_copy(update={"source": "olx"}))
    removed = record.model_copy(
        update={"status": "inactive", "observed_at": record.observed_at + timedelta(hours=2)}
    )
    ingest(session, removed)
    assert session.get(Listing, result["listing_id"]).status == "active"
    ingest(session, removed.model_copy(update={"source": "olx"}))
    assert session.get(Listing, result["listing_id"]).status == "inactive"
    assert search_db(session, SearchFilters())["total"] == 0


def test_history_counts_properties_once_per_month(session, record):
    ingest(session, record)
    ingest(session, record.model_copy(update={"source": "olx"}))
    ingest(
        session,
        record.model_copy(update={"external_id": "two", "address": "Other street 4", "rent_pln": 5000}),
    )
    history = market_history(session, "Warszawa")
    assert len(history["points"]) == 1
    assert history["points"][0]["sample_size"] == 2
    assert history["points"][0]["median_rent_pln"] == 4000


def test_failed_transaction_has_no_receipt_history_or_outbox(session, record):
    ingest(session, record)
    session.rollback()
    assert session.scalar(select(func.count()).select_from(Listing)) == 0
    assert session.scalar(select(func.count()).select_from(Outbox)) == 0
    assert session.scalar(select(func.count()).select_from(Observation)) == 0


def test_description_strips_markup_and_phone(record):
    data = normalize(
        record.model_copy(update={"description": '<script>alert("x")</script><p>Call +48 700 100 101</p>'})
    )
    assert (
        "<" not in data["description"]
        and "700" not in data["description"]
        and "alert" not in data["description"]
    )


def test_agency_evidence_flags_private_offer_without_changing_claim(session, record):
    result = ingest(session, record)
    ingest(
        session,
        record.model_copy(
            update={"external_id": "agency", "address": "Other 2", "advertiser_type": "agency"}
        ),
    )
    listing = session.get(Listing, result["listing_id"])
    assert listing.advertiser_type == "private"
    assert "mixed_identity" in [f["code"] for f in listing.risk_flags]
