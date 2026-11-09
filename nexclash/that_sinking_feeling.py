"""That Sinking Feeling (Sunteam, 2017, 48K-128K, an AGD game): clash removed with figures and objects as hardware sprites; Enhanced colours
from the Spec256 set on Layer 2 and the sprites, by a menu option. See asm/that_sinking_feeling_hooks.asm, games/that_sinking_feeling.md.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/that_sinking_feeling.json'
PALETTE = ROOT / 'docs/profiles/that_sinking_feeling_palette.json'
SOURCE_MD5 = '5123adf2c0e828a380b9e260942def4a'
CMP = tuple(hooklib.CMP_R)
SIGNATURE = {0x8BC0: 'CD6C8C', 0x8BCD: 'CD668C', 0x884D: '3A087D'}
# site: (original, new opcode, symbol, kind, where original and hook meet: 'ret' to the routine's return, else a pc)
COMMON = {0x8B13: ('CD238B', 0xCD, 'h_swap', 'swap', 'ret'), 0x8B1E: ('CD238B', 0xCD, 'h_swap', 'swap', 'ret'),
          0x7FA9: ('CD578C', 0xCD, 'h_old', 'old', 'ret'), 0x86B4: ('CD578C', 0xCD, 'h_old', 'old', 'ret'), 0x8BB3: ('CD578C', 0xCD, 'h_old', 'old', 'ret'),
          0x8BCD: ('CD668C', 0xCD, 'h_new', 'new', 'ret'), 0x8BC0: ('CD6C8C', 0xCD, 'h_both', 'both', 'ret'),
          0x85C6: ('C3DB87', 0xC3, 'h_obj', 'obj', 0x87DB), 0x85E8: ('C3DB87', 0xC3, 'h_obj', 'obj', 0x87DB),
          0x6060: ('F3F5C5', 0xC3, 'isr_w', 'isrw', 0x6063), 0x608C: ('F108FD', 0xC3, 'isr_x', 'isrx', 0x6090),
          0x791F: ('CDAF0D', 0xCD, 'h_cls', 'cls', 0x0DAF), 0x7F8F: ('CD4D88', 0xCD, 'h_room', 'room', 0x884D), 0x8387: ('CD4D88', 0xCD, 'h_room', 'room', 0x884D)}
ENH = {0x877F: ('7E1223', 0xC3, 'h_cell', 'cell', 0x8782), 0x81B0: ('DD7E03', 0xC3, 'h_dot', 'dot', 0x81B3),
       0x7F92: ('CD9D85', 0xCD, 'h_ra', 'rend', 0x859D), 0x838A: ('CDEE82', 0xCD, 'h_rb', 'rend', 0x82EE)}
L2_PAGE, BG_PAGE, FONT_T, BLOCK_T, SP_PAGE = 32, 38, 80, 81, 82
ROM2 = 0x3880                       # the entries and exits, in both copies of the page
BG_ORDER = 7
FIGURE_COLOUR = 0xFD                # the ink the figures have in open water under the game's ULA+ palette: (255, 255, 109)
FIGS, N_FRAMES, FRAMES_AT = 0x8F2E, 24, 0x9062
ALT_FRAMES, FIRST_ALT = (11, 12), 34
OBJS, N_OBJS, OBJ_STEP = 0xD0B1, 10, 38
FONT_BASE, BLOCK_BASE, N_BLOCKS = 0x7900, 0x9C62, 53
DOTS = 0xD96E
DECISIONS = {'figures': 'hardware sprites: their own colour in the default look', 'scenery': 'keeps its own attributes', 'pace': "the game's own frame wait",
             'outline': 'none', 'enhanced': 'the Spec256 set: Layer 2 for scenery and backdrop, sprites for figures and objects'}
PUBLISHER = 'Sunteam, 2017'
PLANES = 131072 * 9
RULES = {0x19: 0, 0x00: 6, 0x04: 1, 0x08: 2, 0x0C: 3, 0x10: 4, 0x15: 5, 0x17: 0}   # SinkFeel.CFG: B0n when (32027) = value


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_tsf(snap):
    banks = getattr(snap, 'banks', None)
    mem = bytes(16384) + banks[5] + banks[2] + banks[0] if banks is not None else bytes(snap.memory)
    try:
        return all(mem[a:a + len(v) // 2] == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (TypeError, IndexError):
        return False


class ColourSet:
    """The player's own .256 and the set's backdrops: nothing of them is in this repository."""
    def __init__(self, path, backdrops):
        self.d = open(path, 'rb').read()
        self.backdrops = backdrops

    def planes(self, a):
        w = ((5, 2, 0)[(a >> 14) - 1] * 16384 + (a & 16383)) * 9
        return self.d[w:w + 8]

    def pixels(self, a):
        pl = self.planes(a)
        return bytes(sum(((pl[p] >> (7 - k)) & 1) << p for p in range(8)) for k in range(8))

    def backdrop(self, n):
        """Layer 2's layout, 256 x 192 of the set's 320 x 200, as the .256 crops it. 255 stays clear of the transparent index."""
        b = open(self.backdrops % n, 'rb').read()
        out = bytearray(256 * 192)
        for y in range(192):
            out[y * 256:y * 256 + 256] = b[(y + 4) * 320 + 32:(y + 4) * 320 + 288]
        return bytes(254 if v == 255 else v for v in out)


def art(path, backdrops, mem):
    """-> the pages: default and Enhanced sprite patterns, font and block tables, backdrops, palette. mem: the game's 64K.
    path None (no set): the default's patterns only, which come from the game's own masks; nothing for Enhanced."""
    s = ColourSet(path, backdrops) if path else None
    pal = json.loads(PALETTE.read_text())
    entries = []
    for c in pal:
        r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
        hi = ((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6)
        lo = (b >> 5) & 1
        entries.append((0xE2 if hi == 0xE3 else hi, lo))
    entries[255] = (0xE3, 1)
    base, enh = bytearray(), bytearray()
    report = dict(figure_ff=0, phase_rows_differ=0)

    def pattern(addrs):
        nb = bytearray(256)
        ne = bytearray(256)
        for r, (a0, a1) in enumerate(addrs):
            m = mem[a0] << 8 | mem[a1]
            v = s.pixels(a0) + s.pixels(a1) if s else bytes(16)
            for k in range(16):
                if m & (0x8000 >> k):
                    nb[r * 16 + k] = FIGURE_COLOUR
                ne[r * 16 + k] = v[k]
                if v[k] == 255:
                    report['figure_ff'] += 1
        return nb, ne
    for f in range(N_FRAMES):
        a = FRAMES_AT + f * 128
        nb, ne = pattern([(a + 2 * r, a + 2 * r + 1) for r in range(16)])
        base += nb
        enh += ne
    for i in range(N_OBJS):
        a = OBJS + i * OBJ_STEP
        nb, ne = pattern([(a + 2 * r, a + 2 * r + 1) for r in range(16)])
        base += nb
        enh += ne
    # The jellyfish (frames 11, 12): the set paints the tentacles yellow at shifts 0, 2 and red at 1, 3. Two more patterns, the
    # shift 1 pre-shift rotated back to the sprite's place.
    for f in ALT_FRAMES:
        a = FRAMES_AT + f * 128
        nb, ne = pattern([(a + 2 * r, a + 2 * r + 1) for r in range(16)])
        for r in range(16 if s else 0):
            v = s.pixels(a + 32 + 2 * r) + s.pixels(a + 32 + 2 * r + 1)
            for k in range(16):
                ne[r * 16 + k] = v[(k + 2) % 16]
        base += nb
        enh += ne
    if s is None:
        return dict(set=None, base=bytes(base), enh=None, font=None, block=None, bgs=None, l2pal=None, report=report)
    font = bytearray(8192)
    for g in range(128):
        for r in range(8):
            font[g * 64 + r * 8:g * 64 + r * 8 + 8] = s.pixels(FONT_BASE + g * 8 + r)
    block = bytearray(8192)
    for g in range(N_BLOCKS):
        for r in range(8):
            block[g * 64 + r * 8:g * 64 + r * 8 + 8] = s.pixels(BLOCK_BASE + g * 8 + r)
        block[0x1F00 + g] = 1 if any(block[g * 64:g * 64 + 64]) else 0
    bgs = [s.backdrop(n) for n in range(BG_ORDER)]
    return dict(set=s, base=bytes(base), enh=bytes(enh), font=bytes(font), block=bytes(block), bgs=bgs, l2pal=bytes(x for e in entries for x in e), report=report)


def game_mem(z80):
    s = zt.Z80Snapshot(z80)
    return bytes(16384) + bytes(s.banks[5]) + bytes(s.banks[2]) + bytes(s.banks[0])


def _pad(b):
    return b + bytes(16384 - len(b))


class Patch:
    uses_printer_buffer = False
    hook_page_data = b''
    tail_addr = 0x5E00

    def __init__(self, source=None, enhanced=False, art=None):
        self.source = str(source) if source else None
        self.enhanced = enhanced
        self.art = art
        self.name = 'That Sinking Feeling: ' + ('Enhanced colours from the Spec256 set' if enhanced else 'figures and objects as hardware sprites')
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.code2 = bytes.fromhex(h['rom2'])
        st = bytearray(bytes.fromhex(h['setup']))
        if enhanced:
            st[self.syms['setup_enh'] - self.syms['setup'] + 1] = 1
            at = self.syms['e_palette'] - self.syms['setup']
            st[at:at + 512] = art['l2pal']
        self.stub_extra = bytes(st)
        self.setup_call = self.syms['setup']
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        rom = zt.rom48()
        self.ram = bytearray(rom[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[ROM2 - 0x2000:ROM2 - 0x2000 + len(self.code2)] = self.code2
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[0x3E3D - 0x2000] = BG_PAGE
        if enhanced:
            self.ram[0x3E3C - 0x2000] = 1
        self.site_info = dict(COMMON)
        if enhanced:
            self.site_info.update(ENH)
        self.sites = [(a, bytes.fromhex(old), bytes((op,)) + zt.w16(self.syms[sym])) for a, (old, op, sym, k, m) in self.site_info.items()]
        if enhanced:
            self.sites.append((0x7FC4, b'\x01', b'\x00'))    # the set is drawn for the Spectrum's colours: ULA+ stays off (7FC3 LD A,1 / OUT (FF3B))
        self._banks()

    def _banks(self):
        rom = zt.rom48()
        self.page = bytearray(rom[0x2000:0x4000])
        self.page[ROM2 - 0x2000:ROM2 - 0x2000 + len(self.code2)] = self.ram[ROM2 - 0x2000:ROM2 - 0x2000 + len(self.code2)]
        a = self.art
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}
        self.extra_banks[SP_PAGE // 2] = _pad(a['enh'] if self.enhanced else a['base'])
        if self.enhanced:
            for n, bg in enumerate(a['bgs']):
                for i in range(3):
                    self.extra_banks[BG_PAGE // 2 + n * 3 + i] = bg[i * 16384:(i + 1) * 16384]
            for i in range(3):
                self.extra_banks[L2_PAGE // 2 + i] = bytes(16384)
            self.extra_banks[FONT_T // 2] = a['font'] + a['block']

    def apply(self, snap):
        if not is_tsf(snap):
            raise ValueError('Not the supported That Sinking Feeling release (MD5 %s)' % SOURCE_MD5)
        banks = {i: bytearray(snap.banks[i]) for i in range(8)}
        for a, old, new in self.sites:
            b, at = (5, a - 0x4000) if a < 0x8000 else (2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000)
            if bytes(banks[b][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[b][at:at + len(new)] = new
        st = bytearray(self.stub_extra)
        at = self.syms['pb_copy'] - self.syms['setup']
        st[at:at + 256] = banks[5][0x1B00:0x1C00]
        self.stub_extra = bytes(st)
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in range(8))


class View:
    def __init__(self, mem, patch, st):
        self.mem = bytearray(mem)
        self.patch, self.st = patch, st
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        s = a >> 13
        if s == 0:
            return self.mem[a]
        if s == 1:
            return self.patch.page[a - 0x2000] if self.model.nr.get(0x51, 255) == 255 else self.st.page[a - 0x2000]
        if s == 4 or s == 5:
            m = self.model.nr.get(0x50 + s, s)
            if m != s:
                return self.st.read(m, a & 8191)
        return self.mem[a]

    def __setitem__(self, a, v):
        s = a >> 13
        if s == 0:
            return
        if s == 1:
            if self.model.nr.get(0x51, 255) == 24:
                self.st.page[a - 0x2000] = v
            return
        if s == 4 or s == 5:
            m = self.model.nr.get(0x50 + s, s)
            if m != s:
                self.st.write(m, a & 8191, v)
                return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, st, speed=0, line=0):
        super().__init__(sim, speed, line=line)
        self.nr.update({0x51: 255, 0x54: 4, 0x55: 5})
        self.io = []
        self.st = st

    def write_port(self, regs, port, v, *args):
        if port == 0x303B:
            self.st.spi = v & 127
            self.st.spn = 0
            return None
        if port & 255 == 0x57:
            self.st.sprites[self.st.spi][self.st.spn & 3] = v
            self.st.spn += 1
            if self.st.spn == 4:
                self.st.spi = (self.st.spi + 1) & 127
                self.st.spn = 0
            return None
        if port in (0x243B, 0x253B) or port & 255 == 0x6B:
            return super().write_port(regs, port, v, *args)
        self.io.append((port, v))


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class State:
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.patch = patch
        self.sprites = [[0, 0, 0, 0] for _ in range(128)]
        self.spi = self.spn = 0
        self.l2 = {p: bytearray(8192) for p in range(L2_PAGE, L2_PAGE + 6)}
        self.nr = {7: 0}
        self.line = 0

    def read(self, m, o):
        if m in self.l2:
            return self.l2[m][o]
        a = self.patch.art
        if BG_PAGE <= m < BG_PAGE + 42:
            n, i = divmod(m - BG_PAGE, 6)
            return a['bgs'][n][i * 8192 + o]
        if m == FONT_T:
            return a['font'][o]
        if m == BLOCK_T:
            return a['block'][o]
        raise AssertionError('hook read page %d' % m)

    def write(self, m, o, v):
        if m not in self.l2:
            raise AssertionError('hook wrote page %d' % m)
        self.l2[m][o] = v


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=20000000):
    Sim = _rw()
    v = View(mem, patch, st)
    s = simpool.machine(Sim, v, list(regs), 'tsf-hook')
    m = Model(s, st, st.nr[7], st.line)
    v.model = m
    n = 0
    R = s.registers
    while n == 0 or R[24] != stop_pc or (stop_sp is not None and R[12] != stop_sp):
        s.opcodes[v[R[24]]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not terminate at %04X' % R[24])
    st.line = m.line()
    st.nr[7] = m.nr[7]
    return list(R), v, m


def _flat(sim):
    mem = sim.memory
    if hasattr(mem, 'banks'):
        return bytes(16384) + bytes(mem.banks[5]) + bytes(mem.banks[2]) + bytes(mem.banks[mem.o7ffd & 7]) if False else _rom(mem) + bytes(mem.banks[5]) + bytes(mem.banks[2]) + bytes(mem.banks[mem.o7ffd & 7])
    return bytes(mem)


def _rom(mem):
    return bytes(mem[a] for a in range(0x4000))


class Picture:
    """What should be on screen, from the plots' registers, the set's own planes and backdrops; never from the hooks' tables."""
    def __init__(self, patch):
        self.a = patch.art
        self.cs = patch.art['set']
        self.px = bytearray(256 * 192)
        self.bg = 0
        self.shown = {}
        self.lit = {}
        self.dot = {}
        self.cells = {}

    def rule(self, mem):
        v = mem[0x7D1B]
        if v in RULES:
            self.bg = RULES[v]

    def clear(self, rows):
        b = self.a['bgs'][self.bg]
        self.px[:rows * 2048] = b[:rows * 2048]
        self.cells = {k: v for k, v in self.cells.items() if k[0] >= rows}
        self.shown = {}
        self.dot = {}

    def cell(self, mem, src, attr, row, col):
        b = self.a['bgs'][self.bg]
        ink = attr & 7
        for r in range(8):
            p = self.cs.pixels((src + r) & 0xFFFF)
            for k in range(8):
                x, y = col * 8 + k, row * 8 + r
                g = b[y * 256 + x]
                v = p[k]
                if v == 0:
                    o = g
                elif v == 255 and ink != 7 and g:
                    o = g
                elif v == 255:
                    o = 255
                else:
                    o = v
                self.px[y * 256 + x] = o
        self.cells[(row, col)] = bytes(mem[(src + r) & 0xFFFF] for r in range(8))

    def toggle_dot(self, y, x, i):
        at = y * 256 + x
        if self.dot.get(i) is None:
            self.dot[i] = self.px[at]
            self.px[at] = 255
        else:
            self.px[at] = self.dot.pop(i)

    def against_ula(self, mem, skip=None):
        """A cell the model printed holds that glyph on the ULA, but for figures, objects and dots XORed over it."""
        return []


