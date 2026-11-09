"""Gunrunner (Cybadyne / Hewson, 1987, 48K): the original game on the Next, no figures moved.

Every level's play area is one colour on black, so the game never had colour clash; figures keep their own
black masks. The default is the original picture. The build owns the ROM (Sinclair's 48K ROM as the whole alt
ROM) so the game runs the same on any NextZXOS. No hook, no site, not one game byte changes. See games/gunrunner.md.
"""
from pathlib import Path
import json
from . import z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/gunrunner.json'
SOURCE_MD5 = 'c9d8ff6b87d413df486a42c988c7079e'
REGBLOCK = 0x3C00                  # in Sinclair's unused 0x386E-0x3CFF: the stub writes the start-up registers here
REGS_LEN = 20
PAGE = 25
SIGNATURE = {0xBC0C: 'CDA3D5CDB1D5CD3DDD', 0xD3C4: 'ED7398ECED7B9AECF3', 0xCAC6: 'DD7E053281E6', 0xF230: '38F7B65C8C45'}
DECISIONS = {'figures': 'unchanged: monochrome play area, figures have their own black masks', 'scenery': 'unchanged',
             'pace': 'original: no hook', 'outline': 'none',
             'enhanced': "the Spec256 set's colours for the play window on a double-buffered Layer 2, off by default"}
