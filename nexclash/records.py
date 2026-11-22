"""Evidence records: one JSON file per game in docs/records/ - what the game's build depends on, how
to rebuild it without a recording, how to re-verify it, its verified outputs and its status.

Why: re-proving every game at every release does not scale (1,000 games x an RZX replay each).
A verification is evidence about exact inputs. Each record keeps two stamps of those inputs
(per-file hashes of everything the build reads):
  checked   - the rebuilt outputs matched the verified MD5s (seconds per game, no recording);
  verified  - the outputs were replayed against the recordings and PASSED (minutes to an hour).
What a change needs follows from the files it touched (plan()):
  a game's OWN files (engine module, .asm, profile, its data)  -> rebuild + re-verify that game;
  SHARED files only (converter, boot stub, build code, ...)    -> rebuild (MD5s must match), and
      re-verify one representative game per engine (shared verification code is exercised there).
Unchanged games are not touched. STATUS.md's table, VERIFICATION.md's checksum list and
docs/profiles/verified.json are generated from the records (views(); `python -m nexclash.records
views`), so a game session edits only its own record.

    python -m nexclash.records plan            what the current tree needs (no running)
    python -m nexclash.records views [--check] regenerate (or check) the generated views
    python -m nexclash.records deps GAME       the files GAME's build depends on
    python -m nexclash.records selfcheck       plan() on synthetic stamps (selftest --tools runs it)

Record fields (docs/records/<name>.json; copy the nearest record, then edit):
  name            file stem; selftest's work folder
  order           STATUS.md row order (unique; next free number)
  game, doc       STATUS title source / games/<doc>
  engine          engine key; games sharing one form a group for "representative" re-verification
  representative  true = the game re-verified when shared files change (one per engine)
  reference       folder under specnext/reference/
  inputs          snapshot + recordings: name (canonical name selftest copies to), md5, path (under
                  the reference folder; maintainers fill it); "missing": why = not in the references yet (the
                  verify that needs it is skipped, nothing stamped; the rebuild and the reworks run);
                  tapes (a game built from its tape files, nexclash/tapeset.py): [{set, files: [{name, md5, path}]}]
                  alternative releases, each its files in order; the rebuild and verify pass set 0 (`--tape`), every
                  other set must rebuild the same outputs; a file two sets share has one name (staged once)
  modules         nexclash modules the build imports (closure computed); own_modules = the engine's
  data            own data files (profile, .asm, ...); shared_data = data shared with other games
  rebuild         auto args (no recording), rzx used by the build, decisions (stored analysis facts)
                  or {"cmd": "convert"} for plain-only games
  verify          auto args, rzx (recordings verified against), auto_record, minutes (rough cost),
                  differential false + note for games verified only by analysis
  outputs         {plain|sprites: {file, md5}} the rebuild must reproduce
  repro           extra builds (old strategies) with their own outputs
  status          STATUS.md columns: title, engine_col, build, software, hardware, next
  checks          quick per-game checks run with every rebuild (e.g. "asm2profile:<profile>")
  rework          opt-in reworks: [{name, version, args, env (e.g. NEXCLASH_REWORK), inputs (its own: missing ones
                  skip the rework, never the base), rebuild / verify (as the record's), outputs, proof (PRF1 line), note}]
  pin             shared behaviour the game keeps ({"altrom_fill": "rom3"}): auto rebuilds it so and skips the ROM
                  path check (it verifies as it was verified)
  rom_paths_known ROM differences the ROM path check lists as KNOWN, not faults: [{image, from, to, why}]
                  (hex addresses; nextboot.rom_paths known; Knight Tyme's Bridge star map)
  excluded        reason string: plan() never rebuilds or re-verifies this game (--affected, release,
                  --full); `selftest.py --game NAME [--verify]` still runs it explicitly
  canary          1 = tool-chain canary stage 1, 2 = stage 2 (selftest --canary); canary_quick =
                  frames of the stage-2 quick verify
  checked / verified   stamps written by selftest --stamp (dependency hashes, date); never by hand
"""
import ast
import glob
import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS = os.path.join(ROOT, 'docs', 'records')
PKG = os.path.join(ROOT, 'nexclash')
ALWAYS = ['nexclash.py', 'nexclash/engines.py']            # dispatch: every build goes through them
# Shared files whose change needs a REBUILD only, never a re-verification: they run no verification
# code, and any effect they can have on a game shows in its rebuilt MD5s. Keep this list short and
# give the reason; a file that runs verification code never belongs here.
REBUILD_ONLY = {
    'nexclash/engines.py': 'engine registry: a table + a loop that picks the module (engines.py docstring)',
}


