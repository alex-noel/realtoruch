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
    duplicate = ingest(session, second)["listing_id"]
    assert duplicate != original
    merged = client.post(
        f"/v1/moderation/listings/{duplicate}/merge", headers=headers,
        json={"target_id": original, "reason": "An earlier mistaken manual identity decision."},
    )
    assert merged.status_code == 200
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
    updated_original = ingest(
        session, record.model_copy(update={"observed_at": now(), "rent_pln": 2900})
    )
    assert updated_original["listing_id"] == original
    assert session.get(Listing, original).rent_pln == 2900
    assert session.get(Listing, separate).rent_pln == 2800
    process_alerts(session)
    assert all(notification.kind != "new_match" for notification in session.scalars(select(Notification)))


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


def test_repost_requires_known_matching_floor_and_independent_evidence(record):
    from types import SimpleNamespace
    from realtoruch.dedupe import matching_property
    from realtoruch.normalization import normalize

    raw = record.model_copy(update={"images": ["https://images.example.test/home.jpg"]})
    data = normalize(raw)
    candidate = SimpleNamespace(**{key: data[key] for key in (
        "is_demo", "city", "rooms", "property_type", "area_m2", "floor", "address", "lat", "lon"
    )})
    sources = [SimpleNamespace(source=data["source"], phone_hash=data["phone_hash"], data=data)]
    assert matching_property(candidate, data, sources)
    assert not matching_property(candidate, {**data, "floor": None}, sources)
    assert not matching_property(candidate, {**data, "floor": data["floor"] + 1}, sources)
    assert not matching_property(candidate, {**data, "images": []}, sources)
    assert not matching_property(candidate, {**data, "lon": data["lon"] + 0.1}, sources)
    assert not matching_property(candidate, {**data, "address": data["address"] + "/9"}, sources)


def test_merge_preserves_pending_genuine_drop_without_identity_alert(client, auth_client, session, record, monkeypatch):
    uid, headers = account(auth_client, "pending-reviewer")
    monkeypatch.setattr(get_settings(), "moderator_user_ids", uid)
    target = ingest(session, record)["listing_id"]
    other = record.model_copy(update={"external_id": "pending-other", "address": "Other 91"})
    source = ingest(session, other)["listing_id"]
    client.put(f"/v1/me/favorites/{source}", headers=headers)
    client.put(f"/v1/me/seen/{source}", headers=headers)
    client.post("/v1/me/searches", headers=headers, json={"name": "Area", "filters": {"city": record.city}})
    client.post("/v1/me/searches", headers=headers, json={"name": "Second", "filters": {"city": record.city}})
    process_alerts(session)
    ingest(session, other.model_copy(update={"rent_pln": record.rent_pln - 200, "observed_at": now()}))
    session.flush()
    result = client.post(f"/v1/moderation/listings/{source}/merge", headers=headers,
        json={"target_id": target, "reason": "Reviewed duplicate despite different address data."})
    assert result.status_code == 200, result.text
    process_alerts(session)
    notifications = session.scalars(select(Notification).where(Notification.user_id == uid)).all()
    assert [(n.kind, n.rent_pln) for n in notifications] == [("price_drop", record.rent_pln - 200)]
    assert session.get(Favorite, (uid, target)).price_floor == record.rent_pln - 200
    assert session.get(SeenPrice, (uid, target, record.rent_pln))
    assert client.get(f"/v1/listings/{source}").json()["id"] == target


def test_split_blocks_pending_unattributed_price_drop(client, auth_client, session, record, monkeypatch):
    from sqlalchemy import func
    from realtoruch.models import (
        AlertEvent, EmailDelivery, EmailSubscription, Observation, PushDelivery,
        PushSubscription, SearchRevision,
    )

    uid, headers = account(auth_client, "split-pending-reviewer")
    monkeypatch.setattr(get_settings(), "moderator_user_ids", uid)
    home = ingest(session, record)["listing_id"]
    other = record.model_copy(update={"external_id": "split-pending", "address": "Other 104"})
    duplicate = ingest(session, other)["listing_id"]
    source_id = session.scalar(select(SourceListing.id).where(SourceListing.listing_id == duplicate))
    assert client.post(f"/v1/moderation/listings/{duplicate}/merge", headers=headers, json={
        "target_id": home, "reason": "Initially reviewed as one combined property."
    }).status_code == 200
    client.put(f"/v1/me/favorites/{home}", headers=headers)
    process_alerts(session)
    session.commit()
    ingest(session, other.model_copy(update={"rent_pln": record.rent_pln - 200, "observed_at": now()}))
    session.commit()
    body = {"source_id": source_id, "reason": "Later review shows distinct source identity."}
    pending = session.scalars(select(AlertEvent.id).where(AlertEvent.listing_id == home, AlertEvent.processed_at.is_(None))).all()
    assert pending
    def counts():
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (
            Listing, SourceListing, Observation, Favorite, IdentityDecision, AlertEvent, Notification,
            EmailDelivery, PushDelivery,
        ))
    def reject_unchanged():
        before = counts()
        revision = session.get(SearchRevision, home).revision
        response = client.post(f"/v1/moderation/listings/{home}/split", headers=headers, json=body)
        assert response.status_code == 409 and "Pending alert state" in response.json()["detail"]
        assert counts() == before and session.get(SearchRevision, home).revision == revision
        assert session.get(SourceListing, source_id).listing_id == home
        assert session.get(Favorite, (uid, home)).price_floor in (record.rent_pln, record.rent_pln - 200)
    reject_unchanged()
    assert session.scalars(select(AlertEvent.id).where(AlertEvent.listing_id == home, AlertEvent.processed_at.is_(None))).all() == pending
    process_alerts(session)
    session.commit()
    notification = session.scalar(select(Notification).where(Notification.user_id == uid))
    assert notification.kind == "price_drop" and notification.rent_pln == record.rent_pln - 200
    reject_unchanged()  # Unread inbox item, even with no transport.
    notification.read_at = now()
    session.add(EmailSubscription(user_id=uid, email="synthetic@example.test", enabled=True,
                                  verified_at=now(), unsubscribe_token="synthetic-token"))
    session.add(PushSubscription(id="t10-synthetic-push", user_id=uid, kind="expo", data={}))
    session.flush()
    email = EmailDelivery(user_id=uid, notification_id=notification.id, status="retry", claim_token="email-claim")
    push = PushDelivery(subscription_id="t10-synthetic-push", notification_id=notification.id,
                        status="receipt", claim_token="push-claim")
    session.add_all([email, push])
    session.commit()
    reject_unchanged()  # Claimed retry and accepted push receipt both remain pending.
    assert email.status == "retry" and email.claim_token == "email-claim"
    assert push.status == "receipt" and push.claim_token == "push-claim"
    email.status, email.claim_token = "sent", None
    session.commit()
    reject_unchanged()  # Receipt remains pending after email drain.
    push.status, push.claim_token = "sent", None
    session.commit()
    original = {key: getattr(notification, key) for key in (
        "id", "listing_id", "kind", "title", "rent_pln", "previous_rent_pln", "dedupe_key", "read_at"
    )}
    response = client.post(f"/v1/moderation/listings/{home}/split", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert session.get(SourceListing, source_id).listing_id == response.json()["listing_id"]
    session.refresh(notification)
    assert {key: getattr(notification, key) for key in original} == original
    inbox = client.get("/v1/me/notifications", headers=headers).json()["items"]
    assert len(inbox) == 1 and inbox[0]["id"] == notification.id and inbox[0]["listing_id"] == home
    process_alerts(session)
    assert session.scalar(select(func.count()).select_from(Notification)) == 1
