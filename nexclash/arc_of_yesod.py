"""The Arc of Yesod (Thor / Odin, 1985, 128K release) engine 'arc_of_yesod'. Additive module: reachable only through is_arc_of_yesod(). Facts, design, results: games/arc_of_yesod.md.

A port of nexclash/nodes_of_yesod.py: the same game engine at other addresses. The game XORs each figure into a back buffer at 0xE400 and copies the changed rectangle to the screen (0xD4B3); it then paints the ink of the empty cells the figure covers (0xD580).
Everything in the buffer stays as it was; only the copy and the paint stop writing, so the only memory that differs from the original is the screen.
Every figure change passes one place, 0xD4AF, with IX at the object: the hook sets that object's sprites from its record (fixed colour from the graphic's own header).
Patterns are built here from the two pointer tables (0x7E1C, 0x8D55), so a figure the recordings never reach has its patterns too.
"""
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
BLIT, ROOM, NEW1, NEW2, OVER, TELE = 0xD4AF, 0xAAF1, 0xA985, 0xAA3F, 0xDA50, 0xC112
ATTR_ENTER, ATTR_ROW, ATTR, PLAYER, IRQ_IN, IRQ_OUT, RANDOM, RANDOM2 = 0xD55A, 0xD589, 0xD580, 0xBAF8, 0xDDB3, 0xDDEE, 0xC355, 0xC1CC
OBJ0, NOBJ = 0xFC00, 16
SITES_ORIG = {ATTR_ENTER: ('dd7e05', 'e_attr_enter'), ATTR_ROW: ('15c262d5', 'e_attr_row'), PLAYER: ('dd21e0fd', 'e_player'), IRQ_IN: ('f5c5d5', 'e_irq_in'), IRQ_OUT: ('e1d1c1', 'e_irq_out'),
              RANDOM: ('7ee60f', 'e_random'), RANDOM2: ('6f677e', 'e_random2'), ATTR: ('77', 'e_attr'), BLIT: ('060008', 'e_blit'), ROOM: ('21bd5b', 'e_room'), NEW1: ('210040', 'e_new1'),
              NEW2: ('210040', 'e_new2'), OVER: ('210040', 'e_over'), TELE: ('210058', 'e_tele')}
STORES = {ATTR: (b'\x77', b'\x00')}
EXIT = {ATTR_ENTER: 0xD55D, ATTR_ROW: 0xD58D, PLAYER: 0xBAFC, IRQ_IN: 0xDDB6, IRQ_OUT: 0xDDF1, RANDOM: 0xC358, RANDOM2: 0xC1CF, ATTR: 0xD581, BLIT: 0xD4D8, ROOM: 0xAAF4, NEW1: 0xA988, NEW2: 0xAA42,
        OVER: 0xDA53, TELE: 0xC115}
KIND = {ATTR_ENTER: 'attribute_enter', ATTR_ROW: 'attribute_row', PLAYER: 'player', IRQ_IN: 'irq_in', IRQ_OUT: 'irq_out', RANDOM: 'random', RANDOM2: 'random2', ATTR: 'attribute', BLIT: 'blit',
        ROOM: 'room', NEW1: 'new1', NEW2: 'new2', OVER: 'over', TELE: 'tele'}
ATTR_AGAIN = 0xD562                  # the paint's row loop: e_attr_row's other exit
INTERIORS = tuple(a + k for a, (old, _) in SITES_ORIG.items() for k in range(1, len(bytes.fromhex(old))))
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
        d = patterns(mem, g, info, cmap, outline)
        pg = pages.setdefault(page, bytearray(8192))
        pg[0] = 0xF3
        pg[128 + idx * 128:128 + (idx + n) * 128] = d
        state[T_INDEX + ((g - G_LOW) >> 1)] = num
        if T_FRAME + num * 8 + 8 > AUX2:
            raise ValueError('too many graphics for the frame table: %d' % num)
        state[T_FRAME + num * 8:T_FRAME + num * 8 + 6] = bytes([page, idx, cols, rows, line_of_colour(c), bw])
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
        self.extra_banks = {ALT_BANK: self.page + self.low}
        for p, data in self.pages.items():
            bank = p // 2
            cur = self.extra_banks.get(bank, bytes(16384))
            o = (p & 1) * 8192
            self.extra_banks[bank] = cur[:o] + data + cur[o + 8192:]


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
    return True
