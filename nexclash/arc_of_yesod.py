"""The Arc of Yesod (Thor / Odin, 1985, 128K release) engine 'arc_of_yesod'. Additive module: reachable only through is_arc_of_yesod(). Facts, design, results: games/arc_of_yesod.md.

A port of nexclash/nodes_of_yesod.py: the same game engine at other addresses. The game XORs each figure into a back buffer at 0xE400 and copies the changed rectangle to the screen (0xD4B3); it then paints the ink of the empty cells the figure covers (0xD580).
Everything in the buffer stays as it was; only the copy and the paint stop writing, so the only memory that differs from the original is the screen.
Every figure change passes one place, 0xD4AF, with IX at the object: the hook sets that object's sprites from its record (fixed colour from the graphic's own header).
Patterns are built here from the two pointer tables (0x7E1C, 0x8D55), so a figure the recordings never reach has its patterns too.
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE, ALT_BANK = 24, 12
PAT_PAGE0 = 26
TAIL_ADDR = 0x5BBC                  # 0x5BBC-0x5C18: variables the game writes before it reads, from the control menu on (scan, games/arc_of_yesod.md)
MAX_TAIL = 90
PRINTER_KEEP = TAIL_ADDR - 0x5B00   # the setup stub puts back the printer buffer NEXLOAD used, up to the tail
STATE_LO, STATE_HI = 0xFBA0, 0xFBE3  # bank 0, the cell map's rows 21-23 (never used): the object state
STATE2_LO, STATE2_HI = 0x5B00, 0x5B23        # the printer buffer's first bytes (never touched): R, speed and pace state
V_WT0, V_PD, V_IRQ_SERIAL = 0x5B19, 0x5B1D, 0x5B10
HELD, SHOWN, V_DROP = 0xFBA0 - STATE_LO, 0xFBC0 - STATE_LO, 0xFBD0 - STATE_LO
T_INDEX, T_FRAME = 0x0200, 0x1600
AUX2 = 0x1B00                       # e_random2, between the frame table and the pace helpers
ROM_KEEP = 0x1F50
G_LOW, G_SPAN = 0x7E00, 0x2800
TABLES = ((0x7E1C, 41), (0x8D55, 98))    # the astronaut's graphics, then the rest
DYNAMIC = (0x8C92, 0x8CF5)          # the appear / vanish effect rewrites these two as it shows them (0xC185, 0xC1A0): their tiles are made from the bytes as they are
BLIT, ROOM, NEW1, NEW2, OVER, TELE = 0xD4AF, 0xAAF1, 0xA985, 0xAA3F, 0xDA50, 0xC112
ATTR_ENTER, ATTR_ROW, ATTR, PLAYER, IRQ_IN, IRQ_OUT, RANDOM, RANDOM2, BEAM = 0xD55A, 0xD589, 0xD580, 0xBAF8, 0xDDB3, 0xDDEE, 0xC355, 0xC1CC, 0xCF07
BEAM_STORE = 0xCF12                 # the beam colours a cell whose ink is black: a screen write the build keeps
BEAM_DRAW, BEAM_WIPE = 0xCF00, 0xCEC3   # LD (HL),A / LD (HL),0: the beam's own pixels, written to the screen (not the buffer) in the original and the build
SHADOW_PAGE = 23                    # the ink the original would have painted, per play-area cell: read by the random reads and the beam
OBJ0, NOBJ = 0xFC00, 16
SITES_ORIG = {ATTR_ENTER: ('dd7e05', 'e_attr_enter'), ATTR_ROW: ('15c262d5', 'e_attr_row'), PLAYER: ('dd21e0fd', 'e_player'), IRQ_IN: ('f5c5d5', 'e_irq_in'), IRQ_OUT: ('e1d1c1', 'e_irq_out'),
              RANDOM: ('7ee60f', 'e_random'), RANDOM2: ('6f677e', 'e_random2'), BEAM: ('7ee607', 'e_beam'), ATTR: ('77', 'e_attr'), BLIT: ('060008', 'e_blit'), ROOM: ('21bd5b', 'e_room'), NEW1: ('210040', 'e_new1'),
              NEW2: ('210040', 'e_new2'), OVER: ('210040', 'e_over'), TELE: ('210058', 'e_tele')}
STORES = {ATTR: (b'\x77', b'\x00')}
EXIT = {ATTR_ENTER: 0xD55D, ATTR_ROW: 0xD58D, PLAYER: 0xBAFC, IRQ_IN: 0xDDB6, IRQ_OUT: 0xDDF1, RANDOM: 0xC358, RANDOM2: 0xC1CF, BEAM: 0xCF0A, ATTR: 0xD581, BLIT: 0xD552, ROOM: 0xAAF4, NEW1: 0xA988, NEW2: 0xAA42,
        OVER: 0xDA53, TELE: 0xC115}
KIND = {ATTR_ENTER: 'attribute_enter', ATTR_ROW: 'attribute_row', PLAYER: 'player', IRQ_IN: 'irq_in', IRQ_OUT: 'irq_out', RANDOM: 'random', RANDOM2: 'random2', BEAM: 'beam', ATTR: 'attribute', BLIT: 'blit',
        ROOM: 'room', NEW1: 'new1', NEW2: 'new2', OVER: 'over', TELE: 'tele'}
ATTR_AGAIN = 0xD562                  # the paint's row loop: e_attr_row's other exit
# bytes inside a patched site that are not the start of one of its original instructions (those run in the original replay)
INTERIORS = tuple(a + k for a, (old, _) in SITES_ORIG.items() for k in range(1, len(bytes.fromhex(old)))
                  if a + k not in (BLIT + 2, BEAM + 1, RANDOM + 1, RANDOM2 + 1, RANDOM2 + 2, IRQ_IN + 1, IRQ_IN + 2, IRQ_OUT + 1, IRQ_OUT + 2, ATTR_ROW + 1))
LDIR, LDIR_END = 0xD4B3, 0xD4B5
RNDREAD, RNDNEXT = 0xC355, 0xC356    # LD A,(HL) at a random address (H = L = R): can land on the screen; 0xC1CE is the other one
PLAY_LINES = 168
INK, FILL, OUTLINE, WHITE = 1, 2, 3, 4
NORMAL = [0x00, 0x02, 0xC0, 0xC2, 0x18, 0x1A, 0xD8, 0xDA]
BRIGHT = [0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
SPARE = [0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0x18, 0x1A, 0xD8, 0x02, 0xC0]        # entries 5-15: colours for a painted sheet, each default ink among them
MIN_OUTLINE = 24
MIN_DENSE = 0.22                    # ink pixels / box below this: a cloud of dots, not a body: no fill, no outline
FULL = (1 << 256) - 1

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'arc_of_yesod_colours.json')

def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'arc_of_yesod.json'), os.path.join(_HERE, 'arc_of_yesod.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('arc_of_yesod.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_arc_of_yesod(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '128K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bool(sig) and bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from .recolour import build_colours_path
    from . import coloursheet as cs
    return cs.load(path or build_colours_path(COLOURS))


# ---------------------------------------------------------------------------------------------
# Graphics
# ---------------------------------------------------------------------------------------------

def view_from_snapshot(path):
    """64K with banks 5, 2, 0 (the game's map in play): graphics come from here, and match the play state byte for byte."""
    from .z80tonex import Z80Snapshot
    s = Z80Snapshot(path)
    return bytes(16384) + bytes(s.banks[5]) + bytes(s.banks[2]) + bytes(s.banks[0])


def catalog(mem):
    """Every usable graphic the two pointer tables name -> {address of the rows: (w, h, colour, bytes wide)}."""
    out = {}
    for base, count in TABLES:
        for i in range(count):
            p = mem[base + 2 * i] | mem[base + 2 * i + 1] << 8
            if p < G_LOW or p >= G_LOW + G_SPAN - 3:
                continue
            w, h, c = mem[p], mem[p + 1], mem[p + 2]
            if not (1 <= w <= 32 and 1 <= h <= 32) or not c & 7:
                continue
            bw = (w - 1) // 8 + 1
            out[p + 3] = (w, h, c, bw)
    return out


def shape(bw, h):
    return (bw * 8 + 2 + 15) // 16, (h + 2 + 15) // 16


def line_of_colour(c):
    return (c & 7) | (8 if c & 0x40 else 0)


def palette():
    out = bytearray(256)
    for line in range(16):
        ink = (BRIGHT if line & 8 else NORMAL)[line & 7]
        e = [0, ink, 0, 0x00 if line & 7 == 7 else 0xFF, 0xFF] + SPARE
        out[line * 16:line * 16 + 16] = bytes(e)
    return bytes(out)


def bits_of(mem, g, bw, h):
    return [int.from_bytes(bytes(mem[g + y * bw:g + (y + 1) * bw]), 'big') for y in range(h)]


def key_for(g, y, bx):
    return '%04X:%d' % (g + y * ((bx >> 8) or 1), bx & 255)


def patterns(mem, g, info, cmap=None, outline=False):
    """cols * rows patterns of 128 bytes. The graphic sits one pixel in from the left and the top, so the outline never covers it. Nibble 1 ink,
    2 black fill inside the silhouette, 3 outline. Clear pixels: 0. The map overrides per (graphic byte, bit)."""
    w, h, c, bw = info
    cols, rows = shape(bw, h)
    H, W = rows * 16, cols * 16
    can = [[0] * W for _ in range(H)]
    rows_bits = bits_of(mem, g, bw, h)
    n = 0
    for y, v in enumerate(rows_bits):
        for x in range(bw * 8):
            if v >> (bw * 8 - 1 - x) & 1:
                can[y + 1][x + 1] = INK
                n += 1
    box = bw * 8 * h
    body = n >= MIN_OUTLINE and n / box >= MIN_DENSE
    if body:
        fills = []
        for y in range(H):
            row = can[y]
            xs = [x for x in range(W) if row[x]]
            if not xs:
                continue
            for x in range(xs[0] + 1, xs[-1]):
                if row[x]:
                    continue
                if any(can[yy][x] for yy in range(y)) and any(can[yy][x] for yy in range(y + 1, H)):
                    fills.append((y, x))
        for y, x in fills:
            can[y][x] = FILL
        edge = []
        for y in range(H):
            for x in range(W):
                if can[y][x]:
                    continue
                if any(0 <= y + dy < H and 0 <= x + dx < W and can[y + dy][x + dx] for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0))):
                    edge.append((y, x))
        if outline:
            for y, x in edge:
                can[y][x] = OUTLINE
    if cmap:
        for y in range(h):
            for bx in range(bw):
                e = cmap.get('%04X' % (g + y * bw + bx))
                if not e or (e[0] is not None and e[0] != mem[g + y * bw + bx]):   # stored maps: null check
                    continue
                for k in range(8):
                    if e[2][k]:
                        can[y + 1][bx * 8 + k + 1] = e[2][k]
                    elif len(e) > 3 and e[3] & (0x80 >> k):
                        can[y + 1][bx * 8 + k + 1] = 0
    out = bytearray()
    for ry in range(rows):
        for cx in range(cols):
            for y in range(16):
                row = can[ry * 16 + y][cx * 16:cx * 16 + 16]
                for k in range(0, 16, 2):
                    out.append(row[k] << 4 | row[k + 1])
    return bytes(out)


