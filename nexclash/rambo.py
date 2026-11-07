"""Rambo - First Blood Part II (Ocean, 1985, 48K) engine 'rambo'. Additive module: reachable only
through is_rambo(). Facts and design: games/rambo.md. Hooks: asm/rambo_hooks.asm.

Back-buffer composer with a display list: every object (scenery and figure) is ORed into a linear
buffer at 0xC000 (20 x 192 bytes, y counted up from the bottom) by one of two plot routines, its
attribute box goes on a list (0xFE00, count 0xFF4F) that 0x8093 paints, then 0x814A blits. Objects
of type >= 0x40 are the figures. A figure's plot is replaced by a sprite built from pre-made tiles,
its attribute box is dropped from the list, and the sprites commit with the blit.

verify() runs the real patched game next to the original on the recording's IN values (the two
differ only by the interrupt wait before the blit, whose IN at 0x8119 is discarded), and compares
at every blit: RAM outside what the patch owns, the live registers, the attribute list, and
original buffer == patched buffer | sprite pixels, bit for bit.
"""
import collections
import hashlib
import json
import os

from .recolour import build_colours_path

RECORD = 'rambo'
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')
TAIL_ADDR = 0x5B00
RAM_ORG = 0x5D80
H_BANK, IMG_BANK = 13, 14            # H page = 26; tiles from page 28
PAGE_ORG = 0x2000
FIGTYPE = 0x40
BUF, ROWS, COLS = 0xC000, 192, 20
DEFAULT = 15                         # pattern nibble: the figure's own colour (palette offset)
LIST, COUNT, ATTRS = 0xFE00, 0xFF4F, 0x87AF
SITES_ORIG = {0x8052: 'dd7e09', 0x8670: '783298', 0x813E: '2100c0', 0x8093: '3a4fff',
              0x6C8F: '110140', 0x7600: '0e133e', 0x74B3: '0e1f3e', 0x8EB4: 'dd21ae'}
SITE_SYM = {0x8052: 's_p1', 0x8670: 's_p2', 0x813E: 's_bl', 0x8093: 's_pt',
            0x6C8F: 's_h3', 0x7600: 's_h1', 0x74B3: 's_h2', 0x8EB4: 's_tn'}
SITE_OP = {0x813E: 0xCD}             # CALL; the others JP
INTERIORS = (0x8053, 0x8054, 0x8671, 0x8672, 0x8673, 0x813F, 0x8140, 0x8094, 0x8095, 0x6C90, 0x6C91,
             0x7601, 0x7602, 0x7603, 0x74B4, 0x74B5, 0x74B6, 0x8EB5, 0x8EB6, 0x8EB7)
HIDES = {0x6C8F: 0x6C92, 0x7600: 0x7604, 0x74B3: 0x74B7}
HIDE_EXTRA = {0x6C8F: 0, 0x7600: 1, 0x74B3: 1}   # the site is one JP; the original ran this many more instructions
SHOW, SHOW_NEXT = 0x8EB4, 0x8EB8      # a life starts: portraits on; the original fetches 2 there, the JP 1
PORTRAIT = 0xAD52
PORTRAIT_X, PORTRAIT_Y = 176, 72
L2_BANK = 20
INK_OFF = (0, 5, 8, 14)               # pattern nibbles that are not the game's ink
HUMANS = (0xD094, 0xD298)
RAMBO = (0xD124, 0xD298)
# Which way a frame faces, from replaying each direction key (work/dirprobe.py): Q D124-48, Q+I D1E4-208, Q+P D214-38
# from behind; Z D1B4-D8, Z+I D244-68, Z+P D274-98 facing us; I D154-78 and P D184-A8 sideways.
RAMBO_BACK = ((0xD124, 0xD148), (0xD1E4, 0xD238))
RAMBO_LEFT, RAMBO_RIGHT = (0xD154, 0xD178), (0xD184, 0xD1A8)
SOLDIER_BACK = (0xD0DC, 0xD0E8)
SOLDIER_FRONT = (0xD0F4, 0xD100)
SOLDIER_LEFT, SOLDIER_RIGHT = (0xD0C4, 0xD0D0), (0xD10C, 0xD118)
HELI_EXTRA = (0xDAA4, 0xDAB0, 0xDABC, 0xDAC8, 0xDAD4, 0xDAE0)     # types 0x4E-0x51: their size byte is not h * w
HELI_BODY = (0xDAA4, 0xDAB0, 0xDABC, 0xDAC8, 0xDC48, 0xDC54, 0xDC60, 0xDC6C)   # outlined; shadows and rotors stay as they are
BLIT, BLIT_NEXT = 0x813E, 0x8141
COPPER = [0x80, 0x00, 0x16, None, 0x17, None, 0xFF, 0xFF]   # WAIT line 0; MOVE 0x16, x; MOVE 0x17, y; HALT
SELF_MOVING = ()                     # scenery types that move by themselves as well as with the world: none found
WAIT_IN = 0x8119                     # the wait before the blit: result discarded, count timing-dependent
IN_SITES = (0x6D06, 0x8B37, 0x8B57, 0x8F7E, 0x8F86, 0x8F8D, 0x8F99, 0x7224, 0x722E, 0x7238, 0x7242, 0x724C,
            0x7256, 0x8FA1)
CMP = [2, 3, 8, 9, 10, 11, 12, 14, 18, 19, 20, 21, 22, 23, 26, 27]   # live at the blit: BC, IX, IY, SP, I, BC', DE', HL', IFF, IM
# Dead at the blit, left out: AF, DE, HL (reloaded before use), AF' (only the wait loop uses it).


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'rambo.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_rambo(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from . import coloursheet as cs
    p = path or build_colours_path(COLOURS)
    return cs.load(p) if os.path.exists(p) else {}


def find_descs(peek):
    """Every graphics descriptor in the game: 12 bytes: first, last, 2 more pointers, height, width,
    rotation, size. -> {address: (first, height, width)}."""
    out = {}
    for a in range(0x6000, 0xFFF0):
        w_ = lambda k: peek(a + k) | peek(a + k + 1) << 8
        p0, p1, p2, p3 = w_(0), w_(2), w_(4), w_(6)
        h, w, sh, tot = peek(a + 8), peek(a + 9), peek(a + 10), peek(a + 11)
        if 0 < h <= 64 and 0 < w <= 8 and sh == 0 and p0 >= 0x6000 and p1 > p0 and p1 - p0 + 1 == h * w \
                and tot == (h * w) & 255 and p3 - p2 == p1 - p0:
            out[a] = (p0, h, w)
    for a in HELI_EXTRA:
        if a not in out and w_at(peek, a) >= 0x6000 and 0 < peek(a + 8) <= 64 and 0 < peek(a + 9) <= 8:
            out[a] = (w_at(peek, a), peek(a + 8), peek(a + 9))
    return out


def w_at(peek, a):
    return peek(a) | peek(a + 1) << 8


def _in(a, *ranges):
    return any(lo <= a <= hi for lo, hi in ranges)


def _head_end(a, h):
    return 6 if h == 23 else 5


def _band(a, r, h):
    """The hand-tuned class of ink at row r from the top of a figure (default palette: its own colour).
    9 skin, 10 headband, 11 clothes, 12 hair or helmet, 13 the dust at the feet."""
    if r >= h - 3:
        return 13
    if _in(a, RAMBO):
        end = _head_end(a, h)
        if _in(a, *RAMBO_BACK):
            if r <= 1:
                return 12
            if r <= 3:
                return 10
            if r <= end:
                return 12
        else:
            if r <= 1:
                return 12
            if r == 2:
                return 10
        return 9 if r <= 13 else 11
    if _in(a, SOLDIER_BACK):
        return 12 if r <= 6 else 11
    if r <= 3:
        return 12
    if r <= 6:
        return 9
    return 12 if r >= h - 5 else 11


