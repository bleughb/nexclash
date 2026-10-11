"""Differential test of a built TidPatch against an RZX: at every patched routine the original
and patched code run from the same real state; registers, memory, the patched-screen model and
the sprite pixels are compared."""
import collections
import skoolkit.rzxplay as rzxplay
from skoolkit.simulator import Simulator, R2
from .analyse import classify, apply_write

G = list.__getitem__
REGS = list(range(0, 13)) + [14] + list(range(16, 24)) + [26, 27]


class _Rec(list):
    P = None
    R = None

    def __setitem__(s, a, v):
        if s.P is not None and type(a) is int and 0x4000 <= a < 0x5800 and not (s.lo <= s.R[24] < s.hi):
            apply_write(s.P, a, G(s, a), v, classify(s, s.R[24]))
        list.__setitem__(s, a, v)


class _M:
    def __init__(self, rec, hook):
        self.mem = _Rec([0] * 65536) if rec else [0] * 65536
        self.sim = Simulator(self.mem)
        self.R = self.sim.registers
        if rec:
            self.mem.R = self.R
        self.nr = {}
        self.attrs = collections.defaultdict(lambda: [0] * 5)
        self.sel = 0
        self.slot0 = 0xFF
        self.hook0 = hook
        ed = self.sim.after_ED
        R, mem, me = self.R, self.mem, self

        def nextreg(reg, val):
            me.nr[reg] = val
            if reg == 0x50:
                if me.slot0 != 0xFF:
                    me.hook = list(mem[0:8192])
                list.__setitem__(mem, slice(0, 8192), me.rom if val == 0xFF else me.hook)
                me.slot0 = val
            elif reg == 0x34:
                me.sel = val & 0x7F
            elif 0x35 <= reg <= 0x39:
                me.attrs[me.sel][reg - 0x35] = val

        def nn():
            pc = R[24]
            nextreg(mem[(pc + 2) % 65536], mem[(pc + 3) % 65536])
            R[15] = R2[R[15]]; R[25] += 20; R[24] = (pc + 4) % 65536

        def na():
            pc = R[24]
            nextreg(mem[(pc + 2) % 65536], R[0])
            R[15] = R2[R[15]]; R[25] += 17; R[24] = (pc + 3) % 65536
        ed[0x91] = nn
        ed[0x92] = na

        class Tr:
            sel = 0

            def read_port(s, regs, port):
                return me.nr.get(Tr.sel, 0) if port == 0x253B else 0xFF

            def write_port(s, regs, port, value, *x):
                if port == 0x243B:
                    Tr.sel = value
        self.sim.set_tracer(Tr())

    def load(self, mm, regs):
        list.__setitem__(self.mem, slice(0, 65536), mm)
        self.R[:] = regs
        self.slot0 = 0xFF
        self.rom = mm[0:8192]
        self.hook = list(self.hook0)

    def run(self, ret_pc, ret_sp, limit=3000000):
        R, mem, ops, n = self.R, self.mem, self.sim.opcodes, 0
        while not (R[24] == ret_pc and R[12] == ret_sp):
            ops[mem[R[24]]]()
            n += 1
            if n > limit:
                raise RuntimeError('routine did not return (%d)' % ret_pc)


def _ypix(a):
    return ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)


