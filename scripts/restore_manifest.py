"""Private, run-owned two-database recovery for the T27 synthetic drill."""

import fcntl
import hashlib
import json
import math
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / '.local' / 'verification' / 'T27'
KINDS = ('rentals', 'auth')
FORMAT = 1
PG_ROLE = 't27_app'
SQL_TABLE = {'sqlite': 'realtoruch_local_migrations', 'postgres': 'realtoruch_migrations'}


class RecoveryError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise RecoveryError(message)


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def write_json(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.record-')
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(data, output, indent=2, sort_keys=True)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_json(path):
    require(path.is_file() and not path.is_symlink(), f'Missing or unsafe {path.name}')
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f'Invalid {path.name} object')
    return value


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def sql_id(name):
    return '"' + name.replace('"', '""') + '"'


def invoke(*args, stdin=None, stdout=subprocess.PIPE, timeout=60):
    env = {key: value for key, value in os.environ.items() if key != 'DOCKER_DEFAULT_PLATFORM'}
    result = subprocess.run(args, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, env=env, timeout=timeout,
                            check=False)
    if result.returncode:
        # Database and Docker diagnostics can contain private fixture details.
        raise RecoveryError(f'{args[0]} command failed (exit {result.returncode})')
    return result.stdout


def check_run_id(run_id):
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', run_id), 'Use a lowercase run ID of at most 32 characters')


class Run:
    def __init__(self, root, engine, *, new):
        self.root = root
        self.path = root / 'ownership.json'
        self.manifest = root / 'manifest.json'
        self.engine = engine
        check_run_id(root.name)
        if new:
            root.mkdir(parents=True, mode=0o700)
            self.record = {'format': FORMAT, 'engine': engine, 'run_id': root.name, 'owner': uuid4().hex}
            write_json(self.path, self.record)
        else:
            require(root.is_dir() and not root.is_symlink(), 'Missing or unsafe run directory')
            self.record = read_json(self.path)
        require(self.record.get('format') == FORMAT and self.record.get('engine') == engine
                and self.record.get('run_id') == root.name and isinstance(self.record.get('owner'), str)
                and re.fullmatch(r'[a-f0-9]{32}', self.record['owner']), 'Invalid ownership record')
        self.owner = self.record['owner']

    def update(self, **fields):
        self.record.update(fields)
        write_json(self.path, self.record)

    @contextmanager
    def lock(self):
        fd = os.open(self.root / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RecoveryError('The run is active; stop it before cleanup') from None
            yield


class SQLite:
    name = 'sqlite'
    version = sqlite3.sqlite_version
    extension = 'sqlite3'

    def __init__(self, run):
        self.run = run
        self.destination = run.root / 'restored'

    def source(self, kind):
        return self.run.root / f'source-{kind}.sqlite3'

    def target(self, kind):
        return self.destination / f'{kind}.sqlite3'

    def artifact_id(self, identifier):
        return str(identifier.relative_to(self.run.root))

    @staticmethod
    def connect(path):
        require(path.is_file() and not path.is_symlink(), 'SQLite database is missing or unsafe')
        return closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True))

    def inventory(self, path, kind):
        with self.connect(path) as db:
            require(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
                    and not db.execute('PRAGMA foreign_key_check').fetchall(), 'SQLite integrity check failed')
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            counts = {table: db.execute(f'SELECT count(*) FROM {sql_id(table)}').fetchone()[0]
                      for (table,) in tables.fetchall()}
            ledger = dict(db.execute(f'SELECT version, checksum FROM {SQL_TABLE[self.name]} WHERE database_name=?', (kind,)))
        return {'rows': counts, 'schema': ledger}

    def backup(self, source, path):
        require(not path.exists(), 'Backup artifact already exists')
        path.touch(mode=0o600, exist_ok=False)
        self.copy_database(source, path)

    def copy_database(self, source, path):
        with self.connect(source) as current, closing(sqlite3.connect(path)) as output:
            current.backup(output)

    def preflight(self, files, entries):
        for kind, path in files.items():
            require(all(entries[kind].get(key) == value for key, value in self.inventory(path, kind).items()),
                    f'SQLite backup inventory or schema differs for {kind}')

    def prepare(self):
        self.destination.mkdir(mode=0o700)
        write_json(self.destination / 'owner.json', {'owner': self.run.owner})

    def restore(self, kind, artifact):
        path = self.target(kind)
        path.touch(mode=0o600, exist_ok=False)
        claims = dict(self.run.record.get('sqlite_files', {}))
        stat = path.stat()
        claims[kind] = [stat.st_dev, stat.st_ino]
        self.run.update(sqlite_files=claims)
        self.copy_database(artifact, path)

    def cleanup(self):
        if not self.destination.exists() and not self.destination.is_symlink():
            return
        require(self.destination.is_dir() and not self.destination.is_symlink()
                and read_json(self.destination / 'owner.json') == {'owner': self.run.owner},
                'Restore directory does not belong to this run')
        expected = {'owner.json'} | {f'{kind}.sqlite3{suffix}' for kind in KINDS for suffix in ('', '-journal', '-wal', '-shm')}
        paths = list(self.destination.iterdir())
        require(all(path.name in expected and path.is_file() and not path.is_symlink() for path in paths),
                'Unrecognized restore content; nothing removed')
        claims = self.run.record.get('sqlite_files', {})
        for kind in KINDS:
            base = self.target(kind)
            stat = base.stat() if base.exists() else None
            related = [path for path in paths if path.name.startswith(base.name)]
            require(not related or (stat and claims.get(kind) == [stat.st_dev, stat.st_ino]),
                    'Unrecognized SQLite restore file; nothing removed')
        for path in paths:
            if path.name != 'owner.json':
                path.unlink()
        (self.destination / 'owner.json').unlink()
        self.destination.rmdir()


