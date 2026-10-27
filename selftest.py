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
    python selftest.py --canary            two-stage tool-chain check (Dean, 2026-10-13): stage 1 = the
                                           record marked "canary": 1 (Chuckie Egg) rebuilt, MD5s, seconds;
                                           if it fails, stage 2 = "canary": 2 (Midnight Resistance) rebuilt
                                           + quick differential verify (~2 min) to tell a broken tool chain
                                           from a game-specific fault. Every selftest run that FAILS a game
                                           runs stage 2 too and says which it is.
  options: [FOLDER] (default $NEXCLASH_REFERENCE, ./reference, ../specnext/reference), --stamp (write the
  passed results into the records: 'checked' after a rebuild, 'verified' after a re-verification),
  --jobs N (games in parallel), --human (also verify against the extra recordings a record lists).

Rebuild = the record's recipe: snapshot (+ the recordings it names) + the stored build decisions, no
analysis, no verification - seconds per game. Re-verify = the record's verify recipe: auto recording or
the reference recordings, differential verification, simulated boot, the old-strategy builds (repro).
Which games need which is plan() in nexclash/records.py: own files changed -> re-verify that game;
shared files changed -> rebuild everything that depends on them + re-verify one representative per
engine. Exit 0 = all good; 1 = a failure; 2 = no failure but games skipped (reference files missing).

WITHOUT PUSH ACCESS to the nexclash repo (contributors, other users; Dean 2026-10-21) only ONE game
other than your own is ever run: --canary stage 1 (Chuckie Egg rebuilt, MD5s; stage 2 is a maintainer
diagnosis and is skipped). Allowed: --canary, --smoke, --tools, --plan, and --game NAME [--verify]
[--stamp] for a record that is NOT on origin/main yet (your own new game). Everything else - --affected,
--full, a release run, --game for an existing game - stops with exit 3: the maintainers run those.
Push access = `git push --dry-run` to origin succeeds (checked once, ~1-2 s; no git checkout, e.g.
the release zip = no push access). Offline maintainers: NEXCLASH_MAINTAINER=1 skips the check.
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
    bad += recolour_guard(rec, out, lines, cmd, d)
    for x in rec.get('repro', []):
        ro = os.path.join(d, 'rebuild_' + x['strategy'])
        _run(cmd + ['-o', ro, '--strategy', x['strategy']])
        bad += _check_outputs(rec, ro, lines, {'repro': x}) + _boot_ok(_report(ro, _snapname(rec)), lines, rec['name'])
    return bad


def recolour_guard(rec, out, lines, cmd, d):
    """Engines with recolour (nexclash/recolour.py guard): the game built again with an empty colour
    map; recolour must turn each build into the other byte for byte, so it never drifts from the builder."""
    from nexclash import recolour as rc
    from nexclash import coloursheet as cs
    mod = rc.engines().get(rec['name'])
    if not mod:
        return 0
    o = rec['outputs'][mod.RECOLOUR['output']]['file']
    bo = os.path.join(d, 'rebuild_nocolours')
    os.makedirs(bo, exist_ok=True)
    empty = os.path.join(d, 'empty_colours.json')
    cs.save({}, empty, 'selftest: empty colour map')
    subprocess.run(cmd + ['-o', bo], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   env=dict(os.environ, NEXCLASH_COLOURS=empty))
    p, pb = os.path.join(out, o), os.path.join(bo, o)
    if not (os.path.exists(p) and os.path.exists(pb)):
        lines.append('FAIL %s recolour: %s not built %s' % (rec['name'], o, 'with an empty map' if os.path.exists(p)
                                                                 else 'with its map'))
        return 1
    ok, info = rc.guard(open(p, 'rb').read(), open(pb, 'rb').read(), mod)
    lines.append('%-4s %s recolour %s: %s' % ('OK' if ok else 'FAIL', rec['name'], o, info))
    return 0 if ok else 1


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


