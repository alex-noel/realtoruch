"""T16 cursor behavior on SQLite and disposable PostgreSQL 16."""

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.orm import sessionmaker
from test_marketplace import account, draft, publish

from realtoruch import marketplace
from realtoruch.auth import validate_claims
from realtoruch.db import Base, get_session, make_engine
from realtoruch.migrations import apply_postgres, load_registry, upgrade_local
from realtoruch.models import Advert, AdvertiserProfile, Conversation, Message

STAMP = datetime(2026, 1, 1, 12, 0, 0, 123456)
INBOX = "/v1/me/conversations"


def key(number):
    return str(UUID(int=number))


@contextmanager
def postgres_schema():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Requires an isolated PostgreSQL test instance")
    schema = "test_t16_" + uuid4().hex
    admin = create_engine(url)
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    try:
        with admin.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()


@pytest.fixture(params=["sqlite", "postgresql"])
def engine(request, tmp_path):
    if request.param == "postgresql":
        with postgres_schema() as engine:
            with engine.begin() as connection:
                apply_postgres(connection, "rentals")
            yield engine
    else:
        engine = make_engine(f"sqlite:///{tmp_path / 'cursors.db'}")
        try:
            Base.metadata.create_all(engine)
            upgrade_local(engine)
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def inbox(engine, auth_client):
    factory = sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(marketplace.router)
    app.state.validate_claims = validate_claims

    def rental_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = rental_session
    owner = account(auth_client, "t16-owner")
    renter = account(auth_client, "t16-renter")
    outsider = account(auth_client, "t16-outsider")
    with TestClient(app) as client:
        yield client, factory, owner, renter, outsider