def image_pixels(peek, a, d, cmap):
    """{(px, py): nibble}, one pixel in from the tile origin: px from the left, py from the TOP of the
    screen (rows stored bottom up). Keys: one graphics byte = 8 pixels; 0 in the map = this default.
    People and helicopter bodies get a black outline and their enclosed gaps filled, in nibbles that
    are not the game's ink: 8 black; 14 inside a face and 5 in a headband, black here, skin and red in
    the Enhanced palette."""
    p0, h, w = d
    out = {}
    human = HUMANS[0] <= a <= HUMANS[1]
    heli = a in HELI_BODY
    rambo_ = _in(a, RAMBO)
    back = _in(a, *RAMBO_BACK) or _in(a, SOLDIER_BACK)
    for r in range(h):
        for c in range(w):
            ad = p0 + r * w + c
            b = peek(ad)
            ent = cmap.get('G%04X' % ad) if cmap else None
            top = h - 1 - r
            for k in range(8):
                if b & (0x80 >> k):
                    n = _band(a, top, h) if human else DEFAULT
                    x = c * 8 + k
                    if human and n in (9, 11):
                        rt = peek(ad) & (0x80 >> (k + 1)) if k < 7 else (peek(ad + 1) & 0x80 if c + 1 < w else 0)
                        below = peek(ad - w) & (0x80 >> k) if r > 0 else 0
                        if not rt or not below:     # the lower right edges: shading, not a flat fill
                            if top > 6 and (n == 9) == rambo_:
                                n = 3
                    if human and 6 <= top <= 9:     # the gun held out sideways: dark
                        if _in(a, RAMBO_LEFT, SOLDIER_LEFT) and x < 9 or _in(a, RAMBO_RIGHT, SOLDIER_RIGHT) and x > 10:
                            n = 12
                    if heli:
                        rt = peek(ad) & (0x80 >> (k + 1)) if k < 7 else (peek(ad + 1) & 0x80 if c + 1 < w else 0)
                        below = peek(ad - w) & (0x80 >> k) if r > 0 else 0
                        if not rt or not below:     # shading, as on the people; its own colour by default
                            n = 3
                    if ent and ent[0] == b and ent[2][k]:
                        n = ent[2][k]
                    out[(x + 1, top + 1)] = n
    if human or heli:
        W, H = w * 8 + 2, h + 2
        seen, todo = set(), [(0, 0)]
        for x in range(W):
            todo += [(x, 0), (x, H - 1)]
        for y in range(H):
            todo += [(0, y), (W - 1, y)]
        while todo:
            q = todo.pop()
            if q in seen or q in out or not (0 <= q[0] < W and 0 <= q[1] < H):
                continue
            seen.add(q)
            todo += [(q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1)]
        ink = dict(out)
        if human and not back:              # a dark feature inside a face, not on its edge: eyes, mouth
            lo, hi = (4, _head_end(a, h)) if rambo_ else (5, 6)
            for (x, y), n in ink.items():
                if lo <= y - 1 <= hi and n == 9 and not any((x + i, y + j) in seen for i in (-1, 0, 1) for j in (-1, 0, 1)):
                    out[(x, y)] = 12
        for y in range(H):
            for x in range(W):
                if (x, y) in ink:
                    continue
                if (x, y) not in seen:
                    n = 8
                    if human:
                        r = y - 1
                        if rambo_:
                            if _in(a, *RAMBO_BACK):
                                n = 5 if 2 <= r <= 3 else 8
                            else:
                                n = 5 if r == 2 else 14 if 3 <= r <= _head_end(a, h) else 8
                        elif not back and 4 <= r <= 6:
                            n = 14
                    out[(x, y)] = n
                elif any((x + i, y + j) in ink and ink[(x + i, y + j)] != 13 for i in (-1, 0, 1) for j in (-1, 0, 1)):
                    out[(x, y)] = 8
    return out


def portrait_tiles(peek):
    """The two 32 x 32 portraits' 4 opaque tiles: nibble 12 the frame, 9 the face, 8 the rest."""
    px = {}
    for r in range(32):
        for c in range(4):
            b = peek(PORTRAIT + r * 4 + c)
            for k in range(8):
                x, y = c * 8 + k, 31 - r
                n = 8
                if b & (0x80 >> k):
                    n = 12 if (x - 15.5) ** 2 + (y - 15.5) ** 2 >= 12.0 ** 2 else 9
                px[(x, y)] = n
    out = bytearray()
    for ty in (0, 16):
        for tx in (0, 16):
            for y in range(16):
                for x in range(0, 16, 2):
                    out.append(px[(tx + x, ty + y)] << 4 | px[(tx + x + 1, ty + y)])
    return bytes(out)


