"""Into the Eagle's Nest (Pandora, 1987, 128K): the original game on the Next; Enhanced colours as a set.

No colour clash: the play area is whole 8x8 tiles, each with its own attribute (8500, tile sets
D200 / DB00, attributes DA00 / E300); figures are blocks of tiles and replace the cells they stand on.
So the default is the game itself, with no hooks. Enhanced mirrors the tiles on Layer 2: asm/into_the_eagles_nest_hooks.asm. Target: the [a][a] dump, already running at its menu: the plain
(128K) dump stops in 128K BASIC, whose statements page ROM 0.
"""
from pathlib import Path
import json
from . import z80tonex as zt
ROOT = Path(__file__).resolve().parents[1]

SOURCE_MD5 = '0566e3b37d49c6fa6f62e81eb883ad0c'
SIGNATURE = {0x8500: '4F3A50BF477B90FE18', 0x8152: 'CD22A6', 0x83AB: 'F53A4CBF', 0x8729: '28F8'}
TAIL_ADDR = 0xB980                 # zero bytes the game never reads or writes (floors 0-4, 6, 7)
TAIL_MAX = 0x80
PRINTER = 0x5B00                   # zero and unused in play; put back after NEXLOAD so the start is exact
DECISIONS = {'figures': 'the original tiles and attributes', 'scenery': 'the original tiles and attributes',
             'outline': 'none', 'enhanced': 'waiting for the mock-up'}


def is_into_the_eagles_nest(snap):
    """The 128K [a][a] dump at its menu: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory)."""
    if getattr(snap, 'banks', None) is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    if not getattr(snap, 'is128', False):
        return False
    return all(bytes(snap.read(a + i) for i in range(len(v) // 2)) == bytes.fromhex(v) for a, v in SIGNATURE.items())


class Patch:
    name = "Into the Eagle's Nest 128K: the original game, no hooks"
    uses_printer_buffer = True
    hook_page_data = b''
    extra_banks = {}
    sites = []
    slot1 = None
    setup_call = zt.STUB_ORG + 0x1000
    tail_addr = TAIL_ADDR
    max_tail = TAIL_MAX

    def __init__(self, source=None):
        self.source = str(source) if source else None
        self.stub_extra = b''

    def apply(self, snap):
        if not is_into_the_eagles_nest(snap):
            raise ValueError("not the Into the Eagle's Nest 128K dump this engine was built for")
        if any(snap.read(a) for a in range(TAIL_ADDR, TAIL_ADDR + TAIL_MAX)):
            raise ValueError('the tail area is not empty')
        printer = bytes(snap.read(PRINTER + i) for i in range(256))
        src = self.setup_call + 12
        code = (b'\x21' + zt.w16(src) + b'\x11' + zt.w16(PRINTER) + b'\x01' + zt.w16(256) + b'\xED\xB0' + b'\xC9')
        assert len(code) == 12
        self.stub_extra = code + printer


COLOURS = 'into_the_eagles_nest_colours.bin'    # built from the Spec256 set: game data, beside the snapshot, never in this repo
PALETTE, BLOB_TILES, BLOB_FONT, BLOB_SPR, BLOB_L2 = 128, 128 + 32768, 128 + 32768 + 8192, 128 + 32768 + 8192 + 16384, 128 + 32768 + 8192 + 16384 + 16384


def load_profile():
    return json.loads((ROOT / 'docs/profiles/into_the_eagles_nest.json').read_text())


class Enhanced(Patch):
    """The Enhanced set: hooks and the colour banks. The game's own bytes change only at the sites below."""
    name = "Into the Eagle's Nest 128K: Enhanced colours on Layer 2 and sprites"
    setup_call = 0xD000

    def __init__(self, source=None, colours=None):
        super().__init__(source)
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.setup = bytes.fromhex(h['setup'])
        self.colours_path = colours or (Path(source).parent / COLOURS)
        self.blob = Path(self.colours_path).read_bytes()
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        S = self.syms
        self.sites = [(0x8514, 'jp', S['h_tile']), (0x9D8C, 'jp', S['h_char']), (0x8458, 'jp', S['h_clear']), (0x8471, 'jp', S['h_draw']),
                      (0x8C94, 'call', S['h_right']), (0x8D22, 'call', S['h_left']), (0x8CFA, 'jp', S['h_step_r']), (0x8D86, 'jp', S['h_step_l']),
                      (0x8DB1, 'call', S['h_up']), (0x8E4A, 'call', S['h_down']), (0x8E06, 'jp', S['h_ud_u']), (0x8EA1, 'jp', S['h_ud_d']),
                      (0x8BFE, 'call', S['h_fast']), (0x8BD6, 'jp', S['h_slow']), (0x91CB, 'jp', S['h_slow2']), (0xBFBF, 'jp', S['h_isr']),
                      (0x83EC, 'jz', S['h_abort'])]
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1E00:0x2000] = bytes(512)
        self._banks()

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for n in ('h_tile', 'h_char', 'h_clear', 'h_draw', 'h_right', 'h_left', 'h_step_r', 'h_step_l', 'h_up', 'h_down', 'h_ud_u', 'h_ud_d', 'h_fast', 'h_slow', 'h_slow2'):
            at = self.syms[n] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        a, b = self.syms['h_isr'] - 0x2000, self.syms['h_isr_end'] - 0x2000
        self.page[a:b] = self.ram[a:b]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 10] = self.ram[at:at + 10]
        b = self.blob
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page),
                            20: b[PALETTE:PALETTE + 16384], 21: b[PALETTE + 16384:PALETTE + 32768],
                            22: b[BLOB_TILES:BLOB_TILES + 8192] + bytes(8192), 23: b[BLOB_FONT:BLOB_FONT + 16384],
                            16: b[BLOB_SPR:BLOB_SPR + 16384], 17: b[BLOB_SPR + 16384:BLOB_SPR + 32768], 18: b[BLOB_SPR + 32768:BLOB_SPR + 49152]}

    def apply(self, snap):
        if not is_into_the_eagles_nest(snap):
            raise ValueError("not the Into the Eagle's Nest 128K dump this engine was built for")
        S = self.syms
        banks = {i: bytearray(snap.banks[i]) for i in range(8)}
        for a, kind, target in self.sites:
            at = a - 0x8000
            banks[2][at:at + 3] = bytes(({'jp': 0xC3, 'call': 0xCD, 'jz': 0xCA}[kind], target & 255, target >> 8))
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in range(8))
        setup = bytearray(self.setup)
        at = S['l2_pal'] - 0xD000
        setup[at:at + 128] = self.blob[:128]
        printer = bytes(snap.read(0x5B00 + i) for i in range(256))
        assert S['printer'] - 0xD000 == len(setup)
        self.stub_extra = bytes(setup) + printer


