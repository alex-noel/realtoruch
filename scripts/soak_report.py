#!/usr/bin/env python3
"""Aggregate an existing T07 manifest without starting collection or reading advert data."""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


COUNTERS = (
    "checked", "new_details", "due_rechecks", "ingested", "search_pages", "fresh_skipped",
    "known_skipped", "skipped",
    "body_bytes", "network_attempts", "robots_attempts", "retry_attempts", "conditional_attempts",
    "responses_304", "reused_304",
)


def aggregate(manifest):
    """Use an allowlist; never emit source URLs/hashes, advert content or private IDs."""
    pin = manifest["pin"]
    provider_names = tuple(pin["sources"])
    per_source = {name: Counter() for name in provider_names}
    errors = {name: Counter() for name in provider_names}
    counts = Counter()
    intervals = []
    for cycle in manifest["cycles"]:
        state = cycle["state"]
        counts[state] += 1
        if cycle.get("started_at"):
            counts["attempted"] += 1
        if cycle.get("eligible"):
            counts["eligible"] += 1
        states = {}
        for name in provider_names:
            source = cycle.get("sources", {}).get(name, {})
            status = source.get("status", state)
            states[name] = status
            stats = per_source[name]
            stats[status] += 1
            if source.get("attempted"):
                stats["attempted"] += 1
            if status == "succeeded" and source.get("ingested", 0) > 0:
                stats["successful_checks"] += 1
            if source.get("reason") == "lease_lost":
                stats["lease_losses"] += 1
            if source.get("attempted") and "network_attempts" not in source:
                stats["unknown_network_totals"] += 1
            if status in ("unobserved", "running") and not source.get("attempted"):
                stats["unknown_provider_attempts"] += 1
            for key in COUNTERS:
                stats[key] += source.get(key, 0)
            for error in source.get("errors", []):
                label = "/".join(str(error[key]) for key in ("stage", "kind", "http_status", "code")
                                 if error.get(key) is not None)
                errors[name][label] += 1
        intervals.append({
            **{key: cycle[key] for key in (
                "id", "scheduled_at", "state", "started_at", "finished_at", "eligible", "reason",
                "counts_before", "counts_after", "history_delta", "budget_violations",
            ) if key in cycle},
            "sources": states,
        })

    horizon = instant(manifest["ends_at"])
    through = min(instant(manifest["observed_through"]), horizon)
    wall_seconds = (through - instant(manifest["started_at"])).total_seconds()
    gap_seconds = sum((instant(gap["to"]) - instant(gap["from"])).total_seconds()
                      for gap in manifest["runner_gaps"])
    covered_seconds = max(0, wall_seconds - gap_seconds)
    history = (manifest.get("latest_counts") or {}).get("history", {})
    all_successful = all(per_source[name]["successful_checks"] for name in provider_names)
    budget_violations = sum(len(cycle.get("budget_violations", [])) for cycle in manifest["cycles"])
    status = "INCOMPLETE"
    if budget_violations:
        status = "FAILED"
    elif (covered_seconds >= 72 * 3600 and counts["eligible"] >= 12 and all_successful
          and not counts["pending"] and not counts["running"]
          and not any(stats["unknown_network_totals"] or stats["unknown_provider_attempts"]
                      for stats in per_source.values())):
        status = "VERIFIED"
    return {
        "kind": "live", "status": status, "run_id": manifest["run_id"],
        "commit": pin["commit"], "config_sha256": pin["config_sha256"], "schema": manifest.get("schema"),
        "runtime": manifest["runtime"], "city": pin["city"], "budget": pin["budget"],
        "started_at": manifest["started_at"], "target_end": manifest["ends_at"],
        "observed_through": timestamp(through), "wall_elapsed_seconds": wall_seconds,
        "runner_covered_seconds": covered_seconds, "runner_gap_seconds": gap_seconds,
        "runner_gaps": manifest["runner_gaps"],
        "cycle_counts": {key: counts[key] for key in (
            "attempted", "eligible", "completed", "deferred", "missed", "interrupted", "running", "pending",
        )},
        "providers": {
            name: {
                **dict(per_source[name]), "errors": dict(errors[name]),
                "success_fraction": {
                    "succeeded": per_source[name]["succeeded"],
                    "accounted_intervals": len(intervals) - counts["pending"] - counts["running"],
                    "scheduled_intervals": len(intervals),
                },
            } for name in provider_names
        },
        "baseline_counts": manifest.get("baseline_counts"),
        "latest_counts": manifest.get("latest_counts"),
        "budget_violations": budget_violations,
        "live_removal": "OBSERVED" if history.get("delisted", 0) else "UNVERIFIED",
        "fixture_evidence": "Separate deterministic drill; fixture outcomes do not enter live totals.",
        "intervals": intervals,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Run-owned manifest.json")
    args = parser.parse_args()
    print(json.dumps(aggregate(json.loads(args.manifest.read_text())), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