def smoke_rzx_census(ez, er, ok):
    import rzx_census                           # probe (tools/probes/README.md): C-simulator PC census
    r = rzx_census.census(er, [40092, 43909], stop=300)
    ok('probe rzx_census (300 frames): ISR 40092 x299 from frame 0, 43909 x141017 (= scan --writers)',
       r['frames'] == 300 and not r['desync'] and r['pcs'][40092]['count'] == 299 and
       r['pcs'][40092]['first'] == 0 and r['pcs'][43909]['count'] == 141017, r)


# Every tools/probes/<name>.py -> its smoke test on Chuckie Egg (ez, er, ok), run by tools_check;
# learncheck fails a probe that is missing here or names no function (GPT6 review, 2026-10-27).
PROBE_SMOKE = {'rzx_census.py': smoke_rzx_census}


def tools_check(src):
    """The shared analysis commands (inspect / scan / isr / cost / preview / survey) against known Chuckie Egg facts
    (~1 min). Returns the number of failures. A session that improves a command keeps these passing
    and adds a check for what it added (one easy game is enough: the commands are game-independent)."""
    from nexclash import snapinfo, memscan, isrinfo, drawcost
    bad = R.selfcheck()
    print('%-4s tools: records plan() on synthetic stamps%s' % ('OK' if not bad else 'FAIL', '' if not bad else ' (%s)' % bad[:3]))
    global _PUSH
    keep, _PUSH = _PUSH, False                  # the no-push-access gate (Dean 2026-10-21)
    try:
        g = [contributor_gate(f, n) is None for f, n in (
            ({'--affected'}, None), (set(), None), ({'--full'}, None), ({'--game', '--verify'}, 'chuckie_egg'),
            ({'--canary', '--affected'}, None), ({'--canary'}, None), ({'--tools'}, None), ({'--plan'}, None),
            ({'--game', '--verify', '--stamp'}, 'no_such_record_selftest'))]
    finally:
        _PUSH = keep
    gate_ok = g == [False] * 5 + [True] * 4
    print('%-4s tools: no-push-access gate (refuses other games, allows --canary / own new game)' % ('OK' if gate_ok else 'FAIL'))
    bad = list(bad) + ([] if gate_ok else ['contributor_gate'])
    cbad = coloursheet_check()
    from nexclash import recolour as rc
    rbad = rc.selfcheck()
    print('%-4s tools: recolour .nex offsets / splice / refusals on a synthetic .nex%s' % (
        'OK' if not rbad else 'FAIL', '' if not rbad else ' (%s)' % rbad))
    cbad += len(rbad)
    from nexclash import z80n
    zbad = z80n.selfcheck()
    print('%-4s tools: z80n - every Z80N instruction against worked results (core 3.02.05 / guide r3)%s' % (
        'OK' if not zbad else 'FAIL', '' if not zbad else ' (%s)' % zbad[:3]))
    cbad += len(zbad)
    rec = R.load('chuckie_egg')
    work = tempfile.mkdtemp(prefix='nexclash_tools_')
    d, why = stage(rec, src, work)
    if d is None:
        print('tools: Chuckie Egg reference not found (%s), nothing checked' % why)
        return 1 + cbad
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
        ok('isr: slots touched 0 r, 3 r, 4 x, 5 r, 7 rw (slot 2 free for a hook page)',
           r['slots'] == {0: 'r', 3: 'r', 4: 'x', 5: 'r', 7: 'rw'}, r['slots'])
        _, r = memscan.scan(ez, [er], ranges=['0x5B00-0x5BFF', '0x4000-0x57FF'], stop=300)
        ok('scan RZX (300 frames): printer buffer 0x5B00-0x5BFF untouched, screen written',
           memscan.touched_count(r, '0x5B00-0x5BFF') == 0 and memscan.touched_count(r, '0x4000-0x57FF') > 0, r['ranges'])
        _, r = memscan.scan(ez, [er], ranges=['0x4000-0x57FF'], stop=300, writers=True)
        w = r['ranges']['0x4000-0x57FF']
        ok('scan --writers (300 frames): screen writers 43909 x141017, 43916 x42204, 42409, 40068; 3 readers',
           w['writers'].get(43909) == 141017 and w['writers'].get(43916) == 42204 and
           set(w['writers']) == {43909, 43916, 42409, 40068} and len(w['readers']) == 3, w)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools', 'probes'))
        for name in sorted(PROBE_SMOKE):        # every kept probe's smoke test (learncheck checks the registry)
            PROBE_SMOKE[name](ez, er, ok)
        sp = memscan.rest_spans({100: 5, 104: 1, 120: 2, 200: 9}, {200})
        ok('scan --writers: writers outside the top 10 joined into routine spans (100-104 x6, 120 x2)',
           [s[:3] for s in sp] == [(100, 104, 6), (120, 120, 2)], sp)
        from nexclash import preview
        pv = os.path.join(work, 'preview.png')
        _, r = preview.preview(ez, [er], pv, at=[400, 800], plots=[39500])
        g = r['groups']
        ok('preview: 2 shots, plotter 39500 in 4 caller groups (40385: 184 calls, 8832 bytes)',
           r['shots'] == [400, 800] and len(g) == 4 and g.get((39500, 40385), {}).get('calls') == 184 and
           g[(39500, 40385)]['bytes'] == 8832 and os.path.getsize(pv) > 1000, g)
        _, r = drawcost.cost(ez, 39500, [er], stop=1500)
        ok('cost plotter 39500 (1500 frames): 1402 calls, median 19535 T',
           r['calls'] == 1402 and r['median'] == 19535, r)
        from nexclash import survey
        _, r = survey.survey(ez, [er], os.path.join(work, 'survey'), stop=600, log=lambda m: None)
        rt = {x['routine']: x for x in r['routines']}
        ok('survey (600 frames): engine chuckie, plain boot OK, 43899 x1059 calls on top, 40000 x814 from 6 callers at 665 T',
           r['engine'] == 'chuckie' and r['plain']['boot'].startswith('OK') and r['routines'][0]['routine'] == 43899 and
           rt[43899]['calls'] == 1059 and rt.get(40000, {}).get('calls') == 814 and
           len(rt[40000]['callers_seen']) == 6 and rt[40000]['T_median'] == 665, r['routines'][:2])
    finally:
        sys.stderr = old
    shutil.rmtree(work, ignore_errors=True)
    return checks_.count(False) + len(bad) + cbad


