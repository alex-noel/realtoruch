import argparse
import json
import logging
import time
from datetime import timedelta
from sqlalchemy import delete, select
from .connectors import Connector, load_sources
from .db import Session, init_db
from .ingest import ingest, recompute_listing
from .models import Listing, SourceListing, Outbox, EventReceipt, now
from .normalization import normalize
from .query import serialize_many
from .search import es_client, INDEX
from .settings import get_settings

log = logging.getLogger("realtoruch.worker")


def publish(raw):
    from google.cloud import bigtable, pubsub_v1
    import hashlib

    settings = get_settings()
    data = json.dumps(normalize(raw), sort_keys=True).encode()
    event_id = hashlib.sha256(data).hexdigest()
    table = (
        bigtable.Client(project=settings.gcp_project)
        .instance(settings.bigtable_instance)
        .table(settings.bigtable_table)
    )
    # HMAC only: no raw phone enters Bigtable or Pub/Sub.
    row = table.direct_row(f"{event_id[:2]}#{raw.source}#{event_id}")
    row.set_cell("raw", "payload", data)
    row.commit()
    state = table.direct_row(f"state#{raw.source}#{hashlib.sha256(str(raw.url).encode()).hexdigest()}")
    state.set_cell("raw", "payload", data)
    state.commit()
    publisher = pubsub_v1.PublisherClient()
    publisher.publish(
        publisher.topic_path(settings.gcp_project, settings.pubsub_topic),
        data,
        event_id=event_id,
        source=raw.source,
    ).result(timeout=30)


def collect(cloud=False):
    failures = 0
    for config in load_sources():
        if not config.get("enabled"):
            continue
        connector = Connector(config)
        try:
            if config.get("mode") == "jsonld":
                entries = []
                for entry in config.get("listing_urls", []):
                    entry = {"url": entry} if isinstance(entry, str) else dict(entry)
                    previous = None
                    if cloud:
                        from google.cloud import bigtable
                        import hashlib

                        settings = get_settings()
                        table = (
                            bigtable.Client(project=settings.gcp_project)
                            .instance(settings.bigtable_instance)
                            .table(settings.bigtable_table)
                        )
                        row = table.read_row(
                            f"state#{config['name']}#{hashlib.sha256(entry['url'].encode()).hexdigest()}"
                        )
                        if row and row.cells.get("raw", {}).get(b"payload"):
                            previous = json.loads(row.cells["raw"][b"payload"][0].value)
                    else:
                        with Session() as session:
                            source = session.scalar(
                                select(SourceListing).where(
                                    SourceListing.source == config["name"], SourceListing.url == entry["url"]
                                )
                            )
                            previous = source.data if source else None
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
        except Exception as exc:
            # Log class only: upstream errors might contain a credential-bearing URL or raw contact data.
            log.error("source_failed source=%s error=%s", config["name"], type(exc).__name__)
            failures += 1
        finally:
            connector.close()
    if failures:
        raise RuntimeError(f"{failures} source(s) failed; no listings were inferred inactive")


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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
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
            collect(args.cloud)
        elif args.command == "index":
            index_once()
        else:
            retention()
        if not args.loop:
            break
        time.sleep(5 if args.command == "index" else 21600)


if __name__ == "__main__":
    main()
