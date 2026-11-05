"""The .nxc output of the user-facing builds: `patch`, `new` and `auto` (refactor plan 23). GPL-3.0-or-later.

A build writes GAME.nxc beside its report: the file to share. It holds the sprite build as a patch that needs the
player's own copy of the game; the loader and the card setup are at github.com/jattree/nxc. The packager is that
repository's tools/nxc.py, vendored unmodified as nexclash/nxc.py (THIRD-PARTY-NOTICES); this module only feeds its
`make` path, which proves the .nxc rebuilds the .nex byte for byte before it writes anything, and checks that again.

  --nex          keep the .nex files too (default: the .nxc and the report only)
  --no-nxc       the .nex files only, as before (selftest's rebuilds use it)
  --patch-by N   your name for the menu's credit line: saved once in the config file (config_path()), or
                 $NEXCLASH_PATCH_BY; never asked for
  --title T, --publisher "Ocean, 1986", --target-file NAME, --pok FILE   override what is found (below)

What goes in: title = the game nexclash knows the snapshot as (verified.json, the engine's record, identify);
publisher only from --publisher (the repository has no ZXDB); credit = nxc.py's NexClash default; version 1.0;
cheats from --pok or GAME.pok beside the .z80 (nxc.py import-pok); PRF1 replay = this run's Verify / Unit / Result
lines, else the record of a byte-identical verified build, else "not verified"; the target = the .z80's own name
(TOSEC style wanted: a note says when it is not) and its MD5, which nxc.py writes.
A build that failed its checks, or has no sprite build, gets no .nxc and keeps its .nex files.
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZX0_SRC = os.path.join(ROOT, 'tools', 'zx0')
NXC_PIN = {'repo': 'https://github.com/jattree/nxc', 'path': 'tools/nxc.py',
           'commit': '391e72a086fa6017e31123f84cc31467ba7bf2ef',
           'sha256': 'f286b3f16e76fbda3d225f75eb00c086bbd3993ce6b5cdd1d81f93c1f3f84f92'}
VERSION = '1.0'
SHARE = 'github.com/jattree/nxc'
NAME_MAX = 32                   # what a loader keeps of a credit name (nxc.CREDIT_NAME)
TOSEC = re.compile(r'.+ \((19|20)\d\d[^)]*\)\(.+\)')
_START = time.time()            # .nex files written after this are this run's


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def add_args(p):
    g = p.add_argument_group('.nxc output (nexclash/nxcout.py)')
    g.add_argument('--nex', action='store_true', help='keep the .nex files too (default: GAME.nxc and the report)')
    g.add_argument('--no-nxc', action='store_true', help='no .nxc: the .nex files only, as before')
    g.add_argument('--patch-by', help='your name for the menu credit; saved once for later builds ($NEXCLASH_PATCH_BY also works)')
    g.add_argument('--title', help='the game\'s title in the .nxc (default: the game nexclash knows the snapshot as)')
    g.add_argument('--publisher', help='the menu\'s publisher line, such as "Ocean, 1986"')
    g.add_argument('--target-file', help='the name players have the game under (default: the .z80\'s own; TOSEC style)')
    g.add_argument('--pok', help='cheats from a .pok (default: GAME.pok beside the .z80, if there)')


# ------------------------------------------------------------------------------------------- settings

def config_path():
    if os.environ.get('NEXCLASH_CONFIG'):
        return os.environ['NEXCLASH_CONFIG']
    base = os.environ.get('APPDATA') if os.name == 'nt' else (os.environ.get('XDG_CONFIG_HOME') or
                                                              os.path.expanduser('~/.config'))
    return os.path.join(base or os.path.expanduser('~'), 'nexclash', 'config.json')


def _config():
    try:
        return json.load(open(config_path()))
    except (OSError, ValueError):
        return {}


def _check_name(n):
    if not (1 <= len(n) <= NAME_MAX and n.isascii() and n.isprintable()):
        raise ValueError('--patch-by must be 1 to %d printable ASCII characters' % NAME_MAX)
    return n


def patch_by(a):
    """-> (name or None, where it came from). A --patch-by is saved, so it is given once."""
    n = getattr(a, 'patch_by', None)
    if n:
        c = _config()
        if c.get('patch_by') != _check_name(n):
            os.makedirs(os.path.dirname(config_path()), exist_ok=True)
            json.dump(dict(c, patch_by=n), open(config_path(), 'w'), indent=1)
        return n, 'saved in %s' % config_path()
    if os.environ.get('NEXCLASH_PATCH_BY'):
        return _check_name(os.environ['NEXCLASH_PATCH_BY']), '$NEXCLASH_PATCH_BY'
    if _config().get('patch_by'):
        return _check_name(_config()['patch_by']), config_path()
    return None, 'not set: add --patch-by "Your Name" once'


# ------------------------------------------------------------------------------------------- zx0

def _pin():
    return json.load(open(os.path.join(ZX0_SRC, 'pin.json')))


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _golden(exe, pin):
    g = pin['golden']
    data = bytes((i * 7 + (i >> 5)) & 255 for i in range(4096)) + bytes(1024) + b'NexClash .nxc ' * 40
    with tempfile.TemporaryDirectory() as d:
        i, o = os.path.join(d, 'i'), os.path.join(d, 'o')
        open(i, 'wb').write(data)
        try:
            subprocess.run([exe, '-f', i, o], check=True, capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return False
        return md5(o) == g['zx0_md5']


def zx0_dir():
    """The folder holding a zx0 that gives the pinned golden output (tools/zx0/README.md). -> path, or RuntimeError."""
    pin = _pin()
    env = os.environ.get('NXC_ZX0_DIR')
    if env and os.path.exists(os.path.join(env, 'zx0')):
        if not _golden(os.path.join(env, 'zx0'), pin):
            raise RuntimeError('$NXC_ZX0_DIR/zx0 does not give the golden output of ZX0 %s' % pin['commit'][:7])
        return env
    cache = os.path.join(os.environ.get('XDG_CACHE_HOME') or os.path.expanduser('~/.cache'), 'nexclash',
                         'zx0-' + pin['commit'][:7])
    exe = os.path.join(cache, 'zx0.exe' if os.name == 'nt' else 'zx0')
    if os.path.exists(os.path.join(cache, 'zx0')) and _golden(exe, pin):
        return cache
    for f, h in pin['sources'].items():
        if _sha(os.path.join(ZX0_SRC, f)) != h:
            raise RuntimeError('tools/zx0/%s does not match tools/zx0/pin.json' % f)
    os.makedirs(cache, exist_ok=True)
    if os.name == 'nt':                         # nxc.py looks for 'zx0'; Windows runs zx0.exe for it
        src = os.path.join(ZX0_SRC, pin['windows_binary'])
        if _sha(src) != pin['windows_binary_sha256']:
            raise RuntimeError('tools/zx0/zx0.exe does not match tools/zx0/pin.json')
        shutil.copy(src, exe)
        shutil.copy(src, os.path.join(cache, 'zx0'))
    else:
        ccs = [c for c in (os.environ.get('CC'), 'cc', 'gcc', 'clang') if c and shutil.which(c)]
        if not ccs:
            raise RuntimeError('no zx0: no C compiler (cc, gcc, clang) to build tools/zx0, and $NXC_ZX0_DIR is not set')
        srcs = [os.path.join(ZX0_SRC, f) for f in pin['sources'] if f.endswith('.c')]
        r = subprocess.run([ccs[0], '-O2', '-o', exe + '.tmp'] + srcs, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError('building tools/zx0 with %s failed: %s' % (ccs[0], r.stderr.strip()[-200:]))
        os.replace(exe + '.tmp', exe)
    if not _golden(exe, pin):
        raise RuntimeError('%s does not give the golden output of ZX0 %s' % (exe, pin['commit'][:7]))
    return cache


# ------------------------------------------------------------------------------------------- metadata

def _ascii(s):
    return ''.join(c if ' ' <= c <= '~' else '?' for c in re.sub(r'\s+', ' ', s).strip())


def _verified():
    try:
        return json.load(open(os.path.join(ROOT, 'docs', 'profiles', 'verified.json'))).get('snapshots', {})
    except (OSError, ValueError):
        return {}


def _records():
    from nexclash import records
    return records.all_records()


def title(a, z80, h):
    """--title, else the game nexclash knows this snapshot as: verified.json, the record of the engine that
    builds it, identify's profile. -> title or None."""
    if getattr(a, 'title', None):
        return a.title
    if _verified().get(h):
        return _verified()[h]['game']
    try:
        from skoolkit.snapshot import Snapshot
        from nexclash.engines import find
        from nexclash.identify import identify
        s = Snapshot.get(z80)
        mod = find(s, a)
        if mod is not None:
            short = mod.__name__.split('.')[-1]
            rec = next((r for r in _records() if short in r.get('own_modules', [])), None)
            return rec['game'] if rec else None
        return identify(s.memory[0:65536]).get('game')
    except Exception:                       # noqa: BLE001 - a title is optional
        return None


