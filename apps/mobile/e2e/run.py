#!/usr/bin/env python3
"""Run browser checks with disposable loopback services and a private catalog."""
import base64
import json
import os
import secrets
import signal
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
MOBILE = ROOT / 'apps/mobile'
run = os.environ.get('VERIFY_RUN_ID', uuid4().hex[:12])
if not run.isascii() or not run.replace('-', '').isalnum():
    raise SystemExit('Invalid run ID')
dest = ROOT / '.local/verification/T18' / run
dest.mkdir(parents=True, exist_ok=False, mode=0o700)

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

api, auth, web = [port() for _ in range(3)]
env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'SYSTEMROOT', 'PLAYWRIGHT_BROWSERS_PATH', 'VERIFY_BROWSER_ARTIFACTS_DIR') if k in os.environ}
sys.path.insert(0, str(ROOT / 'backend'))
from realtoruch.settings import Settings
for key, field in Settings.model_fields.items():
    if isinstance(field.default, (str, int, bool)):
        env[key.upper()] = str(field.default).lower() if isinstance(field.default, bool) else str(field.default)
env.update(PYTHONPATH=str(ROOT / 'backend'), DATABASE_URL=f'sqlite:///{dest}/rentals.db',
    AUTH_DATABASE_URL=f'sqlite:///{dest}/auth.db', EMAIL_DELIVERY_MODE='file',
    EMAIL_PREVIEW_DIRECTORY=str(dest / 'mail'), CONNECTORS_CONFIG=str(ROOT / 'config/sources.json'),
    JWT_SECRET=secrets.token_urlsafe(48), PHONE_HASH_KEY=secrets.token_urlsafe(48),
    INTERNAL_API_KEY=secrets.token_urlsafe(48), REQUEST_LIMIT_PER_MINUTE='10000',
    AUTH_REQUEST_LIMIT_PER_MINUTE='10000', DEMO_MODE='true', EXPO_PUSH_ENABLED='false',
    EXPO_OFFLINE='1', EXPO_NO_TELEMETRY='1', EXPO_NO_DOTENV='1', CI='true',
    EXPO_PUBLIC_API_URL=f'http://127.0.0.1:{api}', EXPO_PUBLIC_AUTH_URL=f'http://127.0.0.1:{auth}',
    EXPO_PUBLIC_MAP_TILE_URL=f'http://127.0.0.1:{web}/tile.png',
    CORS_ORIGINS=f'http://127.0.0.1:{web}', AUTH_SERVICE_URL=f'http://127.0.0.1:{auth}',
    API_BASE_URL=f'http://127.0.0.1:{api}', PUBLIC_WEB_URL=f'http://127.0.0.1:{web}',
    E2E_WEB_URL=f'http://127.0.0.1:{web}', E2E_AUTH_URL=f'http://127.0.0.1:{auth}', E2E_API_URL=f'http://127.0.0.1:{api}', E2E_ALLOWED_PORTS=f'{web},{api},{auth}',
    E2E_OUTPUT_DIR=str(dest / 'playwright'), E2E_MAIL_DIR=str(dest / 'mail'),
    E2E_SUMMARY_FILE=str(dest / 'summary.json'))
token = secrets.token_urlsafe(32)
(dest / 'fixture-token').write_text(token)
(dest / 'fixture-token').chmod(0o600)
env.update(E2E_RUN_DIR=str(dest), E2E_RUN_TOKEN=token, E2E_PYTHON=sys.executable)
if os.environ.get('T18_FAULT_DUPLICATE') == '1':
    env['T18_FAULT_DUPLICATE'] = '1'
processes = []
browser_process = None
def stop_on_term(_signum, _frame):
    raise KeyboardInterrupt()
signal.signal(signal.SIGTERM, stop_on_term)
try:
    subprocess.run([sys.executable, '-m', 'realtoruch.worker', 'migrate'], cwd=ROOT, env=env, check=True)
    subprocess.run(['npm', 'run', 'build:web', '--', '--output-dir', str(dest / 'dist')], cwd=MOBILE, env=env, check=True)
    # A tiny local tile keeps Leaflet fully offline.
    (dest / 'dist/tile.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII='))
    commands = [
        [sys.executable, '-m', 'uvicorn', 'realtoruch.api:app', '--host', '127.0.0.1', '--port', str(api)],
        [sys.executable, '-m', 'uvicorn', 'realtoruch.auth:app', '--host', '127.0.0.1', '--port', str(auth)],
        [sys.executable, '-m', 'realtoruch.worker', 'alerts', '--loop'],
        [sys.executable, '-m', 'realtoruch.auth_jobs', '--loop'],
        [sys.executable, '-m', 'http.server', str(web), '--bind', '127.0.0.1', '--directory', str(dest / 'dist')],
    ]
    with (dest / 'services.log').open('w') as log:
        for command in commands:
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log))
        for url in (f'http://127.0.0.1:{api}/docs', f'http://127.0.0.1:{auth}/docs', env['E2E_WEB_URL']):
            deadline = time.monotonic() + 30
            while True:
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError('A local service exited during startup')
                try:
                    with urllib.request.urlopen(url, timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Local service readiness timed out')
                    time.sleep(.1)
        browser_process = subprocess.Popen(['node', 'node_modules/@playwright/test/cli.js', 'test', *sys.argv[1:]], cwd=MOBILE, env=env, start_new_session=True)
        result_code = browser_process.wait()
        output = dest / 'playwright'
        artifact_dir = Path(env['VERIFY_BROWSER_ARTIFACTS_DIR']) if env.get('VERIFY_BROWSER_ARTIFACTS_DIR') else None
        traces = list(output.rglob('trace.zip')) + list(output.rglob('raw-fault-trace.zip'))
        trace_counts = {'retained': 0, 'omitted': 0}
        for index, raw in enumerate(traces):
            safe = raw.parent / 'sanitized-trace.zip'
            try:
                sanitized = subprocess.run([sys.executable, str(MOBILE / 'e2e/sanitize_fault.py'), str(dest), str(raw), str(safe)], capture_output=True)
                trace_counts['retained' if sanitized.returncode == 0 else 'omitted'] += 1
                if sanitized.returncode == 0 and artifact_dir:
                    (artifact_dir / 'traces').mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(safe, artifact_dir / 'traces' / f'failure-{index}.zip')
            finally:
                raw.unlink(missing_ok=True)
        (dest / 'trace-handling.json').write_text(json.dumps(trace_counts) + '\n')
        if artifact_dir:
            for index, shot in enumerate(output.rglob('test-failed-*.png')):
                (artifact_dir / 'screenshots').mkdir(parents=True, exist_ok=True)
                shutil.copyfile(shot, artifact_dir / 'screenshots' / f'failure-{index}.png')
        sys.exit(result_code)
finally:
    # Stop the entire owned browser process group before removing raw traces.
    if browser_process is not None and browser_process.poll() is None:
        try:
            os.killpg(browser_process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            browser_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(browser_process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            browser_process.wait()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                os.killpg(browser_process.pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.05)
        else:
            try:
                os.killpg(browser_process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    for process in reversed(processes):
        process.terminate()
    for process in reversed(processes):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    # Never retain unredacted Playwright network captures, including interrupted runs.
    for pattern in ('trace.zip', 'raw-fault-trace.zip'):
        for raw_trace in (dest / 'playwright').rglob(pattern):
            raw_trace.unlink(missing_ok=True)
    print(f'Private run data: {dest}', flush=True)
