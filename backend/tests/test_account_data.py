"""Account privacy and closure races; PostgreSQL uses disposable per-test schemas."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from realtoruch.account_data import export_bytes, guard_account_write
from realtoruch.api import erase_account_data
from realtoruch.auth import AuthBase, AuthJob, AuthSession
from realtoruch.db import Base
from realtoruch.models import (AccountClosure, AdvertiserProfile, EmailSubscription, Favorite,
                               Message, now)


@pytest.fixture(params=["sqlite", "postgres"])
def factory(request, tmp_path):
    admin = None
    if request.param == "sqlite":
        engine = create_engine("sqlite:///" + str(tmp_path / "lifecycle.db"), connect_args={"timeout": 10})
    else:
        if not os.environ.get("TEST_POSTGRES_URL"):
            pytest.skip("requires isolated PostgreSQL")
        schema = "t15_" + uuid4().hex
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


def test_stale_authorization_cannot_write_after_cleanup(factory):
    ready, release = Event(), Event()
    def stale_write():
        ready.set()  # Request already passed auth, before any SQL mutation.
        assert release.wait(10)
        with factory() as session:
            with pytest.raises(HTTPException) as exc:
                guard_account_write(session, "deleted")
            assert exc.value.status_code == 401
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(stale_write)
        assert ready.wait(10)
        with factory() as session:
            assert erase_account_data("deleted", session)["erased"]
        release.set()
        future.result(timeout=10)
    with factory() as session:
        assert session.get(AccountClosure, "deleted")
        assert not session.get(AdvertiserProfile, "deleted")
        assert not session.get(AccountClosure, "new-id")


def test_rollback_and_retry_pending_erasure(factory, monkeypatch):
    import realtoruch.auth_jobs as jobs
    monkeypatch.setattr(jobs, "AuthSession", factory)
    with factory.begin() as session:
        session.add_all([AdvertiserProfile(user_id="deleted", name="Private", kind="private"),
                         EmailSubscription(user_id="deleted", email="private@example.test", unsubscribe_token="x"),
                         AdvertiserProfile(user_id="other", name="Other", kind="private"),
                         AuthJob(id="job", user_id="deleted", kind="delete")])
    engine = factory.kw["bind"]
    failed = False
    def fail_after_delete(conn, cursor, statement, parameters, context, executemany):
        nonlocal failed
        if not failed and statement.lstrip().upper().startswith("DELETE FROM EMAIL_DELIVERIES"):
            failed = True
            raise RuntimeError("injected outage")
    event.listen(engine, "before_cursor_execute", fail_after_delete)
    def erase(uid):
        with factory() as session:
            erase_account_data(uid, session)
    assert jobs.process_jobs(limit=1, eraser=erase) == 1
    event.remove(engine, "before_cursor_execute", fail_after_delete)
    with factory.begin() as session:
        assert not session.get(AccountClosure, "deleted")
        assert session.get(AdvertiserProfile, "deleted")
        assert session.get(EmailSubscription, "deleted")
        job = session.get(AuthJob, "job")
        assert job.status == "retry"
        job.next_attempt_at = now() - timedelta(seconds=1)
    # This state also represents a restored backup with a pending delete job.
    assert jobs.process_jobs(limit=1, eraser=erase) == 1
    assert jobs.process_jobs(limit=1, eraser=erase) == 0
    erase("deleted")
    with factory() as session:
        assert session.get(AccountClosure, "deleted")
        assert not session.get(AdvertiserProfile, "deleted")
        assert not session.get(EmailSubscription, "deleted")
        assert session.get(AdvertiserProfile, "other")
        assert session.get(AuthJob, "job").status == "done"


def account(client, email):
    password = "a-long-account-test-password"
    r = client.post("/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201
    return r.json()["user"]["id"], {"Authorization": "Bearer " + r.json()["access_token"]}, password


def test_export_auth_scope_and_size(auth_client, client, session, monkeypatch):
    import realtoruch.account_data as data
    one, h1, password = account(auth_client, "one@example.test")
    two, h2, _ = account(auth_client, "two@example.test")
    session.add_all([AdvertiserProfile(user_id=one, name="MY CANARY", kind="private"),
                     AdvertiserProfile(user_id=two, name="OTHER CANARY", kind="private")])
    session.commit()
    assert client.get("/v1/me/export").status_code == 401
    assert client.get("/v1/me/export", headers=h1).status_code == 401
    assert auth_client.post("/v1/auth/reauthenticate", headers=h1, json={"password": "wrong-password-123"}).status_code == 401
    reply = auth_client.post("/v1/auth/reauthenticate", headers=h1, json={"password": password})
    assert reply.status_code == 200 and reply.json()["expires_in"] == 300
    purpose = reply.json()["export_token"]
    assert "no-store" in reply.headers["cache-control"]
    headers = {**h1, "X-Account-Export-Token": purpose}
    result = client.get("/v1/me/export", headers=headers)
    assert result.status_code == 200, result.text
    assert "private" in result.headers["cache-control"] and "no-store" in result.headers["cache-control"]
    assert "MY CANARY" in result.text and "OTHER CANARY" not in result.text
    assert client.get("/v1/me/export", headers={**h2, "X-Account-Export-Token": purpose}).status_code == 401
    other_session = auth_client.post("/v1/auth/login", json={"email": "one@example.test", "password": password}).json()["access_token"]
    assert client.get("/v1/me/export", headers={"Authorization": "Bearer " + other_session,
                      "X-Account-Export-Token": purpose}).status_code == 401
    assert client.get("/v1/me/favorites", headers={"Authorization": "Bearer " + purpose}).status_code == 401
    from realtoruch.settings import get_settings
    settings = get_settings()
    payload = jwt.decode(purpose, options={"verify_signature": False})
    payload["exp"] = int((now() - timedelta(minutes=1)).timestamp())
    expired = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    assert client.get("/v1/me/export", headers={**h1, "X-Account-Export-Token": expired}).status_code == 401
    monkeypatch.setattr(data, "EXPORT_LIMIT", 64)
    too_large = client.get("/v1/me/export", headers=headers)
    assert too_large.status_code == 413 and "export_too_large" in too_large.text
    assert "MY CANARY" not in too_large.text and "OTHER CANARY" not in too_large.text


def test_deleted_email_re_registers_with_new_id(auth_client, client, session):
    old, headers, password = account(auth_client, "return@example.test")
    session.add(AdvertiserProfile(user_id=old, name="Private", kind="private"))
    session.commit()
    assert auth_client.request("DELETE", "/v1/auth/account", headers=headers, json={"password": password}).status_code == 202
    erase_account_data(old, session)
    new, fresh, _ = account(auth_client, "return@example.test")
    assert new != old
    assert client.get("/v1/me/advertiser", headers=fresh).json()["profile"] is None
    assert client.get("/v1/me/advertiser", headers=headers).status_code == 401
    with pytest.raises(HTTPException):
        guard_account_write(session, old)
    session.rollback()


def test_sent_message_export_excludes_received_and_unknown_fields(auth_client, client, session):
    from test_marketplace import account as market_account, draft, publish
    from realtoruch.models import Advert
    owner_id, owner = market_account(auth_client, "export-owner")
    _, renter = market_account(auth_client, "export-renter")
    advert = publish(client, owner, draft(client, owner))
    started = client.post(f"/v1/adverts/{advert['id']}/conversations", headers=renter,
                          json={"client_id": "renter-one", "body": "OTHER PRIVATE CANARY"})
    assert started.status_code == 201, started.text
    conversation = started.json()["id"]
    sent = client.post(f"/v1/me/conversations/{conversation}/messages", headers=owner,
                       json={"client_id": "owner-one-1", "body": "MY SENT CANARY"})
    assert sent.status_code == 201, sent.text
    row = session.get(Advert, advert["id"])
    row.draft = {**row.draft, "password_hash": "FORBIDDEN CANARY"}
    session.commit()
    token = auth_client.post("/v1/auth/reauthenticate", headers=owner,
                             json={"password": "marketplace-test-password"}).json()["export_token"]
    response = client.get("/v1/me/export", headers={**owner, "X-Account-Export-Token": token})
    assert response.status_code == 200, response.text
    assert "MY SENT CANARY" in response.text
    assert "OTHER PRIVATE CANARY" not in response.text and "FORBIDDEN CANARY" not in response.text
    assert response.json()["account"]["id"] == owner_id
    assert response.json()["sent_messages"][0]["conversation_id"] == conversation


def test_export_consistent_snapshot_during_external_write(factory):
    import json
    engine = factory.kw["bind"]
    with factory.begin() as session:
        session.add_all([AdvertiserProfile(user_id="u", name="profile", kind="private"),
                         EmailSubscription(user_id="u", email="before@example.test", unsubscribe_token="token")])
    started, resume = Event(), Event()
    def pause_after_snapshot(conn, cursor, statement, parameters, context, executemany):
        if "advertiser_profiles" in statement and statement.lstrip().upper().startswith("SELECT") and not started.is_set():
            started.set()
            assert resume.wait(10)
    event.listen(engine, "after_cursor_execute", pause_after_snapshot)
    def reader():
        with factory() as guard:
            guard_account_write(guard, "u")
            if engine.dialect.name == "postgresql":
                with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
                    from sqlalchemy.orm import Session
                    with Session(connection) as snapshot:
                        return json.loads(export_bytes(snapshot, "u", "u@example.test"))
            return json.loads(export_bytes(guard, "u", "u@example.test"))
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(reader)
            assert started.wait(10)
            if engine.dialect.name == "postgresql":
                with engine.begin() as connection:
                    connection.execute(text("UPDATE email_subscriptions SET email='after@example.test' WHERE user_id='u'"))
            else:
                # The guarded SQLite snapshot holds the writer reservation.
                from sqlalchemy.exc import OperationalError
                with engine.connect() as connection:
                    connection.exec_driver_sql("PRAGMA busy_timeout=1")
                    with pytest.raises(OperationalError):
                        connection.execute(text("UPDATE email_subscriptions SET email='after@example.test' WHERE user_id='u'"))
            resume.set()
            exported = result.result(timeout=10)
            assert exported["email_preferences"][0]["email"] == "before@example.test"
    finally:
        resume.set()
        event.remove(engine, "after_cursor_execute", pause_after_snapshot)


def test_sqlite_upgrade_preserves_existing_rows(tmp_path):
    from realtoruch.migrations import upgrade_local
    engine = create_engine("sqlite:///" + str(tmp_path / "upgrade.db"))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO advertiser_profiles (user_id, name, kind, description, updated_at) VALUES ('u', 'kept', 'private', '', CURRENT_TIMESTAMP)"))
        connection.execute(text("DROP TABLE account_closures"))
    upgrade_local(engine)
    upgrade_local(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT name FROM advertiser_profiles WHERE user_id='u'")) == "kept"
        assert connection.scalar(text("SELECT count(*) FROM realtoruch_local_migrations WHERE version='009'")) == 1
        assert connection.scalar(text("SELECT count(*) FROM account_closures")) == 0
    engine.dispose()


@pytest.mark.parametrize("kind", ["favorite", "profile", "message"])
def test_real_write_routes_reject_prior_authorization(factory, kind):
    from realtoruch.api import save_favorite
    from realtoruch.marketplace import MessageBody, ProfileBody, reply, save_profile
    claims = {"sub": "deleted", "email_verified": True}
    with factory() as session:
        erase_account_data("deleted", session)
    with factory() as session:
        with pytest.raises(HTTPException) as exc:
            if kind == "favorite":
                save_favorite("home", "deleted", session)
            elif kind == "profile":
                save_profile(ProfileBody(name="Owner", kind="private"), claims, session)
            else:
                reply("conversation", MessageBody(client_id="abcdefghij", body="Private message"), claims, session)
        assert exc.value.status_code == 401


def test_guarded_write_finishes_before_cleanup(factory):
    acquired, release, deleting = Event(), Event(), Event()
    def writer():
        with factory.begin() as session:
            guard_account_write(session, "u")
            session.add(AdvertiserProfile(user_id="u", name="before", kind="private"))
            session.flush()
            acquired.set()
            assert release.wait(10)
    def cleanup():
        deleting.set()
        with factory() as session:
            erase_account_data("u", session)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(writer)
        assert acquired.wait(10)
        second = pool.submit(cleanup)
        assert deleting.wait(10)
        release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    with factory() as session:
        assert not session.get(AdvertiserProfile, "u")
        assert session.get(AccountClosure, "u")


def test_actual_ten_mib_export_limit(auth_client, client, session):
    from realtoruch.models import SavedSearch
    uid, headers, password = account(auth_client, "large@example.test")
    session.add(SavedSearch(user_id=uid, name="large", filters={"q": "x" * (10 * 1024 * 1024 + 1)}))
    session.commit()
    token = auth_client.post("/v1/auth/reauthenticate", headers=headers, json={"password": password}).json()["export_token"]
    response = client.get("/v1/me/export", headers={**headers, "X-Account-Export-Token": token})
    assert response.status_code == 413 and "export_too_large" in response.text
    assert "xxxxx" not in response.text


def test_oversized_multibyte_export_rejected_before_payload_materialization(factory):
    import json
    import tracemalloc
    from realtoruch.account_data import EXPORT_LIMIT
    from realtoruch.models import SavedSearch
    with factory.begin() as session:
        search = SavedSearch(user_id="large-unicode", name="Unicode", filters={})
        session.add(search)
        session.flush()
        # A legacy JSON payload can exceed schema validation limits. Store the
        # actual multibyte representation, not JSON's optional ASCII escapes.
        value = json.dumps({"q": "🏠" * (EXPORT_LIMIT // 4 + 1)}, ensure_ascii=False)
        placeholder = "CAST(:payload AS JSON)" if session.bind.dialect.name == "postgresql" else ":payload"
        session.execute(text(f"UPDATE saved_searches SET filters={placeholder} WHERE id=:id"),
                        {"payload": value, "id": search.id})
    tracemalloc.start()
    try:
        with factory() as session:
            with pytest.raises(HTTPException) as exc:
                export_bytes(session, "large-unicode", "synthetic@example.test")
            assert exc.value.status_code == 413
        _, peak = tracemalloc.get_traced_memory()
        assert peak < 4 * 1024 * 1024
    finally:
        tracemalloc.stop()


def test_restored_backup_resumes_pending_deletion(tmp_path, record, monkeypatch):
    import sqlite3
    import realtoruch.auth_jobs as jobs
    from realtoruch.ingest import ingest
    from realtoruch.models import Listing
    source_path = tmp_path / "source.db"
    backup_path = tmp_path / "backup.db"
    restored_path = tmp_path / "restored.db"
    source = create_engine("sqlite:///" + str(source_path))
    Base.metadata.create_all(source)
    AuthBase.metadata.create_all(source)
    source_factory = sessionmaker(source, expire_on_commit=False)
    with source_factory.begin() as session:
        listing_id = ingest(session, record)["listing_id"]
        session.add_all([AdvertiserProfile(user_id="deleted", name="Sensitive", kind="private"),
                         EmailSubscription(user_id="deleted", email="private@example.test", unsubscribe_token="secret"),
                         AuthJob(id="pending", user_id="deleted", kind="delete")])
    source.dispose()
    with sqlite3.connect(source_path) as original, sqlite3.connect(backup_path) as backup:
        original.backup(backup)
    with sqlite3.connect(backup_path) as backup, sqlite3.connect(restored_path) as restored:
        backup.backup(restored)
    engine = create_engine("sqlite:///" + str(restored_path))
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(jobs, "AuthSession", factory)
    def erase(uid):
        with factory() as session:
            erase_account_data(uid, session)
    assert jobs.process_jobs(limit=1, eraser=erase) == 1
    with factory() as session:
        assert session.get(AccountClosure, "deleted")
        assert not session.get(EmailSubscription, "deleted")
        assert not session.get(AdvertiserProfile, "deleted")
        assert session.get(Listing, listing_id).status == "active"
        assert session.get(AuthJob, "pending").status == "done"
    engine.dispose()


@pytest.mark.parametrize("operation", ["merge", "split", "review"])
def test_stale_moderator_cannot_change_public_state(factory, operation):
    from realtoruch.identity_review import MergeBody, SplitBody, merge, split
    from realtoruch.marketplace import ReviewBody, review
    with factory() as session:
        erase_account_data("moderator", session)
    with factory() as session:
        with pytest.raises(HTTPException) as exc:
            if operation == "merge":
                merge("old", MergeBody(target_id="new", reason="Reviewed evidence"), "moderator", session)
            elif operation == "split":
                split("old", SplitBody(source_id="source", reason="Reviewed evidence"), "moderator", session)
            else:
                review("report", ReviewBody(action="hide", reason="Reviewed evidence"), "moderator", session)
        assert exc.value.status_code == 401


def test_cleanup_scrubs_own_advert_and_conversation(auth_client, client, session):
    from test_marketplace import account as market_account, draft, publish
    from realtoruch.models import Advert, Conversation, Listing, Message, SourceListing
    owner_id, owner = market_account(auth_client, "scrub-owner")
    _, renter = market_account(auth_client, "scrub-renter")
    advert = publish(client, owner, draft(client, owner))
    response = client.post(f"/v1/adverts/{advert['id']}/conversations", headers=renter,
                           json={"client_id": "renter-1234", "body": "Private message"})
    assert response.status_code == 201
    conversation_id = response.json()["id"]
    erase_account_data(owner_id, session)
    assert not session.get(Advert, advert["id"])
    assert not session.get(Conversation, conversation_id)
    assert not session.scalar(select(Message.id).where(Message.conversation_id == conversation_id))
    source = session.scalar(select(SourceListing).where(SourceListing.source == "realtoruch", SourceListing.external_id == advert["id"]))
    assert source.status == "inactive"
    assert source.data["address"] == "" and source.data["description"] == "" and source.data["images"] == []
    home = session.get(Listing, advert["listing_id"])
    assert home.status == "inactive" and home.address == ""