def target(a, z80):
    """-> (TGT1 file name, note or None). nxc.py adds the MD5 of the .z80."""
    if getattr(a, 'target_file', None):
        return a.target_file, None
    base = os.path.basename(z80)
    if TOSEC.match(os.path.splitext(base)[0]):
        return base, None
    return base, ('%s is not a TOSEC-style name ("Title (Year)(Publisher).z80"): a loader looks for the game under '
                  'this exact name; --target-file NAME sets another' % base)


def proof(rep, h, spr_md5, quick=None):
    """PRF1 fields: this run's verification, else a byte-identical verified build's record, else 'not verified'."""
    today = time.strftime('%Y-%m-%d')
    got = [_ascii(l) for l in rep.splitlines() if l.startswith(('Verify', 'Unit', 'Result'))]
    if any(l.startswith('Verify') for l in got):
        p = {'replay': '; '.join(got), 'replay_when': today}
        if quick:
            p.update(coverage='the first %d frames of each recording only (--quick)' % quick, coverage_when=today)
        return p
    for r in _records():
        outs = [o.get('md5') for o in (r.get('outputs') or {}).values()]
        if r['inputs']['snapshot'].get('md5') == h and spr_md5 in outs and r.get('verified'):
            return {'replay': _ascii('%s (NexClash record %s, verified %s; this build is byte-identical to it)' % (
                r['status']['software'], r['name'], r['verified']['date'])), 'replay_when': r['verified']['date']}
    return {'replay': 'not verified'}


