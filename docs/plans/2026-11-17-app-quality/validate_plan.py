#!/usr/bin/env python3
"""Validate the 40-task planning package, without executing application work."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
manifest = json.loads((BASE / 'manifest.json').read_text())
execution = json.loads((BASE / 'execution.json').read_text())
tasks = manifest['tasks']
expected = {f'Q{i:02}' for i in range(1, 41)}
assert manifest['task_count'] == len(tasks) == 40
assert {t['id'] for t in tasks} == expected
assert len({t['file'] for t in tasks}) == 40
assert {t['id'] for t in execution['tasks']} == expected
assert len(execution['tasks']) == 40
assert manifest['baseline_commit'] == execution['baseline_commit']
by_id = {t['id']: t for t in tasks}

visited, active = set(), set()
def visit(task_id):
    assert task_id not in active, f'Dependency cycle at {task_id}'
    if task_id in visited:
        return
    active.add(task_id)
    for dep in by_id[task_id]['depends_on']:
        assert dep in expected and dep != task_id, (task_id, dep)
        visit(dep)
    active.remove(task_id)
    visited.add(task_id)

for task in tasks:
    visit(task['id'])
    packet = BASE / task['file']
    body = packet.read_text()
    assert body.startswith(f"# {task['id']} {task['title']}\n")
    for key in ('evidence', 'allowed_scope', 'acceptance', 'verification', 'merge_locks'):
        assert task[key], (task['id'], key)
    assert task['priority'] in {'P1', 'P2'}
    assert task['executor'] in {'economy', 'experienced'}
    assert 0 < task['estimate_hours'][0] <= task['estimate_hours'][1]
    assert task['change'] in body and task['out_of_scope'] in body
    assert task['review'] in body
    for scope in task['allowed_scope']:
        assert scope in body
        if '(new)' not in scope and '(from ' not in scope:
            assert (ROOT / scope.split(' (', 1)[0]).exists(), (task['id'], scope)
    for evidence in task['evidence']:
        assert (ROOT / evidence['path']).is_file(), (task['id'], evidence['path'])
        assert evidence['finding'] in body
    for number, acceptance in enumerate(task['acceptance'], 1):
        assert f"{task['id']}-AC{number:02}" in body
        assert acceptance in body
    for check in task['verification']:
        assert check in body
    for dep in task['depends_on']:
        assert dep in body
    assert 'DELEGATION.md' in body and 'HANDOFF_TEMPLATE.md' in body

packets = set((BASE / 'tasks').glob('Q*.md'))
assert packets == {BASE / task['file'] for task in tasks}
for file in BASE.rglob('*.md'):
    assert all(line == line.rstrip() for line in file.read_text().splitlines()), f'Trailing whitespace in {file.name}'
    for target in re.findall(r'\]\(([^)]+)\)', file.read_text()):
        if '://' in target or target.startswith('#'):
            continue
        target = target.split('#', 1)[0]
        assert (file.parent / target).exists(), f'Broken link in {file.name}: {target}'

readme = (BASE / 'README.md').read_text()
assert len(re.findall(r'^\| \[Q\d{2}\]', readme, re.M)) == 40
assert len([t for t in tasks if t['executor'] == 'economy']) == 37
assert {t['id'] for t in tasks if t['executor'] == 'experienced'} == {'Q32', 'Q33', 'Q40'}
print(f'PASS: 40 packets, {sum(len(t["acceptance"]) for t in tasks)} criteria, acyclic dependencies, tracker, source evidence and Markdown links.')
