#!/usr/bin/env python3
"""Run isolated offline or disposable real-service verification."""
import argparse
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
NOW = lambda: datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=['offline', 'services', 'web'])
    parser.add_argument('--run-id', default=uuid4().hex[:12])
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', args.run_id):
        parser.error('run ID must be lowercase letters, digits or hyphens (max 32)')
    dest = ROOT / '.local' / 'verification' / 'T01' / args.run_id
    dest.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = {'run_id': args.run_id, 'profile': args.profile, 'start_utc': NOW(), 'commands': [], 'counts': {'passed': 0, 'failed': 0, 'skipped': 0}, 'artifacts': [], 'platform': {'system': platform.platform(), 'python': sys.version, 'node': '', 'git_revision': ''}}
    containers = []
    owner = uuid4().hex
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'SYSTEMROOT') if key in os.environ}
    # Override even values loaded by pydantic from a developer's .env file.
    sys.path.insert(0, str(ROOT / 'backend'))
    from realtoruch.settings import Settings
    for key, field in Settings.model_fields.items():
        if isinstance(field.default, (str, int, bool)):
            env[key.upper()] = str(field.default).lower() if isinstance(field.default, bool) else str(field.default)
    env.update(CONNECTORS_CONFIG=str(ROOT / 'config' / 'sources.json'),
               EMAIL_DELIVERY_MODE='file', EMAIL_PREVIEW_DIRECTORY=str(dest / 'mail'),
               EXPO_PUSH_ENABLED='false', ELASTICSEARCH_URL='', SEARCH_SERVICE_URL='',
               CLOUDSQL_CONNECTION_NAME='', GCP_PROJECT='')
    env.update(PYTHONPATH=str(ROOT / 'backend'), VERIFY_RUN_ID=args.run_id, TMPDIR=str(dest),
               EXPO_OFFLINE='1', EXPO_NO_TELEMETRY='1', EXPO_NO_DOTENV='1')
    def command(cmd, cwd=ROOT, *, check=True):
        p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            output, _ = p.communicate(timeout=300)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            # Terminate the whole owned process group, including test descendants.
            try:
                os.killpg(p.pid, signal.SIGTERM if args.profile == 'web' else signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                p.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.communicate()
            report['commands'].append({'argv': cmd, 'exit_code': p.returncode, 'interrupted': isinstance(exc, KeyboardInterrupt), 'timed_out': isinstance(exc, subprocess.TimeoutExpired)})
            raise
        p.stdout = output
        report['commands'].append({'argv': cmd, 'exit_code': p.returncode})
        if check and p.returncode:
            raise RuntimeError('Command failed: ' + ' '.join(cmd))
        return p
    def cleanup(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, cleanup)
    status = 1
    try:
        report['platform']['node'] = command(['node', '--version']).stdout.strip()
        node_version = re.fullmatch(r'v24\.(\d+)\.(\d+)', report['platform']['node'])
        if sys.version_info[:2] != (3, 12) or not node_version or int(node_version.group(1)) < 3:
            raise RuntimeError('Python 3.12 and Node 24 are required')
        report['platform']['git_revision'] = command(['git', 'rev-parse', 'HEAD']).stdout.strip()
        report['platform']['worktree_dirty'] = bool(command(['git', 'status', '--porcelain', '--untracked-files=no']).stdout.strip())
        if args.profile == 'web':
            if 'PLAYWRIGHT_BROWSERS_PATH' in os.environ:
                env['PLAYWRIGHT_BROWSERS_PATH'] = os.environ['PLAYWRIGHT_BROWSERS_PATH']
            if 'VERIFY_BROWSER_ARTIFACTS_DIR' in os.environ:
                env['VERIFY_BROWSER_ARTIFACTS_DIR'] = os.environ['VERIFY_BROWSER_ARTIFACTS_DIR']
            env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
            result = command(['npm', 'run', 'test:e2e'], ROOT / 'apps/mobile', check=False)
            summary_path = ROOT / '.local' / 'verification' / 'T18' / args.run_id / 'summary.json'
            if not summary_path.exists():
                raise RuntimeError('Browser runner did not produce its aggregate summary')
            summary = json.loads(summary_path.read_text())
            report['counts'] = summary['counts']
            if result.returncode or summary['status'] != 'passed' or report['counts']['skipped'] or not report['counts']['passed']:
                raise RuntimeError('Browser tests failed, skipped or did not run')
            status = 0
            report['status'] = 'PASS'
            return 0
        if args.profile == 'services':
            database = 'r_' + args.run_id.replace('-', '_')
            for suffix, image, port, options in [
                ('pg', 'postgres:16-alpine', '5432', ['-e', 'POSTGRES_PASSWORD=verification', '-e', 'POSTGRES_USER=rentals', '-e', 'POSTGRES_DB=' + database]),
                ('es', 'docker.elastic.co/elasticsearch/elasticsearch:8.19.6', '9200', ['-e', 'discovery.type=single-node', '-e', 'xpack.security.enabled=false', '-e', 'ES_JAVA_OPTS=-Xms512m -Xmx512m'])]:
                name = 'realtoruch-t01-' + args.run_id + '-' + suffix
                # --pull never keeps verification offline; names are claimed atomically by Docker.
                containers.append(name)
                command(['docker', 'run', '-d', '--pull=never', '--name', name, '--label', 'realtoruch.verification=true', '--label', 'realtoruch.owner=' + owner, '-p', '127.0.0.1::' + port, *options, image])
            def mapped(name, port):
                return command(['docker', 'port', name, port]).stdout.strip().rsplit(':', 1)[1]
            pgport = mapped(containers[0], '5432/tcp')
            esport = mapped(containers[1], '9200/tcp')
            env['TEST_POSTGRES_URL'] = f'postgresql+psycopg://rentals:verification@127.0.0.1:{pgport}/{database}'
            env['TEST_ELASTICSEARCH_URL'] = f'http://127.0.0.1:{esport}'
            report['services'] = {'postgres_port': int(pgport), 'elasticsearch_port': int(esport), 'containers': containers[:], 'database': database, 'index_namespace': 'verify_' + args.run_id.replace('-', '_')}
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                for name in containers:
                    state = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', name], capture_output=True, text=True, timeout=10)
                    if state.returncode or state.stdout.strip() != 'true':
                        raise RuntimeError('Service exited before readiness: ' + name)
                pg = subprocess.run(['docker', 'exec', containers[0], 'pg_isready', '-U', 'rentals'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
                try:
                    with urllib.request.urlopen(env['TEST_ELASTICSEARCH_URL'], timeout=2) as response:
                        es = response.status == 200
                except Exception:
                    es = False
                if pg and es:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Services did not become ready within 120 seconds')
        xml = dest / 'results.xml'
        suites = ['backend/tests/test_infra_contract.py', 'backend/tests/test_service_integration.py', 'backend/tests/test_delivery_races.py',
                  'backend/tests/test_market_history.py', 'backend/tests/test_metrics.py',
                  'backend/tests/test_message_cursors.py', 'backend/tests/test_account_data.py',
                  'backend/tests/test_public_contract.py',
                  'backend/tests/test_restore_contract.py'] if args.profile == 'services' else ['backend/tests']
        selection = ['-k', 'not test_t26_helm and not test_t26_sqlite'] if args.profile == 'services' else []
        result = command([sys.executable, '-m', 'pytest', *suites, *selection, '--junitxml', str(xml)], check=False)
        if xml.exists():
            root = ET.parse(xml).getroot()
            cases = root.findall('.//testcase')
            report['counts'] = {'passed': sum(not list(c) for c in cases), 'failed': sum(c.find('failure') is not None or c.find('error') is not None for c in cases), 'skipped': sum(c.find('skipped') is not None for c in cases)}
            # Strip parametrizations: identifiers and XML can contain fixture secrets.
            report['failed_tests'] = [c.get('classname', '').split('[', 1)[0] + '::' + c.get('name', '').split('[', 1)[0] for c in cases if c.find('failure') is not None or c.find('error') is not None]
            report['skipped_tests'] = [c.get('classname', '').split('[', 1)[0] + '::' + c.get('name', '').split('[', 1)[0] for c in cases if c.find('skipped') is not None]
            xml.unlink()
        if result.returncode or (args.profile == 'services' and (report['counts']['skipped'] or not report['counts']['passed'])):
            raise RuntimeError('Tests failed or required service tests skipped')
        if args.profile == 'offline':
            command(['npm', 'run', 'typecheck'], ROOT / 'apps/mobile')
            package = json.loads((ROOT / 'apps/mobile/package.json').read_text())
            if 'test:unit' in package.get('scripts', {}):
                command(['npm', 'run', 'test:unit'], ROOT / 'apps/mobile')
            else:
                report['frontend_unit'] = 'NOT_IMPLEMENTED (T14 owns test:unit)'
        status = 0
        report['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc) if not isinstance(exc, KeyboardInterrupt) else 'Interrupted'
        print(report['error'], file=sys.stderr)
    finally:
        # Ignore further termination while cleaning; only remove a matching unguessable owner label.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        for name in reversed(containers):
            try:
                check = subprocess.run(['docker', 'inspect', '-f', '{{index .Config.Labels "realtoruch.owner"}}', name], capture_output=True, text=True, timeout=10)
                if check.returncode or check.stdout.strip() != owner:
                    continue
                p = subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                report['commands'].append({'argv': ['docker', 'rm', '-f', name], 'exit_code': p.returncode})
                if p.returncode:
                    status = 1
                    report['status'] = 'FAIL'
            except subprocess.TimeoutExpired:
                status = 1
                report['status'] = 'FAIL'
                report['error'] = 'Cleanup timed out for ' + name
        report['end_utc'] = NOW()
        report['exit_code'] = status
        report['artifacts'] = [str(dest.relative_to(ROOT) / 'report.json')]
        (dest / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Report:', dest / 'report.json')
    return status

if __name__ == '__main__':
    sys.exit(main())
