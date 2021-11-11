"""Run T27's synthetic recovery profile with real application routes and workers."""

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from pathlib import Path
from threading import Event
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from realtoruch import api, auth, auth_jobs, db
from realtoruch.alerts import process_alerts
from realtoruch.email_alerts import dispatch_email
from realtoruch.indexing import index_once
from realtoruch.migrations import load_registry
from realtoruch.models import (
    AccountClosure,
    Advert,
    AdvertiserProfile,
    AlertEvent,
    Conversation,
    EmailDelivery,
    EmailSubscription,
    Favorite,
    Message,
    Notification,
    Outbox,
    SavedSearch,
    SeenPrice,
    now,
)
from realtoruch.schemas import RawListing
from realtoruch.settings import Settings, get_settings

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from restore_manifest import (
    KINDS,
    PG_ROLE,
    RUNS,
    Postgres,
    Run,
    SQLite,
    backup,
    digest,
    invoke,
    read_json,
    restore,
    sql_id,
    status,
    utc,
    write_json,
)

PASSWORD = 'restore-drill-synthetic-password'
MESSAGE = 'Private viewing question from the soon-to-close account.'
KEEP = 'restore-keep@example.test'
ERASE = 'restore-erase@example.test'
FILTERS = {'city': 'Kraków', 'property_type': 'apartment', 'max_price': 5000, 'max_price_exclusive': True,
           'min_area': 50, 'advertiser': 'private'}


def request(client, method, path, code=200, **kwargs):
    response = client.request(method, path, **kwargs)
    assert response.status_code == code, (method, path.split('?')[0], response.status_code)
    return response.json()


def messages(directory):
    return [BytesParser(policy=policy.default).parsebytes(path.read_bytes()) for path in directory.glob('*.eml')]


def link(directory, address, action):
    pattern = re.compile(r'#' + action + r'=([A-Za-z0-9_-]+)')
    matches = [match.group(1) for item in messages(directory) if str(item['To']) == address
               if (match := pattern.search(item.get_content()))]
    assert len(matches) == 1
    return matches[0]


@contextmanager
def application(backend, monkeypatch, *, restored):
    identify = backend.target if restored else backend.source
    if backend.name == 'sqlite':
        if not restored:
            for kind in KINDS:
                identify(kind).touch(mode=0o600, exist_ok=False)
        urls = {kind: 'sqlite:///' + str(identify(kind)) for kind in KINDS}
    else:
        urls = {kind: URL.create('postgresql+psycopg', username=PG_ROLE, password=backend.password,
                                host='127.0.0.1', port=backend.port, database=identify(kind)).render_as_string(hide_password=False)
                for kind in KINDS}
    engines = {kind: db.make_engine(url) for kind, url in urls.items()}
    factory = {kind: sessionmaker(engine, expire_on_commit=False) for kind, engine in engines.items()}
    try:
        with monkeypatch.context() as patch:
            patch.setattr(db, 'engine', engines['rentals'])
            patch.setattr(db, 'Session', factory['rentals'])
            patch.setattr(auth, 'auth_engine', engines['auth'])
            patch.setattr(auth, 'AuthSession', factory['auth'])
            patch.setattr(auth_jobs, 'AuthSession', factory['auth'])
            patch.setattr(api.app.state, 'validate_claims', auth.validate_claims, raising=False)
            # Restore assertions run without startup DDL that could repair a bad backup.
            if not restored:
                db.init_db()
                auth.init_auth_db()
            if backend.name == 'postgres':
                for kind, engine in engines.items():
                    with engine.connect() as conn:
                        assert conn.execute(text('SELECT current_database(), current_user, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user')).one() == (
                            identify(kind), PG_ROLE, False, False, False)
            with closing(TestClient(api.app)) as rentals, closing(TestClient(auth.app)) as identity:
                yield rentals, identity, factory
    finally:
        for engine in engines.values():
            engine.dispose()


