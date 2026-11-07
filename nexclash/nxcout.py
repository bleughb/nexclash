"""The .nxc output of the user-facing builds: `patch`, `new` and `auto` (refactor plan 23). GPL-3.0-or-later.

A build writes GAME.nxc beside its report: the file to share. It holds the sprite build as a patch that needs the
player's own copy of the game; the loader and the card setup are at github.com/jattree/nxc. The packager is that
repository's tools/nxc.py, vendored unmodified as nexclash/nxc.py (THIRD-PARTY-NOTICES); this module only feeds its
`make` path, which proves the .nxc rebuilds the .nex byte for byte before it writes anything, and checks that again.

  --nex          keep the .nex files too (default: the .nxc, the report and the outputs the .nxc does not hold)
  --no-nxc       the .nex files only, as before (selftest's rebuilds use it)
  --patch-by N   your name for the menu's credit line: saved once in the config file (config_path()), or
                 $NEXCLASH_PATCH_BY; never asked for
  --title T, --publisher "Ocean, 1986", --target-file NAME, --pok FILE   override what is found (below)

What goes in: title = the game nexclash knows the snapshot as (verified.json, the engine's record, identify);
publisher only from --publisher (the repository has no ZXDB); credit = nxc.py's NexClash default; version = the
record's (a rework's own, Jet Pac v1.1) for a byte-identical recorded build, else 1.0; cheats from --pok or GAME.pok
beside the .z80 (nxc.py import-pok); PRF1 replay = this run's Verify / Unit / Result / Checks lines, else the record
(or rework) of a byte-identical verified build, else "not verified". This run's structured check status
(NAME_checks.json) decides either way: an open check goes in PRF1 coverage ("this run's checks INCOMPLETE: ...";
nxc.py has no checks key) and a record's proof then reads "historical:". The target = the .z80's own name (TOSEC style
wanted: a note says when it is not) and its MD5, which nxc.py writes. What is packaged: the build's manifest()
(default or loading variant, every colour set, every toggle the engine declares in NAME_outputs.json, alone and with
each colour set); only the .nex files the .nxc holds are removed, the rest are kept and named. A build that failed its
checks, or has no sprite build this run, gets no .nxc and keeps its .nex files.
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
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
    win = os.path.join(ZX0_SRC, 'zx0.exe')      # Windows: upstream's own build, downloaded (never in Git)
    ccs = [c for c in (os.environ.get('CC'), 'cc', 'gcc', 'clang') if c and shutil.which(c)]
    if os.name == 'nt' and os.path.exists(win):
        if _sha(win) != pin['windows_binary_sha256']:
            raise RuntimeError('tools/zx0/zx0.exe is not upstream\'s build of ZX0 %s (tools/zx0/pin.json)' % pin['commit'][:7])
        shutil.copy(win, exe)
    elif ccs:
        srcs = [os.path.join(ZX0_SRC, f) for f in pin['sources'] if f.endswith('.c')]
        r = subprocess.run([ccs[0], '-O2', '-o', exe + '.tmp'] + srcs, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError('building tools/zx0 with %s failed: %s' % (ccs[0], r.stderr.strip()[-200:]))
        os.replace(exe + '.tmp', exe)
    else:
        raise RuntimeError('no zx0: no C compiler (cc, gcc, clang) to build tools/zx0%s, and $NXC_ZX0_DIR is not set' % (
            ', no tools/zx0/zx0.exe (download: %s)' % pin['windows_binary_url'] if os.name == 'nt' else ''))
    if os.name == 'nt':                         # nxc.py looks for 'zx0'; Windows runs zx0.exe for it
        shutil.copy(exe, os.path.join(cache, 'zx0'))
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


def record_build(h, nex_md5):
    """The record (and rework, or None) whose verified outputs include this byte-identical build of the snapshot h:
    -> (record, rework) or (None, None). A rework (record "rework") carries its own version and proof."""
    for r in _records():
        if r['inputs']['snapshot'].get('md5') != h:
            continue
        if nex_md5 in [o.get('md5') for o in (r.get('outputs') or {}).values()]:
            return r, None
        for x in r.get('rework', []):
            if nex_md5 in [o.get('md5') for o in (x.get('outputs') or {}).values()]:
                return r, x
    return None, None


def version_of(h, nex_md5):
    """The patch version: a rework's own ("version", Jet Pac v1.1), else the record's, else VERSION."""
    r, x = record_build(h, nex_md5)
    return (x or {}).get('version') or (r or {}).get('version') or VERSION


QUALIFY = 'coverage'          # PRF1 has no checks key (nxc.PROOF_KEYS): a run's open checks go in its coverage line


def check_status(rep, checks=None, claimed=False):
    """This run's check status -> None when complete, else the text that qualifies its PRF1. The structured status
    (NAME_checks.json, nexclash/runchecks.py) decides whenever there is one, with or without a Verify line; the
    report's Checks line only without it. A run with neither: 'no check status' if it claims a verification
    (claimed), else None (a rebuild claims nothing)."""
    from nexclash import runchecks
    if checks is not None:
        cs = checks.get('checks') or []
        return None if runchecks.complete(cs) else _ascii(runchecks.line(cs))
    line = next((_ascii(l) for l in rep.splitlines() if l.startswith('Checks')), None)
    if line is None:
        return 'INCOMPLETE: no check status' if claimed else None
    st = line.split(':', 1)[1].strip()
    return None if st.startswith('COMPLETE') else st


def _record_proof(h, spr_md5):
    """A byte-identical verified build's record (a rework's own proof line when the build is the rework's) -> PRF1
    replay fields, or None."""
    r, x = record_build(h, spr_md5)
    if r is None or not r.get('verified'):
        return None
    if x is None:
        what = '%s (NexClash record %s' % (r['status']['software'], r['name'])
    elif x.get('proof'):
        what = '%s (NexClash record %s rework %s, version %s' % (x['proof'], r['name'], x['name'], x.get('version', '?'))
    else:
        return None                         # a rework without its own proof line is not the record's proof
    return {'replay': _ascii('%s, verified %s; this build is byte-identical to it)' % (what, r['verified']['date'])),
            'replay_when': r['verified']['date']}


def proof(rep, h, spr_md5, quick=None, checks=None):
    """PRF1 fields: this run's verification, else a byte-identical verified build's record, else 'not verified'.
    checks = this run's structured status (runchecks.read). Whichever proof is used, this run's open checks
    (check_status) stay in the coverage line; a record's proof then reads 'historical:' - an earlier verification of
    the same bytes, never a new one, and it never hides this run's INCOMPLETE."""
    today = time.strftime('%Y-%m-%d')
    got = [_ascii(l) for l in rep.splitlines() if l.startswith(('Verify', 'Unit', 'Result', 'Checks'))]
    ran = any(l.startswith('Verify') for l in got)
    open_ = check_status(rep, checks, ran)
    cover = []
    if ran:
        p = {'replay': '; '.join(got), 'replay_when': today}
        if quick:
            cover.append('the first %d frames of each recording only (--quick)' % quick)
    else:
        p = _record_proof(h, spr_md5) or {'replay': 'not verified'}
        if open_ and p['replay'] != 'not verified':
            p['replay'] = 'historical: ' + p['replay']
    if open_:
        cover.append('this run\'s checks %s' % open_)
    if cover:
        p.update({QUALIFY: '; '.join(cover), QUALIFY + '_when': today})
    return p


