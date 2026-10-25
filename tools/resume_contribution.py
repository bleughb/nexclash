#!/usr/bin/env python3
"""Contributors: carry the work of the previous chat into this one (PLAYBOOK "Sessions").

    python tools/resume_contribution.py nexclash_contribution_GAME.zip

A contributor's session cannot push, so each stage ends with `python nexclash.py contribute GAME`
and the user attaches that zip (with the package, the snapshot and the recording) to the next chat.
This puts its files back over the package, so games/<game>.md (Next session block), the engine,
.asm, profile and record are as the last stage left them. Same path checks as
tools/merge_contribution.py (no game data, toolkit folders only); no git needed. The next
`contribute` again holds every file changed since the release, so the zips stay cumulative.
"""
import fnmatch
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nexclash.userflow import GAME_DATA, ALLOWED  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    z = zipfile.ZipFile(sys.argv[1])
    meta = json.loads(z.read('CONTRIBUTION.json'))
    files = [n for n in z.namelist() if n.startswith('files/') and not n.endswith('/')]
    for n in files:
        f = n[len('files/'):]
        if f.startswith('/') or '..' in f.split('/') or f.lower().endswith(GAME_DATA) or \
                not any(fnmatch.fnmatch(f, g) for g in ALLOWED):
            sys.exit('refused: %s' % f)
    for n in files:
        f = n[len('files/'):]
        p = os.path.join(ROOT, f)
        print('%-8s %s' % ('changed' if os.path.exists(p) else 'new', f))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(z.read(n))
    print('Resumed %s (%s, %d files). Next: the "Next session" block in games/<game>.md.'
          % (meta.get('game'), meta.get('date'), len(files)))


if __name__ == '__main__':
    main()
