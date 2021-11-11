import hmac
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from .alerts import baseline_search, insert_once, notification_data, unread_count
from .db import get_session, init_db
from .delivery_claims import cancel_notifications
from .ingest import ingest
from .models import (
    Favorite,
    Listing,
    Notification,
    Observation,
    PushSubscription,
    Report,
    SavedSearch,
    SeenPrice,
    SourceListing,
    now,
)
from .normalization import fold
from .push import PushBody
from .query import market_history, search_db, serialize_many
from .schemas import RawListing, SearchFilters
from .security import install_http, require_user
from .settings import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    if settings.environment != "production":
        init_db()
    yield


app = FastAPI(
    title="Realtoruch Open Rental API",
    version="0.1.0",
    description="Free, paginated public rental data. No account required for reads. Sample data is explicitly labelled. Contact fingerprints are never exposed.",
    lifespan=lifespan,
)
install_http(app)
from .email_alerts import router as email_router
from .marketplace import router as marketplace_router
from .identity_review import resolve_id, router as identity_router

app.include_router(email_router)
app.include_router(marketplace_router)
app.include_router(identity_router)


@app.get("/healthz", tags=["Operations"])
def health():
    return {"status": "ok", "service": "api", "demo_mode": settings.demo_mode}


@app.get("/readyz", tags=["Operations"])
def ready(session=Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics(session=Depends(get_session)):
    from .models import Outbox

    pending = session.scalar(select(func.count()).select_from(Outbox).where(Outbox.delivered_at.is_(None)))
    return f"# TYPE realtoruch_outbox_pending gauge\nrealtoruch_outbox_pending {pending}\n"


@app.get("/v1/listings", tags=["Public"])
def listings(filters: SearchFilters = Query(), session=Depends(get_session)):
    if settings.search_service_url:
        try:
            response = httpx.get(
                settings.search_service_url + "/v1/search",
                params=filters.model_dump(exclude_none=True),
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            # Availability fallback; SQL remains the source of truth.
            result = search_db(session, filters)
            result["degraded"] = True
            return result
    return search_db(session, filters)


@app.get("/v1/listings/{listing_id}", tags=["Public"])
def listing_detail(listing_id: str, session=Depends(get_session)):
    listing_id = resolve_id(session, listing_id)
    listing = session.get(Listing, listing_id)
    if not listing or listing.hidden:
        raise HTTPException(404, "Home not found")
    result = serialize_many(session, [listing])[0]
    history = session.scalars(
        select(Observation)
        .where(Observation.listing_id == listing_id, Observation.changed.is_(True))
        .order_by(Observation.observed_at.desc())
        .limit(100)
    ).all()
    result["history"] = [
        {
            "at": o.observed_at.isoformat() + "Z",
            "rent_pln": o.rent_pln,
            "fees_pln": o.fees_pln,
            "status": o.status,
        }
        for o in reversed(history)
    ]
    return result


@app.get("/v1/market/history", tags=["Public"])
def history(
    city: str = "",
    district: str = "",
    region: str = "",
    months: int = Query(default=12, ge=1, le=120),
    session=Depends(get_session),
):
    return market_history(session, city, district, region, months)


@app.get("/v1/market/summary", tags=["Public"])
def summary(city: str = "", session=Depends(get_session)):
    query = select(Listing).where(Listing.status == "active")
    if city:
        query = query.where(Listing.city == city)
    homes = session.scalars(query).all()
    from statistics import median

    ids = [home.id for home in homes]
    source_count = (
        session.scalar(
            select(func.count())
            .select_from(SourceListing)
            .where(SourceListing.listing_id.in_(ids), SourceListing.status == "active")
        )
        if ids
        else 0
    )
    return {
        "homes": len(homes),
        "source_listings": source_count,
        "duplicates_removed": source_count - len(homes),
        "private_homes": sum(home.advertiser_type == "private" for home in homes),
        "median_rent_pln": median(home.rent_pln for home in homes) if homes else None,
        "demo": any(home.is_demo for home in homes),
        "districts": sorted({home.district for home in homes if home.district}),
        "cities": sorted(set(session.scalars(select(Listing.city).distinct()).all())),
    }


@app.get("/v1/sources", tags=["Public"])
def sources(city: str = Query("", max_length=100), session=Depends(get_session)):
    from .collection_health import public_health
    from .connectors import load_sources

    observations = {
        row.source: row
        for row in session.execute(
            select(
                SourceListing.source,
                func.max(SourceListing.observed_at).label("last_observed"),
                func.count().label("stored_adverts"),
            )
            .join(Listing)
            .where(Listing.is_demo.is_(False))
            .group_by(SourceListing.source)
        )
    }
    return {
        "sources": [
            {
                "name": s["name"],
                "enabled": s.get("enabled", False),
                "mode": s.get("mode", "feed"),
                "health": public_health(session, s["name"], city=city),
                "status": "configured" if s.get("enabled") else "disabled",
                "disabled_reason": s.get("disabled_reason") if not s.get("enabled") else None,
                "last_observed_at": observations[s["name"]].last_observed.isoformat() + "Z"
                if s["name"] in observations
                else None,
                "stored_adverts": observations[s["name"]].stored_adverts if s["name"] in observations else 0,
            }
            for s in load_sources()
        ],
        "demo_mode": settings.demo_mode,
    }


@app.get("/v1/me/favorites", tags=["Account"])
def favorites(user_id=Depends(require_user), session=Depends(get_session)):
    homes = session.scalars(
        select(Listing).join(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc())
    ).all()
    return {"items": serialize_many(session, homes)}


@app.put("/v1/me/favorites/{listing_id}", tags=["Account"])
def save_favorite(listing_id: str, user_id=Depends(require_user), session=Depends(get_session)):
    from .ingest import lock_identity
    lock_identity(session, shared=True)
    listing_id = resolve_id(session, listing_id)
    home = session.get(Listing, listing_id)
    if not home:
        raise HTTPException(404, "Home not found")
    if not session.get(Favorite, (user_id, listing_id)):
        session.add(Favorite(user_id=user_id, listing_id=listing_id, price_floor=home.rent_pln))
        from sqlalchemy.exc import IntegrityError

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
    return {"saved": True}


@app.delete("/v1/me/favorites/{listing_id}", tags=["Account"])
def remove_favorite(listing_id: str, user_id=Depends(require_user), session=Depends(get_session)):
    from .ingest import lock_identity
    lock_identity(session, shared=True)
    listing_id = resolve_id(session, listing_id)
    favorite = session.get(Favorite, (user_id, listing_id))
    if favorite:
        cancel_notifications(session, user_id=user_id, listing_id=listing_id, kind="price_drop")
        session.delete(favorite)
        session.commit()
    return {"saved": False}


class SaveSearchBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    filters: SearchFilters


@app.post("/v1/me/searches", status_code=201, tags=["Account"])
def save_search(body: SaveSearchBody, user_id=Depends(require_user), session=Depends(get_session)):
    from .ingest import lock_identity
    lock_identity(session, shared=True)
    if (
        session.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id))
        >= 30
    ):
        raise HTTPException(422, "You can save up to 30 searches")
    search = SavedSearch(
        user_id=user_id,
        name=body.name,
        filters=body.filters.model_dump(exclude_none=True),
        city_key=fold(body.filters.city),
    )
    session.add(search)
    session.flush()
    baseline_search(session, search)
    session.commit()
    return {"id": search.id, "name": search.name, "filters": search.filters}