def build(source, destination, enhanced=False, colours=None):
    p = Enhanced(source, colours) if enhanced else Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


# ---- verification: the Enhanced build against the original, hook by hook -------------------------------------------
from collections import Counter, defaultdict
from . import hooklib, simpool
CMP = tuple(hooklib.CMP_R)
SITES = {0x8514: ('ret', 'h_tile'), 0x9D8C: ('ret', 'h_char'), 0x8458: ('ret', 'h_clear'), 0x8471: ('ret', 'h_draw'),
         0x8C94: (0x8C97, 'h_right'), 0x8D22: (0x8D25, 'h_left'), 0x8DB1: (0x8DB4, 'h_up'), 0x8E4A: (0x8E4D, 'h_down'),
         0x8CFA: ('djnz', 'h_step_r'), 0x8D86: ('djnz', 'h_step_l'), 0x8E06: (0x8E0A, 'h_ud_u'), 0x8EA1: (0x8EA5, 'h_ud_d'),
         0x8BFE: (0xA071, 'h_fast'), 0x8BD6: (0x8BD9, 'h_slow'), 0x91CB: (0x91CE, 'h_slow2'), 0xBFBF: ('isr', 'h_isr')}
SPR_DIGIT = 48
FAST = {'h_fast', 'h_right', 'h_left', 'h_up', 'h_down', 'h_step_r', 'h_step_l', 'h_ud_u', 'h_ud_d'}   # leave the clock at 28 MHz


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class View:
    """64K of the game RAM with the Next pages a hook maps, by the model's MMU."""
    def __init__(self, mem, patch, st):
        self.mem, self.patch, self.st = bytearray(mem), patch, st
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        nr = self.model.nr
        if a < 0x2000:
            return self.mem[a]
        if a < 0x4000:
            return self.st.page[a - 0x2000] if nr[0x51] == 24 else self.patch.page[a - 0x2000]
        if a >= 0xC000:
            s = 0x56 if a < 0xE000 else 0x57
            p = nr[s]
            if p not in (0, 1):
                return self.st.pages[p][a & 8191]
        return self.mem[a]

    def __setitem__(self, a, v):
        nr = self.model.nr
        if a < 0x2000:
            return
        if a < 0x4000:
            if nr[0x51] == 24:
                self.st.page[a - 0x2000] = v
            return
        if a >= 0xC000:
            s = 0x56 if a < 0xE000 else 0x57
            p = nr[s]
            if p not in (0, 1):
                self.st.pages[p][a & 8191] = v
                return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line, lines=311, t_line=228)
        self.nr.update({0x51: 255, 0x56: 0, 0x57: 1, 0x16: 0, 0x17: 0})
        self.nr[1] = 0x32
        self.io = []
        self.ins = []

    def read_port(self, regs, port):
        if port == 0x253B:
            return super().read_port(regs, port)
        self.ins.append(port)
        return 0xFF

    def write_port(self, regs, port, v, *args):
        if port in (0x243B, 0x253B, 0x303B) or port & 255 in (0x57, 0x5B, 0x6B):
            return super().write_port(regs, port, v, *args)
        self.io.append((port, v))


