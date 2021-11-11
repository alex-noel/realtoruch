"""Owner/agency publishing and private conversations for first-party adverts."""

import base64
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from sqlalchemy import case, func, or_, select, text, tuple_, update

from .db import get_session
from .ingest import ingest, lock_identity, recompute_listing
from .models import Advert, AdvertiserProfile, Conversation, Listing, Message, ModerationAction, Report, now
from .normalization import clean_text
from .query import serialize_many
from .schemas import RawListing
from .security import require_claims, require_user
from .settings import get_settings

router = APIRouter(tags=["Marketplace"])


class ProfileBody(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    kind: Literal["private", "agency"]
    description: str = Field(default="", max_length=2000)

    @field_validator("name", "description")
    @classmethod
    def plain(cls, value):
        return clean_text(value)


class AdvertBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=5, max_length=240)
    description: str = Field(min_length=20, max_length=20000)
    city: str = Field(min_length=2, max_length=100)
    district: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=100)
    address: str = Field(min_length=3, max_length=240)
    lat: float = Field(ge=49, le=55)
    lon: float = Field(ge=14, le=24.2)
    area_m2: float = Field(gt=0, le=10000)
    rooms: int = Field(ge=1, le=100)
    floor: int | None = Field(default=None, ge=-2, le=200)
    rent_pln: int = Field(gt=0, le=1000000)
    fees_pln: int | None = Field(default=None, ge=0, le=1000000)
    deposit_pln: int | None = Field(default=None, ge=0, le=10000000)
    commission_pln: int | None = Field(default=None, ge=0, le=1000000)
    property_type: Literal["apartment", "house", "room"] = "apartment"
    amenities: list[str] = Field(default_factory=list, max_length=40)
    images: list[HttpUrl] = Field(default_factory=list, max_length=30)

    @field_validator("images")
    @classmethod
    def secure_images(cls, values):
        if any(value.scheme != "https" or value.username or value.password for value in values):
            raise ValueError("Use HTTPS image URLs without credentials")
        return values

    @field_validator("title", "description", "city", "district", "region", "address")
    @classmethod
    def plain(cls, value):
        return clean_text(value)


class VersionBody(BaseModel):
    version: int = Field(ge=1)


class EditBody(VersionBody):
    advert: AdvertBody


def advertiser_data(profile):
    return {
        "id": profile.user_id,
        "name": profile.name,
        "kind": profile.kind,
        "description": profile.description,
    }


def advert_data(advert):
    return {
        "id": advert.id,
        "listing_id": advert.listing_id,
        "state": advert.state,
        "version": advert.version,
        "advert": advert.draft,
        "updated_at": advert.updated_at.isoformat() + "Z",
    }


def owner_advert(session, advert_id, user_id):
    lock_identity(session)
    row = session.scalar(
        select(Advert).where(Advert.id == advert_id, Advert.user_id == user_id).with_for_update()
    )
    if not row:
        raise HTTPException(404, "Advert not found")
    return row


def advance_version(session, advert, expected):
    changed = session.execute(
        update(Advert)
        .where(Advert.id == advert.id, Advert.version == expected)
        .values(
            version=Advert.version + 1,
            updated_at=now(),
        )
    ).rowcount
    if not changed:
        raise HTTPException(409, "This advert changed on another device. Reload before editing.")
    session.refresh(advert)


def publish_observation(session, advert, profile, status):
    raw = RawListing(
        **advert.draft,
        source="realtoruch",
        external_id=advert.id,
        url=get_settings().public_web_url.rstrip("/") + "/?advert=" + advert.id,
        advertiser_type=profile.kind,
        status=status,
        is_demo=get_settings().demo_mode,
    )
    result = ingest(session, raw)
    advert.listing_id = result["listing_id"]


def verified(claims):
    if not claims.get("email_verified"):
        raise HTTPException(403, "Verify your account email first in Account")


@router.get("/v1/me/advertiser")
def my_profile(user_id=Depends(require_user), session=Depends(get_session)):
    profile = session.get(AdvertiserProfile, user_id)
    return {"profile": advertiser_data(profile) if profile else None}


