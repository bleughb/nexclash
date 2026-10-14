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
    cbad = coloursheet_check()
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
    img.resize((img.size[0] * 2, img.size[1] * 2)).save(png)
    try:
        cs.read(png, lay)
        res.append(('resized sheet refused', False))
    except ValueError:
        res.append(('resized sheet refused', True))
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
    print('DIAGNOSE: %d problem(s) in %s - running canary stage 2' % (len(failed), ', '.join(sorted(failed))))
    b2, l2 = canary2(src)
    print('\n'.join(l2))
    if b2 is None:
        print('DIAGNOSE: canary stage 2 could not run - cause unknown')
    elif b2:
        print('DIAGNOSE: canary stage 2 FAILED - the TOOL CHAIN is broken; fix it first')
    else:
        print('DIAGNOSE: canary stage 2 PASSED - the tool chain works; the failures are specific to those games')


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
