"""Shared runner for the analysis commands (inspect / scan / isr / cost): play an RZX, or free-run
a snapshot with a key schedule, with hooks on every instruction, memory access and interrupt.

Game-independent on purpose: everything about a particular game comes in as arguments
(addresses, ranges, keys). Improve it freely, but keep the hook signatures (docs/BRIEFING.md
C4) and run `python selftest.py --tools` after a change.

Hooks object (any attribute may be missing):
    on_sim(sim)                      once, after the simulator exists (48K list or 128K Memory)
    before(pc)                       before every instruction
    after(pc, dt)                    after every instruction, dt = its T-states
    on_read(addr, pc, mem)           every memory read (pc = current instruction; addr == pc is
    on_write(addr, value, pc, mem)       the opcode fetch); mem: the memory object (128K: .o7ffd)
    on_interrupt(sim, prev_pc)       just before an interrupt is accepted
    on_frame(n)                      at the end of frame n (1-based)
Memory hooks slow the run down ~2x; only installed when on_read / on_write exist.
"""
import os
import tempfile

FRAME_T = {'48K': 69888, '128K': 70908}

# keyboard half-rows: port high byte -> keys for bits 0..4
ROWS = {0xFE: ['CAPS', 'Z', 'X', 'C', 'V'], 0xFD: ['A', 'S', 'D', 'F', 'G'],
        0xFB: ['Q', 'W', 'E', 'R', 'T'], 0xF7: ['1', '2', '3', '4', '5'],
        0xEF: ['0', '9', '8', '7', '6'], 0xDF: ['P', 'O', 'I', 'U', 'Y'],
        0xBF: ['ENTER', 'L', 'K', 'J', 'H'], 0x7F: ['SPACE', 'SYM', 'M', 'N', 'B']}
KEYNAMES = {k for ks in ROWS.values() for k in ks} | {'K:UP', 'K:DOWN', 'K:LEFT', 'K:RIGHT', 'K:FIRE'}
KEMPSTON = {'K:RIGHT': 1, 'K:LEFT': 2, 'K:DOWN': 4, 'K:UP': 8, 'K:FIRE': 16}


def parse_keys(spec):
    """'5-14:SPACE; 30-:N' -> [(first, last or None, {keys})]. Frames are 0-based, inclusive."""
    out = []
    for part in (spec or '').replace(',', ';').split(';'):
        part = part.strip()
        if not part:
            continue
        rng, keys = part.split(':', 1)
        a, _, b = rng.partition('-')
        ks = {k.strip().upper() for k in keys.split('+') if k.strip()}
        bad = ks - KEYNAMES
        if bad:
            raise ValueError('unknown key(s) %s (keys: %s)' % (sorted(bad), ' '.join(sorted(KEYNAMES))))
        out.append((int(a), (int(b) if b else None) if _ else int(a), ks))
    return out


def held_at(schedule, frame):
    ks = set()
    for a, b, k in schedule:
        if frame >= a and (b is None or frame <= b):
            ks |= k
    return ks


def _watch(memory, hooks, regs_ref):
    """Wrap memory so reads/writes call the hooks. 128K Memory: swap in a subclass (rzxplay
    checks isinstance(memory, Memory)); 48K list: a list-like wrapper."""
    rd = getattr(hooks, 'on_read', None)
    wr = getattr(hooks, 'on_write', None)
    if not rd and not wr:
        return memory
    from skoolkit.pagingtracer import Memory
    if isinstance(memory, Memory):
        base = type(memory)
        MG, MS = base.__getitem__, base.__setitem__

        class W(base):
            def __getitem__(s, a):
                if rd and type(a) is int and regs_ref:
                    rd(a, regs_ref[0][24], s)
                return MG(s, a)

            def __setitem__(s, a, v):
                if wr and type(a) is int and regs_ref:
                    wr(a, v, regs_ref[0][24], s)
                MS(s, a, v)
        memory.__class__ = W
        return memory

    class L:
        def __init__(s, m):
            s.m = m

        def __len__(s):
            return len(s.m)

        def __getitem__(s, a):
            if rd and type(a) is int and regs_ref:
                rd(a, regs_ref[0][24], s)
            return s.m[a]

        def __setitem__(s, a, v):
            if wr and type(a) is int and regs_ref:
                wr(a, v, regs_ref[0][24], s)
            s.m[a] = v
    return L(memory)


def _sim_class(hooks):
    from skoolkit.simulator import Simulator
    regs_ref = []

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            memory = _watch(memory, hooks, regs_ref)
            super().__init__(memory, registers, state, config)
            regs_ref.append(self.registers)
            R, ops = self.registers, self.opcodes
            before, after = getattr(hooks, 'before', None), getattr(hooks, 'after', None)
            if before or after:
                def wrap(op):
                    def g():
                        pc, t = R[24], R[25]
                        if before:
                            before(pc)
                        op()
                        if after:
                            after(pc, R[25] - t)
                    return g
                for i in range(256):
                    ops[i] = wrap(ops[i])
            if hasattr(hooks, 'on_sim'):
                hooks.on_sim(self)

        def accept_interrupt(self, registers, memory, prev_pc):
            if hasattr(hooks, 'on_interrupt'):
                hooks.on_interrupt(self, prev_pc)
            return super().accept_interrupt(registers, memory, prev_pc)
    return S