def qualified(p):
    """Whether PRF1 fields (proof()) carry an open check of this run."""
    return 'this run\'s checks ' in p.get(QUALIFY, '')


NOT_SETS = ('sprites', 'plain', 'diag', 'debug', 'raw')


def manifest(out, name, since=None):
    """The outputs a build wrote, by role (docs/ENGINE_CONTRACT.md "Outputs"):
    {'default', 'loading': file or None, 'colours': {SET: {'default', 'loading'}}, 'plain': file or None,
     'toggles': {NAME: {'logic', 'what', 'default', 'loading', 'colours'}}, 'other': [files], 'stale': [files]}.
    Names: NAME_sprites.nex the default sprite build; NAME_sprites_loading.nex the same build with the tape's loading
    screen; NAME_SET.nex a colour set (one lower-case word: enhanced -> Enhanced), NAME_SET_loading.nex with the screen;
    NAME.nex the plain conversion; anything else (diagnostic, raw, noring) is other. An engine names its own outputs in
    NAME_outputs.json (the same keys, file names) when it does not follow these; only it can declare a toggle (an
    option a player switches on: "toggles", by its menu name: "logic" true when it changes the game logic, "what" it
    does, its build as "default" / "loading" and with each colour set as "colours"). Only .nex files written since
    `since` (this run's start) count: an older one is stale, never packaged as this build."""
    since = _START - 1 if since is None else since
    m = {'default': None, 'loading': None, 'colours': {}, 'plain': None, 'toggles': {}, 'other': [], 'stale': []}
    if not os.path.isdir(out):
        return m
    fresh = []
    for f in sorted(os.listdir(out)):
        if f.endswith('.nex'):
            (fresh if os.path.getmtime(os.path.join(out, f)) >= since else m['stale']).append(f)
    decl = os.path.join(out, name + '_outputs.json')
    if os.path.exists(decl) and os.path.getmtime(decl) >= since:
        d = json.load(open(decl))
        m.update({k: d.get(k) for k in ('default', 'loading', 'plain')})
        m['colours'] = {k: {'default': v.get('default'), 'loading': v.get('loading')} for k, v in d.get('colours', {}).items()}
        m['toggles'] = {k: {'logic': bool(v.get('logic')), 'what': v.get('what') or '', 'default': v.get('default'),
                            'loading': v.get('loading'),
                            'colours': {c: {'default': x.get('default'), 'loading': x.get('loading')}
                                        for c, x in (v.get('colours') or {}).items()}}
                        for k, v in d.get('toggles', {}).items()}
    else:
        for f in fresh:
            stem = f[:-4]
            rest = stem[len(name) + 1:] if stem.startswith(name + '_') else None
            if stem == name:
                m['plain'] = f
            elif rest == 'sprites':
                m['default'] = f
            elif rest == 'sprites_loading':
                m['loading'] = f
            elif rest and re.fullmatch(r'[a-z0-9]+(_loading)?', rest) and rest.split('_')[0] not in NOT_SETS:
                k = rest.split('_')[0].capitalize()
                m['colours'].setdefault(k, {'default': None, 'loading': None})['loading' if rest.endswith('_loading') else 'default'] = f
        if m['default'] is None and m['loading'] is None:       # an engine outside the naming: its one sprite build
            one = [f for f in fresh if 'sprites' in f and 'diag' not in f]
            m['default'] = one[0] if len(one) == 1 else None
    named = {m['default'], m['loading'], m['plain']} | {v for c in m['colours'].values() for v in c.values()} | \
        set(toggle_files(m))
    m['other'] = [f for f in fresh if f not in named]
    return m


