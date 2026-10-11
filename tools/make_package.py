#!/usr/bin/env python3
"""Build the release zip: every tracked file (git ls-files) + MANIFEST.json (MD5 per file, so
`nexclash.py contribute` can tell what a session changed). Refuses game data.

    python tools/make_package.py [-o dist]      -> dist/nexclash-<VERSION>.zip
"""
import hashlib, json, os, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nexclash.userflow import GAME_DATA  # noqa: E402


def main():
    out = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else os.path.join(ROOT, 'dist')
    ver = open(os.path.join(ROOT, 'VERSION')).read().strip()
    files = subprocess.run(['git', '-C', ROOT, 'ls-files'], capture_output=True, text=True, check=True).stdout.split('\n')
    files = sorted(f for f in files if f)
    bad = [f for f in files if f.lower().endswith(GAME_DATA)]
    if bad:
        sys.exit('game data in the repo, refusing: %s' % bad)
    man = {'version': ver, 'files': {f: hashlib.md5(open(os.path.join(ROOT, f), 'rb').read()).hexdigest() for f in files}}
    os.makedirs(out, exist_ok=True)
    zp = os.path.join(out, 'nexclash-%s.zip' % ver)
    top = 'nexclash-%s/' % ver
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(ROOT, f), top + f)
        z.writestr(top + 'MANIFEST.json', json.dumps(man, indent=0))
    print('%s  %d files  %d KB' % (zp, len(files) + 1, os.path.getsize(zp) // 1024))


if __name__ == '__main__':
    main()
