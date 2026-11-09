#!/usr/bin/env python3
"""Probe: does gameplay need this routine? Replay each update with one CALL skipped and compare game RAM.

    python tools/probes/routine_skip.py GAME.rzx --call 0x8F92 [--exclude 0x9800-0x99FF ...] [--no-r]
        [--stop N] [--json]

Invocation: the RZX (its embedded snapshot is the start state) and the address of a CALL instruction
  the game executes once per update (card detect.routine-removal). At each hit the machine is copied;
  at the next hit that copy is run on from the instruction after the CALL (the routine skipped) until
  it reaches the CALL again, and its memory and registers are compared with the original's.
  The copy is fed, in order, the IN values and `LD A,R` values (--no-r: R is left alone) the original
  read outside the routine, and gets each interrupt at the same count of non-routine instructions
  (an interrupt during the routine: right after the skip).
Output: updates compared, identical (memory outside --exclude, 0x4000-0x5AFF and the 256 bytes below
  the original's SP, whose differences are counted apart as dead stack), differing pages,
  register differences (main set), runaways / IN mismatches, R values fed, the first difference.
Limits: 48K memory only (no 7FFD paging); the routine is the CALL's dynamic extent (until the PC is
  back after the CALL with the same SP); a replay sees only the branches the recording takes - read
  the routine's disassembly for gameplay logic on other paths (Inferno 9804). Python simulator:
  ~1-3 minutes per 1,000 frames.
Origin: Inferno 2026-11-09 (specnext reference/inferno/build/hybrid/probe_skip.py), generalised
  2026-11-10; dispositions in games/inferno.md "Lessons".
Smoke test: `python selftest.py --tools` runs it on Chuckie Egg: skipping the attribute refresh
  CALL 38200 at 39244 leaves game RAM identical outside the attributes; skipping the hens' CALL
  37150 at 39238 must differ (negative control).
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

REGS = {0: 'A', 1: 'F', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'H', 7: 'L', 8: 'IXh', 9: 'IXl',
        10: 'IYh', 11: 'IYl', 12: 'SP'}
MAX_STEPS = 5000000
DEAD_STACK = 256              # bytes below the original's SP at the compare: dead stack, counted apart


class _Feed:
    """Port reads for the skip copy: the original's IN values, in order."""
    def __init__(self, vals):
        self.vals, self.i, self.bad = vals, 0, False

    def read_port(self, registers, port):
        if self.i >= len(self.vals):
            self.bad = True
            return 255
        v = self.vals[self.i]
        self.i += 1
        return v

    def write_port(self, *a):
        pass

    def write_memory(self, *a):
        pass


def _ignored(excl):
    table = bytearray(65536)
    for lo, hi in [(0x4000, 0x5AFF)] + list(excl):
        table[lo:hi + 1] = b'\x01' * (hi + 1 - lo)
    return table


