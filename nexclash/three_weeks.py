"""Three Weeks in Paradise (Mikro-Gen 1986, 128K release) engine 'three_weeks'. Additive module.

The game composes in a back buffer 0x5B00-0x6AFF with save-under, in DI, never in ROM. Hooks (asm/three_weeks_hooks.asm)
log each plot; the blit restores the save-under list first (0xB7D7 later writes the same bytes again) and takes the
attributes from the clean copy, so nothing differs from the original but the screen. Every figure has a fixed colour
by its graphics (FIGS), never the cell it stands in. Banks at 0xC000: figures 0, Wally 3. Facts: games/three_weeks.md.
"""
import collections
import hashlib
import json
import os

RECORD = 'three_weeks'
ROM_ORG = 0x386E
ALT_PAGE = 24
HPG = 26
GP3 = 11
STORE = 28
NSTORE = 40
TAIL_ADDR = 0x6000               # back buffer, write-first (scan)
SCREEN = (0x4000, 0x5B00)
BUFFER = (0x5B00, 0x6B00)
P_OR16, P_M24, P_WAL, P_OR24, P_M16 = 0xB82C, 0xB8B4, 0xB8C2, 0xB9B0, 0xBA5F
P_UND, P_BL, P_WP, P_AW, P_CLS, P_FX, P_AT = 0xB7D7, 0xA8ED, 0xA89C, 0xA9B8, 0x6F09, 0xA3F1, 0xA905
P_FON, P_FOF, P_TILE = 0xA1E9, 0xA204, 0xB78E
CLEAN, PAINT = 0x7400, 0x7600
L2PG = 68
L2BANKS = (34, 35, 36)
SHD = 0x1400
FCL = 0x1800
V_FCP = 0x37
INK = 0x130
PLOTS = (P_OR16, P_M24, P_WAL, P_OR24, P_M16)
SITES_ORIG = {P_OR16: 'fde5d9', P_M24: 'fde5d9', P_WAL: 'fde5d9', P_OR24: 'fde5d9', P_M16: 'fde5d9',
              P_UND: '3ad26c', P_BL: 'ed7303', P_WP: '3ad86c', P_AW: 'c3d7b7', P_CLS: 'afd3fe', P_FX: '210076', P_AT: '210076',
              P_FON: '2187b7', P_FOF: '21df71', P_TILE: 'f5e5c5'}
SITE_SYM = {P_OR16: 'e_or16', P_M24: 'e_m24', P_WAL: 'e_wal', P_OR24: 'e_or24', P_M16: 'e_m16', P_UND: 'e_und',
            P_BL: 'e_bl', P_WP: 'e_wp', P_AW: 'e_aw', P_CLS: 'e_cls', P_FX: 'e_fx', P_AT: 'e_at', P_FON: 'e_fon', P_FOF: 'e_fof', P_TILE: 'e_tile'}
BACK = {P_OR16: 0xB82F, P_M24: 0xB8B7, P_WAL: 0xB8C5, P_OR24: 0xB9B3, P_M16: 0xBA62, P_UND: 0xB7DA, P_WP: 0xA89F,
        P_AW: 0xB7D7, P_CLS: 0x6F0C, P_FX: 0xA3F4, P_FON: 0xA1EC, P_FOF: 0xA207, P_TILE: 0xB791}
INTERIOR = {a + k: a for a in SITES_ORIG for k in (1, 2)}
INTERIOR[0xA8F0] = P_BL
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
CBLACK = 8
CMP = list(range(0, 15)) + list(range(16, 25)) + [26, 27, 28]
ROOM, ROOMAT, WX, WY, WFR, BX, BY, SX, SY, SY2, BASE = 27864, 42298, 27830, 27831, 27841, 27839, 27840, 27906, 27907, 27908, 47723
SINK, NATDX, NAT0 = 27887, 35669, 254
WCOL, WCOL2, UCNT, UPTR, ITEMRET, ITEMT, WALLY, ORIENT = 27866, 27876, 27858, 35663, 0xBB53, 32832, 0xC006, 35634
V_MIR, V_ORI0, V_FX_ = 0x140, 0x141, 4
MINOUT = 24
PAL_AT, INKT_AT = 0x1C00, 0x1D00
# figure colours by graphics range: lo, hi, ink nibble (0 = the room's), palette line << 4. Defaults, a human would choose
def _figs_default():
    try:
        return [tuple(x) for x in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'profiles', 'three_weeks_figs.json')))]
    except FileNotFoundError:
        return [(0xC006, 0xCD86, 14, 0)]


FIGS = _figs_default()
# go-behind scenery: {room: [item, ...]}, item = [[col, row, rows], ...]: whole scenery items of the game's own room list
# (each call of the object drawer 0x6F29 from 0xA9A3; objects of one number whose cells touch are one item), drawn on
# Layer 2 over the sprites, scenery pixels only. Chosen by eye (work/gb/choose2.py); an item is in front whole or not at all.
GBT_AT, GBL_AT, NGBR, V_GBD, GBCAP = 0x1A00, 0x1140, 37, 0x3D, 16      # pointers, lists (to SHD)
P_OBJ, P_OBJEND = 0xA9A3, 0xA9A9
# the owner's one exception to the visibility rule (2026-11-03): the right-edge palm trunk of these rooms, columns 30-31,
# in front although at x 228-230, his last two steps before the room changes, it leaves 35.6 % of his body showing. Only there: the
# check still fails any other item, and these palms anywhere else. {room: (x from, first column of the palm)}
EDGE_EXCEPTION = {1: (228, 30), 3: (228, 30), 7: (228, 30), 14: (228, 30), 15: (228, 30)}


def _gb_default():
    try:
        return {int(k): [[tuple(x) + (0,) * (4 - len(x)) for x in it] for it in v] for k, v in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'profiles', 'three_weeks_gb.json'))).items()}
    except FileNotFoundError:
        return {}


GB = _gb_default()


def gb_items(gb, room):
    """[[cells of item 1 in table order], ...]"""
    return [[(c, r + i) for c, r, n, *_ in it for i in range(n)] for it in gb.get(room, ())]


def gb_solid(gb, room):
    """cells drawn solid: the item's colour is the cell's paper as well (a red trunk is red paper, black dots)"""
    return {(c, r + i) for it in gb.get(room, ()) for c, r, n, *s_ in it if s_ and s_[0] for i in range(n)}


def gb_cells(gb, room):
    return {q for it in gb_items(gb, room) for q in it}


def scenery_items(own, ids):
    """own: {cell: object key}, ids: {object key: object number} -> [set of cells]: objects of one number whose cells
    touch (4-neighbour) are one item, as a palm trunk drawn in stacked segments."""
    cells = {}
    for q, k in own.items():
        cells.setdefault(k, set()).add(q)
    keys = sorted(cells, key=str)
    par = {k: k for k in keys}

    def f(a):
        while par[a] != a:
            a = par[a]
        return a
    for a in keys:
        for b in keys:
            if str(a) < str(b) and ids.get(a) == ids.get(b) and any((c + dc, r + dr) in cells[b] for c, r in cells[a] for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                par[f(b)] = f(a)
    g = {}
    for k in keys:
        g.setdefault(f(k), set()).update(cells[k])
    return list(g.values())


V_N, V_PREV, V_FX, V_COL, V_DROP = 0, 1, 4, 5, 9
CACHE, NSM, NLG, ESZ = 0x1000, 14, 12, 12
FLEN = (32, 64, 96, 192)
SHAPE = {0: (2, 2, 16), 1: (2, 4, 16), 2: (3, 3, 32), 3: (3, 6, 32)}    # K: columns, bytes per row, rows
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'three_weeks_colours.json')
NOTE = ('Three Weeks in Paradise figure colours: key = address of a graphics byte (8 pixels) -> [the byte (check), '
        'kind 1, 8 nibbles (0 = default colour) (, transparent mask)]')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'three_weeks.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_three_weeks(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine == '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    a = int(sg['addr'], 16)
    return bytes(snap.memory[a + k] for k in range(len(sig))) == sig


def save_colours(ent, path=COLOURS):
    from . import coloursheet as cs
    cs.save(ent, path, NOTE)


def load_colours(path=COLOURS):
    from . import coloursheet as cs
    return cs.load(path)


def load_colours_build():
    from . import recolour as rc
    p = rc.build_colours_path(COLOURS)
    return load_colours(p) if p and os.path.exists(p) else {}


def store_pages(colours):
    """Colour map -> NSTORE pages: 8 bytes per address 0x6000-0xFFFF: [1, check, 4 nibble bytes, clear mask, 0]."""
    st = bytearray(NSTORE * 8192)
    for k, e in (colours or {}).items():
        a = int(k, 16)
        if not 0x6000 <= a <= 0xFFFF:
            continue
        i = a - 0x6000
        nib = e[2]
        st[8 * i:8 * i + 8] = bytes([1, e[0] & 255] + [nib[2 * n] << 4 | nib[2 * n + 1] for n in range(4)] +
                                    [e[3] if len(e) > 3 else 0, 0])
    return bytes(st)


def hook_page(code, colours=None, figs=None, pal=None, ori0=1, gb=None):
    p = bytearray(8192)
    p[0x200:0x200 + len(code)] = code
    if 0x200 + len(code) > CACHE:
        raise ValueError('hook code reaches the cache')
    p[V_COL] = 1 if colours else 0
    p[V_FCP] = FCL & 255
    p[V_FCP + 1] = FCL >> 8
    p[INK:INK + 16] = bytes(PALETTE)
    p[V_ORI0] = ori0
    p[0x145] = NAT0
    for i in range(NSM + NLG):
        e = CACHE + i * ESZ
        p[e] = 0xFF
        p[e + 10] = i * 4 if i < NSM else NSM * 4 + (i - NSM) * 6
    tab = pal if pal is not None else bytes(PALETTE) * 16
    if len(tab) != 256:
        raise ValueError('palette table is 16 x 16')
    p[PAL_AT:PAL_AT + 256] = tab
    o = INKT_AT
    for lo, hi, ink, line in (figs if figs is not None else FIGS):
        p[o:o + 6] = bytes([lo & 255, lo >> 8, hi & 255, hi >> 8, ink, line])
        o += 6
    if o > 0x1E80:
        raise ValueError('figure table too long')
    gb = GB if gb is None else gb
    o = GBL_AT
    for room in sorted(gb):
        if not gb[room]:
            continue
        p[GBT_AT + 2 * room:GBT_AT + 2 * room + 2] = o.to_bytes(2, 'little')
        for it in gb[room]:
            for c, r, n, *s_ in it:
                p[o:o + 3] = bytes([c | (0x80 if s_ and s_[0] else 0), r, n])
                o += 3
            p[o] = 0xFE
            o += 1
        p[o] = 0xFF
        o += 1
    if o > SHD:
        raise ValueError('go-behind table too long')
    return bytes(p)


