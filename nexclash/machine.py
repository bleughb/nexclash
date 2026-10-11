"""Fast 48K machine (SkoolKit C simulator) with keyboard + Kempston input and RZX-exact frames."""
import tempfile, os
from skoolkit import CSimulator
from skoolkit.simulator import Simulator
from skoolkit.simutils import from_snapshot, get_state, R, T, IFF, PC

FAST = CSimulator is not None
from skoolkit.snapshot import Snapshot, write_snapshot

FRAME_T = 69888
ROWS = {  # port high byte -> keys for bits 0..4
    0xFE: ['SHIFT', 'Z', 'X', 'C', 'V'], 0xFD: ['A', 'S', 'D', 'F', 'G'],
    0xFB: ['Q', 'W', 'E', 'R', 'T'], 0xF7: ['1', '2', '3', '4', '5'],
    0xEF: ['0', '9', '8', '7', '6'], 0xDF: ['P', 'O', 'I', 'U', 'Y'],
    0xBF: ['ENTER', 'L', 'K', 'J', 'H'], 0x7F: ['SPACE', 'SYM', 'M', 'N', 'B']}
KEYPOS = {k: (row, bit) for row, ks in ROWS.items() for bit, k in enumerate(ks)}
KEMPSTON = {'K:RIGHT': 1, 'K:LEFT': 2, 'K:DOWN': 4, 'K:UP': 8, 'K:FIRE': 16}
ALL_INPUTS = list(KEYPOS) + list(KEMPSTON)


def parse_inputs(text):
    """'Q+SPACE' / 'K:RIGHT+K:FIRE' / '-' -> set of input names."""
    if not text or text == '-':
        return frozenset()
    out = set()
    for t in text.upper().split('+'):
        t = t.strip()
        if t in ('KR', 'KL', 'KU', 'KD', 'KF'):
            t = {'KR': 'K:RIGHT', 'KL': 'K:LEFT', 'KU': 'K:UP', 'KD': 'K:DOWN', 'KF': 'K:FIRE'}[t]
        if t not in KEYPOS and t not in KEMPSTON:
            raise ValueError('unknown key %r (keys: %s)' % (t, ' '.join(ALL_INPUTS)))
        out.add(t)
    return frozenset(out)


class Machine:
    def __init__(self, snap):
        if isinstance(snap, str):
            snap = Snapshot.get(snap)
        # int_active=0: same as SkoolKit's rzxplay, so recordings replay identically
        self.sim = from_snapshot(CSimulator or Simulator, snap, config={'int_active': 0})
        self.border = [(0, snap.border)]
        self.outfe = snap.border
        self.held = frozenset()
        self.ins = []
        self.cov = set()
        self.sim.set_tracer(self)
        m = bytes(self.sim.memory)
        # LD R,A breaks fetch counting by R deltas: frames that run one are re-run exactly
        self.ldr = {a for a in range(0x4000, 65535) if m[a] == 0xED and m[a + 1] == 0x4F}
        self.exact_frames = 0

    # --- tracer interface ---
    def read_port(self, registers, port):
        v = 0xFF
        if port & 1 == 0:
            hi = port >> 8
            for row, ks in ROWS.items():
                if hi & (row ^ 0xFF) == 0:          # this row selected (its address bit is 0)
                    for k in self.held:
                        if k in KEYPOS and KEYPOS[k][0] == row:
                            v &= ~(1 << KEYPOS[k][1])
            v &= 0xFF
        elif port & 0xFF == 0x1F:
            v = 0
            for k in self.held:
                v |= KEMPSTON.get(k, 0)
        self.ins.append(v)
        return v

    def write_port(self, registers, port, value, offset=0):
        if port & 1 == 0:
            self.outfe = value
            self.border = [(0, value)]

    # --- frames ---
    def frame(self, held=frozenset()):
        """Run one 50Hz frame with 'held' inputs; return (fetch_count, in_values)."""
        self.held = held
        self.ins = []
        regs = self.sim.registers
        if not FAST:
            fetches, pc = self._python_frame()
            regs[T] = 0
            if regs[IFF]:
                mem = self.sim.memory
                if mem[pc] == 0x76:
                    regs[PC] = (regs[PC] + 1) % 65536
                self.sim.accept_interrupt(regs, mem, 0)
            return fetches, self.ins
        start = self.save() if self.ldr else None
        fset = set()
        fetches = 0
        pc = regs[PC]
        while regs[T] < FRAME_T:
            r0 = regs[R] & 0x7F
            pc = self.sim.exec_frame(100, fset, None)
            fetches += (regs[R] - r0) & 0x7F
        if start is not None and not fset.isdisjoint(self.ldr):
            self.load(start)
            self.ins = []
            fetches, pc = self._exact()
            self.exact_frames += 1
        self.cov |= fset
        regs[T] = 0
        if regs[IFF]:
            mem = self.sim.memory
            if mem[pc] == 0x76:
                regs[PC] = (regs[PC] + 1) % 65536
            self.sim.accept_interrupt(regs, mem, 0)
        return fetches, self.ins

    def _python_frame(self):
        # pure-Python fallback: count fetches exactly as rzxplay does
        regs, mem, ops, cov = self.sim.registers, self.sim.memory, self.sim.opcodes, self.cov
        fetches = 0
        pc = regs[PC]
        while regs[T] < FRAME_T:
            pc = regs[PC]
            op = mem[pc]
            cov.add(pc)
            if op in (0xDD, 0xFD):
                r0 = regs[R]
                ops[op]()
                fetches += 2 - ((regs[R] ^ r0) % 2)
            else:
                ops[op]()
                fetches += 2 if op in (0xCB, 0xED) else 1
        return fetches, pc

    def _exact(self):
        regs = self.sim.registers
        left = [0, 0]

        class _Stop(Exception):
            pass

        def tr(fc, pc):
            if regs[T] >= FRAME_T:
                left[0], left[1] = fc, pc
                raise _Stop()
        try:
            self.sim.exec_frame(65535, None, tr)
        except _Stop:
            pass
        return 65535 - left[0], left[1]

    def save(self):
        return (bytes(self.sim.memory), list(self.sim.registers), self.outfe)

    def load(self, st):
        mem, regs, fe = st
        self.sim.memory[:] = mem
        self.sim.registers[:] = type(self.sim.registers)('H' if False else self.sim.registers.typecode, regs)
        self.outfe = fe
        self.border = [(0, fe)]

    def z80_bytes(self):
        """Current state as .z80 bytes (for an RZX snapshot block)."""
        ram, regs, state, machine = get_state(self.sim)
        fd, path = tempfile.mkstemp(suffix='.z80')
        os.close(fd)
        try:
            write_snapshot(path, ram, regs, state, machine)
            return open(path, 'rb').read()
        finally:
            os.remove(path)
