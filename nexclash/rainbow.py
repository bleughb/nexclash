"""Rainbow Islands (128K) engine: every figure drawn by the game's sprite-list walker becomes Next
hardware sprites (engine 'rainbow'). Additive module: reachable only through identify_rb().

Game facts (verified by the 128K analysis passes over Dean's two recordings):
  renderer 58851 re-blits the whole 176-line play area from a back buffer (0x9F00) every game frame,
  then the list walker 59504 (list IY=0x6D3C, descriptors 0xB800+code-6, dispatch 59539 JP (IX))
  draws each piece (<= 24 x 8 px, one char-row band) with unrolled masked AND/OR plotters that all
  end with JP 59543. Erase = the next frame's blit. No game logic reads screen pixels.
  The walker runs with interrupts disabled and SP pointing into graphics data.
Hooks: alt ROM stubs at 0x386E map Next RAM page 26 at slot 0, which holds the hook bodies, state,
canvases and tables (asm/rainbow_hooks.asm). Each piece is drawn by the ORIGINAL plotter twice
into canvases (0x00 -> ink, 0xFF -> mask|ink); columns E-2..E+5 become four 4-bit patterns shown as
sprites 4n..4n+3 (empty ones hidden); the render end (59087) hides the sprites left over from the previous frame. The walker is called
once per 8-line band from inside the blit, so the piece counter is reset at render start (58851).
"""
import collections
import json
import os

PAGE_S = 26                 # Next RAM page (bank 13 lower half): hook bodies, state, tables
PAGE_T = 27                 # plotter layout tables (bank 13 upper half), slot 1 while converting
PAGE_C1, PAGE_C2 = 28, 29   # canvas page 29 (bank 14) over the screen for the register run
STORE_PG, STORE_PAGES = 32, 32   # pattern store: Next pages 32-63 (256K), slot 1 during lookup
ALT_PAGE = 24               # alt ROM copy source (bank 12), as for the other altrom builds
ROM_ORG = 0x386E
PAGE_ORG = 0x0100
NIBTAB, CLASSTAB, MIRTAB, PI = 0x1000, 0x1200, 0x0F00, 0x1300     # asm: same names
CODE_END_MAX = 0x0D00       # WBG conversion buffer starts here
V_S, V_FRM, V_HITS = 0x00, 0x24, 0x2A
NSPR_MAX = 128
TAIL_ADDR = 0x9F00          # back buffer: write-first in both of Dean's recordings
MAXP = 32
SITES_ORIG = {58851: bytes.fromhex('FD213C6D'), 59539: bytes.fromhex('26F5DDE9'),
              59543: bytes.fromhex('A7C279E8'), 59087: bytes.fromhex('3AE2E5'),
              65172: bytes.fromhex('3A80BE'), 65274: bytes.fromhex('F1FBC9'),   # IM2 handler
              65029: bytes.fromhex('CD925C'), 65076: bytes.fromhex('CD5B5C'),   # main loop: sprites off
              60853: bytes.fromhex('876F2600'), 60839: bytes.fromhex('3D6F2600'),  # cell drawer: base tile,
              60965: bytes.fromhex('3D878787'),                                     # full overlay, masked item
              59547: bytes.fromhex('2A82E8')}                                       # walker: band done
# music (bank 1, 2026-10-19): AY player entry (a tick starts) and the one AY register-write routine
SITES1_ORIG = {0xD4DE: bytes.fromhex('21595C'), 0xD6D4: bytes.fromhex('01FDFF')}
V_AYR, V_AYN, V_AYO, V_AYW, AYQ = 0x82, 0x83, 0x84, 0x85, 0x1FC0
CLIST, ATTRB, V_NP = 0x1B00, 0x1C80, 0x01
V_TICK, LIMIT = 0x2E, 3     # frame limiter (asm s_lim)
# Objects (2026-10-11, tilemap build): every object the game puts in a back-buffer cell (rainbow
# pieces = codes 1-14 of both drawers, fruit / flowers / collectables = opaque codes >= 15) is shown on
# the tilemap layer (bank 7 = Next page 14, in front of the ULA, behind the sprites); the ULA cell shows
# the cell's map tile. Per-cell arrays in page 27 (slot 1), cell i = 32k + col at base + i.
TILES, OBJO, OBJM1, OBJM2, FLAGS, CTILE = 0x2800, 0x2B00, 0x2E00, 0x3100, 0x3400, 0x3700
KEYS, STAMP, RCNT, MCLASS, OCLASS, BGOVR = 0x3A00, 0x3D00, 0x3DC0, 0x3DE0, 0x3E00, 0x3F00
NCELLS, NTILE, PAGE_TM, TDEF, X2 = 704, 176, 14, 0x0A00, 0x1F00
OCCM, BITS = 0x27A0, 0x1F08   # page 27: occupied cells per row as 32-bit masks; page 26: 0x80 >> n
V_DIAG, V_FRUN = 0x72, 0x73   # diagnostic build flag; a game frame is running (diagnostic)
PBUF = 0x0EE6                 # page 26: rows of the object being drawn (+1..+8; +0 / +9 stay 0)
V_PEND, V_N58 = 0x80, 0x81    # commit deferred to the next interrupt; (58850) at the render end
V_TOK, V_MSB, V_MSD, V_FMAX = 0x3B, 0x3F, 0x40, 0x51
PAGE_SH, LASTT = 28, 0x0600   # shadow map (row kk at kk*64, 2 bytes per column), last tile per cell
CODE2 = 0x1F10              # fourth page-26 code block (tile drawing), up to 0x1FFF
CODE4 = 0x0D60              # third page-26 code block (object classes, inks), up to 0x0DFF
CODE3 = 0x0E60              # second page-26 code block (raster wait, tilemap commit), up to 0x0EFF
OBJ_SITES = {60853: 60857, 60839: 60843, 60965: 60969}      # hook site -> resume address
LINE_T = 1792               # T-states per video line at 28 MHz (224 * 8)
PLAY_TOP, PLAY_END = 16, 176   # video lines of the play area (rows 0-159 of the ULA picture + 16)
ITEM_PAL = 15               # sprite palette offset 15: Spectrum inks (kept; objects now use the tilemap)
TILE_PAL = (0x00, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF)
SPECTRUM_INK = (0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6)
SPECTRUM_INK_BRIGHT = (0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF)
SIG = None                  # walker head bytes: profile 'signature'

# 4-wide zig-zag plotters entered on a leftward row write columns E-3..E (every other dispatch target
# writes within E-2..E+5): the hook shifts their window one byte left (asm s_pc, V_OFF). Found from
# Dean's hardware video of the Insect Island boss (2026-09-29); neither verified RZX reaches them.
LEFT4 = (59906, 59951, 59996, 60041)


def window_off(ix):
    """Window start = E - window_off(ix); the window is 8 bytes (4 sprites)."""
    return 3 if ix in LEFT4 else 2


