"""The Incredible Shrinking Fireman (Mastertronic, 1986; 48K) - engine `incredible_shrinking_fireman_add_opus`.

Figures that become sprites (Dean, 2026-10-25): every moving figure (the fireman and the room's two
figures, every caller of 0xB950) and the diamonds; in front of everything; live inks + the colour map.

    python -m nexclash.incredible_shrinking_fireman_add_opus sheet R.rzx [MORE.rzx] --z80 GAME.z80 -o PREFIX
    python -m nexclash.incredible_shrinking_fireman_add_opus colours PREFIX_PAINTING_SPRITES_painted.png
    python nexclash.py auto GAME.z80 --rzx R.rzx --no-record                   (build + verify)
    python nexclash.py recolour PREFIX_sprites.nex PAINTED.png                    (repaint, no rebuild)

Build (games/incredible_shrinking_fireman-add-OPUS.md "Build"): an OVERLAY - the game's plotter and
diamond drawing still write the ULA exactly as the original (the floor test reads those pixels); alt
ROM hooks at the plotter exit and the diamond draw put hardware sprites exactly on the figures' ink
pixels; the screen clears hide them; the figure attribute painting (0xBCDF) is removed. Verifier:
differential at every hook site + an independent model of the sprite layer, checked against the
plotter's own screen changes; every attribute read checked against the cells the patched game leaves
unpainted.

Figures (games/incredible_shrinking_fireman-add-OPUS.md):
  0xB950 moves object A (A = 0 fireman, 1 / 2 the room's two enemies) of the 8-byte table at 0xBCF7
  (x, y, frame, -, dx, dy, attribute, attribute keep-mask) to (x + dx, y + dy) showing frame (0xBCF6),
  XORing old ^ new graphic into the screen in ONE pass (delta draw); frame 0 is blank (appear /
  disappear). Then 0xBC5F paints the figure's 2 x 3 (3 x 4 unaligned) cells: attr = (scr ^ E) & D ^ E,
  E = attribute, D = keep-mask, cells flagged by bit 6 in the map at 0xBD44 left alone.
  Graphics: 16 x 24 px, 2 bytes per line top down, at base (0xBD42, 0x9C40 in every recording) +
  ((3 * frame) & 255) * 16 - the game's 8-bit multiply: frames >= 86 wrap.
Collectables (the diamonds): per room up to 5 entries (flag, x, y) via the table at 0xD6ED; 0xECCF
(room build) draws each with 0xECFF: 7 lines of 0xED14 written (not XORed), byte j on line B - j,
column C / 8 (C = pixel x: 0xED1B); a pickup (option screen) zeroes the entry (0xED37) and the room is
drawn again without it.
Colour-map keys: G + the graphics byte's address, D + address for the collectable; default colour =
the ink the game gives the figure (fireman: white; enemies: their room's bright ink; collectables:
their cell's ink).
"""
import collections
import json
import os

PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
BLACK = 8                                   # index 0 is transparent: black figures use 8
PLOT, OBJ, NEWF, GBASE, ATTRMAP = 0xB950, 0xBCF7, 0xBCF6, 0xBD42, 0xBD44
ITEM, ITEM_GFX, ITEM_H = 0xECFF, 0xED14, 7       # collectable: 7 lines up from B at column C / 8, overwrite
W, H = 16, 24
GROUPS = ('Fireman', 'Enemies', 'Collectables')
STATIC_GROUP = 'From the code (not in the recordings)'
_HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = 'incredible_shrinking_fireman-add-OPUS'
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')
NOTE = ('Incredible Shrinking Fireman figure colours, read back from the PAINTING_SPRITES sheet '
        '(python -m nexclash.incredible_shrinking_fireman_add_opus colours). Key = G + graphics byte '
        'address; check = that byte, 8 nibbles = colours of its bits (0 = the game\'s ink).')


def gfx_addr(base, frame):
    """Address of a frame's 48 bytes: the plotter's own (8-bit) arithmetic."""
    return (base + ((3 * frame) & 255) * 16) & 0xFFFF


def ink_index(attr, mask=0):
    """Attribute (and the plotter's keep-mask) -> palette index of the figure's ink (black -> BLACK).
    Bright when the attribute or the keep-mask has bit 6: the room build sets BRIGHT on every cell,
    so a figure that keeps the cell's bright bit (the fireman, mask 0x40) shows bright."""
    ink = attr & 7
    if not ink:
        return BLACK
    return ink + (8 if (attr | mask) & 64 else 0)


def figure_part(peek, base, frame, group, ink):
    a0 = gfx_addr(base, frame)
    pixels, entries = [], {}
    for line in range(H):
        for half in range(2):
            a = (a0 + line * 2 + half) & 0xFFFF
            v = peek(a)
            key = 'G%04X' % a
            for bit in range(8):
                if v >> (7 - bit) & 1:
                    pixels.append((half * 8 + bit, line, key, bit, 1, ink))
                    entries[key] = [v, 'G']
    return dict(id=(base, frame), size=1, w=W, h=H, x=0, y=0, mir=0, group=group, role=group,
                pixels=pixels, entries=entries)


def item_part(peek, ink):
    pixels, entries = [], {}
    for line in range(ITEM_H):                   # byte j is drawn on line B - j: row 6 - j
        a = ITEM_GFX + ITEM_H - 1 - line
        v = peek(a)
        key = 'D%04X' % a
        for bit in range(8):
            if v >> (7 - bit) & 1:
                pixels.append((bit, line, key, bit, 1, ink))
                entries[key] = [v, 'D']
    return dict(id=('item', ITEM_GFX), size=1, w=8, h=ITEM_H, x=0, y=0, mir=0, group=GROUPS[2],
                role=GROUPS[2], pixels=pixels, entries=entries)


def capture(rzxs):
    """Replay the recordings (C simulator) -> {(group, base, frame): info} of every drawing seen."""
    from . import rzx as RZ
    seen = collections.OrderedDict()

    def on_pc(pc, sim):
        m, R = sim.memory, sim.registers
        if pc == ITEM:
            y, col = R[2], R[3] >> 3
            at = m[0x5800 + (y >> 3) * 32 + col]
            k = (GROUPS[2], ITEM_GFX, 0)
            e = seen.get(k)
            if e is None:
                e = seen[k] = dict(group=GROUPS[2], base=ITEM_GFX, frame=0, inks=collections.Counter(),
                                   count=0, gfx=bytes(m[ITEM_GFX:ITEM_GFX + ITEM_H]))
            e['inks'][ink_index(at)] += 1
            e['count'] += 1
            return
        a = R[0]
        o = m[OBJ + 8 * a:OBJ + 8 * a + 8]
        f, base = m[NEWF], m[GBASE] | m[GBASE + 1] << 8
        if not f:
            return
        group = GROUPS[0] if a == 0 else GROUPS[1]
        k = (group, base, f)
        e = seen.get(k)
        if e is None:
            e = seen[k] = dict(group=group, base=base, frame=f, inks=collections.Counter(), count=0,
                               gfx=bytes(m[gfx_addr(base, f) + i & 0xFFFF] for i in range(48)))
        e['inks'][ink_index(o[6], o[7])] += 1
        e['count'] += 1
    errs = []
    for path in rzxs:
        n, err = RZ.trace(path, (PLOT, ITEM), on_pc)
        errs.append((path, n, err))
    return seen, errs


