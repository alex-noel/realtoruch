"""Bounded public portal collection, configured feeds and JSON-LD page adapters.

No undocumented portal APIs, CAPTCHA bypass, proxy rotation or inferred removals.
Source-specific public HTML mapping lives in portals.py.
"""

import hashlib
import ipaddress
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from protego import Protego

from .portals import ListingUnavailable, NotRental, canonical_url, discover, parse_detail
from .schemas import RawListing
from .settings import get_settings

USER_AGENT = "Realtoruch/0.2 (rental listing aggregator)"


class SourceAccessError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def load_sources():
    path = Path(get_settings().connectors_config)
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / "config" / "sources.json"
    return json.loads(path.read_text())["sources"] if path.exists() else []


def validate_url(url, allowed_hosts):
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Source URL must use HTTPS on an explicitly allowed host")
    addresses = socket.getaddrinfo(parsed.hostname, 443)
    if any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("Private, loopback and link-local source addresses are forbidden")
    return url


class Connector:
    def __init__(self, config, *, previous_lookup=None, known_urls=()):
        self.config = config
        self.previous_lookup = previous_lookup or (lambda url: None)
        self.known_urls = known_urls
        self.last_request = 0.0
        self.robots = {}
        self.report = {
            "source": config["name"],
            "search_pages": 0,
            "discovered": 0,
            "checked": 0,
            "emitted": 0,
            "inactive": 0,
            "skipped": 0,
            "limited": False,
            "errors": [],
        }
        self.client = httpx.Client(
            timeout=25, follow_redirects=False, headers={"User-Agent": config.get("user_agent", USER_AGENT)}
        )

    def close(self):
        self.client.close()

    def fetch(self, url, *, page=False):
        validate_url(url, self.config["allowed_hosts"])
        delay = max(1.0, 60 / max(1, self.config.get("requests_per_minute", 6)))
        if page:
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in self.robots:
                status, body = self._download(origin + "/robots.txt", {}, delay, limit=512_000)
                if status != 200 or b"<html" in body.lower() or b"<!doctype" in body.lower():
                    raise SourceAccessError("Cannot verify robots policy", status)
                self.robots[origin] = Protego.parse(body.decode("utf-8", errors="replace"))
            parser = self.robots[origin]
            agent = self.client.headers["User-Agent"]
            if not parser.can_fetch(url, agent):
                raise SourceAccessError("Source robots policy disallows this page")
            rate = parser.request_rate(agent)
            delay = max(delay, parser.crawl_delay(agent) or 0, rate.seconds / rate.requests if rate else 0)
        headers = {}
        secret = os.environ.get(self.config.get("token_env", ""))
        if secret and not page:
            headers["Authorization"] = f"Bearer {secret}"
        status, body = self._download(url, headers, delay)
        if status in (404, 410) and not page:
            raise SourceAccessError("Feed unavailable", status)
        return status, body

    def _download(self, url, headers, delay, limit=5_000_000):
        time.sleep(max(0, self.last_request + delay - time.monotonic()))
        self.last_request = time.monotonic()
        # Redirects aren't followed: a trusted host cannot redirect tokens to another origin.
        with self.client.stream("GET", url, headers=headers) as response:
            if response.status_code in (404, 410):
                return response.status_code, b""
            if response.status_code in (401, 403, 429):
                raise SourceAccessError("Source denied or throttled this request", response.status_code)
            response.raise_for_status()
            if response.is_redirect:
                raise RuntimeError("Configure the final feed URL; redirects are not followed")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > limit:
                    raise ValueError("Source payload exceeds size limit")
            return response.status_code, bytes(content)

    def note_error(self, exc, stage, url=""):
        self.report["errors"].append(
            {
                "kind": type(exc).__name__,
                "stage": stage,
                "http_status": getattr(exc, "status_code", None)
                or getattr(getattr(exc, "response", None), "status_code", None),
                "url_hash": hashlib.sha256(url.encode()).hexdigest()[:16],
            }
        )

    def portal_records(self):
        if self.config.get("recheck_only") and not self.known_urls:
            return
        if not (self.config.get("search_urls") or self.config.get("listing_urls") or self.known_urls):
            raise ValueError("Portal collection requires search URLs or existing listing URLs")
        max_pages = min(10, max(1, int(self.config.get("max_pages", 2))))
        max_new = min(500, max(1, int(self.config.get("max_listings", 20))))
        max_rechecks = min(500, max(0, int(self.config.get("max_rechecks", 50))))
        checked, discovered = set(), set()

        def check(entry):
            url = entry["url"] if isinstance(entry, dict) else entry
            url = canonical_url(url)
            if url in checked:
                return None
            checked.add(url)
            self.report["checked"] += 1
            previous = entry.get("previous") if isinstance(entry, dict) else None
            previous = previous or self.previous_lookup(url)
            try:
                status, body = self.fetch(url, page=True)
                if status in (404, 410):
                    raise ListingUnavailable("Confirmed HTTP disappearance")
                record = parse_detail(
                    self.config["name"], body.decode("utf-8"), url, city=self.config.get("city", "")
                )
            except ListingUnavailable:
                if not previous:
                    self.report["skipped"] += 1
                    return None
                record = RawListing.model_validate(
                    {
                        **previous,
                        "source": self.config["name"],
                        "url": url,
                        "status": "inactive",
                        "observed_at": datetime.now(timezone.utc),
                        "is_demo": False,
                    }
                )
                self.report["inactive"] += 1
            except NotRental:
                self.report["skipped"] += 1
                return None
            except (SourceAccessError, httpx.HTTPStatusError) as exc:
                self.note_error(exc, "detail", url)
                # Stop the source on access denial/rate limiting. Other failed pages are isolated.
                if isinstance(exc, SourceAccessError):
                    raise
                return None
            except (ValueError, KeyError, TypeError, httpx.HTTPError) as exc:
                self.note_error(exc, "detail", url)
                return None
            self.report["emitted"] += 1
            return record

        for entry in list(self.known_urls)[:max_rechecks]:
            record = check(entry)
            if record:
                yield record
        new_attempts = 0
        for entry in self.config.get("listing_urls", [])[:max_new]:
            new_attempts += 1
            record = check(entry)
            if record:
                yield record
        if len(self.config.get("listing_urls", [])) > max_new:
            self.report["limited"] = True
        visited = set()
        for seed in self.config.get("search_urls", [])[:10]:
            url = seed
            while url and self.report["search_pages"] < max_pages and new_attempts < max_new:
                if url in visited:
                    self.note_error(ValueError("Pagination loop"), "discovery", url)
                    break
                visited.add(url)
                try:
                    status, body = self.fetch(url, page=True)
                    if status != 200:
                        raise SourceAccessError("Search unavailable", status)
                    page = discover(self.config["name"], body.decode("utf-8"), url)
                except (ValueError, KeyError, TypeError, httpx.HTTPError, SourceAccessError) as exc:
                    self.note_error(exc, "discovery", url)
                    raise
                self.report["search_pages"] += 1
                discovered.update(page.urls)
                self.report["discovered"] = len(discovered)
                for detail_url in page.urls:
                    if detail_url in checked:
                        continue
                    if new_attempts >= max_new:
                        self.report["limited"] = True
                        break
                    new_attempts += 1
                    record = check(detail_url)
                    if record:
                        yield record
                url = page.next_url
            if url:
                self.report["limited"] = True

    def records(self):
        if not self.config.get("enabled"):
            return
        if self.config["mode"] == "portal":
            yield from self.portal_records()
        elif self.config["mode"] == "feed":
            url = self.config["feed_url"]
            visited = set()
            while url:
                if url in visited or len(visited) >= 100:
                    raise ValueError("Feed pagination loop or 100-page limit reached")
                visited.add(url)
                _, content = self.fetch(url)
                payload = json.loads(content)
                items = payload if isinstance(payload, list) else payload["items"]
                for item in items:
                    yield RawListing.model_validate({**item, "source": self.config["name"], "is_demo": False})
                url = payload.get("next_url") if isinstance(payload, dict) else None
        elif self.config["mode"] == "jsonld":
            # A page disappearance can be emitted only when a previous valid record exists.
            for entry in self.config.get("listing_urls", []):
                url = entry["url"] if isinstance(entry, dict) else entry
                status, content = self.fetch(url, page=True)
                if status in (404, 410):
                    if isinstance(entry, dict) and entry.get("previous"):
                        yield RawListing.model_validate(
                            {
                                **entry["previous"],
                                "source": self.config["name"],
                                "url": url,
                                "status": "inactive",
                                "observed_at": datetime.now(timezone.utc),
                                "is_demo": False,
                            }
                        )
                    continue
                yield parse_jsonld(content.decode(), self.config["name"], url)
        else:
            raise ValueError("Supported connector modes are portal, feed and jsonld")


