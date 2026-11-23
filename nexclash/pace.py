"""`python -m nexclash.pace BUILD.nex --original ORIG [--probe ADDR] [--profile P.json] [--updates 600]` - penalty meter.

Runs the original and the build in headless JNext with the SAME input KEYED TO GAME UPDATES: a game update
is one execution of the probe address (a routine the game runs once per update: its main loop's head, the
blit). After the start keys, every random hold starts and ends at an update count, so the two runs reach
the same game state at the same update whatever their pace, and the time between two updates is the cost
of the same game work (pilot three_weeks pace, 2026-11-04). No probe: an automatic main-loop detector
plays the original once with JNext's profiler, counts the candidates exactly in a second pass, and takes
the commonest once-per-update count's lowest address (say which; a per-game probe is better).

Measured per run: master cycles per update (pace), per second AY data writes (music tempo), port 0xFE
writes, interrupts taken, hook time from NR 7 (cycles with the CPU speed non-zero: every engine switches to
28 MHz on hook entry; hooks at 3.5 MHz read 0), the share of time with interrupts held off (IFF1 sampled on
20 lines a frame) and the longest gap between two interrupts taken (a held-off music interrupt). Phases: windows of --window updates, sorted by the ORIGINAL's time per update:
quiet = the fastest third, busy = the slowest third. Penalty = build time / original time - 1 over the same
updates. With the profile's `state` addresses the runs are checked to be in lockstep at every update;
the penalty is computed only up to the first difference. With its `reach` addresses (some of `state`: position,
score) a run in which none of them changes is "not measured: keys did not reach play". A probe hit under 20,000 T
after the one before, with an interrupt taken between, is warned of as a JNext duplicate.

Prints the table (pace/RESULT.txt, the lines a proof record quotes) and writes pace/pace.json. Warns when
the penalty is beyond +-limit % (2: slower, or faster than the original's pace) or interrupts are held off
over 5 ms longer than in the original; never refuses. docs/CHECKS.md.
"""
import argparse
import collections
import json
import os
from . import jnext as J

MHZ28 = 28e6                      # JNext's CYCLE: the 28 MHz master clock (8 per T at 3.5 MHz)
DI_LINES = tuple(range(0, 311, 16))
DUP_T = 20000                     # T: a second probe hit closer than this around an interrupt is suspect (Booty's guard)


def script(prog, prof, probe, updates, seed, orig, max_frames, state=(), candidates=None, frames=None):
    s = J.Script(J.start_frame(prog))
    s.var('u')
    s.start_line(prog)
    s.start_keys(prof, orig, when='u == 0')
    s.rule(J.counters(DI_LINES if candidates is None else ()))
    if candidates is not None:                # detector pass 2: exact counts after play_from
        p0 = prof.get('play_from_orig', prof.get('play_from', 0)) if orig else prof.get('play_from', 0)
        s.frame_input(J.schedule(prof, frames, seed, orig))
        for i, a in enumerate(candidates):
            s.var('c%d' % i)
            s.rule('on execute %d when FRAME >= %d do\n  set c%d = c%d + 1\nend\n' % (a, p0 + s.off, i, i))
        s.at(frames, ''.join('  log "CC A=%d N=${c%d}"\n' % (a, i) for i, a in enumerate(candidates)))
        s.exit_at(frames)
        return s.text()
    st = ''.join(' S%d=${mem[%d]}' % (i, a) for i, a in enumerate(state))
    s.rule('on execute %d do\n  set u = u + 1\n  log "U u=${u} F=${FRAME} C=${CYCLE} %s%s"\nend\n' % (probe, J.CNT, st))
    s.update_input(J.schedule(prof, updates, seed, orig, unit='update'), probe)
    s.rule('on frame when FRAME %% 50 == 0 do\n  log "CNT F=${FRAME} C=${CYCLE} U=${u} %s"\n  set mg = 0\nend\n' % J.CNT)
    s.rule('on execute %d when u == %d do\n  exit 0\nend\n' % (probe, updates + 1))
    s.exit_at(max_frames)
    return s.text()


