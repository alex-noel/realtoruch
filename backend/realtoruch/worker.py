import argparse
import json
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from .connectors import Connector, load_sources
from .db import Session, init_db
from .ingest import ingest, recompute_listing
from .models import EventReceipt, Listing, Outbox, SourceListing, now
from .normalization import normalize
from .query import serialize_many
from .search import INDEX, es_client
from .settings import get_settings

log = logging.getLogger("realtoruch.worker")


def state_table():
    from google.cloud import bigtable

    settings = get_settings()
    return (
        bigtable.Client(project=settings.gcp_project)
        .instance(settings.bigtable_instance)
        .table(settings.bigtable_table)
    )


def state_key(source, url):
    import hashlib

    return f"state#{source}#{hashlib.sha256(url.encode()).hexdigest()}"


def recheck_key(data):
    # Lexically ordered observation time gives the oldest checked advert priority.
    return f"recheck#{data['source']}#{data['observed_at']}#{state_key(data['source'], data['url']).split('#')[-1]}"


def row_payload(row):
    cells = row.cells.get("raw", {}).get(b"payload") if row else None
    return json.loads(cells[0].value) if cells else None


def publish(raw):
    import hashlib

    from google.cloud import pubsub_v1

    settings = get_settings()
    normalized = normalize(raw)
    data = json.dumps(normalized, sort_keys=True).encode()
    event_id = hashlib.sha256(data).hexdigest()
    table = state_table()
    key = state_key(raw.source, str(raw.url))
    previous = row_payload(table.read_row(key))
    if previous and datetime.fromisoformat(previous["observed_at"]) >= raw.observed_at:
        return
    # HMAC only: no raw phone enters Bigtable or Pub/Sub.
    row = table.direct_row(f"{event_id[:2]}#{raw.source}#{event_id}")
    row.set_cell("raw", "payload", data)
    row.commit()
    publisher = pubsub_v1.PublisherClient()
    publisher.publish(
        publisher.topic_path(settings.gcp_project, settings.pubsub_topic),
        data,
        event_id=event_id,
        source=raw.source,
    ).result(timeout=30)
    # Advance state only after publication succeeds, so a failed publish stays due.
    if normalized["status"] != "inactive":
        due = table.direct_row(recheck_key(normalized))
        due.set_cell("raw", "payload", data)
        due.commit()
    state = table.direct_row(key)
    state.set_cell("raw", "payload", data)
    state.commit()
    if previous and recheck_key(previous) != recheck_key(normalized):
        old = table.direct_row(recheck_key(previous))
        old.delete()
        old.commit()


class CollectionFailed(RuntimeError):
    def __init__(self, reports):
        self.reports = reports
        super().__init__("One or more sources failed; inspect the collection report")


def source_state(config, cloud):
    limit = min(500, max(0, int(config.get("max_rechecks", 50))))
    source = config["name"]
    if cloud:
        table = state_table()

        def lookup(url):
            return row_payload(table.read_row(state_key(source, url)))

        known = []
        if limit:
            prefix = f"recheck#{source}#"
            for row in table.read_rows(start_key=prefix, end_key=prefix + "\uffff", limit=limit):
                previous = row_payload(row)
                if not previous:
                    continue
                current = lookup(previous["url"])
                if current and current["observed_at"] == previous["observed_at"]:
                    known.append({"url": current["url"], "previous": current})
                else:
                    stale = table.direct_row(row.row_key)
                    stale.delete()
                    stale.commit()
        return lookup, known

    def lookup(url):
        with Session() as session:
            prior = session.scalar(
                select(SourceListing).where(
                    SourceListing.source == source,
                    SourceListing.url == url,
                )
            )
            return prior.data if prior and not prior.data.get("is_demo") else None

    with Session() as session:
        prior = session.scalars(
            select(SourceListing)
            .join(Listing)
            .where(
                SourceListing.source == source,
                SourceListing.status != "inactive",
                Listing.is_demo.is_(False),
            )
            .order_by(SourceListing.observed_at, SourceListing.id)
            .limit(limit)
        ).all()
        return lookup, [{"url": p.url, "previous": p.data} for p in prior]


def collect(cloud=False, *, source_names=None, limits=None):
    reports = []
    configurations = load_sources()
    if source_names:
        missing = set(source_names) - {c["name"] for c in configurations}
        if missing:
            raise ValueError("Unknown source selection")
        configurations = [c for c in configurations if c["name"] in source_names]
    for configured in configurations:
        config = {**configured, **(limits or {})}
        if not config.get("enabled"):
            reports.append({"source": config["name"], "status": "disabled", "errors": []})
            continue
        connector = Connector(config)
        started = now().isoformat() + "Z"
        ingested = 0
        try:
            if config.get("mode") in ("jsonld", "portal"):
                lookup, known = source_state(config, cloud)
                connector.previous_lookup, connector.known_urls = lookup, known
                if config["mode"] == "jsonld":
                    entries = []
                    for entry in config.get("listing_urls", []):
                        entry = {"url": entry} if isinstance(entry, str) else dict(entry)
                        previous = lookup(entry["url"])
                        if previous:
                            entry["previous"] = previous
                        entries.append(entry)
                    connector.config = {**config, "listing_urls": entries}
            for raw in connector.records():
                if cloud:
                    publish(raw)
                else:
                    with Session.begin() as session:
                        ingest(session, raw)
                ingested += 1
        except Exception as exc:
            # Store class/status only; upstream exceptions may contain raw contact data or secrets.
            if not connector.report["errors"]:
                connector.note_error(exc, "collection")
            log.error("source_failed source=%s error=%s", config["name"], type(exc).__name__)
        finally:
            connector.close()
        report = {
            **connector.report,
            "ingested": ingested,
            "started_at": started,
            "finished_at": now().isoformat() + "Z",
        }
        report["status"] = ("partial" if ingested else "failed") if report["errors"] else "succeeded"
        reports.append(report)
        log.info("collection_report %s", json.dumps(report, sort_keys=True))
    if any(report["errors"] for report in reports):
        raise CollectionFailed(reports)
    return reports


