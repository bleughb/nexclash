"""Make the nxsuite hand-over package for a tester (GPL-3.0-or-later, part of nexclash).

    python tools/hwtests/package.py -o OUTDIR [--allow-dirty]

Builds nxsuite.nex (tools/hwtests/build.py) and writes OUTDIR/nxsuite-<build>.zip holding nxsuite.nex and
TESTER.TXT (from tools/hwtests/nxsuite_tester.txt, with the build id and date filled in). The build id is the
commit the .nex was built from (the src= of its result file); the package is refused while tools/hwtests has
uncommitted changes, so the id names exactly what was built (--allow-dirty marks the name -dirty instead).
OUTDIR must be outside the repository: the zip and the .nex never go into it. Nothing personal is put in
the package: no names, addresses or local paths.
"""
import argparse
import datetime
import os
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('-o', '--out', required=True, help='output folder, outside the repository')
    ap.add_argument('--allow-dirty', action='store_true', help='package uncommitted sources (name ends -dirty)')
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if os.path.commonpath([out, ROOT]) == ROOT:
        sys.exit('refused: %s is inside the repository (the zip and .nex stay out of it)' % a.out)
    build = git('rev-parse', '--short=8', 'HEAD') or 'unknown'
    dirty = git('status', '--porcelain', '--', 'tools/hwtests')
    if dirty:
        if not a.allow_dirty:
            sys.exit('refused: tools/hwtests has uncommitted changes (commit, or --allow-dirty):\n' + dirty)
        build += '-dirty'
    text = open(os.path.join(HERE, 'nxsuite_tester.txt'), encoding='ascii').read()
    text = text.replace('{BUILD}', build).replace('{DATE}', datetime.date.today().isoformat())
    if '{' in text or any(ord(c) > 126 or (ord(c) < 32 and c != '\n') for c in text):
        sys.exit('refused: TESTER.TXT has an unfilled field or a character that is not plain ASCII')
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, os.path.join(HERE, 'build.py'), 'nxsuite', '-o', tmp], check=True,
                       stdout=subprocess.DEVNULL)
        zp = os.path.join(out, 'nxsuite-%s.zip' % build)
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(os.path.join(tmp, 'nxsuite.nex'), 'nxsuite.nex')
            z.writestr('TESTER.TXT', text.replace('\n', '\r\n'))    # CR LF: readable in any PC editor
    print('%s (%d bytes): nxsuite.nex + TESTER.TXT, build %s' % (zp, os.path.getsize(zp), build))
    return 0


if __name__ == '__main__':
    sys.exit(main())
