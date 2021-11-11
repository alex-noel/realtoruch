"""T07 restart, budget, reporting and separate non-network failure evidence."""

import importlib
import json
import multiprocessing
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from realtoruch.db import Base

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
PORTAL = "https://www.otodom.pl"
SEARCH = PORTAL + "/pl/wyniki/wynajem/mieszkanie/malopolskie/krakow/krakow/krakow"
DETAIL = PORTAL + "/pl/oferta/t07-fixture-ID"
SOURCES = ("otodom", "gratka", "morizon")


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return importlib.import_module("reliability")


def synthetic_pin():
    return {"commit": "synthetic", "config_sha256": "synthetic", "city": "Kraków",
            "sources": list(SOURCES), "budget": {}}


def scheduler_process(directory, phase):
    """Use real process exit/reopen and a synthetic clock; never call the network."""
    sys.path.insert(0, str(SCRIPTS))
    runner = importlib.import_module("reliability")
    clock = [T0 if phase == "complete_two" else T0 + timedelta(hours=12)]
    path = directory / "manifest.json"

    class Clock:
        @staticmethod
        def now(_):
            return clock[0]

    def sleep(seconds):
        data = json.loads(path.read_text())
        if phase == "complete_two" and data["cycles"][1]["state"] == "completed":
            os._exit(91)
        if phase == "recover":
            os._exit(0)
        clock[0] += timedelta(seconds=seconds)

    def collect(_, manifest, cycle, __):
        if phase == "crash_during_third":
            assert cycle["id"] == "cycle-03"
            os._exit(92)
        assert phase == "complete_two", "interrupted scheduled cycle was replayed"
        runner.atomic_write(runner.result_path(directory, cycle), {
            "sources": [{"source": name, "status": "succeeded", "ingested": 1, "network_attempts": 3}
                        for name in SOURCES],
        })
        return 0

    runner.datetime = Clock
    runner.time = SimpleNamespace(sleep=sleep)
    runner.checked_pin = lambda _: synthetic_pin()
    runner.run_cycle = collect
    runner.run_soak(directory, "fixture", synthetic_pin(), -1)


def spawn(target, args, exitcode=0):
    process = multiprocessing.get_context("spawn").Process(target=target, args=args)
    process.start()
    process.join(25)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail(f"{target.__name__} exceeded the deterministic drill deadline")
    assert process.exitcode == exitcode
    return process.pid


def test_t07_tc01_restart_preserves_slots_and_never_replays(tmp_path):
    path = tmp_path / "manifest.json"
    spawn(scheduler_process, (tmp_path, "complete_two"), exitcode=91)
    before = json.loads(path.read_text())
    first, second, third, fourth = before["cycles"][:4]
    assert [first["state"], second["state"], third["state"]] == ["completed", "completed", "pending"]
    assert (third["id"], third["scheduled_at"]) == ("cycle-03", "2025-01-01T12:00:00Z")

    spawn(scheduler_process, (tmp_path, "crash_during_third"), exitcode=92)
    interrupted = json.loads(path.read_text())
    assert interrupted["cycles"][2]["state"] == "running"
    spawn(scheduler_process, (tmp_path, "recover"))
    after = json.loads(path.read_text())
    assert after["cycles"][:2] == before["cycles"][:2]
    assert after["cycles"][2]["state"] == "interrupted"
    assert after["cycles"][2]["reason"] == "recovered_without_replay"
    assert after["cycles"][2]["started_at"] == third["scheduled_at"]
    assert after["cycles"][3] == fourth
    assert after["runner_gaps"] == [{"from": "2025-01-01T06:00:00Z", "to": "2025-01-01T12:00:00Z",
                                     "reason": "runner_restart"}]


