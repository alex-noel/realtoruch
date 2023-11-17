# Task handoff

Task: Qxx and title

Status: PLANNED / IN_PROGRESS / IMPLEMENTED_LOCAL / VERIFIED_LOCAL / BLOCKED / CHANGES_REQUESTED

Base revision, dependency revisions, branch and resulting commit or uncommitted diff:

## Result

Describe the user-visible before/after behavior in two or three sentences. List changed files and explain any approved expansion beyond the packet. Include synthetic before/after screenshots for visible UI changes.

## Acceptance evidence

| Criterion | PASS FAIL or BLOCKED | Evidence |
| --- | --- | --- |
| Qxx-AC01 | | Test name, command/run and result |
| Qxx-AC02 | | |
| Qxx-AC03 | | |

## Verification

| Actual command and working directory | Exit code | Passed failed skipped | Evidence path |
| --- | ---: | --- | --- |
| | | | |

Record actual wall-clock date/time, code revision, relevant runtime/browser/device versions, isolated fixture/run ID and any required-but-not-run checks. Explain skips; do not call them passed. Record meaningful fault-injection behavior where requested and confirm the fault was removed.

## Compatibility and review

State API/schema/config changes, migration and recovery implications, dependency/lockfile changes and interactions with the reviewed dependencies. Name the required reviewer and record review outcome. Explain how the relevant session/privacy/visibility invariants were preserved.

## Remaining work

List unresolved defects, exact blockers and owner/input needed. Separate local gaps from NOT_RUN_EXTERNAL device/provider checks. Do not include raw secrets, private exports, real mail, database files or unfiltered logs.
