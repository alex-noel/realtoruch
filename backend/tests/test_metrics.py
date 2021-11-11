"""T26 queue semantics, failure isolation and rendered ingress boundaries."""

import logging
import os
import re
import shutil
import socket
import subprocess
import sys
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from time import monotonic
from uuid import uuid4

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import sessionmaker

from realtoruch import api, auth, auth_jobs, metrics, worker
from realtoruch.auth import AuthBase, AuthJob, User
from realtoruch.db import Base, get_session
from realtoruch.ingest import ingest
from realtoruch.migrations import apply_postgres, upgrade_local
from realtoruch.models import (
    CollectionRun,
    EmailDelivery,
    EmailSubscription,
    Notification,
    Outbox,
    PushDelivery,
    PushSubscription,
    SourcePollState,
    now,
)
from realtoruch.settings import get_settings

ROOT = Path(__file__).resolve().parents[2]
CANARY = "synthetic-private@example.test"
PRIVATE_URL = "https://example.invalid/private-advert?token=synthetic-secret"
PRIVATE_ID = "synthetic-private-job-id"
UNKNOWN_STATE = "synthetic-canary"


@contextmanager
def isolated_sql(kind, tmp_path, *, pool_size=1):
    postgres_url = os.environ.get("TEST_POSTGRES_URL")
    if kind == "postgres" and not postgres_url:
        pytest.skip("requires isolated PostgreSQL")
    admin = create_engine(postgres_url, isolation_level="AUTOCOMMIT") if kind == "postgres" else None
    databases = {}
    try:
        for name, metadata in (("rentals", Base.metadata), ("auth", AuthBase.metadata)):
            schema = "t26_" + uuid4().hex
            if admin:
                with admin.connect() as connection:
                    connection.execute(text(f"CREATE SCHEMA {schema}"))
                engine = create_engine(
                    postgres_url,
                    connect_args={"options": f"-csearch_path={schema}"},
                    pool_size=pool_size,
                    max_overflow=0,
                )
            else:
                engine = create_engine(f"sqlite:///{tmp_path / (name + '.db')}")
            databases[name] = (sessionmaker(engine), schema)
            if admin:
                with engine.begin() as connection:
                    apply_postgres(connection, name)
            else:
                metadata.create_all(engine)
                upgrade_local(engine, name)
        yield databases, admin
    finally:
        for factory, schema in databases.values():
            factory.kw["bind"].dispose()
            if admin:
                with admin.connect() as connection:
                    connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        if admin:
            admin.dispose()


def configure(monkeypatch, databases):
    rentals, _ = databases["rentals"]
    identity, _ = databases["auth"]
    monkeypatch.setattr(api, "Session", rentals)
    monkeypatch.setattr(auth, "AuthSession", identity)
    monkeypatch.setattr(auth_jobs, "AuthSession", identity)
    monkeypatch.setattr(worker, "Session", rentals)

    def request_session():
        with rentals() as session:
            yield session

    monkeypatch.setitem(api.app.dependency_overrides, get_session, request_session)
    monkeypatch.setattr(get_settings(), "email_delivery_mode", "file")
    monkeypatch.setattr(get_settings(), "search_service_url", "")
    return rentals, identity


def samples(client):
    response = client.get("/metrics", headers={"X-Internal-Key": get_settings().internal_api_key})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=")
    result = {
        (sample.name, tuple(sorted(sample.labels.items()))): sample.value
        for family in text_string_to_metric_families(response.text)
        for sample in family.samples
    }
    return result, response.text


def value(samples_, name, **labels):
    return samples_["realtoruch_" + name, tuple(sorted(labels.items()))]


