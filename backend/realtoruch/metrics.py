"""Private operational snapshots. The SQL and label vocabulary are both finite."""

import hmac
import json
import os
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from threading import BoundedSemaphore
from time import monotonic

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import and_, case, exists, func, literal, or_, select, text, union_all

from .models import CollectionRun, EmailDelivery, Outbox, PushDelivery, SourcePollState, now
from .settings import get_settings

PROVIDERS = ("gratka", "morizon", "olx", "otodom")
QUEUE_STATES = ("ready", "leased", "deferred", "failed", "cancelled")
RUN_STATES = ("running", "succeeded", "partial", "failed", "interrupted", "other")
TIMEOUT_MS = 250
# One concurrent scrape per process; replicas report their own SQL snapshots.
_scrape_slot = BoundedSemaphore(1)


def provider_label(value):
    return value if value in PROVIDERS else "other"


def lifecycle_log(logger, event, **fields):
    """Only pass caller-allowlisted dimensions and numeric counts; never exceptions or payloads."""
    logger.info("%s", json.dumps({"event": event, **fields}, sort_keys=True))


def require_metrics_key(request: Request):
    key = get_settings().internal_api_key.encode()
    if not key or not hmac.compare_digest(request.headers.get("X-Internal-Key", "").encode(), key):
        raise HTTPException(403, "Forbidden")


@contextmanager
def diagnostic_session(factory):
    # The transaction always closes, including after PG aborts a timed-out statement.
    with factory() as session:
        connection = session.connection()
        if connection.dialect.name == "postgresql":
            connection.execute(text(f"SET LOCAL statement_timeout = '{TIMEOUT_MS}ms'"))
            connection.execute(text("SET TRANSACTION READ ONLY"))
            yield session
        else:
            driver = connection.connection.driver_connection
            prior_timeout = driver.execute("PRAGMA busy_timeout").fetchone()[0]
            deadline = monotonic() + TIMEOUT_MS / 1000
            driver.execute(f"PRAGMA busy_timeout = {TIMEOUT_MS}")
            driver.set_progress_handler(lambda: monotonic() >= deadline, 1000)
            try:
                yield session
            finally:
                driver.set_progress_handler(None, 0)
                driver.execute(f"PRAGMA busy_timeout = {prior_timeout}")


def can_read_database(factory, *required_tables):
    try:
        with diagnostic_session(factory) as session:
            session.execute(
                select(*(exists(select(literal(1)).select_from(table)) for table in required_tables))
            )
    except Exception:  # noqa: BLE001 - safe diagnostic boundary
        # SQL drivers and connection providers may use different exception hierarchies.
        return False
    return True


def database_ready(factory, *required_tables):
    if not can_read_database(factory, *required_tables):
        return JSONResponse({"status": "unready"}, status_code=503)
    return {"status": "ready"}


def worker_readiness(factory, required_tables, settings, *, needs_cleanup_api=False):
    """Read-only check of dependencies; no job claim, auth attempt or transport send."""
    if not can_read_database(factory, *required_tables):
        return "database"
    if needs_cleanup_api:
        try:
            response = httpx.get(settings.api_base_url.rstrip("/") + "/readyz", timeout=0.75)
            if response.status_code != 200 or response.json().get("status") != "ready":
                return "cleanup_api"
        except (httpx.HTTPError, httpx.InvalidURL, ValueError, AttributeError):
            return "cleanup_api"
    if settings.email_delivery_mode == "smtp" and not settings.smtp_host:
        return "mail_config"
    if settings.email_delivery_mode == "file":
        path = Path(settings.email_preview_directory)
        # The sender creates the directory; readiness checks the nearest existing ancestor.
        existing = next(p for p in (path, *path.parents, Path.cwd()) if p.exists())
        if not existing.is_dir() or not os.access(existing, os.W_OK | os.X_OK):
            return "mail_config"
    return "ready"


def _queue_rows(queue, model, timestamp, state, filter_, errored):
    return (
        select(
            literal(queue),
            state.label("state"),
            func.count(),
            func.min(timestamp),
            func.count().filter(errored),
        )
        .select_from(model)
        .where(filter_)
        .group_by("state")
    )


def _delivery_rows(queue, model, stamp, *, statuses=("pending", "retry"), extra=True, enabled=True):
    active = model.status.in_(statuses)
    state = case(
        (model.status == "failed", "failed"),
        (model.status == "cancelled", "cancelled"),
        (model.lease_until >= stamp, "leased"),
        (or_(model.next_attempt_at > stamp, not enabled), "deferred"),
        else_="ready",
    )
    return _queue_rows(
        queue,
        model,
        model.next_attempt_at,
        state,
        and_(or_(active, model.status.in_(("failed", "cancelled"))), extra),
        model.last_error.is_not(None),
    )


