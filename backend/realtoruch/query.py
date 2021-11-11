from collections import defaultdict
from contextlib import contextmanager
from time import monotonic

from sqlalchemy import Boolean, Float, Integer, String, case, cast, func, or_, select, text, true
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from .models import Listing, Observation, SourceListing, now
from .schemas import (
    PUBLIC_CARD_LINKS,
    SORT_FIELDS,
    PublicRiskFlag,
    SearchFilters,
    public_link,
    public_match_reason,
    without_contacts,
)

PUBLIC_SQL_BUDGET_MS = 2_000


@contextmanager
def catalog_read_budget(session):
    """Put a finite statement/lock budget on public catalog reads."""
    connection = session.connection()
    if connection.dialect.name == "postgresql":
        connection.execute(text(f"SET LOCAL statement_timeout = '{PUBLIC_SQL_BUDGET_MS}ms'"))
        yield
    else:
        driver = connection.connection.driver_connection
        previous = driver.execute("PRAGMA busy_timeout").fetchone()[0]
        deadline = monotonic() + PUBLIC_SQL_BUDGET_MS / 1_000
        driver.execute(f"PRAGMA busy_timeout = {PUBLIC_SQL_BUDGET_MS}")
        driver.set_progress_handler(lambda: monotonic() >= deadline, 1000)
        try:
            yield
        finally:
            driver.set_progress_handler(None, 0)
            driver.execute(f"PRAGMA busy_timeout = {previous}")


def public_links(values):
    for value in values:
        try:
            yield public_link(value)
        except ValueError:
            # A source URL with credentials is still useful internally.
            continue


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
    for key, length in (
        ("title", 240), ("description", 20_000), ("address", 240),
        ("city", 100), ("district", 100), ("region", 100),
    ):
        result[key] = without_contacts(result[key])[:length]
    # Existing ingestion accepts arbitrarily long amenity strings. They cannot
    # match a public filter (max 60 characters) and need not invalidate a card.
    result["amenities"] = [without_contacts(value)[:100] for value in result["amenities"] if len(value) <= 100]
    result["images"] = list(public_links(result["images"]))
    result["risk_flags"] = [PublicRiskFlag.model_validate(flag).model_dump() for flag in result["risk_flags"]]
    result["total_monthly_pln"] = (
        listing.rent_pln + listing.fees_pln if listing.fees_pln is not None else None
    )
    result["sources"] = [
        {
            "name": s.source,
            "url": url,
            "rent_pln": s.data["rent_pln"],
            "fees_pln": s.data.get("fees_pln"),
            "commission_pln": s.data.get("commission_pln"),
            "advertiser_type": s.data["advertiser_type"],
            "status": s.status,
            "last_checked": s.observed_at.isoformat() + "Z",
            "match_reason": public_match_reason(s.match_reason),
        }
        for s in sources
        for url in public_links([s.url])
    ]
    return result


def serialize_many(session, listings):
    if not listings:
        return []
    ids = [listing.id for listing in listings]
    grouped = defaultdict(list)
    sources = select(SourceListing.id, func.row_number().over(
        partition_by=SourceListing.listing_id,
        order_by=(case((SourceListing.status == "active", 0), else_=1), SourceListing.observed_at.desc(), SourceListing.id),
    ).label("n")).where(SourceListing.listing_id.in_(ids)).subquery()
    for source in session.scalars(
        select(SourceListing).join(sources, SourceListing.id == sources.c.id)
        .where(sources.c.n <= PUBLIC_CARD_LINKS).order_by(sources.c.n)
    ):
        grouped[source.listing_id].append(source)
    from .models import Advert, AdvertiserProfile

    contacts = defaultdict(list)
    ranked = select(Advert.id, func.row_number().over(
        partition_by=Advert.listing_id, order_by=(Advert.updated_at.desc(), Advert.id),
    ).label("n")).where(Advert.listing_id.in_(ids), Advert.state == "published").subquery()
    for listing_id, advert_id, profile_id, name, kind in session.execute(
        select(Advert.listing_id, Advert.id, AdvertiserProfile.user_id, AdvertiserProfile.name, AdvertiserProfile.kind)
        .join(ranked, Advert.id == ranked.c.id).join(AdvertiserProfile, Advert.user_id == AdvertiserProfile.user_id)
        .where(ranked.c.n <= PUBLIC_CARD_LINKS).order_by(ranked.c.n)
    ):
        contacts[listing_id].append(
            {"id": advert_id, "name": without_contacts(name)[:100], "kind": kind, "profile_id": profile_id}
        )
    return [
        {
            **public_listing(l, grouped[l.id]),
            "contact_adverts": contacts[l.id] if l.status == "active" else [],
        }
        for l in listings
    ]


def _literal_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ascii_label(FunctionElement):
    type = String()
    inherit_cache = True


@compiles(ascii_label, "postgresql")
def _pg_ascii_label(element, compiler, **kwargs):
    return f'lower({compiler.process(element.clauses, **kwargs)} COLLATE "C")'


