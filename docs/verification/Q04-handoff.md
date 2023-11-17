# Q04 scoped feedback

Implemented and locally verified 2026-11-17. Feedback uses a polite success status and persistent error alert, an explicit Dismiss message button, and an inline dialog placement through shared Panel context. Outside dialogs it occupies layout space below comparison controls. A message tracks its announcement so moving from the dialog to the page does not repeat it. Existing error catches now select persistent errors; successes retain their 4.5 second lifetime.

Node24 typecheck passed. Isolated browser run `q04-feedback-20261117-02`: 2/2 desktop/mobile cases, testing a failed favorite inside details, persistence past the previous timeout, no raw server text, dismissal, retry success, retained focus, 200% text and reachable comparison/dismiss controls. First run caught a collapsed ScrollView footer; setting its intrinsic flex basis fixed that defect. Screenshot: `docs/previews/quality/q04-feedback.png`.

Installed native keyboard and spoken assistive-technology behavior remain external checks. Action-specific retry and pending state are handled in their later task packets.