def seed(backend, monkeypatch, directory):
    with application(backend, monkeypatch, restored=False) as (rentals, identity, factory):
        accounts = [request(identity, 'POST', '/v1/auth/register', 201, json={'email': address, 'password': PASSWORD})
                    for address in (KEEP, ERASE)]
        assert auth_jobs.process_jobs() == 2
        for address in (KEEP, ERASE):
            request(identity, 'POST', '/v1/auth/verify-email', json={'token': link(directory, address, 'verify_account')})
        keep_id, erased_id = [account['user']['id'] for account in accounts]
        keep, erased = [{'Authorization': 'Bearer ' + account['access_token']} for account in accounts]
        assert request(identity, 'GET', '/v1/auth/me', headers=erased)['id'] == erased_id
        get_settings().moderator_user_ids = keep_id
        adverts = []
        for i, headers in enumerate((keep, erased)):
            request(rentals, 'PUT', '/v1/me/advertiser', headers=headers,
                    json={'name': f'Synthetic owner {i}', 'kind': 'private'})
            draft = request(rentals, 'POST', '/v1/me/adverts', 201, headers=headers,
                            json={'title': f'Synthetic owned apartment {i}', 'description': 'Synthetic owned home for backup verification.',
                                  'city': 'Kraków', 'district': 'Podgórze', 'address': f'Własna {20 + i}',
                                  'lat': 50.05, 'lon': 19.95, 'area_m2': 56, 'rooms': 2, 'rent_pln': 4600 + i * 100, 'commission_pln': 0})
            adverts.append(request(rentals, 'POST', f"/v1/me/adverts/{draft['id']}/publish", headers=headers,
                                   json={'version': draft['version']}))
        owned, withdrawn = adverts
        conversation = request(rentals, 'POST', f"/v1/adverts/{owned['id']}/conversations", 201, headers=erased,
                               json={'client_id': 'synthetic-first-message', 'body': MESSAGE})['id']
        assert request(rentals, 'GET', '/v1/me/conversations', headers=keep)['items'][0]['unread_count'] == 1
        # Two sources with deliberately different addresses are initially separate;
        # use the real moderator merge to create an old canonical route.
        prev = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=35)
        latest = now() - timedelta(minutes=2)
        original = RawListing(source='otodom', external_id='delisted', url='https://example.test/delisted',
                              title='Imported fixture home', city='Kraków', district='Krowodrza', address='Importowa 6',
                              area_m2=55, rooms=2, rent_pln=4500, advertiser_type='private',
                              phone='700100101', observed_at=prev)
        alternate = RawListing.model_validate({**original.model_dump(), 'source': 'gratka', 'external_id': 'old-alias',
                                                'url': 'https://example.test/alias', 'address': 'Druga 40',
                                                'phone': None, 'observed_at': prev + timedelta(hours=1)})

        def observe(listing):
            return request(rentals, 'POST', '/internal/observations',
                           headers={'X-Internal-Key': get_settings().internal_api_key},
                           json=listing.model_dump(mode='json'))['listing_id']

        home, alias = observe(original), observe(alternate)
        assert home != alias
        request(rentals, 'POST', f'/v1/moderation/listings/{alias}/merge', headers=keep,
                json={'target_id': home, 'reason': 'Synthetic duplicate reviewed with equivalent floor plan.'})
        for headers in (keep, erased):
            request(rentals, 'PUT', f'/v1/me/favorites/{alias}', headers=headers)
        request(rentals, 'PUT', f'/v1/me/seen/{alias}', headers=keep)
        request(rentals, 'PUT', f'/v1/me/seen/{owned["listing_id"]}', headers=erased)
        assert observe(original.model_copy(update={'rent_pln': 4200, 'observed_at': latest})) == home
        for listing in (original, alternate):
            assert observe(listing.model_copy(update={'rent_pln': 4200, 'status': 'inactive',
                                                     'observed_at': latest + timedelta(seconds=1)})) == home
        with factory['rentals'].begin() as session:
            assert process_alerts(session) > 0
        for headers in (keep, erased):
            request(rentals, 'PUT', '/v1/me/email-notifications', headers=headers, json={'enabled': True})
        assert dispatch_email(factory['rentals']) == 2
        for address in (KEEP, ERASE):
            request(rentals, 'POST', '/v1/notifications/email/confirm', json={'token': link(directory, address, 'confirm_email')})
        search_keep = request(rentals, 'POST', '/v1/me/searches', 201, headers=keep,
                              json={'name': 'Saved active fixture search', 'filters': FILTERS})['id']
        search_erased = request(rentals, 'POST', '/v1/me/searches', 201, headers=erased,
                                json={'name': 'Private erased search', 'filters': {**FILTERS, 'city': 'Warszawa'}})['id']
        assert request(rentals, 'GET', '/v1/me/notifications', headers=keep)['items'] == []
        fresh = observe(RawListing.model_validate({**original.model_dump(), 'external_id': 'new-match',
                                                  'url': 'https://example.test/new', 'title': 'New synthetic match',
                                                  'address': 'Nowa 35', 'phone': None, 'rent_pln': 4300,
                                                  'observed_at': latest + timedelta(seconds=2)}))
        assert fresh != home
        with factory['rentals'].begin() as session:
            assert process_alerts(session) > 0
            delivery = session.scalar(select(EmailDelivery).where(EmailDelivery.status == 'pending'))
            assert delivery and delivery.user_id == keep_id
            delivery_id = delivery.id
        # Leave a separate alert evaluator job pending without adding another matching home.
        assert observe(original.model_copy(update={'rent_pln': 4150, 'status': 'inactive',
                                                   'observed_at': latest + timedelta(seconds=3)})) == home
        request(identity, 'DELETE', '/v1/auth/account', 202, headers=erased, json={'password': PASSWORD})
        with factory['auth']() as session:
            job = session.scalar(select(auth.AuthJob).where(auth.AuthJob.user_id == erased_id,
                                                            auth.AuthJob.kind == 'delete'))
            assert job and job.status == 'pending' and job.attempts == 0
            job_id = job.id
        return {'home': home, 'alias': alias, 'fresh': fresh, 'owned': owned, 'withdrawn': withdrawn,
                'conversation': conversation, 'keep': keep, 'erased': erased, 'keep_id': keep_id, 'erased_id': erased_id,
                'delivery': delivery_id, 'deletion': job_id, 'search_keep': search_keep, 'search_erased': search_erased,
                'erased_refresh': accounts[1]['refresh_token'], 'month': prev.strftime('%Y-%m')}