def test_interruption_recovers_finished_sql_checkpoint_without_assuming_unknown_requests(runner, tmp_path):
    from realtoruch.models import CollectionRun

    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine).begin() as session:
        for name, status in (("otodom", "succeeded"), ("gratka", "running")):
            at = T0.replace(tzinfo=None) + timedelta(seconds=1)
            session.add(CollectionRun(id=f"{name}-checkpoint", city="Kraków", source=name, started_at=at,
                                      status=status, finished_at=at if status == "succeeded" else None,
                                      report={"ingested": 1, "network_attempts": 3} if status == "succeeded" else {}))
    engine.dispose()
    manifest = runner.new_manifest("recovery-fixture", synthetic_pin(), T0)
    cycle = manifest["cycles"][0]
    cycle.update(state="running", started_at=runner.timestamp(T0), counts_before=runner.catalog_snapshot(tmp_path)[0])
    runner.finalize(tmp_path / "manifest.json", manifest, cycle, T0 + timedelta(seconds=3),
                    reason="recovered_without_replay")
    assert cycle["state"] == "interrupted"
    assert cycle["sources"]["otodom"]["checkpoint_id"] == "otodom-checkpoint"
    assert cycle["sources"]["gratka"]["checkpoint_id"] == "gratka-checkpoint"
    report = runner.aggregate(manifest)
    assert report["providers"]["otodom"]["successful_checks"] == 1
    assert report["providers"]["gratka"]["unknown_network_totals"] == 1
    assert report["providers"]["morizon"]["unknown_provider_attempts"] == 1
    assert "otodom-checkpoint" not in json.dumps(report)


def completed(runner, manifest, cycle, now, reports, tmp_path):
    counts, _, _ = runner.catalog_snapshot(tmp_path)
    cycle.update(state="running", started_at=runner.timestamp(now), counts_before=counts)
    runner.finish_cycle(manifest, cycle, now, counts, None, {}, reports)


def test_t07_tc05_tc06_deferrals_failures_gaps_and_removal_are_distinct(runner, tmp_path):
    manifest = runner.new_manifest("aggregate-fixture", synthetic_pin(), T0)
    reports = [
        {"source": "otodom", "status": "failed", "network_attempts": 2,
         "errors": [{"stage": "detail", "kind": "SourceAccessError", "http_status": 429,
                     "url_hash": "PRIVATE_FIXTURE_CANARY"}]},
        *[{"source": name, "status": "succeeded", "ingested": 1, "network_attempts": 3}
          for name in SOURCES[1:]],
    ]
    completed(runner, manifest, runner.advance(manifest, T0), T0, reports, tmp_path)
    for interval in (1, 2):
        now = T0 + timedelta(hours=6 * interval)
        runner.observe(manifest, now)
        deferred = [{"source": name, "status": "deferred", "reason": "backoff"} for name in SOURCES]
        completed(runner, manifest, runner.advance(manifest, now), now, deferred, tmp_path)
    now = T0 + timedelta(hours=25)
    runner.observe(manifest, now, resumed=True)
    assert runner.advance(manifest, now) is None

    summary = runner.aggregate(manifest)
    assert summary["status"] == "INCOMPLETE"
    assert summary["cycle_counts"] == {
        "attempted": 3, "eligible": 1, "completed": 1, "deferred": 2, "missed": 2,
        "interrupted": 0, "running": 0, "pending": 7,
    }
    assert summary["providers"]["otodom"]["failed"] == 1
    assert summary["providers"]["otodom"]["deferred"] == 2
    assert summary["providers"]["gratka"]["success_fraction"] == {
        "succeeded": 1, "accounted_intervals": 5, "scheduled_intervals": 12,
    }
    assert summary["providers"]["otodom"]["errors"] == {"detail/SourceAccessError/429": 1}
    assert len(summary["runner_gaps"]) == 3 and summary["runner_covered_seconds"] == 0
    assert summary["live_removal"] == "UNVERIFIED"
    assert "fixture" in summary["fixture_evidence"].lower()
    assert "PRIVATE_FIXTURE_CANARY" not in json.dumps(summary)


def test_acceptance_requires_elapsed_horizon_and_success_for_each_source(runner, tmp_path):
    manifest = runner.new_manifest("clock-fixture", synthetic_pin(), T0)
    for minute in range(72 * 60 + 1):
        now = T0 + timedelta(minutes=minute)
        runner.observe(manifest, now)
        cycle = runner.advance(manifest, now)
        if cycle:
            completed(runner, manifest, cycle, now, [
                {"source": name, "status": "succeeded", "ingested": 1, "network_attempts": 3}
                for name in SOURCES
            ], tmp_path)
        if minute == 71 * 60:
            assert runner.aggregate(manifest)["status"] == "INCOMPLETE"
    assert runner.aggregate(manifest)["status"] == "VERIFIED"
    for cycle in manifest["cycles"]:
        cycle["sources"]["gratka"]["ingested"] = 0
    assert runner.aggregate(manifest)["status"] == "INCOMPLETE"


