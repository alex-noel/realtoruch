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