def coloursheet_check():
    """nexclash/coloursheet.py on synthetic parts (no game data): a two-part figure drawn normally
    and mirrored is ONE composite, 1:1 sheet with the 8x8 swatches, read-back of one painted pixel,
    a painted clear pixel ignored, a resized sheet refused."""
    from nexclash import coloursheet as cs
    from PIL import Image
    work = tempfile.mkdtemp(prefix='nexclash_sheet_')
    pal = cs.palette_rgb([0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F,
                          0xFC, 0xFF])

    def part(pid, x, y, mir, w=8, h=4):
        px = [(c, r, '%s%d' % (pid, r), c, 1 if (c + r) % 3 else 0, 12 if (c + r) % 3 else 0)
              for r in range(h) for c in range(w)]
        return dict(id=pid, size=h, w=w, h=h, x=x, y=y, mir=mir, group='Fig', pixels=px,
                    entries={'%s%d' % (pid, r): [r, 1] for r in range(h)})
    col = cs.Collector()
    col.add_frame([part('B', 40, 10, 0), part('L', 40, 14, 0), part('K', 90, 10, 0)])
    # same role twice (two overlapping explosions): two figures, not one
    col2 = cs.Collector()
    col2.add_frame([dict(part('E', 10, 10, 0), role=1), dict(part('F', 12, 11, 0), role=1)])
    col2.add_frame([dict(part('W', 10, 60, 0), role=2, repeat=True), dict(part('W', 18, 60, 0), role=2, repeat=True)])
    col.add_frame([part('B', 70, 20, 1), part('L', 70, 24, 1)])
    comps = col.composites(['Fig'])
    png, lay = os.path.join(work, 's.png'), os.path.join(work, 's_layout.json')
    cs.write(comps, png, lay, pal)
    img = Image.open(png).convert('RGB')
    L = json.load(open(lay))
    res = []
    res.append(('2 figures (body + legs joined, mirrored copy the same one), 1:1', len(comps) == 2 and
                sorted(len(c['parts']) for c in comps) == [1, 2] and comps[0]['count'] + comps[1]['count'] == 3))
    res.append(('same role again -> two figures; a repeating role (wheels) -> one',
                sorted(len(c['parts']) for c in col2.comps.values()) == [1, 1, 2]))
    res.append(('8x8 swatches 1-15 in palette order', all(img.getpixel((1 + (i - 1) * 10 + 7, 8)) == pal[i]
                                                          for i in range(1, 16))))
    c0 = [c for c in L['composites'] if len(c['parts']) == 2][0]
    img.putpixel((c0['x'] + 1, c0['y']), pal[10])           # body line 0, column 1: ink -> red
    img.putpixel((c0['x'], c0['y']), pal[10])               # column 0 line 0: clear -> ignored
    img.save(png)
    ent, rep = cs.read(png, lay)
    res.append(('read-back: 1 key, bit 1 = 10, clear pixel ignored', ent == {'B0': [0, 1, [0, 10, 0, 0, 0, 0, 0, 0]]}
                and rep['painted transparent pixels (ignored)'] == 1))
    res.append(('read-back: no copy-spread reported for a figure shown once',
                not any(k.startswith('pixels left unpainted') for k in rep)))
    # painting sheet (unique): a figure sharing graphics shows only its new pixels; an untouched
    # sheet drawn with a map reads back to that same map; a repaint edits only what changed
    col3 = cs.Collector()
    col3.add_frame([part('B', 40, 10, 0), part('L', 40, 14, 0)])
    col3.add_frame([part('B', 70, 10, 0), part('M', 70, 14, 0)])
    pp, pl = os.path.join(work, 'p.png'), os.path.join(work, 'p_layout.json')
    cmap = {'B0': [0, 1, [0, 10, 0, 0, 0, 0, 0, 0]]}
    cs.write(col3.composites(['Fig']), pp, pl, pal, cmap, unique=True)
    P = json.load(open(pl))
    res.append(('painting sheet: shared body once (2 figures, the second only its new legs)',
                len(P['composites']) == 2 and sorted(c['h'] for c in P['composites']) == [4, 8]))
    e2, _ = cs.read(pp, pl)
    res.append(('painting sheet: untouched -> the same map', e2 == cmap))
    im2 = Image.open(pp).convert('RGB')
    c1 = [c for c in P['composites'] if c['h'] == 8][0]
    im2.putpixel((c1['x'] + 1, c1['y']), pal[13])             # repaint the painted pixel: 10 -> 13
    im2.save(pp)
    e3, _ = cs.read(pp, pl)
    res.append(('painting sheet: repaint edits only that pixel', e3 == {'B0': [0, 1, [0, 13, 0, 0, 0, 0, 0, 0]]}))
    im2.putpixel((c1['x'] + 1, c1['y']), pal[12])             # back to its default (12): entry gone
    im2.save(pp)
    e4, _ = cs.read(pp, pl)
    res.append(('painting sheet: painted back to the default -> no entry', e4 == {}))
    # transparent painting (opt-in, Dizzy 1): grey on an opaque pixel
    im2.putpixel((c1['x'] + 2, c1['y']), cs.TRANSP_RGB)         # B0 bit 2 -> transparent
    im2.save(pp)
    e5, r5 = cs.read(pp, pl)
    res.append(('grey on an opaque pixel without clear=True: kept default', e5 == {} and
                r5['opaque pixels painted grey (kept default)'] == 1))
    e6, r6 = cs.read(pp, pl, clear=True)
    res.append(('clear=True: grey -> transparent mask bit', e6 == {'B0': [0, 1, [0] * 8, 0x20]} and
                r6['pixels painted transparent'] == 1))
    cf = os.path.join(work, 'c.json')
    cs.save(e6, cf, 'test')
    res.append(('clear mask survives save / load', cs.load(cf) == e6))
    cs.write(col3.composites(['Fig']), pp, pl, pal, e6, unique=True)
    e7, _ = cs.read(pp, pl, clear=True)
    im3 = Image.open(pp).convert('RGB')
    res.append(('sheet drawn with the mask: that pixel grey, re-read -> the same map',
                im3.getpixel((c1['x'] + 2, c1['y'])) == cs.TRANSP_RGB and e7 == e6))
    im3.putpixel((c1['x'] + 2, c1['y']), pal[12])               # painted back to its default
    im3.save(pp)
    e8, _ = cs.read(pp, pl, clear=True)
    res.append(('transparent pixel painted back to its default -> no entry', e8 == {}))
    # outlines (paint_clear, Dizzy 1 2026-10-14): clear pixels inside the box are paintable
    qp, ql = os.path.join(work, 'q.png'), os.path.join(work, 'q_layout.json')
    cs.write(col3.composites(['Fig']), pp, pl, pal, unique=True)
    cs.write(col3.composites(['Fig']), qp, ql, pal, unique=True, paint_clear=True)
    Q = json.load(open(ql))
    a_, b_ = Image.open(pp).convert('RGB'), Image.open(qp).convert('RGB')
    q1 = [c for c in Q['composites'] if c['h'] == 8][0]
    res.append(('paint_clear: same boxes, layout marked', Q.get('paint_clear') is True and
                [(c['x'], c['y'], c['w'], c['h']) for c in Q['composites']] ==
                [(c['x'], c['y'], c['w'], c['h']) for c in json.load(open(pl))['composites']]))
    # only paintable pixels are grey: B0 bit 0 is clear -> background without paint_clear, grey with
    # it; the PNGs differ exactly at the clear pixels; an untouched sheet reports no ignored paint
    allpx = [(x, y) for y in range(a_.size[1]) for x in range(a_.size[0])]
    diff = [q for q in allpx if a_.getpixel(q) != b_.getpixel(q)]
    res.append(('paintable only: clear pixel background without paint_clear, grey with it; PNGs '
                'differ only there', a_.getpixel((q1['x'], q1['y'])) == cs.BG_RGB and
                b_.getpixel((q1['x'], q1['y'])) == cs.TRANSP_RGB and diff and
                all(a_.getpixel(q) == cs.BG_RGB and b_.getpixel(q) == cs.TRANSP_RGB for q in diff)))
    _, ra = cs.read(pp, pl, clear=True)
    res.append(('paintable only: untouched sheet -> no ignored paint (background is not paint)',
                not any('ignored' in k for k in ra)))
    b_.putpixel((q1['x'], q1['y']), pal[8])                      # B0 bit 0 (clear) -> black outline
    b_.save(qp)
    e9, r9 = cs.read(qp, ql, clear=True)
    res.append(('paint_clear: a clear pixel painted -> its nibble', e9 == {'B0': [0, 1, [8, 0, 0, 0, 0, 0, 0, 0]]}
                and r9['clear pixels painted opaque (outline)'] == 1 and not any('ignored' in k for k in r9)))
    cs.write(col3.composites(['Fig']), qp, ql, pal, e9, unique=True, paint_clear=True)
    e10, _ = cs.read(qp, ql, clear=True)
    b2 = Image.open(qp).convert('RGB')
    res.append(('paint_clear: sheet drawn with it shows it, re-read -> the same map',
                b2.getpixel((q1['x'], q1['y'])) == pal[8] and e10 == e9))
    b2.putpixel((q1['x'], q1['y']), cs.TRANSP_RGB)               # grey again: transparent, entry gone
    b2.save(qp)
    e11, r11 = cs.read(qp, ql, clear=True)
    res.append(('paint_clear: painted grey again -> no entry', e11 == {} and
                r11['painted clear pixels set back to transparent'] == 1))
    img.resize((img.size[0] * 2, img.size[1] * 2)).save(png)
    try:
        cs.read(png, lay)
        res.append(('resized sheet refused', False))
    except ValueError:
        res.append(('resized sheet refused', True))
    # recolour bundle (GPT6 review 2026-10-27): changes against the sheet's map, three-way merge on
    # pixel states, redraw from the layout, two copies of one pixel painted differently
    m = {}
    cs.set_state(m, 'B0', 1, ('C', 10), [0, 1])
    cs.set_state(m, 'B0', 2, 'T', [0, 1])
    res.append(('set_state: colour + transparent', m == {'B0': [0, 1, [0, 10, 0, 0, 0, 0, 0, 0], 0x20]}))
    cs.set_state(m, 'B0', 1, 'D', [0, 1])
    cs.set_state(m, 'B0', 2, 'D', [0, 1])
    res.append(('set_state: back to default removes the override (entry gone)', m == {}))
    base = {'B0': [0, 1, [0, 10, 0, 0, 0, 0, 0, 0]], 'B1': [1, 1, [3, 0, 0, 0, 0, 0, 0, 0]]}
    cur = {'B0': [0, 1, [0, 10, 0, 0, 0, 0, 0, 0]], 'B1': [1, 1, [5, 0, 0, 0, 0, 0, 0, 0]],
           'B2': [2, 1, [0, 0, 7, 0, 0, 0, 0, 0]]}
    meta = {'B0': [0, 1], 'B1': [1, 1], 'B2': [2, 1], 'B3': [3, 1]}
    mg, mc = cs.merge(base, {('B0', 1): 'D', ('B3', 0): 'T'}, meta, cur)
    res.append(('merge: user reset + transparent applied, newer current entries kept',
                not mc and mg == {'B1': cur['B1'], 'B2': cur['B2'], 'B3': [3, 1, [0] * 8, 0x80]}))
    mg, mc = cs.merge(base, {('B1', 0): ('C', 9)}, meta, cur)
    res.append(('merge: changed on the sheet AND since -> conflict, nothing applied',
                len(mc) == 1 and mc[0][1:] == (('C', 3), ('C', 9), ('C', 5)) and mg == cur))
    mg, mc = cs.merge(base, {('B1', 0): ('C', 5)}, meta, cur)
    res.append(('merge: the same change on both sides -> no conflict', not mc and mg == cur))
    rp, rl = os.path.join(work, 'r.png'), os.path.join(work, 'r_layout.json')
    cs.write(col3.composites(['Fig']), rp, rl, pal, base, unique=False)       # body B shown in 2 figures
    rp2, rl2 = os.path.join(work, 'r2.png'), os.path.join(work, 'r2_layout.json')
    cs.redraw(rl, base, rp2, rl2)
    res.append(('redraw from the layout with its own map = the written sheet, same layout',
                list(Image.open(rp).getdata()) == list(Image.open(rp2).getdata()) and
                json.load(open(rl)) == json.load(open(rl2))))
    R_ = json.load(open(rl))
    figs = [c for c in R_['composites'] if any(p['id'] == 'B' for p in c['parts'])]
    imr = Image.open(rp).convert('RGB')
    for c, colr in zip(figs, (pal[4], pal[6])):
        imr.putpixel((c['x'] + 1, c['y']), colr)                # B0 bit 1 (ink) in both figures
    imr.save(rp)
    _, ch, _, cf_, _ = cs.changes(rp, rl)
    res.append(('changes: one pixel painted two ways in two figures -> conflict', len(figs) == 2 and
                len(cf_) == 1 and cf_[0][0] == ('B0', 1) and ('B0', 1) not in ch))
    imr.putpixel((figs[1]['x'] + 1, figs[1]['y']), pal[4])
    imr.save(rp)
    _, ch, _, cf_, _ = cs.changes(rp, rl)
    res.append(('changes: painted the same in both copies -> one change', not cf_ and ch == {('B0', 1): ('C', 4)}))
    cs.redraw(rl, cs.merge(base, ch, {'B0': [0, 1]}, base)[0], rp2, rl2)
    _, ch2, _, _, _ = cs.changes(rp2, rl2)
    res.append(('redrawn with the merged map, read back -> no changes', ch2 == {}))
    shutil.rmtree(work, ignore_errors=True)
    for name, cond in res:
        print('%-4s tools: coloursheet: %s' % ('OK' if cond else 'FAIL', name))
    return sum(1 for _, cond in res if not cond)


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