def verify(prof, patch, rzx_path, stop=None):
    U = prof['undo_buffer']
    lo, hi = prof['plotter'], prof['eraser'] + 53
    sites = [(a, new) for a, old, new in patch.sites]
    excl = set()
    for a, new in sites:
        excl.update(range(a, a + len(new)))
    printer = patch.strategy == 'printer'
    if printer:
        code = list(patch.code)
        excl.update(range(0x5B00, 0x5B00 + len(code)))
        hook = list(patch.hook_page_data) + [0] * (8192 - len(patch.hook_page_data))
    else:
        page = list(patch.page)
        hook = [0] * 8192
    pats = patch.extra_banks[11]
    A, B = _M(True, hook), _M(False, hook)
    A.mem.lo, A.mem.hi = lo, hi
    st = {'P': None, 'applied': 0, 'nr15': 0, 'attrs': {}, 'synced': False}
    stats = collections.Counter()
    log = []

    def sprite_px(m):
        out = {}
        if not (m.nr.get(0x15, 0) & 1):
            return out
        for sp in range(4):
            a = m.attrs[sp]
            if not a[3] & 0x80:
                continue
            x = a[0] | ((a[2] & 1) << 8); y = a[1]; p = ((a[3] & 0x3F) << 1) | ((a[4] >> 6) & 1)
            pat = pats[p * 128:(p + 1) * 128]
            for yy in range(16):
                for xx in range(16):
                    b = pat[yy * 8 + xx // 2]
                    c = (b >> 4) if xx % 2 == 0 else (b & 15)
                    if c:
                        out[(x + xx - 32, y + yy - 32)] = c
        return out

    def undo_px(mem):
        col, h, ptr = mem[U], mem[U + 1], mem[U + 2] | mem[U + 3] << 8
        d = {}
        for r in range(h):
            row = mem[ptr + 2 * r] | mem[ptr + 2 * r + 1] << 8
            for k in range(4):
                v = mem[U + 4 + 4 * r + k]
                if v:
                    d[row + col + k] = d.get(row + col + k, 0) ^ v
        return d

    def check(kind, mm, R, pc):
        if kind in ('isr',) or (kind == 'plot' and prof['plot_site_kind'] == 'CALL'):
            ret_pc, ret_sp = pc + 3, R[12]
        else:
            ret_pc, ret_sp = G(mm, R[12]) | G(mm, R[12] + 1) << 8, R[12] + 2
        snap, regs, P0 = list(mm), list(R), list(st['P'])
        A.load(snap, regs); A.mem.P = list(P0)
        B.load(snap, regs)
        for a, new in sites:
            list.__setitem__(B.mem, slice(a, a + len(new)), list(new))
        if printer:
            list.__setitem__(B.mem, slice(0x5B00, 0x5B00 + len(code)), code)
            B.mem[0x5B00] = st['applied']
        else:
            list.__setitem__(B.mem, slice(0x2000, 0x4000), page)
            B.nr[0x7F] = st['applied']
        list.__setitem__(B.mem, slice(0x4000, 0x5800), P0)
        B.nr[0x15] = st['nr15']
        B.attrs = collections.defaultdict(lambda: [0] * 5, {k: list(v) for k, v in st['attrs'].items()})
        A.run(ret_pc, ret_sp); B.run(ret_pc, ret_sp)
        bad = [i for i in REGS if A.R[i] != B.R[i]]
        dead = range(ret_sp - 40, ret_sp)
        md = [a for a in range(0x5800, 65536) if A.mem[a] != B.mem[a] and a not in excl and a not in dead]
        sd = [a for a in range(0x4000, 0x5800) if B.mem[a] != A.mem.P[a - 0x4000]]
        if bad or md or sd:
            if not bad and not sd and all(U <= a < U + 4 + 4 * 32 for a in md) and kind == 'plot' \
                    and any(snap[a] != P0[a - 0x4000] for a in range(0x4000, 0x5800)):
                stats['plot: undo buffer differs (original ghost pixels, harmless)'] += 1
            else:
                stats[kind + ' MISMATCH'] += 1
                if len(log) < 6:
                    log.append((kind, pc, 'regs', bad, 'mem', md[:6], 'screen', sd[:6]))
        else:
            stats[kind + ' ok'] += 1
        st['applied'] = B.mem[0x5B00] if printer else B.nr.get(0x7F, 0)
        st['nr15'] = B.nr.get(0x15, 0)
        st['attrs'] = {k: list(v) for k, v in B.attrs.items()}
        vis = bool(st['nr15'] & 1)
        if kind == 'plot':
            sp = sprite_px(B)
            miss = wrong = 0
            for a, v in undo_px(A.mem).items():
                y = _ypix(a); x0 = (a & 31) * 8
                for bit in range(8):
                    if (v >> (7 - bit)) & 1 and (x0 + bit, y) not in sp:
                        miss += 1
            for (x, y), c in sp.items():
                a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
                if not (0 <= x < 256 and 0 <= y < 192) or ((A.mem[a] >> (7 - (x & 7))) & 1) != (1 if c == 2 else 0):
                    wrong += 1
            stats['sprite pixel-perfect' if not (miss or wrong) else 'SPRITE PIXEL MISMATCH'] += 1
        elif kind in ('box', 'wipe'):
            stats[kind + (' hides sprite' if not vis else ' LEAVES SPRITE VISIBLE')] += 1
        elif kind == 'isr' and not st['applied'] and vis:
            stats['ISR: SPRITE VISIBLE WHILE ERASED'] += 1

    ev = {prof['plot_site']: 'plot', prof['eraser']: 'erase', prof['wipe']: 'wipe', prof['isr_hide_call']: 'isr'}
    if prof.get('box'):
        ev[prof['box']] = 'box'
    REG = [None]
    last = [None]

    class Mem(list):
        def __getitem__(s, a):
            R = REG[0]
            if type(a) is int and R is not None and a in ev and R[24] == a and last[0] != (a, R[25]):
                last[0] = (a, R[25])
                if ev[a] == 'wipe' and not st['synced']:
                    st['synced'] = True
                    st['P'] = [G(s, x) for x in range(0x4000, 0x5800)]
                    st['applied'] = 0
                if st['synced']:
                    check(ev[a], s, R, a)
            return G(s, a)

        def __setitem__(s, a, v):
            R = REG[0]
            if R is not None and st['synced'] and type(a) is int and 0x4000 <= a < 0x5800 and not (lo <= R[24] < hi):
                apply_write(st['P'], a, G(s, a), v, classify(s, R[24]))
            list.__setitem__(s, a, v)

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            super().__init__(Mem(memory), registers, state, config)
            REG[0] = self.registers
            st['synced'] = False

    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else [])
    try:
        rzxplay.main(args + [rzx_path])
    except SystemExit:
        pass
    REG[0] = None
    failed = any('MISMATCH' in k or 'VISIBLE' in k for k in stats)
    return {'passed': not failed and sum(stats.values()) > 0, 'stats': dict(stats), 'examples': log}