def live_patterns(mem, g, info):
    """A DYNAMIC graphic's tiles as the hook makes them from its bytes: ink only, the graphic one pixel in."""
    w, h, c, bw = info
    cols, rows = shape(bw, h)
    can = [[0] * (cols * 16) for _ in range(rows * 16)]
    for y, v in enumerate(bits_of(mem, g, bw, h)):
        for x in range(bw * 8):
            if v >> (bw * 8 - 1 - x) & 1:
                can[y + 1][x + 1] = INK
    out = bytearray()
    for ry in range(rows):
        for cx in range(cols):
            for y in range(16):
                row = can[ry * 16 + y][cx * 16:cx * 16 + 16]
                for k in range(0, 16, 2):
                    out.append(row[k] << 4 | row[k + 1])
    return bytes(out)


def build_tables(mem, cmap=None, outline=False):
    """-> (the alt ROM's low 8K: the ROM with the tables at 0x0200-0x1FFF, {page: 8K}, {graphic: frame number}). The layout does not depend on the map. Every page has 0xF3 at offset 0 (the handler's JR offset) and tiles from 128."""
    from .build import rom48
    state = bytearray(rom48()[:0x2000])
    state[T_INDEX:ROM_KEEP] = bytes(ROM_KEEP - T_INDEX)      # the game calls 0x1F54 (BREAK-KEY) and 0x22B0: both stay
    pages = {}
    page, idx = PAT_PAGE0, 0
    nums = {}
    cat = catalog(mem)
    for num, g in enumerate(sorted(cat), 1):
        info = cat[g]
        w, h, c, bw = info
        cols, rows = shape(bw, h)
        n = cols * rows
        if n > 6:
            raise ValueError('graphic %04X needs %d tiles' % (g, n))
        if idx + n > 63:
            page, idx = page + 1, 0
        if g in DYNAMIC and (bw, cols, rows) != (3, 2, 3):
            raise ValueError('the hook makes live tiles for a graphic 3 bytes wide, 2 x 3 tiles only')
        d = live_patterns(mem, g, info) if g in DYNAMIC else patterns(mem, g, info, cmap, outline)
        pg = pages.setdefault(page, bytearray(8192))
        pg[0] = 0xF3
        pg[128 + idx * 128:128 + (idx + n) * 128] = d
        state[T_INDEX + ((g - G_LOW) >> 1)] = num
        if T_FRAME + num * 8 + 8 > AUX2:
            raise ValueError('too many graphics for the frame table: %d' % num)
        state[T_FRAME + num * 8:T_FRAME + num * 8 + 7] = bytes([page, idx, cols, rows, line_of_colour(c), bw, int(g in DYNAMIC)])
        nums[g] = num
        idx += n
    # RST 0x30 replaces the one-byte attribute store. The original branch to
    # INC L at 0xD581 stays intact; no jump spans that second entry point.
    attr = int(load_profile()['hooks']['syms']['e_attr'], 16)
    state[0x30:0x33] = bytes([0xC3, attr & 255, attr >> 8])
    helpers = bytes.fromhex(load_profile()['hooks'].get('helpers', ''))
    state[0x1E80:0x1E80 + len(helpers)] = helpers
    aux = bytes.fromhex(load_profile()['hooks'].get('aux', ''))
    state[0x1C50:0x1C50 + len(aux)] = aux
    aux2 = bytes.fromhex(load_profile()['hooks'].get('aux2', ''))
    state[AUX2:AUX2 + len(aux2)] = aux2
    for i in range(64):
        state[0x1E00 + i] = original_random_rom()[i * 257]
    for i in range(0x40, 0x58):
        a = i * 257
        y = ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)
        ptr = 0xE400 + y * 32 + (a & 31)
        at = 0x1E40 + 2 * (i - 0x40)
        state[at:at + 2] = ptr.to_bytes(2, 'little')
    return bytes(state), {k: bytes(v) for k, v in pages.items()}, nums