def _canary_rec(stage_):
    return next((r for r in R.all_records() if r.get('canary') == stage_), None)


def canary2(src):
    """Stage 2: the canary-2 game (128K, alt ROM, interrupts on, paged hook RAM, pattern cache) rebuilt
    (MD5s) and verified differentially against the first `canary_quick` frames of its recording.
    -> (failures, lines); failures None if the references are missing."""
    rec = _canary_rec(2)
    lines = []
    if rec is None:
        return None, ['canary 2: no record marked "canary": 2']
    work = tempfile.mkdtemp(prefix='nexclash_canary2_')
    d, why = stage(rec, src, work)
    if d is None:
        return None, ['canary 2 (%s): %s' % (rec['name'], why)]
    bad = rebuild(rec, d, lines)
    v = rec['verify']
    out = os.path.join(d, 'canary')
    cmd = [sys.executable, NEXCLASH, 'auto', os.path.join(d, rec['inputs']['snapshot']['name'])] + \
        v.get('args', []) + ['--quick', str(rec.get('canary_quick', 300)), '-o', out]
    for r in v.get('rzx', []):
        cmd += ['--rzx', os.path.join(d, r)]
    _run(cmd)
    bad += _verify_report(_report(out, _snapname(rec)), '%s quick (%d frames)' % (rec['name'], rec.get('canary_quick', 300)),
                          lines, rec)
    shutil.rmtree(work, ignore_errors=True)
    return bad, lines


