#!/usr/bin/env python3
"""Probe: how the original paces itself - T and frames per update, the slack before the next frame, beeper OUTs.

    python tools/probes/pacing_census.py GAME.rzx --update 0x8F7C [--limiter 0x9907] [--stop N] [--json]

Invocation: the RZX and the address the game executes once per update (its main loop point; survey
  and `cost` show candidates). --limiter: the entry of the routine that waits for the next frame;
  slack is then measured from its first entry in an update to the next interrupt (card
  detect.pacing-structure). Without it, slack = T idle (HALT, or a jump to itself such as `JR $`)
  before the interrupt that ends the wait.
Output: updates; frames (interrupts) per update; T per update; idle T and slack T (min / p1 / p10 /
  median / max); share of updates whose slack is below +0.5 / 1 / 2 / 5 / 10 ms of added work (they
  would slip a frame); the limiter's callers (return address on the stack: Inferno's limiter is called
  from inside the copier, 97FE); idle PCs; every OUT to an even port (beeper / border) by PC with
  value changes and updates that change it.
Limits: uncontended T at 3.5 MHz (3,500 T per ms), no ULA contention; idle detection is HALT and
  self-jumps only (a polling loop on a flag needs --limiter); OUT (C),r is counted when C is even;
  48K and 128K replay (simrun). Python simulator: ~1 minute per 1,000 frames.
Origin: Inferno 2026-11-07 (specnext reference/inferno/build/copier_window/probe_inferno.py, the
  pacing census that found the limiter inside the copier), generalised 2026-11-10.
Smoke test: `python selftest.py --tools` runs it on Chuckie Egg from its main loop (39241): golden
  update count, frames per update and the main beeper OUT site.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

T_MS = 3500
SLIP_MS = (0.5, 1, 2, 5, 10)


def _q(v):
    v = sorted(v)
    if not v:
        return None
    return {'min': v[0], 'p1': v[len(v) // 100], 'p10': v[len(v) // 10], 'median': v[len(v) // 2], 'max': v[-1]}


class _Probe:
    def __init__(self, update, limiter):
        self.update, self.limiter = update, limiter
        self.sim = None
        self.active = False
        self.tabs = 0
        self.u = None                      # current update: [start T, interrupts, idle T, limiter T or None, idle-run T]
        self.rows = []                     # (T, interrupts, idle T, slack T or None)
        self.callers = collections.Counter()
        self.idle_pcs = collections.Counter()
        self.outs = {}                     # pc -> [count, changes, last value, updates changed]
        self.out_seen = set()

    def on_sim(self, sim):
        self.sim = sim

    def on_interrupt(self, sim, prev_pc):
        u = self.u
        if u is None:
            return
        u[1] += 1
        if u[5] is None:                   # first interrupt after the wait began ends the slack
            if self.limiter is not None and u[3] is not None:
                u[5] = self.tabs - u[3]
            elif self.limiter is None and u[4]:
                u[5] = u[4]
        u[4] = 0

    def before(self, pc):
        sim = self.sim
        m, r = sim.memory, sim.registers
        if pc == self.update:
            if self.u is not None:
                u = self.u
                self.rows.append((self.tabs - u[0], u[1], u[2], u[5]))
            self.u = [self.tabs, 0, 0, None, 0, None]
            self.out_seen = set()
        if self.u is None:
            return
        if pc == self.limiter and self.u[3] is None:
            self.u[3] = self.tabs
            sp = r[12]
            self.callers['0x%04X' % (m[sp] | m[(sp + 1) & 0xFFFF] << 8)] += 1
        op = m[pc]
        port = None
        if op == 0xD3:
            port, val = m[(pc + 1) & 0xFFFF], r[0]
        elif op == 0xED and m[(pc + 1) & 0xFFFF] & 0xC7 == 0x41:
            k = (m[(pc + 1) & 0xFFFF] >> 3) & 7          # OUT (C),r: B C D E H L (0) A
            port, val = r[3], 0 if k == 6 else r[(2, 3, 4, 5, 6, 7, 0, 0)[k]]
        if port is not None and not port & 1:
            e = self.outs.setdefault(pc, [0, 0, None, 0])
            e[0] += 1
            if e[2] is not None and val != e[2]:
                e[1] += 1
                if pc not in self.out_seen:
                    self.out_seen.add(pc)
                    e[3] += 1
            e[2] = val

    def after(self, pc, dt):
        self.tabs += dt
        u = self.u
        if u is None:
            return
        m, r = self.sim.memory, self.sim.registers
        op = m[pc]
        selfjump = (op == 0x18 and m[(pc + 1) & 0xFFFF] == 0xFE) or \
                   (op == 0xC3 and m[(pc + 1) & 0xFFFF] | m[(pc + 2) & 0xFFFF] << 8 == pc)
        if (op == 0x76 or selfjump) and r[24] == pc:
            u[2] += dt
            u[4] += dt
            self.idle_pcs['0x%04X' % pc] += dt


def census(rzx_path, update, limiter=None, stop=None):
    from nexclash import simrun
    p = _Probe(update, limiter)
    frames = simrun.play_rzx(rzx_path, p, stop=stop)
    rows = p.rows
    slack = [s for _, _, _, s in rows if s is not None]
    out = {'frames': frames, 'updates': len(rows),
           'frames_per_update': dict(sorted(collections.Counter(i for _, i, _, _ in rows).items())),
           'T_per_update': _q([t for t, _, _, _ in rows]), 'idle_T': _q([i for _, _, i, _ in rows]),
           'slack_T': _q(slack), 'slack_measured': len(slack),
           'slip_share': {'%gms' % ms: round(sum(1 for s in slack if s < ms * T_MS) / len(slack), 4) if slack else None
                          for ms in SLIP_MS},
           'limiter_callers': dict(p.callers.most_common(8)),
           'idle_pcs': dict(p.idle_pcs.most_common(8)),
           'outs': {'0x%04X' % pc: {'count': e[0], 'changes': e[1], 'updates_changed': e[3]}
                    for pc, e in sorted(p.outs.items(), key=lambda kv: -kv[1][1])}}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog='pacing_census.py', description=__doc__.split('\n')[0])
    ap.add_argument('rzx')
    ap.add_argument('--update', required=True, help='address executed once per game update')
    ap.add_argument('--limiter', help='entry of the frame-wait routine (slack from its entry to the next interrupt)')
    ap.add_argument('--stop', type=int, help='stop after N frames')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    r = census(a.rzx, int(a.update, 0), int(a.limiter, 0) if a.limiter else None, a.stop)
    if a.json:
        print(json.dumps(r))
        return 0
    print('frames %d  updates %d  frames per update %s' % (r['frames'], r['updates'], r['frames_per_update']))
    for k in ('T_per_update', 'idle_T', 'slack_T'):
        print('%-13s %s' % (k, r[k]))
    print('slip share (slack below +x ms, %d updates): %s' % (r['slack_measured'], r['slip_share']))
    print('limiter callers: %s' % (r['limiter_callers'] or '-'))
    print('idle PCs (T): %s' % (r['idle_pcs'] or '-'))
    for pc, o in list(r['outs'].items())[:8]:
        print('OUT %s  count %d  changes %d  updates changed %d' % (pc, o['count'], o['changes'], o['updates_changed']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
