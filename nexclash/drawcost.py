"""`nexclash.py cost GAME.z80 --rzx R --at ADDR [--group IX]` - what a routine (the draw routine)
costs per call and per frame in the original game: the speed budget for hooks (PLAYBOOK 3b).

Every call that reaches ADDR (entered by CALL: PC == ADDR, its return address on the stack) is
timed until it returns (PC == return address, SP back). T-states are counted per instruction;
interrupt-handler time inside a call is reported separately (excluded from the call's cost).
Report: calls, calls per frame, T per call (median / mean / max; ms at 3.5 MHz), share of all
frame time, and optionally per value of a register at entry (e.g. IX = the object's descriptor).
Game-independent; extend freely (keep existing report lines; add new ones) and run
`python selftest.py --tools`.
"""
import collections
import statistics
from .simrun import run, FRAME_T

REGS = {'A': (0,), 'BC': (2, 3), 'DE': (4, 5), 'HL': (6, 7), 'IX': (8, 9), 'IY': (10, 11)}


class CostTracker:
    def __init__(self, at, group=None):
        self.at, self.group = at, group
        self.sim = None
        self.active = []              # [ret, sp, cost, isr_cost, key]
        self.done = []                # (cost, isr_cost, key, frame)
        self.frame = 0
        self.per_frame = collections.Counter()
        self.in_isr = None            # (pc, sp) of the interrupted point

    def on_sim(self, sim):
        self.sim = sim

    def on_interrupt(self, sim, prev_pc):
        if self.active and self.in_isr is None:
            R = sim.registers
            self.in_isr = (R[24], R[12])

    def before(self, pc):
        R = self.sim.registers
        if self.in_isr is not None and pc == self.in_isr[0] and R[12] == self.in_isr[1]:
            self.in_isr = None
        if self.active and self.in_isr is None:
            top = self.active[-1]
            if pc == top[0] and R[12] == top[1]:
                self.active.pop()
                self.done.append((top[2], top[3], top[4], self.frame))
                self.per_frame[self.frame] += 1
        if pc == self.at and self.in_isr is None:
            m = self.sim.memory
            sp = R[12]
            ret = m[sp] | m[(sp + 1) & 0xFFFF] << 8
            key = None
            if self.group:
                ix = REGS[self.group]
                key = R[ix[0]] if len(ix) == 1 else R[ix[0]] * 256 + R[ix[1]]
            self.active.append([ret, (sp + 2) & 0xFFFF, 0, 0, key])

    def after(self, pc, dt):
        if self.active:
            if self.in_isr is not None:
                self.active[-1][3] += dt
            else:
                self.active[-1][2] += dt

    def on_frame(self, n):
        self.frame = n


def cost(z80, at, rzx=None, frames=None, keys=None, stop=None, group=None):
    from skoolkit.snapshot import Snapshot
    is128 = len(Snapshot.get(z80).ram(-1)) == 0x20000
    ft = FRAME_T['128K' if is128 else '48K']
    t = CostTracker(at, group.upper() if group else None)
    n = run(z80, rzx, t, frames=frames, keys=keys, stop=stop)
    lines = ['Source    : %s, %d frames' % (', '.join(rzx) if rzx else 'free run (keys: %s)' % (keys or 'none'), n),
             'Routine   : %d (0x%04X) - entered %d times, %d returned, %d still running at the end' % (
                 at, at, len(t.done) + len(t.active), len(t.done), len(t.active))]
    res = {'calls': len(t.done), 'frames': n}
    if not t.done:
        lines.append('No completed calls (is ADDR the routine entry, reached by CALL?)')
        return '\n'.join(lines), res
    c = [d[0] for d in t.done]
    isr_t = sum(d[1] for d in t.done)
    pf = collections.Counter(t.per_frame[f] for f in range(1, n + 1))
    med = statistics.median(c)
    lines.append('T per call: median %d, mean %d, max %d, min %d  (median %.2f ms at 3.5 MHz)' % (
        med, statistics.mean(c), max(c), min(c), med / 3500))
    lines.append('Per frame : ' + ', '.join('%d call(s) in %d frames' % (k, v) for k, v in sorted(pf.items())))
    lines.append('Share     : %.1f %% of all frame time (%d frames x %d T); interrupt time inside calls '
                 'excluded (%d T)' % (100.0 * sum(c) / (n * ft), n, ft, isr_t))
    busiest = max(t.per_frame.values()) if t.per_frame else 0
    lines.append('Budget    : a hook adding X T per call costs X/%d of a frame per call; busiest frame had %d '
                 'call(s). At 28 MHz hook T count 1/8 (plus wait states).' % (ft, busiest))
    res.update(median=med, max=max(c), per_frame=dict(pf))
    if group:
        by = collections.defaultdict(list)
        for d in t.done:
            by[d[2]].append(d[0])
        lines.append('By %s at entry:' % group.upper())
        for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))[:12]:
            lines.append('  %5d (0x%04X): %5d calls, median %d T, max %d T' % (k, k, len(v), statistics.median(v), max(v)))
        res['by'] = {k: len(v) for k, v in by.items()}
    return '\n'.join(lines), res
