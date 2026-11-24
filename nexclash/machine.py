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


class Refused(ValueError):
    """An input the shared path does not support; nexclash.py prints the message without a traceback."""


def is_128k(snap):
    """A 128K / +2 / +3 snapshot (eight RAM banks), a SkoolKit Snapshot."""
    return len(snap.ram(-1)) > 49152


def refuse_128k(snap, what, name=''):
    """The shared recorder, analyse and verify are 48K only: this Machine has no 7FFD paging, so a 128K game's
    banks and paging writes are not modelled and the run is wrong or stops with port readings left. Refuse such
    a snapshot loudly instead (lesson recorder-128k-not-in-toolkit)."""
    if snap is not None and is_128k(snap):
        raise Refused('%s128K snapshot (%s): %s is 48K only (nexclash/machine.py has no 7FFD paging). A 128K game '
                         'needs an engine with its own paging model: its own recorder (Recorder(..., machine=<a Machine '
                         'with 7FFD paging>)) and its own verifier copy (as fwd128.py and tid128.py carry); or record in '
                         'an emulator and leave out --rzx for the plain build (docs/PLAYBOOK.md)' % (
                             name + ': ' if name else '', snap.machine, what))


def refuse_128k_rzx(path, what):
    """refuse_128k for an RZX's first snapshot (the state its replay starts from)."""
    from .rzx import read_segments
    segs = read_segments(path)
    refuse_128k(segs[0][0] if segs else None, what, os.path.basename(path))


def selfcheck():
    """The 48K-only paths refuse a 128K snapshot and pass a 48K one (made-up snapshots and recordings; selftest
    --tools). -> failures"""
    import shutil
    from .rzx import write_rzx
    from .recorder import Recorder
    from .analyse import analyse
    from .verify import verify
    bad, t = [], tempfile.mkdtemp(prefix='nexclash_m128_')
    try:
        files = {}
        for mach, ram, state in (('48K', [0] * 49152, ()), ('128K', [[0] * 16384 for _ in range(8)], ('7ffd=16',))):
            z = os.path.join(t, mach + '.z80')
            write_snapshot(z, ram, ('pc=32768', 'sp=65000'), state, mach)
            r = os.path.join(t, mach + '.rzx')
            write_rzx(r, [(open(z, 'rb').read(), [(100, [])])])
            files[mach] = z, r
        z48, r48 = files['48K']
        z128, r128 = files['128K']
        for label, call in (('recorder', lambda: Recorder(z128, log=None)),
                            ('analyse', lambda: analyse(None, r128, 65000)),
                            ('verify', lambda: verify({}, None, r128))):
            try:
                call()
                bad.append('%s took a 128K snapshot' % label)
            except Exception as e:              # noqa: BLE001 - only the refusal itself counts
                if '128K snapshot' not in str(e) or '48K only' not in str(e):
                    bad.append('%s: %s' % (label, e))
        try:                                    # negative control: the 48K snapshot and recording pass the same guards
            Recorder(z48, log=None)
            refuse_128k_rzx(r48, 'analyse')
        except ValueError as e:
            bad.append('48K refused: %s' % e)

        class Paged:                            # an engine's own paging model: the recorder takes it
            def __init__(self, snap):
                pass

            def z80_bytes(self):
                return b''
        try:
            Recorder(z128, log=None, machine=Paged)
        except ValueError as e:
            bad.append('a paging model refused: %s' % e)
    finally:
        shutil.rmtree(t, ignore_errors=True)
    return bad


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