def _rental_rows(stamp):
    source = SourcePollState
    run = CollectionRun
    run_state = case((run.status.in_(RUN_STATES[:-1]), run.status), else_="other").label("run_state")
    return (
        _queue_rows(
            "search_outbox",
            Outbox,
            Outbox.created_at,
            case(
                (Outbox.last_index_status.in_((400, 413)), "failed"),
                else_="ready",
            ),
            Outbox.delivered_at.is_(None),
            Outbox.last_index_status.is_not(None),
        ),
        _delivery_rows("rental_email", EmailDelivery, stamp),
        _delivery_rows("push", PushDelivery, stamp, statuses=("pending", "retry", "receipt")),
        select(source.source, literal("success"), literal(0), source.last_success_at, literal(0)).where(
            source.source.in_(PROVIDERS)
        ),
        select(source.source, literal("failures"), source.failures, source.retry_after, literal(0)).where(
            source.source.in_(PROVIDERS)
        ),
        select(source.source, literal("lease"), literal(0), source.lease_until, literal(0)).where(
            source.source.in_(PROVIDERS), source.lease_id.is_not(None)
        ),
        select(run.source, run_state, func.count(), func.min(run.started_at), literal(0))
        .where(
            run.source.in_(PROVIDERS), run.started_at >= stamp - timedelta(hours=24), run.started_at <= stamp
        )
        .group_by(run.source, "run_state"),
    )


def _auth_rows(stamp, model, *, mail_enabled):
    return (
        _delivery_rows(
            "auth_mail", model, stamp, enabled=mail_enabled, extra=model.kind.in_(("verify", "reset"))
        ),
        _delivery_rows("account_erasure", model, stamp, extra=model.kind == "delete"),
    )


def _age(stamp, timestamp):
    return max(0.0, (stamp - timestamp).total_seconds()) if timestamp is not None else 0.0


def _snapshot(factory, queues, statements, *, stamp, collection=False, mail_enabled=True):
    metrics = []

    def gauge(name, help_, labels=()):
        family = GaugeMetricFamily("realtoruch_" + name, help_, labels=labels)
        metrics.append(family)
        return family

    success = gauge("metrics_collection_success", "Whether the database snapshot completed (1/0).")
    if not _scrape_slot.acquire(blocking=False):
        success.add_metric([], 0)
        return metrics
    try:
        with diagnostic_session(factory) as session:
            rows = {
                (name, state): (count, timestamp, errors)
                for name, state, count, timestamp, errors in session.execute(union_all(*statements))
            }
    except Exception:  # noqa: BLE001 - safe diagnostic boundary
        # Suppress driver/connector details, even if checkout itself failed.
        success.add_metric([], 0)
        return metrics
    finally:
        _scrape_slot.release()

    success.add_metric([], 1)
    depth = gauge("queue_depth", "Rows by current operational queue state.", ["queue", "state"])
    age = gauge(
        "queue_oldest_eligible_age_seconds",
        "Seconds since the earliest due time among ready rows.",
        ["queue"],
    )
    recorded_errors = gauge("queue_last_error_depth", "Rows with a recorded last attempt failure.", ["queue"])
    empty = (0, None, 0)
    for queue in queues:
        recorded_errors.add_metric([queue], sum(rows.get((queue, state), empty)[2] for state in QUEUE_STATES))
        for state in QUEUE_STATES:
            count, timestamp, _ = rows.get((queue, state), empty)
            depth.add_metric([queue, state], count)
            if state == "ready":
                age.add_metric([queue], _age(stamp, timestamp))
    if not collection:
        gauge("auth_mail_enabled", "Whether the auth worker is configured to process mail (1/0).").add_metric(
            [], int(mail_enabled)
        )
        return metrics

    gauge("outbox_pending", "All undelivered search outbox rows, including blocked rows.").add_metric(
        [], sum(rows.get(("search_outbox", state), empty)[0] for state in QUEUE_STATES)
    )
    source_age = gauge(
        "collection_last_success_age_seconds", "Seconds since a source last succeeded.", ["provider"]
    )
    known = gauge(
        "collection_success_known", "Whether a last source success is recorded (1/0).", ["provider"]
    )
    failures = gauge("collection_consecutive_failures", "Current consecutive source failures.", ["provider"])
    backoff = gauge(
        "collection_backoff_seconds", "Seconds remaining before the next permitted attempt.", ["provider"]
    )
    lease = gauge(
        "collection_lease_expired", "Whether a recorded source lease is expired (1/0).", ["provider"]
    )
    runs = gauge(
        "collection_runs_24h",
        "Durable source attempts started in the last 24 hours by recorded state.",
        ["provider", "state"],
    )
    for provider in PROVIDERS:
        _, last, _ = rows.get((provider, "success"), empty)
        _, until, _ = rows.get((provider, "lease"), empty)
        failure_count, retry_after, _ = rows.get((provider, "failures"), empty)
        known.add_metric([provider], int(last is not None))
        if last is not None:
            source_age.add_metric([provider], _age(stamp, last))
        failures.add_metric([provider], failure_count)
        backoff.add_metric([provider], _age(retry_after, stamp) if retry_after is not None else 0)
        lease.add_metric([provider], int(until is not None and until < stamp))
        for state in RUN_STATES:
            runs.add_metric([provider, state], rows.get((provider, state), empty)[0])
    return metrics


def _response(samples):
    class Snapshot:
        def collect(self):
            yield from samples

    registry = CollectorRegistry()
    registry.register(Snapshot())
    return PlainTextResponse(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


def rental_metrics(factory):
    stamp = now()
    return _response(
        _snapshot(
            factory,
            ("search_outbox", "rental_email", "push"),
            _rental_rows(stamp),
            stamp=stamp,
            collection=True,
        )
    )


def auth_metrics(factory, model, *, mail_enabled):
    stamp = now()
    return _response(
        _snapshot(
            factory,
            ("auth_mail", "account_erasure"),
            _auth_rows(stamp, model, mail_enabled=mail_enabled),
            stamp=stamp,
            mail_enabled=mail_enabled,
        )
    )
