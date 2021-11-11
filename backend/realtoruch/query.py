from collections import defaultdict
from statistics import median

from sqlalchemy import func, or_, select

from .models import Listing, Observation, SourceListing, now
from .schemas import SearchFilters


def public_listing(listing, sources):
    result = {
        key: getattr(listing, key)
        for key in (
            "id",
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
            "status",
            "amenities",
            "images",
            "risk_flags",
            "risk_score",
            "is_demo",
        )
    }
    for key in ("first_seen", "last_seen", "updated_at"):
        result[key] = getattr(listing, key).isoformat() + "Z"
    result["total_monthly_pln"] = (
        listing.rent_pln + listing.fees_pln if listing.fees_pln is not None else None
    )
    result["sources"] = [
        {
            "name": s.source,
            "url": s.url,
            "rent_pln": s.data["rent_pln"],
            "fees_pln": s.data.get("fees_pln"),
            "commission_pln": s.data.get("commission_pln"),
            "advertiser_type": s.data["advertiser_type"],
            "status": s.status,
            "last_checked": s.observed_at.isoformat() + "Z",
            "match_reason": s.match_reason,
        }
        for s in sources
    ]
    return result


def serialize_many(session, listings):
    if not listings:
        return []
    grouped = defaultdict(list)
    for source in session.scalars(
        select(SourceListing).where(SourceListing.listing_id.in_([l.id for l in listings]))
    ):
        grouped[source.listing_id].append(source)
    return [public_listing(l, grouped[l.id]) for l in listings]


def filtered_query(filters: SearchFilters):
    query = select(Listing).where(Listing.status == "active")
    if filters.city:
        query = query.where(Listing.city.ilike(filters.city.replace("%", "\\%").replace("_", "\\_")))
    if filters.district:
        query = query.where(Listing.district.ilike(filters.district.replace("%", "\\%").replace("_", "\\_")))
    if filters.q:
        term = "%" + filters.q.replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(Listing.title.ilike(term), Listing.address.ilike(term), Listing.district.ilike(term))
        )
    for value, condition in (
        (filters.min_price, Listing.rent_pln >= (filters.min_price or 0)),
        (
            filters.max_price,
            Listing.rent_pln < (filters.max_price or 0)
            if filters.max_price_exclusive
            else Listing.rent_pln <= (filters.max_price or 0),
        ),
        (filters.min_area, Listing.area_m2 >= (filters.min_area or 0)),
        (filters.max_area, Listing.area_m2 <= (filters.max_area or 0)),
        (filters.rooms, Listing.rooms == filters.rooms),
    ):
        if value is not None:
            query = query.where(condition)
    if filters.advertiser != "all":
        query = query.where(Listing.advertiser_type == filters.advertiser)
    if filters.no_commission:
        query = query.where(Listing.commission_pln == 0)
    if filters.hide_suspicious:
        query = query.where(Listing.risk_score == 0)
    if filters.property_type != "all":
        query = query.where(Listing.property_type == filters.property_type)
    if filters.amenity:
        # JSON containment differs by database. Exact quoted token keeps this portable.
        import json

        from sqlalchemy import String, cast

        query = query.where(
            cast(Listing.amenities, String).contains(json.dumps(filters.amenity), autoescape=True)
        )
    if filters.bbox:
        w, s, e, n = map(float, filters.bbox.split(","))
        query = query.where(Listing.lon.between(w, e), Listing.lat.between(s, n))
    if filters.polygon:
        from .geometry import parse_polygon, polygon_sql

        query = query.where(polygon_sql(Listing.lon, Listing.lat, parse_polygon(filters.polygon)))
    return query


def search_db(session, filters):
    query = filtered_query(filters)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    order = {
        "newest": Listing.first_seen.desc(),
        "price_asc": Listing.rent_pln.asc(),
        "price_desc": Listing.rent_pln.desc(),
        "area_desc": Listing.area_m2.desc(),
    }[filters.sort]
    listings = session.scalars(
        query.order_by(order, Listing.id)
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).all()
    return {
        "items": serialize_many(session, listings),
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size,
        "engine": "postgresql" if session.bind.dialect.name == "postgresql" else "sqlite",
    }


def market_history(session, city="", district="", region="", months=12):
    """Monthly last observed asking rent per property, never one vote per portal."""
    query = select(Observation, Listing).join(Listing, Observation.listing_id == Listing.id)
    if city:
        query = query.where(Listing.city == city)
    if district:
        query = query.where(Listing.district == district)
    if region:
        query = query.where(Listing.region == region)
    from datetime import timedelta

    cutoff = now() - timedelta(days=months * 31)
    query = query.where(Observation.observed_at >= cutoff).order_by(Observation.observed_at)
    # A source's removal must not remove a property still active on another source.
    month_sources = defaultdict(dict)
    for observation, listing in session.execute(query):
        month_sources[observation.observed_at.strftime("%Y-%m")][observation.source_listing_id] = (
            observation,
            listing,
        )
    points = []
    for month, records in sorted(month_sources.items()):
        by_property = defaultdict(list)
        for observation, listing in records.values():
            if observation.status == "active":
                by_property[listing.id].append((observation, listing))
        homes = [max(values, key=lambda pair: pair[0].observed_at) for values in by_property.values()]
        if not homes:
            continue
        rents = [obs.rent_pln for obs, _ in homes]
        points.append(
            {
                "month": month,
                "median_rent_pln": median(rents),
                "median_per_m2": round(median(obs.rent_pln / listing.area_m2 for obs, listing in homes), 2),
                "sample_size": len(homes),
                "is_demo": any(listing.is_demo for _, listing in homes),
            }
        )
    return {
        "points": points,
        "methodology": "Median advertised base rent (PLN), excluding fees. One latest observed active price per canonical property per month; months without observations are not interpolated. This is an observed sample, not signed lease prices or a census. Small samples are shown explicitly.",
        "city": city,
        "district": district,
        "region": region,
    }