def seed_queues(rentals, identity, record, stamp):
    past = lambda seconds: stamp - timedelta(seconds=seconds)
    future = stamp + timedelta(hours=1)
    scenarios = [
        ("pending", past(60), None, None),
        ("retry", past(80), past(10), PRIVATE_URL),
        ("pending", past(4000), future, None),
        ("retry", future, None, CANARY),
        ("cancelled", past(8000), None, None),
        ("failed", past(9000), None, CANARY),
        ("pending", past(4500), stamp, None),  # equal to now is still leased by claim()
    ]

    with rentals.begin() as session:
        home = ingest(session, record)["listing_id"]
        session.execute(delete(Outbox))
        for due, status, delivered in [
            (past(100), None, None),
            (past(80), 429, None),
            (past(8000), 400, None),
            (past(9000), 413, None),
            (future, None, None),
            (past(5000), 201, past(3000)),
        ]:
            session.add(
                Outbox(listing_id=home, created_at=due, last_index_status=status, delivered_at=delivered)
            )
        session.add(EmailSubscription(user_id=PRIVATE_ID, email=CANARY, unsubscribe_token="private-token"))
        session.add(
            PushSubscription(
                id="synthetic-device-id", user_id=PRIVATE_ID, kind="expo", data={"token": CANARY}
            )
        )
        session.flush()
        for number, (status, due, lease, error) in enumerate(
            scenarios + [("receipt", past(120), None, None)]
        ):
            fields = {"status": status, "next_attempt_at": due, "lease_until": lease, "last_error": error}
            if status != "receipt":
                session.add(EmailDelivery(user_id=PRIVATE_ID, **fields))
            note = Notification(
                id=f"synthetic-note-{number}",
                user_id=PRIVATE_ID,
                listing_id=home,
                kind="new_match",
                title=CANARY,
                dedupe_key=f"t26-{number}",
                rent_pln=4000,
            )
            session.add(note)
            session.flush()
            session.add(
                PushDelivery(notification_id=note.id, subscription_id="synthetic-device-id", **fields)
            )
        session.add(
            SourcePollState(
                source="otodom",
                last_success_at=past(900),
                failures=2,
                lease_id=PRIVATE_ID,
                lease_until=past(5),
                retry_after=future,
            )
        )
        session.add(SourcePollState(source="olx", failures=1))
        session.add(SourcePollState(source=CANARY))
        session.add_all(
            [
                CollectionRun(
                    source="otodom",
                    city=CANARY,
                    status="failed",
                    started_at=past(1500),
                    report={
                        "errors": [
                            {"http_status": 403, "url": PRIVATE_URL},
                            {"http_status": 429, "url": PRIVATE_URL},
                        ]
                    },
                ),
                CollectionRun(source="otodom", status="failed", started_at=past(90000)),
                CollectionRun(source="otodom", status=UNKNOWN_STATE, started_at=past(10)),
                CollectionRun(source=CANARY, status="failed", started_at=past(10)),
            ]
        )

    with identity.begin() as session:
        session.add(User(id=PRIVATE_ID, email=CANARY, password_hash="synthetic-hash", deleted_at=past(5000)))
        for job_kind in ("delete", "verify"):
            for status, due, lease, error in scenarios:
                session.add(
                    AuthJob(
                        kind=job_kind,
                        user_id=PRIVATE_ID,
                        secret=PRIVATE_URL,
                        status=status,
                        next_attempt_at=due,
                        lease_until=lease,
                        last_error=error,
                    )
                )


