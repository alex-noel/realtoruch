import json
from pathlib import Path

import pytest

from scripts.evaluate_dedupe import evaluate, read_dataset, validate_dataset

DATASET = Path(__file__).parent / 'fixtures/dedupe/pairs.jsonl'


def test_valid_dataset_and_malformed_rows_report_pair_id():
    rows = read_dataset(DATASET)
    summary = validate_dataset(rows)
    assert summary['total'] == 220
    assert summary['labels'] == {'same_home': 80, 'different_home': 100, 'ambiguous': 40}
    duplicate = [*rows, dict(rows[0])]
    with pytest.raises(ValueError, match='T09-001: duplicate pair ID'):
        validate_dataset(duplicate)
    missing = dict(rows[0], rationale='')
    with pytest.raises(ValueError, match='T09-001: missing rationale'):
        validate_dataset([missing])


def test_required_hard_negative_and_ambiguous_scenario_labels_are_explicit():
    rows = read_dataset(DATASET)
    by_family = {}
    for row in rows:
        by_family.setdefault(row['scenario_family'], []).append(row)
    assert all(r['label'] == 'different_home' for r in by_family['shared_agency_phone'])
    assert all(r['label'] == 'different_home' for r in by_family['unit_floor_conflict'])
    assert all(r['label'] == 'different_home' for r in by_family['stock_photo'])
    assert all(r['label'] == 'ambiguous' for r in by_family['missing_address_location'])
    result = evaluate(rows)
    assert result['per_scenario']['shared_agency_phone']['count'] == 20


def test_evaluation_is_deterministic_for_same_rows_and_production_matcher():
    rows = read_dataset(DATASET)
    assert evaluate(rows) == evaluate(rows)


def test_fixed_family_split_does_not_leak_near_identical_variants():
    rows = read_dataset(DATASET)
    partitions = {}
    for row in rows:
        partitions.setdefault(row['scenario_family'], set()).add(row['partition'])
    assert all(len(value) == 1 for value in partitions.values())
    changed = [dict(row, partition='holdout' if row['partition'] == 'development' else 'development') if row['id'] == 'T09-001' else row for row in rows]
    with pytest.raises(ValueError, match='family .* belongs to'):
        validate_dataset(changed)


def test_sequence_path_reports_repost_canonical_and_alert_suppression():
    from scripts.evaluate_dedupe import sequence_evaluation
    result = sequence_evaluation()
    assert result['canonical_count_correct'] is True
    assert result['identity_outcomes'] == {'repost_same_canonical': True, 'distinct_unit_separate': True}
    assert result['alert_suppressed_for_repost'] is True


def test_reject_all_matcher_has_zero_recall_and_undefined_precision():
    rows = read_dataset(DATASET)
    result = evaluate(rows, matcher=lambda *_: None)
    assert result['recall'] == 0.0
    assert result['precision'] is None
    assert result['confusion_known']['tp'] == 0
    assert result['ambiguous_auto_merge_count'] == 0


def test_prediction_exception_fails_run_instead_of_shrinking_metrics():
    rows = read_dataset(DATASET)
    def missing_prediction(*_):
        raise RuntimeError('simulated missing prediction')
    with pytest.raises(RuntimeError, match='simulated missing prediction'):
        evaluate(rows, matcher=missing_prediction)
