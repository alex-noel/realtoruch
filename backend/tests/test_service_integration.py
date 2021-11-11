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
        for migration in ("001_rentals.sql", "002_alerts.sql", "003_email_alerts.sql"):
            connection.exec_driver_sql((root / "infra/sql" / migration).read_text())
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

    with Session(pg_engine, expire_on_commit=False) as session:
        app.dependency_overrides[get_session] = lambda: session
        try:
            with TestClient(app) as client:
                _journey(session, record, client, auth_client)
        finally:
            app.dependency_overrides.clear()


@pytest.mark.skipif(
    not os.getenv("TEST_ELASTICSEARCH_URL"), reason="Requires an isolated Elasticsearch test cluster"
)
def test_index_update_is_not_lost_during_concurrent_ingestion(pg_engine, record, monkeypatch):
    from test_rental_journey import home

    from realtoruch.settings import get_settings

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