def composites(seen, peek=None):
    """One composite per (group, graphic): figures are single plots, never joined. A graphic drawn by
    both groups appears in each. peek: the bank's frames the recordings never drew are added."""
    from . import coloursheet as cs
    comps, drawn = [], set()
    for (group, base, f), e in seen.items():
        g = e['gfx']
        if group == GROUPS[2]:
            p = item_part(lambda a: g[a - ITEM_GFX], e['inks'].most_common(1)[0][0])
            comps.append(dict(count=e['count'], group=group, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
            continue
        p = figure_part(lambda a: g[(a - gfx_addr(base, f)) & 0xFFFF], base, f, group,
                        e['inks'].most_common(1)[0][0])
        drawn.add((base, f))
        if p['pixels']:
            comps.append(dict(count=e['count'], group=group, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    if peek:
        base = peek(GBASE) | peek(GBASE + 1) << 8
        for f in range(1, 86):                       # every whole frame of the bank (3f < 256)
            if (base, f) in drawn:
                continue
            p = figure_part(peek, base, f, STATIC_GROUP, 7)
            if p['pixels']:
                comps.append(dict(count=0, group=STATIC_GROUP, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    order = list(GROUPS) + [STATIC_GROUP]
    comps.sort(key=lambda c: (order.index(c['group']), c['parts'][0]['id']))
    maxsize = {c['parts'][0]['id']: 1 for c in comps}
    return cs.choose(comps, maxsize, order), comps


def sheets(comps, prefix, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix in ('_PAINTING_SPRITES', '_REFERENCE_ALL_SPRITES'):
        png = prefix + suffix + '.png'
        n = cs.write(comps[suffix], png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours,
                     unique=False)
        out.append((png, n))
    return out


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    p = path or build_colours_path(COLOURS)
    return cs.load(p) if os.path.exists(p) else {}


def _peek(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536])).__getitem__



# =============================================================================================
# Build: sites, patch, Next-side model, differential verify (games/<record>.md "Phase B design")
# =============================================================================================
ROM_ORG = 0x3A01                # 0x39FF-0x3A00 stay FF FF: the game's IM 2 vector is read there
ROM2_ORG = 0x386E               # second block, 0x386E-0x39FE
ALT_PAGE = 24                   # alt ROM image page (bank 12)
CPAGE = 26                      # colour map pages 26-30 (banks 13-15), mapped at slot 6 in a hook
CMAP_LEN = 5120                 # entries (8 bytes: 4 nibble bytes, check byte); 0..4143 graphics,
IDX_ITEM = 4144                 # 4144..4150 the collectable
FLAGS_PG, FLAGS_OFF = CPAGE + 4, 0x1F00
CMAP_BANKS = (13, 14, 15)
TAIL_ADDR, TAIL_END = 0x5D00, 0x615C        # 0x5C49-0x615B never read or written (whole-RZX scan)
GFX0 = 0x9C40
GFX_END = GFX0 + 4144           # figure graphics 0x9C40-0xAC6F: never written (whole-RZX scan)
SITES = {0xB950: ('dde587', 'e_ent', 'en'), 0xBC5C: ('dde1c9', 'e_plot', 'pl'), 0xECFF: ('1114ed', 'e_item', 'it'),
         0xC4A7: ('210040', 'e_c1', 'c'), 0xC5B1: ('210048', 'e_c2', 'c'), 0xB4AD: ('210040', 'e_c3', 'c'),
         0xFFF4: ('c34cc2', 'e_isr', 'isr')}
NOPS = [(0xBCDF, 'dd7700', '000000')]       # figure attribute painting removed (LD (IX+0),A)
IM2_SET = 0xC234                            # the game's IM 2 set-up: writes JP 0xC24C to 0xFFF4 (again on a
IM2_OP = 0xC240                             # restart, RZX frame 32335): its LD BC,0xC24C operand -> e_isr
INTERIORS = (0xB951, 0xBC5D, 0xFFF5, 0xFFF6, 0xED00, 0xED01, 0xC4A8, 0xC4A9, 0xC5B2, 0xC5B3, 0xB4AE, 0xB4AF,
             0xBCE0, 0xBCE1, IM2_OP, IM2_OP + 1)
PLOT_RANGE = (0xB950, 0xBC5F)               # the plotter's own screen writes
ITEM_PC = 0xED0B                            # the collectable's screen write (LD (HL),A)
ITEM_RET = 0xECF3
PAINT_PC = 0xBCDF
# attribute readers in the whole RZX (scan), with the register pair holding the address. The LDIR
# fills (0xC4B7, 0xB4BD, 0xC5CA) read only bytes they wrote one step before; 0xBCD9 is the
# painter's own read (dead in the patched game: its write is removed).
ATTR_READERS = {0xCAA2: (6, 7), 0xCABF: (6, 7), 0xB3F4: (4, 5), 0xB3C5: (4, 5), 0xB42C: (4, 5),
                0xC2E4: (4, 5), 0xC2E8: (4, 5)}
P30_OFF = 0x1600              # page 30: the hooks' code that runs from slot 6 (profile hooks['p30'])
RUN_LO, RUN_HI = 0x1E00, 0x1F20  # page 30: the bytes the hooks write at run time (tables, flags, cache)
DEPTH_OFF = 0x1E30              # page 30: plots in progress (hooks); +1 PENDING: a deferred interrupt
SEQUELS = {0xB952: 0xB950, 0xBC5E: 0xBC5C}  # reached right after the site's own first instruction


def spr_own(a):
    """Object a's own 4 sprites (an 18 x 26 masked image: top-left, top-right, bottom-left,
    bottom-right); the pending 4 are the next ones."""
    return 21 - 8 * a


FPAGE = 32                      # figure shapes: frame f at page 32 + f // 8, offset (f % 8) * 1024
MASK_COL = BLACK                # the mask (Dean 2026-10-25: all figures, up/down/left/right only)
FIG_W, FIG_H = W + 2, H + 2     # 18 x 26 with the mask


def fig_grid(g):
    """48 graphics bytes -> (ink, mask) sets of (col, row) in the 32 x 26 sprite area, figure at (1, 1).
    Mask = the 4-neighbours of ink that are not ink."""
    ink = set()
    for line in range(H):
        r = g[2 * line] << 8 | g[2 * line + 1]
        for k in range(16):
            if r >> (15 - k) & 1:
                ink.add((k + 1, line + 1))
    mask = set()
    for c, r in ink:
        for q in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
            if q not in ink:
                mask.add(q)
    return ink, mask


def fig_data(f, peek, cmap):
    """Frame f -> its 1024-byte block (asm upload): +0 the top-left 16 x 16 as code bytes (4 per row,
    each two pixel-pair codes: ink L 8, ink R 4, mask L 2, mask R 1), +64 the first code byte of each
    top-right row (columns 18-31 are always empty), +80 the bottom-left rows 16-25, +120 the first code
    byte of each bottom-right row, +256 one painted-override byte per pattern byte in upload order
    (nibble 0 = the live ink), +1023 1 if any override."""
    ga = gfx_addr(GFX0, f)
    g = bytes(peek((ga + i) & 0xFFFF) for i in range(48))
    ink, mask = fig_grid(g)

    def ov(c, r):
        if (c, r) not in ink:
            return 0
        b = 2 * (r - 1) + (c - 1) // 8
        return colour(cmap, 'G%04X' % ((ga + b) & 0xFFFF), g[b], (c - 1) % 8, 0)

    def pair(c, r):                    # pixel-pair code of columns c, c + 1
        return (((c, r) in ink) << 3 | ((c + 1, r) in ink) << 2 | ((c, r) in mask) << 1
                | ((c + 1, r) in mask))

    blk = bytearray(1024)
    codes, ovs = bytearray(), bytearray()
    for rows, c0, full in ((range(16), 0, True), (range(16), 16, False), (range(16, 26), 0, True),
                           (range(16, 26), 16, False)):
        for r in rows:
            for c in range(c0, c0 + 16, 4):
                if full or c == c0:
                    codes.append(pair(c, r) << 4 | pair(c + 2, r))
                ovs.append(ov(c, r) << 4 | ov(c + 1, r))
                ovs.append(ov(c + 2, r) << 4 | ov(c + 3, r))
    assert len(codes) == 130 and len(ovs) == 416
    blk[0:130] = codes
    blk[256:256 + 416] = ovs
    blk[1023] = 1 if any(ovs) else 0
    return bytes(blk)


def fig_pages(peek, cmap):
    """{page 32-63: 8192 bytes}: every frame's shape data (frame 0: nothing)."""
    pages = {FPAGE + k: bytearray(8192) for k in range(32)}
    for f in range(1, 256):
        pages[FPAGE + f // 8][(f % 8) * 1024:(f % 8) * 1024 + 1024] = fig_data(f, peek, cmap)
    return {k: bytes(v) for k, v in pages.items()}
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR
DECISIONS = {'engine': 'incredible_shrinking_fireman_add_opus',
             'strategy': 'overlay: the game still draws the ULA; hooks (alt ROM 0x3A01 + 0x386E, page 30 '
                         'at slot 6) set hardware sprites on the figures - the new image at the plotter entry '
                         '0xB950 (pending pair), switched at the exit 0xBC5C - and the diamonds (0xECFF); '
                         'figure attribute painting removed (0xBCDF); colour map pages 26-30',
             'figures': 'fireman, both room figures (every caller of 0xB950), the diamonds (Dean 2026-10-25)',
             'mask': 'fireman and both room figures: black, the 4-neighbours of ink (Dean 2026-10-25, hardware round '
                     '1: all figures, up / down / left / right only; black suggested, not objected to)',
             'depth': 'sprites in front of everything',
             'interrupts': 'deferred while a plot runs (0xFFF4 -> e_isr, and the IM 2 set-up 0xC234 writes that jump '
                           'too: it runs again on a restart; the plotter is not re-entrant and the '
                           'hooks moved the plots, so the ISR plotting into a main-code plot corrupted the screen '
                           'on hardware, Dean 2026-10-25 room 5); run at the plot exit',
             'tail': '0x5D00 (0x5C49-0x615B untouched in the whole-game RZX); printer buffer put back '
                     '(the game reads 0x5B41)',
             'colours': 'live inks (fireman white, figures the room ink, diamonds their cell ink) + '
                        'docs/profiles/%s_colours.json when present' % RECORD}


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_incredible_shrinking_fireman_add_opus(snap):
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def cmap_index(key):
    """Colour-map key -> entry index used by the hooks, or None (outside the map)."""
    a = int(key[1:], 16)
    if key[0] == 'G':
        i = a - GFX0
        return i if 0 <= i < IDX_ITEM else None
    if key[0] == 'D':
        i = a - ITEM_GFX
        return IDX_ITEM + i if 0 <= i < ITEM_H else None
    return None


def cmap_pages(cmap, peek=None, code=None):
    """Colour map {key: [check, kind, 8 nibbles]} -> {page: 8192 bytes} for pages 26-30 (run-time
    bytes 0). peek (the game's graphics, static): the painted-frame table at page 30 + 0x1400. code:
    the hooks' page-30 code (default: the profile's), at page 30 + 0x1600."""
    pages = {CPAGE + k: bytearray(8192) for k in range(5)}
    code = bytes.fromhex(load_profile()['hooks']['p30']) if code is None else code
    pages[FLAGS_PG][P30_OFF:P30_OFF + len(code)] = code
    for key, e in cmap.items():
        i = cmap_index(key)
        if i is None:
            continue
        nib = e[2]
        if not any(nib):
            continue
        pg, off = CPAGE + i // 1024, (i % 1024) * 8
        for k in range(4):
            pages[pg][off + k] = nib[2 * k] << 4 | nib[2 * k + 1]
        pages[pg][off + 4] = e[0] & 255
    return pages


def cmap_banks(cmap, peek, code=None):
    """Every bank the colours decide: 13-15 (colour-map pages 26-30, page-30 code and tables) and
    16-31 (the figure shapes with their painted overrides). The game never reads them."""
    pg = cmap_pages(cmap, peek, code)
    fp = fig_pages(peek, cmap)
    out = {13: bytes(pg[26] + pg[27]), 14: bytes(pg[28] + pg[29]), 15: bytes(pg[30]) + bytes(8192)}
    for b in range(16, 32):
        out[b] = fp[2 * b] + fp[2 * b + 1]
    return out


class FiremanPatch:
    name = ('Incredible Shrinking Fireman: fireman, room figures and diamonds -> hardware sprites '
            '(overlay; plotter entry + exit hooks, alt ROM + page 30 at slot 6)')

    def __init__(self, prof=None, rom_code=None, colours=None, rom2=None, p30=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.rom2 = rom2 or bytes.fromhex(h['rom2'])
        self.p30 = p30 or bytes.fromhex(h['p30'])
        if P30_OFF + len(self.p30) > 0x1E00:
            raise ValueError('page-30 code too long (tables from 0x1E00)')
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.keep_printer_buffer = True          # the game reads 0x5B41: NEXLOAD overwrites it
        self.tail_addr = TAIL_ADDR
        self.max_tail = TAIL_END - TAIL_ADDR
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long (0x3D00-0x3DFF: no code, DivMMC trap)')
        if ROM2_ORG + len(self.rom2) > 0x39FF:
            raise ValueError('second hook block too long (0x39FF-0x3A00: the IM 2 vector)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM2_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM2_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        page[ROM2_ORG - 0x2000:ROM2_ORG - 0x2000 + len(self.rom2)] = self.rom2
        self.page = bytes(page)
        self.sites = [(a, bytes.fromhex(old), b'\xC3' + self.syms[sym].to_bytes(2, 'little'))
                      for a, (old, sym, k) in SITES.items()]
        self.sites += [(a, bytes.fromhex(old), bytes.fromhex(new)) for a, old, new in NOPS]
        self.sites.append((IM2_OP, b'\x4C\xC2', self.syms['e_isr'].to_bytes(2, 'little')))
        self.cmap = load_colours() if colours is None else colours
        self.pages = cmap_pages(self.cmap, code=self.p30)
        self.extra_banks = {}

    def prepare(self, peek):
        """The colour-map pages and the figure shapes (from the game's static graphics)."""
        self.peek = peek
        self.pages = cmap_pages(self.cmap, peek, self.p30)
        self.pages.update(fig_pages(peek, self.cmap))

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Incredible Shrinking Fireman patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if ram[GBASE - 0x4000] | ram[GBASE - 0x4000 + 1] << 8 != GFX0:
            raise ValueError('graphics base is not 0x%04X in this snapshot' % GFX0)
        g = bytes(ram)
        self.prepare(lambda a: g[a - 0x4000])
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {12: self.page + bytes(8192)}
        self.extra_banks.update(cmap_banks(self.cmap, self.peek, self.p30))


# ---------------------------------------------------------------------------------------------
# Next-side state of the patched machine: NEXTREG, sprite attributes, pattern upload, MMU6 pages
# ---------------------------------------------------------------------------------------------

class NextState:
    """pages: the Next pages the hooks map - 26-30 at slot 6 (written: tables, flags, cache), the
    figure shapes 32-63 at slot 7 (read only: shared between copies, never copied)."""

    def __init__(self, pages):
        self.nr = {0x56: 0, 0x57: 1}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pidx = 0
        self.pages = {k: (bytearray(v) if k < FPAGE else v) for k, v in pages.items()}
        self.events = []
        self.bad = []

    def copy(self):
        n = NextState({})
        n.nr = dict(self.nr)
        n.attr = [list(a) for a in self.attr]
        n.pat = bytearray(self.pat)
        n.pidx = self.pidx
        n.pages = {k: (bytearray(v) if k < FPAGE else v) for k, v in self.pages.items()}
        return n

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x56:
            if val != 0 and not (CPAGE <= val < CPAGE + 5 and val in self.pages):
                self.bad.append(('MMU6 set to page %d' % val,))
        elif reg == 0x57:
            if val != 1 and not (FPAGE <= val < FPAGE + 32 and val in self.pages):
                self.bad.append(('MMU7 set to page %d' % val,))
        elif reg not in (0x34, 0x07):
            self.bad.append(('NEXTREG 0x%02X' % reg,))
        self.events.append(('nr', reg, val))

    def port(self, port, v):
        if port & 0xFF == 0x3B and port >> 8 == 0x30:
            self.pidx = (v & 0x3F) * 256 + (128 if v & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pidx % 16384] = v
            self.pidx += 1
        else:
            self.bad.append(('OUT 0x%04X' % port,))

    @property
    def flags(self):
        return self.pages[FLAGS_PG][FLAGS_OFF] if FLAGS_PG in self.pages else 0

    def layer(self, sprites=range(128)):
        """Visible sprite pixels -> {(x, y): nibble} in ULA coordinates, higher sprite on top."""
        out = {}
        for i in sprites:
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            if a2 & 0xFE or not a4 & 0x80 or a4 & 0x3E:
                self.bad.append(('sprite %d: unexpected attribute bits' % i,))
                continue
            x = a0 + (a2 & 1) * 256 - 32
            y = a1 + (a4 & 1) * 256 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            for j in range(16):
                row = self.pat[base + j * 8:base + j * 8 + 8]
                for k in range(16):
                    b = row[k >> 1]
                    n = (b >> 4) if not k & 1 else (b & 15)
                    if n and 0 <= x + k < 256 and 0 <= y + j < 192:
                        out[(x + k, y + j)] = n
        return out


def _machine(Sim, mem, regs, ns, slot='o'):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)
    R, ed = sim.registers, sim.after_ED

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536; R[25] += 20

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536; R[25] += 17
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs_, port):
            ns.bad.append(('IN 0x%04X' % port,))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.port(port, value)
    sim.set_tracer(Tr())
    return sim


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def _overlays(get, alt, psite, ns):
    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return v if v is not None else get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if 0xC000 <= a < 0xE000:
                pg = ns.nr.get(0x56, 0)
                if pg:
                    return ns.pages[pg][a - 0xC000]
            elif a >= 0xE000:
                pg = ns.nr.get(0x57, 1)
                if pg != 1:
                    return ns.pages[pg][a - 0xE000]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', 0) + 1
            elif 0xC000 <= a < 0xE000 and ns.nr.get(0x56, 0):
                ns.pages[ns.nr[0x56]][a - 0xC000] = v
            elif a >= 0xE000 and ns.nr.get(0x57, 1) != 1:
                ns.bad.append(('write to a figure-shape page (MMU7)',))
            else:
                s.ov[a] = v
    return O, P


def _run(sim, stop, limit=400000, check=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        if check:
            check()
        n += 1
        if n > limit:
            return False
    return True


def _isafe(sim, regs0, ixs, ns, err):
    """Interrupt safety while the hook runs with interrupts on (alt ROM PC, IFF1 set: before the DI
    or after the EI): the game's ISR (IM 2 via 0xFFF4) reads the interrupted IX, uses the alternate
    set, I and up to 42 bytes of stack, and calls the plotter (needs MMU6 = page 0). Allowed: IX the
    site's or the one POP IX gave, SP at most one push (2 bytes) below the site's SP."""
    R = sim.registers
    iy, i, sp0 = (regs0[10], regs0[11]), regs0[14], regs0[12]
    alt0 = regs0[16:24]

    def chk():
        pc = R[24]
        if pc >= 0x4000 or not R[26]:
            if pc < 0x4000 and 0x3D00 <= pc < 0x3E00 and not err:
                err.append(('instruction fetch in 0x3D00-0x3DFF', pc))
            return
        ISAFE['checked'] += 1
        bad = None
        if (R[8], R[9]) not in ixs or (R[10], R[11]) != iy:
            bad = 'IX/IY'
        elif R[14] != i or R[16:24] != alt0:
            bad = 'I / alternate set'
        elif R[12] < sp0 - 2:
            bad = 'SP more than one push below the site'
        elif ns.nr.get(0x56, 0) or ns.nr.get(0x57, 1) != 1:
            bad = 'MMU6 / MMU7 mapped'
        elif 0x3D00 <= pc < 0x3E00:
            bad = 'fetch in 0x3D00-0x3DFF'
        if bad and not err:
            err.append(('interrupt-unsafe hook: %s' % bad, hex(pc)))
    return chk


ISAFE = {'checked': 0}
COST = {'extra': 0}     # last event: patched - original T at 3.5 MHz (28 MHz T / 6, LEARNINGS 2.1f)


def event(patch, kind, site, get, R, ns, alt, Sim):
    """Original and patched code from one state, to the site's end. -> (failures, original overlay,
    final original registers). ns (the patched machine's Next state) is updated in place."""
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    sp0 = R[12]
    w = lambda a: get(a) | get(a + 1) << 8
    if kind == 'en':
        stop = lambda r: r[24] == 0xB953 and r[12] == sp0 - 2
    elif kind == 'pl':
        ret, end = w(sp0 + 2), sp0 + 4
        stop = lambda r: r[24] == ret and r[12] == end
    elif kind == 'it':
        stop = lambda r: r[24] == 0xED02 and r[12] == sp0
    elif kind == 'isr':
        stop = lambda r: r[24] == 0xC24C and r[12] == sp0
    else:
        nxt = site + 3
        stop = lambda r: r[24] == nxt and r[12] == sp0
    O, P = _overlays(get, alt, psite, ns)
    o, p = O(), P()
    ns.events, ns.bad = [], []
    so = _machine(Sim, o, list(R), NextState({}))
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    f = []
    if not _run(so, stop):
        return ['original did not return'], o, so.registers
    err = []
    ix_after = (w(sp0), ) if kind == 'pl' else ()
    ixs = {(R[8], R[9])} | {(v >> 8, v & 255) for v in ix_after}
    chk = _isafe(sp_, R, ixs, ns, err)
    rp_, tm = sp_.registers, {'prev': R[25], 'slow': 0, 'fast': 0}

    def check():                                 # T at 3.5 MHz / at 28 MHz (NEXTREG $07 = 3)
        chk()
        d = rp_[25] - tm['prev']
        tm['prev'] = rp_[25]
        tm['fast' if ns.nr.get(0x07, 0) == 3 else 'slow'] += d
    if not _run(sp_, stop, check=check):
        return ['patched code did not return'], o, so.registers
    COST['extra'] = tm['slow'] + tm['fast'] / 6.0 - (so.registers[25] - R[25])
    f += err
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    f += ns.bad
    if ns.nr.get(0x56, 0) or ns.nr.get(0x57, 1) != 1:
        f.append(('MMU6 / MMU7 left mapped',))
    dead = range(ro[12] - 64, ro[12])             # below the final SP: dead stack
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if a not in dead and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), [hex(a) for a in sorted(md)[:4]]))
    return f, o, ro


# ---------------------------------------------------------------------------------------------
# Model of what the build must show (from the original's own state, independent of the hooks)
# ---------------------------------------------------------------------------------------------

def row_bits(g, line):
    return g[2 * line] << 8 | g[2 * line + 1]


def screen_addr(x8, y):
    return 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x8


def image_bytes(img):
    """img (x, y, 48 graphics bytes) or None -> {screen address: byte} of its pixels."""
    out = {}
    if img is None:
        return out
    x, y, g = img
    for line in range(H):
        r = row_bits(g, line) << 8 >> (x & 7)
        if not r:
            continue
        for k in range(3):
            v = r >> (16 - 8 * k) & 255
            if v:
                c = (x >> 3) + k
                out[(c, y + line)] = out.get((c, y + line), 0) ^ v
    return {(screen_addr(c, yy) if c < 32 and yy < 192 else ('off', c, yy)): v for (c, yy), v in out.items()}


def colour(cmap, key, byte, bit, ink):
    e = cmap.get(key)
    if e is not None and e[0] == byte:
        n = e[2][bit]
        if n:
            return n
    return ink


class Model:
    """Expected sprite layer: objects 0-2 as last plotted (frame 0 or a screen clear: none), the
    pair rule (objects 1 and 2 on one spot with one frame: both hidden, as their XORs cancel), each
    object's pending image while its plot runs (entry to exit), and the diamonds drawn since the last
    clear. Higher sprite on top: diamonds, then per object 2, 1, 0 its own pair and its pending pair."""

    def __init__(self, cmap):
        self.cmap = cmap
        self.objs = [None, None, None]        # (x, y, frame, gfx address, 48 bytes, ink)
        self.pend = [None, None, None]        # the same for the image being plotted
        self.items = {}                       # k: (pixel x, bottom line, ink)

    def clear(self):
        self.objs = [None, None, None]
        self.pend = [None, None, None]
        self.items = {}

    def image(self, o, out=None, ink_only=False):
        """Object image o -> {(x, y): colour} on the screen: its ink pixels (colour map / live ink) and
        the black mask around them (4-neighbours), one pixel outside the 16 x 24 graphic."""
        out = {} if out is None else out
        x, y, fr, ga, g, ink = o
        inks, mask = fig_grid(g)
        if not ink_only:
            for c, r in mask:
                px, py = x - 1 + c, y - 1 + r
                if 0 <= px < 256 and 0 <= py < 192:
                    out[(px, py)] = MASK_COL
        for c, r in inks:
            px, py = x - 1 + c, y - 1 + r
            if 0 <= px < 256 and 0 <= py < 192:
                b = 2 * (r - 1) + (c - 1) // 8
                out[(px, py)] = colour(self.cmap, 'G%04X' % ((ga + b) & 0xFFFF), g[b], (c - 1) % 8, ink)
        return out

    def pair(self):
        o1, o2 = self.objs[1], self.objs[2]
        return o1 is not None and o2 is not None and o1[:3] == o2[:3]

    def layer(self):
        out = {}
        for k in sorted(self.items):
            c, b, ink = self.items[k]
            for j in range(ITEM_H):
                a = ITEM_GFX + j
                v = self.peek(a)
                for bit in range(8):
                    if v >> (7 - bit) & 1:
                        x, y = (c & 0xF8) + bit, b - j
                        if 0 <= y < 192:
                            out[(x, y)] = colour(self.cmap, 'D%04X' % a, v, bit, ink)
        pair = self.pair()
        for a in (2, 1, 0):
            o = self.objs[a]
            if o is not None and not (pair and a in (1, 2)):
                self.image(o, out)
            if self.pend[a] is not None:
                self.image(self.pend[a], out)
        return out


def obj_predicted(get, a):
    """At the plotter entry (A = a): the image the plot will show - (x + dx, y + dy) 8-bit as
    0xB97D / 0xB982, frame (0xBCF6), ink from the table's attribute and keep-mask."""
    o = [get(OBJ + 8 * a + k) for k in range(8)]
    fr = get(NEWF)
    if not fr:
        return None
    base = get(GBASE) | get(GBASE + 1) << 8
    ga = gfx_addr(base, fr)
    g = bytes(get((ga + i) & 0xFFFF) for i in range(48))
    return ((o[0] + o[4]) & 255, (o[1] + o[5]) & 255, fr, ga, g, ink_index(o[6], o[7]))


def obj_from_table(get, a):
    o = [get(OBJ + 8 * a + k) for k in range(8)]
    fr = o[2]
    if not fr:
        return None
    base = get(GBASE) | get(GBASE + 1) << 8
    ga = gfx_addr(base, fr)
    g = bytes(get((ga + i) & 0xFFFF) for i in range(48))
    return (o[0], o[1], fr, ga, g, ink_index(o[6], o[7]))


def item_ink(get, b, x):
    return ink_index(get(0x5800 + (b >> 3) * 32 + (x >> 3)))


def cover_of(layer):
    """{screen address: mask} of the expected sprite ink pixels."""
    out = {}
    for (x, y) in layer:
        a = screen_addr(x >> 3, y)
        out[a] = out.get(a, 0) | 0x80 >> (x & 7)
    return out


# ---------------------------------------------------------------------------------------------
# Differential verification against an RZX (the replay runs the ORIGINAL game)
# ---------------------------------------------------------------------------------------------

_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX (original game, Python simulator); at every hook site run the original and
    the patched code from the same state and compare; check the sprite layer against the model, the
    plotter's screen changes against the model's images, the diamonds' writes, and every attribute
    read against the cells the patched game leaves unpainted. -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    Sim = _rw()
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    isr_jp = b'\xC3' + patch.syms['e_isr'].to_bytes(2, 'little')
    ns = NextState(patch.pages)
    model = Model(patch.cmap)
    st = {'frame': 0, 'on': False, 'paint': False, 'R': None, 'cover': {}}
    plots, items, adiff = [], [], {}
    cnt = collections.Counter()
    under = collections.Counter()
    fcost = collections.Counter()
    states = []
    WATCH = set(SITES) | set(INTERIORS) | {PLOT, PAINT_PC, ITEM_RET} | set(SEQUELS) | set(ATTR_READERS)

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['on']:
                if a in site_bytes:
                    if 0xFFF4 <= a <= 0xFFF6 and IM2_SET <= st['R'][24] < IM2_SET + 0x17 and v == isr_jp[a - 0xFFF4]:
                        c['IM 2 jump re-written by the game (0xC234) with the hook'] += 1
                    else:
                        fail('game wrote a patch site', (hex(a), hex(st['R'][24]), v))
                if GFX0 <= a < GFX_END or ITEM_GFX <= a < ITEM_GFX + ITEM_H:
                    fail('game wrote figure / diamond graphics (the build precomputes from them)', (hex(a),))
                if a < 0x5800:
                    if a >= 0x4000:
                        d = G(s, a) ^ v
                        pc = st['R'][24]
                        if pc == ITEM_PC and items:
                            items[-1]['w'][a] = v
                        elif d:
                            if plots and PLOT_RANGE[0] <= pc < PLOT_RANGE[1]:
                                t = plots[-1]['delta']
                                t[a] = t.get(a, 0) ^ d
                            else:
                                m = st['cover'].get(a)
                                if m and d & m:
                                    under[pc] += 1
                elif a < 0x5B00 and not st['paint']:
                    adiff.pop(a, None)
            S(s, a, v)

    def mem_snapshot(get):
        return bytes(get(a) for a in range(65536))

    def after(get, kind, pc):
        """Sprite layer of the patched machine vs the model."""
        exp = model.layer()
        got = ns.layer()
        if ns.bad:
            fail('%s: %s' % (kind, ns.bad[0][0]))
            ns.bad = []
        if got != exp:
            go, eo = set(got.items()) - set(exp.items()), set(exp.items()) - set(got.items())
            fail('%s: sprite layer differs from the model' % kind,
                 (hex(pc), 'sprites only', len(go), sorted(go)[:3], 'model only', len(eo), sorted(eo)[:3]))
        c['sprite pixels compared'] += len(exp)
        st['cover'] = cover_of(exp)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            st['R'] = R
            get = lambda a: G(mem, a)

            def run_event(kind, pc):
                if collect and c['collected ' + kind] < collect:
                    c['collected ' + kind] += 1
                    states.append((kind, pc, list(R), mem_snapshot(get), ns.copy()))
                if kind == 'en' and R[26] and collect and c['collected enm'] < 2 and st['frame'] > 1000:
                    c['collected enm'] += 1                 # a main-program plot (interrupts on)
                    states.append(('enm', pc, list(R), mem_snapshot(get), ns.copy()))
                COST['extra'] = 0
                fl, o, ro = event(patch, kind, pc, get, R, ns, alt, Sim)
                c[kind] += 1
                if kind in ('en', 'pl'):
                    st['depth'] = st.get('depth', 0) + (1 if kind == 'en' else -1)
                    if ns.pages[FLAGS_PG][DEPTH_OFF] != max(0, st['depth']):
                        fail('hooks\' plot depth differs from the plots in progress',
                             (ns.pages[FLAGS_PG][DEPTH_OFF], st['depth']))
                fcost[st['frame']] += COST['extra']
                for k in fl:
                    fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k),
                         k[1:] if isinstance(k, tuple) else ())
                return o

            def mk(fn, op):
                def g():
                    pc = R[24]
                    if pc not in WATCH:
                        fn()
                        return
                    cnt[pc] += 1
                    if pc == PLOT:
                        a = R[0]
                        old = obj_from_table(get, a) if a < 3 else None
                        pred = obj_predicted(get, a) if a < 3 else None
                        run_event('en', pc)
                        if a < 3:
                            if model.pend[a] is not None:
                                fail('plot entry while the same object\'s plot runs', (a,))
                            # the old image (as the screen holds it) and the new one must stay
                            # covered while the plot changes the screen between them
                            shown_old = model.objs[a] is not None and not (model.pair() and a in (1, 2))
                            model.pend[a] = pred
                            exp = model.layer()
                            need = set()
                            if shown_old:
                                need |= set(model.image(model.objs[a], ink_only=True))
                            if pred is not None:
                                need |= set(model.image(pred, ink_only=True))
                            miss = need - set(exp)
                            if miss:
                                fail('plot entry: image pixels not under a sprite during the plot', (a, len(miss)))
                            if model.objs[a] is not None and not shown_old:
                                c['plot entry of a pair-hidden figure (its old pixels uncovered while it moves)'] += 1
                            c['transient pixels covered'] += len(need)
                        plots.append({'a': a, 'old': old, 'pred': pred, 'delta': {}})
                        after(get, 'en', pc)
                    elif pc == PAINT_PC:
                        cell = (R[8] << 8 | R[9]) + get(R[24] + 2) - (256 if get(R[24] + 2) > 127 else 0)
                        if 0x5800 <= cell < 0x5B00 and cell not in adiff:
                            adiff[cell] = get(cell)
                        st['paint'] = True
                        fn()
                        st['paint'] = False
                        return
                    elif pc in ATTR_READERS:
                        h, l = ATTR_READERS[pc]
                        addr = R[h] << 8 | R[l]
                        if 0x5800 <= addr < 0x5B00:
                            c['attribute reads checked'] += 1
                            if addr in adiff and adiff[addr] != get(addr):
                                fail('attribute read sees a cell the patched game leaves unpainted',
                                     (hex(pc), hex(addr)))
                    elif pc == 0xBC5C:
                        if get(GBASE) | get(GBASE + 1) << 8 != GFX0:
                            fail('graphics base is not 0x9C40', ())
                        rec = plots.pop() if plots else None
                        a = (R[6] << 8 | R[7]) - (OBJ + 2)
                        a = a // 8 if a % 8 == 0 and 0 <= a < 24 else None
                        run_event('pl', pc)
                        if rec is None or a is None or rec['a'] != a:
                            fail('plot exit without its entry / object', (a,))
                        else:
                            new = obj_from_table(get, a)
                            want = image_bytes(None if rec['old'] is None else rec['old'][:2] + (rec['old'][4],))
                            for k2, v2 in image_bytes(None if new is None else new[:2] + (new[4],)).items():
                                want[k2] = want.get(k2, 0) ^ v2
                            want = {k2: v2 for k2, v2 in want.items() if v2}
                            got = {k2: v2 for k2, v2 in rec['delta'].items() if v2}
                            if want != got:
                                fail('plot: screen change is not old ^ new image', (a, len(set(want.items()) ^ set(got.items()))))
                            c['plot screen bytes compared'] += len(want)
                            pr = rec['pred']
                            if (pr is None) != (new is None) or (pr is not None and pr[:3] != new[:3]):
                                fail('plot exit: (x, y, frame) differs from the entry prediction',
                                     (a, pr and pr[:3], new and new[:3]))
                            model.objs[a] = new
                            model.pend[a] = None
                            after(get, 'pl', pc)
                    elif pc == 0xECFF:
                        k = 5 - get(R[12] + 5)
                        run_event('it', pc)
                        b, col = R[2], R[3]
                        items.append({'k': k, 'b': b, 'c': col, 'w': {}})
                        if 0 <= k < 5:
                            model.items[k] = (col, b, item_ink(get, b, col))
                        else:
                            fail('diamond loop counter outside 1-5', (k,))
                        after(get, 'it', pc)
                    elif pc == ITEM_RET:
                        if items:
                            it = items.pop()
                            want = {screen_addr(it['c'] >> 3, it['b'] - j): get(ITEM_GFX + j) for j in range(ITEM_H)
                                    if 0 <= it['b'] - j < 192}
                            if it['w'] != want:
                                fail('diamond: screen writes are not the 7 graphics bytes at (C, B - j)', ())
                            c['diamond screen bytes compared'] += len(want)
                    elif pc == 0xFFF4:
                        if ns.pages[FLAGS_PG][DEPTH_OFF]:
                            # the frame interrupt inside a main-program plot: the patched game defers
                            # it to the plot's exit. Check the deferral, then (from this real state)
                            # that "deferred" = "the plot first, then the handler"; the replay itself
                            # goes on in the original's order, so the patched state drops the mark.
                            c['isr deferred'] += 1
                            fl = _defer_check(patch, get, R, ns)
                            for k in fl:
                                fail('isr deferral: %s' % k[0], k[1:])
                            ns.pages[FLAGS_PG][DEPTH_OFF + 1] = 0
                        else:
                            run_event('isr', pc)
                            after(get, 'isr', pc)
                    elif pc in SITES:
                        run_event('c', pc)
                        model.clear()
                        after(get, 'c', pc)
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i], i)
            model.peek = get

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if progress and st['frame'] % 1000 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = Sm
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
    for a, site in SEQUELS.items():         # the original's next instruction after the site's first
        if cnt[a] != cnt[site]:
            c['0x%04X reached other than from 0x%04X!' % (a, site)] += 1
    c['frames'] = st['frame']
    c['interrupt-safety points'] = ISAFE['checked']
    if fcost:
        v = sorted(fcost.values())
        c['speed: hook T per game frame, mean'] = int(sum(v) / max(1, st['frame']))
        c['speed: hook T per game frame, max'] = int(v[-1])
        c['speed: hook T per game frame, 99th percentile of frames with hooks'] = int(v[int(len(v) * 0.99) - 1])
    for pc, n in under.most_common():
        c['  writes under a visible sprite by 0x%04X' % pc] = n
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests (paths the RZX does not reach) and negative controls
# ---------------------------------------------------------------------------------------------

