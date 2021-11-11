import base64
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from realtoruch.alerts import process_alerts
from realtoruch.ingest import ingest
from realtoruch.models import Favorite, Notification, PushDelivery, PushSubscription, now
from realtoruch.push import PushBody, PushFailure, dispatch_push, validate_endpoint


def queued(session, record, kind="web"):
    listing_id = ingest(session, record)["listing_id"]
    session.add(Favorite(user_id="one", listing_id=listing_id, price_floor=4000))
    session.add(
        PushSubscription(
            id="device",
            user_id="one",
            kind=kind,
            data={"endpoint": "https://fcm.googleapis.com/example", "keys": {}},
        )
    )
    session.flush()
    process_alerts(session)
    session.commit()
    return sessionmaker(session.bind, expire_on_commit=False)


def test_push_outbox_retries_once_and_does_not_resend_after_success(session, record):
    factory = queued(session, record)
    calls = []

    def fail(subscription, payload):
        calls.append(payload)
        raise PushFailure("temporary")

    assert dispatch_push(factory, sender=fail) == 1
    session.expire_all()
    item = session.scalar(select(PushDelivery))
    assert item.status == "retry" and item.attempts == 1 and item.next_attempt_at > now()
    assert dispatch_push(factory, sender=fail) == 0
    item.next_attempt_at = now() - timedelta(seconds=1)
    session.commit()

    def succeed(subscription, payload):
        calls.append(payload)

    assert dispatch_push(factory, sender=succeed) == 1
    assert dispatch_push(factory, sender=succeed) == 0
    assert len(calls) == 2 and calls[0]["notification_id"] == calls[1]["notification_id"]
    session.expire_all()
    assert session.scalar(select(PushDelivery)).status == "sent"


def test_invalidated_endpoint_is_disabled_and_inbox_survives(session, record):
    factory = queued(session, record)

    def gone(*args):
        raise PushFailure("gone", gone=True)

    dispatch_push(factory, sender=gone)
    session.expire_all()
    assert not session.get(PushSubscription, "device").active
    assert session.scalar(select(PushDelivery)).status == "failed"
    assert session.scalar(select(Notification)) is not None


def test_read_notification_or_changed_device_owner_cancels_pending_delivery(session, record):
    factory = queued(session, record)
    session.get(PushSubscription, "device").user_id = "another-account"
    session.commit()
    sent = []
    dispatch_push(factory, sender=lambda *args: sent.append(args))
    assert not sent
    session.expire_all()
    assert session.scalar(select(PushDelivery)).status == "cancelled"


def test_expo_receipts_are_checked_without_sending_again(session, record):
    factory = queued(session, record, kind="expo")
    sent = []

    def send(*args):
        sent.append(args)
        return "receipt-1"

    dispatch_push(factory, sender=send)
    session.expire_all()
    delivery = session.scalar(select(PushDelivery))
    assert delivery.status == "receipt" and delivery.receipt_id == "receipt-1"
    delivery.next_attempt_at = now() - timedelta(seconds=1)
    session.commit()
    dispatch_push(factory, sender=send, receipt_checker=lambda ticket: ticket == "receipt-1")
    session.expire_all()
    assert len(sent) == 1 and session.scalar(select(PushDelivery)).status == "sent"


@pytest.mark.parametrize(
    "url",
    [
        "http://fcm.googleapis.com/x",
        "https://127.0.0.1/x",
        "https://fcm.googleapis.com.evil.test/x",
        "https://user@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:444/x",
        "https://metadata.google.internal/x",
    ],
)
def test_push_endpoint_allowlist_rejects_untrusted_destinations(url):
    with pytest.raises(ValueError):
        validate_endpoint(url)


def test_web_push_keys_and_subscription_body_are_validated():
    key = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    encoded = lambda data: base64.urlsafe_b64encode(data).decode().rstrip("=")
    body = PushBody(
        kind="web",
        endpoint="https://fcm.googleapis.com/example",
        keys={"p256dh": encoded(key), "auth": encoded(b"1234567890123456")},
    )
    assert body.kind == "web"
    with pytest.raises(ValueError):
        PushBody(kind="web", endpoint=body.endpoint, keys={"auth": "invalid", "p256dh": "invalid"})
    assert PushBody(kind="expo", token="ExpoPushToken[local-test]").kind == "expo"


def test_subscription_ownership_limits_and_no_private_config_leak(client, auth_client, session, monkeypatch):
    from test_rental_journey import account

    from realtoruch.settings import get_settings

    monkeypatch.setattr(get_settings(), "expo_push_enabled", True)
    monkeypatch.setattr(get_settings(), "vapid_private_key", "private-signing-key-never-public")
    headers = account(auth_client)
    other = account(auth_client, "another-push@example.test")
    device = {"kind": "expo", "token": "ExpoPushToken[shared-device]"}
    response = client.post("/v1/me/push-subscriptions", headers=headers, json=device)
    assert response.status_code == 200
    device_id = response.json()["id"]
    assert "shared-device" not in response.text
    assert "private-signing-key" not in client.get("/v1/notifications/config").text
    assert client.delete(f"/v1/me/push-subscriptions/{device_id}", headers=other).status_code == 404
    for i in range(10):
        assert (
            client.post(
                "/v1/me/push-subscriptions",
                headers=other,
                json={"kind": "expo", "token": f"ExpoPushToken[device-{i}]"},
            ).status_code
            == 200
        )
    # Reassigning an existing browser/device must not bypass the account limit.
    assert client.post("/v1/me/push-subscriptions", headers=other, json=device).status_code == 422
    assert client.delete(f"/v1/me/push-subscriptions/{device_id}", headers=headers).status_code == 200
    session.expire_all()
    assert not session.get(PushSubscription, device_id).active


def test_web_push_payload_is_encrypted_and_redirects_are_disabled(monkeypatch):
    import json

    import http_ece
    import requests

    from realtoruch.push import send_push
    from realtoruch.settings import get_settings

    client_key = ec.generate_private_key(ec.SECP256R1())
    vapid_key = ec.generate_private_key(ec.SECP256R1())
    encoded = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    secret = b"1234567890123456"
    subscription = PushSubscription(
        kind="web",
        data={
            "endpoint": "https://fcm.googleapis.com/test-endpoint",
            "keys": {
                "auth": encoded(secret),
                "p256dh": encoded(
                    client_key.public_key().public_bytes(
                        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
                    )
                ),
            },
        },
    )
    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "vapid_private_key",
        encoded(
            vapid_key.private_bytes(
                serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        ),
    )
    monkeypatch.setattr(settings, "vapid_subject", "mailto:operator@example.test")
    monkeypatch.setattr(
        "realtoruch.push.socket.getaddrinfo", lambda *args: [(None, None, None, None, ("8.8.8.8", 443))]
    )
    sent = []

    def transport(self, method, url, **kwargs):
        sent.append(kwargs)
        response = requests.Response()
        response.status_code = 201
        return response

    monkeypatch.setattr(requests.Session, "request", transport)
    payload = {"title": "A new home", "listing_id": "test-home"}
    assert send_push(subscription, payload) is None
    assert sent[0]["allow_redirects"] is False
    decrypted = http_ece.decrypt(
        sent[0]["data"], private_key=client_key, auth_secret=secret, version="aes128gcm"
    )
    assert json.loads(decrypted) == payload
