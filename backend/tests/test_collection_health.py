from datetime import timedelta

from sqlalchemy.orm import sessionmaker

from realtoruch.collection_health import claim, finish, public_health
from realtoruch.models import SourcePollState, now


def test_collector_lease_failure_backoff_and_recovery(session):
    factory = sessionmaker(session.bind, expire_on_commit=False)
    config = {"name": "otodom", "city": "Kraków"}
    lease, deferred = claim(factory, config)
    assert lease and deferred is None
    assert claim(factory, config)[1]["reason"] == "already_running"
    finish(
        factory,
        "otodom",
        lease,
        {
            "status": "failed",
            "errors": [{"kind": "SourceAccessError", "stage": "discovery", "http_status": 403}],
            "ingested": 0,
        },
    )
    assert claim(factory, config)[1]["reason"] == "backoff"
    session.expire_all()
    assert public_health(session, "otodom")["consecutive_failures"] == 1
    with factory.begin() as db:
        db.get(SourcePollState, "otodom").retry_after = now() - timedelta(seconds=1)
    lease, _ = claim(factory, config)
    finish(factory, "otodom", lease, {"status": "succeeded", "errors": [], "ingested": 8, "checked": 9})
    session.expire_all()
    health = public_health(session, "otodom", city="Kraków")
    assert health["status"] == "succeeded" and health["consecutive_failures"] == 0
    assert health["last_success_at"] and health["ingested"] == 8
    assert public_health(session, "otodom", city="Warszawa") is None


def test_interrupted_worker_is_detectable_and_reclaimable(session):
    factory = sessionmaker(session.bind, expire_on_commit=False)
    config = {"name": "gratka", "city": "Kraków"}
    old, _ = claim(factory, config)
    with factory.begin() as db:
        db.get(SourcePollState, "gratka").lease_until = now() - timedelta(seconds=1)
    assert public_health(session, "gratka")["status"] == "interrupted"
    new, _ = claim(factory, {**config, "city": "Warszawa"})
    assert new != old
    session.expire_all()
    assert public_health(session, "gratka", city="Kraków")["status"] == "interrupted"
    assert public_health(session, "gratka", city="Warszawa")["status"] == "running"
    finish(factory, "gratka", old, {"status": "succeeded", "errors": []})
    session.expire_all()
    assert session.get(SourcePollState, "gratka").lease_id == new


def test_empty_run_renews_past_lease_duration(session, monkeypatch):
    from realtoruch import collection_health as health

    factory = sessionmaker(session.bind, expire_on_commit=False)
    clock = [now()]
    monkeypatch.setattr(health, "now", lambda: clock[0])
    lease, _ = claim(factory, {"name": "empty", "city": "Kraków"})

    class Scheduler:
        calls = 0

        def wait(self, seconds):
            assert seconds <= 60
            self.calls += 1
            clock[0] += timedelta(seconds=seconds)
            return self.calls > 31

    scheduler = Scheduler()
    heartbeat = health.LeaseHeartbeat(factory, "empty", lease, event=scheduler)
    heartbeat._run()
    with factory() as db:
        state = db.get(SourcePollState, "empty")
        assert state.lease_id == lease and state.lease_until > clock[0]
    assert not heartbeat.lost.is_set()


def test_takeover_fences_old_commit_and_finish(session):
    import pytest
    from realtoruch.collection_health import LeaseLost, guard

    factory = sessionmaker(session.bind, expire_on_commit=False)
    old, _ = claim(factory, {"name": "fence", "city": "Kraków"})
    with factory.begin() as db:
        db.get(SourcePollState, "fence").lease_until = now() - timedelta(seconds=1)
    new, _ = claim(factory, {"name": "fence", "city": "Warszawa"})
    with factory.begin() as db:
        state = db.get(SourcePollState, "fence")
        state.failures = 3
        state.retry_after = now() + timedelta(hours=1)
        state.last_success_at = now() - timedelta(days=1)
        expected = (state.lease_id, state.lease_until, state.failures, state.retry_after, state.last_success_at)
    with pytest.raises(LeaseLost), factory.begin() as db:
        guard(db, "fence", old)
    finish(factory, "fence", old, {"status": "succeeded", "errors": []})
    with factory() as db:
        state = db.get(SourcePollState, "fence")
        assert (state.lease_id, state.lease_until, state.failures, state.retry_after, state.last_success_at) == expected
        assert new == state.lease_id
        assert public_health(db, "fence", city="Kraków")["status"] == "interrupted"
        assert public_health(db, "fence", city="Warszawa")["status"] == "running"


def test_heartbeat_failure_stops_next_request(monkeypatch):
    import pytest
    from realtoruch import collection_health as health
    from realtoruch.connectors import Connector

    class BrokenFactory:
        def begin(self):
            raise OSError("private database details")

    class OneTick:
        def wait(self, seconds):
            return False

    lease = health.LeaseHeartbeat(BrokenFactory(), "test", "old", event=OneTick())
    lease._run()
    connector = Connector({"name": "test"}, progress=lease.check)
    requests = []
    monkeypatch.setattr("realtoruch.connectors.time.sleep", lambda _: None)
    monkeypatch.setattr(connector.client, "stream", lambda *a, **kw: requests.append(a))
    with pytest.raises(health.LeaseLost):
        connector._download("https://example.com", {}, 10)
    connector.close()
    assert requests == []


def test_city_runs_share_provider_pacing(monkeypatch):
    from realtoruch.connectors import Connector

    clock = [100.0]
    requests = []
    monkeypatch.setattr("realtoruch.connectors.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("realtoruch.connectors.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    class Response:
        status_code = 200
        is_redirect = False
        def __enter__(self):
            requests.append(clock[0])
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def iter_bytes(self):
            return iter([b"ok"])

    for city in ("Kraków", "Warszawa"):
        connector = Connector({"name": "otodom", "city": city})
        monkeypatch.setattr(connector.client, "stream", lambda *args, **kwargs: Response())
        connector._download("https://example.com", {}, 10)
        connector.close()
    assert requests[1] - requests[0] >= 10


def test_worker_fences_inflight_response_and_starts_no_next_request(session, record, monkeypatch):
    import pytest
    from realtoruch import worker
    from realtoruch.models import EventReceipt
    from sqlalchemy import func, select

    factory = sessionmaker(session.bind, expire_on_commit=False)
    monkeypatch.setattr(worker, "Session", factory)
    monkeypatch.setattr(worker, "load_sources", lambda: [{"name": "otodom", "enabled": True, "mode": "feed"}])
    requests = []
    replacement = []

    class InflightConnector:
        def __init__(self, config):
            self.report = {"source": config["name"], "errors": []}
            self.progress = lambda: None
        def records(self):
            self.progress()
            requests.append("first")
            with factory.begin() as db:
                db.get(SourcePollState, "otodom").lease_until = now() - timedelta(seconds=1)
            replacement.append(claim(factory, {"name": "otodom", "city": "Warszawa"})[0])
            yield record
            self.progress()
            requests.append("second")
        def note_error(self, exc, stage):
            self.report["errors"].append({"kind": type(exc).__name__, "stage": stage})
        def close(self):
            pass

    monkeypatch.setattr(worker, "Connector", InflightConnector)
    with pytest.raises(worker.CollectionFailed) as exc:
        worker.collect()
    assert exc.value.reports[0]["status"] == "interrupted"
    assert requests == ["first"]
    with factory() as db:
        assert db.get(SourcePollState, "otodom").lease_id == replacement[0]
        assert db.scalar(select(func.count()).select_from(EventReceipt)) == 0