class FetchClock:
    def __init__(self, hour=0):
        self.utc = T0.replace(tzinfo=None) + timedelta(hours=hour)
        self.elapsed = 0

    def now(self):
        return self.utc + timedelta(seconds=self.elapsed)

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


def install_transport(monkeypatch, clock, transport):
    from realtoruch import collection_health, connectors, worker

    monkeypatch.setattr(connectors, "time", clock)
    monkeypatch.setattr(connectors, "uniform", lambda *_: 0.125)
    monkeypatch.setattr(connectors, "validate_url", lambda *_: None)
    for module in (collection_health, connectors, worker):
        monkeypatch.setattr(module, "now", clock.now)
    init = connectors.Connector.__init__

    def initialize(connector, *args, **kwargs):
        init(connector, *args, **kwargs)
        connector.client.close()
        connector.client = httpx.Client(transport=httpx.MockTransport(transport))

    monkeypatch.setattr(connectors.Connector, "__init__", initialize)


def detail_html(url, *, rent=4500, identifier=700000001):
    ad = {
        "id": identifier, "url": url, "title": "Synthetic home",
        "status": "active", "advertiserType": "private",
        "adCategory": {"name": "FLAT", "type": "RENT"},
        "characteristics": [
            {"key": "price", "value": rent, "currency": "PLN"}, {"key": "m", "value": "55"},
            {"key": "rooms_num", "value": "2"}, {"key": "floor_no", "value": "floor_3"},
        ],
        "location": {
            "reverseGeocoding": {"locations": [{"locationLevel": "city_or_village", "name": "Kraków"}]},
            "address": {"street": {"name": "Synthetic Street", "number": "12/4"}},
        },
        "images": [{"large": "https://images.example.test/synthetic.jpg"}],
    }
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(
        {"props": {"pageProps": {"ad": ad}}}
    ) + "</script>"


