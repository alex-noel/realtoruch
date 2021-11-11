"""Opt-in browser/Expo push with a durable retry queue and bounded destinations."""

import base64
import fnmatch
import ipaddress
import json
import re
import socket
from datetime import timedelta
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select

from .models import Favorite, Listing, Notification, PushDelivery, PushSubscription, now
from .settings import get_settings


class PushFailure(Exception):
    def __init__(self, code, *, gone=False, permanent=False):
        self.code, self.gone, self.permanent = code, gone, permanent
        super().__init__(code)


def validate_endpoint(endpoint, *, resolve=False):
    parsed = urlparse(endpoint)
    allowed = get_settings().web_push_allowed_hosts.split(",")
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.fragment
        or not any(fnmatch.fnmatchcase(parsed.hostname, host.strip()) for host in allowed)
    ):
        raise ValueError("Unsupported browser push service")
    if resolve and any(
        not ipaddress.ip_address(record[4][0]).is_global
        for record in socket.getaddrinfo(parsed.hostname, 443)
    ):
        raise ValueError("Push service must use public addresses")


class PushBody(BaseModel):
    kind: str = Field(pattern=r"^(web|expo)$")
    endpoint: str = Field(default="", max_length=3000)
    keys: dict[str, str] = Field(default_factory=dict, max_length=2)
    token: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def subscription_format(self):
        if self.kind == "web":
            validate_endpoint(self.endpoint)
            try:
                for name, size in (("p256dh", 65), ("auth", 16)):
                    value = self.keys[name]
                    if len(value) > 120 or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
                        raise ValueError()
                    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
                    if len(decoded) != size:
                        raise ValueError()
                from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, EllipticCurvePublicKey

                key = self.keys["p256dh"]
                EllipticCurvePublicKey.from_encoded_point(
                    SECP256R1(), base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
                )
            except (KeyError, ValueError):
                raise ValueError("Invalid browser push keys") from None
        elif not re.fullmatch(r"(Expo|Exponent)PushToken\[[A-Za-z0-9_-]+\]", self.token):
            raise ValueError("Invalid Expo push token")
        return self


def payload_for(item):
    heading = (
        "Price dropped on a saved home" if item.kind == "price_drop" else "A new home matches your search"
    )
    price = (
        f"{item.previous_rent_pln:,} → {item.rent_pln:,} PLN"
        if item.previous_rent_pln
        else f"{item.rent_pln:,} PLN / month"
    )
    return {
        "title": heading,
        "body": f"{item.title[:140]} · {price}",
        "notification_id": item.id,
        "listing_id": item.listing_id,
        "url": "/?listing=" + item.listing_id,
    }


def send_push(subscription, payload):
    settings = get_settings()
    if subscription.kind == "web":
        if not (settings.vapid_private_key and settings.vapid_subject):
            raise PushFailure("web_push_not_configured")
        try:
            validate_endpoint(subscription.data["endpoint"], resolve=True)
        except ValueError:
            raise PushFailure("invalid_push_endpoint", permanent=True) from None
        import requests
        from pywebpush import WebPushException, webpush

        class NoRedirectSession(requests.Session):
            def request(self, *args, **kwargs):
                kwargs["allow_redirects"] = False
                return super().request(*args, **kwargs)

        try:
            with NoRedirectSession() as transport:
                response = webpush(
                    subscription.data,
                    json.dumps(payload),
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject},
                    ttl=3600,
                    timeout=10,
                    requests_session=transport,
                )
                if not 200 <= response.status_code < 300:
                    raise PushFailure("web_push_rejected", permanent=300 <= response.status_code < 400)
        except WebPushException as exc:
            code = getattr(exc, "status_code", None) or (
                exc.response.status_code if exc.response is not None else 0
            )
            raise PushFailure(
                f"web_push_{code}", gone=code in (404, 410), permanent=code in (400, 401, 403, 413)
            ) from None
        except requests.RequestException:
            raise PushFailure("web_push_network") from None
        return None
    if not settings.expo_push_enabled:
        raise PushFailure("expo_push_not_configured")
    headers = (
        {"Authorization": "Bearer " + settings.expo_push_access_token}
        if settings.expo_push_access_token
        else {}
    )
    response = httpx.post(
        "https://exp.host/--/api/v2/push/send",
        headers=headers,
        timeout=10,
        json={
            "to": subscription.data["token"],
            "title": payload["title"],
            "body": payload["body"],
            "data": {"listing_id": payload["listing_id"], "notification_id": payload["notification_id"]},
            "sound": "default",
            "channelId": "rentals",
            "ttl": 3600,
            "collapseId": payload["notification_id"],
        },
    )
    response.raise_for_status()
    result = response.json()["data"]
    if result.get("status") != "ok":
        code = result.get("details", {}).get("error", "expo_push_rejected")
        raise PushFailure(
            code,
            gone=code == "DeviceNotRegistered",
            permanent=code in ("InvalidCredentials", "MessageTooBig"),
        )
    return result["id"]


