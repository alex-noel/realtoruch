"""Confirmed email opt-in and durable, deduplicated rental email delivery."""

import hashlib
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from .db import get_session
from .models import EmailDelivery, EmailSubscription, Favorite, Listing, Notification, now
from .push import payload_for
from .security import require_claims, require_user
from .settings import get_settings

router = APIRouter(tags=["Email notifications"])


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def preference(item):
    return {
        "configured": get_settings().email_delivery_mode != "disabled",
        "enabled": bool(item and item.enabled),
        "verified": bool(item and item.verified_at),
        "email": item.email if item else None,
        "confirmation_pending": bool(
            item
            and item.verification_hash
            and item.verification_expires_at
            and item.verification_expires_at > now()
        ),
    }


@router.get("/v1/me/email-notifications")
def email_status(user_id=Depends(require_user), session=Depends(get_session)):
    return preference(session.get(EmailSubscription, user_id))


class EmailChoice(BaseModel):
    enabled: bool


@router.put("/v1/me/email-notifications")
def email_choice(body: EmailChoice, claims=Depends(require_claims), session=Depends(get_session)):
    user_id = claims["sub"]
    item = session.get(EmailSubscription, user_id)
    if not body.enabled:
        if item:
            item.enabled = False
            item.verification_hash = None
            session.commit()
        return preference(item)
    if get_settings().email_delivery_mode == "disabled":
        raise HTTPException(503, "Email delivery is not configured. Your notification inbox still works.")
    email = claims.get("email")
    if not email:
        raise HTTPException(401, "Sign in again to enable email notifications.")
    if item and item.email == email and item.verified_at:
        item.enabled = True
        session.commit()
        return preference(item)
    if item and item.verification_hash and item.requested_at > now() - timedelta(seconds=60):
        return {**preference(item), "confirmation_pending": True}
    if not item:
        item = EmailSubscription(user_id=user_id, email=email, unsubscribe_token=secrets.token_urlsafe(32))
        session.add(item)
    token = secrets.token_urlsafe(32)
    item.email, item.enabled, item.verified_at = email, False, None
    item.verification_hash, item.verification_expires_at = digest(token), now() + timedelta(hours=1)
    item.requested_at = now()
    session.flush()
    session.add(EmailDelivery(user_id=user_id, confirmation_token=token))
    session.commit()
    return {**preference(item), "confirmation_pending": True}


class EmailToken(BaseModel):
    token: str = Field(min_length=32, max_length=128)


@router.post("/v1/notifications/email/confirm")
def confirm_email(body: EmailToken, session=Depends(get_session)):
    item = session.scalar(
        select(EmailSubscription)
        .where(EmailSubscription.verification_hash == digest(body.token))
        .with_for_update()
    )
    if not item or not item.verification_expires_at or item.verification_expires_at < now():
        raise HTTPException(
            400, "This confirmation link expired or was already used. Sign in to check your email settings."
        )
    item.verified_at, item.enabled, item.verification_hash = now(), True, None
    session.commit()
    return {
        "message": "Email alerts are enabled. New matches and lower prices on liked homes will arrive by email."
    }


@router.post("/v1/notifications/email/unsubscribe")
def unsubscribe_email(body: EmailToken, session=Depends(get_session)):
    item = session.scalar(select(EmailSubscription).where(EmailSubscription.unsubscribe_token == body.token))
    if item:
        item.enabled, item.verification_hash = False, None
        session.commit()
    return {
        "message": "Email alerts are disabled. Your saved homes and in-app notifications are still available."
    }


def message_for(delivery, subscription, item):
    settings = get_settings()
    base = settings.public_web_url.rstrip("/")
    message = EmailMessage()
    message["From"], message["To"] = settings.email_from, subscription.email
    message["Message-ID"] = f"<{delivery.id}@realtoruch.notifications>"
    message["Date"] = format_datetime(now())
    unsubscribe = f"{base}/#unsubscribe_email={subscription.unsubscribe_token}"
    if delivery.confirmation_token:
        message["Subject"] = "Confirm your Realtoruch email alerts"
        content = (
            "Confirm email alerts for new rental matches and lower prices on homes you like:\n\n"
            f"{base}/#confirm_email={delivery.confirmation_token}\n\n"
            "This link expires in one hour. If you did not request this, ignore this email.\n"
        )
    else:
        payload = payload_for(item)
        message["Subject"] = payload["title"]
        content = f"{payload['body']}\n\nView home: {base}/?listing={item.listing_id}\n"
    message.set_content(content + f"\nStop email alerts: {unsubscribe}\n")
    return message


def send_email(message, delivery_id):
    settings = get_settings()
    if settings.email_delivery_mode == "file" and settings.environment != "production":
        directory = Path(settings.email_preview_directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / (delivery_id + ".eml")
        try:
            with path.open("xb") as output:
                path.chmod(0o600)
                output.write(message.as_bytes())
        except FileExistsError:
            pass  # Stable delivery IDs make local retries idempotent.
        return
    if settings.email_delivery_mode != "smtp" or not settings.smtp_host:
        raise RuntimeError("Email delivery is not configured")
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=10)
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    with connection:
        if settings.smtp_security == "starttls":
            connection.starttls(context=context)
        if settings.smtp_username:
            connection.login(settings.smtp_username, settings.smtp_password)
        connection.send_message(message)


def dispatch_email(session_factory, *, limit=50, sender=send_email):
    count = 0
    for _ in range(limit):
        with session_factory.begin() as session:
            delivery = session.scalar(
                select(EmailDelivery)
                .where(
                    EmailDelivery.status.in_(["pending", "retry"]),
                    EmailDelivery.next_attempt_at <= now(),
                    or_(EmailDelivery.lease_until.is_(None), EmailDelivery.lease_until < now()),
                )
                .order_by(EmailDelivery.next_attempt_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if not delivery:
                break
            subscription = session.get(EmailSubscription, delivery.user_id)
            item = session.get(Notification, delivery.notification_id) if delivery.notification_id else None
            valid = bool(subscription)
            if delivery.confirmation_token:
                valid = (
                    valid
                    and subscription.verification_hash == digest(delivery.confirmation_token)
                    and subscription.verification_expires_at > now()
                )
            else:
                home = session.get(Listing, item.listing_id)
                valid = (
                    valid
                    and subscription.enabled
                    and subscription.verified_at
                    and not item.read_at
                    and home.status == "active"
                    and home.rent_pln == item.rent_pln
                    and (item.kind != "price_drop" or session.get(Favorite, (item.user_id, home.id)))
                    and (item.kind != "new_match" or item.search_id)
                )
            if not valid:
                delivery.status, delivery.confirmation_token = "cancelled", None
                continue
            message = message_for(delivery, subscription, item)
            delivery.lease_until, delivery.attempts = now() + timedelta(seconds=60), delivery.attempts + 1
            delivery_id = delivery.id
        error = None
        try:
            sender(message, delivery_id)
        except Exception as exc:
            error = type(exc).__name__  # No recipient, credentials or confirmation token in logs.
        with session_factory.begin() as session:
            delivery = session.get(EmailDelivery, delivery_id)
            delivery.lease_until, delivery.last_error = None, error
            if error:
                delivery.status = "failed" if delivery.attempts >= 8 else "retry"
                delivery.next_attempt_at = now() + timedelta(seconds=min(3600, 30 * 2**delivery.attempts))
                if delivery.status == "failed":
                    delivery.confirmation_token = None
            else:
                delivery.status, delivery.delivered_at, delivery.confirmation_token = "sent", now(), None
        count += 1
    return count