# ---------------------------------------------------------------------------------------------
# Builds
# ---------------------------------------------------------------------------------------------

class PlainPatch:
    """The plain .nex: no hooks."""
    name = 'The Arc of Yesod plain conversion'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    extra_banks = {}
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def apply(self, snap):
        snap.port1ffd = 4       # with 7FFD bit 4 set, as in the file, the ROM is the 48K ROM


_RANDOM_ROM = None


def original_random_rom():
    # This 128K release takes random bytes from ROM 1, including the keypad
    # extension at 0x386E. The Next's 48K ROM has different bytes there.
    global _RANDOM_ROM
    if _RANDOM_ROM is None:
        from skoolkit import ROM128, read_bin_file
        _RANDOM_ROM = bytes(read_bin_file(ROM128[1], 16384))
    return _RANDOM_ROM




class ArcPatch:
    name = 'The Arc of Yesod 128K: figures -> hardware sprites (altrom hooks, interrupts on, tables in Next pages at slot 0)'

    def __init__(self, z80=None, prof=None, rom_code=None, colours=None, stores=None, outline=False, mem=None, pal=None):
        self.prof = prof or load_profile()
        self.outline = outline
        self.colours = {} if colours is None else colours
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        setup = bytearray(bytes.fromhex(h['setup']))
        off = self.syms['pal'] - 0xD000
        self.palette = bytes(pal) if pal is not None else palette()
        if len(self.palette) != 256:
            raise ValueError('sprite palette must have 256 RGB332 entries')
        setup[off:off + 256] = self.palette
        self.stub_extra = bytes(setup)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = MAX_TAIL
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long: %d' % len(self.rom_code))
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.sites = []
        for a, (old, sym) in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old), b'\xF7' if a == ATTR else bytes([0xC3]) + self.syms[sym].to_bytes(2, 'little')))
        self.stores = STORES if stores is None else stores
        for a, (old, new) in self.stores.items():
            if a == ATTR:
                continue
            self.sites.append((a, old, new))
        self.extra_banks = {}
        self.low = None
        self.altrom_low = (ALT_PAGE + 1, bytes(0x2000))    # (the page number decides the stub: the bytes come in apply)
        self.pages = None
        self.nums = None
        self.mem = mem
        if z80 is not None and mem is None:
            self.mem = view_from_snapshot(z80)

    def tables(self):
        self.low, self.pages, self.nums = build_tables(self.mem, self.colours, self.outline)
        self.altrom_low = (ALT_PAGE + 1, self.low)
        # Recover original ink from source bits only when the uploaded tile exactly
        # matches approved art. Mutant runtime pages never define this oracle.
        self.paint_masks = {}
        self.approved_patterns = {}
        for g, info in catalog(self.mem).items():
            w, h, colour, bw = info
            cols, rows = shape(bw, h)
            if g in DYNAMIC:
                continue                # checked against the live bytes at each update
            art = patterns(self.mem, g, info, self.colours, self.outline)
            self.approved_patterns[g] = art
            for tile in range(cols * rows):
                mask = []
                for y in range(16):
                    sy = tile // cols * 16 + y - 1
                    row = 0
                    for x in range(16):
                        sx = tile % cols * 16 + x - 1
                        if 0 <= sy < h and 0 <= sx < bw * 8 and self.mem[g + sy * bw + sx // 8] & (128 >> (sx & 7)):
                            row |= 0x8000 >> x
                    mask.append(row)
                key = art[tile * 128:(tile + 1) * 128]
                if key in self.paint_masks and self.paint_masks[key] != mask:
                    raise ValueError('painted tile has ambiguous original ink')
                self.paint_masks[key] = mask

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128:
            raise ValueError('The Arc of Yesod patch expects the 128K release')
        if self.mem is None:
            self.mem = bytes(16384) + bytes(snap.banks[5]) + bytes(snap.banks[2]) + bytes(snap.banks[0])
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])       # 0x4000-0xFFFF as the game code sees it
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        # The hooks' state: the game never touches these bytes (scans in games/arc_of_yesod.md), so they start at zero.
        for lo, hi in ((STATE_LO, STATE_HI), (STATE2_LO, STATE2_HI)):
            ram[lo - 0x4000:hi - 0x4000] = bytes(hi - lo)
        setup = bytearray(self.stub_extra)
        off = self.syms['printer_saved'] - 0xD000
        setup[off:off + PRINTER_KEEP] = ram[0x1B00:0x1B00 + PRINTER_KEEP]
        self.stub_extra = bytes(setup)
        self.tables()
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        snap.port1ffd = 4
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        pg = bytearray(self.page)
        pg[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self.page = bytes(pg)
        self.altrom_low = (ALT_PAGE + 1, self.low)
        self.extra_banks = {ALT_BANK: self.page + self.low, SHADOW_PAGE // 2: bytes(16384)}
        for p, data in self.pages.items():
            bank = p // 2
            cur = self.extra_banks.get(bank, bytes(16384))
            o = (p & 1) * 8192
            self.extra_banks[bank] = cur[:o] + data + cur[o + 8192:]


STATE_LEN = (STATE_HI - STATE_LO) + (STATE2_HI - STATE2_LO)
V_ATTR_SPEED = 0x5B16
STACK_LO, STACK_HI = STATE2_HI, 0x5BB4       # the game's stack sits in the printer buffer, above the hooks' second state range
ROOMV = 23479
PEND = {0xAB6E, 0xAB9F}             # the room's colours and picture go to the screen: the next copy sees bare scenery
RND2NEXT = 0xC1CF
STARS = 45391


def _si(a):
    """Index into NextState.state of a hook state address, None for any other."""
    if STATE_LO <= a < STATE_HI:
        return a - STATE_LO
    if STATE2_LO <= a < STATE2_HI:
        return STATE_HI - STATE_LO + a - STATE2_LO
    return None


# ---------------------------------------------------------------------------------------------
# Next-side state
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, patch):
        self.patch = patch
        self.nr = {0x50: 0xFF, 0x54: 4, 0x07: 0, 0x34: 0, 0x19: 0, 0x1C: 0}
        self.shadow = bytearray(8192)   # SHADOW_PAGE, as the hooks see it at slot 4
        self.sel = 0
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patptr = 0
        self.state = bytearray(STATE_LEN)
        self.l2_port = 0
        self.cache = {}
        self.ports = 0
        self.clip = [0, 255, 0, 167]
        self.clipi = 0
        self.scaled = False     # v1.6: the line clock counts T at the CPU's speed (slower: only the pace checks use it)
        self.wall = 0.0

    def copy(self):
        q = NextState.__new__(NextState)
        q.__dict__.update(self.__dict__)
        q.nr = dict(self.nr)
        q.attr = [list(a) for a in self.attr]
        q.pat = bytearray(self.pat)
        q.shadow = bytearray(self.shadow)
        q.state = bytearray(self.state).ljust(STATE_LEN, b'\0')
        q.cache = {}
        q.clip = list(self.clip)
        return q

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr[0x34] & 0x7F][reg - 0x35] = val
        elif reg == 0x1C and val & 2:
            self.clipi = 0
        elif reg == 0x19:
            self.clip[self.clipi & 3] = val
            self.clipi += 1

    def out(self, port, val):
        p = port & 0xFF
        if port == 0x243B:
            self.sel = val
        elif port == 0x253B:
            self.nextreg(self.sel, val)
        elif port == 0x303B:
            self.patptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port == 0x123B:
            self.l2_port = val
        elif p == 0x5B:
            self.pat[self.patptr & 0x3FFF] = val
            self.patptr += 1
            if self.cache:
                self.cache.clear()
        else:
            self.ports += 1

    def page_byte(self, page, off):
        d = self.patch.pages.get(page)
        return d[off] if d else 0

    def tile(self, base, mirror):
        k = (base, mirror)
        t = self.cache.get(k)
        if t is None:
            known = getattr(self.patch, 'paint_masks', {}).get(bytes(self.pat[base:base + 128]))
            if known is not None:
                t = [int(f'{v:016b}'[::-1], 2) for v in known] if mirror else list(known)
                self.cache[k] = t
                return t
            t = []
            for j in range(16):
                o = 0
                for x in range(16):
                    b = self.pat[base + j * 8 + x // 2]
                    n = (b >> 4) if x % 2 == 0 else (b & 15)
                    if n and n not in (FILL, OUTLINE):
                        o |= (1 << x) if mirror else (0x8000 >> x)
                t.append(o)
            self.cache[k] = t
        return t

    def visible(self):
        return [s for s in range(128) if self.attr[s][3] & 0x80]

    def compose(self, lines=None):
        """XOR of every sprite's figure pixels (outline and fill are not figure), through the clip window. lines: ints, bit 255 = left."""
        if lines is None:
            lines = [0] * 192
        top, bot = self.clip[2], self.clip[3]
        for s in self.visible():
            a = self.attr[s]
            x = a[0] + (a[2] & 1) * 256
            y = a[1] + (a[4] & 1) * 256
            if x >= 400:
                x -= 512
            if y >= 400:
                y -= 512
            x -= 32
            y -= 32
            base = (a[3] & 0x3F) * 256 + (128 if a[4] & 0x40 else 0)
            for j, o in enumerate(self.tile(base, bool(a[2] & 8))):
                yy = y + j
                if not o or not top <= yy <= bot or yy >= 192:
                    continue
                sh = 240 - x
                om = (o << sh) if sh >= 0 else (o >> -sh)
                lines[yy] ^= om & FULL
        return lines

    def line_of_sprite(self, s):
        return self.attr[s][2] >> 4


class View:
    """The rzxplay simulator's paged memory, with slices."""

    def __init__(self, m):
        self.m = m
        self.slots = m.memory

    def __getitem__(self, a):
        if isinstance(a, slice):
            out = bytearray()
            p, stop = a.start, a.stop
            while p < stop:
                n = min(stop, (p | 0x3FFF) + 1)
                out += bytes(self.slots[p >> 14][p & 0x3FFF:(p & 0x3FFF) + n - p])
                p = n
            return bytes(out)
        return self.slots[a >> 14][a & 0x3FFF]

    def __setitem__(self, a, v):
        self.m[a] = v


def scr_addr(y):
    return 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)


