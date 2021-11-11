#!/usr/bin/env python3
"""Collect a bounded batch of real listings into the separate local live catalog."""

import subprocess
import sys

from local import ROOT, local_environment


def main():
    environment = local_environment(live=True)
    python = str(ROOT / ".venv/bin/python")
    subprocess.run(
        [python, "-m", "realtoruch.worker", "migrate"],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    return subprocess.run(
        [
            python,
            "-m",
            "realtoruch.worker",
            "collect",
            "--report",
            str(ROOT / ".local/last-collection.json"),
            *sys.argv[1:],
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
