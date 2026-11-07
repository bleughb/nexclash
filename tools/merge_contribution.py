#!/usr/bin/env python3
"""Validate a contribution and its original hashes before importing on a new branch.

    python tools/merge_contribution.py nexclash_contribution_GAME.zip

Requires a clean checkout. Legacy archives can add files, but cannot replace existing files.
Reports and .nxc patches stay outside git in contrib_reports/.
"""
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nexclash.userflow import ALLOWED, GAME_DATA, MAX_FILE, MAX_NXC  # noqa: E402


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], check=True, capture_output=True, text=True).stdout.strip()


def digest(data):
    return hashlib.md5(data).hexdigest()


def destination(relative):
    parts = relative.split('/')
    if not relative or any(p in ('', '.', '..') for p in parts) or '\\' in relative or ':' in relative:
        raise ValueError('refused path: ' + relative)
    root = Path(ROOT).resolve()
    path = root.joinpath(*parts)
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
        raise ValueError('refused symlink destination: ' + relative)
    if path.exists() and not path.is_file():
        raise ValueError('destination is not a file: ' + relative)
    if any(p.exists() and not p.is_dir() for p in path.parents):
        raise ValueError('destination parent is not a directory: ' + relative)
    return path


def validate(archive):
    """Read and validate the whole archive before creating a branch or writing files."""
    infos = archive.infolist()
    if len(infos) != len({i.filename for i in infos}):
        raise ValueError('duplicate archive members')
    if archive.getinfo('CONTRIBUTION.json').file_size > MAX_FILE:
        raise ValueError('contribution metadata too large')
    meta = json.loads(archive.read('CONTRIBUTION.json'))
    expected, originals = meta['files'], meta.get('base_files')
    if not isinstance(expected, dict):
        raise ValueError('invalid file manifest')
    if originals is not None and (not isinstance(originals, dict) or set(originals) != set(expected)):
        raise ValueError('original-file manifest differs from contributed files')
    if meta.get('schema', 1) >= 2 and (originals is None or not meta.get('source')):
        raise ValueError('missing contribution baseline')
    branch = 'contrib-' + ''.join(c if c.isalnum() else '-' for c in meta['game'].lower())
    if not branch.removeprefix('contrib-').strip('-'):
        raise ValueError('empty game name')
    files, extras, seen, reports, patches = {}, {}, set(), set(), set()
    for info in infos:
        name = info.filename
        if name == 'CONTRIBUTION.json' or info.is_dir():
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError('refused archive symlink: ' + name)
        if name.startswith('files/'):
            rel = name[len('files/'):]
            target = destination(rel)
            if rel.lower().endswith(GAME_DATA) or not any(fnmatch.fnmatch(rel, g) for g in ALLOWED):
                raise ValueError('refused toolkit file: ' + rel)
            if info.file_size > MAX_FILE:
                raise ValueError('toolkit file too large: ' + rel)
            data = archive.read(info)
            if expected.get(rel) != digest(data):
                raise ValueError('file hash mismatch: ' + rel)
            current = target.read_bytes() if target.exists() else None
            base = originals[rel] if originals is not None else None
            if base is not None and (not isinstance(base, str) or not re.fullmatch(r'[0-9a-f]{32}', base)):
                raise ValueError('invalid original hash: ' + rel)
            if current != data:
                if originals is None and current is not None:
                    raise ValueError('legacy archive cannot replace %s; regenerate with current contribute or use a PR' % rel)
                if (digest(current) if current is not None else None) != base:
                    raise ValueError('baseline conflict: %s changed since the contribution started; use a PR' % rel)
                files[target] = data
            seen.add(rel)
        elif name.startswith(('reports/', 'patches/')):
            kind, rel = name.split('/', 1)
            if PurePosixPath(rel).name != rel or '\\' in rel:
                raise ValueError('refused report/patch name: ' + name)
            target = destination('contrib_reports/' + branch + '/' + rel)
            if target in extras or target.exists():
                raise ValueError('report/patch already exists: ' + rel)
            is_patch = kind == 'patches'
            if info.file_size > (MAX_NXC if is_patch else MAX_FILE):
                raise ValueError('report/patch too large: ' + name)
            data = archive.read(info)
            if is_patch:
                if not rel.lower().endswith('.nxc') or meta.get('patches', {}).get(rel) != digest(data):
                    raise ValueError('patch hash/type mismatch: ' + rel)
                patches.add(rel)
            else:
                if rel.lower().endswith(GAME_DATA):
                    raise ValueError('refused report type: ' + rel)
                reports.add(rel)
            extras[target] = data
        else:
            raise ValueError('unknown archive member: ' + name)
    if seen != set(expected) or not seen:
        raise ValueError('file manifest differs from archive members, or has no toolkit files')
    if reports != set(meta.get('reports', [])) or patches != set(meta.get('patches', {})):
        raise ValueError('report/patch manifest differs from archive members')
    return meta, branch, {**files, **extras}


def publish(files):
    """Replace files atomically; restore prior bytes if any write fails."""
    backups = {p: p.read_bytes() if p.exists() else None for p in files}
    created_dirs = []
    try:
        for path, data in files.items():
            missing = [p for p in path.parents if not p.exists()]
            path.parent.mkdir(parents=True, exist_ok=True)
            created_dirs.extend(reversed(missing))
            fd, temporary = tempfile.mkstemp(prefix='.contribution_', dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                if path.exists():
                    os.chmod(temporary, path.stat().st_mode)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)
    except BaseException:
        for path, data in backups.items():
            if data is None:
                path.unlink(missing_ok=True)
            elif not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
        for directory in reversed(created_dirs):
            directory.rmdir()
        raise


def main():
    archive_path = Path(sys.argv[1]).resolve()
    status = git('status', '--porcelain=v1', '-z', '--untracked-files=all')
    dirty = [s for s in status.split('\0') if s and not (
        s.startswith('?? ') and Path(ROOT, s[3:]).resolve() == archive_path)]
    if dirty:
        raise ValueError('checkout has local changes; commit/stash them or use a clean worktree')
    with zipfile.ZipFile(archive_path) as archive:
        meta, branch, files = validate(archive)
    previous = git('branch', '--show-current') or git('rev-parse', 'HEAD')
    git('checkout', '-b', branch)
    try:
        publish(files)
    except BaseException:
        git('checkout', previous)
        git('branch', '-D', branch)
        raise
    print('game %s, package %s, note: %s' % (meta['game'], meta.get('package_version'), meta.get('note')))
    print('branch %s; validated files:' % branch)
    for path in files:
        print('  ' + str(path.relative_to(Path(ROOT).resolve())))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        sys.exit('contribution refused: %s' % error)