# ---------------------------------------------------------------------------------------------
# One hook event
# ---------------------------------------------------------------------------------------------

CMP = list(range(0, 13)) + [14, 15] + list(range(16, 25)) + [26, 27]   # all but T, MEMPTR
_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _alt(patch):
    return bytearray(patch.low) + bytearray(patch.page)


class _O:
    def __init__(s, get):
        s.get, s.ov = get, {}

    def __getitem__(s, a):
        v = s.ov.get(a)
        return s.get(a) if v is None else v

    def __setitem__(s, a, v):
        if a >= 0x4000:
            s.ov[a] = v

    def __len__(s):
        return 65536


class _P(_O):
    """The patched build: sites, alt ROM, Next pages at slot 0."""

    def __init__(s, get, alt, psite, ns):
        _O.__init__(s, get)
        s.alt, s.psite, s.ns, s.romw, s.pagew, s.scrw = alt, psite, ns, 0, 0, 0

    def __getitem__(s, a):
        if a < 0x2000:
            p = s.ns.nr[0x50]
            return s.alt[a] if p == 0xFF else s.ns.page_byte(p, a)
        if a < 0x4000:
            return s.alt[a]
        i = _si(a)
        if i is not None:
            return s.ns.state[i]
        if 0x8000 <= a < 0xA000 and s.ns.nr[0x54] == SHADOW_PAGE:
            return s.ns.shadow[a - 0x8000]
        v = s.psite.get(a)
        if v is not None:
            return v
        v = s.ov.get(a)
        return s.get(a) if v is None else v

    def __setitem__(s, a, v):
        if a < 0x2000:
            if s.ns.nr[0x50] == 0xFF:
                s.romw += 1
            else:
                s.pagew += 1
            return
        if a < 0x4000:
            s.romw += 1
            return
        i = _si(a)
        if i is not None:
            s.ns.state[i] = v
            return
        if 0x8000 <= a < 0xA000 and s.ns.nr[0x54] == SHADOW_PAGE:
            s.ns.shadow[a - 0x8000] = v
            return
        if a < 0x5B00:
            s.scrw += 1
        s.ov[a] = v


