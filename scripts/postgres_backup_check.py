#!/usr/bin/env python3
"""Rehearse pg_dump/pg_restore on an explicitly labelled disposable local container.

Only containers labelled realtoruch.verification=true are accepted. Source data
must be quiescent for the digest comparison. Restores use newly created databases;
no existing database is overwritten. Cloud/remote restoration is out of scope.
"""

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from uuid import uuid4

from local import ROOT
from restore_manifest import isolated_main, profile_args, status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    profile_args(parser).add_argument("--container", help="Legacy check of an explicitly labelled disposable container")
    parser.add_argument("--user", default="rentals")
    parser.add_argument("--databases", nargs="+", default=["rentals", "auth"])
    args = parser.parse_args()
    if not args.container:
        return status(lambda: isolated_main("postgres", args))
    if not all(
        re.fullmatch(r"[a-z_][a-z0-9_]{0,50}", value)
        for value in [args.user, *args.databases]
    ):
        parser.error("Use simple lowercase PostgreSQL identifiers")
    details = json.loads(
        subprocess.check_output(["docker", "inspect", args.container])
    )[0]
    if (details["Config"].get("Labels") or {}).get("realtoruch.verification") != "true":
        parser.error(
            "This command only accepts a disposable container labelled realtoruch.verification=true"
        )

    def command(*values, data=None):
        return subprocess.run(
            ["docker", "exec", "-i", args.container, *values],
            input=data,
            capture_output=True,
            check=True,
        ).stdout

    def query(database, sql):
        return (
            command(
                "psql",
                "-X",
                "-A",
                "-t",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                args.user,
                "-d",
                database,
                "-c",
                sql,
            )
            .decode()
            .strip()
        )

    def inventory(database):
        tables = query(
            database,
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
        ).splitlines()
        result = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            # Test-container datasets only: sorted logical rows compare content as
            # well as counts, independent of physical row order after restoration.
            value = query(
                database,
                f"SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text, E'\\n' ORDER BY row_to_json(t)::text), '')) FROM public.{quoted} t",
            )
            count, digest = value.split("|")
            result[table] = {"rows": int(count), "content_digest": digest}
        return result

    destination = (
        ROOT
        / ".local/backups"
        / ("postgres-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    )
    destination.mkdir(parents=True, mode=0o700)
    evidence = {}
    for database in args.databases:
        before = inventory(database)
        if not before:
            parser.error(
                f"{database} has no public tables; initialize the test schema first"
            )
        dump = command(
            "pg_dump",
            "-U",
            args.user,
            "-d",
            database,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
        )
        saved = destination / (database + ".dump")
        with saved.open("xb") as handle:
            saved.chmod(0o600)
            handle.write(dump)
        restore_name = "restore_" + uuid4().hex
        command("createdb", "-U", args.user, restore_name)
        try:
            command(
                "pg_restore",
                "-U",
                args.user,
                "-d",
                restore_name,
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                data=dump,
            )
            after = inventory(restore_name)
            if before != after:
                raise RuntimeError(
                    "Restored data differs; ensure the test source is quiescent"
                )
            evidence[database] = {
                "tables": after,
                "bytes": len(dump),
                "sha256": hashlib.sha256(dump).hexdigest(),
                "restored_content": "matched",
            }
        finally:
            # This name was generated and created by this invocation only.
            command("dropdb", "-U", args.user, restore_name)
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
