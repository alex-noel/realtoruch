#!/usr/bin/env python3
"""Bounded, loopback-only read load. Run only against a disposable test service."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
import subprocess
import threading
import time
from urllib.parse import urlsplit

import httpx
from local import ROOT


def percentile(values, q):
    values = sorted(values)
    return values[math.ceil(q * len(values)) - 1] if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8000')
    parser.add_argument('--search-url', help='Second loopback API configured for ES-backed search')
    parser.add_argument('--sql-engine', choices=['postgresql', 'sqlite'], help='Expected SQL engine for discovery responses')
    parser.add_argument('--requests', type=int, default=200, help='Maximum measured requests')
    parser.add_argument('--duration', type=float, default=0, help='Stop dispatching after this many seconds; 0 uses request cap only')
    parser.add_argument('--warmup', type=float, default=0, help='Warmup seconds, excluded from measurements')
    parser.add_argument('--concurrency', type=int, default=8)
    parser.add_argument('--city', default='Kraków')
    parser.add_argument('--profile', choices=['quota', 'capacity'], default='quota')
    parser.add_argument('--capacity-limit', type=int, help='Explicit isolated service requests/minute limit for capacity profile')
    parser.add_argument('--api-pid', type=int, action='append', help='Local API process PID for sampled RSS; repeat for each process')
    parser.add_argument('--output', default=str(ROOT / '.local/load-check.json'))
    args = parser.parse_args()
    if any(urlsplit(url).hostname not in ('localhost', '127.0.0.1', '::1')
           for url in (args.url, args.search_url) if url):
        parser.error('Only loopback hosts are allowed.')
    if not 1 <= args.requests <= 1000000 or not 1 <= args.concurrency <= 20 or not 0 <= args.duration <= 600 or not 0 <= args.warmup <= 120:
        parser.error('Use <=1,000,000 requests, <=20 clients, <=600 seconds and <=120 warmup seconds.')
    if args.profile == 'capacity' and (args.capacity_limit is None or args.capacity_limit < 1):
        parser.error('Capacity profile requires the explicit isolated test limit.')
    filters = {'city': args.city, 'max_price': 5000, 'max_price_exclusive': 'true',
               'min_area': 50, 'advertiser': 'private'}
    geo_filters = {**filters, 'polygon': '[[19.90,50.02],[20.02,50.02],[20.02,50.10],[19.90,50.10]]'}
    paths = [('sql_search', args.url, '/v1/listings', filters),
             ('sql_search_geo', args.url, '/v1/listings', geo_filters),
             ('summary', args.url, '/v1/market/summary', {'city': args.city}),
             ('history', args.url, '/v1/market/history', {'city': args.city})]
    if args.search_url:
        paths.insert(1, ('es_rest_search', args.search_url, '/v1/listings', filters))
        paths.insert(2, ('es_rest_search_geo', args.search_url, '/v1/listings', geo_filters))
    results = defaultdict(list)
    statuses = defaultdict(Counter)
    engines = defaultdict(Counter)
    degraded = defaultdict(Counter)
    lock = threading.Lock()
    counter = 0
    max_rss = {pid: 0 for pid in args.api_pid or []}
    with httpx.Client(timeout=30, limits=httpx.Limits(max_connections=args.concurrency)) as client:
        def request(i, record):
            label, base, path, params = paths[i % len(paths)]
            start = time.perf_counter()
            body = None
            try:
                response = client.get(base.rstrip('/') + path, params=params)
                status = response.status_code
                if status == 200:
                    body = response.json()
            except (httpx.HTTPError, ValueError):
                status = 0
            elapsed = (time.perf_counter() - start) * 1000
            if record:
                with lock:
                    statuses[label][str(status)] += 1
                    if status == 200:
                        results[label].append(elapsed)
                        if label.startswith(('sql_search', 'es_rest_search')):
                            engines[label][str(body.get('engine') if isinstance(body, dict) else None)] += 1
                            degraded[label][str(body.get('degraded') if isinstance(body, dict) else None)] += 1
        def run_phase(seconds, cap, record):
            nonlocal counter, max_rss
            deadline = time.monotonic() + seconds if seconds else float('inf')
            counter = 0
            def worker():
                nonlocal counter, max_rss
                while True:
                    with lock:
                        if counter >= cap or time.monotonic() >= deadline:
                            return
                        i = counter
                        counter += 1
                    request(i, record)
                    if record and args.api_pid and i % 20 == 0:
                        for pid in args.api_pid:
                            proc = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True)
                            if proc.returncode == 0 and proc.stdout.strip():
                                with lock:
                                    max_rss[pid] = max(max_rss[pid], int(proc.stdout.strip()) * 1024)
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                list(pool.map(lambda _: worker(), range(args.concurrency)))
        if args.warmup:
            run_phase(args.warmup, args.requests, False)
        start = time.monotonic()
        run_phase(args.duration, args.requests, True)
        elapsed = time.monotonic() - start
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'profile': args.profile,
              'declared_capacity_limit_per_minute': args.capacity_limit, 'concurrency': args.concurrency,
              'warmup_seconds': args.warmup, 'requested_duration_seconds': args.duration,
              'elapsed_seconds': elapsed, 'requests': counter, 'requests_per_second': counter / elapsed,
              'sampled_max_rss_bytes_by_pid': max_rss or None,
              'endpoints': {label: {'statuses': dict(statuses[label]), 'success_count': len(results[label]),
                                    'engines': dict(engines[label]), 'degraded': dict(degraded[label]),
                                    'p50_ms': percentile(results[label], .50), 'p95_ms': percentile(results[label], .95),
                                    'p99_ms': percentile(results[label], .99), 'success_samples_ms': results[label]}
                            for label, _, _, _ in paths},
              'note': 'Nearest-rank percentiles include only HTTP 200; all other statuses are reported separately.'}
    if args.profile == 'capacity':
        limits = {'sql_search': 300, 'sql_search_geo': 300, 'es_rest_search': 250,
                  'es_rest_search_geo': 250, 'summary': 300, 'history': 750}
        report['targets'] = {}
        for label, _, _, _ in paths:
            p95 = report['endpoints'][label]['p95_ms']
            report['targets'][label + '_p95'] = ('NOT_RUN' if p95 is None else
                                                 'PASS' if p95 <= limits[label] else 'FAIL')
        report['targets']['api_rss_below_500_mib'] = ('NOT_RUN' if not max_rss or not all(max_rss.values()) else
            'PASS' if all(value < 500 * 1024 * 1024 for value in max_rss.values()) else 'FAIL')
        report['targets']['no_non_200'] = ('PASS' if counter and all(set(statuses[label]) == {'200'} for label, _, _, _ in paths) else 'FAIL')
        report['targets']['five_minutes_20_clients'] = ('PASS' if args.duration >= 300 and args.concurrency == 20 and elapsed >= 300 else 'NOT_RUN')
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    print(json.dumps(report, indent=2))
    wrong_engine = any(
        (label.startswith('es_rest_search') and engine != 'elasticsearch') or
        (label.startswith('sql_search') and args.sql_engine and engine != args.sql_engine)
        for label, counts in engines.items() for engine in counts
    )
    failed_targets = (args.profile == 'capacity' and args.duration >= 300 and
                      any(value != 'PASS' for value in report['targets'].values()))
    return int(not counter or failed_targets or any(not statuses[label] for label, _, _, _ in paths) or wrong_engine
               or any(value != 'False' for counts in degraded.values() for value in counts)
               or any(status not in ('200', '429') or (status == '429' and args.profile == 'capacity')
                      for counts in statuses.values() for status in counts))


if __name__ == '__main__':
    raise SystemExit(main())
