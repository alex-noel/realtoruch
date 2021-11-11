#!/usr/bin/env python3
"""Run bounded real collection cycles; emit evidence without claiming exhaustive coverage."""

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from soak_report import aggregate, instant, timestamp

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path("config/sources.live.json")
RUNS = ROOT / ".local/verification/T07"
CITY = "Kraków"
SOURCES = ("otodom", "gratka", "morizon")
INTERVAL = timedelta(hours=6)
ADMISSION = timedelta(minutes=10)
HEARTBEAT = 60
HEARTBEAT_LIMIT = 2 * HEARTBEAT
CYCLE_TIMEOUT = 15 * 60
LIMITS = {
    "max_pages": 1, "max_listings": 2, "max_rechecks": 4,
    "new_details_only": True, "stop_on_robots_error": True,
}
ARTIFACTS = ("manifest.json", "catalog.db", "catalog.db-shm", "catalog.db-wal", "catalog.db-journal",
             "auth.db", "mail", "phone-key", "runner.lock")


def one_shot(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=3, choices=range(1, 25))
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--city", default="Kraków")
    parser.add_argument("--max-listings", type=int, default=2)
    parser.add_argument("--max-rechecks", type=int, default=2)
    args = parser.parse_args(argv)
    if (
        args.interval < 30
        or not 0 <= args.max_listings <= 20
        or not 0 <= args.max_rechecks <= 50
    ):
        parser.error(
            "Use an interval of at least 30s and bounded collection sizes (0–20 new, 0–50 rechecks)."
        )
    from local import local_environment

    os.environ.update(local_environment(live=True))
    from realtoruch.db import Session, init_db
    from realtoruch.models import (
        EventReceipt,
        Listing,
        Observation,
        Outbox,
        SourceListing,
    )
    from realtoruch.worker import CollectionFailed, collect
    from sqlalchemy import func, select

    init_db()
    results = []
    destination = ROOT / ".local/reliability.json"

    def counts():
        with Session() as session:
            return {
                model.__tablename__: session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (Listing, SourceListing, Observation, EventReceipt, Outbox)
            }

    before = counts()
    for cycle in range(args.cycles):
        started = time.monotonic()
        try:
            report = collect(
                city=args.city,
                workers=3,
                limits={
                    "max_pages": 1,
                    "max_listings": args.max_listings,
                    "max_rechecks": args.max_rechecks,
                },
            )
        except CollectionFailed as exc:
            report = exc.reports
        results.append(
            {
                "cycle": cycle + 1,
                "duration_seconds": round(time.monotonic() - started, 2),
                "sources": report,
                "counts": counts(),
            }
        )
        destination.write_text(
            json.dumps({"before": before, "cycles": results}, indent=2) + "\n"
        )
        print(json.dumps(results[-1]), flush=True)
        if cycle + 1 < args.cycles:
            time.sleep(args.interval)
    return int(
        any(
            source["status"] in ("failed", "partial")
            for cycle in results
            for source in cycle["sources"]
        )
    )



def atomic_write(path, content):
    # Same-directory rename prevents partial JSON after interruption. Sync both
    # the file and the name change before a scheduled checkpoint may issue HTTP.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write((json.dumps(content, indent=2) + "\n").encode())
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
            with closing_fd(os.open(path.parent, os.O_RDONLY)) as fd:
                os.fsync(fd)
        finally:
            temporary.unlink(missing_ok=True)