def play_rzx(path, hooks, stop=None):
    """Replay an RZX (autosave snapshots stripped to a temp copy first) with the hooks.
    Returns the number of frames played."""
    import skoolkit.rzxplay as rz
    from skoolkit.snapshot import Snapshot
    from . import rzx as RZ
    tmp = None
    if sum(1 for b in rz.parse_rzx(path) if isinstance(b.obj, Snapshot)) > 1:
        fd, tmp = tempfile.mkstemp(suffix='.rzx')
        os.close(fd)
        RZ.strip(path, tmp)
        path = tmp
    n = [0]
    old = rz.Simulator, rz.CSimulator, rz.RZXTracer.next_frame
    nf = rz.RZXTracer.next_frame

    def next_frame(self):
        n[0] += 1
        if hasattr(hooks, 'on_frame'):
            hooks.on_frame(n[0])
        return nf(self)
    rz.Simulator, rz.CSimulator, rz.RZXTracer.next_frame = _sim_class(hooks), None, next_frame
    try:
        rz.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                (['--stop', str(stop)] if stop else []) + [path])
    except SystemExit:
        pass
    finally:
        rz.Simulator, rz.CSimulator, rz.RZXTracer.next_frame = old
        if tmp:
            os.remove(tmp)
    return n[0]


def free_run(z80, frames, hooks, keys=None, stop_pc=None):
    """Run a snapshot for `frames` frames (interrupts each frame, keys from parse_keys schedule,
    Kempston idle unless K: keys), no recording. Stops early at PC == stop_pc. Returns
    (frames run, simulator)."""
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot, PC, T, IFF
    s = Snapshot.get(z80)
    ft = FRAME_T['128K' if len(s.ram(-1)) == 0x20000 else '48K']
    sim = from_snapshot(_sim_class(hooks), s, config={'int_active': 0})
    mem, R, ops = sim.memory, sim.registers, sim.opcodes
    sched = parse_keys(keys) if isinstance(keys, str) else (keys or [])
    st = {'held': set()}
    from skoolkit.pagingtracer import Memory

    class Tr:
        border, outfe, outfffd, ay = s.border, s.border, 0, [0] * 16
        out7ffd = getattr(mem, 'o7ffd', 0)

        def read_port(self, regs, port):
            if port & 0xFF == 0x1F:
                return sum(v for k, v in KEMPSTON.items() if k in st['held'])
            v = 0xFF
            if port & 1 == 0:
                for row, ks in ROWS.items():
                    if (port >> 8) & (row ^ 0xFF) == 0:
                        for i, k in enumerate(ks):
                            if k in st['held']:
                                v &= ~(1 << i)
            return v

        def write_port(self, regs, port, value, offset=0):
            if port & 1 == 0:
                self.border, self.outfe = value & 7, value
            if port & 0x8002 == 0 and self.out7ffd & 32 == 0 and isinstance(mem, Memory):
                mem.out7ffd(value)
                self.out7ffd = value
    sim.set_tracer(Tr())
    for f in range(frames):
        st['held'] = held_at(sched, f)
        while R[T] < ft:
            if stop_pc is not None and R[PC] == stop_pc:
                return f, sim
            ops[mem[R[PC]]]()
        R[T] -= ft
        if hasattr(hooks, 'on_frame'):
            hooks.on_frame(f + 1)
        if R[IFF]:
            if mem[R[PC]] == 0x76:
                R[PC] = (R[PC] + 1) & 0xFFFF
            sim.accept_interrupt(R, mem, 0)
    return frames, sim


def run(z80, rzx=None, hooks=None, frames=None, keys=None, stop=None):
    """One entry point: each RZX in `rzx` (list) is played (stop = frames per RZX); without an
    RZX the snapshot free-runs `frames` frames (default 500) with `keys`. Returns frames run."""
    if rzx:
        return sum(play_rzx(r, hooks, stop or frames) for r in rzx)
    return free_run(z80, frames or 500, hooks, keys)[0]


def addr_view(snap):
    """64K list of the snapshot's address space (ROM zeros; 128K: banks 5, 2, out7ffd & 7)."""
    ram = snap.ram(-1)
    if len(ram) == 0x20000:
        b = [ram[k:k + 0x4000] for k in range(0, 0x20000, 0x4000)]
        return [0] * 0x4000 + list(b[5]) + list(b[2]) + list(b[snap.out7ffd & 7])
    return [0] * 0x4000 + list(ram)


def disasm(mem, addr):
    """(text, length) of the instruction at addr in a 64K list."""
    from types import SimpleNamespace
    from skoolkit.disassembler import Disassembler
    cfg = SimpleNamespace(defb_size=8, defm_size=65, defw_size=1, handle_rst=False, wrap=False,
                          opcodes='', asm_hex=False, asm_lower=False,
                          imaker=lambda a, o, b: SimpleNamespace(address=a, operation=o, bytes=b))
    i = Disassembler(mem, cfg).disassemble(addr, addr + 1, 'n')[0]
    return i.operation, len(i.bytes)
