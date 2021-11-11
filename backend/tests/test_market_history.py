from datetime import datetime
from statistics import median
import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_service_integration import pg_engine  # noqa: F401 -- shared isolated migration fixture

from realtoruch.db import Base
from realtoruch.models import Listing, Observation, SourceListing
from realtoruch.query import market_history, market_summary
from realtoruch import query


@pytest.fixture(params=['sqlite', 'postgresql'])
def db(request):
    if request.param == 'postgresql':
        if not os.environ.get('TEST_POSTGRES_URL'):
            pytest.skip('Requires an isolated PostgreSQL test instance')
        engine = request.getfixturevalue('pg_engine')
    else:
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()
    if request.param == 'sqlite':
        engine.dispose()


def populate(db):
    # Independent records also serve as input to the deliberately simple reference.
    rows = [
        ('a', 'a1', '2023-12-31 23:59:59', 1000, 'active'),
        ('a', 'a1', '2024-01-01 00:00:00', 2000, 'active'),
        ('a', 'a1', '2024-02-29 12:00:00', 3000, 'active'),
        ('a', 'a1', '2024-02-29 13:00:00', 3000, 'inactive'),
        ('a', 'a2', '2024-02-29 12:30:00', 3500, 'active'),
        ('b', 'b1', '2024-02-29 12:00:00', 4001, 'active'),
        ('c', 'c1', '2024-01-10 12:00:00', 6000, 'active'),
        ('c', 'c1', '2024-03-01 12:00:01', 9000, 'active'),
    ]
    for home, area in [('a', 50), ('b', 100), ('c', 50)]:
        db.add(Listing(id=home, title=home, city='Test', district='D', region='R', address=home,
                       area_m2=area, rooms=2, rent_pln=1000, is_demo=home == 'a'))
    db.flush()
    for source in sorted({r[1] for r in rows}):
        home = source[0]
        db.add(SourceListing(id=source, listing_id=home, source=source, external_id=source,
                             url='https://example.test', data={}, status='active', observed_at=datetime(2024, 1, 1)))
    db.flush()
    for i, (home, source, at, rent, status) in enumerate(rows):
        db.add(Observation(id=str(i), listing_id=home, source_listing_id=source,
                           observed_at=datetime.fromisoformat(at), rent_pln=rent, status=status, changed=True))
    db.flush()
    return rows


def reference(rows, start, end):
    latest = {}
    for home, source, value, rent, status in rows:
        at = datetime.fromisoformat(value)
        if start <= at <= end:
            key = (value[:7], source)
            if key not in latest or at > latest[key][0]:
                latest[key] = (at, home, rent, status)
    by_home = {}
    for (month, source), (at, home, rent, status) in latest.items():
        key = (month, home)
        if status == 'active' and (key not in by_home or (at, source) > by_home[key][:2]):
            by_home[key] = (at, source, rent)
    points = []
    for month in sorted({key[0] for key in by_home}):
        homes = [(home, item[2]) for (m, home), item in by_home.items() if m == month]
        points.append({'month': month, 'median_rent_pln': median(r for _, r in homes),
                       'median_per_m2': round(median(r / (100 if h == 'b' else 50) for h, r in homes), 2),
                       'sample_size': len(homes), 'is_demo': any(h == 'a' for h, _ in homes)})
    return points


def test_reference_and_boundaries(db, monkeypatch):
    rows = populate(db)
    end = datetime(2024, 3, 1, 12)
    monkeypatch.setattr(query, 'now', lambda: end)
    for months, start in [(1, datetime(2024, 3, 1)), (3, datetime(2024, 1, 1)), (12, datetime(2023, 4, 1))]:
        assert market_history(db, 'Test', months=months)['points'] == reference(rows, start, end)
    assert market_history(db, 'Test', months=3)['points'] == [
        {'month': '2024-01', 'median_rent_pln': 4000, 'median_per_m2': 80, 'sample_size': 2, 'is_demo': True},
        {'month': '2024-02', 'median_rent_pln': 3750.5, 'median_per_m2': 55, 'sample_size': 2, 'is_demo': True}]
    assert market_history(db, 'absent')['points'] == []
    assert market_summary(db, 'absent')['median_rent_pln'] is None
    assert market_summary(db, 'Test')['homes'] == 3


def test_merge_split_observations_retained(db, monkeypatch):
    from realtoruch.identity_review import merge, split, MergeBody, SplitBody
    populate(db)
    monkeypatch.setattr(query, 'now', lambda: datetime(2024, 3, 1, 12))
    from realtoruch.ingest import PROPERTY_FIELDS
    db.get(Listing, 'b').is_demo = True
    for source in db.scalars(select(SourceListing)):
        home = db.get(Listing, source.listing_id)
        source.data = {field: getattr(home, field) for field in PROPERTY_FIELDS}
    db.flush()
    before = db.scalar(select(func.count()).select_from(Observation))
    assert market_history(db, 'Test', months=3)['points'][1]['sample_size'] == 2
    merge('b', MergeBody(target_id='a', reason='fixture correction'), moderator='test', session=db)
    assert market_history(db, 'Test', months=3)['points'][1]['sample_size'] == 1
    split('a', SplitBody(source_id='b1', reason='fixture correction'), moderator='test', session=db)
    assert market_history(db, 'Test', months=3)['points'][1]['sample_size'] == 2
    assert db.scalar(select(func.count()).select_from(Observation)) == before


def test_timestamp_ties_are_deterministic(db, monkeypatch):
    populate(db)
    monkeypatch.setattr(query, 'now', lambda: datetime(2024, 3, 1, 12))
    db.get(Observation, '3').status = 'active'
    db.add(Observation(id='tie', listing_id='a', source_listing_id='a2',
                       observed_at=datetime(2024, 2, 29, 13), rent_pln=3101,
                       status='active', changed=True))
    db.flush()
    # Both are active at the same instant; descending source ID selects a2.
    point = market_history(db, 'Test', months=3)['points'][1]
    assert point['median_rent_pln'] == 3551
