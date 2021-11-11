from collections import defaultdict

from sqlalchemy import Float, Integer, case, cast, func, or_, select

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
    from .models import Advert, AdvertiserProfile

    contacts = defaultdict(list)
    for advert, profile in session.execute(
        select(Advert, AdvertiserProfile)
        .join(AdvertiserProfile)
        .where(Advert.listing_id.in_([l.id for l in listings]), Advert.state == "published")
    ):
        contacts[advert.listing_id].append(
            {"id": advert.id, "name": profile.name, "kind": profile.kind, "profile_id": profile.user_id}
        )
    return [
        {
            **public_listing(l, grouped[l.id]),
            "contact_adverts": contacts[l.id] if l.status == "active" else [],
        }
        for l in listings
    ]


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
    """Observed monthly rents, bounded by UTC calendar months and query time."""
    from datetime import datetime

    end = now()
    absolute_month = end.year * 12 + end.month - 1 - (months - 1)
    start = datetime(absolute_month // 12, absolute_month % 12 + 1, 1)
    month = (func.to_char(Observation.observed_at, "YYYY-MM")
             if session.bind.dialect.name == "postgresql"
             else func.strftime("%Y-%m", Observation.observed_at))
    source_rank = func.row_number().over(
        partition_by=(month, Observation.source_listing_id),
        order_by=(Observation.observed_at.desc(), Observation.id.desc()),
    )
    observations = select(
        month.label("month"), Observation.listing_id.label("home_id"),
        Observation.source_listing_id.label("source_id"), Observation.id.label("observation_id"),
        Observation.observed_at.label("observed_at"), Observation.status.label("status"),
        Observation.rent_pln.label("rent"), Listing.area_m2.label("area"),
        Listing.is_demo.label("demo"), source_rank.label("source_rank"),
    ).join(Listing, Observation.listing_id == Listing.id).where(
        Observation.observed_at >= start, Observation.observed_at <= end,
    )
    for value, column in ((city, Listing.city), (district, Listing.district), (region, Listing.region)):
        if value:
            observations = observations.where(column == value)
    sources = observations.subquery()
    home_rank = func.row_number().over(
        partition_by=(sources.c.month, sources.c.home_id),
        order_by=(sources.c.observed_at.desc(), sources.c.source_id.desc(), sources.c.observation_id.desc()),
    )
    active = select(sources, home_rank.label("home_rank")).where(
        sources.c.source_rank == 1, sources.c.status == "active"
    ).subquery()
    homes = select(active).where(active.c.home_rank == 1).subquery()
    per_m2 = cast(homes.c.rent, Float) / homes.c.area
    ranked = select(
        homes.c.month, homes.c.rent, per_m2.label("per_m2"), homes.c.demo,
        func.count().over(partition_by=homes.c.month).label("n"),
        func.row_number().over(partition_by=homes.c.month, order_by=(homes.c.rent, homes.c.home_id)).label("rent_rank"),
        func.row_number().over(partition_by=homes.c.month, order_by=(per_m2, homes.c.home_id)).label("area_rank"),
    ).subquery()
    def middle(rank):
        return (rank * 2 >= ranked.c.n) & (rank * 2 <= ranked.c.n + 2)
    rows = session.execute(select(
        ranked.c.month,
        func.avg(case((middle(ranked.c.rent_rank), cast(ranked.c.rent, Float)))).label("rent"),
        func.avg(case((middle(ranked.c.area_rank), ranked.c.per_m2))).label("per_m2"),
        func.max(ranked.c.n).label("n"),
        func.max(cast(ranked.c.demo, Integer)).label("demo"),
    ).group_by(ranked.c.month).order_by(ranked.c.month)).all()
    return {
        "points": [{"month": row.month, "median_rent_pln": row.rent,
                    "median_per_m2": round(row.per_m2, 2), "sample_size": row.n,
                    "is_demo": bool(row.demo)} for row in rows],
        "methodology": "Median advertised base rent (PLN), excluding fees. Current UTC calendar month and preceding months through the query time; latest observation per source/month, then latest active source per canonical property/month. Per-m² uses current canonical area. Months without observations are not interpolated. This is an observed sample, not signed lease prices or a census. Small samples are shown explicitly.",
        "city": city, "district": district, "region": region,
    }


def market_summary(session, city=""):
    """Summarize active homes without materializing the catalog in Python."""
    filtered = select(Listing.id, Listing.rent_pln, Listing.district, Listing.is_demo,
                      Listing.advertiser_type).where(Listing.status == "active")
    if city:
        filtered = filtered.where(Listing.city == city)
    homes = filtered.subquery()
    ranked = select(homes, func.row_number().over(order_by=(homes.c.rent_pln, homes.c.id)).label("r"),
                    func.count().over().label("n")).subquery()
    count, private, demo, rent = session.execute(select(
        func.count(), func.coalesce(func.sum(case((ranked.c.advertiser_type == "private", 1), else_=0)), 0),
        func.coalesce(func.max(cast(ranked.c.is_demo, Integer)), 0),
        func.avg(case(((ranked.c.r * 2 >= ranked.c.n) & (ranked.c.r * 2 <= ranked.c.n + 2), cast(ranked.c.rent_pln, Float)))),
    )).one()
    source_count = session.scalar(select(func.count()).select_from(SourceListing).join(
        homes, SourceListing.listing_id == homes.c.id).where(SourceListing.status == "active"))
    districts = session.scalars(select(homes.c.district).where(homes.c.district != "").distinct().order_by(homes.c.district)).all()
    cities = session.scalars(select(Listing.city).distinct().order_by(Listing.city)).all()
    return {"homes": count, "source_listings": source_count, "duplicates_removed": source_count - count,
            "private_homes": private, "median_rent_pln": rent, "demo": bool(demo),
            "districts": districts, "cities": cities}