@contextmanager
def projection(run):
    alias = 't27_' + run.owner
    url = os.environ.get('TEST_ELASTICSEARCH_URL')
    if url and os.environ.get('VERIFY_RUN_ID'):
        run_id = os.environ['VERIFY_RUN_ID']
        assert re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', run_id)
        service = 'realtoruch-t01-' + run_id + '-es'
        label = invoke('docker', 'inspect', '-f', '{{index .Config.Labels "realtoruch.verification"}}', service)
        port = invoke('docker', 'port', service, '9200/tcp').decode().strip()
        assert label.strip() == b'true' and re.fullmatch(r'127\.0\.0\.1:\d+', port) and url == 'http://' + port
        with httpx.Client(base_url=url, timeout=10, trust_env=False) as client:
            assert client.head('/' + alias + '-initial').status_code == 404
            try:
                yield alias, lambda: httpx.Client(base_url=url, timeout=10, trust_env=False), client, 'real-loopback-elasticsearch'
            finally:
                assert client.delete('/' + alias + '-initial').status_code in (200, 404)
        return
    docs = {}

    def transport(req):
        if req.method == 'HEAD':
            return httpx.Response(200)
        if req.method == 'POST' and req.url.path == '/_bulk':
            lines = req.content.splitlines()
            assert len(lines) % 2 == 0
            results = []
            for action, doc in zip(lines[::2], lines[1::2]):
                index = json.loads(action)['index']
                assert index['_index'] == alias and index['version_type'] == 'external'
                version = index['version']
                key = index['_id']
                assert version > docs.get(key, (0,))[0]
                docs[key] = (version, json.loads(doc))
                results.append({'index': {'status': 201}})
            return httpx.Response(200, json={'items': results})
        if req.method == 'GET' and req.url.path.startswith('/' + alias + '/_doc/'):
            version, doc = docs[req.url.path.rsplit('/', 1)[1]]
            return httpx.Response(200, json={'_version': version, '_source': doc})
        raise AssertionError('Unexpected search request')

    def client():
        return httpx.Client(base_url='http://search.example.test', transport=httpx.MockTransport(transport), trust_env=False)

    with client() as lookup:
        yield alias, client, lookup, 'in-process-bulk-transport'


