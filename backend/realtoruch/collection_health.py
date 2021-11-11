"""Local/PostgreSQL collector coordination and durable health history."""

from datetime import timedelta
from threading import Event, Thread

from sqlalchemy import String, cast, func, or_, select, update

from .alerts import insert_once
from .models import CollectionRun, SourcePollState, now, uid


def claim(factory, config):
    source = config["name"]
    with factory.begin() as session:
        insert_once(session, SourcePollState, {"source": source, "failures": 0})
        lease_id = uid()
        changed = session.execute(
            update(SourcePollState)
            .where(
                SourcePollState.source == source,
                or_(SourcePollState.lease_until.is_(None), SourcePollState.lease_until < now()),
                or_(SourcePollState.retry_after.is_(None), SourcePollState.retry_after <= now()),
            )
            .values(lease_id=lease_id, lease_until=now() + timedelta(minutes=30))
        ).rowcount
        state = session.get(SourcePollState, source)
        if not changed:
            backoff = state.retry_after if state.retry_after and state.retry_after > now() else None
            return None, {
                "source": source,
                "status": "deferred",
                "errors": [],
                "reason": "backoff" if backoff else "already_running",
                "retry_after": (backoff or state.lease_until or now()).isoformat() + "Z",
            }
        run = CollectionRun(id=lease_id, source=source, city=config.get("city", ""), status="running")
        session.add(run)
        return lease_id, None


class LeaseLost(RuntimeError):
    """The lease expired, changed owners, or could not be verified."""


def guard(session, source, lease_id):
    # The update takes the provider row lock until the observation commits. A
    # concurrent claim therefore cannot pass this fence during ingestion.
    changed = session.execute(
        update(SourcePollState).where(
            SourcePollState.source == source,
            SourcePollState.lease_id == lease_id,
            SourcePollState.lease_until > now(),
        ).values(lease_until=SourcePollState.lease_until)
    ).rowcount
    if not changed:
        raise LeaseLost("Collection lease was lost")


def heartbeat(factory, source, lease_id):
    with factory.begin() as session:
        updated = session.execute(
            update(SourcePollState)
            .where(
                SourcePollState.source == source,
                SourcePollState.lease_id == lease_id,
                SourcePollState.lease_until > now(),
            )
            .values(lease_until=now() + timedelta(minutes=30))
        ).rowcount
        if not updated:
            raise LeaseLost("Collection lease was lost")


class LeaseHeartbeat:
    """One bounded periodic scheduler per provider run; injectable for tests."""

    interval = 60

    def __init__(self, factory, source, lease_id, *, event=None, thread_factory=Thread):
        self.factory, self.source, self.lease_id = factory, source, lease_id
        self.stop_event = event or Event()
        self.lost = Event()
        self.thread = thread_factory(target=self._run, daemon=True)

    def _run(self):
        while not self.stop_event.wait(self.interval):
            try:
                heartbeat(self.factory, self.source, self.lease_id)
            except Exception:
                # A database failure is indistinguishable from lost ownership.
                self.lost.set()
                return

    def start(self):
        self.thread.start()

    def check(self):
        if self.lost.is_set():
            raise LeaseLost("Collection lease could not be renewed")
        try:
            with self.factory.begin() as session:
                guard(session, self.source, self.lease_id)
        except Exception as exc:
            self.lost.set()
            raise LeaseLost("Collection lease could not be verified") from exc

    def _change_timing(self, change):
        if self.lost.is_set():
            raise LeaseLost("Collection lease could not be renewed")
        try:
            with self.factory.begin() as session:
                guard(session, self.source, self.lease_id)
                state = session.get(SourcePollState, self.source)
                instant = now()
                if state.lease_until <= instant:
                    raise LeaseLost("Collection lease expired during request scheduling")
                return change(state, instant)
        except Exception as exc:
            self.lost.set()
            raise LeaseLost("Collection request timing could not be verified") from exc

    def reserve_request(self, delay):
        """Return time to wait or reserve one request start and commit before HTTP."""
        def reserve(state, instant):
            if state.next_allowed_request and state.next_allowed_request > instant:
                return (state.next_allowed_request - instant).total_seconds()
            state.next_allowed_request = instant + timedelta(seconds=delay)
            return 0

        return self._change_timing(reserve)

    def extend_pacing(self, deadline):
        def extend(state, _):
            if not state.next_allowed_request or deadline > state.next_allowed_request:
                state.next_allowed_request = deadline

        self._change_timing(extend)

    def defer_requests(self, deadline):
        def defer(state, _):
            if not state.retry_after or deadline > state.retry_after:
                state.retry_after = deadline

        self._change_timing(defer)

    def close(self):
        self.stop_event.set()
        self.thread.join()


