"""Everyone's a Wally, updated (Mikro-Gen; 48K code in a 128K snapshot) - engine 'wally2', record
everyones_a_wally_updated. A new game to the 2026-10-14 standard; the first version (engine 'wally',
nexclash/wally.py, record wally) is frozen and untouched. Additive module: reachable only through
is_wally2() (cmd_auto) and `python -m nexclash.wally2`. Game facts: games/everyones_a_wally_updated.md.

  Render: the game restores a clean back buffer (61090: pixels 0x6B00-0x7AFF = screen lines 64-191,
  row y at 0x6300 + y*32; attributes 0xFC00-0xFDFF, cell at 0xFB00 + (y & 248)*4 + x/8), its room
  logic plots the objects (B, C), the render (47574) plots the gang (A), then 47611 copies pixels
  (row table 33400, unrolled LDI 47653) and 47637 the attributes. Interrupts are never on.
  A 45286  gang member, IY = descriptor 48231..48235 (+0 frame, +5 x, +10 y, +30 attr, +35/+40 gfx
           base), 16x32 masked, rows of 4 bytes (mask L, mask R, gfx L, gfx R), data base + frame*128
           (37944 + 1024*member + 128*frame); paints (IY+30) into 2-3 x 4-5 attribute cells.
  B 43168  masked 16x16 object, A = frame, data 33656 + A*32 (rows as A), position (43064, 43065).
  C 43069  OR-only 16x16 object, A = frame, data 33656 + A*32 (rows of 2 bytes: gfx L, gfx R).
  61329    paints the cells of the last B/C plot with (62063).
  33251    mirrors graphics IN PLACE (the gang 37816-43063 when a member turns, 35064-35255 from
           61511): each byte pair (L, R) -> (rev R, rev L).

Build (Dean 2026-10-14): every figure on a double-buffered Layer 2 in plot order (later in front),
in one colour per figure (gang member: its attribute ink; object: the 61329 paint, else the ink of the
cell under its centre), a black outline on the 4 neighbours of the ink (never diagonals), the painted
colour map per pixel on top. Each graphic has a precomputed CANVAS (18 x rows+2: the graphic with a
one-pixel ring) in pages the game never reads; a plot is converted when its bytes match the canvas'
check as stored or mirrored (asm/wally2_hooks.asm). Recolour rewrites only the canvas pages.
"""
import collections
import json
import os

A_PLOT, B_PLOT, C_PLOT, PAINT, COPY, COMMIT, MIRROR = 45286, 43168, 43069, 61329, 47611, 47637, 61511
RESTORE, CLEAR = 61090, 47362
GFX, AGFX = 33656, 37944
NA, NB, NC = 40, 133, 134
POS = 43064
PAINT_COL = 62063
BUF, ATTRBUF = (0x6B00, 0x7B00), (0xFC00, 0xFE00)
A_CALLERS = (47597, 61487, 61887)
B_CALLERS = (60787, 60823, 61544, 61560, 61777, 62044, 62055, 62184, 62237, 62350, 62361, 62416, 62430,
             62514, 62664, 62752, 62795, 63041, 63171, 63280, 63708)
C_CALLERS = (61150, 62288, 62298, 62605, 62712, 62854, 62866, 62880, 62892, 63249, 63337, 63448, 63534,
             63904, 64050)
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
L2PAL = [0xE3] + PALETTE[1:]            # Layer 2: index 0 = the transparent colour 0xE3
CBLACK = 8                              # palette index of black (0 is transparent)
GROUPS = ('Gang members', 'Masked objects', 'OR objects', 'From the code (not in the recording)')

PAGE_S, TPAGE, ALT_PAGE = 26, 27, 24
L2PAGES = (32, 38)                      # Layer 2 buffers: 16K banks 16-18 / 19-21
CPAGE0 = 44                             # canvas pages from here (16K bank 22 on)
ROM_ORG, PAGE_ORG = 0x386E, 0x0100
INKTAB, PL, BOX0, BOX1 = 0x1800, 0x1900, 0x1B00, 0x1C80
TA, TB, TC = 0x2000, 0x2200, 0x2700
V_N, V_LAST, V_BACK = 0, 1, 2
MAXP = 24
W = 18                                  # canvas width
TAIL_ADDR = 0x6B00
SITES_ORIG = {45286: bytes.fromhex('D9FD5E'), 43168: bytes.fromhex('D9F5ED'),
              43069: bytes.fromhex('F3D9F5'), 61329: bytes.fromhex('F5D93A'),
              47637: bytes.fromhex('010002'), 61090: bytes.fromhex('11006B'),
              47362: bytes.fromhex('E5C5D5')}
SITE_SYM = {45286: 'e_a', 43168: 'e_b', 43069: 'e_c', 61329: 'e_p', 47637: 'e_cm', 61090: 'e_rs',
            47362: 'e_cl'}
# the original instructions under each 3-byte JP: starts (reached only through the site) and
# interiors (never a PC: a jump there would land inside the JP)
STARTS = {45286: (45287,), 43168: (43169, 43170), 43069: (43070, 43071), 61329: (61330, 61331),
          47637: (), 61090: (), 47362: (47363, 47364)}
INTERIORS = (45288, 47638, 47639, 61091, 61092)

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'everyones_a_wally_updated_colours.json')
NOTE = ("Everyone's a Wally (updated) figure colours (python -m nexclash.wally2 colours): key 'M:addr' "
        "(masked graphics byte, plotters A/B), 'O:addr' (OR graphics byte, plotter C), 'RM:/RO:base.n' "
        "(the outline ring around a graphic, 8 pixels per key) -> [check, kind, 8 nibbles (0 = default)"
        "(, transparent mask)]")


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'everyones_a_wally_updated.json')


def load_profile():
    return json.load(open(_profile_path()))


def cidx(c, bright):
    return CBLACK if c == 0 else c + 8 * bright


def ink_of(attr):
    return cidx(attr & 7, (attr >> 6) & 1)


def rev(v):
    return int('{:08b}'.format(v)[::-1], 2)


def mirror(data):
    """In-place mirror of 33251: every byte pair (L, R) -> (rev R, rev L)."""
    out = bytearray(data)
    for i in range(0, len(data) - 1, 2):
        out[i], out[i + 1] = rev(data[i + 1]), rev(data[i])
    return bytes(out)


def chksum(data):
    s = 0
    for b in data:
        s = (((s << 1) | (s >> 15)) + b) & 0xFFFF
    return s


def rotl(v):
    return ((v << 1) | (v >> 7)) & 255


def entry_check(m, g):
    return m ^ rotl(g)


# ------------------------------------------------------------------------------------ graphics

