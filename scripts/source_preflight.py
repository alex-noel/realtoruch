#!/usr/bin/env python3
"""Offline-first OLX access and sample-mapping preflight; never enables collection."""
import argparse
import ipaddress
import json
import math
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
from realtoruch.portals import discover, parse_detail
from realtoruch.schemas import RawListing

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
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise ValueError("Source host must be public")
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise ValueError("Source host must be public")
    if resolve:
        for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
            if not ipaddress.ip_address(result[4][0]).is_global:
                raise ValueError("Source host resolves to a non-public address")
    return url


def load_olx(config_path):
    payload = json.loads(Path(config_path).read_text())
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return next((source for source in sources if isinstance(source, dict) and source.get("name") == "olx"), None)


def validate_config(config):
    errors, missing = [], []
    if not config:
        return errors, ["OLX source configuration"]
    if not isinstance(config, dict):
        return ["OLX source configuration must be an object"], []
    if config.get("city") != CITY:
        errors.append("city must be exactly Kraków")
    if not isinstance(config.get("enabled"), bool):
        errors.append("enabled must be a boolean")
    if (not isinstance(config.get("allowed_hosts"), list) or not config["allowed_hosts"]
            or any(not isinstance(host, str) or not host for host in config.get("allowed_hosts", []))):
        errors.append("allowed_hosts must be an explicit non-empty list")
    mode = config.get("mode")
    if mode not in ("feed", "portal"):
        errors.append("mode must be feed or portal")
    search_urls = config.get("search_urls", [])
    if mode == "portal" and not isinstance(search_urls, list):
        errors.append("search_urls must be a list")
        search_urls = []
    urls = ([config.get("feed_url")] if mode == "feed" and config.get("feed_url") else [])
    urls += (search_urls if mode == "portal" and isinstance(search_urls, list) else [])
    hosts = config.get("allowed_hosts")
    if not isinstance(hosts, list):
        hosts = []
    for url in urls:
        if not isinstance(url, str):
            errors.append("source URLs must be strings")
            continue
        try:
            validate_url(url, hosts)
        except (ValueError, OSError):
            errors.append("source URL is invalid or outside exact approved HTTPS hosts")
    token_env = config.get("token_env")
    if token_env is not None and not isinstance(token_env, str):
        errors.append("token_env must be a string")
        token_env = None
    if mode == "feed" and token_env and not os.environ.get(token_env):
        missing.append("feed token environment variable: " + token_env)
    if mode == "feed" and not config.get("feed_url"):
        missing.append("approved feed URL")
    if mode == "portal" and not config.get("search_urls"):
        missing.append("approved public search URL")
    rpm = config.get("requests_per_minute", 0)
    if not isinstance(rpm, (int, float)) or isinstance(rpm, bool) or not math.isfinite(rpm) or rpm < 1:
        errors.append("requests_per_minute must be at least 1")
    pages = config.get("max_pages", 1)
    if not isinstance(pages, int) or isinstance(pages, bool) or pages < 1:
        errors.append("max_pages must be positive")
    return errors, missing


def map_feed(payload, source="olx"):
    items = payload if isinstance(payload, list) else payload["items"]
    if not isinstance(items, list):
        raise TypeError("feed items must be a list")
    return [RawListing.model_validate({**item, "source": source, "is_demo": False}) for item in items]


def map_public_detail(html, url, city=CITY):
    return parse_detail("olx", html, url, city=city)


def bounded_get(client, url, headers, max_bytes=MAX_BYTES):
    # No redirects: credentials cannot be forwarded to a different origin.
    with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
        if response.status_code in (401, 403, 429):
            raise PermissionError(f"access denied or throttled (HTTP {response.status_code})")
        if response.is_redirect:
            raise PermissionError("redirect refused; configure the final approved URL")
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ValueError("response exceeds byte budget")
        content_type = response.headers.get("content-type", "")
        content = bytes(body)
        lower = content.lstrip().lower()
        challenge_markers = (b"captcha", b"verify you are human", b"challenge-platform", b"access denied", b"security check")
        login_form = b"<form" in lower and any(marker in lower for marker in (b"type=\"password\"", b"type='password'", b"name=\"password\""))
        login_title = b"<title>login" in lower or b"<title>zaloguj" in lower
        if any(marker in lower for marker in challenge_markers) or login_form or login_title:
            raise PermissionError("HTML challenge or login response refused")
        return response.status_code, content, content_type


def robots_policy(body, content_type):
    sample = body.lstrip().lower()
    if content_type.lower().startswith("text/html") or sample.startswith((b"<!doctype html", b"<html")):
        raise PermissionError("robots response is an HTML challenge or login page")
    text = body.decode("utf-8", "replace")
    # A successful robots response should have at least one recognized directive.
    if not any(line.strip().lower().startswith(("user-agent:", "allow:", "disallow:", "crawl-delay:", "request-rate:"))
               for line in text.splitlines()):
        raise PermissionError("robots response is not a recognizable policy")
    try:
        return Protego.parse(text)
    except (ValueError, TypeError) as exc:
        raise PermissionError("robots policy could not be parsed") from exc


def policy_delay(parser, user_agent, configured_delay):
    delay = parser.crawl_delay(user_agent) or 0
    rate = parser.request_rate(user_agent)
    if rate:
        delay = max(delay, rate.seconds / rate.requests)
    return max(configured_delay, float(delay))