def sprite_nex(out, name):
    """The sprite build the .nxc carries: NAME_sprites.nex, else the one *sprites*.nex that is not a diagnostic."""
    p = os.path.join(out, name + '_sprites.nex')
    if os.path.exists(p):
        return p
    c = [f for f in os.listdir(out) if f.endswith('.nex') and 'sprites' in f and 'diag' not in f] if os.path.isdir(out) else []
    return os.path.join(out, c[0]) if len(c) == 1 else None


# ------------------------------------------------------------------------------------------- packaging

def _run(nxc, argv):
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        nxc.run(argv)
    return log.getvalue().splitlines()


def make(a, z80, out, name, spr, rep, say):
    """GAME.nxc from the sprite build and the .z80, through nxc.py make (+ import-pok); -> its path."""
    from nexclash import nxc
    nxc.ZX0_DIR = zx0_dir()
    h, spr_md5 = md5(z80), md5(spr)
    t = title(a, z80, h)
    who, where = patch_by(a)
    tfile, tnote = target(a, z80)
    prf = proof(rep, h, spr_md5, getattr(a, 'quick', None))
    dst = os.path.join(out, name + '.nxc')
    argv = ['make', spr, z80, '-o', dst, '--file', tfile, '--patch-version', VERSION]
    argv += ['--title', t] if t else []
    argv += ['--publisher', a.publisher] if getattr(a, 'publisher', None) else []
    argv += ['--patch-by', who] if who else []
    for k, v in prf.items():
        argv += ['--proof', '%s=%s' % (k, v)]
    _run(nxc, argv)
    pok = getattr(a, 'pok', None) or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '.pok')
    cheats = None
    if os.path.exists(pok):
        try:
            _run(nxc, ['import-pok', dst, pok, z80, '-o', dst + '.tmp'])
            os.replace(dst + '.tmp', dst)
            cheats = '%d from %s' % (len(nxc.trainers(open(dst, 'rb').read())), os.path.basename(pok))
        except (ValueError, OSError) as e:
            cheats = 'none: %s refused (%s)' % (os.path.basename(pok), e)
    elif getattr(a, 'pok', None):
        raise ValueError('--pok %s: no such file' % a.pok)
    f = open(dst, 'rb').read()
    if nxc.apply(f, game=open(z80, 'rb').read()) != open(spr, 'rb').read():
        os.remove(dst)
        raise ValueError('applied to %s it does not give %s' % (os.path.basename(z80), os.path.basename(spr)))
    acc = [l for l in _run(nxc, [dst]) if l.startswith('accepts')]
    say('NXC       : %s  %d bytes; applied to %s it gives %s exactly (MD5 %s)' % (
        os.path.basename(dst), len(f), os.path.basename(z80), os.path.basename(spr), spr_md5))
    say('            %s (MD5 %s); title %s; version %s; patch_by %s (%s)' % (
        acc[0] if acc else tfile, h, t or '(none)', VERSION, who or '(none)', where))
    say('            PRF1 replay=%s' % prf['replay'][:150])
    if cheats:
        say('            cheats: %s' % cheats)
    if tnote:
        say('            note: ' + tnote)
    return dst


