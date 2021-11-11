import os
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_temporary = tempfile.TemporaryDirectory(prefix="realtoruch-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_temporary.name}/api.db"
os.environ["AUTH_DATABASE_URL"] = f"sqlite:///{_temporary.name}/auth.db"
os.environ["DEMO_MODE"] = "true"
os.environ["REQUEST_LIMIT_PER_MINUTE"] = "10000"
os.environ["AUTH_REQUEST_LIMIT_PER_MINUTE"] = "10000"

from realtoruch.db import Base, get_session
from realtoruch.schemas import RawListing
from realtoruch.models import now


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as value:
        yield value
    engine.dispose()


@pytest.fixture
def record():
    from datetime import timedelta

    return RawListing(
        source="otodom",
        external_id="one",
        url="https://www.otodom.pl/example",
        title="A sunny apartment",
        description="<p>Bright home</p>",
        city="Warszawa",
        district="Mokotów",
        region="mazowieckie",
        address="Dąbrowskiego 24",
        area_m2=54,
        rooms=2,
        floor=2,
        rent_pln=3000,
        fees_pln=500,
        commission_pln=0,
        advertiser_type="private",
        lat=52.2,
        lon=21.0,
        phone="700100101",
        observed_at=now() - timedelta(days=2),
    )


@pytest.fixture
def client(session):
    from fastapi.testclient import TestClient
    from realtoruch.api import app
    from realtoruch.auth import validate_claims

    app.state.validate_claims = validate_claims
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    del app.state.validate_claims


@pytest.fixture
def auth_client():
    from fastapi.testclient import TestClient
    from realtoruch.auth import app, AuthBase, auth_engine

    AuthBase.metadata.drop_all(auth_engine)
    with TestClient(app) as client:
        yield client