@app.get("/v1/me/searches", tags=["Account"])
def saved_searches(user_id=Depends(require_user), session=Depends(get_session)):
    searches = session.scalars(select(SavedSearch).where(SavedSearch.user_id == user_id)).all()
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "filters": s.filters,
                "new_matches": session.scalar(
                    select(func.count()).select_from(
                        select(Notification.id)
                        .where(
                            Notification.search_id == s.id,
                            Notification.user_id == user_id,
                            Notification.read_at.is_(None),
                        )
                        .subquery()
                    )
                ),
            }
            for s in searches
        ]
    }


@app.delete("/v1/me/searches/{search_id}", tags=["Account"])
def delete_search(search_id: str, user_id=Depends(require_user), session=Depends(get_session)):
    search = session.get(SavedSearch, search_id)
    if not search or search.user_id != user_id:
        raise HTTPException(404, "Search not found")
    session.delete(search)
    session.commit()
    return {"deleted": True}


@app.put("/v1/me/seen/{listing_id}", tags=["Account"])
def mark_seen(listing_id: str, user_id=Depends(require_user), session=Depends(get_session)):
    from .ingest import lock_identity
    lock_identity(session, shared=True)
    listing_id = resolve_id(session, listing_id)
    home = session.get(Listing, listing_id)
    if not home:
        raise HTTPException(404, "Home not found")
    insert_once(session, SeenPrice, {"user_id": user_id, "listing_id": listing_id, "rent_pln": home.rent_pln})
    from sqlalchemy import update

    cancel_notifications(session, user_id=user_id, listing_id=listing_id)
    session.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.listing_id == listing_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now())
    )
    session.commit()
    return {"seen": True, "listing_id": listing_id, "rent_pln": home.rent_pln}


