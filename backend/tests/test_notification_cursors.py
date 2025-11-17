from datetime import datetime, timedelta

from realtoruch.ingest import ingest
from realtoruch.models import Notification


def exercise_notification_cursor(session, record, client, auth_client):
    def account(email):
        result = auth_client.post('/v1/auth/register', json={'email': email, 'password': 'local-cursor-password-123'}).json()
        return result['user']['id'], {'Authorization': 'Bearer ' + result['access_token']}

    owner, headers = account('cursor-owner@example.test')
    other, other_headers = account('cursor-other@example.test')
    listing_id = ingest(session, record)['listing_id']
    timestamp = datetime(2026, 1, 2, 12)
    def add(identifier, user=owner, created=timestamp):
        session.add(Notification(id=identifier, user_id=user, listing_id=listing_id,
            dedupe_key=identifier, kind='new_match', title='Synthetic', rent_pln=1000, created_at=created))
        session.commit()
    for identifier in ['b', 'd', 'f', 'h', 'j']:
        add(identifier)
    add('foreign', other, timestamp - timedelta(days=1))
    first = client.get('/v1/me/notifications', headers=headers, params={'page_size': 2}).json()
    assert [row['id'] for row in first['items']] == ['b', 'd']
    assert first['has_more'] and first['next_cursor']
    # Newer insertions must not displace the continuation, even at equal timestamps.
    add('a'); add('e'); add('newer', created=timestamp + timedelta(seconds=1))
    second = client.get('/v1/me/notifications', headers=headers, params={'page_size': 2, 'cursor': first['next_cursor']}).json()
    assert [row['id'] for row in second['items']] == ['e', 'f']
    third = client.get('/v1/me/notifications', headers=headers, params={'page_size': 2, 'cursor': second['next_cursor']}).json()
    assert [row['id'] for row in third['items']] == ['h', 'j']
    assert third['has_more'] is False and third['next_cursor'] is None
    assert client.get('/v1/me/notifications', headers=other_headers, params={'cursor': first['next_cursor']}).json()['items'][0]['id'] == 'foreign'
    assert client.get('/v1/me/notifications', headers=headers, params={'cursor': 'invalid!'}).status_code == 400
    assert client.put('/v1/me/notifications/b/read', headers=other_headers).status_code == 404
    assert [n['id'] for n in client.get('/v1/me/notifications', headers=headers, params={'page': 2, 'page_size': 2}).json()['items']] == ['b', 'd']


def test_cursor_pagination_and_ownership(session, record, client, auth_client):
    exercise_notification_cursor(session, record, client, auth_client)