def canary(src):
    """--canary: stage 1 (seconds); stage 2 only when stage 1 fails."""
    rec = _canary_rec(1)
    work = tempfile.mkdtemp(prefix='nexclash_canary1_')
    d, why = stage(rec, src, work)
    if d is None:
        sys.exit('CANARY 1 (%s): %s under %s' % (rec['name'], why, src))
    lines = []
    bad = rebuild(dict(rec, checks=[]), d, lines)
    shutil.rmtree(work, ignore_errors=True)
    print('\n'.join(lines))
    if not bad:
        print('CANARY PASSED (stage 1: %s)' % rec['name'])
        return 0
    if not push_access():
        print('CANARY FAILED (stage 1: %s). Stage 2 (tool chain vs game) is a maintainer check: report '
              'this failure in your contribution note.' % rec['name'])
        return 1
    print('CANARY stage 1 FAILED (%s) - running stage 2' % rec['name'])
    b2, l2 = canary2(src)
    print('\n'.join(l2))
    if b2 is None:
        print('CANARY FAILED: stage 2 could not run - treat the tool chain as broken')
    elif b2:
        print('CANARY FAILED: stage 2 failed too - the TOOL CHAIN is broken (fix it before any game work)')
    else:
        print('CANARY: stage 2 PASSED - the tool chain works; the stage-1 fault is specific to %s' % rec['name'])
    return 1


