#!/usr/bin/env python3
"""Run the complete local demo. Ctrl-C shuts down all child processes."""

import json
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
local = ROOT / ".local"
local.mkdir(exist_ok=True)
secret_file = local / "development-secrets.json"

if not secret_file.exists():
    secret_file.write_text(
        json.dumps(
            {
                name: secrets.token_urlsafe(48)
                for name in ("JWT_SECRET", "PHONE_HASH_KEY", "INTERNAL_API_KEY")
            }
        )
    )
    secret_file.chmod(0o600)
environment = {
    **os.environ,
    **json.loads(secret_file.read_text()),
    "DEMO_MODE": "true",
    "EXPO_NO_TELEMETRY": "1",
    "EXPO_OFFLINE": "1",
    "CONNECTORS_CONFIG": str(ROOT / "config/sources.json"),
    "DATABASE_URL": f"sqlite:///{local}/rentals.db",
    "AUTH_DATABASE_URL": f"sqlite:///{local}/auth.db",
}
python = str(ROOT / ".venv/bin/python")
subprocess.run([python, "-m", "realtoruch.seed"], env=environment, check=True)
processes = []
commands = [
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
