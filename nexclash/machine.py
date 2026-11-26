"""Fast 48K / 128K machine (SkoolKit C simulator) with keyboard + Kempston input and RZX-exact frames. A 128K snapshot
gets SkoolKit's paged memory (skoolkit.pagingtracer.Memory): 7FFD writes page as on a 128K Spectrum (until bit 5
locks it), the frame is 70908 T, and the AY registers are kept for the snapshot blocks a recording writes."""
import tempfile, os
from skoolkit import CSimulator
from skoolkit.simulator import Simulator
from skoolkit.simutils import from_snapshot, get_state, R, T, IFF, PC

FAST = CSimulator is not None
from skoolkit.snapshot import Snapshot, write_snapshot
from skoolkit.pagingtracer import Memory

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
    """128K in the shared paths (selftest --tools; made-up snapshots, no game files). -> failures
    - the recorder takes a 128K snapshot whose code pages banks 1 and 3 through 7FFD and writes into each; its recording
      replays in SkoolKit's rzxplay to the same eight banks, registers and 7FFD (and the same with a 48K snapshot);
    - analyse's access scan takes the 128K recording and places the two writes in banks 1 and 3 (rd128 / wr128);
    - the generic TID verifier still refuses a 128K recording (a 128K engine brings its own verifier);
    - an engine's own machine class is still taken (Recorder(..., machine=...))."""
    import shutil
    import skoolkit.rzxplay as rp
    from types import SimpleNamespace
    from .rzx import write_rzx, parse_rzx
    from .recorder import Recorder
    from .analyse import analyse
    from .verify import verify
    bad, t = [], tempfile.mkdtemp(prefix='nexclash_m128_')
    # 0x8000: DI; LD BC,7FFD; LD A,0x11; OUT (C),A; LD HL,C000; LD (HL),0x55; LD A,0x13; OUT (C),A; LD (HL),0xAA;
    # LD A,0x10; OUT (C),A; then INC (HL) forever (bank 0 at C000)
    code = bytes.fromhex('F301FD7F3E11ED7921 00C0 3655 3E13 ED79 36AA 3E10 ED79 34 18FD'.replace(' ', ''))
    per_frame = {}
    try:
        files = {}
        for mach in ('48K', '128K'):
            if mach == '48K':
                ram = [0] * 49152
                ram[0x4000:0x4000 + len(code)] = list(code)
                state = ()
            else:
                ram = [[0] * 16384 for _ in range(8)]
                ram[2][0:len(code)] = list(code)
                state = ('7ffd=16',)
            z = os.path.join(t, mach + '.z80')
            write_snapshot(z, ram, ('pc=32768', 'sp=65000'), state, mach)
            r = Recorder(z, log=None)
            for _ in range(60):
                r.first.append(r.m.frame())
            # the INC (HL) / JR loop (no contention) fills each frame: fetches a frame scale with the frame length
            per_frame[mach] = sum(f[0] for f in r.first[10:]) / len(r.first[10:])
            out = os.path.join(t, mach + '.rzx')
            write_rzx(out, [(r.first_z80, r.first)])
            files[mach] = z, out, r.m
            blocks = parse_rzx(out)
            ctx = rp.RZXContext(None)
            ctx.total_frames = sum(len(b.obj.frames) for b in blocks if hasattr(b.obj, 'frames'))
            opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=0, force=False)
            try:
                while blocks:
                    rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
            except Exception as e:              # noqa: BLE001 - a desync is the failure reported
                bad.append('%s recording does not replay: %s' % (mach, e))
                continue
            sim, m = ctx.simulator, r.m
            if ctx.frame_count != 60:
                bad.append('%s replay ran %d frames, not 60' % (mach, ctx.frame_count))
            if [sim.registers[i] for i in range(25)] != [m.sim.registers[i] for i in range(25)]:
                bad.append('%s replay registers differ from the recorder\'s' % mach)
            if mach == '128K':
                if [bytes(b) for b in sim.memory.banks] != [bytes(b) for b in m.sim.memory.banks]:
                    bad.append('128K replay banks differ from the recorder\'s')
                if sim.memory.o7ffd != m.out7ffd or m.out7ffd != 0x10:
                    bad.append('128K paging: replay 7FFD %02X, recorder %02X (want 10)' % (sim.memory.o7ffd, m.out7ffd))
                if m.sim.memory.banks[1][0] != 0x55 or m.sim.memory.banks[3][0] != 0xAA or not m.sim.memory.banks[0][0]:
                    bad.append('128K paging writes not in banks 1 / 3 / 0')
            elif bytes(sim.memory[0x4000:]) != m.view(0x4000, 0x10000):
                bad.append('48K replay memory differs from the recorder\'s')
        ratio = per_frame['128K'] / per_frame['48K']
        if abs(ratio - 70908 / 69888) > 0.003:
            bad.append('128K frame length: %.0f fetches a frame against 48K\'s %.0f (ratio %.4f, want %.4f)' % (
                per_frame['128K'], per_frame['48K'], ratio, 70908 / 69888))
        z128, r128, _ = files['128K']
        a = analyse(None, r128, 65000)
        if a.get('machine') != '128K' or not a['wr128'][0x4000 + 1 * 0x4000] or not a['wr128'][0x4000 + 3 * 0x4000]:
            bad.append('analyse: 128K writes not placed in banks 1 and 3')
        try:
            verify({}, None, r128)
            bad.append('the generic verifier took a 128K recording')
        except Exception as e:                  # noqa: BLE001 - only the refusal itself counts
            if '128K snapshot' not in str(e) or '48K only' not in str(e):
                bad.append('verify: %s' % e)

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
        self.is128 = isinstance(self.sim.memory, Memory)
        self.frame_t = getattr(self.sim, 'frame_duration', FRAME_T)     # 69888 (48K) or 70908 (128K)
        self.out7ffd = getattr(snap, 'out7ffd', 0) if self.is128 else 0
        self.outfffd = getattr(snap, 'outfffd', 0) or 0
        self.ay = list(getattr(snap, 'ay', None) or [0] * 16)
        self.sim.set_tracer(self)
        # LD R,A breaks fetch counting by R deltas: frames that run one are re-run exactly. 128K: every bank's
        # LD R,A as it would sit at 0xC000, plus banks 5 and 2 at their fixed addresses
        if self.is128:
            mem = self.sim.memory
            self.ldr = set()
            for b, base in ((5, 0x4000), (2, 0x8000)) + tuple((b, 0xC000) for b in range(8)):
                d = bytes(mem.banks[b])
                self.ldr |= {base + o for o in range(16383) if d[o] == 0xED and d[o + 1] == 0x4F}
        else:
            m = bytes(self.sim.memory)
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
        if self.is128:
            if port & 0x8002 == 0 and self.out7ffd & 32 == 0:      # 7FFD paging, as SkoolKit's rzxplay
                self.sim.memory.out7ffd(value)
                self.out7ffd = value
            if port & 0xC002 == 0xC000:
                self.outfffd = value
            elif port & 0xC002 == 0x8000 and self.outfffd < 16:
                self.ay[self.outfffd] = value

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
        while regs[T] < self.frame_t:
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
        while regs[T] < self.frame_t:
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
            if regs[T] >= self.frame_t:
                left[0], left[1] = fc, pc
                raise _Stop()
        try:
            self.sim.exec_frame(65535, None, tr)
        except _Stop:
            pass
        return 65535 - left[0], left[1]

    def view(self, lo, hi):
        """bytes lo..hi-1 as the CPU sees them now (the paged bank at 0xC000 on a 128K machine)."""
        m = self.sim.memory
        if self.is128:
            return bytes(m[a] for a in range(lo, hi))
        return bytes(m[lo:hi])

    def save(self):
        if self.is128:
            m = self.sim.memory
            mem = (tuple(bytes(b) for b in m.banks), m.o7ffd, self.out7ffd, self.outfffd, list(self.ay))
        else:
            mem = bytes(self.sim.memory)
        return (mem, list(self.sim.registers), self.outfe)

    def load(self, st):
        mem, regs, fe = st
        if self.is128:
            banks, o7ffd, self.out7ffd, self.outfffd, ay = mem
            m = self.sim.memory
            for b, d in enumerate(banks):
                m.banks[b][:] = d
            m.out7ffd(o7ffd)
            self.ay = list(ay)
        else:
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