@router.put("/v1/me/advertiser")
def save_profile(body: ProfileBody, claims=Depends(require_claims), session=Depends(get_session)):
    lock_identity(session)
    profile = session.get(AdvertiserProfile, claims["sub"])
    if (
        profile
        and profile.kind != body.kind
        and session.scalar(
            select(Advert.id)
            .where(
                Advert.user_id == claims["sub"],
                Advert.state == "published",
            )
            .limit(1)
        )
    ):
        raise HTTPException(409, "Withdraw published adverts before changing advertiser type")
    if not profile:
        profile = AdvertiserProfile(user_id=claims["sub"])
        session.add(profile)
    changed_public = profile.name != body.name or profile.kind != body.kind
    profile.name, profile.kind, profile.description = body.name, body.kind, body.description
    profile.updated_at = now()
    if changed_public:
        from .indexing import queue_listing
        for listing_id in sorted(set(session.scalars(select(Advert.listing_id).where(
            Advert.user_id == claims["sub"], Advert.state == "published", Advert.listing_id.is_not(None)
        )).all())):
            queue_listing(session, listing_id)
    session.commit()
    return {"profile": advertiser_data(profile)}


@router.get("/v1/advertisers/{advertiser_id}")
def profile(advertiser_id: str, session=Depends(get_session)):
    row = session.get(AdvertiserProfile, advertiser_id)
    if not row:
        raise HTTPException(404, "Advertiser not found")
    homes = session.scalars(
        select(Listing)
        .where(
            Listing.id.in_(
                select(Advert.listing_id).where(Advert.user_id == advertiser_id, Advert.state == "published")
            ),
            Listing.status == "active",
        )
        .limit(100)
    ).all()
    return {"profile": advertiser_data(row), "items": serialize_many(session, homes)}


@router.get("/v1/me/adverts")
def my_adverts(user_id=Depends(require_user), session=Depends(get_session)):
    rows = session.scalars(
        select(Advert).where(Advert.user_id == user_id).order_by(Advert.updated_at.desc()).limit(100)
    ).all()
    hidden = set(
        session.scalars(
            select(Listing.id).where(
                Listing.id.in_([row.listing_id for row in rows if row.listing_id]), Listing.hidden.is_(True)
            )
        )
    )
    return {"items": [{**advert_data(row), "hidden": row.listing_id in hidden} for row in rows]}


@router.post("/v1/me/adverts", status_code=201)
def create_advert(body: AdvertBody, user_id=Depends(require_user), session=Depends(get_session)):
    profile = session.scalar(
        select(AdvertiserProfile).where(AdvertiserProfile.user_id == user_id).with_for_update()
    )
    if not profile:
        raise HTTPException(422, "Create your advertiser profile first")
    if session.scalar(select(func.count()).select_from(Advert).where(Advert.user_id == user_id)) >= 100:
        raise HTTPException(422, "You can keep up to 100 adverts")
    advert = Advert(user_id=user_id, draft=body.model_dump(mode="json"))
    session.add(advert)
    session.commit()
    return advert_data(advert)


@router.put("/v1/me/adverts/{advert_id}")
def edit_advert(advert_id: str, body: EditBody, user_id=Depends(require_user), session=Depends(get_session)):
    advert = owner_advert(session, advert_id, user_id)
    advance_version(session, advert, body.version)
    advert.draft = body.advert.model_dump(mode="json")
    # Editing a published advert updates it in the same transaction, including alerts/history.
    if advert.state == "published":
        publish_observation(session, advert, session.get(AdvertiserProfile, user_id), "active")
    session.commit()
    return advert_data(advert)


@router.post("/v1/me/adverts/{advert_id}/publish")
def publish_advert(
    advert_id: str, body: VersionBody, claims=Depends(require_claims), session=Depends(get_session)
):
    verified(claims)
    advert = owner_advert(session, advert_id, claims["sub"])
    advance_version(session, advert, body.version)
    if advert.listing_id and session.get(Listing, advert.listing_id).hidden:
        raise HTTPException(
            409, "This home is hidden after review. Submit an appeal to request another review."
        )
    publish_observation(session, advert, session.get(AdvertiserProfile, claims["sub"]), "active")
    advert.state = "published"
    session.commit()
    return advert_data(advert)


@router.post("/v1/me/adverts/{advert_id}/withdraw")
def withdraw_advert(
    advert_id: str, body: VersionBody, user_id=Depends(require_user), session=Depends(get_session)
):
    advert = owner_advert(session, advert_id, user_id)
    advance_version(session, advert, body.version)
    if advert.listing_id:
        publish_observation(session, advert, session.get(AdvertiserProfile, user_id), "inactive")
    advert.state = "withdrawn"
    session.commit()
    return advert_data(advert)


