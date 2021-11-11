import json
import pytest
from sqlalchemy import create_engine, text
from realtoruch.migrations import REGISTRY, load_registry, upgrade_local
from realtoruch.db import Base
from realtoruch import models  # noqa: F401


def test_registry_rejects_duplicate_and_out_of_order(tmp_path):
    registry = json.loads(REGISTRY.read_text())
    for entries in ([registry['rentals'][0]] * 2, list(reversed(registry['rentals']))):
        registry['rentals'] = entries
        path = tmp_path / 'registry.json'
        path.write_text(json.dumps(registry))
        with pytest.raises(ValueError):
            load_registry(path)


def test_sqlite_upgrade_repeats_and_rejects_checksum_drift(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'upgrade.db'))
    Base.metadata.create_all(engine)
    upgrade_local(engine)
    upgrade_local(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE realtoruch_local_migrations SET checksum='bad'"))
    with pytest.raises(ValueError, match='checksum'):
        upgrade_local(engine)
    engine.dispose()
