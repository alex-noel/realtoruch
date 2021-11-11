from sqlalchemy import select

from realtoruch.auth import AuthSession, User
from realtoruch.models import Advert, Conversation, Listing, Message, ModerationAction, now
from realtoruch.settings import get_settings

DRAFT = {
    "title": "Bright owner apartment in Kraków",
    "description": "A bright apartment with a separate bedroom and balcony.",
    "city": "Kraków",
    "district": "Podgórze",
    "region": "małopolskie",
    "address": "Testowa 18",
    "lat": 50.05,
    "lon": 19.95,
    "area_m2": 55,
    "rooms": 2,
    "rent_pln": 4500,
    "fees_pln": 400,
    "commission_pln": 0,
}


def account(auth_client, name, verified=True):
    result = auth_client.post(
        "/v1/auth/register", json={"email": name + "@example.test", "password": "marketplace-test-password"}
    ).json()
    uid = result["user"]["id"]
    if verified:
        with AuthSession.begin() as identity:
            identity.get(User, uid).verified_at = now()
    return uid, {"Authorization": "Bearer " + result["access_token"]}


def draft(client, headers):
    response = client.put(
        "/v1/me/advertiser",
        headers=headers,
        json={"name": "Local owner", "kind": "private", "description": "My rental profile"},
    )
    assert response.status_code == 200, response.text
    response = client.post("/v1/me/adverts", headers=headers, json=DRAFT)
    assert response.status_code == 201, response.text
    return response.json()