def check_receipt(receipt_id):
    settings = get_settings()
    headers = (
        {"Authorization": "Bearer " + settings.expo_push_access_token}
        if settings.expo_push_access_token
        else {}
    )
    response = httpx.post(
        "https://exp.host/--/api/v2/push/getReceipts", headers=headers, json={"ids": [receipt_id]}, timeout=10
    )
    response.raise_for_status()
    receipt = response.json()["data"].get(receipt_id)
    if not receipt:
        return False
    if receipt.get("status") != "ok":
        code = receipt.get("details", {}).get("error", "expo_receipt_error")
        raise PushFailure(
            code,
            gone=code == "DeviceNotRegistered",
            permanent=code in ("InvalidCredentials", "MessageTooBig"),
        )
    return True


def dispatch_push(session_factory, *, limit=50, sender=send_push, receipt_checker=check_receipt):
    """Lease in SQL, send outside the transaction, then acknowledge. Providers are at-least-once."""
    count = 0
    for _ in range(limit):
        with session_factory.begin() as session:
            delivery = session.scalar(
                select(PushDelivery)
                .where(
                    PushDelivery.status.in_(["pending", "retry", "receipt"]),
                    PushDelivery.next_attempt_at <= now(),
                    or_(PushDelivery.lease_until.is_(None), PushDelivery.lease_until < now()),
                )
                .order_by(PushDelivery.next_attempt_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if not delivery:
                break
            item = session.get(Notification, delivery.notification_id)
            subscription = session.get(PushSubscription, delivery.subscription_id)
            home = session.get(Listing, item.listing_id)
            if (
                not subscription.active
                or subscription.user_id != item.user_id
                or item.read_at
                or home.status != "active"
                or home.rent_pln != item.rent_pln
                or (item.kind == "price_drop" and not session.get(Favorite, (item.user_id, home.id)))
                or (item.kind == "new_match" and not item.search_id)
            ):
                delivery.status = "cancelled"
                continue
            delivery.lease_until = now() + timedelta(seconds=60)
            delivery.attempts += 1
            delivery_id, receipt_id = delivery.id, delivery.receipt_id
            payload = payload_for(item)
            session.expunge(subscription)
        error, accepted, ticket = None, False, receipt_id
        try:
            if receipt_id:
                accepted = receipt_checker(receipt_id)
            else:
                ticket = sender(subscription, payload)
                accepted = not ticket
        except PushFailure as exc:
            error = exc
        except Exception as exc:
            # Error classes only: provider exceptions can contain private push tokens.
            error = PushFailure(type(exc).__name__)
        with session_factory.begin() as session:
            delivery = session.get(PushDelivery, delivery_id)
            delivery.lease_until = None
            if error:
                delivery.last_error = error.code[:100]
                delivery.status = (
                    "failed" if error.permanent or error.gone or delivery.attempts >= 8 else "retry"
                )
                if error.gone:
                    session.get(PushSubscription, delivery.subscription_id).active = False
                delivery.next_attempt_at = now() + timedelta(seconds=min(3600, 30 * 2**delivery.attempts))
            elif accepted:
                delivery.status, delivery.delivered_at, delivery.last_error = "sent", now(), None
            else:
                delivery.receipt_id = ticket
                delivery.status = "receipt" if delivery.attempts < 20 else "failed"
                delivery.last_error = None if delivery.attempts < 20 else "receipt_timeout"
                delivery.next_attempt_at = now() + timedelta(minutes=2)
        count += 1
    return count
