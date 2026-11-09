"""Jilly's Farm Volume 1 - SokoBAArn!, Enhanced: the Spec256 set's colours, faithfully, on a Layer 2.

A second buffer holds the 8-bit value Spec256's planes would hold; the game's dirty cells carry it to the Layer 2 on show.
Value FF, "the attribute's colour", is transparent, so the ULA shows it. The set is V1.00 and the release V1.01: colours are
mapped by graphic, 13 bytes lower in the set, and any byte that doesn't match stays in its original colours. The set is read
from a local .256 (never in this repo); see asm/jillys_farm_enh_hooks.asm. The default mode changes no byte (jillys_farm.py).
"""
from collections import Counter, defaultdict
from pathlib import Path
import json, os
import numpy as np
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/jillys_farm_enh.json'
CMP = tuple(hooklib.CMP_R)
SET_ENV = 'NEXCLASH_JILLY_SET'
OFFSET = 13
T_LO, T_HI = 0xAD00, 0xC000
PG_BACK, PG_FRONT, PG_T = 32, 40, 46
# plot routine: (sym, kind, columns or pairs, rows, sites as (address, opcode))
PLOTS = {
    0x92F6: ('h_92F6', 'ldd', 2, 16, [(a, 0xCD) for a in (0x6B9F, 0x6BA6, 0x6BAF, 0x6BB8, 0xA8A6, 0xA8AD, 0xA8B6, 0xA8BF, 0xA95C)]),
    0x936A: ('h_936A', 'ldd', 2, 48, [(0xA3BA, 0xCD), (0xA3E4, 0xCD)]),
    0x9B8D: ('h_9B8D', 'ldd', 4, 16, [(0x7060, 0xC3), (0x70E9, 0xCD), (0xA2EC, 0xCD), (0xA996, 0xCD)]),
    0x9BF1: ('h_9BF1', 'mask', 4, 8, [(0x70F4, 0xC3), (0xA2F7, 0xCD), (0xA9C8, 0xC3), (0xA9DD, 0xCD)]),
    0x9C33: ('h_9C33', 'mask', 4, 24, [(0x70D0, 0xC3), (0x70DA, 0xC3), (0x85B4, 0xCD)]),
    0x9CE5: ('h_9CE5', 'mask', 2, 24, [(0x70BB, 0xC3), (0x70C6, 0xC3)]),
    0x9D97: ('h_9D97', 'mask', 4, 40, [(0x70A6, 0xC3), (0x70B0, 0xC3)]),
    0x9EB9: ('h_9EB9', 'mask', 4, 29, [(0x7056, 0xC3), (0x7092, 0xC3), (0xA84F, 0xCD), (0xA9BE, 0xC3), (0xA9E8, 0xC3)]),
    0x93D4: ('h_93D4', 'mask', 2, 56, [(0xA864, 0xCD)]),
    0x96EB: ('h_96EB', 'mask', 3, 56, [(0xA85D, 0xCD)]),
    0x9F8E: ('h_9F8E', 'sheep', 3, 29, [(0x706A, 0xC3), (0x7074, 0xC3), (0x707E, 0xC3), (0x7088, 0xC3), (0xA848, 0xCD), (0xA9B4, 0xC3)]),
    0xA02B: ('h_A02B', 'sheep', 4, 29, [(0x709C, 0xC3), (0x8242, 0xCD), (0xA856, 0xCD), (0xA9D2, 0xC3)]),
    0x923E: ('h_clear', 'clear', 0, 0, [(0x6902, 0xCD), (0x822C, 0xCD), (0xA87E, 0xCD)]),
    0x8B00: ('h_wipe', 'wipe', 0, 0, [(0x8531, 0xCD), (0x855C, 0xCD)]),
    0x92D3: ('h_digit', 'digit', 0, 0, [(a, 0xCD) for a in (0x849F, 0x84AA, 0x861D, 0x8628)]),
}
OPEN_SITES = (0x8387, 0x8534, 0x855F)      # the draw run's first CALL (A2C3)
CLOSE_SITES = (0x8393, 0x8540, 0x856B)     # the CALL after its copy (A605)
CLOSE1 = (0x8374, bytes.fromhex('3A94A1'), 'h_close1', 0x8377)   # the first window's end, at a load
SITES = {}
SITES[0x8357] = (0xCD, 0x8692, 'h_open1', 'open', 0, 0)
for _a in OPEN_SITES:
    SITES[_a] = (0xCD, 0xA2C3, 'h_open', 'open', 0, 0)