def _ns_for(pt, ns0):
    """The patched machine's Next state for patch pt from a captured one: pt's OWN colour tables,
    only the run-time bytes (sprites, patterns, the flags byte) restored from the capture."""
    ns = ns0.copy()
    ns.pages = {k: (bytearray(v) if k < FPAGE else v) for k, v in pt.pages.items()}
    if FLAGS_PG in ns0.pages:
        ns.pages[FLAGS_PG][RUN_LO:RUN_HI] = ns0.pages[FLAGS_PG][RUN_LO:RUN_HI]
    return ns


def _plot_case(pt, R, mem, ns0, a, x, y, fr, e=7, d=0x40, flags=None, other=None, ns=None):
    """Run the plot exit for object a placed at (x, y, fr) with no entry hook before it (the
    fallback: the exit builds the image) -> (failures, ns, memory)."""
    m = bytearray(mem)
    o = OBJ + 8 * a
    m[o], m[o + 1], m[o + 2], m[o + 6], m[o + 7] = x, y, fr, e, d
    if other:
        for b, vals in other.items():
            for k, v in vals.items():
                m[OBJ + 8 * b + k] = v
    r = list(R)
    hl = o + 2
    r[6], r[7] = hl >> 8, hl & 255
    if ns is None:
        ns = _ns_for(pt, ns0)
        ns.pages[FLAGS_PG][FLAGS_OFF + 1] = 0                # no pending image
        if flags is not None:
            ns.pages[FLAGS_PG][FLAGS_OFF] = flags
    fl, _, _ = event(pt, 'pl', 0xBC5C, m.__getitem__, r, ns, _alt(pt), _rw())
    return fl, ns, m


