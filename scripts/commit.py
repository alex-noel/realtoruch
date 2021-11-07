#!/usr/bin/env python3
"""Create a local commit with both Git dates five calendar years in the past."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> int:
    arguments = sys.argv[1:]
    if any(arg == "--date" or arg.startswith("--date=") for arg in arguments):
        raise SystemExit("The repository convention controls --date automatically.")

    now = datetime.now(ZoneInfo("Europe/Warsaw"))
    try:
        backdated = now.replace(year=now.year - 5)
    except ValueError:  # February 29 in a non-leap target year.
        backdated = now.replace(year=now.year - 5, day=28)
    timestamp = backdated.isoformat(timespec="seconds")
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_DATE": timestamp,
    }
    return subprocess.run(
        ["git", "commit", f"--date={timestamp}", *arguments],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
