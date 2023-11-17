# Q10 detail recovery

Implemented 2026-11-17. Detail state distinguishes loading, loaded, failed and unavailable while retaining summary data. Retry is inside the dialog. Contact and provider links are unavailable until current detail loads, and remain unavailable on inactive listings. Missing history during hydration is no longer treated as a successful empty observation set. Request IDs plus account generations fence late responses; signing in rehydrates an already open detail for the new session.

Node24 typecheck passed. Isolated run `q10-detail-20261117`: 2/2 desktop/mobile cases for 503/retry, 404, hidden contact/history while loading, closing A, opening B and resolving A late. No live provider calls. Existing session/account-switch coverage will run on the integrated candidate. Independent review of the account boundary remains pending.
