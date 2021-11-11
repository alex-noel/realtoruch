import hashlib
import json
from datetime import timedelta

from sqlalchemy import select, text

from .dedupe import matching_property
from .models import AlertEvent, EventReceipt, Listing, Observation, Outbox, SourceListing, now
from .normalization import normalize
from .schemas import RawListing

PROPERTY_FIELDS = (
    "title",
    "description",
    "city",
    "district",
    "region",
    "address",
    "lat",
    "lon",
    "area_m2",
    "rooms",
    "floor",
    "rent_pln",
    "fees_pln",
    "deposit_pln",
    "commission_pln",
    "advertiser_type",
    "property_type",
    "amenities",
    "images",
    "is_demo",
)


def recompute_listing(session, listing, *, new_property=False):
    tracked = (*PROPERTY_FIELDS, "status", "risk_flags", "risk_score")
    before = {field: getattr(listing, field) for field in tracked}
    sources = session.scalars(select(SourceListing).where(SourceListing.listing_id == listing.id)).all()
    active = [s for s in sources if s.status == "active"]
    eligible = active or [s for s in sources if s.status == "unknown"] or sources
    # Prefer an available, declared private offer. Keep every source's own price/fee evidence.
    chosen = sorted(
        eligible, key=lambda s: (s.data["advertiser_type"] != "private", -s.observed_at.timestamp())
    )[0]
    for field in PROPERTY_FIELDS:
        setattr(listing, field, chosen.data.get(field))
    listing.status = (
        "active" if active else ("unknown" if any(s.status == "unknown" for s in sources) else "inactive")
    )
    if listing.hidden:
        listing.status = "inactive"
    listing.last_seen = max(s.observed_at for s in sources)
    flags = []
    cutoff = now() - timedelta(days=90)
    for source in sources:
        if source.phone_hash and source.data["advertiser_type"] == "private" and source.status == "active":
            linked = session.scalars(
                select(SourceListing).where(
                    SourceListing.phone_hash == source.phone_hash,
                    SourceListing.status == "active",
                    SourceListing.observed_at >= cutoff,
                )
            ).all()
            count = len({s.listing_id for s in linked})
            if count >= 3:
                flags.append(
                    {
                        "code": "frequent_contact",
                        "severity": "medium",
                        "label": "Frequent advertiser",
                        "detail": f"The same contact appears on {count} distinct active homes in the last 90 days. This can indicate a professional or a multi-property owner; it is not proof of misrepresentation.",
                    }
                )
            if any(s.data["advertiser_type"] == "agency" for s in linked):
                flags.append(
                    {
                        "code": "mixed_identity",
                        "severity": "medium",
                        "label": "Advertiser type differs",
                        "detail": "This contact also appears on an offer declared as an agency listing. Check the advertiser and any commission.",
                    }
                )
    if active and max(s.data["rent_pln"] for s in active) > min(s.data["rent_pln"] for s in active) * 1.15:
        flags.append(
            {
                "code": "price_mismatch",
                "severity": "low",
                "label": "Prices differ across sources",
                "detail": "The active source prices differ by more than 15%. Check the latest terms with the advertiser.",
            }
        )
    if listing.advertiser_type == "private" and listing.commission_pln and listing.commission_pln > 0:
        flags.append(
            {
                "code": "private_commission",
                "severity": "medium",
                "label": "Commission on a private offer",
                "detail": "The source declares a private offer and also lists a commission.",
            }
        )
    listing.risk_flags = list({f["code"]: f for f in flags}.values())
    listing.risk_score = min(100, sum(30 if f["severity"] == "medium" else 15 for f in listing.risk_flags))
    canonical_changed = new_property or any(before[field] != getattr(listing, field) for field in tracked)
    if canonical_changed:
        listing.updated_at = now()
        session.add(AlertEvent(listing_id=listing.id))
    # Wait for an in-flight index write before deciding whether another event is needed.
    # Without the row lock, an indexer could acknowledge an old snapshot after this update.
    if not session.scalar(
        select(Outbox.id)
        .where(Outbox.listing_id == listing.id, Outbox.delivered_at.is_(None))
        .limit(1)
        .with_for_update()
    ):
        session.add(Outbox(listing_id=listing.id))


