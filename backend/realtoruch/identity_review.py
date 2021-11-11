"""Audited human corrections of canonical identity, preserving users' history."""

import hashlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text, update

from .account_data import guard_account_write
from .alerts import insert_once, process_alerts
from .db import get_session
from .ingest import PROPERTY_FIELDS, lock_identity, recompute_listing
from .marketplace import require_moderator
from .models import (
    Advert,
    AlertEvent,
    EmailDelivery,
    Favorite,
    IdentityDecision,
    Listing,
    ListingAlias,
    Notification,
    Observation,
    Outbox,
    PushDelivery,
    Report,
    SavedSearch,
    SearchMatch,
    SeenPrice,
    SourceListing,
    now,
)
from .normalization import fold
from .query import filtered_query, serialize_many
from .schemas import SearchFilters

router = APIRouter(tags=["Identity review"])

MAX_MERGE_EVENTS = 100


def resolve_id(session, listing_id):
    alias = session.get(ListingAlias, listing_id)
    return alias.listing_id if alias else listing_id


def copy_preferences(session, source_id, target_id, *, move):
    for favorite in session.scalars(select(Favorite).where(Favorite.listing_id == source_id)).all():
        existing = session.get(Favorite, (favorite.user_id, target_id))
        floor = favorite.price_floor or session.get(Listing, source_id).rent_pln
        if existing:
            existing.price_floor = min(existing.price_floor or floor, floor)
            existing.created_at = min(existing.created_at, favorite.created_at)
        else:
            session.add(
                Favorite(
                    user_id=favorite.user_id,
                    listing_id=target_id,
                    price_floor=floor,
                    created_at=favorite.created_at,
                )
            )
        if move:
            session.delete(favorite)
    for model, fields in (
        (SeenPrice, ("user_id", "rent_pln", "seen_at")),
        (SearchMatch, ("search_id", "created_at")),
    ):
        for row in session.scalars(select(model).where(model.listing_id == source_id)).all():
            insert_once(
                session, model, {"listing_id": target_id, **{key: getattr(row, key) for key in fields}}
            )
            if move:
                session.delete(row)
    session.flush()


def baseline_corrected_home(session, home):
    """Account silently for newly linked prices, without inventing past favorites.

    Genuine pending work is evaluated against each original card before merge.
    After correction, never raise a historical floor; a lower selected price
    becomes the new silent baseline, including while hidden or inactive.
    """
    visible_active = home.status == "active" and not home.hidden
    for favorite in session.scalars(select(Favorite).where(Favorite.listing_id == home.id)).yield_per(100):
        favorite.price_floor = (home.rent_pln if favorite.price_floor is None
                                else min(favorite.price_floor, home.rent_pln))
    session.flush()
    if not visible_active:
        return
    searches = session.scalars(select(SavedSearch).where(
        SavedSearch.city_key.in_(["", fold(home.city)])
    )).yield_per(100)
    for search in searches:
        if session.get(SearchMatch, (search.id, home.id)):
            continue
        match = session.scalar(filtered_query(SearchFilters(**search.filters))
                               .with_only_columns(Listing.id).where(Listing.id == home.id))
        if match:
            insert_once(session, SearchMatch, {"search_id": search.id, "listing_id": home.id})


class MergeBody(BaseModel):
    target_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=10, max_length=1000)


class SplitBody(BaseModel):
    source_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=10, max_length=1000)


@router.get("/v1/moderation/listings/{listing_id}/identity")
def evidence(listing_id: str, _=Depends(require_moderator), session=Depends(get_session)):
    home = session.get(Listing, resolve_id(session, listing_id))
    if not home:
        raise HTTPException(404, "Home not found")
    sources = session.scalars(select(SourceListing).where(SourceListing.listing_id == home.id)).all()
    candidates = session.scalars(
        select(Listing)
        .where(
            Listing.id != home.id,
            Listing.city == home.city,
            Listing.rooms == home.rooms,
            Listing.area_m2.between(home.area_m2 - 3, home.area_m2 + 3),
            Listing.is_demo == home.is_demo,
            ~Listing.id.in_(select(ListingAlias.old_id)),
        )
        .order_by(Listing.updated_at.desc())
        .limit(20)
    ).all()
    return {
        "sources": [
            {
                "id": s.id,
                "name": s.source,
                "url": s.url,
                "title": s.data["title"],
                "address": s.data["address"],
                "rent_pln": s.data["rent_pln"],
            }
            for s in sources
        ],
        "candidates": serialize_many(session, candidates),
    }


