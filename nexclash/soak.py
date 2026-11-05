"""`python -m nexclash.soak BUILD.nex --original GAME.z80 [--profile P.json] [--minutes 15]` - freeze soak.

Plays the build and the original (the control) in headless JNext for N emulated minutes with the same
varied input: the profile's start keys, then random holds of its direction / fire / jump keys and its
restart keys every few hundred frames (a generic profile when none is given: any game, little play).
Saves a picture every --shot frames and the PC every 10 frames, and per second the interrupts, AY and port
0xFE writes and hook time (NR 7).

Reports, for each run:
- STATIC: the picture did not change for --static seconds (20) while the input changed. Matched against
  the original: a picture the original also showed still (a menu or message waiting for a key the profile
  never pressed) is a wait; one it never showed is a FREEZE.
- LOOP: every PC sample for --static seconds inside one 64-byte span that is not one of the profile's
  waits and not a span the original sat in (a tight loop outside known waits), picture or not.
- the run ending early or JNext errors (a crash).
Each finding keeps the last pictures before it (soak/<run>/finding_N/). The result block (soak/RESULT.txt)
is what a proof record quotes; sheet.png shows both runs once a minute (look at it: did the input reach
play?). Warns, never refuses. Origin: pilot leonis_triage soak (23 games, 2026-11-04). docs/CHECKS.md.
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
from . import jnext as J

SPAN = 64


def script(prog, prof, frames, seed, orig, d, shot):
    off = J.start_frame(prog)
    s = J.Script(off)
    s.start_line(prog)
    s.start_keys(prof, orig)
    s.frame_input(J.schedule(prof, frames, seed, orig))
    s.rule(J.counters())
    s.rule('on frame when FRAME %% 50 == 0 do\n  log "CNT F=${FRAME} %s"\nend\n' % J.CNT)
    s.rule('on frame when FRAME % 10 == 0 do\n  log "PC F=${FRAME} PC=${PC} IFF=${IFF1}"\nend\n')
    for f in range(0, frames + 1, shot):
        s.at(f, '  screenshot "%s/f%06d.png"\n' % (d, f))
    s.exit_at(frames)
    return s.text()


def pictures(d):
    out = []
    for p in sorted(glob.glob(os.path.join(d, 'f*.png'))):
        out.append((int(os.path.basename(p)[1:-4]), hashlib.md5(open(p, 'rb').read()).hexdigest(), p))
    return out


def static_runs(pics, minlen):
    runs, i = [], 0
    while i < len(pics):
        j = i
        while j + 1 < len(pics) and pics[j + 1][1] == pics[i][1]:
            j += 1
        if pics[j][0] - pics[i][0] >= minlen:
            runs.append((pics[i][0], pics[j][0], pics[i][1]))
        i = j + 1
    return runs


def loop_spans(pcs, minlen, waits=()):
    """Windows of >= minlen frames whose PC samples all lie in one SPAN-byte span: [(f0, f1, lo, hi)]."""
    out, i, fr = [], 0, sorted(pcs)
    while i < len(fr):
        lo = hi = pcs[fr[i]]
        j = i
        while j + 1 < len(fr):
            v = pcs[fr[j + 1]]
            if max(hi, v) - min(lo, v) >= SPAN:
                break
            lo, hi, j = min(lo, v), max(hi, v), j + 1
        if fr[j] - fr[i] >= minlen and not any(a <= lo and hi <= b for a, b in waits):
            out.append((fr[i], fr[j], lo, hi))
        i = j + 1
    return out


def inputs_in(sched, a, b):
    return sum(1 for t, _, _ in sched if a <= t <= b)


def analyse(d, prog, sched, frames, minlen, waits=(), off=0):
    log = os.path.join(d, 'run.log')
    rec = J.records(log, ('PC', 'CNT', 'START'))
    pcs = {r['F'] - off: r['PC'] for t, r in rec if t == 'PC' and r['F'] >= off}
    cnt = [r for t, r in rec if t == 'CNT' and r['F'] >= off]
    pics = pictures(d)
    st = [(a, b, h) for a, b, h in static_runs(pics, minlen) if inputs_in(sched, a, b) >= 2]
    lp = loop_spans(pcs, minlen, waits)
    last = max(pcs) if pcs else 0
    return dict(pics=pics, static=st, loops=lp, pcs=pcs, cnt=cnt, last=last, errors=J.errors(log),
                warn=J.check_start(log, prog), ended=last >= frames - 20, distinct=len({h for _, h, _ in pics}))


def keep(d, frame, pics, n=4, tag='finding'):
    """Copy the last n pictures up to frame into d/<tag>_<frame>/."""
    k = os.path.join(d, '%s_%06d' % (tag, frame))
    os.makedirs(k, exist_ok=True)
    for f, _, p in [x for x in pics if x[0] <= frame][-n:]:
        shutil.copy(p, k)
    return k


def pcspan(pcs, a, b):
    v = [p for f, p in pcs.items() if a <= f <= b]
    return '0x%04X-0x%04X (%d PCs)' % (min(v), max(v), len(set(v))) if v else 'no PC samples'


def rates(cnt, frames_from=500):
    c = [r for r in cnt]
    if len(c) < 3:
        return {}
    a, b = c[min(len(c) - 2, frames_from // 50)], c[-1]
    n = (b['F'] - a['F']) / 50.0
    return {k: (b[k] - a[k]) / n for k in ('INT', 'AY', 'BP')} if n > 0 else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('build', help='the build (.nex)')
    ap.add_argument('--original', help='the control: the original .z80 (or the plain .nex)')
    ap.add_argument('--profile', help='input profile JSON (nexclash/jnext.py; default generic)')
    ap.add_argument('--minutes', type=float, default=15.0, help='emulated minutes per run (default 15)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--shot', type=int, default=25, help='a picture every N frames (default 25)')
    ap.add_argument('--static', type=float, default=20.0, help='seconds of a still picture or a tight loop (20)')
    ap.add_argument('--card', help='NextZXOS SD card image (default $NEXCLASH_JNEXT_CARD)')
    ap.add_argument('--jnext-home', help='HOME for JNext (default OUT/.jnext_home)')
    ap.add_argument('-o', '--out', default='soak', help='output folder (default ./soak)')
    ap.add_argument('--keep', action='store_true', help='keep every picture (default: findings + sheet only)')
    a = ap.parse_args(argv)
    prof = J.load_profile(a.profile)
    frames = int(a.minutes * 3000)
    minlen = int(a.static * 50)
    card = J.card(a.card)
    runs = [('build', a.build, False)] + ([('original', a.original, True)] if a.original else [])
    jobs, scheds = [], {}
    for tag, prog, orig in runs:
        d = os.path.abspath(os.path.join(a.out, tag))
        os.makedirs(d, exist_ok=True)
        for x in glob.glob(os.path.join(d, 'f*.png')):
            os.remove(x)
        scheds[tag] = J.schedule(prof, frames, a.seed, orig)
        jobs.append((prog, script(prog, prof, frames, a.seed, orig, d, a.shot), d, frames, card, a.jnext_home))
    rcs = J.run_all(jobs)
    waits = [tuple(J.num(x) for x in w.split('-')) for w in prof.get('waits', [])]
    res = {}
    for (tag, prog, orig), rc in zip(runs, rcs):
        d = os.path.abspath(os.path.join(a.out, tag))
        res[tag] = analyse(d, prog, scheds[tag], frames, minlen, waits, J.start_frame(prog))
        res[tag]['rc'] = rc
    ctl = res.get('original')
    if ctl:                                       # spans the original sat in are known waits for the build
        known = [(lo, hi) for _, _, lo, hi in ctl['loops']] + waits
        res['build']['loops'] = loop_spans(res['build']['pcs'], minlen, known)
    ctl_still = {h for a_, b_, h in ctl['static']} if ctl else set()
    lines = ['SOAK  %s (%s) %s, %.1f emulated min each, seed %d, profile %s' % (
        os.path.basename(a.build), J.md5(a.build)[:8],
        'vs %s (%s)' % (os.path.basename(a.original), J.md5(a.original)[:8]) if a.original else 'no control',
        a.minutes, a.seed, prof.get('name'))]
    freezes = 0
    for tag, prog, orig in runs:
        r = res[tag]
        d = os.path.abspath(os.path.join(a.out, tag))
        fz, waitl = [], []
        for f0, f1, h in r['static']:
            k = keep(d, f1, r['pics'])
            item = '%d-%d (%.0f s, PC %s, %s)' % (f0, f1, (f1 - f0) / 50, pcspan(r['pcs'], f0, f1), os.path.relpath(k, a.out))
            (waitl if tag == 'original' or h in ctl_still else fz).append(item)
        lp = ['%d-%d PC 0x%04X-0x%04X (%s)' % (f0, f1, lo, hi, os.path.relpath(keep(d, f1, r['pics'], tag='loop'), a.out))
              for f0, f1, lo, hi in r['loops']] if tag == 'build' else []
        crash = []
        if any('SCRIPT' in e for e in r['errors']):
            lines.append('%-9s: NOT RUN (the check script failed: %s)' % (tag, r['errors'][0]))
            freezes += tag == 'build'
            continue
        if r['rc'] not in (0,):
            crash.append('JNext exit %s' % r['rc'])
        if not r['ended']:
            crash.append('the run ended at frame %d of %d' % (r['last'], frames))
        crash += r['errors']
        if tag == 'build':
            freezes += len(fz) + len(lp) + len(crash)
        rt = rates(r['cnt'])
        lines.append('%-9s: %s; %d distinct pictures of %d; per s: interrupts %.1f, AY writes %.0f, port FE writes %.0f' % (
            tag, ('%d FREEZE(S)' % len(fz)) if fz else 'no freeze', r['distinct'], len(r['pics']),
            rt.get('INT', 0), rt.get('AY', 0), rt.get('BP', 0)))
        for x in fz:
            lines.append('  FREEZE (still picture the original never showed still): %s' % x)
        for x in waitl:
            lines.append('  still, %s: %s' % ('a wait in the original' if tag == 'original' else 'the original waits on this picture too', x))
        for x in lp:
            lines.append('  LOOP (PC in one %d-byte span, not a known wait): %s' % (SPAN, x))
        for x in crash:
            lines.append('  CRASH? %s' % x)
        if r['warn']:
            lines.append('  ' + r['warn'])
    lines.append('RESULT: %s (warns only)' % ('%d finding(s) in the build' % freezes if freezes else 'no freeze, loop or crash in the build'))
    shots = []
    for f in range(0, frames + 1, 3000):
        for tag, _, _ in runs:
            shots.append(os.path.join(os.path.abspath(a.out), tag, 'f%06d.png' % f))
    J.contact(shots, os.path.join(a.out, 'sheet.png'), cols=2 * len(runs) if len(runs) > 1 else 6)
    lines.append('sheet: %s (both runs once a minute: check the input reached play)' % os.path.join(a.out, 'sheet.png'))
    J.result_block(lines, os.path.join(a.out, 'RESULT.txt'))
    json.dump({t: {k: v for k, v in r.items() if k in ('static', 'loops', 'distinct', 'rc', 'last', 'errors')}
               for t, r in res.items()}, open(os.path.join(a.out, 'soak.json'), 'w'), indent=1)
    if not a.keep:
        for tag, _, _ in runs:
            for p in glob.glob(os.path.join(a.out, tag, 'f*.png')):
                os.remove(p)
    return 0


def selfcheck():
    """Synthetic: the still-picture and tight-loop detectors."""
    bad = []
    pics = [(f, 'a' if f < 1000 else 'b' if f < 2200 else 'c%d' % f, '') for f in range(0, 3000, 25)]
    st = static_runs(pics, 1000)
    if st != [(1000, 2175, 'b')]:
        bad.append(('static', st))
    pcs = {f: (0x8000 + f % 7 if 500 <= f < 1600 else 0x9000 + (f * 37) % 4000) for f in range(0, 3000, 10)}
    lp = loop_spans(pcs, 1000)
    if [(x[0], x[1]) for x in lp] != [(500, 1590)]:
        bad.append(('loop', lp))
    if loop_spans(pcs, 1000, [(0x8000, 0x8010)]):
        bad.append('loop: a known wait still reported')
    sched = [(1100, ['q'], 5), (1500, ['p'], 5)]
    if inputs_in(sched, 1000, 2175) != 2:
        bad.append('inputs')
    return bad


if __name__ == '__main__':
    raise SystemExit(main())