def diagnose(src, failed):
    """After a selftest run with failures: stage 2 tells a broken tool chain from game faults."""
    if not push_access():
        print('DIAGNOSE: skipped (canary stage 2 is a maintainer check; no push access)')
        return
    print('DIAGNOSE: %d problem(s) in %s - running canary stage 2' % (len(failed), ', '.join(sorted(failed))))
    b2, l2 = canary2(src)
    print('\n'.join(l2))
    if b2 is None:
        print('DIAGNOSE: canary stage 2 could not run - cause unknown')
    elif b2:
        print('DIAGNOSE: canary stage 2 FAILED - the TOOL CHAIN is broken; fix it first')
    else:
        print('DIAGNOSE: canary stage 2 PASSED - the tool chain works; the failures are specific to those games')


_PUSH = None


def push_access():
    """True when this checkout can push to its origin (the maintainers). Cached."""
    global _PUSH
    if _PUSH is None:
        if os.environ.get('NEXCLASH_MAINTAINER') == '1':
            _PUSH = True
        elif not os.path.isdir(os.path.join(HERE, '.git')):
            _PUSH = False
        else:
            try:
                r = subprocess.run(['git', 'push', '--dry-run', '--porcelain', 'origin',
                                    'HEAD:refs/heads/selftest-push-probe'], cwd=HERE,
                                   capture_output=True, text=True, timeout=30)
                _PUSH = r.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                _PUSH = False
    return _PUSH


