# Task handoff template

Copy this into a sanitized task report. Replace every placeholder; do not invent evidence.

## Identity and outcome

- Task: T__
- Status: PLANNED / IN_PROGRESS / IMPLEMENTED_LOCAL / VERIFIED / BLOCKED_EXTERNAL / FAILED_REVIEW
- Base revision:
- Result commit(s), created using `python3 scripts/commit.py`:
- Actual work/test date and timezone:
- One-sentence user-visible outcome:
- Scope changes approved by the integrator, if any:

## Changed files and contracts

List changed files, what changed, and why. Include migration IDs, API/DTO changes, config additions, compatibility and recovery notes. Explain any intentionally untouched requirement.

## Acceptance evidence

| AC ID | PASS / FAIL / NOT_RUN / BLOCKED | Test case IDs | Command/run ID | Artifact/result |
| --- | --- | --- | --- | --- |
| T__-AC01 | | | | |

Every AC needs a row. Every mapped test case needs an explicit result. “Code exists” and “looks right” are not test evidence.

## Verification

For each actual command: exact invocation, working directory, runtime/service versions, exit code, passed/failed/skipped counts and sanitized artifact path. Record retries and their reason. For service/native/live checks, state exactly which real system was exercised.

Include fixture seed/counts and controlled ordering for races; hardware/workload/sample counts for performance; real elapsed duration/gaps for soak. Do not backdate evidence to match Git metadata.

## Reproduction and review

- How to reproduce the fixed defect or new behavior:
- Negative/boundary tests:
- Remaining risks and independent-review requests:
- Safe rollback/recovery:
- Shared-file conflicts or downstream tasks affected:

## Blockers and next action

For each blocker, name gate/input, completed independent work, failed attempts, who can supply the input and the smallest next action. Do not include secrets. State clearly whether cloud resources, real emails or live provider requests were used; they must match the task authorization.

No push/deploy/publication is part of this handoff.
