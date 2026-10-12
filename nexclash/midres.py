"""Midnight Resistance (Ocean 1990, 128K) engine 'midres'. Additive module: reachable only through
is_midres(). Game facts and decisions: games/midnight_resistance.md. Hooks: asm/midres_hooks.asm.

The game composes each game frame in a back buffer (0x5B00-0x6AFF, attrs 0x6B00) and copies it to
the screen. The patch replaces the target of the CALL 0x7EC1 (buffer address) in five figure
plotters: a converted figure is recorded and its plot runs into a scratch copy of the buffer
(Next RAM page 26 at 0xA000 = buffer + 0x4500); the commit after the screen copy builds the sprites.
Converted: the player (green), enemy soldiers / gun turrets (white), black outline; the jeep and
the end-of-level tank in the colours of their attribute cells. Everything else stays on the ULA.
"""
import collections
import copy
import json
import os

from .rainbow import NextState, _machine, _run, boot_check as _rb_boot_check, _BankMem

PAGE_S = 26
ALT_PAGE = 24
OFS = 0x4500
PAGE_LO = 0x2000                 # alt ROM block: tables 0x2000-0x24FF, code from 0x2500
NIBTAB, FIX, INKI, PAPI, ROM_ORG = 0x2000, 0x2200, 0x2300, 0x2400, 0x2500
MAXF, MAXT, CBLACK = 32, 64, 8
BUF = (0x5B00, 0x6B00)
ATTR = 0x6B00
CLIP = (24, 231, 0, 127)         # sprite clip window (ULA x 24-231, y 0-127)
# page 26 (0xA000-0xBFFF while a hook runs): variables at 0xB000 (offsets in the page)
P_NF, P_NT, P_PREV, P_PAR, P_N, P_LIVE = 0x1004, 0x1005, 0x1006, 0x1007, 0x1008, 0x100A
P_FIG, P_SPR = 0x1100, 0x1300

# CALL 0x7EC1 sites (operand bytes replaced) and loop exits (JP to ROM)
CALL_SITES = {0x97E5: 'c_m', 0x981E: 'c_mf', 0x7DC6: 'c_o', 0x9EF0: 'c_p', 0x9F45: 'c_pm'}
EXIT_SITES = {0x980F: ('C2EA97', 'x_m'), 0x9861: ('C22898', 'x_mf'), 0x7DE5: ('C2CA7D', 'x_o'),
              0x9F3D: ('10B8C9', 'x_p'), 0x9FB7: ('1096D9', 'x_pm'),
              0x8950: ('ED5BEE', 'e_cm'), 0x8993: ('3A70FF', 'e_q')}
