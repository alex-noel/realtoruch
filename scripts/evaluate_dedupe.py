"""Deterministic, synthetic-only evaluation of the production dedupe path."""

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "backend/tests/fixtures/dedupe/pairs.jsonl"
EXPECTED_FAMILIES = {
    "same_home_repost": "development",
    "morizon_gratka": "development",
    "address_image": "development",
    "resized_image_url": "holdout",
    "shared_agency_phone": "holdout",
    "unit_floor_conflict": "holdout",
    "stock_photo": "development",
    "missing_address_location": "development",
    "city_conflict": "holdout",
    "room_area_boundary": "holdout",
    "building_no_unit": "holdout",
}
LABELS = {"same_home", "different_home", "ambiguous"}
FORBIDDEN_RAW_FIELDS = {
    "phone",
    "phonenumber",
    "rawphone",
    "email",
    "emailaddress",
    "accountemail",
    "contactemail",
    "personalemail",
}


def read_dataset(path):
    rows = []
    for lineno, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON: {exc}") from exc
        rows.append(row)
    validate_dataset(rows)
    return rows


def _check_private_keys(value, pair_id, path="pair"):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = "".join(char for char in str(key).lower() if char.isalnum())
            if normalized in FORBIDDEN_RAW_FIELDS:
                raise ValueError(f"{pair_id}: forbidden raw personal field at {path}.{key}")
            _check_private_keys(child, pair_id, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_private_keys(child, pair_id, f"{path}[{index}]")


def validate_dataset(rows):
    seen = set()
    family_partitions = defaultdict(set)
    counts = Counter()
    required = {
        "id",
        "label",
        "rationale",
        "scenario_family",
        "partition",
        "provenance",
        "candidate",
        "incoming",
        "sources",
        "expected_auto_merge",
    }
    for row in rows:
        pid = row.get("id", "<missing id>")
        missing = required - row.keys()
        if missing:
            raise ValueError(f"{pid}: missing fields {sorted(missing)}")
        if pid in seen:
            raise ValueError(f"{pid}: duplicate pair ID")
        seen.add(pid)
        if row["label"] not in LABELS:
            raise ValueError(f"{pid}: invalid label {row['label']!r}")
        if not isinstance(row["rationale"], str) or not row["rationale"].strip():
            raise ValueError(f"{pid}: missing rationale")
        if not isinstance(row["provenance"], str) or not row["provenance"].strip():
            raise ValueError(f"{pid}: missing or invalid provenance")
        _check_private_keys(row, pid)
        fam = row["scenario_family"]
        part = row["partition"]
        if fam not in EXPECTED_FAMILIES:
            raise ValueError(f"{pid}: unknown scenario family {fam!r}")
        if part not in ("development", "holdout"):
            raise ValueError(f"{pid}: invalid partition {part!r}")
        if part != EXPECTED_FAMILIES[fam]:
            raise ValueError(f"{pid}: family {fam!r} belongs to {EXPECTED_FAMILIES[fam]}, not {part}")
        family_partitions[fam].add(part)
        counts[row["label"]] += 1
        if (
            row["expected_auto_merge"]
            is not {"same_home": True, "different_home": False, "ambiguous": None}[row["label"]]
        ):
            raise ValueError(f"{pid}: expected_auto_merge conflicts with authored label")
    if (
        len(rows) < 200
        or counts["same_home"] < 80
        or counts["different_home"] < 80
        or counts["ambiguous"] < 40
    ):
        raise ValueError(f"insufficient dataset: {len(rows)} total, label counts={dict(counts)}")
    for family, parts in family_partitions.items():
        if len(parts) != 1:
            raise ValueError(f"{family}: scenario family leaks across partitions")
    if set(family_partitions) != set(EXPECTED_FAMILIES):
        raise ValueError("required scenario family missing")
    return {
        "total": len(rows),
        "labels": dict(counts),
        "families": {k: min(v) for k, v in family_partitions.items()},
    }


def run_match(row, matcher=None):
    if matcher is None:
        from realtoruch.dedupe import matching_property

        matcher = matching_property
    c = row["candidate"]
    incoming = row["incoming"]
    candidate = SimpleNamespace(**c)
    sources = [
        SimpleNamespace(source=s["source"], phone_hash=s.get("phone_hash"), data=s["data"])
        for s in row["sources"]
    ]
    return matcher(candidate, incoming, sources)


def evaluate(rows, matcher=None):
    matrix = {
        label: {"auto_merge": 0, "no_merge": 0} for label in ("same_home", "different_home", "ambiguous")
    }
    by_family = defaultdict(lambda: {"count": 0, "auto_merge": 0, "failures": []})
    failures = []
    prediction_ids = set()
    for row in rows:
        # A completed match/no-match decision is required for every row; exceptions
        # propagate and leave no report rather than quietly shrinking denominators.
        prediction = run_match(row, matcher)
        prediction_ids.add(row["id"])
        matched = prediction is not None
        label = row["label"]
        family = row["scenario_family"]
        matrix[label]["auto_merge" if matched else "no_merge"] += 1
        metric = by_family[family]
        metric["count"] += 1
        metric["auto_merge"] += int(matched)
        incorrect = (
            (label == "same_home" and not matched)
            or (label == "different_home" and matched)
            or (label == "ambiguous" and matched)
        )
        if incorrect:
            failures.append(row["id"])
            metric["failures"].append(row["id"])
    tp = matrix["same_home"]["auto_merge"]
    fn = matrix["same_home"]["no_merge"]
    fp = matrix["different_home"]["auto_merge"]
    tn = matrix["different_home"]["no_merge"]
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else 0.0
    if len(prediction_ids) != len(rows):
        raise ValueError(f"prediction coverage incomplete: {len(prediction_ids)}/{len(rows)}")
    return {
        "prediction_coverage": {
            "predicted": len(prediction_ids),
            "expected": len(rows),
            "complete": True,
        },
        "confusion_known": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": precision,
        "recall": recall,
        "ambiguous_auto_merge_count": matrix["ambiguous"]["auto_merge"],
        "per_label": matrix,
        "per_scenario": {k: dict(v) for k, v in sorted(by_family.items())},
        "failure_ids": sorted(failures),
    }


def sequence_evaluation(matcher=None):
    """Run a five-observation sequence through production ingest and alert processing.

    Optional matcher injection is test-only. The default delegates to the production
    function imported by ingest.py. Expected truth groups are the original home and
    two distinct, known-unit apartments; results expose canonical and notification
    errors caused by injected merge/reject-all behavior.
    """
    from itertools import combinations

    import realtoruch.ingest as ingest_module
    from realtoruch.alerts import process_alerts
    from realtoruch.db import Base
    from realtoruch.models import AlertEvent, Listing, Notification, SavedSearch
    from realtoruch.schemas import RawListing
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    original_matcher = ingest_module.matching_property
    if matcher is not None:
        ingest_module.matching_property = matcher
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            user_id = "t09-synthetic-user"
            session.add(
                SavedSearch(
                    user_id=user_id,
                    name="T09 synthetic alert search",
                    city_key="warszawa",
                    filters={
                        "city": "Warszawa",
                        "max_price": 5000,
                        "max_price_exclusive": True,
                        "min_area": 50,
                        "advertiser": "private",
                        "property_type": "apartment",
                    },
                )
            )
            session.flush()
            common = {
                "url": "https://synthetic.example.test/listing",
                "title": "Synthetic rental home",
                "description": "Synthetic evaluation record",
                "city": "Warszawa",
                "district": "Test",
                "region": "Synthetic",
                "address": "Sequence Street 10",
                "lat": 52.2,
                "lon": 21.0,
                "area_m2": 54,
                "rooms": 2,
                "floor": 2,
                "rent_pln": 4000,
                "fees_pln": None,
                "deposit_pln": None,
                "commission_pln": None,
                "advertiser_type": "private",
                "property_type": "apartment",
                "phone_hash": "a" * 64,
                "images": ["https://images.example.test/sequence/home.jpg?asset=seq1"],
            }

            def raw(source, eid, **kw):
                return RawListing(source=source, external_id=eid, **(common | kw))

            observations = [
                ("home-a", "otodom", "seq-home-a", {}),
                ("home-a", "otodom", "seq-home-a-repost-1", {}),
                ("home-a", "otodom", "seq-home-a-repost-2", {}),
                (
                    "unit-b",
                    "olx",
                    "seq-unit-b",
                    {"address": "Sequence Street 10/8", "floor": 8},
                ),
                (
                    "unit-c",
                    "gratka",
                    "seq-unit-c",
                    {"address": "Sequence Street 10/9", "floor": 9},
                ),
            ]
            mapped = []
            for truth, source, eid, changes in observations:
                result = ingest_module.ingest(session, raw(source, eid, **changes))
                mapped.append(
                    {
                        "truth_home": truth,
                        "source_id": eid,
                        "listing_id": result["listing_id"],
                        "match_reason": result.get("match_reason"),
                    }
                )
                session.commit()
                process_alerts(session)
                session.commit()
            listings = session.scalars(select(Listing)).all()
            notifications = session.scalars(
                select(Notification).where(Notification.user_id == user_id).order_by(Notification.id)
            ).all()
            actual_by_truth = defaultdict(set)
            truths_by_listing = defaultdict(set)
            for item in mapped:
                actual_by_truth[item["truth_home"]].add(item["listing_id"])
                truths_by_listing[item["listing_id"]].add(item["truth_home"])
            false_merge_pairs = []
            for left, right in combinations(sorted(actual_by_truth), 2):
                shared = actual_by_truth[left] & actual_by_truth[right]
                if shared:
                    false_merge_pairs.append(
                        {
                            "truth_homes": [left, right],
                            "shared_canonical_ids": sorted(shared),
                        }
                    )
            duplicate_canonical_homes = {
                truth: sorted(ids) for truth, ids in sorted(actual_by_truth.items()) if len(ids) > 1
            }
            # Each canonical receives one logical new_match notification. A merged
            # canonical can only produce one notification, while duplicate IDs create extras.
            notification_kinds = Counter(item.kind for item in notifications)
            notification_listing_ids = [item.listing_id for item in notifications]
            logical_notifications_by_truth = {}
            for truth, ids in actual_by_truth.items():
                exclusive_ids = {listing_id for listing_id in ids if truths_by_listing[listing_id] == {truth}}
                logical_notifications_by_truth[truth] = sum(
                    1 for item in notifications if item.listing_id in exclusive_ids
                )
            canonical_labels = {
                listing_id: f"canonical-{index:02d}"
                for index, listing_id in enumerate(dict.fromkeys(item["listing_id"] for item in mapped), 1)
            }
            for item in false_merge_pairs:
                item["shared_canonical_ids"] = [
                    canonical_labels[listing_id] for listing_id in item["shared_canonical_ids"]
                ]
            duplicate_canonical_homes = {
                truth: sorted(canonical_labels[listing_id] for listing_id in ids)
                for truth, ids in duplicate_canonical_homes.items()
            }
            # Truth-based expectation is exactly three homes, independent of actual merges.
            truth_expected_count = 3
            actual_notification_count = len(notifications)
            canonical_count = len(listings)
            canonical_correct = (
                canonical_count == truth_expected_count
                and not false_merge_pairs
                and not duplicate_canonical_homes
            )
            notifications_correct = (
                notification_kinds == Counter({"new_match": truth_expected_count})
                and actual_notification_count == truth_expected_count
                and all(v == 1 for v in logical_notifications_by_truth.values())
            )
            return {
                "steps": [
                    {
                        "truth_home": x["truth_home"],
                        "source_id": x["source_id"],
                        "canonical_id": canonical_labels[x["listing_id"]],
                    }
                    for x in mapped
                ],
                "expected_canonical_count": truth_expected_count,
                "canonical_count": canonical_count,
                "canonical_count_correct": canonical_correct,
                "false_merge_pairs": false_merge_pairs,
                "false_merge_count": len(false_merge_pairs),
                "duplicate_canonical_homes": duplicate_canonical_homes,
                "duplicate_canonical_count": sum(len(v) - 1 for v in duplicate_canonical_homes.values()),
                "expected_logical_notifications": truth_expected_count,
                "actual_logical_notifications": actual_notification_count,
                "notification_kinds": dict(notification_kinds),
                "notification_canonical_ids": sorted(
                    canonical_labels[listing_id] for listing_id in notification_listing_ids
                ),
                "logical_notifications_by_truth_home": logical_notifications_by_truth,
                "lost_notifications": max(0, truth_expected_count - actual_notification_count),
                "extra_notifications": max(0, actual_notification_count - truth_expected_count),
                "notifications_correct": notifications_correct,
                "repost_same_canonical": len(actual_by_truth["home-a"]) == 1,
                "distinct_units_separate": len(actual_by_truth["unit-b"]) == 1
                and len(actual_by_truth["unit-c"]) == 1
                and actual_by_truth["unit-b"].isdisjoint(actual_by_truth["unit-c"]),
                "processed_alert_event_count": session.scalar(
                    select(func.count()).select_from(AlertEvent).where(AlertEvent.processed_at.is_not(None))
                ),
                "matcher": "injected" if matcher is not None else "production default",
            }
    finally:
        ingest_module.matching_property = original_matcher
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--partition", choices=("all", "development", "holdout"), default="all")
    parser.add_argument("--output", type=Path, help="Write JSON report to path; default stdout")
    args = parser.parse_args()
    rows = read_dataset(args.dataset)
    original_count = len(rows)
    if args.partition != "all":
        rows = [r for r in rows if r["partition"] == args.partition]
    dataset_hash = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    code_sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False, timeout=10
        ).stdout.strip()
        or "unavailable"
    )
    production_paths = (
        "backend/realtoruch/dedupe.py",
        "backend/realtoruch/ingest.py",
        "backend/realtoruch/alerts.py",
    )
    production_hash = hashlib.sha256(
        b"".join(path.encode() + b"\0" + (ROOT / path).read_bytes() for path in production_paths)
    ).hexdigest()
    production_git_sha = (
        subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", *production_paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        ).stdout.strip()
        or "unavailable"
    )
    report = {
        "report_version": 1,
        "run_id": datetime.now(timezone.utc).strftime("T09-%Y%m%dT%H%M%SZ"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(
            args.dataset.relative_to(ROOT) if args.dataset.is_relative_to(ROOT) else args.dataset
        ),
        "dataset_sha256": dataset_hash,
        "dataset_pair_count": original_count,
        "evaluated_pair_count": len(rows),
        "code_git_sha": code_sha,
        "production_matching_git_sha": production_git_sha,
        "production_paths_sha256": production_hash,
        "evaluator_sha256": script_hash,
        "parameters": {
            "partition": args.partition,
            "matcher": "realtoruch.dedupe.matching_property",
            "thresholds": "production defaults; no tuning",
            "seed": None,
        },
        "synthetic_only": True,
        "real_market_accuracy_claimed": False,
        "validation": validate_dataset(read_dataset(args.dataset)),
        "metrics": evaluate(rows),
        "partition_metrics": {
            part: evaluate([r for r in read_dataset(args.dataset) if r["partition"] == part])
            for part in ("development", "holdout")
        },
    }
    if args.partition == "all":
        report["ingestion_sequence"] = sequence_evaluation()
        report["ingestion_fault_injection"] = {
            "forced_merge": sequence_evaluation(lambda *_: "T09 test injection: force merge"),
            "reject_all": sequence_evaluation(lambda *_: None),
            "production_behavior_changed": False,
        }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
