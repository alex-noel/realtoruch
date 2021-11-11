import re
from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

SEARCH_WINDOW = 10_000
SEARCH_PAGE_SIZE = 100
PUBLIC_CARD_LINKS = 100
SORT_FIELDS = {
    "newest": "first_seen",
    "price_asc": "rent_pln",
    "price_desc": "rent_pln",
    "area_desc": "area_m2",
}


class RawListing(BaseModel):
    source: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    external_id: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(default="", max_length=20000)
    city: str = Field(min_length=1, max_length=100)
    district: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=240)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    area_m2: float = Field(gt=0, le=10000)
    rooms: int = Field(ge=1, le=100)
    floor: int | None = Field(default=None, ge=-2, le=200)
    rent_pln: int = Field(gt=0, le=1000000)
    fees_pln: int | None = Field(default=None, ge=0, le=1000000)
    deposit_pln: int | None = Field(default=None, ge=0, le=10000000)
    commission_pln: int | None = Field(default=None, ge=0, le=1000000)
    advertiser_type: Literal["private", "agency", "unknown"] = "unknown"
    property_type: Literal["apartment", "house", "room"] = "apartment"
    status: Literal["active", "inactive", "unknown"] = "active"
    phone: str | None = Field(default=None, max_length=50)
    phone_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    # Private source evidence, never included in the public listing serializer.
    syndication_key: str | None = Field(default=None, pattern=r"^morizon-gratka:[0-9]{1,20}$")
    amenities: list[str] = Field(default_factory=list, max_length=40)
    images: list[HttpUrl] = Field(default_factory=list, max_length=30)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), validate_default=True)
    is_demo: bool = False

    @field_validator("observed_at")
    @classmethod
    def utc_observation(cls, value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @model_validator(mode="after")
    def location_pair(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("Latitude and longitude must be provided together")
        if self.observed_at > datetime.now(timezone.utc).replace(tzinfo=None).replace(microsecond=999999):
            raise ValueError("Observation time cannot be in the future")
        return self


class SearchFilters(BaseModel):
    q: str = Field(default="", max_length=200)
    city: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    max_price_exclusive: bool = False
    min_area: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_area: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    rooms: int | None = Field(default=None, ge=1, le=100)
    advertiser: Literal["all", "private", "agency"] = "all"
    no_commission: bool = False
    hide_suspicious: bool = False
    property_type: Literal["all", "apartment", "house", "room"] = "all"
    amenity: str = Field(default="", max_length=60)
    sort: Literal["newest", "price_asc", "price_desc", "area_desc"] = "newest"
    bbox: str | None = Field(default=None, max_length=100)
    polygon: str | None = Field(default=None, max_length=5000)
    page: int = Field(default=1, ge=1, le=SEARCH_WINDOW)
    page_size: int = Field(default=24, ge=1, le=SEARCH_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @field_validator("city")
    @classmethod
    def city_spelling(cls, value):
        from .normalization import fold

        return {"krakow": "Kraków", "warszawa": "Warszawa"}.get(fold(value), value.strip())

    @field_validator("polygon")
    @classmethod
    def valid_polygon(cls, value):
        if value:
            import json

            from .geometry import parse_polygon

            return json.dumps(parse_polygon(value), separators=(",", ":"))
        return None

    @model_validator(mode="after")
    def ranges(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("Minimum price exceeds maximum price")
        if self.min_area is not None and self.max_area is not None and self.min_area > self.max_area:
            raise ValueError("Minimum area exceeds maximum area")
        if self.bbox:
            try:
                west, south, east, north = map(float, self.bbox.split(","))
                if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                    raise ValueError()
            except ValueError:
                raise ValueError(
                    "bbox must be west,south,east,north with increasing valid coordinates"
                ) from None
        return self


class PublicSearchFilters(SearchFilters):
    # Stored alert filters share the match criteria but do not use paging.
    @model_validator(mode="after")
    def window(self):
        if self.page * self.page_size > SEARCH_WINDOW:
            raise ValueError("page × page_size must not exceed 10,000; narrow the filters")
        return self


class PublicModel(BaseModel):
    # Reject wrong types rather than silently coercing untrusted upstream fields.
    # Unlisted keys are discarded independently at every nested model.
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)


def _utc_text(value: str) -> str:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", value):
        raise ValueError("Expected a UTC timestamp ending in Z")
    datetime.fromisoformat(value)
    return value


def without_contacts(value: str) -> str:
    if "@" in value:
        value = re.sub(r"[\w.!#$%&'*+/=?^_`{|}~-]+@[\w.-]+\.[\w-]+", "[contact via source]", value)
    value = re.sub(r"(?<!\d)(?:\+?48[\s.-]?)?(?:\d[\s.-]?){9}(?!\d)", "[contact via source]", value)
    return re.sub(r"(?i)(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])", "[contact via source]", value)


_PRIVATE_QUERY_KEYS = {
    "authorization",
    "access_token",
    "api_key",
    "apikey",
    "email",
    "password",
    "phone",
    "phone_hash",
    "refresh_token",
    "session",
    "secret",
    "token",
    "cookie",
}


def public_link(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 2083
        or "\\" in value
        or any(ord(char) <= 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError("Expected a public HTTP(S) URL")
    value.encode("utf-8", errors="strict")
    parts = urlsplit(value)
    port = parts.port  # Access validates out-of-range and non-numeric port strings.
    # Fragments are not sent to the original server and can carry credentials.
    value = urlunsplit(parts._replace(fragment=""))
    decoded = unquote(value, errors="strict")
    if (
        parts.scheme not in ("https", "http")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or port == 0
        or any(key.lower() in _PRIVATE_QUERY_KEYS for key, _ in parse_qsl(parts.query, errors="strict"))
        or ("@" in decoded and without_contacts(decoded) != decoded)
    ):
        raise ValueError("Expected a public HTTP(S) URL")
    return value


def public_match_reason(value: str) -> str:
    if value in {
        "New property",
        "Shared Morizon–Gratka listing identity, street, area and rooms",
        "Same address, known floor, contact, photo and nearby location",
        "Same unit address, area, rooms and contact fingerprint",
        "Same unit address, area, rooms and image URL",
    }:
        return value
    return "Imported source advert"


UTCText = Annotated[str, StringConstraints(max_length=32), AfterValidator(_utc_text)]
PublicID = Annotated[str, StringConstraints(min_length=1, max_length=36, pattern=r"^[a-zA-Z0-9_-]+$")]
PublicURL = Annotated[str, StringConstraints(min_length=1, max_length=2083), AfterValidator(public_link)]
Provider = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{2,40}$")]
ShortText = Annotated[str, StringConstraints(max_length=100), AfterValidator(without_contacts)]
DisplayText = Annotated[str, StringConstraints(max_length=240), AfterValidator(without_contacts)]
Count = Annotated[int, Field(ge=0)]
Rent = Annotated[int, Field(gt=0, le=1_000_000)]
Charge = Annotated[int, Field(ge=0, le=1_000_000)]
Status = Literal["active", "inactive", "unknown"]
Advertiser = Literal["private", "agency", "unknown"]


class PublicSourceAdvert(PublicModel):
    name: Provider
    url: PublicURL
    rent_pln: Rent
    fees_pln: Charge | None
    commission_pln: Charge | None
    advertiser_type: Advertiser
    status: Status
    last_checked: UTCText
    match_reason: Annotated[str, StringConstraints(max_length=240), AfterValidator(public_match_reason)]


class PublicRiskFlag(PublicModel):
    code: Literal["frequent_contact", "mixed_identity", "price_mismatch", "private_commission"]
    label: ShortText
    detail: Annotated[str, StringConstraints(max_length=1000), AfterValidator(without_contacts)]
    severity: Literal["low", "medium", "high"]

    @model_validator(mode="after")
    def approved_explanation(self):
        # Expose the known explanation for the signal, never free-form notes.
        self.label, self.severity, detail = _RISK_EXPLANATIONS[self.code]
        if self.code == "frequent_contact":
            match = re.fullmatch(
                r"The same contact appears on ([0-9]{1,9}) distinct active homes in the last 90 days\..*",
                self.detail,
            )
            if match:
                detail = (
                    f"The same contact appears on {match[1]} distinct active homes in the last 90 days. "
                    + detail
                )
        self.detail = detail
        return self


_RISK_EXPLANATIONS = {
    "frequent_contact": (
        "Frequent advertiser",
        "medium",
        "A contact appearing on multiple homes can indicate a professional or a multi-property owner; it is not proof of misrepresentation.",
    ),
    "mixed_identity": (
        "Advertiser type differs",
        "medium",
        "This contact also appears on an offer declared as an agency listing. Check the advertiser and any commission.",
    ),
    "price_mismatch": (
        "Prices differ across sources",
        "low",
        "The active source prices differ by more than 15%. Check the latest terms with the advertiser.",
    ),
    "private_commission": (
        "Commission on a private offer",
        "medium",
        "The source declares a private offer and also lists a commission.",
    ),
}


class PublicContactAdvert(PublicModel):
    id: PublicID
    name: ShortText
    kind: Literal["private", "agency"]
    profile_id: PublicID


class PublicListing(PublicModel):
    id: PublicID
    title: DisplayText
    description: Annotated[str, StringConstraints(max_length=20_000), AfterValidator(without_contacts)]
    city: ShortText
    district: ShortText
    region: ShortText
    address: DisplayText
    lat: float | None = Field(ge=-90, le=90)
    lon: float | None = Field(ge=-180, le=180)
    area_m2: float = Field(gt=0, le=10_000)
    rooms: int = Field(ge=1, le=100)
    floor: int | None = Field(ge=-2, le=200)
    rent_pln: Rent
    fees_pln: Charge | None
    deposit_pln: int | None = Field(ge=0, le=10_000_000)
    commission_pln: Charge | None
    total_monthly_pln: int | None = Field(ge=0, le=2_000_000)
    advertiser_type: Advertiser
    property_type: Literal["apartment", "house", "room"]
    status: Status
    amenities: list[ShortText] = Field(max_length=40)
    images: list[PublicURL] = Field(max_length=30)
    risk_flags: list[PublicRiskFlag] = Field(max_length=10)
    risk_score: int = Field(ge=0, le=100)
    is_demo: bool
    first_seen: UTCText
    last_seen: UTCText
    updated_at: UTCText
    sources: list[PublicSourceAdvert] = Field(max_length=PUBLIC_CARD_LINKS)
    contact_adverts: list[PublicContactAdvert] = Field(default_factory=list, max_length=PUBLIC_CARD_LINKS)

    @model_validator(mode="after")
    def consistent_fields(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("Latitude and longitude must be provided together")
        total = None if self.fees_pln is None else self.rent_pln + self.fees_pln
        if self.total_monthly_pln != total:
            raise ValueError("Total must be base rent plus known fees")
        if self.status != "active":
            self.contact_adverts = []
        return self


class PublicObservation(PublicModel):
    at: UTCText
    rent_pln: Rent
    fees_pln: Charge | None
    status: Status


class PublicListingDetail(PublicListing):
    history: list[PublicObservation] = Field(max_length=100)


class PublicSearchPage(PublicModel):
    items: list[PublicListing] = Field(max_length=SEARCH_PAGE_SIZE)
    total: Count
    page: int = Field(ge=1, le=SEARCH_WINDOW)
    page_size: int = Field(ge=1, le=SEARCH_PAGE_SIZE)
    engine: Literal["elasticsearch", "postgresql", "sqlite"]
    degraded: bool
    consistency: Literal["eventual", "sql_checked", "sql"]
    total_relation: Literal["index", "exact"]

    def validate_index_page(self, filters: SearchFilters):
        expected = min(filters.page_size, max(0, self.total - filters.offset))
        if (
            self.page != filters.page
            or self.page_size != filters.page_size
            or self.engine != "elasticsearch"
            or self.degraded
            or self.consistency != "eventual"
            or self.total_relation != "index"
            or len(self.items) != expected
            or len({item.id for item in self.items}) != expected
            or any(item.status != "active" for item in self.items)
        ):
            raise ValueError("Inconsistent index page")
        field = SORT_FIELDS[filters.sort]

        def sort_value(item):
            value = getattr(item, field)
            return datetime.fromisoformat(value) if field == "first_seen" else value

        stable = sorted(self.items, key=lambda item: item.id)
        if self.items != sorted(stable, key=sort_value, reverse=filters.sort != "price_asc"):
            raise ValueError("Unordered index page")
        return self


class PublicMarketPoint(PublicModel):
    month: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    median_rent_pln: float = Field(gt=0)
    median_per_m2: float = Field(ge=0)
    sample_size: int = Field(gt=0)
    is_demo: bool


class PublicMarketHistory(PublicModel):
    points: list[PublicMarketPoint] = Field(max_length=120)
    methodology: str
    city: ShortText
    district: ShortText
    region: ShortText


class PublicMarketSummary(PublicModel):
    homes: Count
    source_listings: Count
    duplicates_removed: int
    private_homes: Count
    median_rent_pln: float | None = Field(gt=0)
    demo: bool
    districts: list[ShortText]
    cities: list[ShortText]


class PublicSourceError(PublicModel):
    kind: Literal[
        "SourceAccessError",
        "HTTPStatusError",
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
        "ConnectError",
        "ParseError",
        "PayloadTooLarge",
        "LeaseLost",
        "ValueError",
        "other",
    ]
    stage: Literal["detail", "discovery", "collection", "other"]
    http_status: int | None = Field(ge=100, le=599)

    @field_validator("kind", "stage", mode="before")
    @classmethod
    def error_category(cls, value, info):
        from typing import get_args

        return value if value in get_args(cls.model_fields[info.field_name].annotation) else "other"

    @field_validator("http_status", mode="before")
    @classmethod
    def known_http_status(cls, value):
        return value if type(value) is int and 100 <= value <= 599 else None


class PublicCollectorHealth(PublicModel):
    status: Literal["running", "succeeded", "partial", "failed", "interrupted", "other"]
    city: ShortText
    started_at: UTCText
    finished_at: UTCText | None
    ingested: Count
    checked: Count
    fresh_skipped: Count
    limited: bool
    errors: list[PublicSourceError] = Field(max_length=20)
    consecutive_failures: Count
    last_success_at: UTCText | None
    retry_after: UTCText | None

    @field_validator("status", mode="before")
    @classmethod
    def known_status(cls, value):
        return value if value in ("running", "succeeded", "partial", "failed", "interrupted") else "other"

    @field_validator("city", mode="before")
    @classmethod
    def collector_city(cls, value):
        return value if isinstance(value, str) and not any(char in value for char in "/?@#") else ""

    @field_validator("ingested", "checked", "fresh_skipped", mode="before")
    @classmethod
    def known_count(cls, value):
        return value if type(value) is int and value >= 0 else 0

    @field_validator("limited", mode="before")
    @classmethod
    def known_limit(cls, value):
        return value is True


class PublicSourceHealth(PublicModel):
    name: Provider
    enabled: bool
    mode: Literal["feed", "portal", "jsonld", "other"]
    status: Literal["configured", "disabled"]
    cadence_minutes: int | None = Field(ge=1, le=10_080)
    disabled_reason: Literal["Source collection is disabled."] | None
    last_observed_at: UTCText | None
    stored_adverts: Count
    health: PublicCollectorHealth | None


class PublicSources(PublicModel):
    sources: list[PublicSourceHealth]
    demo_mode: bool


class PublicError(PublicModel):
    detail: str