def exercise_queue_snapshots(sql_kind, tmp_path, record, monkeypatch):
    with isolated_sql(sql_kind, tmp_path) as (databases, _):
        rentals, identity = configure(monkeypatch, databases)
        stamp = now().replace(microsecond=0)
        monkeypatch.setattr(metrics, "now", lambda: stamp)
        seed_queues(rentals, identity, record, stamp)

        rest, rest_text = samples(TestClient(api.app))
        accounts, account_text = samples(TestClient(auth.app))
        for client in (TestClient(api.app), TestClient(auth.app)):
            assert client.get("/metrics").status_code == 403
            assert client.get("/metrics", headers={"X-Internal-Key": CANARY}).status_code == 403
            assert "/metrics" not in client.get("/openapi.json").json()["paths"]
        with monkeypatch.context() as patch:

            def forbidden_checkout():
                raise AssertionError("unauthenticated metrics touched SQL")

            patch.setattr(api, "Session", forbidden_checkout)
            patch.setattr(auth, "AuthSession", forbidden_checkout)
            assert TestClient(api.app).get("/metrics").status_code == 403
            assert TestClient(auth.app).get("/metrics").status_code == 403
        expected = [
            (rest, "search_outbox", [3, 0, 0, 2, 0], 100, 3),
            (rest, "rental_email", [2, 2, 1, 1, 1], 80, 3),
            (rest, "push", [3, 2, 1, 1, 1], 120, 3),
            (accounts, "auth_mail", [2, 2, 1, 1, 1], 80, 3),
            (accounts, "account_erasure", [2, 2, 1, 1, 1], 80, 3),
        ]
        for response, queue, depths, age, errors in expected:
            assert value(response, "metrics_collection_success") == 1
            assert value(response, "queue_oldest_eligible_age_seconds", queue=queue) == age
            assert value(response, "queue_last_error_depth", queue=queue) == errors
            states = ("ready", "leased", "deferred", "failed", "cancelled")
            assert [value(response, "queue_depth", queue=queue, state=state) for state in states] == depths

        assert value(rest, "outbox_pending") == 5
        assert value(rest, "collection_success_known", provider="olx") == 0
        assert value(rest, "collection_success_known", provider="gratka") == 0
        assert value(rest, "collection_success_known", provider="otodom") == 1
        assert value(rest, "collection_last_success_age_seconds", provider="otodom") == 900
        assert value(rest, "collection_consecutive_failures", provider="otodom") == 2
        assert value(rest, "collection_backoff_seconds", provider="otodom") == 3600
        assert value(rest, "collection_lease_expired", provider="otodom") == 1
        assert value(rest, "collection_runs_24h", provider="otodom", state="failed") == 1
        assert value(rest, "collection_runs_24h", provider="otodom", state="other") == 1
        assert 'collection_last_success_age_seconds{provider="olx"}' not in rest_text
        assert "account_erasure" not in rest_text
        assert "search_outbox" not in account_text
        for secret in (
            CANARY,
            PRIVATE_URL,
            PRIVATE_ID,
            "synthetic-note-",
            "Warszawa",
            "private-token",
            UNKNOWN_STATE,
        ):
            assert secret not in rest_text + account_text

        monkeypatch.setattr(get_settings(), "email_delivery_mode", "disabled")
        accounts, _ = samples(TestClient(auth.app))
        assert value(accounts, "auth_mail_enabled") == 0
        assert value(accounts, "queue_depth", queue="auth_mail", state="ready") == 0
        assert value(accounts, "queue_depth", queue="auth_mail", state="deferred") == 3
        assert value(accounts, "queue_depth", queue="account_erasure", state="ready") == 2

        if sql_kind == "postgres":
            exercise_runbook_sql(databases)


def test_t26_sqlite_queue_snapshots(tmp_path, record, monkeypatch):
    exercise_queue_snapshots("sqlite", tmp_path, record, monkeypatch)


def test_t26_postgres_queue_snapshots_and_runbook_diagnostics(tmp_path, record, monkeypatch):
    exercise_queue_snapshots("postgres", tmp_path, record, monkeypatch)


def exercise_runbook_sql(databases):
    queries = runbook_queries()
    assert len(queries) == 6
    roles = ("rentals", "rentals", "rentals", "rentals", "auth", "auth")
    all_rows = []
    for name, query in zip(roles, queries):
        factory, _ = databases[name]
        with factory() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            session.execute(text("SET LOCAL statement_timeout = '2s'"))
            all_rows.append(session.execute(text(query)).all())
    access, leases, indexing, emails, erasure, versions = all_rows
    assert access == [("otodom", "403", 1), ("otodom", "429", 1)]
    assert len(leases) == 1 and leases[0].source == "otodom"
    assert [(r.state, r.rows) for r in indexing] == [("eligible", 3), ("held", 2)]
    assert {r.status: (r.rows, r.leased) for r in emails} == {
        "cancelled": (1, 0),
        "failed": (1, 0),
        "pending": (3, 1),
        "retry": (2, 0),
    }
    assert sum(row.closed_accounts for row in erasure) == 7
    assert ("005",) in versions
    rentals, _ = databases["rentals"]
    with rentals() as session:
        assert ("008",) in session.execute(text(queries[-1])).all()
    assert all(canary not in str(all_rows) for canary in (CANARY, PRIVATE_URL, PRIVATE_ID))


def runbook_queries():
    instructions = (ROOT / "docs/operations/runbooks.md").read_text()
    return re.findall(r"```sql\n(.*?)\n```", instructions, re.DOTALL)