@router.get("/v1/adverts/{advert_id}")
def public_advert(advert_id: str, session=Depends(get_session)):
    advert = session.get(Advert, advert_id)
    home = session.get(Listing, advert.listing_id) if advert and advert.listing_id else None
    if not advert or advert.state != "published" or not home or home.status != "active":
        raise HTTPException(404, "Advert is not available")
    return {
        "id": advert.id,
        "listing_id": advert.listing_id,
        "advertiser": advertiser_data(session.get(AdvertiserProfile, advert.user_id)),
    }


class MessageBody(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    client_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{10,64}$")

    @field_validator("body")
    @classmethod
    def not_blank(cls, value):
        value = clean_text(value, redact_contacts=False)
        if not value.strip():
            raise ValueError("Write a message first")
        return value


def _begin_conversation_write(session):
    # SQLite ignores FOR UPDATE. Reserve its writer before reading the thread
    # (or before checking whether a start needs to create the thread).
    if session.bind.dialect.name == "sqlite":
        connection = session.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")


def conversation_for(session, conversation_id, user_id, *, write=False):
    query = select(Conversation).where(
        Conversation.id == conversation_id,
        or_(Conversation.renter_id == user_id, Conversation.owner_id == user_id),
    )
    if write:
        _begin_conversation_write(session)
        query = query.with_for_update()
    row = session.scalar(query)
    if not row:
        raise HTTPException(404, "Conversation not found")
    return row


def _latest_message(conversation_id):
    return (
        select(Message.created_at, Message.id)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )


def _message_boundary(session, conversation_id, message_id):
    boundary = session.execute(
        select(Message.created_at, Message.id)
        .where(Message.conversation_id == conversation_id, Message.id == message_id)
    ).one_or_none()
    if boundary is None:
        raise HTTPException(422, "Invalid message cursor")
    return boundary


def send_message(session, conversation, user_id, body):
    existing = session.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.sender_id == user_id,
            Message.client_id == body.client_id,
        )
    )
    if existing:
        if existing.body != body.body:
            raise HTTPException(409, "Client message ID already used with different text")
        return existing
    if conversation.blocked_by:
        raise HTTPException(403, "This conversation is blocked")
    if session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "message:" + user_id})
    if (
        session.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.sender_id == user_id,
                Message.created_at > now() - timedelta(minutes=1),
            )
        )
        >= 20
    ):
        raise HTTPException(429, "Please wait before sending more messages")
    # With the thread locked, assign an arrival order even if the wall clock
    # ties or goes backward. UUIDs alone cannot order arrivals within a tie.
    latest = session.execute(_latest_message(conversation.id)).first()
    prior_stamps = (
        conversation.updated_at,
        conversation.owner_read_at,
        conversation.renter_read_at,
        latest.created_at if latest else None,
    )
    previous = max(stamp for stamp in prior_stamps if stamp is not None)
    created_at = max(now(), previous + timedelta(microseconds=1))
    row = Message(
        conversation_id=conversation.id,
        sender_id=user_id,
        client_id=body.client_id,
        body=body.body,
        created_at=created_at,
    )
    session.add(row)
    conversation.updated_at = created_at
    session.flush()
    return row


def message_data(row, user_id):
    return {
        "id": row.id,
        "body": row.body,
        "mine": row.sender_id == user_id,
        "created_at": row.created_at.isoformat() + "Z",
    }


@router.post("/v1/adverts/{advert_id}/conversations", status_code=201)
def start_conversation(
    advert_id: str, body: MessageBody, claims=Depends(require_claims), session=Depends(get_session)
):
    verified(claims)
    lock_identity(session, shared=True)
    _begin_conversation_write(session)
    advert = session.scalar(select(Advert).where(Advert.id == advert_id).with_for_update())
    home = session.get(Listing, advert.listing_id) if advert and advert.listing_id else None
    if not advert or advert.state != "published" or not home or home.status != "active":
        raise HTTPException(404, "Advert is not available")
    if advert.user_id == claims["sub"]:
        raise HTTPException(422, "This is your own advert")
    row = session.scalar(
        select(Conversation)
        .where(Conversation.advert_id == advert_id, Conversation.renter_id == claims["sub"])
        .with_for_update()
    )
    if not row:
        row = Conversation(advert_id=advert_id, renter_id=claims["sub"], owner_id=advert.user_id)
        session.add(row)
        session.flush()
    message = send_message(session, row, claims["sub"], body)
    session.commit()
    return {"id": row.id, "message": message_data(message, claims["sub"])}


PageLimit = Annotated[int, Query(ge=1, le=50)]
MessageCursor = Annotated[str | None, Query(min_length=1, max_length=36)]


