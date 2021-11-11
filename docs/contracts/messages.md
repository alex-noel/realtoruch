# Private messages API (v1)

All inbox and thread actions require an authenticated participant. A missing or inaccessible conversation returns `404` (`Conversation not found`); another account cannot page, acknowledge, send to, or block a thread it does not belong to. An inbox only contains the caller’s conversations. No login email, participant ID, or private profile data is returned.

## Inbox

`GET /v1/me/conversations?limit=50&cursor=<next_cursor>` returns conversations from newest to oldest by `(updated_at, id)` in descending order. Omit `cursor` for the first page. `limit` is optional and accepts integers from 1 through 50 (default 50). Existing callers can still read `items` with no query parameters. Use the new cursor to retrieve any further pages.

```json
{
  "items": [
    {
      "id": "00000000-0000-4000-8000-000000000001",
      "title": "Apartment near the park",
      "listing_id": null,
      "unread_count": 2,
      "blocked": false,
      "can_unblock": false,
      "updated_at": "2026-11-11T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

`next_cursor` is `null` at the end. Otherwise it encodes the last returned row’s tuple. The token is unpadded URL-safe base64 of ASCII `v1|<UTC ISO 8601 timestamp with six fractional digits and Z>|<lowercase UUID>`, e.g. the encoding of `v1|2026-11-11T10:00:00.000000Z|00000000-0000-4000-8000-000000000001`. Treat it as opaque and pass it back unchanged. The server validates the version, encoding, canonical timestamp and ID; invalid values return `422` (`Invalid conversation cursor` for invalid encoding or contents). The token is a position, not an authorization credential. Every page applies the caller’s participant filter. It still works if the boundary row moves or disappears.

A static inbox has no gaps or duplicates. A new message can move an older conversation ahead of a cursor you already hold, so later pages are not a snapshot. Refresh the first page to see recent activity. Replaying an identical send or acknowledging reads does not reorder the inbox.

## Thread messages

`GET /v1/me/conversations/{conversation_id}?before=<next_cursor>&limit=50` selects the most recent messages strictly before the cursor in `(created_at, id)` order. It returns those messages oldest first, including when timestamps tie. `before` is the existing message-ID cursor; omit it for the newest page. `limit` is optional and accepts integers from 1 through 50 (default 50). An invalid or foreign message ID returns `422` (`Invalid message cursor`). `next_cursor` is the ID of the oldest returned item when another page exists, otherwise `null`.

```json
{
  "id": "00000000-0000-4000-8000-000000000001",
  "items": [
    {
      "id": "00000000-0000-4000-8000-000000000002",
      "body": "Is the apartment still available?",
      "mine": false,
      "created_at": "2026-11-11T10:00:00Z"
    }
  ],
  "next_cursor": null,
  "blocked": false,
  "can_unblock": false
}
```

## Acknowledge displayed messages

`PUT /v1/me/conversations/{conversation_id}/read` takes this JSON body and returns `200 {"read": true}`:

```json
{"last_message_id": "00000000-0000-4000-8000-000000000002"}
```

T17 should send the highest **displayed incoming** message ID for the selected thread. The server accepts any message in that conversation as a boundary and only advances the caller’s watermark to the greater of its existing watermark and that message’s `(created_at, id)`. An older or repeated acknowledgement succeeds without moving it backward. An unread message is one sent by the other participant with a tuple strictly greater than the caller’s watermark; with no watermark every incoming message is unread. Sending a message does not acknowledge incoming messages. A missing/foreign message ID or malformed JSON body returns `422` without changing the watermark. A message received after the displayed boundary stays unread, even if the wall clock ties or regresses.

Prefer the server’s page order. If the client combines or reorders pages, compare UTC timestamps at microsecond precision before comparing IDs. The existing timestamp strings omit the fractional part when it is zero, and JavaScript `Date` only preserves milliseconds.

For older v1 clients, a request with no body still returns `{"read": true}` and acknowledges through the latest message visible when the server processes the request, or does nothing for an empty thread. This legacy action may acknowledge a message that arrived after the client’s last fetch. A supplied JSON object must include `last_message_id`; `{}` and `null` do not request legacy mode. Timestamp-only state from older deployments remains inclusive at the stored timestamp until an acknowledgement advances it.

## Start, reply and block

`POST /v1/adverts/{advert_id}/conversations` (start) and `POST /v1/me/conversations/{conversation_id}/messages` (reply) keep `{"body":"...","client_id":"..."}` and their existing `201` responses. A client ID is scoped to a sender and conversation. Use the same ID when retrying the same text: the normalized stored text determines equality. If the same ID is reused for different text, the API returns `409 {"detail":"Client message ID already used with different text"}` and leaves the original unchanged. A matching retry returns the original message and does not count against send limits, even if the conversation was blocked after the original send. A new message to a blocked thread returns `403`; normal sends require verified email and are limited to 20 per minute per sender (`429` when exceeded). Starting a conversation still requires an available advert and returns the same conversation for that advert and renter. Only the participant who blocked a thread may unblock it.