def verify_application(backend, run, monkeypatch, expected):
    keep, erased, home, alias, fresh = (expected[key] for key in ('keep', 'erased', 'home', 'alias', 'fresh'))
    keep_id, erased_id = expected['keep_id'], expected['erased_id']
    owned, withdrawn, conversation = (expected[key] for key in ('owned', 'withdrawn', 'conversation'))
    with application(backend, monkeypatch, restored=True) as (rentals, identity, factory):
        assert request(identity, 'GET', '/v1/auth/me', headers=keep)['id'] == keep_id
        request(identity, 'GET', '/v1/auth/me', 401, headers=erased)
        request(identity, 'POST', '/v1/auth/login', 401, json={'email': ERASE, 'password': PASSWORD})
        request(identity, 'POST', '/v1/auth/refresh', 401, json={'refresh_token': expected['erased_refresh']})
        request(rentals, 'PUT', f'/v1/me/favorites/{home}', 401, headers=erased)
        request(rentals, 'DELETE', f"/v1/me/searches/{expected['search_erased']}", 404, headers=keep)
        request(rentals, 'PUT', f"/v1/me/adverts/{withdrawn['id']}", 404, headers=keep,
                json={'version': withdrawn['version'], 'advert': withdrawn['advert']})
        detail = request(rentals, 'GET', '/v1/listings/' + alias)
        assert detail == request(rentals, 'GET', '/v1/listings/' + home)
        assert (detail['id'], detail['status'], detail['rent_pln']) == (home, 'inactive', 4150)
        prices = {(row['rent_pln'], row['status']) for row in detail['history']}
        assert {(4500, 'active'), (4200, 'active'), (4200, 'inactive')} <= prices
        assert 'phone_hash' not in json.dumps(detail) and '700100101' not in json.dumps(detail)
        market = request(rentals, 'GET', '/v1/market/history', params={'city': 'Kraków', 'district': 'Krowodrza', 'months': 3})
        previous = next(point for point in market['points'] if point['month'] == expected['month'])
        assert previous['median_rent_pln'] == 4500 and previous['sample_size'] == 1
        discovered = request(rentals, 'GET', '/v1/listings', params=FILTERS)
        assert {item['id'] for item in discovered['items']} == {owned['listing_id'], withdrawn['listing_id'], fresh}
        assert all(value not in json.dumps(discovered) for value in (MESSAGE, ERASE, KEEP, 'phone_hash', 'password_hash'))
        saved = request(rentals, 'GET', '/v1/me/favorites', headers=keep)['items']
        assert [(item['id'], item['status']) for item in saved] == [(home, 'inactive')]
        assert request(rentals, 'POST', '/v1/me/listing-state', headers=keep,
                       json={'listing_ids': [home, owned['listing_id']]})['seen_ids'] == [home]
        assert [item['id'] for item in request(rentals, 'GET', '/v1/me/searches', headers=keep)['items']] == [expected['search_keep']]
        assert [(row['id'], row['unread_count']) for row in request(rentals, 'GET', '/v1/me/conversations', headers=keep)['items']] == [(conversation, 1)]
        assert [row['body'] for row in request(rentals, 'GET', '/v1/me/conversations/' + conversation,
                                              headers=keep)['items']] == [MESSAGE]
        request(rentals, 'GET', '/v1/me/conversations/' + conversation, 401)
        request(rentals, 'GET', '/v1/me/conversations/' + conversation, 401, headers=erased)
        before = request(rentals, 'GET', '/v1/me/notifications', headers=keep)
        assert before['unread_count'] == 1
        assert [(row['kind'], row['listing_id']) for row in before['items']] == [('new_match', fresh)]
        assert request(rentals, 'GET', '/v1/me/email-notifications', headers=keep)['enabled']
        mail = Path(get_settings().email_preview_directory)
        assert not list(mail.glob('*.eml'))
        with factory['auth']() as session:
            job = session.get(auth.AuthJob, expected['deletion'])
            assert job.status == 'pending' and job.attempts == 0
        with factory['rentals']() as session:
            assert session.get(EmailDelivery, expected['delivery']).status == 'pending'
            assert session.get(AdvertiserProfile, erased_id) and session.get(EmailSubscription, erased_id)
            assert not session.get(AccountClosure, erased_id)
            pending = session.scalars(select(Outbox).where(Outbox.delivered_at.is_(None))).all()
            assert {home, fresh} <= {row.listing_id for row in pending}
            pending_count = len(pending)

        entered, release = Event(), Event()

        def stale_writer():
            # An identity authorized before deletion is paused before entering the actual write route.
            entered.set()
            assert release.wait(30)
            with factory['rentals']() as session, pytest.raises(HTTPException) as failure:
                api.save_favorite(fresh, erased_id, session)
            assert failure.value.status_code == 401 and failure.value.detail == 'Account is closed'

        def erase(uid):
            assert uid == erased_id
            assert request(rentals, 'DELETE', f'/internal/accounts/{uid}',
                           headers={'X-Internal-Key': get_settings().internal_api_key}) == {'erased': True}

        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting = executor.submit(stale_writer)
            try:
                assert entered.wait(10)
                assert auth_jobs.process_jobs(eraser=erase) == 1
            finally:
                release.set()
            waiting.result(timeout=10)
        assert auth_jobs.process_jobs(eraser=erase) == 0
        erase(erased_id)  # The worker could have crashed after the endpoint commit and before its ack.
        request(rentals, 'PUT', f'/v1/me/favorites/{home}', 401, headers=erased)
        request(identity, 'POST', '/v1/auth/refresh', 401, json={'refresh_token': expected['erased_refresh']})
        assert request(rentals, 'GET', '/v1/me/conversations', headers=keep)['items'] == []
        request(rentals, 'GET', '/v1/me/conversations/' + conversation, 404, headers=keep)
        assert request(rentals, 'GET', '/v1/listings/' + withdrawn['listing_id'])['title'] == 'Withdrawn listing'
        assert request(rentals, 'GET', '/v1/listings/' + withdrawn['listing_id'])['status'] == 'inactive'
        assert request(rentals, 'GET', '/v1/listings/' + alias)['id'] == home
        with factory['auth']() as session:
            job = session.get(auth.AuthJob, expected['deletion'])
            assert (job.status, job.attempts, job.secret) == ('done', 1, None)
            assert not session.get(auth.User, erased_id) and session.get(auth.User, keep_id)
            assert not session.scalar(select(auth.LoginSession).where(auth.LoginSession.user_id == erased_id))
            assert not session.scalar(select(auth.AccountToken).where(auth.AccountToken.user_id == erased_id))
        with factory['rentals'].begin() as session:
            assert session.get(AccountClosure, erased_id)
            assert not session.get(Conversation, conversation) and not session.get(Advert, withdrawn['id'])
            for model in (AdvertiserProfile, EmailSubscription, EmailDelivery, Favorite, SavedSearch, SeenPrice, Notification):
                assert not session.scalar(select(model).where(model.user_id == erased_id))
            assert not session.scalar(select(Message).where(Message.sender_id == erased_id))
            assert session.get(Favorite, (keep_id, home)) and session.get(Advert, owned['id'])
            assert session.scalar(select(AlertEvent).where(AlertEvent.processed_at.is_(None)))
            assert process_alerts(session) > 0
        with factory['rentals'].begin() as session:
            assert process_alerts(session) == 0
        with projection(run) as (index, client, lookup, transport):
            assert index_once(factory['rentals'], client, index) == pending_count
            assert index_once(factory['rentals'], client, index) == 0
            for listing_id, state in ((home, 'inactive'), (fresh, 'active'), (withdrawn['listing_id'], 'inactive')):
                indexed = lookup.get(f'/{index}/_doc/{listing_id}').json()['_source']
                assert indexed['id'] == listing_id and indexed['status'] == state
                assert all(value not in json.dumps(indexed) for value in (MESSAGE, ERASE, KEEP, 'phone_hash'))
        assert dispatch_email(factory['rentals']) == 1
        sent = messages(mail)
        assert len(sent) == 1 and str(sent[0]['To']) == KEEP and '4,300 PLN' in sent[0].get_content()
        assert sent[0]['Message-ID'] == f"<{expected['delivery']}@realtoruch.notifications>"
        file = mail / (expected['delivery'] + '.eml')
        assert file.stat().st_mode & 0o777 == 0o600
        sent_digest = digest(file)
        assert dispatch_email(factory['rentals']) == 0
        assert len(messages(mail)) == 1 and digest(file) == sent_digest
        assert request(rentals, 'GET', '/v1/me/notifications', headers=keep) == before
        with factory['rentals']() as session:
            assert session.get(EmailDelivery, expected['delivery']).status == 'sent'
            assert not session.scalar(select(Outbox).where(Outbox.delivered_at.is_(None)))
    return {'search_transport': transport, 'index_acknowledged': pending_count, 'logical_rental_mail': 1,
            'erasure_completed': 1, 'repeat_rental_mail': 0, 'repeat_index': 0, 'repeat_erasure': 0}