def _machine(Sim, mem, regs, ns, slot):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot)
    sim.int_active = 0  # isolated event: IRQ delivery is exercised explicitly in injection tests

    class Tr:
        def read_port(self, regs_, port):
            if port == 0x253B:
                if ns.sel in (0x1E, 0x1F):
                    line = (int(ns.wall) // 224 if ns.scaled else sim.registers[25] // 224) % 312
                    return (line >> 8) if ns.sel == 0x1E else (line & 255)
                return ns.nr.get(ns.sel, 0)
            return 0xFF

        def write_port(self, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    z80n.install(sim, ns.nextreg)
    return sim


def _run(sim, stop, limit=2000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[24] != stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


def _run_scaled(sim, stop, ns, limit=2000000):
    """As _run, the line clock counting each instruction's T at the speed it ran at."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[24] != stop:
        t, sh = R[25], ns.nr[0x07] & 3
        ops[mem[R[24]]]()
        ns.wall += (R[25] - t) / (1 << sh)
        n += 1
        if n > limit:
            return False
    return True


def _run_safe(sim, stop, ns, fails, limit=2000000):
    """As _run, and after each instruction: what the interrupt handler needs if it came now."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    ix, iy, i, iff, sp0 = R[8], R[9], R[14], R[26], R[12]
    ix2, iy2 = R[10], R[11]
    n = 0
    while R[24] != stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
        if R[24] == stop:
            break
        player_ix_restore = stop == EXIT[PLAYER] and R[24] == ns.patch.syms['e_blit'] - 3 and (R[8], R[9]) == (0xFD, 0xE0)
        if R[26] != iff or (not player_ix_restore and (R[8], R[9], R[10], R[11], R[14]) != (ix, iy, ix2, iy2, i)):
            fails.append('IX, IY, I or IFF changed inside the hook')
            return True
        if R[12] < sp0 - 36 or R[12] > sp0 + 8:
            fails.append('hook stack out of range')
            return True
        if mem[0] != 0xF3:
            fails.append('slot 0 does not hold the handler byte')
            return True
        p = ns.nr[0x50]
        if p != 0xFF and p not in ns.patch.pages:
            fails.append('slot 0 holds a page that is not ours')
            return True
    return True


def event(patch, pc, get, R, ns, alt, psite, Sim, st):
    """Original and hook from one state. -> (failure strings, original's overlay)."""
    fails = []
    stop = ATTR_AGAIN if pc == ATTR_ROW and R[4] != 1 else EXIT[pc]
    incoming_speed = ns.nr[0x07] & 3
    serial0 = ns.state[_si(V_IRQ_SERIAL)]
    o = _O(get)
    so = _machine(Sim, o, list(R), _NULL, 'o')
    so.registers[24] = pc
    if not _run(so, stop, 400000):
        fails.append('original did not reach its exit')
    # v1.6 pace windows: what the original's displaced work must still cost, from this state's sizes and the carry
    hs = lambda a: ns.state[_si(a)] | ns.state[_si(a + 1)] << 8
    t0 = R[25]
    want16 = None
    if pc == BLIT:
        rows, cols = R[0], R[3]
        want16 = rows * cols * 3 // 2 + rows * 10
    elif pc == ATTR_ENTER:
        ns.attr_t0 = t0
    elif pc == ATTR_ROW and R[4] == 1 and getattr(ns, 'attr_t0', None) is not None:
        want16 = hs(V_WT0)
        t0 = ns.attr_t0
        ns.attr_t0 = None
    pd0 = hs(V_PD)
    pd0 = pd0 - 65536 if pd0 >= 32768 else pd0
    p = _P(get, alt, psite, ns)
    sp = _machine(Sim, p, list(R), ns, 'p')
    sp.registers[24] = pc
    ns.wall = float(R[25])
    if ns.scaled:
        if not _run_scaled(sp, stop, ns, 400000):
            fails.append('hook did not reach its exit')
    elif not _run_safe(sp, stop, ns, fails, 400000):
        fails.append('hook did not reach its exit')
    if pc in (BLIT, ATTR_ROW) and want16 is not None and incoming_speed == 0 and ns.state[_si(V_IRQ_SERIAL)] == serial0:
        need = (want16 + pd0) * 14                      # T at 3.5 MHz, the model's line clock; the wait polls at whole lines
        took = (ns.wall if ns.scaled else sp.registers[25]) - t0
        if need > 672 and took < need - 672:
            fails.append(('pace window did not wait', pc, need, took))
    dt = sp.registers[25] - R[25]
    st['hook T'] += dt
    if dt > st['most hook T in one event']:
        st['most hook T in one event'] = dt
    bad = [k for k in CMP if k != 24 and so.registers[k] != sp.registers[k]]
    if bad and os.environ.get('ARC_DBG'):
        print('DBG', hex(pc), 'in', [hex(x) for x in R[:8]], 'R in %02X orig %02X hook %02X' % (R[15], so.registers[15], sp.registers[15]), bad)
    if bad:
        fails.append(('registers', bad[:6]))
    low = sp.registers[12]
    for a in set(o.ov) | set(p.ov):
        if low - 64 <= a < low or 0x4000 <= a < 0x5B00:
            continue
        if o[a] != p[a] and a not in psite:
            fails.append(('memory', a, o[a], p[a]))
            break
    if p.scrw:
        fails.append('hook wrote the screen')
    if ns.nr[0x50] != 0xFF:
        fails.append('slot 0 not restored')
    if ns.nr[0x54] != 4:
        fails.append('slot 4 not restored')
    expected_speed = 3 if pc == ATTR_ENTER else ns.state[_si(V_ATTR_SPEED)] if pc == ATTR_ROW and R[4] == 1 else incoming_speed
    if ns.nr[0x07] & 3 != expected_speed:
        fails.append('speed not restored')
    if p.romw:
        fails.append('ROM write')
    if p.pagew:
        fails.append('page write')
    return fails, o


class _Null:
    nr = {}
    sel = 0

    def out(self, port, value):
        pass

    def nextreg(self, reg, val):
        pass


_NULL = _Null()


def digest(R, M, undo=None):
    """Registers and all RAM but the screen. undo: {address: original byte} for bytes patched in this replay."""
    h = hashlib.md5()
    h.update(bytes([R[k] & 255 for k in CMP if k != 24]))
    h.update(bytes([R[24] & 255, R[24] >> 8, R[12] & 255, R[12] >> 8]))
    sp = R[12]
    low = sp if STACK_LO <= sp < STACK_HI else STACK_LO
    d = bytearray(M[0x5B00:0x10000])
    if undo:
        for a, v in undo.items():
            d[a - 0x5B00] = v
    d[STACK_LO - 0x5B00:low - 0x5B00] = bytes(low - STACK_LO)       # below the stack: dead
    h.update(d)
    return h.digest()


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shot=None, scaled=False):
    """Differential test. Replay 1, the original code: each hook against the original from one state; registers, memory but the screen, sprites against the screen.
    Replay 2, the sites patched in memory (the copy undone, the paints skipped): the game's whole state against replay 1, event by event, and the screen bare."""
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    if patch.low is None:
        patch.tables()
    alt = _alt(patch)
    Sim = _rw()
    states = []
    psite = {}
    box = {'ns': None, 'clean': None, 'pend': None, 'beam': set()}       # pend None: no room drawn yet in this replay (a recording can start inside one)
    digests = []
    rnds = []
    frames_seen = collections.Counter()

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((c['blit'],) + tuple(info))

    def setup(M):
        if patch.low is None or not patch.pages:
            patch.mem = patch.mem or (bytes(16384) + M[0x4000:0x10000])
            patch.tables()
        for a, old, new in patch.sites:
            if a not in STORES or a in SITES_ORIG:
                for k, v in enumerate(new):
                    psite[a + k] = v
        box['ns'] = NextState(patch)
        box['ns'].scaled = scaled

    def rows_of(M):
        return [bytes(M[scr_addr(y):scr_addr(y) + 32]) for y in range(PLAY_LINES)]

    def check_screen(M, ns, o, whole):
        cl = box['clean']
        if cl is None:
            return
        figs = ns.compose()
        # the beam's pixels are on the screen in the original and in the build; the original's next copy over them puts the
        # buffer's bytes back, the build's does not (it no longer copies): those bytes are not compared while the beam is there
        masks = {}
        for a in box['beam']:
            y = ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)
            masks[y] = masks.get(y, 0) | 0xFF << (248 - 8 * (a & 31))
        if box['beam']:
            c['screen checks with beam bytes left out'] += 1
        ys = set()
        for a in o.ov:
            if 0x4000 <= a < 0x5800:
                y = ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)
                ys.add(y)
        if whole:
            ys = set(range(PLAY_LINES))
        bad = 0
        first = None
        for y in sorted(ys):
            if y >= PLAY_LINES:
                continue
            a = scr_addr(y)
            cur = bytearray(M[a:a + 32])
            for k in range(32):
                v = o.ov.get(a + k)
                if v is not None:
                    cur[k] = v
            if (int.from_bytes(cur, 'big') ^ int.from_bytes(cl[y], 'big') ^ figs[y]) & ~masks.get(y, 0):
                bad += 1
                if first is None:
                    first = y
        c['screen checks'] += 1
        if bad and os.environ.get('ARC_DUMP') and c['dumps'] < int(os.environ['ARC_DUMP']):
            c['dumps'] += 1
            print('DUMP blit', c['blit'], 'room', M[ROOMV], 'R', hex(M[0xFDE0]))
            for i in range(NOBJ):
                b = OBJ0 + i * 32
                print(i, ' '.join('%02X' % M[b + k] for k in range(32)), 'g %04X' % (M[b + 7] | M[b + 8] << 8), 'shown', ns.state[SHOWN + i])
            for y in sorted(ys):
                if y < PLAY_LINES:
                    a = scr_addr(y)
                    cur = bytearray(M[a:a + 32])
                    for k in range(32):
                        v = o.ov.get(a + k)
                        if v is not None:
                            cur[k] = v
                    d = int.from_bytes(cur, 'big') ^ int.from_bytes(cl[y], 'big')
                    print('%3d o %s\n    m %s' % (y, bin(d)[2:].zfill(256).replace('0', '.'), bin(figs[y])[2:].zfill(256).replace('0', '.')))
        if bad:
            fail('sprites over bare scenery differ from the original screen', (first, bad, M[ROOMV]))

    def check_record(M, R, ns):
        ix = R[8] << 8 | R[9]
        if ix & 31 or not OBJ0 <= ix < OBJ0 + 32 * NOBJ:
            fail('blit with IX outside the objects', (hex(ix),))
            return
        k = (ix - OBJ0) >> 5
        fl = M[ix]
        g = M[ix + 7] | M[ix + 8] << 8
        shown = ns.state[SHOWN + k]
        if fl & 1:
            n = patch.nums.get(g)
            if n is None:
                c['updates with a graphic not in the table'] += 1
                fail('graphic not in the table', (hex(g),))
                return
            w, h, col, bw = catalog(patch.mem)[g] if False else _cat(patch)[g]
            frames_seen[g] += 1
            cols, rows = shape(bw, h)
            if shown != cols * rows:
                fail('wrong number of sprites', (hex(g), shown))
            line = line_of_colour(col)
            for s in range(k * 6, k * 6 + shown):
                if ns.attr[s][2] >> 4 != line:
                    fail('sprite colour is not the graphic\'s', (hex(g), s))
                    break
                a = ns.attr[s]
                base = (a[3] & 0x3F) * 256 + (128 if a[4] & 0x40 else 0)
                off = (s - k * 6) * 128
                art = live_patterns(M, g, (w, h, col, bw)) if g in DYNAMIC else patch.approved_patterns[g]
                if bytes(ns.pat[base:base + 128]) != art[off:off + 128]:
                    fail('sprite pattern differs from approved art', (hex(g), s))
                    break
            if M[ix + 5] & 0x47 != col & 0x47:
                c['record colour differs from the graphic\'s header'] += 1
        else:
            if shown:
                fail('hidden object still shows sprites', (k, shown))
        v = len(ns.visible())
        if v > c['most sprites']:
            c['most sprites'] = v

    def on_pc(pc, sim):
        R, M = sim.registers, View(sim.memory)
        if pc >= 0xC000 and sim.memory.o7ffd & 7:
            return                      # bank 6 (the music) is at 0xC000: not the game's code
        if box['ns'] is None:
            setup(M)
        ns = box['ns']
        if pc == 0x30:
            fail('original executed the reserved RST 0x30')
            return
        if pc in INTERIORS:
            c['jump into a patched instruction (%d)!' % pc] += 1
            return
        if pc in (RNDNEXT, RND2NEXT):
            rnds.append(R[0])
            return
        if pc in PEND:
            box['pend'] = True
            box['beam'].clear()
            return
        if pc == BEAM_DRAW or pc == BEAM_WIPE:
            a = R[6] * 256 + R[7]
            if not 0x4000 <= a < 0x5800:
                fail('the beam writes outside the screen', (hex(a),))
            elif pc == BEAM_DRAW:
                box['beam'].add(a)
            else:
                box['beam'].discard(a)
            return
        if pc not in EXIT:
            return
        kind = KIND[pc]
        c[kind] += 1
        if kind == 'blit':
            digests.append(digest(R, M))
            free = M[STATE_LO:STATE_HI] + M[STATE2_LO:STATE2_HI]
            if box.setdefault('free0', free) != free:
                box['freecheck'] = True
            if box['pend'] is None:
                c['copies before the first room is drawn (no bare picture to check against)'] += 1
            if box['pend']:
                box['clean'] = rows_of(M)
                box['pend'] = False
                c['rooms'] += 1
        if collect and c['collected ' + kind] < collect:
            c['collected ' + kind] += 1
            states.append((kind, list(R), bytes(M[0:65536]), ns.copy()))
        fl, o = event(patch, pc, M.__getitem__, list(R), ns, alt, psite, Sim, c)
        for k in fl:
            fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())
        if kind in ('attribute', 'attribute_enter', 'attribute_row', 'random', 'random2', 'beam', 'player', 'irq_in', 'irq_out'):
            pass
        elif kind != 'blit':
            if ns.visible():
                fail('%s leaves sprites on' % kind, (len(ns.visible()),))
            box['clean'] = None
            box['pend'] = True
        else:
            check_record(M, R, ns)
            check_screen(M, ns, o, c['blit'] % 32 == 0)
            d = ns.state[V_DROP] | ns.state[V_DROP + 1] << 8
            if d != box.get('drop', 0):
                box['drop'] = d
                fail('the hook dropped a graphic', (d,))
            if callable(shot):
                shot(c['blit'], M, ns, R)

    pcs = set(EXIT) | set(INTERIORS) | PEND | {RNDNEXT, RND2NEXT, BEAM_DRAW, BEAM_WIPE, 0x30}
    fc, err = RZ.trace(rzx_path, pcs, on_pc, stop=stop)
    if err:
        c['replay stopped: %s!' % err] += 1
    c['frames'] = fc
    if box.get('freecheck'):
        c['the game touched the hook state bytes!'] += 1
    c['hooks never run'] = sum(1 for k in KIND.values() if not c[k])
    c['graphics seen'] = len(frames_seen)
    ex['graphics seen'] = sorted(frames_seen)
    ex['graphics seen counts'] = dict(frames_seen)

    # second replay: the game with the screen as the build leaves it
    idx = {'i': 0, 'first': True, 'pend': None, 'r': 0, 'shadow': {}, 'beam': set()}
    stores = dict(patch.stores)
    undo = {}
    for a, (old, new) in stores.items():
        for k, v in enumerate(old):
            undo[a + k] = v

    def on2(pc, sim):
        R, M = sim.registers, View(sim.memory)
        if pc >= 0xC000 and sim.memory.o7ffd & 7 and not idx['first']:
            return
        if idx['first']:
            idx['first'] = False
            for a, (old, new) in stores.items():
                for k, v in enumerate(new):
                    M[a + k] = v
        if pc in (ROOM, NEW1, NEW2, OVER, TELE):
            idx['shadow'].clear()
            idx['beam'].clear()
            idx['room'] = True
            return
        if pc == ATTR:
            idx['shadow'][R[6] * 256 + R[7]] = R[0]     # the ink the original paints here: the build's shadow page
            return
        if pc == BEAM + 1:
            a = R[6] * 256 + R[7]
            R[0] = idx['shadow'].get(a, M[a])           # as e_beam reads it
            return
        if pc == BEAM_STORE:
            idx['beam'].add(R[6] * 256 + R[7] - 0x5800)
            return
        if pc == LDIR:
            if idx['pend'] is None:
                de = R[4] << 8 | R[5]
                n = R[2] << 8 | R[3]
                idx['pend'] = (de, bytes(M[de:de + n]))
            return
        if pc == LDIR_END:
            if BLIT in {s[0] for s in patch.sites} and idx['pend'] is not None:
                de, saved = idx['pend']
                for k, v in enumerate(saved):
                    M[de + k] = v
            idx['pend'] = None
            return
        if pc in (RNDNEXT, RND2NEXT):
            # The actual e_random hooks resolve the original read view; no oracle substitution.
            i = idx['r']
            idx['r'] = i + 1
            a = R[6] * 256 + R[7]
            got = original_random_value(M, a, idx['shadow'])
            if i >= len(rnds) or got != rnds[i]:
                fail('random read differs', (a, got, rnds[i] if i < len(rnds) else None))
            R[0] = got
            return
        if pc != BLIT:
            return
        i = idx['i']
        idx['i'] = i + 1
        c['events replayed patched'] += 1
        if not (i < len(digests) and digest(R, M, undo) == digests[i]):
            c['the patched game state differs!'] += 1
            if len(ex['patched state']) < 5:
                ex['patched state'].append((i, R[24], M[ROOMV]))
        # the attributes of the play area: the room's clean copy, stars aside
        if i % 64 == 0 and idx.get('room'):     # (a recording that starts inside a room: its screen holds paints from before)
            room = M[ROOMV]
            cur = M[0x5800:0x5800 + 672]
            cln = M[0xF900:0xF900 + 672]
            stars = {M[STARS + k] for k in range(16)} if 64 <= room < 80 else set()     # the surface's twinkling cells (0xAC50)
            badc = 0
            for k in range(672):
                if cur[k] != cln[k] & 0x7F and k not in stars and k not in idx['beam']:
                    badc += 1
            c['bare attribute checks'] += 1
            if badc:
                c['play area attributes are not the room\'s!'] += 1
                if len(ex['attrs']) < 5:
                    ex['attrs'].append((i, room, badc, [(k, cur[k], cln[k]) for k in range(672) if cur[k] != cln[k] & 0x7F and k not in stars and k not in idx['beam']][:6]))
    fc2, err2 = RZ.trace(rzx_path, {BLIT, LDIR, LDIR_END, RNDNEXT, RND2NEXT, BEAM + 1, BEAM_STORE, ATTR, ROOM, NEW1, NEW2, OVER, TELE} | _starts(rzx_path), on2, stop=stop)
    if err2:
        c['patched replay stopped: %s!' % err2] += 1
    if fc2 != fc:
        c['patched replay ran %d frames against %d!' % (fc2, fc)] += 1
    if progress:
        progress(fc, c)
    return (c, dict(ex), states) if collect else (c, dict(ex))


