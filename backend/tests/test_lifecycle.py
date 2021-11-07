from datetime import timedelta
import json
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from realtoruch.ingest import ingest
from realtoruch.models import Listing, SourceListing, Observation, now
from realtoruch.connectors import Connector
from realtoruch import worker


def test_retention_removes_old_fingerprints_and_refreshes_remaining_contact_risk(
    session, record, monkeypatch
):
    for i in range(3):
        ingest(session, record.model_copy(update={"external_id": str(i), "address": f"Example {i + 1}"}))
    session.commit()
    sources = session.scalars(select(SourceListing)).all()
    oldest = sources[0]
    oldest.observed_at = now() - timedelta(days=100)
    session.commit()
    monkeypatch.setattr(worker, "Session", sessionmaker(session.bind, expire_on_commit=False))
    worker.retention()
    session.expire_all()
    old = session.get(SourceListing, oldest.id)
    assert old.phone_hash is None and old.data["phone_hash"] is None
    assert old.status == "unknown"
    assert session.get(Listing, old.listing_id).status == "unknown"
    for source in sources[1:]:
        home = session.get(Listing, source.listing_id)
        assert home.status == "active"
        assert not any(flag["code"] == "frequent_contact" for flag in home.risk_flags)
    assert len(session.scalars(select(Observation)).all()) == 3


def test_404_recheck_uses_previous_record_without_inventing_properties(record, monkeypatch):
    previous = record.model_dump(mode="json")
    connector = Connector(
        {
            "name": "otodom",
            "enabled": True,
            "mode": "jsonld",
            "listing_urls": [{"url": str(record.url), "previous": previous}],
            "allowed_hosts": ["www.otodom.pl"],
        }
    )
    monkeypatch.setattr(connector, "fetch", lambda *args, **kwargs: (410, b""))
    results = list(connector.records())
    connector.close()
    assert len(results) == 1 and results[0].status == "inactive"
    assert results[0].rent_pln == record.rent_pln
    assert results[0].observed_at > record.observed_at


def test_failed_source_does_not_emit_inactive_record(record, monkeypatch):
    connector = Connector(
        {
            "name": "otodom",
            "enabled": True,
            "mode": "jsonld",
            "listing_urls": [str(record.url)],
            "allowed_hosts": ["www.otodom.pl"],
        }
    )

    def fail(*args, **kwargs):
        raise httpx.ReadTimeout("source timed out")

    monkeypatch.setattr(connector, "fetch", fail)
    with pytest.raises(httpx.ReadTimeout):
        list(connector.records())
    connector.close()


def test_feed_pagination_and_repeated_page_protection(record, monkeypatch):
    connector = Connector(
        {
            "name": "otodom",
            "enabled": True,
            "mode": "feed",
            "feed_url": "https://www.otodom.pl/feed",
            "allowed_hosts": ["www.otodom.pl"],
        }
    )
    payload = {"items": [record.model_dump(mode="json")], "next_url": "https://www.otodom.pl/feed"}
    monkeypatch.setattr(connector, "fetch", lambda *args: (200, json.dumps(payload).encode()))
    generator = connector.records()
    assert next(generator).external_id == record.external_id
    with pytest.raises(ValueError, match="pagination"):
        next(generator)
    connector.close()


def test_robots_denial_stops_page_fetch(monkeypatch):
    connector = Connector({"name": "otodom", "allowed_hosts": ["www.otodom.pl"], "requests_per_minute": 60})
    called = []

    def handler(request):
        called.append(str(request.url))
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    connector.client.close()
    connector.client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": "Realtoruch/0.1"}
    )
    monkeypatch.setattr("realtoruch.connectors.validate_url", lambda *args: None)
    with pytest.raises(RuntimeError, match="robots"):
        connector.fetch("https://www.otodom.pl/example", page=True)
    assert called == ["https://www.otodom.pl/robots.txt"]
    connector.close()


def test_source_redirects_do_not_forward_credentials(monkeypatch):
    connector = Connector(
        {"name": "otodom", "allowed_hosts": ["www.otodom.pl"], "token_env": "TEST_FEED_TOKEN"}
    )
    called = []

    def handler(request):
        called.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://untrusted.example/"})

    connector.client.close()
    connector.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    monkeypatch.setattr("realtoruch.connectors.validate_url", lambda *args: None)
    monkeypatch.setenv("TEST_FEED_TOKEN", "synthetic-credential")
    with pytest.raises((RuntimeError, httpx.HTTPStatusError)):
        connector.fetch("https://www.otodom.pl/feed")
    assert called == ["https://www.otodom.pl/feed"]
    connector.close()