def package(a):
    """After a build: GAME.nxc in the output folder, its lines added to the report; without --nex the .nex files
    this run wrote are removed. -> the .nxc path or None."""
    if getattr(a, 'no_nxc', False):
        return None
    z80 = a.z80
    name = os.path.splitext(os.path.basename(z80))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '_nexclash')
    rp = os.path.join(out, name + '_report.txt')
    rep = open(rp).read() if os.path.exists(rp) else ''
    lines = []
    spr = sprite_nex(out, name) if os.path.isdir(out) else None
    dst = None
    if spr is None:
        lines.append('NXC       : not made - no sprite build')
    elif 'FAILED' in rep or 'MISMATCH' in rep:
        lines.append('NXC       : not made - the build failed its checks (its .nex files are kept)')
    else:
        try:
            dst = make(a, z80, out, name, spr, rep, lines.append)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError, SystemExit) as e:
            lines.append('NXC       : not made - %s (the .nex files are kept)' % e)
    if dst:
        lines.append('            share %s: it needs the player\'s own copy of the game; loader and card setup: %s' % (
            os.path.basename(dst), SHARE))
        if not getattr(a, 'nex', False):
            gone = [f for f in sorted(os.listdir(out)) if f.endswith('.nex') and
                    os.path.getmtime(os.path.join(out, f)) >= _START - 1]
            for f in gone:
                os.remove(os.path.join(out, f))
            if gone:
                lines.append('            removed %s (--nex keeps the .nex files)' % ', '.join(gone))
    print('\n'.join(lines))
    if os.path.exists(rp):
        open(rp, 'a').write('\n'.join(lines) + '\n')
    return dst


# ------------------------------------------------------------------------------------------- checks