# ------------------------------------------------------------------------------------ records

def load(name):
    return json.load(open(os.path.join(RECORDS, name + '.json')))


def save(rec):
    open(os.path.join(RECORDS, rec['name'] + '.json'), 'w').write(json.dumps(rec, indent=1) + '\n')


def all_records():
    return [json.load(open(p)) for p in sorted(glob.glob(os.path.join(RECORDS, '*.json')))]


# ------------------------------------------------------------------------------- dependencies

_IMPORTS = {}               # path -> (nexclash modules, uses Pillow): each module parsed once per run, not once per record


def _module_imports(path):
    """nexclash modules a module imports (relative, `from nexclash`, `import nexclash.x`, or the bare
    name when nexclash/ is on sys.path), including imports inside functions and __import__('x')."""
    return _parsed(path)[0]


def uses_pillow(modules):
    """True when a module of this closure imports PIL: its outputs can depend on the Pillow installed."""
    return any(_parsed(os.path.join(PKG, m + '.py'))[1] for m in modules)


def _parsed(path):
    if path not in _IMPORTS:
        _IMPORTS[path] = _parse_imports(path)
    return _IMPORTS[path]


def _parse_imports(path):
    tree = ast.parse(open(path).read())
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            mod = n.module or ''
            if n.level or mod == 'nexclash' or mod.startswith('nexclash.'):
                base = mod.split('.')[-1] if mod not in ('', 'nexclash') else ''
                if base:
                    names.add(base)
                else:
                    names.update(a.name for a in n.names)
            else:
                names.add(mod.split('.')[0])
        elif isinstance(n, ast.Import):
            for a in n.names:
                names.add(a.name.split('.')[-1] if a.name.startswith('nexclash.') else a.name.split('.')[0])
        elif isinstance(n, ast.Call) and getattr(n.func, 'id', None) == '__import__' and n.args:
            for c in ast.walk(n.args[0]):
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    names.add(c.value)
    return {x for x in names if os.path.exists(os.path.join(PKG, x + '.py'))}, 'PIL' in names


def closure(modules):
    """modules (names in nexclash/) plus every nexclash module they import, transitively."""
    seen, todo = set(), list(modules)
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        todo += sorted(_module_imports(os.path.join(PKG, m + '.py')) - seen)
    return seen


def deps(rec):
    """Repository-relative paths the game's build and verification read (sorted), plus the
    pseudo-entries 'skoolkit' (its version) and, for a build whose modules import PIL, 'pillow'."""
    mods = closure(rec['modules'])
    files = set(ALWAYS) | {'nexclash/%s.py' % m for m in mods} | set(rec.get('data', [])) \
        | set(rec.get('shared_data', []))
    return sorted(files) + ['skoolkit'] + (['pillow'] if uses_pillow(mods) else [])


def own(rec):
    """The game's own files: its engine modules and data, and its recipe and ROM identity (PSEUDO): a change ->
    re-verify this game."""
    return {'nexclash/%s.py' % m for m in rec.get('own_modules', [])} | set(rec.get('data', [])) | set(PSEUDO)


def _version(package):
    try:
        from importlib.metadata import version
        return version(package)
    except Exception:                       # noqa: BLE001
        return 'unknown'


def _skoolkit_version():
    return _version('skoolkit')


def hashes(paths, root=ROOT):
    out = {}
    for p in paths:
        if p in VERSIONS:
            out[p] = _version(p)
        else:
            f = os.path.join(root, p)
            out[p] = hashlib.sha256(open(f, 'rb').read()).hexdigest()[:16] if os.path.exists(f) else 'missing'
    return out


# The record's own recipe and the ROM verification modelled are part of what a stamp proves (pseudo entries beside
# the file hashes): 'recipe' = recipe_digest(rec), 'rom' = rom_identity(). A stamp written before they existed has
# neither: such a stamp is taken as it is until the next one (migration). 'rom' counts only when a ROM is supplied
# now (NEXCLASH_NEXT_ROM): a plan without one cannot judge a stamp made with one; a stamp made without one
# ('sinclair') is due when one is supplied.
PSEUDO = ('recipe', 'rom')
# Installed packages a stamp names by version, shared like any shared file (rebuild; the representative re-verifies).
# 'pillow' (2026-11-12) is absent from the stamps before it: taken as it is until the next stamp, like PSEUDO.
VERSIONS = ('skoolkit', 'pillow')
MIGRATING = PSEUDO + ('pillow',)
# Fields that decide what a build makes and what its verification proves; prose (note, why, minutes) is left out.
RECIPE_FIELDS = ('inputs', 'modules', 'own_modules', 'data', 'shared_data', 'rebuild', 'verify', 'outputs', 'repro',
                 'pin', 'rom_paths_known', 'rework', 'checks')