def graphics(mem):
    """Every graphic the hooks can convert: [(kind 'A'|'B'|'C', index, gfx address, canonical bytes)].
    Canonical = as stored in the snapshot (colour keys are taken in this orientation)."""
    out = []
    for i in range(NA):
        g = AGFX + 128 * i
        out.append(('A', i, g, bytes(mem[g:g + 128])))
    for f in range(NB):
        g = GFX + 32 * f
        out.append(('B', f, g, bytes(mem[g:g + 64])))
    for f in range(NC):
        g = GFX + 32 * f
        out.append(('C', f, g, bytes(mem[g:g + 32])))
    return out


def geometry(kind):
    """-> (rows, bytes per row, masked)"""
    return (32, 4, True) if kind == 'A' else (16, 4, True) if kind == 'B' else (16, 2, False)


def ring_index(cx, cy, H):
    if cy == 0:
        return cx
    if cy == H - 1:
        return W + 2 * (H - 2) + cx
    return W + 2 * (cy - 1) + (0 if cx == 0 else 1)


def pixels(kind, gfx, data):
    """Every canvas pixel of a graphic (canonical bytes): [(cx, cy, key, bit, code)], code 1 ink,
    2 outline (a 4-neighbour of the ink), 0 clear. Keys: graphics byte inside the 16-pixel span, the
    ring around it in groups of 8 (Dean 2026-10-14: outlines everywhere, also past the graphic)."""
    rows, bpr, masked = geometry(kind)
    H = rows + 2
    K = 'M' if masked else 'O'

    def ink(c, r):
        if not (0 <= c < 16 and 0 <= r < rows):
            return False
        j = r * bpr + (2 if masked else 0) + (c >> 3)
        return bool(data[j] & (0x80 >> (c & 7)))
    out = []
    for cy in range(H):
        for cx in range(W):
            c, r = cx - 1, cy - 1
            if 0 <= c < 16 and 0 <= r < rows:
                j = r * bpr + (2 if masked else 0) + (c >> 3)
                key, bit = '%s:%04X' % (K, (gfx + j) & 0xFFFF), c & 7
            else:
                n = ring_index(cx, cy, H)
                key, bit = 'R%s:%04X.%d' % (K, gfx, n >> 3), n & 7
            if ink(c, r):
                code = 1
            elif ink(c - 1, r) or ink(c + 1, r) or ink(c, r - 1) or ink(c, r + 1):
                code = 2
            else:
                code = 0
            out.append((cx, cy, key, bit, code))
    return out


def entries_of(kind, gfx, data):
    """{key: [check, kind]} for every key of a graphic (the check guards the painted map)."""
    rows, bpr, masked = geometry(kind)
    ent = {}
    K = 'M' if masked else 'O'
    for r in range(rows):
        for half in (0, 1):
            j = r * bpr + (2 if masked else 0) + half
            m = data[j - 2] if masked else 0
            ent['%s:%04X' % (K, (gfx + j) & 0xFFFF)] = [entry_check(m, data[j]), 1 if masked else 2]
    ck = chksum(data) & 255
    for n in range(((W * 2 + 2 * rows) + 7) // 8):
        ent['R%s:%04X.%d' % (K, gfx, n)] = [ck, 3]
    return ent


def canvas(kind, gfx, data, cmap=None):
    """Canvas bytes (18 x rows+2) of a graphic, colour map applied (entries whose check matches)."""
    cmap = cmap or {}
    ent = entries_of(kind, gfx, data)
    out = bytearray()
    for cx, cy, key, bit, code in pixels(kind, gfx, data):
        e = cmap.get(key)
        if e is not None and (e[0], e[1]) != tuple(ent[key]):
            e = None                                    # painted for other graphics: defaults
        v = e[2][bit] if e else 0
        t = bool(e and len(e) > 3 and e[3] & (0x80 >> bit))
        if code == 1:
            b = 0 if t else (0x20 | v if v else 0x30)
        elif code == 2:
            b = 0 if t else 0x40 | (v or CBLACK)
        else:
            b = v
        out.append(b)
    return bytes(out)


def canvas_pixel(b, colour):
    """Canvas byte -> Layer 2 index (0 = nothing drawn)."""
    if not b:
        return 0
    return colour if b & 0x10 else b & 0x0F


# ------------------------------------------------------------------------------------ the build

class Config:
    def __init__(self, colours=None):
        self.colours = colours if colours is not None else load_colours()


def inktab():
    return bytes(ink_of(a) for a in range(256))


def build_tables(mem, cmap):
    """-> (tpage bytes, {canvas page: bytes}, {('A'|'B'|'C', index): (page, offset)})"""
    tp = bytearray(8192)
    pages, where = {}, {}
    page, off, cur = CPAGE0, 0, bytearray()
    base = {'A': TA, 'B': TB, 'C': TC}
    for kind, i, g, data in graphics(mem):
        cv = canvas(kind, g, data, cmap)
        if off + len(cv) > 8192:
            pages[page] = bytes(cur) + bytes(8192 - len(cur))
            page, off, cur = page + 1, 0, bytearray()
        cur += cv
        where[(kind, i)] = (page, off)
        e = base[kind] - 0x2000 + 8 * i
        tp[e:e + 8] = bytes([page, off & 255, off >> 8]) + chksum(data).to_bytes(2, 'little') + \
            chksum(mirror(data)).to_bytes(2, 'little') + b'\x00'
        off += len(cv)
    pages[page] = bytes(cur) + bytes(8192 - len(cur))
    return bytes(tp), pages, where


def _mem_of(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536]))


def mem64(snap):
    b = snap.memory.banks
    return bytes(16384) + bytes(b[5]) + bytes(b[2]) + bytes(b[0])


def identify(mem):
    sg = load_profile()['signature']
    a, sig = sg['addr'], bytes.fromhex(sg['bytes'])
    return bytes(mem[a:a + len(sig)]) == sig


def is_wally2(snap):
    try:
        return snap.machine != '48K' and identify(mem64(snap))
    except FileNotFoundError:
        return False


