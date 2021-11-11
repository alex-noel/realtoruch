#!/usr/bin/env python3
"""Synthetic T25 operations on explicitly owned disposable Docker services."""
import argparse
from datetime import datetime, timedelta
import json
import subprocess
from urllib.parse import urlsplit

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from realtoruch.alerts import process_alerts
from realtoruch.indexing import ensure_index, index_once, send_bulk, snapshot
from realtoruch.ingest import ingest
from realtoruch.models import AlertEvent, Listing, Notification, Outbox, SearchRevision, SourceListing
from realtoruch.schemas import RawListing


def verify_owner(container, owner, service_port, host, port):
    if host not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Only loopback services are allowed')
    info = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    labels = info['Config'].get('Labels') or {}
    ports = info['NetworkSettings']['Ports'].get(f'{service_port}/tcp') or []
    if labels.get('realtoruch.t25.owner') != owner or not any(
        p['HostIp'] in ('127.0.0.1', '::1') and int(p['HostPort']) == port for p in ports
    ):
        raise ValueError('Service container owner or port mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['index', 'ingest', 'drain', 'plans'])
    parser.add_argument('--database', required=True)
    parser.add_argument('--elasticsearch', required=True)
    parser.add_argument('--pg-container', required=True)
    parser.add_argument('--es-container', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--remove-indexed', action='store_true', help='After drain, remove only the two synthetic batch documents')
    args = parser.parse_args()
    db = make_url(args.database)
    es = urlsplit(args.elasticsearch)
    if db.get_backend_name() != 'postgresql' or not (db.database or '').startswith('t25_'):
        parser.error('A t25_* PostgreSQL database is required')
    try:
        verify_owner(args.pg_container, args.owner, 5432, db.host, db.port)
        verify_owner(args.es_container, args.owner, 9200, es.hostname, es.port)
    except (ValueError, KeyError, IndexError, TypeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    engine = create_engine(args.database)
    factory = sessionmaker(engine, expire_on_commit=False)
    def client(): return httpx.Client(base_url=args.elasticsearch, timeout=30)
    if args.operation == 'index':
        with client() as es_client:
            ensure_index(es_client, 'rentals-search')
            with factory() as session:
                ids = list(session.scalars(select(Listing.id).order_by(Listing.id)))
            failures = 0
            for start in range(0, len(ids), 100):
                with factory() as session:
                    docs = snapshot(session, ids[start:start + 100])
                    outcomes = send_bulk(es_client, docs, 'rentals-search')
                    failures += sum(not success for _, success in outcomes.values())
            es_client.post('/rentals-search/_refresh').raise_for_status()
            print(json.dumps({'documents': len(ids), 'failures': failures}))
            if failures: raise SystemExit(1)
    elif args.operation == 'ingest':
        from time import perf_counter
        from sqlalchemy import event
        count = [0]
        @event.listens_for(engine, 'before_cursor_execute')
        def count_query(*_): count[0] += 1
        results = []
        for i in range(2):
            raw = RawListing(source='fixture_batch', external_id=f'batch-{i}',
                url=f'https://example.test/batch/{i}', title='Batch synthetic', description='',
                city='Kraków', district='D1', region='Bench', address=f'Batch {i}/1',
                lat=50.06, lon=19.96, area_m2=55, rooms=2, floor=2, rent_pln=4500,
                advertiser_type='private', observed_at=datetime(2026, 11, 2) + timedelta(seconds=i))
            start, old = perf_counter(), count[0]
            with factory.begin() as session: outcome = ingest(session, raw)
            results.append({'status': outcome['status'], 'match_reason': outcome['match_reason'],
                            'seconds': perf_counter()-start, 'queries': count[0]-old})
        print(json.dumps(results))
    elif args.operation == 'plans':
        from sqlalchemy import event
        from realtoruch.query import market_history, market_summary, search_db
        from realtoruch.schemas import SearchFilters
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                statements.append((statement, parameters))
        event.listen(engine, 'before_cursor_execute', capture)
        with factory() as session:
            search_db(session, SearchFilters(city='Kraków', max_price=5000, max_price_exclusive=True, min_area=50, advertiser='private'))
            market_summary(session, 'Kraków')
            market_history(session, 'Kraków')
        event.remove(engine, 'before_cursor_execute', capture)
        with engine.connect() as connection:
            for i, (statement, params) in enumerate(statements):
                print('\n--- statement', i, '---\n', statement)
                for row in connection.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS) ' + statement, params):
                    print(row[0])
    else:
        with factory.begin() as session: processed = process_alerts(session)
        indexed = index_once(factory, client, 'rentals-search')
        with factory() as session:
            ids = list(session.scalars(select(SourceListing.listing_id).where(SourceListing.source == 'fixture_batch').order_by(SourceListing.external_id)))
            revisions = {i: session.get(SearchRevision, i).revision for i in ids}
            counts = {'notifications': session.scalar(select(func.count()).select_from(Notification)),
                      'pending_alerts': session.scalar(select(func.count()).select_from(AlertEvent).where(AlertEvent.processed_at.is_(None))),
                      'pending_outbox': session.scalar(select(func.count()).select_from(Outbox).where(Outbox.delivered_at.is_(None)))}
        with client() as es_client:
            es_client.post('/rentals-search/_refresh').raise_for_status()
            docs = [es_client.get(f'/rentals-search/_doc/{i}').json() for i in ids]
            if args.remove_indexed:
                for listing_id in ids:
                    es_client.delete(f'/rentals-search/_doc/{listing_id}').raise_for_status()
                es_client.post('/rentals-search/_refresh').raise_for_status()
        consistent = len(ids) == 2 and all(d.get('found') and d['_version'] == revisions[i] and d['_source']['rent_pln'] == 4500 for i, d in zip(ids, docs))
        print(json.dumps({'events_processed': processed, 'indexed': indexed, **counts,
                          'documents_consistent': consistent}))
        if processed != 2 or indexed != 2 or counts != {'notifications': 4000, 'pending_alerts': 0, 'pending_outbox': 0} or not consistent:
            raise SystemExit(1)
    engine.dispose()


if __name__ == '__main__':
    main()
