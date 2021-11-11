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
from realtoruch.migrations import load_registry
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


@pytest.mark.skipif(not os.getenv("TEST_ELASTICSEARCH_URL"), reason="Requires isolated Elasticsearch")
def test_versioned_interleaving_and_tombstone(pg_engine, record, monkeypatch):
    import threading
    from realtoruch import indexing
    from realtoruch.models import SearchRevision
    from realtoruch.settings import get_settings
    from realtoruch.search import es_client

    alias = "verify_" + os.environ.get("VERIFY_RUN_ID", "test").replace("-", "_")
    monkeypatch.setattr(get_settings(), "elasticsearch_url", os.environ["TEST_ELASTICSEARCH_URL"])
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    with factory.begin() as session:
        listing_id = ingest(session, record)["listing_id"]
    started, release = threading.Event(), threading.Event()
    real_send = indexing.send_bulk
    def pause(client, docs, index):
        started.set()
        assert release.wait(15)
        return real_send(client, docs, index)
    monkeypatch.setattr(indexing, "send_bulk", pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(indexing.index_once, factory, es_client, alias)
        assert started.wait(10)
        with factory.begin() as session:
            ingest(session, record.model_copy(update={"rent_pln": 4200, "status": "inactive", "observed_at": record.observed_at + timedelta(minutes=1)}))
        monkeypatch.setattr(indexing, "send_bulk", real_send)
        assert pool.submit(indexing.index_once, factory, es_client, alias).result(timeout=15) == 1
        release.set()
        first.result(timeout=15)
    with factory() as session:
        revision = session.get(SearchRevision, listing_id).revision
        assert not session.scalars(select(Outbox).where(Outbox.delivered_at.is_(None))).all()
    with es_client() as client:
        doc = client.get(f"/{alias}/_doc/{listing_id}").json()
        assert doc["_version"] == revision
        assert doc["_source"]["rent_pln"] == 4200
        assert doc["_source"]["status"] == "inactive"
        old = dict(doc["_source"], rent_pln=4500, status="active")
        assert real_send(client, [(listing_id, revision - 1, old), (listing_id, revision, old)], alias)[listing_id] == (409, True)
        doc = client.get(f"/{alias}/_doc/{listing_id}").json()
        assert doc["_source"]["status"] == "inactive" and doc["_source"]["rent_pln"] == 4200

    # Separately release the older request before any new indexer runs: its
    # acknowledgement must leave the newer revision pending for the next pass.
    with factory.begin() as session:
        ingest(session, record.model_copy(update={"rent_pln": 4100, "observed_at": record.observed_at + timedelta(minutes=2)}))
    started.clear()
    release.clear()
    monkeypatch.setattr(indexing, "send_bulk", pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(indexing.index_once, factory, es_client, alias)
        assert started.wait(10)
        with factory.begin() as session:
            ingest(session, record.model_copy(update={"rent_pln": 4000, "observed_at": record.observed_at + timedelta(minutes=3)}))
        release.set()
        assert first.result(timeout=15) == 0
    with factory() as session:
        assert session.scalars(select(Outbox).where(Outbox.delivered_at.is_(None))).all()
    monkeypatch.setattr(indexing, "send_bulk", real_send)
    assert indexing.index_once(factory, es_client, alias) == 1
    with es_client() as client:
        assert client.get(f"/{alias}/_doc/{listing_id}").json()["_source"]["rent_pln"] == 4000


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
        assert connection.scalar(text("SELECT count(*) FROM realtoruch_migrations WHERE database_name='rentals'")) == len(load_registry()['rentals'])



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
            connection.execute(text("""INSERT INTO listings (id, title, description, city, district, region,
                address, area_m2, rooms, rent_pln, advertiser_type, property_type, status,
                amenities, images, risk_flags, risk_score, is_demo, first_seen, last_seen, updated_at)
                VALUES ('legacy-home', 'Keep', '', 'Warszawa', '', '', 'Street', 54, 2, 4200,
                'private', 'apartment', 'active', '[]', '[]', '[]', 0, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""))
        with pg_engine.begin() as connection:
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            apply_postgres(connection, 'rentals')
            apply_postgres(connection, 'rentals')
            assert connection.scalar(text("SELECT id FROM event_receipts")) == 'keep'
            assert connection.scalar(text("SELECT rent_pln FROM listings WHERE id='legacy-home'")) == 4200
            assert connection.scalar(text("SELECT revision FROM search_revisions WHERE listing_id='legacy-home'")) == 1
            assert connection.scalar(text("SELECT count(*) FROM outbox WHERE listing_id='legacy-home' AND delivered_at IS NULL")) == 1
            assert connection.scalar(text("SELECT count(*) FROM realtoruch_migrations WHERE database_name='rentals'")) == len(load_registry()['rentals'])
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


@pytest.mark.skipif(not os.getenv('TEST_ELASTICSEARCH_URL'), reason='Requires isolated Elasticsearch')
def test_rebuild_failure_retry_and_concurrent_writes(pg_engine, record, monkeypatch):
    import threading
    from realtoruch import indexing
    from realtoruch.search import es_client
    from realtoruch.settings import get_settings
    alias = 'rebuild_' + os.environ.get('VERIFY_RUN_ID', 'test').replace('-', '_')
    monkeypatch.setattr(get_settings(), 'elasticsearch_url', os.environ['TEST_ELASTICSEARCH_URL'])
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    with factory.begin() as session:
        home = ingest(session, record)['listing_id']
        ingest(session, record.model_copy(update={'external_id': 'second', 'address': 'Second street', 'area_m2': 100}))
    indexing.index_once(factory, es_client, alias)
    with es_client() as client:
        old = client.get(f'/_alias/{alias}').json()
    send = indexing.send_bulk
    def fail(client, docs, index):
        send(client, docs[:1], index)
        raise RuntimeError('injected candidate failure')
    monkeypatch.setattr(indexing, 'send_bulk', fail)
    with pytest.raises(RuntimeError, match='injected'):
        indexing.rebuild(factory, es_client, alias)
    with es_client() as client:
        assert client.get(f'/_alias/{alias}').json() == old
        assert client.get(f'/{alias}/_doc/{home}').status_code == 200
    started, release = threading.Event(), threading.Event()
    def wait(client, docs, index):
        result = send(client, docs, index)
        started.set()
        assert release.wait(15)
        return result
    monkeypatch.setattr(indexing, 'send_bulk', wait)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rebuilding = pool.submit(indexing.rebuild, factory, es_client, alias)
        assert started.wait(10)
        with factory.begin() as session:
            ingest(session, record.model_copy(update={'rent_pln': 4200, 'observed_at': record.observed_at + timedelta(minutes=1)}))
        monkeypatch.setattr(indexing, 'send_bulk', send)
        indexing_future = pool.submit(indexing.index_once, factory, es_client, alias)
        assert not indexing_future.done()
        release.set()
        rebuilding.result(timeout=15)
        indexing_future.result(timeout=15)
    with es_client() as client:
        assert client.get(f'/{alias}/_doc/{home}').json()['_source']['rent_pln'] == 4200
        assert client.get(f'/_alias/{alias}').json() != old
        active_index = next(iter(client.get(f'/_alias/{alias}').json()))
        client.delete(f'/{active_index}').raise_for_status()
    indexing.rebuild(factory, es_client, alias)
    with es_client() as client:
        assert client.get(f'/{alias}/_doc/{home}').json()['_source']['rent_pln'] == 4200


@pytest.mark.skipif(not os.getenv('TEST_ELASTICSEARCH_URL'), reason='Requires isolated Elasticsearch')
def test_hundred_changed_homes_converge(pg_engine, record, monkeypatch):
    from realtoruch import indexing
    from realtoruch.models import Listing, SearchRevision
    from realtoruch.search import es_client
    from realtoruch.settings import get_settings
    alias = 'batch_' + os.environ.get('VERIFY_RUN_ID', 'test').replace('-', '_')
    monkeypatch.setattr(get_settings(), 'elasticsearch_url', os.environ['TEST_ELASTICSEARCH_URL'])
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    with factory.begin() as session:
        ids = []
        for i in range(100):
            raw = record.model_copy(update={'external_id': str(i), 'address': f'Address {i}', 'area_m2': 50 + i * 4})
            ids.append(ingest(session, raw)['listing_id'])
    assert len(set(ids)) == 100
    with factory.begin() as session:
        for home in session.scalars(select(Listing).where(Listing.id.in_(ids))):
            home.rent_pln = 4200
            indexing.queue_listing(session, home.id)
    start = time.monotonic()
    with factory() as session:
        versions = dict(session.execute(select(SearchRevision.listing_id, SearchRevision.revision)).all())
    deadline = start + 30
    while time.monotonic() < deadline:
        indexing.index_once(factory, es_client, alias)
        with es_client() as client:
            client.post(f'/{alias}/_refresh').raise_for_status()
            result = client.post(f'/{alias}/_search', json={'size': 100, 'version': True, 'query': {'match_all': {}}})
            result.raise_for_status()
            hits = result.json()['hits']['hits']
            if len(hits) == 100 and all(hit['_version'] == versions[hit['_id']] and hit['_source']['rent_pln'] == 4200 for hit in hits):
                elapsed = time.monotonic() - start
                print(f'T08_CONVERGENCE_SECONDS={elapsed:.6f} sample_count=100 refresh=explicit poll=immediate')
                Path(os.environ.get('TMPDIR', '/tmp'), 't08-convergence.json').write_text(
                    __import__('json').dumps({'elapsed_seconds': elapsed, 'count': 100,
                        'refresh': 'explicit per poll', 'poll_interval_seconds': 0.2}))
                assert elapsed <= 30
                return
        time.sleep(0.2)
    pytest.fail(f'100 changes did not converge within 30 seconds; elapsed={time.monotonic()-start:.3f}')


@pytest.mark.skipif(not os.getenv('TEST_ELASTICSEARCH_URL'), reason='Requires isolated Elasticsearch')
def test_profile_change_reindexes_public_only(pg_engine, record, monkeypatch):
    import json
    from realtoruch import indexing
    from realtoruch.marketplace import ProfileBody, save_profile
    from realtoruch.models import Advert, AdvertiserProfile
    from realtoruch.search import es_client
    from realtoruch.settings import get_settings
    alias = 'profile_' + os.environ.get('VERIFY_RUN_ID', 'test').replace('-', '_')
    monkeypatch.setattr(get_settings(), 'elasticsearch_url', os.environ['TEST_ELASTICSEARCH_URL'])
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    with factory.begin() as session:
        home = ingest(session, record)['listing_id']
        session.add(AdvertiserProfile(user_id='owner', name='Before', kind='private', description='profile'))
        session.flush()
        session.add(Advert(id='profile-advert', user_id='owner', listing_id=home, state='published', draft={'secret': 'draft-canary'}))
    indexing.index_once(factory, es_client, alias)
    with es_client() as client:
        before = client.get(f'/{alias}/_doc/{home}').json()['_version']
    with factory() as session:
        save_profile(ProfileBody(name='After', kind='private', description='profile'), claims={'sub': 'owner'}, session=session)
    indexing.index_once(factory, es_client, alias)
    with es_client() as client:
        result = client.get(f'/{alias}/_doc/{home}').json()
        assert result['_version'] > before
        payload = json.dumps(result['_source'])
        assert 'After' in payload
        for secret in ('draft-canary', '700100101', 'phone_hash', 'email', 'password'):
            assert secret not in payload
