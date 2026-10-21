"""Build a hardware test .nex with the pinned sjasmplus (GPL-3.0-or-later, part of nexclash).

    python tools/hwtests/build.py im2hold [-o OUTDIR]

Writes OUTDIR/<name>.nex (default: the current directory). The .nex is our own test program,
not game data, but keep built files out of the repo all the same: build them where you run them.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'sjasmplus'))
import sjasm  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('name', help='test name (tools/hwtests/<name>.asm)')
    ap.add_argument('-o', '--out', default='.', help='output folder')
    a = ap.parse_args(argv)
    src = os.path.join(HERE, a.name + '.asm')
    exe = sjasm.find()
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(src, tmp)
        gen = os.path.join(HERE, a.name + '_gen.py')
        if os.path.exists(gen):                 # a test whose cases are generated (z80ntest)
            subprocess.run([sys.executable, gen, tmp], check=True, stdout=subprocess.DEVNULL)
        r = subprocess.run([exe, '--zxnext', '--nologo', os.path.basename(src)], cwd=tmp,
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit('sjasmplus failed:\n' + r.stdout + r.stderr)
        nex = os.path.join(tmp, a.name + '.nex')
        os.makedirs(a.out, exist_ok=True)
        dst = os.path.join(a.out, a.name + '.nex')
        shutil.copy(nex, dst)
    print('%s (%d bytes)' % (dst, os.path.getsize(dst)))


if __name__ == '__main__':
    main()
