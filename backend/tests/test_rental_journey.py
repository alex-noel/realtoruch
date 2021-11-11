"""The user's eight-step journey, exercised through auth/API and the alert worker."""

import json
from datetime import timedelta

import pytest
from pydantic import HttpUrl
from sqlalchemy import func, select

from realtoruch.alerts import process_alerts
from realtoruch.ingest import ingest
from realtoruch.models import AlertEvent, Notification, Observation, Outbox
from realtoruch.query import search_db
from realtoruch.schemas import RawListing, SearchFilters
from realtoruch.search import build_query

POLYGON = [[19.90, 50.03], [19.98, 50.03], [19.98, 50.10], [19.90, 50.10]]
FILTERS = dict(
    city="krakow",
    max_price=5000,
    max_price_exclusive=True,
    min_area=50,
    advertiser="private",
    property_type="apartment",
    polygon=json.dumps(POLYGON),
)


def account(auth_client, email="journey@example.test"):
    response = auth_client.post(
        "/v1/auth/register", json={"email": email, "password": "local-journey-password-123"}
    )
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def pump(session):
    process_alerts(session)
    session.commit()


def home(record, **changes):
    return RawListing.model_validate(
        {
            **record.model_dump(),
            "city": "Kraków",
            "district": "Krowodrza",
            "region": "małopolskie",
            "address": "Przykładowa 12",
            "lat": 50.07,
            "lon": 19.93,
            "area_m2": 55,
            "rent_pln": 4500,
            "images": ["https://images.example.test/apartment-a.jpg"],
            **changes,
        }
    )


def test_complete_rental_journey(session, record, client, auth_client):
    headers = account(auth_client)
    saved = client.post(
        "/v1/me/searches", headers=headers, json={"name": "Kraków under 5k", "filters": FILTERS}
    )
    assert saved.status_code == 201, saved.text
    first = home(record)
    property_id = ingest(session, first)["listing_id"]
    # Outside the polygon, exactly 5k, too small and agency must not enter the saved search.
    for i, change in enumerate(
        [{"lon": 20.1}, {"rent_pln": 5000}, {"area_m2": 49.9}, {"advertiser_type": "agency"}]
    ):
        ingest(session, home(record, external_id=f"excluded-{i}", address=f"Other {i + 1}", **change))
    pump(session)
    result = client.get("/v1/listings", params=FILTERS).json()
    assert result["total"] == 1 and result["items"][0]["id"] == property_id
    inbox = client.get("/v1/me/notifications", headers=headers).json()
    assert inbox["unread_count"] == 1 and inbox["items"][0]["kind"] == "new_match"
    assert client.get("/v1/me/searches", headers=headers).json()["items"][0]["new_matches"] == 1

    assert client.get(f"/v1/listings/{property_id}").status_code == 200
    assert client.put(f"/v1/me/seen/{property_id}", headers=headers).status_code == 200
    state = client.post("/v1/me/listing-state", headers=headers, json={"listing_ids": [property_id]}).json()
    assert state["seen_ids"] == [property_id]
    assert client.get("/v1/me/notifications", headers=headers).json()["unread_count"] == 0
    client.put(f"/v1/me/favorites/{property_id}", headers=headers)

    removed = first.model_copy(
        update={"status": "inactive", "observed_at": first.observed_at + timedelta(hours=1)}
    )
    ingest(session, removed)
    pump(session)
    assert client.get("/v1/listings", params=FILTERS).json()["total"] == 0
    favorites = client.get("/v1/me/favorites", headers=headers).json()["items"]
    assert len(favorites) == 1 and favorites[0]["status"] == "inactive"

    relisted = first.model_copy(
        update={
            "external_id": "reposted-id",
            "url": HttpUrl("https://www.otodom.pl/reposted"),
            "observed_at": first.observed_at + timedelta(hours=2),
        }
    )
    assert ingest(session, relisted)["listing_id"] == property_id
    pump(session)
    assert client.get("/v1/me/notifications", headers=headers).json()["unread_count"] == 0
    assert client.get("/v1/listings", params=FILTERS).json()["total"] == 1

    # Delist again, then repost cheaper under yet another advert ID.
    ingest(
        session,
        relisted.model_copy(
            update={"status": "inactive", "observed_at": first.observed_at + timedelta(hours=3)}
        ),
    )
    cheaper = relisted.model_copy(
        update={
            "external_id": "cheaper-repost",
            "rent_pln": 4200,
            "observed_at": first.observed_at + timedelta(hours=4),
        }
    )
    assert ingest(session, cheaper)["listing_id"] == property_id
    pump(session)
    inbox = client.get("/v1/me/notifications", headers=headers).json()
    assert len(inbox["items"]) == 2 and inbox["unread_count"] == 1
    price_alert = inbox["items"][0]
    assert (price_alert["kind"], price_alert["previous_rent_pln"], price_alert["rent_pln"]) == (
        "price_drop",
        4500,
        4200,
    )
    ingest(session, cheaper)  # At-least-once event redelivery.
    ingest(session, cheaper.model_copy(update={"observed_at": first.observed_at + timedelta(hours=5)}))
    pump(session)
    assert len(client.get("/v1/me/notifications", headers=headers).json()["items"]) == 2

    other = account(auth_client, "other@example.test")
    assert client.get("/v1/me/notifications", headers=other).json()["items"] == []
    assert (
        client.post("/v1/me/listing-state", headers=other, json={"listing_ids": [property_id]}).json()[
            "seen_ids"
        ]
        == []
    )
    assert client.put(f"/v1/me/notifications/{price_alert['id']}/read", headers=other).status_code == 404
    assert client.get("/v1/me/favorites", headers=other).json()["items"] == []