@router.post("/v1/moderation/listings/{listing_id}/merge")
def merge(
    listing_id: str, body: MergeBody, moderator=Depends(require_moderator), session=Depends(get_session)
):
    lock_identity(session)
    guard_account_write(session, moderator)
    session.expire_all()
    source_id, target_id = resolve_id(session, listing_id), resolve_id(session, body.target_id)
    if source_id == target_id:
        raise HTTPException(409, "Home identity has changed; reload before correcting")
    candidate, other = session.get(Listing, source_id), session.get(Listing, target_id)
    if not candidate or not other:
        raise HTTPException(404, "Home not found")
    if candidate.city != other.city:
        raise HTTPException(422, "Homes must be in the same city")
    if session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:city))"), {"city": candidate.city.casefold()}
        )
    homes = session.scalars(
        select(Listing).where(Listing.id.in_([source_id, target_id])).order_by(Listing.id).with_for_update()
    ).all()
    if len(homes) != 2:
        raise HTTPException(404, "Home not found")
    source, target = session.get(Listing, source_id), session.get(Listing, target_id)
    if (
        source.city != target.city
        or source.is_demo != target.is_demo
        or source.property_type != target.property_type
    ):
        raise HTTPException(422, "Homes must have the same city, category and dataset")
    sources = session.scalars(select(SourceListing).where(SourceListing.listing_id == source_id)).all()
    if not sources:
        raise HTTPException(409, "Source identity has already changed")
    # Evaluate real pending work against each original card before changing its
    # identity or price. Large backlogs can be drained normally and retried.
    pending = session.scalars(select(AlertEvent.id).where(
        AlertEvent.listing_id.in_([source_id, target_id]), AlertEvent.processed_at.is_(None)
    ).limit(MAX_MERGE_EVENTS + 1)).all()
    if len(pending) > MAX_MERGE_EVENTS:
        raise HTTPException(409, "Pending alert state prevents this merge; drain it and retry")
    created = []
    if pending:
        process_alerts(session, limit=MAX_MERGE_EVENTS, listing_ids=[source_id, target_id],
                       created_notifications=created)
        if session.scalar(select(AlertEvent.id).where(
            AlertEvent.listing_id.in_([source_id, target_id]), AlertEvent.processed_at.is_(None)
        ).limit(1)):
            raise HTTPException(409, "Pending alert state prevents this merge; retry after it is resolved")
    # Two pre-correction cards can produce both kinds for the same user/price.
    # Suppress only a newly created new-match, never historical notifications.
    drops = {(item.user_id, item.rent_pln) for item in created if item.kind == "price_drop"}
    for item in created:
        if item.kind == "new_match" and (item.user_id, item.rent_pln) in drops:
            session.execute(delete(EmailDelivery).where(EmailDelivery.notification_id == item.id))
            session.execute(delete(PushDelivery).where(PushDelivery.notification_id == item.id))
            session.delete(item)
    session.flush()
    copy_preferences(session, source_id, target_id, move=True)
    for notification in session.scalars(
        select(Notification).where(Notification.listing_id == source_id)
    ).all():
        key = hashlib.sha256(
            f"{notification.user_id}:{target_id}:{notification.kind}:{notification.rent_pln}".encode()
        ).hexdigest()
        existing = session.scalar(select(Notification).where(Notification.dedupe_key == key))
        if existing:
            session.execute(delete(EmailDelivery).where(EmailDelivery.notification_id == notification.id))
            session.execute(delete(PushDelivery).where(PushDelivery.notification_id == notification.id))
            if notification.read_at and not existing.read_at:
                existing.read_at = notification.read_at
            session.delete(notification)
        else:
            notification.listing_id, notification.dedupe_key = target_id, key
    for model in (SourceListing, Observation, Advert, Report):
        session.execute(update(model).where(model.listing_id == source_id).values(listing_id=target_id))
    session.execute(
        update(ListingAlias).where(ListingAlias.listing_id == source_id).values(listing_id=target_id)
    )
    session.add(ListingAlias(old_id=source_id, listing_id=target_id))
    target.hidden = target.hidden or source.hidden
    source.status, source.hidden = "inactive", True
    target.first_seen = min(source.first_seen, target.first_seen)
    session.flush()
    from .indexing import queue_listing
    # Queue in ID order; recomputation itself queues the target revision.
    if source_id < target_id:
        queue_listing(session, source_id)
    recompute_listing(session, target, identity_correction=True)
    baseline_corrected_home(session, target)
    if source_id > target_id:
        queue_listing(session, source_id)
    session.add(
        IdentityDecision(
            moderator_id=moderator,
            from_listing_id=source_id,
            to_listing_id=target_id,
            source_ids=[s.id for s in sources],
            action="merge",
            reason=body.reason,
        )
    )
    session.commit()
    return {
        "listing_id": target_id,
        "message": "Homes merged. Favorites, seen prices and alert history were retained.",
    }


