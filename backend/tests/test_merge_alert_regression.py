"""Merge evaluates real pending alerts before silently baselining correction effects."""
from datetime import timedelta
import os
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_service_integration import pg_engine  # noqa: F401

from realtoruch.alerts import baseline_search, process_alerts
from realtoruch.db import Base
from realtoruch.identity_review import MergeBody, merge
from realtoruch.ingest import ingest
from realtoruch.models import AlertEvent, Favorite, Listing, Notification, SavedSearch, SearchMatch


@pytest.fixture(params=['sqlite', 'postgresql'])
def db(request, tmp_path):
    if request.param == 'postgresql':
        if not os.environ.get('TEST_POSTGRES_URL'):
            pytest.skip('Requires disposable PostgreSQL')
        engine = request.getfixturevalue('pg_engine')
    else:
        engine = create_engine(f'sqlite:///{tmp_path / "merge.db"}', connect_args={'timeout': 10})
        Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    if request.param == 'sqlite':
        engine.dispose()


def homes(db, record):
    target_raw = record.model_copy(update={'rent_pln': 4500, 'address': 'Target 1/1'})
    source_raw = record.model_copy(update={'source': 'gratka', 'external_id': 'source',
        'address': 'Different 2/1', 'rent_pln': 4200,
        'observed_at': record.observed_at + timedelta(minutes=2)})
    target = ingest(db, target_raw)['listing_id']
    source = ingest(db, source_raw)['listing_id']
    assert target != source
    process_alerts(db)
    db.commit()
    return target_raw, source_raw, target, source


def correct(db, target, source):
    merge(source, MergeBody(target_id=target, reason='Reviewed as one canonical apartment.'), 'moderator', db)


@pytest.mark.parametrize('pending_title', [False, True])
def test_merge_price_change_and_future_title_are_silent(db, record, pending_title):
    raw, other, target, source = homes(db, record)
    db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
    # A search that has not been matched must be silently baselined after correction.
    db.add(SavedSearch(id='search', user_id='u', name='cheap', city_key='',
                       filters={'city': raw.city, 'max_price': 4300}))
    db.flush()
    if pending_title:
        ingest(db, raw.model_copy(update={'title': 'Only title changed',
            'observed_at': raw.observed_at + timedelta(minutes=1)}))
    db.commit()
    correct(db, target, source)
    assert db.get(Listing, target).rent_pln == 4200
    assert db.get(Favorite, ('u', target)).price_floor == 4200
    assert db.get(SearchMatch, ('search', target)) is not None
    process_alerts(db)
    assert db.scalars(select(Notification)).all() == []
    ingest(db, other.model_copy(update={'title': 'Later title only',
        'observed_at': other.observed_at + timedelta(minutes=1)}))
    process_alerts(db)
    assert db.scalars(select(Notification)).all() == []


def test_pending_genuine_drop_survives_and_historical_floor_never_increases(db, record):
    raw, other, target, source = homes(db, record)
    db.add_all([Favorite(user_id='u', listing_id=target, price_floor=4500),
                Favorite(user_id='old-low', listing_id=target, price_floor=3900)])
    db.flush()
    ingest(db, raw.model_copy(update={'rent_pln': 4300,
        'observed_at': raw.observed_at + timedelta(minutes=1)}))
    db.commit()
    correct(db, target, source)
    process_alerts(db)
    notifications = db.scalars(select(Notification).order_by(Notification.user_id)).all()
    assert [(n.user_id, n.kind, n.previous_rent_pln, n.rent_pln) for n in notifications] == [('u', 'price_drop', 4500, 4300)]
    assert db.get(Favorite, ('u', target)).price_floor == 4200
    assert db.get(Favorite, ('old-low', target)).price_floor == 3900
    ingest(db, other.model_copy(update={'rent_pln': 4100,
        'observed_at': other.observed_at + timedelta(minutes=1)}))
    process_alerts(db)
    assert sorted((n.user_id, n.previous_rent_pln, n.rent_pln) for n in db.scalars(select(Notification))) == [
        ('u', 4200, 4100), ('u', 4500, 4300)]