for _a in CLOSE_SITES:
    SITES[_a] = (0xCD, 0xA605, 'h_close', 'close', 0, 0)
for _t, (_s, _k, _n, _r, _l) in PLOTS.items():
    for _a, _op in _l:
        SITES[_a] = (_op, _t, _s, _k, _n, _r)
COPY_SITE = 0x8BED      # the copy itself, not its CALLs: 8BE9 falls into it (a full redraw, HALT, copy)
COPY_OLD = bytes.fromhex('2100FC')
CHAR_SITE = 0x92AE
CHAR_OLD = bytes.fromhex('872600')
CHAR_RESUME = 0x92B1


def load_profile():
    return json.loads(PROFILE.read_text())


def _bank(a):
    return (5, a - 0x4000) if a < 0x8000 else (2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000)


def _ram(snap_or_mem, a):
    return snap_or_mem[a]


class Set256:
    """The set's planes and master by 64K address, and its colours mapped by graphic onto the release: release byte a
    takes the set's byte a - 13 when the set's master there equals the release's byte; otherwise it has no colour."""
    def __init__(self, release, path=None):
        self.d = open(path or os.environ[SET_ENV], 'rb').read()
        self.release = bytes(release)
        self.no_match = []
        for a in range(T_LO, T_HI):
            if self.set_master(a - OFFSET) != self.release[a]:
                self.no_match.append(a)
        self.nm = set(self.no_match)
        self.cache = {}

    def word(self, a):
        b, off = _bank(a)
        return (b * 16384 + off) * 9

    def set_master(self, a):
        return self.d[self.word(a) + 8]

    def planes(self, a):
        """The 8 plane bytes of release byte a (uncoloured, or no match: the release's byte on every plane)."""
        if T_LO <= a < T_HI and a not in self.nm:
            s = self.word(a - OFFSET)
            return self.d[s:s + 8]
        return bytes((self.release[a],)) * 8

    def values(self, a):
        v = self.cache.get(a)
        if v is None:
            pl = self.planes(a)
            v = bytes(sum(((pl[i] >> (7 - k)) & 1) << i for i in range(8)) for k in range(8))
            self.cache[a] = v
        return v


def palette(rgb):
    """The set's palette as NR 0x44 pairs. Value 255 is the transparent colour; no other value may land on it."""
    out = bytearray()
    for i, c in enumerate(rgb):
        r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
        r3, g3, b3 = round(r * 7 / 255), round(g * 7 / 255), round(b * 7 / 255)
        top = r3 << 5 | g3 << 2 | b3 >> 1
        low = b3 & 1
        if i == 255:
            top, low = 0xE3, 1
        elif top == 0xE3:
            top = 0xE7
        out += bytes((top, low))
    return bytes(out)


def entry(s, a):
    """16 bytes for source byte a: +0-7 values; +8 and +9 which pixels a mask here simply writes, as an AND mask and a CPL
    mask, with the graphic one source byte lower; +10 bit 0, bit 1: not that simple, take the general path (sentinel 1);
    bit 2: the mask is not all 0 or FF a pixel; +11 the pixels the CPL mask covers, always; +12, +13 when the AND mask
    writes one run of pixels, its start + 1 and its length."""
    m, g = s.values(a), s.values(a - 1) if a > T_LO else bytes(8)
    wa = wo = raw = 0
    fl = 0
    for k in range(8):
        bit = 0x80 >> k
        if m[k] == 0:
            wa |= bit
        elif not (m[k] == 255 and g[k] == 0):
            fl |= 1
        if m[k] not in (0, 255):
            fl |= 4
        if m[k] == 255:
            raw |= bit
            wo |= bit
        elif not (m[k] == 0 and g[k] == 0):
            fl |= 2
    if fl & 1:
        wa = 1
    if fl & 2:
        wo = 1
    start, n = 0, 0
    if not fl & 1 and wa not in (0, 255):
        bits = format(wa, '08b')
        if '1' * bits.count('1') in bits:
            start, n = bits.index('1') + 1, bits.count('1')
    return m + bytes((wa, wo, fl, raw, start, n)) + bytes(2)


