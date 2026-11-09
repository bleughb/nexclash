"""Scooby Doo in the Castle Mystery (Elite, 1986, 48K): the original game on the Next, no figures moved.

Its play area is one colour pair throughout, so the game never had colour clash; figures carry their own masks.
The default is the original picture. The build owns the ROM (Sinclair's 48K ROM as the whole alt ROM) so the
game and its BASIC loader run the same on any NextZXOS. No hook, no site, not one game byte changes. See
games/scooby_doo.md.
"""
from pathlib import Path
import json
from . import z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/scooby_doo.json'
SOURCE_MD5 = '8a82e06f6829a2a1c30781491cfbc42e'
REGBLOCK = 0x3C00                  # in Sinclair's unused 0x386E-0x3CFF: the stub writes the start-up registers here
REGS_LEN = 20
PAGE = 25
SIGNATURE = {0x73AB: '21B961', 0x75B1: '21C06C35C0', 0x7320: 'ED73DD703AB861'}
DECISIONS = {'figures': 'unchanged: monochrome play area, figures have their own masks', 'scenery': 'unchanged',
             'pace': 'original: no hook', 'outline': 'none', 'enhanced': 'waiting for the mock-up'}
CMP = ()                           # no hook: nothing runs instead of the game's code


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_scooby_doo(snap):
    try:
        mem = snap.memory if hasattr(snap, 'memory') else (bytes(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0])
        return all(bytes(mem[a:a + len(bytes.fromhex(v))]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


class Patch:
    name = 'Scooby Doo: the original game, Sinclair ROM as the whole alt ROM'
    uses_printer_buffer = False
    keep_printer_buffer = True
    hook_page_data = b''
    stub_extra = b''
    setup_call = None
    sites = ()

    def __init__(self, source=None):
        self.source = str(source) if source else None
        rom = zt.rom48()
        self.page = bytearray(rom[0x2000:0x4000])
        self.slot1 = (PAGE, REGBLOCK)
        self.altrom = (REGBLOCK, REGBLOCK + REGS_LEN)
        self.extra_banks = {PAGE // 2: bytes(8192) + bytes(self.page)}

    def apply(self, snap):
        if not is_scooby_doo(snap):
            raise ValueError('Not the supported Scooby Doo release (MD5 %s)' % SOURCE_MD5)


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """No hook: what can differ is the ROM and the tail. nextboot.rom_paths replays the original and compares every ROM
    byte it runs or reads, and the tail bytes it reads, against the .nex (work/replay.py); here the game's bytes."""
    from collections import Counter
    c = Counter(hooks=0)
    if patch.sites:
        c['a site in a no-hook build!'] += 1
    return (c, {}, []) if collect else (c, {})


def unit_tests(patch, states, neg=True):
    from collections import Counter
    return Counter()


# ---- Enhanced: the set's colours on a double-buffered Layer 2 (asm/scooby_doo_hooks.asm) ----
COLOUR_PAINTER = 'Armando Quaranta'
CANVAS_LO = 0x9400              # the canvas: RAM address A's colours at page CBASE + A // 1024, offset (A % 1024) * 8
BUFFER = (0x9FCC, 0xAFCC)
SCREENED = (0x9FCC, 0xB1CC)     # the buffer and its attributes: no colours of their own at the start
JP, CALL = 0xC3, 0xCD
SITES = [(0x8D67, '012828', JP, 'h_s1'), (0x8D6F, '21C0FF', JP, 'h_s2'), (0x8D85, '013008', JP, 'h_s3'), (0x8A7A, '3AD961', JP, 'h_s4'),
         (0x8E0C, 'DD2100', JP, 'h_s5'), (0x8550, 'CD8E84', JP, 'h_sl'), (0x8532, 'CDD384', JP, 'h_sr'), (0x8571, 'CD8E84', JP, 'h_su'),
         (0x8598, 'CDD384', JP, 'h_sd'), (0x8E71, '119F96', JP, 'h_r1'), (0x8E97, '219F96', JP, 'h_r2'), (0x8EBE, '119F96', JP, 'h_r3'),
         (0x8EFA, 'ED5BD0', JP, 'h_r4'), (0x8B99, 'ED5BD0', JP, 'h_r5'), (0x9180, 'ED4BD9', JP, 'h_plot'), (0x91BA, 'ED4BD9', JP, 'h_nib'),
         (0x9237, '3ADA61', JP, 'h_ldir'),
         (0x6F3B, 'CD5F7D', CALL, 'h_hide'), (0x8464, 'CDE382', JP, 'h_copy')]
# where each hook comes back: (address, stack change)
RESUME = {0x8D67: (0x8D6A, 0), 0x8D6F: (0x8D72, 0), 0x8D85: (0x8D88, 0), 0x8A7A: (0x8A7D, 0), 0x8E0C: (0x8E10, 0), 0x8550: (0x8553, 0), 0x8532: (0x8535, 0),
          0x8571: (0x8574, 0), 0x8598: (0x859B, 0), 0x8E71: (0x8E74, 0), 0x8E97: (0x8E9A, 0), 0x8EBE: (0x8EC1, 0), 0x8EFA: (0x8EFE, 0), 0x8B99: (0x8B9D, 0),
          0x9180: (0x9184, 0), 0x91BA: (0x91BE, 0), 0x9237: (0x923A, 0), 0x6F3B: (0x7D5F, -2),
          0x8464: (0x8475, 0)}


def read_set(path):
    """-> (planes(A) -> 9 bytes: 8 planes, master; cfg up, down, flags) of a 48K .256."""
    d = open(path, 'rb').read()
    bank = {1: 5, 2: 2, 3: 0}

    def word(a):
        o = (bank[a >> 14] * 16384 + (a & 0x3FFF)) * 9
        return d[o:o + 9]
    return word, d[131072 * 9 + 29], d[131072 * 9 + 30], d[131072 * 9 + 31]


def chunky(w):
    """9 bytes of the set -> the 8 pixels of that RAM byte, left first."""
    return bytes(sum(((w[p] >> (7 - k)) & 1) << p for p in range(8)) for k in range(8))


def mono8(v):
    return bytes(255 if v & (0x80 >> k) else 0 for k in range(8))


PALETTE_FILE = 'emu256_datos.js'   # emu256's datos.js, staged beside the set; never in this repo


def palette_rgb(set_path=None):
    """The emulator's table: the palette every .256 is painted in. Never in this repo: emu256's datos.js, from
    $EMU256/datos.js, else staged beside the set as emu256_datos.js."""
    import re
    import os
    env = os.environ.get('EMU256')
    path = Path(env) / 'datos.js' if env else Path(set_path).parent / PALETTE_FILE
    t = open(path).read()
    m = re.search(r'PALETTE_RGB\s*=\s*\[([^\]]*)\]', t)
    out = [int(x, 0) for x in m.group(1).replace('\n', ' ').split(',') if x.strip()]
    assert len(out) == 256
    return out


def nine(r, g, b):
    q = lambda v: min(7, (v * 7 + 127) // 255)
    r3, g3, b3 = q(r), q(g), q(b)
    return (r3 << 5) | (g3 << 2) | (b3 >> 1), b3 & 1


class Enhanced(Patch):
    name = 'Scooby Doo: Enhanced, the Spec256 colours on a Layer 2 canvas'

    def __init__(self, source, set_path):
        super().__init__(source)
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = self.syms['setup']
        rom = zt.rom48()
        self.ram = bytearray(rom[0x2000:0x4000])
        self.ram[0:len(self.code)] = self.code
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[self.syms['V_BACK'] - 0x2000] = self.syms['L2_BANK_B']
        q = self.syms['QSTART']
        self.ram[self.syms['V_QT'] - 0x2000:self.syms['V_QT'] - 0x2000 + 2] = bytes((q & 255, q >> 8))
        self.page = bytearray(rom[0x2000:0x4000])
        lo, hi = self.syms['ven_start'], self.syms['ven_end']
        self.page[lo - 0x2000:hi - 0x2000] = self.ram[lo - 0x2000:hi - 0x2000]
        self.altrom = (lo, REGBLOCK + REGS_LEN)
        self.sites = [(a, bytes.fromhex(o), bytes((op,)) + zt.w16(self.syms[n])) for a, o, op, n in SITES]
        self.site_of = {a: n for a, o, op, n in SITES}
        self.set_path = str(set_path)
        self.extra_banks = dict(self._bank12())

    def _bank12(self):
        return {PAGE // 2: bytes(self.ram) + bytes(self.page)}

    def palette(self):
        """256 entries. The set has a background: behind pixels of value 0, and of 255 on any ink but white (none in the window), its value there, one
        colour over the whole window (0xB9), so entries 0 and 255 take it. 192-254, which the renderer mixes with the attribute, do not occur in play."""
        d = open(self.set_path, 'rb').read()
        bg = d[131072 * 9 + 32:131072 * 9 + 32 + 256 * 128]
        assert len(set(bg)) == 1
        rgb = palette_rgb(self.set_path)
        out = []
        for v in range(256):
            c = rgb[bg[0]] if v in (0, 255) else rgb[v]
            r, g, b = c >> 16, (c >> 8) & 255, c & 255
            if 192 <= v < 255:
                e = nine(r >> 1, g >> 1, b >> 1)
            else:
                e = nine(r, g, b)
            # Layer 2's transparent colour stays the Next's 0xE3: an entry on it moves one step of blue
            out.append((0xE2, 1) if e[0] == 0xE3 else e)
        page = bytearray(8192)
        for i, e in enumerate(out):
            page[i * 2:i * 2 + 2] = bytes(e)
        return bytes(page)

    def in_play(self):
        """The game's memory past its BASIC loader, which relocates the sprite table: 300 frames on, as the set's memory is."""
        if getattr(self, '_play', None) is None:
            from .machine import Machine
            m = Machine(self.source)
            for _ in range(300):
                m.frame(frozenset())
            self._play = bytes(m.sim.memory)
        return self._play

    def canvas(self, snap):
        """{page: 8K} from the set, for this release. The set was taken with some sprites mirrored: they are stored here as the release holds them.
        A byte the set holds differently otherwise keeps the release's picture (mono) and is listed."""
        word = read_set(self.set_path)[0]
        rel = self.in_play().__getitem__
        cb = self.syms['CBASE']
        pages = {}
        self.differ = []
        self.mirrored = []
        put = {}
        for a in range(CANVAS_LO, 0x10000):
            pages.setdefault(cb + (a >> 10), bytearray(8192))
            if SCREENED[0] <= a < SCREENED[1]:
                continue
            w = word(a)
            if w[8] == rel(a):
                put[a] = chunky(w)
            else:
                self.differ.append(a)
                put[a] = mono8(rel(a))
        p = 0xB404
        rev = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))
        while p < 0xB728:
            ptr, b2, b3 = rel(p) | rel(p + 1) << 8, rel(p + 2), rel(p + 3)
            p += 4
            rows, width = (b2 & 0x7F) * 8, b3 & 0x7F
            if ptr < 0xB000 or rows == 0 or width == 0 or width > 40:
                continue
            same = all(word(ptr + i)[8] == rel(ptr + i) for i in range(rows * width))
            if same:
                continue
            flipped = all(word(ptr + r * width + width - 1 - c)[8] == rev[rel(ptr + r * width + c)] for r in range(rows) for c in range(width))
            if flipped:
                self.mirrored.append(ptr)
                for r in range(rows):
                    for c in range(width):
                        a = ptr + r * width + c
                        put[a] = chunky(word(ptr + r * width + width - 1 - c))[::-1]
                        if a in self.differ:
                            self.differ.remove(a)
        self.init_pix = dict(put)
        moff = self.syms['MOFF']
        base = dict(put)
        other = dict(put)
        p = 0xB404
        while p < 0xB728:
            ptr, b2, b3 = rel(p) | rel(p + 1) << 8, rel(p + 2), rel(p + 3)
            p += 4
            rows, width = (b2 * 8) & 255, b3 & 0x7F
            if ptr < 0xB000 or rows == 0 or width == 0 or width > 40:
                continue
            for r in range(rows):
                for c in range(width):
                    a = ptr + r * width + c
                    m = put[ptr + r * width + width - 1 - c][::-1]
                    if b3 & 0x80:           # the release holds it mirrored: the unmirrored way is the other one
                        base[a] = m
                        other[a] = put[a]
                    else:
                        other[a] = m
        for a, b in base.items():
            pg = pages[cb + (a >> 10)]
            pg[(a & 1023) * 8:(a & 1023) * 8 + 8] = b
        for a in range(0xB000, 0x10000):
            b = other.get(a)
            if b is None:
                continue
            pg = pages.setdefault(cb + moff + (a >> 10), bytearray(8192))
            pg[(a & 1023) * 8:(a & 1023) * 8 + 8] = b
        return pages

    def apply(self, snap):
        if not is_scooby_doo(snap):
            raise ValueError('Not the supported Scooby Doo release (MD5 %s)' % SOURCE_MD5)
        pages = self.canvas(snap)
        pages[self.syms['PAL_PAGE']] = self.palette()
        self.mono = {a: self.in_play()[a] for a in range(CANVAS_LO, 0x10000)}
        banks = {i: bytearray(snap.banks[i]) for i in snap.banks}
        for a, old, new in self.sites:
            b = {1: 5, 2: 2, 3: 0}[a >> 14]
            at = a & 0x3FFF
            if bytes(banks[b][at:at + 3]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[b][at:at + 3] = new
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in banks)
        eb = self._bank12()
        for p, data in pages.items():
            b = p // 2
            cur = bytearray(eb.get(b, bytes(16384)))
            cur[(p & 1) * 8192:(p & 1) * 8192 + 8192] = data
            eb[b] = bytes(cur)
        self.extra_banks = eb
        self.pages_init = pages


def build_enhanced(source, destination, set_path):
    p = Enhanced(source, set_path)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


# ---- verification: independent plane models of the game's writes, against the hooks run from the same state ----
from . import hooklib, simpool   # noqa: E402
CMP_E = tuple(hooklib.CMP_R)
STD = (255, 255, 10, 11, 4, 5, 0, 1)


class View:
    """64K as the hook's MMU shows it. mem = the game's 48K view, flat; pages = canvas, palette, Layer 2."""
    def __init__(self, mem, patch, st):
        self.mem, self.patch, self.st = mem, patch, st
        self.nr = None
        self.rom = zt.rom48()

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        s = a >> 13
        m = self.nr.get(0x50 + s, STD[s])
        if m == STD[s]:
            if s == 0:
                return self.rom[a]
            if s == 1:
                return self.patch.page[a - 0x2000]
            return self.mem[a]
        if m == 24:
            return self.st.page[a & 8191]
        return self.st.pages.setdefault(m, bytearray(8192))[a & 8191]

    def __setitem__(self, a, v):
        s = a >> 13
        m = self.nr.get(0x50 + s, STD[s])
        if m == STD[s]:
            if s >= 2:
                self.mem[a] = v
            return
        if m == 24:
            self.st.page[a & 8191] = v
        else:
            self.st.pages.setdefault(m, bytearray(8192))[a & 8191] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line, lines=312, t_line=224)
        self.nr.update({0x50 + i: p for i, p in enumerate(STD)})
        self.nr[1] = 0x32
        self.io = []

    def write_port(self, regs, port, v, *args):
        if port in (0x243B, 0x253B) or port & 255 == 0x6B:
            return super().write_port(regs, port, v, *args)
        self.io.append((port, v))


class State:
    """What persists between hooks."""
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = {p: bytearray(d) for p, d in patch.pages_init.items()}
        self.nr = {0x12: patch.syms['L2_BANK_A'], 0x69: 0}
        self.line = 0
        self.flips = 0


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st)
    s = simpool.machine(Sim, v, list(regs), 'scooby-hook')
    m = Model(s, speed, st.line)
    m.nr.update(st.nr)
    v.nr = m.nr
    n = 0
    R = s.registers
    while n == 0 or R[24] != stop_pc or (stop_sp is not None and R[12] != stop_sp):
        s.opcodes[v[R[24]]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not terminate: PC %04X, want %04X SP %s; SP now %04X; nr %s' % (R[24], stop_pc, stop_sp, R[12], {k: m.nr.get(k) for k in (0x54, 0x55, 0x56, 0x57, 7)}))
    st.line = m.line()
    for k in (0x12, 0x69):
        st.nr[k] = m.nr[k]
    return list(R), v, m


class Planes:
    """The set's model: each RAM byte as eight pixels (a 64-bit integer), written as the game's own instructions write the mono byte."""
    M = (1 << 64) - 1

    def __init__(self, init):
        self.P = init
        self.A = 0
        self.used = set()

    def ops(self):
        P = self.P
        H = lambda R: R[6] * 256 + R[7]
        D = lambda R: R[4] * 256 + R[5]
        IX = lambda R: R[8] * 256 + R[9]

        def ldi(R, mem):
            s = H(R)
            P[D(R)] = P[s]
            self.used.add(s)

        def load(R, mem):
            a = D(R)
            self.A = P[a]
            self.used.add(a)

        def op_and(R, mem):
            self.A &= P[H(R)]

        def op_or_ix(R, mem):
            a = IX(R)
            self.A |= P[a]
            self.used.add(a)

        def store(R, mem):
            P[H(R)] = self.A

        def zero(R, mem):
            P[H(R)] = 0

        def nib(R, mem):
            w16 = lambda a: mem[a] | mem[a + 1] << 8
            rows, w, f = mem[0x61D9], mem[0x61DA], mem[0x8F99]
            gfx, mask, dst, ss = w16(0x61D7), w16(0xB400), H(R), w16(0x8F95)
            px = lambda base, i: (P[base + (i >> 3)] >> (56 - 8 * (i & 7))) & 255
            for r in range(rows or 256):
                d0 = dst + r * 32
                g0, m0 = gfx + r * ss, mask + r * ss
                i0 = -4 if f & 1 else 0
                i1 = 8 * w - (4 if f & 2 else 0)
                if w == 0:
                    i1 = 0
                for i in range(i0, i1):
                    p = 4 + i
                    a = d0 + (p >> 3)
                    sh = 56 - 8 * (p & 7)
                    old = (P[a] >> sh) & 255
                    new = (old & px(m0, i)) | px(g0, i)
                    P[a] = (P[a] & ~(255 << sh) & Planes.M) | new << sh
                    self.used.add(g0 + (i >> 3))

        def flip(R, mem):
            e = 0xB404 + R[7] * 4
            a = mem[e] | mem[e + 1] << 8
            rows, w = (mem[e + 2] * 8) & 255, mem[e + 3] & 0x7F
            rv = lambda x: int.from_bytes(x.to_bytes(8, 'big')[::-1], 'big')
            for r in range(rows):
                b = a + r * w
                row = [P[b + i] for i in range(w)]
                for i in range(w):
                    P[b + i] = rv(row[w - 1 - i])
        t = {0x8E14: load, 0x8E15: store, 0x8E9D: zero, 0x919D: load, 0x919E: op_and, 0x919F: op_or_ix, 0x91A2: store, 0x9270: load, 0x9271: op_and,
             0x9272: op_or_ix, 0x9275: store, 0x91BA: nib, 0x8F1D: flip}
        for a in (0x8D6A, 0x8D74, 0x8D88, 0x8A7D, 0x8EA2, 0x8E76, 0x8E78, 0x8E7A, 0x8E7C, 0x8E82, 0x8E84, 0x8E86, 0x8E88, 0x8EC3, 0x8EC5, 0x8EC9, 0x8ECB,
                  0x8ECF, 0x8ED1, 0x8ED5, 0x8ED7, 0x8F01, 0x8F03, 0x8F05, 0x8F07, 0x8F0D, 0x8BA6, 0x9256, 0x929C, 0x9152):
            t[a] = ldi
        for k in range(32):
            t[0x848E + 2 * k] = ldi
            t[0x84D3 + 2 * k] = ldi
        return t


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original. At every hook site the hook runs on a copy of the state and the original to the same point: every register
    with R, all 48K RAM but the dead stack, MMU, clock. At every copy: the canvas and the published Layer 2 window against the plane model;
    a second model fed with the release's own mono bytes against the game's real buffer and ULA, so a write the models miss shows."""
    from collections import Counter, defaultdict
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    ex = defaultdict(list)
    st = State(patch)
    cb = patch.syms['CBASE']
    init = [0] * 65536
    mono = [0] * 65536
    for a in range(CANVAS_LO, 0x10000):
        if a in patch.init_pix:
            init[a] = int.from_bytes(patch.init_pix[a], 'big')
        mono[a] = int.from_bytes(mono8(patch.mono[a]), 'big')
    pl = Planes(init)
    mo = Planes(mono)
    ops, opm = pl.ops(), mo.ops()
    exp = [int.from_bytes(mono8(v), 'big') for v in range(256)]

    def fail(k, d):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append(d)
    sites = {a: (old, new) for a, old, new in patch.sites}
    pcs = set(sites) | set(ops)
    shown = [None]
    shown_ok = [True]

    def on_pc(pc, sim):
        R = sim.registers
        hook = pc in sites
        if pc in ops:
            if pc in (0x91BA, 0x8F1D):
                m = sim.memory[0:65536]
                ops[pc](R, m)
                opm[pc](R, m)
            else:
                ops[pc](R, None)
                opm[pc](R, None)
        if not hook:
            return
        m0 = bytearray(sim.memory[0:65536])
        regs = list(R)
        old, new = sites[pc]
        if bytes(m0[pc:pc + 3]) != old:
            fail('site bytes changed', hex(pc))
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, bytes(m0)))
        patched = bytearray(m0)
        for a, o, n in patch.sites:
            patched[a:a + 3] = n
        ref = simpool.machine(Simulator, list(m0), regs, 'sd-ref')
        RR = ref.registers
        sp = regs[12]
        stop_pc, dsp = RESUME[pc]
        stop_sp = sp + dsp
        n = 0
        while n == 0 or RR[24] != stop_pc or RR[12] != stop_sp:
            ref.opcodes[ref.memory[RR[24]]]()
            n += 1
            if n > 400000:
                raise AssertionError('reference did not reach %04X from %04X' % (stop_pc, pc))
        got, v, model = run_hook(patch, st, patched, regs, stop_pc, stop_sp)
        for i in CMP_E:
            if (bool(RR[i]) != bool(got[i])) if i == 26 else RR[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': RR[i], 'got': got[i]})
        expected = bytearray(ref.memory[0:65536])
        actual = bytearray(v.mem)
        for a, o, nw in patch.sites:
            expected[a:a + 3] = nw
        lo2 = min(sp, stop_sp)
        for a in range(lo2 - 32, lo2):
            expected[a] = actual[a]
        if expected[0x4000:] != actual[0x4000:]:
            bad_a = [a for a in range(0x4000, 65536) if expected[a] != actual[a]]
            fail('48K RAM differs', {'pc': hex(pc), 'count': len(bad_a), 'addresses': [hex(x) for x in bad_a[:8]]})
        for k in range(8):
            if model.nr[0x50 + k] != STD[k]:
                fail('MMU not restored', {'pc': hex(pc), 'slot': k, 'page': model.nr[0x50 + k]})
        if model.nr[7] != 0:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        name = patch.site_of[pc]
        if name == 'h_hide' and st.nr[0x69] != 0:
            fail('overlay not hidden', {'pc': hex(pc)})
        c['hooks'] += 1
        c['hooks ' + name] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if name == 'h_copy':
            c['publications'] += 1
            # the replay runs the plane writes after this hook, so the models hold what the buffer holds now
            monob = [a for a in range(*BUFFER) if mo.P[a] != exp[m0[a]]]
            if monob:
                a0 = monob[0]
                fail('mono model differs from the game', {'count': len(monob), 'ex': [hex(x) for x in monob[:8]], 'model': mo.P[a0].to_bytes(8, 'big').hex(), 'ram': hex(m0[a0])})
            w16 = lambda a: m0[a] | m0[a + 1] << 8
            t, nb, g, mk = m0[0x61B5] * 8, m0[0x61B6] * 8, w16(0x61B1), w16(0x61B3)
            pend = st.page[patch.syms['V_PEND'] - 0x2000]
            back = st.page[patch.syms['V_BACK'] - 0x2000]         # the picture just drawn: flipped now, or waiting for its flip
            if not pend:
                back = patch.syms['L2_BANK_A'] + patch.syms['L2_BANK_B'] - back
            if st.nr[0x12] == st.page[patch.syms['V_BACK'] - 0x2000]:
                fail('picture never shown', {'pc': hex(pc)})
            lit = 0
            hi = 0
            scr_bad = 0
            for y in range(128):
                p = st.pages[back * 2 + (y >> 5)]
                o = (y & 31) * 256
                seg = bytes(p[o:o + 256])
                a = BUFFER[0] + 32 * y
                row = [pl.P[a + i] for i in range(32)]
                rmono = [mo.P[a + i] for i in range(32)]
                if t <= y < t + nb:
                    r = y - t
                    for k in range(4):
                        row[14 + k] = (row[14 + k] & pl.P[mk + 4 * r + k]) | pl.P[g + 4 * r + k]
                        rmono[14 + k] = (rmono[14 + k] & mo.P[mk + 4 * r + k]) | mo.P[g + 4 * r + k]
                want = b''.join(x.to_bytes(8, 'big') for x in row)
                if seg != want:
                    fi = next(i for i in range(256) if seg[i] != want[i])
                    fail('published window differs', {'row': y, 'first': fi, 'n': sum(1 for i in range(256) if seg[i] != want[i]), 'band': (t, nb), 'pl': hex(g), 'mk': hex(mk), 'got': seg[fi & ~7:(fi & ~7) + 24].hex(), 'want': want[fi & ~7:(fi & ~7) + 24].hex(), 'frame': c.get('publications')})
                    break
                lit += 256
                hi += sum(1 for x in want if x >= 192)
                sa = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
                for i in range(32):
                    if rmono[i] != exp[expected[sa + i]]:
                        scr_bad += 1
            c['pixels compared'] += lit
            c['pixels the set gives to the attribute'] += hi
            if scr_bad:
                fail('mono model differs from the ULA', {'bytes': scr_bad})
        if progress and c['hooks'] % 25 == 0:
            progress(c)
    states = []
    frames, err = trace(str(rzx_path), pcs, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    pat = set(pl.used)
    c['source bytes'] = len(pat)
    c['source bytes the set holds differently'] = len(pat & set(getattr(patch, 'differ', ())))
    patch.used_sources = pat
    return (c, dict(ex), states) if collect else (c, dict(ex))


def unit_tests(patch, states, neg=True):
    """Every hook state at the four incoming clocks, both IFF values and four R phases: registers with R, the clock the caller had, MMU back."""
    from collections import Counter
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        sp = regs[12]
        stop_pc, dsp = RESUME[pc]
        stop_sp = sp + dsp
        patched = bytearray(mem)
        for a, o, n in patch.sites:
            patched[a:a + 3] = n
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 127, 128, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    R = ref.registers
                    n = 0
                    while n == 0 or R[24] != stop_pc or R[12] != stop_sp:
                        ref.opcodes[ref.memory[R[24]]]()
                        n += 1
                    st = State(patch)
                    got, v, model = run_hook(patch, st, bytearray(patched), rr, stop_pc, stop_sp, speed=speed)
                    for i in CMP_E:
                        if i == 26:
                            continue
                        if R[i] != got[i]:
                            c['ABI registers differ!'] += 1
                            break
                    if model.nr[7] != speed:
                        c['incoming clock not restored!'] += 1
                    if any(model.nr[0x50 + k] != STD[k] for k in range(8)):
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken hook bytes: each must fail the replay."""
    import copy
    out = {}

    def mut(name, old, new):
        b = copy.deepcopy(patch)
        i = bytes(b.ram).find(old)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[i:i + len(new)] = new
        out[name] = b
    w = lambda s: bytes((patch.syms[s] & 255, patch.syms[s] >> 8))
    mut('R off by one', bytes.fromhex('3E71CD'), bytes.fromhex('3E70CD'))
    mut('clock left at 28 MHz', bytes.fromhex('F53A303EED9207'), bytes.fromhex('F53E0300ED9207'))
    mut('OR pass dropped', bytes.fromhex('EBB6EB77'), bytes.fromhex('EB00EB77'))
    mut('AND pass dropped', bytes.fromhex('79A6EB'), bytes.fromhex('7900EB'))
    mut('row stride off', bytes.fromhex('2A603E24'), bytes.fromhex('2A603E00'))
    mut('source one page out', bytes.fromhex('C603C600'), bytes.fromhex('C604C600'))
    mut('MMU slot 7 left mapped', bytes.fromhex('ED915701C9'), bytes.fromhex('ED915702C9'))
    mut('window a pixel to the right', bytes.fromhex('2100002 24E3E'.replace(' ', '')), bytes.fromhex('210100224E3E'))
    mut('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('ED916980'))
    mut('picture never shown', bytes.fromhex('ED9212'), bytes.fromhex('000000'))
    mut('mirrored sprites taken as stored', bytes.fromhex('E68028023E18'), bytes.fromhex('E68028023E00'))
    mut('player left off', bytes.fromhex('3A573EB7'), bytes.fromhex('3E0000B7'))
    mut('figures left off', b'\xCD' + w('figures'), bytes(3))
    b = copy.deepcopy(patch)
    b.ram[patch.syms['op_fwd'] - 0x2000] = 0xC9
    out['scroll left not mirrored'] = b
    return out


# ---- nexclash.py auto: the published builds, boot checks, and with --rzx Enhanced's replay proof ----
LOAD_SCREEN = 'scooby_doo_loading.scr'
LOAD_MD5 = '56499a0d35fc5113fe24445457d59290'   # the tape's ScoobyDoo2 block, first 6,912 bytes
SET_FILE = 'Scooby-Doo.256'
SET_MD5 = 'e22c336b026a51d6b2249d993f7c12a7'    # the Spec256 set, painter Armando Quaranta; never in this repo
NEG_STOP = 900
PUBLISHER = 'Elite, 1986'


def _beside(z80, fname, md5):
    """A local input beside the snapshot, or None. A different file there is refused."""
    import hashlib
    path = Path(z80).resolve().parent / fname
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not the expected file (MD5 %s)' % (fname, md5))
    return path


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD: every register with R and all 48K RAM against the patched snapshot, bar the
    start-up tail's own bytes. -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
    tail = zt.choose_tail_addr(s, size, None, False)[0]
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if tail <= a < tail + size:
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _enhanced(z80, set_path):
    p = Enhanced(z80, set_path)
    p.apply(zt.Z80Snapshot(str(z80)))
    return p


def _replay(z80, set_path, rzx, stop, collect):
    """One recording against Enhanced's hooks (a process of its own) -> (name, counts, failures, states)."""
    r = verify(_enhanced(z80, set_path), rzx, stop=stop, collect=collect)
    c, ex, states = r[0], r[1], (r[2] if len(r) > 2 else [])
    return Path(rzx).name, dict(c), {k: (v, ex.get(k[:-1], [])[:2]) for k, v in c.items() if k.endswith('!')}, states


def _negative(z80, set_path, name, rzx, stop):
    """One deliberately broken build's replay (a process of its own) -> (name, its failure keys)."""
    try:
        c, ex = verify(negative_patches(_enhanced(z80, set_path))[name], rzx, stop=stop)
        return name, sorted(k for k in c if k.endswith('!'))
    except Exception as e:          # noqa: BLE001 - a hang or crash of a broken build is a catch
        return name, ['hung or crashed: %s' % repr(e)[:80]]


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build (no hook) and, with the Spec256 set and emu256's palette beside the snapshot,
    Enhanced; each with the tape's loading screen when it is beside the snapshot, each boot-checked. With --rzx: every
    recording replayed against Enhanced's hooks, the ABI cases and the broken builds (the first recording's first 900
    frames; one that survives that is run over the other recordings in full). Pace, soak, flicker and the real loader
    are the review runs' (games/scooby_doo.md "Evidence")."""
    import concurrent.futures, hashlib, os, tempfile
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    from . import rzx as RZ
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    say('Game      : Scooby Doo in the Castle Mystery (Elite, 1986, 48K)')
    say('Engine    : scooby_doo; default: the original game, no hook; Enhanced: the Spec256 colours on a double-buffered Layer 2')
    ok = True
    screen_path = _beside(z80, LOAD_SCREEN, LOAD_MD5)
    screen = screen_path.read_bytes() if screen_path else None
    set_path = _beside(z80, SET_FILE, SET_MD5)
    if set_path is not None and not os.environ.get('EMU256') and not (set_path.parent / PALETTE_FILE).is_file():
        say('Enhanced  : %s found but no %s beside it (or $EMU256): default only' % (SET_FILE, PALETTE_FILE))
        set_path = None
    builds = [('Default', '', lambda: Patch(z80), lambda dst: build(z80, dst))]
    if set_path is None:
        say('Enhanced  : no %s beside the snapshot: default only' % SET_FILE)
    else:
        builds.append(('Enhanced', '_enhanced', lambda: _enhanced(z80, set_path), lambda dst: build_enhanced(z80, dst, set_path)))
    if screen is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    for label, suffix, patch, make in builds:
        nex = out / (name + suffix + '.nex')
        make(nex)
        nexes = [nex]
        if screen is not None:
            loading = out / (name + suffix + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen))
            nexes.append(loading)
        for n in nexes:
            bad = boot_check(n, z80, patch())
            ok = ok and not bad
            say('%-10s: %s  %s' % (label, n.name, hashlib.md5(n.read_bytes()).hexdigest()))
            say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)' if not bad
                                    else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    if not rzxs:
        say('Verify    : not requested; boot evidence only')
    elif set_path is None:
        say('Verify    : the default has no hook (the ROM path check below covers it); Enhanced not built, no replay')
    else:
        stop = getattr(a, 'quick', None)
        workers = os.cpu_count() or 1
        with tempfile.TemporaryDirectory(prefix='scooby_doo_') as temp:
            replayed = []
            for path in rzxs:
                if sum(isinstance(b.obj, Snapshot) for b in parse_rzx(path)) > 1:
                    stripped = str(Path(temp) / Path(path).name)
                    RZ.strip(path, stripped)
                    path = stripped
                replayed.append(path)
            with concurrent.futures.ProcessPoolExecutor(min(len(replayed) + 1, workers)) as pool:
                first = pool.submit(_replay, z80, set_path, replayed[0], NEG_STOP if stop is None else min(stop, NEG_STOP), 2)
                done = list(pool.map(_replay, [z80] * len(replayed), [set_path] * len(replayed), replayed,
                                     [stop] * len(replayed), [0] * len(replayed)))
                states = first.result()[3]
            for rname, c, fail, _ in done:
                ok = ok and not fail
                say('Verify    : Enhanced %s %d frames, %d hooks, %d pixels against the plane model: %s' % (
                    rname, c.get('frames', 0), c.get('hooks', 0), c.get('pixels compared', 0),
                    'IDENTICAL' if not fail else str(fail)[:400]))
            counts = unit_tests(_enhanced(z80, set_path), states)
            fail = {k: v for k, v in counts.items() if k.endswith('!')}
            ok = ok and not fail and counts.get('ABI cases', 0) > 0
            say('Unit      : %s' % dict(counts))
            if stop is None:
                names = list(negative_patches(_enhanced(z80, set_path)))
                with concurrent.futures.ProcessPoolExecutor(min(len(names), workers)) as pool:
                    res = dict(pool.map(_negative, [z80] * len(names), [set_path] * len(names), names,
                                        [replayed[0]] * len(names), [NEG_STOP] * len(names)))
                    left = [n for n, k in res.items() if not k]
                    jobs = [(n, r) for n in left for r in replayed[1:]]
                    if jobs:
                        for n, k in pool.map(_negative, [z80] * len(jobs), [set_path] * len(jobs), [j[0] for j in jobs],
                                             [j[1] for j in jobs], [None] * len(jobs)):
                            res[n] = res[n] or k
                missed = [n for n, k in res.items() if not k]
                ok = ok and not missed
                say('Negatives : %d of %d broken builds caught%s' % (len(res) - len(missed), len(res),
                                                                     '; MISSED %s' % missed if missed else ''))
    say('Coverage  : Enhanced replay, ABI and broken builds here (--rzx); pace, soak, flicker and real loader in games/scooby_doo.md "Evidence"')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
