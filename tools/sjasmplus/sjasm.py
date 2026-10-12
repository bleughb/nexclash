"""The pinned sjasmplus (tools/sjasmplus/pin.json): find it, check it, or build it.

    python tools/sjasmplus/sjasm.py            print the path of a working pinned sjasmplus
    python tools/sjasmplus/sjasm.py --build    build the pinned tag from source (cache dir)

Order: the bundled static Linux x86-64 binary (checked by SHA-256 and --version), else a
previous source build in the cache, else build the pinned tag from source (~15 s; needs git,
make and a C++ compiler; network to github.com). Any other sjasmplus is refused: the hook
hex in docs/profiles must come from exactly one assembler version.
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PIN = json.load(open(os.path.join(HERE, 'pin.json')))
CACHE = os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), 'nexclash',
                     'sjasmplus-' + PIN['version'])


def _version(exe):
    try:
        out = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (out.stdout + out.stderr).splitlines():
        if 'SjASMPlus' in line and ' v' in line:
            return line.split(' v', 1)[1].split()[0]
    return None


def _ok(exe):
    return exe and os.path.isfile(exe) and _version(exe) == PIN['version']


def bundled():
    exe = os.path.join(HERE, PIN['binary'])
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        return None
    if not os.path.isfile(exe):
        return None
    if hashlib.sha256(open(exe, 'rb').read()).hexdigest() != PIN['binary_sha256']:
        raise RuntimeError('%s does not match pin.json binary_sha256' % exe)
    if not os.access(exe, os.X_OK):
        os.chmod(exe, 0o755)
    return exe if _ok(exe) else None


def build(log=sys.stderr):
    """Build the pinned tag into the cache dir; returns the executable path."""
    src = CACHE + '-src'
    if os.path.isdir(src):
        shutil.rmtree(src)
    os.makedirs(os.path.dirname(src), exist_ok=True)
    subprocess.run(['git', '-c', 'advice.detachedHead=false', 'clone', '-q', '--depth', '1', '--branch', PIN['tag'], PIN['repo'], src],
                   check=True)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=src, capture_output=True, text=True,
                          check=True).stdout.strip()
    if head != PIN['commit']:
        raise RuntimeError('tag %s is commit %s, pin.json says %s' % (PIN['tag'], head, PIN['commit']))
    r = subprocess.run(['make', '-j2', 'USE_LUA=0'], cwd=src, capture_output=True, text=True)
    if r.returncode:
        log.write(r.stdout[-2000:] + r.stderr[-2000:])
        raise RuntimeError('sjasmplus build failed')
    os.makedirs(CACHE, exist_ok=True)
    exe = os.path.join(CACHE, 'sjasmplus')
    shutil.copy2(os.path.join(src, 'sjasmplus'), exe)
    shutil.rmtree(src)
    if not _ok(exe):
        raise RuntimeError('built sjasmplus does not report version %s' % PIN['version'])
    return exe


def find(allow_build=True):
    """Path of the pinned sjasmplus (bundled, cached, or freshly built)."""
    exe = bundled()
    if exe:
        return exe
    cached = os.path.join(CACHE, 'sjasmplus')
    if _ok(cached):
        return cached
    if not allow_build:
        raise RuntimeError('pinned sjasmplus %s not available (run tools/sjasmplus/sjasm.py --build)'
                           % PIN['version'])
    return build()


if __name__ == '__main__':
    print(build() if '--build' in sys.argv else find())