PROSE = ('note', 'why', 'minutes')
SINCLAIR = 'sinclair'


def _semantic(v):
    if isinstance(v, dict):
        return {k: _semantic(x) for k, x in sorted(v.items()) if k not in PROSE and not k.startswith('_')}
    if isinstance(v, list):
        return [_semantic(x) for x in v]
    return v


def recipe_digest(rec):
    """Canonical digest of the record's recipe: inputs, build / verify arguments, decisions, pins, waivers, reworks,
    expected outputs (RECIPE_FIELDS; stamps, status and prose left out)."""
    d = {k: _semantic(rec[k]) for k in RECIPE_FIELDS if k in rec}
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


def rom_identity():
    """MD5 (16 hex) of the system ROM a verification models now ($NEXCLASH_NEXT_ROM), None without one."""
    p = os.environ.get('NEXCLASH_NEXT_ROM')
    return hashlib.md5(open(p, 'rb').read()).hexdigest()[:16] if p and os.path.isfile(p) else None


def state(rec):
    """What a stamp records now: the dependency hashes + the recipe digest + the ROM identity."""
    now = hashes(deps(rec))
    now['recipe'] = recipe_digest(rec)
    now['rom'] = rom_identity() or SINCLAIR
    return now


def changed(stamp, now, build=False):
    """Paths whose hash differs between a stamp {path: hash} and now (added / removed count). Pseudo entries
    (PSEUDO): absent from the stamp = not compared (migration); 'rom' only when a ROM is supplied now, and never for a
    build (build=True: the checked stamp; the ROM changes no byte)."""
    stamp = stamp or {}
    keys = set(stamp) | set(now)

    def skip(k):
        return k in MIGRATING and (k not in stamp or (k == 'rom' and (build or now.get(k) in (None, SINCLAIR))))
    return sorted(k for k in keys if not skip(k) and stamp.get(k) != now.get(k))


def plan(recs=None, full=False):
    """-> list of (record, action, reason): action 'skip' | 'rebuild' | 'reverify' | 'none' (no
    automated rebuild for this game yet)."""
    recs = recs if recs is not None else all_records()
    out = []
    shared_hit = {}                             # engine -> shared files changed since a verification
    now_all = {}
    for r in recs:
        now = state(r)
        now_all[r['name']] = now
        ch_checked = changed(r.get('checked', {}).get('deps'), now, build=True)
        ch_verified = changed(r.get('verified', {}).get('deps'), now)
        mine = [p for p in ch_verified if p in own(r)]
        shared = [p for p in ch_verified if p not in own(r) and p not in REBUILD_ONLY]
        if shared:
            shared_hit.setdefault(r['engine'], set()).update(shared)
        if r.get('excluded'):
            out.append([r, 'none', 'excluded: %s' % r['excluded']])
        elif not r.get('rebuild'):
            out.append([r, 'none', 'no automated rebuild recipe yet'])
        elif full and r.get('verify'):
            out.append([r, 'reverify', '--full'])
        elif mine and r.get('verify'):
            out.append([r, 'reverify', 'own files changed since verified: %s' % ', '.join(mine[:4])])
        elif full and not r.get('verify'):
            out.append([r, 'rebuild', 'no verify recipe (rebuild only)'])
        elif ch_checked:
            out.append([r, 'rebuild', 'changed since last check: %s' % ', '.join(ch_checked[:4])])
        else:
            out.append([r, 'skip', 'unchanged since checked'])
    # one representative per engine re-verifies when shared files changed since ITS verification
    for item in out:
        r, act = item[0], item[1]
        if r.get('representative') and act in ('rebuild', 'skip') and shared_hit.get(r['engine']) and r.get('verify'):
            sh = sorted(p for p in changed(r.get('verified', {}).get('deps'), now_all[r['name']])
                        if p not in own(r) and p not in REBUILD_ONLY)
            if sh:
                item[1], item[2] = 'reverify', 'representative of engine %s; shared files changed: %s' % (
                    r['engine'], ', '.join(sh[:4]))
    # every shared file changed since a member's verification is replayed by a member that READS it: a library only
    # one member uses would otherwise ride on a representative that does not depend on it (Codex review T3)
    def shared_changed(r):
        return {p for p in changed(r.get('verified', {}).get('deps'), now_all[r['name']])
                if p not in own(r) and p not in REBUILD_ONLY}
    def verified_now(r):                        # shared files this member verified at their current hash
        v = r.get('verified', {}).get('deps') or {}
        n = now_all[r['name']]
        return {p for p, h in v.items() if n.get(p) == h and p not in own(r) and p not in REBUILD_ONLY}
    for eng, files in shared_hit.items():
        items = [i for i in out if i[0]['engine'] == eng]
        covered = set().union(set(), *(shared_changed(i[0]) for i in items if i[1] == 'reverify'),
                              *(verified_now(i[0]) for i in items if i[0].get('verify')))
        for f in sorted(files - covered):
            cand = sorted((i for i in items if i[1] in ('rebuild', 'skip') and i[0].get('verify')
                           and f in shared_changed(i[0])), key=lambda i: not i[0].get('representative'))
            if cand:
                i = cand[0]
                i[1], i[2] = 'reverify', 'engine %s: replays shared %s (no member re-verifying reads it)' % (eng, f)
                covered |= shared_changed(i[0])
    return [tuple(x) for x in out], now_all


