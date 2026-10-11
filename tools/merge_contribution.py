#!/usr/bin/env python3
"""Maintainers: unpack an uploaded contribution zip onto a new git branch for review.

    python tools/merge_contribution.py nexclash_contribution_GAME.zip

Checks every path stays inside the toolkit folders and refuses game data; prints the note, the
files (new / changed) and the reports. Commit + PR after review (CONTRIBUTING.md).
"""
import json, os, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nexclash.userflow import screen, GAME_DATA, ALLOWED  # noqa: E402,F401
import fnmatch  # noqa: E402


def main():
    zp = sys.argv[1]
    z = zipfile.ZipFile(zp)
    meta = json.loads(z.read('CONTRIBUTION.json'))
    files = [n[len('files/'):] for n in z.namelist() if n.startswith('files/') and not n.endswith('/')]
    for f in files:
        if f.startswith('/') or '..' in f.split('/') or f.lower().endswith(GAME_DATA) or \
                not any(fnmatch.fnmatch(f, g) for g in ALLOWED):
            sys.exit('refused: %s' % f)
    branch = 'contrib-%s' % ''.join(c if c.isalnum() else '-' for c in meta['game'].lower())
    subprocess.run(['git', '-C', ROOT, 'checkout', '-b', branch], check=True)
    for f in files:
        p = os.path.join(ROOT, f)
        print('%-8s %s' % ('changed' if os.path.exists(p) else 'new', f))
        os.makedirs(os.path.dirname(p) or ROOT, exist_ok=True)
        open(p, 'wb').write(z.read('files/' + f))
    rep = os.path.join(ROOT, 'contrib_reports', branch)
    for n in z.namelist():
        if n.startswith('reports/'):
            os.makedirs(rep, exist_ok=True)
            open(os.path.join(rep, os.path.basename(n)), 'wb').write(z.read(n))
    print('game %s, package %s, note: %s' % (meta['game'], meta.get('package_version'), meta.get('note')))
    print('branch %s; reports in %s (not to be committed)' % (branch, rep))


if __name__ == '__main__':
    main()