KIND = {0x97E5: 0, 0x981E: 1, 0x7DC6: 2, 0x9EF0: 4, 0x9F45: 5}
# patched blocks (JP over these bytes): an address inside a block other than its start may be a PC
# in the ORIGINAL run only as the next instruction of the same block (DJNZ falling through to RET /
# EXX); instruction interiors never
BLOCKS = {0x980F: 3, 0x9861: 3, 0x7DE5: 3, 0x9F3D: 3, 0x9FB7: 3, 0x8950: 4, 0x8993: 3}
FALLTHROUGH = {0x9F3F: 0x9F3D, 0x9FB9: 0x9FB7}           # instruction start -> previous instruction
INTERIORS = tuple(a + k for a, n in BLOCKS.items() for k in range(1, n) if a + k not in FALLTHROUGH)
PLAYER, SOLDIERS, TANK_P = (0x9E04, 0x9E0C), (0xA4F2, 0xA504), (0xDEB2,)
VEHICLES = (0xE395, 0xE3AE, 0xE3A1, 0xDEDF, 0xDEEA, 0xDEF9, 0xDF28, 0xDF34)
# Next palette (RRRGGGBB): index 0 transparent, 1-7 colours, 8 black, 9-15 bright colours
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
CMP = list(range(0, 15)) + list(range(16, 25)) + [26, 27, 28]   # all but R, T, MEMPTR (AF' included)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'midnight_resistance.json'),
              os.path.join(_HERE, 'midnight_resistance.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('midnight_resistance.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def cidx(c, bright):
    return CBLACK if c == 0 else c + 8 * bright


def ink_of(attr):
    return cidx(attr & 7, (attr >> 6) & 1)


def paper_of(attr):
    return cidx((attr >> 3) & 7, (attr >> 6) & 1)


def nibtab(swap=False):
    """(G nibble << 4 | M nibble) -> 2 bytes of pixel codes: 1 ink, 2 paper (mask 0), 0 clear."""
    t = bytearray(512)
    ink, pap = (2, 1) if swap else (1, 2)
    for i in range(256):
        g, m = i >> 4, i & 15
        px = [ink if g & b else (0 if m & b else pap) for b in (8, 4, 2, 1)]
        t[i] = px[0] << 4 | px[1]
        t[256 + i] = px[2] << 4 | px[3]
    return bytes(t)


def tables(swap=False):
    fix = bytes((d - 0x45) if 0xA0 <= d <= 0xB1 else d for d in range(256))
    return {NIBTAB: nibtab(swap), FIX: fix, INKI: bytes(ink_of(a) for a in range(256)),
            PAPI: bytes(paper_of(a) for a in range(256))}


def identify_midres(mem):
    sg = load_profile()['signature']
    a, sig = sg['addr'], bytes.fromhex(sg['bytes'])
    return bytes(mem[a:a + len(sig)]) == sig


def mem64(snap):
    b = snap.memory.banks
    return bytes(16384) + bytes(b[5]) + bytes(b[2]) + bytes(b[0])


def is_midres(snap):
    try:
        return snap.machine != '48K' and identify_midres(mem64(snap))
    except FileNotFoundError:
        return False


def static_check(code, org, data_ranges=()):
    """Hook code must never write IX/IY/I or IFF (interrupts are on at every hook site): no DD/FD
    prefix, DI, EI, LD I,A, IM, RETI/RETN in the code bytes (data ranges excluded)."""
    from .simrun import disasm
    mem = [0] * 65536
    mem[org:org + len(code)] = code
    bad, a = [], org
    while a < org + len(code):
        if any(lo <= a < hi for lo, hi in data_ranges):
            a = next(hi for lo, hi in data_ranges if lo <= a < hi)
            continue
        op = mem[a]
        t, n = disasm(mem, a)
        if op in (0xDD, 0xFD, 0xF3, 0xFB) or (op == 0xED and mem[a + 1] in (0x47, 0x46, 0x56, 0x5E, 0x4D, 0x45)):
            bad.append((hex(a), t))
        a += n
    return bad


class MidresPatch:
    name = 'Midnight Resistance figures (player, soldiers, vehicles) -> hardware sprites (altrom + page 26 at slot 5)'

    def __init__(self, prof=None, swap=False, edit=None):
        """swap: negative control (ink and outline codes swapped in NIBTAB); edit: {ROM address:
        bytes} written over the hook code (negative control of the interrupt-safety check)."""
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.setup = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = self.setup + bytes(PALETTE)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = None
        self.max_tail = 80
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long (must end below the font at 0x3D00)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (PAGE_LO, self.regblock + 20)
        from .build import rom48
        page = bytearray(rom48()[0x2000:0x4000])
        for a, d in tables(swap).items():
            page[a - 0x2000:a - 0x2000 + len(d)] = d
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        for a, d in (edit or {}).items():
            page[a - 0x2000:a - 0x2000 + len(d)] = d
        self.page = bytes(page)
        self.scratch = bytes(8192)              # page 26: all state zero at start
        self.extra_banks = {12: self.page + bytes(8192), 13: self.scratch + bytes(8192)}
        self.sites = [(a, bytes.fromhex('CDC17E'), b'\xCD' + self.syms[s].to_bytes(2, 'little'))
                      for a, s in CALL_SITES.items()]
        self.sites += [(a, bytes.fromhex(o), b'\xC3' + self.syms[s].to_bytes(2, 'little'))
                       for a, (o, s) in EXIT_SITES.items()]

    @staticmethod
    def _bank_of(a):
        return (5, 2, 0)[(a >> 14) - 1]

    def check_sites(self, banks):
        for a, old, new in self.sites:
            b = banks[self._bank_of(a)]
            cur = bytes(b[(a & 0x3FFF):(a & 0x3FFF) + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('Midnight Resistance patch expects the 128K snapshot')
        if snap.port7ffd & 0x17 != 0x10:
            raise ValueError('snapshot must select ROM 1 (48K BASIC) and bank 0 at C000')
        self.check_sites(snap.banks)
        for a, old, new in self.sites:
            k = self._bank_of(a)
            b = bytearray(snap.banks[k])
            b[(a & 0x3FFF):(a & 0x3FFF) + len(new)] = new
            snap.banks[k] = bytes(b)

    def alt_image(self):
        from .build import rom48
        alt = bytearray(rom48())
        alt[0x2000:0x4000] = self.page
        return alt


def boot_check(nex, z80, patch=None):
    from . import z80tonex as zt
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch.apply(s)
    tail = build_tail_range(s, patch)
    return _rb_boot_check(nex, z80, patch, tail=tail)


def build_tail_range(s, patch):
    from . import z80tonex as zt
    slot1 = getattr(patch, 'slot1', None) if patch else None
    altrom = getattr(patch, 'altrom', None) if patch else None
    probe = zt.build_tail(s, 0x8000, slot1, altrom is not None)[0]
    a, _ = zt.choose_tail_addr(s, len(probe), None, bool(patch and patch.uses_printer_buffer))
    return a, a + len(probe)


# ---------------------------------------------------------------------------------------------
# Python model of the hook's decision (unit tests compare against it)
# ---------------------------------------------------------------------------------------------

def model_decide(kind, get, R, sp, page):
    """-> None (pass) or dict(W, R, X, Y, fl, col, gfx). get(a) = game memory, R = registers at the
    CALL site, sp = SP at the CALL site (before the CALL), page = page-26 bytes."""
    w16 = lambda a: get(a) | get((a + 1) & 0xFFFF) << 8
    if not page[0x100A]:
        return None
    nf, nt = page[0x1004], page[0x1005]
    if nf >= MAXF:
        return None
    d, e, b, c = R[4], R[5], R[2], R[3]
    if d >= 128:
        return None
    gfx, caller = w16(sp), w16(sp + 2)
    if kind & 4:
        if caller in PLAYER:
            col = 12
        elif caller in SOLDIERS:
            col = 15
        elif caller in TANK_P:
            col = 0
        else:
            return None
        w = 4
        cnt, opa = (0x9F4E, 0x9F55) if kind & 1 else (0x9EF6, 0x9EFA)
        n = get(cnt)
        if n == 0 or n > 24:
            return None
        rows = 2 * n
        op = get(opa)
        if op not in (0x00, 0xB6):
            return None
        fl = (kind & 1) | (4 if op == 0 else 0)
    else:
        if caller not in VEHICLES:
            return None
        col = 0
        if b == 0 or b > 8 or c == 0 or c > 24:
            return None
        w, rows, fl = b, 2 * c, kind & 3
        chk = {0: ((0x97F7, 0x9809), (0x97EE, 0x9800)), 1: ((0x983E, 0x9859), (0x982F, 0x984B)),
               2: ((0x7DD3, 0x7DE0), ())}[fl]
        if any(w16(a) != 32 for a in chk[0]) or any(get(a) != 0xB6 for a in chk[1]):
            return None
    col0 = (e >> 3) & 31
    x = col0 - (w - 1) if fl & 1 else col0
    if fl & 1:
        if x < -3:
            return None
    elif x + w - 1 > 34:
        return None
    a0 = 0x5B00 + d * 32 + x
    if a0 < 0x5B00 or a0 + (rows - 1) * 32 + w - 1 >= 0x6B00:
        return None
    ln = rows * w * (1 if fl & 2 else 2)
    end = gfx + ln
    if end > 0xFFFF or (end > 0xA000 and gfx < 0xC000):
        return None
    tiles = ((w + 1) >> 1) * ((rows + 15) >> 4)
    if nt + tiles > MAXT:
        return None
    return dict(W=w, R=rows, X=x, Y=d, fl=fl, col=col, gfx=gfx, a0=a0, tiles=tiles)


# ---------------------------------------------------------------------------------------------
# Paired runs: original vs patched from one state
# ---------------------------------------------------------------------------------------------

class _Orig:
    def __init__(s, get, fill=None):
        s.get, s.ov, s.fill = get, {}, fill

    def __getitem__(s, a):
        v = s.ov.get(a)
        if v is not None:
            return v
        if s.fill is not None and BUF[0] <= a < BUF[1]:
            return s.fill
        return s.get(a)

    def __setitem__(s, a, v):
        if a >= 0x4000:
            s.ov[a] = v

    def __len__(s):
        return 65536


class _Patched(_Orig):
    def __init__(s, get, patch, ns, alt, psite, err):
        super().__init__(get)
        s.ns, s.alt, s.psite, s.err = ns, alt, psite, err

    def _paged(s, a):
        return 0xA000 <= a < 0xC000 and s.ns.nr.get(0x55) == PAGE_S

    def __getitem__(s, a):
        if a < 0x4000:
            return s.alt[a]
        if s._paged(a):
            return s.ns.scratch[a - 0xA000]
        v = s.psite.get(a)
        if v is not None and a not in s.ov:
            return v
        return _Orig.__getitem__(s, a)

    def __setitem__(s, a, v):
        if a < 0x4000:
            if s.ns.R is not None and s.ns.R[24] < 0x4000:
                s.err.append(('hook wrote ROM', a))
        elif s._paged(a):
            s.ns.scratch[a - 0xA000] = v
        else:
            s.ov[a] = v


def new_state(patch):
    ns = NextState(patch)
    ns.nr[0x55] = 5
    ns.nr[0x54] = 4
    return ns


def _sim():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def pair(patch, get, regs, ns, stop, alt, psite, run_orig=True):
    """Run the original (unless run_orig is False) and the patched code from one state until
    stop(registers) is true. Returns (so, o, sp_, p, err)."""
    Sim = _sim()
    err = []
    o = _Orig(get)
    p = _Patched(get, patch, ns, alt, psite, err)
    ns.events = []
    so = None
    if run_orig:
        so = _machine(Sim, o, list(regs), NextState(patch))
        if not _run_until(so, stop):
            err.append('original did not return')
    sp_ = _machine(Sim, p, list(regs), ns)
    if not _run_until(sp_, stop, check=_isafe(sp_, regs, ns, err)):
        err.append('patched did not return')
    if ns.nr.get(0x55) != 5 or ns.nr.get(0x07, 0) != 0:
        err.append(('MMU5 / speed not restored', ns.nr.get(0x55), ns.nr.get(0x07)))
    if any(e[0] == 'in' for e in ns.events):
        err.append('port read in hook')
    return so, o, sp_, p, err


def _run_until(sim, stop, limit=3000000, check=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        if check is not None:
            check()
        n += 1
        if n > limit:
            return False
    return True


ISAFE = {'checked': 0}
HOOK_STACK = (0xB200 + 24, 0xB300)      # room for the ISR's 22 bytes below SP


def _isafe(sim, regs0, ns, err):
    """Interrupt safety after every instruction while the hook is active (PC in the alt ROM, or the
    page mapped at slot 5): an IM 2 interrupt may arrive there. The game's handler needs IX, IY, I
    and the interrupt state unchanged, and room on the stack it lands on: the hook stack (page
    mapped) or the game's own stack at or above the hook site's SP - 4 (the game's plot loops push
    no deeper than the original). No instruction fetch at 0x3D00-0x3DFF (DivMMC trap, BRIEFING A1)."""
    R = sim.registers
    ix, iy, i, iff, sp0 = (regs0[8], regs0[9]), (regs0[10], regs0[11]), regs0[14], regs0[26], regs0[12]
    seen = []

    def chk():
        pc, mapped = R[24], ns.nr.get(0x55) == PAGE_S
        if not (pc < 0x4000 or mapped):
            return
        ISAFE['checked'] += 1
        bad = None
        if (R[8], R[9]) != ix or (R[10], R[11]) != iy:
            bad = 'IX/IY changed'
        elif R[14] != i or R[26] != iff:
            bad = 'I / interrupt state changed'
        elif 0xA000 <= R[12] < 0xC000:
            if not (mapped and HOOK_STACK[0] <= R[12] <= HOOK_STACK[1]):
                bad = 'SP in slot 5 outside the mapped hook stack'
        elif R[12] < sp0 - 4 and R[24] < 0x4000:
            bad = 'SP below the game stack at the hook site'
        elif 0x3D00 <= pc < 0x3E00:
            bad = 'instruction fetch in 0x3D00-0x3DFF'
        if bad and not seen:
            seen.append(bad)
            err.append(('interrupt-unsafe hook: %s' % bad, pc))
    return chk


def truth(get, regs, stop):
    """Pixels of the original plot: run it on a buffer of 0x00 and of 0xFF.
    -> {(x, y): 1 ink / 2 paper} in buffer coordinates (x 0-255, y 0-127)."""
    Sim = _sim()
    outs = []
    for fill in (0x00, 0xFF):
        m = _Orig(get, fill)
        s = _machine(Sim, m, list(regs), NextState(_Dummy))
        _run_until(s, stop)
        outs.append({a: v for a, v in m.ov.items() if BUF[0] <= a < BUF[1]})
    z, f = outs
    px = {}
    for a in z:
        y, xb = divmod(a - 0x5B00, 32)
        for k in range(8):
            bit = 0x80 >> k
            if z[a] & bit:
                px[(xb * 8 + k, y)] = 1
            elif not f.get(a, 0xFF) & bit:
                px[(xb * 8 + k, y)] = 2
    return px


class _Dummy:
    scratch = bytes(8192)


def sprite_layer(ns):
    """Composite of the visible sprites (higher number on top), clipped -> {(x, y): index}."""
    out = {}
    for i in range(128):
        px = ns.sprite_pixels_m(i) if hasattr(ns, 'sprite_pixels_m') else _sprite_pixels(ns, i)
        if not px:
            continue
        for x, y, c in px:
            if c and CLIP[0] <= x <= CLIP[1] and CLIP[2] <= y <= CLIP[3]:
                out[(x, y)] = c
    return out


def _sprite_pixels(ns, i):
    a0, a1, a2, a3, a4 = ns.attr[i]
    if not a3 & 0x80:
        return None
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    mir = a2 & 8
    base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
    out = []
    for j in range(16):
        for k in range(16):
            b = ns.pat[base + j * 8 + k // 2]
            c = (b >> 4) if k % 2 == 0 else (b & 15)
            out.append((x + (15 - k if mir else k), y + j, c))
    return out


def expected_layer(figs, get):
    """figs: [(pixels, col)] in plot order; colours from the attribute buffer at commit (cells)."""
    out = {}
    for px, col in figs:
        for (x, y), code in px.items():
            if not (CLIP[0] <= x <= CLIP[1] and CLIP[2] <= y <= CLIP[3]):
                continue
            if col:
                c = col if code == 1 else CBLACK
            else:
                at = get(ATTR + (y >> 3) * 32 + (x >> 3))
                c = ink_of(at) if code == 1 else paper_of(at)
            out[(x, y)] = c
    return out


def _cmp_regs(so, sp_):
    ro, rp = so.registers, sp_.registers
    return [i for i in CMP if ro[i] != rp[i]]


def _site_maps(patch):
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    return psite


# ---------------------------------------------------------------------------------------------
# Differential verification against an RZX (the replay runs the ORIGINAL game)
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = patch.alt_image()
    psite = _site_maps(patch)
    site_bytes = set(psite)
    st = {'sim': None, 'frame': 0}
    ns = new_state(patch)
    figs = []
    cnt = collections.Counter()
    WATCH = set(CALL_SITES) | set(EXIT_SITES) | set(INTERIORS) | set(FALLTHROUGH)
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class HookMem(Memory):
        def __setitem__(s, a, v):
            if a in site_bytes and st['sim'] is not None:
                fail('game wrote a patch site', (a,))
            MS(s, a, v)

    def snapshot_state(real, R):
        return (list(R), [bytes(b) for b in real.banks], real.o7ffd, bytes(ns.scratch),
                [list(x) for x in ns.attr], bytes(ns.pat))

    def plot_event(pc, real, R):
        get = lambda a: MG(real, a)
        sp = R[12]
        ret, sp_ret = get(sp + 2) | get(sp + 3) << 8, sp + 4
        stopf = lambda r: r[24] == ret and r[12] == sp_ret
        nf0 = ns.scratch[0x1004]
        model = model_decide(KIND[pc], get, R, sp, ns.scratch)
        if collect and c['collected %04X' % pc] < collect and model is not None:
            c['collected %04X' % pc] += 1
            states.append(('plot', pc, snapshot_state(real, R)))
        so, o, sp_, p, err = pair(patch, get, R, ns, stopf, alt, psite)
        for e in err:
            fail('plot %04X: %s' % (pc, e))
        d = _cmp_regs(so, sp_)
        if d:
            fail('plot: registers differ', (hex(pc), d, [so.registers[i] for i in d], [sp_.registers[i] for i in d]))
        conv = ns.scratch[0x1004] != nf0
        if conv != (model is not None):
            fail('plot: converted != model', (hex(pc), conv))
        keys = set(o.ov) | set(p.ov)
        if conv:
            md = [a for a in keys if not (BUF[0] <= a < BUF[1] and a in o.ov and a not in p.ov) and o[a] != p[a]]
            if any(BUF[0] <= a < BUF[1] for a in p.ov):
                fail('plot: patched wrote the buffer', (hex(pc),))
            px = truth(get, R, stopf)
            figs.append((px, model['col'] if model else 0))
            c['converted %s' % CALL_SITES[pc]] += 1
        else:
            md = [a for a in keys if o[a] != p[a]]
            c['passthrough %s' % CALL_SITES[pc]] += 1
        if md:
            fail('plot: memory differs', (hex(pc), len(md), [hex(a) for a in sorted(md)[:4]]))
        if any(ev[0] == 'nr' and 0x34 <= ev[1] <= 0x39 for ev in ns.events) or ns.pat_writes:
            pass

    def commit_event(real, R):
        get = lambda a: MG(real, a)
        if collect and c['collected commit'] < collect:
            c['collected commit'] += 1
            states.append(('commit', 0x8950, snapshot_state(real, R)))
        so, o, sp_, p, err = pair(patch, get, R, ns, lambda r: r[24] == 0x8954, alt, psite)
        for e in err:
            fail('commit: %s' % (e,))
        d = _cmp_regs(so, sp_)
        if d or o.ov != p.ov:
            fail('commit: registers/memory differ', (d, len(set(o.ov) ^ set(p.ov))))
        exp = expected_layer(figs, get)
        got = sprite_layer(ns)
        bad = len(set(exp) ^ set(got)) + sum(1 for k in exp if k in got and exp[k] != got[k])
        c['commits'] += 1
        c['sprite pixels compared'] += len(exp)
        c['max sprites in a frame'] = max(c['max sprites in a frame'], ns.scratch[0x1006])
        if bad:
            fail('commit: sprite pixels differ from the original plots', (bad, len(exp), len(got)))
        figs.clear()

    def quit_event(real, R):
        get = lambda a: MG(real, a)
        so, o, sp_, p, err = pair(patch, get, R, ns, lambda r: r[24] == 0x8996, alt, psite)
        for e in err:
            fail('loop exit: %s' % (e,))
        d = _cmp_regs(so, sp_)
        if d or o.ov != p.ov:
            fail('loop exit: registers/memory differ', (d,))
        if get(0xFF70):
            c['loop exits (sprites hidden)'] += 1
            if any(a[3] & 0x80 for a in ns.attr):
                fail('loop exit: sprites still visible')
            figs.clear()

    def event(pc, real, R):
        if pc in CALL_SITES:
            plot_event(pc, real, R)
        elif pc == 0x8950:
            commit_event(real, R)
        elif pc == 0x8993:
            quit_event(real, R)

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            memory.__class__ = HookMem
            super().__init__(memory, registers, state_, config)
            st['sim'] = self
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        # reached by falling through, or resumed there after an interrupt that
                        # was accepted right after the previous instruction of the block
                        if pc in FALLTHROUGH and st.get('last') != FALLTHROUGH[pc] and \
                                st.get('keep') != (FALLTHROUGH[pc], pc):
                            fail('0x%04X reached other than from 0x%04X' % (pc, FALLTHROUGH[pc]))
                        event(pc, mem, R)
                    st['last'] = pc
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

        def accept_interrupt(self, registers, memory, prev_pc):
            st['keep'] = (st.get('last'), registers[24])    # (last instruction, interrupted PC)
            return super().accept_interrupt(registers, memory, prev_pc)

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if progress and st['frame'] % 500 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (0x%04X)!' % a] += 1
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests: guards (converted == model), budget limits, live flag, negative control
# ---------------------------------------------------------------------------------------------

def _restore(patch, s):
    R, banks, o7, page, attr, pat = s
    from .build import rom48
    bm = _BankMem(banks, o7, rom48())
    ns = new_state(patch)
    ns.scratch[:] = page
    ns.attr = [list(x) for x in attr]
    ns.pat = bytearray(pat)
    return bm, list(R), ns


def _plot_case(patch, pc, s, edit=None, regs=None, page_edit=None):
    """Run one plot event (state s, optional memory/register/page edits). -> (fails, converted, model)."""
    bm, R, ns = _restore(patch, s)
    wr = dict(edit or {})
    get = lambda a: wr[a] if a in wr else bm[a]
    for i, v in (regs or {}).items():
        R[i] = v
    for a, v in (page_edit or {}).items():
        ns.scratch[a] = v
    sp = R[12]
    ret, sp_ret = get(sp + 2) | get(sp + 3) << 8, sp + 4
    stopf = lambda r: r[24] == ret and r[12] == sp_ret
    nf0, nt0 = ns.scratch[0x1004], ns.scratch[0x1005]
    model = model_decide(KIND[pc], get, R, sp, ns.scratch)
    so, o, sp_, p, err = pair(patch, get, R, ns, stopf, patch.alt_image(), _site_maps(patch))
    f = list(err)
    d = _cmp_regs(so, sp_)
    if d:
        f.append(('registers differ', d))
    conv = ns.scratch[0x1004] != nf0
    keys = set(o.ov) | set(p.ov)
    if conv:
        md = [a for a in keys if not (BUF[0] <= a < BUF[1] and a in o.ov and a not in p.ov) and o[a] != p[a]]
    else:
        md = [a for a in keys if o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md)))
    if conv != (model is not None):
        f.append(('guard: converted != model', conv))
    if conv:
        e = ns.scratch[0x1100 + 8 * nf0:0x1100 + 8 * nf0 + 8]
        want = [model['gfx'] & 255, model['gfx'] >> 8, model['W'], model['R'], model['X'] & 255, model['Y'],
                model['fl'], model['col']]
        if list(e) != want:
            f.append(('FIG entry', list(e), want))
        if ns.scratch[0x1005] - nt0 != model['tiles']:
            f.append(('tile count',))
    return f, conv, model, ns, (get, R, stopf)


def unit_tests(patch, states, neg=None, neg_int=None):
    c = collections.Counter()
    if neg_int is not None:
        for kind, pc, s in states:
            if kind == 'plot':
                f = _plot_case(neg_int, pc, s)[0]
                c['interrupt negative cases'] += 1
                c['interrupt negative control detected' if any('interrupt-unsafe' in str(x) for x in f)
                  else 'interrupt negative control NOT detected!'] += 1
    for kind, pc, s in states:
        if kind != 'plot':
            continue
        R = s[0]
        base = [({}, {}, {})]
        # positions: x/y edges (and through the guards)
        for d in (0, 1, 60, 96, 112, 120, 126, 127):
            for e in (0, 7, 8, 16, 24, 31, 200, 223, 224, 231, 232, 240, 248, 255):
                base.append(({}, {4: d, 5: e}, {}))
        # widths / line pairs (97E1 family)
        if not KIND[pc] & 4:
            for b in (1, 2, 3, 8, 9):
                for cc in (1, 8, 24, 25, 33):
                    base.append(({}, {2: b, 3: cc}, {}))
        else:
            cnt = 0x9F4E if KIND[pc] & 1 else 0x9EF6
            opa = 0x9F55 if KIND[pc] & 1 else 0x9EFA
            for n in (1, 12, 20, 24, 25, 33):
                base.append(({cnt: n}, {}, {}))
            for op in (0x00, 0xAE):
                base.append(({opa: op}, {}, {}))
        # budget / live
        for nf, nt in ((MAXF - 1, 0), (MAXF, 0), (0, MAXT - 6), (0, MAXT - 1), (0, MAXT)):
            base.append(({}, {}, {0x1004: nf, 0x1005: nt}))
        base.append(({}, {}, {0x100A: 0}))
        # caller not a converted figure
        sp = R[12]
        base.append(({sp + 2: 0x00, sp + 3: 0x80}, {}, {}))
        # graphics pointer in slot 5 / wrapping
        base.append(({sp: 0x00, sp + 1: 0xA0}, {}, {}))
        base.append(({sp: 0xF0, sp + 1: 0xFF}, {}, {}))
        for edit, regs, pe in base:
            f, conv, model, ns, _ = _plot_case(patch, pc, s, edit, regs, pe)
            c['cases'] += 1
            c['converted' if conv else 'passthrough'] += 1
            for k in f:
                c['%s: %s!' % (CALL_SITES[pc], k[0] if isinstance(k, tuple) else k)] += 1
    # commit: one recorded figure per plot state -> sprite pixels; negative control must fail
    for kind, pc, s in states:
        if kind != 'plot':
            continue
        for pt, label in ((patch, 'commit'), (neg, 'negative')):
            if pt is None:
                continue
            r = _one_commit(pt, pc, s)
            if r is None:
                continue
            r, informative = r
            if label == 'negative' and not informative:
                continue
            c['%s cases' % label] += 1
            if label == 'commit' and r:
                c['commit: sprite pixels differ!'] += 1
            if label == 'negative':
                c['negative control detected' if r else 'negative control NOT detected!'] += 1
    return c


def _one_commit(patch, pc, s):
    """Fresh page (live, empty), one plot, then a commit at a synthetic 0x8950 state. -> pixel
    mismatches (0 = identical) or None if the plot was not converted."""
    bm, R, ns0 = _restore(patch, s)
    page = bytearray(8192)
    page[0x100A] = 1
    page[0x1006] = 0
    f, conv, model, ns, (get, R2, stopf) = _plot_case(patch, pc, s[:3] + (bytes(page),) + s[4:])
    if not conv:
        return None
    ns.attr = [[0, 0, 0, 0, 0] for _ in range(128)]     # nothing on show (page: PREV = 0)
    px = truth(get, R2, stopf)
    # commit from the plot state's registers (only memory matters to the commit)
    Rc = list(R)
    Rc[24] = 0x8950
    Rc[12] = 0x7BD0
    so, o, sp_, p, err = pair(patch, get, Rc, ns, lambda r: r[24] == 0x8954, patch.alt_image(),
                              _site_maps(patch), run_orig=False)
    exp = expected_layer([(px, model['col'])], get)
    got = sprite_layer(ns)
    # informative for the negative control: a visible pixel whose ink and paper colours differ
    inf = any((model['col'] or ink_of(get(ATTR + (y >> 3) * 32 + (x >> 3)))) !=
              (CBLACK if model['col'] else paper_of(get(ATTR + (y >> 3) * 32 + (x >> 3)))) for x, y in exp)
    return len(set(exp) ^ set(got)) + sum(1 for k in exp if k in got and exp[k] != got[k]) + len(err), inf


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    say('Game      : %s' % name)
    say('Engine    : midres (Midnight Resistance: back-buffer composer; player, soldiers, vehicles -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain),
                                         'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = MidresPatch()
    sc = static_check(patch.rom_code, ROM_ORG, [(patch.syms['pcall'], patch.syms['e_cm'])]
                      if 'pcall' in patch.syms else [])
    say('Static    : hook code %d bytes at 0x%04X, no IX/IY/I/IFF/IM instructions: %s' % (
        len(patch.rom_code), ROM_ORG, 'PASS' if not sc else 'FAIL %s' % sc))
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2 and not sc
    states = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1,
                                                                   os.path.basename(s2)))
            r = s2
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        conv = sum(v for k, v in c.items() if k.startswith('converted'))
        pas = sum(v for k, v in c.items() if k.startswith('passthrough'))
        say('Verify    : %s  %d frames, %d plots converted, %d passed through, %d commits (max %d sprites), '
            '%d sprite pixels -> %s' % (os.path.basename(r), c['frames'], conv, pas, c['commits'],
                                        c['max sprites in a frame'], c['sprite pixels compared'],
                                        'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            %s' % ', '.join('%s %d' % (k, v) for k, v in sorted(c.items())
                                         if k.startswith(('converted', 'passthrough', 'loop'))))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:240]))
    if states:
        u = unit_tests(patch, states, MidresPatch(swap=True), negative_int_patch(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d cases (%d converted, %d passthrough), %d commit cases, negative control %d/%d -> %s' % (
            u['cases'], u['converted'], u['passthrough'], u['commit cases'], u['negative control detected'],
            u['negative cases'], 'PASS' if not uf else 'FAIL %s' % uf))
        say('Interrupt : %d hook instructions checked (IX, IY, I, interrupt state, stack, 0x3D00 fetches); '
            'negative control (LD IY in every CALL hook) %d/%d' % (
                ISAFE['checked'], u['interrupt negative control detected'], u['interrupt negative cases']))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def negative_int_patch(patch):
    """Broken copy: every CALL hook starts with LD IY,0xB000 (4 bytes over NEXTREG's 4)."""
    return MidresPatch(edit={patch.syms[k]: bytes.fromhex('FD2100B0') for k in CALL_SITES.values()})
