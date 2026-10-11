"""One analysis pass over an RZX for a TID-engine profile (Python simulator, memory hooks)."""
import collections
import skoolkit.rzxplay as rzxplay
from skoolkit.simulator import Simulator
from skoolkit.snapshot import Snapshot

G = list.__getitem__


def classify(mem, pc):
    """How a screen write at pc combines with the old byte: ('xor',), ('keep', mask) or ('over',)."""
    op = G(mem, pc)
    if op == 0x77:
        prev = G(mem, (pc - 1) & 0xFFFF)
        if prev == 0xAE:
            return ('xor',)
        if 0x80 <= prev <= 0x87 or 0xB0 <= prev <= 0xB7:
            for a in range(pc - 24, pc - 2):
                if G(mem, a & 0xFFFF) == 0x7E and G(mem, (a + 1) & 0xFFFF) == 0xE6:
                    return ('keep', G(mem, (a + 2) & 0xFFFF))
    return ('over',)


def apply_write(P, a, old, v, cls):
    i = a - 0x4000
    if cls[0] == 'xor':
        P[i] ^= (v ^ old)
    elif cls[0] == 'keep':
        P[i] = (P[i] & cls[1]) | (v & ~cls[1] & 0xFF)
    else:
        P[i] = v


class _State:
    pass


def analyse(prof, rzx_path, z80_sp, stop=None, progress=None):
    """prof=None: access scan only (free memory, ROM use, stack low-water)."""
    if prof:
        P0, E0 = prof['plotter'], prof['eraser']
        player = (P0, E0 + 53)
        events = {prof['plot_site']: 'plot', E0: 'erase', prof['wipe']: 'wipe', prof['isr_hide_call']: 'isr'}
        if prof.get('box'):
            events[prof['box']] = 'box'
        pt = prof['pixel_test']
        PT = {pt + 8: 0xF0, pt + 13: 0x0F}
        sites = set()
        for k in ('plot_site', 'eraser', 'wipe', 'isr_hide_call', 'box'):
            if prof.get(k):
                sites.update(range(prof[k], prof[k] + 4))
        sites.update(prof['plotter_writes'] + prof['eraser_writes'])
    else:
        P0 = E0 = -1
        player = (-1, -1)
        events, PT, sites = {}, {}, set()
    st = _State()
    st.P = None; st.drawn = False; st.synced = False
    c = collections.Counter(); diffw = collections.Counter(); diffr = collections.Counter()
    RD = bytearray(65536); WR = bytearray(65536); ccache = {}
    REG = [None]

    class Mem(list):
        def __getitem__(s, a):
            R = REG[0]
            if type(a) is int and R is not None:
                RD[a] = 1
                pc = R[24]
                if a == pc and a in events:
                    k = events[a]
                    if st.synced:
                        c[(k, 'drawn' if st.drawn else 'not drawn')] += 1
                    if k == 'wipe':
                        st.drawn = False
                        st.synced = True
                        st.P = [G(s, x) for x in range(0x4000, 0x5800)]
                elif prof and st.synced and 0x4000 <= a < 0x5800 and not (player[0] <= pc < player[1]):
                    if pc in PT and a != pc:
                        m = PT[pc]
                        c['pixel tests'] += 1
                        if bool(G(s, a) & m) != bool(st.P[a - 0x4000] & m):
                            c['PIXEL TESTS THAT DEPEND ON THE PLAYER'] += 1
                    elif G(s, a) != st.P[a - 0x4000] and a != pc:
                        diffr[pc] += 1
            return G(s, a)

        def __setitem__(s, a, v):
            R = REG[0]
            if R is not None and type(a) is int:
                WR[a] = 1
                if a in sites:
                    c['WRITES TO PATCH SITES'] += 1
                if prof and 0x4000 <= a < 0x5800 and st.synced:
                    pc = R[24]
                    if player[0] <= pc < E0:
                        st.drawn = True
                    elif E0 <= pc < player[1]:
                        st.drawn = False
                    else:
                        old = G(s, a)
                        key = (pc, G(s, (pc - 1) & 0xFFFF))
                        cls = ccache.get(key) or ccache.setdefault(key, classify(s, pc))
                        if st.P[a - 0x4000] != old:
                            diffw[(pc, cls[0])] += 1
                        apply_write(st.P, a, old, v, cls)
            list.__setitem__(s, a, v)

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            super().__init__(Mem(memory), registers, state, config)
            REG[0] = self.registers
            st.synced = False
            st.drawn = False

    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0']
    if stop:
        args += ['--stop', str(stop)]
    try:
        rzxplay.main(args + [rzx_path])
    except SystemExit:
        pass
    REG[0] = None
    # stack low-water mark below the snapshot's SP (contiguous stack writes)
    low, a, gap = z80_sp, z80_sp - 1, 0
    while a > z80_sp - 1024 and gap < 8:
        if WR[a]:
            low, gap = a, 0
        else:
            gap += 1
        a -= 1
    rom_reads = sum(RD[1:0x4000])
    pb_touched = any(RD[x] or WR[x] for x in range(0x5B00, 0x5C00))
    return {
        'events': {'%s (%s)' % k if isinstance(k, tuple) else k: n for k, n in sorted(c.items(), key=str)},
        'writes_where_screens_differ': [(pc, cls, n) for (pc, cls), n in diffw.most_common(8)],
        'reads_where_screens_differ': diffr.most_common(6),
        'virtual_read_needed': c['PIXEL TESTS THAT DEPEND ON THE PLAYER'] > 0,
        'rom_used': rom_reads > 0, 'printer_buffer_touched': pb_touched,
        'stack_low_water': low, 'self_modified_sites': c['WRITES TO PATCH SITES'],
        'rd': RD, 'wr': WR,
    }