class ListingStateBody(BaseModel):
    listing_ids: list[str] = Field(max_length=100)


@app.post("/v1/me/listing-state", tags=["Account"])
def listing_state(body: ListingStateBody, user_id=Depends(require_user), session=Depends(get_session)):
    ids = session.scalars(
        select(SeenPrice.listing_id)
        .where(SeenPrice.user_id == user_id, SeenPrice.listing_id.in_(body.listing_ids))
        .distinct()
    ).all()
    return {"seen_ids": ids}


@app.get("/v1/me/notifications", tags=["Account"])
def notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    user_id=Depends(require_user),
    session=Depends(get_session),
):
    rows = session.execute(
        select(Notification, Listing.status)
        .join(Listing)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [notification_data(n, status) for n, status in rows],
        "unread_count": unread_count(session, user_id),
        "page": page,
        "page_size": page_size,
    }


@app.put("/v1/me/notifications/{notification_id}/read", tags=["Account"])
def read_notification(notification_id: str, user_id=Depends(require_user), session=Depends(get_session)):
    item = session.get(Notification, notification_id)
    if not item or item.user_id != user_id:
        raise HTTPException(404, "Notification not found")
    cancel_notifications(session, notification_id=notification_id)
    item.read_at = item.read_at or now()
    session.commit()
    return {"read": True}


@app.get("/v1/notifications/config", tags=["Public"])
def notification_config():
    return {
        "web_push_enabled": bool(settings.vapid_public_key and settings.vapid_subject),
        "vapid_public_key": settings.vapid_public_key,
        "expo_push_enabled": settings.expo_push_enabled,
    }


@app.post("/v1/me/push-subscriptions", tags=["Account"])
def subscribe_push(body: PushBody, user_id=Depends(require_user), session=Depends(get_session)):
    import hashlib

    if body.kind == "web" and not notification_config()["web_push_enabled"]:
        raise HTTPException(503, "Browser push is not configured on this server")
    if body.kind == "expo" and not settings.expo_push_enabled:
        raise HTTPException(503, "Mobile push is not configured on this server")
    key = hashlib.sha256((body.endpoint if body.kind == "web" else body.token).encode()).hexdigest()
    item = session.get(PushSubscription, key)
    if (not item or item.user_id != user_id or not item.active) and session.scalar(
        select(func.count())
        .select_from(PushSubscription)
        .where(PushSubscription.user_id == user_id, PushSubscription.active.is_(True))
    ) >= 10:
        raise HTTPException(422, "You can enable alerts on up to 10 devices")
    data = {"endpoint": body.endpoint, "keys": body.keys} if body.kind == "web" else {"token": body.token}
    if item:
        if item.user_id != user_id:
            cancel_notifications(session, subscription_id=key)
        item.user_id, item.data, item.active = user_id, data, True
    else:
        session.add(PushSubscription(id=key, user_id=user_id, kind=body.kind, data=data))
    session.commit()
    return {"id": key, "enabled": True}


