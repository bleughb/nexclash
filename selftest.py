#!/usr/bin/env python3
"""nexclash self-test, driven by the evidence records (docs/records/<game>.json; nexclash/records.py).

    python selftest.py --smoke             Chuckie Egg rebuilt from its snapshot, MD5s: under a second.
                                           Game sessions run this after touching shared code.
    python selftest.py --affected          maintainers, per change: rebuild the games whose dependencies
                                           changed since their last check (MD5s); list the re-verifications
                                           now due (--verify runs them)
    python selftest.py                     release: rebuild EVERY game (MD5s) + run the due re-verifications
    python selftest.py --full              every game rebuilt AND re-verified against its recordings (~2.5 h)
    python selftest.py --game NAME [--verify]   one game
    python selftest.py --plan              what --affected would do, without running anything
    python selftest.py --tools             the analysis commands (inspect/scan/isr/cost) on Chuckie Egg,
                                           and records.plan() on synthetic stamps
  options: [FOLDER] (default $NEXCLASH_REFERENCE, ./reference, ../specnext/reference), --stamp (write the
  passed results into the records: 'checked' after a rebuild, 'verified' after a re-verification),
  --jobs N (games in parallel), --human (also verify against the extra recordings a record lists).

Rebuild = the record's recipe: snapshot (+ the recordings it names) + the stored build decisions, no
analysis, no verification - seconds per game. Re-verify = the record's verify recipe: auto recording or
the reference recordings, differential verification, simulated boot, the old-strategy builds (repro).
Which games need which is plan() in nexclash/records.py: own files changed -> re-verify that game;
shared files changed -> rebuild everything that depends on them + re-verify one representative per
engine. Exit 0 = all good; 1 = a failure; 2 = no failure but games skipped (reference files missing).
"""
import concurrent.futures
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nexclash import records as R   # noqa: E402

NEXCLASH = os.path.join(HERE, 'nexclash.py')


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def reference_dir(pos):
    return pos[0] if pos else next((d for d in (os.environ.get('NEXCLASH_REFERENCE'), os.path.join(HERE, 'reference'),
                                                os.path.join(HERE, '..', 'specnext', 'reference')) if d and os.path.isdir(d)), '')


def stage(rec, src, work):
    """Copy the record's inputs from the reference folder under their canonical names; MD5-checked.
    -> (dir, None) or (None, why)."""
    d = os.path.join(work, rec['name'])
    os.makedirs(d, exist_ok=True)
    for it in [rec['inputs']['snapshot']] + rec['inputs']['recordings']:
        p = os.path.join(src, it.get('path', ''))
        if not it.get('path') or not os.path.isfile(p):
            return None, 'missing %s' % (it.get('path') or it['name'])
        if it.get('md5') and md5(p) != it['md5']:
            return None, '%s md5 %s, record says %s' % (it['path'], md5(p), it['md5'])
        shutil.copy(p, os.path.join(d, it['name']))
    return d, None


def _run(cmd):
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _report(out, name):
    p = os.path.join(out, name + '_report.txt')
    return open(p).read() if os.path.exists(p) else ''


def _snapname(rec):
    return os.path.splitext(rec['inputs']['snapshot']['name'])[0]


def _check_outputs(rec, out, lines, want=None, stage_='rebuild'):
    bad = 0
    for k, o in (want or rec['outputs']).items():
        p = os.path.join(out, o['file'])
        got = md5(p) if os.path.exists(p) else None
        ok = got == o['md5']
        bad += not ok
        lines.append('%-4s %s %s %s%s%s' % ('OK' if ok else 'FAIL', rec['name'], stage_, o['file'],
                                            ' --strategy %s' % o['strategy'] if o.get('strategy') else '',
                                            '' if ok else ' (got %s)' % got))
    return bad


def _boot_ok(rep, lines, label):
    if 'Boot      :' in rep and 'MISMATCH' in rep.split('Boot      :', 1)[1].split('\n', 1)[0]:
        lines.append('FAIL %s simulated boot' % label)
        return 1
    return 0