def publish(client, headers, advert):
    response = client.post(
        f"/v1/me/adverts/{advert['id']}/publish", headers=headers, json={"version": advert["version"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_draft_publish_edit_withdraw_and_relist_identity(client, auth_client, session):
    uid, owner = account(auth_client, "owner")
    _, renter = account(auth_client, "renter")
    advert = draft(client, owner)
    assert client.get("/v1/listings").json()["total"] == 0
    assert (
        client.put(
            f"/v1/me/adverts/{advert['id']}", headers=renter, json={"version": 1, "advert": DRAFT}
        ).status_code
        == 404
    )
    advert = publish(client, owner, advert)
    home_id = advert["listing_id"]
    home = client.get("/v1/listings/" + home_id).json()
    assert home["contact_adverts"][0]["id"] == advert["id"]
    assert home["sources"][0]["name"] == "realtoruch"
    assert client.get("/v1/advertisers/" + uid).json()["items"][0]["id"] == home_id
    assert (
        client.get("/v1/listings?max_price=5000&min_area=50&advertiser=private&no_commission=true").json()[
            "total"
        ]
        == 1
    )
    client.put("/v1/me/favorites/" + home_id, headers=renter)
    stale = client.put(
        f"/v1/me/adverts/{advert['id']}",
        headers=owner,
        json={"version": 1, "advert": {**DRAFT, "rent_pln": 4200}},
    )
    assert stale.status_code == 409
    response = client.put(
        f"/v1/me/adverts/{advert['id']}",
        headers=owner,
        json={"version": advert["version"], "advert": {**DRAFT, "rent_pln": 4200}},
    )
    assert response.status_code == 200, response.text
    advert = response.json()
    assert client.get("/v1/listings/" + home_id).json()["rent_pln"] == 4200
    assert session.get(Advert, advert["id"]).version == 3
    response = client.post(
        f"/v1/me/adverts/{advert['id']}/withdraw", headers=owner, json={"version": advert["version"]}
    )
    assert response.status_code == 200
    advert = response.json()
    assert client.get("/v1/listings").json()["total"] == 0
    assert client.get("/v1/me/favorites", headers=renter).json()["items"][0]["status"] == "inactive"
    assert publish(client, owner, advert)["listing_id"] == home_id


def test_unverified_publish_cannot_inject_identity_or_publish(client, auth_client):
    _, headers = account(auth_client, "unverified", verified=False)
    advert = draft(client, headers)
    assert (
        client.post(
            f"/v1/me/adverts/{advert['id']}/publish", headers=headers, json={"version": 1}
        ).status_code
        == 403
    )
    assert (
        client.post("/v1/me/adverts", headers=headers, json={**DRAFT, "user_id": "other-owner"}).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/me/adverts", headers=headers, json={**DRAFT, "images": ["http://example.test/image.jpg"]}
        ).status_code
        == 422
    )
    assert client.get("/v1/moderation/reports", headers=headers).status_code == 403


def test_messages_are_private_idempotent_and_blockable(client, auth_client, session):
    _, owner = account(auth_client, "owner")
    _, renter = account(auth_client, "renter")
    _, stranger = account(auth_client, "stranger")
    advert = publish(client, owner, draft(client, owner))
    body = {
        "body": "Is this apartment available for a viewing? Call 700 100 101.",
        "client_id": "first-message-001",
    }
    response = client.post(f"/v1/adverts/{advert['id']}/conversations", headers=renter, json=body)
    assert response.status_code == 201, response.text
    thread = response.json()["id"]
    assert (
        client.post(f"/v1/adverts/{advert['id']}/conversations", headers=renter, json=body).json()["id"]
        == thread
    )
    assert len(session.scalars(select(Message)).all()) == 1
    assert session.scalar(select(Message)).body == body["body"]
    assert client.get("/v1/me/conversations", headers=stranger).json()["items"] == []
    assert client.get(f"/v1/me/conversations/{thread}", headers=stranger).status_code == 404
    assert (
        client.post(f"/v1/me/conversations/{thread}/messages", headers=stranger, json=body).status_code == 404
    )
    assert client.get("/v1/me/conversations", headers=owner).json()["items"][0]["unread_count"] == 1
    client.put(f"/v1/me/conversations/{thread}/read", headers=owner)
    assert client.get("/v1/me/conversations", headers=owner).json()["items"][0]["unread_count"] == 0
    assert (
        client.post(
            f"/v1/me/conversations/{thread}/messages",
            headers=owner,
            json={"body": "Yes, tomorrow works.", "client_id": "owner-reply-001"},
        ).status_code
        == 201
    )
    assert client.get(f"/v1/me/conversations/{thread}", headers=renter).json()["items"][-1]["mine"] is False
    client.put(f"/v1/me/conversations/{thread}/block", headers=owner, json={"blocked": True})
    assert (
        client.post(
            f"/v1/me/conversations/{thread}/messages",
            headers=renter,
            json={**body, "client_id": "blocked-attempt-1"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/v1/me/conversations/{thread}/block", headers=renter, json={"blocked": False}
        ).status_code
        == 403
    )
    assert (
        client.put(f"/v1/me/conversations/{thread}/block", headers=owner, json={"blocked": False}).status_code
        == 200
    )


def test_moderation_survives_edits_and_owner_can_appeal(client, auth_client, session, monkeypatch):
    _, owner = account(auth_client, "owner")
    moderator_id, moderator = account(auth_client, "moderator")
    monkeypatch.setattr(get_settings(), "moderator_user_ids", moderator_id)
    advert = publish(client, owner, draft(client, owner))
    home_id = advert["listing_id"]
    report = client.post(
        f"/v1/listings/{home_id}/reports",
        headers=owner,
        json={"reason": "Please review the advertised terms."},
    ).json()
    decision = {"action": "hide", "reason": "Terms need additional advertiser evidence."}
    assert (
        client.post(f"/v1/moderation/reports/{report['id']}/review", headers=owner, json=decision).status_code
        == 403
    )
    assert (
        client.post(
            f"/v1/moderation/reports/{report['id']}/review", headers=moderator, json=decision
        ).status_code
        == 200
    )
    assert client.get("/v1/listings").json()["total"] == 0
    assert client.get("/v1/listings/" + home_id).status_code == 404
    assert client.get("/v1/me/adverts", headers=owner).json()["items"][0]["hidden"] is True
    changed = client.put(
        f"/v1/me/adverts/{advert['id']}",
        headers=owner,
        json={"version": advert["version"], "advert": {**DRAFT, "rent_pln": 4100}},
    )
    assert changed.status_code == 200
    assert session.get(Listing, home_id).hidden
    assert session.get(Listing, home_id).status == "inactive"
    assert (
        client.post(
            f"/v1/me/adverts/{advert['id']}/appeal",
            headers=owner,
            json={
                "action": "restore",
                "reason": "I have corrected the description and supplied clear terms.",
            },
        ).status_code
        == 201
    )
    pending = client.get("/v1/moderation/reports", headers=moderator).json()["items"]
    assert len(pending) == 1
    assert (
        client.post(
            f"/v1/moderation/reports/{pending[0]['id']}/review",
            headers=moderator,
            json={"action": "restore", "reason": "Advertiser evidence reviewed; corrected terms are clear."},
        ).status_code
        == 200
    )
    assert client.get("/v1/listings").json()["total"] == 1
    assert len(session.scalars(select(ModerationAction)).all()) == 2


def test_deletion_withdraws_owner_adverts_and_removes_conversations(client, auth_client, session):
    from realtoruch.auth_jobs import process_jobs

    uid, owner = account(auth_client, "owner")
    _, renter = account(auth_client, "renter")
    advert = publish(client, owner, draft(client, owner))
    client.post(
        f"/v1/adverts/{advert['id']}/conversations",
        headers=renter,
        json={"body": "I would like to arrange a viewing.", "client_id": "before-deletion"},
    )
    response = auth_client.request(
        "DELETE", "/v1/auth/account", headers=owner, json={"password": "marketplace-test-password"}
    )
    assert response.status_code == 202

    def erase(user_id):
        response = client.delete(
            f"/internal/accounts/{user_id}", headers={"X-Internal-Key": get_settings().internal_api_key}
        )
        assert response.status_code == 200, response.text

    process_jobs(eraser=erase)
    assert session.get(Advert, advert["id"]) is None
    assert session.scalar(select(Conversation)) is None
    assert session.scalar(select(Message)) is None
    home = session.get(Listing, advert["listing_id"])
    assert home.status == "inactive"
    assert home.description == ""
    assert client.get("/v1/advertisers/" + uid).status_code == 404