def plotter_extents(peek):
    """Column extent (lo, hi) relative to E of every dispatch target in the 0xF300 table, measured
    by running the ORIGINAL plotter from a mid-screen address with both AF' carry values."""
    from skoolkit.simulator import Simulator
    base = bytearray(peek[a] for a in range(65536))
    targets = sorted({base[a] | base[a + 1] << 8 for a in range(0xF300, 0xF400, 2)})
    ext = {}
    for t in targets:
        if not 59567 <= t < 60200:              # table words that are not plotter code
            continue
        cols = set()

        class W(list):                          # records every write address
            def __setitem__(s, a, v):
                s.w.add(a)
                list.__setitem__(s, a, v)
        for cy in (0, 1):
            m = W(base)
            m.w = set()
            sim = Simulator(m, {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
            R = sim.registers
            R[16], R[17] = 0, cy
            if not _run(sim, (59543,), 5000):
                raise ValueError('plotter %d did not return' % t)
            cols |= {(a & 31) - 8 for a in m.w if 0x4000 <= a < 0x5800}
        ext[t] = (min(cols), max(cols))
    return ext


def plotter_layouts(peek):
    """For every plotter entry: window offset (off = -leftmost column), sprites (nspr = columns/2
    rounded up), stream length per AF' carry, and a layout table per carry: one byte per stream
    byte = target row*6 + column in the window (bits 5-0), bit 6 = mirrored (table page 245),
    bit 7 = mask byte. Derived by running the ORIGINAL plotter with single-bit streams."""
    from skoolkit.simulator import Simulator
    base = bytearray(peek[a] for a in range(65536))
    ext = plotter_extents(peek)
    lens = plotter_stream_lengths(peek)
    out = {}

    def run(t, cy, stream, fill):
        m = bytearray(base)
        m[0x4000:0x5800] = bytes([fill]) * 0x1800
        m[0x8000:0x8000 + len(stream)] = stream
        sim = Simulator(m, {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
        sim.registers[17] = cy
        if not _run(sim, (59543,), 5000):
            raise ValueError('plotter %d did not return' % t)
        return m
    for t, (lo, hi) in ext.items():
        if t not in lens:
            continue
        off, nspr = -lo, (hi - lo + 2) // 2
        lay = []
        for cy in (0, 1):
            n = lens[t][cy]
            b0, bf = run(t, cy, bytes(n), 0), run(t, cy, bytes(n), 0xFF)
            tb = bytearray()
            for j in range(n):
                st = bytearray(n)
                st[j] = 1
                m0, mf = run(t, cy, st, 0), run(t, cy, st, 0xFF)
                d0 = [a for a in range(0x4000, 0x5800) if m0[a] != b0[a]]
                df = [a for a in range(0x4000, 0x5800) if mf[a] != bf[a]]
                if d0:
                    role, (a,), v = 0, d0, m0[d0[0]]
                elif df:
                    role, (a,), v = 1, df, mf[df[0]] ^ bf[df[0]]
                else:
                    raise ValueError('plotter %d byte %d has no effect' % (t, j))
                if v not in (1, 0x80):
                    raise ValueError('plotter %d byte %d: value %02X' % (t, j, v))
                row, col = (a >> 8) - 0x48, (a & 31) - 8 + off
                if not (0 <= row <= 9 and 0 <= col < 2 * nspr):
                    raise ValueError('plotter %d byte %d outside window (%d, %d)' % (t, j, row, col))
                tb.append((row * 6 + col) | (0x40 if v == 0x80 else 0) | (role << 7))
            lay.append(bytes(tb))
        if max(lens[t]) > 256 - 64 * nspr - 8:
            raise ValueError('plotter %d stream too long for its store entry' % t)
        out[t] = {'off': off, 'nspr': nspr, 'len': lens[t], 'layout': [x.hex() for x in lay]}
    return out


def layout_convert(info, cy, stream, row0=0):
    """Python model of the hook's direct conversion -> (G, MG) as {(row, col): byte}."""
    G, M = {}, {}
    rev = [int('{:08b}'.format(i)[::-1], 2) for i in range(256)]
    for j, tb in enumerate(bytes.fromhex(info['layout'][cy])):
        v = stream[j]
        if tb & 0x40:
            v = rev[v]
        k = divmod(tb & 0x3F, 6)
        if tb & 0x80:
            M[k] = M.get(k, 0xFF) & 0 | v | G.get(k, 0)
        else:
            G[k] = v
            M[k] = M.get(k, 0xFF) | v
    return G, M


def plotter_stream_lengths(peek):
    """Graphics stream bytes consumed by every plotter entry (SP advance), AF' carry clear / set."""
    from skoolkit.simulator import Simulator
    base = bytearray(peek[a] for a in range(65536))
    out = {}
    for t in sorted({base[a] | base[a + 1] << 8 for a in range(0xF300, 0xF400, 2)}):
        if not 59567 <= t < 60176:
            continue
        ln = []
        for cy in (0, 1):
            sim = Simulator(bytearray(base), {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
            sim.registers[17] = cy
            if not _run(sim, (59543,), 5000):
                raise ValueError('plotter %d did not return' % t)
            ln.append(sim.registers[12] - 0x8000)
        out[t] = ln
    return out


COLOURS = {'white': 0xFF, 'black': 0x00, 'blue': 0x03, 'transparent': None}

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'rainbow_islands.json'),
              os.path.join(_HERE, 'rainbow_islands.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('rainbow_islands.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def colour(v):
    """'white' | 'black' | 'blue' | 'transparent' | '#RRGGBB' -> RRRGGGBB byte (None = transparent)."""
    v = v.strip().lower()
    if v in COLOURS:
        return COLOURS[v]
    if v.startswith('#') and len(v) == 7:
        r, g, b = int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)
        return (r >> 5) << 5 | (g >> 5) << 2 | (b >> 6)
    raise ValueError('unknown colour %r (white, black, blue, transparent or #RRGGBB)' % v)


class Config:
    """Colour selection. ink/outline apply to palette offset 0 (and every class without its own
    entry); class_colours = {'pages': {'D6': 1, ...}, 'palettes': {'1': {'ink': .., 'outline': ..}}}
    maps graphics-address high bytes to palette offsets 1-15 (the per-class hook; off by default)."""

    def __init__(self, ink='white', outline='black', class_colours=None, diag=False):
        self.diag = diag                # diagnostic build: border colours (rainbow_sprites_diag.nex)
        self.ink, self.outline = colour(ink), colour(outline)
        if self.ink is None:
            raise ValueError('ink cannot be transparent')
        self.cls = class_colours or {'pages': {}, 'palettes': {}}
        self.transparent_outline = self.outline is None
        for k, p in self.cls.get('palettes', {}).items():
            if 'outline' in p and self.transparent_outline and colour(p['outline']) is not None:
                raise ValueError('with outline transparent everywhere, a class cannot have one')

    def no_outline(self, page):
        """True = figures from this graphics page are drawn without outline (their class's palette
        says outline transparent; the piece hook drops outline pixels, CLASSTAB bit 0)."""
        if self.transparent_outline:
            return True
        off = self.cls.get('pages', {}).get('%02X' % page)
        p = self.cls.get('palettes', {}).get(str(off), {}) if off is not None else {}
        return 'outline' in p and colour(p['outline']) is None

    def nibtab(self):
        """(G nibble << 4 | MG nibble) -> 2 bytes of 4-bit pixels: 1 ink, 0 transparent, 2 outline."""
        out = 0 if self.transparent_outline else 2
        t = bytearray(512)
        for i in range(256):
            g, m = i >> 4, i & 15
            px = []
            for b in (8, 4, 2, 1):
                px.append(1 if g & b else (0 if m & b else out))
            t[i] = px[0] << 4 | px[1]
            t[256 + i] = px[2] << 4 | px[3]
        return bytes(t)

    def classtab(self):
        t = bytearray(256)
        for page, off in self.cls.get('pages', {}).items():
            off = int(off)
            if not 0 <= off <= 14:
                raise ValueError('palette offset must be 0-14 (15 = item sprites)')
            t[int(page, 16)] = off << 4 | (1 if self.no_outline(int(page, 16)) and not self.transparent_outline
                                            else 0)
        return bytes(t)

    def tile_palette(self):
        """Tilemap palette, 16 banks of 16 (setup): bank 0 = 0 transparent, 1 black, 2-8 inks 1-7, 9-15
        bright inks 1-7; bank n = bank 0 with pixel 2 = ink index n (one-ink tiles: the map entry's
        palette offset is the ink) and pixel 3 = the contrast colour of ink n (collectables' insides):
        bright white for black / blue / red / magenta, black for the others."""
        out = bytearray()
        for n in range(16):
            b = bytearray(TILE_PAL)
            if n:
                b[2] = TILE_PAL[n]
                b[3] = 0xFF if fill_white(n) else 0x00
            out += b
        return bytes(out)

    def palette(self):
        pal = bytearray(256)
        for k in range(16):
            p = self.cls.get('palettes', {}).get(str(k), {})
            ink = colour(p['ink']) if 'ink' in p else self.ink
            outl = colour(p['outline']) if 'outline' in p else self.outline
            pal[16 * k + 1] = ink
            pal[16 * k + 2] = 0 if outl is None else outl
        b = 16 * ITEM_PAL                       # item sprites: 1 black (outline / black ink),
        pal[b + 1] = 0x00                       # 2-8 ink 1-7, 9-15 bright ink 1-7
        pal[b + 2:b + 9] = bytes(SPECTRUM_INK)
        pal[b + 9:b + 16] = bytes(SPECTRUM_INK_BRIGHT)
        return bytes(pal)


def _code_range(spec):
    """'5' or '1-14' -> range of codes."""
    a, _, b = str(spec).partition('-')
    return range(int(a), int(b or a) + 1)


def object_tables(objs):
    """Profile 'objects' section -> (OCLASS 256, MCLASS 16, BGOVR 256). Per code (ranges allowed),
    under "opaque" (60839 codes) or "masked" (60965 codes 1-14): "group": "rainbow" (drawn behind the
    others, ink = the cell's) or "item" (default); "ula": true (the cell stays as the game draws it);
    "border": false (no black border); "ink": 0-7 and "bright": true/false (fixed colour).
    "background": {"tile": tile} shows another map tile under objects."""
    tabs = {'opaque': bytearray(256), 'masked': bytearray(16)}
    for kind, tab in tabs.items():
        for spec, o in objs.get(kind, {}).items():
            if spec.startswith('_'):
                continue
            v = 0
            if o.get('group', 'item') == 'rainbow':
                v |= 1
            if o.get('ula'):
                v |= 2
            if o.get('border', True) is False:
                v |= 4
            if 'ink' in o:
                v |= ink_index(int(o['ink']) | (64 if o.get('bright') else 0)) << 4
            for code in _code_range(spec):
                if code >= len(tab):
                    raise ValueError('object code out of range: %s %d' % (kind, code))
                tab[code] = v
    bg = bytearray(range(256))
    for t, u in objs.get('background', {}).items():
        if not str(t).startswith('_'):
            bg[int(t)] = int(u)
    return bytes(tabs['opaque']), bytes(tabs['masked']), bytes(bg)


PAGE_F, FILLM, FILLC = 25, 0x0000, 0x0600     # page 25 offsets (slot 1: 0x2000 / 0x2600)
FILL_CODES = range(15, 191)


def fill_white(ink):
    """Ink index (1 black, 2-8 inks 1-7, 9-15 bright) -> True = white inside (dark ink)."""
    return (ink - 7 if ink >= 8 else ink) < 5


def fill_page(prof):
    """Page 25: FILLM per opaque code 15-190 (8 bytes: the enclosed paper, profile `fills`), FILLC per
    code (inside colour as a pixel byte; 0 = automatic, from the profile `objects` "fill": "white" /
    "black" / "none")."""
    pg = bytearray(8192)
    for code, m in prof.get('fills', {}).items():
        if not str(code).startswith('_'):
            c = int(code)
            if c in FILL_CODES:
                pg[FILLM + 8 * (c - 15):FILLM + 8 * (c - 15) + 8] = bytes.fromhex(m)
    for spec, o in prof.get('objects', {}).get('opaque', {}).items():
        if str(spec).startswith('_') or 'fill' not in o:
            continue
        for c in _code_range(spec):
            if o['fill'] == 'none':
                if c in FILL_CODES:
                    pg[FILLM + 8 * (c - 15):FILLM + 8 * (c - 15) + 8] = bytes(8)
            else:
                pg[FILLC + c] = {'white': 0xFF, 'black': 0x11}[o['fill']]
    return bytes(pg)


def obj_fill(fpage, code):
    """(inside mask rows, FILLC byte) of an opaque code, or None."""
    if code not in FILL_CODES:
        return None
    m = fpage[FILLM + 8 * (code - 15):FILLM + 8 * (code - 15) + 8]
    return (list(m), fpage[FILLC + code]) if any(m) else None


def identify_rb(mem):
    """mem: 64K view with bank 0 at C000. True if the Rainbow Islands list walker is present."""
    sg = load_profile()['signature']
    a, sig = sg['addr'], bytes.fromhex(sg['bytes'])
    return bytes(mem[a:a + len(sig)]) == sig


class RainbowPatch:
    name = 'Rainbow Islands sprite-list walker -> hardware sprites (altrom + RAM page 26)'

    def __init__(self, cfg=None, prof=None):
        self.cfg = cfg or Config()
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.page_code = bytes.fromhex(h['page'])
        self.page_code3 = bytes.fromhex(h.get('page3', ''))
        self.page_code4 = bytes.fromhex(h.get('page4', ''))
        self.page_code2 = bytes.fromhex(h.get('page2', ''))
        self.setup = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = self.setup + self.cfg.palette() + self.cfg.tile_palette()
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 64
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
        self.page = bytes(page)                     # alt ROM image of 0x2000-0x3FFF (for nextboot)
        sp = bytearray(8192)
        sp[PAGE_ORG:PAGE_ORG + len(self.page_code)] = self.page_code
        if CODE3 + len(self.page_code3) > PBUF:
            raise ValueError('second code block too long')
        sp[CODE3:CODE3 + len(self.page_code3)] = self.page_code3
        if CODE4 + len(self.page_code4) > 0x0E00:
            raise ValueError('fourth code block too long')
        sp[CODE4:CODE4 + len(self.page_code4)] = self.page_code4
        if CODE2 + len(self.page_code2) > AYQ:
            raise ValueError('code block at 0x1F10 too long')
        sp[CODE2:CODE2 + len(self.page_code2)] = self.page_code2
        if PAGE_ORG + len(self.page_code) > CODE_END_MAX or ATTRB + 5 * NSPR_MAX > X2:
            raise ValueError('page code overlaps the conversion buffers')
        sp[V_FRM] = 1
        sp[V_FMAX] = NSPR_MAX                       # figure sprite limit
        sp[V_MSB] = sp[V_MSD] = 0xFF                # no tilemap built yet
        sp[X2:X2 + 4] = b'\x00\x0F\xF0\xFF'          # 2 bits -> 2 nibbles (tile composer)
        sp[BITS:BITS + 8] = bytes(0x80 >> n for n in range(8))
        sp[V_DIAG] = 1 if self.cfg.diag else 0
        tp = bytearray(8192)                        # page 27: layout tables (slot 1 = 0x2000)
        at = 0
        self.plot = {int(k): v for k, v in self.prof['plotters'].items()}
        for t, pi in sorted(self.plot.items()):
            sp[PI + (t & 255)] = t >> 8
            sp[PI + 0x100 + (t & 255)] = pi['off'] | pi['nspr'] << 4
            for cy in (0, 1):
                lay = bytes.fromhex(pi['layout'][cy])
                sp[PI + 0x200 + 0x100 * cy + (t & 255)] = len(lay)
                a = 0x2000 + at
                sp[PI + 0x400 + 0x200 * cy + (t & 255)] = a & 255
                sp[PI + 0x500 + 0x200 * cy + (t & 255)] = a >> 8
                tp[at:at + len(lay)] = lay
                at += len(lay)
        if at > OCCM - 0x2000:
            raise ValueError('layout tables overlap the object masks in page 27')
        sp[MIRTAB:MIRTAB + 256] = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))
        sp[NIBTAB:NIBTAB + 512] = self.cfg.nibtab()
        sp[CLASSTAB:CLASSTAB + 256] = self.cfg.classtab()
        ocls, mcls, bg = object_tables(self.prof.get('objects', {}))
        tp[OCLASS - 0x2000:OCLASS - 0x2000 + 256] = ocls
        tp[MCLASS - 0x2000:MCLASS - 0x2000 + 16] = mcls
        tp[BGOVR - 0x2000:BGOVR - 0x2000 + 256] = bg
        self.scratch = bytes(sp)
        self.tpage = bytes(tp)
        self.fpage = fill_page(self.prof)
        self.extra_banks = {12: self.page + self.fpage, 13: self.scratch + self.tpage}
        s = self.syms
        self.sites = [(58851, SITES_ORIG[58851], b'\xC3' + s['e_rs'].to_bytes(2, 'little') + b'\x00'),
                      (59539, SITES_ORIG[59539], b'\xC3' + s['e_pc'].to_bytes(2, 'little') + b'\x00'),
                      (59543, SITES_ORIG[59543], b'\xC3' + s['e_af'].to_bytes(2, 'little') + b'\x00'),
                      (59087, SITES_ORIG[59087], b'\xC3' + s['e_re'].to_bytes(2, 'little')),
                      (65172, SITES_ORIG[65172], b'\xC3' + s['e_lim'].to_bytes(2, 'little')),
                      (65274, SITES_ORIG[65274], b'\xC3' + s['e_hx'].to_bytes(2, 'little')),
                      (65029, SITES_ORIG[65029], b'\xCD' + s['e_off2'].to_bytes(2, 'little')),
                      (65076, SITES_ORIG[65076], b'\xCD' + s['e_off1'].to_bytes(2, 'little')),
                      (60853, SITES_ORIG[60853], b'\xC3' + s['e_bt'].to_bytes(2, 'little') + b'\x00'),
                      (60839, SITES_ORIG[60839], b'\xC3' + s['e_ov'].to_bytes(2, 'little') + b'\x00'),
                      (60965, SITES_ORIG[60965], b'\xC3' + s['e_it'].to_bytes(2, 'little')),
                      (59547, SITES_ORIG[59547], b'\xC3' + s['e_bend'].to_bytes(2, 'little'))]
        self.sites1 = [(0xD4DE, SITES1_ORIG[0xD4DE], b'\xC3' + s['e_ps'].to_bytes(2, 'little')),
                       (0xD6D4, SITES1_ORIG[0xD6D4], b'\xC3' + s['e_ay'].to_bytes(2, 'little'))]

    def check_sites(self, bank0):
        for a, old, new in self.sites:
            cur = bytes(bank0[a - 0xC000:a - 0xC000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def patched_bank0(self, bank0):
        self.check_sites(bank0)
        b = bytearray(bank0)
        for a, old, new in self.sites:
            b[a - 0xC000:a - 0xC000 + len(new)] = new
        return bytes(b)

    def patched_bank1(self, bank1):
        b = bytearray(bank1)
        for a, old, new in self.sites1:
            if bytes(b[a - 0xC000:a - 0xC000 + len(old)]) != old:
                raise ValueError('unexpected code at bank 1 0x%04X' % a)
            b[a - 0xC000:a - 0xC000 + len(new)] = new
        return bytes(b)

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('Rainbow Islands patch needs the 128K snapshot')
        if snap.port7ffd & 0x10 == 0:
            raise ValueError('snapshot selects ROM 0; the hooks need the 48K ROM (alt image 1)')
        if any(snap.banks[7][:8192]):
            raise ValueError('bank 7 (first 8K) is not empty: needed for the tilemap')
        snap.banks[0] = self.patched_bank0(snap.banks[0])
        snap.banks[1] = self.patched_bank1(snap.banks[1])


# ---------------------------------------------------------------------------------------------
# Boot check (128K): simulated Next boot of the built .nex against the patched snapshot
# ---------------------------------------------------------------------------------------------

def boot_check(nex, z80, patch=None, tail=None):
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
    t0, t1 = tail if tail else (TAIL_ADDR, TAIL_ADDR + 80)
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not t0 <= a < t1]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    img = bytearray(rom48())
    if patch is not None:
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
    if st['p7ffd'] != s.port7ffd or not st['p1ffd'] & 4:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 2 * top, 2 * top + 1]:
        bad.append(('MMU', st['mmu']))
    if patch is not None and st['nr'].get(0x15) != 1:
        bad.append(('sprites not enabled by setup', st['nr'].get(0x15)))
    if isinstance(patch, RainbowPatch):         # Rainbow writes only the top 64 bytes of each pattern;
        z = setup_zeroes_patterns(patch)        # other engines (Wally) upload full patterns
        if z:
            bad.append(('setup', z))
    return bad


# ---------------------------------------------------------------------------------------------
# Differential verification against an RZX (Python simulator, 128K)
# ---------------------------------------------------------------------------------------------

CMP = list(range(0, 13)) + [14] + list(range(18, 25)) + [26, 27, 28]   # all but R, T, MEMPTR, AF'


class NextState:
    """Next-side state the patched code sees: page 26, NextRegs, sprite attributes, pattern RAM."""

    def __init__(self, patch):
        self.scratch = bytearray(patch.scratch)
        self.no_swapnib = getattr(patch, 'no_swapnib', False)     # negative control only
        self.pages = collections.defaultdict(lambda: bytearray(8192))
        self.pages[PAGE_T] = bytearray(getattr(patch, 'tpage', bytes(8192)))
        self.pages[PAGE_F] = bytearray(getattr(patch, 'fpage', bytes(8192)))
        self.nr = {0x50: 0xFF, 0x51: 0xFF, 0x07: 0, 0x52: 10, 0x53: 11}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.a57, self.a57_pos = 0, 0
        self.pat_writes = 0
        self.sel = 0
        self.events = []
        self.line = 200             # video line seen by the raster wait: fixed (bottom border: no wait),
        self.line_t = None          # or (line at T = 0) advancing LINE_T per line (unit tests)
        self.rsel = 0
        self.R = None               # registers of the machine running this state (T for the raster)
        self.t34 = None             # T of the first sprite select ($34) write
        self.t6e = None             # T of the first tilemap base ($6E) write
        self.polls = 0
        self.last_line = None
        self.int_until = 0          # T until which the INT signal reads as held ($22 bit 7)
        self.clip_tm, self.clip_i = [None] * 4, 0

    def video_line(self):
        if self.line_t is None:
            return self.line
        return (self.line_t + self.R[25] // LINE_T) % 312

    def read(self, port):
        if port == 0x253B:
            if self.rsel in (0x1E, 0x1F):
                self.polls += 1
                v = self.video_line()
                self.last_line = v
                return (v >> 8) & 1 if self.rsel == 0x1E else v & 255
            if self.rsel == 0x22:                   # bit 7 = the INT signal (held until int_until T)
                return (0x80 if self.R is not None and self.R[25] < self.int_until else 0) | \
                    (self.nr.get(0x22, 0) & 0x7F)
            return self.nr.get(self.rsel, 0)
        self.events.append(('in', port))
        return 0xFF

    def nextreg(self, reg, val):
        if reg == 0x1C and val & 8:
            self.clip_tm, self.clip_i = [None] * 4, 0
        elif reg == 0x1B:
            self.clip_tm[self.clip_i & 3] = val
            self.clip_i += 1
        if reg in (0x6E, 0x6F):
            val &= 0xBF                     # bit 6 reads back 0
        if reg == 0xC8:                     # interrupt status: writing 1 clears the bit (not while
            val = self.nr.get(0xC8, 0) & ~val & 255     # the INT signal is still held: model)
            if self.R is not None and self.R[25] < self.int_until:
                val |= self.nr.get(0xC8, 0) & 1
        self.nr[reg] = val
        if reg == 0x34 and self.t34 is None and self.R is not None:
            self.t34 = self.R[25]
        if reg == 0x6E and self.t6e is None and self.R is not None:
            self.t6e = self.R[25]
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def out(self, port, val):
        if port == 0x243B:
            self.rsel = val
        elif port == 0x303B:                # pattern slot for 0x5B AND sprite index for 0x57
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
            self.a57, self.a57_pos = val & 0x7F, 0
        elif port & 0xFF == 0x57:           # attributes in $35-$39 order; 4 bytes if byte 3 bit 6 = 0
            a = self.attr[self.a57]
            a[self.a57_pos] = val
            self.a57_pos += 1
            if self.a57_pos == 4 and not a[3] & 0x40:
                a[4] = 0
                self.a57_pos = 5
            if self.a57_pos == 5:
                self.a57, self.a57_pos = (self.a57 + 1) & 0x7F, 0
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
            self.pat_writes += 1
        else:
            self.events.append(('port', port, val))

    def sprite_pixels(self, i):
        """Visible 4-bit anchor sprite i -> list of (x, y, index) in ULA coordinates, else None."""
        a0, a1, a2, a3, a4 = self.attr[i]
        if not a3 & 0x80:
            return None
        x = a0 + (a2 & 1) * 256 - 32
        y = a1 + (a4 & 1) * 256 - 32
        base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
        out = []
        for j in range(16):
            for k in range(16):
                b = self.pat[base + j * 8 + k // 2]
                out.append((x + k, y + j, (b >> 4) if k % 2 == 0 else (b & 15)))
        return out


def staged(ns, first):
    """A copy of ns in which sprites first..V_S-1 show what the render-end commit will write:
    attributes from ATTRB, patterns from the piece's store entry (V_EPG / V_ENT+1 / V_NS)."""
    import copy
    t = copy.copy(ns)
    t.attr = [list(a) for a in ns.attr]
    t.pat = bytearray(ns.pat)
    n = ns.scratch[V_S] - first
    if n <= 0:
        return t
    pg, hi, nspr = ns.scratch[0x28], ns.scratch[0x27], ns.scratch[0x21]
    ent = ns.pages[pg][(hi - 0x20) * 256:(hi - 0x20) * 256 + 256]
    for k in range(n):
        i = first + k
        t.attr[i] = list(ns.scratch[ATTRB + 5 * i:ATTRB + 5 * i + 5])
        b = (i >> 1) * 256 + (i & 1) * 128
        t.pat[b:b + 64] = ent[256 - 64 * nspr + 64 * k:256 - 64 * nspr + 64 * k + 64]
    return t


def cell_index(d, e):
    return (d - 0x9F) * 32 + e if 0x9F <= d <= 0xB4 and e < 32 else None


class ObjShadow:
    """Python model of the per-cell object map kept by the hooks at 60853 / 60839 / 60965 (page 27):
    tiles (background map tile), objo (opaque object, FF = unsupported: left as drawn), m1/m2 (masked
    objects, nibbles in draw order), flags (bit 7 background known, bits 0-3 remembered item ink),
    ctile (tile assigned this render)."""

    ARR = (('tiles', TILES), ('objo', OBJO), ('m1', OBJM1), ('m2', OBJM2), ('flags', FLAGS), ('ctile', CTILE))

    def __init__(self):
        for name, _ in self.ARR:
            setattr(self, name, bytearray(NCELLS))

    def occupied(self, i):
        return bool(self.objo[i] or self.m1[i])

    def event(self, pc, a, d, e, peek, bc2=0, page27=None):
        """Returns (cell, ctile before) or (None, 0). page27: the class tables (OCLASS / MCLASS)."""
        i = cell_index(d, e)
        if i is None:
            return None, 0
        ct = self.ctile[i]
        self.ctile[i] = 0
        if pc == 60853:
            self.tiles[i], self.objo[i], self.m1[i], self.m2[i], self.flags[i] = a, 0, 0, 0, 0x80
        elif pc == 60839:
            self.tiles[i] = peek(bc2)
            self.m1[i] = self.m2[i] = 0
            g = None if a in (0, 0xFF) else class_bits(page27[OCLASS - 0x2000 + a])
            self.objo[i] = 0xFF if g is None else a
            self.flags[i] = 0x80 | (g or 0)
        elif self.objo[i] != 0xFF:
            g = class_bits(page27[MCLASS - 0x2000 + a]) if 1 <= a <= 14 else None
            if g is None:
                self.objo[i] = 0xFF
            elif not self.m1[i] & 0xF0:
                self.m1[i] = a << 4
            elif not self.m1[i] & 0x0F:
                self.m1[i] |= a
            elif not self.m2[i] & 0xF0:
                self.m2[i] = a << 4
            elif not self.m2[i] & 0x0F:
                self.m2[i] |= a
            else:
                self.objo[i] = 0xFF
                g = None
            if g is not None:
                self.flags[i] |= g
        return i, ct

    def fix_flags(self, page27):
        """Unit tests: FLAGS group bits (and FF for a 'leave as drawn' class) as the hooks would
        have set them for the objects now in each cell."""
        for i in range(NCELLS):
            if not self.occupied(i) or self.objo[i] == 0xFF:
                continue
            f = 0
            for kind, code in self.objects(i):
                g = class_bits(obj_class(page27, kind, code))
                if g is None:
                    self.objo[i] = 0xFF
                    break
                f |= g
            self.flags[i] = (self.flags[i] & 0x8F) | f

    def rcnt(self):
        return bytes(sum(1 for i in range(32 * k, 32 * k + 32) if self.occupied(i)) for k in range(22))

    def same_as(self, page27, which=None):
        for name, base in self.ARR:
            if which and name not in which:
                continue
            if bytes(page27[base - 0x2000:base - 0x2000 + NCELLS]) != bytes(getattr(self, name)):
                return False
        return bytes(page27[RCNT - 0x2000:RCNT - 0x2000 + 22]) == self.rcnt() and \
            bytes(page27[OCCM - 0x2000:OCCM - 0x2000 + 88]) == self.occm()

    def occm(self):
        out = bytearray(88)
        for i in range(NCELLS):
            if self.occupied(i):
                out[4 * (i >> 5) + ((i & 31) >> 3)] |= 0x80 >> (i & 7)
        return bytes(out)

    def load(self, page27):
        for name, base in self.ARR:
            page27[base - 0x2000:base - 0x2000 + NCELLS] = getattr(self, name)
        page27[RCNT - 0x2000:RCNT - 0x2000 + 22] = self.rcnt()
        page27[OCCM - 0x2000:OCCM - 0x2000 + 88] = self.occm()

    def objects(self, i):
        """[('O', code)] + [('M', code)...] in draw order."""
        out = [('O', self.objo[i])] if self.objo[i] else []
        for b in (self.m1[i], self.m2[i]):
            for n in (b >> 4, b & 15):
                if n:
                    out.append(('M', n))
        return out


def class_bits(cls):
    """Class byte -> FLAGS group bits (0x10 rainbow group / 0x20 item group, + 0x40 fixed ink), None
    for a 'leave the cell as drawn' class (asm ocls)."""
    if cls & 2:
        return None
    return (0x10 if cls & 1 else 0x20) | (0x40 if cls & 0xF0 else 0)


def obj_class(page27, kind, code):
    return page27[(OCLASS if kind == 'O' else MCLASS) - 0x2000 + code]


def ink_index(attr):
    """Ink pixel index from an attribute: 1 black, 2-8 ink, 9-15 bright ink."""
    ink = attr & 7
    return 1 if ink == 0 else ink + 1 + (7 if attr & 64 else 0)


def obj_rows(peek, kind, code):
    """The object's 8 pixel rows (opaque: 0xF700 + 8*(code-1); masked: odd bytes of 0xF600 +
    16*(code-1))."""
    if kind == 'O':
        return [peek(0xF700 + 8 * (code - 1) + j) for j in range(8)]
    return [peek(0xF600 + 16 * (code - 1) + 2 * j + 1) for j in range(8)]


def obj_compose(peek, page27, objs, inkr, inki, fpage=None, one_ink=False):
    """32-byte 4-bit tile: rainbow-group objects first, then the others, each in draw order; per
    object its border (8-neighbours of its pixels inside the cell, minus its pixels) -> 1, its pixels
    -> its ink (class override, else rainbow group: inkr, others: inki)."""
    px = [[0] * 8 for _ in range(8)]
    for pas in (0, 1):
        for kind, code in objs:
            cls = obj_class(page27, kind, code)
            if (0 if cls & 1 else 1) != pas:
                continue
            ink = cls >> 4 or (inkr if pas == 0 else inki)
            P = obj_rows(peek, kind, code)
            for j in range(8):
                if cls & 4:
                    B = 0
                else:
                    v = P[j] | (P[j - 1] if j else 0) | (P[j + 1] if j < 7 else 0)
                    B = (v | (v << 1) | (v >> 1)) & 255 & ~P[j]
                for x in range(8):
                    m = 0x80 >> x
                    if P[j] & m:
                        px[j][x] = ink
                    elif B & m:
                        px[j][x] = 1
            fl = obj_fill(fpage, code) if fpage is not None and kind == 'O' else None
            if fl:                                  # collectables: the inside pixels (asm ofill / odraw)
                mask, fc = fl
                v = fc & 15 if fc else (3 if one_ink else (15 if fill_white(inki) else 1))
                for j in range(8):
                    for x in range(8):
                        if mask[j] & ~P[j] & (0x80 >> x):
                            px[j][x] = v
    return bytes((px[j][2 * q] << 4) | px[j][2 * q + 1] for j in range(8) for q in range(4))


def obj_build(peek, sh, page27, fpage=None):
    """Render start (asm obuild): None if the scroll is not a multiple of 8 (tilemap off), else
    {(kk, col): (cell, key, tile content, map attribute)} for every visible object cell, and the
    item inks remembered (sh.flags updated in place)."""
    s, N = peek(48782), peek(58850)
    if s & 7:
        return None
    out = {}
    for kk in range(20):
        if 8 * kk >= N:
            break
        k = (s // 8 + kk) % 22
        for col in range(32):
            i = 32 * k + col
            if not sh.occupied(i) or sh.objo[i] == 0xFF or not sh.flags[i] & 0x80:
                continue
            objs = sh.objects(i)
            f = sh.flags[i]
            has = (f >> 4) & 3 | (8 if f & 0x40 else 0)     # group bits kept by the cell hooks
            inkr = ink_index(peek(0xB500 + i))
            if has & 3 == 2:
                inki = inkr
                sh.flags[i] = (f & 0xF0) | inkr
            elif has & 3 == 3:
                inki = sh.flags[i] & 15 or inkr
            else:
                inki = inkr
            if has & 3 == 3 or has & 8:             # several inks: in the pixels, palette offset 0
                key = bytes([sh.objo[i], sh.m1[i], sh.m2[i], inki << 4 | inkr])
                out[(kk, col)] = (i, key, obj_compose(peek, page27, objs, inkr, inki, fpage), 0)
            else:                                   # one ink: pixel 2 + the entry's palette offset
                key = bytes([sh.objo[i], sh.m1[i], sh.m2[i], 0])
                out[(kk, col)] = (i, key, obj_compose(peek, page27, objs, 2, 2, fpage, True), inkr << 4)
    return out


def tile_row(peek, t, j):
    """Row j of map tile t as the game's base-tile drawer 60853 draws it: 0x8000 + 8*t + j, tiles
    >= 128 from tile t-128 mirrored through the bit-reversal table at 0xF500."""
    b = peek(0x8000 + 8 * (t & 127) + j)
    return peek(0xF500 | b) if t & 128 else b


def obj_fix(peek, sh, page27, row):
    """Screen writes of the band hook for screen char row `row`: every object cell with a tile this
    render (CTILE) -> its background tile's rows inside the play area; its attribute -> the tile's
    colour while the screen shows the attribute-buffer value."""
    s, N = peek(48782), peek(58850)
    w = {}
    kk = row - 2
    if s & 7 or not 0 <= kk < 20 or 8 * kk >= N:
        return w
    k = (s // 8 + kk) % 22
    n = min(8, N - 8 * kk)
    for col in range(32):
        i = 32 * k + col
        if not sh.ctile[i]:
            continue
        t = page27[BGOVR - 0x2000 + sh.tiles[i]]
        for j in range(n):
            y = 8 * row + j
            a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col
            w[a] = tile_row(peek, t, j)
        a = 0x5800 + 32 * row + col
        if peek(a) == peek(0xB500 + i):
            w[a] = peek(0xF200 | t | 128) & 127
    return w


def obj_truth(peek, sh, i):
    """The cell as the game draws it from the modelled objects: background tile (no opaque object) or
    the opaque object over a blank cell, then each masked object (cell AND mask) OR gfx."""
    k, col = i >> 5, i & 31
    objs = sh.objects(i)
    if objs and objs[0][0] == 'O':
        rows = obj_rows(peek, 'O', objs[0][1])
        objs = objs[1:]
    else:
        rows = [tile_row(peek, sh.tiles[i], j) for j in range(8)]
    for _, code in objs:
        g = 0xF600 + 16 * (code - 1)
        rows = [(rows[j] & peek(g + 2 * j)) | peek(g + 2 * j + 1) for j in range(8)]
    return rows


def map_pos(kk, col):
    """Byte offset of the tilemap entry (40x32, 2 bytes) of screen char row kk+2, column col."""
    return ((kk + 6) * 40 + col + 4) * 2


def sh_pos(kk, col):
    """Byte offset in the shadow map (page 28) of screen char row kk+2, column col."""
    return kk * 64 + col * 2


def piece_plan(patch, ix, s_before, fmax=NSPR_MAX):
    """What the hook does with a piece: ('star' | 'ula' | 'sprites', nspr). fmax = 128 - item sprites."""
    if ix in (60176, 60180):
        return 'star', 0
    pi = patch.plot.get(ix)
    if pi is None or s_before + pi['nspr'] > fmax:
        return 'ula', 0
    return 'sprites', pi['nspr']


def _swapnib(R):
    """Z80N SWAPNIB (ED 23, 8 T): swap the nibbles of A; flags unchanged. SkoolKit would run it as a
    silent 2-byte NOP (NEXT_REGISTERS.md), so every simulator that runs the hooks installs this."""
    from skoolkit.simulator import R2
    R[0] = ((R[0] << 4) | (R[0] >> 4)) & 0xFF
    R[15] = R2[R[15]]
    R[25] += 8
    R[24] = (R[24] + 2) % 65536


def swapnib_selftest():
    """Run ED 23 for every A through the simulator hook: A swapped, F kept, PC += 2, T += 8."""
    from skoolkit.simulator import Simulator
    bad = 0
    for a in range(256):
        m = bytearray(65536)
        m[0x8000:0x8002] = b'\xED\x23'
        sim = Simulator(m, {'PC': 0x8000, 'A': a, 'F': a ^ 0x5A})
        sim.after_ED[0x23] = lambda R=sim.registers: _swapnib(R)
        t0 = sim.registers[25]
        sim.opcodes[0xED]()
        R = sim.registers
        bad += R[0] != ((a & 15) << 4 | a >> 4) or R[1] != a ^ 0x5A or R[24] != 0x8002 or R[25] - t0 != 8
    return bad


def setup_zeroes_patterns(patch):
    """Run the setup routine (0xD000) with pattern RAM full of garbage: all 16K must end zero,
    because the piece hook writes only the top 64 bytes of each 4-bit pattern."""
    import random
    from skoolkit.simulator import Simulator
    m = bytearray(65536)
    m[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra
    m[0x8000:0x8003] = b'\xCD\x00\xD0'
    ns = NextState(patch)
    rnd = random.Random(1)
    ns.pat[:] = bytes(rnd.randrange(256) for _ in range(16384))
    sim = _machine(Simulator, m, Simulator(m, {'PC': 0x8000, 'SP': 0x7FF0}).registers[:], ns)
    if not _run(sim, (0x8003,), 2000000):
        return 'setup did not return'
    nz = sum(1 for b in ns.pat if b)
    return 'pattern RAM not zeroed (%d bytes)' % nz if nz else None


def _machine(Sim, mem, regs, ns):
    sim = Sim(mem, {})
    sim.registers[:] = regs
    R, ed = sim.registers, sim.after_ED
    ns.R = R
    from skoolkit.simulator import R2

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na
    if not getattr(ns, 'no_swapnib', False):
        ed[0x23] = lambda: _swapnib(R)

    class Tr:
        def read_port(s, regs_, port):
            return ns.read(port)

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stops, limit=200000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[24] not in stops:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


class AYModel:
    """The AY queue of the hooks (asm aywr / ayopen / aytick / ayplay), with the original's chip
    state as the reference: `truth` = the registers as the original game has written them so far;
    each queued tick keeps the truth at its close; after a replay the chip (= every write the
    patched build sent) must equal the truth at the close of the tick just sent."""

    def __init__(self):
        self.q = []                 # [values(14), mask set, truth at close or None while open]
        self.r = 0
        self.open_ = False
        self.chip = [None] * 16
        self.truth = [None] * 16
        self.check = None
        self.opened = self.flushed = 0

    def _play(self):
        vals, mask, _ = self.q.pop(0)
        out = []
        for reg in range(14):
            if reg in mask:
                out += [(0xFFFD, reg), (0xBFFD, vals[reg])]
                self.chip[reg] = vals[reg]
        self.r = (self.r + 1) & 3
        return out

    def open(self):
        out = []
        if len(self.q) == 4:
            out = self._play()
            self.flushed += 1
        if self.q and self.q[-1][2] is None:
            self.q[-1][2] = list(self.truth)
        self.q.append([[0] * 14, set(), None])
        self.open_ = True
        self.opened += 1
        return out

    def write(self, reg, val):
        self.truth[reg & 15] = val
        if reg >= 14:
            self.chip[reg & 15] = val
            return [(0xFFFD, reg), (0xBFFD, val)]
        out = []
        if not self.open_:
            out = self.open()
        self.q[-1][0][reg] = val
        self.q[-1][1].add(reg)
        return out

    def tick(self):
        """One interrupt: the oldest tick to the chip, a second one when 3+ remain (asm aytick).
        Sets `check` = the original's registers at the close of the last tick sent (None: none sent)."""
        out, self.check = [], None
        if self.q:
            for _ in range(2 if len(self.q) >= 4 else 1):
                last = self.q[0][2] if self.q[0][2] is not None else list(self.truth)
                out += self._play()
            if not self.q:
                self.open_ = False
            self.check = last[:14]
        return out

    def same(self, sc):
        if sc[V_AYN] != len(self.q) or sc[V_AYR] != self.r or bool(sc[V_AYO]) != (self.open_ and bool(self.q)):
            return False
        for k, (vals, mask, _) in enumerate(self.q):
            a = AYQ + 16 * ((self.r + k) & 3)
            m = 0
            for reg in mask:
                m |= 0x8000 >> reg
            if sc[a + 14] != m >> 8 or sc[a + 15] != m & 255:
                return False
            if any(sc[a + reg] != vals[reg] for reg in mask):
                return False
        return True


RS_LINE = 240                # render end at or past this line: commit at once (asm rsafe)
INT_LINE = 248               # video line of the ULA interrupt (50 Hz; Next manual ch. 17)
PROF_KEYS = ('Tp', 'T0', 'T1', 'T2', 'Tre')   # pieces, render start, band ends, cell hooks, render end


def verify(patch, rzx_path, progress=None, stop=None):
    """Replay the RZX (original game). At every walker event run the original and the patched code
    from the same state and compare. Returns a Counter of results (keys ending in '!' = failures)."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    from .dizzy6 import _rw_simulator
    MG, MS = Memory.__getitem__, Memory.__setitem__
    Sim = _rw_simulator()
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = bytearray(16384)
    from .build import rom48
    alt[:] = rom48()
    alt[0x2000:0x4000] = patch.page
    psite = {}
    for a, old, new in patch.sites:
        for k, v in enumerate(new):
            psite[a + k] = v
    site_bytes = set(psite)
    psite1 = {a + k: v for a, old, new in patch.sites1 for k, v in enumerate(new)}
    site_bytes1 = set(psite1)
    st = {'sim': None, 'frame': 0, 'afp': None, 'n': 0, 'prev_vis': set(), 'render': False, 'figw': set(),
          'shadow': ObjShadow(), 'tmax': 0, 'tsum': 0, 'opq': {}, 'bands': set()}
    ns = NextState(patch)
    WATCH = set(range(58851, 58855)) | set(range(59539, 59547)) | {59547} | set(range(59087, 59090)) | \
        {65172, 65274, 65029, 65076} | set(range(60853, 60857)) | set(range(60839, 60843)) | \
        set(range(60965, 60969)) | {59548, 59549}
    cnt = collections.Counter()
    WATCH1 = {0xD4DE, 0xD4DF, 0xD4E0, 0xD4E1, 0xD6D4, 0xD6D5, 0xD6D6, 0xD6D7}
    ay = AYModel()

    def fail(k, info):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class OMem:                     # original code, private overlay over the live memory
        def __init__(s, real):
            s.real, s.ov = real, {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return MG(s.real, a) if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class PMem(OMem):               # patched game on the Next: slot 0 = page 26 or alt ROM, slot 1 = alt ROM
        def __getitem__(s, a):
            if a < 0x4000:
                if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                    return ns.scratch[a]
                if a >= 0x2000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                    return ns.pages[ns.nr[0x51]][a - 0x2000]
                return alt[a]
            if a < 0x8000:
                pg = ns.nr.get(0x52 + ((a >> 13) & 1))
                if pg != 10 + ((a >> 13) & 1):
                    return ns.pages[pg][a & 0x1FFF]
            v = psite.get(a)
            if v is not None and (s.real.o7ffd & 7) == 0:
                return v
            v = psite1.get(a)
            if v is not None and (s.real.o7ffd & 7) == 1:
                return v
            v = s.ov.get(a)
            return MG(s.real, a) if v is None else v

        def __setitem__(s, a, v):
            if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                ns.scratch[a] = v
            elif 0x2000 <= a < 0x4000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                ns.pages[ns.nr[0x51]][a - 0x2000] = v
            elif a < 0x4000:
                fail('patched code wrote ROM/alt ROM', (a,))
            elif a < 0x8000 and ns.nr.get(0x52 + ((a >> 13) & 1)) != 10 + ((a >> 13) & 1):
                ns.pages[ns.nr[0x52 + ((a >> 13) & 1)]][a & 0x1FFF] = v
            else:
                s.ov[a] = v

    def xt(so, sp_):
        """Extra T of the patched code for this event (both machines start from the same T)."""
        if st.get('fr_on'):
            st['fx'] += sp_.registers[25] - so.registers[25]

    def compare(o, p, ro, rp, what, dead=()):
        diff = [i for i in CMP if ro[i] != rp[i] and i not in dead]
        if diff:
            fail(what + ': registers differ', (diff, [ro[i] for i in diff], [rp[i] for i in diff]))
        keys = set(o.ov) | set(p.ov)
        md = [a for a in keys if not 0x4000 <= a < 0x5800 and o[a] != p[a]]
        if md:
            fail(what + ': memory differs', (len(md), sorted(md)[:4]))
        if any(0x4000 <= a < 0x5B00 for a in p.ov):
            fail(what + ': patched code wrote the screen', (st.get('ix'),))
        return not diff and not md

    def ev_piece(real, R):
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        ok1 = _run(so, (59513, 59547))
        n_before = ns.scratch[V_S]
        ns.events = []
        h0 = ns.scratch[V_HITS] | ns.scratch[V_HITS + 1] << 8
        sp0 = ns.nr.get(0x07)                       # the piece hook must not change the CPU speed
        ov0 = ns.scratch[0x36]
        sp_ = _machine(Sim, p, list(R), ns)
        ok2 = _run(sp_, (59513, 59547))
        if not (ok1 and ok2):
            fail('piece: did not return', (ok1, ok2))
            return
        ro, rp = so.registers, sp_.registers
        xt(so, sp_)
        if st.get('fr_on'):
            st['Tp'] = st.get('Tp', 0) + sp_.registers[25] - so.registers[25]
        c['pieces'] += 1
        st['ix'] = (R[8] * 256 + R[9], R[12])
        plan, nspr = piece_plan(patch, R[8] * 256 + R[9], n_before, ns.scratch[V_FMAX])
        if plan != 'sprites':                       # passthrough: patched = original, screen included
            if [i for i in CMP if ro[i] != rp[i]] or o.ov != p.ov:
                fail('passthrough piece differs from the original', ())
        else:
            compare(o, p, ro, rp, 'piece')
        st['afp'] = (ro[16:18], rp[16:18]) if ro[16:18] != rp[16:18] else None
        if ns.nr.get(0x50) != 0xFF or ns.nr.get(0x51) != 0xFF or ns.nr.get(0x07) != sp0 or \
                ns.nr.get(0x52) != 10 or ns.nr.get(0x53) != 11:
            fail('piece: MMU / CPU speed not restored', (ns.nr.get(0x50), ns.nr.get(0x51), ns.nr.get(0x52),
                                                         ns.nr.get(0x53), ns.nr.get(0x07)))
        if any(e[0] == 'in' for e in ns.events):
            fail('piece: port read in hook', ())
        if plan == 'star':
            c['star pieces left on the ULA (60176/60180)'] += 1
            if ns.scratch[V_S] != n_before:
                fail('piece: counter changed for a star', ())
            return
        if plan == 'ula':
            c['pieces passed through to the ULA (sprites used up)'] += 1
            return
        if ns.scratch[V_S] != n_before + nspr:
            fail('piece: sprite counter', (n_before, nspr, ns.scratch[V_S]))
        h1 = ns.scratch[V_HITS] | ns.scratch[V_HITS + 1] << 8
        if ns.scratch[0x36] != ov0:
            c['overflow entries (4 ways in use)'] += 1
        c['pattern cache hits' if h1 != h0 else 'pattern cache misses'] += 1
        c['max sprites in a render'] = max(c['max sprites in a render'], n_before + nspr)
        # sprite pixels vs what the original drew (screen before = live memory, after = overlay)
        cov = {}
        stg = staged(ns, n_before)
        for i in range(n_before, n_before + nspr):
            px = stg.sprite_pixels(i)
            if px is None:
                continue
            for x, y, idx in px:
                if idx and 0 <= x < 256 and 0 <= y < 192:
                    cov[(x, y)] = idx
                elif idx:
                    c['sprite pixels off screen (not compared)'] += 1

        def bit(m, x, y):
            a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
            return (m[a] >> (7 - (x & 7))) & 1, a
        bad_px = 0
        for (x, y), idx in cov.items():
            after, a = bit(o, x, y)
            if idx == 1 and after != 1 or idx == 2 and after != 0:
                bad_px += 1
            c['sprite pixels ink' if idx == 1 else 'sprite pixels outline'] += 1
        for a in o.ov:
            if 0x4000 <= a < 0x5800:
                y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
                for k in range(8):
                    x = (a & 31) * 8 + k
                    before = (MG(real, a) >> (7 - k)) & 1
                    after = (o.ov[a] >> (7 - k)) & 1
                    if (x, y) in cov:
                        continue
                    if after != before:
                        if patch.cfg.no_outline(R[12] >> 8) and after == 0:
                            c['outline pixels dropped (transparent mode)'] += 1
                        else:
                            bad_px += 1
        if bad_px:
            fail('piece: sprite pixels differ from the original plot', (bad_px, st.get('ix')))

    def ev_simple(real, R, stop_at, what, dead=()):
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        sp_ = _machine(Sim, p, list(R), ns)
        ns.events = []
        if not (_run(so, (stop_at,)) and _run(sp_, (stop_at,))):
            fail(what + ': did not return', ())
            return None
        xt(so, sp_)
        compare(o, p, so.registers, sp_.registers, what, dead)
        c[what] += 1
        if ns.nr.get(0x50) != 0xFF:
            fail(what + ': slot 0 not restored', ())
        return sp_

    def ay_writes(ns_):
        return [(e[1], e[2]) for e in ns_.events if e[0] == 'port' and e[1] & 0xC002 == 0xC000 or
                e[0] == 'port' and e[1] & 0xC002 == 0x8000]

    def ev_ay(real, R):
        """0xD6D4 (A = register, D = value): patched = original (registers incl. F, memory); the
        write goes into the queue (registers 0-13) or straight to the chip (others), as the model."""
        ret = MG(real, R[12]) | MG(real, R[12] + 1) << 8
        o, p = OMem(real), PMem(real)
        nso = NextState(patch)
        so = _machine(Sim, o, list(R), nso)
        sp_ = _machine(Sim, p, list(R), ns)
        ns.events = []
        if not (_run(so, (ret,)) and _run(sp_, (ret,))):
            fail('AY write: did not return', ())
            return
        xt(so, sp_)
        compare(o, p, so.registers, sp_.registers, 'AY write')
        if ns.nr.get(0x50) != 0xFF:
            fail('AY write: slot 0 not restored', ())
        orig = ay_writes(nso)
        if orig != [(0xFFFD, R[0]), (0xBFFD, R[4])]:
            fail('AY write: original not as expected', (orig[:4],))
        want = ay.write(R[0], R[4])
        if ay_writes(ns) != want:
            fail('AY write: chip writes differ from the model', (ay_writes(ns)[:4], want[:4]))
        if not ay.same(ns.scratch):
            fail('AY write: queue differs from the model', ())
        c['AY writes (music)'] += 1

    def ev_ps(real, R):
        """0xD4DE (AY player entry): patched = original at 0xD4E1; a new tick opens in the queue."""
        ns.events = []
        ev_simple(real, R, 0xD4E1, 'AY player ticks')
        want = ay.open()
        if ay_writes(ns) != want:
            fail('AY tick: chip writes differ from the model', (ay_writes(ns)[:4], want[:4]))
        if not ay.same(ns.scratch):
            fail('AY tick: queue differs from the model', ())

    def ev_render_start(real, R):
        """Render start: original = patched (all registers); the back tilemap (page 14) = the model:
        every visible object cell has a tile whose 32 bytes are the composed objects (or 0 when no
        cache entry was free), every other play position 0; CTILE = the tile numbers; the tiles of
        the map on screen are not touched. And the modelled objects = the original's back buffer."""
        peek = lambda a: MG(real, a)
        sh = st['shadow']
        pg = ns.pages[PAGE_T]
        if not sh.same_as(pg):
            fail('render start: object map differs from the model', ())
        for i in range(NCELLS):                     # the object model against the game's own cell
            if sh.occupied(i) and sh.objo[i] != 0xFF and sh.flags[i] & 0x80:
                k, col = i >> 5, i & 31
                got = [peek(0x9F00 + 256 * k + col + 32 * j) for j in range(8)]
                if got == obj_truth(peek, sh, i):
                    c['object cells = the game\'s back buffer'] += 1
                else:
                    fail('object model differs from the back buffer', (i, sh.objects(i)))
        tm = ns.pages[PAGE_TM]
        fb = {}                                     # tiles of the map on screen
        if ns.scratch[V_MSD] != 0xFF:
            for kk in range(20):
                for col in range(32):
                    t = tm[map_pos(kk, col)]
                    if t:
                        fb[t] = bytes(tm[TDEF + 32 * t:TDEF + 32 * t + 32])
        exp = obj_build(peek, sh, pg, ns.pages[PAGE_F])
        keys0 = bytes(pg[KEYS - 0x2000:KEYS - 0x2000 + 4 * NTILE])
        fx0 = st.get('fx', 0)
        sp_ = ev_simple(real, R, 58855, 'render start')
        keys1 = bytes(pg[KEYS - 0x2000:KEYS - 0x2000 + 4 * NTILE])
        c['tiles composed (cache misses)'] += sum(1 for t in range(NTILE) if keys0[4 * t:4 * t + 4] != keys1[4 * t:4 * t + 4])
        st['fxi'] = st.get('fxi', 0) + st.get('fx', 0) - fx0
        st['T0'] = st.get('T0', 0) + st.get('fx', 0) - fx0
        if sp_ is not None:
            st['tsmax'] = max(st.get('tsmax', 0), sp_.registers[25] - R[25])
        st['tok'] = exp is not None
        if ns.scratch[V_TOK] != (1 if exp is not None else 0):
            fail('render start: tilemap flag', (ns.scratch[V_TOK],))
        if exp is None:
            c['renders with the scroll not a multiple of 8 (tilemap off)'] += 1
            return
        if ns.scratch[V_MSB] != MG(real, 48782):
            fail('render start: shadow map scroll', ())
        shm = ns.pages[PAGE_SH]
        nt = 0
        for kk in range(20):
            for col in range(32):
                t, at = shm[sh_pos(kk, col)], shm[sh_pos(kk, col) + 1]
                e = exp.get((kk, col))
                if e is None:
                    if t or at:
                        fail('render start: tile where the model has no object', (kk, col, t))
                    continue
                i, key, data, attr = e
                if pg[CTILE - 0x2000 + i] != t:
                    fail('render start: CTILE differs from the map', (i, t, pg[CTILE - 0x2000 + i]))
                if not t:
                    fail('render start: object cell without a tile (cache full)', (i,))
                    continue
                nt += 1
                if bytes(tm[TDEF + 32 * t:TDEF + 32 * t + 32]) != data or at != attr:
                    fail('render start: tile differs from the composed objects', (i, key.hex(), t, at, attr))
                if bytes(pg[KEYS - 0x2000 + 4 * t:KEYS - 0x2000 + 4 * t + 4]) != key:
                    fail('render start: tile key', (i, t))
        st['shadow_map'] = bytes(shm[:20 * 64])
        for t, d in fb.items():
            if bytes(tm[TDEF + 32 * t:TDEF + 32 * t + 32]) != d:
                fail('render start: a tile on screen was overwritten', (t,))
        for i in range(NCELLS):                     # CTILE only for the cells just assigned
            if pg[CTILE - 0x2000 + i] and not any(e[0] == i for e in exp.values()):
                fail('render start: stale CTILE', (i,))
        sh.ctile[:] = pg[CTILE - 0x2000:CTILE - 0x2000 + NCELLS]
        if not sh.same_as(pg, ('flags',)):
            fail('render start: remembered item inks differ from the model', ())
        c['object tiles shown'] += nt
        c['max object tiles in a render'] = max(c['max object tiles in a render'], nt)
        st['nmap'] = nt

    def ev_band(real, R):
        """Walker end of a band (59547): original = patched (all registers, memory), and the screen
        changes = the object model's fix for this band's char row (from (59522))."""
        peek = lambda a: MG(real, a)
        ba = peek(59522) | peek(59523) << 8
        row = (ba >> 8 & 0x18) | (ba & 0xE0) >> 5
        exp = {a: v for a, v in obj_fix(peek, st['shadow'], ns.pages[PAGE_T], row).items() if v != peek(a)}
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        sp_ = _machine(Sim, p, list(R), ns)
        if not (_run(so, (59550,)) and _run(sp_, (59550,))):
            fail('band: did not return', ())
            return
        fx0 = st.get('fx', 0)
        xt(so, sp_)
        st['fxi'] = st.get('fxi', 0) + st.get('fx', 0) - fx0
        st['T1'] = st.get('T1', 0) + st.get('fx', 0) - fx0
        st['bands'].add(row)
        ro, rp = so.registers, sp_.registers
        diff = [k for k in CMP + [16, 17] if ro[k] != rp[k]]
        if diff:
            fail('band: registers differ', (diff,))
        md = [a for a in set(o.ov) | set(p.ov) if not 0x4000 <= a < 0x5B00 and o[a] != p[a]]
        if md:
            fail('band: memory differs', (len(md), sorted(md)[:4]))
        got = {a: v for a, v in p.ov.items() if 0x4000 <= a < 0x5B00 and v != peek(a)}
        if got != exp:
            fail('band: screen differs from the object model', (row, len(got), len(exp)))
        if ns.nr.get(0x50) != 0xFF or ns.nr.get(0x51) != 0xFF:
            fail('band: MMU not restored', ())
        c['bands checked'] += 1
        c['object screen bytes changed at band ends'] += len(exp)

    def ev_cell(real, R, pc):
        """Cell hooks 60853 / 60839 / 60965: patched = original (registers incl. F, memory), the
        page-27 object map changes exactly as the model, a dropped tile is cleared in both maps."""
        sh = st['shadow']
        i0 = cell_index(R[4], R[5])
        if pc == 60853 and i0 is not None and sh.objo[i0] not in (0, 0xFF) and i0 in st['opq']:
            # the game redraws an opaque object's cell with its base tile (pickup, or the cell
            # reused, or a new round): the same map byte (BC' address) at the same scroll as when the
            # object was drawn = the same map cell -> the tile must be TILES
            same = st['opq'].pop(i0) == (R[18] * 256 + R[19], MG(real, 48782))
            ok = R[0] == sh.tiles[i0]
            c['opaque object cell redrawn: %s scroll, tile %s' % ('same' if same else 'other',
                                                                   'as stored' if ok else 'different')] += 1
            if same and not ok:
                fail('opaque object: stored tile differs from the base tile the game draws', (i0, sh.tiles[i0], R[0]))
        tm0 = bytes(ns.pages[PAGE_TM][:0x0A00])
        sm0 = bytes(ns.pages[PAGE_SH][:20 * 64])
        i, ct = sh.event(pc, R[0], R[4], R[5], lambda a: MG(real, a), R[18] * 256 + R[19], ns.pages[PAGE_T])
        if pc == 60839 and i is not None:
            st['opq'][i] = (R[18] * 256 + R[19], MG(real, 48782))
            c['opaque object draws'] += 1
        fx0 = st.get('fx', 0)
        ev_simple(real, R, OBJ_SITES[pc], 'cell hook %d' % pc)
        st['fxi'] = st.get('fxi', 0) + st.get('fx', 0) - fx0
        st['T2'] = st.get('T2', 0) + st.get('fx', 0) - fx0
        if i is None:
            c['cell hook: not a back-buffer cell (ignored)'] += 1
        elif not sh.same_as(ns.pages[PAGE_T], ('tiles', 'objo', 'm1', 'm2', 'flags', 'ctile')):
            fail('cell hook: object map differs from the model', (pc, i))
        want, wsh = drop_tile(tm0, sm0, ns.scratch, i, ct)
        if ct:
            c['cell hook: tile dropped'] += 1
        if bytes(ns.pages[PAGE_TM][:0x0A00]) != want or bytes(ns.pages[PAGE_SH][:20 * 64]) != wsh:
            fail('cell hook: tilemaps changed other than the dropped tile', (pc, i))
        if ns.nr.get(0x51) != 0xFF or ns.nr.get(0x52) != 10 or ns.nr.get(0x53) != 11:
            fail('cell hook: MMU not restored', (pc,))

    def ev_render_end(real, R):
        n = ns.scratch[V_S]
        want = {}
        for pi_ in range(ns.scratch[V_NP]):
            pg, hi, nsp = ns.scratch[CLIST + 3 * pi_:CLIST + 3 * pi_ + 3]
            want[pi_] = (bytes(ns.pages[pg][(hi - 0x20) * 256 + 256 - 64 * nsp:(hi - 0x20) * 256 + 256]), nsp)
        exp_attr = [list(ns.scratch[ATTRB + 5 * i:ATTRB + 5 * i + 5]) for i in range(n)]
        pw0 = ns.pat_writes
        st['tre_at'] = 0
        if st.get('fr_on'):                 # patched T from the frame start to the render end (raster model)
            st['tre_at'] = st['facc'] + R[25] - st['f0'] + st['fx']
        tok = ns.scratch[V_TOK]
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        sp_ = _machine(Sim, p, list(R), ns)
        ns.events = []
        if st.get('fr_on'):                 # the beam: the frame starts at the interrupt (line INT_LINE);
            ns.line_t = INT_LINE + st['tre_at'] // LINE_T - R[25] // LINE_T   # patched T since then
        t0 = sp_.registers[25]
        ok_run = _run(so, (59092,), 400000) and _run(sp_, (59092,), 400000)
        ns.line_t = None
        if not ok_run:
            fail('render end: did not return', ())
            return
        t = sp_.registers[25] - t0
        xt(so, sp_)
        if st.get('fr_on'):
            st['Tre'] = st.get('Tre', 0) + sp_.registers[25] - so.registers[25]
        st['tmax'] = max(st['tmax'], t)
        st['tsum'] += t
        ro, rp = so.registers, sp_.registers
        diff = [k for k in CMP if ro[k] != rp[k]]
        if diff:
            fail('render end: registers differ', (diff,))
        md = [a for a in set(o.ov) | set(p.ov) if not 0x4000 <= a < 0x5B00 and o[a] != p[a]]
        if md:
            fail('render end: memory differs', (len(md), sorted(md)[:4]))
        if any(0x4000 <= a < 0x5B00 for a in o.ov) or any(0x4000 <= a < 0x5B00 for a in p.ov):
            fail('render end: screen written here (objects are fixed at band ends)', ())
        sh = st['shadow']
        if tok:                                     # every object cell with a tile was on a band
            s = MG(real, 48782)
            for i in range(NCELLS):
                if sh.ctile[i]:
                    row = 2 + ((i >> 5) - s // 8) % 22
                    if row not in st['bands']:
                        fail('render end: object cell on a char row without a band end', (i, row))
        c['render end'] += 1
        if ns.nr.get(0x50) != 0xFF:
            fail('render end: slot 0 not restored', ())
        N = MG(real, 58850)
        line0 = ns.last_line                        # the beam as the render end read it
        now = line0 >= RS_LINE and 327 - line0 - 20 >= n
        if ns.scratch[V_PEND] == (0 if now else 1) and ns.scratch[V_N58] == N:
            c['render end: commit %s' % ('at once' if now else 'deferred to the next interrupt')] += 1
        else:
            fail('render end: commit now / deferred', (line0, n, ns.scratch[V_PEND]))
        if ns.scratch[V_PEND]:
            if any(e[0] == 'nr' and (0x34 <= e[1] <= 0x39 or e[1] in (0x15, 0x6B, 0x6E, 0x6F, 0x1B))
                   for e in ns.events) or any(e[0] == 'port' for e in ns.events) or ns.pat_writes != pw0:
                fail('render end: deferred commit changed sprites / tilemap', ())
            st['pend'] = (want, exp_attr, n, tok, N)
            return
        check_commit(want, exp_attr, n, tok, N)

    def check_commit(want, exp_attr, n, tok, N):
        if tok:
            errs = commit_errors(ns.pages[PAGE_TM], ns.pages[PAGE_SH], ns.nr, ns.clip_tm, N)
            if errs or ns.scratch[V_MSD] != ns.scratch[V_MSB]:
                fail('render end: tilemap commit', errs[:3])
        elif ns.nr.get(0x6B) != 0 or ns.scratch[V_MSD] != 0xFF:
            fail('render end: tilemap not switched off', (ns.nr.get(0x6B),))
        i = 0
        for pi_ in sorted(want):
            data, nsp = want[pi_]
            for k in range(nsp):
                b = (i >> 1) * 256 + (i & 1) * 128
                if bytes(ns.pat[b:b + 64]) != data[64 * k:64 * k + 64] or any(ns.pat[b + 64:b + 128]):
                    fail('commit: pattern differs from the staged entry', (i,))
                if ns.attr[i] != exp_attr[i]:
                    fail('commit: attributes differ from the staged ones', (i, ns.attr[i], exp_attr[i]))
                i += 1
        if i != n:
            fail('commit: sprite count', (i, n))
        if ns.nr.get(0x15) != 1 or ns.nr.get(0x51) != 0xFF:
            fail('commit: sprites not on / MMU1 not restored', (ns.nr.get(0x15), ns.nr.get(0x51)))
        c['commits checked'] += 1
        vis = {i for i in range(128) if ns.attr[i][3] & 0x80}
        if not vis <= set(range(n)):
            fail('render end: sprite visible that no piece drew this frame', (n, sorted(vis - set(range(n)))[:6]))
        c['max sprites in a render'] = max(c['max sprites in a render'], n)

    def ev_end(real, R):
        c['walker calls (list ends)'] += 1
        if st['afp']:                               # AF' holds a canvas-derived byte: prove it dies
            ro_af, rp_af = st['afp']
            a, b = OMem(real), OMem(real)
            ma = _machine(Sim, a, list(R), NextState(patch))
            rb = list(R); rb[16:18] = rp_af
            mb = _machine(Sim, b, rb, NextState(patch))
            for step in range(100000):
                if all(ma.registers[i] == mb.registers[i] for i in CMP + [16, 17]):
                    if a.ov == b.ov:
                        c["AF' difference overwritten (converged)"] += 1
                    else:
                        fail("AF' convergence: memory differs", ())
                    break
                if ma.registers[24] != mb.registers[24] or ma.memory[ma.registers[24]] == 0x76:
                    fail("AF' used before overwritten", (step, ma.registers[24]))
                    break
                ma.opcodes[ma.memory[ma.registers[24]]]()
                mb.opcodes[mb.memory[mb.registers[24]]]()
            else:
                fail("AF' convergence: step limit", ())
            st['afp'] = None

    class HookMem(Memory):
        def __setitem__(s, a, v):
            if a in site_bytes and (s.o7ffd & 7) == 0 and st['sim'] is not None:
                fail('game wrote a patch site', (a,))
            if a in site_bytes1 and (s.o7ffd & 7) == 1 and st['sim'] is not None:
                fail('game wrote a bank-1 patch site', (a,))
            if st['render'] and 0x4000 <= a < 0x5800 and 59567 <= st['sim'].registers[24] < 60221:
                st['figw'].add(a)
            MS(s, a, v)

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            memory.__class__ = HookMem
            super().__init__(memory, registers, state_, config)
            st['sim'] = self
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in WATCH1 and (mem.o7ffd & 7) == 1:
                        cnt[('b1', pc)] += 1
                        if R[26]:
                            fail('interrupts enabled at a music hook', (pc,))
                        if pc == 0xD6D4:
                            ev_ay(mem, R)
                        elif pc == 0xD4DE:
                            ev_ps(mem, R)
                    if pc in WATCH and (mem.o7ffd & 7) == 0:
                        cnt[pc] += 1
                        if R[26] and pc not in (65029, 65076):
                            fail('interrupts enabled at a hook site', (pc,))
                        if pc == 59539:
                            ev_piece(mem, R)
                        elif pc in OBJ_SITES:
                            if st['render']:
                                fail('cell hook during a render (the tilemap is built at render start)', (pc,))
                            ev_cell(mem, R, pc)
                        elif pc == 58851:
                            ev_render_start(mem, R)
                            st['render'], st['figw'] = True, set()
                        elif pc == 59087:
                            st['render'] = False
                            ev_render_end(mem, R)
                        elif pc == 59547:
                            ev_end(mem, R)
                            ev_band(mem, R)
                        elif pc == 65172:
                            pend = st.pop('pend', None)
                            if (ns.scratch[V_PEND] != 0) != (pend is not None):
                                fail('limiter: commit pending flag', (ns.scratch[V_PEND],))
                            f7f = ns.nr.get(0x7F, 0)
                            ns.scratch[V_TICK] = LIMIT - 1          # the recording ran this frame
                            ns.line_t = INT_LINE - R[25] // LINE_T  # the interrupt: line 248
                            pw0, ns.events = ns.pat_writes, []
                            st['fr_on'] = False
                            fx0 = st.get('fx', 0)
                            ev_simple(mem, R, 65175, 'limiter: frame runs', dead=(1,))   # F: CP 3 next
                            ns.line_t = None
                            want = ay.tick()
                            if ay_writes(ns) != want:
                                fail('AY replay at the interrupt differs from the model', (ay_writes(ns)[:4], want[:4]))
                            if not ay.same(ns.scratch):
                                fail('AY queue after the interrupt differs from the model', ())
                            if ay.check is not None:
                                c['AY ticks sent at interrupts'] += 1
                                if ay.chip[:14] != ay.check:
                                    fail('AY chip after the replay differs from the original after that tick', ())
                            if pend is not None:
                                if ns.scratch[V_PEND]:
                                    fail('deferred commit: still pending', ())
                                elif f7f:               # a non-play screen came after the render: dropped
                                    if any(e[0] == 'nr' and 0x34 <= e[1] <= 0x39 for e in ns.events) or \
                                            ns.pat_writes != pw0 or ns.nr.get(0x15) or ns.nr.get(0x6B):
                                        fail('deferred commit: not dropped on a non-play screen', ())
                                    c['deferred commits dropped (non-play screen)'] += 1
                                else:
                                    check_commit(*pend)
                                    c['deferred commits checked'] += 1
                            st['fr_on'], st['f0'], st['facc'], st['fx'], st['fxi'] = True, R[25], 0, 0, 0
                            st['pf0'] = tuple(st.get(k, 0) for k in PROF_KEYS)
                            if ns.nr.get(0x07) != 3:
                                fail('limiter: not 28 MHz for the frame', (ns.nr.get(0x07),))
                        elif pc in (65029, 65076):
                            ev_simple(mem, R, 23698 if pc == 65029 else 23643, 'sprites off (non-play)')
                            if ns.nr.get(0x15) != 0 or ns.nr.get(0x6B) != 0 or ns.nr.get(0x7F) != 1:
                                fail('sprites / tilemap not switched off, or no cache flush', (pc,))
                        elif pc == 65274:
                            if st.get('fr_on'):
                                ft = st['facc'] + R[25] - st['f0'] + st['fx']
                                st['fr_on'] = False
                                st.setdefault('prof', []).append(
                                    (st['frame'], ft, ft - st['fx']) + tuple(st.get(k, 0) - v for k, v in
                                                                              zip(PROF_KEYS, st['pf0']))
                                    + (st.pop('tre_at', None),))
                                st['ftmax'] = max(st.get('ftmax', 0), ft)
                                c['game frames over 20 ms at 28 MHz'] += ft > 560000
                                c['game frames over 20 ms at 28 MHz without the item hooks'] += ft - st['fxi'] > 560000
                                c['patched game frame max (28 MHz us)'] = st['ftmax'] * 1000000 // 28000000
                                st['fimax'] = max(st.get('fimax', 0), st['fxi'])
                                c['item hooks per game frame max (28 MHz us)'] = st['fimax'] * 1000000 // 28000000
                                st['fisum'] = st.get('fisum', 0) + st['fxi']
                                st['fn'] = st.get('fn', 0) + 1
                                c['item hooks per game frame avg (28 MHz us)'] = st['fisum'] * 1000000 // 28000000 // st['fn']
                            ret = MG(mem, R[12] + 2) | MG(mem, R[12] + 3) << 8
                            ev_simple(mem, R, ret, 'handler exit')
                            if ns.nr.get(0x07) != 0:
                                fail('handler exit: not back to 3.5 MHz', (ns.nr.get(0x07),))
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if st.get('fr_on'):
            st['facc'] += st['sim'].registers[25]
        if progress and st['frame'] % 1000 == 0:
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
    # entry-point proof: patched instructions' interiors are only reached by fall-through
    if cnt[59539] != cnt[59541]:
        c['59541 reached other than from 59539!'] += 1
    if cnt[59543] != cnt[59544]:
        c['59544 reached other than from 59543!'] += 1
    if not 0 <= cnt[58851] - cnt[59087] <= 1:          # the recording may end mid-render
        c['render start/end counts differ (%d/%d)!' % (cnt[58851], cnt[59087])] += 1
    for a in (58852, 58853, 58854, 59088, 59089, 59540, 59542, 59545, 59546, 60856, 60842, 59548, 59549):
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    for a, b in ((0xD4DF, None), (0xD4E0, None), (0xD6D5, None), (0xD6D6, None), (0xD4E1, 0xD4DE),
                 (0xD6D7, 0xD6D4)):
        if cnt[('b1', a)] != (cnt[('b1', b)] if b else 0):
            c['bank 1 0x%04X reached other than by fall-through!' % a] += 1
    c['AY ticks queued'] = ay.opened
    c['AY queue full: oldest tick sent early'] = ay.flushed
    for site, inner in ((60853, (60854, 60855)), (60839, (60840, 60841)), (60965, (60966, 60967, 60968))):
        for a in inner:                     # instruction starts inside a JP: only by fall-through
            if cnt[a] != cnt[site]:
                c['%d reached other than from %d!' % (a, site)] += 1
    c['frames'] = st['frame']
    c['render end T max (28 MHz us)'] = st['tmax'] * 1000000 // 28000000
    c['render end T avg (28 MHz us)'] = st['tsum'] * 1000000 // 28000000 // max(c['render end'], 1)
    c['render start T max (28 MHz us)'] = st.get('tsmax', 0) * 1000000 // 28000000
    for k, name in (('T0', 'render start'), ('T1', 'bands'), ('T2', 'cell hooks')):
        c['_T %s total (28 MHz ms)' % name] = st.get(k, 0) // 28000
    verify.profile = st.get('prof', [])     # per game frame: (frame, total T, original T, extra T per PROF_KEYS)
    return c, dict(ex)


# ---------------------------------------------------------------------------------------------
# Unit tests for paths the recordings do not reach (edge columns, >= MAXP pieces, class colours)
# ---------------------------------------------------------------------------------------------

class _BankMem:
    """Stand-alone 128K memory view (bank at C000 = o7ffd & 7, 48K ROM below 0x4000)."""

    def __init__(self, banks, o7ffd, rom):
        self.banks, self.o7ffd, self.rom = [bytearray(b) for b in banks], o7ffd, rom

    def __getitem__(self, a):
        s = a >> 14
        if s == 0:
            return self.rom[a]
        b = (5, 2, self.o7ffd & 7)[s - 1]
        return self.banks[b][a & 0x3FFF]


def _pair(patch, bm, regs, n_before, scratch=None, pat=None, pages=None, stops=(59513, 59547), oregs=None,
          line_t=None, nr=None):
    """Run original and patched code from one dispatch state (PC 59539) on views of bm.
    Returns (orig_regs, orig_overlay, patched_regs, patched_overlay, NextState, errors)."""
    from .dizzy6 import _rw_simulator
    from .build import rom48
    Sim = _rw_simulator()
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    ns = NextState(patch)
    if scratch is not None:
        ns.scratch[:] = scratch
    if pat is not None:
        ns.pat[:] = pat
    if pages is not None:
        for k, v in pages.items():
            ns.pages[k] = bytearray(v)
    ns.scratch[V_S] = n_before
    ns.line_t = line_t
    if nr:
        ns.nr.update(nr)
    err = []

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return bm[a] if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                    return ns.scratch[a]
                if a >= 0x2000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                    return ns.pages[ns.nr[0x51]][a - 0x2000]
                return alt[a]
            if a < 0x8000:
                pg = ns.nr.get(0x52 + ((a >> 13) & 1))
                if pg != 10 + ((a >> 13) & 1):
                    return ns.pages[pg][a & 0x1FFF]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                ns.scratch[a] = v
            elif 0x2000 <= a < 0x4000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                ns.pages[ns.nr[0x51]][a - 0x2000] = v
            elif a < 0x4000:
                err.append(('rom write', a))
            elif a < 0x8000 and ns.nr.get(0x52 + ((a >> 13) & 1)) != 10 + ((a >> 13) & 1):
                ns.pages[ns.nr[0x52 + ((a >> 13) & 1)]][a & 0x1FFF] = v
            else:
                s.ov[a] = v
    o, p = O(), P()
    so = _machine(Sim, o, list(oregs or regs), NextState(patch))
    sp_ = _machine(Sim, p, list(regs), ns)
    if not (_run(so, stops) and _run(sp_, stops)):
        err.append('did not return')
    return so.registers, o, sp_.registers, p, ns, err


def _pixels_ok(ns, first, bm, o, transparent=False):
    """Sprites first..first+3 against the original plot (before = bm, after = overlay o)."""
    cov = {}
    for i in range(first, min(first + 4, 128)):
        px = ns.sprite_pixels(i)
        for x, y, idx in px or ():
            if idx and 0 <= x < 256 and 0 <= y < 192:
                cov[(x, y)] = idx

    def at(m, x, y):
        a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
        return (m[a] >> (7 - (x & 7))) & 1
    bad = sum(1 for (x, y), idx in cov.items() if (idx == 1) != (at(o, x, y) == 1))
    for a in o.ov:
        if 0x4000 <= a < 0x5800:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                x = (a & 31) * 8 + k
                if (x, y) not in cov and ((bm[a] ^ o.ov[a]) >> (7 - k)) & 1:
                    if not (transparent and not (o.ov[a] >> (7 - k)) & 1):
                        bad += 1
    return bad


def _pix(ns, first, bm, o, **kw):
    return _pixels_ok(staged(ns, first), first, bm, o, **kw)


def unit_tests(patch, rzx_path, want=40, frames=3000):
    """Collect `want` dispatch states from the RZX, then for each: move the piece to edge columns,
    run with n = MAXP-1 and n = MAXP (passthrough), and a negative control (ink/outline swapped)."""
    import copy
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .build import rom48
    rom = rom48()
    states, seen, hstates, rstates, cstates = [], set(), [], [], {60853: [], 60839: [], 60965: []}

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    if R[24] == 65172 and (mem.o7ffd & 7) == 0 and len(hstates) < 6:
                        hstates.append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    if R[24] == 58851 and (mem.o7ffd & 7) == 0 and len(rstates) < 2 and R[25] % 7 == 0:
                        rstates.append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    if R[24] in cstates and (mem.o7ffd & 7) == 0 and len(cstates[R[24]]) < 3:
                        cstates[R[24]].append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    if R[24] == 59539 and (mem.o7ffd & 7) == 0 and len(states) < want:
                        ix = R[8] * 256 + R[9]
                        if ix not in (60176, 60180) and (ix, len(states) // 8) not in seen:
                            seen.add((ix, len(states) // 8))
                            states.append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])
    old = rzxplay.Simulator, rzxplay.CSimulator
    rzxplay.Simulator, rzxplay.CSimulator = S, None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0', '--stop', str(frames), rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.Simulator, rzxplay.CSimulator = old
    c = collections.Counter()
    bad_patch = copy.deepcopy(patch)
    sc = bytearray(bad_patch.scratch)
    t = bytearray(Config().nibtab())                               # ink and outline indices swapped
    for i in range(512):
        hi, lo = t[i] >> 4, t[i] & 15
        sw = {1: 2, 2: 1}
        t[i] = sw.get(hi, hi) << 4 | sw.get(lo, lo)
    sc[NIBTAB:NIBTAB + 512] = t
    bad_patch.scratch = bytes(sc)
    import random
    rnd = random.Random(7)
    peek0 = _BankMem(states[0][0], states[0][1], rom)
    for banks, o7, R in states:
        bm = _BankMem(banks, o7, rom)
        ix = R[8] * 256 + R[9]
        pi = patch.plot[ix]
        right = ix in (59717, 59759, 59801, 59843)                 # plotters that run leftwards
        cols = (2, 3, 16, 29, 31) if right else (0, 1, 16, 26, 29)
        for col in cols:
            r = list(R)
            r[5] = (r[5] & 0xE0) | col
            ro, o, rp, p, ns, err = _pair(patch, bm, r, 5)
            ok = not err and all(ro[i] == rp[i] for i in CMP) and not any(0x4000 <= a < 0x5B00 for a in p.ov)
            ok = ok and _pix(ns, 5, bm, o) == 0 and ns.scratch[V_S] == 5 + pi['nspr']
            width = {60105: 1, 60110: 2, 60115: 3, 60120: 4, 60125: 5, 60130: 6}.get(ix, 3)
            wraps = col - 2 < 0 if right else col + width > 32
            if wraps:                  # the ULA wraps into the next char row; the sprite clips
                c['edge column wraps on the ULA (sprite clips; not a game case) %s' % ('same' if ok else 'differs')] += 1
            else:
                c['edge column %s' % ('ok' if ok else 'FAIL!')] += 1
                if not ok:
                    c['  fail ix %d col %d' % (ix, col)] += 1
        for n, what in ((NSPR_MAX - pi['nspr'], 'last sprites'), (NSPR_MAX - pi['nspr'] + 1, 'passthrough')):
            ro, o, rp, p, ns, err = _pair(patch, bm, R, n)
            same = all(ro[i] == rp[i] for i in CMP + [16, 17]) and o.ov == p.ov and ns.scratch[V_S] == n \
                if what == 'passthrough' else _pix(ns, n, bm, o) == 0 and ns.scratch[V_S] == NSPR_MAX
            c['%s %s' % (what, 'ok' if same and not err else 'FAIL!')] += 1
        ro, o, rp, p, ns, err = _pair(bad_patch, bm, R, 3)
        visible = any(staged(ns, 3).attr[i][3] & 0x80 for i in range(3, 3 + pi['nspr']))   # (staged:
        # attributes reach the sprites only at the render-end commit; ns.attr made this n/a every time)
        if not visible:
            c['negative control n/a (piece has no pixels)'] += 1
        else:
            c['negative control %s' % ('detected' if _pix(ns, 3, bm, o) else 'NOT DETECTED!')] += 1
    # plotter layouts (direct conversion): profile = derivation from the game's plotters; window
    # covers every plotter's extent; the Python model of the hook's conversion reproduces the
    # plotter on random streams; negative control: one corrupted layout byte must be caught
    lay = plotter_layouts(peek0)
    c['plotter layout table %s' % ('ok' if {str(k): v for k, v in lay.items()} == patch.prof['plotters']
                                   else 'FAIL!')] += 1
    ext = plotter_extents(peek0)
    for t, (lo, hi) in ext.items():
        if t in patch.plot:
            pi = patch.plot[t]
            c['window covers plotter extent %s' % (
                'ok' if -pi['off'] <= lo and hi <= 2 * pi['nspr'] - 1 - pi['off'] else 'FAIL!')] += 1
    from skoolkit.simulator import Simulator
    base = bytearray(peek0[a] for a in range(65536))

    def truth(t, cy, stream):
        out = []
        for fill in (0, 0xFF):
            m = bytearray(base)
            m[0x4000:0x5800] = bytes([fill]) * 0x1800
            m[0x8000:0x8000 + len(stream)] = stream
            sim = Simulator(m, {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
            sim.registers[17] = cy
            _run(sim, (59543,), 5000)
            out.append(m)
        return out

    def model_ok(info, t, cy, stream):
        g, mg = truth(t, cy, stream)
        G, M = layout_convert(info, cy, stream)
        for row in range(10):
            for col in range(2 * info['nspr']):
                a = (0x48 + row) * 256 + 0x48 - info['off'] + col
                if row >= 8 and (row, col) not in G and (row, col) not in M:
                    continue
                if G.get((row, col), 0) != g[a] or M.get((row, col), 0xFF) != mg[a]:
                    return False
        return True
    for t, info in sorted(patch.plot.items()):
        for cy in (0, 1):
            n = info['len'][cy]
            good = all(model_ok(info, t, cy, bytes(rnd.randrange(256) for _ in range(n))) for _ in range(4))
            c['direct conversion = plotter (random streams) %s' % ('ok' if good else 'FAIL!')] += 1
    bad = dict(patch.plot[59699])
    lb = bytearray.fromhex(bad['layout'][0])
    lb[1] ^= 0x40                                               # one byte wrongly mirrored
    bad['layout'] = [lb.hex(), bad['layout'][1]]
    st_ = bytes(rnd.randrange(1, 255) for _ in range(bad['len'][0]))
    c['layout negative control %s' % ('detected' if not model_ok(bad, 59699, 0, st_) else 'NOT DETECTED!')] += 1
    rev_ok = all(base[0xF500 + i] == int('{:08b}'.format(i)[::-1], 2) for i in range(256))
    c['game table page 245 = bit reversal %s' % ('ok' if rev_ok else 'FAIL!')] += 1
    # LEFT4 plotters (only the boss spider uses them) on real graphics streams
    for banks, o7, R in states[:8]:
        bm = _BankMem(banks, o7, rom)
        for ix in LEFT4:
            for col in (3, 16, 28):
                r = list(R)
                r[8], r[9] = ix >> 8, ix & 255
                r[4] = (r[4] & 0xF8) | 2 * LEFT4.index(ix)     # entry for 8/6/4/2 rows: start row 0/2/4/6
                r[5] = (r[5] & 0xE0) | col
                ro, o, rp, p, ns, err = _pair(patch, bm, r, 5)
                ok = not err and all(ro[i] == rp[i] for i in CMP) and \
                    not any(0x4000 <= a < 0x5B00 for a in p.ov) and _pix(ns, 5, bm, o) == 0
                c['left-entry 4-wide plotter %s' % ('ok' if ok else 'FAIL!')] += 1
    # pattern store: a repeat piece HITS and draws exactly the original; a changed stream at the
    # same address MISSES; garbage store pages never hit. Negative controls: stream compare patched
    # out (stale image), corrupted patterns in the stored entry.
    cj = patch.syms['s_pc.cmpj']
    if patch.scratch[cj] != 0x20:
        raise ValueError('s_pc.cmpj is not JR NZ')

    def hits(ns):
        return ns.scratch[V_HITS] | ns.scratch[V_HITS + 1] << 8

    class Mod:
        def __init__(s, bm, ov):
            s.bm, s.ov = bm, ov

        def __getitem__(s, a):
            return s.ov.get(a, s.bm[a])
    garbage = {STORE_PG + k: bytes(rnd.randrange(256) for _ in range(8192)) for k in range(STORE_PAGES)}
    for si, (banks, o7, R) in enumerate(states):
        bm = _BankMem(banks, o7, rom)
        ro, o1, rp, p, ns, err = _pair(patch, bm, R, 3, pages=garbage if si < 4 else None)
        ok = not err and hits(ns) == 0 and _pix(ns, 3, bm, o1) == 0 and all(ro[i] == rp[i] for i in CMP)
        c['store first sighting misses%s %s' % (' (garbage store)' if si < 4 else '', 'ok' if ok else 'FAIL!')] += 1
        store = {k: v for k, v in ns.pages.items() if k >= STORE_PG}
        ro, o, rp, p, ns2, err = _pair(patch, bm, R, 5, scratch=ns.scratch, pages=store)
        ok = not err and all(ro[i] == rp[i] for i in CMP) and hits(ns2) == 1 and _pix(ns2, 5, bm, o) == 0
        c['store hit (registers, pixels) %s' % ('ok' if ok else 'FAIL!')] += 1   # (AF': verify proves it dies)
        sp0, ln = R[12], patch.plot[R[8] * 256 + R[9]]['len'][R[17] & 1]
        cb = sp0 + ln - 1 if ln > 16 else sp0 + 1              # beyond the hashed 16 bytes if possible
        chg = Mod(bm, {cb: bm[cb] ^ 0xFF})
        ro, o, rp, p, ns3, err = _pair(patch, chg, R, 5, scratch=ns.scratch, pages=store)
        ok = not err and hits(ns3) == 0 and _pix(ns3, 5, chg, o) == 0
        c['store changed stream -> miss %s' % ('ok' if ok else 'FAIL!')] += 1
        sc = bytearray(ns.scratch)
        sc[cj:cj + 2] = b'\x00\x00'
        ro, o, rp, p, ns4, err = _pair(patch, chg, R, 5, scratch=sc, pages=store)
        if ln <= 16:
            c['store no-compare negative control n/a (stream fully hashed)'] += 1
        elif {a: v for a, v in o.ov.items() if a < 0x5800} == {a: v for a, v in o1.ov.items() if a < 0x5800}:
            c['store no-compare negative control n/a (changed byte draws the same)'] += 1
        else:
            c['store no-compare negative control %s' % (
                'detected' if _pix(ns4, 5, chg, o) else 'NOT DETECTED!')] += 1
        pg, hi = ns.scratch[0x28], ns.scratch[0x27]               # V_EPG, V_ENT+1 of this piece
        stale = {k: bytearray(v) for k, v in store.items()}
        e0 = (hi - 0x20) * 256
        nsp = patch.plot[R[8] * 256 + R[9]]['nspr']
        for i in range(e0 + 256 - 64 * nsp, e0 + 256):
            stale[pg][i] ^= 0x11
        ro, o, rp, p, ns5, err = _pair(patch, bm, R, 5, scratch=ns.scratch, pages=stale)
        if not any(staged(ns, 3).attr[i][3] & 0x80 for i in range(3, 3 + nsp)):
            c['store stale-pattern negative control n/a (piece has no pixels)'] += 1
        else:
            c['store stale-pattern negative control %s' % (
                'detected' if _pix(ns5, 5, bm, o) else 'NOT DETECTED!')] += 1
    # frame limiter: tick < LIMIT-1 -> the interrupt returns at once, exactly like the original's
    # POP AF / EI / RET at 65274, tick counted, CPU at 3.5 MHz; tick = LIMIT-1 -> the frame runs
    # (reaches 65175 as the original, tick 0, 28 MHz). Control: the skip jump patched out.
    sl = patch.syms['s_lim.skip']
    for banks, o7, R in hstates:
        bm = _BankMem(banks, o7, rom)
        ret = bm[R[12] + 2] | bm[R[12] + 3] << 8
        for tick in range(LIMIT):
            sc = bytearray(patch.scratch)
            sc[V_TICK] = tick
            runs = tick == LIMIT - 1
            oR = list(R)
            if not runs:
                oR[24] = 65274                                 # original: straight to the exit
            ro, o, rp, p, ns, err = _pair(patch, bm, R, 0, scratch=sc, oregs=oR,
                                          stops=(65175,) if runs else (ret,))
            ok = not err and all(ro[i] == rp[i] for i in CMP + [24] if not (runs and i == 1)) and o.ov == p.ov and \
                ns.scratch[V_TICK] == (0 if runs else tick + 1) and ns.nr.get(0x07) == (3 if runs else 0)
            c['limiter %s %s' % ('frame runs' if runs else 'interrupt skipped', 'ok' if ok else 'FAIL!')] += 1
    if hstates:
        banks, o7, R = hstates[0]
        bm = _BankMem(banks, o7, rom)
        ret = bm[R[12] + 2] | bm[R[12] + 3] << 8
        sc = bytearray(patch.scratch)
        sc[V_TICK] = 0
        k = bytes(sc).find(b'\x38', patch.syms['s_lim'], sl)
        sc[k:k + 2] = b'\x00\x00'
        ro, o, rp, p, ns, err = _pair(patch, bm, R, 0, scratch=sc, stops=(65175, ret))
        c['limiter negative control (skip removed) %s' % (
            'detected' if rp[24] == 65175 else 'NOT DETECTED!')] += 1
    else:
        c['limiter states FAIL! (none collected)'] += 1
    # render-end commit: negative control through the verifier itself (a short replay with the
    # commit writing attribute 4 to the wrong register must fail the commit check)
    bc = copy.deepcopy(patch)
    sc = bytearray(bc.scratch)
    k = patch.syms['commit.a5']
    if sc[k:k + 2] != b'\xED\xA3':
        raise ValueError('commit.a5 is not OUTI')
    sc[k:k + 2] = b'\x00\x00'
    bc.scratch = bytes(sc)
    bc.extra_banks = {12: bc.page + bc.fpage, 13: bc.scratch + bc.tpage}
    cc, _ = verify(bc, rzx_path, stop=1500)
    c['commit negative control (attr 4 not written) %s' % (
        'detected' if any(k.startswith('commit: attributes') for k in cc) else 'NOT DETECTED!')] += 1
    # Z80N SWAPNIB in the simulator: exhaustive opcode test; negative control = the hooks run with
    # ED 23 as SkoolKit's silent NOP must produce wrong pixels
    c['SWAPNIB simulator self-test %s' % ('ok' if swapnib_selftest() == 0 else 'FAIL!')] += 1
    nop_patch = copy.deepcopy(patch)
    nop_patch.no_swapnib = True
    det = 0
    for banks, o7, R in states:
        bm = _BankMem(banks, o7, rom)
        ro, o, rp, p, ns, err = _pair(nop_patch, bm, R, 3)
        det += _pix(ns, 3, bm, o) > 0
    c['SWAPNIB-as-NOP negative control %s' % ('detected' if det else 'NOT DETECTED!')] += 1
    # pattern bottom halves: setup must zero pattern RAM; negative control = setup without its
    # OUT (0x5B) in the zero loop must be caught
    c['setup zeroes pattern RAM %s' % ('ok' if setup_zeroes_patterns(patch) is None else 'FAIL!')] += 1
    np_ = copy.deepcopy(patch)
    zb = patch.syms['setup.zb'] - 0xD000
    se = bytearray(np_.stub_extra)
    if se[zb:zb + 2] != b'\xD3\x5B':
        raise ValueError('setup.zb is not OUT (0x5B),A')
    se[zb:zb + 2] = b'\x00\x00'
    np_.stub_extra = bytes(se)
    c['setup-without-zeroing negative control %s' % (
        'detected' if setup_zeroes_patterns(np_) else 'NOT DETECTED!')] += 1
    # class colour hook: page -> palette offset in attr 2 bits 7-4
    cc = RainbowPatch(Config(class_colours={'pages': {'%02X' % (states[0][2][12] >> 8): 5},
                                            'palettes': {'5': {'ink': '#FF0000'}}}), patch.prof)
    banks, o7, R = states[0]
    ro, o, rp, p, ns, err = _pair(cc, _BankMem(banks, o7, rom), R, 0)
    t = staged(ns, 0)
    offs = {t.attr[i][2] >> 4 for i in range(4) if t.attr[i][3] & 0x80}
    c['class colour offset %s' % ('ok' if offs == {5} and cc.cfg.palette()[81] == 0xE0 else '%s FAIL!' % offs)] += 1
    # a class without outline (the thrown rainbow, 2026-10-19): its patterns hold ink and transparent
    # pixels only, the others keep their outline; control: the drop of outline pixels removed
    pg0 = '%02X' % (states[0][2][12] >> 8)
    nc = RainbowPatch(Config(class_colours={'pages': {pg0: 5}, 'palettes': {'5': {'outline': 'transparent'}}}),
                      patch.prof)

    def outl(pt):
        n2 = n1 = 0
        for banks_, o7_, R_ in states:
            if '%02X' % (R_[12] >> 8) != pg0:
                continue
            _, o_, _, _, ns_, err_ = _pair(pt, _BankMem(banks_, o7_, rom), R_, 0)
            t_ = staged(ns_, 0)
            for i_ in range(4):
                if t_.attr[i_][3] & 0x80:
                    px_ = t_.sprite_pixels(i_) or []
                    n2 += sum(1 for x_, y_, v_ in px_ if v_ == 2)
                    n1 += sum(1 for x_, y_, v_ in px_ if v_ == 1)
        return n1, n2
    a1, a2 = outl(nc)
    b1, b2 = outl(_with_bytes(nc, 'nooutl.w', b'\x71', b'\x00'))
    p1, p2 = outl(patch)
    c['class without outline (ink %d, outline %d; normal class outline %d) %s' % (
        a1, a2, p2, 'ok' if a1 and not a2 and p2 else 'FAIL!')] += 1
    c['class without outline negative control (outline kept) %s' % ('detected' if b2 else 'NOT DETECTED!')] += 1
    ay_unit_tests(patch, c)
    obj_unit_tests(patch, rstates, cstates, rom, c, rzx_path)
    c['states'] = len(states)
    return c


def _ay_writes(ns_):
    return [(e[1], e[2]) for e in ns_.events if e[0] == 'port' and e[1] & 0x8002 == 0x8000]


def ay_unit_tests(patch, c):
    """The AY queue routines (alt ROM) against AYModel on long random sequences shaped like play:
    per game frame an interrupt that runs it, 3 player ticks (1-4 register writes each), then the
    skip interrupts; with overrun frames (an interrupt lost), writes outside a tick (the silence
    routine) and non-sound registers (straight to the chip). Every step: the chip writes and the
    queue = the model, and after each interrupt the chip = the original's registers at the close of
    the tick sent. Negative control: the OUT of the value removed."""
    import random
    from .dizzy6 import _rw_simulator
    Sim = _rw_simulator()

    def ops_for(seed, frames):
        rnd = random.Random(seed)
        ops = []
        for f in range(frames):
            ops.append(('int',))
            for t in range(3):
                ops.append(('open',))
                for w in range(rnd.randrange(1, 5)):
                    ops.append(('w', rnd.choice((0, 1, 2, 3, 6, 7, 8, 9, 10, 11, 13)), rnd.randrange(256)))
            if rnd.random() < 0.05:
                ops.append(('w', rnd.randrange(14), 0))            # silence routine, no tick
            if rnd.random() < 0.03:
                ops.append(('w', 14 + rnd.randrange(2), rnd.randrange(256)))
            for k in range(0 if rnd.random() < 0.1 else rnd.choice((1, 2, 2, 2, 3))):
                ops.append(('int',))
        return ops

    def run_case(pt, ops):
        ns = NextState(pt)
        ns.nr[0x50] = PAGE_S
        ram = bytearray(65536)

        class M:
            def __getitem__(s_, a):
                if a < 0x2000:
                    return ns.scratch[a]
                if a < 0x4000:
                    return pt.page[a - 0x2000]
                return ram[a]

            def __setitem__(s_, a, v):
                if a < 0x2000:
                    ns.scratch[a] = v
                elif a >= 0x4000:
                    ram[a] = v

            def __len__(s_):
                return 65536
        model = AYModel()
        bad = sent = 0
        for op in ops:
            regs = [0] * 29
            regs[12], regs[24] = 0xF000, pt.syms[{'int': 'aytick', 'open': 'ayopen', 'w': 'aywr'}[op[0]]]
            ram[0xF000], ram[0xF001] = 0xF0, 0xFF
            if op[0] == 'w':
                regs[0], regs[4] = op[1], op[2]
                want = model.write(op[1], op[2])
            elif op[0] == 'open':
                want = model.open()
            else:
                want = model.tick()
            sim = _machine(Sim, M(), regs, ns)
            ns.events = []
            ok = _run(sim, (0xFFF0,), 20000) and _ay_writes(ns) == want and model.same(ns.scratch)
            if op[0] == 'int' and model.check is not None:
                sent += 1
                ok &= model.chip[:14] == model.check
            bad += not ok
        return bad, sent, model.flushed
    bad, sent, fl = run_case(patch, ops_for(5, 400))
    c['AY queue: %d ticks sent at interrupts (%d sent early, queue full) %s' % (
        sent, fl, 'ok' if not bad and sent and fl else '%d steps FAIL!' % bad)] += 1
    bad, _, _ = run_case(_with_rom_bytes(patch, 'ayplay.o', b'\xED\x79', b'\x00\x00'), ops_for(5, 40))
    c['AY queue negative control (values not sent) %s' % ('detected' if bad else 'NOT DETECTED!')] += 1


def _with_rom_bytes(patch, sym, old, new):
    """A copy of the patch whose alt-ROM code has `old` at symbol `sym` replaced by `new`."""
    import copy
    b = copy.deepcopy(patch)
    a = patch.syms[sym] - 0x2000
    pg = bytearray(b.page)
    if old is not None and bytes(pg[a:a + len(old)]) != old:
        raise ValueError('%s is not %s' % (sym, old.hex()))
    pg[a:a + len(new)] = new
    b.page = bytes(pg)
    b.extra_banks = {12: b.page + b.fpage, 13: b.scratch + b.tpage}
    return b


def _with_bytes(patch, sym, old, new):
    """A copy of the patch whose page-26 code has `old` at symbol `sym` replaced by `new`."""
    import copy
    b = copy.deepcopy(patch)
    a = patch.syms[sym]
    sc = bytearray(b.scratch)
    if old is not None and bytes(sc[a:a + len(old)]) != old:
        raise ValueError('%s is not %s' % (sym, old.hex()))
    sc[a:a + len(new)] = new
    b.scratch = bytes(sc)
    b.extra_banks = {12: b.page + b.fpage, 13: b.scratch + b.tpage}
    return b


def drop_tile(tm0, sm0, scratch, i, ct):
    """Expected map on screen (page 14, first 0x0A00 bytes) and shadow map (page 28, 1280 bytes) after a
    cell hook on cell i that dropped tile ct (0: nothing dropped): the cell's entry cleared in each
    map that shows it (scroll V_MSD / V_MSB)."""
    want, wsh = bytearray(tm0), bytearray(sm0)
    if ct:
        for m, v in ((want, V_MSD), (wsh, V_MSB)):
            s = scratch[v]
            if s != 0xFF:
                kk = ((i >> 5) - s // 8) % 22
                if kk < 20:
                    o = map_pos(kk, i & 31) if m is want else sh_pos(kk, i & 31)
                    m[o] = m[o + 1] = 0
    return bytes(want), bytes(wsh)


def tilemap_errors(pg, tm, shm, exp, front_defs):
    """Shadow map shm (page 28) and tile definitions (page 14 image tm) after render start against
    obj_build's model `exp`; tiles of the map on screen (front_defs: tile -> 32 bytes before the
    build) untouched. Returns a list of faults."""
    errs = []
    for kk in range(20):
        for col in range(32):
            t, at = shm[sh_pos(kk, col)], shm[sh_pos(kk, col) + 1]
            e = exp.get((kk, col))
            if e is None:
                if t or at:
                    errs.append(('tile without object', kk, col))
                continue
            i, key, data, attr = e
            if pg[CTILE - 0x2000 + i] != t:
                errs.append(('ctile', i))
            if not t:
                errs.append(('no tile', i))
            elif bytes(tm[TDEF + 32 * t:TDEF + 32 * t + 32]) != data or at != attr:
                errs.append(('content', i, key.hex()))
    for t, d in front_defs.items():
        if bytes(tm[TDEF + 32 * t:TDEF + 32 * t + 32]) != d:
            errs.append(('on-screen tile overwritten', t))
    if any(tm[TDEF:TDEF + 32]):
        errs.append(('tile 0 written',))
    return errs


def commit_errors(tm, shm, nr, clip, N):
    """Render end with the tilemap on: the shadow map copied into the map on screen (rows 6-25,
    columns 4-35; the rest untouched = 0), NextRegs $6E/$6F/$6B and the clip window."""
    errs = []
    for kk in range(20):
        if bytes(tm[map_pos(kk, 0):map_pos(kk, 0) + 64]) != bytes(shm[sh_pos(kk, 0):sh_pos(kk, 0) + 64]):
            errs.append(('map row', kk))
    if not (nr.get(0x6E) == 0x80 and nr.get(0x6F) == 0x80 | (TDEF >> 8) and nr.get(0x6B) == 0x81 and
            clip == [16, 143, 48, 47 + N]):
        errs.append(('registers', nr.get(0x6E), nr.get(0x6F), nr.get(0x6B), clip))
    return errs


def obj_unit_tests(patch, rstates, cstates, rom, c, rzx_path):
    """Objects on the tilemap: cell hooks (every register incl. F, object map = model, dropped tile
    cleared in both maps) on random states; render paths (render start -> every band -> render
    end) on synthetic object maps; tile cache (hit, on-screen tiles kept, flush); raster wait;
    profile tables. Every negative control must be detected."""
    import random
    rnd = random.Random(23)

    class Mod:
        def __init__(s, bm, ov):
            s.bm, s.ov = bm, ov

        def __getitem__(s, a):
            return s.ov.get(a, s.bm[a])
    if not all(cstates.values()) or not rstates:
        c['object states FAIL! (not collected: %s)' % {k: len(v) for k, v in cstates.items()}] += 1
        return

    def rnd_shadow():
        sh = ObjShadow()
        for i in range(NCELLS):
            r = rnd.random()
            if r < 0.5:
                continue
            sh.tiles[i] = rnd.randrange(256)
            sh.flags[i] = rnd.choice((0, 0x80, 0x80, 0x83, 0x8C))
            sh.objo[i] = rnd.choice((0, 0, 3, 20, 99, 0xFF))
            sh.m1[i] = rnd.choice((0, 0, 0x50, 0x5A, 0x12))
            sh.m2[i] = rnd.choice((0, 0x30, 0x34)) if sh.m1[i] & 0x0F else 0
            sh.ctile[i] = rnd.choice((0, 0, 7, 150))
        return sh

    def cell_cases(pt):
        out = bad = 0
        for site, sts in cstates.items():
            for banks, o7, R0 in sts:
                bm = _BankMem(banks, o7, rom)
                for case in range(30):
                    r = list(R0)
                    r[24] = site
                    if site == 60853:
                        r[0] = rnd.randrange(256)
                    else:
                        r[0] = rnd.choice((0, 1, 2, 7, 13, 14, 15, 19, 99, 190, 255))
                    if site == 60965 and case % 6 == 2:
                        r[0] = rnd.choice((7, 13))
                    d, e = rnd.choice(((0x9F, 0), (0xB4, 31), (0xA5, 17), (0x9E, 3), (0xB5, 3), (0xA0, 32),
                                       (0x9F + rnd.randrange(22), rnd.randrange(32))))
                    r[4], r[5] = d, e
                    r[1] = (r[1] & 0xFE) | rnd.randrange(2)
                    bc2 = rnd.choice((0x6000 + rnd.randrange(0x2000), 0x8000 + rnd.randrange(0x4000),
                                      0xC000 + rnd.randrange(0x4000)))
                    r[18], r[19] = bc2 >> 8, bc2 & 255
                    sh = rnd_shadow()
                    i0 = cell_index(d, e)
                    if i0 is not None and case % 4 == 0:
                        sh.ctile[i0] = 1 + rnd.randrange(NTILE - 1)         # a tile to drop
                    if i0 is not None and site == 60965 and case % 5 == 1:
                        sh.objo[i0], sh.m1[i0], sh.m2[i0] = 0, 0x12, 0x34    # list full
                    pg = bytearray(patch.tpage)
                    pg[OCLASS - 0x2000 + 99] = 2                            # leave as drawn
                    pg[MCLASS - 0x2000 + 13] = 2
                    pg[OCLASS - 0x2000 + 19] = 0x51                         # rainbow, fixed ink
                    pg[MCLASS - 0x2000 + 7] = 0x30                          # item, fixed ink
                    sh.load(pg)
                    tm = bytearray(rnd.randrange(256) for _ in range(8192))
                    shm = bytearray(rnd.randrange(256) for _ in range(8192))
                    sc = bytearray(pt.scratch)
                    sc[V_MSB] = rnd.choice((0xFF, 0, 8 * rnd.randrange(22)))
                    sc[V_MSD] = rnd.choice((0xFF, 8 * rnd.randrange(22)))
                    i, ct = sh.event(site, r[0], d, e, lambda a: bm[a], bc2, pg)
                    want, wsh = drop_tile(bytes(tm[:0x0A00]), bytes(shm[:20 * 64]), sc, i, ct)
                    ro, ov, rp, pv, ns, err = _pair(pt, bm, r, 0, scratch=sc,
                                                    pages={PAGE_T: pg, PAGE_TM: tm, PAGE_SH: shm},
                                                    stops=(OBJ_SITES[site],))
                    ok = not err and all(ro[k] == rp[k] for k in CMP + [16, 17]) and ov.ov == pv.ov and \
                        sh.same_as(ns.pages[PAGE_T]) and bytes(ns.pages[PAGE_TM][:0x0A00]) == want and \
                        ns.pages[PAGE_TM][0x0A00:] == tm[0x0A00:] and \
                        bytes(ns.pages[PAGE_SH][:20 * 64]) == wsh and ns.pages[PAGE_SH][20 * 64:] == shm[20 * 64:] and \
                        ns.nr.get(0x50) == 0xFF and ns.nr.get(0x51) == 0xFF and ns.nr.get(0x52) == 10 and \
                        ns.nr.get(0x53) == 11
                    out += 1
                    bad += not ok
        return out, bad
    n, bad = cell_cases(patch)
    c['object cell hooks (registers incl. F, object map = model, dropped tiles) %s' % ('ok' if not bad else 'FAIL!')] += n
    for sym, new, what in (('s_ov.wr', b'\x00', 'opaque object not recorded'),
                           ('s_ov.rla', b'\x00', 'carry not restored'),
                           ('oafter.tg', b'\x00', 'occupancy mask not kept')):
        n, bad = cell_cases(_with_bytes(patch, sym, None, new))
        c['object cell hook negative control (%s) %s' % (what, 'detected' if bad else 'NOT DETECTED!')] += 1

    def scen(bm, pg):
        """Synthetic object map on real game memory: every kind of cell."""
        s, N = 16, 155                       # cell rows wrap; the bottom char row is partial
        ov = {48782: s, 58850: N}
        sh = ObjShadow()
        cells = []

        def put(kk, col, tile, objo=0, m=(), flags=0x80, ink=None):
            k = (s // 8 + kk) % 22
            i = 32 * k + col
            sh.tiles[i], sh.objo[i], sh.flags[i] = tile, objo, flags
            ms = list(m) + [0] * (4 - len(m))
            sh.m1[i], sh.m2[i] = ms[0] << 4 | ms[1], ms[2] << 4 | ms[3]
            if ink is not None:
                ov[0xB500 + i] = ink
            cells.append(i)
        put(0, 0, 0x23, 20, ink=0x42)                    # fruit alone (ink remembered)
        put(1, 31, 0x9C, 99, ink=0x05)                   # fruit on a mirrored tile, X edge
        put(2, 5, 0x40, 5)                               # rainbow piece drawn opaque
        put(3, 6, 0x41, 0, (3, 4))                       # two masked rainbow pieces on the base tile
        put(4, 7, 0x42, 22, (9,), flags=0x8B, ink=0x46)  # fruit + rainbow, remembered ink 11
        put(5, 8, 0x43, 22, (9,), flags=0x80, ink=0x46)  # fruit + rainbow, ink not remembered
        put(6, 9, 0x44, 0, (1, 2, 3, 4))                 # four masked
        put(7, 10, 0x45, 0xFF)                           # unsupported: left as drawn
        put(8, 11, 0x46, 30, flags=0)                    # background unknown: left as drawn
        put(9, 12, 0x47, 31)                             # class: left on the ULA (profile)
        put(10, 13, 0x48, 32)                            # class: fixed ink, no border
        put(19, 14, 0x49, 40)                            # bottom char row, partial (N = 155)
        put(20, 15, 0x4A, 41)                            # off screen
        sh.ctile[cells[-1]] = 7                          # with a tile left from an earlier render
        put(11, 4, 0x4B, 20, ink=0x42)                   # same key as the first: shared tile
        pg[OCLASS - 0x2000 + 31] = 2
        pg[OCLASS - 0x2000 + 32] = 4 | ink_index(0x45) << 4
        ov[0x5800 + 32 * 12 + 9] = 0x41                  # a star changed this attribute
        sh.fix_flags(pg)
        return Mod(bm, ov), sh

    def render_case(pt, bm, R, sh, pg, tm, shm, sc, line_t=None, nr7f=0):
        """render start -> every band -> render end. Returns (faults, ns after render start, model,
        ns after render end)."""
        fails = []
        peek = lambda a: bm[a]
        sh.load(pg)
        front_defs = {}
        if sc[V_MSD] != 0xFF:
            for kk in range(20):
                for col in range(32):
                    t = tm[map_pos(kk, col)]
                    if t:
                        front_defs[t] = bytes(tm[TDEF + 32 * t:TDEF + 32 * t + 32])
        exp = obj_build(peek, sh, pg, pt.fpage)
        r = list(R)
        r[24] = 58851
        ro, ov, rp, pv, ns, err = _pair(pt, bm, r, 0, scratch=sc, pages={PAGE_T: pg, PAGE_TM: tm, PAGE_SH: shm},
                                        stops=(58855,), nr={0x7F: nr7f})
        if err or any(ro[k] != rp[k] for k in CMP + [16, 17]) or ov.ov != pv.ov:
            fails.append('render start registers/memory')
        if ns.nr.get(0x51) != 0xFF or ns.nr.get(0x52) != 10 or ns.nr.get(0x53) != 11:
            fails.append('render start MMU')
        pg2, tm2, shm2 = ns.pages[PAGE_T], ns.pages[PAGE_TM], ns.pages[PAGE_SH]
        fails += tilemap_errors(pg2, tm2, shm2, exp, front_defs)
        assigned = {e[0] for e in exp.values()}
        if any(pg2[CTILE - 0x2000 + i] and i not in assigned for i in range(NCELLS)):
            fails.append('stale CTILE')
        sh.ctile[:] = pg2[CTILE - 0x2000:CTILE - 0x2000 + NCELLS]
        if not sh.same_as(pg2):
            fails.append('object map after render start')
        sc2, pages = bytes(ns.scratch), {k: bytes(v) for k, v in ns.pages.items()}
        for row in range(2, 24):
            ba = 0x4000 | (row & 0x18) << 8 | (row & 7) << 5
            m2 = Mod(bm, {59522: ba & 255, 59523: ba >> 8})
            want = {a: v for a, v in obj_fix(lambda a: m2[a], sh, pg2, row).items() if v != m2[a]}
            r = list(R)
            r[24] = 59547
            ro, ov, rp, pv, ns2, err = _pair(pt, m2, r, sc2[V_S], scratch=sc2, pages=pages, stops=(59550,))
            got = {a: v for a, v in pv.ov.items() if 0x4000 <= a < 0x5B00 and v != m2[a]}
            if err or any(ro[k] != rp[k] for k in CMP + [16, 17]) or got != want or \
                    ns2.nr.get(0x50) != 0xFF or ns2.nr.get(0x51) != 0xFF:
                fails.append('band %d' % row)
        sc3 = bytearray(sc2)
        sc3[V_NP] = 0
        r = list(R)
        r[24] = 59087
        r[25] = 0
        ro, ov, rp, pv, ns3, err = _pair(pt, bm, r, 0, scratch=sc3, pages=pages, stops=(59092,), line_t=line_t)
        render_case.ns3 = ns3
        got = {a: v for a, v in pv.ov.items() if 0x4000 <= a < 0x5B00 and v != bm[a]}
        if err or any(ro[k] != rp[k] for k in CMP) or got:
            fails.append('render end screen/registers')
        if exp is not None and not ns3.scratch[V_PEND]:     # (a deferred commit is checked by defer_case)
            e = commit_errors(ns3.pages[PAGE_TM], ns3.pages[PAGE_SH], ns3.nr, ns3.clip_tm, bm[58850])
            if e or ns3.scratch[V_MSD] != ns3.scratch[V_MSB] or ns3.nr.get(0x52) != 10 or ns3.nr.get(0x53) != 11:
                fails.append('tilemap commit %s' % e[:2])
        return fails, ns, exp, ns3

    banks, o7, R = rstates[0]
    bm0 = _BankMem(banks, o7, rom)

    def fresh(pt=patch):
        sc = bytearray(pt.scratch)
        sc[V_MSB] = sc[V_MSD] = 0xFF
        return sc, bytearray(8192), bytearray(rnd.randrange(256) for _ in range(8192))

    def again(ns3, garbage=None):
        """State for the next render after ns3 (render end): same pages, next frame, shadow map
        overwritten (rebuilt from scratch at render start)."""
        pg2, tm2, sc2 = bytearray(ns3.pages[PAGE_T]), bytearray(ns3.pages[PAGE_TM]), bytearray(ns3.scratch)
        shm2 = bytearray(ns3.pages[PAGE_SH])
        for o in range(20 * 64):
            shm2[o] = rnd.randrange(256) if garbage is None else garbage
        sc2[V_FRM] = (sc2[V_FRM] + 1) & 255
        return pg2, tm2, shm2, sc2

    nfail, ntiles = [], 0
    for banks, o7, R in rstates:
        bm = _BankMem(banks, o7, rom)
        pg = bytearray(patch.tpage)
        m, sh = scen(bm, pg)
        sc, tm, shm = fresh()
        f, ns, exp, ns3 = render_case(patch, m, R, sh, pg, tm, shm, sc)
        nfail += f
        ntiles += sum(1 for e in exp.values())
        pg2, tm2, shm2, sc2 = again(ns3)            # second render: same objects -> cache hits
        f, _, _, _ = render_case(patch, m, R, sh, pg2, tm2, shm2, sc2)
        nfail += f
    c['object render path (start, 22 bands, end; tiles, background, inks, classes) %s' % (
        'ok' if not nfail else '%s FAIL!' % nfail[:4])] += len(rstates)
    c['object render cases: tiles checked'] += ntiles

    def one(pt, second=False):
        pg = bytearray(pt.tpage)
        m, sh = scen(bm0, pg)
        sc, tm, shm = fresh(pt)
        f, ns, _, ns3 = render_case(pt, m, R0, sh, pg, tm, shm, sc)
        if not second:
            return f
        pg2, tm2, shm2, sc2 = again(ns3, 0x55)
        f2, _, _, _ = render_case(pt, m, R0, sh, pg2, tm2, shm2, sc2)
        return f + f2
    R0 = R
    # border control: the profile has no object with a border (Dean, 2026-10-19), so it runs on a
    # copy whose objects all keep theirs (the base copy must pass first, or the control proves nothing)
    import copy
    bprof = copy.deepcopy(patch.prof)
    for kind in ('opaque', 'masked'):
        for v in bprof.get('objects', {}).get(kind, {}).values():
            v['border'] = True
    bpatch = RainbowPatch(patch.cfg, bprof)
    f = one(bpatch)
    c['object render path with borders (control base) %s' % ('ok' if not f else '%s FAIL!' % f[:4])] += 1
    f = one(_with_bytes(bpatch, 'odraw.bk', None, b'\xE6\x00'))
    c['object render negative control (no black border) %s' % ('detected' if f else 'NOT DETECTED!')] += 1
    for sym, new, what, second in (
                                   ('s_bend.wt', b'\x00', 'background tile not drawn', False),
                                   ('obuild.cb', b'\x00\x00\x00\x00', 'map not cleared', True),
                                   ('ocomp.selx', b'\xEE\x00', 'fruit behind rainbows', False),
                                   ('obuild.tj', b'\x18', 'off-screen tile left assigned', False),
                                   ('obuild.vi', b'\x00\x00', 'one-ink tile with the ink in its pixels', False),
                                   ('odraw.fc', b'\xAF', "collectables' inside pixels not drawn", False)):
        f = one(_with_bytes(patch, sym, None, new), second)
        c['object render negative control (%s) %s' % (what, 'detected' if f else 'NOT DETECTED!')] += 1

    # tile cache: every entry on screen (used last render), one new key -> no tile, nothing overwritten
    def cache_case(pt):
        pg = bytearray(patch.tpage)
        m, sh = scen(bm0, pg)
        sc, tm, shm = fresh(pt)
        prv = sc[V_FRM] | 0x80                    # s_rs counts this render before obuild: the
        for t in range(1, NTILE):                 # counter's present value = the previous render
            pg[STAMP - 0x2000 + t] = prv
            pg[KEYS - 0x2000 + 4 * t:KEYS - 0x2000 + 4 * t + 4] = bytes([200, 0, 0, t])
            tm[TDEF + 32 * t:TDEF + 32 * t + 32] = bytes([t]) * 32
            tm[map_pos((t - 1) // 32, (t - 1) % 32)] = t
        sc[V_MSD] = 16
        sh2 = ObjShadow()
        i = 32 * ((16 // 8 + 3) % 22) + 3
        sh2.tiles[i], sh2.objo[i], sh2.flags[i] = 0x20, 20, 0x80
        sh2.fix_flags(pg)
        sh2.load(pg)
        r = list(R0)
        r[24] = 58851
        ro, ov, rp, pv, ns, err = _pair(pt, m, r, 0, scratch=sc, pages={PAGE_T: pg, PAGE_TM: tm, PAGE_SH: shm},
                                        stops=(58855,))
        tm2, shm2 = ns.pages[PAGE_TM], ns.pages[PAGE_SH]
        kept = all(tm2[TDEF + 32 * t:TDEF + 32 * t + 32] == bytes([t]) * 32 for t in range(1, NTILE))
        return not err and kept and shm2[sh_pos(3, 3)] == 0 and ns.pages[PAGE_T][CTILE - 0x2000 + i] == 0
    ok = cache_case(patch)
    c['tile cache full: on-screen tiles kept, cell left as drawn %s' % ('ok' if ok else 'FAIL!')] += 1
    ok = cache_case(_with_bytes(patch, 'olook.np', None, b'\x00\x00'))
    c['tile cache negative control (on-screen tile reused) %s' % ('detected' if not ok else 'NOT DETECTED!')] += 1

    # flush (NextReg $7F set by the sprites-off hooks): a stale entry (graphics changed) is rebuilt
    def flush_case(pt):
        pg = bytearray(patch.tpage)
        m, sh = scen(bm0, pg)
        sc, tm, shm = fresh(pt)
        f, ns, exp, ns3 = render_case(pt, m, R0, sh, pg, tm, shm, sc)
        pg2, tm2, shm2, sc2 = again(ns3)
        for t in range(1, NTILE):                           # every cached tile now stale
            if pg2[STAMP - 0x2000 + t]:
                tm2[TDEF + 32 * t:TDEF + 32 * t + 32] = bytes(32)
        sc2[V_MSD] = 0xFF                                   # nothing on screen to protect
        sc2[V_FRM] = (sc2[V_FRM] + 1) & 255
        f2, _, _, _ = render_case(pt, m, R0, sh, pg2, tm2, shm2, sc2, nr7f=1)
        return f + f2
    f = flush_case(patch)
    c['tile cache flush (stale tiles rebuilt) %s' % ('ok' if not f else '%s FAIL!' % f[:3])] += 1
    f = flush_case(_with_bytes(patch, 'obuild.fj', b'\x28', b'\x18'))
    c['tile cache negative control (flush ignored) %s' % ('detected' if f else 'NOT DETECTED!')] += 1

    # render-end commit (2026-10-19): at once only when the frame will miss the interrupt (L >= 240)
    # and the commit fits before line 16 (L + sprites <= 308), else at the next interrupt (s_int, line
    # 248) - never a wait. The deferred commit is dropped after a non-play screen ($7F set).
    def defer_case(pt, ns3, nr7f=0):
        """s_lim at the interrupt (line INT_LINE) with ns3's state (a commit pending): original =
        patched at 65175 (F dead: CP 3 next), BC DE HL SP kept. Returns (ok, ns)."""
        r = list(R0)
        r[24], r[25] = 65172, 0
        sc = bytearray(ns3.scratch)
        sc[V_TICK] = LIMIT - 1
        ro, ov, rp, pv, ns, err = _pair(pt, bm0, r, ns3.scratch[V_S], scratch=sc,
                                        pages={k: bytes(v) for k, v in ns3.pages.items()},
                                        stops=(65175,), line_t=INT_LINE, nr={0x7F: nr7f})
        ok = not err and all(ro[k] == rp[k] for k in CMP if k != 1) and ov.ov == pv.ov and \
            rp[24] == 65175 and ns.scratch[V_PEND] == 0 and ns.nr.get(0x07) == 3 and ns.nr.get(0x50) == 0xFF
        return ok, ns

    def raster(pt):
        res = {}
        pg = bytearray(patch.tpage)
        m, sh = scen(bm0, pg)
        ok = True
        for l0 in (100, 175, 15, 176, 200, 239, 240, 300, 307, 308):
            sc, tm, shm = fresh(pt)
            f, _, exp, ns = render_case(pt, m, R0, sh, bytearray(pg), tm, shm, sc, line_t=l0)
            now = l0 >= RS_LINE and l0 + ns.scratch[V_S] <= 307
            if now:
                l6e = None if ns.t6e is None else (l0 + ns.t6e // LINE_T) % 312
                ok &= not f and ns.scratch[V_PEND] == 0 and l6e is not None and l6e - l0 < 30
            else:
                ok &= ns.t6e is None and ns.scratch[V_PEND] == 1 and not any(
                    e[1] in (0x6B, 0x6E, 0x15) or 0x34 <= e[1] <= 0x39 for e in ns.events if e[0] == 'nr')
                okd, nsd = defer_case(pt, ns)
                l6e = None if nsd.t6e is None else (INT_LINE + nsd.t6e // LINE_T) % 312
                e = commit_errors(nsd.pages[PAGE_TM], nsd.pages[PAGE_SH], nsd.nr, nsd.clip_tm, m[58850])
                ok &= okd and not e and l6e is not None and INT_LINE <= l6e < INT_LINE + 30
                okx, nsx = defer_case(pt, ns, nr7f=1)            # a non-play screen came: dropped
                ok &= okx and nsx.t6e is None and not nsx.nr.get(0x6B)
            res[l0] = ('now' if now else 'deferred', l6e)
        return ok, res
    ok, res = raster(patch)
    c['commit at once / deferred to the interrupt (line at the tilemap switch %s) %s' % (
        res, 'ok' if ok else 'FAIL!')] += 1
    ok, _ = raster(_with_rom_bytes(patch, 's_re.rs', b'\xDC', b'\xCD'))
    c['commit negative control (committed in the play area) %s' % ('detected' if not ok else 'NOT DETECTED!')] += 1

    # diagnostic build: border colours (blue while the commit waits, red while a tile is composed,
    # yellow after a frame with an interrupt in it); the normal build writes no border at all
    import copy as _copy
    dpt = _copy.deepcopy(patch)
    dsc = bytearray(dpt.scratch)
    dsc[V_DIAG] = 1
    dpt.scratch = bytes(dsc)

    def border(ns_):
        return [e[2] for e in ns_.events if e[0] == 'port' and e[1] & 0xFF == 0xFE]

    def diag_case(pt):
        pg = bytearray(patch.tpage)
        m, sh = scen(bm0, pg)
        sc, tm, shm = fresh(pt)
        f, ns, exp, ns3 = render_case(pt, m, R0, sh, pg, tm, shm, sc, line_t=100)
        okd, nsd = defer_case(pt, ns3)                  # (border: blue, black; then the frame start's black)
        f2, _, _, ns4 = render_case(pt, m, R0, sh, bytearray(patch.tpage), bytearray(8192),
                                    bytearray(8192), fresh(pt)[0], line_t=200)
        return f + f2 + ([] if okd else ['deferred commit']), border(ns), border(ns3) + border(nsd), border(ns4)

    def frame_case(pt):
        """dfst at a frame start, then dfend: (interrupt during the frame, T the INT signal is held
        after the frame's own interrupt): an overrun -> yellow; none -> no colour; INT never drops
        (the frame-start clear cannot take) -> magenta when the flag is set at the end."""
        from .dizzy6 import _rw_simulator
        Sim = _rw_simulator()
        out = []
        for irq, hold in ((1, 300), (0, 300), (0, 10 ** 9)):
            ns = NextState(pt)
            ns.nr[0xC8] = 1                         # the interrupt that started this frame
            ns.int_until = hold
            mem = bytearray(65536)

            class M:
                def __getitem__(s, a):
                    if a < 0x2000:
                        return ns.scratch[a]
                    return pt.page[a - 0x2000] if a < 0x4000 else mem[a]

                def __setitem__(s, a, v):
                    if a < 0x2000:
                        ns.scratch[a] = v
                    elif a >= 0x4000:
                        mem[a] = v

                def __len__(s):
                    return 65536
            res = []
            t = 0
            for sym in ('dfst', 'dfend'):
                if sym == 'dfend' and irq:
                    ns.nr[0xC8] |= 1                # another interrupt came during the frame
                mem[0xFEFE], mem[0xFEFF] = 0xF0, 0xFF  # return address 0xFFF0
                regs = list(R0)
                regs[12], regs[24], regs[25] = 0xFEFE, pt.syms[sym], t
                sim = _machine(Sim, M(), regs, ns)
                ns.events = []
                okr = _run(sim, (pt.syms['x_lrun' if sym == 'dfst' else 'x_hx'],), 20000) and \
                    sim.registers[12] == 0xFEFE and sim.registers[2:4] == list(R0[2:4])   # no stack, BC kept
                t = sim.registers[25] + 100000
                res.append((okr, border(ns), ns.scratch[V_FRUN]))
            out.append(res)
        return out
    W = [[(True, [0], 1), (True, [6], 0)], [(True, [0], 1), (True, [], 0)], [(True, [0], 1), (True, [3], 0)]]
    f, rs, re_, re2 = diag_case(dpt)
    fr = frame_case(dpt)
    ok = not f and rs and rs[-1] == 0 and set(rs) == {0, 2} and re_ == [1, 0, 0] and re2 == [] and fr == W
    c['diagnostic border (deferred commit blue, tile red, overrun yellow / magenta; %d / %d / %d writes) %s' % (
        len(rs), len(re_), len(re2), 'ok' if ok else '%s FAIL!' % ((f[:2], rs[:4], re_[:4], re2, fr),))] += 1
    f, rs, re_, re2 = diag_case(patch)
    fr = frame_case(patch)
    ok = not f and not rs and not re_ and not re2 and all(r == [(True, [], 0), (True, [], 0)] for r in fr)
    c['diagnostic border off in the normal build %s' % ('ok' if ok else '%s FAIL!' % ((f[:2], rs[:4], re_[:4], re2, fr),))] += 1
    k = bytes(dpt.page).find(b'\x3E\xFF\x32', patch.syms['dfst'] - 0x2000)  # dfst poll limit 255 -> 1
    nw = _with_rom_bytes(dpt, 'dfst', None, b'')                           # (a copy)
    pgw = bytearray(nw.page)
    pgw[k + 1] = 1                                                          # no wait for the INT
    nw.page = bytes(pgw)
    nw.extra_banks = {12: nw.page + nw.fpage, 13: nw.scratch + nw.tpage}
    c['diagnostic negative control (no wait for the INT to drop) %s' % (
        'detected' if frame_case(nw) != W else 'NOT DETECTED!')] += 1
    f, rs, re_, re2 = diag_case(_with_bytes(dpt, 'dcol.o', b'\xD3\xFE', b'\x00\x00'))
    c['diagnostic negative control (no colour shown) %s' % ('detected' if not rs or set(rs) != {0, 2} or re_ != [1, 0, 0]
                                                           else 'NOT DETECTED!')] += 1

    # profile tables
    o, mm, bg = object_tables({'opaque': {'1-3': {'group': 'rainbow'}, '20': {'ula': True},
                                          '21': {'border': False, 'ink': 2, 'bright': True}},
                               'masked': {'5': {'group': 'rainbow'}}, 'background': {'7': 9}})
    ok = o[1:4] == b'\x01\x01\x01' and o[0] == 0 and o[4] == 0 and o[20] == 2 and o[21] == 4 | 10 << 4 and \
        mm[5] == 1 and mm[6] == 0 and bg[7] == 9 and bg[8] == 8
    c['profile object tables %s' % ('ok' if ok else 'FAIL!')] += 1


# ---------------------------------------------------------------------------------------------
# nexclash auto entry point for this engine
# ---------------------------------------------------------------------------------------------

def mem64(snap):
    """64K view of a SkoolKit 128K snapshot with bank 0 at C000 (where the engine code lives)."""
    b = snap.memory.banks
    return bytes(16384) + bytes(b[5]) + bytes(b[2]) + bytes(b[0])


def is_rainbow(snap):
    return snap.machine != '48K' and identify_rb(mem64(snap))


def auto(a, z80, name, out, say):
    """Plain + sprite .nex, boot checks, differential verification per RZX, unit tests."""
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    cls = json.load(open(a.class_colours)) if getattr(a, 'class_colours', None) else \
        load_profile().get('colours', {}).get('class_colours')       # default: the profile's
    cfg = Config(getattr(a, 'ink', None) or 'white', getattr(a, 'outline', None) or 'black', cls)
    say('Game      : %s' % name)
    say('Engine    : rainbow (Rainbow Islands 128K: sprite-list walker, full-redraw renderer)')
    say('Colours   : ink %s, outline %s%s' % (getattr(a, 'ink', None) or 'white',
                                              getattr(a, 'outline', None) or 'black',
                                              ', class colours from %s' % (getattr(a, 'class_colours', None) or
                                                                             'the profile') if cls else ''))
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, TAIL_ADDR, quiet=True)
    bad = boot_check(plain, z80, tail=(TAIL_ADDR, TAIL_ADDR + 80))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = back buffer, write-first in both reference RZX)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = RainbowPatch(cfg)
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    dpatch = RainbowPatch(Config(getattr(a, 'ink', None) or 'white', getattr(a, 'outline', None) or 'black',
                                 cls, diag=True))
    dspr = os.path.join(out, name + '_sprites_diag.nex')
    zt.convert(z80, dspr, quiet=True, patch=dpatch)
    bad3 = boot_check(dspr, z80, dpatch)
    say('Diagnostic: %s  %s  boot %s  (border: blue = commit deferred to the interrupt, red = tile built, '
        'yellow = frame overran)' % (os.path.basename(dspr), md5(dspr),
                                     'OK' if not bad3 else 'MISMATCH %s' % str(bad3[:3])[:200]))
    ok = ok and not bad3
    rzxs = list(a.rzx or [])
    for r in rzxs:
        segs = RZ.read_segments(r)
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1,
                                                                   os.path.basename(s2)))
            r = s2
        c, ex = verify(patch, r, stop=getattr(a, 'quick', None))
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        hm = c['pattern cache hits'] + c['pattern cache misses']
        say('Verify    : %s  %d frames, %d renders, %d pieces (max %d sprites/render, store hits %d%%), %d stars '
            "kept on ULA, AF' converged %d -> %s" % (os.path.basename(r), c['frames'], c['render start'],
                                         c['pieces'], c['max sprites in a render'],
                                         100 * c['pattern cache hits'] // max(hm, 1),
                                         c['star pieces left on the ULA (60176/60180)'],
                                         c["AF' difference overwritten (converged)"],
                                         'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            limiter: %d game frames checked (entry + exit), 28 MHz inside, 3.5 MHz outside' %
            c['limiter: frame runs'])
        say('            commits checked %d (patterns + attributes = staged): at once %d, deferred to the next '
            'interrupt %d (dropped on a non-play screen %d); non-play sprites-off %d, overflow entries %d' % (
                c['commits checked'], c['render end: commit at once'],
                c['render end: commit deferred to the next interrupt'],
                c['deferred commits dropped (non-play screen)'], c['sprites off (non-play)'],
                c['overflow entries (4 ways in use)']))
        say('            music: %d AY writes, %d player ticks queued, %d sent at interrupts (%d sent early: queue '
            'full - the replay sees one interrupt per game frame), chip = original after each tick sent' % (
                c['AY writes (music)'], c['AY ticks queued'], c['AY ticks sent at interrupts'],
                c['AY queue full: oldest tick sent early']))
        say('            objects: %d cell hooks (60853 %d / 60839 %d / 60965 %d), %d tiles dropped by a cell change; '
            '%d object tiles shown (max %d per render), %d bands checked, %d screen bytes set to the map tile at '
            'band ends; object cells = the game\'s back buffer %d; max %d figure sprites' % (
                c['cell hook 60853'] + c['cell hook 60839'] + c['cell hook 60965'], c['cell hook 60853'],
                c['cell hook 60839'], c['cell hook 60965'], c['cell hook: tile dropped'], c['object tiles shown'],
                c['max object tiles in a render'], c['bands checked'], c['object screen bytes changed at band ends'],
                c["object cells = the game's back buffer"], c['max sprites in a render']))
        say('            opaque objects: %d drawn (map tile stored); cell redrawn by the game from the same map '
            'cell: %d with the stored tile, %d different; cell reused for another map cell: %d / %d' % (
                c['opaque object draws'], c['opaque object cell redrawn: same scroll, tile as stored'],
                c['opaque object cell redrawn: same scroll, tile different'],
                c['opaque object cell redrawn: other scroll, tile as stored'],
                c['opaque object cell redrawn: other scroll, tile different']))
        say('            timing (simulated T at 28 MHz, no wait states): render-end commit max %d us / avg %d us, '
            'render-start tilemap build max %d us; object hooks per game frame avg %d / max %d us; whole game '
            'frame (original + hooks) max %d us, frames over 20 ms: %d (%d without the object hooks)'
            % (c['render end T max (28 MHz us)'], c['render end T avg (28 MHz us)'],
               c['render start T max (28 MHz us)'], c['item hooks per game frame avg (28 MHz us)'],
               c['item hooks per game frame max (28 MHz us)'], c['patched game frame max (28 MHz us)'],
               c['game frames over 20 ms at 28 MHz'], c['game frames over 20 ms at 28 MHz without the item hooks']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if rzxs:                                    # the diagnostic build changes nothing but the border
        cd, _ = verify(dpatch, r, stop=min(getattr(a, 'quick', None) or 1500, 1500))
        fd = {k: v for k, v in cd.items() if k.endswith('!')}
        ok = ok and not fd
        say('            diagnostic build: %s first %d frames, %d renders -> %s' % (
            os.path.basename(r), cd['frames'], cd['render start'], 'IDENTICAL' if not fd else 'FAILED %s' % fd))
        u = unit_tests(patch, r)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d states x (edge columns, last sprites, passthrough, negative control) + '
            'direct conversion vs %d plotter/carry cases (+ control) + %d left-entry 4-wide pieces + store '
            'hit/miss/garbage (+ 2 controls) + SWAPNIB + setup + class colour -> %s' % (
                u['states'], u['direct conversion = plotter (random streams) ok'],
                u['left-entry 4-wide plotter ok'], 'PASS' if not uf else 'FAIL %s' % uf))
        oc = [k for k in u if 'negative control' in k and not k.startswith(('negative control', 'store '))]
        say('            objects: %d cell-hook cases + %d render paths (start, 22 bands, end) + cache full / flush '
            '+ raster wait + profile tables; %d negative controls (%d detected); figure controls detected: '
            'ink/outline %d, stale pattern %d' % (
                u['object cell hooks (registers incl. F, object map = model, dropped tiles) ok'],
                u['object render path (start, 22 bands, end; tiles, background, inks, classes) ok'],
                len(oc), sum(1 for k in oc if k.endswith('detected')),
                u['negative control detected'], u['store stale-pattern negative control detected']))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Colour sheet (PLAYBOOK 3b, Dean 2026-10-19): every figure the sprite hooks draw, on a PNG to paint
# ---------------------------------------------------------------------------------------------
# Paint palette = the 15 Spectrum inks (sprite palette offset ITEM_PAL): 1 black, 2-8 inks 1-7,
# 9-15 bright inks 1-7. Today's colours: ink = bright white (15), outline = black (1).
SHEET_PAL = (0x00, 0x00) + SPECTRUM_INK + SPECTRUM_INK_BRIGHT
SHEET_INK, SHEET_OUTLINE = 15, 1       # bright white (Config ink 'white' = 0xFF), black
COLOURS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'profiles',
                            'rainbow_colours.json')


LEVEL_PAGES = (0x94, 0x9E)         # the island's figure graphics: buffer 0x9400-0x9EFF, loaded per island
BOSS_PAGES = (0x78, 0x7E)          # the island's boss graphics: 0x7800-0x7EFF, loaded per island
ISLAND_VAR = 0x636E                # island 0-6 (round var 0x636F = 4 * island + round in island)


def gfx_key(a, island):
    """Colour-map key of a graphics byte: the island buffer's bytes per island ('I3:9A12'; the same
    address holds another island's creature there), every other byte by address ('D612')."""
    return 'I%d:%04X' % (island + 1, a) if island_page(a >> 8) else '%04X' % a


def island_page(h):
    return LEVEL_PAGES[0] <= h <= LEVEL_PAGES[1] or BOSS_PAGES[0] <= h <= BOSS_PAGES[1]


def figure_family(gfx, island=0):
    """Graphics address -> sheet group: the player (0xD6-0xDA), the thrown rainbow (0xC3), 'Island n'
    (the island's creature and boss buffers), other fixed graphics ('Items': power-ups and bonus
    items drawn as figures, shown with the collectables)."""
    h = gfx >> 8
    if island_page(h):
        return 'Island %d' % (island + 1)
    if 0xD6 <= h <= 0xDA:
        return 'Player'
    if h == 0xC3:
        return 'Rainbow'
    return 'Items'


SHIFT_SET, SHIFT_GFX = 60332, 60342   # shifter (60300): LD (HL),D = new shift / LD SP,HL = graphic start
SHIFT_ROWS, SHIFT_ROW = 24, 6        # a shifted graphic: 24 rows x (mask, gfx) x 3 bytes
SHIFT_AREA = (0xD662, 0xD662 + 8 * 144)   # the 8 shifted graphics seen (whole playthrough, 2026-10-19)


def shifted_key(a, sb, shifts):
    """A byte of a graphic the game shifts IN PLACE (the player's 8 frames 0xD662 + 144 k: 60300
    rotates mask and gfx right / left to the figure's x & 6, so the same address holds other pixels
    after a move) -> (key, bit) of the UNSHIFTED pixel ('G<start>.<row>.<byte>'), None outside such a
    graphic (False: a pixel the shift moved in from outside the picture)."""
    for st, sh in shifts.items():
        if st <= a < st + SHIFT_ROWS * SHIFT_ROW:
            off = a - st
            ux = 8 * ((off % SHIFT_ROW) // 2) + sb - sh
            if ux < 0:                  # moved in from the left: never ink, shown clear
                return 'G%04X.%d.L' % (st, off // SHIFT_ROW), ux & 7
            return 'G%04X.%d.%d' % (st, off // SHIFT_ROW, ux >> 3), ux & 7
    return None


def sheet_piece(prof, ix, carry, gfx, de, peek, no_outline=False, island=0, shifts=None):
    """One walker piece (59539 state) -> a coloursheet part in SCREEN orientation: per window pixel
    the colour-map key (gfx_key of the graphics byte it comes from: the ink byte for ink and clear
    pixels, the mask byte for outline pixels), its bit as stored, code 1 ink / 2 outline / 0 clear.
    None for pieces the hooks leave on the ULA (stars, unknown plotters)."""
    pi = prof['plotters'].get(str(ix))
    if pi is None or ix in (60176, 60180):
        return None
    lay = bytes.fromhex(pi['layout'][carry])
    ink, mask = {}, {}
    for i, t in enumerate(lay):
        a = (gfx + i) & 0xFFFF
        (mask if t & 0x80 else ink)[t & 0x3F] = (peek(a), a, bool(t & 0x40))
    rows = max(p // 6 for p in set(ink) | set(mask)) + 1
    pixels, entries = [], {}
    for pos in range(6 * rows):
        r, col = divmod(pos, 6)
        g, m = ink.get(pos), mask.get(pos)
        if g is None and m is None:
            continue
        for b in range(8):
            def src(e):
                v, a, mir = e
                sb = 7 - b if mir else b
                return a, sb, v >> (7 - sb) & 1
            gi = src(g) if g else None
            mi = src(m) if m else None
            if gi and gi[2]:
                key, bit, code, d = gi[0], gi[1], 1, SHEET_INK
            elif mi and not mi[2] and not no_outline:
                key, bit, code, d = mi[0], mi[1], 2, SHEET_OUTLINE
            else:
                key, bit, code, d = (gi or mi)[0], (gi or mi)[1], 0, 0
            sk = shifted_key(key, bit, shifts) if shifts else None
            if sk is False:
                continue
            if sk:
                k, bit = sk
                entries.setdefault(k, [0, 3])
            else:
                k = gfx_key(key, island)
                entries.setdefault(k, [peek(key), 1])
            pixels.append((col * 8 + b, r, k, bit, code, d))
    e, d = de & 255, de >> 8
    x = ((e & 31) - pi['off']) * 8
    y = ((e & 0xE0) >> 2 | (d & 0x18) << 3) + (d & 7)
    sk = shifted_key(gfx, 0, shifts) if shifts else None
    gid = gfx_key(gfx, island)
    if sk:                                  # the graphic's row, at its shift now
        st = next(a for a in shifts if a <= gfx < a + SHIFT_ROWS * SHIFT_ROW)
        gid = '%s>%d' % (sk[0].rsplit('.', 1)[0], shifts[st])
    return dict(id=(ix, carry, gid), size=rows, w=48, h=rows, x=x, y=y, mir=0,
                group=figure_family(gfx, island), pixels=pixels, entries=entries, gfx=gfx, len=len(lay))


def fill_mask(rows, w):
    """Enclosed paper of a picture (rows: ints, w bits wide, bit w-1 = leftmost): the paper pixels a
    4-connected flood through paper from outside the picture does not reach."""
    h = len(rows)
    ink = lambda x, y: rows[y] >> (w - 1 - x) & 1
    seen = set()
    todo = [(x, y) for x in range(-1, w + 1) for y in (-1, h)] + [(x, y) for y in range(h) for x in (-1, w)]
    while todo:
        x, y = todo.pop()
        if (x, y) in seen:
            continue
        seen.add((x, y))
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if -1 <= nx <= w and -1 <= ny <= h and (nx, ny) not in seen and \
                    (not (0 <= nx < w and 0 <= ny < h) or not ink(nx, ny)):
                todo.append((nx, ny))
    return [sum(1 << (w - 1 - x) for x in range(w) if not ink(x, y) and (x, y) not in seen) for y in range(h)]


class ObjectFills:
    """Collectables (opaque codes >= 15) as the game draws them into back-buffer cells: at each render
    start the cells holding a 2x2 group (codes c, c+1 / c+2, c+3 on the four cells) are joined into
    one 16x16 picture, the others are single 8x8 pictures; fill_mask of each picture -> per cell
    graphic (its 8 rows) the inside pixels. inks: per code, the cell inks seen. pictures: every
    (codes, cell attributes) drawn -> [rows per cell, times seen] (the collectables sheet)."""

    def __init__(self):
        self.cells, self.fills, self.inks, self.codes = {}, {}, collections.defaultdict(collections.Counter), {}
        self.pictures = {}

    def on_pc(self, pc, mem, R):
        if (mem.o7ffd & 7) != 0:
            return
        if pc in (60839, 60853):
            i = cell_index(R[4], R[5])
            if i is None:
                return
            if pc == 60853 or R[0] < 15:
                self.cells.pop(i, None)
            else:
                from skoolkit.pagingtracer import Memory
                peek = lambda a: Memory.__getitem__(mem, a)
                self.cells[i] = (R[0], bytes(obj_rows(peek, 'O', R[0])))
        elif pc == 58851:
            from skoolkit.pagingtracer import Memory
            att = {i: Memory.__getitem__(mem, 0xB500 + i) for i in self.cells}
            for i, (c, g) in list(self.cells.items()):
                self.inks[c][att[i] & 0x47] += 1
            self.render(att)

    def render(self, att=None):
        cells, done = self.cells, set()
        for i, (c, g) in cells.items():
            k, col = i >> 5, i & 31
            q = [i, 32 * k + (col + 1) % 32, 32 * ((k + 1) % 22) + col, 32 * ((k + 1) % 22) + (col + 1) % 32]
            if all(cells.get(q[n], (None,))[0] == c + n for n in range(4)):
                rows = [cells[q[0 if y < 8 else 2]][1][y % 8] << 8 | cells[q[1 if y < 8 else 3]][1][y % 8]
                        for y in range(16)]
                m = fill_mask(rows, 16)
                for n in range(4):
                    part = [(m[y + 8 * (n >> 1)] >> (8 * (1 - (n & 1)))) & 255 for y in range(8)]
                    self._add(cells[q[n]], part, True)
                    done.add(q[n])
                if att is not None:
                    self._pic(tuple(c + n for n in range(4)), tuple(att[q[n]] & 0x47 for n in range(4)),
                              tuple(cells[q[n]][1] for n in range(4)))
        for i, cg in cells.items():
            if i not in done:
                self._add(cg, fill_mask(list(cg[1]), 8), False)
                if att is not None:
                    self._pic((cg[0],), (att[i] & 0x47,), (cg[1],))

    def _pic(self, codes, attrs, rows):
        e = self.pictures.setdefault((codes, attrs), [rows, 0])
        e[1] += 1

    def _add(self, cg, mask, grouped):
        c, g = cg
        self.codes.setdefault(g, set()).add(c)
        old = self.fills.get(g)
        if old is None or (grouped and not old[1]):
            self.fills[g] = (bytes(mask), grouped)


def ink_index(attr):
    """Cell attribute -> sheet / tile palette index as the build draws a collectable's ink
    (oinkx: 1 black, 2-8 inks 1-7, 9-15 bright inks 1-7)."""
    ink = attr & 7
    return 1 if not ink else ink + 1 + (7 if attr & 0x40 else 0)


def collectable_comps(pictures, prof):
    """ObjectFills.pictures -> coloursheet composites, one per (collectable, colour) the game drew, in
    the build's colours: ink in the cell's ink, the inside (profile `fills`) black or white, paper clear
    (paintable). Key per cell row and colour: 'C<code>.<attr>:<row>' (each colour paints apart)."""
    fpage = fill_page(prof)
    comps = []
    whole = {(c, a) for (codes, attrs) in pictures if len(codes) == 4 for c, a in zip(codes, attrs)}
    for (codes, attrs), (rows, n) in sorted(pictures.items()):
        if len(codes) == 1 and (codes[0], attrs[0]) in whole:
            continue                    # one cell of a 2x2 collectable (the rest off screen): shown whole
        w = 16 if len(codes) == 4 else 8
        pixels, entries = [], {}
        for ci, (c, a) in enumerate(zip(codes, attrs)):
            ox, oy = 8 * (ci & 1), 8 * (ci >> 1)
            idx = ink_index(a)
            f = obj_fill(fpage, c)
            fm, fc = (f[0], f[1]) if f else ([0] * 8, 0)
            fidx = {0xFF: 15, 0x11: 1}.get(fc) or (15 if fill_white(idx) else 1)
            for y in range(8):
                k = 'C%d.%02X:%d' % (c, a, y)
                entries[k] = [rows[ci][y], 2]
                for b in range(8):
                    if rows[ci][y] >> (7 - b) & 1:
                        pixels.append((ox + b, oy + y, k, b, 1, idx))
                    elif fm[y] >> (7 - b) & 1:
                        pixels.append((ox + b, oy + y, k, b, 2, fidx))
                    else:
                        pixels.append((ox + b, oy + y, k, b, 0, 0))
        part = dict(id=('C', codes, attrs), size=w, w=w, h=w, x=0, y=0, mir=0, group='Collectables',
                    pixels=pixels, entries=entries, dx=0, dy=0, dmir=0, vmir=0)
        comps.append(dict(count=n, group='Collectables', parts=[part]))
    return comps


class SheetCapture:
    """Hooks for rzx.trace (C simulator): every figure piece -> a coloursheet part, the pieces of one
    game object joined (a boss's objects - its graphics in BOSS_PAGES - are one figure; the object's builder call: 54533 per creature / player record IX, 50614 the
    thrown rainbow, 53318 single pieces; the descriptor code each allocates (54574 / 50635 / 53318) ->
    that object; the walker reads the code at 59513 and dispatches at 59539), flushed per render
    (59087); collectables per render start (ObjectFills)."""
    PCS = (54533, 54574, 50614, 50635, 53318, 59513, 59539, 59087, 60839, 60853, 58851, SHIFT_SET, SHIFT_GFX)

    def __init__(self, prof):
        from . import coloursheet as cs
        self.prof = prof
        self.cfg = Config(class_colours=prof.get('colours', {}).get('class_colours'))
        self.col = cs.Collector(family=lambda p: p['group'])
        self.fills = ObjectFills()
        self.obj, self.objs, self.code, self.n, self.frame = None, {}, 0, 0, []
        self.shifts, self.newshift = {}, 0               # shifted graphic start -> its shift now
        self.drawn = collections.defaultdict(set)       # island -> island-buffer addresses drawn
        self.buffers = {}                               # island -> its buffer 0x9400-0x9EFF (first seen)

    def on_pc(self, pc, sim):
        from skoolkit.pagingtracer import Memory
        mem, R = sim.memory, sim.registers
        if (mem.o7ffd & 7) != 0:
            return
        if pc in (60839, 60853, 58851):
            self.fills.on_pc(pc, mem, R)
        elif pc == 59513:
            self.code = R[0]
        elif pc == SHIFT_SET:
            self.newshift = R[4]
        elif pc == SHIFT_GFX:
            self.shifts[R[6] * 256 + R[7]] = self.newshift
        elif pc == 59539:
            peek = lambda a: Memory.__getitem__(mem, a)
            isl = peek(ISLAND_VAR) % 7
            gfx = R[12]
            if SHIFT_AREA[0] <= gfx < SHIFT_AREA[1] and shifted_key(gfx, 0, self.shifts) is None:
                return                          # shifted graphic whose shift is not known yet
            p = sheet_piece(self.prof, R[8] * 256 + R[9], R[17] & 1, gfx, R[4] * 256 + R[5], peek,
                            self.cfg.no_outline(gfx >> 8), isl, self.shifts)
            if p and p['pixels']:
                o = self.objs.get(self.code)
                if o is None:
                    self.n += 1
                    o = ('?', self.n)
                self.frame.append((o, p))
                if island_page(gfx >> 8):
                    reg = LEVEL_PAGES if LEVEL_PAGES[0] <= gfx >> 8 <= LEVEL_PAGES[1] else BOSS_PAGES
                    self.drawn[isl].update(range(gfx, gfx + p['len']))
                    if (isl, reg) not in self.buffers:
                        self.buffers[(isl, reg)] = (reg[0] << 8, bytes(peek(a) for a in range(reg[0] << 8,
                                                                                          reg[1] + 1 << 8)))
        elif pc == 54533:
            self.obj = ('M', R[8] * 256 + R[9])
        elif pc == 50614:
            self.n += 1
            self.obj = ('R', self.n)
        elif pc in (54574, 50635):
            self.objs[R[0]] = self.obj
        elif pc == 53318:
            self.n += 1
            self.objs[R[0]] = ('S', self.n)
        elif pc == 59087:
            groups = collections.OrderedDict()
            for o, p in self.frame:                     # a boss is several objects (one per part)
                if BOSS_PAGES[0] <= p['gfx'] >> 8 <= BOSS_PAGES[1]:
                    o = ('boss',)
                groups.setdefault(o, []).append(p)
            for g in groups.values():
                self.col.add_frame(sorted(g, key=lambda p: (p['y'], p['x'])))
            self.frame.clear()
            self.objs.clear()

    def coverage(self):
        """Per (island, 'creatures' / 'boss'): graphics bytes of its buffer drawn / non-zero bytes in it,
        the buffer read when its first figure was drawn (a gap = figures the recordings never showed,
        or data in the buffer that is not figure graphics)."""
        out = {}
        for (isl, reg), (base, buf) in sorted(self.buffers.items()):
            nz = {base + i for i, v in enumerate(buf) if v}
            out[(isl + 1, 'boss' if reg == BOSS_PAGES else 'creatures')] = (len(self.drawn[isl] & nz), len(nz))
        return out


SHEET_SPLIT = (('PLAYER', ('Player', 'Rainbow')),) + tuple(
    ('ISLAND%d' % i, ('Island %d' % i,)) for i in range(1, 8)) + (('COLLECTABLES', ('Items', 'Collectables')),)


def sheet_capture(rzx_paths, prof=None, progress=None):
    """Replay the RZX(s) (original game, C simulator) with SheetCapture's hooks. Fuse autosave
    snapshots are stripped first. -> the SheetCapture (desyncs are reported, not fatal)."""
    import shutil
    import tempfile
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot as SS
    from . import rzx as RZ
    prof = prof or json.load(open(_profile_path()))
    cap = SheetCapture(prof)
    tmp = tempfile.mkdtemp(prefix='nexclash_sheet_')
    try:
        for k, r in enumerate([rzx_paths] if isinstance(rzx_paths, str) else rzx_paths):
            src = r
            if sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS)) > 1:      # Fuse autosaves
                r = os.path.join(tmp, '%d_%s' % (k, os.path.basename(r)))
                RZ.strip(src, r)
            cap.frame.clear()
            n, err = RZ.trace(r, SheetCapture.PCS, cap.on_pc)
            if progress:
                progress(src, n, err)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return cap


def sheets(cap, prefix, colours=None):
    """Per SHEET_SPLIT name (players, each island, collectables; Dean 2026-10-19: one sheet per level +
    collectables + player when there are many figures): <prefix>_<NAME>_PAINTING_SPRITES.png (the
    fewest WHOLE figures that show every graphics byte once at least; + _layout.json, read back) and
    <prefix>_<NAME>_REFERENCE_ALL_SPRITES.png (every distinct figure drawn whole - not clipped at the
    play area's edge - and every collectable colour). -> [(path, figures)]."""
    from . import coloursheet as cs
    rgb = cs.palette_rgb(SHEET_PAL)
    order = [g for _, gs in SHEET_SPLIT for g in gs]
    fig_paint = cs.choose(list(cap.col.comps.values()), cap.col.maxsize, order)
    full = lambda c: all(p['size'] == cap.col.maxsize.get(p['id'], p['size']) for p in c['parts'])
    fig_all = sorted([c for c in cap.col.comps.values() if full(c)], key=lambda c: (order.index(c['group']) if c['group'] in order else 99,
                                                           str(c['parts'][0]['id'])))
    coll = collectable_comps(cap.fills.pictures, cap.prof)
    out = []
    for name, groups in SHEET_SPLIT:
        paint = [c for c in fig_paint if c['group'] in groups] + (coll if 'Collectables' in groups else [])
        allc = [c for c in fig_all if c['group'] in groups] + (coll if 'Collectables' in groups else [])
        opaque = lambda c: any(q[4] for p in c['parts'] for q in p['pixels'])
        paint, allc = [c for c in paint if opaque(c)], [c for c in allc if opaque(c)]
        if not paint:
            continue
        for kind, comps in (('PAINTING_SPRITES', paint), ('REFERENCE_ALL_SPRITES', allc)):
            png = '%s_%s_%s.png' % (prefix, name, kind)
            n = cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', rgb, colours, unique=False,
                         paint_clear=True)
            out.append((png, n))
    return out


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.rainbow',
                                 description='Rainbow Islands figure colours: sheets to paint')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> sheet PNGs + layout JSON (game graphics: keep private)')
    p.add_argument('rzx', nargs='+', help='recordings (e.g. the playthrough bookmarks, one per round)')
    p.add_argument('-o', '--output', default='rainbow_islands')
    a = ap.parse_args(argv)
    cap = sheet_capture(a.rzx, progress=lambda r, n, err: print('%s: %d frames%s' % (
        os.path.basename(r), n, ' (WARNING: desync: %s)' % err if err else ''), flush=True))
    for (isl, what), (d, nz) in cap.coverage().items():
        print('island %d %s: %d of %d non-zero buffer bytes drawn (%.0f%%)' % (isl, what, d, nz, 100.0 * d / max(nz, 1)))
    for png, n in sheets(cap, a.output):
        print('%d figures -> %s' % (n, png))


if __name__ == '__main__':
    _main()