def _entry_case(pt, R, mem, ns, a, x0, y0, f0, dx, dy, f, e=7, d=0x40):
    """Run the plot ENTRY for object a at (x0, y0, f0) moving by (dx, dy) to frame f, on Next state
    ns -> (failures, memory)."""
    m = bytearray(mem)
    o = OBJ + 8 * a
    m[o], m[o + 1], m[o + 2], m[o + 4], m[o + 5], m[o + 6], m[o + 7] = x0, y0, f0, dx, dy, e, d
    m[NEWF] = f
    r = list(R)
    r[0] = a
    fl, _, _ = event(pt, 'en', 0xB950, m.__getitem__, r, ns, _alt(pt), _rw())
    return fl, m


def _own(a):
    return range(spr_own(a), spr_own(a) + 8)


def _model_objs(pt, m, shown):
    md = Model(pt.cmap)
    md.peek = m.__getitem__
    for b in range(3):
        if b in shown:
            md.objs[b] = obj_from_table(m.__getitem__, b)
    return md


def _defer_check(pt, get, R, ns):
    """At 0xFFF4 with a main-program plot in progress (live state get / R, patched Next state ns):
    (1) the patched e_isr returns to the interrupted PC with every register and all memory as they
    were (the interrupt's push popped) and PENDING set; (2) from this state, the patched game (plot
    continues, its exit runs the handler) = the original with the handler delivered right after the
    plot returns: registers, all memory (dead stack excepted). -> failures."""
    f = []
    sp0 = R[12]
    back = get(sp0) | get(sp0 + 1) << 8
    psite = {a + k: v for a, old, new in pt.sites for k, v in enumerate(new)}
    alt = _alt(pt)
    n1 = ns.copy()
    _, P = _overlays(get, alt, psite, n1)
    p = P()
    sim = _machine(_rw(), p, list(R), n1, 'd')
    if not _run(sim, lambda r: r[24] == back and r[12] == sp0 + 2):
        return [('patched e_isr did not return to the plot',)]
    r = sim.registers
    d = [i for i in CMP if i not in (12, 24, 26) and r[i] != R[i]]
    if d or not r[26]:
        f.append(('registers changed by the deferral', d))
    md = [a for a in p.ov if a < sp0 - 64 or a >= sp0 + 2]
    if md:
        f.append(('memory changed by the deferral', [hex(a) for a in md[:3]]))
    if n1.pages[FLAGS_PG][DEPTH_OFF + 1] != 1:
        f.append(('PENDING not set',))
    # (2) the pair: the plot's return address is on the stack below its own frame - find it by
    # running the original (no interrupt) from the interrupted PC until the plotter's RET
    def resumed():
        rr = list(R)
        rr[24], rr[12], rr[26] = back, sp0 + 2, 1
        return rr
    O, _ = _overlays(get, None, {}, NextState({}))
    o = O()
    so = _machine(_rw(), o, resumed(), NextState({}), 'o')
    ro = so.registers
    exits = {'n': 0}
    while True:                                   # the original, to the plotter's exit 0xBC5C
        if ro[24] == 0xBC5C:
            break
        so.opcodes[o[ro[24]]]()
        exits['n'] += 1
        if exits['n'] > 400000:
            return f + [('original plot did not reach its exit',)]
    sp_ex = ro[12]
    ret = o[sp_ex + 2] | o[sp_ex + 3] << 8      # (POP IX; RET)
    _run(so, lambda r: r[24] == ret and r[12] == sp_ex + 4)
    spr = ro[12]
    o[spr - 2], o[spr - 1], ro[12], ro[24], ro[26] = ret & 255, ret >> 8, spr - 2, 0xFFF4, 0
    if not _run(so, lambda r: r[24] == ret and r[12] == spr, limit=4000000):
        return f + [('original handler did not return',)]
    n2 = n1.copy()
    _, P2 = _overlays(get, alt, psite, n2)
    p2 = P2()
    for a, v in p.ov.items():
        p2.ov[a] = v
    sp2 = _machine(_rw(), p2, list(sim.registers), n2, 'p')
    if not _run(sp2, lambda r: r[24] == ret and r[12] == spr, limit=4000000):
        return f + [('patched plot + deferred handler did not return',)]
    rp = sp2.registers
    d = [i for i in CMP if ro[i] != rp[i]]
    if d:
        f.append(('deferred run: registers differ from plot-then-handler', d))
    dead = range(spr - 80, spr)
    keys = set(o.ov) | set(p2.ov)
    md = [a for a in keys if a not in dead and o[a] != p2[a]]
    if md:
        f.append(('deferred run: memory differs from plot-then-handler', len(md), [hex(a) for a in sorted(md)[:4]]))
    if n2.pages[FLAGS_PG][DEPTH_OFF + 1]:
        f.append(('PENDING left set',))
    return f