@router.post("/v1/moderation/listings/{listing_id}/split")
def split(
    listing_id: str, body: SplitBody, moderator=Depends(require_moderator), session=Depends(get_session)
):
    lock_identity(session)
    guard_account_write(session, moderator)
    session.expire_all()
    candidate = session.get(Listing, resolve_id(session, listing_id))
    if candidate and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:city))"), {"city": candidate.city.casefold()}
        )
    home = session.scalar(
        select(Listing).where(Listing.id == resolve_id(session, listing_id)).with_for_update()
    )
    source = session.get(SourceListing, body.source_id)
    if not home or not source or source.listing_id != home.id:
        raise HTTPException(409, "Source identity has changed; reload before correcting")
    sources = session.scalars(select(SourceListing).where(SourceListing.listing_id == home.id)).all()
    if len(sources) < 2:
        raise HTTPException(422, "A home must keep at least one source")
    # Legacy events and notifications describe the combined home, not a source.
    # Do not guess where outstanding user-facing work belongs after a split.
    notification_ids = select(Notification.id).where(Notification.listing_id == home.id)
    pending_event = session.scalar(select(AlertEvent.id).where(
        AlertEvent.listing_id == home.id, AlertEvent.processed_at.is_(None)).limit(1))
    unread = session.scalar(select(Notification.id).where(
        Notification.listing_id == home.id, Notification.read_at.is_(None)).limit(1))
    terminal = ("sent", "failed", "cancelled")
    pending_email = session.scalar(select(EmailDelivery.id).where(
        EmailDelivery.notification_id.in_(notification_ids),
        EmailDelivery.status.not_in(terminal)).limit(1))
    pending_push = session.scalar(select(PushDelivery.id).where(
        PushDelivery.notification_id.in_(notification_ids),
        PushDelivery.status.not_in(terminal)).limit(1))
    if pending_event or unread or pending_email or pending_push:
        raise HTTPException(409, "Pending alert state prevents this split; retry after it is resolved")
    new = Listing(
        **{key: getattr(home, key) for key in PROPERTY_FIELDS},
        first_seen=home.first_seen,
        last_seen=source.observed_at,
        hidden=home.hidden,
    )
    session.add(new)
    session.flush()
    source.listing_id = new.id
    session.execute(
        update(Observation).where(Observation.source_listing_id == source.id).values(listing_id=new.id)
    )
    if source.source == "realtoruch":
        advert = session.get(Advert, source.external_id)
        if advert:
            advert.listing_id = new.id
    # The previously combined card may have represented either property. Keep both
    # on existing shortlists and suppress alerts caused solely by this correction.
    copy_preferences(session, home.id, new.id, move=False)
    session.flush()
    for listing in sorted((home, new), key=lambda row: row.id):
        recompute_listing(session, listing, identity_correction=True)
    baseline_corrected_home(session, home)
    baseline_corrected_home(session, new)
    session.flush()
    session.add(
        IdentityDecision(
            moderator_id=moderator,
            from_listing_id=home.id,
            to_listing_id=new.id,
            source_ids=[source.id],
            action="split",
            reason=body.reason,
        )
    )
    session.commit()
    return {
        "listing_id": new.id,
        "message": "Source separated. Existing shortlists retain both homes without a new-match alert.",
    }