def test_coalesces_only_newly_evaluated_drop_and_match(db, record):
    from realtoruch.models import EmailDelivery, EmailSubscription, now
    raw = record.model_copy(update={'rent_pln': 4500, 'address': 'Target 1/1'})
    target = ingest(db, raw)['listing_id']
    process_alerts(db)
    db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
    db.add(EmailSubscription(user_id='u', email='synthetic@example.test', enabled=True,
                             verified_at=now(), unsubscribe_token='synthetic-token'))
    search = SavedSearch(id='search', user_id='u', name='area', city_key='', filters={'city': raw.city})
    db.add(search)
    db.flush()
    baseline_search(db, search)
    ingest(db, raw.model_copy(update={'rent_pln': 4200,
        'observed_at': raw.observed_at + timedelta(minutes=1)}))
    source = ingest(db, raw.model_copy(update={'source': 'gratka', 'external_id': 'source',
        'address': 'Different 2/1', 'rent_pln': 4200,
        'observed_at': raw.observed_at + timedelta(minutes=2)}))['listing_id']
    db.commit()
    correct(db, target, source)
    process_alerts(db)
    notifications = db.scalars(select(Notification)).all()
    assert [(n.kind, n.rent_pln) for n in notifications] == [('price_drop', 4200)]
    assert [item.notification_id for item in db.scalars(select(EmailDelivery))] == [notifications[0].id]


def test_existing_cross_kind_history_is_not_deleted(db, record):
    raw, other, target, source = homes(db, record)
    db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
    db.add(Notification(user_id='u', listing_id=source, kind='new_match', dedupe_key='historic',
                        title='Prior match', rent_pln=4200))
    db.flush()
    ingest(db, raw.model_copy(update={'rent_pln': 4200,
        'observed_at': raw.observed_at + timedelta(minutes=1)}))
    db.commit()
    correct(db, target, source)
    assert sorted(n.kind for n in db.scalars(select(Notification))) == ['new_match', 'price_drop']


def test_hidden_active_card_does_not_create_notifications(db, record):
    raw = record.model_copy(update={'rent_pln': 4500})
    home = ingest(db, raw)['listing_id']
    process_alerts(db)
    db.add(Favorite(user_id='u', listing_id=home, price_floor=4500))
    db.flush()
    ingest(db, raw.model_copy(update={'rent_pln': 4200,
        'observed_at': raw.observed_at + timedelta(minutes=1)}))
    db.get(Listing, home).hidden = True  # Legacy inconsistent active/hidden state.
    db.flush()
    process_alerts(db)
    assert db.scalars(select(Notification)).all() == []
    assert db.get(Favorite, ('u', home)).price_floor == 4500


def test_large_pending_backlog_is_recoverable_without_partial_merge(db, record):
    from fastapi import HTTPException
    raw, other, target, source = homes(db, record)
    db.add_all([AlertEvent(listing_id=target) for _ in range(101)])
    db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
    db.commit()
    with pytest.raises(HTTPException) as error:
        correct(db, target, source)
    assert error.value.status_code == 409
    db.rollback()
    assert len(db.scalars(select(AlertEvent).where(AlertEvent.processed_at.is_(None))).all()) == 101
    assert db.get(Listing, target).rent_pln == 4500
    assert db.get(Favorite, ('u', target)).price_floor == 4500
    assert db.scalars(select(Notification)).all() == []
    assert process_alerts(db) == 100
    db.commit()
    correct(db, target, source)
    assert db.get(Listing, target).rent_pln == 4200


def test_incomplete_scoped_drain_rolls_back(db, record, monkeypatch):
    from fastapi import HTTPException
    from realtoruch import identity_review
    from realtoruch.models import EmailDelivery, EmailSubscription, now
    raw, other, target, source = homes(db, record)
    db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
    db.add(EmailSubscription(user_id='u', email='synthetic@example.test', enabled=True,
                             verified_at=now(), unsubscribe_token='synthetic-token'))
    db.flush()
    ingest(db, raw.model_copy(update={'rent_pln': 4300,
        'observed_at': raw.observed_at + timedelta(minutes=1)}))
    db.flush()
    ingest(db, other.model_copy(update={'title': 'Pending on source',
        'observed_at': other.observed_at + timedelta(minutes=1)}))
    db.commit()
    real = identity_review.process_alerts
    def partial(session, **kwargs):
        kwargs['limit'] = 1
        processed = real(session, **kwargs)
        assert session.get(Favorite, ('u', target)).price_floor == 4300
        assert len(session.scalars(select(Notification)).all()) == 1
        assert len(session.scalars(select(EmailDelivery)).all()) == 1
        return processed
    monkeypatch.setattr(identity_review, 'process_alerts', partial)
    with pytest.raises(HTTPException) as error:
        correct(db, target, source)
    assert error.value.status_code == 409
    db.rollback()
    assert len(db.scalars(select(AlertEvent).where(AlertEvent.processed_at.is_(None))).all()) == 2
    assert db.get(Listing, target).rent_pln == 4300
    assert db.get(Favorite, ('u', target)).price_floor == 4500
    assert db.scalars(select(Notification)).all() == []
    assert db.scalars(select(EmailDelivery)).all() == []