EVIDENCE = ('functional', 'integration', 'timing', 'display', 'hardware')
EVIDENCE_LEVELS = ('not assessed', 'host', 'assembled', 'integrated', 'hardware')


def evidence(rec):
    """status.evidence, every category filled: {category: {level, scope, artifact?}}. Optional: a record without
    it (every legacy record) reads 'not assessed', never a failure."""
    given = rec.get('status', {}).get('evidence', {})
    return {c: dict(given.get(c) or {'level': 'not assessed', 'scope': ''}) for c in EVIDENCE}


_INCLUDE_RE = re.compile(r'^[ \t]*INCLUDE[ \t]+"?([^"\s;]+)"?', re.I | re.M)


def asm_includes(path, seen=None, root=ROOT):
    """Repository-relative paths an assembly source INCLUDEs, recursively, resolved from its folder as sjasmplus
    does (asm/x.asm: INCLUDE "lib/hlib_speed.asm" -> asm/lib/hlib_speed.asm). Generated files that do not exist
    in the tree are left out."""
    seen = set() if seen is None else seen
    try:
        text = open(os.path.join(root, path), errors='replace').read()
    except OSError:
        return seen
    for m in _INCLUDE_RE.finditer(text):
        inc = posixpath.normpath(posixpath.join(posixpath.dirname(path), m.group(1).replace('\\', '/')))   # '/' on Windows too
        if inc not in seen and os.path.exists(os.path.join(root, inc)):
            seen.add(inc)
            asm_includes(inc, seen, root)
    return seen


def include_problems(rec):
    """Assembly the record's declared sources INCLUDE but the record does not list: deps() follows Python imports,
    not INCLUDEs, so a library edit would not plan this game. Libraries (asm/lib/) belong in shared_data, the
    game's own includes in data. -> list"""
    data, shared = set(rec.get('data', [])), set(rec.get('shared_data', []))
    bad = []
    for src in sorted(p for p in data if p.endswith(('.asm', '.inc'))):
        for inc in sorted(asm_includes(src)):
            lib = inc.startswith('asm/lib/')
            if lib and inc not in shared:
                bad.append('%s: %s (INCLUDEd by %s) %s' % (rec['name'], inc, src,
                           'is in data: a library belongs in shared_data' if inc in data else 'not in shared_data'))
            elif not lib and inc not in data | shared:
                bad.append('%s: %s (INCLUDEd by %s) not in data' % (rec['name'], inc, src))
    return bad


def evidence_problems(rec):
    """Unknown categories / levels, or a claim without its scope. -> list"""
    bad = []
    for c, e in rec.get('status', {}).get('evidence', {}).items():
        if c not in EVIDENCE:
            bad.append('%s: evidence category %s' % (rec['name'], c))
        elif e.get('level') not in EVIDENCE_LEVELS:
            bad.append('%s: evidence %s level %s' % (rec['name'], c, e.get('level')))
        elif e['level'] != 'not assessed' and not e.get('scope'):
            bad.append('%s: evidence %s has no scope (artifact, inputs, environment)' % (rec['name'], c))
    return bad