def record_is_new(name):
    """True when docs/records/<name>.json is not on origin/main (or in the release MANIFEST): the
    caller's own new game."""
    rel = 'docs/records/%s.json' % name
    man = os.path.join(HERE, 'MANIFEST.json')
    if os.path.exists(man):
        return rel not in json.load(open(man)).get('files', {})
    r = subprocess.run(['git', 'cat-file', '-e', 'origin/main:' + rel], cwd=HERE, capture_output=True)
    return r.returncode != 0


def contributor_gate(flags, game):
    """None when the run is allowed, else the reason it is not (no push access)."""
    if flags & {'--plan', '--canary', '--smoke', '--tools'} and not flags & {'--affected', '--full'}:
        return None
    if game and record_is_new(game) and not flags & {'--affected', '--full'}:
        return None
    if push_access():
        return None
    what = ('--game %s (a game already in the repo)' % game) if game else \
        ' '.join(sorted(flags & {'--affected', '--full', '--verify', '--stamp'})) or 'a release run (every game)'
    return ('selftest: %s needs push access to the nexclash repo - it rebuilds or re-verifies OTHER games, '
            'which the maintainers do before merging. Without push access run only:\n'
            '  python selftest.py --canary                   (one other game: Chuckie Egg, MD5s)\n'
            '  python selftest.py --game <your new record> --verify\n'
            'and say in your contribution note that shared code changed (CONTRIBUTING.md).' % what)


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else default