def _im2_setup(sites, mem):
    """Run the game's IM 2 set-up 0xC234 to its RET on mem with `sites` applied -> bytes at 0xFFF4."""
    from skoolkit.simulator import Simulator
    m = list(mem)
    for a, old, new in sites:
        m[a:a + len(new)] = new
    m[0x8000:0x8002] = [0x00, 0x90]                 # return address 0x9000
    sim = Simulator(m, {'PC': IM2_SET, 'SP': 0x8000})
    for _ in range(100):
        if sim.registers[24] == 0x9000:
            break
        sim.opcodes[m[sim.registers[24]]]()
    return bytes(m[0xFFF4:0xFFF7])


def _plot_len(pt, R, mem, ns0):
    """Instructions from a plot entry to its return, no interrupt (pt: patched, None: original)."""
    get = bytes(mem).__getitem__
    sp0 = R[12]
    ret = mem[sp0] | mem[sp0 + 1] << 8
    if pt is None:
        ns = NextState({})
        o = _overlays(get, None, {}, ns)[0]()
    else:
        ns = _ns_for(pt, ns0)
        o = _overlays(get, _alt(pt), {a + k: v for a, old, new in pt.sites for k, v in enumerate(new)}, ns)[1]()
    sim = _machine(_rw(), o, list(R), ns, 'i')
    r, n = sim.registers, 0
    while not (r[24] == ret and r[12] == sp0 + 2) and n < 400000:
        sim.opcodes[o[r[24]]]()
        n += 1
    return n