def test_soak_budget_bounds_distinct_requests_robots_and_retry(monkeypatch, runner):
    from realtoruch.connectors import Connector
    from realtoruch.portals import parse_detail

    clock = FetchClock()
    urls = [DETAIL + str(i) for i in range(10)]
    urls[0] = urls[0].replace("www.otodom.pl", "otodom.pl")
    # Discovery includes four selected and three other due known adverts before the two new ones.
    # The known overflow must not spend either new-advert slot.
    known = {url: parse_detail("otodom", detail_html(url, identifier=700000001 + i), url).model_copy(
        update={"observed_at": clock.now() - timedelta(days=1)}
    ).model_dump(mode="json") for i, url in enumerate(urls[:7])}
    requests = []

    def transport(request):
        url = str(request.url)
        requests.append(url)
        if requests.count(url) == 1:
            raise httpx.ReadTimeout("injected first attempt")
        if url.endswith("robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if url == SEARCH:
            search = {"items": [{"slug": item.rsplit("/", 1)[-1], "transaction": "RENT", "estate": "FLAT"}
                                for item in urls[1:]], "pagination": {"currentPage": 1, "totalPages": 2}}
            state = {"props": {"pageProps": {"transaction": "RENT", "data": {"searchAds": search}}}}
            return httpx.Response(200, text='<script id="__NEXT_DATA__">' + json.dumps(state) + "</script>")
        return httpx.Response(200, text=detail_html(url, identifier=700000001 + urls.index(url)))

    install_transport(monkeypatch, clock, transport)
    connector = Connector({
        "name": "otodom", "mode": "portal", "enabled": True, "city": "Kraków",
        "search_urls": [SEARCH], "allowed_hosts": ["www.otodom.pl", "otodom.pl"], "recheck_interval_minutes": 360,
        **runner.LIMITS,
    }, previous_lookup=known.get, known_urls=[{"url": url} for url in urls[:4]])
    try:
        assert len(list(connector.records())) == 6
    finally:
        connector.close()
    assert set(requests) == {SEARCH, PORTAL + "/robots.txt", "https://otodom.pl/robots.txt", *urls[:4], *urls[7:9]}
    assert connector.report["due_rechecks"] == 4 and connector.report["new_details"] == 2
    assert connector.report["known_skipped"] == 3
    assert connector.report["robots_attempts"] == 4 and connector.report["search_pages"] == 1
    assert connector.report["retry_attempts"] == 9 and connector.report["network_attempts"] == 18
    assert connector.report["errors"] == []


def test_soak_stops_after_exhausting_robots_retry(monkeypatch, runner):
    from realtoruch.connectors import Connector, SourceAccessError

    attempts = []

    def fail_robots(request):
        attempts.append(str(request.url))
        raise httpx.ReadTimeout("synthetic robots timeout")

    install_transport(monkeypatch, FetchClock(), fail_robots)
    connector = Connector({
        "name": "otodom", "mode": "portal", "enabled": True, "city": "Kraków",
        "search_urls": [SEARCH], "allowed_hosts": ["www.otodom.pl"], **runner.LIMITS,
    }, known_urls=[{"url": DETAIL + str(i)} for i in range(4)])
    try:
        with pytest.raises(SourceAccessError, match="robots policy"):
            list(connector.records())
    finally:
        connector.close()
    assert attempts == [PORTAL + "/robots.txt"] * 2
    assert connector.report["robots_attempts"] == 2 and connector.report["retry_attempts"] == 1


def drill_phase(directory, scenario, hour):
    from realtoruch import email_alerts, worker
    from realtoruch.alerts import process_alerts
    from realtoruch.ingest import ingest
    from realtoruch.models import (
        EmailSubscription,
        Favorite,
        Listing,
        Notification,
        Observation,
        SavedSearch,
        SeenPrice,
        SourceListing,
    )
    from realtoruch.schemas import RawListing, SearchFilters
    from realtoruch.settings import Settings

    engine = create_engine(f"sqlite:///{directory / 'catalog.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    clock = FetchClock(hour)
    url = DETAIL + ("rel" if scenario in ("relist", "final_remove") else "orig")
    requests = []

    def transport(request):
        requests.append(str(request.url))
        if str(request.url) == PORTAL + "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        assert str(request.url) == url
        if scenario == "timeout":
            raise httpx.ReadTimeout("synthetic timeout")
        if scenario == "forbidden":
            return httpx.Response(403)
        if scenario == "throttle":
            return httpx.Response(429, headers={"Retry-After": "46800"})
        if scenario == "malformed":
            return httpx.Response(200, text='<script id="__NEXT_DATA__">malformed')
        if scenario in ("remove", "final_remove"):
            return httpx.Response(410 if scenario == "remove" else 404)
        return httpx.Response(200, text=detail_html(
            url, rent=4200 if scenario in ("reprice", "relist") else 4500,
            identifier=700000002 if scenario == "relist" else 700000001,
        ))

    with pytest.MonkeyPatch.context() as monkeypatch:
        install_transport(monkeypatch, clock, transport)
        monkeypatch.setattr(worker, "Session", factory)
        monkeypatch.setattr(worker, "load_sources", lambda: [{
            "name": "otodom", "mode": "portal", "city": "Kraków", "enabled": True,
            "listing_urls": [url], "allowed_hosts": ["www.otodom.pl"],
            "requests_per_minute": 6, "recheck_interval_minutes": 0, "max_rechecks": 4,
        }])
        monkeypatch.setattr(email_alerts, "get_settings", lambda: Settings(
            _env_file=None, environment="development", email_delivery_mode="file",
            email_preview_directory=str(directory / "mail"), public_web_url="http://localhost",
        ))

        if scenario == "first":
            with factory.begin() as session:
                filters = SearchFilters(city="Kraków", max_price=5000, max_price_exclusive=True,
                                        min_area=50, advertiser="private")
                session.add(SavedSearch(user_id="fixture", name="T07 fixture search",
                                        filters=filters.model_dump(mode="json"), city_key="krakow"))
                session.add(EmailSubscription(user_id="fixture", email="fixture@example.test",
                                              enabled=True, verified_at=clock.now(), unsubscribe_token="fixture"))
        if scenario == "duplicate":
            with factory.begin() as session:
                row = session.scalar(select(SourceListing))
                report = ingest(session, RawListing.model_validate(row.data))
        else:
            try:
                report, = worker.collect()
            except worker.CollectionFailed as exc:
                report, = exc.reports
        with factory.begin() as session:
            process_alerts(session)
            if scenario == "first":
                home = session.scalar(select(Listing))
                session.add(Favorite(user_id="fixture", listing_id=home.id, price_floor=home.rent_pln))
                session.add(SeenPrice(user_id="fixture", listing_id=home.id, rent_pln=home.rent_pln))
        email_alerts.dispatch_email(factory)
        # Re-evaluate with a new connection. The parent starts a new Python process for each phase.
        with factory() as session:
            evidence = {
                "report": report, "requests": len(requests),
                "canonical": [(item.id, item.status) for item in session.scalars(select(Listing))],
                "favorite": [(item.listing_id, item.price_floor) for item in session.scalars(select(Favorite))],
                "observations": [
                    (item.observed_at.date().isoformat(), item.rent_pln, item.status, item.changed)
                    for item in session.scalars(select(Observation).order_by(Observation.observed_at))
                ],
                "notifications": [
                    (item.kind, item.previous_rent_pln, item.rent_pln)
                    for item in session.scalars(select(Notification).order_by(Notification.created_at))
                ],
                "file_previews": len(list((directory / "mail").glob("*.eml"))),
            }
            (directory / f"{scenario}-{hour}.json").write_text(json.dumps(evidence))
    engine.dispose()


def test_t07_tc03_tc04_separate_failure_restart_replay_and_confirmed_removal(tmp_path):
    def phase(name, hour):
        spawn(drill_phase, (tmp_path, name, hour))
        return json.loads((tmp_path / f"{name}-{hour}.json").read_text())

    first = phase("first", 0)
    canonical = first["canonical"][0][0]
    assert first["notifications"] == [["new_match", None, 4500]] and first["file_previews"] == 1
    for hour in (1, 2):
        assert phase("unchanged", hour)["observations"] == first["observations"]
    checkpoint = phase("unchanged", 24)
    assert checkpoint["observations"] == [
        ["2025-01-01", 4500, "active", True], ["2025-01-02", 4500, "active", False],
    ]
    for scenario, hour, status, attempts, error in (
        ("timeout", 25, "failed", 3, ("ReadTimeout", None)),
        ("forbidden", 26, "failed", 2, ("SourceAccessError", 403)),
        ("throttle", 27, "failed", 2, ("SourceAccessError", 429)),
        ("deferred", 33, "deferred", 0, None),
        ("deferred", 39, "deferred", 0, None),
        ("malformed", 41, "failed", 2, ("ParseError", None)),
    ):
        evidence = phase(scenario, hour)
        report = evidence["report"]
        assert report["status"] == status and evidence["requests"] == attempts
        if error:
            failure, = report["errors"]
            assert (failure["kind"], failure["http_status"]) == error
        assert evidence["canonical"] == [[canonical, "active"]]
        assert evidence["observations"] == checkpoint["observations"]
        assert evidence["notifications"] == first["notifications"] and evidence["file_previews"] == 1

    repriced = phase("reprice", 44)
    assert repriced["notifications"] == [*first["notifications"], ["price_drop", 4500, 4200]]
    assert repriced["file_previews"] == 2
    duplicate = phase("duplicate", 44)
    assert duplicate["report"] == {"status": "duplicate_event"}
    assert duplicate["observations"] == repriced["observations"]
    assert duplicate["notifications"] == repriced["notifications"] and duplicate["file_previews"] == 2

    removed = phase("remove", 45)
    assert removed["canonical"] == [[canonical, "inactive"]] and removed["report"]["inactive"] == 1
    relisted = phase("relist", 46)
    assert relisted["canonical"] == [[canonical, "active"]]
    assert relisted["notifications"] == repriced["notifications"] and relisted["file_previews"] == 2
    final = phase("final_remove", 47)
    assert final["canonical"] == [[canonical, "inactive"]] and final["report"]["inactive"] == 1
    assert final["favorite"] == [[canonical, 4200]]
    assert final["notifications"] == repriced["notifications"] and final["file_previews"] == 2
    assert final["observations"] == [
        *checkpoint["observations"], ["2025-01-02", 4200, "active", True],
        ["2025-01-02", 4200, "inactive", True], ["2025-01-02", 4200, "active", True],
        ["2025-01-02", 4200, "inactive", True],
    ]