def toggle_files(m):
    """Every file the manifest's toggles name."""
    return [f for t in m.get('toggles', {}).values()
            for f in [t['default'], t['loading']] + [x for c in t['colours'].values() for x in c.values()] if f]


def selection(m):
    """What the .nxc carries: (main .nex, {SET: .nex}, [(file, why) not packaged]). The loading variant is the build
    the player gets when there is one (the tape's screen in the .nxc), its colour sets then their loading variants."""
    skip = []
    loading = m['loading'] is not None
    main = m['loading'] if loading else m['default']
    sets = {}
    for k, v in sorted(m['colours'].items()):
        f = v['loading'] if loading else v['default']
        if f:
            sets[k] = f
        else:
            skip += [(x, 'colour set %s has no %s variant to go with %s' % (k, 'loading' if loading else 'default', main))
                     for x in v.values() if x]
    return main, sets, skip


def toggle_selection(m, sets):
    """The toggles the .nxc carries, with the build that goes with the main one (loading or not):
    ({NAME: (file, logic, what, {SET: file with that colour set too})}, [(file, why) not packaged]). sets = the colour
    sets selection() chose."""
    loading = m['loading'] is not None
    v = 'loading' if loading else 'default'
    out, skip = {}, []
    for n, t in m.get('toggles', {}).items():
        if not t[v]:
            skip += [(x, 'toggle %s has no %s variant' % (n, v)) for x in toggle_files({'toggles': {n: t}})]
            continue
        cs = {}
        for k, c in t['colours'].items():
            if c[v] and k in sets:
                cs[k] = c[v]
            else:
                skip += [(x, 'toggle %s with colour set %s: not a set the .nxc carries as %s' % (n, k, v))
                         for x in c.values() if x]
        out[n] = (t[v], t['logic'], t['what'], cs)
    return out, skip


# ------------------------------------------------------------------------------------------- packaging

def _run(nxc, argv):
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        nxc.run(argv)
    return log.getvalue().splitlines()