def _inject(pt, R, mem, ns0, at, limit=3_000_000):
    """From a main-program plot entry (0xB950, interrupts on): run the plot (pt: patched, None: the
    original), deliver the frame interrupt after `at` instructions (None, or `at` past the plot's
    end: right after the plot returns) - at the first instruction boundary from there with interrupts enabled, as the Z80
    accepts it: push PC, IFF off, PC = 0xFFF4 (the game's IM 2 target) - and run until the plot has
    returned and the handler too. -> the screen bytes, or None if it did not finish."""
    get = bytes(mem).__getitem__
    sp0 = R[12]
    ret = mem[sp0] | mem[sp0 + 1] << 8
    if pt is None:
        ns = NextState({})
        O, _ = _overlays(get, None, {}, ns)
        o = O()
    else:
        ns = _ns_for(pt, ns0)
        _, P = _overlays(get, _alt(pt), {a + k: v for a, old, new in pt.sites for k, v in enumerate(new)}, ns)
        o = P()
    sim = _machine(_rw(), o, list(R), ns, 'i')
    r, ops = sim.registers, sim.opcodes
    n, done = 0, False
    while True:
        if not done and r[26] and ((at is not None and n >= at) or (r[24] == ret and r[12] == sp0 + 2)):
            sp = (r[12] - 2) & 0xFFFF
            o[sp], o[sp + 1] = r[24] & 255, r[24] >> 8
            r[12], r[24], r[26], done = sp, 0xFFF4, 0, True
            continue
        if done and r[24] == ret and r[12] == sp0 + 2 and n > 0:
            break
        ops[o[r[24]]]()
        n += 1
        if n > limit:
            return None
    return bytes(o[a] for a in range(0x4000, 0x5800))