class ThreeWeeksPatch:
    name = 'Three Weeks in Paradise figures -> hardware sprites (alt ROM stubs, page 26 at slot 0, blit without figures)'

    def __init__(self, prof=None, colours=None, code=None, rom_code=None, extra_sites=(), figs=None, pal=None, ori0=1, gb=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.code = code if code is not None else bytes.fromhex(h['hook'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.figs = figs if figs is not None else FIGS
        self.ori0 = ori0
        self.gb = GB if gb is None else gb
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.colours = dict(colours) if colours is not None else load_colours_build()
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM stubs too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM stub range is not free ($FF) in the 48K ROM')
        pg = bytearray(rom[0x2000:0x4000])
        pg[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(pg)
        self.hpage = bytearray(hook_page(self.code, self.colours, self.figs, pal, ori0, self.gb))
        self.pal = pal
        self.store = store_pages(self.colours)
        self.sites = [(a, bytes.fromhex(old), b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]
        self.sites += list(extra_sites)
        self.pats = None
        self.num_patterns = 128
        self._banks()

    def _banks(self):
        self.extra_banks = {12: bytes(self.page) + bytes(8192), 13: bytes(self.hpage) + bytes(8192)}
        for n in range(NSTORE // 2):
            self.extra_banks[14 + n] = self.store[16384 * n:16384 * (n + 1)]
        for b in L2BANKS:
            self.extra_banks[b] = bytes([0xE3]) * 16384

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('expects the 128K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2])
        for a, old, new in self.sites:
            if bytes(ram[a - 0x4000:a - 0x4000 + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X' % a)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        self._banks()

    def alt_view(self, rom_get):
        lo, hi = self.altrom
        pg = self.page
        return lambda a: pg[a - 0x2000] if lo <= a < hi else rom_get(a)


# ---------------------------------------------------------------------------------------------
# The plot model: independent of the hook code
# ---------------------------------------------------------------------------------------------

def nib(a):
    k = a & 7
    if not k:
        return CBLACK
    return k + 8 if a & 0x40 else k


def fig_entry(g, figs, wally=False):
    if wally:
        return figs[0][2], figs[0][3]
    for lo, hi, ink, line in figs[1:]:
        if lo <= g < hi:
            return ink, line
    return 0, 0


def plot_params(get, R, pc, figs=None):
    """-> dict(K, g, x, y, ink[4], item, wally, line) at a plotter's entry, or None (off the buffer)."""
    figs = FIGS if figs is None else figs
    a = R[0]
    w = lambda p: get(p) | get((p + 1) & 0xFFFF) << 8
    room = nib(get(ROOMAT + get(ROOM)))
    item = False
    if pc == P_OR16:
        K, g, x, y = 0, (w(BASE) + a * 32) & 0xFFFF, get(SX), get(SY)
        if get(SY2):
            return None
    elif pc == P_M16:
        K, g, x, y = 1, (w(BASE) + a * 64) & 0xFFFF, get(SX), get(SY)
        if w(R[12]) == ITEMRET:
            item = True
    elif pc == P_OR24:
        K, g, x, y = 2, (w(BASE) + a * 96) & 0xFFFF, get(BX), get(BY)
    elif pc == P_M24:
        K, g, x, y = 3, (w(BASE) + a * 192) & 0xFFFF, get(BX), get(BY)
    else:
        K, g, x, y = 3, (WALLY + get(WFR) * 192) & 0xFFFF, get(WX), get(WY)
    fi, line = fig_entry(g, figs, pc == P_WAL)
    ink = [fi or room] * 4
    if pc == P_WAL and get(WCOL):
        ink = [room] * 4
    if item:
        for i in range(4):
            v = get(ITEMT + a * 4 + i)
            if v != 255:
                ink[i] = nib(v)
    return dict(K=K, g=g, x=x, y=y, ink=ink, item=item, pc=pc, ret=w(R[12]), wally=pc == P_WAL, line=line)


def figure_masks(rd, K, g, inks0):
    """Independent of the hook code. Box coordinates, a margin of one pixel on all four sides: per box row a 32-bit int
    (bit 31 = box column 0, which is graphic column -1): opaque, fill, ring; the ring's nibble."""
    cols, S, rows = SHAPE[K]
    masked = K & 1
    vis = [0]
    n = 0
    for r in range(rows):
        row = g + r * S
        v = 0
        for c in range(cols):
            if masked:
                b = (~rd((row + c) & 0xFFFF) | rd((row + cols + c) & 0xFFFF)) & 0xFF
            else:
                b = rd((row + c) & 0xFFFF)
            n += bin(b).count('1')
            v |= b << (24 - 8 * c)
        vis.append(v >> 1)
    vis.append(0)
    empty = [0] * (rows + 2)
    if min(n, 255) < MINOUT:
        return vis, empty, empty, 0
    fill = []
    M = 0xFFFFFFFF
    for r in range(rows + 2):
        above = 0
        for k in range(r):
            above |= vis[k]
        below = 0
        for k in range(r + 1, rows + 2):
            below |= vis[k]
        v = vis[r]
        left = right = 0
        for i in range(32):
            bit = 1 << (31 - i)
            if v >> (32 - i) if i else 0:           # an opaque pixel left of i
                left |= bit
            if v & (bit - 1):                       # an opaque pixel right of i
                right |= bit
        fill.append(above & below & left & right & ~v & M)
    all_ = [a | b for a, b in zip(vis, fill)]
    ring = []
    for r in range(rows + 2):
        v = all_[r]
        x = ((v >> 1) | (v << 1)) & M
        if r:
            x |= all_[r - 1]
        if r < rows + 1:
            x |= all_[r + 1]
        ring.append(x & ~v & M)
    oc = CBLACK if (inks0 & 7) == 7 else 15
    return all_, fill, ring, oc


def set_nb(plots):
    """Parts of one figure (h_nb): 16 x 16 plots of one kind whose frames follow one another (graphics 32 or 64
    apart) and that abut exactly: 'nb' = 1 a part to the right, 2 left, 4 below, 8 above. No outline where they meet."""
    for p in plots:
        p['nb'] = 0
        if p['K'] >= 2:
            continue
        fl = 32 if p['K'] == 0 else 64
        for q in plots:
            if q is p or q['K'] != p['K'] or abs(q['g'] - p['g']) != fl:
                continue
            dx, dy = (q['x'] - p['x']) & 255, (q['y'] - p['y']) & 255
            if dy == 0:
                p['nb'] |= {16: 1, 240: 2}.get(dx, 0)
            elif dx == 0:
                p['nb'] |= {16: 4, 240: 8}.get(dy, 0)


def _parts(p, q):
    """two plots that are parts of one figure (set_nb's rule)"""
    if p['K'] != q['K'] or p['K'] >= 2 or abs(q['g'] - p['g']) != (32 if p['K'] == 0 else 64):
        return False
    dx, dy = (q['x'] - p['x']) & 255, (q['y'] - p['y']) & 255
    return (dy == 0 and dx in (16, 240)) or (dx == 0 and dy in (16, 240))


def plot_pixels(get, p, colours=None, banks=None, ori0=None):
    """Yield (x, y, nibble, code) over the box: code 1 ink, 2 the game's black mask pixel, 0 otherwise: a painted
    transparent, or the added fill and outline, which the game's buffer does not have."""
    K, g = p['K'], p['g']
    bank = 3 if p.get('wally') else 0

    def rd(a):
        return banks[bank][a - 0xC000] if banks is not None and a >= 0xC000 else get(a)
    cols, S, rows = SHAPE[K]
    masked = K & 1
    _, fill, ring, oc = figure_masks(rd, K, g, p['ink'][0])
    mirror = ori0 is not None and (get(ORIENT) != ori0 if p.get('wally') else
                                   K == 3 and 0xD680 <= g < 0xD800 and (get(NATDX) ^ NAT0) & 0x80)
    if p.get('wally') and get(SINK):
        colours = None                                # no map fits while frame 0 is shifted: whole in his ink
    width = cols * 8
    nb = p.get('nb', 0)
    off = 0x6000 if p.get('wally') else 0             # Wally's keys, bank 3: address - 0x6000
    for r in range(-1, rows + 1):
        row = g + r * S
        for c in range(-1, cols + 1):
            e = None
            if 0 <= r < rows and 0 <= c < cols:
                ga = (row + (cols if masked else 0) + c) & 0xFFFF
                gb = rd(ga)
                mb = rd(row + c) if masked else 0xFF
                if colours:
                    if mirror:
                        e = colours.get('%04X' % (ga + 2 - 2 * c - off))
                        if e is not None:
                            if (e[0] & 255) != int('{:08b}'.format(gb)[::-1], 2):
                                e = None
                            else:
                                cl = int('{:08b}'.format(e[3])[::-1], 2) if len(e) > 3 else 0
                                e = [gb, 1, list(e[2][::-1]), cl]
                    else:
                        e = colours.get('%04X' % (ga - off))
                        if e is not None and (e[0] & 255) != gb:
                            e = None
            else:
                gb, mb = 0, 0xFF
            q = (2 if r >= 8 else 0) + c if K < 2 and c >= 0 else 0
            for b in range(8):
                gx = c * 8 + b                        # graphic column; the margin is one pixel
                if not -1 <= gx <= width:
                    continue
                bit = 0x80 >> b
                ink = bool(gb & bit)
                out = not ink and not (mb & bit)
                code = 1 if ink else (2 if out else 0)
                n = p['ink'][q if q < 4 else 0] if ink else (CBLACK if out else 0)
                if not ink and not out:
                    sh = 30 - (gx)                    # box column gx + 1
                    if fill[r + 1] >> sh & 1:
                        n = CBLACK
                    elif ring[r + 1] >> sh & 1 and not (nb & 1 and gx == width or nb & 2 and gx == -1 or
                                                        nb & 4 and r == rows or nb & 8 and r == -1):
                        n = oc
                if e is not None:
                    pn = e[2][b]
                    if pn:
                        n = pn
                    elif len(e) > 3 and e[3] & bit:
                        n = 0
                yield p['x'] + gx, p['y'] + r, n, code


def expected_layer(get, plots, colours=None, banks=None, ori0=None):
    """Sprite layer {(x, y): palette line + nibble} and {(x, y): code} of the plots in plot order (later on top). A
    transparent pixel with no code leaves what is under it."""
    lay, code = {}, {}
    if any('nb' not in p for p in plots):
        set_nb(plots)
    own = {}                                          # pixel -> the plot whose own graphic pixel is there
    expected_layer.cuts = 0
    for p in sorted(plots, key=lambda q: not q.get('item')):     # items (collectables) first: under every figure
        if p['y'] >= 128:
            continue
        for x, y, n, k in plot_pixels(get, p, colours, banks, ori0):
            if 0 <= x < 256 and 0 <= y < 128:
                if k:
                    own[(x, y)] = p
                elif n and (x, y) in own and own[(x, y)] is not p and p.get('nb') and _parts(own[(x, y)], p):
                    expected_layer.cuts += 1         # a part's outline or fill over the other part of the same figure
                if n:
                    lay[(x, y)] = n | p.get('line', 0)
                elif k:                      # painted transparent: shows what is under it
                    lay.pop((x, y), None)
                if k:
                    code[(x, y)] = k
    return lay, code


# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------

ENHANCED = os.path.join(_HERE, '..', 'docs', 'profiles', 'three_weeks_enhanced.json')


def enhanced_patch():
    """The Enhanced colour set (menu set, off by default): docs/profiles/three_weeks_enhanced.json (work/paint128.py)."""
    e = json.load(open(ENHANCED))
    return ThreeWeeksPatch(colours=e['map'], figs=[tuple(x) for x in e['figs']], pal=bytes(e['pal']), ori0=e['ori0'])


def boot_check(nex, z80, patch=None, tail=None):
    """nextboot.check with two facts of this build the shared check does not model, kept here so no other game's
    check changes (imported 2026-11-04; the clone changed nextboot itself): the set-up's hold of the loading
    picture waits on the raster line (NR 0x1F, a counter that steps per read), and a 128K game's paging stays
    unlocked as the snapshot has it (7FFD bits 4-5 as saved, 1FFD bit 2)."""
    from . import nextboot as nb
    from . import z80tonex as zt
    base = nb._rw_simulator()

    class Sim(base):
        def set_tracer(self, tr, *a, **k):
            class Raster:
                sel, line = 0, -1

                def read_port(s, regs, port):
                    if port == 0x253B and s.sel == 0x1F:
                        s.line = (s.line + 1) % 312
                        return min(s.line, 255)
                    return tr.read_port(regs, port)

                def write_port(s, regs, port, value, *x):
                    if port == 0x243B:
                        s.sel = value
                    return tr.write_port(regs, port, value, *x)
            return super().set_tracer(Raster(), *a, **k)
    old = nb._rw_simulator
    nb._rw_simulator = lambda: Sim
    try:
        bad = nb.check(nex, z80, patch, tail)
    finally:
        nb._rw_simulator = old
    s = zt.Z80Snapshot(z80)
    if s.is128:
        out = []
        for b in bad:
            if b[0] == 'paging':
                p7, p1 = int(b[1], 16), int(b[2], 16)
                if p7 & 0x30 == s.port7ffd & 0x30 and p1 & 4:
                    continue
            out.append(b)
        bad = out
    return bad


def build(z80, out, name, say=print):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = boot_check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300], TAIL_ADDR))
    patch = ThreeWeeksPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    say('Colours   : %s' % ('%d colour-map entries' % len(patch.colours) if patch.colours else "no colour map: figures' default colours"))
    epatch = enhanced_patch()
    enh = os.path.join(out, name + '_enhanced.nex')
    conv = zt.convert(z80, enh, None, True, quiet=True, patch=epatch)
    bad3 = boot_check(enh, z80, epatch, (conv[1], conv[1] + len(conv[2])))
    say('Enhanced  : %s  %s  boot %s  (%d colour-map entries)' % (os.path.basename(enh), md5(enh), 'OK' if not bad3 else 'MISMATCH %s' % str(bad3[:3])[:300], len(epatch.colours)))
    return (not bad and not bad2 and not bad3), (plain, spr), patch, epatch


# ---------------------------------------------------------------------------------------------
# Differential verification
# ---------------------------------------------------------------------------------------------

class _NS:
    def __init__(self, patch):
        self.nr = {0x07: 0, 0x50: 0xFF, 0x53: GP3, 0x54: 4, 0x15: 5, 0x69: 0, 0x56: 0, 0x57: 1, 0x52: 10}
        self.X = bytearray(8192)         # the build's page, slot 2 while a pattern is made
        self.sel = 0
        self.cur = 0
        self.l2 = bytearray([0xE3]) * (6 * 8192)
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.H = bytearray(patch.hpage)
        self.R = None
        self.ports = 0
        self.fe = []

    def read(self, port):
        if port == 0x253B:
            if self.sel in (0x1E, 0x1F):          # the video line, for the blit's pace window: from T, 228 T a line
                v = (self.R[25] // 228) % 311 if self.R is not None else 0
                return (v >> 8) & 1 if self.sel == 0x1E else v & 255
            return self.nr.get(self.sel, 0)
        self.ports += 1
        return 0xFF

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x243B:
            self.sel = val
        elif port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
        elif port & 0xFF == 0xFE:
            self.fe.append(val)
        else:
            self.ports += 1

    def sprite_layer(self):
        out = {}
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            ln = a2 & 0xF0
            if not a3 & 0x80:
                continue
            x0 = a0 + (a2 & 1) * 256 - 32
            y0 = a1 + (a4 & 1) * 256 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    c = (b >> 4) if k % 2 == 0 else (b & 15)
                    x, y = x0 + k, y0 + j
                    if c and 0 <= x <= 255 and 0 <= y <= 127:
                        out[(x, y)] = c | ln
        return out


class _OrigView:
    def __init__(self, get):
        self.get, self.ov = get, {}

    def __getitem__(self, a):
        v = self.ov.get(a)
        return v if v is not None else self.get(a)

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.ov[a] = v

    def __len__(self):
        return 65536


class _PatchedView(_OrigView):
    """The patched machine: alt ROM, patch sites, slot 0 = H when mapped, slot 3 = the colour store when mapped."""

    def __init__(self, get, ns, alt, psite, store, err, banks=None):
        super().__init__(get)
        self.ns, self.alt, self.psite, self.store, self.err, self.banks = ns, alt, psite, store, err, banks

    def __getitem__(self, a):
        if a < 0x4000:
            if a < 0x2000 and self.ns.nr[0x50] == HPG:
                return self.ns.H[a]
            return self.alt(a)
        if a < 0x6000 and self.ns.nr[0x52] != 10:
            return self.ns.X[a - 0x4000]
        if 0x8000 <= a < 0xA000 and self.ns.nr[0x54] != 4:
            return self.ns.l2[(self.ns.nr[0x54] - L2PG) * 8192 + a - 0x8000]
        if 0x6000 <= a < 0x8000 and self.ns.nr[0x53] != GP3:
            pg = self.ns.nr[0x53] - STORE
            if 0 <= pg < NSTORE:
                return self.store[pg * 8192 + a - 0x6000]
            self.err.append(('slot 3: page', self.ns.nr[0x53]))
            return 0
        if a >= 0xC000:
            pg = self.ns.nr[0x56 if a < 0xE000 else 0x57]
            if pg != self.ns.cur * 2 + (a >= 0xE000):
                if a >= 0xE000:
                    pg -= 1
                return self.banks[pg >> 1][a - 0xC000]
        v = self.ov.get(a)
        if v is not None:
            return v
        v = self.psite.get(a)
        if v is not None:
            return v
        return self.get(a)

    def __setitem__(self, a, v):
        nr = self.ns.nr
        if a < 0x2000 and nr[0x50] == HPG:
            self.ns.H[a] = v
            return
        if a < 0x4000:
            self.err.append(('ROM write', a))
            return
        if a < 0x6000 and nr[0x52] != 10:
            self.ns.X[a - 0x4000] = v
            return
        if 0x8000 <= a < 0xA000 and nr[0x54] != 4:
            pg = nr[0x54] - L2PG
            if 0 <= pg < 6:
                self.ns.l2[pg * 8192 + a - 0x8000] = v
            else:
                self.err.append(('slot 4: page', nr[0x54]))
            return
        if 0x6000 <= a < 0x8000 and nr[0x53] != GP3:
            self.err.append(('write to the colour store', a))
            return
        self.ov[a] = v


def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def _machine(Sim, mem, regs, ns, slot=None):
    from .rainbow import _machine as m
    return m(Sim, mem, regs, ns, slot)


def _run_until(sim, stop, limit=6000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


class _Dummy:
    hpage = bytes(8192)


def _replay(rzx_path, stop, S, next_frame):
    import skoolkit.rzxplay as rzxplay
    from . import rzx as RZ
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix='.rzx')
    os.close(fd)
    RZ.strip(rzx_path, tmp)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    nf0 = old[0]
    rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = lambda self: (next_frame(), nf0(self))[1], S, None
    try:
        try:
            rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else []) + [tmp])
        except SystemExit:
            pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
        os.remove(tmp)


ULA_LOG = None


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """-> (Counter, examples, states). Replays the ORIGINAL game; at each patch site original and patched code run
    from the same state and are compared; each commit checks the sprite layer against an independent plot model, and
    ULA + sprites against the original's own buffer pixel by pixel."""
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    Sim = _sim_class()
    ori0 = patch.ori0
    c = collections.Counter()
    ex = collections.defaultdict(list)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    site_bytes = {a + k: old[k] for a, old, new in patch.sites for k in range(len(old))}
    ns = _NS(patch)
    st = {'frame': 0, 'prev': None, 'plots': [], 'clean': None, 'hookT': 0, 'gf': 0, 'fx': False, 'on': False,
          'front_on': False, 'fcells': set(), 'front': set(), 'gbn': 0, 'gbdone': False, 'gbdrawn': set(), 'gb': set(),
          'own': {}, 'gbsol': set(), 'objkey': None, 'objids': {}, 'built': None, 'splitdone': None, 'nobj': 0}
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    def pair(pc, get, R):
        regs = list(R)
        err = []
        cur = st['mem'].o7ffd & 7
        ns.cur = cur
        ns.nr[0x56], ns.nr[0x57] = cur * 2, cur * 2 + 1
        banks = st['mem'].banks
        sp0 = regs[12]
        if pc == P_BL:
            ret = get(sp0) | get((sp0 + 1) & 0xFFFF) << 8
            stop_ = lambda r: r[24] == ret and r[12] == (sp0 + 2) & 0xFFFF
        else:
            tgt = BACK[pc]
            stop_ = lambda r: r[24] == tgt
        o = _OrigView(get)
        so = _machine(Sim, o, list(regs), _NS(_Dummy), 'o')
        if not _run_until(so, stop_):
            fail('original did not return', (hex(pc),))
            return None
        p = _PatchedView(get, ns, patch.alt_view(get), psite, patch.store, err, banks)
        sp_ = _machine(Sim, p, list(regs), ns, 'p')
        t0 = sp_.registers[25]
        if not _run_until(sp_, stop_):
            fail('patched did not return', (hex(pc),))
            return None
        dt = (sp_.registers[25] - t0) - (so.registers[25] - regs[25])
        st['hookT'] += dt
        c['hook T at 0x%04X' % pc] += dt
        if pc == P_BL:
            st.setdefault('commitT', []).append((len(st['plots']), dt, so.registers[25] - regs[25]))
        for i in CMP:
            a, b = so.registers[i], sp_.registers[i]
            if i == 1 and pc == P_BL:              # bits 3 and 5 follow the last byte copied; game code overwrites them
                a, b = a & 0xD7, b & 0xD7
            if a != b:
                fail('registers differ', (hex(pc), i, a, b))
        excl_s = pc == P_BL
        excl_b = pc in (P_BL, P_WP)
        dm = []
        for a in set(o.ov) | set(p.ov):
            if a in psite:
                continue
            if excl_s and SCREEN[0] <= a < SCREEN[1]:
                continue
            if excl_b and BUFFER[0] <= a < BUFFER[1]:
                continue
            if excl_s and (sp0 - 2) & 0xFFFF <= a < sp0 + (65536 if sp0 < 2 else 0):   # dead stack: the original's CALL of the LDI chain
                continue
            if o.ov.get(a, get(a)) != p.ov.get(a, get(a)):
                dm.append(a)
        if dm:
            fail('memory differs', (hex(pc), len(dm), [hex(a) for a in sorted(dm)[:4]]))
        if not excl_s and any(SCREEN[0] <= a < SCREEN[1] for a in p.ov):
            fail('screen written by a hook', (hex(pc),))
        if (ns.nr[0x50], ns.nr[0x52], ns.nr[0x53], ns.nr[0x54], ns.nr[0x07], ns.nr[0x56], ns.nr[0x57]) != (0xFF, 10, GP3, 4, 0, cur * 2, cur * 2 + 1):
            fail('MMU / speed not restored', (hex(pc), ns.nr[0x50], ns.nr[0x52], ns.nr[0x53], ns.nr[0x54], ns.nr[0x07], ns.nr[0x56], ns.nr[0x57]))
            ns.nr.update({0x50: 0xFF, 0x52: 10, 0x53: GP3, 0x54: 4, 0x07: 0})
        if ns.ports:
            fail('port access in a hook', (hex(pc), ns.ports))
            ns.ports = 0
        for e in err:
            fail(str(e[0]), (hex(pc),) + tuple(e[1:]))
        if R[26] and pc not in (P_CLS,):
            fail('hook with interrupts on', (hex(pc),))
        c['pairs 0x%04X' % pc] += 1
        return so, o, sp_, p

    def commit_checks(get, p, plots):
        c['commits'] += 1
        st['gf'] += 1
        # the clean buffer the hook made; the original's buffer holds the figures
        pget = lambda a: p.ov.get(a, get(a))
        exp, code = expected_layer(get, plots, patch.colours, st['mem'].banks, ori0)
        lay = ns.sprite_layer()
        c['sprite pixels compared'] += len(exp)
        if expected_layer.cuts:
            fail('a figure cut by its other part\'s outline', (expected_layer.cuts,))
        # on the sprite layer itself: every ink pixel of a part shows in its colour unless a later figure's own pixel covers it
        order = sorted([q for q in plots if q['y'] < 128], key=lambda q: not q.get('item'))
        cut_ = 0
        for i, q in enumerate(order):
            if not q.get('nb'):
                continue
            later = set()                    # what later figures draw: all of another figure, only the own pixels of a part
            for q2 in order[i + 1:]:
                pt = _parts(q, q2)
                later |= {(x, y) for x, y, n, k in plot_pixels(get, q2, patch.colours, st['mem'].banks, ori0) if k or (n and not pt)}
            for x, y, n, k in plot_pixels(get, q, patch.colours, st['mem'].banks, ori0):
                if k == 1 and n and 0 <= x < 256 and 0 <= y < 128 and (x, y) not in later and lay.get((x, y)) != n | q.get('line', 0):
                    cut_ += 1
        if cut_:
            fail('a part of a figure not shown whole on the sprite layer', (cut_,))
        for q in plots:
            if q.get('nb') and q['y'] < 128:
                c['multi-part figure plots'] += 1
                st.setdefault('parts', collections.Counter())['%04X K%d nb%d' % (q['g'], q['K'], q['nb'])] += 1
        if lay != exp:
            d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
            fail('sprite layer differs from the plots', (len(d), sorted(d)[:3], [(lay.get(k), exp.get(k)) for k in sorted(d)[:3]], [(hex(q['pc']), q['x'], q['y'], hex(q['g'])) for q in plots], [(i, a) for i, a in enumerate(ns.attr) if a[3] & 0x80][:12]))
        wrapx = any(q['x'] + (24 if q['K'] >= 2 else 16) > 248 for q in plots)   # the buffer wraps past column 31
        front_check(get, pget)
        black_check(exp)
        front = st['front']
        bad = 0
        # collectables go under every figure (owner, 2026-11-03): where an item and another figure overlap the
        # original shows whichever was plotted last; these pixels are counted, not compared
        under = set()
        its_ = [q for q in plots if q.get('item') and q['y'] < 128]
        oth_ = [q for q in plots if not q.get('item') and q['y'] < 128]
        if its_ and oth_:
            a_ = expected_layer(get, its_, patch.colours, st['mem'].banks, ori0)
            b_ = expected_layer(get, oth_, patch.colours, st['mem'].banks, ori0)
            under = (set(a_[0]) | set(a_[1])) & (set(b_[0]) | set(b_[1]))
            c['item pixels kept under a figure'] += len(under)
        for y in range(128):
            base = 0x5B00 + y * 32
            for b in range(32):
                if (b, y >> 3) in front:        # Layer 2 shows the tile: front_check
                    continue
                ob = get(base + b)
                cb = pget(base + b)
                gbcell = (b, y >> 3) in st['gb']
                gbsol = gbcell and (b, y >> 3) in st['gbsol']
                for i in range(8):
                    if (b * 8 + i, y) in under:
                        continue
                    k = code.get((b * 8 + i, y))
                    bit = 0x80 >> i
                    want = (k == 1) if k else bool(cb & bit)
                    if gbcell and (cb & bit or gbsol):      # a go-behind scenery pixel: Layer 2 shows it over the figure
                        if k and not ob & bit:
                            c['go-behind pixels over figures'] += 1
                        continue
                    if bool(ob & bit) != want:
                        bad += 1
        gb_census(get, plots)
        if bad:
            if wrapx:
                c['margin wrap pixels (original only)'] += bad
            else:
                fail('ULA + sprites differ from the original buffer', (bad, [(q['pc'], q['x'], q['y']) for q in plots][:6]))
        # the ULA play area: pixels = clean buffer via the line map, attributes = clean copy (or 0xF900 with the effect)
        bad = 0
        src = PAINT if st['fx'] else CLEAN
        for row in range(16):
            for col in range(32):
                if pget(0x5800 + row * 32 + col) != get(src + row * 32 + col):
                    bad += 1
        for y in range(128):
            sa = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            for col in range(32):
                if pget(sa + col) != pget(0x5B00 + y * 32 + col):
                    bad += 1
        if bad:
            fail('ULA play area is not the scenery', (bad,))
        # by layer: what moves on the ULA? Cells of the clean buffer and clean attributes that change within a room
        rm = get(ROOM)
        snap_ = (rm, tuple(tuple(pget(0x5B00 + y_ * 32 + b_) for y_ in range(r_ * 8, r_ * 8 + 8)) + (get(CLEAN + r_ * 32 + b_),) for r_ in range(16) for b_ in range(32)))
        if st.get('ula') and st['ula'][0] == rm and not st.get('fresh'):
            ch = sum(1 for i_, v_ in enumerate(snap_[1]) if v_ != st['ula'][1][i_] and (i_ % 32, i_ // 32) not in front)
            if ch:
                c['ULA cells changed, room %d' % rm] += ch
                if ULA_LOG is not None:
                    ULA_LOG.append((st['frame'], rm, [(i_ % 32, i_ // 32) for i_, v_ in enumerate(snap_[1]) if v_ != st['ula'][1][i_] and (i_ % 32, i_ // 32) not in front]))
        st['ula'] = snap_
        st['fresh'] = False
        c['max sprites in a frame'] = max(c['max sprites in a frame'], sum(1 for a in ns.attr if a[3] & 0x80))
        c['max plots in a frame'] = max(c['max plots in a frame'], len(plots))
        if ns.H[V_DROP]:
            fail('figures dropped', (ns.H[V_DROP],))
            ns.H[V_DROP] = 0
        if ns.H[V_N]:
            fail('log not empty after the commit')

    def front_check(get, cget=None, regular=True):
        cget = cget or get              # the clean buffer (the hook's restore): the original's holds the figures
        if regular and not st['gbdone']:      # h_gb: whole items in table order, none started once GBCAP cells are drawn
            its = gb_items(getattr(patch, 'gb_spec', None) or GB, get(ROOM)) if get(ROOM) < NGBR else []
            k, drawn = st['gbn'], 0
            while k < len(its) and drawn < GBCAP:
                st['gbdrawn'] |= set(its[k])
                drawn += len(its[k])
                k += 1
            st['gbn'] = k
            st['gbdone'] = k >= len(its)
        front = st['front'] = {(c_, r_) for c_, r_ in st['fcells'] if c_ < 32 and r_ < 16}
        st['fcells'] = set()
        c['front cells checked'] += len(front)
        bad = 0
        gbc = st['gb'] = st['gbdrawn'] - front
        gpx = st['gbpix'] = set()
        sol = st['gbsol'] = gb_solid(getattr(patch, 'gb_spec', None) or GB, get(ROOM))
        for c_, r_ in gbc:
            at = get(CLEAN + r_ * 32 + c_)
            ink = PALETTE[(at & 7) + (8 if at & 0x40 else 0)] or 0xE3          # black is transparent: figures show through
            clr = (PALETTE[((at >> 3) & 7) + (8 if at & 0x40 else 0)] or 0xE3) if (c_, r_) in sol else 0xE3
            for l in range(8):
                y = r_ * 8 + l
                v = cget(0x5B00 + y * 32 + c_)
                for b in range(8):
                    on = v & (0x80 >> b)
                    if (ink if on else clr) != 0xE3:
                        gpx.add((c_ * 8 + b, y))
                    if ns.l2[y * 256 + c_ * 8 + b] != (ink if on else clr):
                        bad += 1
                        if len(ex['go-behind pixels wrong']) < 8:
                            ex['go-behind pixels wrong'].append((st['frame'], c_ * 8 + b, y, ns.l2[y * 256 + c_ * 8 + b], ink if on else 0xE3))
        c['go-behind cells checked'] += len(gbc)
        split_check(get, cget, front)
        if gbc:
            st.setdefault('gbrooms', collections.Counter())[get(ROOM)] += 1
        if bad:
            fail('Layer 2 differs from the go-behind cells', (bad, get(ROOM), sorted(gbc)[:6]))
        bad = 0
        for c_, r_ in front:
            at = get(CLEAN + r_ * 32 + c_)
            br = 8 if at & 0x40 else 0
            ink, pap = PALETTE[(at & 7) + br] or 0xE3, PALETTE[((at >> 3) & 7) + br] or 0xE3    # black: transparent
            for l in range(8):
                y = r_ * 8 + l
                v = get(0x5B00 + y * 32 + c_)
                for b in range(8):
                    if ns.l2[y * 256 + c_ * 8 + b] != (ink if v & (0x80 >> b) else pap):
                        bad += 1
        if bad:
            fail('Layer 2 differs from the front tiles', (bad, sorted(front)[:6]))
        if ns.nr[0x69] != 0x80:
            fail('Layer 2 not on at a commit')
        # nothing else on Layer 2
        for r_ in range(16):
            for c_ in range(32):
                if (c_, r_) not in front and (c_, r_) not in gbc and any(ns.l2[(r_ * 8 + l) * 256 + c_ * 8 + b] != 0xE3 for l in (0, 3, 7) for b in (0, 3, 7)):
                    if (c_, r_) not in st.setdefault('l2seen', set()):
                        st['l2seen'].add((c_, r_))
                        c['Layer 2 cells kept from an earlier frame'] += 1

    def black_check(exp):
        # owner, 2026-11-03: no figure pixel may sit under a black front pixel (Layer 2 over the sprites)
        n_ = 0
        for c_, r_ in st['front'] | st['gb']:
            for l in range(8):
                y = r_ * 8 + l
                for b in range(8):
                    x = c_ * 8 + b
                    if ns.l2[y * 256 + x] == 0x00 and (x, y) in exp:
                        n_ += 1
        c['figure pixels under the front layer checked for black'] += 1
        if n_:
            fail('a figure pixel under a black front pixel', (n_, st['frame']))

    def split_check(get, cget, front):
        # owner's rule: a scenery item is in front whole or not at all. Items from this replay's own room build
        rm = get(ROOM)
        if not st['gbdone'] or st['built'] != rm or st['splitdone'] == (rm, st['gbn']):
            return
        st['splitdone'] = (rm, st['gbn'])
        pap = collections.Counter((get(CLEAN + i_) >> 3) & 0x0F for i_ in range(15 * 32))
        bg = pap.most_common(1)[0][0]           # the room's background paper (with bright)
        ink = lambda q: any(cget(0x5B00 + (q[1] * 8 + l) * 32 + q[0]) for l in range(8)) or (get(CLEAN + q[1] * 32 + q[0]) >> 3) & 0x0F != bg
        own = {q: k for q, k in st['own'].items() if k is not None and k[0] == rm and q not in front and ink(q)}
        drawn = st['gbdrawn']
        c['go-behind: rooms checked for split items'] += 1
        for it in scenery_items(own, st['objids']):
            a = len(it & drawn)
            if a:
                c['go-behind: items in front'] += 1
            if a and a < len(it):
                fail('a scenery item split by go-behind', (rm, sorted(it)[:3], a, len(it)))
        stray = [q for q in drawn if ink(q) and q not in own and q not in front]
        if stray:
            fail('go-behind cells not owned by a room object', (rm, sorted(stray)[:4]))

    def gb_census(get, plots):
        # owner's limits: Wally never mostly hidden, no item hidden at all, by go-behind scenery pixels
        gpx = st.get('gbpix')
        if not gpx:
            return
        for q in plots:
            if q['y'] >= 128:
                continue
            w_ = 24 if q['K'] >= 2 else 16
            h_ = 32 if q['K'] >= 2 else 16
            if not any((x_, y_) in gpx for x_ in range(q['x'] - 1, q['x'] + w_ + 1) for y_ in range(q['y'] - 1, q['y'] + h_ + 1)):
                continue
            px = expected_layer(get, [q], patch.colours, st['mem'].banks, ori0)[0]
            hid = sum(1 for k in px if k in gpx)
            if q['pc'] == P_WAL:
                # the owner's words: 'at least his outline or most of him stays visible': the better of all his
                # pixels and his outline (the sprite's edge pixels) must be at least half showing
                c['go-behind: Wally frames behind scenery'] += 1
                # owner, second look: his body counts, not the outline. Body = his pixels inside the outline
                edge = {k for k in px if any((k[0] + dx, k[1] + dy) not in px for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
                body = [k for k in px if k not in edge]
                vis = 1000 * sum(1 for k in body if k not in gpx) // max(1, len(body))
                ex_ = EDGE_EXCEPTION.get(get(ROOM))
                if vis < 500 and ex_ and q['x'] >= ex_[0]:
                    g2 = {k for k in gpx if k[0] < ex_[1] * 8}       # without the palm: the rest must keep the rule
                    vis2 = 1000 * sum(1 for k in body if k not in g2) // max(1, len(body))
                    if vis2 >= 500:
                        c["go-behind: Wally at a right-edge palm (owner's exception)"] += 1
                        c["go-behind: least visible at the palm exception, per mille"] = min(c.get("go-behind: least visible at the palm exception, per mille", 1000), vis)
                        vis = 1000
                c['go-behind: Wally least visible, per mille'] = min(c.get('go-behind: Wally least visible, per mille', 1000), vis)
                if vis < 500:
                    st.setdefault('gbfail', set()).add(('wally', get(ROOM), q['x'], q['y'], vis))
                    fail('Wally mostly hidden by go-behind scenery', (get(ROOM), q['x'], q['y'], vis))
            elif q.get('item'):
                st.setdefault('gbitems', set()).add((get(ROOM), q['x'], q['y']))
                if hid:
                    st.setdefault('gbfail', set()).add(('item', get(ROOM), q['x'], q['y'], hid))
                    fail('an item hidden by go-behind scenery', (get(ROOM), q['x'], q['y'], hex(q['g']), hid))
            elif hid:
                # every creature the same way as Wally (owner, 2026-11-03): at least half of its body shows
                c['go-behind: other figures behind scenery'] += 1
                edge = {k for k in px if any((k[0] + dx, k[1] + dy) not in px for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
                body = [k for k in px if k not in edge] or list(px)
                vis = 1000 * sum(1 for k in body if k not in gpx) // max(1, len(body))
                ex_ = EDGE_EXCEPTION.get(get(ROOM))
                if vis < 500 and ex_:
                    g2 = {k for k in gpx if k[0] < ex_[1] * 8}
                    if 1000 * sum(1 for k in body if k not in g2) // max(1, len(body)) >= 500:
                        c["go-behind: a creature at a right-edge palm (owner's exception)"] += 1
                        vis = 1000
                key_ = 'go-behind: least visible creature %04X, per mille' % q['g']
                if vis < 1000:
                    c[key_] = min(c.get(key_, 1000), vis)
                if vis < 500:
                    st.setdefault('gbfail', set()).add(('creature', get(ROOM), hex(q['g']), q['x'], q['y'], vis))
                    fail('a creature mostly hidden by go-behind scenery', (get(ROOM), hex(q['g']), q['x'], q['y'], vis))

    def on_event(pc, get, R, mem):
        for a in range(pc, pc + 3):
            if get(a) != site_bytes[a]:
                fail('site bytes changed in the game', (hex(pc),))
                return
        if pc == P_TILE:
            if st['front_on']:
                st['fcells'].add((R[5], R[4]))
            elif R[4] < 16 and R[5] < 32:
                st['own'][(R[5], R[4])] = st['objkey']      # the last object printed in a cell owns it
            pair(pc, get, R)
            return
        if pc in (P_FON, P_FOF):
            st['front_on'] = pc == P_FON
            pair(pc, get, R)
            return
        if pc in PLOTS:
            pr = plot_params(get, R, pc, patch.figs)
            res = pair(pc, get, R)
            if pr is None:
                c['plots off the buffer'] += 1
            else:
                if pr['y'] >= 128:
                    c['plots with y >= 128'] += 1
                st['plots'].append(pr)
                c['plots 0x%04X' % pc] += 1
                st.setdefault('rets', collections.Counter())[(pc, pr['ret'])] += 1
                st.setdefault('gfx', set()).add((pr['K'], pr['g']))
            return
        if pc == P_FX:
            st['fx'] = True
            c['effect runs (room %d)' % get(ROOM)] += 1
            pair(pc, get, R)
            return
        if pc == P_BL:
            if collect and len(states) < collect and st['plots'] and st['frame'] >= st.get('next_c', 0):
                st['next_c'] = st['frame'] + 300
                states.append(dict(R=list(R), mem=bytes(get(a) for a in range(65536)), H=bytes(ns.H), banks=[bytes(b) for b in st['mem'].banks], cur=st['mem'].o7ffd & 7,
                                   plots=[dict(q) for q in st['plots']]))
            res = pair(pc, get, R)
            if res:
                commit_checks(get, res[3], st['plots'])
                st['clean'] = {a: v for a, v in res[3].ov.items() if BUFFER[0] <= a < BUFFER[1]}
                st['clean_rest'] = True
            st['plots'] = []
            st['fx'] = False
            return
        if pc == P_UND:
            # the original's restore must write what the hook's restore already wrote
            if st.get('clean_rest'):
                sp0 = R[12]
                ret = get(sp0) | get((sp0 + 1) & 0xFFFF) << 8
                o = _OrigView(get)
                so = _machine(Sim, o, list(R), _NS(_Dummy), 'o')
                if _run_until(so, lambda r: r[24] == ret and r[12] == (sp0 + 2) & 0xFFFF):
                    d = [a for a in set(st['clean']) | {a for a in o.ov if BUFFER[0] <= a < BUFFER[1]}
                         if st['clean'].get(a, get(a)) != o.ov.get(a, get(a))]
                    if d:
                        fail('the hook\'s restore differs from 0xB7D7', (len(d), hex(sorted(d)[0])))
                    c['restores compared'] += 1
                st['clean_rest'] = False
            if ns.H[V_N]:
                c['plots pending at 0xB7D7'] += 1
            pair(pc, get, R)
            if ns.H[V_N]:
                fail('plots left after 0xB7D7')
            st['plots'] = []
            st['fcells'] = set()
            return
        if pc == P_WP:
            st['fresh'] = True
            st['gbn'], st['gbdone'], st['gbdrawn'] = 0, False, set()     # h_l2clr
            res = pair(pc, get, R)
            if res:
                st['clean'] = {a: v for a, v in res[3].ov.items() if BUFFER[0] <= a < BUFFER[1]}
                st['clean_rest'] = True
                if any(a[3] & 0x80 for a in ns.attr):
                    fail('sprites on show during the wipe')
                if ns.nr[0x69] != 0 or any(v != 0xE3 for v in ns.l2):
                    fail('Layer 2 on show during the wipe')
            return
        if pc == P_AW:
            res = pair(pc, get, R)
            if res:
                exp, code = expected_layer(get, st['plots'], patch.colours, st['mem'].banks, ori0)
                lay = ns.sprite_layer()
                c['commits after a wipe'] += 1
                c['sprite pixels compared'] += len(exp)
                if lay != exp:
                    fail('sprite layer differs from the plots (wipe)', (len({k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)}),))
                front_check(get, lambda a, o_=res[3].ov: o_.get(a, get(a)), regular=False)
                black_check(exp)
                if ns.H[V_DROP]:
                    fail('figures dropped', (ns.H[V_DROP],))
                    ns.H[V_DROP] = 0
            st['plots'] = []
            return
        if pc == P_CLS:
            fe0 = len(ns.fe)
            res = pair(pc, get, R)
            if res and any(a[3] & 0x80 for a in ns.attr):
                fail('sprites on show after a clear')
            if ns.nr[0x69] != 0:
                fail('Layer 2 on show after a clear')
            if len(ns.fe) - fe0 != 1 or (ns.fe and ns.fe[-1] != 0):
                fail('clear: border write differs')
            return

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            st['mem'] = mem

            class W(type(mem)):
                def __setitem__(s, a, v):
                    if a in psite and a >= 0x4000:
                        fail('game wrote a patch site', (hex(a),))
                    MS(s, a, v)
            mem.__class__ = W
            get = lambda a: MG(mem, a)

            def mk(f):
                def g():
                    pc = R[24]
                    prev, st['prev'] = st['prev'], pc
                    if pc in INTERIOR and not (prev is not None and INTERIOR[pc] <= prev < pc):
                        fail('jump into a patched instruction', (hex(pc), prev))
                    if pc in SITES_ORIG and pc != P_AT:
                        on_event(pc, get, R, mem)
                    elif pc == P_OBJ:                # a room-list object: (room, its place in the list)
                        if st['objkey'] is None:
                            st['nobj'] = 0
                            st['built'] = None
                        st['nobj'] += 1
                        st['objkey'] = (get(ROOM), st['nobj'])
                        st['objids'][st['objkey']] = (R[2] << 8 | R[3]) >> 1
                    elif pc == P_OBJEND:
                        if st['objkey'] is not None:
                            st['built'] = get(ROOM)
                        st['objkey'] = None
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    def nf():
        st['frame'] += 1
        c['frames'] = st['frame']
        if progress and st['frame'] % 500 == 0:
            progress(st['frame'], c)

    _replay(rzx_path, stop, S, nf)
    c['hook T per game frame'] = st['hookT'] // max(1, st['gf'])
    ex['callers'] = sorted(('%04X' % a, '%04X' % b, n) for (a, b), n in st.get('rets', {}).items())
    ex['graphics seen'] = len(st.get('gfx', ()))
    ex['go-behind rooms (commits)'] = dict(sorted(st.get('gbrooms', {}).items()))
    ex['go-behind items near'] = sorted(st.get('gbitems', ()))
    ex['go-behind failures'] = sorted(st.get('gbfail', ()))
    ex['multi-part figures'] = dict(st.get('parts', collections.Counter()).most_common(12))
    ex['commit T'] = st.get('commitT', [])
    st_gfx = st.get('gfx', set())
    return c, ex, states, st_gfx


def unit_tests(patch, states, negatives=()):
    """Cases the recordings do not reach, on captured states: every plot with x, y at the edges, a full log, cache
    pressure, and the colour map; each negative must be seen."""
    c = collections.Counter()
    Sim = _sim_class()
    f = []

    def run_commit(pt, st, plots_regs, ns=None):
        ns = ns or _NS(pt)
        ns.H[V_N] = 0
        get = lambda a: st['mem'][a]
        psite = {a + k: v for a, old, new in pt.sites for k, v in enumerate(new)}
        err = []
        ns.cur = st['cur']
        ns.nr[0x56], ns.nr[0x57] = st['cur'] * 2, st['cur'] * 2 + 1
        p = _PatchedView(get, ns, pt.alt_view(get), psite, pt.store, err, st['banks'])
        out = []
        for pc, regs, over in plots_regs:
            p.ov.update(over)
            sim = _machine(Sim, p, list(regs), ns, 'p')
            gt = lambda a: p.ov.get(a, get(a))
            pr = plot_params(gt, regs, pc, pt.figs)
            sim.registers[24] = pc
            tgt = BACK[pc]
            if not _run_until(sim, lambda r: r[24] == tgt, 200000):
                err.append(('plot did not return', pc))
                break
            if pr:
                out.append(pr)
        regs = list(st['R'])
        ret = 0x4000
        sp0 = regs[12]
        p.ov[sp0], p.ov[(sp0 + 1) & 0xFFFF] = 0, 0x40
        sim = _machine(Sim, p, regs, ns, 'p')
        sim.registers[24] = P_BL
        if not _run_until(sim, lambda r: r[24] == ret):
            err.append(('commit did not return',))
        gt = lambda a: p.ov.get(a, get(a))
        return ns, out, err, gt

    def case(pt, st, pc, a, x, y, K=None):
        regs = list(st['R'])
        regs[0] = a
        over = {}
        if pc in (P_OR16, P_M16):
            over = {SX: x, SY: y, SY2: 0}
        elif pc in (P_M24, P_OR24):
            over = {BX: x, BY: y}
        else:
            over = {WX: x, WY: y, WFR: a}
        return pc, regs, over

    for st in states:
        for pc in PLOTS:
            for x, y in ((0, 0), (7, 3), (232, 96), (239, 111), (240, 112), (248, 120), (255, 127), (128, 130)):
                for a in (0, 1):
                    item = case(patch, st, pc, a, x, y)
                    ns, plots, err, gt = run_commit(patch, st, [item])
                    exp, _ = expected_layer(gt, plots, patch.colours, st['banks'], patch.ori0)
                    lay = ns.sprite_layer()
                    c['cases'] += 1
                    if err:
                        f.append(('error', hex(pc), x, y, err[:2]))
                        c['case error!'] += 1
                    if lay != exp:
                        f.append(('layer', hex(pc), x, y, a, len(set(lay) ^ set(exp))))
                        c['layer differs!'] += 1
        # a full log and more: 30 plots; 24 kept, the rest counted
        items = [case(patch, st, P_M16, i & 7, 8 * i, 16 + i) for i in range(30)]
        ns, plots, err, gt = run_commit(patch, st, items)
        c['full log cases'] += 1
        if ns.H[V_DROP] != 6:
            c['full log: drop count wrong!'] += 1
            f.append(('drop', ns.H[V_DROP]))
        # cache pressure: more graphics than entries, over several commits, the same NS; frames & 7 stay off the site at 0xA4C9
        ns = _NS(patch)
        for round_ in range(6):
            items = [case(patch, st, P_M24, (round_ * 7 + i) & 7, 20 * i, 20) for i in range(5)] + \
                    [case(patch, st, P_OR16, (round_ * 11 + i) & 63, 8 * i, 8) for i in range(9)]
            ns, plots, err, gt = run_commit(patch, st, items, ns)
            exp, _ = expected_layer(gt, plots, patch.colours, st['banks'], patch.ori0)
            c['pressure commits'] += 1
            if ns.sprite_layer() != exp:
                c['pressure: layer differs!'] += 1
                lay_ = ns.sprite_layer()
                d_ = sorted(k for k in set(lay_) | set(exp) if lay_.get(k) != exp.get(k))
                f.append(('pressure', round_, len(d_), d_[:4], [(lay_.get(k), exp.get(k)) for k in d_[:4]], ns.H[V_DROP],
                          [(hex(q['pc']), q['x'], q['y'], hex(q['g']), q['ink'][0]) for q in plots], hex(st['mem'][BASE] | st['mem'][BASE + 1] << 8)))
        # the colour map: a synthetic painting of the first plot
        p0 = st['plots'][0]
        bk = 3 if p0.get('wally') else 0
        get = lambda a: st['banks'][bk][a - 0xC000] if a >= 0xC000 else st['mem'][a]
        cmap = {}
        cols, S, rows = SHAPE[p0['K']]
        for r in range(rows):
            for q_ in range(cols):
                ga = p0['g'] + r * S + (cols if p0['K'] & 1 else 0) + q_
                cmap['%04X' % (ga - (0x6000 if bk else 0))] = [get(ga), 1, [5, 0, 3, 0, 9, 0, 0, 0], 0x10]
        pc = p0['pc']
        pt2 = ThreeWeeksPatch(patch.prof, colours=cmap, code=patch.code, rom_code=patch.rom_code, ori0=st['mem'][ORIENT])
        regs = list(st['R'])
        over = {}
        frm = (p0['g'] - (WALLY if pc == P_WAL else (get(BASE) | get(BASE + 1) << 8))) // FLEN[p0['K']]
        regs[0] = frm & 255
        item = case(pt2, st, pc, frm & 255, 40, 40)
        ns, plots, err, gt = run_commit(pt2, st, [item])
        exp, _ = expected_layer(gt, plots, cmap, st['banks'], pt2.ori0)
        c['map cases'] += 1
        if err or ns.sprite_layer() != exp:
            c['map: layer differs!'] += 1
            f.append(('map', err[:2], len(set(ns.sprite_layer()) ^ set(exp))))
        # plots logged, then the save-under list consumed with no blit between: they must go (no recording reaches this)
        item = case(patch, st, P_M16, 1, 40, 40)
        ns = _NS(patch)
        ns.cur = st['cur']
        ns.nr[0x56], ns.nr[0x57] = st['cur'] * 2, st['cur'] * 2 + 1
        get0 = lambda a: st['mem'][a]
        psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
        err = []
        pv = _PatchedView(get0, ns, patch.alt_view(get0), psite, patch.store, err, st['banks'])
        pv.ov.update(item[2])
        sim = _machine(Sim, pv, list(item[1]), ns, 'p')
        sim.registers[24] = P_M16
        _run_until(sim, lambda r: r[24] == BACK[P_M16], 200000)
        c['guard cases'] += 1
        if ns.H[V_N] != 1:
            c['guard: the plot was not logged!'] += 1
        sim = _machine(Sim, pv, list(st['R']), ns, 'p')
        sim.registers[24] = P_UND
        _run_until(sim, lambda r: r[24] == BACK[P_UND], 200000)
        if ns.H[V_N] != 0:
            c['guard: plots survive 0xB7D7!'] += 1
            f.append(('plots survive', ns.H[V_N]))
        # the effect: room 21's flag makes the next blit show the painted attributes
        ns = _NS(patch)
        ns.cur = st['cur']
        ns.nr[0x56], ns.nr[0x57] = st['cur'] * 2, st['cur'] * 2 + 1
        err = []
        pv = _PatchedView(get0, ns, patch.alt_view(get0), psite, patch.store, err, st['banks'])
        sim = _machine(Sim, pv, list(st['R']), ns, 'p')
        sim.registers[24] = P_FX
        _run_until(sim, lambda r: r[24] == BACK[P_FX], 200000)
        c['effect cases'] += 1
        if not ns.H[V_FX_]:
            c['effect: flag not set!'] += 1
            f.append(('effect flag', ns.H[V_FX_]))
    return c, f


def negative_patches(patch):
    """Broken builds. Each must be seen by verify on the real recording: {name: patch}."""
    out = {}
    code = bytes(patch.code)
    rom = bytes(patch.rom_code)
    prof = patch.prof
    sy = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}

    def mk(name, code2=None, rom2=None, extra=()):
        p = ThreeWeeksPatch(prof, colours=patch.colours, code=code2 or code, rom_code=rom2 or rom, figs=patch.figs, pal=patch.pal, ori0=patch.ori0, gb=patch.gb)
        if extra:
            p.sites = [s for s in p.sites if s[0] not in extra]
        out[name] = p
    def patch_at(buf, pat, off, val, start=0):
        k = bytes(buf).index(bytes(pat), start)
        buf[k + off] = val
    # 1. the blit keeps the figures: h_rest returns at once
    i = sy['h_rest'] - 0x200
    c1 = bytearray(code)
    c1[i] = 0xC9
    mk('no restore before the blit', bytes(c1))
    # 2. the attributes from the painted buffer
    r = bytearray(rom)
    patch_at(r, [0x21, 0x00, 0x74], 2, 0x76)
    mk('blit with the painted attributes', None, bytes(r))
    # 3. a plot's x is off by one: h_spr adds 33
    c3 = bytearray(code)
    patch_at(c3, [0x7A, 0xC6, 31], 2, 32)
    mk('sprite x off by one', bytes(c3))
    # 4. the hook loses a register: e_or16 does not put BC back
    r = bytearray(rom)
    k = sy['e_or16'] - ROM_ORG
    pos = bytes(r).index(bytes([0xE1, 0xD1, 0xC1, 0xF1]), k)
    r[pos + 2] = 0x00
    r[pos + 3] = 0xF1
    mk('a plot hook loses BC (stack off)', None, bytes(r))
    # 5. Wally's frame: the wrong graphics
    c5 = bytearray(code)
    k = code.index(bytes([0x01, WALLY & 255, WALLY >> 8]))
    c5[k + 1] = (WALLY + 192) & 255
    c5[k + 2] = (WALLY + 192) >> 8
    mk('Wally with the next frame', bytes(c5))
    # 6. the game's mask pixels left out: h_px's black -> transparent
    c6 = bytearray(code)
    k = sy['h_px'] - 0x200
    patch_at(c6, [0xCB, 0x7B, 0x20], 5, 0, k)
    mk('no mask pixels', bytes(c6))
    # 7. the pending plots are not dropped at 0xB7D7: e_und keeps V_N
    r = bytearray(rom)
    k = sy['e_und'] - ROM_ORG
    pos = bytes(r).index(bytes([0x36, 0x00]), k)
    r[pos], r[pos + 1] = 0x00, 0x00
    mk('plots survive 0xB7D7', None, bytes(r))
    # 10. no go-behind scenery: the room's chosen cells are left off Layer 2
    p = ThreeWeeksPatch(prof, colours=patch.colours, code=code, rom_code=rom, figs=patch.figs, pal=patch.pal, ori0=patch.ori0, gb={})
    out['no go-behind scenery'] = p
    # 11. go-behind cells whole: their paper drawn black over the figures (not pixel-accurate)
    c11 = bytearray(code)
    k = sy['h_gcell'] - 0x200
    patch_at(c11, [0x3E, 0xE3, 0x32, 0x2D, 0x00], 1, 0x00, k)
    mk('go-behind cells whole (paper drawn)', bytes(c11))
    # 9. the front routine's cells are not noted: figures in front of the tiles
    r = bytearray(rom)
    k = sy['e_fon'] - ROM_ORG
    pos = bytes(r).index(bytes([0x36, 0x01]), k)
    r[pos + 1] = 0
    mk('no Layer 2 front cells', None, bytes(r))
    # 8. no hide of old sprites on a clear
    r = bytearray(rom)
    k = sy['e_cls'] - ROM_ORG
    pos = bytes(r).index(bytes([0xED, 0x91, 0x38, 0x00]), k)
    r[pos + 3] = 0x80
    mk('clear leaves sprites', None, bytes(r))
    # 10. Wally's patterns read with bank 0 at 0xC000
    c = bytearray(code)
    patch_at(c, [0xED, 0x91, 0x56, 6], 3, 0)
    patch_at(c, [0xED, 0x91, 0x57, 7], 3, 1)
    mk('Wally read from the wrong bank', bytes(c))
    # 11. the game's bank not put back after a commit
    c = bytearray(code)
    k = code.index(bytes([0xED, 0x92, 0x56]))
    c[k:k + 3] = bytes(3)
    mk('bank at 0xC000 not restored', bytes(c))
    # 12. figures in the room's colour, not their own
    c = bytearray(code)
    k = sy['h_ink'] - 0x200
    c[k + 1:k + 1] = b''
    pos = code.index(bytes([0x21, 0x06, 0x1D]), k)        # LD HL,INKT+6
    c[pos + 1], c[pos + 2] = 0xF0, 0x1F                   # an empty table
    mk('fixed colours ignored', bytes(c))
    # 13. no outline
    c = bytearray(code)
    k = sy['h_outl'] - 0x200
    patch_at(c, [0x3E, 15], 1, 0, k)
    mk('no outline', bytes(c))
    # 14. no fill
    c = bytearray(code)
    k = sy['h_px'] - 0x200
    patch_at(c, [0xCB, 0x7D, 0x3E, CBLACK], 3, 0, k)
    mk('no fill', bytes(c))
    # 15. room 21's effect not passed on: the blit shows the clean attributes
    r = bytearray(rom)
    k = sy['e_fx'] - ROM_ORG
    pos = bytes(r).index(bytes([0x36, 0x01]), k)
    r[pos + 1] = 0
    mk('the effect not shown', None, bytes(r))
    # 17. the box's margin row lost: the outline a row down from where it belongs, so the top row goes
    c = bytearray(code)
    k = sy['h_outl'] - 0x200
    pos = code.index(bytes([0x11, 0x00, 0x41]), k + 16)   # LD DE,OUTL in the ring
    c[pos + 1] = 4
    mk('outline a row down', bytes(c))
    # 16. the plot's palette line dropped
    c = bytearray(code)
    k = sy['h_spr'] - 0x200
    pos = code.index(bytes([0xB6, 0xED, 0x92, 0x37]), k)  # OR (HL) / NEXTREG 0x37,A
    c[pos] = 0
    mk('palette line dropped', bytes(c))
    # 18-19. the pace window (x_pad in e_at): the wait must leave registers and the clock as the original's blit
    k = sy['e_at'] - ROM_ORG
    r = bytearray(rom)
    pos = bytes(r).index(bytes([0xF5, 0xC5, 0xD5, 0xCD]), k)            # push af, bc, de; call x_pad
    r[pos] = 0
    pos2 = bytes(r).index(bytes([0xD1, 0xC1, 0xF1]), pos)               # pop de, bc, af
    r[pos2 + 2] = 0
    mk('the pace wait loses AF', None, bytes(r))
    r = bytearray(rom)
    pos = bytes(r).index(bytes([0xED, 0x91, 0x07, 0x00, 0xC9]), k)      # nextreg 7,0 ; ret
    r[pos:pos + 4] = bytes(4)
    mk('the blit left at 28 MHz', None, bytes(r))
    return out


def run_negatives(rzx, stop=1500, say=print, patch=None):
    patch = patch or ThreeWeeksPatch()
    res = {}
    for name, p in negative_patches(patch).items():
        try:
            c, ex, _, _ = verify(p, rzx, stop=stop)
        except Exception as e:                      # a crash of the broken build's run is a detection too
            res[name] = 'DETECTED (raised %s)' % type(e).__name__
            say('Negative  : %-38s %s' % (name, res[name]))
            continue
        fl = {k: v for k, v in c.items() if k.endswith('!')}
        res[name] = 'DETECTED %s' % fl if fl else 'NOT DETECTED'
        say('Negative  : %-38s %s' % (name, str(res[name])[:150]))
    return res


# Enhanced is replayed on these recordings (the approved build's proof: 5 recordings, 28,930 frames)
ENH_VERIFY = ('t128_tour', 't128_gameover', 't128_r6', 't128_r12', 't128_r21')
# negatives: the recordings (name, frames; 0 = whole) that reach each case, first that detects counts
NEG_PLAN = {'the effect not shown': [('t128_r21', 0)], 'clear leaves sprites': [('t128_gameover', 10600)],
            'plots survive 0xB7D7': [('t128_r21', 0), ('t128_pend', 0)]}
NEG_DEFAULT = [('t128_tour', 1500)]


def _verify_one(patch, r, stop, say, label):
    import time
    t = time.time()
    c, ex, st, g = verify(patch, r, stop=stop, collect=3)
    fails = {k: v for k, v in c.items() if k.endswith('!')}
    say('Verify    : %s%s  %d frames, %d commits (+%d after wipes, max %d sprites, %d plots), %d sprite pixels, %d restores, %.0fs -> %s' % (
        label, os.path.basename(r), c['frames'], c['commits'], c['commits after a wipe'], c['max sprites in a frame'], c['max plots in a frame'],
        c['sprite pixels compared'], c['restores compared'], time.time() - t, 'IDENTICAL' if not fails else 'FAILED %s' % fails))
    say('            pairs: %s' % ', '.join('%s %d' % (k[6:], v) for k, v in sorted(c.items()) if k.startswith('pairs ')))
    say('            hook T per game frame %d (simulator T; hooks at 28 MHz); %s' % (
        c['hook T per game frame'], ', '.join('%s %d' % (k, v) for k, v in sorted(c.items())
                                              if k.startswith(('margin', 'hook T at', 'plots')))))
    say('            callers: %s' % str(ex.pop('callers', ''))[:900])
    say('            graphics seen: %s' % ex.pop('graphics seen', ''))
    for k, v in ex.items():
        say('            %s: %s' % (k, str(v)[:300]))
    return not fails, st


def negatives(rzxs, say, patch=None, epatch=None):
    """negative_patches on the recordings that reach each case (NEG_PLAN); -> (detected, total)."""
    by = {os.path.splitext(os.path.basename(r))[0]: r for r in rzxs}
    negs = [(n, p) for n, p in negative_patches(patch or ThreeWeeksPatch()).items() if n != 'palette line dropped']
    negs.append(('palette line dropped', negative_patches(epatch or enhanced_patch())['palette line dropped']))
    det = tot = 0
    for name, p in negs:
        plan = [(by[k], n) for k, n in NEG_PLAN.get(name, NEG_DEFAULT) if k in by]
        if not plan:
            say('Negative  : %-38s not run (no recording reaches it)' % name)
            continue
        tot += 1
        res = 'NOT DETECTED'
        for r, n in plan:
            try:
                c, _, _, _ = verify(p, r, stop=n or None)
                fl = {k: v for k, v in c.items() if k.endswith('!')}
                if fl:
                    res = 'DETECTED %s %s' % (os.path.basename(r), str(fl)[:120])
            except Exception as e:                  # a crash of the broken build's run is a detection too
                res = 'DETECTED %s (raised %s)' % (os.path.basename(r), type(e).__name__)
            if res.startswith('DETECTED'):
                break
        det += res.startswith('DETECTED')
        say('Negative  : %-38s %s' % (name, res))
    return det, tot


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : three_weeks (back buffer + save-under; blit without figures; every figure -> sprites)')
    ok, (plain, spr), patch, epatch = build(z80, out, name, say)
    states = []
    stop = getattr(a, 'quick', None)
    rzxs = list(a.rzx or [])
    for r in rzxs:
        good, st = _verify_one(patch, r, stop, say, '')
        ok = ok and good
        states += st
    for r in rzxs:
        if os.path.splitext(os.path.basename(r))[0] in ENH_VERIFY:
            good, _ = _verify_one(epatch, r, stop, say, 'Enhanced ')
            ok = ok and good
    if states:
        u, f = unit_tests(patch, states[:2])
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d edge cases, %d full-log, %d pressure commits, %d map cases -> %s' % (
            u['cases'], u['full log cases'], u['pressure commits'], u['map cases'], 'PASS' if not uf else 'FAIL %s %s' % (uf, f[:4])))
        neg = negative_patches(patch)
        for n, key in (('plots survive 0xB7D7', 'guard'), ('the effect not shown', 'effect')):
            nu, _ = unit_tests(neg[n], states[:1])
            hit = any(k.endswith('!') for k in nu)
            ok = ok and hit
            say('Unit neg. : %-38s %s' % (n, 'DETECTED %s' % [k for k in nu if k.endswith('!')] if hit else 'NOT DETECTED'))
    if rzxs and not stop:
        det, tot = negatives(rzxs, say, patch, epatch)
        ok = ok and det == tot
        say('Negatives : %d of %d DETECTED' % (det, tot))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Colour sheets and recolour (docs/COLOURS.md)
# ---------------------------------------------------------------------------------------------

GROUPS = ('Wally', 'Big figures', 'Masked', 'Plain', 'Items')


def group_of(p):
    if p['pc'] == P_WAL:
        return 'Wally'
    if p['K'] >= 2:
        return 'Big figures'
    if p.get('item'):
        return 'Items'
    return 'Masked' if p['K'] == 1 else 'Plain'


def sheet_part(get, p, frame):
    """A plot -> a coloursheet part: every bit of its graphics bytes (clear bits code 0); default colours."""
    K, g = p['K'], p['g']
    cols, S, rows = SHAPE[K]
    masked = K & 1
    pixels, entries = [], {}
    for r in range(rows):
        row = g + r * S
        for c in range(cols):
            ga = (row + (cols if masked else 0) + c) & 0xFFFF
            gb = get(ga)
            mb = get(row + c) if masked else 0xFF
            q = (2 if r >= 8 else 0) + c if K < 2 else 0
            key = '%04X' % (ga - (0x6000 if p.get('wally') else 0))
            entries.setdefault(key, [gb, 1])
            for b in range(8):
                bit = 0x80 >> b
                ink = bool(gb & bit)
                out = not ink and not (mb & bit)
                code = 1 if ink else (2 if out else 0)
                dflt = p['ink'][q] if ink else (CBLACK if out else 0)
                pixels.append((c * 8 + b, r, key, b, code, dflt))
    return dict(id=(g, K, tuple(p['ink'])) if p.get('item') else (g, K), size=rows, w=8 * cols, h=rows, x=p['x'], y=p['y'], mir=0,
                group=group_of(p), fam=(frame, g), role=None, pixels=pixels, entries=entries)


def capture(rzx_paths, stop=None, progress=None):
    """Replay the recordings (original game): every plot, frame by frame."""
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    from . import coloursheet as cs
    G = Memory.__getitem__
    col = cs.Collector(family=lambda p: p['fam'])
    st = {'f': 0, 'mem': None}
    frame = []

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)

            def rd(p):
                bk = 3 if p.get('wally') else 0
                return lambda a: mem.banks[bk][a - 0xC000] if a >= 0xC000 else get(a)

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in PLOTS:
                        p = plot_params(get, R, pc)
                        if p and p['y'] < 128:
                            frame.append(sheet_part(rd(p), p, st['f']))
                    elif pc == P_BL:
                        if frame:
                            col.add_frame(list(frame))
                            frame.clear()
                        if st['mem'] is None:
                            st['mem'] = bytes(get(a) for a in range(65536))
                    elif pc == P_UND:
                        frame.clear()
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    def nf():
        st['f'] += 1
        if progress and st['f'] % 2000 == 0:
            progress(st['f'])
    for path in ([rzx_paths] if isinstance(rzx_paths, str) else rzx_paths):
        frame.clear()
        _replay(path, stop, S, nf)
    return col, st['mem']


def sheets(col, prefix, peek, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    comps = list(col.comps.values())
    ident = colour_identity(peek)
    res = []
    paint = cs.choose(comps, col.maxsize, GROUPS)
    png = prefix + '_PAINTING_SPRITES.png'
    res.append((png, cs.write(paint, png, prefix + '_PAINTING_SPRITES_layout.json', rgb16, colours or {}, unique=False, paint_clear=True, identity=ident)))
    full = sorted(comps, key=lambda c: (GROUPS.index(c['group']) if c['group'] in GROUPS else 99, str(c['parts'][0]['id'])))
    png = prefix + '_REFERENCE_ALL_SPRITES.png'
    res.append((png, cs.write(full, png, prefix + '_REFERENCE_ALL_SPRITES_layout.json', rgb16, colours or {}, unique=False, paint_clear=True, identity=ident)))
    return res


COLOUR_BANKS = tuple([13] + [14 + n for n in range(NSTORE // 2)])
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/three_weeks_colours.json', 'clear': True, 'note': NOTE}


def colour_inputs_md5(peek):
    """MD5 of the game bytes the colours belong to, sites restored."""
    orig = {a + k: bytes.fromhex(v)[k] for a, v in SITES_ORIG.items() for k in range(3)}
    h = hashlib.md5()
    h.update(bytes(orig.get(a, peek(a)) for a in range(0x6B00, 0x10000)))
    return h.hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': RECORD, 'engine': 'three_weeks', 'keys': 'three_weeks-1: %04X graphics byte, bit = stored pixel',
            'inputs': colour_inputs_md5(peek), 'geometry': None}


def nex_peek(nex):
    from .recolour import nex_offsets
    d = bytes(nex)
    off = nex_offsets(d)
    bank = lambda b: d[off[b]:off[b] + 16384]
    ram = {5: bank(5), 2: bank(2), 0: bank(0)}
    return lambda a: ram[5][a - 0x4000] if a < 0x8000 else (ram[2][a - 0x8000] if a < 0xC000 else ram[0][a - 0xC000])


def recolour(nex, cmap):
    from .recolour import nex_offsets, splice
    d = bytearray(nex)
    off = nex_offsets(d)
    need = set(COLOUR_BANKS) | {5, 2, 0, 10, 12}
    if not need <= set(off):
        raise ValueError('not a Three Weeks sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    prof = load_profile()
    peek = nex_peek(nex)
    want = prof.get('colour_inputs')
    if want != colour_inputs_md5(peek):
        raise ValueError('game graphics differ from the expected snapshot (%s, expected %s)' % (colour_inputs_md5(peek), want))
    p0 = ThreeWeeksPatch(prof, colours={})
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    b12 = bank(12)
    lo, hi = ROM_ORG - 0x2000, p0.regblock - 0x2000
    if b12[lo:hi] != p0.page[lo:hi]:
        raise ValueError('hook code differs from this version\'s (rebuild with nexclash.py auto)')
    if bank(10)[0x1000:0x1000 + len(p0.stub_extra)] != p0.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    p = ThreeWeeksPatch(prof, colours=cmap, ori0=peek(ORIENT))
    out, changed = splice(nex, {b: p.extra_banks[b] for b in COLOUR_BANKS})
    return out, {'banks changed': changed, 'colour-map entries': len(cmap)}


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == 'sheet':
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument('rzx', nargs='+')
        ap.add_argument('-o', '--prefix', required=True)
        ap.add_argument('--stop', type=int)
        a = ap.parse_args(sys.argv[2:])
        col, mem = capture(a.rzx, a.stop, lambda f: print('frame', f, flush=True))
        for png, r in sheets(col, a.prefix, lambda x: mem[x], load_colours_build()):
            print(png, r)
    else:
        print(__doc__)