def make(a, z80, out, name, spr, rep, say, colours=None, toggles=None, checks=None):
    """GAME.nxc from the sprite build, its colour sets {SET: .nex path}, its toggles {NAME: (.nex path, logic, what,
    {SET: .nex path})} and the .z80, through nxc.py make (+ import-pok); checks = the run's structured status (PRF1).
    Every build it holds, each toggle alone and with each colour set, is checked on read-back. -> its path."""
    from nexclash import nxc
    nxc.ZX0_DIR = zx0_dir()
    colours, toggles = colours or {}, toggles or {}
    h, spr_md5 = md5(z80), md5(spr)
    t = title(a, z80, h)
    who, where = patch_by(a)
    tfile, tnote = target(a, z80)
    prf = proof(rep, h, spr_md5, getattr(a, 'quick', None), checks)
    for i, n in enumerate([k for k, x in toggles.items() if x[1]], 1):     # nxc.py: a logic toggle's toggle_N line
        prf['toggle_%d' % i] = _ascii('%s; %s' % (toggles[n][2] or n, 'not verified' if prf['replay'] == 'not verified'
                                                  else 'its builds checked with the others (replay%s)' % (
                                                      ', ' + QUALIFY if qualified(prf) else '')))
    ver = version_of(h, spr_md5)
    dst = os.path.join(out, name + '.nxc')
    argv = ['make', spr, z80, '-o', dst, '--file', tfile, '--patch-version', ver]
    for k, f in colours.items():
        argv += ['--colours', '%s=%s' % (k, f)]
    for k, (f, logic, _what, _cs) in toggles.items():
        argv += ['--toggle-logic' if logic else '--toggle', '%s=%s' % (k, f)]
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
    game = open(z80, 'rb').read()
    if nxc.apply(f, game=game) != open(spr, 'rb').read():
        os.remove(dst)
        raise ValueError('applied to %s it does not give %s' % (os.path.basename(z80), os.path.basename(spr)))
    if sorted(nxc.colour_sets(f)) != sorted(colours):
        os.remove(dst)
        raise ValueError('it offers colour sets %s, the build made %s' % (nxc.colour_sets(f), sorted(colours)))
    for k, cf in colours.items():
        if nxc.apply(f, game=game, colours=k) != open(cf, 'rb').read():
            os.remove(dst)
            raise ValueError('with colour set %s it does not give %s' % (k, os.path.basename(cf)))
    if nxc.toggles_of(f) != [(k, x[1]) for k, x in toggles.items()]:
        os.remove(dst)
        raise ValueError('it offers toggles %s, the build made %s' % (nxc.toggles_of(f), list(toggles)))
    for k, (tf, _logic, _what, cs) in toggles.items():
        for c, g in [(None, tf)] + sorted(cs.items()):
            if nxc.apply(f, game=game, colours=c, toggles=[k]) != open(g, 'rb').read():
                os.remove(dst)
                raise ValueError('with toggle %s%s it does not give %s' % (k, ' and colour set %s' % c if c else '',
                                                                           os.path.basename(g)))
    acc = [l for l in _run(nxc, [dst]) if l.startswith('accepts')]
    say('NXC       : %s  %d bytes; applied to %s it gives %s exactly (MD5 %s)' % (
        os.path.basename(dst), len(f), os.path.basename(z80), os.path.basename(spr), spr_md5))
    for k, cf in colours.items():
        say('            colour set %s gives %s exactly (MD5 %s)' % (k, os.path.basename(cf), md5(cf)))
    for k, (tf, logic, _what, cs) in toggles.items():
        for c, g in [(None, tf)] + sorted(cs.items()):
            say('            toggle %s%s%s gives %s exactly (MD5 %s)' % (
                k, ' (changes the game logic)' if logic and c is None else '', ' + colour set %s' % c if c else '',
                os.path.basename(g), md5(g)))
        for c in sorted(set(colours) - set(cs)):
            say('            toggle %s + colour set %s: no build of it to check against' % (k, c))
    say('            %s (MD5 %s); title %s; version %s; patch_by %s (%s)' % (
        acc[0] if acc else tfile, h, t or '(none)', ver, who or '(none)', where))
    say('            PRF1 replay=%s' % prf['replay'][:150])
    if qualified(prf):
        say('            PRF1 %s=%s' % (QUALIFY, prf[QUALIFY][:150]))
    if cheats:
        say('            cheats: %s' % cheats)
    if tnote:
        say('            note: ' + tnote)
    return dst


