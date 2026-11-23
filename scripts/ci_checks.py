#!/usr/bin/env python3
"""Check proposed changes, audit dependency locks and select safe CI reports."""

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
LOCKS = {
    "runtime/requirements.txt": "backend/requirements-runtime.lock",
    "dev/requirements.txt": "backend/requirements-dev.lock",
    "cloud/requirements.txt": "backend/requirements-cloud.lock",
    "dataflow/requirements.txt": "backend/requirements-gcp.lock",
    "mobile/package-lock.json": "apps/mobile/package-lock.json",
}
PRIVATE_PATH = re.compile(
    r"(^|/)(?:\.local|captures?|credentials?|secrets?)(?:/|$)"
    r"|\.(?:db|sqlite3?|pem|key|p12|pfx|keystore|jks|mobileprovision|tfstate|tfplan|har|eml)(?:$|[-.])",
    re.IGNORECASE,
)
SECRET = re.compile(
    rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"
    rb"|\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|"
    rb"AKIA[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{35}|xox[baprs]-[A-Za-z0-9-]{10,})\b"
)
TEST_ID = re.compile(r"(?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*::test_[A-Za-z0-9_]+", re.ASCII)
SEVERITY_FLOORS = {"CRITICAL": 9, "HIGH": 7, "MODERATE": 4, "MEDIUM": 4, "LOW": 1}
SEVERITY_LEVELS = ((9, "critical"), (7, "high"), (4, "moderate"), (0.1, "low"))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def changed_files(base):
    return git("diff", "--name-only", "-z", "--diff-filter=ACMRT", base, "HEAD", "--").split(b"\0")