def unit_tests(patch, states, negs=None):
    """Plot exit: every frame 0-255 (the 8-bit wrap included) x edge positions for the fireman, a
    few for the figures, inks, the pair rule, the object guard; colour map: entries, a wrong check
    byte; diamonds: k 0-4 x edge positions + the loop-counter guard; screen clears. negs: broken
    patches {name: (patch, case kind)} that must FAIL."""
    c = collections.Counter()
    by = collections.defaultdict(list)
    for s in states:
        by[s[0]].append(s)
    xs = (0, 1, 7, 8, 100, 232, 233, 239, 240)
    ys = (0, 61, 120, 168)

    def plot_ok(pt, R, mem, ns0, a, x, y, fr, e=7, d=0x40):
        fl, ns, m = _plot_case(pt, R, mem, ns0, a, x, y, fr, e, d, flags=0)
        exp = _model_objs(pt, m, {a} if fr else set()).layer()
        got = ns.layer(_own(a))
        if ns.bad:
            fl = fl + ns.bad
        return fl, got == exp

    def note(label, fl, same):
        ok = not fl and same
        c['%s %s' % (label, 'ok' if ok else 'FAIL!')] += 1
        if not ok and c['  ' + label + ' example'] < 2:
            c['  ' + label + ' example'] += 1
            c['  %s: %s same=%s' % (label, str(fl[:2])[:160], same)] += 1
        return ok

    for kind, pc, R, mem, ns0 in by['pl'][:1]:
        for fr in range(256):
            for x in xs:
                for y in ys:
                    fl, same = plot_ok(patch, R, mem, ns0, 0, x, y, fr)
                    note('fireman frame x position', fl, same)
        ens = by['en'][:1]
        for ek, epc, eR, emem, ens0 in ens:
            # entry then exit: during the plot the old image (own pair) and the new one (pending
            # pair) are both up; after the exit only the new one, on the own pair
            def ee(pt, a, x0, y0, f0, dx, dy, f, e=7, d=0x40):
                fl0, ns, m0 = _plot_case(pt, R, mem, ns0, a, x0, y0, f0, e, d, flags=0)   # old image up
                fl1, m1 = _entry_case(pt, eR, emem, ns, a, x0, y0, f0, dx, dy, f, e, d)
                md = _model_objs(pt, m0, {a} if f0 else set())
                md.pend[a] = obj_predicted(m1.__getitem__, a)
                ok1 = ns.layer(_own(a)) == md.layer()
                x1, y1 = (x0 + dx) & 255, (y0 + dy) & 255
                fl2, ns, m2 = _plot_case(pt, R, mem, ns0, a, x1, y1, f, e, d, ns=ns)
                ok2 = ns.layer(_own(a)) == _model_objs(pt, m2, {a} if f else set()).layer()
                return fl0 + fl1 + fl2 + ns.bad, ok1 and ok2
            for f in range(256):
                for x0, y0, dx, dy in ((100, 100, 2, 0), (0, 61, 0xFE, 1), (238, 168, 2, 0xFF),
                                       (8, 0, 0, 0)):
                    fl, ok = ee(patch, 0, x0, y0, 3, dx, dy, f)
                    note('entry + exit, fireman, every frame (moves incl. carries)', fl, ok)
            for a in (1, 2):
                for f0, f in ((0, 97), (97, 98), (98, 0), (11, 11), (40, 41)):
                    fl, ok = ee(patch, a, 120, 90, f0, 0xFF, 2, f, 0x43, 0)
                    note('entry + exit, figures (appear, wrapped frames, vanish, same image)', fl, ok)
            if negs:
                for name, (neg, k) in negs.items():
                    if k == 'en':
                        fl, ok = ee(neg, 2, 120, 90, 97, 1, 0, 98, 0x43, 0)
                        det = bool(fl) or not ok
                        c['negative control: %s %s' % (name, 'detected' if det else 'NOT DETECTED!')] += 1
        if not ens:
            c['entry + exit cases: no captured entry state FAIL!'] += 1
        for a in (1, 2):
            for fr in (0, 1, 40, 85, 86, 100, 255):
                for x, y in ((0, 0), (233, 168), (240, 61)):
                    for e, d in ((1, 0), (0x46, 0), (0, 0), (5, 0x40)):
                        fl, same = plot_ok(patch, R, mem, ns0, a, x, y, fr, e, d)
                        note('figure frame position ink', fl, same)
        # pair rule: object 2 shown at (100, 100, 20); object 1 plotted onto it / next to it
        for x1, fr1 in ((100, 20), (101, 20), (100, 21)):
            fl, ns, m = _plot_case(patch, R, mem, ns0, 1, x1, 100, fr1, 3, 0, flags=0x04,
                                   other={2: {0: 100, 1: 100, 2: 20, 6: 3, 7: 0}})
            exp = _model_objs(patch, m, {1, 2}).layer()
            # object 2's sprite shows the pattern from its capture: compare only object 1's sprites
            # and both visibility bits
            vis = [bool(ns.attr[i][3] & 0x80) for i in list(range(5, 9)) + list(range(13, 17))]
            pair = (x1, fr1) == (100, 20)
            want = [not pair] * 8
            got1 = ns.layer(range(13, 17))
            exp1 = {} if pair else _model_objs(patch, m, {1}).layer()
            note('pair rule', fl + ns.bad, vis == want and got1 == exp1)
        # cache: one Next state through a sequence (same image twice, the other buffer's image, an
        # ink change on the same frame, a new frame); each step checked against the model
        def seq(pt):
            ns = _ns_for(pt, ns0)
            ns.pages[FLAGS_PG][FLAGS_OFF] = 0
            ns.pages[FLAGS_PG][FLAGS_OFF + 1] = 0
            bad = 0
            for x, fr, e in ((100, 30, 7), (104, 30, 7), (108, 31, 7), (112, 30, 7), (116, 30, 2),
                             (120, 30, 2), (124, 31, 7), (128, 31, 2), (132, 31, 2)):
                m = bytearray(mem)
                o = OBJ
                m[o], m[o + 1], m[o + 2], m[o + 6], m[o + 7] = x, 100, fr, e, 0x40
                r = list(R)
                r[6], r[7] = (o + 2) >> 8, (o + 2) & 255
                fl, _, _ = event(pt, 'pl', 0xBC5C, m.__getitem__, r, ns, _alt(pt), _rw())
                exp = _model_objs(pt, m, {0}).layer()
                bad += bool(fl or ns.bad) or ns.layer(_own(0)) != exp
            return bad
        note('cache sequence (same, other buffer, ink change)', [] if not seq(patch) else ['layer'], True)
        if negs:
            for name, (neg, k) in negs.items():
                if k == 'cache':
                    det = seq(neg) > 0
                    c['negative control: %s %s' % (name, 'detected' if det else 'NOT DETECTED!')] += 1
        # guard: HL past the three objects -> no sprite change
        r = list(R)
        hl = OBJ + 8 * 3 + 2
        r[6], r[7] = hl >> 8, hl & 255
        ns = _ns_for(patch, ns0)
        before = [list(x_) for x_ in ns.attr]
        fl, _, _ = event(patch, 'pl', 0xBC5C, bytes(mem).__getitem__, r, ns, _alt(patch), _rw())
        note('object guard (HL past the table: no sprite change)', fl, ns.attr == before)
        # colour map: entries for one frame, one with a wrong check byte (ignored)
        base = mem[GBASE] | mem[GBASE + 1] << 8
        for fr in (3, 90):
            ga = gfx_addr(base, fr)
            cm = {}
            for i in range(48):
                a_ = (ga + i) & 0xFFFF
                cm['G%04X' % a_] = [mem[a_] ^ (0x55 if i == 5 else 0), 'G', [(i + k) % 15 + 1 for k in range(8)]]
            q = FiremanPatch(patch.prof, patch.rom_code, colours=cm, rom2=patch.rom2)
            q.prepare(bytes(mem).__getitem__)
            fl, ns, m = _plot_case(q, R, mem, ns0, 0, 100, 100, fr, flags=0)
            exp = _model_objs(q, m, {0}).layer()
            note('colour map (painted + wrong check byte)', fl + ns.bad, ns.layer(_own(0)) == exp)
            if negs is not None and fr == 3:
                q0 = FiremanPatch(patch.prof, patch.rom_code, colours={}, rom2=patch.rom2)
                q0.prepare(bytes(mem).__getitem__)
                fl, ns, m = _plot_case(q0, R, mem, ns0, 0, 100, 100, fr, flags=0)
                det = bool(fl) or ns.layer(_own(0)) != exp
                c['negative control: colour map left out %s' % ('detected' if det else 'NOT DETECTED!')] += 1
        if negs:
            for name, (neg, k) in negs.items():
                if k == 'pl':
                    det = False
                    for x in (0, 100, 240):
                        fl, ns, m = _plot_case(neg, R, mem, ns0, 0, x, 100, 40, flags=0)
                        exp = _model_objs(neg, m, {0}).layer()
                        det = det or bool(fl) or ns.layer(_own(0)) != exp
                    c['negative control: %s %s' % (name, 'detected' if det else 'NOT DETECTED!')] += 1
                elif k == 'pair':
                    fl, ns, m = _plot_case(neg, R, mem, ns0, 1, 100, 100, 20, 3, 0, flags=0x04,
                                           other={2: {0: 100, 1: 100, 2: 20, 6: 3, 7: 0}})
                    det = bool(fl) or any(ns.attr[i][3] & 0x80 for i in list(range(5, 9)) + list(range(13, 17)))
                    c['negative control: %s %s' % (name, 'detected' if det else 'NOT DETECTED!')] += 1
    # an interrupt inside a main-program plot (the handler plots the other figures): the patched
    # game must finish the plot exactly as if the interrupt came after it; the original corrupts
    ndet = collections.defaultdict(bool)
    for kind, pc, R, mem, ns0 in by['enm'][:2]:
        def pts(pt):                                  # 20 points over this plot's own length
            n = _plot_len(pt, R, mem, ns0)
            return [i * n // 20 for i in range(20)]
        ref = _inject(patch, R, mem, ns0, None)
        bad = [at for at in pts(patch) if _inject(patch, R, mem, ns0, at) != ref]
        note('interrupt inside a main-program plot (20 points): plot intact', [] if not bad else [('corrupt at', bad[:3])], True)
        oref = _inject(None, R, mem, ns0, None)
        obad = sum(_inject(None, R, mem, ns0, at) != oref for at in pts(None))
        c['  original game, same interrupts: %d of 20 plots corrupt' % obad] += 1
        for name, (neg, k) in (negs or {}).items():
            if k == 'nest':
                nref = _inject(neg, R, mem, ns0, None)
                ndet[name] |= any(_inject(neg, R, mem, ns0, at) != nref for at in pts(neg))
    for name, det in ndet.items():
        c['negative control: %s %s' % (name, 'detected' if det else 'NOT DETECTED!')] += 1
    if not by['enm']:
        c['interrupt inside a plot: no captured main-program plot entry FAIL!'] += 1
    # the game's IM 2 set-up (run again on a restart) must keep the deferral hook at 0xFFF4
    for kind, pc, R, mem, ns0 in by['pl'][:1]:
        want = b'\xC3' + patch.syms['e_isr'].to_bytes(2, 'little')
        got = _im2_setup(patch.sites, mem)
        note('IM 2 set-up (0xC234) writes JP e_isr to 0xFFF4', [] if got == want else [('0xFFF4', got.hex())], True)
        det = _im2_setup([t for t in patch.sites if t[0] != IM2_OP], mem) != want
        c['negative control: IM 2 set-up operand left out %s' % ('detected' if det else 'NOT DETECTED!')] += 1
    negd = collections.defaultdict(bool)
    for kind, pc, R, mem, ns0 in by['it'][:1]:
        sp = R[12]
        for cnt_ in (0, 1, 3, 5, 6):
            for b, col in ((6, 0), (100, 120), (191, 248), (70, 243)):
                for at in (0x47, 0x02, 0x40):
                    m = bytearray(mem)
                    m[sp + 5] = cnt_
                    m[0x5800 + (b >> 3) * 32 + (col >> 3)] = at
                    r = list(R)
                    r[2], r[3] = b, col
                    for pt, lab in [(patch, None)] + [(n_, nm) for nm, (n_, k_) in (negs or {}).items() if k_ == 'it']:
                        ns = _ns_for(pt, ns0)
                        before = [list(x_) for x_ in ns.attr]
                        fl, _, _ = event(pt, 'it', 0xECFF, m.__getitem__, r, ns, _alt(pt), _rw())
                        k = 5 - cnt_
                        if 0 <= k < 5:
                            md = Model(pt.cmap)
                            md.peek = m.__getitem__
                            md.items[k] = (col, b, item_ink(m.__getitem__, b, col))
                            same = ns.layer(range(k, k + 1)) == md.layer()
                            others = all(ns.attr[i] == before[i] for i in range(128) if i != k)
                        else:
                            same, others = True, ns.attr == before
                        if lab is None:
                            note('diamond k position ink' if 0 <= k < 5 else 'diamond guard (counter outside 1-5)',
                                 fl + ns.bad, same and others)
                        elif 0 <= k < 5:
                            negd[lab] |= bool(fl) or not (same and others)
        for nm, (n_, k_) in (negs or {}).items():
            if k_ == 'it':
                det = negd[nm]
                c['negative control: %s %s' % (nm, 'detected' if det else 'NOT DETECTED!')] += 1
    for kind, pc, R, mem, ns0 in by['c'][:3]:
        ns = _ns_for(patch, ns0)
        for i in range(29):
            ns.attr[i][3] |= 0x80
        ns.pages[FLAGS_PG][FLAGS_OFF] = 0x3F
        ns.pages[FLAGS_PG][FLAGS_OFF + 1] = 0x3F
        fl, _, _ = event(patch, 'c', pc, bytes(mem).__getitem__, list(R), ns, _alt(patch), _rw())
        ok = (not any(ns.attr[i][3] & 0x80 for i in range(29)) and ns.flags == 0
              and ns.pages[FLAGS_PG][FLAGS_OFF + 1] == 0)
        note('screen clear hides all (0x%04X)' % pc, fl + ns.bad, ok)
    return c


def _neg(patch, old, new, what, nth=None):
    """Copy of the patch with one hook byte sequence changed (exactly once in the two blocks, or
    its nth occurrence)."""
    o, n = bytes.fromhex(old), bytes.fromhex(new)
    blocks = [bytearray(patch.rom_code), bytearray(patch.rom2), bytearray(patch.p30)]
    hits = [(b, i) for b, blk in enumerate(blocks) for i in range(len(blk)) if blk[i:i + len(o)] == o]
    if nth is None and len(hits) != 1:
        raise ValueError('negative control %s: pattern %s found %d times' % (what, old, len(hits)))
    b, i = hits[nth or 0]
    blocks[b][i:i + len(o)] = n
    q = FiremanPatch(patch.prof, bytes(blocks[0]), colours=patch.cmap, rom2=bytes(blocks[1]), p30=bytes(blocks[2]))
    if getattr(patch, 'peek', None):
        q.prepare(patch.peek)
    return q


def negative_patches(patch):
    return {'sprite X one pixel off': (_neg(patch, '3a02dfc61f', '3a02dfc620', 'X', nth=0), 'pl'),
            'pair rule left out': (_neg(patch, 'e6f9', 'e6ff', 'pair'), 'pair'),
            'diamond one line low': (_neg(patch, 'c61aed9236', 'c61bed9236', 'item Y'), 'it'),
            'cache ignores the ink': (_neg(patch, '2c7eb928', '2c7ebf28', 'cache', nth=0), 'cache'),
            'pending sprites not shown at the plot entry': (_neg(patch, 'f1f6c04f', 'f1f6404f', 'pending'), 'en'),
            'mask left out (left pixel of a pair)': (_neg(patch, 'e6023e08', 'e6023e00', 'mask', nth=0), 'pl'),
            'interrupt not deferred during a plot': (_neg(patch, 'ed91561e3a30deb720', 'ed91561e3a30deb738', 'defer'), 'nest')}


# ---------------------------------------------------------------------------------------------
# Recolour (PLAYBOOK 3b): the colour map lives in banks 13-15, read only by the hooks
# ---------------------------------------------------------------------------------------------

RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/%s_colours.json' % RECORD,
            'clear': False, 'note': NOTE}


