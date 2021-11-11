"""Local-only synthetic observations, invoked by the browser runner as a child process."""
import json
import os
import sys
from pathlib import Path

run_dir = Path(os.environ['E2E_RUN_DIR']).resolve()
expected = (run_dir / 'fixture-token').read_text()
if (os.environ.get('ENVIRONMENT') == 'production' or not expected or
        os.environ.get('E2E_RUN_TOKEN') != expected or
        os.environ.get('DATABASE_URL') != f'sqlite:///{run_dir}/rentals.db' or
        not run_dir.is_relative_to(Path(__file__).resolve().parents[3] / '.local/verification/T18')):
    raise SystemExit('Fixture isolation check failed')

from sqlalchemy import select
from realtoruch.db import Session
from realtoruch.ingest import ingest
from realtoruch.models import SourceListing, Notification, Favorite, SeenPrice, AlertEvent
from realtoruch.auth import AuthSession, User
from realtoruch.schemas import RawListing

action, profile = sys.argv[1:]
if action not in {'baseline', 'new', 'delist', 'relist', 'drop', 'state', 'boundaries', 'duplicate'} or profile not in {'desktop', 'mobile'}:
    raise SystemExit('Invalid fixture action')
prefix = 't18-' + profile
if action == 'duplicate':
    from uuid import uuid4
    with AuthSession() as auth:
        user_id = auth.scalar(select(User.id).where(User.email == f'journey-{profile}@example.test'))
    with Session.begin() as session:
        original = session.scalar(select(Notification).where(Notification.user_id == user_id))
        if not original:
            raise SystemExit('Fault needs an existing notification')
        session.add(Notification(user_id=user_id, listing_id=original.listing_id, search_id=original.search_id,
            dedupe_key=uuid4().hex, kind=original.kind, title=original.title, rent_pln=original.rent_pln,
            previous_rent_pln=original.previous_rent_pln))
    print(json.dumps({'injected': True}))
    raise SystemExit(0)
if action == 'state':
    with AuthSession() as auth:
        user_id = auth.scalar(select(User.id).where(User.email == f'journey-{profile}@example.test'))
    with Session() as session:
        notices = session.scalars(select(Notification).where(Notification.user_id == user_id)).all()
        favorites = session.scalars(select(Favorite).where(Favorite.user_id == user_id)).all()
        seen = session.scalars(select(SeenPrice).where(SeenPrice.user_id == user_id)).all()
        print(json.dumps({'notices': [{'kind': n.kind, 'listing_id': n.listing_id} for n in notices],
                          'pending': len(session.scalars(select(AlertEvent).where(AlertEvent.processed_at.is_(None))).all()),
                          'favorites': [{'listing_id': f.listing_id, 'price_floor': f.price_floor} for f in favorites],
                          'seen': [{'listing_id': s.listing_id, 'rent_pln': s.rent_pln} for s in seen]}))
    raise SystemExit(0)
base = dict(source='otodom', url='https://fixture.example.test/', title='T18 synthetic home ' + profile,
    description='Fictional local-only apartment', city='Kraków', region='małopolskie',
    district='Krowodrza', address='Fixture 12/' + ('1' if profile == 'desktop' else '2'), area_m2=55, rooms=2, floor=2,
    fees_pln=500, commission_pln=0, advertiser_type='private', property_type='apartment',
    lat=50.0647, lon=19.945, phone='000000000', is_demo=True, images=[])
with Session.begin() as session:
    if action == 'boundaries':
        changes = [
            ('good', {'rent_pln': 4999, 'area_m2': 50.0}), ('price', {'rent_pln': 5000}), ('area', {'area_m2': 49.9}),
            ('agency', {'advertiser_type': 'agency'}), ('outside', {'lon': 20.2}),
            ('unknown', {'commission_pln': None}),
        ]
        ids = {}
        for index, (name, change) in enumerate(changes):
            data = {**base, 'title': f'T18 boundary {profile} {name}',
                    'address': f'Boundary {index + 1}/1', 'rent_pln': 4500, **change}
            ids[name] = ingest(session, RawListing(**data, external_id=prefix + '-boundary-' + name))['listing_id']
        session.commit()
        print(json.dumps(ids))
        raise SystemExit(0)
    if action == 'baseline':
        result = ingest(session, RawListing(**{**base, 'address': 'Baseline 99/' + ('1' if profile == 'desktop' else '2'),
            'title': 'T18 baseline ' + profile}, external_id=prefix + '-baseline', rent_pln=4700))
    else:
        for source in session.scalars(select(SourceListing).where(SourceListing.source == 'otodom',
            SourceListing.external_id.in_([prefix + '-new', prefix + '-relist', prefix + '-drop']))).all():
            if not source.external_id.endswith('-baseline') and source.status != 'inactive':
                ingest(session, RawListing(**base, external_id=source.external_id,
                    rent_pln=source.data['rent_pln'], status='inactive'))
        result = {'status': 'delisted'} if action == 'delist' else ingest(session, RawListing(
            **base, external_id=prefix + '-' + action, rent_pln=4200 if action == 'drop' else 4500))
    print(json.dumps(result))