def test_t26_postgres_and_es_index_runbook(tmp_path, record, monkeypatch):
    from realtoruch.indexing import index_once
    from realtoruch.search import es_client

    url = os.environ.get("TEST_ELASTICSEARCH_URL")
    if not url:
        pytest.skip("requires isolated Elasticsearch")
    monkeypatch.setattr(get_settings(), "elasticsearch_url", url)
    alias = "t26-" + uuid4().hex
    with isolated_sql("postgres", tmp_path, pool_size=2) as (databases, _):
        rentals, _ = databases["rentals"]
        with rentals.begin() as session:
            home = ingest(session, record)["listing_id"]
        assert index_once(rentals, es_client, alias) == 1
        with rentals.begin() as session:
            ingest(
                session,
                record.model_copy(
                    update={
                        "rent_pln": record.rent_pln - 100,
                        "observed_at": record.observed_at + timedelta(minutes=1),
                    }
                ),
            )
            # Creation time is an ordering/age field, not a delivery deadline.
            # A future timestamp (including clock skew) must remain visible
            # to diagnostics, just as it remains eligible to index_once.
            session.execute(text("UPDATE outbox SET created_at = timezone('UTC', now()) + interval '1 hour' WHERE delivered_at IS NULL"))
        with rentals() as session:
            (pending,) = session.execute(text(runbook_queries()[2])).all()
            assert pending.state == "eligible" and pending.rows == 1
        monkeypatch.setattr(api, "Session", rentals)
        snapshot, _ = samples(TestClient(api.app))
        assert value(snapshot, "queue_depth", queue="search_outbox", state="ready") == 1
        assert value(snapshot, "queue_depth", queue="search_outbox", state="deferred") == 0
        assert value(snapshot, "queue_oldest_eligible_age_seconds", queue="search_outbox") == 0
        with es_client() as client:
            doc_url = f"/{alias}/_doc/{home}"
            stale = client.get(doc_url, params={"_source": "false"}).raise_for_status().json()
            assert "_source" not in stale and stale["_version"] < pending.highest_waiting_revision
            assert index_once(rentals, es_client, alias) == 1
            current = client.get(doc_url, params={"_source": "false"}).raise_for_status().json()
            assert current["_version"] == pending.highest_waiting_revision
        with rentals() as session:
            assert session.execute(text(runbook_queries()[2])).all() == []


def test_t26_postgres_timeout_does_not_poison_api(tmp_path, record, monkeypatch):
    with isolated_sql("postgres", tmp_path) as (databases, admin):
        rentals, _ = configure(monkeypatch, databases)
        _, schema = databases["rentals"]
        with rentals.begin() as session:
            ingest(session, record)
        client = TestClient(api.app)
        assert value(samples(client)[0], "metrics_collection_success") == 1
        # Separate connection holds the lock until after the scrape and an ordinary read.
        with admin.connect().execution_options(isolation_level="READ COMMITTED") as lock:
            lock.execute(text(f"LOCK TABLE {schema}.outbox IN ACCESS EXCLUSIVE MODE"))
            begin = monotonic()
            snapshot, _ = samples(client)
            elapsed = monotonic() - begin
            assert 0.15 <= elapsed < 2
            assert snapshot == {("realtoruch_metrics_collection_success", ()): 0}
            result = client.get("/v1/listings", params={"city": record.city})
            assert result.status_code == 200 and result.json()["total"] == 1
            # Single-connection pool: the next checkout must not inherit the timeout.
            with rentals() as session:
                assert session.scalar(text("SHOW statement_timeout")) == "0"
        assert value(samples(client)[0], "metrics_collection_success") == 1


