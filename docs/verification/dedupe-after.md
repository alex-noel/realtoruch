# T10 synthetic identity evaluation

Actual evaluation: 2026-11-11 (Europe/Warsaw), against the T10 working tree based on `4e6f00b`. The frozen 220-pair T09 dataset SHA-256 remains `511c5f6c7ef1e4a16bffb706ddd94e30a18e8c13423ea37eea0bd541da40940c`. No rows or labels were changed. The final holdout was evaluated once, after development. The evaluator API was called directly because its CLI also evaluates both partitions when a partition is selected. Full sanitized run data is in ignored `.local/verification/T10/final-20261111/evaluation.json`.

| Partition | TP | FP | TN | FN | Recall | Ambiguous automatic merges |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 60 | 0 | 20 | 0 | 100% | 0/20 |
| Holdout | 20 | 0 | 80 | 0 | 100% | 0/20 |
| Total | 80 | 0 | 100 | 0 | 100% | 0/40 |

The T09 baseline was TP 80, FP 0, TN 100, FN 0, but automatically merged 20 ambiguous cases. With actual production `ingest` and `process_alerts`, the five-observation sequence produced three homes and three logical new-match notifications. Forced-merge diagnostics produced one home and one notification with three false-merge pairs; reject-all produced five homes and five notifications, with two duplicate canonicals. These injections are diagnostics, not production outcomes.

This is a synthetic, bounded fixture, not an estimate of live-market accuracy. A shared unit plus corroboration, an explicit supported syndication identity, or matching address, known matching floor, both contact and photo, and nearby coordinates can establish an automatic match; known conflicting floor, unit or location rejects it. The latter evidence is still heuristic: two different apartments can share a floor, contact and photo. Missing floor is not agreement. Phone, stock image or approximate location alone cannot prove identity. These results do not establish zero false merges in real listings.

Integration correction: the previously existing portal regression `test_shared_contact_without_syndication_identity_does_not_merge` exposed the street-only fallback as too broad. The fallback now also requires a building number. The 142-test combined collector/portal/identity regression passes after this change. The frozen corpus and labels remain unchanged; the table above records the earlier evaluated revision, not a new measurement of the tightened matcher. Final integrated frozen evaluation belongs to T32, with no tuning from holdout results.

## Final integrated regression report — 12 November 2026

The unchanged dataset was formally evaluated on `a775a776885ce6c4269f209ad99aaf82138cd647`: development TP60/FP0/TN20/FN0, holdout TP20/FP0/TN80/FN0, ambiguous automatic merges0/40. Production sequence: three canonical homes, three logical alerts, zero missing/extra. [Sanitized exact report](dedupe-final.json). The matcher is unchanged in the final code candidate. One formal call was made per partition, but automated determinism tests also execute the full frozen corpus; this is a reused synthetic regression set, not an untouched statistical holdout. No labels or matcher were tuned to the current results.