def seed_threads(factory, owner, renter, count=1):
    with factory.begin() as session:
        if not session.get(AdvertiserProfile, owner):
            session.add(AdvertiserProfile(user_id=owner, name="Synthetic profile", kind="private"))
            session.flush()
        threads = []
        for number in range(count):
            advert = Advert(user_id=owner, draft={"title": f"Synthetic apartment {number}"})
            session.add(advert)
            session.flush()
            thread = Conversation(
                id=key(number + 1) if count > 1 else str(uuid4()),
                advert_id=advert.id,
                owner_id=owner,
                renter_id=renter,
                created_at=STAMP,
                updated_at=STAMP + timedelta(seconds=number // 60),
            )
            session.add(thread)
            threads.append(thread.id)
    return threads


def seed_messages(factory, thread, sender, count, first=1, *, timestamps_tied=True):
    with factory.begin() as session:
        session.add_all(
            Message(
                id=key(number),
                conversation_id=thread,
                sender_id=sender,
                body=f"Synthetic message {number}",
                client_id=f"seed-message-{number}",
                created_at=STAMP + timedelta(seconds=0 if timestamps_tied else number // 65),
            )
            for number in range(first, first + count)
        )
    return [key(number) for number in range(first, first + count)]


def read(client, headers, thread, last):
    return client.put(f"{INBOX}/{thread}/read", headers=headers, json={"last_message_id": last})


def unread(client, headers, thread):
    response = client.get(INBOX, headers=headers)
    assert response.status_code == 200, response.text
    return next(item["unread_count"] for item in response.json()["items"] if item["id"] == thread)


def send(client, headers, thread, key, body="Synthetic reply"):
    return client.post(f"{INBOX}/{thread}/messages", headers=headers, json={"client_id": key, "body": body})


def watermark(factory, thread):
    with factory() as session:
        row = session.get(Conversation, thread)
        return (
            row.owner_read_at,
            row.owner_read_message_id,
            row.renter_read_at,
            row.renter_read_message_id,
        )


def test_t16_tc01_read_stops_at_displayed_message_and_send_does_not_ack(inbox, monkeypatch):
    client, factory, (owner_id, owner), (renter_id, renter), _ = inbox
    (thread,) = seed_threads(factory, owner_id, renter_id)
    m1, m2 = seed_messages(factory, thread, renter_id, 2)
    shown = client.get(f"{INBOX}/{thread}", headers=owner).json()["items"]
    assert [m["id"] for m in shown] == [m1, m2]

    # A reply arrives after fetch with a tied or regressed application wall clock.
    # Its random ID must not allow it to sort before the displayed boundary.
    monkeypatch.setattr(marketplace, "now", lambda: STAMP)
    arrival = send(client, renter, thread, "after-displayed-page")
    assert arrival.status_code == 201, arrival.text
    assert arrival.json()["created_at"] == "2026-01-01T12:00:00.123457Z"
    monkeypatch.setattr(marketplace, "now", lambda: STAMP - timedelta(seconds=1))
    assert send(client, owner, thread, "own-reply-after-arrival").status_code == 201
    assert unread(client, owner, thread) == 3
    assert read(client, owner, thread, m2).json() == {"read": True}
    assert unread(client, owner, thread) == 1
    assert unread(client, renter, thread) == 1

    # The other participant stores a separate cursor. The original v1 request
    # still acknowledges the latest committed message when the body is omitted.
    assert client.put(f"{INBOX}/{thread}/read", headers=renter).json() == {"read": True}
    assert unread(client, renter, thread) == 0
    assert unread(client, owner, thread) == 1
    assert watermark(factory, thread)[:2] == (STAMP, m2)


def test_t16_tc02_equal_timestamps_and_monotonic_ack(inbox):
    client, factory, (owner_id, owner), (renter_id, _), _ = inbox
    (thread,) = seed_threads(factory, owner_id, renter_id)
    m1, m2, m3 = seed_messages(factory, thread, renter_id, 3)
    assert read(client, owner, thread, m2).status_code == 200
    assert unread(client, owner, thread) == 1
    for last in (m1, m2):
        assert read(client, owner, thread, last).status_code == 200
        assert watermark(factory, thread) == (STAMP, m2, None, None)
        assert unread(client, owner, thread) == 1
    assert read(client, owner, thread, m3).status_code == 200
    assert unread(client, owner, thread) == 0


def test_t16_tc02_concurrent_acknowledgements_cannot_regress(inbox, engine):
    client, factory, (owner_id, owner), (renter_id, _), _ = inbox
    (thread,) = seed_threads(factory, owner_id, renter_id)
    m1, m2 = seed_messages(factory, thread, renter_id, 2)
    at_update, at_second_lock, release = Event(), Event(), Event()

    def pause_after_lock(_conn, _cursor, sql, _parameters, _context, _many):
        if sql.startswith("UPDATE conversations SET") and not at_update.is_set():
            at_update.set()
            assert release.wait(5), "newer acknowledgement was not released"
        if at_update.is_set() and (sql == "BEGIN IMMEDIATE" or "FOR UPDATE" in sql or "pg_advisory_xact_lock" in sql):
            at_second_lock.set()

    event.listen(engine, "before_cursor_execute", pause_after_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            newer = pool.submit(read, client, owner, thread, m2)
            try:
                assert at_update.wait(5), "newer acknowledgement did not reach its update"
                older = pool.submit(read, client, owner, thread, m1)
                assert at_second_lock.wait(5), "older acknowledgement did not reach the lock"
                assert not older.done()
            finally:
                release.set()
            assert newer.result(timeout=5).status_code == 200
            assert older.result(timeout=5).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", pause_after_lock)
    assert watermark(factory, thread) == (STAMP, m2, None, None)
    assert unread(client, owner, thread) == 0


def test_t16_tc03_invalid_and_foreign_ack_preserve_state(inbox):
    client, factory, (owner_id, owner), (renter_id, _), (outsider_id, outsider) = inbox
    thread, sibling, foreign = [
        seed_threads(factory, actor, renter_id)[0] for actor in (owner_id, owner_id, outsider_id)
    ]
    first, last = seed_messages(factory, thread, renter_id, 2)
    (sibling_msg,) = seed_messages(factory, sibling, renter_id, 1, first=3)
    (foreign_msg,) = seed_messages(factory, foreign, renter_id, 1, first=4)
    assert read(client, owner, thread, first).status_code == 200
    for candidate in (sibling_msg, foreign_msg, key(999), "", "x" * 37, None):
        assert read(client, owner, thread, candidate).status_code == 422
    assert client.put(f"{INBOX}/{thread}/read", headers=owner, json={}).status_code == 422
    assert (
        client.put(
            f"{INBOX}/{thread}/read", headers={**owner, "Content-Type": "application/json"}, content="null"
        ).status_code
        == 422
    )
    assert read(client, outsider, thread, last).status_code == 404
    assert read(client, owner, foreign, foreign_msg).status_code == 404
    assert watermark(factory, thread) == (STAMP, first, None, None)
    assert unread(client, owner, thread) == 1


def test_t16_tc04_static_keyset_pages_cover_all_ties(inbox):
    client, factory, (owner_id, owner), (renter_id, _), (outsider_id, outsider) = inbox
    threads = seed_threads(factory, owner_id, renter_id, 120)
    target = threads[0]
    (foreign,) = seed_threads(factory, outsider_id, renter_id)
    messages = seed_messages(factory, target, renter_id, 130, timestamps_tied=False)
    (foreign_msg,) = seed_messages(factory, foreign, renter_id, 1, first=131)

    cursor = None
    seen = []
    for expected_size in (50, 50, 20):
        params = {"limit": 50, "cursor": cursor} if cursor is not None else {}
        response = client.get(INBOX, headers=owner, params=params)
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page["items"]) == expected_size
        assert foreign not in [item["id"] for item in page["items"]]
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if expected_size == 50:
            payload = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
            last = page["items"][-1]
            stamp = datetime.fromisoformat(last["updated_at"].removesuffix("Z"))
            assert payload == f"v1|{stamp.isoformat(timespec='microseconds')}Z|{last['id']}"
            # Even a valid cursor from another account does not authorize rows.
            other = client.get(INBOX, headers=outsider, params={"cursor": cursor}).json()
            assert all(item["id"] == foreign for item in other["items"])
    assert seen == threads[::-1]
    assert cursor is None

    before = None
    seen = []
    for expected_size in (50, 50, 30):
        params = {"before": before} if before is not None else {}
        response = client.get(f"{INBOX}/{target}", headers=owner, params=params)
        assert response.status_code == 200, response.text
        page = response.json()
        ids = [item["id"] for item in page["items"]]
        assert len(ids) == expected_size
        seen[0:0] = ids
        before = page["next_cursor"]
        assert before == (ids[0] if expected_size == 50 else None)
    assert seen == messages
    assert (
        client.get(f"{INBOX}/{target}", headers=owner, params={"limit": 1}).json()["items"][0]["id"]
        == messages[-1]
    )
    for invalid in (foreign_msg, key(999), "", "x" * 37):
        assert client.get(f"{INBOX}/{target}", headers=owner, params={"before": invalid}).status_code == 422
    for url in (INBOX, f"{INBOX}/{target}"):
        for invalid in (0, 51, "all", "1.5"):
            assert client.get(url, headers=owner, params={"limit": invalid}).status_code == 422
    for payload in (
        f"v2|2026-01-01T12:00:00.123456Z|{target}",
        f"v1|2026-01-01T13:00:00.123456+01:00|{target}",
        f"v1|2026-01-01T12:00:00Z|{target}",
        "v1|2026-01-01T12:00:00.123456Z|invalid-id",
        f"v1|2026-01-01T12:00:00.123456Z|{target}|extra",
    ):
        token = base64.urlsafe_b64encode(payload.encode("ascii")).decode("ascii").rstrip("=")
        assert client.get(INBOX, headers=owner, params={"cursor": token}).status_code == 422
    for invalid in ("", "?", "AA==", "a" * 129):
        assert client.get(INBOX, headers=owner, params={"cursor": invalid}).status_code == 422


def test_t16_tc05_start_and_reply_retry_conflict_preserve_original(inbox, auth_client):
    client, factory, (owner_id, owner), (renter_id, renter), (_, outsider) = inbox
    advert = publish(client, owner, draft(client, owner))
    unverified = account(auth_client, "t16-unverified", verified=False)[1]
    url = f"/v1/adverts/{advert['id']}/conversations"
    payload = {"client_id": "idempotent-start", "body": "Still available?"}
    started = client.post(url, headers=renter, json=payload)
    assert started.status_code == 201, started.text
    assert client.post(url, headers=renter, json=payload).json() == started.json()
    thread = started.json()["id"]
    assert client.post(url, headers=unverified, json=payload).status_code == 403
    assert client.post(url, headers=renter, json={**payload, "body": "Different"}).status_code == 409

    first = send(client, owner, thread, "idempotent-reply")
    assert first.status_code == 201
    assert send(client, owner, thread, "idempotent-reply", " <p>Synthetic reply</p> ").json() == first.json()
    conflict = send(client, owner, thread, "idempotent-reply", "Different")
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Client message ID already used with different text"}
    assert send(client, outsider, thread, "idempotent-reply").status_code == 404
    assert send(client, unverified, thread, "idempotent-reply").status_code == 403
    assert client.put(f"{INBOX}/{thread}/block", headers=owner, json={"blocked": True}).status_code == 200
    assert send(client, owner, thread, "idempotent-reply").json() == first.json()
    assert send(client, renter, thread, "new-blocked-reply").status_code == 403
    assert client.put(f"{INBOX}/{thread}/block", headers=renter, json={"blocked": False}).status_code == 403
    with factory() as session:
        assert [c.id for c in session.scalars(select(Conversation))] == [thread]
        assert [m.body for m in session.scalars(select(Message).order_by(Message.created_at))] == [
            payload["body"],
            first.json()["body"],
        ]
        assert session.get(Conversation, thread).renter_id == renter_id
        assert session.get(Conversation, thread).owner_id == owner_id


def test_t16_tc06_inbox_has_two_selects_for_one_or_fifty_threads(inbox, engine):
    client, factory, (owner_id, owner), (renter_id, renter), (_, outsider) = inbox
    threads = seed_threads(factory, owner_id, renter_id, 50)
    seed_messages(factory, threads[-1], renter_id, 1)
    block = client.put(f"{INBOX}/{threads[-1]}/block", headers=owner, json={"blocked": True})
    assert block.status_code == 200
    assert send(client, renter, threads[-1], "blocked-attempt").status_code == 403
    statements = []

    def count_selects(_conn, _cursor, sql, _parameters, _context, _many):
        if sql.startswith("SELECT"):
            statements.append(sql)

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        for size in (1, 50):
            statements.clear()
            response = client.get(INBOX, headers=owner, params={"limit": size})
            assert response.status_code == 200, response.text
            assert len(response.json()["items"]) == size
            assert len(statements) == 2, statements
            assert response.json()["items"][0] == {
                "id": threads[-1],
                "title": "Synthetic apartment 49",
                "listing_id": None,
                "unread_count": 1,
                "blocked": True,
                "can_unblock": True,
                "updated_at": STAMP.isoformat() + "Z",
            }
        statements.clear()
        assert client.get(INBOX, headers=outsider).json() == {"items": [], "next_cursor": None}
        assert len(statements) == 1
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)


def test_t16_send_limit_is_shared_across_threads_and_retries_are_free(inbox, monkeypatch):
    client, factory, (owner_id, owner), (renter_id, _), _ = inbox
    first, second = seed_threads(factory, owner_id, renter_id, 2)
    seed_messages(factory, first, owner_id, 20)
    monkeypatch.setattr(marketplace, "now", lambda: STAMP + timedelta(seconds=1))
    assert send(client, owner, second, "send-after-twenty").status_code == 429
    replay = send(client, owner, first, "seed-message-20", "Synthetic message 20")
    assert replay.status_code == 201
    assert replay.json()["id"] == key(20)


def seed_legacy(connection):
    # Reflect the pre-010 tables so inserts cannot accidentally depend on new columns.
    metadata = MetaData()

    def insert(table, **values):
        connection.execute(Table(table, metadata, autoload_with=connection).insert().values(**values))

    insert(
        "advertiser_profiles", user_id=key(1), name="Keep", kind="private", description="", updated_at=STAMP
    )
    insert(
        "adverts",
        id=key(2),
        user_id=key(1),
        draft={"title": "Keep"},
        state="draft",
        version=2,
        created_at=STAMP,
        updated_at=STAMP,
    )
    insert(
        "conversations",
        id=key(3),
        advert_id=key(2),
        renter_id=key(4),
        owner_id=key(1),
        renter_read_at=None,
        owner_read_at=STAMP,
        blocked_by=key(1),
        created_at=STAMP,
        updated_at=STAMP,
    )
    insert(
        "messages",
        id=key(5),
        conversation_id=key(3),
        sender_id=key(4),
        client_id="legacy-message",
        body="Keep this message",
        created_at=STAMP,
    )


def assert_legacy_upgrade(engine):
    with sessionmaker(engine)() as session:
        row = session.get(Conversation, key(3))
        assert (
            row.owner_read_at,
            row.owner_read_message_id,
            row.renter_read_at,
            row.renter_read_message_id,
        ) == (STAMP, None, None, None)
        assert (row.blocked_by, row.updated_at, row.advert_id) == (key(1), STAMP, key(2))
        message = session.get(Message, key(5))
        assert (message.body, message.client_id, message.created_at) == (
            "Keep this message",
            "legacy-message",
            STAMP,
        )
        assert (
            marketplace.conversations(user_id=key(1), session=session, cursor=None, limit=50)["items"][0][
                "unread_count"
            ]
            == 0
        )
        assert marketplace.read_conversation(
            key(3), marketplace.ReadMessageBody(last_message_id=key(5)), user_id=key(1), session=session
        ) == {"read": True}
        assert session.get(Conversation, key(3)).owner_read_message_id is None
    inspector = inspect(engine)
    assert {"ix_conversations_renter_order", "ix_conversations_owner_order"} <= {
        index["name"] for index in inspector.get_indexes("conversations")
    }
    assert "ix_message_thread_order" in {index["name"] for index in inspector.get_indexes("messages")}


def test_t16_upgrade_tracked_sqlite_keeps_rows_and_hook_checksums(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'upgrade.db'}")
    try:
        Base.metadata.create_all(engine)
        upgrade_local(engine)
        ledger = text("SELECT version, checksum FROM realtoruch_local_migrations ORDER BY version")
        with engine.begin() as connection:
            # Reconstruct a tracked pre-010 schema with the original hook entries.
            connection.execute(text("DELETE FROM realtoruch_local_migrations WHERE version >= '010'"))
            before = dict(connection.execute(ledger).all())
            for index in (
                "ix_conversations_renter_order",
                "ix_conversations_owner_order",
                "ix_message_thread_order",
            ):
                connection.execute(text(f"DROP INDEX {index}"))
            for column in ("renter_read_message_id", "owner_read_message_id"):
                connection.execute(text(f"ALTER TABLE conversations DROP COLUMN {column}"))
            seed_legacy(connection)
        Base.metadata.create_all(engine)
        upgrade_local(engine)
        upgrade_local(engine)
        with engine.connect() as connection:
            after = dict(connection.execute(ledger).all())
            assert set(after) - set(before) == {"010"}
            assert {version: after[version] for version in before} == before
        assert_legacy_upgrade(engine)
    finally:
        engine.dispose()


def test_t16_upgrade_tracked_postgres_keeps_rows_and_sql_checksums(tmp_path):
    registry = load_registry()
    registry["rentals"] = [entry for entry in registry["rentals"] if entry["version"] < "010"]
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(registry))
    ledger = text(
        "SELECT version, checksum FROM realtoruch_migrations WHERE database_name='rentals' ORDER BY version"
    )
    with postgres_schema() as engine:
        with engine.begin() as connection:
            apply_postgres(connection, "rentals", baseline)
            assert "owner_read_message_id" not in {
                col["name"] for col in inspect(connection).get_columns("conversations")
            }
            before = dict(connection.execute(ledger).all())
            seed_legacy(connection)
        with engine.begin() as connection:
            apply_postgres(connection, "rentals")
            apply_postgres(connection, "rentals")
            after = dict(connection.execute(ledger).all())
            assert "010" in after and "010" not in before
            assert {version: after[version] for version in before} == before
        assert_legacy_upgrade(engine)
