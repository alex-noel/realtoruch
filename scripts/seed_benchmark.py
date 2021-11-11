"""Seed and benchmark a disposable database. Never point this at a real catalog."""
import argparse
import json
import math
import os
import resource
import sys
import time
import tracemalloc
from datetime import timedelta

# The API lifespan must never initialize a developer's configured database.
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['AUTH_DATABASE_URL'] = 'sqlite://'
os.environ['ENVIRONMENT'] = 'test'

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from realtoruch.db import Base
from realtoruch.models import Listing, SourceListing, Observation, now
from realtoruch.query import market_history, market_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True, help='Empty disposable database only')
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--measure-only', action='store_true', help='Measure an already seeded disposable database in a fresh process')
    args = parser.parse_args()
    engine = create_engine(args.url)
    from sqlalchemy import inspect
    if not args.measure_only and inspect(engine).get_table_names():
        raise SystemExit('Refusing nonempty database')
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
