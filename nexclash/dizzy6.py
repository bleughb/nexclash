"""Dizzy 6 / Prince of the Yolkfolk ('tid_mirror'): TID engine with a second, mirrored copy of the
player plotted by an actor handler through the same plotter/eraser, using its own undo buffer
(pointer at prof['undo_ptr']).

Design: the player path is the generic TID slot-1 patch (build.TidPatch). The mirrored copy must
stay on the ULA screen, but the generic patch NOPs the plotter's/eraser's screen writes and hooks
the eraser entry. So an UNPATCHED copy of plotter+eraser is placed at 0x2000 in the slot-1 page and
the actor's two calls (plot CALL, erase CALL) are redirected to it. The copy keeps using the
original variables; only its 3 internal absolute references are relocated (2 JP NZ, and the
eraser's self-modifying LD (nn),A, which then writes the copy's own operand in the page).
Tail: the player's undo buffer (every plot writes it before the eraser reads it; proven per RZX).
"""
import collections

from . import build as B

COPY_ORG = 0x2000
_ABS_OPS = {0xC3, 0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA, 0xCD, 0x32, 0x3A, 0x22, 0x2A, 0x01, 0x11, 0x21}


def _w(m, a):
    return m[a] | m[a + 1] << 8


def layout(prof, m):
    """Copy range, relocations and mirror call sites, all from the snapshot bytes."""
    P, E, sp = prof['plotter'], prof['eraser'], prof['eraser_spsave']
    tail = bytes([0xED, 0x7B, sp & 255, sp >> 8, 0xFB, 0xC9])      # LD SP,(spsave) / EI / RET
    end = bytes(m).find(tail, E) + len(tail)
    assert E < end < E + 80, 'eraser end not found'
    rel = [a - P for a in range(P + 1, end - 1) if m[a - 1] in _ABS_OPS and P <= _w(m, a) < end]
    ptr = prof['undo_ptr']
    call_e = bytes([0xCD, E & 255, E >> 8])
    mer = [a for a in range(0x4000, 0xFFF8) if bytes(m[a:a + 3]) == call_e
           and bytes(m[a - 4:a]) == bytes([0xED, 0x43, ptr & 255, ptr >> 8])]
    assert len(mer) == 1, 'mirror erase call not unique: %s' % mer
    return {'start': P, 'end': end, 'reloc': rel, 'plot_call': prof['plot_site2'], 'erase_call': mer[0]}


def relocated_copy(m, lay):
    P, n = lay['start'], lay['end'] - lay['start']
    b = bytearray(m[P:P + n])
    for r in lay['reloc']:
        v = b[r] | b[r + 1] << 8
        v += COPY_ORG - P
        b[r:r + 2] = bytes([v & 255, v >> 8])
    return bytes(b)


class Dizzy6Patch(B.TidPatch):
    def __init__(self, prof, mem, tail_addr, undo_size):
        super().__init__(prof, 'slot1', tail_addr)
        self.name = 'TID-engine hardware sprite (slot1) + unpatched mirror copy (Dizzy 6)'
        self.lay = layout(prof, mem)
        self.copy = relocated_copy(mem, self.lay)
        E, P = prof['eraser'], prof['plotter']
        ce = COPY_ORG + E - P
        self.copy_plot, self.copy_erase = COPY_ORG, ce
        self.sites += [(self.lay['plot_call'], bytes([0xCD, P & 255, P >> 8]), bytes([0xCD, COPY_ORG & 255, COPY_ORG >> 8])),
                       (self.lay['erase_call'], bytes([0xCD, E & 255, E >> 8]), bytes([0xCD, ce & 255, ce >> 8]))]
        self.undo_size = undo_size

    def apply(self, snap):
        ram = snap.banks[5] + snap.banks[2] + snap.banks[0]
        P = self.lay['start']
        assert bytes(ram[P - 0x4000:P - 0x4000 + len(self.copy)]) == relocated_copy_src(ram, self.lay), 'plotter bytes changed'
        super().apply(snap)
        if self.tail_addr is not None:
            self.max_tail = self.undo_size
        org = B.T['slot1']['org']
        assert COPY_ORG + len(self.copy) <= org
        page = bytearray(self.page)
        assert not any(page[0:len(self.copy)])
        page[0:len(self.copy)] = self.copy
        self.page = bytes(page)
        self.extra_banks[12] = self.page + bytes(8192)


def relocated_copy_src(ram, lay):
    """The unrelocated source bytes as they sit in 48K RAM (bank 5,2,0 order)."""
    P = lay['start']
    return bytes(ram[P - 0x4000:P - 0x4000 + lay['end'] - P])