SHEEP = [(0xAD59 + 0xAE * i, 3) for i in range(12)] + [(0xB7A9, 4)]


def tables(s, check=True):
    data = b''.join(entry(s, a) for a in range(T_LO, T_HI))
    for h, n in SHEEP if check else ():      # the shifted routines' path takes the mask as whole pixels
        for i in range(n * 29):
            if data[(h + 2 * i + 1 - T_LO) * 16 + 10] & 4:
                raise ValueError('a sheep mask at %04X has a part-pixel value' % (h + 2 * i + 1))
    return {PG_T + i // 8192: data[i:i + 8192].ljust(8192, b'\0') for i in range(0, len(data), 8192)}


PG_C = 56                # compiled sprites from here
# Every source the game plots: routine's table, kind, columns or pairs, rows, sources
SPRITES = [
    (0x3C00, 'ldd', 2, 16, [0xBF18, 0xBF38, 0xBF58, 0xBF78, 0xBF98, 0xBFB8]),
    (0x3C20, 'ldd', 2, 48, [0xB9D8, 0xBA38]),
    (0x3C40, 'ldd', 4, 16, [0xB680]),
    (0x3C60, 'mask', 4, 8, [0xB6C0]),
    (0x3C80, 'mask', 4, 24, [0xB640, 0xBE38, 0xBEF8]),
    (0x3CA0, 'mask', 2, 24, [0xBD18, 0xBD78]),
    (0x3CC0, 'mask', 4, 40, [0xBB78, 0xBCB8]),
    (0x3CE0, 'mask', 4, 29, [0xB7A8, 0xB978]),
    (0x3D00, 'sheep', 3, 29, [0xAD59 + 0xAE * _i for _i in range(12)]),
    (0x3D40, 'sheep', 4, 29, [0xB7A9]),
]


def sprite_rows(s, kind, n, rows, h, force_write=False):
    """rows[r][dx] = None (keep), ('w', v) write, ('o', g) OR, ('g', m, g) (v AND m) OR g, with the pixels as the planes treat them."""
    out = [[None] * (8 * n) for _ in range(rows)]
    for r in range(rows):
        for c in range(n):
            if kind == 'ldd':
                v = s.values(h - (c * rows + r))
                for k in range(8):
                    out[r][c * 8 + k] = ('w', v[k])
                continue
            if kind == 'mask':
                i = c * rows + r
                m, g = s.values(h - 2 * i), s.values(h - 2 * i - 1)
            else:
                i = r * n + c
                g, m0 = s.values(h + 2 * i), s.values(h + 2 * i + 1)
                m = bytes(x ^ 255 for x in m0)
            for k in range(8):
                if force_write or m[k] == 0:
                    out[r][c * 8 + k] = ('w', g[k])
                elif m[k] == 255:
                    if g[k]:
                        out[r][c * 8 + k] = ('o', g[k])
                else:
                    out[r][c * 8 + k] = ('g', m[k], g[k])
    return out


def compile_sprite(rows, up_c):
    """Z80: HL the first pixel, E its x, C 0, D FF; rows going up the screen."""
    code = bytearray()
    for r, row in enumerate(rows):
        skip = 0
        for a in row:
            if a is None:
                skip += 1
                continue
            if skip > 3:
                code += bytes((0x7D, 0xC6, skip, 0x6F))      # ld a,l / add a,n / ld l,a
            else:
                code += b'\x2C' * skip                       # inc l
            skip = 1                                         # the next pixel is one along
            if a[0] == 'w':
                code += b'\x71' if a[1] == 0 else b'\x72' if a[1] == 255 else bytes((0x36, a[1]))
            elif a[0] == 'o':
                code += bytes((0x3E, a[1], 0xB6, 0x77))
            else:
                code += bytes((0x3E, a[1], 0xA6, 0xF6, a[2], 0x77))
        if r < len(rows) - 1:
            code += bytes((0x6B, 0x25, 0xFC)) + zt.w16(up_c)  # ld l,e / dec h / call m,up_c
    code.append(0xC9)
    return bytes(code)


def compiled(s, up_c, force_write=False):
    """{page: 8192 bytes}, {table address: bytes}: every known source as its own code."""
    pages, tabs = {}, {}
    page, at = PG_C, 0
    buf = bytearray()
    for tab, kind, n, rows, sources in SPRITES:
        t = bytearray()
        for h in sources:
            code = compile_sprite(sprite_rows(s, kind, n, rows, h, force_write), up_c)
            if at + len(code) > 8192:
                pages[page] = bytes(buf).ljust(8192, b'\0')
                page, at, buf = page + 1, 0, bytearray()
            t += zt.w16(h) + bytes((page,)) + zt.w16(0xC000 + at)
            buf += code
            at += len(code)
        tabs[tab] = bytes(t) + b'\0\0'
    pages[page] = bytes(buf).ljust(8192, b'\0')
    return pages, tabs


class Patch:
    name = "Jilly's Farm: the Spec256 colours on Layer 2"
    uses_printer_buffer = True
    keep_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = 0x5B00

    def __init__(self, source=None, set_path=None, palette_path=None):
        from .machine import Machine
        self.source = str(source) if source else None
        release = bytes(Machine(str(source)).sim.memory)
        self.set = Set256(release, set_path)
        rgb = json.load(open(palette_path or os.environ[SET_ENV + '_PALETTE']))
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup']) + palette(rgb)
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1E00:0x2000] = bytes(512)
        self.sites = [(a, bytes((op,)) + zt.w16(t), bytes((op,)) + zt.w16(self.syms[s])) for a, (op, t, s, k, n, r) in SITES.items()]
        self.sites.append((CHAR_SITE, CHAR_OLD, b'\xC3' + zt.w16(self.syms['h_char'])))
        self.sites.append((COPY_SITE, COPY_OLD, b'\xC3' + zt.w16(self.syms['h_copy'])))
        self.sites.append((CLOSE1[0], CLOSE1[1], b'\xC3' + zt.w16(self.syms[CLOSE1[2]])))
        self.tables = tables(self.set)
        self.compile(self.set)
        self._banks()

    def compile(self, s, force_write=False):
        pages, tabs = compiled(s, self.syms['up_c'], force_write)
        self.tables = dict(self.tables)
        self.tables.update(pages)
        self.ram[0x1C00:0x1E00] = bytes(512)
        for a, d in tabs.items():
            self.ram[a - 0x2000:a - 0x2000 + len(d)] = d

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in {v[0] for v in PLOTS.values()} | {'h_char', 'h_copy', 'h_open', 'h_close', 'h_open1', 'h_close1'}:
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}
        for bank in sorted({p // 2 for p in self.tables}):
            self.extra_banks[bank] = self.tables.get(bank * 2, bytes(8192)) + self.tables.get(bank * 2 + 1, bytes(8192))

    def apply(self, snap):
        banks = {i: bytearray(snap.banks[i]) for i in snap.banks}
        for a, old, new in self.sites:
            b, at = _bank(a)
            if bytes(banks[b][at:at + len(old)]) != old:
                raise ValueError('Not the supported release: original bytes differ at %04X' % a)
            banks[b][at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in banks)


def build(source, destination, set_path=None, palette_path=None):
    p = Patch(source, set_path, palette_path)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


class View:
    """64K view of the game RAM + the pages the hook maps, per the model's MMU."""
    DEFAULT = (255, 255, 10, 11, 4, 5, 0, 1)

    def __init__(self, mem, patch, page, pages):
        self.mem = bytearray(mem)
        self.patch, self.page, self.pages = patch, page, pages
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        s = a >> 13
        m = self.model.nr.get(0x50 + s, self.DEFAULT[s])
        if m == self.DEFAULT[s] and a >= 0x4000:
            return self.mem[a]
        if a < 0x4000 and m == 255:
            return self.patch.page[a - 0x2000] if a >= 0x2000 else self.mem[a]
        if m == 24:
            return self.page[a & 8191]
        if m == 25:
            return self.patch.page[a & 8191]
        return self.pages[m][a & 8191]

    def __setitem__(self, a, v):
        s = a >> 13
        m = self.model.nr.get(0x50 + s, self.DEFAULT[s])
        if m == self.DEFAULT[s]:
            if a >= 0x4000:
                self.mem[a] = v
            return
        if m == 24:
            self.page[a & 8191] = v
        elif m == 25 or m >= PG_T:
            raise AssertionError('write to a read-only page %d at %04X' % (m, a))
        else:
            self.pages[m][a & 8191] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line)
        self.nr.update({0x50 + i: p for i, p in enumerate(View.DEFAULT)})
        self.nr[1] = 0x32
        self.io = []

    def write_port(self, regs, port, v, *args):
        if port in (0x243B, 0x253B) or port & 255 == 0x6B:
            return super().write_port(regs, port, v, *args)
        self.io.append((port, v))


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class State:
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = {p: bytearray(8192) for p in range(PG_BACK, PG_FRONT + 6)}
        for p, d in patch.tables.items():
            self.pages[p] = bytearray(d)
        self.nr = {0x69: 0}
        self.line = 0
        self.clock = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'jfe-hook')
    m = Model(s, speed, st.line)
    m.nr.update(st.nr)
    v.model = m
    n = 0
    R = s.registers
    while n == 0 or R[24] != stop_pc or (stop_sp is not None and R[12] != stop_sp):
        s.opcodes[v[R[24]]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not terminate at %04X' % R[24])
    st.line = m.line()
    st.nr[0x69] = m.nr.get(0x69, 0)
    return list(R), v, m


class Planes:
    """The expected buffers, by another route: the set's plane bytes as the game's own byte operations would treat them, on
    the eight planes and on the master, which must always equal the game's real buffer. Layer 2 values are read off the end."""
    def __init__(self, s):
        self.set = s
        self.back = np.zeros((9, 32, 256), dtype=np.uint8)
        self.front = np.zeros((9, 32, 192), dtype=np.uint8)

    def src(self, a, mem):
        return tuple(self.set.planes(a)) + (mem[a],)

    def plot(self, kind, mem, regs, n, rows):
        hl, d, e = regs[6] << 8 | regs[7], regs[4], regs[5]
        col = d - 0xDC
        if kind == 'ldd':
            for c in range(n):
                y = e
                for r in range(rows):
                    self.back[:, col + c, y] = self.src(hl, mem)
                    hl -= 1
                    y = (y - 1) & 255
        elif kind == 'mask':
            for c in range(n):
                y = e
                for r in range(rows):
                    m, g = self.src(hl, mem), self.src(hl - 1, mem)
                    self.back[:, col + c, y] = (self.back[:, col + c, y] & np.array(m, dtype=np.uint8)) | np.array(g, dtype=np.uint8)
                    hl -= 2
                    y = (y - 1) & 255
        elif kind == 'sheep':
            s = regs[9] & 7
            y = e
            for r in range(rows):
                cg = np.zeros((9, n + 1), dtype=np.uint16)
                cm = np.zeros((9, n + 1), dtype=np.uint16)
                for j in range(n):
                    g, m = self.src(hl, mem), self.src(hl + 1, mem)
                    hl += 2
                    if s:           # the shifted routines keep the graphic in IY, which has no planes: the master's on all
                        g = (g[8],) * 9
                    # through the game's own shift tables: page CE + 2(s-1) high part, one page up the low part
                    for p in range(9):
                        if s:
                            b = 0xCE + 2 * (s - 1)
                            cg[p, j] |= mem[b << 8 | g[p]]
                            cg[p, j + 1] |= mem[(b + 1) << 8 | g[p]]
                            cm[p, j] |= mem[b << 8 | m[p]]
                            cm[p, j + 1] |= mem[(b + 1) << 8 | m[p]]
                        else:
                            cg[p, j] = g[p]
                            cm[p, j] = m[p]
                for j in range(n + 1 if s else n):
                    self.back[:, col + j, y] = (self.back[:, col + j, y] & ~cm[:, j].astype(np.uint8)) | cg[:, j].astype(np.uint8)
                y = (y - 1) & 255

    def char(self, mem, code, d, e):
        hl = (((code * 2) & 255) * 4 + (mem[0x92B5] | mem[0x92B6] << 8)) & 0xFFFF
        for r in range(8):
            self.back[:, d - 0xDC, (e + r) & 255] = mem_at(mem, hl + r)

    def digit(self, mem, code, d, e):
        base = mem[0x92DA] | mem[0x92DB] << 8
        hl = (((code * 2) & 255) * 4 + base) & 0xFFFF
        for r in range(8):
            f = mem[hl + r]
            for ln in range(2):
                y = (e + 2 * r + ln) & 255
                self.back[:, d - 0xDC, y] = mem[0x7800 | f]
                self.back[:, d - 0xDC + 1, y] = mem[0x7900 | f]

    def clear(self):
        self.back[:, :, :192] = 0

    def cells(self, mem):
        for i in range(0x60):
            f = mem[0xFC00 + i]
            for b in range(8):
                if f & (0x80 >> b):
                    yield (i & 3) * 8 + b, (i >> 2) * 8

    def wipe(self, mem):
        for x, y in self.cells(mem):
            self.back[:, x, y:y + 8] = 0

    def copy(self, mem):
        for x, y in self.cells(mem):
            self.front[:, x, y:y + 8] = self.back[:, x, y:y + 8]

    def values(self, planes):
        """(8, 32, h) plane bytes -> (h, 256) values."""
        bits = np.unpackbits(planes.transpose(0, 2, 1), axis=2)
        return sum((bits[i].astype(np.uint16) << i) for i in range(8)).astype(np.uint8)


def mem_at(mem, a):
    return mem[a & 0xFFFF]


SCREEN = np.array([[(y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x for y in range(192)] for x in range(32)])


def _picture(st, first):
    return np.frombuffer(b''.join(bytes(st.pages[first + i]) for i in range(6)), dtype=np.uint8).reshape(192, 256)


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original; at every changed site run the hook on a copy of the state and compare with the original's run to
    its return: every register with R, all 48K RAM except 32 bytes of dead stack. Both Layer 2 pictures against Planes, whose
    master plane must equal the game's real buffer at every hook."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    pl = Planes(patch.set)
    allsites = set(SITES) | {CHAR_SITE, CLOSE1[0], COPY_SITE}
    seen = Counter()

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)

    def patched_mem(mem):
        p = bytearray(mem)
        for a, old, new in patch.sites:
            p[a:a + len(new)] = new
        return p

    def on_pc(pc, sim):
        mem = bytes(sim.memory)
        regs = list(sim.registers)
        seen[pc] += 1
        if pc == CHAR_SITE:
            op, target, sym, kind, n, rows = 0xC3, CHAR_RESUME, 'h_char', 'char', 0, 0
            if mem[pc:pc + 3] != CHAR_OLD:
                fail('site bytes changed', {'pc': hex(pc)})
                return
        elif pc == COPY_SITE:
            op, target, sym, kind, n, rows = 0xC3, 0, 'h_copy', 'copy', 0, 0
            if mem[pc:pc + 3] != COPY_OLD:
                fail('site bytes changed', {'pc': hex(pc)})
                return
        elif pc == CLOSE1[0]:
            op, target, sym, kind, n, rows = 0xC3, CLOSE1[3], CLOSE1[2], 'close1', 0, 0
            if mem[pc:pc + 3] != CLOSE1[1]:
                fail('site bytes changed', {'pc': hex(pc)})
                return
        else:
            op, target, sym, kind, n, rows = SITES[pc]
            if mem[pc:pc + 3] != bytes((op, target & 255, target >> 8)):
                fail('site bytes changed', {'pc': hex(pc)})
                return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ref = simpool.machine(Simulator, list(mem), regs, 'jfe-ref')
        sp = regs[12]
        R = ref.registers
        m0 = 0
        if kind == 'open' and st.clock:
            fail('a window opened inside a window', {'pc': hex(pc)})
        if kind in ('char', 'close1'):
            ret, want_sp = target, sp
        elif kind in ('open', 'close'):
            ret, want_sp = target, sp - 2
        elif op == 0xC3:
            ret, want_sp = mem[sp] | mem[sp + 1] << 8, sp + 2
        else:
            ret, want_sp = (pc + 3) & 0xFFFF, sp
        k = 0
        while k == 0 or R[24] != ret or R[12] != want_sp:
            ref.opcodes[ref.memory[R[24]]]()
            k += 1
        if kind in ('ldd', 'mask', 'sheep'):
            pl.plot(kind, mem, regs, n, rows)
        elif kind == 'clear':
            pl.clear()
        elif kind == 'wipe':
            pl.wipe(mem)
        elif kind == 'copy':
            pl.copy(mem)
        elif kind == 'char':
            pl.char(mem, regs[0], regs[4], regs[5])
        elif kind == 'digit':
            pl.digit(mem, regs[0], regs[4], regs[5])
        got, v, model = run_hook(patch, st, patched_mem(mem), regs, ret, want_sp, speed=st.clock)
        st.clock = 3 if kind == 'open' else 0 if kind in ('close', 'close1') else st.clock
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        for a in range(sp - 32, sp):
            expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x56] != 0 or model.nr[0x57] != 1:
            fail('MMU not restored', {'pc': hex(pc), 'sym': sym, 'nr': [model.nr[x] for x in (0x50, 0x51, 0x56, 0x57)]})
        if model.nr[7] != st.clock:
            fail('clock differs', {'pc': hex(pc), 'sym': sym, 'value': model.nr[7], 'want': st.clock})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        if kind == 'copy' and st.nr.get(0x69) != 0x80:
            fail('overlay not on after a copy', {'pc': hex(pc)})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if kind in ('open', 'close', 'close1'):
            if progress and c['hooks'] % 500 == 0:
                progress(c)
            return
        # the model's master plane is the game's real buffer: the model means what the routine does
        real = np.frombuffer(bytes(ref.memory[0xDC00:0xFC00]), dtype=np.uint8).reshape(32, 256)
        if kind != 'char' and not np.array_equal(pl.back[8, :, :192], real[:, :192]):   # a letter's bytes come after its hook
            d = np.argwhere(pl.back[8, :, :192] != real[:, :192])
            fail('model master differs from the game', {'pc': hex(pc), 'sym': sym, 'count': len(d), 'ex': d[:4].tolist(), 'regs': regs[:8]})
        pic = _picture(st, PG_BACK)
        want = pl.values(pl.back[:8, :, :192])
        if not np.array_equal(pic, want):
            d = np.argwhere(pic != want)
            fail('value buffer differs from the model', {'pc': hex(pc), 'sym': sym, 'count': len(d), 'ex': [(int(y), int(x), int(pic[y, x]), int(want[y, x])) for y, x in d[:4]]})
        c['value pictures compared'] += 1
        if kind == 'copy':
            pic = _picture(st, PG_FRONT)
            want = pl.values(pl.front[:8])
            if not np.array_equal(pic, want):
                d = np.argwhere(pic != want)
                fail('Layer 2 differs from the model', {'pc': hex(pc), 'count': len(d), 'ex': [(int(y), int(x), int(pic[y, x]), int(want[y, x])) for y, x in d[:4]]})
            c['Layer 2 pictures compared'] += 1
            # the model's copied master is the game's real screen: nothing reaches the screen without passing a hook
            scr = np.frombuffer(bytes(ref.memory[0x4000:0x5800]), dtype=np.uint8)[SCREEN]
            if not np.array_equal(scr, pl.front[8]):
                d = np.argwhere(scr != pl.front[8])
                fail('the screen changed outside the hooks', {'pc': hex(pc), 'count': len(d), 'ex': d[:4].tolist()})
            c['screens compared'] += 1
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), allsites, on_pc, stop)
    c['frames'] = frames
    c['sites never reached'] = len(allsites - set(seen))
    if err:
        fail('recording desynced', err)
    res = (c, dict(examples))
    patch.never_reached = sorted(allsites - set(seen))
    return res + (states,) if collect else res


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the
    caller had; the MMU restored."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        spec = (0xC3, 0, 'h_copy', 'copy', 0, 0) if pc == COPY_SITE else None if pc in (CHAR_SITE, CLOSE1[0]) else SITES[pc]
        kind_u = 'close' if pc == CLOSE1[0] else 'char' if pc == CHAR_SITE else spec[3]
        op = spec[0] if spec else None
        patched = bytearray(mem)
        for a, old, new in patch.sites:
            patched[a:a + len(new)] = new
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    s0 = rr[12]
                    if pc == CHAR_SITE:
                        ret, sp = CHAR_RESUME, s0
                    elif pc == CLOSE1[0]:
                        ret, sp = CLOSE1[3], s0
                    elif kind_u in ('open', 'close'):
                        ret, sp = spec[1], s0 - 2
                    else:
                        ret, sp = (mem[s0] | mem[s0 + 1] << 8, s0 + 2) if op == 0xC3 else ((pc + 3) & 0xFFFF, s0)
                    n = 0
                    while n == 0 or ref.registers[24] != ret or ref.registers[12] != sp:
                        ref.opcodes[ref.memory[ref.registers[24]]]()
                        n += 1
                    st = State(patch)
                    want = speed
                    if kind_u == 'open':
                        want = 3
                    if kind_u == 'close':
                        st.page[0x1E2D] = speed       # the window's latched clock
                        st.page[0x1E2C] = 1
                    got, v, model = run_hook(patch, st, patched, rr, ret, sp, speed=3 if kind_u == 'close' else speed)
                    if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    if model.nr[7] != want:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x56] != 0 or model.nr[0x57] != 1:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def clone():
        b = copy.copy(patch)
        b.ram = bytearray(patch.ram)
        return b

    def mutate(name, old, new):
        b = clone()
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.find(old)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new)] = new
        b._banks()
        out[name] = b

    def call(sym):
        return b'\xCD' + zt.w16(patch.syms[sym])
    mutate('R off by one', bytes((0x3E, 0x100 - 21, 0xCD)), bytes((0x3E, 0x100 - 20)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('draw window left at 28 MHz', bytes.fromhex('3A2D3EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('x off by one column', bytes.fromhex('D6DC87878732'), bytes.fromhex('D6DB87878732'))
    mutate("sheep's shift ignored", bytes.fromhex('DD7DE6074F'), bytes.fromhex('DD7DE6004F'))
    mutate('slot 7 left mapped', bytes.fromhex('ED915701C9'), bytes.fromhex('00000000C9'))
    mutate('slot 0 left mapped', bytes.fromhex('ED9150FFED9156'), bytes.fromhex('00000000ED9156'))
    mutate('wipe not done', call('l2_wipe'), bytes(3))
    mutate('clear not done', call('l2_clear'), bytes(3))
    mutate('copy not done', call('l2_copy'), bytes(3))
    mutate('Layer 2 never shown', bytes.fromhex('ED916980'), bytes(4))
    # masks ignored: every mask writes its whole graphic
    b = clone()
    b.tables = {}
    for p, d in patch.tables.items():
        e = bytearray(d)
        for i in range(0, 8192 if p < PG_C else 0, 16):
            e[i + 8] = 0xFF
            e[i + 9] = 0xFF
            e[i + 11] = 0xFF
        b.tables[p] = bytes(e)
    b.compile(b.set, force_write=True)
    b._banks()
    out['masks ignored'] = b
    # the colours 12 bytes lower instead of 13: another graphic's
    b = clone()
    s12 = copy.copy(patch.set)
    s12.cache = {}
    s12.nm = set()
    orig_word = patch.set.word
    s12.word = lambda a: orig_word(a + 1)
    b.tables = tables(s12, check=False)
    b.compile(s12)
    b._banks()
    out['set read at the wrong offset'] = b
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}