class Postgres:
    name = 'postgres'
    extension = 'dump'

    def __init__(self, run):
        self.run = run
        self.namespace = 't27_' + run.owner[:20]
        self.container_name = 'realtoruch-t27-' + run.owner
        self.container = run.record.get('postgres_container')
        self.password = uuid4().hex

    def start(self):
        require(self.container is None, 'Container already registered')
        self.require_local_docker()
        # --cidfile records the immutable ID even if interrupted before ownership.json is updated.
        cid = self.run.root / 'postgres.cid'
        self.container = invoke('docker', 'run', '--detach', '--pull=never', '--name', self.container_name,
                                '--cidfile', str(cid), '--label', 'realtoruch.verification=true',
                                '--label', f'realtoruch.owner={self.run.owner}',
                                '--publish', '127.0.0.1::5432', '--tmpfs', '/var/lib/postgresql/data',
                                '-e', f'POSTGRES_PASSWORD={self.password}', 'postgres:16-alpine').decode().strip()
        self.run.update(postgres_container=self.container)
        for _ in range(80):
            try:
                self.port = int(invoke('docker', 'port', self.container, '5432/tcp').decode().strip().split(':')[-1])
                # TCP avoids mistaking the bootstrap-only Unix socket for the final server.
                self.command('pg_isready', '-h', '127.0.0.1', '-U', 'postgres')
                break
            except (RecoveryError, ValueError):
                time.sleep(.25)
        else:
            raise RecoveryError('Disposable PostgreSQL did not start')
        self.version = self.query('postgres', 'SHOW server_version_num')
        self.architecture = self.command('uname', '-m').decode().strip()
        require(self.version.isdecimal() and int(self.version) // 10000 == 16, 'PostgreSQL 16 is required')
        self.dump_version = self.command('pg_dump', '--version').decode().strip()
        self.query('postgres', f"CREATE ROLE {PG_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{self.password}'")
        for kind in KINDS:
            self.claim(kind, self.source(kind), 'source_oids')

    @staticmethod
    def require_local_docker():
        context = invoke('docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}').decode().strip()
        require(all(endpoint.startswith(('unix:///', 'npipe:////./')) for endpoint in
                    (context, os.environ.get('DOCKER_HOST') or context)), 'A local Docker socket is required')

    def verify_container(self):
        self.require_local_docker()
        if not self.container:
            cid = self.run.root / 'postgres.cid'
            if not cid.exists() and not cid.is_symlink():
                return False
            require(cid.is_file() and not cid.is_symlink(), 'Unsafe PostgreSQL container ID record')
            self.container = cid.read_text().strip()
        require(re.fullmatch(r'[a-f0-9]{64}', self.container), 'Invalid PostgreSQL container identifier')
        matches = invoke('docker', 'container', 'ls', '--all', '--quiet', '--no-trunc',
                         '--filter', 'id=' + self.container).decode().splitlines()
        if not matches:
            return False
        require(matches == [self.container], 'Ambiguous PostgreSQL container identifier')
        inspect = json.loads(invoke('docker', 'inspect', '--type', 'container', self.container))[0]
        require(inspect['Id'] == self.container and inspect['Name'] == '/' + self.container_name
                and inspect['Config']['Labels'].get('realtoruch.owner') == self.run.owner
                and inspect['Config']['Labels'].get('realtoruch.verification') == 'true', 'PostgreSQL container is unowned')
        return True

    def command(self, *args, **kwargs):
        return invoke('docker', 'exec', '-i', self.container, *args, **kwargs)

    def query(self, database, statement):
        return self.command('psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', database,
                            '-c', statement).decode().strip()

    def source(self, kind):
        return f'{self.namespace}_source_{kind}'

    def target(self, kind):
        return f'{self.namespace}_restore_{kind}'

    def artifact_id(self, identifier):
        return identifier

    def create(self, name):
        self.query('postgres', f'CREATE DATABASE {sql_id(name)} OWNER {PG_ROLE} TEMPLATE template0')

    def claim(self, kind, name, field):
        self.create(name)  # Atomic collision refusal; no --clean or --create is used by pg_restore.
        self.query('postgres', f"COMMENT ON DATABASE {sql_id(name)} IS 't27:{self.run.owner}'")
        claims = dict(self.run.record.get(field, {}))
        claims[kind] = self.catalog()[name][0]
        self.run.update(**{field: claims})

    def inventory(self, database, kind):
        tables = self.query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
        counts, content = {}, {}
        require(tables and all(re.fullmatch(r'[a-z_][a-z_0-9]*', table) for table in tables),
                'Unexpected PostgreSQL table inventory')
        unions = ' UNION ALL '.join(
            f"SELECT '{table}', count(*), encode(sha256(convert_to(coalesce(string_agg(row_to_json(t)::text, "
            f"E'\\n' ORDER BY row_to_json(t)::text), ''), 'UTF8')), 'hex') FROM public.{sql_id(table)} t"
            for table in tables
        )
        for value in self.query(database, unions).splitlines():
            table, count, signature = value.split('|')
            counts[table], content[table] = int(count), signature
        ledger = dict(row.split('|') for row in self.query(
            database, f"SELECT version, checksum FROM {SQL_TABLE[self.name]} WHERE database_name='{kind}'").splitlines())
        require(self.query(database, f"SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner <> '{PG_ROLE}'") == '0',
                'Unexpected PostgreSQL table owner')
        return {'rows': counts, 'content': content, 'schema': ledger}

    def backup(self, source, path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            self.command('pg_dump', '-U', 'postgres', '-d', source, '--format=custom', '--no-owner',
                         '--no-privileges', stdout=output)

    def preflight(self, files, _entries):
        require(self.verify_container(), 'Owned PostgreSQL container is absent')
        for path in files.values():
            # Read the entire custom archive, including compressed table data, before creating any destination.
            with path.open('rb') as source:
                self.command('pg_restore', '--no-owner', '--no-privileges', '--file=/dev/null', stdin=source)

    def prepare(self):
        existing = self.catalog()
        require(not any(self.target(kind) in existing for kind in KINDS), 'Restore database already exists; refusing replacement')

    def restore(self, kind, artifact):
        name = self.target(kind)
        self.claim(kind, name, 'restore_oids')
        with artifact.open('rb') as source:
            self.command('pg_restore', '-U', 'postgres', '-d', name, '--role=' + PG_ROLE, '--single-transaction',
                         '--exit-on-error', '--no-owner', '--no-privileges', stdin=source)

    def catalog(self):
        return {name: (oid, owner, mark) for name, oid, owner, mark in (
            row.split('|', 3) for row in self.query('postgres', "SELECT datname, oid, pg_get_userbyid(datdba), coalesce(shobj_description(oid, 'pg_database'), '') FROM pg_database").splitlines())}

    def cleanup(self):
        if self.verify_container():
            self.cleanup_catalog(self.catalog())

    def cleanup_catalog(self, databases):
        claims = self.run.record.get('restore_oids', {})
        targets = {kind: self.target(kind) for kind in KINDS if self.target(kind) in databases}
        require(all(databases[name] == (claims.get(kind), PG_ROLE, 't27:' + self.run.owner)
                    for kind, name in targets.items()), 'Unrecognized restore database; nothing removed')
        for name in targets.values():
            self.query('postgres', f'DROP DATABASE {sql_id(name)}')

    def dispose(self):
        if not self.verify_container():
            return
        # Before removing even this run's container, refuse unknown databases inside it.
        databases = self.catalog()
        allowed = {'postgres', 'template0', 'template1', *(self.source(kind) for kind in KINDS),
                   *(self.target(kind) for kind in KINDS)}
        require(set(databases) <= allowed, 'Unrecognized database in disposable container; container retained')
        claims = self.run.record.get('source_oids', {})
        require(all(databases[self.source(kind)] == (claims.get(kind), PG_ROLE, 't27:' + self.run.owner)
                    for kind in KINDS if self.source(kind) in databases), 'Unrecognized source database; container retained')
        self.cleanup_catalog(databases)
        invoke('docker', 'rm', '--force', self.container)


def backup(run, backend, *, quiesced_at):
    require(not run.manifest.exists(), 'Backup manifest already exists')
    revision = invoke('git', '-C', str(ROOT), 'rev-parse', 'HEAD').decode().strip()
    dirty = bool(invoke('git', '-C', str(ROOT), 'status', '--porcelain'))
    start, tick = utc(), time.monotonic()
    databases = {}
    for kind in KINDS:
        path = run.root / f'{kind}.{backend.extension}'
        source = backend.source(kind)
        inventory = backend.inventory(source, kind)
        require(inventory['schema'] and inventory['rows'], 'Source has no migration ledger or tables')
        backend.backup(source, path)
        databases[kind] = {'source': backend.artifact_id(source), 'destination': backend.artifact_id(backend.target(kind)),
                           'file': path.name, 'sha256': digest(path), 'bytes': path.stat().st_size, **inventory}
    manifest = {'format': FORMAT, 'engine': run.engine, 'engine_version': backend.version, 'owner': run.owner,
                'run_id': run.root.name, 'commit': revision, 'worktree_dirty': dirty, 'quiesced_at': quiesced_at,
                'backup_start': start, 'backup_end': utc(), 'backup_seconds': round(time.monotonic() - tick, 3),
                'databases': databases}
    if backend.name == 'postgres':
        manifest['container_id'] = backend.container
        manifest['database_owner'] = PG_ROLE
        manifest['server_architecture'] = backend.architecture
        manifest['dump_version'] = backend.dump_version
    write_json(run.manifest, manifest)
    return manifest


def validate(run, backend, schemas):
    manifest = read_json(run.manifest)
    require(manifest.get('format') == FORMAT and manifest.get('engine') == backend.name
            and manifest.get('engine_version') == backend.version and manifest.get('owner') == run.owner
            and manifest.get('run_id') == run.root.name
            and isinstance(manifest.get('commit'), str) and re.fullmatch(r'[a-f0-9]{40,64}', manifest['commit']),
            'Incompatible backup manifest, engine version or ownership')
    if backend.name == 'postgres':
        require(manifest.get('container_id') == backend.container and manifest.get('database_owner') == PG_ROLE
                and manifest.get('dump_version') == backend.dump_version,
                'Incompatible PostgreSQL cluster, client or role')
    times = [datetime.fromisoformat(manifest[field]) for field in ('quiesced_at', 'backup_start', 'backup_end')]
    require(all(t.tzinfo is not None for t in times) and times == sorted(times), 'Invalid backup interval')
    seconds = manifest.get('backup_seconds')
    require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0, 'Invalid backup duration')
    entries = manifest.get('databases')
    require(isinstance(entries, dict) and set(entries) == set(KINDS), 'Manifest must contain both databases')
    files = {}
    for kind in KINDS:
        entry = entries[kind]
        path = run.root / f'{kind}.{backend.extension}'
        require(isinstance(entry, dict) and entry.get('source') == backend.artifact_id(backend.source(kind))
                and entry.get('destination') == backend.artifact_id(backend.target(kind))
                and entry.get('file') == path.name and entry.get('schema') == schemas[kind],
                f'Incompatible schema or namespace for {kind}')
        require(path.is_file() and not path.is_symlink() and entry.get('bytes') == path.stat().st_size
                and entry.get('sha256') == digest(path), f'Backup digest/size mismatch for {kind}')
        files[kind] = path
        rows = entry.get('rows')
        require(isinstance(rows, dict) and rows and all(type(count) is int and count >= 0 for count in rows.values()),
                f'Invalid table inventory for {kind}')
        if backend.name == 'postgres':
            content = entry.get('content')
            require(isinstance(content, dict) and set(content) == set(rows)
                    and all(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) for value in content.values()),
                    f'Invalid content digests for {kind}')
    backend.preflight(files, entries)
    return manifest, files