def _encode_inbox_cursor(stamp, conversation_id):
    data = f"v1|{stamp.isoformat(timespec='microseconds')}Z|{conversation_id}"
    return base64.urlsafe_b64encode(data.encode("ascii")).decode("ascii").rstrip("=")


def _decode_inbox_cursor(cursor):
    try:
        payload = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        version, stamp, conversation_id = payload.decode("ascii").split("|")
        updated_at = datetime.fromisoformat(stamp.removesuffix("Z"))
        if (
            version == "v1"
            and updated_at.tzinfo is None
            and str(UUID(conversation_id)) == conversation_id
            and _encode_inbox_cursor(updated_at, conversation_id) == cursor
        ):
            return updated_at, conversation_id
    except ValueError:
        pass
    raise HTTPException(422, "Invalid conversation cursor")


def _after_read(stamp, message_id, read_at, read_id):
    # For legacy timestamp-only state, the tuple comparison is unknown at an
    # equal timestamp, so those messages remain read.
    return or_(read_at.is_(None), tuple_(stamp, message_id) > tuple_(read_at, read_id))


@router.get("/v1/me/conversations")
def conversations(
    cursor: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    limit: PageLimit = 50,
    user_id=Depends(require_user),
    session=Depends(get_session),
):
    query = (
        select(Conversation, Advert.draft["title"].as_string(), Advert.listing_id)
        .join(Advert, Advert.id == Conversation.advert_id)
        .where(
            or_(
                Conversation.renter_id == user_id,
                Conversation.owner_id == user_id,
            )
        )
    )
    if cursor is not None:
        query = query.where(tuple_(Conversation.updated_at, Conversation.id) < _decode_inbox_cursor(cursor))
    rows = session.execute(
        query.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit + 1)
    ).all()
    more = len(rows) > limit
    rows = rows[:limit]
    if not rows:
        return {"items": [], "next_cursor": None}
    read_at = case(
        (Conversation.owner_id == user_id, Conversation.owner_read_at),
        else_=Conversation.renter_read_at,
    )
    read_id = case(
        (Conversation.owner_id == user_id, Conversation.owner_read_message_id),
        else_=Conversation.renter_read_message_id,
    )
    unread = dict(
        session.execute(
            select(Message.conversation_id, func.count())
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.id.in_([row.id for row, _, _ in rows]),
                Message.sender_id != user_id,
                _after_read(Message.created_at, Message.id, read_at, read_id),
            )
            .group_by(Message.conversation_id)
        ).all()
    )
    items = [
        {
            "id": row.id,
            "title": title,
            "listing_id": listing_id,
            "unread_count": unread.get(row.id, 0),
            "blocked": bool(row.blocked_by),
            "can_unblock": row.blocked_by == user_id,
            "updated_at": row.updated_at.isoformat() + "Z",
        }
        for row, title, listing_id in rows
    ]
    last = rows[-1][0]
    return {"items": items, "next_cursor": _encode_inbox_cursor(last.updated_at, last.id) if more else None}


@router.get("/v1/me/conversations/{conversation_id}")
def conversation_detail(
    conversation_id: str,
    before: MessageCursor = None,
    limit: PageLimit = 50,
    user_id=Depends(require_user),
    session=Depends(get_session),
):
    row = conversation_for(session, conversation_id, user_id)
    query = select(Message).where(Message.conversation_id == conversation_id)
    if before is not None:
        cursor = _message_boundary(session, row.id, before)
        query = query.where(tuple_(Message.created_at, Message.id) < (cursor.created_at, cursor.id))
    messages = session.scalars(query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)).all()
    more = len(messages) > limit
    messages = messages[:limit]
    return {
        "id": row.id,
        "items": [message_data(m, user_id) for m in reversed(messages)],
        "next_cursor": messages[-1].id if more else None,
        "blocked": bool(row.blocked_by),
        "can_unblock": row.blocked_by == user_id,
    }


class ReadMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_message_id: str = Field(min_length=1, max_length=36)


async def _read_message_body(request: Request, body: ReadMessageBody | None = None):
    # FastAPI represents both an absent body and explicit JSON null as None.
    if body is None and await request.body():
        raise HTTPException(422, "Invalid message cursor")
    return body


