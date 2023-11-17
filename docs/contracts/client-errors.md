# Client error recovery

The shared request helper keeps `SessionError.kind` and `status` compatible and adds a bounded `code` plus `fields` array. UI consumers may branch on the code. Do not parse displayed messages, echo backend error text or treat a business failure as an authentication failure.

| Code | Recovery |
| --- | --- |
| version_conflict | Keep local draft; review current advert version before retrying. |
| verification_required | Verify account email, then retry the same action. |
| rate_limited | Wait before another request; no automatic repeated submission. |
| search_limit | Remove an unwanted saved search before creating another. |
| advert_limit | Explain the current limit without silently discarding adverts. |
| profile_required | Complete advertiser profile. |
| profile_type_conflict | Withdraw published adverts before changing advertiser type. |
| conversation_blocked | Disable sending and explain the conversation state. |
| message_retry_conflict | Refresh context before another send; preserve existing retry identity. |
| appeal_pending | Show the existing pending review state. |
| already_reviewed | Refresh the moderation queue. |
| moderation_hidden | Direct the owner to the appeal workflow. |
| validation | Associate the allowlisted fields with local field labels. |
| unknown | Show the safe generic message and an appropriate retry. |

Mappings require a known route, HTTP status and exact known server detail, except generic rate-limit status and allowlisted validation field names. Arbitrary `detail`, validator `msg`/`input`, URLs and IDs are never copied into UI messages. Field names are bounded to 20 unique known identifiers. Array-element errors resolve to their known parent field.

Authentication refresh, replay rejection, account-generation fencing and safe link messages are unchanged. Q26 separately adds purpose-token handling for account export; an export reauthentication failure must not be mistaken for an invalid login session.