class _Probe:
    def __init__(self, call, excl, feed_r):
        self.call, self.ret, self.feed_r = call, (call + 3) & 0xFFFF, feed_r
        self.ign = _ignored(excl)
        self.sim = None
        self.copy = None             # (memory, registers) at the previous hit
        self.routine = False         # inside the CALL's dynamic extent
        self.call_sp = None
        self.isr = None              # (return pc, sp) while an interrupt runs outside the routine
        self.count = 0               # non-routine, non-ISR instructions since the hit
        self.ints, self.ins, self.rs = [], [], []
        self.n = self.same = self.runaway = 0
        self.r_fed = self.dead = 0
        self.pages, self.regs, self.first = collections.Counter(), collections.Counter(), None
        self.frame = 0

    def on_sim(self, sim):
        self.sim = sim

    def on_frame(self, n):
        self.frame = n

    def on_interrupt(self, sim, prev_pc):
        m = sim.memory
        refused = m[prev_pc] == 0xFB or (m[prev_pc] in (0xDD, 0xFD) and prev_pc == (sim.registers[24] - 1) & 0xFFFF)
        if sim.registers[26] and not refused and self.copy is not None:   # accepted: record when it came
            self.ints.append(self.count)
            if not self.routine and self.isr is None:
                self.isr = (sim.registers[24], sim.registers[12])

    def before(self, pc):
        sim = self.sim
        r, m = sim.registers, sim.memory
        if self.routine:
            if pc == self.ret and r[12] == self.call_sp:
                self.routine = False
            else:
                return
        if self.isr is not None and pc == self.isr[0] and r[12] == self.isr[1]:
            self.isr = None
        if pc == self.call:
            if self.copy is not None:
                self._compare()
            self.copy = (list(m), list(r))
            self.count, self.ints, self.ins, self.rs = 0, [], [], []
        if self.copy is None:
            return
        if m[pc] == 0xED and m[(pc + 1) & 0xFFFF] == 0x5F:
            self.rs.append(r[15])
        if self.isr is None:
            self.count += 1
        if pc == self.call:
            self.routine, self.call_sp = True, r[12]

    def record_in(self, value):
        if self.copy is not None and not self.routine:
            self.ins.append(value)

    def _compare(self):
        from skoolkit.simulator import Simulator
        from nexclash import simpool
        mem, regs = self.copy
        s = simpool.machine(Simulator, mem, regs, 'routine_skip', copy=True)
        q, sm = s.registers, s.memory
        q[24] = self.ret
        feed = _Feed(self.ins)
        s.set_tracer(feed)
        count, pending, ri, steps = 1, list(self.ints), 0, 0
        isr = None
        prev = q[24]
        while q[24] != self.call and steps < MAX_STEPS:
            pc = q[24]
            if isr is not None and pc == isr[0] and q[12] == isr[1]:
                isr = None
            if pending and pending[0] <= count and isr is None and q[26]:
                pending.pop(0)
                ret = (q[24], q[12])
                if s.accept_interrupt(q, sm, prev):
                    isr = ret
                    continue
            if self.feed_r and sm[pc] == 0xED and sm[(pc + 1) & 0xFFFF] == 0x5F and ri < len(self.rs):
                q[15] = self.rs[ri]
                ri += 1
            if isr is None:
                count += 1
            prev = pc
            s.opcodes[sm[pc]]()
            steps += 1
        self.r_fed += ri
        self.n += 1
        real, rr = self.sim.memory, self.sim.registers
        bad = steps >= MAX_STEPS or feed.bad or feed.i != len(self.ins)
        if bad:
            self.runaway += 1
        sp = rr[12]
        dead = {(sp - k) & 0xFFFF for k in range(1, DEAD_STACK + 1)}      # below SP: never read again
        diff = [a for a in range(0x4000, 0x10000) if sm[a] != real[a] and not self.ign[a]]
        self.dead += sum(1 for a in diff if a in dead)
        diff = [a for a in diff if a not in dead]
        rd = [REGS[k] for k in REGS if q[k] != rr[k]]
        for a in diff:
            self.pages[a >> 8] += 1
        for k in rd:
            self.regs[k] += 1
        if not diff and not bad:
            self.same += 1
        elif self.first is None:
            self.first = {'update': self.n, 'frame': self.frame, 'runaway_or_in': bad,
                          'addresses': ['0x%04X' % a for a in diff[:12]], 'registers': rd}


def skip(rzx_path, call, exclude=(), feed_r=True, stop=None):
    """-> {'frames', 'updates', 'identical', 'runaway_or_in', 'r_fed', 'pages', 'registers', 'first'}"""
    import skoolkit.rzxplay as rz
    from nexclash import simrun
    p = _Probe(call, exclude, feed_r)
    orig = rz.RZXTracer.read_port

    def read_port(self, registers, port):
        v = orig(self, registers, port)
        p.record_in(v)
        return v
    rz.RZXTracer.read_port = read_port
    try:
        frames = simrun.play_rzx(rzx_path, p, stop=stop)
    finally:
        rz.RZXTracer.read_port = orig
    if p.sim is not None and len(p.sim.memory) != 65536:
        raise SystemExit('routine_skip: 48K memory only')
    return {'frames': frames, 'updates': p.n, 'identical': p.same, 'runaway_or_in': p.runaway,
            'r_fed': p.r_fed, 'dead_stack_bytes': p.dead, 'pages': {'0x%02X' % k: v for k, v in sorted(p.pages.items())},
            'registers': dict(p.regs), 'first': p.first}


def _range(s):
    lo, _, hi = s.partition('-')
    return int(lo, 0), int(hi or lo, 0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='routine_skip.py', description=__doc__.split('\n')[0])
    ap.add_argument('rzx')
    ap.add_argument('--call', required=True, help='address of the CALL instruction (once per update)')
    ap.add_argument('--exclude', action='append', default=[], help='LO-HI not compared (repeatable)')
    ap.add_argument('--no-r', action='store_true', help='do not feed the recorded LD A,R values')
    ap.add_argument('--stop', type=int, help='stop after N frames')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    r = skip(a.rzx, int(a.call, 0), [_range(x) for x in a.exclude], not a.no_r, a.stop)
    if a.json:
        print(json.dumps(r))
        return 0
    print('frames %d  updates %d  identical %d  runaway/IN %d  R fed %d  dead-stack bytes %d' % (
        r['frames'], r['updates'], r['identical'], r['runaway_or_in'], r['r_fed'], r['dead_stack_bytes']))
    print('differing pages: %s' % (r['pages'] or 'none'))
    print('register differences: %s' % (r['registers'] or 'none'))
    if r['first']:
        print('first difference: %s' % r['first'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
