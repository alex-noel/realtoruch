import pytest
from realtoruch.ingest import ingest
from realtoruch.models import Listing


def test_public_search_filters_and_fee_unknowns(session, record, client):
    ingest(session, record)
    ingest(
        session,
        record.model_copy(
            update={"external_id": "two", "address": "Other 2", "commission_pln": None, "rent_pln": 5000}
        ),
    )
    ingest(
        session,
        record.model_copy(
            update={
                "external_id": "agency",
                "address": "Other 3",
                "advertiser_type": "agency",
                "commission_pln": 3000,
            }
        ),
    )
    result = client.get("/v1/listings?advertiser=private&no_commission=true").json()
    assert result["total"] == 1
    assert result["items"][0]["total_monthly_pln"] == 3500
    assert client.get("/v1/listings?max_price=2999").json()["total"] == 0
    assert client.get("/v1/listings?bbox=20,52,22,53").json()["total"] == 3
    assert client.get("/v1/listings?page_size=1&page=2").json()["page"] == 2


@pytest.mark.parametrize(
    "query",
    [
        "min_price=4000&max_price=3000",
        "page=0",
        "page_size=1000",
        "bbox=bad",
        "bbox=nan,0,1,1",
        "sort=script",
        "min_area=70&max_area=50",
    ],
)
def test_invalid_search_is_validation_error(client, query):
    assert client.get("/v1/listings?" + query).status_code == 422


def test_internal_ingestion_is_not_public(client, record):
    assert client.post("/internal/observations", json=record.model_dump(mode="json")).status_code == 403
    assert "/internal" not in client.get("/openapi.json").text


def test_accounts_and_favorites_are_isolated(client, auth_client, session, record):
    listing_id = ingest(session, record)["listing_id"]
    credentials = {"email": "one@example.test", "password": "a-long-local-test-password"}
    response = auth_client.post("/v1/auth/register", json=credentials)
    assert response.status_code == 201
    token1 = response.json()["access_token"]
    assert (
        auth_client.post(
            "/v1/auth/login", json={**credentials, "password": "incorrect-test-password"}
        ).status_code
        == 401
    )
    assert auth_client.post("/v1/auth/login", json=credentials).status_code == 200
    other = auth_client.post("/v1/auth/register", json={**credentials, "email": "two@example.test"})
    token2 = other.json()["access_token"]
    h1, h2 = {"Authorization": f"Bearer {token1}"}, {"Authorization": f"Bearer {token2}"}
    assert client.get("/v1/me/favorites").status_code == 401
    assert client.put(f"/v1/me/favorites/{listing_id}", headers=h1).status_code == 200
    assert client.put(f"/v1/me/favorites/{listing_id}", headers=h1).status_code == 200
    assert len(client.get("/v1/me/favorites", headers=h1).json()["items"]) == 1
    assert client.get("/v1/me/favorites", headers=h2).json()["items"] == []
    saved = client.post("/v1/me/searches", headers=h1, json={"name": "Two rooms", "filters": {"rooms": 2}})
    assert saved.status_code == 201
    assert client.delete("/v1/me/searches/" + saved.json()["id"], headers=h2).status_code == 404
    assert client.get("/v1/me/searches", headers=h2).json()["items"] == []
    report = client.post(
        f"/v1/listings/{listing_id}/reports", headers=h1, json={"reason": "A local integration-test report"}
    )
    assert report.status_code == 201
    assert session.get(Listing, listing_id).risk_score == 0
    assert client.delete(f"/v1/me/favorites/{listing_id}", headers=h1).status_code == 200
    assert client.get("/v1/me/favorites", headers=h1).json()["items"] == []


def test_missing_listing_and_unknown_commission(session, record, client):
    listing_id = ingest(session, record.model_copy(update={"fees_pln": None, "commission_pln": None}))[
        "listing_id"
    ]
    detail = client.get(f"/v1/listings/{listing_id}").json()
    assert detail["total_monthly_pln"] is None
    assert detail["commission_pln"] is None
    assert detail["history"]
    assert client.get("/v1/listings/missing").status_code == 404


def test_public_cache_headers_and_metrics(client):
    response = client.get("/healthz")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get("/metrics").status_code == 403
