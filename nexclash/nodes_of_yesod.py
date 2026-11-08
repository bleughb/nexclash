"""Nodes of Yesod (Odin, 1985, 128K release) engine 'nodes_of_yesod'. Additive module: reachable only through is_nodes_of_yesod(). Facts, design, results: games/nodes_of_yesod.md.

The game XORs each figure into a back buffer at 0xE400 and copies the changed rectangle to the screen (36684); it then paints the ink of the empty cells the figure covers (36889).
Everything in the buffer stays as it was; only the copy and the paint stop writing, so the only memory that differs from the original is the screen.
Every figure change passes one place, 36680, with IX at the object: the hook sets that object's sprites from its record (fixed colour from the graphic's own header).
Patterns are built here from the two pointer tables (0xB700, 0xC700), so a figure the recordings never reach has its patterns too.
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE, ALT_BANK = 24, 12
PAT_PAGE0 = 26
TAIL_ADDR = 0xB440                  # 0xB3BB-0xB500 zero, never touched in the recordings
STATE_LO, STATE_HI = 0xB3BB, 0xB422  # backdrop and Enhanced HUD flags; v1.6 pace windows
V_WT0, V_PD, V_IRQ_SERIAL = 0xB419, 0xB41D, 0xB410
BACKDROP_FLAG = 0xB417 - STATE_LO
HUD_FLAG = 0xB418 - STATE_LO
HELD, SHOWN, V_DROP, V_CLIP = 0xB3C0 - STATE_LO, 0xB3E0 - STATE_LO, 0xB3F0 - STATE_LO, 0xB3F2 - STATE_LO
T_INDEX, T_FRAME = 0x0200, 0x1800
ROM_KEEP = 0x1F50
BUGGY_CLIP = 0x92C0                  # table entry 19 falls through into the mirrored entry: the game's own bug, a figure 4 bytes wide with one column left in the screen
G_LOW, G_SPAN = 0xB200, 0x2C00
BLIT, ROOM, NEW1, NEW2, OVER, TELE = 36680, 34268, 33766, 33946, 38127, 41596
OBJ0, NOBJ = 0xFC00, 16
SITES_ORIG = {36851: ('dd7e05', 'e_attr_enter'), 36898: ('15c2fb8f', 'e_attr_row'), 40048: ('dd21e0fd', 'e_player'), 39083: ('f5c5d5', 'e_irq_in'), 39125: ('e1d1c1', 'e_irq_out'), 31996: ('7ee60f', 'e_random'), 36889: ('77', 'e_attr'), BLIT: ('060008', 'e_blit'), ROOM: ('21135b', 'e_room'), NEW1: ('210040', 'e_new1'), NEW2: ('210040', 'e_new2'),
              OVER: ('210040', 'e_over'), TELE: ('210058', 'e_tele')}
STORES = {36889: (b'\x77', b'\x00'), 40371: (b'\x36\x47', b'\x18\x00'), 40374: (b'\x77', b'\x00'), 40379: (b'\x36\x47', b'\x18\x00'), 40382: (b'\x36\x47', b'\x18\x00')}
EXIT = {36851: 36854, 36898: 36902, 40048: 40052, 39083: 39086, 39125: 39128, 31996: 31999, 36889: 36890, BLIT: 36843, ROOM: 34271, NEW1: 33769, NEW2: 33949, OVER: 38130, TELE: 41599}
KIND = {36851: 'attribute_enter', 36898: 'attribute_row', 40048: 'player', 39083: 'irq_in', 39125: 'irq_out', 31996: 'random', 36889: 'attribute', BLIT: 'blit', ROOM: 'room', NEW1: 'new1', NEW2: 'new2', OVER: 'over', TELE: 'tele'}
INTERIORS = tuple(a + k for a, (old, _) in SITES_ORIG.items() for k in range(1, len(bytes.fromhex(old)))
                  if a + k not in (36682, 31997, 39084, 39085, 39126, 39127, 36899))
LDIR, LDIR_END = 36684, 36686
RNDREAD, RNDNEXT = 31996, 31997      # LD A,(HL) at a random address (H = L = R): can land on the screen
ROOMV = 23309
BOTTOM = 36486
PLAY_LINES = 168
INK, FILL, OUTLINE, WHITE = 1, 2, 3, 4
NORMAL = [0x00, 0x02, 0xC0, 0xC2, 0x18, 0x1A, 0xD8, 0xDA]
BRIGHT = [0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
SPARE = [0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0x18, 0x1A, 0xD8, 0x02, 0xC0]        # entries 5-15: colours for a painted sheet, each default ink among them
ALCHIEM = {0xB29D, 0xB2C0, 0xB2E3, 0xB306}     # white, but for the top right cell, as the game paints them (40371-40382)
MIN_OUTLINE = 24
MIN_DENSE = 0.22                    # ink pixels / box below this: a cloud of dots, not a body: no fill, no outline
FULL = (1 << 256) - 1

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'nodes_of_yesod_colours.json')


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'nodes_of_yesod.json'), os.path.join(_HERE, 'nodes_of_yesod.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('nodes_of_yesod.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_nodes_of_yesod(snap):
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
    """Every usable graphic the two pointer tables name -> {address of the rows: (w, h, colour, bytes wide)}. The rest of the tables' 256 words are not graphics."""
    out = {}
    for base in (0xB700, 0xC700):
        for i in range(128):
            p = mem[base + 2 * i] | mem[base + 2 * i + 1] << 8
            if p < G_LOW + 3 or p >= G_LOW + G_SPAN - 3:
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
    if g in ALCHIEM:
        for y in range(H):
            for x in range(W):
                if can[y][x] and not (x - 1 >= 8 and y - 1 < 8):
                    can[y][x] = WHITE
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
        state[T_FRAME + num * 8:T_FRAME + num * 8 + 6] = bytes([page, idx, cols, rows, line_of_colour(c), bw])
        nums[g] = num
        idx += n
    # RST 0x30 replaces the one-byte attribute store. The original branch to
    # INC L at 36890 stays intact; no jump spans that second entry point.
    attr = int(load_profile()['hooks']['syms']['e_attr'], 16)
    state[0x30:0x33] = bytes([0xC3, attr & 255, attr >> 8])
    helpers = bytes.fromhex(load_profile()['hooks'].get('helpers', ''))
    state[0x1E80:0x1E80 + len(helpers)] = helpers
    aux = bytes.fromhex(load_profile()['hooks'].get('aux', ''))
    state[0x1C50:0x1C50 + len(aux)] = aux
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
    name = 'Nodes of Yesod plain conversion'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    extra_banks = {}
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def apply(self, snap):
        snap.port1ffd = 4       # with 7FFD bit 4 set, as in the file, the ROM is the 48K ROM