def test_t26_postgres_readiness_and_search_fallback(tmp_path, record, monkeypatch):
    from contextlib import nullcontext

    from realtoruch import search

    with isolated_sql("postgres", tmp_path) as (databases, admin):
        rentals, _ = configure(monkeypatch, databases)
        with rentals.begin() as session:
            ingest(session, record)
        with socket.socket() as unused:
            # A bound but non-listening loopback endpoint deterministically refuses ES connections.
            unused.bind(("127.0.0.1", 0))
            monkeypatch.setattr(
                search.settings, "elasticsearch_url", f"http://127.0.0.1:{unused.getsockname()[1]}"
            )
            monkeypatch.setattr(api.settings, "search_service_url", "http://private-search")
            search_client = TestClient(search.app)
            monkeypatch.setattr(
                api.httpx,
                "stream",
                lambda method, url, *, params, headers, timeout: nullcontext(
                    search_client.get("/v1/search", params=params)
                ),
            )
            client = TestClient(api.app)
            assert search_client.get("/readyz").status_code == 503
            assert client.get("/readyz").json() == {"status": "ready"}
            result = client.get("/v1/listings", params={"city": record.city})
            assert result.status_code == 200 and result.json()["degraded"] and result.json()["total"] == 1
        _, schema = databases["rentals"]
        with admin.connect().execution_options(isolation_level="READ COMMITTED") as lock:
            lock.execute(text(f"LOCK TABLE {schema}.listings IN ACCESS EXCLUSIVE MODE"))
            response = client.get("/readyz")
            assert response.status_code == 503 and response.json() == {"status": "unready"}
            assert client.get("/healthz").status_code == 200
            assert TestClient(auth.app).get("/readyz").json() == {"status": "ready"}
        _, schema = databases["auth"]
        with admin.connect().execution_options(isolation_level="READ COMMITTED") as lock:
            lock.execute(text(f"LOCK TABLE {schema}.users IN ACCESS EXCLUSIVE MODE"))
            response = TestClient(auth.app).get("/readyz")
            assert response.status_code == 503 and response.json() == {"status": "unready"}
            assert client.get("/readyz").json() == {"status": "ready"}


def test_t26_sqlite_diagnostic_connection_failure_is_sanitized(monkeypatch):
    def broken_connection():
        raise RuntimeError(PRIVATE_URL)

    monkeypatch.setattr(api, "Session", broken_connection)
    monkeypatch.setattr(auth, "AuthSession", broken_connection)
    for app in (api.app, auth.app):
        client = TestClient(app)
        snapshot, raw = samples(client)
        assert snapshot == {("realtoruch_metrics_collection_success", ()): 0}
        assert PRIVATE_URL not in raw
        response = client.get("/readyz")
        assert response.status_code == 503 and response.json() == {"status": "unready"}
        assert client.get("/healthz").status_code == 200


def test_t26_sqlite_private_worker_logs(tmp_path, monkeypatch, caplog):
    with isolated_sql("sqlite", tmp_path) as (databases, _):
        _, identity = configure(monkeypatch, databases)
        monkeypatch.setattr(
            worker,
            "load_sources",
            lambda: [
                {"name": CANARY, "city": PRIVATE_ID, "enabled": True},
            ],
        )

        class BrokenConnector:
            def __init__(self, config):
                self.report = {"errors": [], "source": config["name"], "city": config["city"]}

            def records(self):
                raise RuntimeError(PRIVATE_URL)

            def note_error(self, exc, stage):
                self.report["errors"].append(
                    {"http_status": 429, "message": str(exc), "url_hash": PRIVATE_ID}
                )

            def close(self):
                pass

        monkeypatch.setattr(worker, "Connector", BrokenConnector)
        with identity.begin() as session:
            session.add(User(id=PRIVATE_ID, email=CANARY, password_hash="synthetic-hash", deleted_at=now()))
            session.add(AuthJob(kind="delete", user_id=PRIVATE_ID, secret=PRIVATE_URL))

        def failed_erase(user_id):
            assert user_id == PRIVATE_ID
            raise RuntimeError(PRIVATE_URL)

        with caplog.at_level(logging.INFO):
            with pytest.raises(worker.CollectionFailed):
                worker.collect()
            assert auth_jobs.process_jobs(limit=1, eraser=failed_erase) == 1
        assert '"provider": "other"' in caplog.text and '"throttled": 1' in caplog.text
        assert '"queue": "account_erasure"' in caplog.text and '"outcome": "retry"' in caplog.text
        assert all(secret not in caplog.text for secret in (CANARY, PRIVATE_URL, PRIVATE_ID))


