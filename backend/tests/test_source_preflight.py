import json
from pathlib import Path

import httpx
import pytest
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.source_preflight import map_feed, preflight, validate_config

DETAIL = (ROOT / "backend/tests/fixtures/portals/olx-detail.html").read_text()
DETAIL_URL = "https://www.olx.pl/d/oferta/synthetic-rental-CID3-IDabc123.html"


def profile(mode="feed", **updates):
    config = {"name": "olx", "enabled": True, "mode": mode, "city": "Kraków",
              "allowed_hosts": ["www.olx.pl"], "feed_url": "https://www.olx.pl/feed.json",
              "token_env": "T06_TEST_TOKEN", "requests_per_minute": 6, "max_pages": 1,
              "search_urls": ["https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/"]}
    config.update(updates)
    return config


class MockClient:
    def __init__(self, responses, **kwargs):
        self.responses = iter(responses)
        self.client = httpx.Client(transport=httpx.MockTransport(self.handler), **kwargs)

    def handler(self, request):
        status, body, content_type = next(self.responses)
        return httpx.Response(status, content=body, headers={"content-type": content_type}, request=request)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def stream(self, *args, **kwargs):
        return self.client.stream(*args, **kwargs)


def client_factory(responses):
    return lambda **kwargs: MockClient(responses, **kwargs)


@pytest.fixture(autouse=True)
def no_real_waits(monkeypatch):
    monkeypatch.setattr("scripts.source_preflight.time.sleep", lambda _seconds: None)


def test_offline_default_makes_no_http_requests(monkeypatch):
    monkeypatch.delenv("T06_TEST_TOKEN", raising=False)
    config = profile(enabled=False, feed_url="")
    report = preflight(config)
    assert report["state"] == "not_configured"
    assert report["requests_made"] == 0
    monkeypatch.setenv("T06_TEST_TOKEN", "offline-test-token")
    report = preflight(profile(enabled=False), client_factory=lambda **kw: pytest.fail("HTTP client created"))
    assert report["state"] == "ready_offline"


def test_invalid_hosts_and_missing_token_do_not_leak_secret(monkeypatch):
    monkeypatch.setenv("T06_TEST_TOKEN", "canary-secret-value")
    errors, missing = validate_config(profile(feed_url="http://127.0.0.1/feed?token=canary-secret-value"))
    assert errors and not missing
    monkeypatch.delenv("T06_TEST_TOKEN")
    report = preflight(profile())
    rendered = json.dumps(report)
    assert "canary-secret-value" not in rendered
    assert "T06_TEST_TOKEN" in rendered


def test_feed_and_public_fixture_map_to_raw_listing():
    item = {"external_id": "provider-1", "url": DETAIL_URL, "title": "Synthetic flat",
            "city": "Kraków", "area_m2": 53, "rooms": 2, "rent_pln": 2550,
            "observed_at": "2026-11-11T10:00:00Z"}
    record = map_feed({"items": [item]})[0]
    assert record.external_id == "provider-1" and record.rent_pln == 2550
    from scripts.source_preflight import map_public_detail
    parsed = map_public_detail(DETAIL, DETAIL_URL)
    assert parsed.external_id and parsed.city == "Kraków" and parsed.rent_pln == 2550


def test_403_stops_without_enabling_source(monkeypatch):
    monkeypatch.setenv("T06_TEST_TOKEN", "secret-canary")
    # Avoid DNS entirely in this fake-transport test.
    monkeypatch.setattr("scripts.source_preflight.socket.getaddrinfo", lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 443))])
    report = preflight(profile(mode="portal"), network=True,
                       client_factory=client_factory([(403, b"blocked", "text/plain")]))
    assert report["state"] == "blocked_access"
    assert report["requests_made"] == 1
    assert report["collection_enabled"] is False


def test_configuration_alone_never_claims_live_verification(monkeypatch):
    monkeypatch.setenv("T06_TEST_TOKEN", "configured-token")
    assert preflight(profile())["state"] == "ready_offline"


def test_malformed_fetched_feed_is_unsupported_payload(monkeypatch):
    monkeypatch.setenv("T06_TEST_TOKEN", "configured-token")
    monkeypatch.setattr("scripts.source_preflight.socket.getaddrinfo", lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 443))])
    responses = [(200, b"User-agent: *\nAllow: /\n", "text/plain"),
                 (200, b'{"items":[{"broken":true}]}', "application/json")]
    report = preflight(profile(), network=True, client_factory=client_factory(responses))
    assert report["state"] == "unsupported_payload"
    assert report["requests_made"] == 2


def test_manual_import_remains_separate_and_network_success_requires_parsed_sample(monkeypatch):
    monkeypatch.delenv("T06_TEST_TOKEN", raising=False)
    assert any("import_html.py" in item for item in preflight(profile(enabled=False))["checklist"])
    monkeypatch.setattr("scripts.source_preflight.socket.getaddrinfo", lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 443))])
    robots = b"User-agent: *\nAllow: /\n"
    from pathlib import Path
    search = (ROOT / "backend/tests/fixtures/portals/olx-search.html").read_bytes()
    responses = [(200, robots, "text/plain"), (200, search, "text/html"), (200, DETAIL.encode(), "text/html")]
    report = preflight(profile(mode="portal"), network=True, client_factory=client_factory(responses))
    assert report["state"] == "live_sample_verified"
    assert report["requests_made"] == 3


def test_robots_path_denial_blocks_before_discovery(monkeypatch):
    monkeypatch.setattr("scripts.source_preflight.socket.getaddrinfo", lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 443))])
    policy = b"User-agent: *\nDisallow: /nieruchomosci/\n"
    report = preflight(profile(mode="portal"), network=True,
                       client_factory=client_factory([(200, policy, "text/plain")]))
    assert report["state"] == "blocked_access"
    assert report["requests_made"] == 1