class NodesPatch:
    name = 'Nodes of Yesod 128K: figures -> hardware sprites (altrom hooks, interrupts on, tables in Next pages at slot 0)'

    def __init__(self, z80=None, prof=None, rom_code=None, colours=None, stores=None, outline=False, mem=None, pal=None, backdrop=False, hud=None):
        self.prof = prof or load_profile()
        self.backdrop = bool(backdrop)
        self.outline = outline
        self.colours = {} if colours is None else colours
        self.hud = bool(self.colours) if hud is None else bool(hud)
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        setup = bytearray(bytes.fromhex(h['setup']))
        off = self.syms['pal'] - 0xD000
        self.palette = bytes(pal) if pal is not None else palette()
        if len(self.palette) != 256:
            raise ValueError('sprite palette must have 256 RGB332 entries')
        setup[off:off + 256] = self.palette
        assets = os.path.join(_HERE, '..', 'assets', 'nodes_of_yesod')
        with open(os.path.join(assets, 'aurora.bin'), 'rb') as f:
            self.backdrop_pixels = f.read()
        with open(os.path.join(assets, 'aurora.pal'), 'rb') as f:
            backdrop_palette = f.read()
        if len(self.backdrop_pixels) != 49152 or len(backdrop_palette) != 32:
            raise ValueError('aurora needs a 256x192 indexed plane and 16 paired RGB333 palette entries')
        with open(os.path.join(assets, 'cavern.bin'), 'rb') as f:
            self.cavern_pixels = f.read()
        with open(os.path.join(assets, 'cavern.pal'), 'rb') as f:
            cavern_palette = f.read()
        if len(self.cavern_pixels) != 49152 or len(cavern_palette) != 32:
            raise ValueError('cavern needs a 256x192 indexed plane and 16 paired RGB333 palette entries')
        setup[self.syms['backdrop_enabled'] - 0xD000] = int(self.backdrop)
        off = self.syms['backdrop_pal'] - 0xD000
        setup[off:off + 64] = backdrop_palette + cavern_palette
        with open(os.path.join(assets, 'hud_map.json')) as f:
            self.hud_writes = {int(k): v for k, v in json.load(f).items()}
        with open(os.path.join(assets, 'hud.pal'), 'rb') as f:
            hud_palette = f.read()
        if len(hud_palette) != 32 or any(not 0x1B00 <= a < 0x2000 for a in self.hud_writes):
            raise ValueError('invalid HUD palette or reserved-bank footprint')
        setup[self.syms['hud_enabled'] - 0xD000] = int(self.hud)
        off = self.syms['hud_pal'] - 0xD000
        setup[off:off + 32] = hud_palette
        self.stub_extra = bytes(setup)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 90
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
            self.sites.append((a, bytes.fromhex(old), b'\xF7' if a == 36889 else bytes([0xC3]) + self.syms[sym].to_bytes(2, 'little')))
        self.stores = STORES if stores is None else stores
        for a, (old, new) in self.stores.items():
            if a == 36889:
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
        self.start_pc = None                # a stub that holds the loading picture, when one is added
        self.hold = None

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
            raise ValueError('Nodes of Yesod patch expects the 128K release')
        if self.mem is None:
            self.mem = bytes(16384) + bytes(snap.banks[5]) + bytes(snap.banks[2]) + bytes(snap.banks[0])
        setup = bytearray(self.stub_extra)
        off = self.syms['printer_saved'] - 0xD000
        setup[off:off + 256] = snap.banks[5][0x1B00:0x1C00]
        self.stub_extra = bytes(setup)
        ram = bytearray(snap.banks[5] + snap.banks[2])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[STATE_LO - 0x4000:TAIL_ADDR + 90 - 0x4000]):
            raise ValueError('the state and tail bytes are not free in this snapshot')
        self.tables()
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.port1ffd = 4
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        pg = bytearray(self.page)
        pg[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self.page = bytes(pg)
        self.altrom_low = (ALT_PAGE + 1, self.low)
        self.extra_banks = {ALT_BANK: self.page + self.low}
        bank7 = bytearray(snap.banks[7])
        if any(bank7[a] for a in self.hud_writes):
            raise ValueError('the HUD tile/map bytes are not free in original bank 7')
        for a, b in self.hud_writes.items():
            bank7[a] = b
        self.extra_banks[7] = bytes(bank7)
        for p, data in self.pages.items():
            bank = p // 2
            cur = self.extra_banks.get(bank, bytes(16384))
            o = (p & 1) * 8192
            self.extra_banks[bank] = cur[:o] + data + cur[o + 8192:]
        for bank in range(18, 21):
            if bank in self.extra_banks:
                raise ValueError('aurora bank overlaps engine data')
            off = (bank - 18) * 16384
            self.extra_banks[bank] = self.backdrop_pixels[off:off + 16384]
        for bank in range(21, 24):
            if bank in self.extra_banks:
                raise ValueError('cavern bank overlaps engine data')
            off = (bank - 21) * 16384
            self.extra_banks[bank] = self.cavern_pixels[off:off + 16384]


# ---------------------------------------------------------------------------------------------
# Next-side state
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, patch):
        self.patch = patch
        self.nr = {0x50: 0xFF, 0x07: 0, 0x34: 0, 0x19: 0, 0x1C: 0}
        self.sel = 0
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patptr = 0
        self.state = bytearray(STATE_HI - STATE_LO)
        self.state[BACKDROP_FLAG] = int(patch.backdrop)
        self.state[HUD_FLAG] = int(patch.hud)
        self.l2_port = 0
        self.cache = {}
        self.ports = 0
        self.clip = [0, 255, 0, 167]
        self.clipi = 0

    def copy(self):
        q = NextState.__new__(NextState)
        q.__dict__.update(self.__dict__)
        q.nr = dict(self.nr)
        q.attr = [list(a) for a in self.attr]
        q.pat = bytearray(self.pat)
        q.state = bytearray(self.state).ljust(STATE_HI - STATE_LO, b'\0')
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
        if STATE_LO <= a < STATE_HI:
            return s.ns.state[a - STATE_LO]
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
        if STATE_LO <= a < STATE_HI:
            s.ns.state[a - STATE_LO] = v
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
                    line = (sim.registers[25] // 224) % 312
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
        player_ix_restore = stop == 40052 and R[24] == ns.patch.syms['e_blit'] - 3 and (R[8], R[9]) == (0xFD, 0xE0)
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
    stop = 36859 if pc == 36898 and R[4] != 1 else EXIT[pc]
    incoming_speed = ns.nr[0x07] & 3
    serial0 = ns.state[V_IRQ_SERIAL - STATE_LO]
    o = _O(get)
    so = _machine(Sim, o, list(R), _NULL, 'o')
    so.registers[24] = pc
    if not _run(so, stop, 400000):
        fails.append('original did not reach its exit')
    # v1.6 pace windows: what the original's displaced work must still cost, from this state's sizes and the carry
    hs = lambda a: ns.state[a - STATE_LO] | ns.state[a + 1 - STATE_LO] << 8
    t0 = R[25]
    want16 = None
    if pc == BLIT:
        rows, cols = R[0], R[3]
        want16 = rows * cols * 3 // 2 + rows * 10
    elif pc == 36851:
        ns.attr_t0 = t0
    elif pc == 36898 and R[4] == 1 and getattr(ns, 'attr_t0', None) is not None:
        want16 = hs(V_WT0)
        t0 = ns.attr_t0
        ns.attr_t0 = None
    pd0 = hs(V_PD)
    pd0 = pd0 - 65536 if pd0 >= 32768 else pd0
    p = _P(get, alt, psite, ns)
    sp = _machine(Sim, p, list(R), ns, 'p')
    sp.registers[24] = pc
    if not _run_safe(sp, stop, ns, fails, 400000):
        fails.append('hook did not reach its exit')
    if pc in (BLIT, 36898) and want16 is not None and incoming_speed == 0 and ns.state[V_IRQ_SERIAL - STATE_LO] == serial0:
        need = (want16 + pd0) * 14                      # T at 3.5 MHz, the model's line clock; the wait polls at whole lines
        if need > 672 and sp.registers[25] - t0 < need - 672:
            fails.append(('pace window did not wait', pc, need, sp.registers[25] - t0))
    dt = sp.registers[25] - R[25]
    st['hook T'] += dt
    if dt > st['most hook T in one event']:
        st['most hook T in one event'] = dt
    bad = [k for k in CMP if k != 24 and so.registers[k] != sp.registers[k]]
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
    expected_speed = 3 if pc == 36851 else ns.state[0xB416 - STATE_LO] if pc == 36898 and R[4] == 1 else incoming_speed
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
    low = sp if 0x9A00 <= sp < 0x9B80 else 0x9A00
    d = bytearray(M[0x5B00:0x10000])
    if undo:
        for a, v in undo.items():
            d[a - 0x5B00] = v
    d[0x9A00 - 0x5B00:low - 0x5B00] = bytes(low - 0x9A00)       # below the stack: dead
    h.update(d)
    return h.digest()


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shot=None):
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
    box = {'ns': None, 'clean': None, 'pend': True}
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

    def rows_of(M):
        return [bytes(M[scr_addr(y):scr_addr(y) + 32]) for y in range(PLAY_LINES)]

    def check_screen(M, ns, o, whole):
        cl = box['clean']
        if cl is None:
            return
        figs = ns.compose()
        # the game's own wrong plot at BUGGY_CLIP: the first 8 pixels of those lines are not compared
        masks = {}
        for i in range(NOBJ):
            b = OBJ0 + i * 32
            # The clear-before-erase path clears bit 0 one plot before its sprite
            # is retired. The same original wrong-left-edge plot applies there.
            if (M[b] & 1 or ns.state[SHOWN + i]) and (M[b + 14] | M[b + 15] << 8) == BUGGY_CLIP:
                y0, hh = M[b + 2], M[b + 4]
                for yy in range(y0, min(y0 + hh, PLAY_LINES)):
                    masks[yy] = ((1 << 8) - 1) << 248
                c['plots at the game\'s wrong clip'] += 1
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
        if bad and os.environ.get('NY_DUMP') and c['dumps'] < int(os.environ['NY_DUMP']):
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
        noplot = M[ix + 15] == 0x90 and M[ix + 14] in (0xC1, 0xC2)
        if noplot:
            c['updates at a clip where the original draws nothing'] += 1
            if shown:
                fail('sprites on where the original draws nothing', (k, shown))
        elif fl & 1:
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
                if bytes(ns.pat[base:base + 128]) != patch.approved_patterns[g][off:off + 128]:
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
        if pc in (40048, ROOM, NEW1, NEW2, OVER, TELE) and any(sim.memory.banks[7][a] for a in patch.hud_writes):
            fail('original uses the HUD tile/map bytes in bank 7')
        if box['ns'] is None:
            setup(M)
        ns = box['ns']
        if pc == 0x30:
            fail('original executed the reserved RST 0x30')
            return
        if pc in INTERIORS:
            c['jump into a patched instruction (%d)!' % pc] += 1
            return
        if pc == RNDNEXT:
            rnds.append(R[0])
            return
        if pc == 34384 or pc == 34361:
            box['pend'] = True
            return
        if pc not in EXIT:
            return
        kind = KIND[pc]
        c[kind] += 1
        if kind == 'blit':
            digests.append(digest(R, M))
            if c['blit'] % 256 == 1 and any(M[STATE_LO:TAIL_ADDR + 90]):
                box['freecheck'] = True
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
        if kind in ('attribute', 'attribute_enter', 'attribute_row', 'random', 'player', 'irq_in', 'irq_out'):
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

    pcs = set(EXIT) | set(INTERIORS) | {34384, 34361, RNDNEXT, 0x30}
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
    idx = {'i': 0, 'first': True, 'pend': None, 'r': 0, 'shadow': {}}
    stores = dict(patch.stores)
    undo = {}
    for a, (old, new) in stores.items():
        for k, v in enumerate(old):
            undo[a + k] = v

    def on2(pc, sim):
        R, M = sim.registers, View(sim.memory)
        if idx['first']:
            idx['first'] = False
            # Include the display-storage changes in the patched replay as well.
            for a, v in patch.hud_writes.items():
                sim.memory.banks[7][a] = v
            for a, (old, new) in stores.items():
                for k, v in enumerate(new):
                    M[a + k] = v
        if pc in (BLIT, ROOM, NEW1, NEW2, OVER, TELE) and any(sim.memory.banks[7][a] != v for a, v in patch.hud_writes.items()):
            fail('patched game changes the HUD tile/map storage')
        if pc in (ROOM, NEW1, NEW2, OVER, TELE):
            idx['shadow'].clear()
            return
        if pc == 36889:
            a = R[6] * 256 + R[7]
            if a in (0x5858, 0x5959, 0x5A5A):
                idx['shadow'][a] = R[0]
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
        if pc == RNDNEXT:
            # The actual e_random hook resolves the original read view; no oracle substitution.
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
        if i % 64 == 0:
            room = M[ROOMV]
            cur = M[0x5800:0x5800 + 672]
            cln = M[0xF900:0xF900 + 672]
            stars = {M[45018 + k] for k in range(16)} if room < 16 else set()
            badc = 0
            for k in range(672):
                if cur[k] != cln[k] & 0x7F and k not in stars:
                    badc += 1
            c['bare attribute checks'] += 1
            if badc:
                c['play area attributes are not the room\'s!'] += 1
                if len(ex['attrs']) < 5:
                    ex['attrs'].append((i, room, badc))
    fc2, err2 = RZ.trace(rzx_path, {BLIT, LDIR, LDIR_END, RNDNEXT, 36889, ROOM, NEW1, NEW2, OVER, TELE} | _starts(rzx_path), on2, stop=stop)
    if err2:
        c['patched replay stopped: %s!' % err2] += 1
    if fc2 != fc:
        c['patched replay ran %d frames against %d!' % (fc2, fc)] += 1
    if progress:
        progress(fc, c)
    return (c, dict(ex), states) if collect else (c, dict(ex))


