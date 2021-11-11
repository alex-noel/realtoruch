import re
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from test_rental_journey import FILTERS, account, home


def test_email_registration_rejects_multiple_recipients():
    from realtoruch.auth import Credentials

    with pytest.raises(ValueError):
        Credentials(email="one,two@example.test", password="a-long-test-password")


from realtoruch.alerts import process_alerts
from realtoruch.email_alerts import dispatch_email
from realtoruch.ingest import ingest
from realtoruch.models import EmailDelivery, EmailSubscription, now
from realtoruch.settings import get_settings


def opt_in(client, auth_client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "email_delivery_mode", "file")
    headers = account(auth_client)
    assert client.put("/v1/me/email-notifications", headers=headers, json={"enabled": True}).json()[
        "confirmation_pending"
    ]
    sent = []
    factory = sessionmaker(session.bind, expire_on_commit=False)
    dispatch_email(factory, sender=lambda message, delivery_id: sent.append(message))
    token = re.search(r"#confirm_email=([A-Za-z0-9_-]+)", sent[0].get_content()).group(1)
    assert client.post("/v1/notifications/email/confirm", json={"token": token}).status_code == 200
    return headers, factory, sent


def test_confirmed_email_new_matches_reposts_price_drop_and_unsubscribe(
    client, auth_client, session, record, monkeypatch
):
    headers, factory, sent = opt_in(client, auth_client, session, monkeypatch)
    client.post("/v1/me/searches", headers=headers, json={"name": "Kraków email", "filters": FILTERS})
    original = home(record)
    listing_id = ingest(session, original)["listing_id"]
    process_alerts(session)
    session.commit()
    dispatch_email(factory, sender=lambda message, delivery_id: sent.append(message))
    assert len(sent) == 2 and "4,500 PLN" in sent[-1].get_content()
    assert sent[-1]["To"] == "journey@example.test"
    client.put(f"/v1/me/seen/{listing_id}", headers=headers)
    client.put(f"/v1/me/favorites/{listing_id}", headers=headers)
    ingest(
        session,
        original.model_copy(
            update={"status": "inactive", "observed_at": original.observed_at + timedelta(hours=1)}
        ),
    )
    ingest(
        session,
        original.model_copy(
            update={"external_id": "repost", "observed_at": original.observed_at + timedelta(hours=2)}
        ),
    )
    process_alerts(session)
    session.commit()
    assert dispatch_email(factory, sender=lambda *args: sent.append(args)) == 0
    ingest(
        session,
        original.model_copy(
            update={
                "external_id": "repost",
                "rent_pln": 4200,
                "observed_at": original.observed_at + timedelta(hours=3),
            }
        ),
    )
    process_alerts(session)
    session.commit()
    dispatch_email(factory, sender=lambda message, delivery_id: sent.append(message))
    assert len(sent) == 3 and "4,500 → 4,200 PLN" in sent[-1].get_content()
    token = re.search(r"#unsubscribe_email=([A-Za-z0-9_-]+)", sent[-1].get_content()).group(1)
    assert client.post("/v1/notifications/email/unsubscribe", json={"token": token}).status_code == 200
    assert not client.get("/v1/me/email-notifications", headers=headers).json()["enabled"]
    ingest(
        session,
        original.model_copy(
            update={
                "external_id": "repost",
                "rent_pln": 4100,
                "observed_at": original.observed_at + timedelta(hours=4),
            }
        ),
    )
    process_alerts(session)
    session.commit()
    assert dispatch_email(factory, sender=lambda *args: sent.append(args)) == 0
    # Email opt-out preserves the in-app price alert.
    assert len(client.get("/v1/me/notifications", headers=headers).json()["items"]) == 3