def selfcheck():
    """plan() on synthetic stamps (no reference files needed): an unchanged tree skips everything; an
    engine file re-verifies its game only; a shared file rebuilds every dependent and re-verifies
    only the representative; a re-verification left due survives a rebuild-only stamp; an excluded
    record is never planned. -> failures"""
    import copy
    recs = [r for r in all_records() if r.get('rebuild') and not r.get('excluded')]
    base = {r['name']: state(r) for r in recs}

    def run(edit=None, verified_edit=None):
        rs = copy.deepcopy(recs)
        for r in rs:
            c = dict(base[r['name']])
            v = dict(c)
            if edit and edit in c:
                c[edit] = v[edit] = 'old'
            if verified_edit and verified_edit in v:
                v[verified_edit] = 'old'
            r['checked'], r['verified'] = {'deps': c}, {'deps': v}
        return {r['name']: act for r, act, _ in plan(rs)[0]}
    bad = []
    p = run()
    if set(p.values()) != {'skip'}:
        bad.append('unchanged tree: %s' % p)
    p = run('nexclash/chuckie.py')
    if p['chuckie_egg'] != 'reverify' or any(a != 'skip' for n, a in p.items() if n != 'chuckie_egg'):
        bad.append('engine file: %s' % p)
    tid = [r for r in recs if r['engine'] == 'tid']
    p = run('nexclash/z80tonex.py')
    for r in recs:
        want = 'reverify' if r.get('representative') and r.get('verify') else 'rebuild'
        if p[r['name']] != want:
            bad.append('shared file: %s %s, want %s' % (r['name'], p[r['name']], want))
    p = run('nexclash/engines.py')            # rebuild-only shared file: no re-verification anywhere
    if any(a != 'rebuild' for a in p.values()):
        bad.append('rebuild-only file (engines.py): %s' % {n: a for n, a in p.items() if a != 'rebuild'})
    if len(tid) < 2:
        bad.append('need two tid records to test a non-representative')
    p = run(verified_edit='nexclash/z80tonex.py')
    for r in recs:
        want = 'reverify' if r.get('representative') and r.get('verify') else 'skip'
        if p[r['name']] != want:
            bad.append('due re-verification after a rebuild stamp: %s %s, want %s' % (r['name'], p[r['name']], want))
    # the representative verified the shared file at its hash now and the others have rebuild stamps only: nothing is
    # due (a member's older verification is covered by a current one of the same file)
    rs = copy.deepcopy(recs)
    for r in rs:
        c = dict(base[r['name']])
        v = dict(c)
        if not (r.get('representative') and r.get('verify')) and 'nexclash/z80tonex.py' in v:
            v['nexclash/z80tonex.py'] = 'old'
        r['checked'], r['verified'] = {'deps': c}, {'deps': v}
    p = {r['name']: act for r, act, _ in plan(rs)[0]}
    if any(a != 'skip' for a in p.values()):
        bad.append('shared file the representative verified now: %s, want skip' % {n: a for n, a in p.items() if a != 'skip'})
    # coverage: an engine whose only verified member is not marked representative still replays a shared change
    lone = copy.deepcopy([r for r in recs if r['name'] == 'stormbringer'])
    for r in lone:
        r['representative'] = False
        c = dict(base[r['name']])
        c['nexclash/z80tonex.py'] = 'old'
        r['checked'], r['verified'] = {'deps': c}, {'deps': dict(c)}
    acts = [a for r, a, _ in plan(lone)[0]]
    if acts != ['reverify']:
        bad.append('shared change with no representative member reading it: %s, want reverify' % acts)
    # INCLUDE keys are repository paths with '/' whatever the platform writes (a Windows source's "lib\\x.asm")
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, 'asm', 'lib'))
        open(os.path.join(d, 'asm', 'g.asm'), 'w').write('        INCLUDE "lib\\y.asm"\n')
        open(os.path.join(d, 'asm', 'lib', 'y.asm'), 'w').write('        INCLUDE "z.inc"\n')
        open(os.path.join(d, 'asm', 'lib', 'z.inc'), 'w').write('')
        got = asm_includes('asm/g.asm', root=d)
        if got != {'asm/lib/y.asm', 'asm/lib/z.inc'}:
            bad.append('asm_includes: %s, want asm/lib/y.asm and asm/lib/z.inc' % sorted(got))
    # exclusion: a record marked "excluded" stays 'none' even when its own and shared files changed
    ex = copy.deepcopy(recs[0])
    ex['excluded'] = 'selfcheck'
    ex['checked'] = ex['verified'] = {'deps': {k: 'old' for k in base[ex['name']]}}
    acts = [a for r, a, _ in plan([ex])[0]]
    if acts != ['none']:
        bad.append('excluded record planned: %s' % acts)
    # recipe and ROM identity (PSEUDO): a stamped record whose recipe changes is due; prose and stamps are not recipe
    by = {r['name']: r for r in recs}

    def one(name, edit, want, env_rom=None, legacy=False):
        r = copy.deepcopy(by[name])
        keep = os.environ.get('NEXCLASH_NEXT_ROM')
        try:
            if env_rom is not None:
                os.environ['NEXCLASH_NEXT_ROM'] = env_rom
            now = state(r)
            if legacy:
                now = {k: v for k, v in now.items() if k not in PSEUDO}
            stamp(r, 'verified', now, 'selfcheck')
            edit(r)
            got = plan([r])[0][0][1]
        finally:
            if keep is None:
                os.environ.pop('NEXCLASH_NEXT_ROM', None)
            else:
                os.environ['NEXCLASH_NEXT_ROM'] = keep
        return got == want or bad.append('recipe: %s %s -> %s, want %s' % (name, edit.__doc__, got, want))

    def rework_arg(r):
        """a rework argument"""
        r['rework'][0]['args'].append('--allow-60hz')

    def pin(r):
        """the pin rom3 -> whole"""
        r['pin']['altrom_fill'] = 'whole'

    def waiver(r):
        """rom_paths_known removed"""
        r.pop('rom_paths_known', None)

    def input_md5(r):
        """a recording's MD5"""
        (r['inputs']['recordings'] or [r['inputs']['snapshot']])[0]['md5'] = '0' * 32

    def tape_md5(r):
        """a tape's MD5 (inputs.tapes)"""
        r['inputs']['tapes'][-1]['files'][0]['md5'] = '0' * 32

    def build_arg(r):
        """a rebuild argument"""
        r['rebuild'].setdefault('args', []).append('--quick')

    def output(r):
        """an expected output MD5"""
        next(iter(r['outputs'].values()))['md5'] = '0' * 32

    def prose(r):
        """a note and a status line (prose)"""
        r['verify']['note'] = 'changed'
        r.setdefault('status', {})['next'] = 'changed'

    def nothing(r):
        """no change"""
    one('jetpac', rework_arg, 'reverify')
    one('chuckie_egg', pin, 'reverify')
    one('knight_tyme', waiver, 'reverify')
    one('lunar_jetman', input_md5, 'reverify')
    for r in recs:                              # a tape-set game: its tapes are inputs like any other (rebuild = due)
        if r['inputs'].get('tapes'):
            one(r['name'], tape_md5, 'reverify' if r.get('verify') else 'rebuild')
            break
    one('commando', build_arg, 'reverify')
    one('smash_tv', output, 'reverify')
    one('midnight_resistance', prose, 'skip')
    one('commando', pin, 'skip', legacy=True)                  # a stamp before the digest: taken as it is
    rom = os.path.join(ROOT, 'docs', 'records', 'chuckie_egg.json')   # any file: a stand-in "ROM"
    one('chuckie_egg', lambda r: os.environ.__setitem__('NEXCLASH_NEXT_ROM', os.path.join(ROOT, 'README.md')),
        'reverify', env_rom=rom)                                # another ROM supplied
    one('chuckie_egg', lambda r: os.environ.pop('NEXCLASH_NEXT_ROM'), 'skip', env_rom=rom)   # none supplied now
    # Pillow's version: named by the stamps of the builds that import PIL, and by no other
    pil = next((r for r in recs if 'pillow' in deps(r)), None)
    if pil is None or all('pillow' in deps(r) for r in recs):
        bad.append('pillow: want some records with the entry and some without (got %s)' % ('none' if pil is None else 'all'))
    else:
        now = state(pil)
        if changed(dict(now, pillow='0'), now) != ['pillow']:
            bad.append('pillow: another version in the stamp is not reported')
        if changed({k: v for k, v in now.items() if k != 'pillow'}, now):
            bad.append('pillow: a stamp from before the entry is reported as changed')
        if 'pillow' in own(pil):
            bad.append('pillow: counted as the game\'s own file (it is shared: rebuild, representative re-verifies)')
    return bad