def finish(factory, source, lease_id, report):
    with factory.begin() as session:
        # Conditional UPDATE is both the ownership test and health mutation.
        # It takes the same row lock as claims and ingestion fences.
        state = session.get(SourcePollState, source)
        values = {"lease_id": None, "lease_until": None}
        if report["errors"]:
            # Lock first with a conditional no-op so the read cannot race takeover.
            locked = session.execute(update(SourcePollState).where(
                SourcePollState.source == source, SourcePollState.lease_id == lease_id,
                SourcePollState.lease_until > now(),
            ).values(lease_until=SourcePollState.lease_until)).rowcount
            if locked:
                session.refresh(state)
                failures = state.failures + 1
                deadline = state.retry_after if report.get("retry_after") else now() + timedelta(
                    minutes=min(360, 15 * 2 ** min(failures - 1, 5)))
                values.update(failures=failures, retry_after=deadline)
        else:
            values.update(failures=0, retry_after=None, last_success_at=now())
        owned = session.execute(update(SourcePollState).where(
            SourcePollState.source == source, SourcePollState.lease_id == lease_id,
            SourcePollState.lease_until > now(),
        ).values(**values)).rowcount
        run = session.get(CollectionRun, lease_id)
        if run:
            final_report = report if owned else {**report, "status": "interrupted", "reason": "lease_lost"}
            run.finished_at, run.status, run.report = now(), final_report["status"], final_report
        return bool(owned)


def public_health(session, source, *, city=""):
    query = select(CollectionRun).where(CollectionRun.source == source)
    if city:
        query = query.where(CollectionRun.city == city)
    run = session.scalar(query.order_by(CollectionRun.started_at.desc()).limit(1))
    state = session.get(SourcePollState, source)
    if not run:
        return None
    # Reuse the source/time lookup and only select one timestamp. A capped
    # sample may be successful without completing the configured city scan.
    limited = func.coalesce(cast(CollectionRun.report["limited"].as_string(), String), "")
    last_complete = session.scalar(
        query.with_only_columns(CollectionRun.finished_at).where(
            CollectionRun.status == "succeeded", CollectionRun.finished_at.is_not(None),
            limited.not_in(("1", "true")),
        ).order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc()).limit(1)
    )
    status = run.status
    if status == "running" and (
        not state or state.lease_id != run.id or not state.lease_until or state.lease_until < now()
    ):
        status = "interrupted"
    report = run.report if isinstance(run.report, dict) else {}
    errors = report.get("errors")
    errors = errors[:20] if isinstance(errors, list) else []
    return {
        "status": status,
        "city": run.city,
        "started_at": run.started_at.isoformat() + "Z",
        "finished_at": run.finished_at.isoformat() + "Z" if run.finished_at else None,
        "ingested": report.get("ingested", 0),
        "checked": report.get("checked", 0),
        "fresh_skipped": report.get("fresh_skipped", 0),
        "limited": report.get("limited", False),
        "errors": [
            {"kind": e.get("kind"), "stage": e.get("stage"), "http_status": e.get("http_status")}
            for e in errors if isinstance(e, dict)
        ],
        "consecutive_failures": state.failures if state else 0,
        "last_success_at": last_complete.isoformat() + "Z" if last_complete else None,
        "retry_after": state.retry_after.isoformat() + "Z" if state and state.retry_after else None,
    }
