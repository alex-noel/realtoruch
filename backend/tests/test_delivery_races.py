"""Controlled lease races on independent SQLite connections and PostgreSQL sessions."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from realtoruch.auth import AccountToken, AuthBase, AuthJob, User, digest as auth_digest
from realtoruch.auth_jobs import process_jobs
from realtoruch.db import Base
from realtoruch.email_alerts import digest, dispatch_email
from realtoruch.models import EmailDelivery, EmailSubscription, Favorite, PushDelivery, PushSubscription, now
from realtoruch.push import dispatch_push
from realtoruch.settings import get_settings


@pytest.fixture(params=["sqlite", "postgres"])
def factory(request, tmp_path):
    admin = None
    if request.param == "sqlite":
        engine = create_engine("sqlite:///" + str(tmp_path / "races.db"), connect_args={"timeout": 10})
    else:
        if not os.environ.get("TEST_POSTGRES_URL"):
            pytest.skip("requires isolated PostgreSQL")
        schema = "t13_" + uuid4().hex
        admin = create_engine(os.environ["TEST_POSTGRES_URL"], isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        engine = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    AuthBase.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()
    if admin:
        with admin.connect() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def setup_job(factory, kind, record, monkeypatch):
    from realtoruch.alerts import process_alerts
    from realtoruch.ingest import ingest
    import realtoruch.auth_jobs as auth_jobs
    monkeypatch.setattr(auth_jobs, "AuthSession", factory)
    monkeypatch.setattr(get_settings(), "email_delivery_mode", "file")
    with factory.begin() as session:
        if kind == "email":
            session.add(EmailSubscription(user_id="user", email="synthetic@example.test", enabled=False,
                        verification_hash=digest("secret"), verification_expires_at=now() + timedelta(hours=1),
                        unsubscribe_token="unsubscribe"))
            session.flush()
            session.add(EmailDelivery(id="job", user_id="user", confirmation_token="secret"))
            model, run = EmailDelivery, lambda sender: dispatch_email(factory, limit=1, sender=sender)
        elif kind == "push":
            home = ingest(session, record)["listing_id"]
            session.add(Favorite(user_id="user", listing_id=home, price_floor=4000))
            session.add(PushSubscription(id="device", user_id="user", kind="expo", data={"token": "synthetic"}))
            session.flush()
            process_alerts(session)
            model, run = PushDelivery, lambda sender: dispatch_push(factory, limit=1, sender=sender)
        else:
            session.add(User(id="user", email="synthetic@example.test", password_hash="unused"))
            session.flush()
            session.add(AccountToken(token_hash=auth_digest("secret"), user_id="user", kind="verify", expires_at=now()+timedelta(hours=1)))
            session.add(AuthJob(id="job", user_id="user", kind="verify", secret="secret"))
            model, run = AuthJob, lambda sender: process_jobs(limit=1, sender=sender)
    with factory() as session:
        job_id = session.scalar(select(model.id))
    return model, job_id, run


@pytest.mark.parametrize("kind", ["email", "push", "auth"])
def test_simultaneous_workers_send_once(factory, record, monkeypatch, kind):
    model, job_id, run = setup_job(factory, kind, record, monkeypatch)
    start = Barrier(2)
    entered, release = Event(), Event()
    calls = []
    def sender(*args):
        calls.append(1)
        entered.set()
        assert release.wait(10)
    def worker():
        start.wait(timeout=10)
        return run(sender)
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(worker) for _ in range(2)]
        assert entered.wait(10)
        # One worker remains blocked in transport while the other finishes.
        done = next(task for task in tasks if task.done()) if any(t.done() for t in tasks) else None
        if done is None:
            # Wait for either worker to return without releasing the sender.
            from concurrent.futures import wait, FIRST_COMPLETED
            done = next(iter(wait(tasks, timeout=10, return_when=FIRST_COMPLETED).done))
        assert done.result() == 0
        release.set()
        assert sum(t.result(timeout=10) for t in tasks) == 1
    assert len(calls) == 1
    with factory() as session:
        assert session.get(model, job_id).attempts == 1


@pytest.mark.parametrize("kind", ["email", "push", "auth"])
@pytest.mark.parametrize("failure", [False, True])
def test_stale_completion_cannot_change_replacement(factory, record, monkeypatch, kind, failure):
    model, job_id, run = setup_job(factory, kind, record, monkeypatch)
    a_entered, a_release, b_entered, b_release = Event(), Event(), Event(), Event()
    def first(*args):
        a_entered.set(); assert a_release.wait(10)
        if failure: raise ConnectionError("private destination")
    def second(*args):
        b_entered.set(); assert b_release.wait(10)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(run, first)
        assert a_entered.wait(10)
        with factory.begin() as session:
            session.get(model, job_id).lease_until = now() - timedelta(seconds=1)
        b = pool.submit(run, second)
        assert b_entered.wait(10)
        with factory() as session:
            claimed = session.get(model, job_id)
            token, lease, status = claimed.claim_token, claimed.lease_until, claimed.status
        a_release.set(); a.result(timeout=10)
        with factory() as session:
            claimed = session.get(model, job_id)
            assert (claimed.claim_token, claimed.lease_until, claimed.status) == (token, lease, status)
        b_release.set(); b.result(timeout=10)


@pytest.mark.parametrize("kind", ["email", "push", "auth"])
def test_cancel_during_transport_is_not_replayed(factory, record, monkeypatch, kind):
    model, job_id, run = setup_job(factory, kind, record, monkeypatch)
    def cancel(*args):
        with factory.begin() as session:
            session.get(model, job_id).status = "cancelled"
    run(cancel)
    with factory() as session:
        assert session.get(model, job_id).status == "cancelled"
    assert run(lambda *args: pytest.fail("cancelled work replayed")) == 0


def test_disabled_mail_does_not_block_erasure(factory, monkeypatch):
    import realtoruch.auth_jobs as auth_jobs
    monkeypatch.setattr(auth_jobs, "AuthSession", factory)
    monkeypatch.setattr(get_settings(), "email_delivery_mode", "disabled")
    with factory.begin() as session:
        session.add_all([AuthJob(id="mail", user_id="mail-user", kind="verify", secret="secret", next_attempt_at=now()-timedelta(seconds=5)),
                         AuthJob(id="erase", user_id="deleted-user", kind="delete", next_attempt_at=now()-timedelta(seconds=1))])
    erased = []
    assert process_jobs(limit=2, eraser=erased.append) == 1
    assert erased == ["deleted-user"]
    with factory() as session:
        assert session.get(AuthJob, "mail").status == "pending"
        assert session.get(AuthJob, "erase").status == "done"


@pytest.mark.parametrize("kind", ["email", "push", "auth"])
def test_related_state_invalidated_during_transport(factory, record, monkeypatch, kind):
    from realtoruch.models import Notification
    model, job_id, run = setup_job(factory, kind, record, monkeypatch)
    def invalidate(*args):
        with factory.begin() as session:
            if kind == "email":
                session.get(EmailSubscription, "user").verification_hash = None
            elif kind == "push":
                session.scalar(select(Notification)).read_at = now()
            else:
                session.get(User, "user").deleted_at = now()
        raise ConnectionError("synthetic private value")
    run(invalidate)
    with factory() as session:
        assert session.get(model, job_id).status == "cancelled"
    assert run(lambda *args: pytest.fail("invalidated work replayed")) == 0


def test_bounded_mail_and_stable_identity_after_uncertain_acceptance(factory, record, monkeypatch):
    model, job_id, run = setup_job(factory, "email", record, monkeypatch)
    messages = []
    def uncertain(message, delivery_id):
        messages.append((message["Message-ID"], delivery_id))
        raise ConnectionError("connection lost after acceptance")
    for _ in range(8):
        assert run(uncertain) == 1
        with factory.begin() as session:
            session.get(model, job_id).next_attempt_at = now() - timedelta(seconds=1)
    assert run(uncertain) == 0
    with factory() as session:
        delivery = session.get(model, job_id)
        assert delivery.status == "failed" and delivery.attempts == 8
        assert session.scalar(select(model.id)) == job_id
    assert len(messages) == 8 and len(set(messages)) == 1


def test_erasure_retries_without_attempt_limit(factory, monkeypatch):
    import realtoruch.auth_jobs as auth_jobs
    monkeypatch.setattr(auth_jobs, "AuthSession", factory)
    monkeypatch.setattr(get_settings(), "email_delivery_mode", "disabled")
    with factory.begin() as session:
        session.add(AuthJob(id="erase", user_id="deleted", kind="delete", attempts=8))
    def fail(_):
        raise ConnectionError("private")
    assert process_jobs(limit=1, eraser=fail) == 1
    with factory.begin() as session:
        job = session.get(AuthJob, "erase")
        assert job.status == "retry" and job.attempts == 9
        job.next_attempt_at = now() - timedelta(seconds=1)
    assert process_jobs(limit=1, eraser=lambda _: None) == 1
    with factory() as session:
        assert session.get(AuthJob, "erase").status == "done"


def test_existing_sqlite_rows_upgrade_and_repeat(tmp_path):
    from realtoruch.migrations import upgrade_local
    engine = create_engine("sqlite:///" + str(tmp_path / "old.db"))
    Base.metadata.create_all(engine)
    AuthBase.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO email_subscriptions (user_id,email,enabled,requested_at,unsubscribe_token) VALUES ('u','synthetic@example.test',0,CURRENT_TIMESTAMP,'token')"))
        conn.execute(text("INSERT INTO email_deliveries (id,user_id,status,attempts,next_attempt_at) VALUES ('e','u','retry',3,CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO auth_jobs (id,user_id,kind,status,attempts,next_attempt_at) VALUES ('a','u','delete','retry',9,CURRENT_TIMESTAMP)"))
        for table in ("email_deliveries", "push_deliveries", "auth_jobs"):
            conn.execute(text(f"ALTER TABLE {table} DROP COLUMN claim_token"))
    for _ in range(2):
        upgrade_local(engine, "rentals")
        upgrade_local(engine, "auth")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status, attempts, claim_token FROM email_deliveries WHERE id='e'")).one() == ("retry", 3, None)
        assert conn.execute(text("SELECT status, attempts, claim_token FROM auth_jobs WHERE id='a'")).one() == ("retry", 9, None)
    engine.dispose()


@pytest.mark.parametrize("kind", ["email", "push", "auth"])
def test_delivery_removed_during_transport(factory, record, monkeypatch, kind):
    model, job_id, run = setup_job(factory, kind, record, monkeypatch)
    def remove(*args):
        with factory.begin() as session:
            session.delete(session.get(model, job_id))
    run(remove)
    with factory() as session:
        assert session.get(model, job_id) is None
    assert run(lambda *args: pytest.fail("deleted work replayed")) == 0


@pytest.mark.parametrize("invalidation", ["read", "delist", "unlike"])
def test_pending_push_is_cancelled_for_each_policy(factory, record, monkeypatch, invalidation):
    from realtoruch.models import Listing, Notification
    model, job_id, run = setup_job(factory, "push", record, monkeypatch)
    with factory.begin() as session:
        notification = session.scalar(select(Notification))
        if invalidation == "read":
            notification.read_at = now()
        elif invalidation == "delist":
            session.get(Listing, notification.listing_id).status = "inactive"
        else:
            session.delete(session.get(Favorite, ("user", notification.listing_id)))
    assert run(lambda *args: pytest.fail("invalidated work sent")) == 0
    with factory() as session:
        assert session.get(model, job_id).status == "cancelled"


def test_receipt_error_never_resends_accepted_ticket(factory, record, monkeypatch):
    model, job_id, run = setup_job(factory, "push", record, monkeypatch)
    calls = []
    assert run(lambda *args: calls.append("send") or "ticket") == 1
    with factory.begin() as session:
        session.get(model, job_id).next_attempt_at = now() - timedelta(seconds=1)
    def failed_receipt(_):
        raise ConnectionError("token must not leak")
    dispatch_push(factory, limit=1, sender=lambda *args: pytest.fail("resent"), receipt_checker=failed_receipt)
    with factory.begin() as session:
        job = session.get(model, job_id)
        assert job.status == "receipt" and job.receipt_id == "ticket"
        assert job.last_error == "push_error"
        job.next_attempt_at = now() - timedelta(seconds=1)
    dispatch_push(factory, limit=1, sender=lambda *args: pytest.fail("resent"), receipt_checker=lambda _: True)
    with factory() as session:
        assert session.get(model, job_id).status == "sent"
    assert calls == ["send"]


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requires isolated PostgreSQL")
@pytest.mark.parametrize("database", ["rentals", "auth"])
def test_postgres_retained_row_upgrade_and_repeat(database, tmp_path):
    import json
    from realtoruch.migrations import REGISTRY, apply_postgres
    schema = "t13_upgrade_" + uuid4().hex
    admin = create_engine(os.environ["TEST_POSTGRES_URL"], isolation_level="AUTOCOMMIT")
    registry = json.loads(REGISTRY.read_text())
    registry[database] = registry[database][:-1]
    old_registry = tmp_path / "old-registry.json"
    old_registry.write_text(json.dumps(registry))
    try:
        with admin.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
            conn.execute(text(f"SET search_path TO {schema}"))
            apply_postgres(conn, database, old_registry)
            if database == "rentals":
                conn.execute(text("INSERT INTO email_subscriptions (user_id,email,enabled,requested_at,unsubscribe_token) VALUES ('u','synthetic@example.test',false,CURRENT_TIMESTAMP,'token')"))
                conn.execute(text("INSERT INTO email_deliveries (id,user_id,status,attempts,next_attempt_at) VALUES ('e','u','retry',3,CURRENT_TIMESTAMP)"))
            else:
                conn.execute(text("INSERT INTO auth_jobs (id,user_id,kind,status,attempts,next_attempt_at) VALUES ('a','u','delete','retry',9,CURRENT_TIMESTAMP)"))
            apply_postgres(conn, database)
            apply_postgres(conn, database)
            table, identity, attempts = ("email_deliveries", "e", 3) if database == "rentals" else ("auth_jobs", "a", 9)
            assert conn.execute(text(f"SELECT status, attempts, claim_token FROM {table} WHERE id=:id"), {"id": identity}).one() == ("retry", attempts, None)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()


def test_unsubscribe_is_durable_even_if_reenabled_during_transport(factory, record, monkeypatch):
    from realtoruch.email_alerts import EmailToken, unsubscribe_email
    model, job_id, run = setup_job(factory, "email", record, monkeypatch)
    def unsubscribe_then_enable(*args):
        with factory() as session:
            unsubscribe_email(EmailToken(token="x" * 32), session=session)  # unknown token is harmless
        with factory.begin() as session:
            subscription = session.get(EmailSubscription, "user")
            token = subscription.unsubscribe_token
        # Call the actual endpoint function; its request model validates length at the API boundary.
        with factory() as session:
            unsubscribe_email(EmailToken.model_construct(token=token), session=session)
        with factory.begin() as session:
            subscription = session.get(EmailSubscription, "user")
            subscription.verification_hash = digest("secret")
            subscription.enabled = True
        raise ConnectionError("synthetic")
    run(unsubscribe_then_enable)
    with factory() as session:
        assert session.get(model, job_id).status == "cancelled"
    assert run(lambda *args: pytest.fail("unsubscribed delivery replayed")) == 0


@pytest.mark.parametrize("change", ["unlike", "delist"])
def test_reversed_invalidation_does_not_reactivate_leased_job(factory, record, monkeypatch, change):
    from realtoruch.api import remove_favorite
    from realtoruch.ingest import ingest
    from realtoruch.models import Notification
    model, job_id, run = setup_job(factory, "push", record, monkeypatch)
    with factory() as session:
        listing_id = session.scalar(select(Notification.listing_id))
    def invalidate_and_restore(*args):
        if change == "unlike":
            with factory() as session:
                remove_favorite(listing_id, user_id="user", session=session)
            with factory.begin() as session:
                session.add(Favorite(user_id="user", listing_id=listing_id, price_floor=4000))
        else:
            with factory.begin() as session:
                ingest(session, record.model_copy(update={"status": "inactive", "observed_at": record.observed_at + timedelta(hours=1)}))
            with factory.begin() as session:
                ingest(session, record.model_copy(update={"status": "active", "observed_at": record.observed_at + timedelta(hours=2)}))
        raise ConnectionError("synthetic")
    run(invalidate_and_restore)
    with factory() as session:
        job = session.get(model, job_id)
        assert job.status == "cancelled" and job.claim_token is None
    assert run(lambda *args: pytest.fail("cancelled job replayed")) == 0


def test_accepted_receipt_survives_read_cancellation(factory, record, monkeypatch):
    from realtoruch.api import read_notification
    from realtoruch.models import Notification
    model, job_id, run = setup_job(factory, "push", record, monkeypatch)
    run(lambda *args: "ticket")
    with factory() as session:
        notification_id = session.scalar(select(Notification.id))
        read_notification(notification_id, user_id="user", session=session)
    with factory.begin() as session:
        job = session.get(model, job_id)
        assert job.status == "receipt" and job.receipt_id == "ticket"
        job.next_attempt_at = now() - timedelta(seconds=1)
    dispatch_push(factory, limit=1, sender=lambda *args: pytest.fail("resent"), receipt_checker=lambda _: True)
    with factory() as session:
        assert session.get(model, job_id).status == "sent"


@pytest.mark.parametrize("factory", ["postgres"], indirect=True)
def test_postgres_listing_writer_and_completion_do_not_deadlock(factory, record, monkeypatch):
    from sqlalchemy import update
    import realtoruch.push as push_module
    from realtoruch.delivery_claims import cancel_notifications
    from realtoruch.models import Listing, Notification
    model, job_id, run = setup_job(factory, "push", record, monkeypatch)
    with factory() as session:
        listing_id = session.scalar(select(Notification.listing_id))
    completion_locked, writer_locked, continue_completion = Event(), Event(), Event()
    original = push_module.lock_owned
    def controlled_lock(*args):
        owned = original(*args)
        completion_locked.set()
        assert continue_completion.wait(10)
        return owned
    monkeypatch.setattr(push_module, "lock_owned", controlled_lock)
    def fail(*args):
        raise ConnectionError("synthetic")
    def writer():
        with factory.begin() as session:
            session.execute(update(Listing).where(Listing.id == listing_id).values(status="inactive"))
            writer_locked.set()
            cancel_notifications(session, listing_id=listing_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(run, fail)
        assert completion_locked.wait(10)
        mutation = pool.submit(writer)
        assert writer_locked.wait(10)
        continue_completion.set()
        worker.result(timeout=10)
        mutation.result(timeout=10)
    with factory() as session:
        assert session.get(model, job_id).status == "cancelled"


def test_diagnostics_exclude_transport_details(factory, record, monkeypatch, caplog):
    import logging
    model, job_id, run = setup_job(factory, "email", record, monkeypatch)
    def fail(*args):
        raise ConnectionError("private-address@example.test secret-token smtp-password")
    with caplog.at_level(logging.INFO, logger="realtoruch.delivery_claims"):
        run(fail)
    assert "status=retry" in caplog.text and "attempt=1" in caplog.text
    assert all(secret not in caplog.text for secret in ("private-address", "secret-token", "smtp-password"))
    with factory() as session:
        assert session.get(model, job_id).last_error == "ConnectionError"


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requires isolated PostgreSQL")
@pytest.mark.parametrize("database", ["rentals", "auth"])
def test_postgres_fresh_registry_and_repeat(database):
    from realtoruch.migrations import apply_postgres, load_registry
    schema = "t13_fresh_" + uuid4().hex
    admin = create_engine(os.environ["TEST_POSTGRES_URL"], isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
            conn.execute(text(f"SET search_path TO {schema}"))
            apply_postgres(conn, database)
            apply_postgres(conn, database)
            assert conn.scalar(text("SELECT count(*) FROM realtoruch_migrations WHERE database_name=:db"), {"db": database}) == len(load_registry()[database])
            table = "email_deliveries" if database == "rentals" else "auth_jobs"
            assert conn.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema AND table_name=:table AND column_name='claim_token'"), {"schema": schema, "table": table}) == 1
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()


def test_auth_user_removed_during_transport(factory, record, monkeypatch):
    model, job_id, run = setup_job(factory, "auth", record, monkeypatch)
    def remove_user(*args):
        with factory.begin() as session:
            session.delete(session.get(User, "user"))
        raise ConnectionError("synthetic")
    run(remove_user)
    with factory() as session:
        assert session.get(model, job_id).status == "cancelled"
    assert run(lambda *args: pytest.fail("deleted account replayed")) == 0
