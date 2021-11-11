"""Private proof that a validator describes an existing, parsed listing payload."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from urllib.parse import urlsplit

from .normalization import fold
from .schemas import RawListing


def url_key(url):
    return hashlib.sha256(url.encode()).hexdigest()


def payload_key(data):
    payload = {key: value for key, value in data.items() if key not in ("observed_at", "_fetch")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def http_date(value):
    if not value or len(value) > 128:
        return None
    try:
        date = parsedate_to_datetime(value)
        if date is not None:
            return date.replace(tzinfo=date.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        pass
    return None


def retry_deadline(value, received_at):
    if not value or len(value) > 128:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]+", value):
        digits = value.lstrip("0") or "0"
        maximum = int((datetime.max - received_at).total_seconds()) - 1
        return received_at + timedelta(seconds=min(int(digits), maximum))
    date = http_date(value)
    return max(received_at, date.replace(tzinfo=None)) if date else None


def etag_header(value):
    # A validator is replayed verbatim, so reject controls, lists and tags that
    # resemble a phone number. Never persist other response/request headers.
    if (value and len(value) <= 256 and re.fullmatch(r'(?:W/)?"[!#-~]*"', value)
            and not re.search(r"(?<!\d)(?:\d[ .-]?){9}(?!\d)", value)):
        return value
    return None


def last_modified_header(value):
    date = http_date(value)
    return format_datetime(date, usegmt=True) if date else None


_VARIANT_HEADERS = ("accept", "accept-encoding", "accept-language", "user-agent")


def request_variant(url, headers, mode):
    parsed = urlsplit(url)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        return None
    if any(header in headers for header in ("authorization", "proxy-authorization", "cookie")):
        return None
    variant = [mode, *(headers.get(header, "") for header in _VARIANT_HEADERS)]
    return hashlib.sha256(json.dumps(variant).encode()).hexdigest()


def permits_cache(headers):
    vary = {name.strip().lower() for name in headers.get("vary", "").split(",") if name.strip()}
    cache_control = {name.strip().lower() for name in headers.get("cache-control", "").split(",")}
    return not (vary - set(_VARIANT_HEADERS) or "no-store" in cache_control)


@dataclass(frozen=True)
class Validators:
    variant: str
    validated_at: str
    etag: str | None
    last_modified: str | None

    @classmethod
    def from_headers(cls, headers, variant, validated_at):
        if not variant or not permits_cache(headers):
            return None
        etag = etag_header(headers.get("etag"))
        modified = last_modified_header(headers.get("last-modified"))
        return cls(variant, validated_at.isoformat(), etag, modified) if etag or modified else None

    def for_payload(self, data):
        return {**asdict(self), "url_hash": url_key(data["url"]), "payload_hash": payload_key(data)}


@dataclass(frozen=True)
class CachedPage:
    data: dict
    state: dict
    raw: RawListing

    @classmethod
    def read(cls, data, state, source, url, variant, city=""):
        if not isinstance(data, dict) or not isinstance(state, dict) or not variant:
            return None
        if (data.get("source") != source or data.get("url") != url or data.get("status") != "active"
                or data.get("is_demo") or "phone" in data or state.get("url_hash") != url_key(url)
                or state.get("variant") != variant or state.get("payload_hash") != payload_key(data)):
            return None
        try:
            raw = RawListing.model_validate(data)
            if str(raw.url) != url or (city and fold(raw.city) != fold(city)):
                return None
            if datetime.fromisoformat(data["observed_at"]) != raw.observed_at:
                return None
            validated_at = datetime.fromisoformat(state["validated_at"])
            if validated_at.tzinfo is not None or validated_at > raw.observed_at:
                return None
        except (KeyError, ValueError, TypeError):
            return None
        etag, modified = state.get("etag"), state.get("last_modified")
        if ((etag is not None and (not isinstance(etag, str) or etag_header(etag) != etag))
                or (modified is not None and (not isinstance(modified, str)
                                              or last_modified_header(modified) != modified))
                or not (etag or modified)):
            return None
        return cls(data, state, raw)

    def headers(self):
        return {header: self.state[key] for header, key in (
            ("If-None-Match", "etag"), ("If-Modified-Since", "last_modified")
        ) if self.state.get(key)}

    def accepts_304(self, headers):
        if not permits_cache(headers):
            return False
        if self.state.get("etag") and "etag" in headers:
            received = etag_header(headers["etag"])
            return bool(received and received.removeprefix("W/") == self.state["etag"].removeprefix("W/"))
        if not self.state.get("etag") and self.state.get("last_modified") and "last-modified" in headers:
            return last_modified_header(headers["last-modified"]) == self.state["last_modified"]
        return True

    def matches(self, data, state):
        return (isinstance(data, dict) and state == self.state
                and data.get("url") == self.data["url"] and data.get("source") == self.data["source"]
                and data.get("external_id") == self.data["external_id"]
                and payload_key(data) == self.state["payload_hash"])