def create_index(client):
    if client.head(f"/{INDEX}").status_code == 200:
        return
    properties = {
        key: {"type": "keyword"}
        for key in (
            "id",
            "city",
            "district",
            "region",
            "status",
            "advertiser_type",
            "property_type",
            "amenities",
        )
    }
    properties.update({key: {"type": "text"} for key in ("title", "description", "address")})
    properties.update(
        {
            key: {"type": "integer"}
            for key in ("rent_pln", "fees_pln", "commission_pln", "rooms", "risk_score")
        }
    )
    properties.update(
        {"area_m2": {"type": "float"}, "location": {"type": "geo_point"}, "first_seen": {"type": "date"}}
    )
    response = client.put(
        f"/{INDEX}",
        json={
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {"dynamic": False, "properties": properties},
        },
    )
    if response.status_code != 400 or "resource_already_exists_exception" not in response.text:
        response.raise_for_status()


def index_once():
    with es_client() as client, Session.begin() as session:
        create_index(client)
        events = session.scalars(
            select(Outbox)
            .where(Outbox.delivered_at.is_(None))
            .order_by(Outbox.created_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        ).all()
        # Each write reads the latest canonical state, so retrying an old event cannot roll the index back.
        for event in events:
            listing = session.get(Listing, event.listing_id)
            document = serialize_many(session, [listing])[0]
            if listing.lat is not None:
                document["location"] = {"lat": listing.lat, "lon": listing.lon}
            client.put(f"/{INDEX}/_doc/{listing.id}", json=document).raise_for_status()
            event.delivered_at = now()
        return len(events)


def retention():
    settings = get_settings()
    cutoff = now() - timedelta(days=settings.contact_retention_days)
    with Session.begin() as session:
        affected = set()
        changed_phones = set()
        for source in session.scalars(
            select(SourceListing).where(
                SourceListing.observed_at < cutoff, SourceListing.phone_hash.is_not(None)
            )
        ):
            if source.phone_hash:
                changed_phones.add(source.phone_hash)
            source.phone_hash = None
            source.data = {**source.data, "phone_hash": None}
            affected.add(source.listing_id)
        # Stale sources are unknown, not claimed inactive; another active source keeps the home visible.
        for source in session.scalars(
            select(SourceListing).where(
                SourceListing.observed_at < now() - timedelta(days=7), SourceListing.status == "active"
            )
        ):
            if source.phone_hash:
                changed_phones.add(source.phone_hash)
            source.status = "unknown"
            source.data = {**source.data, "status": "unknown"}
            affected.add(source.listing_id)
        session.flush()
        if changed_phones:
            affected.update(
                session.scalars(
                    select(SourceListing.listing_id).where(SourceListing.phone_hash.in_(changed_phones))
                ).all()
            )
        for listing_id in affected:
            recompute_listing(session, session.get(Listing, listing_id))
        session.execute(delete(EventReceipt).where(EventReceipt.received_at < cutoff))
        session.execute(delete(Outbox).where(Outbox.delivered_at < now() - timedelta(days=7)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "index", "retention", "migrate"])
    parser.add_argument("--cloud", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--source", action="append", help="Collect only this configured source; repeatable")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-listings", type=int)
    parser.add_argument("--max-rechecks", type=int)
    parser.add_argument("--recheck-only", action="store_true", help="Refresh stored adverts without discovery")
    parser.add_argument("--report", help="Write a machine-readable collection report")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.command == "migrate":
        if get_settings().environment == "production":
            raise SystemExit(
                "Apply the versioned SQL migrations as an operator; application identities cannot create tables"
            )
        init_db()
        from .auth import AuthBase, auth_engine

        AuthBase.metadata.create_all(auth_engine)
        return
    while True:
        if args.command == "collect":
            limits = {
                name: getattr(args, name)
                for name in ("max_pages", "max_listings", "max_rechecks")
                if getattr(args, name) is not None
            }
            if args.recheck_only:
                limits.update(search_urls=[], listing_urls=[], recheck_only=True)
            failure = False
            try:
                reports = collect(args.cloud, source_names=args.source, limits=limits)
            except CollectionFailed as exc:
                reports, failure = exc.reports, True
            if args.report:
                from pathlib import Path

                destination = Path(args.report)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps({"sources": reports}, indent=2) + "\n")
            if failure and not args.loop:
                raise SystemExit(1)
        elif args.command == "index":
            index_once()
        else:
            retention()
        if not args.loop:
            break
        time.sleep(5 if args.command == "index" else 21600)


if __name__ == "__main__":
    main()