def package(a):
    """After a build: GAME.nxc in the output folder, its lines added to the report. The .nxc carries the build's
    manifest (manifest(), selection()): the default or its loading variant and every colour set, each checked on
    read-back. Without --nex only the .nex files the .nxc holds are removed; every other output is kept and named.
    -> the .nxc path or None."""
    if getattr(a, 'no_nxc', False):
        return None
    z80 = a.z80
    name = os.path.splitext(os.path.basename(z80))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '_nexclash')
    rp = os.path.join(out, name + '_report.txt')
    rep = open(rp).read() if os.path.exists(rp) else ''
    lines = []
    m = manifest(out, name)
    main, sets, skip = selection(m)
    tgl, tskip = toggle_selection(m, sets)
    skip += tskip
    from nexclash import runchecks
    ck = runchecks.read(out, name)          # this run's structured status (a stale file is an earlier run's)
    if ck is not None and os.path.getmtime(runchecks.path(out, name)) < _START - 1:
        ck = None
    dst = None
    if main is None:
        old = [f for f in m['stale'] if 'sprites' in f]
        lines.append('NXC       : not made - no sprite build%s' % (
            ' this run (%s is from an earlier run)' % ', '.join(old) if old else ''))
    elif 'FAILED' in rep or 'MISMATCH' in rep or any(c['status'] == 'fail' for c in (ck or {}).get('checks', [])):
        lines.append('NXC       : not made - the build failed its checks (its .nex files are kept)')
    else:
        try:
            dst = make(a, z80, out, name, os.path.join(out, main), rep, lines.append,
                       {k: os.path.join(out, f) for k, f in sets.items()},
                       {k: (os.path.join(out, f), lg, w, {c: os.path.join(out, g) for c, g in cs.items()})
                        for k, (f, lg, w, cs) in tgl.items()}, ck)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError, SystemExit) as e:
            lines.append('NXC       : not made - %s (the .nex files are kept)' % e)
    if dst:
        lines.append('            share %s: it needs the player\'s own copy of the game; loader and card setup: %s' % (
            os.path.basename(dst), SHARE))
        held = [main] + list(sets.values()) + [x for f, _lg, _w, cs in tgl.values() for x in [f] + list(cs.values())]
        kept = sorted(f for f in {m['default'], m['plain']} | {v for c in m['colours'].values() for v in c.values()}
                      | set(toggle_files(m)) | set(m['other']) if f and f not in held)
        if not getattr(a, 'nex', False):
            for f in held:
                os.remove(os.path.join(out, f))
            lines.append('            removed %s: the .nxc holds them (--nex keeps the .nex files)' % ', '.join(held))
        why = dict(skip)
        if kept:
            lines.append('            kept %s: not in the .nxc' % ', '.join(
                '%s (%s)' % (f, why.get(f) or ('the plain conversion' if f == m['plain'] else
                                               'the build without the loading screen' if f == m['default'] else 'not a packaged role'))
                for f in kept))
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
    bad += proof_selfcheck()
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


def _status(st, required=True):
    return {'schema': 1, 'checks': [dict(check='rom_paths', status=st, why='synthetic', required=required, coverage={})]}