CMP = ()                           # no hook: nothing runs instead of the game's code


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_gunrunner(snap):
    try:
        mem = snap.memory if hasattr(snap, 'memory') else (bytes(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0])
        return all(bytes(mem[a:a + len(bytes.fromhex(v))]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


class Patch:
    name = 'Gunrunner: the original game, Sinclair ROM as the whole alt ROM'
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
        if not is_gunrunner(snap):
            raise ValueError('Not the supported Gunrunner release (MD5 %s)' % SOURCE_MD5)


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


# ---- Enhanced: the set's colours on a double-buffered Layer 2 (asm/gunrunner_hooks.asm) ----
COLOUR_PAINTER = 'Jao Paulo'
CANVAS_LO = 0x6800              # the canvas: RAM address A's colours at page CBASE + A // 1024, offset (A % 1024) * 8
BUFFER = (0x6A00, 0x7B01)
JP, CALL = 0xC3, 0xCD
SITES = [(0xD5B1, '11016A', JP, 'h_clr'), (0xD986, '7E8787', JP, 'h_tile'), (0xDA0B, '237EFE', JP, 'e_tile'), (0x811D, '3A0982', JP, 'h_fig'),
         (0xD330, 'DD7E0B', JP, 'h_save'), (0xD274, 'DD7E0B', JP, 'h_rest'), (0xD2B1, 'CD37D3', CALL, 'h_sb'),
         (0xD2D3, 'C337D3', JP, 'h_sb'), (0xD1F6, 'CD7BD2', CALL, 'h_rb'), (0xD218, 'C37BD2', JP, 'h_rb'),
         (0xD2DC, '06183E', JP, 'h_s24'), (0xD220, '06183E', JP, 'h_r24'), (0xC688, 'CD17D6', CALL, 'h_bul'),
         (0xC8FB, '21546F', JP, 'h_st1'), (0xC980, '21546F', JP, 'h_st2'), (0xDC0E, '211E6E', JP, 'h_col'), (0xD3B4, '3A78E2', JP, 'h_ffs'),
         (0xD3C4, 'ED7398', JP, 'h_hide'), (0xD5A3, '110140', JP, 'h_cls'), (0xD97A, '21406E', JP, 'h_fill'),
         (0xD942, '21516F', JP, 'h_left'), (0xD95E, '21FE7A', JP, 'h_right'), (0xBF04, 'CDC4D3', CALL, 'h_copy'),
         (0xD4D2, 'CDC4D3', CALL, 'h_copy')]
ENTRIES = sorted({s[3] for s in SITES})


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


def palette_rgb(path=None):
    """The emulator's table: the palette every .256 is painted in. Never in this repo: from `path` (a JSON list of 256 RGB
    ints, staged beside the snapshot) or else read from Jon's local emu256 copy."""
    import re
    import os
    if path is not None:
        out = json.loads(Path(path).read_text())
        assert len(out) == 256
        return out
    t = open(os.environ.get('EMU256', '/home/jon/Downloads/emu256-extract/emu256') + '/datos.js').read()
    m = re.search(r'PALETTE_RGB\s*=\s*\[([^\]]*)\]', t)
    out = [int(x, 0) for x in m.group(1).replace('\n', ' ').split(',') if x.strip()]
    assert len(out) == 256
    return out


def nine(r, g, b):
    q = lambda v: min(7, (v * 7 + 127) // 255)
    r3, g3, b3 = q(r), q(g), q(b)
    return (r3 << 5) | (g3 << 2) | (b3 >> 1), b3 & 1


class Enhanced(Patch):
    name = 'Gunrunner: Enhanced, the Spec256 colours on a Layer 2 canvas'

    def __init__(self, source, set_path, palette_path=None):
        super().__init__(source)
        self.palette_path = palette_path
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
        self.ram[self.syms['V_ATTR'] - 0x2000] = 0xFF
        self.page = bytearray(rom[0x2000:0x4000])
        lo, hi = self.syms['ven_start'], self.syms['ven_end']
        self.page[lo - 0x2000:hi - 0x2000] = self.ram[lo - 0x2000:hi - 0x2000]
        self.altrom = (lo, REGBLOCK + REGS_LEN)
        self.sites = [(a, bytes.fromhex(o), bytes((op,)) + zt.w16(self.syms[n])) for a, o, op, n in SITES]
        self.site_of = {a: n for a, o, op, n in SITES}
        self.set_path = str(set_path)
        self.extra_banks = dict(self._bank12())
        self._snap = None

    def _bank12(self):
        return {PAGE // 2: bytes(self.ram) + bytes(self.page)}

    def palettes(self):
        word, up, down, flags = read_set(self.set_path)
        rgb = palette_rgb(self.palette_path)
        base = [nine(c >> 16, (c >> 8) & 255, c & 255) for c in rgb]
        inks = []
        for t in range(16):
            ink, bright = t & 7, t & 8
            ent = []
            for v in range(192, 256):
                c = rgb[v]
                r, g, b = c >> 16, (c >> 8) & 255, c & 255
                if v == 255:
                    level = 255 if bright else 215
                    e = nine(level if ink & 2 else 0, level if ink & 4 else 0, level if ink & 1 else 0)
                else:
                    level = 191
                    e = nine((r + (level if ink & 2 else 0)) >> 1, (g + (level if ink & 4 else 0)) >> 1, (b + (level if ink & 1 else 0)) >> 1)
                ent.append(e)
            inks.append(ent)
        # Layer 2's transparent colour stays the Next's 0xE3: an entry on it moves one step of blue
        fix = lambda e: (0xE2, 1) if e[0] == 0xE3 else e
        base = [fix(e) for e in base]
        inks = [[fix(e) for e in tb] for tb in inks]
        spare = 0xE3
        page = bytearray(8192)
        o = 0
        for t in inks:
            for e in t:
                page[o:o + 2] = bytes(e)
                o += 2
        o = 0x800
        for e in base:
            page[o:o + 2] = bytes(e)
            o += 2
        return bytes(page), spare

    def canvas(self, snap):
        """{page: 8K} from the set, for this release: a byte the set holds differently keeps the release's picture (mono)."""
        word = read_set(self.set_path)[0]
        rel = lambda a: snap.banks[{1: 5, 2: 2, 3: 0}[a >> 14]][a & 0x3FFF]
        cb = self.syms['CBASE']
        pages = {}
        self.differ = []
        for a in range(CANVAS_LO, 0x10000):
            p = cb + (a >> 10)
            pg = pages.setdefault(p, bytearray(8192))
            if BUFFER[0] <= a < BUFFER[1]:
                continue
            w = word(a)
            if w[8] == rel(a):
                pg[(a & 1023) * 8:(a & 1023) * 8 + 8] = chunky(w)
            else:
                self.differ.append(a)
                pg[(a & 1023) * 8:(a & 1023) * 8 + 8] = mono8(rel(a))
        return pages

    def apply(self, snap):
        if not is_gunrunner(snap):
            raise ValueError('Not the supported Gunrunner release (MD5 %s)' % SOURCE_MD5)
        pages = self.canvas(snap)
        pal, self.spare = self.palettes()
        pages[self.syms['PAL_PAGE']] = pal
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


def build_enhanced(source, destination, set_path, palette_path=None):
    p = Enhanced(source, set_path, palette_path)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


# ---- verification: an independent plane model of the game's buffer writes, against the hooks run from the same state ----
from . import hooklib, simpool   # noqa: E402
CMP_E = tuple(hooklib.CMP_R)
RESUME = {0xD5B1: 0xD5B4, 0xD2B1: 0xD337, 0xD2D3: 0xD337,
          0xD1F6: 0xD27B, 0xD218: 0xD27B, 0xD2DC: 0xD337, 0xD220: 0xD27B, 0xC688: 0xD617, 0xDC0E: 0xDC11,
          0xD3B4: 0xD3B7, 0xD3C4: 0xD3C8, 0xD5A3: 0xD5A6, 0xD942: 0xD94D, 0xD95E: 0xD969}
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


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=4000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st)
    s = simpool.machine(Sim, v, list(regs), 'gunrunner-hook')
    m = Model(s, speed, st.line)
    m.nr.update(st.nr)
    v.nr = m.nr
    n = 0
    R = s.registers
    while n == 0 or (R[24] not in stop_pc if isinstance(stop_pc, tuple) else (R[24] != stop_pc or (stop_sp is not None and R[12] != stop_sp))):
        s.opcodes[v[R[24]]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not terminate: PC %04X, want %04X SP %s; SP now %04X; nr %s' % (R[24], stop_pc, stop_sp, R[12], {k: m.nr.get(k) for k in (0x54, 0x55, 0x56, 0x57, 7)}))
    st.line = m.line()
    for k in (0x12, 0x69):
        st.nr[k] = m.nr[k]
    return list(R), v, m


def _flat(sim):
    m = sim.memory
    return bytearray(bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])) if hasattr(m, 'memory') else bytearray(m)


def set_snapshot_state(patch, source):
    from . import z80tonex
    snap = z80tonex.Z80Snapshot(source)
    patch.apply(snap)
    return snap


class Planes:
    """The set's model of the buffer: each RAM byte as eight pixels (a 64-bit integer), written as the game's own instructions write the mono byte."""
    def __init__(self, patch):
        self.P = [0] * 65536
        cb = patch.syms['CBASE']
        for a in range(CANVAS_LO, 0x10000):
            pg = patch.pages_init[cb + (a >> 10)]
            o = (a & 1023) * 8
            self.P[a] = int.from_bytes(pg[o:o + 8], 'big')
        self.A = 0
        self.used = set()

    def ops(self):
        P = self.P
        H = lambda R: R[6] * 256 + R[7]
        D = lambda R: R[4] * 256 + R[5]
        def load(R):
            a = D(R)
            self.A = P[a]
            self.used.add(a)
        def op_and(R):
            self.A &= P[H(R)]
        def op_xor(R):
            self.A ^= P[H(R)]
        def store(R):
            P[H(R)] = self.A
        def ldi(R):
            P[D(R)] = P[H(R)]
        def zero(R):
            P[H(R)] = 0
        def ones(R):
            P[H(R)] = (1 << 64) - 1
        def save1(R):
            self.A = P[H(R)]
        def save2(R):
            P[D(R)] = self.A
        t = {0x8129: load, 0x812A: op_and, 0x812B: store, 0x8145: load, 0x8146: op_xor, 0x8147: store,
             0xD9D4: load, 0xD9D5: op_and, 0xD9D6: store, 0xD9F8: load, 0xD9FA: store,
             0xC690: load, 0xC691: op_and, 0xC692: store, 0xC694: load, 0xC695: op_xor, 0xC696: store,
             0xCA0D: load, 0xCA0E: op_xor, 0xCA0F: store, 0xD27E: load, 0xD27F: store, 0xD33A: save1, 0xD33B: save2,
             0xDC1D: zero, 0xD3BE: ones, 0xD5B7: zero, 0xD5BC: ldi, 0xD94B: ldi, 0xD967: ldi, 0xDF63: ldi}
        return t


def verify(patch, rzx_path, stop=None, collect=0, progress=None, compare_every=1):
    """Replay the original. At every hook site the hook runs on a copy of the state and the original to the same point: every
    register with R, all 48K RAM but the dead stack, MMU, clock. At every copy in play: canvas and the published Layer 2 window against the
    plane model, the game's buffer against the model's master byte."""
    from collections import Counter, defaultdict
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    ex = defaultdict(list)
    st = State(patch)
    pl = Planes(patch)
    ops = pl.ops()
    states = []
    cb = patch.syms['CBASE']
    win_y, win_x, rows = patch.syms['WIN_Y'], patch.syms['WIN_X'], patch.syms['WIN_ROWS']
    bad = bytes((0xFF,))

    def fail(k, d):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append(d)
    sites = {a: (old, new) for a, old, new in patch.sites if a != 0xDA0B}
    pcs = set(sites) | set(ops) | {0xD9F9}
    pl_pending = []
    shown = [None]

    def on_pc(pc, sim):
        R = sim.registers
        if pc == 0xD9F9:
            if sim.memory[0xD9F9] == 0xAE:
                pl.A ^= pl.P[R[6] * 256 + R[7]]
            return
        if pc in ops:
            ops[pc](R)
            if pc not in sites:
                return
        if pc not in sites:
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
        ref = simpool.machine(Simulator, list(m0), regs, 'gr-ref')
        RR = ref.registers
        sp = regs[12]
        if pc in RESUME:
            stop_pc, stop_sp = RESUME[pc], (sp - 2 if m0[pc] == 0xCD else sp)
        elif pc in (0xD97A, 0x811D, 0xD330, 0xD274, 0xC8FB, 0xC980):   # the hook runs the body too: to its RET
            stop_pc, stop_sp = m0[sp] | m0[sp + 1] << 8, sp + 2
        elif pc == 0xD986:          # one record: to the next, or to the caller
            stop_pc, stop_sp = (0xD986, m0[sp] | m0[sp + 1] << 8), None
        else:                       # the copy: to the caller's next instruction
            stop_pc, stop_sp = pc + 3, sp
        n = 0
        def there(r):
            return (r[24] == stop_pc and r[12] == stop_sp) if stop_sp is not None else r[24] in stop_pc
        while n == 0 or not there(RR):
            ref.opcodes[ref.memory[RR[24]]]()
            n += 1
            if n > 300000:
                raise AssertionError('reference did not reach %04X from %04X' % (stop_pc, pc))
        got, v, model = run_hook(patch, st, patched, regs, stop_pc, stop_sp)
        for i in CMP_E:
            if (bool(RR[i]) != bool(got[i])) if i == 26 else RR[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': RR[i], 'got': got[i]})
        expected = bytearray(ref.memory[0:65536])
        actual = bytearray(v.mem)
        for a, o, nw in patch.sites:
            expected[a:a + 3] = nw
        lo2 = min(sp, stop_sp) if stop_sp is not None else sp
        low = lo2 - 32
        for a in range(low, lo2):
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
        if pc in (0x811D, 0xD330, 0xD274):             # the plane model sees the writes when the replay runs them, after this
            pl_pending.append(pc)
        if patch.site_of[pc] in ('h_hide', 'h_cls') and st.nr[0x69] != 0:
            fail('overlay not hidden', {'pc': hex(pc)})
        c['hooks'] += 1
        c['hooks ' + patch.site_of[pc]] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if patch.site_of[pc] == 'h_copy':
            c['publications'] += 1
            front = st.page[patch.syms['V_BACK'] - 0x2000]   # the picture just drawn; shown by this or a later hook
            if shown[0] is not None and st.nr[0x12] != shown[0]:
                fail('picture never shown', {'pc': hex(pc)})
            shown[0] = front
            # the buffer: canvas against the plane model; the shown window against the canvas
            diff = []
            for a in range(0x6A00, 0x7A7E):
                pg = st.pages[cb + (a >> 10)]
                o = (a & 1023) * 8
                if int.from_bytes(pg[o:o + 8], 'big') != pl.P[a]:
                    diff.append(a)
            if diff:
                a0 = diff[0]
                pg0 = st.pages[cb + (a0 >> 10)]
                fail('canvas differs from the plane model', {'count': len(diff), 'ex': [hex(x) for x in diff[:8]], 'pc': hex(pc), 'canvas': bytes(pg0[(a0 & 1023) * 8:(a0 & 1023) * 8 + 8]).hex(), 'model': pl.P[a0].to_bytes(8, 'big').hex(), 'ram': hex(actual[a0])})
            lit = 0
            for r in range(rows):
                y = win_y + r
                p = st.pages[front * 2 + (y >> 5)]
                o = (y & 31) * 256 + win_x
                seg = bytes(p[o:o + 208])
                a = 0x6A04 + 34 * r
                want = b''.join(pl.P[a + i].to_bytes(8, 'big') for i in range(26))
                if seg != want:
                    fail('published window differs', {'row': r})
                    break
                lit += 208
            c['pixels compared'] += lit
            # missed writers: the model's buffer must have seen every byte's master write (the game's RAM against the planes' bit 7 is not it: compare where the set is mono)
        if progress and c['hooks'] % 25 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), pcs, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    pat = set(a for a in pl.used)
    c['source bytes'] = len(pat)
    c['source bytes the set holds differently'] = len(pat & set(getattr(patch, 'differ', ())))
    patch.used_sources = pat
    return (c, dict(ex), states) if collect else (c, dict(ex))


def stop_of(pc, m0, sp):
    if pc in RESUME:
        return RESUME[pc], (sp - 2 if m0[pc] == 0xCD else sp)
    if pc in (0xD97A, 0x811D, 0xD330, 0xD274, 0xC8FB, 0xC980):
        return m0[sp] | m0[sp + 1] << 8, sp + 2
    if pc == 0xD986:
        return (0xD986, m0[sp] | m0[sp + 1] << 8), None
    return pc + 3, sp


def unit_tests(patch, states, neg=True):
    """Every hook state at the four incoming clocks, both IFF values and four R phases: registers with R, the clock the caller had, MMU back."""
    from collections import Counter
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        sp = regs[12]
        stop_pc, stop_sp = stop_of(pc, mem, sp)
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
                    there = (lambda r: r[24] == stop_pc and r[12] == stop_sp) if stop_sp is not None else (lambda r: r[24] in stop_pc)
                    while n == 0 or not there(R):
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

    def mut(name, old, new, ven=False):
        b = copy.deepcopy(patch)
        i = bytes(b.ram).find(old)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[i:i + len(new)] = new
        out[name] = b
    mut('R off by one', bytes.fromhex('3E73CD'), bytes.fromhex('3E72CD'))
    mut('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mut('XOR pass dropped', bytes.fromhex('1AAE77'), bytes.fromhex('1A0077'))
    mut('AND pass dropped', bytes.fromhex('1AA677'), bytes.fromhex('1A0077'))
    mut('row stride off by one', bytes.fromhex('D5112200'), bytes.fromhex('D5112100'))
    mut('source one page out', bytes.fromhex('CB3FCB3FC60E323E3E'), bytes.fromhex('CB3FCB3FC60F323E3E'))
    mut('MMU slot 7 left mapped', bytes.fromhex('ED915701C9'), bytes.fromhex('ED915702C9'))
    mut('window a pixel to the right', bytes.fromhex('1E18'), bytes.fromhex('1E19'))
    mut('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('ED916980'))
    mut('picture never shown', bytes.fromhex('ED9212FE0E'), bytes.fromhex('000000FE0E'))
    return out


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the Enhanced replay proof -------------------
PUBLISHER = 'Hewson, 1987'
LOAD_SCREEN = 'gunrunner_loading.scr'        # the tape's screen, beside the snapshot: game data, never in this repo
LOAD_MD5 = '0e91e97044f364484428d4db07b3db98'
# Enhanced, beside the snapshot, both or none; never in this repo:
SET_NAME, SET_MD5 = 'gunrunner.256', '63866a2bdf48934940a486c7d5996c9d'                       # the Spec256 set as a .256
PALETTE_NAME, PALETTE_MD5 = 'gunrunner_palette.json', 'cc822d044ec89ffcffbfb3a122f4d088'     # emu256's table (datos.js)
NEG_RECORDING, NEG_STOP = 'a1.rzx', 700      # the broken builds and the ABI states (two a site), as in the review run
# The archive's POKEs for this release, each tested in the simulator (games/gunrunner.md); bank 8 = no paging.
TRAINERS = """NInfinite lives
Z 8 49171 0 0
NNo enemies
Z 8 48838 62 0
NImmunity
Z 8 49081 0 0
NInfinite poison
Z 8 48659 0 0
NInfinite jet pac
M 8 48976 0 0
Z 8 52562 0 0
NInfinite shield
Z 8 49053 0 0
Y
"""


def _beside(z80, file, md5, what):
    """A private input beside the snapshot -> its path, or None. A different file there is refused."""
    import hashlib
    path = Path(z80).resolve().parent / file
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not %s (MD5 %s)' % (file, what, md5))
    return path


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites). -> problems."""
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
            if tail <= a < tail + size or (nexload and 0x5B00 <= a < 0x5C00):
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _enhanced(z80, inputs):
    p = Enhanced(z80, *inputs)
    p.apply(zt.Z80Snapshot(str(z80)))
    return p


def _replay(z80, inputs, rzx, stop, collect):
    """One recording's Enhanced replay (a process of its own) -> (counts, examples, states)."""
    got = verify(_enhanced(z80, inputs), rzx, stop=stop, collect=collect)
    return got if collect else (got[0], got[1], [])


def _negative(z80, inputs, name, rzx, stop):
    """One deliberately broken build's replay (a process of its own): -> (name, its failure keys)."""
    try:
        c, ex = verify(negative_patches(_enhanced(z80, inputs))[name], rzx, stop=stop)
    except Exception as e:                  # noqa: BLE001 - a broken hook that runs off into data is caught too
        return name, ['exception ' + type(e).__name__]
    return name, sorted(k for k in c if k.endswith('!'))


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build (no hook, no game byte changed; Sinclair's ROM as the whole alt ROM) and, with
    the set and the palette beside the snapshot, the Enhanced build; each with the tape's loading screen when it is beside
    the snapshot, as published; every build boot-checked. With --rzx the Enhanced replay proof of each recording, the ABI
    cases and the broken builds (the default runs no hook). The pace, soak, flicker and real loader proofs are the review
    run's (games/gunrunner.md "Evidence")."""
    import concurrent.futures, hashlib, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : Gunrunner (Cybadyne / Hewson, 1987, 48K)')
    say("Engine    : gunrunner; default: the original game, no hook (no clash to remove), Sinclair's ROM as the whole alt "
        "ROM; Enhanced: the Spec256 set's colours for the play window on a double-buffered Layer 2")
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, "the tape's loading screen")
    cset = _beside(z80, SET_NAME, SET_MD5, 'the set this engine was proved with')
    pal = _beside(z80, PALETTE_NAME, PALETTE_MD5, 'the palette this engine was proved with')
    inputs = (cset, pal) if cset and pal else None
    if screen is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    if inputs is None:
        say('Enhanced  : not both of %s, %s beside the snapshot: default build only' % (SET_NAME, PALETTE_NAME))
    builds = [('Default', name, lambda: Patch(z80))]
    if inputs is not None:
        builds.append(('Enhanced', name + '_enhanced', lambda: Enhanced(z80, *inputs)))
    for label, stem, make in builds:
        nex = out / (stem + '.nex')
        zt.convert(str(z80), str(nex), patch=make(), quiet=True)
        nexes = [(label, nex)]
        if screen is not None:
            loading = out / (stem + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen.read_bytes()))
            nexes.append((label[:3] + '+scr', loading))
        for lab, path in nexes:
            bad = boot_check(path, z80, make())
            ok = ok and not bad
            say('%-10s: %s  %s' % (lab, path.name, hashlib.md5(path.read_bytes()).hexdigest()))
            say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)'
                                    if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    if rzxs and inputs is None:
        say('Verify    : FAILED: recordings given but no %s and %s beside the snapshot (the default runs no hook; the '
            'replay proves Enhanced)' % (SET_NAME, PALETTE_NAME))
        ok = False
    elif rzxs:
        quick = getattr(a, 'quick', None)
        neg = next((r for r in rzxs if Path(r).name == NEG_RECORDING), rzxs[0])
        stop = min(quick or NEG_STOP, NEG_STOP)
        jobs = [(r, quick, 0) for r in rzxs] + [(neg, stop, 2)]
        with concurrent.futures.ProcessPoolExecutor(min(len(jobs), os.cpu_count() or 1)) as pool:
            done = list(pool.map(_replay, [z80] * len(jobs), [inputs] * len(jobs), *zip(*jobs)))
        states = []
        for (path, st, collect), (c, ex, got) in zip(jobs, done):
            fail = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fail
            if collect:
                states = got
                if fail:
                    say('Verify    : ABI states (%s to %d): %s' % (Path(path).name, st, fail))
                continue
            say('Verify    : %s %d frames, %d hooks, %d R comparisons, %d Layer 2 pictures, %d pixels: %s' % (
                Path(path).name, c['frames'], c['hooks'], c['R comparisons'], c['publications'], c['pixels compared'],
                'IDENTICAL' if not fail else str(fail)))
            for k, v in ex.items():
                say('            %s: %s' % (k, str(v)[:300]))
        counts = unit_tests(_enhanced(z80, inputs), states)
        fail = {k: v for k, v in counts.items() if k.endswith('!')}
        ok = ok and not fail
        say('Unit      : %s (%d states)' % (dict(counts), len(states)))
        names = list(negative_patches(_enhanced(z80, inputs)))
        with concurrent.futures.ProcessPoolExecutor(min(len(names), os.cpu_count() or 1)) as pool:
            negs = list(pool.map(_negative, [z80] * len(names), [inputs] * len(names), names, [neg] * len(names),
                                 [stop] * len(names)))
        missed = [n for n, keys in negs if not keys]
        ok = ok and not missed
        say('Negatives : %d of %d broken builds caught (%s, %d frames each)%s' % (
            len(negs) - len(missed), len(negs), Path(neg).name, stop, '; MISSED %s' % missed if missed else ''))
    else:
        say('Verify    : not requested; boot evidence only (the default runs no hook)')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