def preflight(config, *, network=False, client_factory=httpx.Client, clock=None, sleeper=None):
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep
    errors, missing = validate_config(config)
    safe_config = config if isinstance(config, dict) else {}
    report = {"source": "olx", "state": "not_configured", "collection_enabled": False,
              "configured_enabled": bool(safe_config.get("enabled")) if isinstance(safe_config.get("enabled"), bool) else False,
              "preflight_enables_collection": False,
              "mode": safe_config.get("mode") if isinstance(safe_config.get("mode"), str) else None,
              "city": safe_config.get("city") if isinstance(safe_config.get("city"), str) else None,
              "requests_made": 0, "evidence": [], "missing_evidence": missing, "errors": errors,
              "sample": None, "checklist": ["Obtain documented permission or an authorized provider feed.",
              "Supply exact HTTPS host, Kraków scope, field mapping, pagination and removal semantics.",
              "Run this preflight with --network only after access is supplied.",
              "Have T29 independently verify a successful fetch and parsed sample.",
              "Keep automatic OLX collection disabled until that review is complete.",
              "For a one-off public page, use scripts/import_html.py as a separate manual path."]}
    if not isinstance(config, dict) or not config:
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
        feed_origin = urlparse(config["feed_url"])
        robots_url = feed_origin._replace(path="/robots.txt", query="", fragment="").geturl()
        sequence = [("robots", robots_url), ("feed", config["feed_url"])]
    else:
        search = config["search_urls"][0]
        sequence = [("robots", urlparse(search)._replace(path="/robots.txt", query="").geturl()), ("search", search)]
    headers = {"User-Agent": "Realtoruch/0.2 (source preflight)"}
    token_env = config.get("token_env")
    token = os.environ.get(token_env) if config.get("mode") == "feed" and token_env else None
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with client_factory(timeout=10, follow_redirects=False, headers={"User-Agent": headers["User-Agent"]}) as client:
            fetched = {}
            previous_request = None
            delay = 60 / max(1, int(config.get("requests_per_minute", 6)))
            parser = None
            for kind, url in sequence:
                if report["requests_made"] >= MAX_REQUESTS:
                    raise PermissionError("preflight request budget exhausted")
                try:
                    validate_url(url, config["allowed_hosts"], resolve=True)
                except (ValueError, OSError):
                    raise PermissionError("source destination failed HTTPS/host/public-address checks") from None
                request_headers = headers if kind == "feed" else {"User-Agent": headers["User-Agent"]}
                if previous_request is not None:
                    sleeper(max(0, delay - (clock() - previous_request)))
                previous_request = clock()
                report["requests_made"] += 1
                status, body, content_type = bounded_get(client, url, request_headers)
                if kind == "robots":
                    if status != 200:
                        raise PermissionError("robots policy could not be checked")
                    parser = robots_policy(body, content_type)
                    next_url = sequence[1][1]
                    if not parser.can_fetch(next_url, headers["User-Agent"]):
                        raise PermissionError("robots policy disallows automated access")
                    try:
                        delay = policy_delay(parser, headers["User-Agent"], delay)
                    except (ValueError, TypeError, AttributeError, ZeroDivisionError):
                        raise PermissionError("robots pacing policy is invalid") from None
                else:
                    fetched[kind] = (url, body, content_type)
            if config.get("mode") == "feed":
                payload = json.loads(fetched["feed"][1])
                records = map_feed(payload)
                if not records:
                    report["state"] = "unsupported_payload"
                    report["errors"].append("feed page contains no sample item")
                    return report
                if records[0].city != CITY:
                    report["state"] = "unsupported_payload"
                    report["errors"].append("sample city does not match configured Kraków scope")
                    return report
                detail = next((item.url for item in records), None)
            else:
                page_url, body, _ = fetched["search"]
                result = discover("olx", body.decode("utf-8", "replace"), page_url)
                detail = result.urls[0] if result.urls else None
                records = []
            if detail:
                if report["requests_made"] >= MAX_REQUESTS:
                    raise PermissionError("preflight request budget exhausted")
                detail_url = str(detail)
                detail_origin = urlparse(detail_url)
                robots_origin = urlparse(sequence[0][1])
                if (detail_origin.scheme, detail_origin.netloc) != (robots_origin.scheme, robots_origin.netloc):
                    raise PermissionError("detail origin differs; its robots policy cannot be checked within budget")
                try:
                    validate_url(detail_url, config["allowed_hosts"], resolve=True)
                except (ValueError, OSError):
                    raise PermissionError("detail destination failed HTTPS/host/public-address checks") from None
                if parser is None or not parser.can_fetch(detail_url, headers["User-Agent"]):
                    raise PermissionError("robots policy disallows detail access")
                sleeper(max(0, delay - (clock() - previous_request)))
                report["requests_made"] += 1
                _, detail_body, _ = bounded_get(client, detail_url, {"User-Agent": headers["User-Agent"]})
                if config.get("mode") == "feed":
                    sample = records[0]
                else:
                    sample = map_public_detail(detail_body.decode("utf-8", "replace"), detail_url, CITY)
                if sample.city != CITY:
                    report["state"] = "unsupported_payload"
                    report["errors"].append("sample city does not match configured Kraków scope")
                    return report
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
    try:
        config = load_olx(args.config)
        report = preflight(config, network=args.network)
    except (OSError, json.JSONDecodeError, TypeError, KeyError):
        report = preflight(None)
        report["errors"] = ["source configuration could not be loaded"]
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
