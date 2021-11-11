#!/usr/bin/env python3
"""Run the complete local demo. Ctrl-C shuts down all child processes."""

import os
import signal
import subprocess
import sys
import time

from local import ROOT, local_environment

os.chdir(ROOT)
live = "--live" in sys.argv
journey = "--journey" in sys.argv
environment = local_environment(live=live, journey=journey)
python = str(ROOT / ".venv/bin/python")
subprocess.run(
    [python, "-m", "realtoruch.worker", "migrate"], env=environment, check=True
)
if journey:
    subprocess.run(
        [python, "scripts/journey.py", "prepare"], env=environment, check=True
    )
elif not live:
    subprocess.run([python, "-m", "realtoruch.seed"], env=environment, check=True)
processes = []
commands = [
    ([python, "-m", "realtoruch.worker", "alerts", "--loop"], ROOT),
    ([python, "-m", "realtoruch.auth_jobs", "--loop"], ROOT),
    (
        [
            python,
            "-m",
            "uvicorn",
            "realtoruch.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        ROOT,
    ),
    (
        [
            python,
            "-m",
            "uvicorn",
            "realtoruch.auth:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        ROOT,
    ),
    (
        [
            python,
            "-m",
            "http.server",
            "8081",
            "--bind",
            "127.0.0.1",
            "--directory",
            str(ROOT / "apps/mobile/dist"),
        ]
        if "--static" in sys.argv
        else ["npm", "run", "web"],
        ROOT / "apps/mobile",
    ),
]


def stop(*_):
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
    sys.exit(0)


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    for command, cwd in commands:
        processes.append(
            subprocess.Popen(command, cwd=cwd, env=environment, start_new_session=True)
        )
    print(
        "Web: http://localhost:8081 | API docs: http://localhost:8000/docs", flush=True
    )
    while all(process.poll() is None for process in processes):
        time.sleep(1)
    failed = next(
        process.returncode for process in processes if process.poll() is not None
    )
    print(f"A service exited ({failed}); stopping the remaining services.", flush=True)
finally:
    stop()
