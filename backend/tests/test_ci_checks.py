import subprocess

import pytest

from scripts import ci_checks
from scripts.ci_checks import audit_findings, compare_findings


def test_unavailable_previous_revision_uses_full_snapshot_for_ci_base(monkeypatch):
    previous = "1" * 40

    def missing_revision(*args):
        assert args == ("rev-parse", "--verify", "--quiet", f"{previous}^{{commit}}")
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(ci_checks, "git", missing_revision)
    base = ci_checks.compare_base(previous, "master", scan_if_missing=True)
    assert base == ci_checks.EMPTY_TREE
    assert ci_checks.compare_base(base, "") == ci_checks.EMPTY_TREE
    with pytest.raises(subprocess.CalledProcessError):
        ci_checks.compare_base(previous, "")


def test_existing_high_development_advisory_still_requires_an_exception():
    key = ("npm", "example-build-tool", "1.0.0", "GHSA-example")
    report = {
        "results": [{
            "packages": [{
                "package": {"ecosystem": key[0], "name": key[1], "version": key[2]},
                "dependency_groups": ["dev"],
                "groups": [{"ids": [key[3]], "max_severity": 8.0}],
            }],
        }],
    }
    current = audit_findings(report)
    assert current == {key: "high"}

    finding, = compare_findings(current, current, {})
    assert finding["new"] is False
    assert finding["blocked"] is True

    exception = {"owner": "maintainer", "expires": "2026-12-31"}
    finding, = compare_findings(current, current, {key: exception})
    assert finding["exception"] == exception
    assert finding["blocked"] is False
