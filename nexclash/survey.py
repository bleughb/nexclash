"""Stage 0 (PLAYBOOK): one command that does the mechanical part of a new game before any design work.

    python -m nexclash.survey GAME.z80 [--rzx R ...] [--stop N] [--frames N --keys K] [-o DIR]

Writes DIR (default <game>_survey/ next to the snapshot): survey.md (one page: read it first),
survey.json (the raw numbers), preview.png (what each plot routine draws, per caller), <game>.nex
(the plain conversion). Steps:
  1. snapshot check (`inspect`), engine identification (engines.py detectors + identify),
  2. plain conversion with the tail placement of `convert` (48K: proven by the access analysis) and
     the simulated boot (nextboot.check),
  3. ONE pass over the recording(s) with three trackers: memory access + screen writers (`scan`),
     the interrupt handler (`isr`), and the plot routines (below),
  4. a preview pass for the top plot routines (`preview --plot`).
Plot routines: every screen write is put on the innermost CALL (or interrupt) that is running - a
shadow call stack, so a game that drops return addresses or uses SP as a data pointer can blur it.
Per routine: screen bytes written, calls, callers seen, T-states per call (interrupts included),
the routines that call it, block-copy writes (LDIR / LDI / PUSH: a back buffer copy).
Coverage gate: every CALL to a top plot routine found in the 64K view (byte pattern CD/C4/.. nn,
so some can be data) against the callers the recording reached. A site in code that ran but not
reached = a path the recording missed; ask for a recording that reaches it before stage 1.

Game-independent. Reuses memscan.Scanner / isrinfo.IsrTracker and their report() unchanged; this
module is no game's dependency (docs/records), so changing it re-verifies nothing.
"""
import argparse
import collections
import json
import os
import statistics
import sys