def ingest(session, raw: RawListing):
    """Caller owns transaction. Receipt, canonical update, history and outbox commit atomically."""
    data = normalize(raw)
    if session.bind.dialect.name == "postgresql":
        # Serialize canonical decisions within a city, including concurrent Dataflow workers.
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:city))"), {"city": data["city"].casefold()}
        )
    event_id = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    if session.get(EventReceipt, event_id):
        return {"status": "duplicate_event"}
    session.add(EventReceipt(id=event_id))
    source = session.scalar(
        select(SourceListing).where(
            SourceListing.source == raw.source, SourceListing.external_id == raw.external_id
        )
    )
    observed_at = raw.observed_at
    if source and source.observed_at >= observed_at:
        return {"status": "stale_event", "listing_id": source.listing_id}
    previous_phone = source.phone_hash if source else None
    previous_observed = source.observed_at if source else None
    new_property = False
    changed = not source or any(source.data.get(k) != data.get(k) for k in (*PROPERTY_FIELDS, "status"))
    if not source:
        listing, reason = None, "New property"
        if data["status"] == "active":
            candidates = session.scalars(
                select(Listing).where(
                    Listing.city == raw.city,
                    Listing.rooms == raw.rooms,
                    Listing.area_m2.between(raw.area_m2 - 3, raw.area_m2 + 3),
                )
            ).all()
            for candidate in candidates:
                related = session.scalars(
                    select(SourceListing).where(SourceListing.listing_id == candidate.id)
                ).all()
                reason_match = matching_property(candidate, data, related)
                if reason_match:
                    listing, reason = candidate, reason_match
                    break
        if not listing:
            new_property = True
            listing = Listing(
                **{k: data[k] for k in PROPERTY_FIELDS}, first_seen=observed_at, last_seen=observed_at
            )
            session.add(listing)
            session.flush()
        source = SourceListing(
            listing_id=listing.id,
            source=raw.source,
            external_id=raw.external_id,
            url=str(raw.url),
            data=data,
            observed_at=observed_at,
            match_reason=reason,
        )
        session.add(source)
    else:
        listing = session.get(Listing, source.listing_id)
    source.data, source.phone_hash = data, data["phone_hash"]
    source.url, source.status, source.observed_at = str(raw.url), raw.status, observed_at
    session.flush()
    # Keep all changes and one unchanged daily checkpoint for historical aggregates.
    latest_history = session.scalar(
        select(Observation.observed_at)
        .where(Observation.source_listing_id == source.id)
        .order_by(Observation.observed_at.desc())
        .limit(1)
    )
    if changed or not latest_history or latest_history.date() < observed_at.date():
        session.add(
            Observation(
                listing_id=listing.id,
                source_listing_id=source.id,
                observed_at=observed_at,
                rent_pln=raw.rent_pln,
                fees_pln=raw.fees_pln,
                status=raw.status,
                changed=changed,
            )
        )
    session.flush()
    affected = {listing.id}
    if (
        changed
        or previous_phone != source.phone_hash
        or (previous_observed and previous_observed < now() - timedelta(days=90))
    ):
        for phone in {source.phone_hash, previous_phone} - {None}:
            affected.update(
                session.scalars(
                    select(SourceListing.listing_id).where(SourceListing.phone_hash == phone)
                ).all()
            )
    for listing_id in affected:
        recompute_listing(
            session, session.get(Listing, listing_id), new_property=new_property and listing_id == listing.id
        )
    session.flush()
    return {
        "status": "updated" if changed else "checked",
        "listing_id": listing.id,
        "match_reason": source.match_reason,
    }
