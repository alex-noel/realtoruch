"""Bounded, owner-scoped image processing and derivative access."""
import hashlib
import io
import re
import warnings

import anyio
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from .account_data import guard_account_write
from .db import get_session
from .models import Advert, Listing, MediaAsset, now, uid
from .normalization import clean_text
from .security import require_claims
from .settings import get_settings
from .media_storage import GCSStorage, LocalStorage

router = APIRouter(tags=["Media"])
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000


def storage():
    settings = get_settings()
    if settings.media_storage_backend == "disabled":
        raise HTTPException(503, "Media storage is unavailable")
    if settings.media_storage_backend == "gcs":
        from google.cloud import storage as gcs
        return GCSStorage(gcs.Client().bucket(settings.media_gcs_bucket))
    return LocalStorage(settings.media_directory)


def key_for(asset, rendition):
    return asset.id + "/" + ("a" if rendition == "display" else "b")


def media_url(asset, rendition):
    return get_settings().media_public_base_url.rstrip("/") + "/v1/media/" + asset.id + "/" + rendition


def asset_data(asset):
    ready = asset.state == "ready"
    base = "/v1/me/media/" + asset.id
    return {"id": asset.id, "state": asset.state, "description": asset.description,
            "display_url": base + "/display" if ready else None,
            "thumbnail_url": base + "/thumbnail" if ready else None}


def verify_owner(claims):
    if not claims.get("email_verified"):
        raise HTTPException(403, "Verify your account email first in Account")
    return claims["sub"]


def valid_key(value):
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise HTTPException(422, "Invalid idempotency key")
    return value


def find_key(session, user, key):
    return session.scalar(select(MediaAsset).where(MediaAsset.user_id == user, MediaAsset.idempotency_key == key))


def owned(session, user, asset_id):
    row = session.get(MediaAsset, asset_id)
    if not row:
        raise HTTPException(404, "Media not found")
    if row.user_id != user:
        raise HTTPException(403, "Media not available")
    return row


def referenced(session, asset):
    return any(asset.id in (ad.draft.get("media_ids") or []) for ad in session.scalars(
        select(Advert).where(Advert.user_id == asset.user_id)))


def delete_bytes(asset, *, permanent=False):
    adapter = storage()
    for kind in ("display", "thumbnail"):
        (adapter.fence if permanent else adapter.delete)(key_for(asset, kind))


def decode(data, mime):
    expected = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    if mime not in expected:
        raise HTTPException(415, "Unsupported image type")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
                if (image.format == "PNG" and image.get_format_mimetype() == "image/apng") or (
                    image.format == "WEBP" and len(data) > 20 and data[:4] == b"RIFF"
                    and data[8:16] == b"WEBPVP8X" and data[20] & 2
                ):
                    raise HTTPException(422, "Animated images are not supported")
                if image.format != expected[mime]:
                    raise HTTPException(415, "Image type does not match")
                if max(image.size) > 32768 or image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(422, "Invalid image dimensions or animation")
                image.load()
                oriented = ImageOps.exif_transpose(image).convert("RGB")
                # A new canvas drops info dictionaries, ICC, EXIF, XMP and comments.
                clean = Image.new("RGB", oriented.size)
                clean.paste(oriented)
                output = []
                for size in (2048, 400):
                    rendition = clean.copy()
                    rendition.thumbnail((size, size), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    rendition.save(buf, format="JPEG", quality=85, optimize=True)
                    output.append(buf.getvalue())
                return output
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "Invalid image") from None


