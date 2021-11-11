"""Transactional account closure fence and bounded, private own-data export."""
import hashlib
import json
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import LargeBinary, String, cast, func, select, text
from sqlalchemy.orm import Session

from .db import get_session
from .models import (AccountClosure, Advert, AdvertiserProfile, EmailSubscription, Favorite,
                     Message, SavedSearch, SeenPrice)
from .security import require_claims
from .settings import get_settings

router = APIRouter(tags=["Account"])
EXPORT_LIMIT = 10 * 1024 * 1024


def guard_account_write(session, user_id, *, closing=False):
    """Hold the per-account lock through commit; lock identity before calling if needed."""
    if session.bind.dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(("account:" + user_id).encode()).digest()[:8], "big", signed=True)
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    elif session.bind.dialect.name == "sqlite":
        # SQLite has no row/advisory locks. Take its writer reservation before
        # any reads so cleanup and stale writes cannot both pass the fence.
        connection = session.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.exec_driver_sql("UPDATE account_closures SET user_id=user_id WHERE 0")
    if session.get(AccountClosure, user_id):
        if not closing:
            raise HTTPException(401, "Account is closed")
    elif closing:
        session.add(AccountClosure(user_id=user_id))
        session.flush()


def validate_export_token(value, claims):
    settings = get_settings()
    try:
        payload = jwt.decode(
            value, settings.jwt_public_key.replace("\\n", "\n") or settings.jwt_secret,
            algorithms=["RS256"] if settings.jwt_public_key else ["HS256"],
            issuer=settings.jwt_issuer, audience="realtoruch-account-export",
            options={"require": ["exp", "iat", "sub", "sid", "iss", "aud", "purpose"]},
        )
        if payload["purpose"] != "account_export" or payload["sub"] != claims["sub"] or payload["sid"] != claims.get("sid"):
            raise ValueError("wrong export binding")
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, "Export reauthentication required") from None


def export_bytes(session, user_id, email):
    # Only explicitly named fields are exported. Preflight variable-length fields
    # in SQL, before fetching values into Python, including legacy oversized rows.
    groups = [
        ("profile", AdvertiserProfile, ["name", "kind", "description", "updated_at"], AdvertiserProfile.user_id == user_id),
        ("email_preferences", EmailSubscription, ["email", "enabled", "verified_at"], EmailSubscription.user_id == user_id),
        ("favorites", Favorite, ["listing_id", "created_at", "price_floor"], Favorite.user_id == user_id),
        ("searches", SavedSearch, ["id", "name", "filters", "created_at"], SavedSearch.user_id == user_id),
        ("seen", SeenPrice, ["listing_id", "rent_pln", "seen_at"], SeenPrice.user_id == user_id),
        ("adverts", Advert, ["id", "listing_id", "draft", "state", "version", "created_at", "updated_at"], Advert.user_id == user_id),
        ("sent_messages", Message, ["id", "conversation_id", "body", "created_at"], Message.sender_id == user_id),
    ]
    parts = []
    size = 0
    def append(value):
        nonlocal size
        size += len(value)
        if size > EXPORT_LIMIT:
            raise HTTPException(413, "export_too_large: a paginated export is required")
        parts.append(value)
    def encode(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=lambda v: v.isoformat() + "Z" if isinstance(v, datetime) else str(v)).encode("utf-8")
    append(b'{"version":1,"account":')
    append(encode({"id": user_id, "email": email}))
    for name, model, fields, predicate in groups:
        columns = [getattr(model, field) for field in fields]
        def byte_length(column):
            value = cast(column, String)
            length = (func.octet_length(value) if session.bind.dialect.name == "postgresql"
                      else func.length(cast(value, LargeBinary)))
            return func.coalesce(length, 0)
        raw_bytes = session.scalar(select(func.coalesce(func.sum(sum(byte_length(c) for c in columns)), 0))
                                   .select_from(model).where(predicate))
        if raw_bytes > EXPORT_LIMIT - size:
            raise HTTPException(413, "export_too_large: a paginated export is required")
        append(b',' + encode(name) + b':[')
        first = True
        for row in session.execute(select(*columns).where(predicate).execution_options(yield_per=1)):
            if not first:
                append(b',')
            item = dict(zip(fields, row))
            if name == "adverts":
                from .marketplace import AdvertBody
                from pydantic import ValidationError
                try:
                    clean = {k: v for k, v in item["draft"].items() if k in AdvertBody.model_fields}
                    item["draft"] = AdvertBody.model_validate(clean).model_dump(mode="json")
                except (ValidationError, AttributeError, TypeError):
                    raise HTTPException(422, "export_data_invalid: contact support") from None
            elif name == "searches":
                from .schemas import SearchFilters
                from pydantic import ValidationError
                try:
                    clean = {k: v for k, v in item["filters"].items() if k in SearchFilters.model_fields}
                    item["filters"] = SearchFilters.model_validate(clean).model_dump(mode="json")
                except (ValidationError, AttributeError, TypeError):
                    raise HTTPException(422, "export_data_invalid: contact support") from None
            append(encode(item))
            first = False
        append(b']')
    append(b'}')
    return b''.join(parts)


@router.get("/v1/me/export")
def export_account(request: Request, claims=Depends(require_claims), session=Depends(get_session)):
    validate_export_token(request.headers.get("X-Account-Export-Token", ""), claims)
    guard_account_write(session, claims["sub"])
    if session.bind.dialect.name == "postgresql":
        # The guard serializes this user's writers; a separate repeatable-read
        # transaction gives every exported table one database snapshot.
        with session.bind.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with Session(connection) as snapshot:
                content = export_bytes(snapshot, claims["sub"], claims.get("email"))
    else:
        content = export_bytes(session, claims["sub"], claims.get("email"))
    return Response(content, media_type="application/json", headers={"Cache-Control": "private, no-store"})
