#!/usr/bin/env python3
"""Back up local SQLite catalogs and verify restoration into new isolated files."""

import argparse
import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from local import ROOT
from restore_manifest import isolated_main, profile_args, status


def inventory(connection):
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    counts = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        counts[table] = connection.execute(f"SELECT count(*) FROM {quoted}").fetchone()[
            0
        ]
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    profile_args(parser).add_argument("--catalog", choices=["sample", "live", "journey"],
                                      help="Legacy check of the explicitly chosen existing catalog")
    args = parser.parse_args()
    if not args.catalog:
        return status(lambda: isolated_main("sqlite", args))
    rental = {
        "sample": "rentals.db",
        "live": "live-rentals.db",
        "journey": "journey-rentals.db",
    }[args.catalog]
    files = [ROOT / ".local" / rental, ROOT / ".local/auth.db"]
    if not all(path.is_file() for path in files):
        parser.error("Start the selected local catalog once so both databases exist.")
    destination = (
        ROOT
        / ".local/backups"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    destination.mkdir(parents=True, mode=0o700)
    evidence = {}
    for source in files:
        saved = destination / source.name
        with (
            sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as current,
            sqlite3.connect(saved) as backup,
        ):
            current.backup(
                backup
            )  # SQLite online backup includes committed WAL content.
        saved.chmod(0o600)
        with tempfile.TemporaryDirectory(prefix="realtoruch-restore-") as temporary:
            restored_path = Path(temporary) / source.name
            with (
                sqlite3.connect(saved) as backup,
                sqlite3.connect(restored_path) as restored,
            ):
                backup.backup(restored)
                assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert not restored.execute("PRAGMA foreign_key_check").fetchall()
                assert inventory(backup) == inventory(restored)
                evidence[source.name] = {
                    "tables": inventory(restored),
                    "bytes": saved.stat().st_size,
                    "sha256": hashlib.sha256(saved.read_bytes()).hexdigest(),
                    "restored_integrity": "ok",
                }
    (destination / "manifest.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "backup_directory": str(destination),
                "verified_databases": list(evidence),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