def main():
    vals = {_arg(x) for x in ('--game', '--jobs')}
    pos = [x for x in sys.argv[1:] if not x.startswith('--') and x not in vals]
    src = reference_dir(pos)
    flags = set(x for x in sys.argv[1:] if x.startswith('--'))
    known = {'--plan', '--full', '--smoke', '--canary', '--tools', '--game', '--affected', '--verify',
             '--stamp', '--jobs', '--human'}
    if '-h' in sys.argv[1:] or flags - known:   # an unknown flag used to start a release run
        print(__doc__)
        bad = sorted(flags - known - {'--help'})
        return 2 if bad else 0
    if '--plan' in flags:
        items, _ = R.plan(full='--full' in flags)
        for r, act, why in items:
            print('%-9s %-24s %s' % (act, r['name'], why))
        return 0
    gate = contributor_gate(flags, _arg('--game'))
    if gate:
        print(gate)
        return 3
    if not os.path.isdir(src):
        sys.exit(__doc__)
    if '--smoke' in flags:
        smoke(src)
    if '--canary' in flags:
        return canary(src)
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
    fails, skipped, passed, failed = 0, [], [], []
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
            if bad:
                failed.append(rec['name'])
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
    if failed and not (len(failed) == 1 and failed[0] == (_canary_rec(2) or {}).get('name')):
        diagnose(src, failed)
    if skipped:
        print('SKIPPED: %s' % '; '.join(skipped))
    res = 'FAILED: %d problem(s)' % fails if fails else 'PASSED' if not skipped else \
        'PASSED for the games run (%d skipped)' % len(skipped)
    print('SELFTEST %s (%s)' % (res, work))
    return 1 if fails else 2 if skipped else 0


if __name__ == '__main__':
    sys.exit(main())
