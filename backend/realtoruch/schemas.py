from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


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
    min_area: float | None = Field(default=None, ge=0)
    max_area: float | None = Field(default=None, ge=0)
    rooms: int | None = Field(default=None, ge=1, le=100)
    advertiser: Literal["all", "private", "agency"] = "all"
    no_commission: bool = False
    hide_suspicious: bool = False
    property_type: Literal["all", "apartment", "house", "room"] = "all"
    amenity: str = Field(default="", max_length=60)
    sort: Literal["newest", "price_asc", "price_desc", "area_desc"] = "newest"
    bbox: str | None = Field(default=None, max_length=100)
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=24, ge=1, le=100)

    @model_validator(mode="after")
    def ranges(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("Minimum price exceeds maximum price")
        if self.min_area is not None and self.max_area is not None and self.min_area > self.max_area:
            raise ValueError("Minimum area exceeds maximum area")
        if self.bbox:
            try:
                west, south, east, north = map(float, self.bbox.split(","))
                assert -180 <= west < east <= 180 and -90 <= south < north <= 90
            except (ValueError, AssertionError):
                raise ValueError("bbox must be west,south,east,north with increasing valid coordinates")
        return self