def test_existing_matches_and_seen_prices_are_silent_across_searches(session, record, client, auth_client):
    headers = account(auth_client)
    original = home(record)
    property_id = ingest(session, original)["listing_id"]
    client.put(f"/v1/me/seen/{property_id}", headers=headers)
    for name in ("one", "two"):
        assert (
            client.post(
                "/v1/me/searches", headers=headers, json={"name": name, "filters": FILTERS}
            ).status_code
            == 201
        )
    pump(session)
    assert session.scalar(select(func.count()).select_from(Notification)) == 0
    another = home(record, external_id="new", address="Elsewhere 42", phone=None, images=[])
    ingest(session, another)
    pump(session)
    assert session.scalar(select(func.count()).select_from(Notification)) == 1


def test_seen_repost_after_saving_search_has_no_new_alert(session, record, client, auth_client):
    headers = account(auth_client)
    original = home(record, address="Przykładowa")  # Street only, two corroborating signals.
    property_id = ingest(session, original)["listing_id"]
    client.put(f"/v1/me/seen/{property_id}", headers=headers)
    ingest(
        session,
        original.model_copy(
            update={"status": "inactive", "observed_at": original.observed_at + timedelta(hours=1)}
        ),
    )
    client.post("/v1/me/searches", headers=headers, json={"name": "After viewing", "filters": FILTERS})
    repost = original.model_copy(
        update={"external_id": "new-id", "observed_at": original.observed_at + timedelta(hours=2)}
    )
    assert ingest(session, repost)["listing_id"] == property_id
    pump(session)
    assert client.get("/v1/me/notifications", headers=headers).json()["items"] == []


def test_unchanged_checks_are_daily_checkpoints_and_search_writes_coalesce(session, record):
    first = home(record)
    ingest(session, first)
    for minutes in range(1, 5):
        ingest(
            session, first.model_copy(update={"observed_at": first.observed_at + timedelta(minutes=minutes)})
        )
    assert session.scalar(select(func.count()).select_from(Observation)) == 1
    assert session.scalar(select(func.count()).select_from(AlertEvent)) == 1
    assert session.scalar(select(func.count()).select_from(Outbox)) == 1
    ingest(session, first.model_copy(update={"observed_at": first.observed_at + timedelta(days=1)}))
    assert session.scalar(select(func.count()).select_from(Observation)) == 2


def test_alert_rollback_and_rent_oscillation_do_not_duplicate(session, record, client, auth_client):
    headers = account(auth_client)
    first = home(record)
    property_id = ingest(session, first)["listing_id"]
    client.put(f"/v1/me/favorites/{property_id}", headers=headers)
    ingest(
        session,
        first.model_copy(update={"rent_pln": 4000, "observed_at": first.observed_at + timedelta(hours=1)}),
    )
    session.commit()
    process_alerts(session)
    session.rollback()
    assert session.scalar(select(func.count()).select_from(Notification)) == 0
    pump(session)
    for hour, rent in [(2, 4500), (3, 4000), (4, 3900)]:
        ingest(
            session,
            first.model_copy(
                update={"rent_pln": rent, "observed_at": first.observed_at + timedelta(hours=hour)}
            ),
        )
        pump(session)
    assert session.scalar(select(func.count()).select_from(Notification)) == 2


@pytest.mark.parametrize(
    "points",
    [
        [],
        [[0, 0], [1, 1]],
        [[0, 0], [1, 1], [0, 1], [1, 0]],
        [[0, 0], [1, 1], [2, 2]],
        [[0, 0], [True, 1], [0, 1]],
        [[0, 0], [float("nan"), 1], [0, 1]],
        [[0, 0], [181, 1], [0, 1]],
    ],
)
def test_invalid_map_areas_are_rejected(client, points):
    assert client.get("/v1/listings", params={"polygon": json.dumps(points)}).status_code == 422


def test_concave_polygon_matches_exactly_with_pagination_and_boundary(session, record):
    points = [[19.9, 50.0], [20.0, 50.0], [20.0, 50.1], [19.95, 50.05], [19.9, 50.1]]
    for i, (lon, lat) in enumerate([(19.91, 50.02), (19.95, 50.09), (19.95, 50.05), (20.1, 50.02)]):
        ingest(
            session,
            home(record, external_id=str(i), address=f"Test {i}", lon=lon, lat=lat, phone=None, images=[]),
        )
    filters = SearchFilters(polygon=json.dumps(points), page_size=1)
    result = search_db(session, filters)
    assert result["total"] == 2 and len(result["items"]) == 1
    filters.page = 2
    assert search_db(session, filters)["items"][0]["id"] != result["items"][0]["id"]
    elastic = build_query(SearchFilters(**FILTERS))
    assert any("geo_shape" in clause for clause in elastic["query"]["bool"]["filter"])
    assert {"range": {"rent_pln": {"lt": 5000}}} in elastic["query"]["bool"]["filter"]