_RANDOM_ROM = None



def original_random_value(M, a, shadow):
    if a < 0x4000:
        return original_random_rom()[a]
    if a < 0x5800:
        y = ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)
        return M[0xE400 + y * 32 + (a & 31)]
    return shadow.get(a, M[a])


def _starts(rzx_path):
    """The first PC of a replay (so the sites can be patched at the first instruction)."""
    from . import rzx as RZ
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    for b in parse_rzx(rzx_path):
        if isinstance(b.obj, Snapshot):
            return {b.obj.pc}
    return set()


_CATS = {}


def _cat(patch):
    k = id(patch.mem)
    if k not in _CATS:
        _CATS[k] = catalog(patch.mem)
    return _CATS[k]


# ---------------------------------------------------------------------------------------------
# Unit tests: every graphic at the edges
# ---------------------------------------------------------------------------------------------


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    say('Game      : %s' % name)
    say('Engine    : arc_of_yesod (the screen copy and paints no longer write; object records -> sprites at the copy; scenery/text stay on the ULA)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=PlainPatch())
    say('Plain     : %s  %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), TAIL_ADDR))
    patch = ArcPatch(z80)
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, TAIL_ADDR, True, quiet=True, patch=patch)
    say('Sprites   : %s  %s' % (os.path.basename(spr), md5(spr)))
    ok = True
    for r in list(a.rzx or []):
        cc, ex = verify(patch, r, stop=getattr(a, 'quick', None))
        fails = {k: v for k, v in cc.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, blit %d, room %d, new %d/%d, over %d, tele %d, %d screen checks, most sprites %d, %d graphics -> %s' % (
            os.path.basename(r), cc['frames'], cc['blit'], cc['room'], cc['new1'], cc['new2'], cc['over'], cc['tele'], cc['screen checks'], cc['most sprites'], cc['graphics seen'],
            'IDENTICAL' if not fails else 'FAILED %s' % fails))
        if fails:
            for k, v in ex.items():
                if k + '!' in cc or k == 'attrs':
                    say('            %s: %s' % (k, str(v)[:300]))
    return ok
