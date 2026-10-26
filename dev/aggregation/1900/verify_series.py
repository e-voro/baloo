import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

root = Path('/home/evoro/tantor/dv/pg19beta3xid64')
state = json.loads((root/'baloo/dev/aggregation/1900/mapping.json').read_text())
dest = Path(tempfile.mkdtemp(prefix='xid64-1900-verified-am-'))

def source(*args):
    return subprocess.check_output(['git', '-C', str(root), *args])

def replay(*args):
    return subprocess.check_output(['git', '-C', str(dest), '-c',
        'user.name=Evgeny Voropaev', '-c', 'user.email=evorop@gmail.com', *args],
        stderr=subprocess.STDOUT)

archive = source('archive', state['base'])
with tarfile.open(fileobj=io.BytesIO(archive)) as t:
    t.extractall(dest, filter='data')
replay('init', '-q')
# A tracked vanilla Windows resource matches a repository ignore pattern.
# Preserve every tracked base file when constructing the replay repository.
replay('add', '-f', '-A')
replay('commit', '-qm', 'Vanilla PG19 beta3 replay base')
assert replay('rev-parse', 'HEAD^{tree}') == source('rev-parse', state['base']+'^{tree}')
pdir = root/'baloo/patches/func/pg19xid64evoro1900'
patches = [str(pdir/p) for p in (pdir/'series').read_text().splitlines()]
print(replay('am', '--whitespace=nowarn', *patches).decode(), flush=True)
actual = replay('rev-parse', 'HEAD^{tree}').decode().strip()
assert actual == state['source_tree'], (actual, state['source_tree'])
applied = replay('rev-list', '--reverse', 'HEAD~7..HEAD').decode().splitlines()
for c, applied_commit in zip(state['commits'], applied, strict=True):
    ref = c['commit']
    assert replay('rev-parse', applied_commit+'^{tree}') == source('rev-parse', ref+'^{tree}')
    fmt = '--format=%an <%ae>%n%aI'
    assert replay('show', '-s', fmt, applied_commit) == source('show', '-s', fmt, ref)
    body = source('show', '-s', '--format=%B', ref).decode()
    assert 'Evgeny Voropaev <evorop@gmail.com>' in body
    paths = source('diff-tree', '--no-commit-id', '--name-only', '-r', ref).decode().splitlines()
    assert not set(paths) & {'.gitmodules', 'baloo', 'codex_todo.txt'}
    print(ref[:12], source('show', '-s', '--format=%an <%ae>', ref).decode().strip(),
          len(paths), 'paths: tree/authorship/infrastructure checks PASS', flush=True)
print('PASS: vanilla base and every git-am commit tree match exactly.', dest, flush=True)
with (root/'baloo/xid64-aggregation-1900.txt').open('a') as f:
    f.write(f'\nSeven-patch git-am replay: PASS, exact tree {actual}.\nReplay directory: {dest}.\n'
            'Every intermediate commit tree, author identity/date and infrastructure exclusion: PASS.\n')
