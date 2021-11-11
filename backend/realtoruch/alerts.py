"""Durable property-level alerts. HTTP reads never generate notifications."""

import hashlib

from sqlalchemy import func, literal, select

from .models import AlertEvent, Favorite, Listing, Notification, SavedSearch, SearchMatch, SeenPrice, now
from .normalization import fold
from .query import filtered_query
from .schemas import SearchFilters


def insert_once(session, model, values):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    statement = (pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert)(model)
    return session.execute(statement.values(**values).on_conflict_do_nothing())


def baseline_search(session, search):
    """Existing matches are a silent baseline, inserted without loading entire catalogs."""
    query = filtered_query(SearchFilters(**search.filters)).with_only_columns(Listing.id).subquery()
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    session.execute(
        insert(SearchMatch)
        .from_select(
            ["search_id", "listing_id", "created_at"],
            select(literal(search.id), query.c.id, literal(now())).where(literal(True)),
            include_defaults=False,
        )
        .on_conflict_do_nothing()
    )


def create_notification(session, home, user_id, kind, *, search_id=None, previous=None):
    key = hashlib.sha256(f"{user_id}:{home.id}:{kind}:{home.rent_pln}".encode()).hexdigest()
    if session.scalar(select(Notification.id).where(Notification.dedupe_key == key)):
        return None
    item = Notification(
        user_id=user_id,
        listing_id=home.id,
        search_id=search_id,
        dedupe_key=key,
        kind=kind,
        title=home.title,
        rent_pln=home.rent_pln,
        previous_rent_pln=previous,
    )
    session.add(item)
    session.flush()
    from .models import EmailDelivery, EmailSubscription

    email = session.get(EmailSubscription, user_id)
    if email and email.enabled and email.verified_at:
        session.add(EmailDelivery(user_id=user_id, notification_id=item.id))
    from .models import PushDelivery, PushSubscription

    for subscription in session.scalars(
        select(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.active.is_(True))
    ):
        session.add(PushDelivery(notification_id=item.id, subscription_id=subscription.id))
    return item


def process_alerts(session, limit=100):
    """Caller owns transaction. Inbox records and event acknowledgements commit together."""
    from .ingest import lock_identity
    lock_identity(session, shared=True)
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        # One evaluator prevents concurrent search/favorite events from duplicating an alert.
        if not session.scalar(text("SELECT pg_try_advisory_xact_lock(761994031)")):
            return 0
    events = session.scalars(
        select(AlertEvent)
        .where(AlertEvent.processed_at.is_(None))
        .order_by(AlertEvent.created_at, AlertEvent.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    for listing_id in dict.fromkeys(event.listing_id for event in events):
        home = session.get(Listing, listing_id)
        if home.status != "active":
            continue
        price_alert_users = set()
        favorites = session.scalars(
            select(Favorite).where(Favorite.listing_id == listing_id).with_for_update()
        ).all()
        for favorite in favorites:
            if favorite.price_floor is None:
                favorite.price_floor = home.rent_pln
            elif home.rent_pln < favorite.price_floor:
                create_notification(
                    session, home, favorite.user_id, "price_drop", previous=favorite.price_floor
                )
                favorite.price_floor = home.rent_pln
                price_alert_users.add(favorite.user_id)
        searches = session.scalars(
            select(SavedSearch).where(SavedSearch.city_key.in_(["", fold(home.city)]))
        ).all()
        for search in searches:
            if session.get(SearchMatch, (search.id, home.id)):
                continue
            matches = session.scalar(
                filtered_query(SearchFilters(**search.filters))
                .with_only_columns(Listing.id)
                .where(Listing.id == home.id)
            )
            if not matches:
                continue
            insert_once(session, SearchMatch, {"search_id": search.id, "listing_id": home.id})
            seen = session.get(SeenPrice, (search.user_id, home.id, home.rent_pln))
            if not seen and search.user_id not in price_alert_users:
                create_notification(session, home, search.user_id, "new_match", search_id=search.id)
    for event in events:
        event.processed_at = now()
    session.flush()
    return len(events)


def notification_data(item, listing_status=None):
    return {
        "id": item.id,
        "listing_id": item.listing_id,
        "search_id": item.search_id,
        "kind": item.kind,
        "title": item.title,
        "rent_pln": item.rent_pln,
        "previous_rent_pln": item.previous_rent_pln,
        "created_at": item.created_at.isoformat() + "Z",
        "read_at": item.read_at.isoformat() + "Z" if item.read_at else None,
        "listing_status": listing_status,
    }


def unread_count(session, user_id):
    return session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