def stamp(rec, kind, now, date, extra=None):
    """Record a passed check ('checked') or verification ('verified', implies checked)."""
    s = {'deps': now, 'date': date}
    s.update(extra or {})
    rec['checked'] = dict(s)
    if kind == 'verified':
        rec['verified'] = dict(s)


# -------------------------------------------------------------------------------------- views

GEN_BEGIN = '<!-- generated from docs/records by `python -m nexclash.records views`: do not edit by hand -->'
GEN_END = '<!-- end generated -->'


def _replace_block(text, block, where):
    if GEN_BEGIN in text:
        a = text.index(GEN_BEGIN)
        b = text.index(GEN_END) + len(GEN_END)
        return text[:a] + block + text[b:]
    return text.replace(where, block, 1) if where in text else text + '\n' + block + '\n'


def view_status(recs):
    rows = ['| Game | Engine (file) | Sprite build | Software | Hardware | Next |', '|---|---|---|---|---|---|']
    for r in sorted(recs, key=lambda r: r.get('order', 999)):
        if not r.get('in_status', True):
            continue
        st = r.get('status', {})
        rows.append('| %s | %s | %s | %s | %s | %s |' % (
            st.get('title', r['game']), st.get('engine_col', '%s (%s)' % (r['engine'], r['doc'])), st.get('build', '-'),
            st.get('software', '-'), st.get('hardware', '-'), st.get('next', '-')))
    return GEN_BEGIN + '\n' + '\n'.join(rows) + '\n' + GEN_END