@contextmanager
def sentinel(run, backend):
    """An unrelated database, never passed to the recovery code."""
    if backend.name == 'sqlite':
        import sqlite3
        path = run.root / 'independent.sqlite3'
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("CREATE TABLE sentinel(value TEXT)")
            connection.execute("INSERT INTO sentinel VALUES ('untouched')")
        original = digest(path)

        def check():
            assert digest(path) == original

        yield check
        check()
    else:
        name = 't27_unrelated_' + uuid4().hex[:16]
        backend.create(name)
        backend.query(name, "CREATE TABLE sentinel(value TEXT); INSERT INTO sentinel VALUES ('untouched')")
        fingerprint = backend.catalog()[name]

        def check():
            assert backend.catalog()[name] == fingerprint
            assert backend.query(name, 'SELECT value FROM sentinel') == 'untouched'

        try:
            yield check
            check()
        finally:
            # This test fixture created this DB independently and knows its OID.
            assert backend.catalog()[name] == fingerprint
            backend.query('postgres', 'DROP DATABASE ' + sql_id(name))


def missing(backend, *kinds):
    if backend.name == 'sqlite':
        return all(not backend.target(kind).exists() for kind in kinds)
    catalog = backend.catalog()
    return all(backend.target(kind) not in catalog for kind in kinds)