def check_boundary(base):
    if subprocess.run(
        ["git", "diff", "--check", base, "HEAD", "--"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        check=False,
    ).returncode:
        raise ValueError("git diff --check failed. Inspect the diff in your checkout.")
    for raw_path in filter(None, changed_files(base)):
        path = raw_path.decode("utf-8", errors="surrogateescape")
        name = PurePosixPath(path).name
        if PRIVATE_PATH.search(path) or (name.startswith(".env") and not name.endswith(".example")):
            raise ValueError("Change includes a private file type or directory.")
    diff = git("diff", "--no-ext-diff", "--no-textconv", "--unified=0", base, "HEAD", "--")
    if any(SECRET.search(line[1:]) for line in diff.splitlines() if line.startswith(b"+")):
        raise ValueError("Change includes a private key or a recognized credential pattern.")
    sources = json.loads((ROOT / "config/sources.json").read_text())["sources"]
    if any(source.get("enabled") is not False for source in sources):
        raise ValueError("Verification connector configuration must keep every source disabled.")


def compare_base(before, default_branch):
    # A new branch push uses its fork point with the default branch.
    if before == "0" * 40:
        return git("merge-base", "HEAD", f"refs/remotes/origin/{default_branch}").decode().strip()
    if not re.fullmatch(r"[a-f0-9]{40}", before):
        raise ValueError("Expected a full Git comparison SHA.")
    return git("rev-parse", "--verify", f"{before}^{{commit}}").decode().strip()


def sanitized_report(profile, source):
    if not source.is_file():
        return {"profile": profile, "status": "NO_REPORT"}
    report = json.loads(source.read_text())
    result = {"profile": profile, "status": "FAIL"}
    if report.get("status") == "PASS":
        result["status"] = "PASS"
    result["counts"] = {
        key: value for key, value in report.get("counts", {}).items()
        if key in {"passed", "failed", "skipped"} and type(value) is int and value >= 0
    }
    # Pytest parametrizations and error output can contain fixture credentials.
    for key in ("failed_tests", "skipped_tests"):
        result[key] = [name for name in report.get(key, []) if isinstance(name, str) and TEST_ID.fullmatch(name)]
    return result


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")


def audit_locks(scanner, locks):
    with TemporaryDirectory(prefix="realtoruch-audit-") as directory:
        root = Path(directory).resolve()
        paths = []
        expected = {}
        for name, contents in locks.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
            paths.extend(("--lockfile", name))
            expected[path] = "npm" if path.name == "package-lock.json" else "PyPI"
        run = subprocess.run(
            [scanner, "scan", "source", "--format=json", "--all-packages", "--no-resolve", *paths],
            cwd=root, capture_output=True, timeout=120, check=False,
        )
        if run.returncode not in (0, 1):
            raise ValueError(f"OSV-Scanner failed with exit {run.returncode}.")
        report = json.loads(run.stdout)
        scanned = {
            (root / source["source"]["path"]).resolve(): {
                entry["package"]["ecosystem"] for entry in source["packages"]
            }
            for source in report["results"]
        }
        missing = [str(path.relative_to(root)) for path, ecosystem in expected.items()
                   if ecosystem not in scanned.get(path, set())]
        if missing:
            raise ValueError(f"OSV-Scanner did not report packages for {', '.join(missing)}.")
        return audit_findings(report)


def audit_findings(report):
    scores = {}
    for source in report["results"]:
        for entry in source["packages"]:
            package = entry["package"]
            for group in entry.get("groups", []):
                ids = group["ids"]
                advisories = (
                    item.get("database_specific", {}).get("severity", "")
                    for item in entry.get("vulnerabilities", []) if item["id"] in ids
                )
                label_score = max((SEVERITY_FLOORS.get(label.upper(), 0) for label in advisories), default=0)
                score = max(float(group["max_severity"] or 0), label_score)
                for advisory in ids:
                    key = (package["ecosystem"], package["name"], package["version"], advisory)
                    scores[key] = max(scores.get(key, 0), score)
    return {
        key: next((rating for floor, rating in SEVERITY_LEVELS if score >= floor), "unknown")
        for key, score in scores.items()
    }


def audit_exceptions(path, today):
    exceptions = {}
    for item in json.loads(path.read_text()):
        key = tuple(item[field] for field in ("ecosystem", "package", "version", "advisory"))
        expiry = date.fromisoformat(item["expires"])
        if key in exceptions or not all(key) or not item["owner"].strip() or not item["reason"].strip():
            raise ValueError("An audit exception is incomplete or duplicated.")
        if expiry < today:
            raise ValueError(f"An audit exception expired on {expiry.isoformat()}.")
        exceptions[key] = {"owner": item["owner"], "expires": expiry.isoformat()}
    return exceptions


def compare_findings(base, current, exceptions):
    severe = {"high", "critical"}
    findings = []
    for key, severity in sorted(current.items()):
        is_new = key not in base or (severity in severe and base[key] not in severe)
        exception = exceptions.get(key)
        blocked = severity in severe and exception is None
        findings.append({
            **dict(zip(("ecosystem", "package", "version", "advisory"), key)),
            "severity": severity, "new": is_new, "blocked": blocked, "exception": exception,
        })
    return findings


def dependency_audit(base, scanner, output, *, working_tree=False):
    try:
        exceptions = audit_exceptions(ROOT / "config/ci-audit-exceptions.json", datetime.now(timezone.utc).date())
        current_locks = {
            name: (ROOT / path).read_bytes() if working_tree else git("show", f"HEAD:{path}")
            for name, path in LOCKS.items()
        }
        base_paths = git("ls-tree", "-r", "-z", "--name-only", base, "--", *LOCKS.values()).split(b"\0")
        base_locks = {name: git("show", f"{base}:{path}") for name, path in LOCKS.items()
                      if path.encode() in base_paths}
        current = audit_locks(scanner, current_locks)
        baseline = current
        if base_locks != current_locks:
            baseline = audit_locks(scanner, base_locks) if base_locks else {}
        findings = compare_findings(baseline, current, exceptions)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        write_report(output, {"status": "ERROR", "error_type": type(exc).__name__})
        raise
    blocked = sum(finding["blocked"] for finding in findings)
    write_report(output, {"status": "FAIL" if blocked else "PASS", "findings": findings})
    print(f"Dependency audit: {len(findings)} findings, {blocked} high/critical findings without exceptions.")
    return int(bool(blocked))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    base = commands.add_parser("base")
    base.add_argument("before")
    base.add_argument("default_branch")
    boundary = commands.add_parser("boundary")
    boundary.add_argument("base")
    audit = commands.add_parser("audit")
    audit.add_argument("base")
    audit.add_argument("scanner", type=lambda path: str(Path(path).resolve()))
    audit.add_argument("output", type=Path)
    audit.add_argument("--working-tree", action="store_true", help="audit local lock files instead of HEAD")
    report = commands.add_parser("report")
    report.add_argument("profile", choices=("offline", "services", "web"))
    report.add_argument("source", type=Path)
    report.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "base":
            print(compare_base(args.before, args.default_branch))
        elif args.command == "boundary":
            check_boundary(compare_base(args.base, ""))
        elif args.command == "audit":
            return dependency_audit(
                compare_base(args.base, ""), args.scanner, args.output, working_tree=args.working_tree
            )
        elif args.command == "report":
            write_report(args.output, sanitized_report(args.profile, args.source))
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print(f"CI check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