def test_email_retry_has_stable_message_id_and_cancels_after_read(
    client, auth_client, session, record, monkeypatch
):
    headers, factory, _ = opt_in(client, auth_client, session, monkeypatch)
    client.post("/v1/me/searches", headers=headers, json={"name": "retry", "filters": FILTERS})
    listing_id = ingest(session, home(record))["listing_id"]
    process_alerts(session)
    session.commit()
    sent = []

    def temporary_failure(message, delivery_id):
        sent.append(message)
        raise ConnectionError("Do not persist recipient details")

    dispatch_email(factory, sender=temporary_failure)
    session.expire_all()
    delivery = session.scalar(select(EmailDelivery).where(EmailDelivery.notification_id.is_not(None)))
    assert delivery.status == "retry" and delivery.last_error == "ConnectionError"
    assert dispatch_email(factory, sender=temporary_failure) == 0
    delivery.next_attempt_at = now() - timedelta(seconds=1)
    session.commit()
    dispatch_email(factory, sender=lambda message, delivery_id: sent.append(message))
    assert sent[0]["Message-ID"] == sent[1]["Message-ID"]
    # A subsequently queued lower price is suppressed if opened before dispatch.
    client.put(f"/v1/me/favorites/{listing_id}", headers=headers)
    ingest(session, home(record, rent_pln=4000, observed_at=record.observed_at + timedelta(hours=1)))
    process_alerts(session)
    session.commit()
    client.put(f"/v1/me/seen/{listing_id}", headers=headers)
    assert dispatch_email(factory, sender=temporary_failure) == 0


def test_confirmation_is_required_expires_and_is_account_isolated(client, auth_client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "email_delivery_mode", "file")
    headers = account(auth_client)
    other = account(auth_client, "other-mail@example.test")
    for _ in range(2):
        assert (
            client.put("/v1/me/email-notifications", headers=headers, json={"enabled": True}).status_code
            == 200
        )
    assert len(session.scalars(select(EmailDelivery)).all()) == 1
    item = session.scalar(select(EmailSubscription))
    assert not item.enabled and not item.verified_at
    assert client.get("/v1/me/email-notifications", headers=other).json()["email"] is None
    token = session.scalar(select(EmailDelivery)).confirmation_token
    item.verification_expires_at = now() - timedelta(seconds=1)
    session.commit()
    assert client.post("/v1/notifications/email/confirm", json={"token": token}).status_code == 400
    assert client.put("/v1/me/email-notifications", json={"enabled": True}).status_code == 401


def test_file_delivery_is_private_and_idempotent(client, auth_client, session, monkeypatch, tmp_path):
    from realtoruch.email_alerts import send_email

    _, _, sent = opt_in(client, auth_client, session, monkeypatch)
    monkeypatch.setattr(get_settings(), "email_preview_directory", str(tmp_path))
    send_email(sent[0], "same-delivery")
    send_email(sent[0], "same-delivery")
    files = list(tmp_path.glob("*.eml"))
    assert len(files) == 1 and files[0].stat().st_mode & 0o777 == 0o600
    assert b"Confirm your Realtoruch" in files[0].read_bytes()


def test_smtp_delivery_over_a_real_local_socket(monkeypatch):
    from email.message import EmailMessage
    from socketserver import StreamRequestHandler, TCPServer
    from threading import Thread

    from realtoruch.email_alerts import send_email

    received = []

    class MailReceiver(StreamRequestHandler):
        def handle(self):
            self.wfile.write(b"220 test-mailbox\r\n")
            while line := self.rfile.readline():
                command = line.split()[0].upper()
                if command == b"DATA":
                    self.wfile.write(b"354 send message\r\n")
                    parts = []
                    while (part := self.rfile.readline()) != b".\r\n":
                        if not part:
                            return
                        parts.append(part)
                    received.append(b"".join(parts))
                    self.wfile.write(b"250 queued\r\n")
                elif command == b"QUIT":
                    self.wfile.write(b"221 bye\r\n")
                    return
                else:
                    self.wfile.write(b"250 ok\r\n")

    with TCPServer(("127.0.0.1", 0), MailReceiver) as server:
        thread = Thread(target=server.handle_request)
        thread.start()
        settings = get_settings()
        for key, value in {
            "email_delivery_mode": "smtp",
            "smtp_host": "127.0.0.1",
            "smtp_port": server.server_address[1],
            "smtp_security": "none",
            "smtp_username": "",
        }.items():
            monkeypatch.setattr(settings, key, value)
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = (
            "sender@example.test",
            "recipient@example.test",
            "Rental alert",
        )
        message.set_content("New apartment at 4500 PLN.")
        send_email(message, "smtp-test")
        thread.join(timeout=5)
    assert len(received) == 1 and b"4500 PLN" in received[0]