class RefPorts:
    def __init__(self):
        self.io, self.ins = [], []

    def read_port(self, regs, port):
        self.ins.append(port)
        return 0xFF

    def write_port(self, regs, port, v, *args):
        self.io.append((port, v))


class State:
    """What persists between hooks: the hook page, Layer 2 and the colour pages, the sprites, the NextRegs."""
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        b = patch.extra_banks
        self.pages = {}
        for bank, page in ((16, 32), (17, 34), (18, 36), (20, 40), (21, 42), (22, 44), (23, 46)):
            self.pages[page] = bytearray(b[bank][:8192])
            self.pages[page + 1] = bytearray(b[bank][8192:])
        self.attrs = [list(patch.blob[BLOB_FONT + 60 * 256 + n * 4:BLOB_FONT + 60 * 256 + n * 4 + 4]) + [0] for n in range(60)] + [[0] * 5 for _ in range(68)]
        self.nr = {0x16: 0, 0x17: 0}
        self.line = 0
        self.speed = 0


def run_hook(patch, st, mem, regs, stop, limit=8000000, speed=None):
    """stop(R, view) -> True at the hook's return."""
    Sim = _rw()
    v = View(mem, patch, st)
    s = simpool.machine(Sim, v, list(regs), 'eagle-hook')
    m = Model(s, st.speed if speed is None else speed, st.line)
    m.nr.update(st.nr)
    m.attrs = st.attrs
    v.model = m
    n = 0
    R = s.registers
    while n == 0 or not stop(R, v):
        s.opcodes[v[R[24]]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not terminate at %04X' % R[24])
    st.line = m.line()
    st.nr.update({k: m.nr[k] for k in (0x16, 0x17)})
    st.speed = m.nr[7] & 3
    return list(R), v, m


def _flat(sim):
    m = sim.memory
    return bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])


def l2_cell_read(st, ox, oy, cx, cy):
    ry = (cy + oy) % 24
    rx = (cx + ox) % 32
    p = st.pages[32 + (ry >> 2)]
    base = (ry & 3) * 8
    return bytes(p[((base + y) << 8) + rx * 8 + x] for y in range(8) for x in range(8))


def tile_image(patch, tb, i):
    o = PALETTE + (0 if tb == TILESET0 else 16384) + i * 64
    return patch.blob[o:o + 64]


TILESET0 = 0xD2


def font_image(patch, c):
    o = BLOB_TILES + (c - 0x20) * 64
    return patch.blob[o:o + 64]