def parse_jsonld(html, source, url):
    soup = BeautifulSoup(html, "html.parser")
    nodes = []

    def collect(value):
        if isinstance(value, list):
            for child in value:
                collect(child)
        elif isinstance(value, dict):
            nodes.append(value)
            if "@graph" in value:
                collect(value["@graph"])

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            collect(json.loads(script.string or script.get_text()))
        except json.JSONDecodeError:
            continue
    listing = next(
        (n for n in nodes if n.get("@type") in ("Apartment", "House", "Residence", "RealEstateListing")), None
    )
    if not listing:
        raise ValueError("No supported JSON-LD listing; an explicit source mapper is needed")
    property_data = listing.get("mainEntity", listing)
    offer = listing.get("offers", property_data.get("offers", {}))
    if isinstance(offer, list):
        offer = offer[0]
    if offer.get("priceCurrency") != "PLN":
        raise ValueError("Only explicitly PLN-denominated rental offers are accepted")
    # Do not mistake a sale price for monthly rent.
    business = str(offer.get("businessFunction", ""))
    unit = str(offer.get("priceSpecification", {}).get("unitText", "")).lower()
    if "LeaseOut" not in business and unit not in ("month", "monthly", "miesiąc", "miesiac"):
        raise ValueError("JSON-LD does not explicitly identify a rental offer")
    address, geo = property_data.get("address", {}), property_data.get("geo", {})
    image = listing.get("image", property_data.get("image", []))
    if isinstance(image, str):
        image = [image]
    image = [i.get("url") if isinstance(i, dict) else i for i in image]
    floor_size = property_data.get("floorSize", {})
    return RawListing(
        source=source,
        external_id=str(listing.get("identifier") or url),
        url=url,
        title=listing["name"],
        description=listing.get("description", ""),
        city=address["addressLocality"],
        region=address.get("addressRegion", ""),
        address=address.get("streetAddress", ""),
        lat=geo.get("latitude"),
        lon=geo.get("longitude"),
        area_m2=floor_size["value"],
        rooms=property_data["numberOfRooms"],
        rent_pln=int(float(offer["price"])),
        images=image,
        status="inactive"
        if offer.get("availability", "").endswith(("SoldOut", "Discontinued"))
        else "active",
    )
