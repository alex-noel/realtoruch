"""Opt-in real PostgreSQL/Elasticsearch tests; never use a production database.

TEST_POSTGRES_URL must point to a disposable test instance. Each test owns a
unique schema. TEST_ELASTICSEARCH_URL must point to an isolated test cluster.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from test_rental_journey import FILTERS
from test_rental_journey import test_complete_rental_journey as _journey

from realtoruch import worker
from realtoruch.ingest import ingest
from realtoruch.models import Outbox, now
from realtoruch.schemas import SearchFilters
from realtoruch.search import build_query

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"), reason="Requires an isolated PostgreSQL test instance"
)


@pytest.fixture
def pg_engine():
    schema = "test_" + uuid4().hex
    admin = create_engine(os.environ["TEST_POSTGRES_URL"], isolation_level="AUTOCOMMIT")
    root = Path(__file__).resolve().parents[2]
    with admin.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(text(f"SET search_path TO {schema}"))
        from realtoruch.migrations import apply_postgres
        apply_postgres(connection, "rentals")
    engine = create_engine(
        os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_rental_journey_on_versioned_postgres_schema(pg_engine, record, auth_client):
    from fastapi.testclient import TestClient

    from realtoruch.api import app
    from realtoruch.db import get_session
    from realtoruch.auth import validate_claims

    with Session(pg_engine, expire_on_commit=False) as session:
        app.state.validate_claims = validate_claims
        app.dependency_overrides[get_session] = lambda: session
        try:
            with TestClient(app) as client:
                _journey(session, record, client, auth_client)
        finally:
            app.dependency_overrides.clear()
            del app.state.validate_claims


@pytest.mark.skipif(
    not os.getenv("TEST_ELASTICSEARCH_URL"), reason="Requires an isolated Elasticsearch test cluster"
)
def test_index_update_is_not_lost_during_concurrent_ingestion(pg_engine, record, monkeypatch):
    from test_rental_journey import home

    from realtoruch.settings import get_settings

    monkeypatch.setattr(worker, "INDEX", "verify_" + os.environ.get("VERIFY_RUN_ID", "test").replace("-", "_"))

    monkeypatch.setattr(get_settings(), "elasticsearch_url", os.environ["TEST_ELASTICSEARCH_URL"])
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    monkeypatch.setattr(worker, "Session", factory)
    original = home(record)
    with factory.begin() as session:
        listing_id = ingest(session, original)["listing_id"]
    with ThreadPoolExecutor(max_workers=1) as pool, factory() as indexing:
        pending = indexing.scalar(select(Outbox).with_for_update())

        def update_home():
            with factory.begin() as session:
                ingest(
                    session,
                    original.model_copy(
                        update={"rent_pln": 4200, "observed_at": original.observed_at + timedelta(minutes=1)}
                    ),
                )

        update = pool.submit(update_home)
        deadline = time.monotonic() + 5
        blocked = False
        while time.monotonic() < deadline:
            with pg_engine.connect() as inspector:
                blocked = bool(
                    inspector.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND query LIKE '%outbox%'"
                        )
                    )
                )
            if blocked:
                break
            time.sleep(0.02)
        assert blocked, "Ingestion must wait until the prior search write is acknowledged"
        pending.delivered_at = now()
        indexing.commit()
        update.result(timeout=10)
    with factory() as session:
        assert len(session.scalars(select(Outbox).where(Outbox.delivered_at.is_(None))).all()) == 1
    assert worker.index_once() == 1
    with worker.es_client() as client:
        client.post(f"/{worker.INDEX}/_refresh").raise_for_status()
        response = client.post(f"/{worker.INDEX}/_search", json=build_query(SearchFilters(**FILTERS)))
        response.raise_for_status()
        matches = {hit["_id"]: hit["_source"] for hit in response.json()["hits"]["hits"]}
        assert matches[listing_id]["rent_pln"] == 4200
    with factory.begin() as session:
        ingest(
            session,
            original.model_copy(
                update={"status": "inactive", "observed_at": original.observed_at + timedelta(minutes=2)}
            ),
        )
    worker.index_once()
    with worker.es_client() as client:
        client.post(f"/{worker.INDEX}/_refresh").raise_for_status()
        response = client.post(f"/{worker.INDEX}/_search", json=build_query(SearchFilters(**FILTERS)))
        response.raise_for_status()
        assert listing_id not in {hit["_id"] for hit in response.json()["hits"]["hits"]}


def test_marketplace_on_versioned_postgres_schema(pg_engine, auth_client):
    from fastapi.testclient import TestClient
    from realtoruch.api import app
    from realtoruch.auth import validate_claims
    from realtoruch.db import get_session
    from test_marketplace import test_draft_publish_edit_withdraw_and_relist_identity as flow

    with Session(pg_engine, expire_on_commit=False) as session:
        app.dependency_overrides[get_session] = lambda: session
        app.state.validate_claims = validate_claims
        try:
            with TestClient(app) as client:
                flow(client, auth_client, session)
        finally:
            app.dependency_overrides.clear()
            del app.state.validate_claims


def test_identity_review_on_versioned_postgres_schema(pg_engine, auth_client, record, monkeypatch):
    from fastapi.testclient import TestClient
    from realtoruch.api import app
    from realtoruch.auth import validate_claims
    from realtoruch.db import get_session
    from test_identity_review import test_manual_merge_preserves_favorites_seen_history_and_old_links as flow

    with Session(pg_engine, expire_on_commit=False) as session:
        app.dependency_overrides[get_session] = lambda: session
        app.state.validate_claims = validate_claims
        try:
            with TestClient(app) as client:
                flow(client, auth_client, session, record, monkeypatch)
        finally:
            app.dependency_overrides.clear()
            del app.state.validate_claims


def test_auth_recovery_on_versioned_postgres_schema(pg_engine, monkeypatch):
    from fastapi.testclient import TestClient
    from realtoruch import auth, auth_jobs
    from test_accounts import test_verification_reset_mail_retry_and_single_use as flow

    from realtoruch.migrations import apply_postgres
    with pg_engine.begin() as connection:
        apply_postgres(connection, "auth")
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    monkeypatch.setattr(auth, "auth_engine", pg_engine)
    monkeypatch.setattr(auth, "AuthSession", factory)
    monkeypatch.setattr(auth_jobs, "AuthSession", factory)
    # The reused behavioral test imports its factory directly.
    import test_accounts

    monkeypatch.setattr(test_accounts, "AuthSession", factory)
    with TestClient(auth.app) as client:
        flow(client, monkeypatch)


def test_registry_rejects_checksum_drift_and_rolls_back(pg_engine):
    from realtoruch.migrations import apply_postgres
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("UPDATE realtoruch_migrations SET checksum='bad' WHERE database_name='rentals' AND version='001'"))
        with pytest.raises(ValueError, match='checksum'):
            apply_postgres(connection, 'rentals')
        transaction.rollback()
    with pg_engine.begin() as connection:
        apply_postgres(connection, 'rentals')
        assert connection.scalar(text("SELECT count(*) FROM realtoruch_migrations WHERE database_name='rentals'")) == 4



def test_registry_postgres_transaction_rolls_back(pg_engine):
    from realtoruch.migrations import apply_postgres
    schema = 'rollback_' + uuid4().hex
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(f'CREATE SCHEMA {schema}'))
        connection.execute(text(f'SET LOCAL search_path TO {schema}'))
        apply_postgres(connection, 'rentals')
        transaction.rollback()
        assert connection.scalar(text('SELECT count(*) FROM pg_namespace WHERE nspname=:schema'), {'schema': schema}) == 0


def test_registry_refuses_untracked_existing_schema(pg_engine):
    from realtoruch.migrations import apply_postgres
    schema = 'untracked_' + uuid4().hex
    with pg_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
        connection.execute(text(f'CREATE TABLE {schema}.event_receipts (id text PRIMARY KEY)'))
        connection.execute(text(f"INSERT INTO {schema}.event_receipts VALUES ('keep')"))
    try:
        with pytest.raises(ValueError, match="Untracked PostgreSQL schema"):
            with pg_engine.begin() as connection:
                connection.execute(text(f'SET LOCAL search_path TO {schema}'))
                apply_postgres(connection, 'rentals')
        with pg_engine.connect() as connection:
            assert connection.scalar(text(f'SELECT id FROM {schema}.event_receipts')) == 'keep'
            assert connection.scalar(text('SELECT to_regclass(:name)'), {'name': schema + '.realtoruch_migrations'}) is None
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))


def test_registry_upgrades_tracked_baseline_preserving_rows(pg_engine, tmp_path):
    import json
    from realtoruch.migrations import apply_postgres, load_registry

    schema = 'upgrade_' + uuid4().hex
    registry = load_registry()
    registry['rentals'] = registry['rentals'][:1]
    baseline = tmp_path / 'baseline.json'
    baseline.write_text(json.dumps(registry))
    try:
        with pg_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            apply_postgres(connection, 'rentals', baseline)
            connection.execute(text("INSERT INTO event_receipts VALUES ('keep', CURRENT_TIMESTAMP)"))
        with pg_engine.begin() as connection:
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            apply_postgres(connection, 'rentals')
            apply_postgres(connection, 'rentals')
            assert connection.scalar(text("SELECT id FROM event_receipts")) == 'keep'
            assert connection.scalar(text("SELECT count(*) FROM realtoruch_migrations WHERE database_name='rentals'")) == 4
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))


def test_t03_postgres_claim_and_takeover_fence(pg_engine, record):
    from threading import Barrier
    from sqlalchemy import func
    from realtoruch.collection_health import LeaseLost, claim, finish, guard
    from realtoruch.models import CollectionRun, EventReceipt, SourcePollState

    factory = sessionmaker(pg_engine, expire_on_commit=False)
    start = Barrier(2)

    def contender(city):
        start.wait(timeout=10)
        return claim(factory, {"name": "otodom", "city": city})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(contender, ["Kraków", "Warszawa"]))
    assert sum(bool(lease) for lease, _ in results) == 1
    assert [deferred["reason"] for _, deferred in results if deferred] == ["already_running"]
    old = next(lease for lease, _ in results if lease)
    # Simulate a completed in-flight response, then expire and replace its owner.
    response_ready, resumed = Barrier(2), Barrier(2)

    def old_response():
        response_ready.wait(timeout=10)
        resumed.wait(timeout=10)
        with pytest.raises(LeaseLost), factory.begin() as db:
            guard(db, "otodom", old)
            ingest(db, record)
        finish(factory, "otodom", old, {"status": "succeeded", "errors": []})

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(old_response)
        response_ready.wait(timeout=10)
        with factory.begin() as db:
            db.get(SourcePollState, "otodom").lease_until = now() - timedelta(seconds=1)
        new, _ = claim(factory, {"name": "otodom", "city": "Warszawa"})
        with factory.begin() as db:
            state = db.get(SourcePollState, "otodom")
            state.failures, state.retry_after, state.last_success_at = 2, now() + timedelta(hours=1), now()
            expected = (state.lease_id, state.lease_until, state.failures, state.retry_after, state.last_success_at)
        resumed.wait(timeout=10)
        pending.result(timeout=10)
    with factory() as db:
        state = db.get(SourcePollState, "otodom")
        assert new == state.lease_id
        assert (state.lease_id, state.lease_until, state.failures, state.retry_after, state.last_success_at) == expected
        assert db.get(CollectionRun, old).status == "interrupted"
        assert db.scalar(select(func.count()).select_from(EventReceipt)) == 0


def test_t03_postgres_replay_after_interruption(pg_engine, record):
    from sqlalchemy import func
    from realtoruch.collection_health import claim, guard
    from realtoruch.models import AlertEvent, EventReceipt, Observation, SourceListing, SourcePollState

    factory = sessionmaker(pg_engine, expire_on_commit=False)
    old, _ = claim(factory, {"name": "otodom"})
    with factory.begin() as db:
        guard(db, "otodom", old)
        ingest(db, record)
    with factory.begin() as db:
        db.get(SourcePollState, "otodom").lease_until = now() - timedelta(seconds=1)
    new, _ = claim(factory, {"name": "otodom"})
    with factory() as db:
        before = [db.scalar(select(func.count()).select_from(m)) for m in (EventReceipt, Observation, SourceListing, AlertEvent)]
    with factory.begin() as db:
        guard(db, "otodom", new)
        ingest(db, record)
    with factory() as db:
        after = [db.scalar(select(func.count()).select_from(m)) for m in (EventReceipt, Observation, SourceListing, AlertEvent)]
    assert after == before
