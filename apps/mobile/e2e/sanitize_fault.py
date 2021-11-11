#!/usr/bin/env python3
"""Keep only synthetic trace events/screenshots; refuse known secret leaks.

Not a general-purpose trace sanitizer: only use with the isolated T18 fault run.
Network captures, response bodies, sources and stacks are deliberately omitted.
"""
import re
import sys
from email import message_from_bytes
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(sys.argv[1]).resolve()
allowed_root = Path(__file__).resolve().parents[3] / '.local/verification/T18'
if not root.is_relative_to(allowed_root.resolve()):
    raise SystemExit('Only run-owned T18 artifacts are supported')
raw = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else next(root.rglob('raw-fault-trace.zip'))
if not raw.is_relative_to(root):
    raise SystemExit('Trace must belong to the run')
output = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else root / 'sanitized-fault-trace.zip'
if not output.is_relative_to(root):
    raise SystemExit('Sanitized output must remain in the run')
output.unlink(missing_ok=True)
secrets = []
for path in (root / 'mail').glob('*.eml'):
    body = message_from_bytes(path.read_bytes()).get_payload(decode=True).decode()
    secrets.extend(x.encode() for x in re.findall(r'#(?:verify_account|confirm_email|unsubscribe_email|reset_password)=([^\s]+)', body))
with ZipFile(raw) as source:
    trace_names = [name for name in source.namelist() if name.endswith('.trace')]
    if not trace_names:
        raise SystemExit('No trace events; no sanitized archive created')
    traces = {name: source.read(name) for name in trace_names}
    trace = b'\n'.join(traces.values())
    network = '\n'.join(source.read(name).decode(errors='replace') for name in source.namelist() if name.endswith('.network'))
    # Include both authorization values and individual cookie values in the leak check.
    for name, value in re.findall(r'"name"\s*:\s*"(authorization|cookie|set-cookie)"\s*,\s*"value"\s*:\s*"([^"\\]+)', network, re.I):
        secrets.append(value.encode())
        if name.lower() != 'authorization':
            secrets.extend(part.encode() for part in re.findall(r'=([^;\s]+)', value) if len(part) >= 20)
    forbidden = (b'authorization', b'cookie', b'verify_account=', b'confirm_email=',
                 b'unsubscribe_email=', b'reset_password=', b'access_token', b'refresh_token')
    if any(term in trace.lower() for term in forbidden) or any(len(secret) >= 20 and secret in trace for secret in secrets):
        raise SystemExit('Trace contains secret-bearing content; no sanitized archive created')
    if re.search(rb'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', trace):
        raise SystemExit('Trace contains a JWT-like value; no sanitized archive created')
    with ZipFile(output, 'w', ZIP_DEFLATED) as target:
        for name in source.namelist():
            if name in traces or name.startswith('screencast/') or re.fullmatch(r'resources/page@[^/]+\.jpe?g', name):
                target.writestr(name, source.read(name))
print('Kept trace events and synthetic screenshots; omitted network, resource bodies and stacks.')