def proof_selfcheck():
    """proof() against a run's structured status (no game data: a verified record's MD5s stand for a byte-identical
    build). An open check is kept whether or not the run has a Verify line, beside a record's proof (labelled
    historical) or 'not verified'; a complete rebuild gets the record's proof unchanged; nxc.py takes every result.
    -> list of failures."""
    from nexclash import nxc
    bad = []
    r0 = next((r for r in _records() if r.get('verified') and record_build(
        r['inputs']['snapshot'].get('md5'), (r.get('outputs') or {}).get('sprites', {}).get('md5')) == (r, None)), None)
    if r0 is None:
        return ['proof: no verified record to stand for a byte-identical build']
    h0, s0 = r0['inputs']['snapshot']['md5'], r0['outputs']['sprites']['md5']
    rebuild = 'Game      : x\nResult    : PASSED (rebuild)\n'
    run = 'Game      : x\nVerify    : x.rzx  100 frames -> IDENTICAL\nResult    : PASSED\n'
    inc, done = _status('incomplete'), _status('not run', False)
    hist = _record_proof(h0, s0)
    cases = [
        ('incomplete, no Verify line, record', proof(rebuild, h0, s0, checks=inc),
         lambda p: p['replay'] == 'historical: ' + hist['replay'] and p['replay_when'] == hist['replay_when']
         and qualified(p) and 'INCOMPLETE' in p[QUALIFY]),
        ('incomplete, no Verify line, no record', proof(rebuild, 'no-such-md5', 'no-such-md5', checks=inc),
         lambda p: p['replay'] == 'not verified' and qualified(p) and 'INCOMPLETE' in p[QUALIFY]),
        ('incomplete, Verify line', proof(run, h0, s0, checks=inc),
         lambda p: p['replay'].startswith('Verify : x.rzx') and qualified(p) and 'INCOMPLETE' in p[QUALIFY]),
        ('failed, no Verify line, record', proof(rebuild, h0, s0, checks=_status('fail')),
         lambda p: p['replay'].startswith('historical: ') and 'FAILED' in p.get(QUALIFY, '')),
        ('complete rebuild, record (unchanged)', proof(rebuild, h0, s0, checks=done), lambda p: p == hist),
        ('rebuild without a status, record (unchanged)', proof(rebuild, h0, s0), lambda p: p == hist),
        ('report Checks line INCOMPLETE, no status file', proof(rebuild + 'Checks    : INCOMPLETE: rom_paths incomplete\n',
                                                                h0, s0), lambda p: qualified(p)),
        ('Verify line, complete', proof(run + 'Checks    : COMPLETE: rom_paths pass\n', h0, s0, checks=_status('pass')),
         lambda p: not qualified(p)),
        ('Verify line, no status at all', proof(run, h0, s0), lambda p: qualified(p))]
    for label, p, ok in cases:
        try:
            nxc.proof_text(p)
        except ValueError as e:
            bad.append(('proof %s: nxc.py refuses it' % label, str(e)))
            continue
        if not ok(p):
            bad.append(('proof %s' % label, p))
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
    res = [('nxc: `patch` Chuckie Egg writes chuckie_egg.nxc and keeps only the plain chuckie_egg.nex (not in the .nxc)',
            left == [name + '.nex', name + '.nxc'], left)]
    ls = subprocess.run([python, os.path.join(ROOT, 'nexclash', 'nxc.py'), pa], capture_output=True, text=True).stdout
    from nexclash import records
    rec_md5 = records.load('chuckie_egg')['outputs']['sprites']['md5']     # the record's, not a copy of it here
    want = ['accepts %s, z80, 19515 bytes' % os.path.basename(z80), 'version=1.0', 'patch_by=selftest',
            'credit=Built with NexClash by Dean Woodyatt (Bleugh.biz, bleughb/nexclash, GPL-3.0-or-later)',
            'replay=RZX IDENTICAL, unit PASS (NexClash record chuckie_egg', 'nex_md5=' + rec_md5]
    res.append(('nxc: nxc.py lists it (target, version 1.0, patch_by, credit, PRF1 from the record)',
                all(w in ls for w in want), [w for w in want if w not in ls] or ls[-300:]))
    got = None
    if os.path.exists(pa) and os.path.exists(spr):
        from nexclash import nxc
        got = hashlib.md5(nxc.apply(open(pa, 'rb').read(), game=open(z80, 'rb').read())).hexdigest()
    res.append(('nxc: applied to the game it gives the `--nex` sprite build exactly (%s)' % rec_md5[:8],
                got == (md5(spr) if os.path.exists(spr) else None) == rec_md5,
                (got, md5(spr) if os.path.exists(spr) else None)))
    return res


QAOP = 'QAOP + Space'
MULTI = (('nightshade', None, {(None, None): 'sprites', ('Enhanced', None): 'enhanced'}, ['plain']),
         ('starquake', None, {(None, None): 'loading'}, ['plain', 'sprites']),
         ('atic_atac', 'v13', {(None, None): 'sprites', ('Enhanced', None): 'enhanced', (None, QAOP): 'sprites_qaop',
                               ('Enhanced', QAOP): 'enhanced_qaop'}, ['plain']))