def selfcheck():
    """selftest --tools, no game data: the vendored packager and compressor match their pins, and the metadata
    rules on synthetic input. -> list of failures."""
    bad = []
    if _sha(os.path.join(ROOT, 'nexclash', 'nxc.py')) != NXC_PIN['sha256']:
        bad.append('nexclash/nxc.py differs from %s %s (THIRD-PARTY-NOTICES)' % (NXC_PIN['repo'], NXC_PIN['commit'][:7]))
    from nexclash import nxc
    if nxc.CREDIT != 'Built with NexClash by Dean Woodyatt (Bleugh.biz, bleughb/nexclash, GPL-3.0-or-later)':
        bad.append(('credit', nxc.CREDIT))
    try:
        zx0_dir()
    except RuntimeError as e:
        bad.append(str(e))
    rep = 'Game      : x\nVerify    : x.rzx  100 frames -> IDENTICAL\nUnit      : 5 -> PASS\nResult    : PASSED\n'
    p = proof(rep, 'no-such-md5', 'no-such-md5', 300)
    if not p['replay'].startswith('Verify : x.rzx 100 frames -> IDENTICAL; Unit : 5 -> PASS') or 'coverage' not in p:
        bad.append(('proof from a run', p))
    if proof('Game      : x\n', 'no-such-md5', 'no-such-md5') != {'replay': 'not verified'}:
        bad.append('proof without a verification')
    if target(type('A', (), {})(), 'd/Chuckie Egg (1983)(A\'n\'F)[a3].z80')[1] is not None or \
            target(type('A', (), {})(), 'd/chuckie_egg.z80')[1] is None:
        bad.append('target: TOSEC name test')
    keep = {k: os.environ.get(k) for k in ('NEXCLASH_CONFIG', 'NEXCLASH_PATCH_BY')}
    with tempfile.TemporaryDirectory() as d:
        os.environ['NEXCLASH_CONFIG'] = os.path.join(d, 'sub', 'config.json')
        os.environ.pop('NEXCLASH_PATCH_BY', None)
        try:
            one = patch_by(type('A', (), {'patch_by': 'Ann Author'})())
            two = patch_by(type('A', (), {})())
            if one[0] != 'Ann Author' or two != ('Ann Author', os.environ['NEXCLASH_CONFIG']):
                bad.append(('patch_by saved once', one, two))
        finally:
            for k, v in keep.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    return bad


def chuckie_check(z80, work, nexclash_py, python):
    """selftest --tools with the reference: `patch` on Chuckie Egg writes the .nxc only, nxc.py lists it, and
    applied to the game it gives exactly the sprite .nex `patch --nex` writes (the record's MD5).
    -> [(name, ok, info)]."""
    env = dict(os.environ, NEXCLASH_CONFIG=os.path.join(work, 'config.json'), NEXCLASH_PATCH_BY='selftest')
    a, b = os.path.join(work, 'nxc_default'), os.path.join(work, 'nxc_nex')
    for o, extra in ((a, []), (b, ['--nex'])):
        subprocess.run([python, nexclash_py, 'patch', z80, '-o', o] + extra, env=env, capture_output=True)
    name = os.path.splitext(os.path.basename(z80))[0]
    pa, spr = os.path.join(a, name + '.nxc'), os.path.join(b, name + '_sprites.nex')
    left = sorted(f for f in os.listdir(a) if f.endswith(('.nex', '.nxc'))) if os.path.isdir(a) else []
    res = [('nxc: `patch` Chuckie Egg writes chuckie_egg.nxc and no .nex', left == [name + '.nxc'], left)]
    ls = subprocess.run([python, os.path.join(ROOT, 'nexclash', 'nxc.py'), pa], capture_output=True, text=True).stdout
    want = ['accepts %s, z80, 19515 bytes' % os.path.basename(z80), 'version=1.0', 'patch_by=selftest',
            'credit=Built with NexClash by Dean Woodyatt (Bleugh.biz, bleughb/nexclash, GPL-3.0-or-later)',
            'replay=RZX IDENTICAL, unit PASS (NexClash record chuckie_egg', 'nex_md5=bfad6be1e7c8a2c797a6242d7f339e35']
    res.append(('nxc: nxc.py lists it (target, version 1.0, patch_by, credit, PRF1 from the record)',
                all(w in ls for w in want), [w for w in want if w not in ls] or ls[-300:]))
    got = None
    if os.path.exists(pa) and os.path.exists(spr):
        from nexclash import nxc
        got = hashlib.md5(nxc.apply(open(pa, 'rb').read(), game=open(z80, 'rb').read())).hexdigest()
    res.append(('nxc: applied to the game it gives the `--nex` sprite build exactly (bfad6be1)',
                got == (md5(spr) if os.path.exists(spr) else None) == 'bfad6be1e7c8a2c797a6242d7f339e35',
                (got, md5(spr) if os.path.exists(spr) else None)))
    return res