@compiles(ascii_label)
def _sqlite_ascii_label(element, compiler, **kwargs):
    return f"lower({compiler.process(element.clauses, **kwargs)})"


class amenity_matches(FunctionElement):
    type = Boolean()
    inherit_cache = True


@compiles(amenity_matches, "postgresql")
def _pg_amenity_matches(element, compiler, **kwargs):
    column, value = (compiler.process(clause, **kwargs) for clause in element.clauses)
    return f"CAST({column} AS jsonb) @> jsonb_build_array(CAST({value} AS text))"


@compiles(amenity_matches, "sqlite")
def _sqlite_amenity_matches(element, compiler, **kwargs):
    column, value = (compiler.process(clause, **kwargs) for clause in element.clauses)
    return f"EXISTS (SELECT 1 FROM json_each({column}) item WHERE item.type = 'text' AND item.value = {value})"


def _ascii_label_match(column, value):
    # SQLite and ES keyword case-insensitive matching both use ASCII case
    # folding. Explicit C collation gives PostgreSQL the same behavior.
    folded = value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
    return ascii_label(column) == folded


def filtered_query(filters: SearchFilters, *, include_text=True):
    query = select(Listing).where(Listing.status == "active", Listing.hidden.is_(False))
    if filters.city:
        query = query.where(_ascii_label_match(Listing.city, filters.city))
    if filters.district:
        query = query.where(_ascii_label_match(Listing.district, filters.district))
    if include_text and filters.q:
        term = "%" + _literal_like(filters.q) + "%"
        query = query.where(
            or_(*(column.ilike(term, escape="\\") for column in (Listing.title, Listing.address, Listing.district)))
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
        # Query decoded array elements; a quoted substring can match escaped
        # data inside a different amenity or miss a non-ASCII token.
        query = query.where(amenity_matches(Listing.amenities, filters.amenity))
    if filters.bbox:
        w, s, e, n = map(float, filters.bbox.split(","))
        query = query.where(Listing.lon.between(w, e), Listing.lat.between(s, n))
    if filters.polygon:
        from .geometry import parse_polygon, polygon_sql

        query = query.where(polygon_sql(Listing.lon, Listing.lat, parse_polygon(filters.polygon)))
    return query


def search_db(session, filters):
    query = filtered_query(filters)
    sort_column = getattr(Listing, SORT_FIELDS[filters.sort])
    order = sort_column.asc() if filters.sort == "price_asc" else sort_column.desc()
    ids = query.with_only_columns(Listing.id)
    counts = select(func.count().label("total")).select_from(ids.subquery()).subquery()
    page_ids = ids.order_by(order, Listing.id).offset(filters.offset).limit(filters.page_size).subquery()
    # An empty page still carries the count. Count and page share the same
    # statement snapshot even while collectors change the catalog.
    rows = session.execute(
        select(Listing, counts.c.total).select_from(counts)
        .outerjoin(page_ids, true()).outerjoin(Listing, Listing.id == page_ids.c.id)
        .order_by(order, Listing.id).execution_options(populate_existing=True)
    ).all()
    return {
        "items": serialize_many(session, [listing for listing, _ in rows if listing is not None]),
        "total": rows[0].total,
        "page": filters.page,
        "page_size": filters.page_size,
        "engine": "postgresql" if session.bind.dialect.name == "postgresql" else "sqlite",
        "degraded": False,
        "consistency": "sql",
        "total_relation": "exact",
    }


def check_index_page(session, filters, page):
    ids = [item.id for item in page.items]
    # This query deliberately runs for an empty candidate page too: a SQL
    # outage must not look like a successful, empty REST catalog.
    current = {
        row.id: row for row in session.scalars(
            filtered_query(filters, include_text=False).where(Listing.id.in_(ids))
            .execution_options(populate_existing=True)
        )
    }
    if len(current) != len(ids):
        return None
    sort_field = SORT_FIELDS[filters.sort]
    items = serialize_many(session, [current[listing_id] for listing_id in ids])
    checked_fields = {sort_field}
    if filters.q:
        checked_fields.update(("title", "address", "district", "description"))
    if any(item[field] != getattr(hit, field) for item, hit in zip(items, page.items) for field in checked_fields):
        return None
    return {**page.model_dump(exclude={"items"}), "items": items, "consistency": "sql_checked"}


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
        Observation.observed_at >= start, Observation.observed_at <= end, Listing.hidden.is_(False),
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
                      Listing.advertiser_type).where(Listing.status == "active", Listing.hidden.is_(False))
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
    cities = session.scalars(
        select(Listing.city).where(Listing.hidden.is_(False)).distinct().order_by(Listing.city)
    ).all()
    return {"homes": count, "source_listings": source_count, "duplicates_removed": source_count - count,
            "private_homes": private, "median_rent_pln": rent, "demo": bool(demo),
            "districts": districts, "cities": cities}
