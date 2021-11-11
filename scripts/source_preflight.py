#!/usr/bin/env python3
"""Offline-first OLX access and sample-mapping preflight; never enables collection."""
import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
from protego import Protego
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from realtoruch.portals import discover, parse_detail  # noqa: E402
from realtoruch.schemas import RawListing  # noqa: E402

MAX_BYTES = 5_000_000
MAX_REQUESTS = 3
CITY = "Kraków"


def safe_url(url):
    """Return a display URL with all query and fragment values removed."""
    if not url:
        return ""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "[redacted]" if parsed.query else "", ""))


def validate_url(url, hosts, *, resolve=False):
    parsed = urlparse(url or "")
    if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.query):
        raise ValueError("URL must be query-free HTTPS on an exact approved host")
    # Reject local/private destinations before the HTTP client can connect.
    if resolve:
        import ipaddress
        for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
            if not ipaddress.ip_address(result[4][0]).is_global:
                raise ValueError("Source host resolves to a non-public address")
    return url


def load_olx(config_path):
    payload = json.loads(Path(config_path).read_text())
    return next((source for source in payload.get("sources", []) if source.get("name") == "olx"), None)


def validate_config(config):
    errors, missing = [], []
    if not config:
        return errors, ["OLX source configuration"]
    if config.get("city") != CITY:
        errors.append("city must be exactly Kraków")
    if not isinstance(config.get("allowed_hosts"), list) or not config["allowed_hosts"]:
        errors.append("allowed_hosts must be an explicit non-empty list")
    mode = config.get("mode")
    if mode not in ("feed", "portal"):
        errors.append("mode must be feed or portal")
    for url in ([config.get("feed_url")] if mode == "feed" and config.get("feed_url") else []) + (config.get("search_urls", []) if mode == "portal" else []):
        try:
            validate_url(url, config.get("allowed_hosts", []))
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    token_env = config.get("token_env")
    if mode == "feed" and token_env and not os.environ.get(token_env):
        missing.append("feed token environment variable: " + token_env)
    if mode == "feed" and not config.get("feed_url"):
        missing.append("approved feed URL")
    if mode == "portal" and not config.get("search_urls"):
        missing.append("approved public search URL")
    if config.get("requests_per_minute", 0) < 1:
        errors.append("requests_per_minute must be at least 1")
    if config.get("max_pages", 1) < 1:
        errors.append("max_pages must be positive")
    return errors, missing


def map_feed(payload, source="olx"):
    items = payload if isinstance(payload, list) else payload["items"]
    if not isinstance(items, list):
        raise ValueError("feed items must be a list")
    return [RawListing.model_validate({**item, "source": source, "is_demo": False}) for item in items]


def map_public_detail(html, url, city=CITY):
    return parse_detail("olx", html, url, city=city)


def bounded_get(client, url, headers, max_bytes=MAX_BYTES):
    # No redirects: credentials cannot be forwarded to a different origin.
    with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
        if response.status_code in (401, 403, 429):
            raise PermissionError("access denied or throttled (HTTP %d)" % response.status_code)
        if response.is_redirect:
            raise PermissionError("redirect refused; configure the final approved URL")
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ValueError("response exceeds byte budget")
        return response.status_code, bytes(body), response.headers.get("content-type", "")