def restore(run, backend, schemas, *, checkpoint=lambda _kind: None):
    start, tick = utc(), time.monotonic()
    manifest, files = validate(run, backend, schemas)
    backend.prepare()
    for kind in KINDS:
        backend.restore(kind, files[kind])
        actual = backend.inventory(backend.target(kind), kind)
        require(all(manifest['databases'][kind].get(key) == value for key, value in actual.items()),
                f'Restored inventory or schema mismatch for {kind}')
        checkpoint(kind)
    return {'restore_start': start, 'restore_end': utc(), 'restore_seconds': round(time.monotonic() - tick, 3)}


def status(action):
    try:
        action()
    except (RecoveryError, OSError, KeyError, TypeError, ValueError, sqlite3.Error, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        # Avoid including parsed manifest values or connection credentials in diagnostics.
        message = str(error) if isinstance(error, RecoveryError) else type(error).__name__
        print('Recovery failed:', message, file=sys.stderr)
        return 1
    return 0


def profile_args(parser):
    profile = parser.add_mutually_exclusive_group(required=True)
    profile.add_argument('--isolated', metavar='RUN_ID', help='Run the synthetic two-database restore drill')
    profile.add_argument('--cleanup', metavar='RUN_ID', help='Clean owned restore destinations from an interrupted drill')
    return profile


def isolated_main(engine, args):
    run_id = args.isolated or args.cleanup
    check_run_id(run_id)
    root = RUNS / run_id
    require(root.resolve() == root and not root.is_symlink(), 'Run path may not traverse symlinks')
    if args.cleanup:
        run = Run(root, engine, new=False)
        with run.lock():
            if engine == 'postgres':
                Postgres(run).dispose()
            else:
                SQLite(run).cleanup()
        return
    require(not root.exists(), 'Run ID already exists; use a fresh ID')
    # Use an explicit safe environment. In particular, never load a developer .env or SMTP/provider credentials.
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'SYSTEMROOT') if k in os.environ}
    sys.path.insert(0, str(ROOT / 'backend'))
    from realtoruch.settings import Settings

    for key, field in Settings.model_fields.items():
        env[key.upper()] = str(field.default).lower() if isinstance(field.default, bool) else str(field.default)
    env.update(PYTHONPATH=str(ROOT / 'backend'), T27_RUN_ROOT=str(root), T27_ENGINE=engine,
               EMAIL_DELIVERY_MODE='file', EXPO_PUSH_ENABLED='false')
    process = subprocess.Popen([sys.executable, '-m', 'pytest', '-q', 'backend/tests/test_restore_contract.py',
                                '-k', engine, '--tb=short'], cwd=ROOT, env=env)
    previous = signal.signal(signal.SIGTERM, lambda *_: process.terminate())
    try:
        if process.wait() != 0:
            raise RecoveryError('Synthetic restore verification did not pass; see test output')
    except KeyboardInterrupt:
        if process.poll() is None:
            process.terminate()
            process.wait()
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)
    require((root / 'report.json').is_file(), 'Synthetic restore verification produced no report')
    print('Report:', root / 'report.json')
