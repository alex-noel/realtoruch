import json
from pydantic import HttpUrl
from datetime import timedelta

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from realtoruch.db import Base
from realtoruch.ingest import ingest
from realtoruch.indexing import batches, index_once
from realtoruch.migrations import upgrade_local
from realtoruch.models import Favorite, Outbox, SearchRevision


class Reply:
    def __init__(self, status, data=None):
        self.status_code, self.data = status, data or {}
        self.text = ''
    def json(self): return self.data
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)


class Mixed:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def head(self, path): return Reply(200)
    def post(self, path, content=None, **kw):
        lines = content.decode().splitlines()
        statuses = [201, 429, 400, 409]
        return Reply(200, {'items': [{'index': {'status': status}} for status in statuses[:len(lines)//2]]})
    def get(self, path): return Reply(200, {'_version': 999})


def test_mixed_bulk_acknowledges_only_success_and_verified_conflict(tmp_path, record):
    engine = create_engine('sqlite:///' + str(tmp_path / 'test.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        for i in range(4):
            ingest(session, record.model_copy(update={'external_id': str(i), 'url': HttpUrl(f'https://example.com/{i}'), 'address': f'Address {i}', 'area_m2': 60 + i * 10}))
    assert index_once(factory, Mixed, 'test') == 2
    with factory() as session:
        pending = session.scalars(select(Outbox).where(Outbox.delivered_at.is_(None))).all()
        assert sorted(event.last_index_status for event in pending) == [400, 429]
    engine.dispose()


def test_legacy_sqlite_null_favorite_floor_upgrades_and_repeats(tmp_path, record):
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False).begin() as session:
        home = ingest(session, record)['listing_id']
        session.add(Favorite(user_id='legacy', listing_id=home, price_floor=None))
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE search_revisions'))
        conn.execute(text('ALTER TABLE outbox DROP COLUMN last_index_status'))
    upgrade_local(engine)
    upgrade_local(engine)
    with sessionmaker(engine)() as session:
        assert session.get(Favorite, ('legacy', home)).price_floor == record.rent_pln
        assert session.get(SearchRevision, home).revision == 1
        assert session.get(Favorite, ('legacy', home)).user_id == 'legacy'
    engine.dispose()


def test_bulk_bounds():
    docs = [(str(i), 1, {'id': str(i), 'title': 'x' * 100}) for i in range(201)]
    groups = list(batches(docs, 'index'))
    assert [len(group) for group in groups] == [100, 100, 1]
    assert all(sum(len(item[2]) for item in group) <= 5 * 1024 * 1024 for group in groups)


def test_profile_edit_revises_public_payload_and_excludes_secrets(session, record):
    from realtoruch.marketplace import ProfileBody, save_profile
    from realtoruch.models import Advert, AdvertiserProfile
    from realtoruch.query import serialize_many
    from realtoruch.models import Listing
    listing_id = ingest(session, record)['listing_id']
    session.add(AdvertiserProfile(user_id='owner', name='Before', kind='private', description='profile'))
    session.flush()
    session.add(Advert(id='advert', user_id='owner', listing_id=listing_id,
                       draft={'secret': 'draft-secret'}, state='published'))
    session.commit()
    old = session.get(SearchRevision, listing_id).revision
    save_profile(ProfileBody(name='After', kind='private', description='other'), claims={'sub': 'owner'}, session=session)
    session.expire_all()
    assert session.get(SearchRevision, listing_id).revision > old
    payload = json.dumps(serialize_many(session, [session.get(Listing, listing_id)]))
    assert 'After' in payload
    for secret in ('draft-secret', '700100101', 'phone_hash', 'email', 'password'):
        assert secret not in payload


def test_oversized_document_is_recorded_without_starving_later_work(tmp_path, record):
    from realtoruch.models import Listing, now
    from realtoruch.indexing import MAX_BYTES
    engine = create_engine('sqlite:///' + str(tmp_path / 'large.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        for i in range(101):
            listing = Listing(id=f'{i:03}', title='x' * MAX_BYTES if i == 0 else 'ok',
                description='', city='Warszawa', district='', region='', address='', area_m2=55,
                rooms=2, rent_pln=4200, advertiser_type='private', property_type='apartment',
                status='active', amenities=[], images=[], risk_flags=[], risk_score=0, is_demo=False)
            session.add(listing)
            session.flush()
            session.add(SearchRevision(listing_id=listing.id, revision=1))
            session.add(Outbox(listing_id=listing.id, created_at=now() + timedelta(seconds=i)))
    class Success(Mixed):
        def post(self, path, content=None, **kw):
            count = len(content.decode().splitlines()) // 2
            return Reply(200, {'items': [{'index': {'status': 201}} for _ in range(count)]})
    assert index_once(factory, Success, 'test') == 99
    assert index_once(factory, Success, 'test') == 1
    with factory() as session:
        pending = session.scalars(select(Outbox).where(Outbox.delivered_at.is_(None))).all()
        assert len(pending) == 1 and pending[0].last_index_status == 413
    engine.dispose()
