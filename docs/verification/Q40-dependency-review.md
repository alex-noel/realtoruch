# Q40 runtime dependency review

The repository OSV comparison gate passed on 17 November 2026 against `4cb5503`: four findings, all also present in the baseline locks; zero new high/critical findings and no exceptions added. The Q26 sharing dependency and Q34 picker lock merge introduce no new reported advisory in this scan. The exact sanitized results are included in the Q40 evidence JSON.

| Package | Locked version | Reported severity | Advisory |
| --- | --- | --- | --- |
| glob | 13.0.7 | moderate | GHSA-3g3m-2fjr-6pw4 |
| minimatch | 10.2.6 | moderate | GHSA-g3hv-75wg-m249 |
| picomatch | 2.3.2 | high | GHSA-fc5q-39xc-vjpf |
| picomatch | 4.0.7 | high | GHSA-fc5q-39xc-vjpf |

The current scan reports more findings than the historical T23/T24 report; the older report is retained with its original result. The comparison establishes that these dependency versions were already present, not that they are safe.

At review time, the [picomatch advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) is marked unreviewed and lists no patched version. The [upstream releases](https://github.com/micromatch/picomatch/releases) still identify 4.0.7 as latest. No speculative override or unmerged upstream patch was installed. The repository maintainer owns confirming exposure through the Expo/Metro dependency chain and adopting a reviewed compatible fix when available. Application source contains no direct picomatch/micromatch imports; that source scan is narrower than a complete reachability analysis.

Command from the checkout root, using the previously verified OSV-Scanner executable and the full comparison SHA:

```sh
.venv/bin/python scripts/ci_checks.py audit "$TASK_BASE" "$OSV_SCANNER" .local/verification/Q40/dependency-audit.json
```

This is a baseline comparison gate, not an assertion that the dependency tree has no known advisories. Hosted CI must rerun on the final revision after a separately requested push.
