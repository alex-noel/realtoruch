from datetime import timedelta

from sqlalchemy import select
from test_marketplace import account

from realtoruch.alerts import process_alerts
from realtoruch.ingest import ingest
from realtoruch.models import (
    Favorite,
    IdentityDecision,
    Listing,
    ListingAlias,
    Notification,
    SeenPrice,
    SourceListing,
    now,
)
from realtoruch.settings import get_settings


def test_manual_merge_preserves_favorites_seen_history_and_old_links(
    client, auth_client, session, record, monkeypatch
):
    uid, headers = account(auth_client, "reviewer")
    monkeypatch.setattr(get_settings(), "moderator_user_ids", uid)
    original = ingest(session, record)["listing_id"]
    duplicate = ingest(
        session,
        record.model_copy(
            update={"source": "gratka", "external_id": "alternate", "address": "Incomplete street"}
        ),
    )["listing_id"]
    assert original != duplicate
    client.put(f"/v1/me/favorites/{original}", headers=headers)
    client.put(f"/v1/me/favorites/{duplicate}", headers=headers)
    client.put(f"/v1/me/seen/{original}", headers=headers)
    client.post("/v1/me/searches", headers=headers, json={"name": "Area", "filters": {"city": record.city}})
    with session.begin_nested():
        process_alerts(session)
    response = client.post(
        f"/v1/moderation/listings/{duplicate}/merge",
        headers=headers,
        json={"target_id": original, "reason": "Reviewed photos and full address; this is the same home."},
    )
    assert response.status_code == 200, response.text
    assert client.get("/v1/listings").json()["total"] == 1
    assert client.get(f"/v1/listings/{duplicate}").json()["id"] == original
    favorites = client.get("/v1/me/favorites", headers=headers).json()["items"]
    assert len(favorites) == 1 and favorites[0]["id"] == original
    assert len(favorites[0]["sources"]) == 2
    assert session.get(SeenPrice, (uid, original, record.rent_pln))
    assert session.get(ListingAlias, duplicate).listing_id == original
    process_alerts(session)
    assert session.scalar(select(Notification)) is None
    assert len(session.scalars(select(IdentityDecision)).all()) == 1
    assert client.delete(f"/v1/me/favorites/{duplicate}", headers=headers).status_code == 200
    assert session.get(Favorite, (uid, original)) is None


def test_split_keeps_both_shortlisted_and_future_source_updates_stay_separate(
    client, auth_client, session, record, monkeypatch
):
    uid, headers = account(auth_client, "reviewer")
    monkeypatch.setattr(get_settings(), "moderator_user_ids", uid)
    original = ingest(session, record)["listing_id"]
    second = record.model_copy(update={"source": "gratka", "external_id": "alternate"})
    assert ingest(session, second)["listing_id"] == original
    client.put(f"/v1/me/favorites/{original}", headers=headers)
    client.put(f"/v1/me/seen/{original}", headers=headers)
    process_alerts(session)
    evidence = client.get(f"/v1/moderation/listings/{original}/identity", headers=headers).json()
    source = next(s for s in evidence["sources"] if s["name"] == "gratka")
    response = client.post(
        f"/v1/moderation/listings/{original}/split",
        headers=headers,
        json={
            "source_id": source["id"],
            "reason": "Similar apartments but the photos show different floor plans.",
        },
    )
    assert response.status_code == 200, response.text
    separate = response.json()["listing_id"]
    assert separate != original
    assert client.get("/v1/listings").json()["total"] == 2
    assert len(client.get("/v1/me/favorites", headers=headers).json()["items"]) == 2
    assert session.get(SeenPrice, (uid, separate, record.rent_pln))
    updated = ingest(
        session, second.model_copy(update={"observed_at": now() - timedelta(seconds=1), "rent_pln": 2800})
    )
    assert updated["listing_id"] == separate
    assert session.get(Listing, original).rent_pln == record.rent_pln
    assert session.get(Listing, separate).rent_pln == 2800
    assert session.get(SourceListing, source["id"]).listing_id == separate


def test_identity_corrections_require_moderator_and_preserve_hidden_status(
    client, auth_client, session, record, monkeypatch
):
    uid, moderator = account(auth_client, "reviewer")
    _, ordinary = account(auth_client, "ordinary")
    monkeypatch.setattr(get_settings(), "moderator_user_ids", uid)
    first = ingest(session, record)["listing_id"]
    second = ingest(
        session, record.model_copy(update={"external_id": "different", "address": "Different 2"})
    )["listing_id"]
    body = {"target_id": first, "reason": "Source identity confirmed by manual review."}
    assert (
        client.post(f"/v1/moderation/listings/{second}/merge", headers=ordinary, json=body).status_code == 403
    )
    session.get(Listing, second).hidden = True
    session.commit()
    assert (
        client.post(f"/v1/moderation/listings/{second}/merge", headers=moderator, json=body).status_code
        == 200
    )
    assert session.get(Listing, first).hidden
    assert client.get("/v1/listings").json()["total"] == 0