def checks(rec, lines):
    """Per-game quick checks of the game's own source files (run with every rebuild)."""
    bad = 0
    for c in rec.get('checks', []):
        if c.startswith('asm2profile:'):
            prof = c.split(':', 1)[1]
            r = subprocess.run([sys.executable, os.path.join(HERE, 'tools', 'asm2profile.py'), '--check', prof],
                               capture_output=True, text=True)
            ok = r.returncode == 0
            lines.append('%-4s %s hook profile %s = pinned sjasmplus output of its .asm%s' % (
                'OK' if ok else 'FAIL', rec['name'], prof, '' if ok else ' (%s)' % (r.stdout + r.stderr).strip()[-200:]))
        elif c == 'dizzy5_asm':
            ok, info = dizzy5_asm()
            lines.append('%-4s %s asm/dizzy5_hooks.asm (pinned sjasmplus) = dizzy5.hook_code()%s' % (
                'OK' if ok else 'FAIL', rec['name'], '' if ok else ' (%s)' % info))
        else:
            ok = False
            lines.append('FAIL %s unknown check %r' % (rec['name'], c))
        bad += not ok
    return bad


def dizzy5_asm():
    """asm/dizzy5_hooks.asm has no profile hooks section (dizzy5.py emits the bytes itself): the pinned
    sjasmplus must produce exactly what dizzy5.hook_code() emits for the Dizzy V profile."""
    try:
        sys.path.insert(0, os.path.join(HERE, 'tools', 'sjasmplus'))
        import sjasm
        from nexclash import dizzy5
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sjasm.find(), '--zxnext', '--msg=war', os.path.join(HERE, 'asm', 'dizzy5_hooks.asm')],
                               cwd=tmp, capture_output=True, text=True)
            got = open(os.path.join(tmp, 'dizzy5_hooks.bin'), 'rb').read() if not r.returncode else b''
        prof = json.load(open(os.path.join(HERE, 'docs', 'profiles', 'dizzy5_spellbound_dizzy.json')))
        code = dizzy5.hook_code(prof)
        code = bytes(code[0] if isinstance(code, tuple) else code)
        return got == code, (r.stdout + r.stderr)[-200:] or (len(got), len(code))
    except Exception as e:                      # noqa: BLE001
        return False, e


def rebuild(rec, d, lines):
    """The record's rebuild recipe -> outputs (+ repro builds) compared with the verified MD5s."""
    rb = rec['rebuild']
    z80 = os.path.join(d, rec['inputs']['snapshot']['name'])
    out = os.path.join(d, 'rebuild')
    os.makedirs(out, exist_ok=True)
    bad = checks(rec, lines)
    if rb.get('cmd') == 'convert':
        o = next(iter(rec['outputs'].values()))['file']
        _run([sys.executable, NEXCLASH, 'convert', z80, '-o', os.path.join(out, o)] + rb.get('args', []))
        return bad + _check_outputs(rec, out, lines)
    cmd = [sys.executable, NEXCLASH, 'auto', z80, '--no-record'] + rb.get('args', [])
    cmd = [c for i, c in enumerate(cmd) if c != '--no-record' or i == cmd.index('--no-record')]
    for r in rb.get('rzx', []):
        cmd += ['--rzx', os.path.join(d, r)]
    if rb.get('decisions'):
        dp = os.path.join(d, rec['name'] + '_decisions.json')
        json.dump(rb['decisions'], open(dp, 'w'))
        cmd += ['--decisions', dp]
    _run(cmd + ['-o', out])
    rep = _report(out, _snapname(rec))
    bad += _check_outputs(rec, out, lines) + _boot_ok(rep, lines, rec['name'])
    for x in rec.get('repro', []):
        ro = os.path.join(d, 'rebuild_' + x['strategy'])
        _run(cmd + ['-o', ro, '--strategy', x['strategy']])
        bad += _check_outputs(rec, ro, lines, {'repro': x}) + _boot_ok(_report(ro, _snapname(rec)), lines, rec['name'])
    return bad


def _verify_report(rep, label, lines, rec=None):
    if not rep or 'FAILED' in rep or 'MISMATCH' in rep:
        lines.append('FAIL %s verification' % label)
        return 1
    n = rep.count('PASSED')
    boot = 'OK' if 'Boot      : simulated' in rep or 'boot OK' in rep else 'not simulated'
    if n == 0 and rec and rec['verify'].get('differential') is False:
        lines.append('OK   %s analysis + boot %s (no differential verification: %s)' % (label, boot, rec['verify']['note']))
        return 0
    if n == 0:
        lines.append('FAIL %s verification: nothing PASSED (record says it is verified differentially)' % label)
        return 1
    lines.append('OK   %s verification (%d PASSED, boot %s)' % (label, n, boot))
    return 0