def _sprite(st, i):
    s = st.sprites[i]
    if not s[3] & 0x80:
        return None
    x = s[0] | (s[2] & 1) << 8
    return x - 32, s[1] - 32, s[3] & 0x7F


def _l2(st):
    return b''.join(bytes(st.l2[p]) for p in range(L2_PAGE, L2_PAGE + 6))


def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=64, first_failure=False):
    """Replay the original; at every site run the hook on a copy of the state and compare with the original's run to where they meet again:
    every register with R and all 48K RAM. Sprites against the game's own figure and object plots after every plot; Layer 2 against an
    independent picture from the set's planes and backdrops."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    pic = Picture(patch)
    info = patch.site_info
    obj_on = {}
    allp = {}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
        if first_failure:
            raise _Stop()

    def patched(mem):
        p = bytearray(mem)
        for a, old, new in patch.sites:
            p[a:a + len(new)] = new
        return p

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        old, op, sym, kind, meet = info[pc]
        if mem[pc:pc + 3] != bytes.fromhex(old):
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ref = simpool.machine(Simulator, list(mem), regs, 'tsf-ref')
        R = ref.registers
        sp = regs[12]
        ix = regs[8] << 8 | regs[9]
        hsp = None
        if meet == 'ret':
            ret = (pc + 3) & 0xFFFF
            n = 0
            while n == 0 or R[24] != ret or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stop_pc, hsp = ret, sp
        else:
            n = 0
            while n == 0 or R[24] != meet:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stop_pc = meet
        got, v, model = run_hook(patch, st, patched(mem), regs, stop_pc, hsp)
        for i in CMP:
            if (bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': R[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, _, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        for a in range(max(0x4000, min(sp, got[12]) - 40), min(sp, got[12])):
            expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if kind != 'isrx' and (model.nr[0x51] != 255 or model.nr[0x54] != 4 or model.nr[0x55] != 5):
            fail('MMU not restored', {'pc': hex(pc)})
        want_clock = 3 if (kind == 'room' and patch.enhanced) else 0
        if st.page[0x3E3E - 0x2000]:        # a room at 28 MHz
            want_clock = 3
        if model.nr[7] != want_clock:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7], 'want': want_clock})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        # sprites, from the record the game's own plot reads
        def frame_of(sp_, fr, x=0):
            t = mem[0x7D3B] | mem[0x7D3C] << 8
            f = (mem[(t + 2 * sp_) & 0xFFFF] + fr) & 255
            return f - ALT_FRAMES[0] + FIRST_ALT if f in ALT_FRAMES and x & 2 else f
        def slot():
            return (ix - FIGS) // 15
        if kind in ('new', 'both'):
            want = ((mem[ix + 9] & 0xFE), mem[ix + 8], frame_of(mem[ix + 6], mem[ix + 7], mem[ix + 9]))
            if _sprite(st, slot()) != want:
                fail('figure sprite differs', {'pc': hex(pc), 'got': _sprite(st, slot()), 'want': want})
            allp[slot()] = want
            c['sprites compared'] += 1
            # the measure of the clash: figure pixels in cells whose ink is not the figure's white
            fa = FRAMES_AT + want[2] * 128
            for r in range(16):
                m_ = mem[fa + 2 * r] << 8 | mem[fa + 2 * r + 1]
                for k in range(16):
                    if m_ & (0x8000 >> k):
                        cy, cx = (want[1] + r) >> 3, (want[0] + k) >> 3
                        c['figure pixels'] += 1
                        if cy < 24 and cx < 32 and mem[0x5800 + cy * 32 + cx] & 7 != 7:
                            c['figure pixels in another ink'] += 1
        elif kind == 'old':
            if _sprite(st, slot()) is not None:
                fail('figure sprite not hidden', {'pc': hex(pc)})
            old_rec = ((mem[ix + 4] & 0xFE), mem[ix + 3], frame_of(mem[ix + 1], mem[ix + 2], mem[ix + 4]))
            if allp.get(slot()) != old_rec:
                c['old plot of a place the model has not (warn)'] += 1
            allp.pop(slot(), None)
            c['sprites compared'] += 1
        elif kind == 'swap':
            a, b_ = slot(), slot() + 1
            pa, pb = allp.pop(a, None), allp.pop(b_, None)
            if pb is not None:
                allp[a] = pb
            if pa is not None:
                allp[b_] = pa
            for k_, w_ in ((a, pb), (b_, pa)):
                if _sprite(st, k_) != w_:
                    fail('sprite not swapped with its record', {'pc': hex(pc), 'slot': k_, 'got': _sprite(st, k_), 'want': w_})
            c['sprites compared'] += 2
        elif kind == 'obj':
            hl = regs[6] << 8 | regs[7]
            i = (hl - OBJS) // OBJ_STEP
            obj_on[i] = not obj_on.get(i, False)
            want = ((mem[0x7D32] & 0xFE), mem[0x7D31], 24 + i) if obj_on[i] else None
            if _sprite(st, 12 + i) != want:
                fail('object sprite differs', {'pc': hex(pc), 'got': _sprite(st, 12 + i), 'want': want, 'i': i})
            c['sprites compared'] += 1
        elif kind in ('cls', 'room'):
            obj_on.clear()
            allp.clear()
            if any(_sprite(st, i) is not None for i in range(22)):
                fail('sprites left on', {'pc': hex(pc)})
            if patch.enhanced:
                pic.rule(mem)
                pic.clear(24 if kind == 'cls' else 23)
        elif kind == 'cell':
            hl = regs[6] << 8 | regs[7]
            row, col = mem[0x7D31], mem[0x7D32]
            attr = mem[0x5C8D] if hl < 0x9000 else mem[0x5800 + row * 32 + (col & 31)]
            pic.cell(mem, hl, attr, row, col)
        elif kind == 'dot':
            if mem[ix + 3] < 0xC0:
                if mem[ix] == 0:
                    c['laser dots left to the ULA'] += 1
                else:
                    pic.toggle_dot(mem[ix + 3], mem[ix + 5], (ix - (mem[0x7D53] | mem[0x7D54] << 8)) // 6)
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if patch.enhanced and kind in ('cell', 'dot', 'cls', 'rend') and (c['hooks'] % every == 0 or kind in ('cls', 'rend')):
            got_l2 = _l2(st)
            if got_l2 != bytes(pic.px):
                diff = [i for i, (a, b) in enumerate(zip(got_l2, pic.px)) if a != b]
                fail('Layer 2 differs from the set', {'pc': hex(pc), 'sym': sym, 'count': len(diff), 'ex': [(i % 256, i // 256, got_l2[i], pic.px[i]) for i in diff[:6]]})
            c['Layer 2 pictures compared'] += 1
            c['Layer 2 pixels compared'] += 49152
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    try:
        frames, err = trace(str(rzx_path), set(info), on_pc, stop)
    except _Stop:
        return c, dict(examples)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


class _Stop(Exception):
    pass


def pattern_ram(patch, regs):
    """The start-up's sprite upload, run alone: what it sends to port 5B, from the pages as the build holds them."""
    art = patch.extra_banks[SP_PAGE // 2]
    st = State(patch)

    class Mem(View):
        def __getitem__(self, a):
            if a < 0x2000:
                m = self.model.nr.get(0x50, 255)
                return art[(m - SP_PAGE) * 8192 + a] if m in (SP_PAGE, SP_PAGE + 1) else 0xFF
            if a < 0x4000:
                return patch.page[a - 0x2000]
            return patch.stub_extra[a - patch.syms['setup']] if a >= patch.syms['setup'] else 0

        def __setitem__(self, a, v):
            pass
    v = Mem(bytes(65536), patch, st)
    rr = list(regs)
    rr[24] = patch.syms['sp_load']
    s = simpool.machine(_rw(), v, rr, 'tsf-hook')
    m = Model(s, st, 0, 0)
    v.model = m
    n = 0
    while s.registers[24] != patch.syms['setup_enh']:
        s.opcodes[v[s.registers[24]]]()
        n += 1
        if n > 200000:
            raise AssertionError('upload did not end')
    return bytes(val for port, val in m.io if port & 255 == 0x5B), m.nr.get(0x50, 255)


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the caller had; the MMU
    restored. The ISR's two ends with a hook interrupted: slot 1 kept at entry and put back after the second OUT."""
    from skoolkit.simulator import Simulator
    c = Counter()
    info = patch.site_info

    def patched(mem):
        p = bytearray(mem)
        for a, old, new in patch.sites:
            p[a:a + len(new)] = new
        return p
    want = patch.art['enh'] if patch.enhanced else patch.art['base']
    got, left = pattern_ram(patch, states[0][1])
    c['pattern bytes uploaded'] = len(got)
    if got != want:
        c['pattern RAM differs from the art!'] += 1
    if left != 255:
        c['slot 0 not given back after the upload!'] += 1
    for pc, regs, mem in states:
        old, op, sym, kind, meet = info[pc]
        p = patched(mem)
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    R = ref.registers
                    sp = rr[12]
                    if meet == 'ret':
                        ret = (pc + 3) & 0xFFFF
                        n = 0
                        while n == 0 or R[24] != ret or R[12] != sp:
                            ref.opcodes[ref.memory[R[24]]]()
                            n += 1
                        stop, hsp = ret, sp
                    else:
                        n = 0
                        while n == 0 or R[24] != meet:
                            ref.opcodes[ref.memory[R[24]]]()
                            n += 1
                        stop, hsp = meet, None
                    st = State(patch)
                    st.nr[7] = speed
                    got, v, model = run_hook(patch, st, p, rr, stop, hsp)
                    if any((bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    want = 3 if (kind == 'room' and patch.enhanced) else 0 if (kind == 'rend') else speed
                    if kind == 'rend':
                        want = st.page[0x3E3F - 0x2000]
                    if model.nr[7] != want:
                        c['incoming clock not restored!'] += 1
                    if kind != 'isrx' and (model.nr[0x51] != 255 or model.nr[0x54] != 4 or model.nr[0x55] != 5):
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
        if kind == 'obj':
            # shown at one plot, off at the next (the recordings collect no object)
            st = State(patch)
            rr = list(regs)
            run_hook(patch, st, p, rr, 0x87DB)
            i = ((regs[6] << 8 | regs[7]) - OBJS) // OBJ_STEP
            if _sprite(st, 12 + i) is None:
                c['object sprite not shown!'] += 1
            run_hook(patch, st, p, rr, 0x87DB)
            if _sprite(st, 12 + i) is not None:
                c['object sprite not hidden at its second plot!'] += 1
            c['object toggle cases'] += 1
        if kind == 'isrw':
            st = State(patch)
            v = View(p, patch, st)
            s = simpool.machine(_rw(), v, list(regs), 'tsf-hook')
            m = Model(s, st)
            m.nr[0x51] = 24
            v.model = m
            n = 0
            while s.registers[24] != 0x6063 and n < 200:
                s.opcodes[v[s.registers[24]]]()
                n += 1
            if m.nr.get(0x7F) != 24:
                c['slot 1 not kept by the ISR!'] += 1
            c['ISR-in-hook cases'] += 1
        if kind == 'isrx':
            st = State(patch)
            v = View(p, patch, st)
            s = simpool.machine(_rw(), v, list(regs), 'tsf-hook')
            m = Model(s, st)
            m.nr[0x7F] = 24
            v.model = m
            n = 0
            while s.registers[24] != 0x6090 and n < 200:
                s.opcodes[v[s.registers[24]]]()
                n += 1
            if m.nr.get(0x51) != 24:
                c['slot 1 not put back by the ISR!'] += 1
            c['ISR-in-hook cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def mutate(name, sym, old, new, enh=False):
        if enh and not patch.enhanced:
            return
        b = copy.deepcopy(patch)
        at = patch.syms[sym] - 0x2000
        i = bytes(b.ram).find(bytes.fromhex(old), at)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[i:i + len(bytes.fromhex(new))] = bytes.fromhex(new)
        b._banks()
        out[name] = b
    b = copy.deepcopy(patch)
    st_ = bytearray(b.stub_extra)
    at_ = bytes(st_).find(bytes((0xED, 0x91, 0x50, SP_PAGE + 1)))
    st_[at_ + 3] = SP_PAGE
    b.stub_extra = bytes(st_)
    out['upload reads the first page twice'] = b
    mutate('R off by one', 'h_new', '3EEE', '3EEF')
    mutate('jellyfish odd shift not used', 'fig_new', 'CB4B', 'CB7B')
    mutate('clock left at 28 MHz', 'h_new', '3A303EED9207', '3E0300ED9207')
    mutate('figure sprite never shown', 'h_new', 'CD' + patch.syms['fig_new'].to_bytes(2, 'little').hex(), '000000')
    mutate('figure x one column off', 'fig_new', 'E6FE', 'E6F6')
    mutate('figure y wrong', 'fig_new', 'DD7E08', 'DD7E03')
    mutate('wrong frame', 'fig_new', 'DD8607', 'DD8602')
    mutate('figure sprite never hidden', 'h_old', 'CD' + patch.syms['fig_off'].to_bytes(2, 'little').hex(), '000000')
    mutate('wrong figure slot', 'fig_new', 'D60F04', 'D60F00')
    mutate('object sprite left on', 'obj_body', 'EE01', 'F601')
    mutate('object wrong y', 'obj_body', '3A317D', '3A327D')
    mutate('sprites not hidden at a room', 'h_room', 'CD' + patch.syms['all_off'].to_bytes(2, 'little').hex(), '000000')
    mutate('sprites not hidden at CLS', 'h_cls', 'CD' + patch.syms['all_off'].to_bytes(2, 'little').hex(), '000000')
    mutate('ISR entry R wrong', 'isr_w', 'C6EB', 'C6EC')
    mutate('ISR exit R wrong', 'isr_x', 'C6FA', 'C6FB')
    mutate('backdrop not laid at a room', 'h_room', 'CD' + patch.syms['l2_lines'].to_bytes(2, 'little').hex(), '000000', True)
    mutate('backdrop not laid at CLS', 'h_cls', 'CD' + patch.syms['l2_lines'].to_bytes(2, 'little').hex(), '000000', True)
    mutate('rule ignored', 'h_room', 'CD' + patch.syms['pick_bg'].to_bytes(2, 'little').hex(), '000000', True)
    mutate('room left at 28 MHz', 'h_rb', '3A3F3E32303E', '3E0332303E00', True)
    mutate('swap left out', 'h_swap', 'CD' + patch.syms['fig_swap'].to_bytes(2, 'little').hex(), '000000')
    mutate('cell: x wrong', 'cell_body', '3A327D', '3A317D', True)
    mutate('cell: transparent treated as colour', 'cell_body', '3C20', '0020', True)
    mutate('cell: Layer 2 page left mapped', 'cell_body', 'ED915505', '00000000', True)
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop, first_failure=True)
    return {k: v for k, v in c.items() if k.endswith('!')}


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the replay proof of both modes ---------------
LOAD_SCREEN, LOAD_MD5 = 'that_sinking_feeling_loading.scr', '56e2886a9e1c74956b96db96fd9f0bb4'   # the tape's screen: game data
# Enhanced, beside the start state, all or none; game data from the Spec256 set and its source folder, never in this repo:
SET_NAME, SET_MD5 = 'that_sinking_feeling.256', 'a10321c6576f04cf8afc4c90618ed4e6'      # the set (That Sinking Feeling.256)
BACKDROPS = 'that_sinking_feeling.B0%d'                   # the source folder's SinkFeel.B00-B06, 320 x 200 each
BACKDROP_MD5 = ('9e8a82c1a2e210fa3a4868b1a47d6b49', 'af853fee9da3ce952f3f757987de6dba', 'ac927d60ac44b84a4eda13e9b3180e09',
                '6629b92e57a6c076dc322c9e41457f16', 'cf55f8deb9cafc35b1256e20f125eac8', '3ec9e8371b22ccf2090413e4085e76c9',
                'edea278ab1cdf8a8e4a312466eac6934')
DEFAULT_RZX = ('a1.rzx', 'over.rzx', 'tour.rzx')          # the default's replays, as in the review run; Enhanced replays all
NEG_RZX, NEG_STOP = ('a1.rzx', 'tour.rzx'), 12000         # each broken build on these in turn, to its first failure
# The archive's one, tested (games/that_sinking_feeling.md); bank 8 = no paging.
TRAINERS = """NInfinite lives
Z 8 31157 0 0
Y
"""


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def _beside(z80, file, md5, what):
    """A private input beside the start state -> its path, or None. A different file there is refused."""
    import hashlib
    path = Path(z80).resolve().parent / file
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not %s (MD5 %s)' % (file, what, md5))
    return path


def enhanced_inputs(z80):
    """-> (set path, backdrop pattern) beside the start state, or None when any is missing."""
    got = [_beside(z80, SET_NAME, SET_MD5, 'the set this engine was proved with')]
    got += [_beside(z80, BACKDROPS % n, m, 'the backdrop this engine was proved with') for n, m in enumerate(BACKDROP_MD5)]
    if not all(got):
        return None
    return str(got[0]), str(Path(z80).resolve().parent / BACKDROPS)


def _patch(z80, inputs):
    """The default from the game's own masks (no set needed); Enhanced from the set and backdrops."""
    return Patch(z80, inputs is not None, art(*(inputs or (None, None)), game_mem(str(z80))))


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer (the build's setup puts the game's back): every register with R and
    all RAM 4000-FFFF (the paged bank at C000) against the patched start state, bar the start-up tail. -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
    tail = zt.choose_tail_addr(s, size, patch.tail_addr, False)[0]
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
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _replay(z80, inputs, rzx, stop, collect):
    """One recording against one build's hooks (a process of its own) -> (name, counts, failures, states)."""
    r = verify(_patch(z80, inputs), rzx, stop=stop, collect=collect)
    c, ex, states = r[0], r[1], (r[2] if len(r) > 2 else [])
    return Path(rzx).name, dict(c), {k: (v, ex.get(k[:-1], [])[:2]) for k, v in c.items() if k.endswith('!')}, states


def _negative(z80, inputs, name, rzxs, stop):
    """One deliberately broken build on each recording in turn until one fails it (a process of its own) -> (name, keys)."""
    b = negative_patches(_patch(z80, inputs))[name]
    got = {}
    for r in rzxs:
        try:
            got = run_negative(b, r, stop)
        except Exception as e:          # noqa: BLE001 - a hang or crash of a broken build is a catch
            got = {'exception %s!' % type(e).__name__: 1}
        if got:
            break
    return name, sorted(got)


def auto(a, z80, name, out, say):
    """nexclash.py auto: the sprite build and, with the set and the seven backdrops beside the start state, Enhanced; each
    with the tape's loading screen when it is beside the start state, as published; every build boot-checked. With --rzx:
    the default replayed on a1, over and tour, Enhanced on every recording; the ABI cases on a1's states; each broken
    build on a1 then tour until one fails it, and one no recording reaches must fail a unit case (the upload, an object
    going off). Pace, soak, flicker and the real loader are the review run's (games/that_sinking_feeling.md "Evidence")."""
    import concurrent.futures, hashlib, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : That Sinking Feeling (Sunteam, 2017, the tape\'s 128K form with its AY music)')
    say('Engine    : that_sinking_feeling; the ULA as the original, figures and objects as hardware sprites; Enhanced: the '
        "Spec256 set's colours on the sprites and a Layer 2 backdrop")
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, "the tape's loading screen")
    inputs = enhanced_inputs(z80)
    if screen is None:
        say('Loading   : no %s beside the start state: builds without the loading screen' % LOAD_SCREEN)
    builds = [('Sprites', '_sprites', None)]
    if inputs is None:
        say('Enhanced  : not all of %s and %s beside the start state: default build only' % (SET_NAME, 'that_sinking_feeling.B00-B06'))
    else:
        builds.append(('Enhanced', '_enhanced', inputs))
    for label, suffix, inp in builds:
        nex = out / (name + suffix + '.nex')
        zt.convert(str(z80), str(nex), patch=_patch(z80, inp), quiet=True)
        nexes = [(label, nex)]
        if screen is not None:
            loading = out / (name + suffix + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen.read_bytes()))
            nexes.append((label[:3] + '+scr', loading))
        for lab, path in nexes:
            bad = boot_check(path, z80, _patch(z80, inp))
            ok = ok and not bad
            say('%-10s: %s  %s' % (lab, path.name, hashlib.md5(path.read_bytes()).hexdigest()))
            say('Boot      : %s' % ('simulated, OK (registers with R, all RAM, the paged bank; converter loader and NEXLOAD)'
                                    if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    stop = getattr(a, 'quick', None)
    if not rzxs:
        say('Verify    : not requested; boot evidence only')
        say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
        return bool(ok)
    byname = {Path(r).name: r for r in rzxs}
    first_rzx = byname.get(NEG_RZX[0], rzxs[0])
    negs_rzx = [byname[n] for n in NEG_RZX if n in byname] or [rzxs[0]]
    nstop = NEG_STOP if stop is None else min(stop, NEG_STOP)
    with concurrent.futures.ProcessPoolExecutor(os.cpu_count() or 1) as pool:
        jobs = []
        for label, suffix, inp in builds:
            mine = [r for r in rzxs if inp is not None or Path(r).name in DEFAULT_RZX] or rzxs[:1]
            first = pool.submit(_replay, z80, inp, first_rzx, nstop, 1)
            reps = [pool.submit(_replay, z80, inp, r, stop, 0) for r in mine]
            negs = []
            if stop is None:
                negs = [pool.submit(_negative, z80, inp, k, negs_rzx, NEG_STOP) for k in negative_patches(_patch(z80, inp))]
            jobs.append((label, inp, first, reps, negs))
        for label, inp, first, reps, negs in jobs:
            frames = hooks = 0
            for f in reps:
                rname, c, fail, _ = f.result()
                ok = ok and not fail
                frames, hooks = frames + c.get('frames', 0), hooks + c.get('hooks', 0)
                say('Verify    : %s %s %d frames, %d hooks, %d R comparisons, %d Layer 2 pictures: %s' % (
                    label, rname, c.get('frames', 0), c.get('hooks', 0), c.get('R comparisons', 0),
                    c.get('Layer 2 pictures compared', 0), 'IDENTICAL' if not fail else str(fail)[:400]))
            say('Verify    : %s %d recordings, %d frames, %d hooks' % (label, len(reps), frames, hooks))
            p = _patch(z80, inp)
            states = first.result()[3]
            u = unit_tests(p, states)
            ok = ok and not [k for k in u if k.endswith('!')] and u.get('ABI cases', 0) > 0
            say('Unit      : %s %s' % (label, dict(u)))
            if negs:
                res = dict(f.result() for f in negs)
                by_unit = []
                for k, v in list(res.items()):
                    if not v:               # one no recording reaches: a unit case must catch it
                        v = sorted(x for x, y in unit_tests(negative_patches(p)[k], states).items() if x.endswith('!'))
                        res[k] = v
                        if v:
                            by_unit.append(k)
                missed = [k for k, v in res.items() if not v]
                ok = ok and not missed
                say('Negatives : %s %d of %d broken builds caught (%s in turn, to the first failure, %d frames at most)%s%s' % (
                    label, len(res) - len(missed), len(res), ', '.join(NEG_RZX), NEG_STOP,
                    '; by a unit case: %s' % ', '.join(by_unit) if by_unit else '', '; MISSED %s' % missed if missed else ''))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
