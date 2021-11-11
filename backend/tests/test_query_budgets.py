"""Candidate loading must preserve decisions without one query per candidate."""
import pytest
from sqlalchemy import event, select

from realtoruch.dedupe import matching_property
from realtoruch.models import Listing, SourceListing
from realtoruch.normalization import normalize


@pytest.mark.parametrize('url', ['sqlite://', 'postgresql://localhost/not_owned',
                                 'postgresql://example.test/t25_owned'])
def test_t25_seed_rejects_unowned_destinations(url):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, str(root / 'scripts/seed_benchmark.py'),
                             '--t25-seed-only', '--url', url], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'requires a loopback PostgreSQL database named t25_' in result.stderr


def test_capacity_runner_rejects_degraded_search(tmp_path):
    import json
    import subprocess
    import sys
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({'engine': 'postgresql', 'degraded': True}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    output = tmp_path / 'load.json'
    root = Path(__file__).resolve().parents[2]
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        result = subprocess.run([sys.executable, str(root / 'scripts/load_check.py'),
                                 '--url', url, '--search-url', url, '--sql-engine', 'postgresql',
                                 '--profile', 'capacity', '--capacity-limit', '1000',
                                 '--requests', '6', '--concurrency', '1', '--output', str(output)],
                                capture_output=True, text=True, timeout=30)
        report = json.loads(output.read_text())
        assert result.returncode == 1
        assert report['endpoints']['es_rest_search']['engines'] == {'postgresql': 1}
        assert report['endpoints']['es_rest_search']['degraded'] == {'True': 1}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.skipif(not __import__('os').getenv('TEST_POSTGRES_URL'), reason='Requires disposable PostgreSQL')
def test_history_keeps_database_collation_for_source_ties(pg_engine):
    from datetime import datetime, timezone
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from realtoruch.models import Observation
    from realtoruch.query import market_history
    observed = datetime.now(timezone.utc).replace(tzinfo=None, day=1, hour=0, minute=0, second=0, microsecond=0)
    with Session(pg_engine) as session:
        session.add(Listing(id='home', title='home', city='Tie', district='d', region='r',
                            address='x', area_m2=50, rooms=2, rent_pln=1000))
        session.flush()
        for source_id, rent in [('A', 1000), ('a', 2000)]:
            session.add(SourceListing(id=source_id, listing_id='home', source=source_id,
                external_id=source_id, url='https://example.test', data={}, observed_at=observed))
            session.flush()
            session.add(Observation(id='obs' + source_id, listing_id='home', source_listing_id=source_id,
                                    observed_at=observed, rent_pln=rent, status='active', changed=True))
        session.flush()
        expected = session.execute(text("SELECT rent FROM (VALUES ('A'::text, 1000), ('a'::text, 2000)) AS x(id, rent) ORDER BY id DESC LIMIT 1")).scalar_one()
        assert market_history(session, 'Tie')['points'][0]['median_rent_pln'] == expected


@pytest.mark.parametrize('size', [1, 10, 100, 101])
@pytest.mark.parametrize('match_position', ['none', 'first', 'last'])
def test_candidate_batches_match_unbatched_decisions(session, record, size, match_position):
    from realtoruch.ingest import candidate_match
    data = normalize(record.model_copy(update={'address': 'Bench 1/2'}))
    candidates = []
    for i in range(size):
        matches = (match_position == 'first' and i == 0) or (match_position == 'last' and i == size - 1)
        address = 'Bench 1/2' if matches else f'Other {i}/1'
        home = Listing(id=f'h{i}', title='home', city=record.city, district='d', region='r',
                       address=address, area_m2=record.area_m2, rooms=record.rooms,
                       floor=record.floor, rent_pln=record.rent_pln)
        session.add(home)
        session.add(SourceListing(id=f's{i}', listing_id=home.id, source='fixture',
                                  external_id=f's{i}', url='https://example.test',
                                  phone_hash=data['phone_hash'], data={'images': []},
                                  observed_at=record.observed_at))
        candidates.append(home)
    session.flush()
    count = 0
    def counter(*_):
        nonlocal count
        count += 1
    event.listen(session.bind, 'before_cursor_execute', counter)
    try:
        expected = (None, 'New property')
        for candidate in candidates:
            sources = session.scalars(select(SourceListing).where(SourceListing.listing_id == candidate.id)).all()
            reason = matching_property(candidate, data, sources)
            if reason:
                expected = candidate, reason
                break
        assert count == (1 if match_position == 'first' else size)
        count = 0
        actual = candidate_match(session, candidates, data)
        assert actual == expected
        assert count == (1 if match_position == 'first' else (size + 99) // 100)
    finally:
        event.remove(session.bind, 'before_cursor_execute', counter)


@pytest.mark.skipif(not __import__('os').getenv('TEST_POSTGRES_URL') or not __import__('os').getenv('TEST_ELASTICSEARCH_URL'),
                    reason='Requires disposable PostgreSQL and Elasticsearch')
def test_relist_index_and_replay_converge(pg_engine, record, monkeypatch):
    """A stale in-flight bulk must not overwrite the committed relist revision."""
    import os
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from uuid import uuid4
    import httpx
    from sqlalchemy.orm import sessionmaker
    from realtoruch import indexing
    from realtoruch.alerts import process_alerts
    from realtoruch.ingest import ingest
    from realtoruch.models import Favorite, Notification, Outbox, SearchRevision

    alias = 't25_test_' + uuid4().hex
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    def client():
        return httpx.Client(base_url=os.environ['TEST_ELASTICSEARCH_URL'], timeout=30)
    first = record.model_copy(update={'rent_pln': 4500})
    with factory.begin() as session:
        home_id = ingest(session, first)['listing_id']
        process_alerts(session)
        session.add(Favorite(user_id='synthetic-user', listing_id=home_id, price_floor=4500))
    with factory.begin() as session:
        ingest(session, first.model_copy(update={'status': 'inactive', 'observed_at': first.observed_at + timedelta(hours=1)}))
    started, release = threading.Event(), threading.Event()
    real_send = indexing.send_bulk
    def pause_send(client, docs, index):
        started.set()
        assert release.wait(30)
        return real_send(client, docs, index)
    monkeypatch.setattr(indexing, 'send_bulk', pause_send)
    relist = first.model_copy(update={'rent_pln': 4200, 'observed_at': first.observed_at + timedelta(hours=2)})
    barrier = threading.Barrier(2)
    def write():
        barrier.wait(timeout=30)
        with factory.begin() as session:
            return ingest(session, relist)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            stale = pool.submit(indexing.index_once, factory, client, alias)
            assert started.wait(30)
            a, b = pool.submit(write), pool.submit(write)
            statuses = sorted([a.result(timeout=60)['status'], b.result(timeout=60)['status']])
            assert statuses == ['duplicate_event', 'updated']
            monkeypatch.setattr(indexing, 'send_bulk', real_send)
            assert pool.submit(indexing.index_once, factory, client, alias).result(timeout=60) == 1
            release.set()
            stale.result(timeout=60)
        with factory.begin() as session:
            process_alerts(session)
            revision = session.get(SearchRevision, home_id).revision
            notifications = session.scalars(select(Notification).where(Notification.user_id == 'synthetic-user')).all()
            assert [(n.kind, n.rent_pln, n.previous_rent_pln) for n in notifications] == [('price_drop', 4200, 4500)]
            assert not session.scalars(select(Outbox).where(Outbox.delivered_at.is_(None))).all()
        with client() as es:
            doc = es.get(f'/{alias}/_doc/{home_id}').json()
            assert (doc['_version'], doc['_source']['rent_pln'], doc['_source']['status']) == (revision, 4200, 'active')
    finally:
        release.set()
        with client() as es:
            response = es.delete(f'/{alias}-initial')
            assert response.status_code in (200, 404)


# Reuse the service fixture's unique, migration-managed PostgreSQL schema.
from test_service_integration import pg_engine  # noqa: E402,F401