def test_t26_sqlite_worker_readiness_is_read_only(tmp_path, monkeypatch, caplog):
    with isolated_sql("sqlite", tmp_path) as (databases, _):
        _, identity = configure(monkeypatch, databases)
        settings = get_settings()
        preview = tmp_path / "not-created-by-readiness"
        monkeypatch.setattr(settings, "email_preview_directory", str(preview))
        monkeypatch.setattr(sys, "argv", ["worker", "alerts", "--check-ready"])
        with caplog.at_level(logging.INFO):
            assert worker.main() == 0
        assert not preview.exists()
        preview.write_text("file blocks the preview directory")
        with caplog.at_level(logging.INFO):
            assert worker.main() == 1
        assert '"outcome": "mail_config"' in caplog.text

        # Auth erasure remains ready with mail disabled; it still requires the cleanup API.
        monkeypatch.setattr(settings, "email_delivery_mode", "disabled")
        monkeypatch.setattr(sys, "argv", ["auth_jobs", "--check-ready"])
        client = TestClient(api.app)
        with identity.begin() as session:
            session.add(AuthJob(id=PRIVATE_ID, kind="delete", user_id=PRIVATE_ID, secret=CANARY))

        def cleanup_ready(url, *, timeout):
            assert url.endswith("/readyz")
            return client.get("/readyz")

        monkeypatch.setattr(metrics.httpx, "get", cleanup_ready)
        with caplog.at_level(logging.INFO):
            assert auth_jobs.main() == 0
        monkeypatch.setattr(metrics.httpx, "get", lambda *args, **kw: httpx.Response(503, text=CANARY))
        with caplog.at_level(logging.INFO):
            assert auth_jobs.main() == 1
        assert '"outcome": "cleanup_api"' in caplog.text
        assert CANARY not in caplog.text
        with identity() as session:
            job = session.get(AuthJob, PRIVATE_ID)
            assert job.attempts == 0 and job.status == "pending"


@pytest.mark.parametrize("collector", [False, True])
def test_t26_helm_diagnostics_boundary(collector, tmp_path):
    helm = os.environ.get("HELM_BINARY") or shutil.which("helm")
    if not helm:
        pytest.skip("requires local Helm; supply HELM_BINARY for config verification")
    command = [helm, "template", "t26", str(ROOT / "infra/helm/realtoruch")]
    if collector:
        command += ["--set", "collector.enabled=true"]
    rendered = subprocess.run(command, check=True, text=True, capture_output=True, timeout=20).stdout
    (tmp_path / "rendered.yaml").write_text(rendered)
    resources = [obj for obj in yaml.safe_load_all(rendered) if obj]
    by_kind = lambda kind: {obj["metadata"]["name"]: obj for obj in resources if obj["kind"] == kind}
    ingress = by_kind("Ingress")
    assert set(ingress) == {"public-api"}
    spec = ingress["public-api"]["spec"]
    assert "defaultBackend" not in spec
    assert len(spec["rules"]) == 1 and spec["rules"][0]["host"]
    paths = spec["rules"][0]["http"]["paths"]
    assert {(p["path"], p["pathType"]) for p in paths} == {
        ("/v1", "Prefix"),
        ("/v1/auth", "Prefix"),
        ("/v1/search", "Prefix"),
        ("/docs", "Exact"),
        ("/openapi.json", "Exact"),
        ("/healthz", "Exact"),
        ("/readyz", "Exact"),
    }
    for service in by_kind("Service").values():
        spec = service["spec"]
        assert spec.get("type", "ClusterIP") == "ClusterIP"
        assert not spec.get("externalIPs")
        assert not any("nodePort" in port for port in spec["ports"])
    policies = by_kind("NetworkPolicy")
    assert policies["default-deny-ingress"]["spec"] == {"podSelector": {}, "policyTypes": ["Ingress"]}
    cidrs = {
        peer["ipBlock"]["cidr"]
        for policy in policies.values()
        for rule in policy["spec"].get("ingress", [])
        for peer in rule.get("from", [])
        if "ipBlock" in peer
    }
    assert cidrs == {"35.191.0.0/16", "130.211.0.0/22"}
    assert all(rule.get("from") for policy in policies.values() for rule in policy["spec"].get("ingress", []))
    assert ("collect-listings" in by_kind("CronJob")) is collector