def preflight(config, *, network=False, client_factory=httpx.Client):
    errors, missing = validate_config(config)
    report = {"source": "olx", "state": "not_configured", "collection_enabled": False,
              "mode": config.get("mode") if config else None, "city": config.get("city") if config else None,
              "requests_made": 0, "evidence": [], "missing_evidence": missing, "errors": errors,
              "sample": None, "checklist": ["Obtain documented permission or an authorized provider feed.",
              "Supply exact HTTPS host, Kraków scope, field mapping, pagination and removal semantics.",
              "Run this preflight with --network only after access is supplied.",
              "Have T29 independently verify a successful fetch and parsed sample.",
              "Keep automatic OLX collection disabled until that review is complete.",
              "For a one-off public page, use scripts/import_html.py as a separate manual path."]}
    if not config:
        return report
    if errors:
        return report
    endpoint_present = bool(config.get("feed_url") if config.get("mode") == "feed" else config.get("search_urls"))
    configured = bool(endpoint_present and not missing)
    if not configured:
        report["state"] = "ready_offline" if not missing else "not_configured"
        return report
    report["state"] = "ready_offline"
    if not network:
        return report
    if config.get("mode") == "feed":
        sequence = [("robots", config["feed_url"].split("/", 3)[0] + "//" + urlparse(config["feed_url"]).netloc + "/robots.txt"),
                    ("feed", config["feed_url"])]
    else:
        search = config["search_urls"][0]
        sequence = [("robots", urlparse(search)._replace(path="/robots.txt", query="").geturl()), ("search", search)]
    headers = {"User-Agent": "Realtoruch/0.2 (source preflight)"}
    token = os.environ.get(config.get("token_env", "")) if config.get("mode") == "feed" else None
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with client_factory(timeout=10, follow_redirects=False, headers={"User-Agent": headers["User-Agent"]}) as client:
            fetched = {}
            previous_request = None
            delay = 60 / max(1, int(config.get("requests_per_minute", 6)))
            for kind, url in sequence:
                validate_url(url, config["allowed_hosts"], resolve=True)
                request_headers = headers if kind == "feed" else {"User-Agent": headers["User-Agent"]}
                if previous_request is not None:
                    time.sleep(max(0, delay - (time.monotonic() - previous_request)))
                previous_request = time.monotonic()
                report["requests_made"] += 1
                status, body, content_type = bounded_get(client, url, request_headers)
                if kind == "robots":
                    # Check the next requested path against the parsed policy; fail closed.
                    parser = Protego.parse(body.decode("utf-8", "replace"))
                    next_url = sequence[1][1]
                    if not parser.can_fetch(next_url, headers["User-Agent"]):
                        raise PermissionError("robots policy disallows automated access")
                else:
                    fetched[kind] = (url, body, content_type)
            if config.get("mode") == "feed":
                payload = json.loads(fetched["feed"][1])
                records = map_feed(payload)
                detail = next((item.url for item in records), None)
            else:
                page_url, body, _ = fetched["search"]
                result = discover("olx", body.decode("utf-8", "replace"), page_url)
                detail = result.urls[0] if result.urls else None
                records = []
            if detail:
                validate_url(str(detail), config["allowed_hosts"], resolve=True)
                time.sleep(max(0, delay - (time.monotonic() - previous_request)))
                report["requests_made"] += 1
                _, detail_body, _ = bounded_get(client, str(detail), {"User-Agent": headers["User-Agent"]})
                if config.get("mode") == "feed":
                    # Feed item itself is the parsed detail evidence; bounded detail fetch verifies URL reachability.
                    sample = records[0]
                else:
                    sample = map_public_detail(detail_body.decode("utf-8", "replace"), str(detail), CITY)
                report["sample"] = {"source": sample.source, "external_id": sample.external_id, "city": sample.city,
                                    "required_fields_valid": True}
                report["state"] = "live_sample_verified"
                report["evidence"].append("robots, discovery/feed and one detail sample fetched and parsed")
            else:
                report["errors"].append("No detail URL available within one discovery page")
                report["state"] = "unsupported_payload"
    except PermissionError as exc:
        report["state"] = "blocked_access"
        report["errors"].append(str(exc))
    except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        report["state"] = "unsupported_payload"
        # Exception text may contain a URL, provider payload, or secret-bearing input.
        report["errors"].append(type(exc).__name__ + ": sample fetch or mapping failed")
    # Never include raw URLs or secrets in reports.
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "config/sources.json"))
    parser.add_argument("--network", action="store_true", help="make at most three explicitly authorized requests")
    args = parser.parse_args()
    config = load_olx(args.config)
    print(json.dumps(preflight(config, network=args.network), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