@contextmanager
def closing_fd(fd):
    try:
        yield fd
    finally:
        os.close(fd)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def checked_pin(commit):
    if not re.fullmatch("[0-9a-f]{40}", commit) or git("rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("Use the full reviewed commit checked out at HEAD")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("The pinned soak checkout must be clean")
    config_bytes = (ROOT / CONFIG).read_bytes()
    if config_bytes != git("show", f"{commit}:{CONFIG}"):
        raise ValueError("Source config differs from the reviewed commit")
    configs = json.loads(config_bytes)["sources"]
    by_name = {source["name"]: source for source in configs}
    if (len(configs) != len(by_name) or set(by_name) != {*SOURCES, "olx"}
            or by_name["olx"].get("enabled") is not False):
        raise ValueError("Expected the three reviewed sources and explicitly disabled OLX")
    for name in SOURCES:
        source = by_name[name]
        seed = source.get("search_urls_by_city", {}).get(CITY, [])
        hosts = {name + ".pl", "www." + name + ".pl"}
        if (source.get("enabled") is not True or source.get("mode") != "portal"
                or len(seed) != 1 or set(source["allowed_hosts"]) != hosts
                or not seed[0].startswith(tuple(f"https://{host}/" for host in hosts))
                or source.get("listing_urls") != [] or source.get("force_rechecks")
                or source.get("recheck_only") or source.get("token_env") or source.get("user_agent")
                or not 1 <= source.get("requests_per_minute", 0) <= 6
                or source.get("recheck_interval_minutes") != 360):
            raise ValueError(f"Source policy differs from the bounded Kraków soak: {name}")
    # Two origin controls plus one search and at most six detail URLs. The
    # pinned connector allows one retry total for each logical request.
    return {
        "commit": commit, "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "sources": list(SOURCES), "city": CITY,
        "budget": {
            **LIMITS, "max_logical_robots": 2, "max_attempts_per_request": 2,
            "max_network_attempts": 18, "interval_hours": 6, "admission_minutes": 10,
            "cycle_timeout_seconds": CYCLE_TIMEOUT, "recheck_interval_minutes": 360,
            "requests_per_minute": {name: by_name[name]["requests_per_minute"] for name in SOURCES},
        },
    }


def new_manifest(run_id, pin, now):
    return {
        "version": 1, "run_id": run_id, "pin": pin,
        "runtime": {
            "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
        },
        "started_at": timestamp(now), "observed_through": timestamp(now),
        "ends_at": timestamp(now + 12 * INTERVAL), "runner_gaps": [],
        "cycles": [
            {"id": f"cycle-{index + 1:02}", "scheduled_at": timestamp(now + index * INTERVAL),
             "state": "pending"}
            for index in range(12)
        ],
    }


def observe(manifest, now, *, resumed=False):
    previous = instant(manifest["observed_through"])
    now = min(now, instant(manifest["ends_at"]))
    if now < previous:
        raise ValueError("UTC clock precedes the saved heartbeat; wait for the clock to catch up")
    if now > previous and (resumed or (now - previous).total_seconds() > HEARTBEAT_LIMIT):
        manifest["runner_gaps"].append({
            "from": timestamp(previous), "to": timestamp(now),
            "reason": "runner_restart" if resumed else "heartbeat_gap",
        })
    manifest["observed_through"] = timestamp(now)


def advance(manifest, now):
    """Mark expired slots missed and return at most one due slot. Never catch up HTTP."""
    due = None
    for cycle in manifest["cycles"]:
        if cycle["state"] != "pending":
            continue
        scheduled = instant(cycle["scheduled_at"])
        if now > scheduled + ADMISSION:
            cycle.update(state="missed", reason="runner_unavailable_at_admission",
                         finished_at=timestamp(now), eligible=False)
        elif scheduled <= now:
            due = cycle
    return due


def catalog_snapshot(directory, since=None):
    """Read aggregate counts and persisted worker checkpoints from the owned SQLite catalog."""
    database = directory / "catalog.db"
    tables = ("listings", "source_listings", "observations", "event_receipts", "notifications", "outbox")
    queue_filters = {
        "outbox": "delivered_at IS NULL", "alert_events": "processed_at IS NULL",
        "email_deliveries": "status IN ('pending', 'retry')",
        "push_deliveries": "status IN ('pending', 'retry', 'receipt')",
    }
    fields = ("changed", "daily_checkpoints", "rent_changes", "status_changes", "delisted")
    snapshot = {
        "rows": dict.fromkeys(tables, 0), "queues": dict.fromkeys(queue_filters, 0),
        "history": dict.fromkeys(fields, 0),
    }
    if not database.exists():
        return snapshot, None, {}
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.execute("BEGIN")
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        schema = None
        if "realtoruch_local_migrations" in present:
            schema = [row[0] for row in db.execute(
                "SELECT version FROM realtoruch_local_migrations WHERE database_name = 'rentals' ORDER BY version"
            )]
        for table in tables:
            if table in present:
                snapshot["rows"][table] = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table, condition in queue_filters.items():
            if table in present:
                snapshot["queues"][table] = db.execute(f"SELECT count(*) FROM {table} WHERE {condition}").fetchone()[0]
        if "observations" in present:
            values = db.execute("""
                WITH history AS (
                    SELECT *, lag(rent_pln) OVER series AS prior_rent, lag(status) OVER series AS prior_status
                    FROM observations WINDOW series AS (PARTITION BY source_listing_id ORDER BY observed_at)
                )
                SELECT count(*) FILTER (WHERE changed),
                       count(*) FILTER (WHERE NOT changed),
                       count(*) FILTER (WHERE prior_rent <> rent_pln),
                       count(*) FILTER (WHERE prior_status <> status),
                       count(*) FILTER (WHERE prior_status IS NOT NULL AND prior_status <> 'inactive'
                                        AND status = 'inactive')
                FROM history
            """).fetchone()
            snapshot["history"].update(zip(fields, values))
        recovered = {}
        if since and "collection_runs" in present:
            since_sql = instant(since).replace(tzinfo=None).isoformat(sep=" ")
            for checkpoint, name, status, finished, report in db.execute(
                "SELECT id, source, status, finished_at, report FROM collection_runs "
                "WHERE started_at >= ? AND city = ? ORDER BY started_at", (since_sql, CITY),
            ):
                source = json.loads(report) if report else {}
                recovered[name] = {
                    **source, "status": status if finished else "interrupted", "checkpoint_id": checkpoint,
                    "attempted": True, **({} if finished else {"reason": "unfinished_worker_checkpoint"}),
                }
        return snapshot, schema, recovered


def finish_cycle(manifest, cycle, now, counts, schema, recovered, reports, *, reason=None):
    returned = {report["source"]: report for report in reports or []}
    sources = {}
    for name in SOURCES:
        if name in returned:
            report = returned[name]
            sources[name] = {**recovered.get(name, {}), **report,
                             "attempted": report["status"] != "deferred"}
        elif name in recovered:
            sources[name] = recovered[name]
        else:
            sources[name] = {"status": "unobserved", "attempted": False}
    violations = []
    for name, report in sources.items():
        for field, bound in {
            "search_pages": 1, "new_details": 2, "due_rechecks": 4, "checked": 6,
            "robots_attempts": 4, "retry_attempts": 9, "network_attempts": 18,
        }.items():
            if report.get(field, 0) > bound:
                violations.append({"source": name, "field": field, "actual": report[field], "limit": bound})
    all_deferred = all(report["status"] == "deferred" for report in sources.values())
    fully_observed = all(report["status"] in ("succeeded", "failed", "partial", "deferred")
                         for report in sources.values())
    before = cycle["counts_before"]["history"]
    cycle.update(
        state=("deferred" if all_deferred else "completed" if fully_observed else "interrupted"),
        finished_at=timestamp(now), sources=sources,
        eligible=fully_observed and not all_deferred, counts_after=counts,
        history_delta={key: value - before[key] for key, value in counts["history"].items()},
        budget_violations=violations,
    )
    if reason:
        cycle["reason"] = reason
    manifest.update(latest_counts=counts, schema=schema)


def result_path(directory, cycle):
    return directory / f"{cycle['id']}.json"


def checkpoint(manifest_path, manifest, now, *, resumed=False):
    observe(manifest, now, resumed=resumed)
    atomic_write(manifest_path, manifest)


def collect_child(manifest_path, cycle_id, lock_fd):
    """Start one admitted cycle in a fresh process with a minimal environment."""
    import fcntl

    # The inherited open file description keeps the run locked if the parent dies.
    if not os.path.samestat(os.fstat(lock_fd), (manifest_path.parent / "runner.lock").stat()):
        raise ValueError("Collector requires the run's inherited lock")
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads(manifest_path.read_text())
    cycle = next(cycle for cycle in manifest["cycles"] if cycle["id"] == cycle_id)
    if cycle["state"] != "running" or result_path(manifest_path.parent, cycle).exists():
        raise ValueError("Collector checkpoint is not open")
    if datetime.now(timezone.utc) > instant(cycle["scheduled_at"]) + ADMISSION:
        raise ValueError("Collector missed its admission window")
    signal.alarm(CYCLE_TIMEOUT)
    from realtoruch.db import init_db
    from realtoruch.worker import CollectionFailed, collect

    init_db()
    try:
        reports = collect(source_names=SOURCES, limits=LIMITS, city=CITY, workers=len(SOURCES))
    except CollectionFailed as exc:
        reports = exc.reports
    atomic_write(result_path(manifest_path.parent, cycle), {"sources": reports})
    return 0


def run_cycle(manifest_path, manifest, cycle, lock_fd):
    directory = manifest_path.parent
    key_path = directory / "phone-key"
    if not key_path.exists():
        with os.fdopen(
            os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as handle:
            handle.write(secrets.token_urlsafe(48))
    environment = {
        "PATH": os.defpath, "PYTHONPATH": str(ROOT / "backend"), "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
        "DATABASE_URL": f"sqlite:///{directory / 'catalog.db'}",
        "AUTH_DATABASE_URL": f"sqlite:///{directory / 'auth.db'}",
        "CONNECTORS_CONFIG": str(ROOT / CONFIG), "PHONE_HASH_KEY": key_path.read_text(),
        "DEMO_MODE": "false", "EMAIL_DELIVERY_MODE": "file",
        "EMAIL_PREVIEW_DIRECTORY": str(directory / "mail"),
    }
    args = [sys.executable, str(Path(__file__).resolve()), "_soak-cycle",
            str(manifest_path), cycle["id"], str(lock_fd)]
    log_path = directory / f"{cycle['id']}.log"
    with log_path.open("xb") as log:
        process = subprocess.Popen(args, cwd=directory, env=environment, pass_fds=(lock_fd,),
                                   stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + CYCLE_TIMEOUT
        try:
            while process.poll() is None and time.monotonic() < deadline:
                try:
                    process.wait(timeout=min(HEARTBEAT, max(0, deadline - time.monotonic())))
                except subprocess.TimeoutExpired:
                    checkpoint(manifest_path, manifest, datetime.now(timezone.utc))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return process.returncode


def finalize(manifest_path, manifest, cycle, now, *, reason=None):
    path = result_path(manifest_path.parent, cycle)
    reports = json.loads(path.read_text())["sources"] if path.exists() else None
    counts, schema, recovered = catalog_snapshot(manifest_path.parent, cycle["started_at"])
    finish_cycle(manifest, cycle, now, counts, schema, recovered, reports, reason=reason)
    checkpoint(manifest_path, manifest, now)


def run_soak(directory, run_id, pin, lock_fd):
    path = directory / "manifest.json"
    now = datetime.now(timezone.utc)
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest["version"] != 1 or manifest["run_id"] != run_id or manifest["pin"] != pin:
            raise ValueError("Manifest pin, format or run ID differs; keep the original checkout/config")
        checkpoint(path, manifest, now, resumed=True)
        for cycle in manifest["cycles"]:
            if cycle["state"] == "running":
                finalize(path, manifest, cycle, now, reason="recovered_without_replay")
    else:
        if {item.name for item in directory.iterdir()} - {"runner.lock"}:
            raise ValueError("New run requires an empty private directory")
        manifest = new_manifest(run_id, pin, now)
        manifest["baseline_counts"], _, _ = catalog_snapshot(directory)
        checkpoint(path, manifest, now)
    print(json.dumps({"run_id": run_id, "manifest": str(path),
                      "started_at": manifest["started_at"], "target_end": manifest["ends_at"]}), flush=True)
    while True:
        now = datetime.now(timezone.utc)
        observe(manifest, now)
        cycle = advance(manifest, now)
        if cycle:
            if checked_pin(pin["commit"]) != pin:
                raise ValueError("Soak pin changed before the scheduled cycle")
            now = datetime.now(timezone.utc)
            if now > instant(cycle["scheduled_at"]) + ADMISSION:
                continue
            cycle.update(state="running", started_at=timestamp(now),
                         counts_before=catalog_snapshot(directory)[0])
            checkpoint(path, manifest, now)
            code = run_cycle(path, manifest, cycle, lock_fd)
            finalize(path, manifest, cycle, datetime.now(timezone.utc),
                     reason=f"collector_exit_{code}" if code else None)
            print(json.dumps({"cycle": cycle["id"], "state": cycle["state"],
                              "sources": {key: val["status"] for key, val in cycle["sources"].items()}}),
                  flush=True)
            if cycle["budget_violations"]:
                print(json.dumps(aggregate(manifest)), flush=True)
                return 1
            continue
        checkpoint(path, manifest, now)
        if now >= instant(manifest["ends_at"]):
            report = aggregate(manifest)
            print(json.dumps(report), flush=True)
            return int(report["status"] != "VERIFIED")
        next_due = min((instant(row["scheduled_at"]) for row in manifest["cycles"]
                        if row["state"] == "pending"), default=instant(manifest["ends_at"]))
        time.sleep(min(HEARTBEAT, max(0, (next_due - datetime.now(timezone.utc)).total_seconds())))


def soak(argv):
    parser = argparse.ArgumentParser(description="Run/resume the pinned 72-hour Kraków collection soak")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--commit", required=True, help="Full reviewed SHA checked out in this worktree")
    args = parser.parse_args(argv)
    try:
        import fcntl
    except ImportError:
        parser.error("The soak requires a POSIX runner with process locks")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", args.run_id):
        parser.error("Use a run ID of up to 64 letters, digits, dashes and underscores")
    try:
        pin = checked_pin(args.commit)
        directory = RUNS / args.run_id
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.resolve() != directory or directory.stat().st_mode & 0o077:
            raise ValueError("The run directory must be private and must not resolve through symlinks")
        artifacts = (*ARTIFACTS, ".env", *(f"cycle-{i:02}.{ext}" for i in range(1, 13) for ext in ("log", "json")))
        if any((directory / name).is_symlink() for name in artifacts) or (directory / ".env").exists():
            raise ValueError("Symlinked run artifacts and local .env files are forbidden")
        for name in ("catalog.db", "auth.db", "phone-key"):
            artifact = directory / name
            if artifact.exists() and artifact.stat().st_nlink != 1:
                raise ValueError("Run-owned data must not be hard-linked")
        fd = os.open(directory / "runner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with closing_fd(fd):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                parser.error("A runner or its current collector already owns this run")
            return run_soak(directory, args.run_id, pin, fd)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["soak"]:
        return soak(argv[1:])
    if argv[:1] == ["_soak-cycle"]:
        return collect_child(Path(argv[1]), argv[2], int(argv[3]))
    return one_shot(argv)


if __name__ == "__main__":
    sys.exit(main())
