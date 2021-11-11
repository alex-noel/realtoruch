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


@pytest.mark.parametrize("fails", [False, True])
def test_state_and_recheck_queue_advance_only_after_successful_publish(record, monkeypatch, fails):
    table = MemoryTable()
    previous = normalize(record)
    state_key = worker.state_key(record.source, str(record.url))
    table.rows[state_key] = json.dumps(previous).encode()
    table.rows[worker.recheck_key(previous)] = json.dumps(previous).encode()
    monkeypatch.setattr(worker, "state_table", lambda: table)
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
    updated = record.model_copy(update={"observed_at": now() - timedelta(seconds=1), "rent_pln": 3200})
    if fails:
        with pytest.raises(TimeoutError):
            worker.publish(updated)
        assert json.loads(table.rows[state_key])["rent_pln"] == record.rent_pln
        assert worker.recheck_key(previous) in table.rows
    else:
        worker.publish(updated)
        assert json.loads(table.rows[state_key])["rent_pln"] == 3200
        assert worker.recheck_key(previous) not in table.rows
        assert worker.recheck_key(normalize(updated)) in table.rows
    assert b'"phone":' not in sent[0] and b"700100101" not in sent[0]