def detect(orig, prof, card, home, work, seed, frames=3000, build=None):
    """Automatic main-loop detector -> (address, note)."""
    d = os.path.join(work, 'detect_profile')
    sc = J.Script(J.start_frame(orig))
    sc.start_keys(prof, True)
    sc.frame_input(J.schedule(prof, frames, seed, True))
    sc.exit_at(frames)
    p = J.launch(orig, sc.text(), d, frames, card, home, ['--profile', '--profile-output', 'prof.dat'])
    p.wait()
    tot = collections.Counter()
    for ln in open(os.path.join(d, 'prof.dat')):
        f = ln.split()
        if len(f) == 3:
            tot[int(f[1], 16)] += int(f[2])
    span = frames - prof.get('play_from_orig', prof.get('play_from', 0))
    cand = sorted(a for a, t in tot.items() if 0x4000 <= a < 0xC000 and 4 * span // 25 <= t <= 23 * span)
    if len(cand) > 400:                       # keep it cheap (each rule slows JNext): an even sample
        cand = cand[::len(cand) // 400 + 1]
    counts = {}
    for tag, prog, o in (('orig', orig, True),) + ((('build', build, False),) if build else ()):
        dd = os.path.join(work, 'detect_' + tag)
        J.launch(prog, script(prog, prof, None, 0, seed, o, 0, candidates=cand, frames=frames), dd, frames,
                 card, home).wait()
        counts[tag] = {r['A']: r['N'] for t, r in J.records(os.path.join(dd, 'run.log'), ('CC',))}
    co = counts['orig']
    ok = {a: n for a, n in co.items() if span / 25 <= n <= span and (not build or counts['build'].get(a, 0) > 0)}
    if not ok:
        return None, 'no candidate executed between 2 and 50 times a second in play'
    mode, k = collections.Counter(ok.values()).most_common(1)[0]
    a = min(x for x, n in ok.items() if n == mode)
    return a, 'automatic: 0x%04X, %d executions in %d frames of play (%.1f/s), shared by %d candidate addresses' % (
        a, mode, span, mode * 50.0 / span, k)


def load(d):
    rec = J.records(os.path.join(d, 'run.log'), ('U', 'CNT'))
    return J.unwrap([r for t, r in rec if t == 'U']), J.unwrap([r for t, r in rec if t == 'CNT'])


def windows(uo, ub, w, upto):
    """[(u0, u1, original cycles, build cycles, build T28 cycles)] over update windows of w."""
    out = []
    for a in range(1, upto - w + 1, w):
        b = a + w
        if b > upto:
            break
        to = uo[b - 1]['C'] - uo[a - 1]['C']
        tb = ub[b - 1]['C'] - ub[a - 1]['C']
        out.append((a, b, to, tb, ub[b - 1]['T28'] - ub[a - 1]['T28'], uo[b - 1]['T28'] - uo[a - 1]['T28']))
    return out


def summary(ws):
    to, tb = sum(x[2] for x in ws), sum(x[3] for x in ws)
    n = sum(x[1] - x[0] for x in ws)
    return dict(updates=n, orig_s=to / MHZ28, build_s=tb / MHZ28, penalty=100.0 * (tb / to - 1) if to else 0.0,
                hook_ms=1000.0 * sum(x[4] for x in ws) / MHZ28 / max(n, 1), orig_hook_ms=1000.0 * sum(x[5] for x in ws) / MHZ28 / max(n, 1))


def phases(ws):
    """all / quiet / busy (thirds by the original's time per update) / the worst window by penalty."""
    srt = sorted(ws, key=lambda x: x[2])
    k = max(1, len(srt) // 3)
    out = [('all', summary(ws)), ('quiet (fastest third)', summary(srt[:k])), ('busy (slowest third)', summary(srt[-k:]))]
    worst = max(ws, key=lambda x: x[3] / x[2] if x[2] else 0)
    out.append(('worst window u%d-%d' % (worst[0], worst[1] - 1), summary([worst])))
    return out


def rates(cnt, u0_frame):
    c = [r for r in cnt if r['F'] >= u0_frame]
    if len(c) < 2:
        return {}
    a, b = c[0], c[-1]
    sec = (b['F'] - a['F']) / 50.0
    fr = b['F'] - a['F']
    cyc = b['C'] - a['C']
    worst = max(((y['T28'] - x['T28']) / max(1, y['C'] - x['C']) for x, y in zip(c, c[1:])), default=0)
    return dict(updates=(b['U'] - a['U']) / sec, AY=(b['AY'] - a['AY']) / sec, BP=(b['BP'] - a['BP']) / sec,
                INT=(b['INT'] - a['INT']) / sec, hook=100.0 * (b['T28'] - a['T28']) / cyc if cyc else 0,
                hook_worst=100.0 * worst, DI=100.0 * (b['DI'] - a['DI']) / (fr * len(DI_LINES)) if fr else 0,
                gap=1000.0 * max(r.get('MG', 0) for r in c[1:]) / MHZ28)


def lockstep(uo, ub, nstate):
    if not nstate:
        return None, min(len(uo), len(ub))
    for i, (x, y) in enumerate(zip(uo, ub)):
        if any(x.get('S%d' % k) != y.get('S%d' % k) for k in range(nstate)):
            return i + 1, i
    return None, min(len(uo), len(ub))


def duplicates(us):
    """Probe hits that look like JNext firing an execute rule twice at one address around an accepted interrupt
    (lesson jnext-execute-probe-fires-twice): under DUP_T T states after the hit before, under half the run's
    median gap, and an interrupt taken in between. -> [(update, gap in T)]"""
    gaps = [(b['u'], b['C'] - a['C'], b.get('INT', 0) - a.get('INT', 0)) for a, b in zip(us, us[1:])]
    if not gaps:
        return []
    med = sorted(g for _, g, _ in gaps)[len(gaps) // 2]
    return [(u, g // 8) for u, g, i in gaps if i > 0 and g < 8 * DUP_T and 2 * g < med]


def reached(us, idx):
    """The first update at which one of the state bytes idx (indices into the profile's state list) differs from
    its value at the first update, or None: the input never changed them."""
    for r in us:
        if any(r.get('S%d' % k) != us[0].get('S%d' % k) for k in idx):
            return r
    return None


def table(prog_b, prog_o, probe, note, uo, ub, co, cb, nstate, window, limit, seed, reach=()):
    """reach: indices into the profile's state list of the bytes the input must change (its "reach" key)."""
    first, upto = lockstep(uo, ub, nstate)
    lines = ['PACE  %s (%s) vs %s (%s): probe 0x%04X (%s), input keyed to updates, seed %d' % (
        os.path.basename(prog_b), J.md5(prog_b)[:8], os.path.basename(prog_o), J.md5(prog_o)[:8], probe, note, seed)]
    for tag, us in (('original', uo), ('build', ub)):
        dup = duplicates(us)
        if dup:
            lines.append('WARNING: %s: the probe fired twice around an interrupt %d time(s), first at update %d (%d T '
                         'after the hit before): a JNext duplicate shifts the update count and the keyed input; guard the '
                         'probe or move it (lesson jnext-execute-probe-fires-twice)' % (tag, len(dup), dup[0][0], dup[0][1]))
    if reach:
        got = [(tag, reached(us, reach)) for tag, us in (('original', uo), ('build', ub))]
        miss = [tag for tag, r in got if r is None]
        if miss:
            lines.append('RESULT: not measured: keys did not reach play: no "reach" byte changed in the %s run (%s '
                         'updates; start keys, a menu, or keys the game does not read?)' % (
                             ' and '.join(miss), ' / '.join(str(len(us)) for us in (uo, ub))))
            return lines, None
        lines.append('reach: input reached play: a "reach" byte changed at update %s' % ', '.join(
            '%d (frame %d) in the %s' % (r['u'], r['F'], tag) for tag, r in got))
    else:
        lines.append('reach: not checked (no "reach" addresses in the profile: bytes such as position or score '
                     'that the input must change)')
    if upto < 2 * window:
        lines.append('RESULT: not measured: %d updates in lockstep (original %d, build %d; the probe or the start keys?)' % (
            upto, len(uo), len(ub)))
        return lines, None
    ph = phases(windows(uo, ub, window, upto))
    lines.append('%-24s %8s %9s %9s %8s %9s %9s' % ('phase', 'updates', 'original', 'build', 'penalty', 'hook/upd', 'orig hook'))
    for name, s in ph:
        lines.append('%-24s %8d %8.2fs %8.2fs %+7.2f%% %7.2fms %7.2fms' % (
            name, s['updates'], s['orig_s'], s['build_s'], s['penalty'], s['hook_ms'], s['orig_hook_ms']))
    ro, rb = rates(co, uo[0]['F']), rates(cb, ub[0]['F'])
    lines.append('%-24s %9s %9s' % ('per second (play)', 'original', 'build'))
    for k, name, fmt in (('updates', 'game updates', '%9.2f'), ('AY', 'AY data writes', '%9.0f'), ('BP', 'port FE writes', '%9.0f'),
                         ('INT', 'interrupts taken', '%9.2f'), ('hook', 'hook time % of time', '%9.2f'),
                         ('hook_worst', 'hook time, worst 1 s %', '%9.2f'), ('DI', 'interrupts off % time', '%9.1f'),
                         ('gap', 'longest interrupt gap ms', '%9.1f')):
        lines.append('%-24s %s %s' % (name, fmt % ro.get(k, 0), fmt % rb.get(k, 0)))
    if nstate:
        lines.append('lockstep: game state equal at every update up to %d%s' % (
            upto - 1, '' if first is None else ' (first difference at update %d: measured up to there)' % first))
    else:
        lines.append('lockstep: not checked (no state addresses in the profile)')
    pen = ph[0][1]['penalty']
    warn = []
    if pen > limit:
        warn.append('over %.1f%%: the build plays slower than the original' % limit)
    elif pen < -limit:
        warn.append('under -%.1f%%: the build plays faster than the original (pace target ORIGINAL)' % limit)
    if ro.get('INT') and rb.get('gap', 0) > ro.get('gap', 0) + 5:
        warn.append('interrupts held off longer than the original (%.1f ms against %.1f)' % (rb['gap'], ro['gap']))
    lines.append('RESULT: penalty %+.2f%% over %d updates%s' % (pen, ph[0][1]['updates'],
                                                            ' - WARNING: ' + '; '.join(warn) if warn else ''))
    return lines, dict(phases=ph, original=ro, build=rb, lockstep_upto=upto, first_difference=first)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('build', help='the build (.nex)')
    ap.add_argument('--original', required=True, help='the original .z80 or the plain .nex (same machine as the build)')
    ap.add_argument('--probe', help='address run once per game update (default: the profile\'s, else automatic)')
    ap.add_argument('--profile', help='input profile JSON (nexclash/jnext.py; default generic)')
    ap.add_argument('--updates', type=int, default=600, help='game updates to measure (default 600)')
    ap.add_argument('--window', type=int, default=20, help='updates per phase window (default 20)')
    ap.add_argument('--limit', type=float, default=2.0, help='warn over this penalty %% (default 2)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--max-frames', type=int, default=60000, help='stop a run after this many frames')
    ap.add_argument('--card', help='NextZXOS SD card image (default $NEXCLASH_JNEXT_CARD)')
    ap.add_argument('--jnext-home', help='HOME for JNext (default OUT/.jnext_home)')
    ap.add_argument('-o', '--out', default='pace', help='output folder (default ./pace)')
    a = ap.parse_args(argv)
    prof = J.load_profile(a.profile)
    card = J.card(a.card)
    os.makedirs(a.out, exist_ok=True)
    out = os.path.abspath(a.out)
    probe = a.probe or prof.get('probe')
    note = 'given' if a.probe else 'profile' if probe else None
    if probe:
        probe = J.num(probe)
    else:
        probe, note = detect(a.original, prof, card, a.jnext_home, out, a.seed, build=a.build)
        if probe is None:
            J.result_block(['PACE  RESULT: not measured: %s' % note], os.path.join(a.out, 'RESULT.txt'))
            return 0
    state = [J.num(x) for x in prof.get('state', [])]
    reach = [J.num(x) for x in prof.get('reach', [])]
    if any(x not in state for x in reach):
        raise SystemExit('profile "reach" addresses must be in its "state" list (they are read from the logged state): %s'
                         % ', '.join('0x%04X' % x for x in reach if x not in state))
    jobs =[(prog, script(prog, prof, probe, a.updates, a.seed, o, a.max_frames, state), os.path.join(out, tag),
             a.max_frames, card, a.jnext_home) for tag, prog, o in (('original', a.original, True), ('build', a.build, False))]
    J.run_all(jobs)
    uo, co = load(os.path.join(out, 'original'))
    ub, cb = load(os.path.join(out, 'build'))
    lines, res = table(a.build, a.original, probe, note, uo, ub, co, cb, len(state), a.window, a.limit, a.seed,
                       [state.index(x) for x in reach])
    for tag, prog, _ in (('original', a.original, 0), ('build', a.build, 0)):
        w = J.check_start(os.path.join(out, tag, 'run.log'), prog)
        if w:
            lines.insert(-1, w)
    J.result_block(lines, os.path.join(a.out, 'RESULT.txt'))
    json.dump(dict(probe=probe, note=note, result=res), open(os.path.join(a.out, 'pace.json'), 'w'), indent=1)
    return 0


def selfcheck():
    """Synthetic update logs: a build 10% slower on every update, in lockstep, then one state difference."""
    bad = []
    uo = [dict(u=i + 1, C=1000 * i * (2 if i % 60 >= 30 else 1), T28=0, S0=i) for i in range(120)]
    uo = [dict(r, C=sum(1000 * (2 if j % 60 >= 30 else 1) for j in range(i))) for i, r in enumerate(uo)]
    ub = [dict(r, C=int(r['C'] * 1.1), T28=int(r['C'] * 0.05)) for r in uo]
    ph = phases(windows(uo, ub, 10, 120))
    pen = [round(s['penalty'], 3) for _, s in ph]
    if pen[:3] != [10.0, 10.0, 10.0]:
        bad.append(('penalty', pen))
    q, b = ph[1][1], ph[2][1]
    if not b['orig_s'] > q['orig_s']:
        bad.append(('phases', q, b))
    ub2 = [dict(r, S0=r['S0'] + (1 if r['u'] > 90 else 0)) for r in ub]
    if lockstep(uo, ub2, 1) != (91, 90):
        bad.append(('lockstep', lockstep(uo, ub2, 1)))
    # probe duplicates: updates of 70,000 T with an interrupt each; a second hit 300 T after update 20 around one
    run = [dict(u=i + 1, F=i, C=560000 * i, INT=i) for i in range(50)]
    dup = run[:20] + [dict(run[19], u=21, C=run[19]['C'] + 2400, INT=20)] + [dict(r, u=r['u'] + 1) for r in run[20:]]
    if duplicates(dup) != [(21, 300)]:
        bad.append(('duplicate probe hit missed', duplicates(dup)))
    short = [dict(u=i + 1, F=i // 7, C=80000 * i, INT=i // 7) for i in range(70)]     # 10,000 T updates, 7 a frame
    if duplicates(run) or duplicates(short):
        bad.append(('duplicate on a clean run', duplicates(run), duplicates(short)))
    # reach: the input must change a "reach" state byte (S1) in both runs, or "keys did not reach play"
    import tempfile
    import shutil
    t = tempfile.mkdtemp(prefix='nexclash_pace_')
    try:
        prog = os.path.join(t, 'x.z80')
        open(prog, 'wb').write(b'x')
        moved = [dict(r, T28=0, S0=r['u'], S1=40 + (r['u'] > 30)) for r in run]
        still = [dict(r, S1=40) for r in moved]
        for label, o, b, ok in (('moved', moved, moved, True), ('build still', moved, still, False),
                                ('both still', still, still, False)):
            lines, res = table(prog, prog, 0x8000, 'given', o, b, [], [], 2, 10, 2.0, 1, reach=[1])
            if ok != (res is not None) or ok != ('keys did not reach play' not in lines[-1]):
                bad.append(('reach %s' % label, lines[1:3]))
        lines, res = table(prog, prog, 0x8000, 'given', still, still, [], [], 2, 10, 2.0, 1)
        if res is None or not any(ln.startswith('reach: not checked') for ln in lines):
            bad.append(('reach not asked', lines[1:3]))
        dupb = [dict(r, T28=0, S0=r['u'], S1=40 + (r['u'] > 30)) for r in dup]
        lines, _ = table(prog, prog, 0x8000, 'given', moved, dupb, [], [], 2, 10, 2.0, 1, reach=[1])
        if not any('build: the probe fired twice' in ln for ln in lines):
            bad.append(('duplicate not reported', lines[1:3]))
    finally:
        shutil.rmtree(t, ignore_errors=True)
    return bad


if __name__ == '__main__':
    raise SystemExit(main())
