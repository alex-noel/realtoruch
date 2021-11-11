"""Revisioned search projection. SQL remains authoritative; ES is eventually consistent."""
import contextlib
import fcntl
import hashlib
import json
import logging
import os
import tempfile
from uuid import uuid4

from sqlalchemy import or_, select, text, update

from .models import Listing, Outbox, SearchRevision, now
from .query import serialize_many

log = logging.getLogger(__name__)
MAX_DOCS = 100
MAX_BYTES = 5 * 1024 * 1024


def queue_listing(session, listing_id):
    """Increment under the transaction's row lock and add independent durable work."""
    revision = session.execute(
        update(SearchRevision).where(SearchRevision.listing_id == listing_id)
        .values(revision=SearchRevision.revision + 1).returning(SearchRevision.revision)
    ).scalar_one_or_none()
    if revision is None:
        session.add(SearchRevision(listing_id=listing_id, revision=1))
    pending = session.scalars(select(Outbox).where(
        Outbox.listing_id == listing_id, Outbox.delivered_at.is_(None))).all()
    if pending:
        for event in pending:
            event.last_index_status = None
    else:
        session.add(Outbox(listing_id=listing_id))


@contextlib.contextmanager
def rebuild_gate(factory, exclusive=False):
    """Coordinate indexers and rebuilds without holding canonical row locks."""
    with factory() as session:
        engine = session.get_bind()
    if engine.dialect.name == 'postgresql':
        # Session-level advisory locks cover the network phase, on a dedicated connection.
        with engine.connect() as conn:
            suffix = '' if exclusive else '_shared'
            conn.execute(text(f'SELECT pg_advisory_lock{suffix}(728325105)'))
            try:
                yield
            finally:
                conn.execute(text(f'SELECT pg_advisory_unlock{suffix}(728325105)'))
    else:
        name = hashlib.sha256(str(engine.url).encode()).hexdigest()
        path = os.path.join(tempfile.gettempdir(), 'realtoruch-index-' + name + '.lock')
        with open(path, 'a') as gate:
            fcntl.flock(gate, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(gate, fcntl.LOCK_UN)

def create_physical_index(client, index):
    if client.head(f"/{index}").status_code == 200:
        return
    properties = {
        key: {"type": "keyword"}
        for key in (
            "id",
            "city",
            "district",
            "region",
            "status",
            "advertiser_type",
            "property_type",
            "amenities",
        )
    }
    properties.update({key: {"type": "text"} for key in ("title", "description", "address")})
    properties.update(
        {
            key: {"type": "integer"}
            for key in ("rent_pln", "fees_pln", "commission_pln", "rooms", "risk_score")
        }
    )
    properties.update(
        {"area_m2": {"type": "float"}, "location": {"type": "geo_point"}, "first_seen": {"type": "date"}}
    )
    response = client.put(
        f"/{index}",
        json={
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {"dynamic": False, "properties": properties},
        },
    )
    if response.status_code != 400 or "resource_already_exists_exception" not in response.text:
        response.raise_for_status()


def ensure_index(client, alias, *, allow_legacy=False):
    if client.head(f'/{alias}').status_code == 200:
        return
    # Adopt the legacy physical index without deleting it.
    legacy = alias == 'rentals-search' and client.head('/rentals-v1').status_code == 200
    if legacy and not allow_legacy:
        raise RuntimeError('Legacy search index requires rebuild-index before versioned indexing')
    physical = 'rentals-v1' if legacy else alias + '-initial'
    create_physical_index(client, physical)
    response = client.post('/_aliases', json={'actions': [{'add': {'index': physical, 'alias': alias, 'is_write_index': True}}]})
    response.raise_for_status()


def snapshot(session, ids):
    """Lock revision rows briefly so every DTO and version share a committed state."""
    if not ids:
        return []
    from .ingest import lock_identity
    lock_identity(session, shared=True)
    revisions = dict(session.execute(
        select(SearchRevision.listing_id, SearchRevision.revision)
        .where(SearchRevision.listing_id.in_(ids)).order_by(SearchRevision.listing_id).with_for_update()
    ).all())
    listings = session.scalars(select(Listing).where(Listing.id.in_(revisions))).all()
    documents = serialize_many(session, listings)
    result = []
    for listing, document in zip(listings, documents):
        if listing.hidden:
            document['status'] = 'inactive'
        if listing.lat is not None and listing.lon is not None:
            document['location'] = {'lat': listing.lat, 'lon': listing.lon}
        result.append((listing.id, revisions[listing.id], document))
    return result


def encode_document(listing_id, revision, document, index):
    action = {'index': {'_index': index, '_id': listing_id, 'version': revision, 'version_type': 'external'}}
    return (json.dumps(action, separators=(',', ':')) + '\n' + json.dumps(document, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def batches(docs, index):
    batch, size = [], 0
    for listing_id, revision, document in docs:
        lines = encode_document(listing_id, revision, document, index)
        if len(lines) > MAX_BYTES:
            log.error('search document exceeds bulk limit listing_id=%s', listing_id)
            continue
        if batch and (len(batch) == MAX_DOCS or size + len(lines) > MAX_BYTES):
            yield batch
            batch, size = [], 0
        batch.append((listing_id, revision, lines))
        size += len(lines)
    if batch:
        yield batch


def send_bulk(client, docs, index):
    outcomes = {listing_id: (413, False) for listing_id, revision, document in docs
                if len(encode_document(listing_id, revision, document, index)) > MAX_BYTES}
    for batch in batches(docs, index):
        response = client.post('/_bulk', content=b''.join(item[2] for item in batch), headers={'Content-Type': 'application/x-ndjson'})
        response.raise_for_status()
        items = response.json()['items']
        if len(items) != len(batch):
            raise RuntimeError('Elasticsearch returned an incomplete bulk response')
        for (listing_id, revision, _), item in zip(batch, items):
            result = item['index']
            status = result['status']
            if 200 <= status < 300:
                outcomes[listing_id] = (status, True)
            elif status == 409:
                stored = client.get(f'/{index}/_doc/{listing_id}')
                if stored.status_code == 200 and stored.json().get('_version', 0) >= revision:
                    outcomes[listing_id] = (status, True)
                else:
                    outcomes[listing_id] = (status, False)
                    log.warning('unverified index conflict listing_id=%s', listing_id)
            else:
                outcomes[listing_id] = (status, False)
                log.warning('index failure listing_id=%s status=%s', listing_id, status)
    return outcomes


def index_once(factory, client_factory, alias):
    with rebuild_gate(factory):
        with client_factory() as client:
            ensure_index(client, alias)
            with factory.begin() as session:
                events = session.execute(select(Outbox.id, Outbox.listing_id).where(
                    Outbox.delivered_at.is_(None), or_(Outbox.last_index_status.is_(None), Outbox.last_index_status.not_in((400, 413)))).order_by(Outbox.created_at, Outbox.id).limit(MAX_DOCS)).all()
                docs = snapshot(session, sorted({event.listing_id for event in events}))
            outcomes = send_bulk(client, docs, alias)
            with factory.begin() as session:
                from .ingest import lock_identity
                lock_identity(session, shared=True)
                sent = {listing_id: revision for listing_id, revision, _ in docs if listing_id in outcomes}
                current = dict(session.execute(select(SearchRevision.listing_id, SearchRevision.revision)
                    .where(SearchRevision.listing_id.in_(sent)).order_by(SearchRevision.listing_id).with_for_update()).all())
                eligible = [event for event in events if event.listing_id in sent
                            and current.get(event.listing_id) == sent[event.listing_id]]
                acknowledged = 0
                for event in eligible:
                    status, success = outcomes[event.listing_id]
                    values = {"last_index_status": status}
                    if success:
                        values["delivered_at"] = now()
                    result = session.execute(update(Outbox).where(Outbox.id == event.id,
                        Outbox.delivered_at.is_(None)).values(**values))
                    if success:
                        acknowledged += result.rowcount
            return acknowledged


def rebuild(factory, client_factory, alias):
    """Rebuild under the exclusive gate; writers continue queuing until indexers resume."""
    with rebuild_gate(factory, exclusive=True), client_factory() as client:
        ensure_index(client, alias, allow_legacy=True)
        candidate = alias + '-rebuild-' + uuid4().hex[:12]
        create_physical_index(client, candidate)
        with factory() as session:
            ids = session.scalars(select(Listing.id).order_by(Listing.id)).all()
        expected = {}
        for offset in range(0, len(ids), MAX_DOCS):
            with factory.begin() as session:
                docs = snapshot(session, ids[offset:offset + MAX_DOCS])
            outcomes = send_bulk(client, docs, candidate)
            if len(outcomes) != len(docs) or not all(ok for _, ok in outcomes.values()):
                raise RuntimeError('Rebuild indexing failed; alias unchanged')
            expected.update({listing_id: revision for listing_id, revision, _ in docs})
        client.post(f'/{candidate}/_refresh').raise_for_status()
        count = client.get(f'/{candidate}/_count').json()['count']
        if count != len(ids) or len(expected) != len(ids):
            raise RuntimeError('Rebuild count mismatch; alias unchanged')
        for listing_id in list(expected)[::max(1, len(expected) // 20)]:
            response = client.get(f'/{candidate}/_doc/{listing_id}')
            response.raise_for_status()
            if response.json()['_version'] != expected[listing_id]:
                raise RuntimeError('Rebuild version mismatch; alias unchanged')
        old = client.get(f'/_alias/{alias}')
        old.raise_for_status()
        actions = [{'remove': {'index': index, 'alias': alias}} for index in old.json()]
        actions.append({'add': {'index': candidate, 'alias': alias, 'is_write_index': True}})
        client.post('/_aliases', json={'actions': actions}).raise_for_status()
        return candidate