def reverify(rec, d, lines, human=False):
    """The record's verify recipe: full analysis + differential verification (+ repro builds verified
    from the same recording). Also checks the build decisions it derives equal the stored ones."""
    v = rec['verify']
    z80 = os.path.join(d, rec['inputs']['snapshot']['name'])
    out = os.path.join(d, 'verify')
    cmd = [sys.executable, NEXCLASH, 'auto', z80] + v.get('args', [])
    rz = list(v.get('rzx', [])) + (list(v.get('human_rzx', [])) if human else [])
    for r in rz:
        cmd += ['--rzx', os.path.join(d, r)]
    _run(cmd + ['-o', out])
    name = _snapname(rec)
    bad = _check_outputs(rec, out, lines, stage_='verify') + _verify_report(_report(out, name), rec['name'], lines, rec)
    dec_p = os.path.join(out, name + '_decisions.json')
    stored = (rec.get('rebuild') or {}).get('decisions')
    if stored is not None:
        got = json.load(open(dec_p)) if os.path.exists(dec_p) else None
        ok = got == stored
        bad += not ok
        lines.append('%-4s %s build decisions = stored%s' % ('OK' if ok else 'FAIL', rec['name'], '' if ok else ' (got %s)' % got))
    auto = os.path.join(out, name + '_auto.rzx')
    if v.get('auto_rzx_md5') and os.path.exists(auto) and md5(auto) != v['auto_rzx_md5']:
        lines.append('NOTE %s auto recording %s differs from the recorded one %s (recorder or explorer changed)'
                     % (rec['name'], md5(auto), v['auto_rzx_md5']))
    for x in rec.get('repro', []):
        ro = os.path.join(d, 'verify_' + x['strategy'])
        rcmd = [sys.executable, NEXCLASH, 'auto', z80, '--no-record', '--strategy', x['strategy'], '-o', ro]
        for r in ([auto] if os.path.exists(auto) else []) + [os.path.join(d, r) for r in rz]:
            rcmd += ['--rzx', r]
        _run(rcmd)
        bad += _check_outputs(rec, ro, lines, {'repro': x}, 'verify')
        bad += _verify_report(_report(ro, name), '%s --strategy %s' % (rec['name'], x['strategy']), lines)
    return bad


def run_one(rec, action, src, work, human):
    """-> (record, action, failures, lines, skipped-why)"""
    lines = []
    d, why = stage(rec, src, work)
    if d is None:
        return rec, action, 0, lines, why
    bad = rebuild(rec, d, lines)
    if action == 'reverify' and rec.get('verify'):
        bad += reverify(rec, d, lines, human)
    else:
        action = 'rebuild'                      # no verify recipe: only a rebuild was proven
    return rec, action, bad, lines, None


def tools_check(src):
    """The shared analysis commands (inspect / scan / isr / cost) against known Chuckie Egg facts
    (~1 min). Returns the number of failures. A session that improves a command keeps these passing
    and adds a check for what it added (one easy game is enough: the commands are game-independent)."""
    from nexclash import snapinfo, memscan, isrinfo, drawcost
    bad = R.selfcheck()
    print('%-4s tools: records plan() on synthetic stamps%s' % ('OK' if not bad else 'FAIL', '' if not bad else ' (%s)' % bad[:3]))
    rec = R.load('chuckie_egg')
    work = tempfile.mkdtemp(prefix='nexclash_tools_')
    d, why = stage(rec, src, work)
    if d is None:
        print('tools: Chuckie Egg reference not found (%s), nothing checked' % why)
        return 1
    ez, er = os.path.join(d, 'chuckie_egg.z80'), os.path.join(d, 'chuckie_egg.rzx')
    checks_ = []

    def ok(name, cond, info=''):
        checks_.append(cond)
        print('%-4s tools: %s%s' % ('OK' if cond else 'FAIL', name, '' if cond else ' (%s)' % str(info)[:200]))
    old = sys.stderr
    sys.stderr = io.StringIO()                  # SkoolKit's SZX warnings
    try:
        facts, warn = snapinfo.inspect(ez)
        txt = '\n'.join(v for k, v in facts)
        ok('inspect: 48K, IM 2, no loader warning', '48K' in txt and 'IM 2' in txt and not warn, (txt, warn))
        _, r = isrinfo.isr(ez, [er], stop=150)
        ok('isr: handler 40092, no IX/IY reads', 40092 in r['entries'] and not any(r['reads_entry'].values()), r)
        _, r = memscan.scan(ez, [er], ranges=['0x5B00-0x5BFF', '0x4000-0x57FF'], stop=300)
        ok('scan RZX (300 frames): printer buffer 0x5B00-0x5BFF untouched, screen written',
           memscan.touched_count(r, '0x5B00-0x5BFF') == 0 and memscan.touched_count(r, '0x4000-0x57FF') > 0, r['ranges'])
        _, r = drawcost.cost(ez, 39500, [er], stop=1500)
        ok('cost plotter 39500 (1500 frames): 1402 calls, median 19535 T',
           r['calls'] == 1402 and r['median'] == 19535, r)
    finally:
        sys.stderr = old
    shutil.rmtree(work, ignore_errors=True)
    return checks_.count(False) + len(bad)