def recolour(nex, cmap):
    """Built <record>_sprites.nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is
    not this engine's build of the expected snapshot (signature, patch sites, hook code, set-up)."""
    from .recolour import nex_offsets, splice
    d = bytes(nex)
    off = nex_offsets(d)
    need = {5, 2, 0, 10, 12} | set(CMAP_BANKS) | set(range(16, 32))
    if not need <= set(off):
        raise ValueError('not an Incredible Shrinking Fireman sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: d[off[b]:off[b] + 16384]
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000]
    prof = load_profile()
    sg = prof['signature']
    p0 = FiremanPatch(prof, colours={})
    sig = bytearray.fromhex(sg['bytes'])
    for a, old, new in p0.sites:                # a patch site inside the signature holds its hook
        for k, v in enumerate(new):
            if 0 <= a + k - sg['addr'] < len(sig):
                sig[a + k - sg['addr']] = v
    if bytes(peek(sg['addr'] + k) for k in range(len(sig))) != bytes(sig):
        raise ValueError('not The Incredible Shrinking Fireman (signature)')
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook bytes' % a)
    if bank(12)[:8192] != p0.page:
        raise ValueError('hook code differs from this version\'s (rebuild with nexclash.py auto)')
    if bank(10)[0x1000:0x1000 + len(p0.stub_extra)] != p0.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    if bank(15)[P30_OFF:P30_OFF + len(p0.p30)] != p0.p30:
        raise ValueError('page-30 hook code differs from this version\'s (rebuild with nexclash.py auto)')
    new, changed = splice(d, cmap_banks(cmap, peek))
    return new, {'banks changed': changed, 'entries': len(cmap)}


# ---------------------------------------------------------------------------------------------
# auto: plain + sprite build, verify, unit tests
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : incredible_shrinking_fireman_add_opus (fireman, room figures, diamonds -> sprites; '
        'overlay, plotter-exit hooks)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, keep_printer_buffer=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X; printer buffer put back: the game reads 0x5B41)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = FiremanPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Sprites   : %s  %s  boot %s  (colour map: %d entries)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200],
        len(patch.cmap)))
    ok = not bad and not bad2
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):           # selftest rebuild: build only
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
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
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3,
                           progress=lambda f, c_: say('            ... frame %d, plots %d' % (f, c_['pl']))
                           if f % 5000 == 0 else None)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, plot entries %d, plots %d, interrupts %d (%d deferred to a plot exit), '
            'diamonds %d, clears %d, %d sprite pixels, '
            '%d transient pixels covered, %d plot screen bytes, %d diamond bytes, %d attribute reads, %d '
            'interrupt-safety points -> %s' % (
                os.path.basename(r), c['frames'], c['en'], c['pl'], c['isr'] + c['isr deferred'], c['isr deferred'],
                c['it'], c['c'], c['sprite pixels compared'],
                c['transient pixels covered'],
                c['plot screen bytes compared'], c['diamond screen bytes compared'],
                c['attribute reads checked'], c['interrupt-safety points'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
        say('Speed     : hook cost per game frame (69888 T): mean %d T, 99%% of frames with hooks <= %d T, '
            'max %d T (28 MHz parts as T / 6, LEARNINGS 2.1f)' % (
                c['speed: hook T per game frame, mean'],
                c['speed: hook T per game frame, 99th percentile of frames with hooks'],
                c['speed: hook T per game frame, max']))
        for k, v in c.items():
            if k.startswith('  writes under') or 'pair-hidden' in k:
                say('          %s: %d' % (k.strip(), v))
    if states:
        u = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items())
                                                if not k.startswith('  ')), 'PASS' if not uf else 'FAIL'))
        for k, v in u.items():
            if k.startswith('  '):
                say('          %s' % k.strip())
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.incredible_shrinking_fireman_add_opus')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', help='also show the frames the recordings never drew (from the code)')
    p.add_argument('-o', '--out', default=RECORD)
    p = sub.add_parser('colours', help='painted PAINTING sheet -> colours json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--out', default=COLOURS)
    a = ap.parse_args(argv)
    from . import coloursheet as cs
    if a.cmd == 'sheet':
        seen, errs = capture(a.rzx)
        for path, n, err in errs:
            print('%s: %d frames%s' % (path, n, ', DESYNC: ' + err if err else ''))
        chosen, every = composites(seen, _peek(a.z80) if a.z80 else None)
        for png, n in sheets({'_PAINTING_SPRITES': chosen, '_REFERENCE_ALL_SPRITES': every}, a.out,
                             load_colours()):
            print('%s: %d figures' % (png, n))
        g = collections.Counter(k[0] for k in seen)
        print('graphics drawn per group:', dict(g))
        for k, e in seen.items():
            if len(e['inks']) > 1:
                print('  %s frame %d drawn in inks %s' % (k[0], k[2], dict(e['inks'])))
    elif a.cmd == 'colours':
        lay = a.layout or a.png.replace('_painted.png', '.png').replace('.png', '_layout.json')
        ent, rep = cs.read(a.png, lay)
        cs.save(ent, a.out, NOTE)
        for k, v in rep.items():
            print('%-70s %d' % (k, v))
        print('->', a.out)


if __name__ == '__main__':
    main()