def _auto(python, nexclash_py, z80, o, rec, x, work, extra=()):
    """`auto` as the record's (or rework x's) rebuild, default .nxc output unless extra says otherwise."""
    rc = (x or rec)['rebuild']
    cmd = [python, nexclash_py, 'auto', z80, '--no-record', '-o', o] + list((x or {}).get('args', [])) + \
        [v for v in rc.get('args', []) if v != '--no-record'] + list(extra)
    if x is not None and rc.get('decisions'):
        dp = os.path.join(work, 'rework_%s_decisions.json' % x['name'])
        json.dump(rc['decisions'], open(dp, 'w'))
        cmd += ['--decisions', dp]
    env = dict(os.environ, NEXCLASH_CONFIG=os.path.join(work, 'config.json'), NEXCLASH_PATCH_BY='selftest',
               **(x or {}).get('env', {}))
    subprocess.run(cmd, env=env, capture_output=True)


def multi_check(src, work, nexclash_py, python, stage):
    """selftest --tools with the reference: the default output of builds with several outputs (Nightshade: default +
    Enhanced; Starquake: the loading variant; Atic Atac v1.3: default + Enhanced + the QAOP + Space toggle, alone and
    with Enhanced) packages every variant, keeps the outputs the .nxc does not hold, and each variant read back from
    the .nxc is its record's MD5. stage = selftest.stage. -> [(name, ok, info)], or [('SKIP', why)] per record whose
    reference files are missing."""
    from nexclash import nxc, records
    res = []
    for game, rw, want, keep in MULTI:
        rec = records.load(game)
        d, why = stage(rec, src, os.path.join(work, 'multi'))
        x = next((r for r in rec.get('rework', []) if r['name'] == rw), None) if rw else None
        if d is None or (x or {}).get('_missing'):
            res.append(('SKIP', 'nxc multi-output %s%s: %s' % (game, ' rework %s' % rw if rw else '',
                                                               why or x['_missing'])))
            continue
        label = game + (' v%s' % x.get('version', rw) if x else '')
        outs = (x or rec)['outputs']
        z80 = os.path.join(d, rec['inputs']['snapshot']['name'])
        o = os.path.join(d, 'nxc_default' + ('_' + rw if rw else ''))
        _auto(python, nexclash_py, z80, o, rec, x, d)
        name = os.path.splitext(os.path.basename(z80))[0]
        pa = os.path.join(o, name + '.nxc')
        left = sorted(f for f in os.listdir(o) if f.endswith(('.nex', '.nxc'))) if os.path.isdir(o) else []
        wl = sorted([name + '.nxc'] + [rec['outputs'][k]['file'] for k in keep])
        res.append(('nxc: %s default output = %s (the outputs the .nxc does not hold are kept)' % (label, ', '.join(wl)),
                    left == wl, left))
        f = open(pa, 'rb').read() if os.path.exists(pa) else b''
        sets = sorted({k for k, _ in want if k})
        res.append(('nxc: %s offers colour sets %s' % (label, sets or 'none'), bool(f) and sorted(nxc.colour_sets(f)) == sets,
                    nxc.colour_sets(f) if f else 'no .nxc'))
        tg = [(t, True) for t in sorted({t for _, t in want if t})]
        res.append(('nxc: %s offers toggles %s' % (label, tg or 'none'), bool(f) and nxc.toggles_of(f) == tg,
                    nxc.toggles_of(f) if f else 'no .nxc'))
        if tg:
            prf = _prf1(f) if f else {}
            res.append(('nxc: %s PRF1 toggle_1 says what the toggle changes' % label,
                        prf.get('toggle_1', '').startswith(tg[0][0] + ', changes the game logic'), prf.get('toggle_1')))
        g = open(z80, 'rb').read()
        for (k, t), out_key in want.items():
            exp = outs[out_key]['md5']
            got = hashlib.md5(nxc.apply(f, game=g, colours=k, toggles=[t] if t else ())).hexdigest() if f else None
            res.append(('nxc: %s %s read back = the record\'s %s (%s)' % (
                label, ' + '.join(v for v in (k, t) if v) or 'default', out_key, exp[:8]), got == exp, got))
    return res


def _prf1(f):
    """A .nxc's PRF1 fields, decoded from the file."""
    from nexclash import nxc
    body = b''.join(b for t, b in nxc.blocks(f)[1] if t == b'PRF1').decode('ascii', 'replace')
    return dict(l.split('=', 1) for l in body.splitlines() if '=' in l)