def build_images(peek, cmap=None):
    """-> (directory bytes, list bytes, {bank: 16K}): the portrait's tiles, then every descriptor's
    non-empty 16x16 tiles."""
    descs = find_descs(peek)
    pages = [bytearray(portrait_tiles(peek))]
    entries, lst = bytearray(), bytearray()
    LIST_ORG = 0x3600
    for a in sorted(descs):
        px = image_pixels(peek, a, descs[a], cmap or {})
        tiles = []
        p0, h, w = descs[a]
        for ty in range(0, h + 2 + 15, 16):
            for tx in range(0, w * 8 + 2 + 15, 16):
                cells = [[px.get((tx + x, ty + y), 0) for x in range(16)] for y in range(16)]
                if any(any(r) for r in cells):
                    data = bytearray()
                    for r in cells:
                        for x in range(0, 16, 2):
                            data.append(r[x] << 4 | r[x + 1])
                    tiles.append((tx // 16, ty // 16, bytes(data)))
        size = 128 * len(tiles)
        if len(pages[-1]) + size > 8192:
            pages.append(bytearray())
        off = len(pages[-1])
        for tx, ty, data in tiles:
            pages[-1] += data
        lptr = LIST_ORG + len(lst)
        for tx, ty, data in tiles:
            lst.append(tx << 4 | ty)
        page = IMG_BANK * 2 + len(pages) - 1
        entries += bytes([a & 255, a >> 8, page, off & 255, off >> 8, len(tiles), lptr & 255, lptr >> 8])
    banks = {}
    for i in range(0, len(pages), 2):
        banks[IMG_BANK + i // 2] = bytes(pages[i]).ljust(8192, b'\0') + \
            (bytes(pages[i + 1]).ljust(8192, b'\0') if i + 1 < len(pages) else bytes(8192))
    if IMG_BANK + len(banks) > L2_BANK:
        raise ValueError('tiles run into the Layer 2 banks')
    return bytes(entries), bytes(lst), banks


# ---------------------------------------------------------------------------------------------
# Palettes and the dirt
# ---------------------------------------------------------------------------------------------

SP = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
PAINTS = [0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x00, 0xFC, 0xFF, 0x00]      # nibbles 0-8: the sheet's first swatches; 5 is the band's fill
SKIN, DUST = 0xF5, 0xB1
ENH_BLOCKS = {
    14: {3: 0xAC, 5: 0xE0, 9: SKIN, 10: 0xE0, 11: 0x4C, 12: 0x24, 13: DUST, 14: SKIN},  # Rambo
    12: {3: 0x2C, 9: 0xD5, 10: 0x92, 11: 0x34, 12: 0x4C, 13: DUST, 14: 0xD5},        # green soldiers
    13: {3: 0x2B, 9: 0xD5, 10: 0x92, 11: 0x2F, 12: 0x4B, 13: DUST, 14: 0xD5},        # blue soldiers
    15: {3: 0xB6, 9: 0xD5, 10: 0x92, 11: 0xDB, 12: 0x6D, 13: DUST, 14: 0xD5},        # white: prisoners; shots keep nibble 15
}


def palette(enhanced=False):
    """256 sprite palette bytes: block o = the figure's game colour; nibbles 1-8 fixed, 9-13 and 15
    its own colour, 14 black; the Enhanced set changes only this table, the flag and two bytes."""
    out = bytearray()
    for o in range(16):
        b = PAINTS + [SP[o]] * 5 + [0x00, SP[o]]
        b[3] = SP[o]                        # nibble 3: shading, its own colour by default
        if o == 1:
            b[9], b[12] = 0xFF, 0x1C        # the portrait's own: white face, green frame, in both sets: the panel stays
        if enhanced and o in ENH_BLOCKS:
            for n, v in ENH_BLOCKS[o].items():
                b[n] = v
            if o != 15:
                b[15] = ENH_BLOCKS[o][11]
        out += bytes(b)
    return bytes(out)


def dirt_tile():
    """256 x 64 dirt that wraps both ways, made here by a fixed-seed generator: soft patches and fine grain, four browns.
    256 wide and 64 tall because the hook scrolls Layer 2 by the world position in x modulo 256 and in y modulo 64."""
    W, H = 256, 64
    seed = [0x2F6E2B1]

    def rnd():
        seed[0] = (seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return seed[0] >> 16

    field = [[0.0] * W for _ in range(H)]
    for sx, sy, amp in ((32, 32, 1.6), (16, 16, 1.2), (8, 8, 0.8), (4, 4, 0.6), (2, 2, 0.5), (1, 1, 0.4)):
        nx, ny = W // sx, H // sy
        g = [[rnd() % 256 / 255.0 for _ in range(nx)] for _ in range(ny)]
        for y in range(H):
            for x in range(W):
                fx, fy = x / sx, y / sy
                x0, y0 = int(fx), int(fy)
                tx, ty = fx - x0, fy - y0
                tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
                a, b = g[y0 % ny][x0 % nx], g[y0 % ny][(x0 + 1) % nx]
                c, d = g[(y0 + 1) % ny][x0 % nx], g[(y0 + 1) % ny][(x0 + 1) % nx]
                field[y][x] += amp * ((a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty)
    vals = sorted(v for row in field for v in row)
    cut = [vals[len(vals) * k // 100] for k in (18, 62, 92)]
    return [[1 + sum(v > c for c in cut) for v in row] for row in field]    # Layer 2 palette entries 1-4, set up by the hook


def dirt_banks():
    """Three 16K Layer 2 banks: the dirt over the whole picture; a clip window keeps it off the panel. No other art."""
    tile = dirt_tile()
    pic = bytearray(49152)
    for y in range(192):
        pic[y * 256:y * 256 + 256] = bytes(tile[y % 64])
    return {L2_BANK + i: bytes(pic[i * 16384:(i + 1) * 16384]) for i in range(3)}


class RamboPatch:
    name = 'Rambo figures -> hardware sprites (RAM stubs, Next page at slot 1 during hooks)'

    def __init__(self, prof=None, edit=None, enhanced=False):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.ram_code = bytearray.fromhex(h['ram'])
        self.page_code = bytearray.fromhex(h['page'])
        st = bytearray.fromhex(h['setup'])
        pt = self.syms['pal_tab'] - 0xD000
        st[pt:pt + 256] = palette(enhanced)
        if enhanced:
            st[self.syms['enh_flag'] - 0xD000] = 1
            self.page_code[self.syms['vnr15'] - PAGE_ORG] = 9
            self.page_code[self.syms['vnr69'] - PAGE_ORG] = 0x80
        self.stub_extra = bytes(st)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.extra_banks = {}
        self.num_patterns = 128
        self.page = b''
        self.images = {}
        if edit:
            edit(self)
        self.sites = []
        for a, old in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old),
                               bytes([SITE_OP.get(a, 0xC3)]) + self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        self.sites.append((RAM_ORG, bytes(len(self.ram_code)), bytes(self.ram_code)))

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Rambo patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        peek = lambda a: ram[a - 0x4000]
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        base = getattr(self, 'base_z80', None)  # a later scene's snapshot: tiles from the game's start
        if base:
            from . import z80tonex as zt
            b = zt.Z80Snapshot(base)
            r0 = bytes(b.banks[5] + b.banks[2] + b.banks[0])
            self.build_page(lambda a: r0[a - 0x4000])
        else:
            self.build_page(peek)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {H_BANK: bytes(self.page) + bytes(8192)}
        self.extra_banks.update(self.images)
        self.extra_banks.update(dirt_banks())

    def build_page(self, peek):
        d, l, self.images = build_images(peek, load_colours())
        pg = bytearray(8192)
        pg[0:len(self.page_code)] = self.page_code
        dir_at = self.syms['DIR'] - PAGE_ORG
        if len(d) > 0x600 or len(l) > 0x400:
            raise ValueError('directory %d, list %d: too long' % (len(d), len(l)))
        pg[dir_at:dir_at + len(d)] = d
        pg[dir_at + 0x600:dir_at + 0x600 + len(l)] = l
        pg[self.syms['ndir'] - PAGE_ORG] = len(d) // 8
        self.page = bytes(pg)


# ---------------------------------------------------------------------------------------------
# The patched machine
# ---------------------------------------------------------------------------------------------

class Patched:
    """The real patched game on a Python simulator: slot 0 / 1 paging, sprite ports, NEXTREG."""

    def __init__(self, patch, snap, frames=None):
        from skoolkit.simutils import from_snapshot
        from .build import rom48
        from .dizzy6 import _rw_simulator
        from . import z80n
        self.patch = patch
        self.sim = from_snapshot(_rw_simulator(), snap, config={'int_active': 0})
        self.mem = self.sim.memory
        self.rom = bytes(rom48())
        self.mem[0:0x4000] = list(self.rom)
        self.pages = {H_BANK * 2: bytearray(patch.page)}
        for b, data in patch.images.items():
            self.pages[b * 2], self.pages[b * 2 + 1] = bytearray(data[:8192]), bytearray(data[8192:])
        self.map = {0: 0xFF, 1: 0xFF}
        for a, old, new in patch.sites:
            self.mem[a:a + len(new)] = list(new)
        self.nr = {0x15: 1}
        self.cop, self.cop_i, self.cop_mode, self.cop_starts = bytearray(2048), 0, 0, 0
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.sel_a = self.sel_p = 0
        self.apos = 0
        self.inq = collections.deque()
        self.c = collections.Counter()
        self.fail = None
        s = patch.syms
        self.watch = {s['h_fig'], s['s_fb0'], s['s_fb1'], s['s_bl'], s['s_pt'], s['s_h1'], s['s_h2'], s['s_h3'],
                      s['s_tn'], 0x8068, 0x8680} | set(INTERIORS)
        self.names = {s['h_fig']: 'figure', s['s_fb0']: 'fallback', s['s_fb1']: 'fallback', s['s_bl']: 'blit',
                      s['s_pt']: 'painter', s['s_h1']: 'hide 7600', s['s_h2']: 'hide 74B3', s['s_h3']: 'hide 6C8F',
                      s['s_tn']: 'life start'}
        self.fb = False
        self.seen = collections.Counter()
        self.frames = frames or []
        self.fi = -1
        self.fc = self.next_frame()
        self.sim.set_tracer(self)
        z80n.install(self.sim, self.nextreg, strict=False)

    def _slot(self, slot, page):
        lo, hi = slot * 0x2000, (slot + 1) * 0x2000
        cur = self.map[slot]
        if cur != 0xFF:
            self.pages[cur][:] = bytes(self.mem[lo:hi])
        elif bytes(self.mem[lo:hi]) != self.rom[lo:hi]:
            self.c['ROM written!'] += 1
        self.mem[lo:hi] = list(self.rom[lo:hi]) if page == 0xFF else list(self.pages.setdefault(page, bytearray(8192)))
        self.map[slot] = page

    def nextreg(self, reg, val):
        if reg in (0x50, 0x51):
            self._slot(reg - 0x50, val)
        elif reg == 0x60:
            self.cop[self.cop_i & 0x7FF] = val
            self.cop_i += 1
        elif reg == 0x61:
            self.cop_i = self.cop_i & 0x700 | val
        elif reg == 0x62:
            self.cop_i = self.cop_i & 0xFF | (val & 7) << 8
            self.cop_mode = val >> 6
            self.cop_starts += self.cop_mode == 1
        self.nr[reg] = val
        self.c['nr other!' if reg not in (0x07, 0x15, 0x50, 0x51, 0x60, 0x61, 0x62, 0x69) else 'nr ok'] += 1

    def dirt(self):
        """The scroll the copper sets at the top of the next frame: (x, y), or None if its list is not the expected one."""
        got = list(self.cop[:8])
        if self.cop_mode != 1 or any(w is not None and w != g for w, g in zip(COPPER, got)):
            return None
        return got[3], got[5]

    def read_port(self, regs, port):
        pc = regs[24]
        if port == 0x253B and getattr(self, 'nrsel', None) == 0x07:   # the hooks' speed latch: NR 7 as the core
            sp = self.nr.get(0x07, 0) & 3                             # composes it (actual << 4 | programmed)
            return sp << 4 | sp
        if pc == WAIT_IN:
            return 0xFF
        if not self.inq:
            self.c['IN with no recorded value!'] += 1
            return 0xFF
        qpc, v = self.inq.popleft()
        if qpc != pc:
            self.c['IN out of step!'] += 1
            self.fail = (pc, qpc)
        return v

    def write_port(self, regs, port, value, *x):
        p = port & 0xFF
        if port == 0x243B:                  # NextREG select (the speed latch reads NR 7)
            self.nrsel = value
            return
        if port == 0x303B:
            self.sel_a = value & 0x7F
            self.sel_p = ((value & 0x3F) << 8) | (0x80 if value & 0x80 else 0)
            self.apos = 0
        elif p == 0x5B:
            if 60 * 128 <= self.sel_p & 0x3FFF < 64 * 128:
                self.c['portrait pattern overwritten!'] += 1
            self.pat[self.sel_p & 0x3FFF] = value
            self.sel_p += 1
        elif p == 0x57:
            self.attr[self.sel_a & 0x7F][self.apos] = value
            self.apos += 1
            if self.apos == 5 or (self.apos == 4 and not value & 0x40):
                self.apos = 0
                self.sel_a += 1

    def run_to(self, target, limit=20000000):
        """Run to `target`. Frames as rzxplay counts them: the recording's fetch counts, not counting
        the hooks' own fetches, so the patched game takes interrupts where the original does in
        everything the hooks do not touch (the title tune's IN sequence depends on it)."""
        R, mem, ops, watch = self.sim.registers, self.mem, self.sim.opcodes, self.watch
        fc, lo, hi = self.fc, RAM_ORG, RAM_ORG + len(self.patch.ram_code)
        n = 0
        while True:
            pc = R[24]
            if pc == target:
                self.fc = fc
                return True
            if pc in watch:
                self.on_watch(pc)
            op = mem[pc]
            if lo <= pc < hi or 0x2000 <= pc < 0x3000:
                ops[op]()
            elif op == 0xDD or op == 0xFD:
                r0 = R[15]
                ops[op]()
                fc -= 2 - ((R[15] ^ r0) % 2)
            else:
                ops[op]()
                fc -= 2 if op == 0xCB or op == 0xED else 1
            n += 1
            if fc <= 0:
                R[25] = 0
                fc = self.next_frame()
                if R[26]:
                    if mem[pc] == 0x76:
                        R[24] = (R[24] + 1) % 65536
                    self.c['interrupts'] += 1
                    self.sim.accept_interrupt(R, mem, 0)
            if n > limit:
                self.fc = fc
                self.c['ran away!'] += 1
                return False

    def next_frame(self):
        while True:
            self.fi += 1
            if self.fi >= len(self.frames):
                return 17000            # past the recording's end: a plain frame's worth
            f = self.frames[self.fi]
            if f > 0:
                return f

    def on_watch(self, pc):
        from skoolkit.simutils import IFF
        R, mem = self.sim.registers, self.mem
        name = self.names.get(pc)
        if name:
            self.c[name] += 1
            if name == 'fallback':
                self.fb = True
            if name in ('figure', 'blit', 'life start') and R[IFF]:
                self.c['interrupts on at a hook!'] += 1
            if name == 'figure':
                iy, ix = R[10] * 256 + R[11], R[8] * 256 + R[9]
                self.seen[(mem[iy + 1], ix)] += 1
            return
        if pc in (0x8068, 0x8680):
            iy = R[10] * 256 + R[11]
            if mem[iy + 1] >= FIGTYPE:
                if self.fb:
                    self.c['figures left on the ULA (fallback)'] += 1
                else:
                    self.c['figure reached the ULA plot!'] += 1
            self.fb = False
            return
        self.c['jump into a patched instruction!'] += 1

    def sprite_rows_coloured(self):
        """{(x, y): palette offset} of the sprite layer inside the clip window."""
        out, used = {}, set()
        for a0, a1, a2, a3, a4 in self.attr[:120]:
            if not a3 & 0x80:
                continue
            x, y = a0 | (a2 & 1) << 8, a1 | (a4 & 1) << 8
            x, y = (x - 512 if x >= 448 else x) - 32, (y - 512 if y >= 448 else y) - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            used.add(a2 >> 4)
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + (k >> 1)]
                    if (b >> 4 if not k & 1 else b & 15) not in INK_OFF and 0 <= x + k < COLS * 8 and 0 <= y + j < ROWS:
                        out[(x + k, y + j)] = a2 >> 4
        return out, used

    def sprite_rows(self):
        """{row: {col: bits}} of the sprite layer inside the clip window, and the palette offsets used."""
        S, used = collections.defaultdict(dict), set()
        pat = self.pat
        if not self.nr.get(0x15, 0) & 1:
            return S, used
        for a0, a1, a2, a3, a4 in self.attr[:120]:
            if not a3 & 0x80:
                continue
            x = a0 | (a2 & 1) << 8
            y = a1 | (a4 & 1) << 8
            if x >= 448:
                x -= 512
            if y >= 448:
                y -= 512
            x -= 32
            y -= 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            used.add(a2 >> 4)
            for j in range(16):
                sy = y + j
                if not 0 <= sy < ROWS:
                    continue
                row = pat[base + j * 8:base + j * 8 + 8]
                for k in range(16):
                    b = row[k >> 1]
                    nib = b >> 4 if not k & 1 else b & 15
                    sx = x + k
                    if nib and sx >= COLS * 8:
                        self.c['figure pixel over the panel!'] += 1
                    if nib not in INK_OFF and 0 <= sx < COLS * 8:
                        d = S[sy]
                        d[sx >> 3] = d.get(sx >> 3, 0) | 0x80 >> (sx & 7)
        return S, used


def _masks(patch):
    """RAM the patch owns or that no logic reads: not compared."""
    m = [(0x4000, 0x5B01), (patch.tail_addr, patch.tail_addr + 64), (RAM_ORG, RAM_ORG + len(patch.ram_code)),
         (BUF, BUF + ROWS * COLS), (LIST, LIST + 0x100), (COUNT, COUNT + 1)]
    m += [(a, a + len(new)) for a, old, new in patch.sites if a != RAM_ORG]
    return m


def _ranges(masks):
    pos, out = 0x4000, []
    for lo, hi in sorted(masks):
        if lo > pos:
            out.append((pos, lo))
        pos = max(pos, hi)
    if pos < 0x10000:
        out.append((pos, 0x10000))
    return out


def picture(o_mem, p):
    """Original buffer against patched buffer | sprites. -> (differing bytes, sprite offsets used)."""
    S, used = p.sprite_rows()
    bad = 0
    o = bytes(o_mem[BUF:BUF + ROWS * COLS])
    q = bytes(p.mem[BUF:BUF + ROWS * COLS])
    if not S:
        return (0 if o == q else sum(1 for a, b in zip(o, q) if a != b)), used
    for y in range(ROWS):
        ro, rq = o[y * COLS:(y + 1) * COLS], q[y * COLS:(y + 1) * COLS]
        d = S.get(y)
        if d:
            for c in range(COLS):
                if ro[c] != rq[c] | d.get(c, 0):
                    bad += 1
        elif ro != rq:
            bad += sum(1 for a, b in zip(ro, rq) if a != b)
    return bad, used


def census(o_mem, p, c):
    """Informational: what the original does to the figures' pixels and to the scenery near them."""
    S, used = p.sprite_rows_coloured()
    for (sx, sy), col in S.items():
        a = o_mem[0x5800 + (sy >> 3) * 32 + (sx >> 3)]
        c['clash: figure pixels'] += 1
        if (a & 7) | (a & 0x40) >> 3 != col:
            c['clash: figure pixels in another colour in the original'] += 1
    o = o_mem
    q = p.mem
    for row in range(24):
        for col in range(COLS):
            ao, ap = o[0x5800 + row * 32 + col], q[0x5800 + row * 32 + col]
            if ao != ap:
                n = 0
                for y in range(8):
                    n += bin(q[BUF + (row * 8 + y) * COLS + col]).count('1')
                if n:
                    c['clash: scenery pixels recoloured in the original'] += n


def render(mem, attrs=None, sprites=None):
    """A frame as the blit will show it: buffer for the play area, the screen for the panel. -> Image"""
    from PIL import Image
    pal = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
           (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]
    im = Image.new('RGB', (256, 192))
    px = im.load()
    for y in range(192):
        base = 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2
        for cx in range(32):
            b = mem[BUF + y * COLS + cx] if cx < COLS else mem[base + cx]
            a = mem[0x5800 + (y >> 3) * 32 + cx]
            bright = 8 if a & 0x40 else 0
            for i in range(8):
                px[cx * 8 + i, y] = pal[(a & 7 if b & 0x80 >> i else a >> 3 & 7) + bright]
    if sprites:
        for (sx, sy), col in sprites.items():
            px[sx, sy] = pal[col]
    return im


def portraits(o_mem, p, fail):
    """Slots 120-127 against what the original's screen holds in each portrait's place."""
    for i, slot in enumerate((120, 124)):
        x = PORTRAIT_X // 8 + i * 4
        on = False
        for y in range(PORTRAIT_Y, PORTRAIT_Y + 32):
            base = 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2
            if any(o_mem[base + x + k] for k in range(4)):
                on = True
                break
        shown = [bool(p.attr[slot + k][3] & 0x80) for k in range(4)]
        if shown != [on] * 4:
            fail('portrait count', (i, on, shown))


def scenery(m):
    """(type, descriptor, x, y) of every scenery object on show; y counts up from the bottom."""
    n, q, out = m[0xFF2C], m[0xFF2D] | m[0xFF2E] << 8, []
    for _ in range(n):
        q -= 10
        if m[q + 1] < FIGTYPE:
            x, y = m[q + 2], m[q + 3] + (m[q + 4] & 0x7F)
            if m[q] & 0x40 and x >= 128:
                x -= 256
            if m[q] & 0x80 and y >= 128:
                y -= 256
            d = m[q + 8] | m[q + 9] << 8
            if x < COLS * 8 and x + m[d + 9] * 8 > 0 and y < ROWS and y + m[d + 8] > 0:    # on show: the game keeps
                out.append((m[q + 1], d, x, y))         # columns beyond the edge, and re-makes them as it turns round
    return out


def _followed(st, mem):
    """The world values a commit shows: those at the commit before, or the new ones after a jump of more than a step."""
    cy, cx = mem[0xFF2F], mem[0xFF33]
    py = st['py'] if ((cy - st['py'] + 8) & 255) < 17 else cy
    px = st['px'] if ((cx - st['px'] + 1) & 255) < 3 else cx
    st['py'], st['px'] = cy, cx
    return py, px


def pinned(mem, p, st, c, fail):
    """Is each scenery object where it was on the dirt? Its place: the dirt column and row under it, from the Layer 2 scroll
    registers. An object the last blit had in that place is kept; one whose place changed, with the old place now empty and
    within 16 pixels, has slid on the dirt. Objects with no such neighbour are new on the list. The offsets add up the objects'
    own steps against the registers' from each start: they must stay 0. A register jump larger than a step is a new start."""
    nx, ny = p.dirt() or (0, 0)
    now = scenery(mem)
    places = [(t, d, (x + nx) & 255, (ny - y) & 63) for t, d, x, y in now]
    old, was = st.get('places', []), st.get('now', [])
    seen = st.setdefault('seen', set())
    reset = not was or ((nx - st['nx'] + 8) & 255) > 16 or ((ny - st['ny'] + 8) & 63) > 16
    if was and reset:                   # a new start: the old list is gone; is the same map on the same dirt?
        c['lock: resets'] += 1
    if reset:
        st.pop('ox', None), st.pop('oy', None)
        again = sum(k in seen for k in places)
        c['lock: at a reset, objects on dirt they had before'] += again
        c['lock: at a reset, objects new to the run'] += len(places) - again
    else:
        left = collections.Counter(old)
        fresh = []
        for k, o in zip(places, now):
            if left[k]:
                left[k] -= 1
                c['lock: objects kept their place'] += 1
            else:
                fresh.append(o)
        gone = []
        for k, o in zip(old, was):
            if left[k]:
                left[k] -= 1
                gone.append(o)
        for o in fresh:
            near = [g for g in gone if g[:2] == o[:2] and abs(g[2] - o[2]) <= 16 and abs(g[3] - o[3]) <= 16]
            if near and o[2] < 0 and any(g[2:] == o[2:] for g in near):
                c['lock: re-made by the game at the left edge, one column on show'] += 1
            elif near:
                c['lock: objects slid on the dirt'] += 1
                if o[0] not in SELF_MOVING:
                    fail('scenery slid on the dirt', (c['blits'], o, near[0], nx, ny))
            else:
                c['lock: objects new on the list'] += 1
        steps = collections.Counter()
        for a in now:
            for b in was:
                if a[:2] == b[:2] and a[2] >= 0 and b[2] >= 0 and abs(a[2] - b[2]) <= 16 and abs(a[3] - b[3]) <= 16:
                    steps[(a[2] - b[2], a[3] - b[3])] += 1
        if steps:
            (dx, dy), _ = steps.most_common(1)[0]
            st['ox'] = st.get('ox', 0) + dx + ((nx - st['nx'] + 128) & 255) - 128
            st['oy'] = st.get('oy', 0) - dy + ((ny - st['ny'] + 32) & 63) - 32
            c['lock: x offset, largest'] = max(c['lock: x offset, largest'], abs(st['ox']))
            c['lock: y offset, largest'] = max(c['lock: y offset, largest'], abs(st['oy']))
            c['lock: pixels scrolled x'] += abs(dx)
            c['lock: pixels scrolled y'] += abs(dy)
            c['lock: Layer 2 x wraps'] += nx < st['nx'] and st['nx'] - nx > 128 or nx > st['nx'] and nx - st['nx'] > 128
            c['lock: Layer 2 y wraps'] += ny < st['ny'] and st['ny'] - ny > 32 or ny > st['ny'] and ny - st['ny'] > 32
    seen.update(places)
    st['places'], st['now'], st['nx'], st['ny'] = places, now, nx, ny


def attr_lists(o_mem, p):
    """The patched list must be the original's minus the figures. -> (ok, colours of the figures)."""
    no, np_ = o_mem[COUNT], p.mem[COUNT]
    a = bytes(o_mem[LIST:LIST + 5 * no])
    b = bytes(p.mem[LIST:LIST + 5 * np_])
    i = 0
    gone = set()
    for k in range(no):
        e = a[k * 5:k * 5 + 5]
        if i < np_ and b[i * 5:i * 5 + 5] == e:
            i += 1
        else:
            gone.add((e[4] & 7) | (e[4] & 0x40) >> 3)
    return i == np_, gone


def _trace(path, pcs, on_pc, stop=None):
    """rzx.trace, with the frame index and the fetch count left passed on."""
    import skoolkit.rzxplay as rp
    from types import SimpleNamespace
    from skoolkit import SkoolKitError
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    blocks = parse_rzx(path)
    while blocks and isinstance(blocks[-1].obj, Snapshot):
        blocks.pop()
    ctx = rp.RZXContext(None)
    for b in blocks:
        if isinstance(b.obj, rp.InputRecording):
            ctx.total_frames += len(b.obj.frames)
    if stop:
        ctx.total_frames = min(stop, ctx.total_frames)

    class Sink:
        def write(self, s):
            pass
    ctx.tracefile = Sink()
    pcs = frozenset(pcs)

    def hook(tf, context, fc, pc):
        if pc in pcs:
            on_pc(pc, context.simulator, context.simulator.tracer.frame_index, fc)
    old = rp.trace_exec
    rp.trace_exec = hook
    err = None
    try:
        opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=stop or 0, force=False)
        while blocks:
            rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
            if ctx.stop:
                break
    except SkoolKitError as e:
        err = str(e)
    finally:
        rp.trace_exec = old
    return ctx.frame_count, err


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shots=None, stats=False):
    """See the module docstring. -> (Counter, examples[, states]); failures end in '!'."""
    from . import rzx as RZ
    import tempfile
    c = collections.Counter()
    ex = collections.defaultdict(list)
    segs = RZ.read_segments(rzx_path)
    if len(segs) != 1:
        raise ValueError('expects one segment (record --script), found %d' % len(segs))
    p = Patched(patch, segs[0][0], [f.fetch_counter for f in segs[0][1].frames])
    masks = _masks(patch)
    states = []
    site_old = [(a, old) for a, old, new in patch.sites]
    m0 = segs[0][0].memory
    in_after = {a + 2: a for a in range(0x6000, 0xFFF0) if m0[a] == 0xDB and m0[a + 1] == 0xFE and a != WAIT_IN}
    pcs = set(in_after) | set(HIDES) | {BLIT, SHOW}
    st = {'frames': 0, 'py': 0, 'px': 0}

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append(info)

    def on_pc(pc, sim, fi, fc):
        R = sim.registers
        if pc in in_after:
            p.inq.append((in_after[pc], R[0]))
            return
        mem = sim.memory
        if not p.run_to(pc):
            fail('patched run lost', (hex(pc), hex(p.sim.registers[24])))
            return
        c['events'] += 1
        p.fi, p.fc = fi, fc             # same place in the frame as the original from here on
        for lo, hi in _ranges(masks + [(R[12] - 64, R[12])]):      # + the dead stack
            if bytes(mem[lo:hi]) != bytes(p.mem[lo:hi]):
                d = [a for a in range(lo, hi) if mem[a] != p.mem[a]]
                fail('memory differs', (hex(pc), len(d), [hex(a) for a in d[:6]]))
                break
        sp = R[12]
        if sp != p.sim.registers[12]:
            fail('SP differs', (hex(pc), sp, p.sim.registers[12]))
        if pc == SHOW:
            p.run_to(SHOW_NEXT)
            p.fc -= 1
            c['life starts'] += 1
            _followed(st, mem)
            st['cop_starts'] = p.cop_starts     # its commit arms the copper too
            if not p.nr.get(0x15, 0) & 1:
                fail('sprites off at a life start', (hex(pc),))
            if any(a[3] & 0x80 for a in p.attr[:120]):
                fail('a figure left on at a life start', (hex(pc),))
            if p.nr.get(0x69, 0):
                fail('Layer 2 on during a life start', (hex(pc),))
            portraits(mem, p, fail)
            return
        if pc in HIDES:
            p.run_to(HIDES[pc])
            p.fc -= HIDE_EXTRA[pc]
            c['hides'] += 1
            if p.nr.get(0x15, 1) & 1 or p.nr.get(0x69, 0):
                fail('sprites still on after a hide site', (hex(pc),))
            return
        # the blit
        diff = [i for i in CMP if R[i] != p.sim.registers[i]]
        if diff:
            fail('registers differ', (hex(pc), diff, [R[i] for i in diff], [p.sim.registers[i] for i in diff]))
        ok, gone = attr_lists(mem, p)
        if not ok:
            fail('attribute list', (mem[COUNT], p.mem[COUNT]))
        p.run_to(BLIT_NEXT)
        bad, used = picture(mem, p)
        c['blits'] += 1
        portraits(mem, p, fail)
        shown = tuple(bool(p.attr[s_][3] & 0x80) for s_ in (120, 124))
        if st.get('shown') not in (None, shown):
            c['portrait changes'] += 1
        st['shown'] = shown
        c['portraits on, 2'] += all(shown)
        c['portraits on, 1'] += sum(shown) == 1
        c['portraits on, 0'] += not any(shown)
        if p.nr.get(0x69, 0) != patch.page_code[patch.syms['vnr69'] - PAGE_ORG]:
            fail('Layer 2 not as the set says at a blit', (p.nr.get(0x69),))
        py, px = _followed(st, mem)
        d = p.dirt()
        if d is None:
            fail('copper list not as written', (p.cop_mode, list(p.cop[:8])))
        elif d != (px * 8 & 255, -py & 63):
            fail('dirt not at the world position', (d, py, px))
        if p.cop_starts != st.get('cop_starts', 0) + 1:
            fail('copper not started once at the commit', (p.cop_starts, st.get('cop_starts')))
        st['cop_starts'] = p.cop_starts
        pinned(mem, p, st, c, fail)
        if bad:
            fail('picture differs', (c['blits'], bad))
        if used - gone:
            fail('sprite colour not a figure colour', (sorted(used), sorted(gone)))
        c['sprites shown'] += sum(1 for a in p.attr if a[3] & 0x80)
        if stats and c['blits'] % 4 == 0:
            census(mem, p, c)
        if shots is not None:
            shots(c['blits'], mem, p)
        if collect and len(states) < collect:
            states.append((bytes(mem[:65536]), list(R)))

    frames, err = _trace(rzx_path, pcs, on_pc, stop=stop)
    if err:
        c['recording desynced!'] += 1
        ex['recording desynced'].append(err)
    c['frames'] = frames
    c.update(p.c)
    c.seen = p.seen
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit cases: every descriptor at edge positions, through the game's own display-list loop
# ---------------------------------------------------------------------------------------------

UNIT_REC, UNIT_STOP = 0xCF00, 0x5BFF
POSITIONS = [(64, 64, 0), (67, 8, 0), (155, 100, 0), (152, 180, 0), (0xF0, 40, 0x40), (0xFB, 120, 0x40), (0x04, 60, 0x40),
             (32, 0xF8, 0x80), (100, 0xE0, 0x80)]


def _one(mem, ty, desc, x, y, flags, sp):
    mem[UNIT_REC:UNIT_REC + 10] = [flags, ty, x, y, 0, 0, 0, 0, desc & 255, desc >> 8]
    mem[0xFF2C] = 1
    mem[0xFF2D], mem[0xFF2E] = (UNIT_REC + 10) & 255, (UNIT_REC + 10) >> 8
    mem[BUF:BUF + ROWS * COLS] = [0] * (ROWS * COLS)
    mem[sp], mem[sp + 1] = UNIT_STOP & 255, UNIT_STOP >> 8


def _go(sim, stop, limit=4000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[24] != stop and n < limit:
        ops[mem[R[24]]]()
        n += 1
    return R[24] == stop


def unit_tests(patch, ctx, cases=None):
    """ctx = (RZX snapshot, memory, registers) of a captured blit. Original against patched, one object
    at a time through 0x83D1: all RAM the patch does not own, the attribute list, and the picture.
    cases: [(descriptor, type)]; default every descriptor, x the positions."""
    from skoolkit.simutils import from_snapshot
    from skoolkit.simulator import Simulator
    u = collections.Counter()
    snap, mem0, regs0 = ctx
    found = find_descs(lambda a: snap.memory[a])
    descs = sorted(found)
    p = Patched(patch, snap)
    o = from_snapshot(Simulator, snap, config={'int_active': 0})
    p.mem[0x4000:] = list(mem0[0x4000:])
    for a, old, new in patch.sites:
        p.mem[a:a + len(new)] = list(new)
    o.memory[0x4000:] = list(mem0[0x4000:])
    o.memory[0:0x4000] = list(p.rom)
    o.registers[:] = type(o.registers)(o.registers.typecode, regs0) if hasattr(o.registers, 'typecode') else list(regs0)
    p.sim.registers[:] = type(o.registers)(o.registers.typecode, regs0) if hasattr(o.registers, 'typecode') else list(regs0)
    ranges = _ranges(_masks(patch))
    SP = 0xFFE0
    def spare(d):
        q0, h, w = found[d]
        return not any(snap.memory[q0 + r * w + w - 1] for r in range(h))
    # Rotation needs an empty last column (bits leaving a row enter the next): the game rotates only
    # types >= 0x42, whose graphics have one; a graphic with no spare column goes down the cell path.
    for d, ty in cases or [(d, 0x44 if spare(d) else 0x40) for d in descs]:
        for x, y, fl in POSITIONS:
            for sim in (o, p.sim):
                _one(sim.memory, ty, d, x, y, fl, SP)
                sim.registers[12], sim.registers[24] = SP, 0x83D1
            if not (_go(o, UNIT_STOP) and p.run_to(UNIT_STOP)):
                u['did not return!'] += 1
                continue
            u['cases'] += 1
            ok, gone = attr_lists(o.memory, p)
            if not ok:
                u['attribute list!'] += 1
            for lo, hi in ranges:
                if bytes(o.memory[lo:hi]) != bytes(p.mem[lo:hi]):
                    bad = [a for a in range(lo, hi) if o.memory[a] != p.mem[a] and not SP - 32 <= a < SP + 2]
                    if bad:
                        u['memory differs!'] += 1
                        break
            p.mem[SP], p.mem[SP + 1] = UNIT_STOP & 255, UNIT_STOP >> 8
            p.sim.registers[12], p.sim.registers[24] = SP, patch.syms['s_bl']
            p.run_to(UNIT_STOP)
            bad, used = picture(o.memory, p)
            if bad:
                u['picture differs!'] += 1
            if used - gone:
                u['sprite colour!'] += 1
            for a in range(len(p.attr)):
                u['sprites visible'] += 1 if p.attr[a][3] & 0x80 else 0
    u.update({k: v for k, v in p.c.items() if k.endswith('!') or k in ('figure', 'fallback')})
    return u


def _set(block, off, val):
    block[off] = val


def negative_patches():
    """Broken builds, each with one thing wrong: name -> RamboPatch."""
    def page(sym, k, v):
        return lambda t: _set(t.page_code, t.syms[sym] - PAGE_ORG + k, v)

    def ram(sym, k, v):
        return lambda t: _set(t.ram_code, t.syms[sym] - RAM_ORG + k, v)

    def many(*fs):
        def f(t):
            for g in fs:
                g(t)
        return f
    return {
        'sprites one row low': page('h_y224', 1, 225),
        'sprites one pixel right': page('h_x32', 1, 33),
        'colour lost': many(page('h_col', 0, 0), page('h_col', 1, 0)),
        'attribute box kept': page('h_rew', 6, 0),
        'figures stay on the ULA': many(ram('s_p1', 4, 0xFF), ram('s_p2', 4, 0xFF)),
        'commit never runs': many(ram('s_blc', 0, 0), ram('s_blc', 1, 0), ram('s_blc', 2, 0)),
        'plot side effect lost': many(ram('s_f1', 3, 0), ram('s_f1', 4, 0), ram('s_f1', 5, 0)),
        'hide sites do nothing': many(ram('s_h1', 3, 1), ram('s_h2', 3, 1), ram('s_h3', 3, 1)),
        'portraits read the wrong row': many(page('h_ln', -1, 0x40)),
        'figures over the panel': many(page('h_clip', 1, 255), page('h_clip2', 1, 255)),
        'dirt stays still in y': page('h_scr', 1, 0),
        'dirt stays still in x': many(page('h_scx', 0, 0xAF), page('h_scx', 1, 0), page('h_scx', 2, 0)),
        'dirt one step ahead': many(page('h_scy', 1, 0x2F), page('h_scy', 2, 0xFF)),
        'dirt registers swapped in the copper list': many(page('h_cw', 11, 0x17), page('h_cw', 19, 0x16)),
        'copper waits for line 100, mid-picture': page('h_cw', 7, 100),
        'copper never started': page('h_cw', 35, 0),
        'Layer 2 on during the life tune': ram('s_tn', 17, 0x80),   # NEXTREG 0x69,0's operand (after CALL spdi)
    }


def build(z80, out, edit=None, quiet=True):
    from . import z80tonex as zt
    t = RamboPatch(edit=edit)
    conv = zt.convert(z80, out, None, True, quiet=quiet, patch=t)
    return t, conv


def build_enhanced(z80, out, quiet=True):
    """The Enhanced colour set (off by default): the same layout, 35 bytes differ (palette, enh_flag, 2 in
    the hook page)."""
    from . import z80tonex as zt
    t = RamboPatch(enhanced=True)
    conv = zt.convert(z80, out, None, True, quiet=quiet, patch=t)
    return t, conv


LOAD_BANK = 23          # the loading screen's entry bank (pages 46, 47)
LOAD_SCREEN = 'rambo_loading.scr'   # the archive tape's 6,912-byte screen block, beside the snapshot


def loading_screen(z80, name):
    """The loading screen beside the snapshot (<name>_loading.scr or rambo_loading.scr), or None. Game
    data: never in this repo (specnext/reference/rambo/rambo_loading.scr)."""
    d = os.path.dirname(os.path.abspath(z80))
    for f in (name + '_loading.scr', LOAD_SCREEN):
        p = os.path.join(d, f)
        if os.path.isfile(p) and os.path.getsize(p) == 6912:
            return open(p, 'rb').read()
    return None


def loading_nex(nex, scr):
    """A built .nex -> the same with the loading screen (runs/rambo/loading/mk.py, 2026-11-03): bank 5's
    screen area in the file = the loading screen (on show while the rest loads), new bank 23 = the
    entry bank: the stub (asm ldscr: ld_head, the game's own screen bytes at 0x0200, ld_tail) shows it
    for 250 frames or a key, puts bank 5's bytes back and falls into the original start at 0xC000.
    -> (bytes, problems); problems lists any byte outside the header, bank 5's screen and bank 23."""
    prof = load_profile()['hooks']
    head, tail = bytes.fromhex(prof['ldhead']), bytes.fromhex(prof['ldtail'])
    orig = nex[512:512 + 6912]
    bank = head + bytes(0x200 - len(head)) + orig + bytes(0x3FD0 - 0x200 - 6912) + tail
    h = bytearray(nex[:512])
    bad = []
    if not (h[18 + LOAD_BANK] == 0 and h[139] == 10 and h[18 + 22] == 1 and
            all(h[18 + k] == 0 for k in range(LOAD_BANK + 1, 112))):
        bad.append('header: bank 23 used, entry bank not 10 or banks above 22')
    h[9] += 1
    h[18 + LOAD_BANK] = 1
    h[139] = LOAD_BANK
    n = bytes(h) + scr + nex[512 + 6912:] + bank
    diff = [i for i in range(512) if nex[i] != n[i]]
    if diff != [9, 18 + LOAD_BANK, 139]:
        bad.append('header bytes changed: %s' % diff)
    if n[512 + 6912:len(nex)] != nex[512 + 6912:] or n[len(nex) + 0x200:len(nex) + 0x200 + 6912] != orig:
        bad.append('rest of the file or the stub\'s copy of the screen differs')
    return n, bad


def _unit_sample(ctx):
    found = find_descs(lambda a: ctx[0].memory[a])
    return [(a, 0x44) for a in (0xD0C4, 0xD124, 0xF3C0, 0xF42C)]


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda f: hashlib.md5(open(f, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : rambo (display-list objects of type >= 0x40 -> sprites)')
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else str(bad[:3])[:200]))
    spr = os.path.join(out, name + '_sprites.nex')
    patch, conv = build(z80, spr)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else str(bad2[:3])[:200]))
    enh = os.path.join(out, name + '_enhanced.nex')
    t3, conv = build_enhanced(z80, enh)
    bad3 = check(enh, z80, t3, (conv[1], conv[1] + len(conv[2])))
    say('Enhanced  : %s  %s  boot %s' % (os.path.basename(enh), md5(enh), 'OK' if not bad3 else str(bad3[:3])[:200]))
    ok = not bad and not bad2 and not bad3
    scr = loading_screen(z80, name)
    if scr is None:
        say('Loading   : no %s beside the snapshot: sprite and Enhanced builds without the loading screen' % LOAD_SCREEN)
    else:
        say('Loading   : screen md5 %s' % hashlib.md5(scr).hexdigest())
        for f in (spr, enh):
            n, lb = loading_nex(open(f, 'rb').read(), scr)
            open(f, 'wb').write(n)
            ok = ok and not lb
            say('            %s  %s  bank %d stub, %s' % (os.path.basename(f), md5(f), LOAD_BANK,
                                                         'the rest as built' if not lb else 'PROBLEM %s' % lb))
    ctx = None
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=1)
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails and c['blits'] > 0
        say('Verify    : %s  %d frames, %d blits, figures %d, fallback %d, painter %d, hides %d, sprites shown %d -> %s' % (
            os.path.basename(r), c['frames'], c['blits'], c['figure'], c['fallback'], c['painter'], c['hides'],
            c['sprites shown'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        if st:
            from . import rzx as RZ
            ctx = (RZ.read_segments(r)[0][0], st[-1][0], st[-1][1])
        c, ex = verify(t3, r, stop=getattr(a, 'quick', None))      # the Enhanced set: the same checks
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails and c['blits'] > 0
        say('Verify    : %s Enhanced  %d frames, %d blits, figures %d, fallback %d, hides %d -> %s' % (
            os.path.basename(r), c['frames'], c['blits'], c['figure'], c['fallback'], c['hides'],
            'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if ctx:
        u = unit_tests(patch, ctx)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d cases, figures %d, fallback %d -> %s' % (u['cases'], u['figure'], u['fallback'],
                                                                      'PASS' if not uf else 'FAIL %s' % uf))
        r0 = list(a.rzx or [])[0]
        n = d = 0
        for nm, ed in negative_patches().items():
            t = RamboPatch(edit=ed)
            t.apply(zt.Z80Snapshot(z80))
            c, ex = verify(t, r0, stop=min(getattr(a, 'quick', None) or 2500, 2500))
            fl = {k: v for k, v in c.items() if k.endswith('!')}
            how = 'replay, 2500 frames'
            if not fl:
                c, ex = verify(t, r0)
                fl = {k: v for k, v in c.items() if k.endswith('!')}
                how = 'replay, whole recording'
            if not fl:
                uu = unit_tests(t, ctx, cases=_unit_sample(ctx))
                fl = {k: v for k, v in uu.items() if k.endswith('!')}
                how = 'unit cases only, NOT the replay'
            n += 1
            d += bool(fl)
            say('Negative  : %-26s %s' % (nm, 'DETECTED by %s %s' % (how, str(sorted(fl))[:70]) if fl else 'NOT DETECTED!'))
        ok = ok and d == n
        say('Negatives : %d/%d detected' % (d, n))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Colours (docs/COLOURS.md): tiles live in banks the game never reads
# ---------------------------------------------------------------------------------------------

RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/rambo_colours.json', 'clear': False,
            'note': 'Rambo: keys G<address> = one graphics byte as stored in the snapshot, nibble 1-14 a sheet swatch (5 is not ink), '
                    '0 = the rule\'s colour; 1-8 fixed; 9-14 the classes, own colour by default, skin, band, clothes '
                    'etc. in the Enhanced set, 3 shading the same way; 15 the figure\'s own colour'}
SWATCH = PAINTS + [SKIN, 0xE0, 0x4C, 0x44, DUST, 0xD5]


def rgb16():
    from . import coloursheet as cs
    return cs.palette_rgb(SWATCH + [0x92])          # the last swatch: grey, "the figure's own colour"


def colour_identity(peek):
    descs = find_descs(peek)
    h = hashlib.md5()
    for a in sorted(descs):
        p0, ht, w = descs[a]
        h.update(bytes(peek(p0 + k) for k in range(ht * w)))
    return {'schema': 1, 'game': RECORD, 'engine': 'rambo', 'keys': 'G-address-v1', 'inputs': h.hexdigest(),
            'geometry': hashlib.md5(json.dumps({str(a): descs[a] for a in sorted(descs)}).encode()).hexdigest()}


def recolour(nex_bytes, cmap):
    from .recolour import banks, nex_peek
    from . import recolour as rc
    b = banks(nex_bytes)
    prof = load_profile()
    peek = nex_peek(nex_bytes)
    for a, old in SITES_ORIG.items():
        want = bytes([SITE_OP.get(a, 0xC3)]) + int(prof['hooks']['syms'][SITE_SYM[a]], 16).to_bytes(2, 'little')
        if bytes(peek(a + k) for k in range(3)) != want:
            raise ValueError('not this engine\'s build: patch site 0x%04X' % a)
    sig = bytes.fromhex(prof['signature']['bytes'])
    if bytes(peek(prof['signature']['addr'] + k) for k in range(len(sig))) != sig:
        raise ValueError('not this game')
    d, l, images = build_images(peek, cmap)
    h = b[H_BANK]
    dir_at = int(prof['hooks']['syms']['DIR'], 16) - PAGE_ORG
    if bytes(h[dir_at:dir_at + len(d)]) != d:
        raise ValueError('tile directory differs: not this build')
    out, changed = rc.splice(nex_bytes, images)
    return out, {'banks changed': changed, 'map entries': len(cmap)}


def parts_for(peek, ty, a):
    """One figure's sheet part, upright as shown."""
    p0, h, w = find_descs(peek)[a]
    col = peek(ATTRS + ty)
    col = (col & 7) | (col & 0x40) >> 3
    col = (col & 7) or 8                # the swatch nearest the game's colour
    pixels, entries = [], {}
    for r in range(h):
        for c in range(w):
            ad = p0 + r * w + c
            b = peek(ad)
            key = 'G%04X' % ad
            entries[key] = [b, 'g']
            for k in range(8):
                if b & 0x80 >> k:
                    pixels.append((c * 8 + k, h - 1 - r, key, k, 1, col))
    return dict(id='%02X:%04X' % (ty, a), size=h, w=w * 8, h=h, x=0, y=0, mir=0, group='%02X' % ty, pixels=pixels,
                entries=entries)


def sheets(seen, peek, prefix, colours=None):
    from . import coloursheet as cs
    coll = cs.Collector()
    for ty, a in sorted(seen):
        coll.add_frame([parts_for(peek, ty, a)])
    comps = list(coll.comps.values())
    ident = colour_identity(peek)
    chosen = cs.choose(comps, coll.maxsize)
    cs.write(chosen, prefix + '_PAINTING_SPRITES.png', prefix + '_PAINTING_SPRITES_layout.json', rgb16(),
             colours=colours, unique=False, identity=ident)
    cs.write(comps, prefix + '_REFERENCE_ALL_SPRITES.png', prefix + '_REFERENCE_ALL_SPRITES_layout.json', rgb16(),
             colours=colours, unique=False, identity=ident)
    return len(chosen), len(comps)
