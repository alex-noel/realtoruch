# Q25 Account and device recovery

Implemented independent identity/device loading, refresh and retry, local revocation pending/error feedback, current-device labels, verification refresh on link completion/app focus, sign-out retry, and separated password-confirmed deletion. Failed sections retain explicitly stale successful data. No account service/schema change.

Validation: Node 24 typecheck; 43 account-action/session unit tests; isolated browser run `q25-account-20261117`, desktop/mobile 2/2 at 320 px. Cases include each load failing independently, verification refresh, delayed/failed device revocation, another device remaining usable, and failed then successful sign-out. Browser export entry was 646 KB before the small action fence; final integrated budget is checked by Q40. Native installed-device verification remains an external gate.

Independent Terra high review caught delayed push-cleanup and post-session-cleanup account-switch races. `accountActions.ts` now captures the session revision before cleanup, checks before sign-out, and only publishes completion for that action's terminal revision. The global session subscriber owns private UI teardown. Four controlled tests cover delayed push cleanup, delayed secure cleanup, deletion completion and provider failure. Reviewer approved the corrected Q25 scope. Q23 must also fence ownership of the push subscription marker itself.

Files: AccountDialog, App, api session-revision accessor, accountActions, focused browser and unit cases. No private production data or external messages used.
