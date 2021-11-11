#!/usr/bin/env python3
"""Run bounded real collection cycles; emit evidence without claiming exhaustive coverage."""

import argparse
import json
import os
import sys
import time

from local import ROOT, local_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=3, choices=range(1, 25))
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--city", default="Kraków")
    parser.add_argument("--max-listings", type=int, default=2)
    parser.add_argument("--max-rechecks", type=int, default=2)
    args = parser.parse_args()
    if (
        args.interval < 30
        or not 0 <= args.max_listings <= 20
        or not 0 <= args.max_rechecks <= 50
    ):
        parser.error(
            "Use an interval of at least 30s and bounded collection sizes (0–20 new, 0–50 rechecks)."
        )
    os.environ.update(local_environment(live=True))
    from realtoruch.db import Session, init_db
    from realtoruch.models import (
        EventReceipt,
        Listing,
        Observation,
        Outbox,
        SourceListing,
    )
    from realtoruch.worker import CollectionFailed, collect
    from sqlalchemy import func, select

    init_db()
    results = []
    destination = ROOT / ".local/reliability.json"

    def counts():
        with Session() as session:
            return {
                model.__tablename__: session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (Listing, SourceListing, Observation, EventReceipt, Outbox)
            }

    before = counts()
    for cycle in range(args.cycles):
        started = time.monotonic()
        try:
            report = collect(
                city=args.city,
                workers=3,
                limits={
                    "max_pages": 1,
                    "max_listings": args.max_listings,
                    "max_rechecks": args.max_rechecks,
                },
            )
        except CollectionFailed as exc:
            report = exc.reports
        results.append(
            {
                "cycle": cycle + 1,
                "duration_seconds": round(time.monotonic() - started, 2),
                "sources": report,
                "counts": counts(),
            }
        )
        destination.write_text(
            json.dumps({"before": before, "cycles": results}, indent=2) + "\n"
        )
        print(json.dumps(results[-1]), flush=True)
        if cycle + 1 < args.cycles:
            time.sleep(args.interval)
    return int(
        any(
            source["status"] in ("failed", "partial")
            for cycle in results
            for source in cycle["sources"]
        )
    )


if __name__ == "__main__":
    sys.exit(main())
