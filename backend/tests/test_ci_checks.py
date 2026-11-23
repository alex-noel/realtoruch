from scripts.ci_checks import audit_findings, compare_findings


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