def proof_check(src, work, nexclash_py, python, stage):
    """selftest --tools with the reference: PRF1 decoded from real .nxc files of Nightshade's byte-identical rebuild,
    packaged after a run whose structured status (NAME_checks.json) says: (a) INCOMPLETE, no Verify line, the record
    matching: the record's proof as historical + this run's INCOMPLETE; (b) the same, no record matching: 'not
    verified' + INCOMPLETE; (c) complete, no Verify line: the record's proof exactly as before, nothing added;
    (d) INCOMPLETE with a Verify line: packaged (nxc.py has no checks key) with the INCOMPLETE kept.
    -> [(name, ok, info)] or [('SKIP', why)]."""
    from unittest import mock
    from types import SimpleNamespace
    from nexclash import nxc, records, runchecks
    rec = records.load('nightshade')
    d, why = stage(rec, src, os.path.join(work, 'proof'))
    if d is None:
        return [('SKIP', 'nxc PRF1 status regressions: %s' % why)]
    z80 = os.path.join(d, rec['inputs']['snapshot']['name'])
    name = os.path.splitext(os.path.basename(z80))[0]
    built = os.path.join(d, 'built')
    _auto(python, nexclash_py, z80, built, rec, None, d, ['--no-nxc'])
    hist = '%s (NexClash record nightshade, verified %s; this build is byte-identical to it)' % (
        _ascii(rec['status']['software']), rec['verified']['date'])
    rebuild = ['Game      : %s' % name, 'Result    : PASSED (no differential verification line)']
    run = ['Game      : %s' % name, 'Verify    : synthetic.rzx  100 frames -> IDENTICAL', 'Result    : PASSED']
    inc, done = _status('incomplete'), _status('not run', False)
    cases = (('a', rebuild, inc, True, lambda p: p.get('replay') == 'historical: ' + hist and
              p.get('replay_when') == rec['verified']['date'] and 'INCOMPLETE' in p.get(QUALIFY, '')),
             ('b', rebuild, inc, False, lambda p: p.get('replay') == 'not verified' and 'INCOMPLETE' in p.get(QUALIFY, '')),
             ('c', rebuild, done, True, lambda p: p == {'replay': hist, 'replay_when': rec['verified']['date']}),
             ('d', run, inc, True, lambda p: p.get('replay', '').startswith('Verify : synthetic.rzx') and
              'INCOMPLETE' in p.get(QUALIFY, '')))
    what = {'a': 'INCOMPLETE, no Verify line, record matching: historical record proof + INCOMPLETE',
            'b': 'INCOMPLETE, no Verify line, no record: not verified + INCOMPLETE',
            'c': 'complete rebuild, no Verify line: the record\'s proof unchanged',
            'd': 'INCOMPLETE with a Verify line: packaged, INCOMPLETE kept'}
    res = []
    keep = {k: os.environ.get(k) for k in ('NEXCLASH_CONFIG', 'NEXCLASH_PATCH_BY')}
    os.environ.update(NEXCLASH_CONFIG=os.path.join(work, 'config.json'), NEXCLASH_PATCH_BY='selftest')
    try:
        for key, rep, st, rec_on, ok in cases:
            o = os.path.join(d, 'case_' + key)
            os.makedirs(o, exist_ok=True)
            for f in os.listdir(built):
                if f.endswith('.nex'):
                    shutil.copy(os.path.join(built, f), o)          # written now: this run's outputs
            st = dict(st, complete=runchecks.complete(st['checks']))
            json.dump(st, open(runchecks.path(o, name), 'w'))
            rep = rep + ['Checks    : %s' % runchecks.line(st['checks'])]
            open(os.path.join(o, name + '_report.txt'), 'w').write('\n'.join(rep) + '\n')
            a = SimpleNamespace(z80=z80, out=o, nex=False, no_nxc=False)
            with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(
                    sys.modules[__name__], '_records', side_effect=lambda: [] if not rec_on else records.all_records()):
                dst = package(a)
            p = _prf1(open(dst, 'rb').read()) if dst else {}
            same = bool(dst) and hashlib.md5(nxc.apply(open(dst, 'rb').read(), game=open(z80, 'rb').read())).hexdigest() \
                == rec['outputs']['sprites']['md5']
            res.append(('nxc: PRF1 read from the .nxc, (%s) %s' % (key, what[key]), bool(dst) and same and ok(p), p or 'no .nxc'))
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return res
