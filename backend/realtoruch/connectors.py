"""Explicitly configured feeds and conservative JSON-LD page adapters.

No undocumented portal APIs, CAPTCHA bypass, proxy rotation or inferred removals.
Portal-specific contracted feed formats should map to RawListing here.
"""

import ipaddress
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from .schemas import RawListing
from .settings import get_settings

USER_AGENT = "Realtoruch/0.1 (+https://example.invalid/realtoruch; configured-feed-client)"


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
    def __init__(self, config):
        self.config = config
        self.last_request = 0.0
        self.robots = {}
        self.client = httpx.Client(
            timeout=25, follow_redirects=False, headers={"User-Agent": config.get("user_agent", USER_AGENT)}
        )

    def close(self):
        self.client.close()

    def fetch(self, url, *, page=False):
        validate_url(url, self.config["allowed_hosts"])
        delay = max(1.0, 60 / max(1, self.config.get("requests_per_minute", 6)))
        time.sleep(max(0, self.last_request + delay - time.monotonic()))
        if page:
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in self.robots:
                robots_response = self.client.get(origin + "/robots.txt")
                if robots_response.status_code != 200:
                    raise RuntimeError("Cannot verify robots policy; page fetching stopped")
                parser = RobotFileParser()
                parser.parse(robots_response.text.splitlines())
                self.robots[origin] = parser
            parser = self.robots[origin]
            if not parser.can_fetch(self.client.headers["User-Agent"], url):
                raise RuntimeError("Source robots policy disallows this page")
            crawl_delay = (
                parser.crawl_delay(self.client.headers["User-Agent"]) or parser.crawl_delay("*") or 0
            )
            time.sleep(max(0, self.last_request + crawl_delay - time.monotonic()))
        self.last_request = time.monotonic()
        headers = {}
        secret = os.environ.get(self.config.get("token_env", ""))
        if secret and not page:
            headers["Authorization"] = f"Bearer {secret}"
        # Redirects aren't followed: a trusted host cannot redirect tokens to another origin.
        with self.client.stream("GET", url, headers=headers) as response:
            if response.status_code in (404, 410) and page:
                return response.status_code, b""
            response.raise_for_status()
            if response.is_redirect:
                raise RuntimeError("Configure the final feed URL; redirects are not followed")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 5_000_000:
                    raise ValueError("Source payload exceeds 5 MB")
            return response.status_code, bytes(content)

    def records(self):
        if not self.config.get("enabled"):
            return
        if self.config["mode"] == "feed":
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
            raise ValueError("Supported connector modes are feed and jsonld")


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