class Wally2Patch:
    name = "Everyone's a Wally (updated): every figure on Layer 2, outlined (altrom + pages 26/27)"

    def __init__(self, mem, cfg=None, prof=None):
        self.cfg = cfg or Config()
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.page_code = bytes.fromhex(h['page'])
        self.setup = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = self.setup + bytes(L2PAL)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 80
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM stubs too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        sp = bytearray(8192)
        if PAGE_ORG + len(self.page_code) > INKTAB:
            raise ValueError('page code overlaps the tables')
        sp[PAGE_ORG:PAGE_ORG + len(self.page_code)] = self.page_code
        sp[INKTAB:INKTAB + 256] = inktab()
        sp[V_BACK] = 1                      # buffer 0 is on show at start (setup), draw into 1
        self.scratch = bytes(sp)
        self.tpage, self.cpages, self.where = build_tables(mem, self.cfg.colours)
        self.gfx_md5 = graphics_md5(mem)
        self.extra_banks = {12: self.page + bytes(8192), 13: self.scratch + self.tpage}
        for b in range(16, 22):
            self.extra_banks[b] = bytes(16384)
        for p in sorted(self.cpages):
            b = p // 2
            cur = bytearray(self.extra_banks.get(b, bytes(16384)))
            cur[(p & 1) * 8192:(p & 1) * 8192 + 8192] = self.cpages[p]
            self.extra_banks[b] = bytes(cur)
        self.sites = [(a, old, b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]

    def _bank_of(self, a):
        return (5, 2, 0)[(a >> 14) - 1]

    def check_sites(self, banks):
        for a, old, new in self.sites:
            b = banks[self._bank_of(a)]
            cur = bytes(b[(a & 0x3FFF):(a & 0x3FFF) + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        if not snap.is128:
            raise ValueError("Everyone's a Wally patch expects the 128K snapshot")
        if snap.port7ffd & 0x17 != 0x10:
            raise ValueError('snapshot must select ROM 1 (48K BASIC) and bank 0 at C000')
        self.check_sites(snap.banks)
        for a, old, new in self.sites:
            k = self._bank_of(a)
            b = bytearray(snap.banks[k])
            b[(a & 0x3FFF):(a & 0x3FFF) + len(new)] = new
            snap.banks[k] = bytes(b)


def graphics_md5(mem):
    import hashlib
    return hashlib.md5(bytes(mem[GFX:AGFX + 128 * NA])).hexdigest()


def boot_check(nex, z80, patch=None):
    """The rainbow boot check, with this engine's set-up (Layer 2 on, sprites off)."""
    import copy
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = nextboot.boot(nex, s.pc)
    R, mem, bad = st['R'], st['mem'], list(st['bad'])
    w = lambda h, l: R[h] * 256 + R[l]
    got = [w(2, 3), w(4, 5), w(6, 7), w(0, 1), w(8, 9), w(10, 11), w(18, 19), w(20, 21), w(22, 23),
           w(16, 17), R[12], R[14], R[27], R[26]]
    exp = [s.bc, s.de, s.hl, s.a * 256 + s.f, s.ix, s.iy, s.bc_, s.de_, s.hl_, s.a_ * 256 + s.f_,
           s.sp, s.i, s.im, s.iff1]
    bad += [('register', i, g, e) for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    banks, _, _ = nextboot.load_nex(nex)
    for b in range(8):
        if bytes(banks[b]) != bytes(s.banks[b]):
            bad.append(('NEX bank differs from the (patched) snapshot', b))
    top = s.port7ffd & 7
    ram = s.banks[5] + s.banks[2] + s.banks[top]
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not TAIL_ADDR <= a < TAIL_ADDR + 80]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    if patch is not None:
        img = bytearray(rom48())
        lo, hi = patch.altrom
        img[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
        regs = zt.build_tail(s, 0x8000, patch.slot1, True)[3]
        img[patch.regblock:patch.regblock + len(regs)] = regs
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
        view = bytes(mem[a] for a in range(0x4000))
        if view != bytes(img):
            d = [a for a in range(0x4000) if view[a] != img[a]]
            bad.append(('slots 0/1 differ from the expected ROM image', len(d), d[:6]))
        for reg, want in ((0x15, 0x00), (0x69, 0x80), (0x12, 16), (0x13, 19), (0x14, 0xE3), (0x70, 0)):
            if st['nr'].get(reg) != want:
                bad.append(('setup NextReg $%02X' % reg, st['nr'].get(reg), want))
        for p in range(32, 44):
            if any(banks[p // 2][(p & 1) * 8192:(p & 1) * 8192 + 8192]):
                bad.append(('Layer 2 page not empty', p))
    if st['p7ffd'] != s.port7ffd or not st['p1ffd'] & 4:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 2 * top, 2 * top + 1]:
        bad.append(('MMU', st['mmu']))
    return bad


# ----------------------------------------------------------------------------- run-time model

def ident(kind, gfx_or_frame, get):
    """The graphic a plot draws, as the hooks find it: -> (index, gfx, live bytes, orientation) or
    None (not convertible: the original plotter draws it). orientation 1 = mirrored in place."""
    if kind == 'A':
        g = gfx_or_frame
        if g < AGFX or (g - AGFX) & 127 or (g - AGFX) >> 7 >= NA:
            return None
        i, n = (g - AGFX) >> 7, 128
    else:
        i = gfx_or_frame
        if i >= (NB if kind == 'B' else NC):
            return None
        g, n = GFX + 32 * i, 64 if kind == 'B' else 32
    return i, g, bytes(get((g + k) & 0xFFFF) for k in range(n))


class Model:
    """What the hooks should do, from the original's state at each event (the verification's truth):
    plot list of the render, the canvases they draw, the expected Layer 2 image at a commit."""

    def __init__(self, patch, mem):
        self.patch = patch
        self.canon = {(k, i): (g, d) for k, i, g, d in graphics(mem)}
        self.cmap = patch.cfg.colours
        self.cvs = {}
        self.plots = []
        self.last = 0

    def canvas_for(self, kind, i):
        k = (kind, i)
        if k not in self.cvs:
            g, d = self.canon[k]
            self.cvs[k] = canvas(kind, g, d, self.cmap)
        return self.cvs[k]

    def plot(self, kind, R, get):
        """-> the entry the hook must stage, or None (passthrough)."""
        sp = R[12]
        caller = get(sp) | get(sp + 1) << 8
        if len(self.plots) >= MAXP:
            return None
        if kind == 'A':
            iy = R[10] << 8 | R[11]
            x, y = get(iy + 5), get(iy + 10)
            if not (64 <= y <= 160 and x <= 240):
                return None
            g = ((get(iy + 35) | get(iy + 40) << 8) + get(iy) * 128) & 0xFFFF
            idn = ident('A', g, get)
            col, rows = ink_of(get(iy + 30)), 34
        else:
            x, y = get(POS), get(POS + 1)
            if not (64 <= y <= 168 and x <= 240):
                return None
            idn = ident(kind, R[0], get)
            col = ink_of(get(0xFB00 + ((y + 8) & 248) * 4 + (((x + 8) & 255) >> 3)))
            rows = 18
        if idn is None:
            return None
        i, g, live = idn
        cg, cd = self.canon[(kind, i)]
        cs = chksum(live)
        if cs == chksum(cd):
            ori = 0
        elif cs == chksum(mirror(cd)):
            ori = 1
        else:
            return None
        e = dict(kind=kind, i=i, x=x, y=y, rows=rows, colour=col, ori=ori, caller=caller, live=live,
                 joined=False)
        if self.plots and kind != 'A':
            p = self.plots[-1]
            e['joined'] = (p['kind'] == kind and p['caller'] != caller and abs(x - p['x']) < 18 and
                           abs(y - p['y']) < 18)
        self.plots.append(e)
        self.last = len(self.plots) if kind != 'A' else self.last
        return e

    def passthrough(self, kind):
        if kind != 'A':
            self.last = 0

    def paint(self, get):
        """61329: -> True if it colours a converted plot."""
        if not self.last:
            return False
        self.plots[self.last - 1]['colour'] = ink_of(get(PAINT_COL))
        self.last = 0
        return True

    def restore(self):
        self.plots, self.last = [], 0

    def image(self):
        """Expected Layer 2 buffer after the commit (192 x 256 indexes) and the render's plots reset."""
        img = bytearray(192 * 256)
        n, P = 0, self.plots
        while n < len(P):
            m = n + 1
            while m < len(P) and P[m]['joined']:
                m += 1
            passes = ((3,),) if m - n == 1 else ((1,), (2,))
            for (mode,) in passes:
                for e in P[n:m]:
                    self._draw(img, e, mode)
            n = m
        self.plots, self.last = [], 0
        return bytes(img)

    def _draw(self, img, e, mode):
        cv = self.canvas_for(e['kind'], e['i'])
        H = e['rows']
        for cy in range(H):
            Y = e['y'] - 1 + cy
            if not 64 <= Y < 192:
                continue
            for c in range(W):
                X = e['x'] - 1 + c
                if not 0 <= X < 256:
                    continue
                b = cv[cy * W + (W - 1 - c if e['ori'] else c)]
                if not b:
                    continue
                if not mode & (2 if b & 0x20 else 1):
                    continue
                img[Y * 256 + X] = canvas_pixel(b, e['colour'])


# ------------------------------------------------------------------------ Next state + memory

def _next_state(patch):
    from .rainbow import NextState

    class NS(NextState):
        pass
    ns = NS(patch)
    ns.pages[TPAGE] = bytearray(patch.tpage)
    for p, b in patch.cpages.items():
        ns.pages[p] = bytearray(b)
    for p in range(32, 44):
        ns.pages[p] = bytearray(8192)
    ns.nr.update({0x12: 16, 0x13: 19, 0x69: 0x80, 0x52: 10})
    return ns


def shown(ns):
    """Layer 2 image on show (192 x 256), or None when Layer 2 is off."""
    if not ns.nr.get(0x69, 0) & 0x80:
        return None
    p = ns.nr.get(0x12, 16) * 2
    return b''.join(bytes(ns.pages[p + k]) for k in range(6))


def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


CMP = list(range(0, 13)) + [14, 16, 17] + list(range(18, 25)) + [26, 27, 28]   # all but R, T, MEMPTR


def _pair(patch, get, regs, ns, stops, alt):
    """Run original and patched code from one state (memory read through get(a)) until PC in stops.
    ns = the patched Next state (mutated). Returns (so, o, sp, p, err)."""
    from .rainbow import _machine, _run
    Sim = _sim_class()
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    err = []

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return get(a) if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def _pg(s, a):
            slot = a >> 13
            pg = ns.nr.get(0x50 + slot, 0xFF if slot < 2 else (10, 11)[slot - 2] if slot < 4 else None)
            if slot < 2:
                if pg == 0xFF:
                    return None
                return ns.scratch if pg == PAGE_S else ns.pages[pg]
            if slot == 2 and pg not in (10, None):
                return ns.pages[pg]
            return False

        def __getitem__(s, a):
            m = s._pg(a)
            if m is None:
                return alt[a]
            if m is not False:
                return m[a & 0x1FFF]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            m = s._pg(a)
            if m is None:
                err.append(('rom write', a))
            elif m is not False:
                if a < 0x4000 and m is not ns.scratch:
                    err.append(('write to a table / canvas page', a))
                m[a & 0x1FFF] = v
            else:
                s.ov[a] = v
    o, p = O(), P()
    ns.events = []
    from .rainbow import NextState
    so = _machine(Sim, o, list(regs), NextState(patch), 'o')
    sp_ = _machine(Sim, p, list(regs), ns, 'p')
    if not (_run(so, stops, 400000) and _run(sp_, stops, 4000000)):
        err.append('did not return')
    for reg, want in ((0x50, 0xFF), (0x51, 0xFF), (0x52, 10), (0x07, 0)):
        if ns.nr.get(reg, want) != want:
            err.append(('NextReg $%02X not restored' % reg, ns.nr.get(reg)))
    if any(e[0] == 'in' for e in ns.events):
        err.append('port read in hook')
    return so, o, sp_, p, err


def _in(a, r):
    return r[0] <= a < r[1]


def _ret(get, R):
    sp = R[12]
    return (get(sp) | get(sp + 1) << 8,)


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def check_plot(kind, so, o, sp_, p, ns, n_before, exp, model):
    """A/B/C event: registers, memory (buffers excepted when converted), staging vs the model."""
    f = []
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    n_after = ns.scratch[V_N]
    converted = n_after != n_before
    if converted != (exp is not None):
        f.append(('converted / passthrough differs from the guard model', converted))
        return f
    if not converted:
        if o.ov != p.ov:
            f.append(('passthrough differs', len(set(o.ov) ^ set(p.ov))))
        return f
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not (_in(a, BUF) or _in(a, ATTRBUF)) and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    if any(_in(a, BUF) or _in(a, ATTRBUF) or 0x4000 <= a < 0x5B00 for a in p.ov):
        f.append(('patched code wrote the buffer/screen',))
    if n_after != n_before + 1:
        f.append(('plot count', n_before, n_after))
        return f
    e = ns.scratch[PL + 16 * n_before:PL + 16 * n_before + 16]
    want_page, want_off = model.patch.where[(kind, exp['i'])]
    got = (e[0], e[1] | e[2] << 8, e[3], e[4], e[5], e[6], e[7], e[8], e[9] | e[10] << 8)
    want = (want_page, want_off, exp['x'], exp['y'], exp['rows'], exp['colour'],
            exp['ori'] | (2 if exp['joined'] else 0), 'ABC'.index(kind), exp['caller'])
    if got != want:
        f.append(('plot entry differs from the model', got, want))
    # the canvas it draws vs the graphic as the original drew it (live bytes, oriented)
    cv = bytes(ns.pages[e[0]][want_off:want_off + W * exp['rows']])
    rows, bpr, masked = geometry(kind)
    bad = 0
    for cy in range(1, rows + 1):
        for c in range(1, 17):
            b = cv[cy * W + (W - 1 - c if exp['ori'] else c)]
            j = (cy - 1) * bpr + (2 if masked else 0) + ((c - 1) >> 3)
            ink = bool(exp['live'][j] & (0x80 >> ((c - 1) & 7)))
            bad += (bool(b & 0x20) != ink) if not model.cmap else (bool(b & 0x20) and not ink)
    if bad:
        f.append(('canvas ink differs from the original plot', bad))
    return f


# ------------------------------------------------------------------- differential verification

def verify(patch, rzx_path, mem, stop=None, collect=0, progress=None):
    """Replay the RZX (the ORIGINAL game); at every hook site run original and patched code from the
    same state and compare; at every commit compare the Layer 2 image on show with the model."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'sim': None, 'frame': 0}
    ns = _next_state(patch)
    model = Model(patch, mem)
    cnt = collections.Counter()
    WATCH = set(SITES_ORIG) | set(INTERIORS) | {b for v in STARTS.values() for b in v}
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

    def event(pc, real, R):
        get = lambda a: MG(real, a & 0xFFFF)
        if pc != C_PLOT and R[26]:
            fail('interrupts enabled at a hook site', (pc,))
        if pc in (A_PLOT, B_PLOT, C_PLOT):
            kind = 'A' if pc == A_PLOT else 'B' if pc == B_PLOT else 'C'
            if collect and c['collected %s' % kind] < collect:
                c['collected %s' % kind] += 1
                states.append((pc, list(R), [bytes(b) for b in real.banks], real.o7ffd, bytes(ns.scratch)))
            n0 = ns.scratch[V_N]
            exp = model.plot(kind, R, get)
            if exp is None:
                model.passthrough(kind)
            so, o, sp_, p, err = _pair(patch, get, R, ns, _ret(get, R), alt)
            c['T %s original' % kind] += so.registers[25] - R[25]
            c['T %s hook' % kind] += sp_.registers[25] - R[25]
            for e in err:
                fail('%s: %s' % (kind, e))
            for k in check_plot(kind, so, o, sp_, p, ns, n0, exp, model):
                fail('%s: %s' % (kind, k[0]), k[1:])
            c['%s converted' % kind if exp is not None else '%s passed through to the ULA' % kind] += 1
        elif pc == PAINT:
            last = ns.scratch[V_LAST]
            painted = model.paint(get)
            so, o, sp_, p, err = _pair(patch, get, R, ns, _ret(get, R), alt)
            for e in err:
                fail('61329: %s' % (e,))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            if diff:
                fail('61329: registers differ', (diff,))
            if bool(last) != painted:
                fail('61329: pending plot differs from the model', (last, painted))
            if painted:
                c['61329 after a converted plot (colour only)'] += 1
                md = [a for a in set(o.ov) | set(p.ov) if not _in(a, ATTRBUF) and o[a] != p[a]]
                if md or any(_in(a, ATTRBUF) for a in p.ov):
                    fail('61329: memory differs', (sorted(md)[:4],))
                got = ns.scratch[PL + 16 * (last - 1) + 6]
                if got != model.plots[last - 1]['colour']:
                    fail('61329: colour differs', (got, model.plots[last - 1]['colour']))
            else:
                c['61329 unchanged (ULA)'] += 1
                if o.ov != p.ov:
                    fail('61329: memory differs', ())
        elif pc in (COMMIT, RESTORE, CLEAR):
            what = {COMMIT: 'commit', RESTORE: 'restore', CLEAR: 'clear'}[pc]
            stops = {COMMIT: (47640,), RESTORE: (61093,), CLEAR: (47365,)}[pc]
            n = ns.scratch[V_N]
            if pc == COMMIT:
                want = model.image()
                c['max plots in a render'] = max(c['max plots in a render'], n)
            elif pc == RESTORE:
                model.restore()
            so, o, sp_, p, err = _pair(patch, get, R, ns, stops, alt)
            c['T %s hook' % what] += sp_.registers[25] - R[25]
            c['T %s max' % what] = max(c['T %s max' % what], sp_.registers[25] - R[25])
            for e in err:
                fail('%s: %s' % (what, e))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            if diff or o.ov != p.ov:
                fail('%s: registers/memory differ' % what, (diff, len(set(o.ov) ^ set(p.ov))))
            c[what + 's'] += 1
            if pc == COMMIT:
                img = shown(ns)
                if img != want:
                    bad = sum(1 for a, b in zip(img or bytes(len(want)), want) if a != b)
                    fail('commit: Layer 2 differs from the model', (bad,))
                c['Layer 2 pixels drawn'] += sum(1 for b in want if b)
                if ns.scratch[V_N] or ns.scratch[V_LAST]:
                    fail('commit: plot list not reset')
            elif pc == RESTORE and ns.scratch[V_N]:
                fail('restore: plot list not dropped')
            elif pc == CLEAR and ns.nr.get(0x69, 0) & 0x80:
                fail('clear: Layer 2 still on')

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            memory.__class__ = HookMem
            super().__init__(memory, registers, state_, config)
            st['sim'] = self
            R, mem_, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        if pc in SITES_ORIG:
                            event(pc, mem_, R)
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if progress and st['frame'] % 2000 == 0:
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
    for a, starts in STARTS.items():
        for b in starts:
            if cnt[b] != cnt[a]:
                c['%d reached other than from %d!' % (b, a)] += 1
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ------------------------------------------------------------------------------------- unit tests

def unit_tests(patch, states, mem, neg=None):
    """From captured plot states: x/y at the guard edges, every graphic of the kind (stored and
    mirrored in place, plus a changed byte = passthrough), the plot list full, a joined pair, a
    commit of the pair; a broken patch must FAIL (negative control)."""
    from .build import rom48
    from .rainbow import _BankMem
    rom = rom48()
    alt = _alt(patch)
    c = collections.Counter()
    canon = {(k, i): (g, d) for k, i, g, d in graphics(mem)}

    def one(pt, pc, R, banks, o7, scratch, xs, ys, gi, n, ori=0, poke=False, prev=None, nsx=None):
        kind = 'A' if pc == A_PLOT else 'B' if pc == B_PLOT else 'C'
        bm = _BankMem(banks, o7, rom)
        get0 = bm.__getitem__
        R = list(R)
        wr = {}
        g, d = canon[(kind, gi)]
        if kind == 'A':
            iy = R[10] * 256 + R[11]
            base = (get0(iy + 35) | get0(iy + 40) << 8)
            fr = ((g - base) // 128) & 255
            if not 0 <= g - base < 8 * 128:           # point the descriptor at the graphic
                wr[iy + 35], wr[iy + 40], fr = g & 255, g >> 8, 0
            wr[iy] = fr
            wr[iy + 5], wr[iy + 10] = xs, ys
        else:
            R[0] = gi
            wr[POS], wr[POS + 1] = xs, ys
        live = mirror(d) if ori else d
        for k, b in enumerate(live):
            wr[g + k] = b
        if poke:
            wr[g + 5] = live[5] ^ 0x10
        get = lambda a: wr[a] if a in wr else get0(a)
        ns = nsx or _next_state(pt)
        if nsx is None:
            ns.scratch[0:0x100] = scratch[0:0x100]      # run-time state only; code/tables from pt
            ns.scratch[V_N] = n
            ns.scratch[V_LAST] = 0
        model = Model(pt, mem)
        model.plots = list(prev or [dict(kind='-', x=0, y=0, caller=-1, joined=False)] * ns.scratch[V_N])
        n0 = ns.scratch[V_N]
        exp = model.plot(kind, R, get)
        so, o, sp_, p, err = _pair(pt, get, R, ns, _ret(get, R), alt)
        f = check_plot(kind, so, o, sp_, p, ns, n0, exp, model)
        guard = (ys < 64 or ys > (160 if kind == 'A' else 168) or xs > 240 or n0 >= MAXP or poke)
        conv = ns.scratch[V_N] != n0
        if conv == guard:
            f.append(('guard/convert mismatch', xs, ys, n0, poke))
        return err + f, conv, ns, model, exp

    def tally(kind, f, what=''):
        for k in f:
            c['%s%s: %s!' % (kind, what, k[0] if isinstance(k, tuple) else k)] += 1

    seen = set()
    for pc, R, banks, o7, scratch in states:
        kind = 'A' if pc == A_PLOT else 'B' if pc == B_PLOT else 'C'
        n_g = NA if kind == 'A' else NB if kind == 'B' else NC
        xs_l = (0, 1, 7, 8, 120, 223, 232, 239, 240, 241, 255)
        ys_l = (63, 64, 65, 100, 159, 160, 161) if kind == 'A' else (63, 64, 65, 100, 167, 168, 169)
        for xs in xs_l:
            for ys in ys_l:
                gi = (xs * 7 + ys) % n_g
                f, conv, *_ = one(patch, pc, R, banks, o7, scratch, xs, ys, gi, 0, ori=(xs + ys) & 1)
                c['cases'] += 1
                c['converted' if conv else 'passthrough'] += 1
                tally(kind, f)
        if kind in seen:
            continue
        seen.add(kind)
        for gi in range(n_g):                          # every graphic, both orientations, and a poke
            for ori, poke in ((0, False), (1, False), (0, True)):
                f, conv, *_ = one(patch, pc, R, banks, o7, scratch, 100, 100, gi, 3, ori=ori, poke=poke)
                c['graphic cases'] += 1
                tally(kind, f, ' graphic %d' % gi)
        for n in (MAXP - 1, MAXP):
            f, conv, *_ = one(patch, pc, R, banks, o7, scratch, 100, 100, 1, n)
            c['cases'] += 1
            c['full-list passthrough' if not conv else 'converted'] += 1
            tally(kind, f, ' full')
        if kind != 'A':                                 # a joined pair (another caller) + its commit
            f1, _, ns, m1, e1 = one(patch, pc, R, banks, o7, scratch, 100, 100, 12, 0)
            R2 = list(R)
            sp = R2[12]
            R2[12] = sp - 2                             # a different caller: return address below
            bm = _BankMem(banks, o7, rom)
            ret = bm[sp] | bm[sp + 1] << 8
            banks2 = [bytearray(b) for b in banks]
            for a, v in ((sp - 2, (ret + 3) & 255), (sp - 1, (ret + 3) >> 8)):
                banks2[(5, 2, o7 & 7)[(a >> 14) - 1]][a & 0x3FFF] = v
            f2, _, ns, m2, e2 = one(patch, pc, R2, banks2, o7, scratch, 100, 116, 13, 0, prev=m1.plots, nsx=ns)
            c['joined cases'] += 1
            if not (e2 and e2['joined']) or not ns.scratch[PL + 16 + 7] & 2:
                c['%s joined pair not joined!' % kind] += 1
            tally(kind, f1 + f2, ' joined')
            m2.plots = [e1, e2]
            want = m2.image()
            R3 = list(R)
            R3[24] = COMMIT
            so, o, sp_, p, err = _pair(patch, bm.__getitem__, R3, ns, (47640,), alt)
            c['commit cases'] += 1
            if err or shown(ns) != want:
                c['%s joined commit: Layer 2 differs!' % kind] += 1
        if neg is not None:
            f, conv, *_ = one(neg, pc, R, banks, o7, scratch, 100, 100, 1, 0)
            c['negative control detected' if f else 'negative control NOT detected!'] += 1
    # commit: clears what it drew two commits ago (no stale pixels), restore drops the list
    if states:
        pc, R, banks, o7, scratch = states[0]
        bm = _BankMem(banks, o7, rom)
        ns = _next_state(patch)
        ns.scratch[:] = patch.scratch
        model = Model(patch, mem)
        for rnd, pos in enumerate(((10, 70), (200, 150), (240, 168), (0, 64))):
            model.plots = []
            ns.scratch[V_N] = 0
            e = dict(kind='B', i=48, x=pos[0], y=pos[1], rows=18, colour=6, ori=rnd & 1, caller=1,
                     live=b'', joined=False)
            model.plots.append(e)
            pg, off = patch.where[('B', 48)]
            ns.scratch[PL:PL + 11] = bytes([pg, off & 255, off >> 8, pos[0], pos[1], 18, 6, rnd & 1, 1, 1, 0])
            ns.scratch[V_N] = 1
            want = model.image()
            R3 = list(R)
            R3[24] = COMMIT
            so, o, sp_, p, err = _pair(patch, bm.__getitem__, R3, ns, (47640,), alt)
            c['commit cases'] += 1
            if err or shown(ns) != want:
                c['commit round %d: Layer 2 differs (stale or missing pixels)!' % rnd] += 1
        R3 = list(R)
        R3[24] = RESTORE
        ns.scratch[V_N], ns.scratch[V_LAST] = 5, 3
        so, o, sp_, p, err = _pair(patch, bm.__getitem__, R3, ns, (61093,), alt)
        c['restore cases'] += 1
        if err or ns.scratch[V_N] or ns.scratch[V_LAST] or o.ov != p.ov:
            c['restore: plot list not dropped!'] += 1
    return c


def negative_patch(patch):
    """Broken copy: canvas pages with ink and outline codes swapped (canvas / image checks must fail)."""
    import copy
    q = copy.copy(patch)
    q.cpages = {}
    for p, b in patch.cpages.items():
        t = bytearray(b)
        for k, v in enumerate(t):
            if v & 0x60 == 0x20:
                t[k] = (v & 0x1F) ^ 0x60
            elif v & 0x60 == 0x40:
                t[k] = (v & 0x1F) ^ 0x60 | 0x10
        q.cpages[p] = bytes(t)
    return q


# ---------------------------------------------------------------------------------- recolour

RECOLOUR = {'game': 'everyones_a_wally_updated', 'output': 'sprites',
            'colours': 'docs/profiles/everyones_a_wally_updated_colours.json', 'clear': True,
            'note': 'figure colours live only in the canvas pages (banks 22 on), which the game never reads'}


def recolour(nex, cmap):
    """A built everyones_a_wally_updated sprites .nex + a colour map -> (the .nex with only the canvas
    banks rebuilt, info). Refuses a .nex that is not this engine's build of the expected snapshot:
    patch sites, hook pages, graphic tables (= the graphics), set-up code, empty Layer 2 banks."""
    from . import recolour as RC
    bk = RC.banks(nex)
    for b in (0, 2, 5, 10, 12, 13):
        if b not in bk:
            raise ValueError('not an everyones_a_wally_updated build: bank %d missing' % b)
    mem = bytearray(16384) + bytearray(bk[5] + bk[2] + bk[0])
    if not identify(mem):
        raise ValueError("not Everyone's a Wally (signature)")
    p0 = Wally2Patch(mem, Config(colours={}))
    for a, old, new in p0.sites:
        if bytes(mem[a:a + len(new)]) != new:
            raise ValueError("patch site %d does not hold this build's hook jump" % a)
    for b in (12, 13) + tuple(range(16, 22)):
        if bk.get(b) != p0.extra_banks[b]:
            raise ValueError('bank %d differs from this version\'s hook / table / Layer 2 bank (rebuild with nexclash.py auto)' % b)
    if bk[10][0x1000:0x1000 + len(p0.stub_extra)] != p0.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    p = Wally2Patch(mem, Config(colours=cmap))
    out = {b: p.extra_banks[b] for b in sorted({x // 2 for x in p.cpages})}
    d, changed = RC.splice(nex, out)
    return d, {'banks changed': changed, 'canvas pages': len(p.cpages), 'map entries': len(cmap),
               'graphics md5': p.gfx_md5}


# --------------------------------------------------------------------- colour sheets + preview

def default_colour(d, code):
    if code != 1:
        return CBLACK
    return d['colour']


def sheet_part(d, canon):
    """A plot (capture) -> coloursheet part over the whole canvas (paint_clear)."""
    g, data = canon[(d['k'], d['i'])]
    rows = geometry(d['k'])[0] + 2
    pix = [(cx, cy, key, bit, code, default_colour(d, code) if code else 0)
           for cx, cy, key, bit, code in pixels(d['k'], g, data)]
    return dict(id=(d['k'], g), size=rows, w=W, h=rows, x=d['x'] - 1, y=d['y'] - 1, mir=d['ori'], vmir=0,
                group=d['group'], role=d.get('caller'), pixels=pix, entries=entries_of(d['k'], g, data))


class Capture:
    """simrun hooks: every plot the build converts (the Model's rules), per render, with the clean
    buffer at the render's first plot and the composed one at the commit (preview)."""

    def __init__(self, patch, mem, keep_screens=()):
        self.model = Model(patch, mem)
        self.sim = None
        self.frame = 0
        self.cur = []
        self.clean = None
        self.renders = []
        self.keep = set(keep_screens)
        self.calls = collections.Counter()
        self.passed = collections.Counter()
        self.dropped = 0

    def on_sim(self, sim):
        self.sim = sim

    def on_frame(self, n):
        self.frame = n

    def _bufs(self, g):
        return (bytes(g(BUF[0] + i) for i in range(BUF[1] - BUF[0])),
                bytes(g(ATTRBUF[0] + i) for i in range(ATTRBUF[1] - ATTRBUF[0])),
                bytes(g(0x4000 + i) for i in range(6912)))

    def before(self, pc):
        if pc not in (A_PLOT, B_PLOT, C_PLOT, PAINT, COMMIT, RESTORE):
            return
        R, m = self.sim.registers, self.sim.memory
        g = lambda a: m[a & 0xFFFF]
        want = len(self.renders) in self.keep
        if pc == RESTORE:
            self.dropped += len(self.model.plots)
            self.model.restore()
            self.cur, self.clean = [], None
            return
        if pc in (A_PLOT, B_PLOT, C_PLOT):
            kind = 'A' if pc == A_PLOT else 'B' if pc == B_PLOT else 'C'
            if not self.model.plots and want and self.clean is None:
                self.clean = self._bufs(g)
            caller = (g(R[12]) | g(R[12] + 1) << 8) - 3
            self.calls[(kind, caller)] += 1
            e = self.model.plot(kind, R, g)
            if e is None:
                self.model.passthrough(kind)
                self.passed[(kind, caller)] += 1
            else:
                e = dict(e, k=kind, caller=caller, group=GROUPS['ABC'.index(kind)])
                self.model.plots[-1] = e
        elif pc == PAINT:
            self.model.paint(g)
        elif pc == COMMIT:
            plots = list(self.model.plots)
            img = self.model.image()
            self.renders.append(dict(frame=self.frame, plots=plots, clean=self.clean if want else None,
                                     done=self._bufs(g) if want else None, image=img if want else None))
            self.clean = None


def static_frames(mem):
    """Frames the code passes to B / C as a constant (walk back from each CALL over instructions that
    keep A to an LD A,n). -> {('B'|'C', caller): frame}."""
    keep = {0x01, 0x11, 0x21, 0x22, 0x2A, 0xC5, 0xD5, 0xE5}
    out = {}
    for kind, callers in (('B', B_CALLERS), ('C', C_CALLERS)):
        for c in callers:
            a, n = c, 0
            while n < 6:
                n += 1
                if mem[a - 2] == 0x3E:
                    out[(kind, c)] = mem[a - 1]
                    break
                if mem[a - 3] == 0xCD and mem[a - 2] | mem[a - 1] << 8 == 61237:
                    a -= 3
                    continue
                if mem[a - 3] in keep:
                    a -= 3
                    continue
                if mem[a - 4] == 0xDD and mem[a - 3] == 0x21:
                    a -= 4
                    continue
                break
    return out


def capture(rzx, z80, patch=None, stop=None, keep_screens=()):
    from . import simrun
    mem = _mem_of(z80)
    patch = patch or Wally2Patch(mem)
    cap = Capture(patch, mem, keep_screens)
    simrun.run(z80, [rzx] if isinstance(rzx, str) else list(rzx), cap, stop=stop)
    return cap


def collect(cap, z80):
    """Capture -> coloursheet composites (+ the constant-frame figures no recording drew)."""
    from . import coloursheet as cs
    mem = _mem_of(z80)
    canon = {(k, i): (g, d) for k, i, g, d in graphics(mem)}
    col = cs.Collector(family=lambda p: None if p['id'][0] == 'A' else p['id'][0])
    for r in cap.renders:
        col.add_frame([sheet_part(d, canon) for d in r['plots']])
    seen = {p['id'] for cm in col.comps.values() for p in cm['parts']}
    for (k, caller), fr in sorted(static_frames(mem).items()):
        if fr >= (NB if k == 'B' else NC):
            continue
        g = GFX + fr * 32
        if (k, g) in seen:
            continue
        seen.add((k, g))
        p = sheet_part(dict(k=k, i=fr, x=1, y=1, ori=0, colour=7, caller=caller, group=GROUPS[3]), canon)
        col.comps[('static', k, fr)] = dict(count=0, group=GROUPS[3], parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)])
        col.maxsize[p['id']] = p['size']
    return col.composites(list(GROUPS))


def rgb16():
    from . import coloursheet as cs
    return cs.palette_rgb(PALETTE)


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def sheets(comps, prefix, colours=None):
    """<prefix>_PAINTING_SPRITES.png (every graphic once; + _layout.json, read back) and
    <prefix>_REFERENCE_ALL_SPRITES.png (every figure whole). Outlines paintable (paint_clear)."""
    from . import coloursheet as cs
    out = []
    for suffix, uniq in (('_PAINTING_SPRITES', True), ('_REFERENCE_ALL_SPRITES', False)):
        png = prefix + suffix + '.png'
        n = cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', rgb16(), colours, unique=uniq,
                     paint_clear=True)
        out.append((png, n))
    return out


def read_sheet(png, layout_path):
    from . import coloursheet as cs
    return cs.read(png, layout_path, clear=True)


def save_colours(ent, path=COLOURS):
    from . import coloursheet as cs
    cs.save(ent, path, NOTE)


def _ula_rgb(attr, on):
    pal = rgb16()
    ink, paper, br = attr & 7, (attr >> 3) & 7, (attr >> 6) & 1
    c = ink if on else paper
    return pal[cidx(c, br)] if c else (0, 0, 0)


def _screen_img(bufs, img, ox):
    buf, attrs, scr = bufs
    for y in range(192):
        for xb in range(32):
            if y < 64:
                a = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | xb
                v, at = scr[a], scr[6144 + (y >> 3) * 32 + xb]
            else:
                v, at = buf[(y - 64) * 32 + xb], attrs[((y - 64) >> 3) * 32 + xb]
            for b in range(8):
                img.putpixel((ox + xb * 8 + b, y), _ula_rgb(at, v & (0x80 >> b)))


def preview(cap, indexes, png):
    """Per shot: the original | the build (clean ULA + the model's Layer 2 image on top). 2x."""
    from PIL import Image
    pal = rgb16()
    shots = [cap.renders[i] for i in indexes if i < len(cap.renders) and cap.renders[i]['done']
             and cap.renders[i]['clean']]
    img = Image.new('RGB', (520, 196 * len(shots)), (40, 40, 40))
    for n, r in enumerate(shots):
        sub = Image.new('RGB', (520, 192), (40, 40, 40))
        _screen_img(r['done'], sub, 0)
        _screen_img(r['clean'], sub, 264)
        for i, v in enumerate(r['image']):
            if v:
                sub.putpixel((264 + (i & 255), i >> 8), pal[v])
        img.paste(sub, (0, 196 * n))
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    img.save(png)
    return len(shots)


def report(cap):
    lines = []
    for k, callers in (('A', A_CALLERS), ('B', B_CALLERS), ('C', C_CALLERS)):
        seen = {c for (kk, c) in cap.calls if kk == k}
        lines.append('%s: %d plots (%d passed through), %d of %d callers in the recording; not reached: %s' % (
            k, sum(n for (kk, _), n in cap.calls.items() if kk == k),
            sum(n for (kk, _), n in cap.passed.items() if kk == k), len(seen & set(callers)), len(callers),
            ' '.join(str(c) for c in callers if c not in seen) or '-'))
    lines.append('plots wiped by a buffer restore before any commit (never shown): %d' % cap.dropped)
    return lines


# ------------------------------------------------------------------------------------- auto

def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    say('Game      : %s' % name)
    say("Engine    : wally2 (Everyone's a Wally, updated: every figure on Layer 2, outlined)")
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, TAIL_ADDR, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = back buffer, write-first in the reference RZX)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    mem = _mem_of(z80)
    patch = Wally2Patch(mem)
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch)
    say('Sprites   : %s  %s  boot %s  (%d canvas pages, %d painted keys)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200],
        len(patch.cpages), len(patch.cfg.colours)))
    ok = not bad and not bad2
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
        c, ex, st = verify(patch, r, mem, stop=getattr(a, 'quick', None), collect=4)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, A %d, B %d, C %d converted (%d passed through), %d commits '
            '(max %d plots), %d restores, %d clears, %d Layer 2 pixels -> %s' % (
                os.path.basename(r), c['frames'], c['A converted'], c['B converted'], c['C converted'],
                sum(v for k, v in c.items() if 'passed through' in k), c['commits'],
                c['max plots in a render'], c['restores'], c['clears'], c['Layer 2 pixels drawn'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        say('Speed     : simulator T (all of it counted at 3.5 MHz; the hooks run at 28 MHz, ~1/8): '
            'plots A/B/C original %d / %d / %d, hook %d / %d / %d; commit hook mean %d, max %d T per render' % (
                c['T A original'], c['T B original'], c['T C original'], c['T A hook'], c['T B hook'],
                c['T C hook'], c['T commit hook'] // max(1, c['commits']), c['T commit max']))
    if states:
        u = unit_tests(patch, states, mem, negative_patch(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d cases (%d converted, %d passthrough), %d graphic cases, %d joined, %d commit, '
            '%d restore cases, negative control %d/%d -> %s' % (
                u['cases'], u['converted'], u['passthrough'] + u['full-list passthrough'], u['graphic cases'],
                u['joined cases'], u['commit cases'], u['restore cases'], u['negative control detected'],
                len({s[0] for s in states}), 'PASS' if not uf else 'FAIL %s' % uf))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.wally2',
                                 description="Everyone's a Wally (updated): colour sheets, read-back, preview")
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX -> the two sheets + layout JSON (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', required=True)
    p.add_argument('-o', '--output', default='everyones_a_wally_updated')
    p.add_argument('--preview', help='also write preview frames (PNG) at these renders, e.g. 100,800,2000')
    p.add_argument('--stop', type=int)
    p = sub.add_parser('colours', help='painted sheet -> docs/profiles/everyones_a_wally_updated_colours.json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--output', default=COLOURS)
    a = ap.parse_args(argv)
    if a.cmd == 'sheet':
        idx = [int(x) for x in a.preview.split(',')] if a.preview else []
        cap = capture(a.rzx, a.z80, stop=a.stop, keep_screens=idx)
        for line in report(cap):
            print(line)
        comps = collect(cap, a.z80)
        for png, n in sheets(comps, a.output, load_colours()):
            print('%d figures -> %s' % (n, png))
        if idx:
            n = preview(cap, idx, a.output + '_preview.png')
            print('%d shots -> %s_preview.png' % (n, a.output))
    else:
        lay = a.layout or os.path.splitext(a.png)[0] + '_layout.json'
        ent, rep = read_sheet(a.png, lay)
        save_colours(ent, a.output)
        for k, v in sorted(rep.items()):
            print('%s: %d' % (k, v))
        print('-> %s' % a.output)


if __name__ == '__main__':
    _main()