def test_scoped_drain_does_not_consume_unrelated_events(db, record):
    raw, other, target, source = homes(db, record)
    unrelated = ingest(db, raw.model_copy(update={'external_id': 'unrelated', 'address': 'Third 3/1'}))['listing_id']
    ingest(db, raw.model_copy(update={'title': 'Pending',
        'observed_at': raw.observed_at + timedelta(minutes=1)}))
    db.commit()
    correct(db, target, source)
    remaining = db.scalars(select(AlertEvent).where(AlertEvent.processed_at.is_(None))).all()
    assert len(remaining) == 1 and remaining[0].listing_id == unrelated


def test_evaluator_waits_for_merge_before_reading_state(db, record, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import event
    from realtoruch import identity_review
    raw, other, target, source = homes(db, record)
    db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
    ingest(db, raw.model_copy(update={'title': 'Pending',
        'observed_at': raw.observed_at + timedelta(minutes=1)}))
    db.commit()
    engine = db.get_bind()
    entered, release, attempting, finished = (threading.Event() for _ in range(4))
    local = threading.local()
    real = identity_review.recompute_listing
    def pause(*args, **kwargs):
        entered.set()
        assert release.wait(15)
        return real(*args, **kwargs)
    def before_execute(conn, cursor, statement, parameters, context, executemany):
        if getattr(local, 'evaluator', False) and (
            'BEGIN IMMEDIATE' in statement or 'pg_advisory_xact_lock_shared' in statement
        ):
            attempting.set()
    monkeypatch.setattr(identity_review, 'recompute_listing', pause)
    event.listen(engine, 'before_cursor_execute', before_execute)
    def correct_in_thread():
        with Session(engine) as session:
            correct(session, target, source)
    def evaluate_in_thread():
        local.evaluator = True
        try:
            with Session(engine) as session:
                process_alerts(session)
                session.commit()
        finally:
            finished.set()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            merger = pool.submit(correct_in_thread)
            assert entered.wait(15)
            evaluator = pool.submit(evaluate_in_thread)
            assert attempting.wait(15)
            assert not finished.wait(.2)
            release.set()
            merger.result(timeout=15)
            evaluator.result(timeout=15)
    finally:
        release.set()
        event.remove(engine, 'before_cursor_execute', before_execute)
    db.expire_all()
    assert db.get(Favorite, ('u', target)).price_floor == 4200
    assert db.scalars(select(Notification)).all() == []


def test_split_silently_baselines_retained_home_then_alerts_real_drop(db, record):
    from realtoruch.identity_review import SplitBody, split
    from realtoruch.models import SourceListing
    low = record.model_copy(update={'rent_pln': 4200, 'address': 'Low 1/1'})
    high = record.model_copy(update={'source': 'gratka', 'external_id': 'high',
        'rent_pln': 4500, 'address': 'Different 2/1',
        'observed_at': low.observed_at + timedelta(minutes=2)})
    original = ingest(db, low)['listing_id']
    duplicate = ingest(db, high)['listing_id']
    high_source = db.scalar(select(SourceListing.id).where(SourceListing.listing_id == duplicate))
    process_alerts(db)
    db.commit()
    correct(db, original, duplicate)
    assert db.get(Listing, original).rent_pln == 4500
    db.add(Favorite(user_id='u', listing_id=original, price_floor=4500))
    db.add(Favorite(user_id='old-low', listing_id=original, price_floor=3900))
    db.add(SavedSearch(id='cheap', user_id='u', name='cheap', city_key='',
                       filters={'city': low.city, 'max_price': 4300}))
    db.commit()
    new = split(original, SplitBody(source_id=high_source, reason='Review found separate apartments.'),
                'moderator', db)['listing_id']
    assert db.get(Listing, original).rent_pln == 4200
    assert db.get(Favorite, ('u', original)).price_floor == 4200
    assert db.get(Favorite, ('old-low', original)).price_floor == 3900
    assert db.get(Favorite, ('u', new)).price_floor == 4500
    assert db.get(SearchMatch, ('cheap', original)) is not None
    ingest(db, low.model_copy(update={'title': 'Title only',
        'observed_at': low.observed_at + timedelta(minutes=3)}))
    process_alerts(db)
    assert db.scalars(select(Notification)).all() == []
    ingest(db, low.model_copy(update={'rent_pln': 4100,
        'observed_at': low.observed_at + timedelta(minutes=4)}))
    process_alerts(db)
    assert [(n.user_id, n.kind, n.previous_rent_pln, n.rent_pln) for n in db.scalars(select(Notification))] == [
        ('u', 'price_drop', 4200, 4100)]


def test_split_inactive_source_keeps_same_price_relist_quiet(db, record):
    from realtoruch.identity_review import SplitBody, split
    from realtoruch.models import SourceListing
    active = record.model_copy(update={'rent_pln': 4500, 'address': 'Active 1/1'})
    inactive = record.model_copy(update={'source': 'gratka', 'external_id': 'inactive',
        'rent_pln': 4200, 'status': 'inactive', 'address': 'Other 2/1',
        'observed_at': active.observed_at + timedelta(minutes=1)})
    home = ingest(db, active)['listing_id']
    other = ingest(db, inactive)['listing_id']
    source = db.scalar(select(SourceListing.id).where(SourceListing.listing_id == other))
    process_alerts(db)
    db.commit()
    correct(db, home, other)
    db.add(Favorite(user_id='u', listing_id=home, price_floor=4500))
    db.commit()
    separated = split(home, SplitBody(source_id=source, reason='Distinct apartments confirmed.'),
                      'moderator', db)['listing_id']
    assert db.get(Listing, separated).status == 'inactive'
    assert db.get(Favorite, ('u', separated)).price_floor == 4200
    ingest(db, inactive.model_copy(update={'status': 'active',
        'observed_at': inactive.observed_at + timedelta(minutes=1)}))
    process_alerts(db)
    assert db.scalars(select(Notification)).all() == []


def test_corrected_search_baselines_stream_across_batches(db, record):
    raw, other, target, source = homes(db, record)
    db.add_all([SavedSearch(id=f'search-{i:03}', user_id=f'u{i}', name='cheap', city_key='',
                            filters={'city': raw.city, 'max_price': 4300}) for i in range(150)])
    db.commit()
    correct(db, target, source)
    assert len(db.scalars(select(SearchMatch).where(SearchMatch.listing_id == target)).all()) == 150
    assert db.scalars(select(Notification)).all() == []


def test_hidden_merge_restore_is_silent_but_later_real_drop_alerts(db, record):
    from realtoruch.ingest import recompute_listing
    raw, other, target, source = homes(db, record)
    db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
    db.get(Listing, target).hidden = True
    db.get(Listing, target).status = 'inactive'
    db.commit()
    correct(db, target, source)
    home = db.get(Listing, target)
    assert home.hidden and home.status == 'inactive' and home.rent_pln == 4200
    assert db.get(Favorite, ('u', target)).price_floor == 4200
    home.hidden = False
    recompute_listing(db, home)
    process_alerts(db)
    assert db.scalars(select(Notification)).all() == []
    ingest(db, other.model_copy(update={'rent_pln': 4100,
        'observed_at': other.observed_at + timedelta(minutes=1)}))
    process_alerts(db)
    assert [(n.kind, n.previous_rent_pln, n.rent_pln) for n in db.scalars(select(Notification))] == [
        ('price_drop', 4200, 4100)]


@pytest.mark.skipif(not os.environ.get('TEST_POSTGRES_URL'), reason='Requires disposable PostgreSQL')
def test_busy_evaluator_returns_409_without_changes(pg_engine, record):
    from fastapi import HTTPException
    from sqlalchemy import text
    with Session(pg_engine, expire_on_commit=False) as db:
        raw, other, target, source = homes(db, record)
        db.add(Favorite(user_id='u', listing_id=target, price_floor=4500))
        ingest(db, raw.model_copy(update={'rent_pln': 4300,
            'observed_at': raw.observed_at + timedelta(minutes=1)}))
        db.commit()
        with pg_engine.begin() as blocker:
            blocker.execute(text('SELECT pg_advisory_xact_lock(761994031)'))
            with pytest.raises(HTTPException) as error:
                correct(db, target, source)
            assert error.value.status_code == 409
            db.rollback()
            assert len(db.scalars(select(AlertEvent).where(AlertEvent.processed_at.is_(None))).all()) == 1
            assert db.get(Favorite, ('u', target)).price_floor == 4500
            assert db.get(Listing, target).rent_pln == 4300
            assert db.scalars(select(Notification)).all() == []
        correct(db, target, source)
        assert [(n.kind, n.previous_rent_pln, n.rent_pln) for n in db.scalars(select(Notification))] == [
            ('price_drop', 4500, 4300)]