CALLS = {0xCD} | {0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
JPS = {0xC3} | {0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA}
BLOCK = {(0xED, 0xB0): 'LDIR', (0xED, 0xB8): 'LDDR', (0xED, 0xA0): 'LDI', (0xED, 0xA8): 'LDD'}
PUSHES = {0xC5, 0xD5, 0xE5, 0xF5}


class PlotTracker:
    """Shadow call stack; screen writes per innermost routine; calls, callers, T per call."""

    def __init__(self):
        self.sim = None
        self.stack = []                       # [target, ret, sp, caller_pc, t0]
        self.pending = None                   # (pc, target, sp) of a CALL about to run
        self.pix = collections.Counter()      # routine -> pixel bytes written (bitmap 0x4000-0x57FF)
        self.attr = collections.Counter()     # routine -> attribute bytes written
        self.block = collections.Counter()    # routine -> screen bytes written by LDIR/LDI/PUSH...
        self.calls = collections.defaultdict(collections.Counter)    # target -> caller pc -> calls
        self.parents = collections.defaultdict(collections.Counter)  # target -> enclosing routine -> calls
        self.tcost = collections.defaultdict(list)                   # target -> T per call (sampled)
        self.frames_active = collections.defaultdict(set)
        self.frame = 0
        self.T = 0                            # own T-state count (the replay resets its counter per frame)

    def on_sim(self, sim):
        self.sim = sim
        self.stack, self.pending = [], None

    def on_frame(self, n):
        self.frame = n

    def on_interrupt(self, sim, prev_pc):
        R = sim.registers                     # R[24] = where it returns (as isrinfo / drawcost)
        self.stack.append(['ISR', R[24], R[12], R[24], self.T])

    def _pop(self, pc, sp, R):
        st = self.stack
        while st and sp > st[-1][2]:                      # unwound some other way: drop the frame
            st.pop()
        if st and sp == st[-1][2] and (pc == st[-1][1] or (st[-1][0] == 'ISR' and pc == (st[-1][1] + 1) & 0xFFFF)):
            # an interrupt taken at a HALT returns to the instruction after it
            f = st.pop()
            if f[0] != 'ISR':
                c = self.tcost[f[0]]
                if len(c) < 4000:
                    c.append(self.T - f[4])

    def before(self, pc):
        R = self.sim.registers
        sp = R[12]
        p = self.pending
        if p is not None:
            self.pending = None
            if pc == p[1] and sp == (p[2] - 2) & 0xFFFF:
                parent = self.stack[-1][0] if self.stack else 'top'
                self.calls[p[1]][p[0]] += 1
                self.parents[p[1]][parent] += 1
                self.stack.append([p[1], (p[0] + 3) & 0xFFFF, p[2], p[0], self.T])
                return
        if self.stack:
            self._pop(pc, sp, R)
        m = self.sim.memory
        op = m[pc]
        if op in CALLS:
            self.pending = (pc, m[(pc + 1) & 0xFFFF] | m[(pc + 2) & 0xFFFF] << 8, sp)

    def after(self, pc, dt):
        self.T += dt

    def on_write(self, a, v, pc, mem):
        if 0x4000 <= a < 0x5B00:
            pass
        elif a >= 0xC000 and getattr(mem, 'o7ffd', 0) & 7 == 7 and a < 0xDB00:
            a -= 0x8000                                    # shadow screen (bank 7) seen at 0xC000
        else:
            return
        r = self.stack[-1][0] if self.stack else 'top'
        (self.pix if a < 0x5800 else self.attr)[r] += 1
        self.frames_active[r].add(self.frame)
        op = mem[pc]
        if op in PUSHES or (op == 0xED and (0xED, mem[(pc + 1) & 0xFFFF]) in BLOCK):
            self.block[r] += 1


class Multi:
    """Fan the simrun hooks out to several trackers (one pass instead of one per command)."""

    def __init__(self, *ts):
        for name in ('on_sim', 'before', 'after', 'on_read', 'on_write', 'on_interrupt', 'on_frame'):
            fs = [getattr(t, name) for t in ts if hasattr(t, name)]
            if fs:
                setattr(self, name, (lambda fs: lambda *x: [f(*x) for f in fs])(fs))


def static_sites(mem, target, ran):
    """CALL / JP byte patterns to `target` in the 64K view; ran(addr) = code ran near it."""
    lo, hi = target & 0xFF, target >> 8
    out = []
    for a in range(0x4000, 0xFFFE):
        if mem[a + 1] == lo and mem[a + 2] == hi:
            op = mem[a]
            if op in CALLS or op in JPS:
                out.append((a, 'CALL' if op in CALLS else 'JP', ran(a)))
    return out


def _h(a):
    return '%d (0x%04X)' % (a, a) if isinstance(a, int) else str(a)


def survey(z80, rzx=None, out=None, stop=None, frames=None, keys=None, top=6, log=print):
    from skoolkit.snapshot import Snapshot
    from . import snapinfo, memscan, isrinfo, preview as P, build as B, z80tonex as zt, nextboot
    from .simrun import run
    from .identify import identify
    from .engines import find
    name = os.path.splitext(os.path.basename(z80))[0]
    out = out or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '_survey')
    os.makedirs(out, exist_ok=True)
    md, js = [], {'game': name}
    say = md.append
    s = Snapshot.get(z80)
    is128 = len(s.ram(-1)) == 0x20000
    say('# Survey: %s (%s)' % (name, '128K' if is128 else '48K'))
    say('Read this first (PLAYBOOK stage 0). Raw numbers: survey.json. Commands to dig further: PLAYBOOK 2-3.')
    say('')
    say('## Snapshot (inspect)')
    say('```\n' + snapinfo.report(z80) + '\n```')

    # engine
    eng = find(s, argparse.Namespace(engine=None))
    prof = identify(s.memory[0:65536]) if not is128 else {'engine': None}
    js['engine'] = eng.__name__.split('.')[-1] if eng else prof.get('engine')
    say('## Engine')
    if eng:
        say('KNOWN dedicated engine `%s`: `python nexclash.py auto %s --rzx R --no-record` builds it; no new engine needed.'
            % (js['engine'], os.path.basename(z80)))
    elif prof.get('engine'):
        say('Generic engine `%s` (identify): `python nexclash.py auto` builds it.' % prof['engine'])
    else:
        say('Unknown: no detector in nexclash/engines.py and no TID / Dizzy 1 signature -> stage 1 (a new engine).')
    say('')

    # recordings
    rz = []
    if rzx:
        from skoolkit.rzxplay import parse_rzx
        from . import rzx as RZ
        say('## Recordings')
        for r in rzx:
            nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, Snapshot))
            if nsnap > 1:          # analyse() (the plain build's tail proof) desyncs on autosave snapshots
                r2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
                RZ.strip(r, r2)
            say('- %s: %s' % (os.path.basename(r), 'autosave snapshots: %d, stripped -> %s' % (nsnap - 1, os.path.basename(r2))
                              if nsnap > 1 else 'no autosave snapshots'))
            rz.append(r2 if nsnap > 1 else r)
        say('')

    # plain conversion + boot
    log('survey: plain conversion ...')
    plain = os.path.join(out, name + '.nex')
    an, note = None, ''
    if rz and not is128:
        from .analyse import analyse
        ans = [analyse(None, r, s.sp, stop=stop) for r in rz]
        an = dict(ans[0])
        for x in ans[1:]:
            an['rd'] = bytes(p | q for p, q in zip(an['rd'], x['rd']))
            an['wr'] = bytes(p | q for p, q in zip(an['wr'], x['wr']))
            an['rom_used'] |= x['rom_used']
            an['stack_low_water'] = min(an['stack_low_water'], x['stack_low_water'])
    elif is128:
        note = ' (128K: tail not proven by a recording - prove it with `scan --range`, PLAYBOOK 1)'
    cap, orig = {}, zt.convert

    def conv(*a, **k):
        cap['c'] = orig(*a, **k)
        return cap['c']
    zt.convert = conv
    try:
        where = B.plain(z80, plain, an, log=lambda *x: None)
    except ValueError as e:
        where = 'FAILED: %s' % e
    finally:
        zt.convert = orig
    boot = 'not run'
    if is128:
        boot = "not run: nextboot.check models 48K start-up only (128K engines bring their own boot check, e.g. midres.boot_check)"
    elif 'c' in cap:
        c = cap['c']
        try:
            bad = nextboot.check(plain, z80, None, (c[1], c[1] + len(c[2])))
            boot = 'OK (registers, RAM, ROM view, paging)' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]
        except Exception as e:                              # noqa: BLE001 - report, do not hide
            boot = 'boot simulation error: %s' % e
    js['plain'] = {'file': os.path.basename(plain), 'tail': where, 'boot': boot}
    say('## Plain conversion')
    say('- %s: %s%s; simulated boot: %s. The user tests it on the Next with the stage-1 question.'
        % (os.path.basename(plain), where, note, boot))
    say('')

    # the combined pass
    log('survey: analysis pass (memory, screen writers, interrupts, plot routines) ...')
    screen = '0x4000-0x5AFF'
    watch = [(screen, set(memscan.parse_range(screen, is128)))]
    sc, it, pt = memscan.Scanner(None, watch), isrinfo.IsrTracker(), PlotTracker()
    n = run(z80, rz or None, Multi(sc, it, pt), frames=frames, keys=keys, stop=stop)
    js['frames'] = n
    mem_txt = memscan.report(sc, n, rz or None, keys, None, None, is128, None)[0]
    scr_txt = memscan.report(sc, n, rz or None, keys, [screen], None, is128, watch)[0]
    isr_txt = isrinfo.report(it, n, z80, rz or None, keys)[0]

    # plot routines
    ran = lambda a: any(sc.flags[i] & memscan.EXEC for i in range(max(0, a - 24), min(0xC000, a + 24)) if i < 0xC000)
    rank = sorted(set(pt.pix) | set(pt.attr), key=lambda r: -(pt.pix[r] + pt.attr[r]))
    rows, gaps, routines = [], 0, []
    mem = pt.sim.memory if pt.sim is not None else s.memory
    for r in rank[:top]:
        calls = sum(pt.calls[r].values()) if r not in ('top', 'ISR') else 0
        tc = pt.tcost.get(r, [])
        info = {'routine': r, 'pixel_bytes': pt.pix[r], 'attr_bytes': pt.attr[r], 'block_copy_bytes': pt.block[r],
                'calls': calls, 'frames_active': len(pt.frames_active[r]),
                'callers_seen': {str(k): v for k, v in pt.calls[r].most_common()} if isinstance(r, int) else {},
                'called_from_routines': {str(k): v for k, v in pt.parents[r].most_common(3)} if isinstance(r, int) else {},
                'T_median': int(statistics.median(tc)) if tc else None, 'T_max': max(tc) if tc else None}
        if isinstance(r, int) and r >= 0x4000:
            st = static_sites(mem, r, ran)
            seen = set(pt.calls[r])
            info['call_sites'] = [{'at': a, 'kind': k, 'code_ran_near': g, 'reached': a in seen} for a, k, g in st]
            miss = [x for x in info['call_sites'] if x['kind'] == 'CALL' and not x['reached'] and x['code_ran_near']]
            info['not_reached'] = [x['at'] for x in miss]
            gaps += len(miss)
        routines.append(info)
        cov = ''
        if 'call_sites' in info:
            nc = [x for x in info['call_sites'] if x['kind'] == 'CALL']
            cov = '%d/%d CALL sites reached%s' % (sum(x['reached'] for x in nc), len(nc),
                                                  ('; NOT reached (code ran nearby): ' + ', '.join(_h(a) for a in info['not_reached'][:6]))
                                                  if info['not_reached'] else '')
            nj = sum(1 for x in info['call_sites'] if x['kind'] == 'JP')
            if nj:
                cov += '; %d JP site(s) (not tracked)' % nj
        rows.append('| %s | %d / %d%s | %d | %d | %s | %s | %s |' % (
            _h(r) if isinstance(r, int) else r + (' (outside any CALL)' if r == 'top' else ' (interrupt handler)'),
            pt.pix[r], pt.attr[r], ' (%d block copy)' % pt.block[r] if pt.block[r] else '', calls,
            len(pt.calls[r]),
            '%s / %s' % (info['T_median'], info['T_max']) if tc else '-',
            ', '.join(_h(k) if isinstance(k, int) else k for k in pt.parents[r]) if isinstance(r, int) else '-',
            cov or '-'))
    js['routines'] = routines
    js['coverage_gaps'] = gaps
    say('## Recording and coverage')
    say('- %d frames analysed%s.' % (n, ' (free run, keys: %s)' % (keys or 'none') if not rz else ''))
    say('- GATE: %s' % ('OK - every CALL site to the top plot routines in code that ran was reached'
                         if not gaps else 'CHECK - %d CALL site(s) to these routines, in code that ran, were never reached '
                         '(table below). For a FIGURE plotter that is a path the recording missed: ask the user for a '
                         'recording that reaches it (docs/RECORDING_CHECKLIST.md) before stage 1. For a text / score '
                         'printer it usually is a message that did not come up: say so in games/<game>.md.' % gaps))
    say('')
    say('## Screen writers by routine (innermost CALL running at the write)')
    say('| Routine | pixel / attr bytes | calls | callers seen | T per call median / max | called from | coverage |')
    say('|---|---|---|---|---|---|---|')
    md.extend(rows)
    say('Block copies (LDIR / LDI / PUSH) into the screen = probably a back buffer: `scan --range BUF --writers` '
        'on its source (PLAYBOOK 2). A routine in ROM (< 0x4000) is the ROM printing text.')
    say('')

    # preview
    plots = [r for r in rank[:top] if isinstance(r, int) and r >= 0x4000][:6]
    if n >= 8:
        log('survey: preview pass ...')
        step = max(1, n // 8)
        at = list(range(step, n + 1, step))[:8]
        try:
            ptxt = P.preview(z80, rz or None, os.path.join(out, 'preview.png'), at, None, plots or None, None,
                             frames or (n if not rz else None), keys, n)[0]
        except Exception as e:                              # noqa: BLE001
            ptxt = 'preview failed: %s' % e
        say('## Preview (preview.png: screen at frames %s, what each plot routine draws per caller)' % ','.join(map(str, at)))
        say('```\n' + '\n'.join(ptxt.split('\n')[:14]) + '\n```')
        say('')
    say('## Screen writers (scan --writers)')
    say('```\n' + scr_txt + '\n```')
    say('## Memory (scan: free memory for hook state, stack low-water)')
    say('```\n' + '\n'.join(mem_txt.split('\n')[:28]) + '\n```')
    say('## Interrupt handler (isr: what hooks must keep intact)')
    say('```\n' + isr_txt + '\n```')
    text = '\n'.join(md) + '\n'
    open(os.path.join(out, 'survey.md'), 'w').write(text)
    json.dump(js, open(os.path.join(out, 'survey.json'), 'w'), indent=1, default=str)
    return text, js


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('z80')
    ap.add_argument('--rzx', action='append', help='recording(s) (repeatable); none = a free run')
    ap.add_argument('--stop', type=int, help='RZX: stop after N frames')
    ap.add_argument('--frames', type=int, help='free run: frames (default 500)')
    ap.add_argument('--keys', help='free run: key schedule, e.g. "5-14:SPACE; 30-:N"')
    ap.add_argument('--top', type=int, default=6, help='plot routines to report (default 6)')
    ap.add_argument('-o', '--out', help='output folder (default <game>_survey next to the snapshot)')
    a = ap.parse_args(argv)
    text, js = survey(a.z80, a.rzx, a.out, a.stop, a.frames, a.keys, a.top, log=lambda m: print(m, file=sys.stderr))
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
