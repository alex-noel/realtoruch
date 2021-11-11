#!/usr/bin/env python3
"""Import an operator-supplied public listing HTML snapshot. No network fetches."""

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from local import local_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", required=True, choices=["olx", "otodom", "gratka", "morizon"]
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--city", required=True)
    args = parser.parse_args()
    if args.html.stat().st_size > 5_000_000:
        parser.error("Snapshot exceeds the 5MB limit")
    observed = datetime.fromtimestamp(args.html.stat().st_mtime, timezone.utc)
    if (datetime.now(timezone.utc) - observed).total_seconds() > 86400:
        parser.error("Capture a fresh page; this snapshot is over 24 hours old")
    os.environ.update(local_environment(live=True))
    from realtoruch.db import Session, init_db
    from realtoruch.ingest import ingest
    from realtoruch.portals import parse_detail
    from realtoruch.schemas import RawListing

    raw = parse_detail(args.source, args.html.read_text(), args.url, city=args.city)
    raw = RawListing.model_validate({**raw.model_dump(), "observed_at": observed})
    init_db()
    with Session.begin() as session:
        result = ingest(session, raw)
    print({"source": args.source, "transport": "operator_html_snapshot", **result})


if __name__ == "__main__":
    main()
