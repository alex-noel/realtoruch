from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def uid():
    return str(uuid4())


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (Index("ix_listing_match_candidates", "city", "rooms", "area_m2"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(100), index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    region: Mapped[str] = mapped_column(String(100), index=True)
    address: Mapped[str] = mapped_column(String(240))
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_m2: Mapped[float] = mapped_column(Float)
    rooms: Mapped[int] = mapped_column(Integer)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rent_pln: Mapped[int] = mapped_column(Integer, index=True)
    fees_pln: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_pln: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission_pln: Mapped[int | None] = mapped_column(Integer, nullable=True)
    advertiser_type: Mapped[str] = mapped_column(String(20), default="unknown")
    property_type: Mapped[str] = mapped_column(String(30), default="apartment")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    amenities: Mapped[list] = mapped_column(JSON, default=list)
    images: Mapped[list] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SourceListing(Base):
    __tablename__ = "source_listings"
    __table_args__ = (UniqueConstraint("source", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    match_reason: Mapped[str] = mapped_column(Text, default="New property")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("source_listing_id", "observed_at"),
        Index("ix_obs_listing_time", "listing_id", "observed_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"))
    source_listing_id: Mapped[str] = mapped_column(ForeignKey("source_listings.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    rent_pln: Mapped[int] = mapped_column(Integer)
    fees_pln: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    changed: Mapped[bool] = mapped_column(Boolean)


class EventReceipt(Base):
    __tablename__ = "event_receipts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(100))
    filters: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"))
    user_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