@router.put("/v1/me/conversations/{conversation_id}/read")
def read_conversation(
    conversation_id: str,
    body: Annotated[ReadMessageBody | None, Depends(_read_message_body)],
    user_id=Depends(require_user),
    session=Depends(get_session),
):
    row = conversation_for(session, conversation_id, user_id, write=True)
    if body is None:
        boundary = session.execute(_latest_message(row.id)).first()
    else:
        boundary = _message_boundary(session, row.id, body.last_message_id)
    if row.owner_id == user_id:
        read_at, read_id = Conversation.owner_read_at, Conversation.owner_read_message_id
    else:
        read_at, read_id = Conversation.renter_read_at, Conversation.renter_read_message_id
    if boundary is not None:
        session.execute(
            update(Conversation)
            .where(Conversation.id == row.id, _after_read(boundary.created_at, boundary.id, read_at, read_id))
            .values({read_at: boundary.created_at, read_id: boundary.id})
        )
    session.commit()
    return {"read": True}


@router.post("/v1/me/conversations/{conversation_id}/messages", status_code=201)
def reply(
    conversation_id: str, body: MessageBody, claims=Depends(require_claims), session=Depends(get_session)
):
    verified(claims)
    row = conversation_for(session, conversation_id, claims["sub"], write=True)
    message = send_message(session, row, claims["sub"], body)
    session.commit()
    return message_data(message, claims["sub"])


class BlockBody(BaseModel):
    blocked: bool


@router.put("/v1/me/conversations/{conversation_id}/block")
def block_conversation(
    conversation_id: str, body: BlockBody, user_id=Depends(require_user), session=Depends(get_session)
):
    row = conversation_for(session, conversation_id, user_id, write=True)
    if not body.blocked and row.blocked_by and row.blocked_by != user_id:
        raise HTTPException(403, "Only the person who blocked this conversation can unblock it")
    if body.blocked and not row.blocked_by:
        row.blocked_by = user_id
    elif not body.blocked:
        row.blocked_by = None
    session.commit()
    return {"blocked": bool(row.blocked_by)}


def is_moderator(user_id):
    return user_id in {uid.strip() for uid in get_settings().moderator_user_ids.split(",") if uid.strip()}


def require_moderator(claims=Depends(require_claims)):
    if not is_moderator(claims["sub"]) or not claims.get("email_verified"):
        raise HTTPException(403, "Moderator access required")
    return claims["sub"]


@router.get("/v1/me/capabilities")
def capabilities(claims=Depends(require_claims)):
    return {"moderator": is_moderator(claims["sub"]) and claims.get("email_verified", False)}


@router.get("/v1/moderation/reports")
def reports(_=Depends(require_moderator), session=Depends(get_session)):
    rows = session.execute(
        select(Report, Listing)
        .join(Listing)
        .where(Report.status == "pending")
        .order_by(Report.created_at)
        .limit(100)
    ).all()
    return {
        "items": [
            {
                "id": report.id,
                "reason": report.reason,
                "created_at": report.created_at.isoformat() + "Z",
                "listing": serialize_many(session, [home])[0],
                "hidden": home.hidden,
            }
            for report, home in rows
        ]
    }


class ReviewBody(BaseModel):
    action: Literal["hide", "restore", "dismiss"]
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/v1/moderation/reports/{report_id}/review")
def review(
    report_id: str, body: ReviewBody, moderator=Depends(require_moderator), session=Depends(get_session)
):
    lock_identity(session)
    report = session.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if not report or report.status != "pending":
        raise HTTPException(409, "Report is no longer pending")
    home = session.get(Listing, report.listing_id)
    if body.action != "dismiss":
        home.hidden = body.action == "hide"
        recompute_listing(session, home)
    report.status = "reviewed"
    session.add(
        ModerationAction(
            listing_id=home.id, moderator_id=moderator, action=body.action, reason=clean_text(body.reason)
        )
    )
    session.commit()
    return {"reviewed": True, "hidden": home.hidden}


@router.post("/v1/me/adverts/{advert_id}/appeal", status_code=201)
def appeal(advert_id: str, body: ReviewBody, user_id=Depends(require_user), session=Depends(get_session)):
    advert = owner_advert(session, advert_id, user_id)
    if not advert.listing_id or not session.get(Listing, advert.listing_id).hidden:
        raise HTTPException(422, "This advert is not hidden")
    if session.scalar(
        select(Report.id).where(
            Report.user_id == user_id, Report.listing_id == advert.listing_id, Report.status == "pending"
        )
    ):
        raise HTTPException(409, "A review is already pending")
    session.add(
        Report(
            listing_id=advert.listing_id, user_id=user_id, reason="Appeal: " + clean_text(body.reason)[:990]
        )
    )
    session.commit()
    return {"message": "Appeal submitted for review"}
