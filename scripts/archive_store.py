"""Durable collection state in a data branch; immutable source files in releases."""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'automated-data'
GIT = os.environ.get('FTB_GIT', 'git')


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.stage')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def restore(state, source=None):
    state = Path(state).resolve()
    state.mkdir(parents=True, exist_ok=True)
    if any(state.iterdir()):
        raise ValueError('Restore needs a new empty state directory')
    lookup = subprocess.run([GIT, 'ls-remote', '--exit-code', '--heads', 'origin', BRANCH],
                            cwd=ROOT, capture_output=True)
    if lookup.returncode == 2:
        return False
    if lookup.returncode:
        raise RuntimeError('Could not check the durable data branch')
    run([GIT, 'fetch', '--no-tags', 'origin', f'+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}'], cwd=ROOT)
    payload = run([GIT, 'archive', '--format=zip', 'origin/' + BRANCH], cwd=ROOT).stdout
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for item in archive.infolist():
            target = (state / item.filename).resolve()
            if not target.is_relative_to(state):
                raise ValueError('Unsafe durable state path')
        archive.extractall(state)
    if source:
        overlay(state, source)
    return True


def overlay(state, source):
    folder = Path(state) / 'seasons' / '2026-27'
    if not folder.exists():
        return
    manifest = read(folder / 'manifest.json')
    version = manifest['activeVersion']
    if len(version) != 69 or any(c not in '0123456789abcdef' for c in version[:-5]) or not version.endswith('.json'):
        raise ValueError('Unsafe collected season version')
    payload = read(folder / 'versions' / version)
    actual = hashlib.sha256(json.dumps(payload['games'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if actual != manifest['evidenceContentHash'] or actual != version[:-5]:
        raise ValueError('Durable season state hash mismatch')
    shutil.copytree(folder, Path(source) / 'seasons' / '2026-27', dirs_exist_ok=True)


def persist(state):
    state = Path(state).resolve()
    (state / '.gitignore').write_text('library/pdf/\nlibrary/text/opening_quarter/\nlibrary/gamebooks.sqlite\nlibrary/play_by_play.sqlite\nlibrary/identity_sources/\n_runtime/\n*.stage\n', encoding='utf-8')
    scratch = ROOT / '.build-tests'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temporary) / 'index'),
               'GIT_AUTHOR_NAME': 'FTB data collector', 'GIT_AUTHOR_EMAIL': '41898282+github-actions[bot]@users.noreply.github.com',
               'GIT_COMMITTER_NAME': 'FTB data collector', 'GIT_COMMITTER_EMAIL': '41898282+github-actions[bot]@users.noreply.github.com'}
        base = [GIT, '--git-dir=' + str(ROOT / '.git'), '--work-tree=' + str(state)]
        run(base + ['read-tree', '--empty'], cwd=state, env=env)
        run(base + ['add', '--all', '--', '.'], cwd=state, env=env)
        tree = run(base + ['write-tree'], cwd=state, env=env).stdout.decode().strip()
        parent = subprocess.run([GIT, 'rev-parse', '--verify', 'origin/' + BRANCH], cwd=ROOT, capture_output=True)
        args = base + ['commit-tree', tree]
        if parent.returncode == 0:
            parent_id = parent.stdout.decode().strip()
            prior_tree = run([GIT, 'rev-parse', parent_id + '^{tree}'], cwd=ROOT).stdout.decode().strip()
            if prior_tree == tree:
                return parent_id
            args += ['-p', parent_id]
        commit = run(args + ['-m', 'Update verified NBA collection state'], cwd=state, env=env).stdout.decode().strip()
        run([GIT, 'push', 'origin', commit + ':refs/heads/' + BRANCH], cwd=ROOT)
        run([GIT, 'update-ref', 'refs/remotes/origin/' + BRANCH, commit], cwd=ROOT)
        return commit


class ReleaseArchive:
    def __init__(self, repository=None):
        self.repository = repository or os.environ.get('GITHUB_REPOSITORY', 'lopoke89-ops/ftb-updated-model')
        self.releases = {}

    def upload(self, path, tag, title):
        path = Path(path)
        gh = ['gh', '--repo', self.repository]
        if tag not in self.releases:
            result = subprocess.run(gh + ['release', 'view', tag, '--json', 'assets'], capture_output=True)
            if result.returncode:
                # A network/authentication error must not be mistaken for an empty archive.
                exists = subprocess.run(['gh', 'api', f'repos/{self.repository}/releases/tags/{tag}'], capture_output=True)
                if b'404' not in exists.stderr and b'Not Found' not in exists.stdout:
                    raise RuntimeError('Cannot inspect the persistent NBA archive')
                run(gh + ['release', 'create', tag, '--target', 'main', '--title', title,
                          '--notes', 'Original NBA gamebooks and verified research data. Files are named by content hash.'])
                assets = []
            else:
                assets = json.loads(result.stdout)['assets']
            self.releases[tag] = {a['name']: a for a in assets}
        asset = self.releases[tag].get(path.name)
        if asset:
            if asset['size'] != path.stat().st_size:
                raise ValueError('An archive asset with this hash has a different size')
        else:
            run(gh + ['release', 'upload', tag, str(path)])
            self.releases[tag][path.name] = {'name': path.name, 'size': path.stat().st_size}
        return f'https://github.com/{self.repository}/releases/download/{tag}/{path.name}'

    def content_file(self, path, runtime, season, day):
        path = Path(path)
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        name = path.stem + '-' + digest + path.suffix
        target = Path(runtime) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        tag = f'nba-gamebooks-{season}-{day[:7]}'
        return self.upload(target, tag, f'NBA {season} gamebooks - {day[:7]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['restore', 'persist', 'mark-published'])
    parser.add_argument('--state', type=Path, default=ROOT / '.collection-state')
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    if args.action == 'restore':
        print('Durable data restored:', restore(args.state, args.source))
    else:
        if args.action == 'mark-published':
            value = read(args.state / 'state.json')
            value['publishedKey'] = value['readyKey']
            save(args.state / 'state.json', value)
        print('Durable data commit:', persist(args.state))