_RANDOM_ROM = None


def original_random_rom():
    # This 128K release takes random bytes from ROM 1, including the keypad
    # extension at 0x386E. The Next's 48K ROM has different bytes there.
    global _RANDOM_ROM
    if _RANDOM_ROM is None:
        from skoolkit import ROM128, read_bin_file
        _RANDOM_ROM = bytes(read_bin_file(ROM128[1], 16384))
    return _RANDOM_ROM


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

def plot_model(mem, g, info, x, y, neg_x, mirror, bottom):
    """The figure's pixels as the game shows them -> lines. x, y as in the record; neg_x = bit 7 of +0."""
    w, h, c, bw = info
    X = x - 256 if neg_x else x
    Y = y - 256 if y + h > 255 else y
    lines = [0] * 192
    for j, v in enumerate(bits_of(mem, g, bw, h)):
        yy = Y + j
        if not 0 <= yy <= bottom:
            continue
        if mirror:
            v = int('{:0{}b}'.format(v, bw * 8)[::-1], 2)
        sh = 256 - bw * 8 - X
        o = (v << sh) if sh >= 0 else (v >> -sh)
        lines[yy] = o & FULL
    return lines


def unit_tests(patch, states, neg=None):
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    blits = [s for s in states if s[0] == 'blit']
    if not blits:
        c['no captured blit state!'] += 1
        return c, []
    _, R0, mem0, _ns = blits[0]
    cat = _cat(patch)
    psite = {}
    for a, old, new in patch.sites:
        if a not in STORES or a in SITES_ORIG:
            for k, v in enumerate(new):
                psite[a + k] = v
    fails = collections.Counter()
    ns = NextState(patch)
    ix = 0xFC20
    R = list(R0)
    R[8], R[9] = ix >> 8, ix & 255
    for g, info in sorted(cat.items()):
        w, h, col, bw = info
        cases = [(40, 40, 0, 0), (40, 40, 0, 1), (0, 0, 0, 0), (250, 100, 0, 0), (250, 100, 0, 1), (250, 100, 1, 0), (250, 100, 1, 1),
                 (100, 256 - max(1, h // 2), 0, 0), (100, 256 - max(1, h // 2), 0, 1), (100, 160, 0, 0), (225, 150, 0, 1)]
        for x, y, nx, mir in cases:
            for bot_v, bot in ((88, 167), (112, 143)):
                m = bytearray(mem0)
                for o in range(NOBJ):
                    m[OBJ0 + o * 32] = 0
                m[ix] = 1 | (0x80 if nx else 0)
                m[ix + 1] = x
                m[ix + 2] = y
                m[ix + 3] = w
                m[ix + 4] = h
                m[ix + 5] = col
                m[ix + 7] = g & 255
                m[ix + 8] = g >> 8
                m[ix + 30] = 0x80 if mir else 0
                m[ix + 14] = m[ix + 15] = 0
                m[BOTTOM] = bot_v
                ns.state[HELD:HELD + 32] = bytes(32)
                ns.state[SHOWN:SHOWN + 16] = bytes(16)
                for s in range(128):
                    ns.attr[s][3] = 0
                p = _P(m.__getitem__, alt, psite, ns)
                sim = _machine(Sim, p, list(R), ns, 'p')
                sim.registers[24] = BLIT
                if not _run(sim, EXIT[BLIT], 200000):
                    fails['hook ran away!'] += 1
                    continue
                got = ns.compose()
                want = plot_model(m, g, info, x, y, nx, mir, bot)
                c['positions'] += 1
                if got != want:
                    fails['pixels (%04X x=%d y=%d nx=%d m=%d b=%d)!' % (g, x, y, nx, mir, bot)] += 1
                if ns.nr[0x50] != 0xFF or ns.nr[0x07] != 0:
                    fails['slot or speed!'] += 1
                line = line_of_colour(col)
                for s in ns.visible():
                    if ns.attr[s][2] >> 4 != line:
                        fails['colour (%04X)!' % g] += 1
                        break
        c['graphics'] += 1
    # a pattern upload the handler interrupts: its 7FFD writes put the ROM back at slot 0 in the middle of a tile; the tile goes again
    g = sorted(cat)[20]
    info = cat[g]
    for hit in (1, 70, 127, 128, 200, 300, 500):
        m = bytearray(mem0)
        for o in range(NOBJ):
            m[OBJ0 + o * 32] = 0
        m[ix] = 1
        m[ix + 1], m[ix + 2] = 40, 40
        m[ix + 14] = m[ix + 15] = 0
        m[ix + 7], m[ix + 8] = g & 255, g >> 8
        m[ix + 30] = 0
        m[BOTTOM] = 88
        ns.state[HELD:HELD + 32] = bytes(32)
        ns.state[SHOWN:SHOWN + 16] = bytes(16)
        for s_ in range(128):
            ns.attr[s_][3] = 0
        ns.pat[:] = bytes(16384)
        out0 = ns.out
        count = {'n': 0}

        def out_hit(port, val, out0=out0, count=count, hit=hit):
            if port & 0xFF == 0x5B:
                count['n'] += 1
                if count['n'] == hit:
                    ns.nr[0x50] = 0xFF
            out0(port, val)
        ns.out = out_hit
        p = _P(m.__getitem__, alt, psite, ns)
        sim = _machine(Sim, p, list(R), ns, 'p')
        sim.registers[24] = BLIT
        ok = _run(sim, EXIT[BLIT], 200000)
        ns.out = out0
        c['interrupted uploads'] += 1
        if not ok or ns.compose() != plot_model(m, g, info, 40, 40, 0, 0, 167):
            fails['an interrupted upload left a wrong pattern (after byte %d)!' % hit] += 1
    # a graphic not in the table: hidden, counted, never a wrong picture
    m = bytearray(mem0)
    m[ix] = 1
    m[ix + 14] = m[ix + 15] = 0
    m[ix + 7] = 0x34
    m[ix + 8] = 0x12
    ns.state[V_DROP] = ns.state[V_DROP + 1] = 0
    p = _P(m.__getitem__, alt, psite, ns)
    sim = _machine(Sim, p, list(R), ns, 'p')
    sim.registers[24] = BLIT
    _run(sim, EXIT[BLIT], 200000)
    if ns.state[V_DROP] != 1 or ns.visible():
        fails['unknown graphic not dropped!'] += 1
    c['unknown graphic case'] += 1
    # the object index for all 16 objects: sprites k*6
    for k in range(NOBJ):
        i = OBJ0 + k * 32
        g = sorted(cat)[10]
        info = cat[g]
        m = bytearray(mem0)
        for o in range(NOBJ):
            m[OBJ0 + o * 32] = 0
        m[i] = 1
        m[i + 1] = 40
        m[i + 2] = 40
        m[i + 7] = g & 255
        m[i + 8] = g >> 8
        m[i + 30] = 0
        m[i + 14] = m[i + 15] = 0
        ns.state[SHOWN:SHOWN + 16] = bytes(16)
        ns.state[HELD:HELD + 32] = bytes(32)
        for s in range(128):
            ns.attr[s][3] = 0
        R2 = list(R0)
        R2[8], R2[9] = i >> 8, i & 255
        p = _P(m.__getitem__, alt, psite, ns)
        sim = _machine(Sim, p, list(R2), ns, 'p')
        sim.registers[24] = BLIT
        _run(sim, EXIT[BLIT], 200000)
        if not ns.visible() or min(ns.visible()) != k * 6:
            fails['object %d sprites!' % k] += 1
        c['objects'] += 1
    for k, v in fails.items():
        c[k] = v
    return c, sorted(fails)[:8]


# ---------------------------------------------------------------------------------------------
# Colour route (docs/COLOURS.md)
# ---------------------------------------------------------------------------------------------

def default_entry(c):
    """The palette entry (4-15) that shows a graphic's own ink on the sheet, where one line of entries serves every figure."""
    v = (BRIGHT if c & 0x40 else NORMAL)[c & 7]
    return 4 if v == 0xFF else 5 + SPARE.index(v) if v in SPARE else 4


def graphics_part(mem, g, info):
    w, h, c, bw = info
    px, ent = [], {}
    d = default_entry(c)
    for y in range(h):
        for bx in range(bw):
            a = g + y * bw + bx
            key = '%04X' % a
            data = mem[a]
            ent[key] = [data, 'g']
            for k in range(8):
                on = data >> (7 - k) & 1
                px.append((bx * 8 + k, y, key, k, 1 if on else 0, d if on else 0))
    return {'id': '%04X' % g, 'size': 1, 'w': bw * 8, 'h': h, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
            'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}


def colour_identity(peek):
    return {'schema': 1, 'game': 'nodes_of_yesod', 'engine': 'nodes_of_yesod', 'keys': 'nodes_of_yesod-gfx-1: %04X address of the graphics byte; bit = pixel',
            'inputs': hashlib.md5(bytes(peek(a) for a in range(G_LOW, G_LOW + G_SPAN))).hexdigest(), 'geometry': None}


def sheets(z80, out_dir, prefix='nodes_of_yesod', colours=None, say=print):
    """<prefix>_PAINTING_SPRITES.png + _REFERENCE_ALL_SPRITES.png, one figure per graphic, all of them whether or not a recording drew them. Painted nibbles are palette entries of the sprite's line."""
    from . import coloursheet as cs
    mem = view_from_snapshot(z80)
    cat = catalog(mem)
    comps = [{'count': 1, 'group': 0, 'parts': [graphics_part(mem, g, cat[g])]} for g in sorted(cat) if any(mem[g:g + cat[g][1] * cat[g][3]])]
    cmap = load_colours() if colours is None else colours
    pal = palette()
    rgb = cs.palette_rgb(list(pal[15 * 16:16 * 16]))
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(lambda a: mem[a])
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb, colours=cmap, paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb, colours=cmap, paint_clear=True, identity=ident)
    say('Sheets    : %d graphics; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


NOTE = 'Nodes of Yesod: pattern pages hold every graphic in the game\'s two tables; the sheet shows one figure per graphic. Painted entries 4-15 are fixed colours; 1 is the figure\'s own ink.'
RECOLOUR = {'game': 'nodes_of_yesod', 'output': 'enhanced', 'colours': 'docs/profiles/nodes_of_yesod_colours.json', 'clear': True, 'note': NOTE}


def recolour(nex, cmap, outline=False, pal=None):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build. Only pattern pages and the setup palette change."""
    from .recolour import banks, splice
    have = banks(nex)
    if not {5, 2, 0, ALT_BANK} <= set(have):
        raise ValueError('not a Nodes of Yesod sprite build')
    mem = bytes(16384) + bytes(have[5]) + bytes(have[2]) + bytes(have[0])
    for a, (old, sym) in SITES_ORIG.items():
        if mem[a] != (0xF7 if a == 36889 else 0xC3):
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    state, pages, _ = build_tables(mem, cmap, outline)
    if have[ALT_BANK][8192:] != state:
        raise ValueError("graphics table differs from this version's (rebuild with nexclash.py auto)")
    new = {}
    for pg, data in pages.items():
        bank = pg // 2
        cur = new.get(bank, have[bank])
        o = (pg & 1) * 8192
        new[bank] = cur[:o] + data + cur[o + 8192:]
    if pal is None:
        pf = os.path.join(_HERE, '..', 'docs', 'profiles', 'nodes_of_yesod_palette.json')
        pal = json.load(open(pf)) if cmap else palette()
    if len(pal) != 256:
        raise ValueError('sprite palette must contain 256 entries')
    setup = bytearray(have[10])
    off = 0x1000 + int(load_profile()['hooks']['syms']['pal'], 16) - 0xD000
    setup[off:off + 256] = bytes(pal)
    setup[0x1000 + int(load_profile()['hooks']['syms']['hud_enabled'], 16) - 0xD000] = int(bool(cmap))   # as NodesPatch: HUD on with a map
    new[10] = bytes(setup)
    out, changed = splice(nex, new)
    return out, {'banks changed': changed, 'map entries': len(cmap)}


# ---------------------------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------------------------

def _rom_patch(patch, off, new):
    import copy
    q = copy.copy(patch)
    code = bytearray(patch.rom_code)
    code[off:off + len(new)] = new
    q.rom_code = bytes(code)
    page = bytearray(patch.page)
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    q.page = bytes(page)
    return q


def negative_patches(patch):
    """Broken builds. Each must be detected on a real recording."""
    import copy
    out = {}
    if patch.low is None:
        patch.tables()
    code = patch.rom_code
    s = patch.syms

    def at(sym, needle, extra=0):
        return code.index(needle, s[sym] - ROM_ORG) + extra

    def pages(fn):
        q = copy.copy(patch)
        q.pages = {pg: fn(d) for pg, d in patch.pages.items()}
        return q

    def shifted(d):
        b = bytearray(d)
        for r in range(128 // 8, len(d) // 8):
            row = int.from_bytes(d[8 * r:8 * r + 8], 'big')
            b[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
        return bytes(b)
    out['patterns shifted one pixel'] = pages(shifted)

    def nib(d, m):
        b = bytearray(d)
        for i in range(128, len(b)):
            b[i] = m.get(b[i] >> 4, b[i] >> 4) << 4 | m.get(b[i] & 15, b[i] & 15)
        return bytes(b)
    out['ink pixels shown as fill'] = pages(lambda d: nib(d, {i: FILL for i in (INK, *range(4, 16))}))
    out['fill pixels shown as ink'] = pages(lambda d: nib(d, {FILL: INK}))
    out['outline covers the figure'] = pages(lambda d: nib(d, {i: OUTLINE for i in (INK, *range(4, 16))}))
    for addr, nm in ((36889, 'the figure paint still writes'), (40371, 'the item paint still writes')):
        q = copy.copy(patch)
        q.stores = {a: v for a, v in patch.stores.items() if a != addr}
        q.sites = [x for x in patch.sites if x[0] not in (addr, 36888 if addr == 36889 else addr)]
        out[nm] = q
    q = copy.copy(patch)
    q.sites = [x for x in patch.sites if x[0] != BLIT]
    out['the copy still writes, no sprites'] = q
    k = code.index(bytes([0xE1]), s['e_blit'] - ROM_ORG)
    out['e_blit loses HL'] = _rom_patch(patch, k, b'\x00')
    k = code.index(bytes([0xCD, s['update'] & 255, s['update'] >> 8]), s['e_blit'] - ROM_ORG)
    out['sprites never updated'] = _rom_patch(patch, k, bytes(3))
    k = at('e_room', bytes([0xCD, s['hideall'] & 255, s['hideall'] >> 8]))
    out['room redraw leaves sprites on'] = _rom_patch(patch, k, bytes(3))
    k = at('e_over', bytes([0xCD, s['hideall'] & 255, s['hideall'] >> 8]))
    out['game over leaves sprites on'] = _rom_patch(patch, k, bytes(3))
    k = at('e_tele', bytes([0xCD, s['hideall'] & 255, s['hideall'] >> 8]))
    out['teleport leaves sprites on'] = _rom_patch(patch, k, bytes(3))
    k = at('show', bytes([0x11, 31, 0, 0x19, 0x22]))            # LD DE,31 / ADD HL,DE / LD (V_X),HL
    out['x one column off'] = _rom_patch(patch, k, bytes([0x11, 33, 0]))
    k = at('show', bytes([0x11, 31, 0, 0x19, 0x22]), 0)
    k = code.index(bytes([0x11, 31, 0, 0x19, 0x22]), k + 1)
    out['y one line off'] = _rom_patch(patch, k, bytes([0x11, 33, 0]))
    k = at('show', bytes([0x3E, 8]))                             # mirror bit
    out['mirror flag not set'] = _rom_patch(patch, k, bytes([0x3E, 0]))
    k = code.index(bytes([0xED, 0xB3]))
    out['patterns never sent'] = _rom_patch(patch, k, bytes(2))
    k = at('upload', bytes([0xED, 0x91, 0x50, 0xFF]))
    out['slot 0 not restored'] = _rom_patch(patch, k, bytes(4))
    q = copy.copy(patch)
    low = bytearray(patch.low)
    k = s['ny_speed_out'] + 4
    assert low[k:k + 3] == bytes.fromhex('ed9207')
    low[k:k + 3] = bytes(3)
    q.low = bytes(low)
    out['speed not restored'] = q
    out['R not restored'] = _rom_patch(patch, s['ny_r_out_set'] - ROM_ORG, bytes(2))
    out['interrupts disabled'] = _rom_patch(patch, s['ny_r_run'] - ROM_ORG, b'\xF3')
    # v1.6 pace windows: the blit's call of win_wait gone, its target computed as zero (win_wait lives in the low 8K)
    k = at('e_blit', bytes([0x2A, 0x19, 0xB4]))                  # LD HL,(V_WT0)
    wait = code.index(bytes([0xCD, s['win_wait'] & 255, s['win_wait'] >> 8]), k)
    out['pace window never waits'] = _rom_patch(patch, wait, bytes(3))
    q = copy.copy(patch)
    low = bytearray(patch.low)
    k = s['blit_tgt'] + 3
    low[k:k + 2] = bytes.fromhex('1600')        # LD D,A -> LD D,0: rows x columns gone, the target too short
    q.low = bytes(low)
    out['pace target too short'] = q
    k = at('update', bytes([0xED, 0x92, 0x19]))
    out['clip window not updated'] = _rom_patch(patch, k, bytes(3))
    k = at('show', bytes([0xED, 0x92, 0x37]), 0)
    k2 = code.rindex(bytes([0xB2]), 0, k)                        # OR D: palette line + mirror + x high
    out['palette line dropped'] = _rom_patch(patch, k2 - 3, bytes([0x3E, 0, 0]))
    q = copy.copy(patch)
    q.low = patch.low[:T_INDEX] + bytes(T_FRAME - T_INDEX) + patch.low[T_FRAME:]
    out['graphics table empty'] = q

    def noh(d):
        b = bytearray(d)
        b[0] = 0
        return bytes(b)
    out['pattern page without the handler byte'] = pages(noh)
    return out


def negative_real(patch, rzx_path, stop=1500, only=None):
    out = []
    for name, q in negative_patches(patch).items():
        if only and name not in only:
            continue
        cc, _ = verify(q, rzx_path, stop=stop)
        out.append((name, {k: v for k, v in cc.items() if k.endswith('!')}))
    return out


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    say('Game      : %s' % name)
    say('Engine    : nodes_of_yesod (the screen copy and paints no longer write; object records -> sprites at the copy; scenery/text stay on the ULA; optional Enhanced HUD tilemap)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=PlainPatch())
    say('Plain     : %s  %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), TAIL_ADDR))
    patch = NodesPatch(z80)
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, TAIL_ADDR, True, quiet=True, patch=patch)
    say('Sprites   : %s  %s' % (os.path.basename(spr), md5(spr)))
    cmap = load_colours()           # Enhanced (the .nxc's colour set): the painted map, its palette and the HUD tilemap
    enh = os.path.join(out, name + '_enhanced.nex')
    pal = json.load(open(os.path.join(_HERE, '..', 'docs', 'profiles', 'nodes_of_yesod_palette.json'))) if cmap else None
    zt.convert(z80, enh, TAIL_ADDR, True, quiet=True, patch=NodesPatch(z80, colours=cmap, pal=pal))
    say('Enhanced  : %s  %s' % (os.path.basename(enh), md5(enh)))
    for label, cm, suffix in (('Backdrops', {}, '_backdrops'), ('Enh + bg', cmap, '_enhanced_backdrops')):   # the .nxc's toggle
        bd = os.path.join(out, name + suffix + '.nex')
        zt.convert(z80, bd, TAIL_ADDR, True, quiet=True, patch=NodesPatch(z80, colours=cm, pal=pal if cm else None, backdrop=True))
        say('%-10s: %s  %s' % (label, os.path.basename(bd), md5(bd)))
    ok = True
    states = []
    for r in list(a.rzx or []):
        cc, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in cc.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, blit %d, room %d, new %d/%d, over %d, tele %d, %d screen checks, most sprites %d, %d graphics -> %s' % (
            os.path.basename(r), cc['frames'], cc['blit'], cc['room'], cc['new1'], cc['new2'], cc['over'], cc['tele'], cc['screen checks'], cc['most sprites'], cc['graphics seen'],
            'IDENTICAL' if not fails else 'FAILED %s' % fails))
    if states:
        u, f = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.endswith('!')), 'PASS' if not uf else 'FAIL %s' % str(uf)[:400]))
    if a.rzx:
        nr = negative_real(patch, list(a.rzx)[0], stop=getattr(a, 'quick', None) or 2000)
        miss = [n for n, k in nr if not k]
        ok = ok and not miss
        say('Negative  : %d of %d detected %s' % (len(nr) - len(miss), len(nr), miss))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
