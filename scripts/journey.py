#!/usr/bin/env python3
"""Reproducible synthetic lifecycle, isolated from the collected live catalog.

Start `make journey`, save a Kraków search, then run these events in order:
new, delist, relist, drop, delist. Open and like the home after `new`.
The running alert worker, rather than this script, generates notifications.
"""

import argparse
import os

from local import local_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", choices=["prepare", "new", "delist", "relist", "drop"])
    event = parser.parse_args().event
    os.environ.update(local_environment(journey=True))
    from realtoruch.db import Session, init_db
    from realtoruch.ingest import ingest
    from realtoruch.models import SourceListing
    from realtoruch.schemas import RawListing
    from sqlalchemy import select

    init_db()
    base = dict(
        source="otodom",
        url="https://www.otodom.pl/",
        title="Demo · Jasne mieszkanie w Krakowie",
        description="Fictional apartment for testing saved areas, reposts and price alerts. Not a real offer.",
        city="Kraków",
        region="małopolskie",
        district="Krowodrza",
        address="Testowa 12",
        area_m2=55,
        rooms=2,
        floor=2,
        fees_pln=500,
        commission_pln=0,
        advertiser_type="private",
        property_type="apartment",
        lat=50.075,
        lon=19.925,
        # Synthetic contact evidence; no real person's phone or photograph is used.
        phone="000000000",
        is_demo=True,
    )
    with Session.begin() as session:
        sources = session.scalars(
            select(SourceListing).where(
                SourceListing.source == "otodom",
                SourceListing.external_id.like("journey-%"),
            )
        ).all()
        if event == "prepare":
            if sources:
                print(
                    "Journey catalog already initialized; existing account data is preserved."
                )
                return
            result = ingest(
                session,
                RawListing(
                    **{
                        **base,
                        "external_id": "journey-baseline",
                        "address": "Testowa 99",
                        "images": [],
                        "rent_pln": 5200,
                        "title": "Demo · Existing home above the budget",
                    }
                ),
            )
        elif event == "delist":
            for source in sources:
                if (
                    source.external_id != "journey-baseline"
                    and source.status != "inactive"
                ):
                    ingest(
                        session,
                        RawListing(
                            **base,
                            external_id=source.external_id,
                            rent_pln=source.data["rent_pln"],
                            status="inactive",
                        ),
                    )
            result = {"status": "delisted"}
        else:
            # A repost replaces the previous advert, even if a separate delist wasn't run.
            for source in sources:
                if (
                    source.external_id != "journey-baseline"
                    and source.status != "inactive"
                ):
                    ingest(
                        session,
                        RawListing(
                            **base,
                            external_id=source.external_id,
                            rent_pln=source.data["rent_pln"],
                            status="inactive",
                        ),
                    )
            result = ingest(
                session,
                RawListing(
                    **base,
                    external_id=f"journey-{event}",
                    rent_pln=4200 if event == "drop" else 4500,
                ),
            )
        print(result)


if __name__ == "__main__":
    main()