def view_checksums(recs):
    lines = ['Every game\'s verified outputs (`selftest.py` rebuilds them; the record says how):', '']
    for r in sorted(recs, key=lambda r: r.get('order', 999)):
        o = r.get('outputs', {})
        parts = ['`%s` %s' % (v['file'], v['md5']) for k, v in o.items()]
        parts += ['`%s --strategy %s` %s%s' % (x['file'], x['strategy'], x['md5'], ' (%s)' % x['note'] if x.get('note') else '')
                  for x in r.get('repro', [])]
        v = r.get('verified', {})
        lines.append('- %s (%s): %s; verified %s%s' % (
            r['game'], r['name'], ', '.join(parts), v.get('date', 'never'),
            '' if r.get('rebuild') else ' (no automated rebuild yet)'))
    return GEN_BEGIN + '\n' + '\n'.join(lines) + '\n' + GEN_END


def _proof(r):
    """How a record's outputs are proven: differential (replayed against a recording), not differential, or rebuild only."""
    v = r.get('verify')
    if not v:
        return 'rebuild only'
    return 'not differential' if v.get('differential') is False else 'differential'


def _releases(r):
    """(snapshot MD5, release) for a record and each of its reworks of the same snapshot (Jetpac v1.1, Atic Atac v1.3 /
    v1.4). A rework of another snapshot (a 128K release) is left out: listing it would make `patch` refuse that
    snapshot's default build where the rework needs options (Cauldron v1.1: --altrom-fill whole)."""
    snap = r['inputs']['snapshot']['md5']
    game = r['verified_json_game'] if r.get('verified_json_game') else r['game']
    yield snap, {'record': r['name'], 'game': game, 'doc': r['doc'],
                 'args': [x for x in r['rebuild'].get('args', []) if x != '--no-record'], 'proof': _proof(r),
                 'nex': {k: v['md5'] for k, v in r['outputs'].items()}}
    for x in r.get('rework', []):
        if x.get('snapshot') and next((i['md5'] for i in x.get('inputs', []) if i.get('name') == x['snapshot']), None) != snap:
            continue
        if not x.get('outputs'):
            continue
        v = {'record': '%s rework %s' % (r['name'], x['name']), 'game': game, 'doc': r['doc'],
             'args': [a for a in x.get('args', []) if a != '--no-record'], 'proof': _proof(x),
             'nex': {k: o['md5'] for k, o in x['outputs'].items()}, 'rework': True}
        if x.get('env'):
            v['env'] = dict(x['env'])
        yield snap, v


def view_verified(recs):
    """One entry per snapshot MD5 (the release `patch` builds by default, for its title) with every release of that
    snapshot under 'variants', reworks included: a frozen or alternate release shares the snapshot, and a single
    entry let it overwrite the default (Everyone's a Wally, Fireman OPUS / ASTRA, Rainbow / Rainbow Z80N). The
    default is a record's own build where there is one, a rework's only for a snapshot no record builds."""
    by = {}
    for r in recs:
        if r.get('verified_json', True) and r['inputs']['snapshot']['md5']:
            for m, v in _releases(r):
                by.setdefault(m, []).append(v)
    snaps = {}
    for m, vs in by.items():
        variants = sorted(vs, key=lambda v: v['record'])
        d = min(variants, key=lambda v: (bool(v.get('rework')), bool(v.get('env')), '--engine' in v['args'],
                                         len(v['game']), v['record']))
        snaps[m] = dict({k: d[k] for k in ('game', 'doc', 'nex', 'proof')}, variants=variants)
    return {'_note': 'GENERATED from docs/records by `python -m nexclash.records views` - do not edit. '
                     'Snapshots with a recorded build: nex = the MD5s `nexclash.py patch` reproduces for the default '
                     'release; variants = every release of that snapshot (args: how it is selected; proof: '
                     'differential = replayed against a recording, otherwise not).', 'snapshots': snaps}


