#!/usr/bin/env python3
"""Bounded read-only local API load check. Does not run against public hosts."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from statistics import median
from urllib.parse import urlsplit

import httpx
from local import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    if urlsplit(args.url).hostname not in ("localhost", "127.0.0.1", "::1"):
        parser.error("This rehearsal only accepts loopback hosts.")
    if not 1 <= args.requests <= 2000 or not 1 <= args.concurrency <= 20:
        parser.error("Use 1–2000 requests and 1–20 concurrent clients.")
    paths = [
        "/v1/listings?city=Krak%C3%B3w&max_price=5000&min_area=50&advertiser=private",
        "/v1/market/summary?city=Krak%C3%B3w",
        "/v1/market/history?city=Krak%C3%B3w",
        "/v1/sources",
    ]
    with httpx.Client(
        base_url=args.url,
        timeout=10,
        limits=httpx.Limits(max_connections=args.concurrency),
    ) as client:

        def sample(i):
            started = time.perf_counter()
            try:
                response = client.get(paths[i % len(paths)])
                status = response.status_code
                if status == 200:
                    response.json()
            except (httpx.HTTPError, ValueError):
                status = 0
            return status, (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(sample, range(args.requests)))
        elapsed = time.perf_counter() - started
    times = sorted(duration for _, duration in results)
    statuses = {
        str(status): sum(s == status for s, _ in results) for status, _ in results
    }
    report = {
        "requests": args.requests,
        "concurrency": args.concurrency,
        "statuses": statuses,
        "elapsed_seconds": round(elapsed, 3),
        "requests_per_second": round(args.requests / elapsed, 1),
        "median_ms": round(median(times), 1),
        "p95_ms": round(times[min(len(times) - 1, int(len(times) * 0.95))], 1),
        "max_ms": round(max(times), 1),
        "scope": "Local read-only sample; not an SLA or production capacity measurement",
    }
    (ROOT / ".local").mkdir(exist_ok=True)
    (ROOT / ".local/load-check.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(any(status != 200 for status, _ in results))


if __name__ == "__main__":
    raise SystemExit(main())