@router.post("/v1/me/media", status_code=201)
async def upload(request: Request, claims=Depends(require_claims), session=Depends(get_session),
                 idempotency_key: str = Header(alias="Idempotency-Key")):
    user = verify_owner(claims)
    if get_settings().media_storage_backend == "disabled":
        raise HTTPException(503, "Media storage is unavailable")
    key = valid_key(idempotency_key)
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1:
        raise HTTPException(400, "Invalid Content-Length")
    length = lengths[0] if lengths else None
    try:
        declared_length = int(length) if length is not None else None
    except ValueError:
        raise HTTPException(400, "Invalid Content-Length") from None
    if declared_length is not None and declared_length < 0:
        raise HTTPException(400, "Invalid Content-Length")
    if declared_length is not None and declared_length > MAX_BYTES:
        raise HTTPException(413, "Request too large")

    def reserve():
        guard_account_write(session, user)
        row = find_key(session, user, key)
        if not row:
            row = MediaAsset(id=uid(), user_id=user, idempotency_key=key, state="pending", description="")
            session.add(row)
        if row.state in ("deleted", "rejected"):
            raise HTTPException(409, "Upload key is no longer usable")
        asset_id = row.id
        session.commit()
        return asset_id

    asset_id = await anyio.to_thread.run_sync(reserve)
    mime = request.headers.get("content-type", "").split(";")[0].lower().strip()
    async with request.app.state.media_processors:
        data = bytearray()
        try:
            with anyio.fail_after(30):
                async for chunk in request.stream():
                    if len(data) + len(chunk) > MAX_BYTES:
                        raise HTTPException(413, "Request too large")
                    data.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, "Upload timed out") from None
        if declared_length is not None and declared_length != len(data):
            raise HTTPException(400, "Content-Length mismatch")
        digest = hashlib.sha256(data).hexdigest()

        def bind():
            guard_account_write(session, user)
            row = session.get(MediaAsset, asset_id, populate_existing=True)
            if not row or row.state in ("deleted", "rejected"):
                raise HTTPException(409, "Upload cancelled")
            if row.digest and row.digest != digest:
                raise HTTPException(409, "Upload key already used")
            row.digest = digest
            session.commit()

        await anyio.to_thread.run_sync(bind)
        try:
            renditions = await anyio.to_thread.run_sync(decode, bytes(data), mime)
        except HTTPException:
            def reject():
                guard_account_write(session, user)
                row = session.get(MediaAsset, asset_id, populate_existing=True)
                if row and row.state == "pending" and row.digest == digest:
                    row.state = "rejected"
                    session.commit()
            await anyio.to_thread.run_sync(reject)
            raise

        def finish():
            guard_account_write(session, user)
            row = session.get(MediaAsset, asset_id, populate_existing=True)
            if not row or row.state in ("deleted", "rejected"):
                raise HTTPException(409, "Upload cancelled")
            if row.state == "ready":
                if row.digest != digest:
                    raise HTTPException(409, "Upload key already used")
                return asset_data(row)
            # The account fence serializes finalization with deletion and erasure.
            delete_bytes(row)
            for kind, content in zip(("display", "thumbnail"), renditions):
                storage().put(key_for(row, kind), content)
            row.digest, row.state = digest, "ready"
            session.commit()
            return asset_data(row)
        return await anyio.to_thread.run_sync(finish)


@router.get("/v1/me/media/by-key/{key}")
def status_key(key: str, claims=Depends(require_claims), session=Depends(get_session)):
    user = verify_owner(claims)
    guard_account_write(session, user)
    row = find_key(session, user, valid_key(key))
    if not row:
        raise HTTPException(404, "Media not found")
    return asset_data(row)


@router.delete("/v1/me/media/by-key/{key}")
def cancel_key(key: str, claims=Depends(require_claims), session=Depends(get_session)):
    user = verify_owner(claims)
    guard_account_write(session, user)
    row = find_key(session, user, valid_key(key))
    if not row:
        row = MediaAsset(id=uid(), user_id=user, idempotency_key=key, state="deleted", description="")
        session.add(row)
    elif referenced(session, row):
        raise HTTPException(409, "Remove media from adverts before deleting")
    else:
        row.state = "deleted"
    session.commit()
    guard_account_write(session, user)
    row = owned(session, user, row.id)
    if row.digest is not None:
        delete_bytes(row, permanent=True)
        row.digest = None
    session.commit()
    return asset_data(row)


@router.get("/v1/me/media/{asset_id}")
def status(asset_id: str, claims=Depends(require_claims), session=Depends(get_session)):
    user = verify_owner(claims)
    guard_account_write(session, user)
    return asset_data(owned(session, user, asset_id))


@router.delete("/v1/me/media/{asset_id}")
def remove(asset_id: str, claims=Depends(require_claims), session=Depends(get_session)):
    user = verify_owner(claims)
    guard_account_write(session, user)
    row = owned(session, user, asset_id)
    if referenced(session, row):
        raise HTTPException(409, "Remove media from adverts before deleting")
    row.state = "deleted"
    session.commit()
    guard_account_write(session, user)
    row = owned(session, user, row.id)
    if row.digest is not None:
        delete_bytes(row, permanent=True)
        row.digest = None
    session.commit()
    return asset_data(row)


class Description(BaseModel):
    description: str = Field(max_length=500)


@router.patch("/v1/me/media/{asset_id}")
def describe(asset_id: str, body: Description, claims=Depends(require_claims), session=Depends(get_session)):
    user = verify_owner(claims)
    guard_account_write(session, user)
    row = owned(session, user, asset_id)
    if row.state != "ready":
        raise HTTPException(409, "Media is not ready")
    row.description = clean_text(body.description)
    session.commit()
    return asset_data(row)


def rendition(row, kind):
    if not row or row.state != "ready" or kind not in ("display", "thumbnail"):
        raise HTTPException(404, "Media not found")
    try:
        return Response(storage().get(key_for(row, kind)), media_type="image/jpeg")
    except FileNotFoundError:
        raise HTTPException(404, "Media not found") from None


@router.get("/v1/me/media/{asset_id}/{kind}")
def preview(asset_id: str, kind: str, claims=Depends(require_claims), session=Depends(get_session)):
    user = verify_owner(claims)
    guard_account_write(session, user)
    return rendition(owned(session, user, asset_id), kind)