def verified_selfcheck():
    """verified.json for the snapshots two releases share: both kept, the default the one built without --engine,
    and userflow.match_release taking each release's own outputs and refusing a sprite build neither made. -> failures"""
    from . import userflow
    snaps = view_verified(all_records())['snapshots']
    bad = []
    for default, other in (('everyones_a_wally_updated', 'wally'), ('rainbow_z80n', 'rainbow'),
                           ('incredible_shrinking_fireman-add-OPUS', 'incredible_shrinking_fireman-add-GPT6_ASTRA')):
        e = next((e for e in snaps.values() if {default, other} <= {v['record'] for v in e.get('variants', [])}), None)
        if e is None:
            bad.append('verified.json: %s and %s not under one snapshot' % (default, other))
            continue
        rel = {v['record']: v for v in e['variants']}
        if e['nex'] != rel[default]['nex']:
            bad.append('verified.json: the default of %s / %s is not %s' % (default, other, default))
        for name in (default, other):
            got = {k: rel[name]['nex'].get(k) for k in ('plain', 'sprites')}
            hit = userflow.match_release(e, got)
            if not hit or hit['record'] != name:
                bad.append('match_release: %s outputs matched %s' % (name, hit and hit['record']))
        if userflow.match_release(e, {'plain': rel[default]['nex'].get('plain'), 'sprites': 'f' * 32}):
            bad.append('match_release: a sprite build no release made was accepted (%s)' % default)
    jet = next((r for r in all_records() if r['name'] == 'jetpac'), None)     # a rework of the same snapshot (Codex review)
    if jet:
        x = next(x for x in jet['rework'] if x['name'] == 'v11')
        got = {k: x['outputs'][k]['md5'] for k in ('plain', 'sprites')}
        hit = userflow.match_release(snaps[jet['inputs']['snapshot']['md5']], got)
        if not hit or hit['record'] != 'jetpac rework v11':
            bad.append('match_release: Jetpac v1.1 (--altrom-fill whole) outputs matched %s' % (hit and hit['record']))
    with tempfile.TemporaryDirectory() as d:                                # userflow.output_paths: declared names
        if userflow.output_paths(d, 'g') != (os.path.join(d, 'g.nex'), os.path.join(d, 'g_sprites.nex')):
            bad.append('output_paths: NAME.nex / NAME_sprites.nex not the default')
        json.dump({'plain': 'g_plain-x.nex', 'default': 'g_sprites-x.nex'}, open(os.path.join(d, 'g_outputs.json'), 'w'))
        if userflow.output_paths(d, 'g') != (os.path.join(d, 'g_plain-x.nex'), os.path.join(d, 'g_sprites-x.nex')):
            bad.append('output_paths: NAME_outputs.json names not used (Fireman ASTRA)')
    return bad


def views(check=False):
    """Regenerate STATUS.md's table, VERIFICATION.md's checksum list and verified.json. check=True:
    write nothing, return the list of files that are out of date."""
    recs = all_records()
    stale = []
    targets = [
        (os.path.join(ROOT, 'STATUS.md'), lambda t: _replace_block(t, view_status(recs), '<!-- status table -->')),
        (os.path.join(ROOT, 'docs', 'VERIFICATION.md'),
         lambda t: _replace_block(t, view_checksums(recs), '<!-- checksum list -->')),
    ]
    for path, fn in targets:
        old = open(path).read()
        new = fn(old)
        if new != old:
            stale.append(os.path.relpath(path, ROOT))
            if not check:
                open(path, 'w').write(new)
    vp = os.path.join(ROOT, 'docs', 'profiles', 'verified.json')
    new = json.dumps(view_verified(recs), indent=1)
    if open(vp).read() != new:
        stale.append(os.path.relpath(vp, ROOT))
        if not check:
            open(vp, 'w').write(new)
    return stale


def main(argv):
    if argv[:1] == ['views']:
        st = views(check='--check' in argv)
        print(('out of date: ' if '--check' in argv else 'updated: ') + (', '.join(st) or 'nothing'))
        return 1 if st and '--check' in argv else 0
    if argv[:1] == ['deps'] and len(argv) > 1:
        r = load(argv[1])
        for p in deps(r):
            print(('own    ' if p in own(r) else 'shared ') + p)
        return 0
    if argv[:1] == ['evidence'] and len(argv) > 1:
        for c, e in evidence(load(argv[1])).items():
            print('%-12s %-13s %s' % (c, e['level'], e.get('scope', '')))
        return 0
    if argv[:1] == ['selfcheck']:
        bad = selfcheck()
        print('\n'.join(bad) or 'plan selfcheck OK')
        return 1 if bad else 0
    if argv[:1] == ['plan']:
        items, _ = plan(full='--full' in argv)
        for r, act, why in items:
            print('%-9s %-24s %s' % (act, r['name'], why))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