@app.delete("/v1/me/push-subscriptions/{subscription_id}", tags=["Account"])
def unsubscribe_push(subscription_id: str, user_id=Depends(require_user), session=Depends(get_session)):
    item = session.get(PushSubscription, subscription_id)
    if not item or item.user_id != user_id:
        raise HTTPException(404, "Subscription not found")
    cancel_notifications(session, subscription_id=subscription_id)
    item.active = False
    session.commit()
    return {"enabled": False}


class ReportBody(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


@app.post("/v1/listings/{listing_id}/reports", status_code=201, tags=["Account"])
def report(listing_id: str, body: ReportBody, user_id=Depends(require_user), session=Depends(get_session)):
    from .ingest import lock_identity
    lock_identity(session, shared=True)
    listing_id = resolve_id(session, listing_id)
    if not session.get(Listing, listing_id):
        raise HTTPException(404, "Home not found")
    item = Report(listing_id=listing_id, user_id=user_id, reason=body.reason)
    session.add(item)
    session.commit()
    return {
        "id": item.id,
        "status": "pending",
        "message": "Report saved for review. Reports do not automatically change a listing's risk assessment.",
    }


def internal_access(request: Request):
    if not hmac.compare_digest(request.headers.get("X-Internal-Key", ""), settings.internal_api_key):
        raise HTTPException(403, "Internal service only")


@app.post("/internal/observations", dependencies=[Depends(internal_access)], include_in_schema=False)
def observations(body: RawListing, session=Depends(get_session)):
    if body.is_demo and not settings.demo_mode:
        raise HTTPException(422, "Demo observations are disabled")
    result = ingest(session, body)
    session.commit()
    return result


@app.delete("/internal/accounts/{user_id}", dependencies=[Depends(internal_access)], include_in_schema=False)
def erase_account_data(user_id: str, session=Depends(get_session)):
    from sqlalchemy import delete
    from .models import EmailDelivery, EmailSubscription, PushDelivery, SearchMatch
    from .models import Advert, AdvertiserProfile, Conversation, Message
    from .marketplace import publish_observation

    conversations = select(Conversation.id).where(
        (Conversation.renter_id == user_id) | (Conversation.owner_id == user_id)
    )
    session.execute(
        delete(Message).where(Message.conversation_id.in_(conversations)),
        execution_options={"synchronize_session": False},
    )
    session.execute(
        delete(Conversation).where(Conversation.id.in_(conversations)),
        execution_options={"synchronize_session": False},
    )
    for advert in session.scalars(select(Advert).where(Advert.user_id == user_id).with_for_update()):
        if advert.listing_id:
            advert.draft = {**advert.draft, "title": "Withdrawn listing", "description": "", "images": []}
            publish_observation(session, advert, session.get(AdvertiserProfile, user_id), "inactive")
        session.delete(advert)
    session.flush()
    session.execute(delete(AdvertiserProfile).where(AdvertiserProfile.user_id == user_id))

    notifications = select(Notification.id).where(Notification.user_id == user_id)
    subscriptions = select(PushSubscription.id).where(PushSubscription.user_id == user_id)
    searches = select(SavedSearch.id).where(SavedSearch.user_id == user_id)
    session.execute(
        delete(PushDelivery).where(
            PushDelivery.notification_id.in_(notifications) | PushDelivery.subscription_id.in_(subscriptions)
        ),
        execution_options={"synchronize_session": False},
    )
    session.execute(delete(EmailDelivery).where(EmailDelivery.user_id == user_id))
    session.execute(
        delete(SearchMatch).where(SearchMatch.search_id.in_(searches)),
        execution_options={"synchronize_session": False},
    )
    for model in (
        Notification,
        PushSubscription,
        EmailSubscription,
        SavedSearch,
        Favorite,
        SeenPrice,
        Report,
    ):
        session.execute(delete(model).where(model.user_id == user_id))
    session.commit()
    return {"erased": True}
