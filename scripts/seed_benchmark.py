"""Seed and benchmark a disposable database. Never point this at a real catalog."""
import argparse
import json
import math
import os
import resource
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timedelta

# The API lifespan must never initialize a developer's configured database.
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['AUTH_DATABASE_URL'] = 'sqlite://'
os.environ['ENVIRONMENT'] = 'test'

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from realtoruch.db import Base
from realtoruch.models import Listing, SourceListing, Observation, SavedSearch, SearchRevision, now
from realtoruch.query import market_history, market_summary


def seed_t25(engine):
    """A fixed synthetic fixture; never derive data from an existing catalog."""
    timestamp = datetime(2026, 11, 1, 12)
    from realtoruch.migrations import apply_postgres
    with engine.begin() as connection:
        apply_postgres(connection, 'rentals')
    with engine.begin() as connection:
        for start in range(0, 10000, 500):
            homes, sources, observations, revisions = [], [], [], []
            for i in range(start, start + 500):
                home = f't25-h{i:05d}'
                advertiser = ('private', 'agency', 'unknown')[i % 3]
                status = 'inactive' if i % 10 == 0 else 'active'
                area = (49.9, 50.0, 55.0, 65.0)[i % 4]
                rent = (4200, 4999, 5000, 5500)[i % 4]
                lat, lon = [(50.02, 19.90), (50.10, 20.02), (50.06, 19.96), (50.11, 20.03)][i % 4]
                address = f'Benchmark {i}/1'
                values = dict(title=f'Benchmark home {i}', description='', city='Kraków', district=f'D{i % 10}',
                              region='Bench', address=address, lat=lat, lon=lon, area_m2=area, rooms=2,
                              floor=2, rent_pln=rent, fees_pln=None, deposit_pln=None,
                              commission_pln=0 if i % 2 else None, advertiser_type=advertiser,
                              property_type='apartment', amenities=[], images=[], is_demo=False)
                homes.append(dict(id=home, **values, status=status, first_seen=timestamp - timedelta(days=200),
                                  last_seen=timestamp, updated_at=timestamp))
                revisions.append(dict(listing_id=home, revision=1))
                # Every fifth home has a distinct crosspost or historical repost.
                for k in range(2 if i % 5 == 0 else 1):
                    source = f't25-s{i:05d}-{k}'
                    source_status = ('inactive' if k == 0 and i % 10 == 5 else status)
                    data = {**values, 'status': source_status, 'source': 'fixture', 'phone_hash': None,
                            'observed_at': timestamp.isoformat()}
                    sources.append(dict(id=source, listing_id=home, source=f'fixture{k}', external_id=source,
                                        url='https://example.test/fixture', data=data, status=source_status,
                                        observed_at=timestamp))
                    if k == 0:
                        for j in range(10):
                            observations.append(dict(id=f't25-o{i:05d}-{j}', listing_id=home,
                                source_listing_id=source, observed_at=timestamp - timedelta(days=j * 20),
                                rent_pln=rent + j, status=source_status if j == 0 else 'active', changed=True))
            connection.execute(Listing.__table__.insert(), homes)
            connection.execute(SourceListing.__table__.insert(), sources)
            connection.execute(Observation.__table__.insert(), observations)
            connection.execute(SearchRevision.__table__.insert(), revisions)
        connection.execute(SavedSearch.__table__.insert(), [dict(
            id=f't25-search{i:04d}', user_id=f't25-user{i:04d}', name='Synthetic search',
            city_key='krakow', created_at=timestamp,
            filters={'city': 'Kraków', 'max_price': 5000, 'min_area': 50})
            for i in range(2000)])
    return {'homes': 10000, 'sources': 12000, 'observations': 100000, 'saved_searches': 2000}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True, help='Empty disposable database only')
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--measure-only', action='store_true', help='Measure an already seeded disposable database in a fresh process')
    parser.add_argument('--t25-seed-only', action='store_true', help='Seed fixed T25 data in a fresh owned PostgreSQL database named t25_*')
    parser.add_argument('--t25-container', help='Run-owned PostgreSQL container name')
    parser.add_argument('--t25-owner', help='Expected realtoruch.t25.owner container label')
    args = parser.parse_args()
    if args.t25_seed_only:
        url = make_url(args.url)
        if url.get_backend_name() != 'postgresql' or url.host not in ('localhost', '127.0.0.1', '::1') or not (url.database or '').startswith('t25_'):
            parser.error('T25 requires a loopback PostgreSQL database named t25_*')
        if not args.t25_container or not args.t25_owner:
            parser.error('T25 requires an owned container and expected owner label')
        try:
            metadata = json.loads(subprocess.check_output(['docker', 'inspect', args.t25_container], text=True))[0]
            owner = (metadata['Config'].get('Labels') or {}).get('realtoruch.t25.owner')
            ports = metadata['NetworkSettings']['Ports'].get('5432/tcp') or []
        except (subprocess.CalledProcessError, KeyError, IndexError, TypeError, ValueError):
            parser.error('Cannot inspect the named PostgreSQL container')
        if owner != args.t25_owner or not any(p['HostIp'] in ('127.0.0.1', '::1') and int(p['HostPort']) == url.port for p in ports):
            parser.error('Container owner or loopback port does not match the database URL')
    engine = create_engine(args.url)
    from sqlalchemy import inspect
    if not args.measure_only and inspect(engine).get_table_names():
        raise SystemExit('Refusing nonempty database')
    if args.t25_seed_only:
        if args.measure_only:
            parser.error('--measure-only and --t25-seed-only are incompatible')
        print(json.dumps(seed_t25(engine), indent=2))
        engine.dispose()
        return
    timestamp = now().replace(microsecond=0)
    if not args.measure_only:
        Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for start in range(0, 10000 if not args.measure_only else 0, 1000):
            homes, sources, observations = [], [], []
            for i in range(start, start + 1000):
                home, source = f'h{i}', f's{i}'
                homes.append(dict(id=home, title=home, city='Bench', district=f'D{i % 10}', region='Bench',
                                  address=home, area_m2=50 + i % 50, rooms=2, rent_pln=2000 + i % 4000))
                sources.append(dict(id=source, listing_id=home, source='fixture', external_id=source,
                                    url='https://example.test', data={}, observed_at=timestamp))
                for j in range(10):
                    observations.append(dict(id=f'o{i}-{j}', listing_id=home, source_listing_id=source,
                                             observed_at=timestamp - timedelta(days=j * 20),
                                             rent_pln=2000 + i % 4000 + j, status='active', changed=True))
            connection.execute(Listing.__table__.insert(), homes)
            connection.execute(SourceListing.__table__.insert(), sources)
            connection.execute(Observation.__table__.insert(), observations)
    counts = {'queries': 0}
    @event.listens_for(engine, 'before_cursor_execute')
    def count(*_):
        counts['queries'] += 1
    results = {}
    from fastapi.testclient import TestClient
    from realtoruch.api import app
    from realtoruch.db import get_session
    def session_override():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_session] = session_override
    # TestClient runs the real HTTP handlers in this fresh Python process. It is
    # intentionally not a network/deployment benchmark.
    with TestClient(app) as client:
        baseline_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        for name, path in [('history', '/v1/market/history?city=Bench'), ('summary', '/v1/market/summary?city=Bench')]:
            def operation():
                response = client.get(path)
                response.raise_for_status()
                return response.json()
            tracemalloc.start()
            counts['queries'] = 0
            start = time.perf_counter()
            operation()
            cold = (time.perf_counter() - start) * 1000
            for _ in range(3): operation()
            times = []
            for _ in range(args.samples):
                start = time.perf_counter()
                operation()
                times.append((time.perf_counter() - start) * 1000)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            results[name] = {'cold_ms': cold, 'warm_ms': times, 'p95_ms': sorted(times)[math.ceil(.95 * len(times))-1],
                             'python_peak_bytes': peak, 'queries_per_request': counts['queries'] / (args.samples + 4)}
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    app.dependency_overrides.clear()
    rss_factor = 1 if sys.platform == 'darwin' else 1024
    print(json.dumps({'timestamp_utc': timestamp.isoformat(), 'homes': 10000, 'observations': 100000,
                      'warmups': 3, 'samples': args.samples, 'rss_growth_bytes': max(0, peak_rss-baseline_rss)*rss_factor,
                      'results': results}, indent=2))
    engine.dispose()

if __name__ == '__main__':
    main()
