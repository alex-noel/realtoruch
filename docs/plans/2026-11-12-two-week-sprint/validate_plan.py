#!/usr/bin/env python3
"""Validate the task pack's structure, coverage, dependencies and capacity.

This checks planning artifacts only. It does not execute application acceptance
tests, contact providers, start services or change Git state.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> int:
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text())
    plan, tasks = manifest["plan"], manifest["tasks"]
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    ids = [task["id"] for task in tasks]
    check(len(ids) == len(set(ids)), "Duplicate task IDs")
    check(ids == [f"T{i:02}" for i in range(1, 37)], "Expected ordered T01–T36")
    by_id = {task["id"]: task for task in tasks}
    all_ac_ids, all_test_ids = [], []
    seen_paths: set[str] = set()
    for task in tasks:
        task_id = task["id"]
        path = root / task["path"]
        check(task["path"] not in seen_paths, f"{task_id}: duplicate prompt path")
        seen_paths.add(task["path"])
        check(path.is_file(), f"{task_id}: missing prompt {path}")
        check(task["tier"] in {"core", "conditional", "stretch"}, f"{task_id}: invalid tier")
        check(task["priority"] in {"P0", "P1", "P2"}, f"{task_id}: invalid priority")
        check(task["hours"] > 0, f"{task_id}: effort must be positive")
        check(len(task["acs"]) >= 6, f"{task_id}: fewer than six ACs")
        check(len(task["tests"]) >= 6, f"{task_id}: fewer than six test cases")
        check(bool(task["goal"].startswith("I want")), f"{task_id}: missing user instruction")
        check(len(task["requirements"]) >= 6, f"{task_id}: missing technical detail")
        check(bool(task["read"] and task["write"] and task["checks"]), f"{task_id}: incomplete scope/checks")
        for dependency in task["depends"]:
            check(dependency in by_id and dependency != task_id, f"{task_id}: invalid dependency {dependency}")
        ac_ids = [ac["id"] for ac in task["acs"]]
        test_ids = [test["id"] for test in task["tests"]]
        check(ac_ids == [f"{task_id}-AC{i:02}" for i in range(1, len(ac_ids) + 1)], f"{task_id}: AC numbering")
        check(test_ids == [f"{task_id}-TC{i:02}" for i in range(1, len(test_ids) + 1)], f"{task_id}: case numbering")
        covered: set[str] = set()
        for case in task["tests"]:
            check(bool(case["covers"]), f"{case['id']}: no mapped AC")
            check(set(case["covers"]).issubset(ac_ids), f"{case['id']}: unknown AC")
            check(all(case.get(k) for k in ("given", "when", "then")), f"{case['id']}: incomplete Given/When/Then")
            covered.update(case["covers"])
        check(set(ac_ids) == covered, f"{task_id}: uncovered ACs {set(ac_ids) - covered}")
        all_ac_ids.extend(ac_ids)
        all_test_ids.extend(test_ids)
        if path.is_file():
            body = path.read_text()
            for evidence_id in ac_ids + test_ids:
                check(evidence_id in body, f"{task_id}: prompt missing {evidence_id}")
            for section in ("Working instructions", "Technical requirements", "Acceptance criteria",
                            "Required test cases", "Allowed implementation scope", "Deliverables"):
                check(f"## {section}" in body, f"{task_id}: missing section {section}")

    check(len(all_ac_ids) == len(set(all_ac_ids)) == 217, "AC IDs/count mismatch")
    check(len(all_test_ids) == len(set(all_test_ids)) == 222, "Test IDs/count mismatch")
    state: dict[str, int] = {}

    def visit(task_id: str) -> None:
        if state.get(task_id) == 1:
            errors.append(f"Dependency cycle at {task_id}")
            return
        if state.get(task_id) == 2:
            return
        state[task_id] = 1
        for dependency in by_id[task_id]["depends"]:
            if dependency in by_id:
                visit(dependency)
        state[task_id] = 2

    for task_id in ids:
        visit(task_id)

    capacity = plan["capacity"]
    totals = Counter()
    for task in tasks:
        totals[task["tier"]] += task["hours"]
    check(totals["core"] == capacity["core_hours"] == 175, "Core estimate/capacity mismatch")
    check(totals["conditional"] == capacity["conditional_catalog_hours"] == 20, "Conditional estimate mismatch")
    check(totals["stretch"] == capacity["stretch_catalog_hours"] == 50, "Stretch estimate mismatch")
    check(capacity["total_worker_hours"] == capacity["implementation_workers"] *
          capacity["productive_hours_per_worker_day"] * capacity["workdays"], "Total capacity formula mismatch")
    check(capacity["core_hours"] + capacity["protected_buffer_hours"] +
          capacity["conditional_capacity_hours"] == capacity["total_worker_hours"], "Allocated capacity mismatch")
    check(capacity["protected_buffer_hours"] >= 48, "Protected buffer reduced without plan update")

    slots: dict[str, list[tuple[int, int, str]]] = {worker: [] for worker in "ABCD"}
    for task in tasks:
        scheduled = task["schedule"]
        if task["tier"] == "core":
            check(bool(scheduled), f"{task['id']}: unscheduled core task")
        if scheduled:
            check(sum(end - start for start, end, _ in scheduled) == task["hours"], f"{task['id']}: slot hours mismatch")
            for start, end, worker in scheduled:
                check(0 <= start < end <= 60, f"{task['id']}: slot outside sprint")
                check(worker in slots, f"{task['id']}: invalid worker")
                if worker in slots:
                    slots[worker].append((start, end, task["id"]))
            for dependency in task["depends"]:
                previous = by_id.get(dependency, {}).get("schedule", [])
                if previous:
                    check(scheduled[0][0] >= previous[-1][1],
                          f"{task['id']}: starts before dependency {dependency} finishes")
    for worker, assigned in slots.items():
        assigned.sort()
        for previous, current in zip(assigned, assigned[1:]):
            check(current[0] >= previous[1], f"Worker {worker}: overlap {previous[2]} / {current[2]}")

    days = [date.fromisoformat(day) for day in plan["days"]]
    check(len(days) == 10 and len(set(days)) == 10 and days == sorted(days), "Workday list invalid")
    check(all(day.weekday() < 5 for day in days), "Workday list contains weekend")
    check(days[0].isoformat() == plan["start"] and days[-1].isoformat() == plan["end"], "Window mismatch")
    # Nominal 09:00 starts check that the schedule makes 72 real hours possible.
    # Only a future runner's timestamps can prove actual soak duration.
    def nominal_wall_time(hour: int) -> datetime:
        index, remainder = divmod(hour, 6)
        return datetime.combine(days[index], time(9), ZoneInfo(plan["timezone"])) + timedelta(hours=remainder)

    soak = by_id["T07"]["schedule"]
    check(nominal_wall_time(soak[-1][0]) - nominal_wall_time(soak[0][0]) >= timedelta(hours=72),
          "Schedule does not permit 72-hour soak")

    migration_keys = [(entry["database"], entry["version"]) for entry in plan["migrations"]]
    check(len(migration_keys) == len(set(migration_keys)), "Duplicate reserved migration version")
    for entry in plan["migrations"]:
        check(entry["owner"] in by_id, f"Unknown migration owner {entry['owner']}")
        check(Path(entry["file"]).name.startswith(entry["version"] + "_"), f"Migration filename/version mismatch {entry}")
        owner = by_id.get(entry["owner"])
        if owner:
            check(any(path.startswith(entry["file"]) for path in owner["write"]),
                  f"{entry['owner']}: reserved migration absent from write scope")
    gates = {entry["id"] for entry in plan["gates"]}
    for task in tasks:
        for gate in task["gates"]:
            match = re.match(r"G[0-9]+", gate)
            check(bool(match and match.group() in gates), f"{task['id']}: unknown gate {gate}")

    for markdown in root.rglob("*.md"):
        for destination in re.findall(r"\]\(([^)]+)\)", markdown.read_text()):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", destination):
                continue
            local = destination.split("#", 1)[0]
            if local:
                check((markdown.parent / local).resolve().exists(),
                      f"Broken local link in {markdown.relative_to(root)}: {destination}")

    matrix = (root / "AC_TEST_MATRIX.md").read_text()
    for ac_id in all_ac_ids:
        check(f"[{ac_id}]" in matrix, f"Traceability matrix missing {ac_id}")
    for case_id in all_test_ids:
        check(case_id in matrix, f"Traceability matrix missing {case_id}")

    if errors:
        print("Plan validation FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Plan validation PASSED: {len(tasks)} tasks, {len(all_ac_ids)} ACs, {len(all_test_ids)} cases.")
    print(f"Core {totals['core']} h + buffer {capacity['protected_buffer_hours']} h + conditional allocation "
          f"{capacity['conditional_capacity_hours']} h = {capacity['total_worker_hours']} h.")
    print("Dependencies, worker slots, migration reservations, traceability and local links are consistent.")
    print("Planning artifacts only; application acceptance tests were not run by this validator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
