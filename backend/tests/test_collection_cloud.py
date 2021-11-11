"""Cloud publication ordering contract, using in-memory clients (no GCP calls)."""

import json
import sys
import types
from datetime import timedelta

import pytest

from realtoruch import worker
from realtoruch.models import now
from realtoruch.normalization import normalize


class MemoryTable:
    def __init__(self):
        self.rows = {}

    def read_row(self, key):
        value = self.rows.get(key)
        return (
            types.SimpleNamespace(cells={"raw": {b"payload": [types.SimpleNamespace(value=value)]}})
            if value
            else None
        )

    def direct_row(self, key):
        table = self

        class Row:
            deleted = False

            def set_cell(self, family, qualifier, value):
                self.value = value

            def delete(self):
                self.deleted = True

            def commit(self):
                if self.deleted:
                    table.rows.pop(key, None)
                else:
                    table.rows[key] = self.value

        return Row()


def fake_publisher(monkeypatch, *, fails=False):
    sent = []

    class Publisher:
        def topic_path(self, project, topic):
            return "test-topic"

        def publish(self, topic, payload, **attrs):
            sent.append(payload)

            class Future:
                def result(self, timeout):
                    if fails:
                        raise TimeoutError("synthetic publish failure")

            return Future()

    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    pubsub = types.ModuleType("google.cloud.pubsub_v1")
    pubsub.PublisherClient = Publisher
    google.cloud, cloud.pubsub_v1 = cloud, pubsub
    for name, value in (("google", google), ("google.cloud", cloud), ("google.cloud.pubsub_v1", pubsub)):
        monkeypatch.setitem(sys.modules, name, value)
    return sent


@pytest.mark.parametrize("fails", [False, True])
def test_state_and_recheck_queue_advance_only_after_successful_publish(record, monkeypatch, fails):
    from realtoruch.fetch_state import Validators

    table = MemoryTable()
    previous = normalize(record)
    state_key = worker.state_key(record.source, str(record.url))
    table.rows[state_key] = json.dumps(previous).encode()
    table.rows[worker.recheck_key(previous)] = json.dumps(previous).encode()
    monkeypatch.setattr(worker, "state_table", lambda: table)
    sent = fake_publisher(monkeypatch, fails=fails)
    updated = record.model_copy(update={"observed_at": now() - timedelta(seconds=1), "rent_pln": 3200})
    validator = Validators("fixture-variant", updated.observed_at.isoformat(), '"fixture"', None)
    if fails:
        with pytest.raises(TimeoutError):
            worker.publish(updated, validator)
        assert json.loads(table.rows[state_key])["rent_pln"] == record.rent_pln
        assert worker.recheck_key(previous) in table.rows
        assert "_fetch" not in json.loads(table.rows[state_key])
    else:
        worker.publish(updated, validator)
        assert json.loads(table.rows[state_key])["rent_pln"] == 3200
        assert worker.recheck_key(previous) not in table.rows
        assert worker.recheck_key(normalize(updated)) in table.rows
        assert json.loads(table.rows[state_key])["_fetch"]["etag"] == '"fixture"'
    assert b'"phone":' not in sent[0] and b"700100101" not in sent[0] and b'"_fetch"' not in sent[0]
    assert all(b'"_fetch"' not in value for key, value in table.rows.items() if key != state_key)


def test_t04_cloud_legacy_and_current_state_are_readable_without_replaying_304(record, monkeypatch):
    from datetime import datetime

    import httpx
    from test_connectors import DETAIL_URL, ETAG, ROBOTS, detail_page, fake_collector

    table = MemoryTable()
    monkeypatch.setattr(worker, "state_table", lambda: table)
    sent = fake_publisher(monkeypatch)
    old = record.model_copy(update={"observed_at": datetime(2024, 1, 1), "external_id": "detail-one"})
    key = worker.state_key(record.source, DETAIL_URL)
    table.rows[key] = json.dumps(normalize(old)).encode()
    replies = iter([200, 200, 304, 304])

    def handler(request):
        assert "If-None-Match" not in request.headers
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        status = next(replies)
        return httpx.Response(status, content=detail_page() if status == 200 else b"", headers={"ETag": ETAG})

    _, attempts, config = fake_collector(monkeypatch, None, handler, config={"max_rechecks": 0})
    legacy, _ = worker.source_state(config, True)
    assert "_fetch" not in legacy(DETAIL_URL)
    assert worker.collect(cloud=True)[0]["ingested"] == 1
    current, _ = worker.source_state(config, True)
    assert current(DETAIL_URL)["_fetch"]["etag"] == ETAG
    assert worker.collect(cloud=True)[0]["ingested"] == 1
    assert len(sent) == 2 and all(b'"_fetch"' not in payload for payload in sent)
    previous = current(DETAIL_URL)["observed_at"]
    with pytest.raises(worker.CollectionFailed) as error:
        worker.collect(cloud=True)
    assert error.value.reports[0]["reused_304"] == 0
    assert len(attempts) == 7 and len(sent) == 2
    assert current(DETAIL_URL)["observed_at"] == previous


def test_t04_cloud_timing_survives_new_run_under_single_cronjob_assumption(monkeypatch):
    from datetime import timedelta

    import httpx
    from test_connectors import DETAIL_URL, fake_collector

    table = MemoryTable()
    monkeypatch.setattr(worker, "state_table", lambda: table)
    replies = iter([httpx.Response(503, headers={"Retry-After": "23"}), httpx.Response(200, json=[])])
    clock, attempts, _ = fake_collector(monkeypatch, None, lambda _: next(replies),
                                        config={"mode": "feed", "feed_url": DETAIL_URL})
    with pytest.raises(worker.CollectionFailed):
        worker.collect(cloud=True)
    timing = worker.CloudTiming(table, "otodom")
    assert timing.deadline("retry_after") == clock.now() + timedelta(seconds=23)
    assert timing.deadline("next_allowed_request") == clock.now() + timedelta(seconds=1)
    assert worker.collect(cloud=True)[0]["reason"] == "backoff" and len(attempts) == 1
    clock.sleep(23)
    assert worker.collect(cloud=True)[0]["status"] == "succeeded" and len(attempts) == 2
