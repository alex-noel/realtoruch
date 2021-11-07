#!/usr/bin/env python3
"""Create Git commits with an optional task selector."""

import re
import subprocess
import sys
from pathlib import Path


def task_arguments(arguments):
    """Remove our task selector without changing normal git commit arguments."""
    result, task = [], None
    index = 0
    while index < len(arguments):
        value = arguments[index]
        if value == "--task" or value.startswith("--task="):
            if task is not None:
                raise SystemExit("Specify --task only once.")
            if value == "--task":
                index += 1
                if index >= len(arguments):
                    raise SystemExit("--task requires Q01 through Q40.")
                task = arguments[index]
            else:
                task = value.partition("=")[2]
            if not re.fullmatch(r"Q(?:0[1-9]|[12][0-9]|3[0-9]|40)", task):
                raise SystemExit("--task requires Q01 through Q40.")
        else:
            result.append(value)
        index += 1
    return result


def main() -> int:
    arguments = task_arguments(sys.argv[1:])
    return subprocess.run(
        ["git", "commit", *arguments],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
