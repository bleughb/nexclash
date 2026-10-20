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
                  the reference folder; maintainers fill it)
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
import sys

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

def _module_imports(path):
    """nexclash modules a module imports (relative, `from nexclash`, `import nexclash.x`, or the bare
    name when nexclash/ is on sys.path), including imports inside functions and __import__('x')."""
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
    return {x for x in names if os.path.exists(os.path.join(PKG, x + '.py'))}


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
    pseudo-entry 'skoolkit' (its version)."""
    files = set(ALWAYS) | {'nexclash/%s.py' % m for m in closure(rec['modules'])} | set(rec.get('data', [])) \
        | set(rec.get('shared_data', []))
    return sorted(files) + ['skoolkit']


def own(rec):
    """The game's own files: its engine modules and data (a change -> re-verify this game)."""
    return {'nexclash/%s.py' % m for m in rec.get('own_modules', [])} | set(rec.get('data', []))


def _skoolkit_version():
    try:
        from importlib.metadata import version
        return version('skoolkit')
    except Exception:                       # noqa: BLE001
        return 'unknown'


def hashes(paths, root=ROOT):
    out = {}
    for p in paths:
        if p == 'skoolkit':
            out[p] = _skoolkit_version()
        else:
            f = os.path.join(root, p)
            out[p] = hashlib.sha256(open(f, 'rb').read()).hexdigest()[:16] if os.path.exists(f) else 'missing'
    return out


def changed(stamp, now):
    """Paths whose hash differs between a stamp {path: hash} and now (added / removed count)."""
    keys = set(stamp or {}) | set(now)
    return sorted(k for k in keys if (stamp or {}).get(k) != now.get(k))


def plan(recs=None, full=False):
    """-> list of (record, action, reason): action 'skip' | 'rebuild' | 'reverify' | 'none' (no
    automated rebuild for this game yet)."""
    recs = recs if recs is not None else all_records()
    out = []
    shared_hit = {}                             # engine -> shared files changed since a verification
    now_all = {}
    for r in recs:
        now = hashes(deps(r))
        now_all[r['name']] = now
        ch_checked = changed(r.get('checked', {}).get('deps'), now)
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
    return [tuple(x) for x in out], now_all


def selfcheck():
    """plan() on synthetic stamps (no reference files needed): an unchanged tree skips everything; an
    engine file re-verifies its game only; a shared file rebuilds every dependent and re-verifies
    only the representative; a re-verification left due survives a rebuild-only stamp; an excluded
    record is never planned. -> failures"""
    import copy
    recs = [r for r in all_records() if r.get('rebuild') and not r.get('excluded')]
    base = {r['name']: hashes(deps(r)) for r in recs}

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
    # exclusion: a record marked "excluded" stays 'none' even when its own and shared files changed
    ex = copy.deepcopy(recs[0])
    ex['excluded'] = 'selfcheck'
    ex['checked'] = ex['verified'] = {'deps': {k: 'old' for k in base[ex['name']]}}
    acts = [a for r, a, _ in plan([ex])[0]]
    if acts != ['none']:
        bad.append('excluded record planned: %s' % acts)
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


def view_verified(recs):
    snaps = {}
    for r in recs:
        if r.get('verified_json', True) and r['inputs']['snapshot']['md5']:
            snaps[r['inputs']['snapshot']['md5']] = {
                'game': r['verified_json_game'] if r.get('verified_json_game') else r['game'], 'doc': r['doc'],
                'nex': {k: v['md5'] for k, v in r['outputs'].items()}}
    return {'_note': 'GENERATED from docs/records by `python -m nexclash.records views` - do not edit. '
                     'Snapshots whose sprite build was differentially verified against a recording. nex = MD5s '
                     '`nexclash.py patch` reproduces.', 'snapshots': snaps}


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