class Oracle:
    """Independent of the mirror: every play cell's ULA bitmap names the images it may show."""
    def __init__(self, patch, mem):
        self.by = defaultdict(set)
        for tb in (0xD2, 0xDB):
            for i in range(256):
                self.by[bytes(mem[(tb << 8) + i * 8 + j] for j in range(8))].add(tile_image(patch, tb, i))
        for c in range(0x20, 0x80):
            self.by[bytes(mem[0xEDC0 + c * 8 + j] for j in range(8))].add(font_image(patch, c))
        self.digit = {bytes(mem[0xEDC0 + (0x30 + d) * 8 + j] for j in range(8)): d for d in range(10)}


def _scr_addr(r, c, l):
    return 0x4000 | ((r & 0x18) << 8) | ((r & 7) << 5) | c | (l << 8)


DIGITS = [(9, 25 + i) for i in range(6)] + [(11, 29), (11, 30), (13, 29), (13, 30), (15, 29), (15, 30)]


def verify(patch, rzx_path, stop=None, collect=0, progress=None, full_every=1):
    """Replay the original; at every site run the hook on a copy of the state and compare with the original's run: every
    register with R, all 48K RAM bar the site bytes and the dead stack, the clock and MMU, the game's ports (the interrupt's
    AY and border writes, in order). Layer 2 by what each hook must draw, and at every update's end against the ULA."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    orc = [None]
    S = patch.syms
    wr = {}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        kind, sym = SITES[pc]
        if pc == 0x8514 and mem[0x8514] != 0x57:
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        patched = bytearray(mem)
        for a, k, target in patch.sites:
            patched[a:a + 3] = bytes(({'jp': 0xC3, 'call': 0xCD, 'jz': 0xCA}[k], target & 255, target >> 8))
        ref = simpool.machine(Simulator, list(mem), regs, 'eagle-ref')
        ports = RefPorts()
        ref.set_tracer(ports)
        R = ref.registers
        sp = regs[12]
        if kind == 'ret':
            ret = mem[sp] | mem[sp + 1] << 8
            n = 0
            while n == 0 or R[24] != ret or R[12] != sp + 2:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stopf = lambda r, v: r[24] == ret and r[12] == sp + 2
        elif kind == 'isr':
            ret = mem[sp] | mem[sp + 1] << 8
            n = 0
            while n == 0 or R[24] != ret or R[12] != sp + 2:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stopf = lambda r, v: r[24] == ret and r[12] == sp + 2 and r[26]
            if ret == 0 or mem[0x83EC] != 0xCA:
                return
        elif kind == 'djnz':
            ref.opcodes[ref.memory[R[24]]]()
            ref.opcodes[ref.memory[R[24]]]()
            tgt = R[24]
            stopf = lambda r, v: r[24] == tgt
        else:
            n = 0
            while R[24] != kind or n == 0:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            tgt = kind
            stopf = lambda r, v: r[24] == tgt
        before = (st.page[S['V_OX'] - 0x2000], st.page[S['V_OY'] - 0x2000])
        speed0 = st.speed
        got, v, model = run_hook(patch, st, patched, regs, stopf)
        for i in CMP:
            if (bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': R[i], 'got': got[i], 'sym': sym})
                if i == 15:
                    c['R off %s %d' % (sym, (R[i] - got[i]) & 127)] += 1
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, k, target in patch.sites:
            expected[a - 0x4000:a - 0x4000 + 3] = actual[a - 0x4000:a - 0x4000 + 3] = bytes(({'jp': 0xC3, 'call': 0xCD, 'jz': 0xCA}[k], target & 255, target >> 8))
        low = min(sp, regs[12]) - 34
        for a in range(max(0x4000, low), sp):
            expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 and sym != 'h_isr':
            fail('MMU not restored', {'pc': hex(pc), 'slot1': model.nr[0x51]})
        if model.nr[0x56] != 0 or model.nr[0x57] != 1:
            fail('MMU not restored', {'pc': hex(pc), 'sym': sym})
        want_clock = 3 if sym in FAST else (0 if sym in ('h_slow', 'h_slow2') else speed0)
        if model.nr[7] & 3 != want_clock:
            fail('clock differs', {'pc': hex(pc), 'sym': sym, 'got': model.nr[7], 'want': want_clock})
        if model.io != ports.io:
            fail('game ports differ', {'pc': hex(pc), 'sym': sym, 'orig': ports.io[:4], 'got': model.io[:4]})
        if model.ins != ports.ins:
            fail('game reads differ', {'pc': hex(pc), 'sym': sym})
        if sym == 'h_isr' and speed0 == 3 and ('s', st.page[0x3E30 - 0x2000]) not in model.events:
            fail('interrupt not at the game clock', {'pc': hex(pc)})
        if sym == 'h_isr' and model.sel != 7:
            fail('interrupt leaves another register selected', {'pc': hex(pc), 'sel': model.sel})
        c['hooks'] += 1
        c['hooks ' + sym] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        # ---- the picture
        ox, oy = st.page[S['V_OX'] - 0x2000], st.page[S['V_OY'] - 0x2000]
        if st.nr[0x16] != ox * 8 or st.nr[0x17] != oy * 8:
            fail('scroll register differs', {'sym': sym, 'ox': ox, 'oy': oy, 'nr': (st.nr[0x16], st.nr[0x17])})
        m = mem
        if sym == 'h_tile':
            a, e, t = regs[0], regs[5], regs[3]
            tb = m[0xBF41]
            if l2_cell_read(st, ox, oy, e, a) != tile_image(patch, tb, t):
                fail('tile differs', {'tile': t, 'x': e, 'y': a, 'set': tb})
            c['tiles compared'] += 1
        elif sym == 'h_char':
            ch, de = regs[7], regs[4] << 8 | regs[5]
            col = de & 31
            row = (de >> 8 & 0x18) | (de & 0xFF) >> 5
            if col < 24 and 0x20 <= ch < 0x80:
                if l2_cell_read(st, ox, oy, col, row) != font_image(patch, ch):
                    fail('character differs', {'ch': ch, 'col': col, 'row': row})
                c['characters compared'] += 1
            elif (row, col) in DIGITS:
                n = DIGITS.index((row, col))
                at = st.attrs[SPR_DIGIT + n]
                d = ch - 0x30
                want = (0x80 | (48 + d)) if 0 <= d < 10 else 0
                if at[3] != want or (want and (at[0] != (col * 8 + 32) & 255 or at[1] != row * 8 + 32)):
                    fail('digit sprite differs', {'ch': ch, 'at': at, 'cell': (row, col)})
                c['digits compared'] += 1
        elif sym == 'h_clear':
            if (ox, oy) != (0, 0) or any(any(l2_cell_read(st, 0, 0, x, y)) for y in range(24) for x in range(24)):
                fail('clear differs', {})
        elif sym == 'h_draw':
            base = 0x5C00 + m[0xBF51] * 96 + m[0xBF50]
            for y in range(24):
                for x in range(24):
                    if l2_cell_read(st, ox, oy, x, y) != tile_image(patch, 0xD2, m[base + y * 96 + x]):
                        fail('redraw differs', {'x': x, 'y': y})
                        break
            c['redraws compared'] += 1
        elif sym in ('h_right', 'h_left'):
            if ox != (before[0] + (1 if sym == 'h_right' else 31)) % 32 or oy != before[1]:
                fail('step offset differs', {'sym': sym})
            bf50 = regs[0]
            col = 23 if sym == 'h_right' else 0
            base = 0x5C00 + m[0xBF51] * 96 + bf50 + col
            for y in range(24):
                if l2_cell_read(st, ox, oy, col, y) != tile_image(patch, 0xD2, m[base + y * 96]):
                    fail('new column differs', {'y': y})
                    break
            c['columns compared'] += 1
        elif sym in ('h_up', 'h_down'):
            if oy != (before[1] + (23 if sym == 'h_up' else 1)) % 24 or ox != before[0]:
                fail('step offset differs', {'sym': sym})
        elif sym == 'h_slow':
            if orc[0] is None:
                orc[0] = Oracle(patch, m)
            bad = 0
            for y in range(24):
                for x in range(24):
                    bm = bytes(m[_scr_addr(y, x, l)] for l in range(8))
                    im = orc[0].by.get(bm)
                    if im is None or l2_cell_read(st, ox, oy, x, y) not in im:
                        bad += 1
            if bad:
                fail('picture differs from the ULA', {'cells': bad, 'pc': hex(pc)})
            for n, (y, x) in enumerate(DIGITS):
                bm = bytes(m[_scr_addr(y, x, l)] for l in range(8))
                d = orc[0].digit.get(bm)
                at = st.attrs[SPR_DIGIT + n]
                if d is not None and at[3] != 0x80 | (48 + d):
                    fail('digit differs from the ULA', {'cell': (y, x), 'at': at, 'digit': d})
                c['digit cells checked'] += 1
            c['pictures compared'] += 1
            c['cells compared'] += 576
        if progress and c['hooks'] % 2000 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), set(SITES), on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


def unit_tests(patch, states):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R, the clock the caller
    had (or 28 MHz where the hook keeps it), the MMU restored."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        kind, sym = SITES[pc]
        if sym == 'h_isr':
            continue
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15], rr[26] = refresh, iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    ref.set_tracer(RefPorts())
                    R = ref.registers
                    sp = rr[12]
                    if kind == 'ret':
                        ret = mem[sp] | mem[sp + 1] << 8
                        n = 0
                        while n == 0 or R[24] != ret or R[12] != sp + 2:
                            ref.opcodes[ref.memory[R[24]]]()
                            n += 1
                        stopf = lambda r, v: r[24] == ret and r[12] == sp + 2
                    elif kind == 'djnz':
                        ref.opcodes[ref.memory[R[24]]]()
                        ref.opcodes[ref.memory[R[24]]]()
                        tgt = R[24]
                        stopf = lambda r, v: r[24] == tgt
                    else:
                        n = 0
                        while R[24] != kind or n == 0:
                            ref.opcodes[ref.memory[R[24]]]()
                            n += 1
                        tgt = kind
                        stopf = lambda r, v: r[24] == tgt
                    st = State(patch)
                    st.page[patch.syms['V_OX'] - 0x2000] = 3
                    st.page[patch.syms['V_OY'] - 0x2000] = 5
                    st.nr[0x16], st.nr[0x17] = 24, 40
                    st.page[0x3E30 - 0x2000] = speed
                    patched = bytearray(mem)
                    for a, k, target in patch.sites:
                        patched[a:a + 3] = bytes(({'jp': 0xC3, 'call': 0xCD, 'jz': 0xCA}[k], target & 255, target >> 8))
                    got, v, model = run_hook(patch, st, patched, rr, stopf, speed=speed)
                    if any((bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    want = 3 if sym == 'h_fast' else (speed if sym in ('h_slow', 'h_slow2') else (speed if kind == 'ret' else speed))
                    if model.nr[7] & 3 != want:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x56] != 0 or model.nr[0x57] != 1:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def mutate(name, old, new, after=0x2800):
        b = copy.copy(patch)
        b.ram = bytearray(patch.ram)
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.find(bytes.fromhex(old), after - 0x2800)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new) // 2] = bytes.fromhex(new)
        b._banks()
        out[name] = b
    mutate('interrupt leaves another register selected', '013B243E07ED79', '00000000000000', patch.syms['h_isr'] + 30)
    mutate('R off by one', '3EE9CD', '3EEACD')
    mutate('clock left at 28 MHz', 'F53A423EED9207F1', 'F53E0300ED9207F1')
    mutate('interrupt runs at 28 MHz', '3A303EED9207', '000000000000')
    mutate('tile one column off', '3A383E4F3A363E', '3A393E4F3A363E')
    mutate('wrong tile set', 'FED20628', 'BF000628')
    mutate('MMU slot 6 left mapped', 'ED915600ED915701C9', '00000000000000' + '00C9')
    mutate('view step does not move Layer 2', 'ED9216', '000000')
    mutate('new column never drawn', '3E17CD', '3E1721')
    mutate('character not drawn', '3A3E3ED620', 'C93E3ED620')
    mutate('digit sprite wrong', 'C6B0', 'C6B1')
    mutate('clear not black', '3600', '3601')
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}