def verify_failures(run, backend, schemas, monkeypatch):
    original = read_json(run.manifest)
    artifact = run.root / original['databases']['auth']['file']
    contents = artifact.read_bytes()
    failures = []
    started = time.monotonic()
    with sentinel(run, backend) as unchanged:
        for name in ('wrong-digest', 'wrong-format', 'wrong-engine-version', 'wrong-schema', 'corrupt', 'truncated'):
            edited = json.loads(json.dumps(original))
            entry = edited['databases']['auth']
            if name == 'wrong-digest':
                entry['sha256'] = '0' * 64
            elif name == 'wrong-format':
                edited['format'] += 1
            elif name == 'wrong-engine-version':
                edited['engine_version'] = '0'
            elif name == 'wrong-schema':
                entry['schema']['999'] = '0' * 64
            else:
                artifact.write_bytes(contents[:len(contents) // 2] if name == 'truncated' else b'invalid database')
                entry.update(sha256=digest(artifact), bytes=artifact.stat().st_size)
            write_json(run.manifest, edited)
            assert status(lambda: restore(run, backend, schemas)) == 1, name
            assert missing(backend, *KINDS), name
            unchanged()
            failures.append(name)
            artifact.write_bytes(contents)
            write_json(run.manifest, original)

        if backend.name == 'sqlite':
            backend.destination.write_text('unrelated destination, not a directory')
            original_blocker = digest(backend.destination)
            assert status(lambda: restore(run, backend, schemas)) == 1
            assert status(backend.cleanup) == 1
            assert digest(backend.destination) == original_blocker
            backend.destination.unlink()
        else:
            # Real server refusal to connect to the new destination (also safe when tests run as root).
            create = backend.create

            def disallow_connections(name):
                create(name)
                backend.query('postgres', f'ALTER DATABASE {sql_id(name)} ALLOW_CONNECTIONS false')

            with monkeypatch.context() as patch:
                patch.setattr(backend, 'create', disallow_connections)
                assert status(lambda: restore(run, backend, schemas)) == 1
            backend.cleanup()
        assert missing(backend, *KINDS)
        unchanged()
        failures.append('unwritable-destination')

        def interrupt(kind):
            assert kind == 'rentals'
            raise KeyboardInterrupt

        assert status(lambda: restore(run, backend, schemas, checkpoint=interrupt)) == 1
        assert not missing(backend, 'rentals') and missing(backend, 'auth')
        unchanged()
        recovered = type(backend)(Run(run.root, run.engine, new=False))
        # Place an unrecognized resource at an expected target name. Cleanup must preflight
        # every candidate and leave even the owned partial rental restore in place on refusal.
        if backend.name == 'sqlite':
            foreign = backend.target('auth')
            foreign.write_bytes((run.root / 'independent.sqlite3').read_bytes())
            stamp = digest(foreign)
            assert status(recovered.cleanup) == 1
            assert digest(foreign) == stamp
            foreign.unlink()
        else:
            foreign = backend.target('auth')
            backend.create(foreign)
            stamp = backend.catalog()[foreign]
            backend.query(foreign, "CREATE TABLE sentinel(value TEXT); INSERT INTO sentinel VALUES ('untouched')")
            assert status(lambda: restore(run, backend, schemas)) == 1
            assert status(recovered.cleanup) == 1
            assert backend.catalog()[foreign] == stamp
            assert backend.query(foreign, 'SELECT value FROM sentinel') == 'untouched'
            backend.query('postgres', 'DROP DATABASE ' + sql_id(foreign))
        assert not missing(backend, 'rentals')
        recovered.cleanup()
        assert missing(backend, *KINDS)
        unchanged()
        failures.extend(('interrupted-after-first-database', 'unrecognized-destination-preserved'))
    return {'negative_cases': failures, 'negative_seconds': round(time.monotonic() - started, 3),
            'unrelated_database_preserved': True}


@pytest.mark.parametrize('engine', ['sqlite', 'postgres'])
def test_restore_contract(engine, monkeypatch):
    if engine == 'postgres' and not (os.environ.get('TEST_POSTGRES_URL') or os.environ.get('T27_ENGINE') == 'postgres'):
        pytest.skip('PostgreSQL restore requires the isolated service or CLI profile')
    root = Path(os.environ['T27_RUN_ROOT']) if 'T27_RUN_ROOT' in os.environ else RUNS / ('test-' + uuid4().hex[:16])
    run = Run(root, engine, new=True)
    backend = {'sqlite': SQLite, 'postgres': Postgres}[engine](run)
    settings = get_settings()
    for key in Settings.model_fields:
        # BaseSettings still reads environment even with no .env; these fixtures never inherit endpoints/secrets.
        monkeypatch.setattr(settings, key, Settings.model_fields[key].default)
    monkeypatch.setattr(settings, 'email_delivery_mode', 'file')
    monkeypatch.setattr(settings, 'email_preview_directory', str(run.root / 'seed-mail'))
    monkeypatch.setattr(settings, 'auth_request_limit_per_minute', 1000)
    monkeypatch.setattr(settings, 'request_limit_per_minute', 1000)
    with run.lock():
        try:
            if engine == 'postgres':
                backend.start()
            expected = seed(backend, monkeypatch, Path(settings.email_preview_directory))
            quiesced = utc()  # Both source application clients/pools stopped; no writers or workers remain.
            schemas = {kind: backend.inventory(backend.source(kind), kind)['schema'] for kind in KINDS}
            if engine == 'postgres':
                assert {kind: sorted(schemas[kind]) for kind in KINDS} == {
                    kind: [entry['version'] for entry in entries] for kind, entries in load_registry().items()}
            else:
                assert schemas['rentals'] and schemas['auth']
            manifest = backup(run, backend, quiesced_at=quiesced)
            failure_evidence = verify_failures(run, backend, schemas, monkeypatch)
            monkeypatch.setattr(settings, 'email_preview_directory', str(run.root / 'restored-mail'))
            rto = time.monotonic()
            timings = restore(run, backend, schemas)
            app_evidence = verify_application(backend, run, monkeypatch, expected)
            report = {**timings, **failure_evidence, **app_evidence, 'engine': engine, 'run_id': run.root.name,
                      'application_recovery_seconds': round(time.monotonic() - rto, 3),
                      'backup_seconds': manifest['backup_seconds'], 'quiesced_at': quiesced, 'verified_at': utc(),
                      'fixture_accounts': manifest['databases']['auth']['rows']['users'],
                      'fixture_private_messages': manifest['databases']['rentals']['rows']['messages'],
                      'fixture_canonical_aliases': manifest['databases']['rentals']['rows']['listing_aliases'],
                      'schema_versions': {kind: sorted(schemas[kind]) for kind in KINDS},
                      'committed_fixture_writes_lost': 0, 'backup_start': manifest['backup_start'],
                      'backup_end': manifest['backup_end'], 'engine_version': manifest['engine_version']}
            assert report['fixture_accounts'] == 2 and report['fixture_private_messages'] == 1
            assert report['fixture_canonical_aliases'] == 1
            write_json(run.root / 'report.json', report)
        finally:
            # Keep the private evidence, but never leave successful restored destinations active.
            if engine == 'postgres' and (backend.container or (root / 'postgres.cid').exists()):
                backend.dispose()
            elif engine == 'sqlite':
                backend.cleanup()