def smoke(src):
    """--smoke: rebuild the simplest game (Chuckie Egg, stateless alt-ROM hooks) from its snapshot alone
    and compare both .nex MD5s - seconds, catches any shared-code change that alters a build."""
    rec = R.load('chuckie_egg')
    work = tempfile.mkdtemp(prefix='nexclash_smoke_')
    d, why = stage(rec, src, work)
    if d is None:
        sys.exit('SMOKE: %s under %s' % (why, src))
    lines = []
    bad = rebuild(dict(rec, checks=[]), d, lines)
    print('\n'.join(lines))
    print('SMOKE %s' % ('PASSED' if not bad else 'FAILED'))
    shutil.rmtree(work, ignore_errors=True)
    sys.exit(1 if bad else 0)


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else default


def main():
    vals = {_arg(x) for x in ('--game', '--jobs')}
    pos = [x for x in sys.argv[1:] if not x.startswith('--') and x not in vals]
    src = reference_dir(pos)
    flags = set(x for x in sys.argv[1:] if x.startswith('--'))
    if '--plan' in flags:
        items, _ = R.plan(full='--full' in flags)
        for r, act, why in items:
            print('%-9s %-24s %s' % (act, r['name'], why))
        return 0
    if not os.path.isdir(src):
        sys.exit(__doc__)
    if '--smoke' in flags:
        smoke(src)
    if '--tools' in flags:
        bad = tools_check(src)
        print('TOOLS %s' % ('PASSED' if not bad else 'FAILED'))
        return 1 if bad else 0
    items, now_all = R.plan(full='--full' in flags)
    game = _arg('--game')
    if game:
        items = [(r, 'reverify' if '--verify' in flags else 'rebuild', 'requested') for r, _, _ in items if r['name'] == game]
        if not items:
            sys.exit('no record docs/records/%s.json' % game)
    elif '--affected' in flags:
        due = [(r, why) for r, act, why in items if act == 'reverify']
        if '--verify' not in flags:
            items = [(r, 'rebuild' if act == 'reverify' else act, why) for r, act, why in items]
            for r, why in due:
                print('DUE  re-verify %s: %s (--verify runs it)' % (r['name'], why))
        items = [x for x in items if x[1] not in ('skip',)]
    else:                                       # release: every game at least rebuilt
        items = [(r, 'rebuild' if act == 'skip' else act, why) for r, act, why in items]
    todo = [x for x in items if x[1] in ('rebuild', 'reverify')]
    for r, act, why in items:
        if act == 'none':
            print('--   %s: %s' % (r['name'], why))
    work = tempfile.mkdtemp(prefix='nexclash_selftest_')
    fails, skipped, passed = 0, [], []
    human = '--human' in flags
    jobs = int(_arg('--jobs', '1'))
    print('plan: %s' % (', '.join('%s %s' % (act, r['name']) for r, act, _ in todo) or 'nothing to do'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(run_one, r, act, src, work, human) for r, act, _ in todo]
        for f in concurrent.futures.as_completed(futs):
            rec, act, bad, lines, why = f.result()
            if why:
                skipped.append('%s (%s)' % (rec['name'], why))
                continue
            print('\n'.join(lines), flush=True)
            fails += bad
            if not bad:
                passed.append((rec, act))
    if '--stamp' not in flags:                 # --stamp regenerates them below
        stale = R.views(check=True)
        for s in stale:
            print('FAIL %s is out of date: run `python -m nexclash.records views`' % s)
        fails += len(stale)
    if '--stamp' in flags:
        today = datetime.date.today().isoformat()
        for rec, act in passed:
            r = R.load(rec['name'])
            R.stamp(r, 'verified' if act == 'reverify' else 'checked', now_all[rec['name']], today)
            R.save(r)
        print('stamped: %s' % ', '.join('%s (%s)' % (r['name'], 'verified' if a == 'reverify' else 'checked')
                                        for r, a in passed) or 'nothing')
        R.views()
    if skipped:
        print('SKIPPED: %s' % '; '.join(skipped))
    res = 'FAILED: %d problem(s)' % fails if fails else 'PASSED' if not skipped else \
        'PASSED for the games run (%d skipped)' % len(skipped)
    print('SELFTEST %s (%s)' % (res, work))
    return 1 if fails else 2 if skipped else 0


if __name__ == '__main__':
    sys.exit(main())
