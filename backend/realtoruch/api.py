import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from .db import get_session, init_db
from .models import Listing, SourceListing, Observation, Favorite, SavedSearch, Report, now
from .schemas import RawListing, SearchFilters
from .query import search_db, serialize_many, market_history, filtered_query
from .ingest import ingest
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
    listing = session.get(Listing, listing_id)
    if not listing:
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
        "districts": sorted({home.district for home in homes}),
        "cities": sorted(set(session.scalars(select(Listing.city).distinct()).all())),
    }


@app.get("/v1/sources", tags=["Public"])
def sources():
    from .connectors import load_sources

    return {
        "sources": [
            {
                "name": s["name"],
                "enabled": s.get("enabled", False),
                "mode": s.get("mode", "feed"),
                "status": "configured" if s.get("enabled") else "awaiting_access",
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
    if not session.get(Listing, listing_id):
        raise HTTPException(404, "Home not found")
    if not session.get(Favorite, (user_id, listing_id)):
        session.add(Favorite(user_id=user_id, listing_id=listing_id))
        from sqlalchemy.exc import IntegrityError

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
    return {"saved": True}


@app.delete("/v1/me/favorites/{listing_id}", tags=["Account"])
def remove_favorite(listing_id: str, user_id=Depends(require_user), session=Depends(get_session)):
    favorite = session.get(Favorite, (user_id, listing_id))
    if favorite:
        session.delete(favorite)
        session.commit()
    return {"saved": False}


class SaveSearchBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    filters: SearchFilters


@app.post("/v1/me/searches", status_code=201, tags=["Account"])
def save_search(body: SaveSearchBody, user_id=Depends(require_user), session=Depends(get_session)):
    if (
        session.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id))
        >= 30
    ):
        raise HTTPException(422, "You can save up to 30 searches")
    search = SavedSearch(user_id=user_id, name=body.name, filters=body.filters.model_dump(exclude_none=True))
    session.add(search)
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
                        filtered_query(SearchFilters(**s.filters))
                        .where(Listing.first_seen > s.created_at)
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


class ReportBody(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


@app.post("/v1/listings/{listing_id}/reports", status_code=201, tags=["Account"])
def report(listing_id: str, body: ReportBody, user_id=Depends(require_user), session=Depends(get_session)):
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