def first_access(rzx_path, lo, hi):
    """'.', 'r', 'w' per byte in [lo, hi): first access over the whole recording."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G = list.__getitem__
    FA = bytearray(hi - lo)
    REG = [None]

    class Mem(list):
        def __getitem__(s, a):
            if REG[0] is not None and type(a) is int and lo <= a < hi and not FA[a - lo]:
                FA[a - lo] = 1
            return G(s, a)

        def __setitem__(s, a, v):
            if REG[0] is not None and type(a) is int and lo <= a < hi and not FA[a - lo]:
                FA[a - lo] = 2
            list.__setitem__(s, a, v)

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            super().__init__(Mem(memory), registers, state, config)
            REG[0] = self.registers
    old = rzxplay.Simulator, rzxplay.CSimulator
    rzxplay.Simulator, rzxplay.CSimulator = S, None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0', rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.Simulator, rzxplay.CSimulator = old
        REG[0] = None
    return ''.join('.rw'[x] for x in FA)


_RW = []


def _rw_simulator():
    """SkoolKit Simulator whose writes below 0x4000 are NOT dropped (slot-1 RAM page). Built once per
    process: compiling the patched simulator source costs ~30 ms, and some verifiers asked for it per
    patched call (Target Renegade: twice per event). No engine modifies the class."""
    if not _RW:
        _RW.append(_rw_simulator_())
    return _RW[0]


def _rw_simulator_():
    import skoolkit.simulator as sm
    import types
    src = open(sm.__file__).read().replace('> 0x3FFF', '>= 0')
    mod = types.ModuleType('sim_rw')
    mod.__dict__['__name__'] = 'sim_rw'
    exec(compile(src, 'sim_rw', 'exec'), mod.__dict__)
    return mod.Simulator


def mirror_selftest(prof, patch, orig_mem, patched_mem, heights=(80, 120, 160, 184), xs=(2, 14, 30, 46, 56)):
    """Differential test of the mirror path: original plotter/eraser (orig_mem) vs the copy in the
    slot-1 page (patched_mem), every frame the actor can use x several positions: plot, then erase.
    Compares all RAM 0x4000-0xFFFF (except patch sites, the original's self-modified operand) and
    registers (except R). Returns (cases, [mismatch examples])."""
    Sim = _rw_simulator()
    from skoolkit.simutils import SP as RSP
    P, E = prof['plotter'], prof['eraser']
    ptr, ub2 = prof['undo_ptr'], None
    lay = patch.lay
    # the mirror buffer the actor installs: LD BC,nn just before the erase call's LD (ptr),BC
    a = lay['erase_call'] - 7
    assert orig_mem[a] == 0x01
    ub2 = _w(orig_mem, a + 1)
    tbl = _w(orig_mem, lay['plot_call'] - 13)        # LD IY,table (frame map)
    assert orig_mem[lay['plot_call'] - 15:lay['plot_call'] - 13] == [0xFD, 0x21], 'frame map not found'
    frames = sorted({orig_mem[tbl + f] for f in range(39)})
    skip = {x for s, old, new in patch.sites for x in range(s, s + len(new))}
    skip |= {P + r for r in lay['reloc']} | {P + r + 1 for r in lay['reloc']}
    smod = _w(orig_mem, E + 12)
    skip |= {smod, smod + 1}
    RET, SPV = lay['plot_call'] + 3, 0xFF00
    bad, n = [], 0

    def run(mem, entry, regs, stop):
        m = list(mem)
        m[SPV - 2], m[SPV - 1] = stop & 255, stop >> 8
        s = Sim(m, {'PC': entry, 'SP': SPV - 2, **regs})
        s.run(stop=stop)
        assert s.registers[RSP] == SPV, 'stack unbalanced after %d' % entry
        return s

    for f in frames:
        for x in xs:
            for y in heights:
                n += 1
                res = []
                for mem, pe, ee in ((orig_mem, P, E), (patched_mem, patch.copy_plot, patch.copy_erase)):
                    m = list(mem)
                    m[ptr], m[ptr + 1] = ub2 & 255, ub2 >> 8
                    s1 = run(m, pe, {'A': f, 'E': x, 'L': y}, RET)
                    m2 = s1.memory
                    after_plot = list(m2[0x4000:0x10000])
                    s2 = run(m2, ee, {}, RET)
                    res.append((after_plot, list(s2.memory[0x4000:0x10000]), list(s1.registers), list(s2.registers)))
                (p0, e0, r0, q0), (p1, e1, r1, q1) = res
                for tag, u, v in (('plot', p0, p1), ('erase', e0, e1)):
                    d = [i + 0x4000 for i in range(len(u)) if u[i] != v[i] and i + 0x4000 not in skip]
                    if d:
                        bad.append((tag, f, x, y, d[:4]))
                for tag, u, v in (('plot regs', r0, r1), ('erase regs', q0, q1)):
                    d = [i for i in range(len(u)) if u[i] != v[i] and i not in (15, 24, 25)]   # R, PC (stop), T
                    if d:
                        bad.append((tag, f, x, y, d))
    return n, bad[:8]
