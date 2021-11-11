from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    BigInteger,
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
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SearchRevision(Base):
    __tablename__ = "search_revisions"
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")


class SourceListing(Base):
    __tablename__ = "source_listings"
    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        Index("ix_source_recheck", "source", "status", "observed_at"),
        Index("ix_source_lookup", "source", "url"),
    )
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
    __table_args__ = (Index("ix_outbox_pending", "delivered_at", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_index_status: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    price_floor: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(100))
    filters: Mapped[dict] = mapped_column(JSON)
    city_key: Mapped[str] = mapped_column(String(100), default="", server_default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"))
    user_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SeenPrice(Base):
    __tablename__ = "seen_prices"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    rent_pln: Mapped[int] = mapped_column(Integer, primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SearchMatch(Base):
    __tablename__ = "search_matches"
    search_id: Mapped[str] = mapped_column(
        ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True
    )
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AlertEvent(Base):
    __tablename__ = "alert_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_inbox", "user_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36))
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"))
    search_id: Mapped[str | None] = mapped_column(
        ForeignKey("saved_searches.id", ondelete="SET NULL"), nullable=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(240))
    rent_pln: Mapped[int] = mapped_column(Integer)
    previous_rent_pln: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    data: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "subscription_id"),
        Index("ix_push_due", "status", "next_attempt_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id"))
    subscription_id: Mapped[str] = mapped_column(ForeignKey("push_subscriptions.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EmailSubscription(Base):
    __tablename__ = "email_subscriptions"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True)


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"
    __table_args__ = (Index("ix_email_due", "status", "next_attempt_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("email_subscriptions.user_id"))
    notification_id: Mapped[str | None] = mapped_column(
        ForeignKey("notifications.id"), nullable=True, unique=True
    )
    confirmation_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AdvertiserProfile(Base):
    __tablename__ = "advertiser_profiles"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(2000), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Advert(Base):
    __tablename__ = "adverts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("advertiser_profiles.user_id"), index=True)
    listing_id: Mapped[str | None] = mapped_column(ForeignKey("listings.id"), nullable=True, index=True)
    draft: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(20), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("advert_id", "renter_id"),
        Index("ix_conversations_renter_order", "renter_id", "updated_at", "id"),
        Index("ix_conversations_owner_order", "owner_id", "updated_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    advert_id: Mapped[str] = mapped_column(ForeignKey("adverts.id"))
    renter_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    renter_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    renter_read_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner_read_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    blocked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sender_id", "client_id"),
        Index("ix_message_thread", "conversation_id", "created_at"),
        Index("ix_message_thread_order", "conversation_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    sender_id: Mapped[str] = mapped_column(String(36), index=True)
    client_id: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ModerationAction(Base):
    __tablename__ = "moderation_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    moderator_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (Index("ix_collection_source_time", "source", "started_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source: Mapped[str] = mapped_column(String(40))
    city: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)


class SourcePollState(Base):
    __tablename__ = "source_poll_state"
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    lease_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_allowed_request: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CollectionFetchState(Base):
    __tablename__ = "collection_fetch_state"
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    url_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_listing_id: Mapped[str] = mapped_column(ForeignKey("source_listings.id", ondelete="CASCADE"))
    validators: Mapped[dict] = mapped_column(JSON)


class ListingAlias(Base):
    __tablename__ = "listing_aliases"
    old_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)


class IdentityDecision(Base):
    __tablename__ = "identity_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    moderator_id: Mapped[str] = mapped_column(String(36))
    from_listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"))
    to_listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"))
    source_ids: Mapped[list] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
