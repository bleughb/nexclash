"""3D Stock Car Championship (Firebird Software, 1988, 48K) engine 'stock_car_3d'. Additive module:
reachable only through is_stock_car_3d().

Game facts (survey of the reference snapshot and a scripted race; details in
games/3d_stock_car_championship.md):
  0xC55A  draw all cars, once a frame: waits for the frame (HALT at 0xC57C), restores the screen
          under each car's old place, then stores each car's prepared 24 x 8 block and paints the
          car's colour into up to six cells (LD (HL),B at 0xC8AE .. 0xC8E0).
  0xC3E7  prepare one car: screen address from x (IX+0x46), y (IX+0x43) through the ROM's pixel
          address routine, its image (IX+0x5F; table 0xBA86, 26 bytes an image: 8 rows of 2 bytes that
          are drawn, then 5 rows that never are) shifted into the car's record.
  0xD900  car records, 0x100 bytes each, four of them; count at 0xF994; ink (IX+0x3F).
  0xF9D0  clear the screen (0xF9CE = the same with attribute 0x43): every screen change starts here.
  Game logic READS the screen: a car's image ANDed with the screen at 0xC750 (collisions with the
  fences and with other cars' pixels), and a probe along a line at 0xD1A2. So every pixel write stays.
Hooks (asm/stock_car_3d_hooks.asm, alt ROM image 1, stateless): the overlay of docs/techniques
patch.xor-overlay-keep-ula - the game draws its cars as before; the six colour writes are removed
(no clash) and one sprite per car, set at the frame wait, covers the car's ink in the car's colour.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00          # printer buffer: holds old bytes in the snapshot, never read by the game (rom_paths)
GFX = 0xBA86
IMAGES = 28                 # image 28 is the game's blank
ROWS = 8                    # rows of an image that are drawn
CARS, NCARS = 0xD900, 0xF994
SITES_ORIG = {0xC90D: '3dc2fd', 0xF9D0: '265b06', 0xD27B: '16d6d9'}
SITE_SYM = {0xC90D: 'e_done', 0xF9D0: 'e_cls', 0xD27B: 'e_track'}
COLOUR_WRITES = (0xC8AE, 0xC8B7, 0xC8BF, 0xC8CF, 0xC8D8, 0xC8E0)    # LD (HL),B: the car's colour into a cell
SCREEN_PATCHES = [(a, '70', '00') for a in COLOUR_WRITES]
# bytes that must never be executed as an instruction start (interiors of patched instructions)
INTERIORS = (0xC90E, 0xC90F, 0xC910, 0xC911, 0xF9D1, 0xF9D2, 0xD27C, 0xD27D)   # 0xC910-0xC911: the rest of the JP and the RET the hook now does
BODY, GLASS = 1, 2          # pattern colour indexes of the plain cars (the game's own shapes)
LIVERIES = 4                # painted cars: cyan, green, yellow, white, picked in the hook by the car's ink
L2_BANK, L2_BANKS = 16, 5   # the backdrop: Layer 2 at 320 x 256, within banks 8-31 (all a NextTang's Layer 2 reaches)
PAL_AT = 0x3800             # in bank 11, after the patterns: the sprite palette
DATA_BANK, SKIP_BANK = 21, 47   # packed backdrops from bank 21 up, stepping over the build's own bank 47; past bank 47 needs a 2MB Next
MENU_KEY = 1                        # the menu picture's key in the index: no track's data is there
INDEX_ROOM, ENTRY = 1024, 35        # the index: ENTRY bytes a circuit (track data address, eleven places), 0xFFFF ends it
COVER_COLOURS = 64          # colours kept for the pixels that cover the game's own stands, trees and flags

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', '3d_stock_car_championship.json'),
              os.path.join(_HERE, '3d_stock_car_championship.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('3d_stock_car_championship.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_stock_car_3d(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


# ---------------------------------------------------------------------------------------------
# Patterns: image n -> pattern n, 16 x 16, the image in rows 0-7 (1 = body, 2 = glass, 0 = clear)
# ---------------------------------------------------------------------------------------------

def image_rows(peek, n):
    """The 8 drawn rows of image n, 16 bits each, the first byte the left eight pixels."""
    a = GFX + 26 * n
    return [peek(a + 2 * r) << 8 | peek(a + 2 * r + 1) for r in range(ROWS)]


def image_cells(peek, n):
    """16 x 16 colour indexes. A clear pixel with the car's ink on both sides of it in its row and
    above and below it in its column is glass, so the windows are not see-through."""
    rows = image_rows(peek, n)
    lit = [[rows[y] >> (15 - x) & 1 for x in range(16)] for y in range(ROWS)]
    out = [[0] * 16 for _ in range(16)]
    for y in range(ROWS):
        for x in range(16):
            if lit[y][x]:
                out[y][x] = BODY
            elif (any(lit[y][:x]) and any(lit[y][x + 1:]) and any(lit[r][x] for r in range(y))
                  and any(lit[r][x] for r in range(y + 1, ROWS))):
                out[y][x] = GLASS
    return out


def patterns(peek):
    out = bytearray()
    for n in range(IMAGES):
        for row in image_cells(peek, n):
            for k in range(0, 16, 2):
                out.append(row[k] << 4 | row[k + 1])
    return bytes(out)


# ---------------------------------------------------------------------------------------------
# Painted cars and the backdrop (assets/3d_stock_car_championship: original art, no game data)
# ---------------------------------------------------------------------------------------------

def _asset(name):
    return os.path.join(_HERE, '..', 'assets', '3d_stock_car_championship', name)


def nine_bit(rgb):
    """A colour on the Next's 512 grid -> the two bytes NEXTREG 0x44 takes."""
    r, g, b = (round(v * 7 / 255) for v in rgb)
    return bytes([r << 5 | g << 2 | b >> 1, b & 1])


def painted_cars():
    """-> (patterns: LIVERIES * IMAGES x 128 bytes, palette: LIVERIES x 16 colours x 2 bytes). A cell of the
    sheet is 16 x 16 with the game's image in rows 4-11; the sheet's grey is see-through (index 0)."""
    from PIL import Image
    lay = json.load(open(_asset('cars_layout.json')))
    sheet = Image.open(_asset('cars.png')).convert('RGB')
    clear = tuple(lay['transparent'])
    at = {(c['car'], c['image']): (c['x'], c['y']) for c in lay['cells']}
    pats, pal = bytearray(), bytearray()
    for car in range(1, LIVERIES + 1):
        colours = [tuple(c) for c in lay['cars'][car - 1]['colours']]
        if len(colours) > 15:
            raise ValueError('car %d has %d colours: a 4-bit sprite has 15' % (car, len(colours)))
        index = {c: i + 1 for i, c in enumerate(colours)}
        pal += bytes(2) + b''.join(nine_bit(c) for c in colours) + bytes(2 * (15 - len(colours)))
        for image in range(IMAGES):
            x0, y0 = at[(car, image)]
            for y in range(16):
                row = []
                for x in range(16):
                    p = sheet.getpixel((x0 + x, y0 + y))
                    row.append(0 if p == clear else index[p])
                for k in range(0, 16, 2):
                    pats.append(row[k] << 4 | row[k + 1])
    return bytes(pats), bytes(pal)


PLAIN_INKS = ((0, 255, 255), (0, 255, 0), (255, 255, 0), (255, 255, 255))   # livery 0-3: cyan, green, yellow, white


def plain_cars(peek):
    """-> (patterns, palette) as painted_cars(): the game's own shapes, each car in the colour the game gives it,
    its windows black. The image sits in rows 4-11 of its cell, where the painted ones have it."""
    pats, pal = bytearray(), bytearray()
    for ink in PLAIN_INKS:
        pal += bytes(2) + nine_bit(ink) + nine_bit((0, 0, 0)) + bytes(2 * 13)
        for image in range(IMAGES):
            cells = image_cells(peek, image)
            for y in range(16):
                row = cells[y - 4] if 4 <= y < 4 + ROWS else [0] * 16
                for k in range(0, 16, 2):
                    pats.append(row[k] << 4 | row[k + 1])
    return bytes(pats), bytes(pal)


def _pack(data):
    """ZX0, the format the hooks' decoder reads (the compressor the .nxc packager uses)."""
    import subprocess
    import tempfile
    from . import nxcout
    exe = os.path.join(nxcout.zx0_dir(), 'zx0.exe' if os.name == 'nt' else 'zx0')
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, 'a'), os.path.join(tmp, 'b')
        open(a, 'wb').write(data)
        subprocess.run([exe, '-f', a, b], check=True, capture_output=True)
        return open(b, 'rb').read()


def circuit_picture(path, cover_path):
    """One circuit's backdrop -> (Layer 2 bytes for 320 x 256, a column at a time: 81,920; palette: 256 x 2 bytes).
    cover_path is a 256 x 192 picture, white over the game's own stands, trees and flags: the backdrop's pixels
    there are redrawn in at most COVER_COLOURS colours whose palette entries carry the priority bit, so Layer 2
    draws them over the ULA and the game's decoration is not seen. Screen memory is not touched."""
    from PIL import Image
    im = Image.open(path).convert('RGB')
    if im.size != (320, 256):
        raise ValueError('%s must be 320 x 256' % path)
    px = im.load()
    cover = set()
    if cover_path:
        mask = Image.open(cover_path).convert('L')
        if mask.size != (256, 192):
            raise ValueError('%s must be 256 x 192' % cover_path)
        mp = mask.load()
        cover = set((32 + x, 32 + y) for x in range(256) for y in range(192) if mp[x, y])
    base = sorted(set(px[x, y] for x in range(320) for y in range(256) if (x, y) not in cover))
    if (0, 0, 0) in base or len(base) > 256:
        raise ValueError('%s has %d colours, or black: 256 at most, black is the see-through colour' % (path, len(base)))
    top, where = [], {}
    if cover:
        room = min(COVER_COLOURS, 256 - len(base))
        if room < 4:
            raise ValueError('%s uses %d colours: no room for the colours that cover the game\'s stands' % (path, len(base)))
        spots = sorted(cover)
        strip = Image.new('RGB', (len(spots), 1))
        strip.putdata([px[p] for p in spots])
        few = strip.quantize(room, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB')
        snap = lambda v: round(round(v * 7 / 255) * 255 / 7)
        for p, colour in zip(spots, few.getdata()):
            colour = tuple(snap(v) for v in colour)
            if colour == (0, 0, 0):
                colour = (0, 0, 36)
            if colour not in top:
                top.append(colour)
            where[p] = len(base) + top.index(colour)
    index = {c: i for i, c in enumerate(base)}
    data = bytes(where[(x, y)] if (x, y) in where else index[px[x, y]] for x in range(320) for y in range(256))
    pal = b''.join(nine_bit(c) for c in base)
    pal += b''.join(bytes([nine_bit(c)[0], nine_bit(c)[1] | 0x80]) for c in top)      # bit 15: over every other layer
    return data, pal + bytes(512 - len(pal))


_PACKED = []


def backdrops():
    """backdrops_(), packed once a run: every build with the pictures holds the same ones."""
    if not _PACKED:
        _PACKED.append(backdrops_())
    return _PACKED[0]


def backdrops_():
    """-> ({bank: bytes}, [circuits with a picture]). Every circuit with a picture in assets, packed: the index,
    then for each its palette and ten ZX0 streams (8K of Layer 2 each). A place is a page and an address in
    0xA000-0xBFFF; the hook maps that page and the next, so a stream may run on into the following page."""
    listed = json.load(open(_asset('circuits.json')))
    pages, at = {}, [2 * DATA_BANK, INDEX_ROOM]              # at: the page and offset the next byte goes to
    def after(page):
        return page + 1 if (page + 1) // 2 != SKIP_BANK else 2 * SKIP_BANK + 2
    def place(data):
        if at[1] + len(data) > 8192 and after(at[0]) != at[0] + 1:
            at[0], at[1] = after(at[0]), 0                   # it would run on into the bank that is not ours: start past it
        where = bytes([at[0], at[1] & 0xFF, 0xA0 + (at[1] >> 8)])
        for b in data:
            pages.setdefault(at[0], bytearray(8192))[at[1]] = b
            at[1] += 1
            if at[1] == 8192:
                at[0], at[1] = after(at[0]), 0
        return where
    index, have, shown, pictures = bytearray(), [], None, {}
    for c in listed:
        path = _asset('circuit_%02d.png' % c['circuit'])
        if not os.path.exists(path):
            continue
        cover = _asset('circuit_%02d_cover.png' % c['circuit'])
        data, pal = circuit_picture(path, cover if os.path.exists(cover) else None)
        places = place(pal) + b''.join(place(_pack(data[i:i + 8192])) for i in range(0, len(data), 8192))
        for track in c['track_data']:
            index += int(track, 16).to_bytes(2, 'little') + places
            pictures[int(track, 16)] = (data, pal)
        have.append(c['circuit'])
    menu = _asset('menu.png')
    if os.path.exists(menu):                                 # the picture behind the menu and the other text screens
        data, pal = circuit_picture(menu, None)
        shown = (data, pal)
        pictures[MENU_KEY] = shown
        places = place(pal) + b''.join(place(_pack(data[i:i + 8192])) for i in range(0, len(data), 8192))
        index += MENU_KEY.to_bytes(2, 'little') + places
    index += b'\xFF\xFF'
    if len(index) > INDEX_ROOM - 2:                          # its last two bytes: the picture Layer 2 holds (the hook's)
        raise ValueError('the backdrop index is %d bytes: %d at most' % (len(index), INDEX_ROOM))
    pages.setdefault(2 * DATA_BANK, bytearray(8192))[0:len(index)] = index
    if shown:                                                # the game starts on its menu: Layer 2 holds that picture
        pages[2 * DATA_BANK][INDEX_ROOM - 2:INDEX_ROOM] = MENU_KEY.to_bytes(2, 'little')
    if max(pages) > 223:
        raise ValueError('the backdrops need pages up to %d: a 2MB Next has 224' % max(pages))
    banks = {}
    for page, data in pages.items():
        banks.setdefault(page // 2, bytearray(16384))[(page % 2) * 8192:(page % 2) * 8192 + 8192] = data
    return {bank: bytes(data) for bank, data in banks.items()}, have, shown, pictures


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

class StockCar3dPatch:
    name = '3D Stock Car Championship cars -> hardware sprites over the game\'s own (altrom, stateless hooks)'

    def __init__(self, prof=None, rom_code=None, sound=None, backdrops=None, painted=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        code = bytearray(rom_code or bytes.fromhex(h['rom']))
        self.engine_sound = os.environ.get('NEXCLASH_STOCK_CAR_SOUND', '1') != '0' if sound is None else bool(sound)
        code[self.syms['engines'] - ROM_ORG] = int(self.engine_sound)      # the "engine sound for every car" option
        self.rom_code = bytes(code)
        # The painted circuits need a 2MB Next. Without them the build is the game on a 1MB one: cars as sprites only.
        self.with_backdrops = (os.environ.get('NEXCLASH_STOCK_CAR_BACKDROPS', '1') != '0' if backdrops is None
                               else bool(backdrops))
        # The cars: painted ("Enhanced colours"), or the game's own shapes in the game's own four colours
        self.painted = os.environ.get('NEXCLASH_STOCK_CAR_PAINTED', '1') != '0' if painted is None else bool(painted)
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
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
        for a, old in SITES_ORIG.items():
            if a == 0xD27B and not self.with_backdrops:
                continue                                       # the track is drawn as the game draws it, on black
            self.sites.append((a, bytes.fromhex(old), b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.pats = None
        self.num_patterns = LIVERIES * IMAGES

    def apply(self, snap):
        if snap.is128:
            raise ValueError('3D Stock Car Championship patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.plain = patterns(lambda a: ram[a - 0x4000])      # the game's own shapes: what a sprite must cover
        self.plain_rows = [image_rows(lambda a: ram[a - 0x4000], n) for n in range(IMAGES)]
        self.pats, self.sprite_palette = painted_cars() if self.painted else plain_cars(lambda a: ram[a - 0x4000])
        self.backdrop_banks, self.backdrop_circuits, menu, self.pictures = (
            backdrops() if self.with_backdrops else ({}, [], None, {}))
        self.menu_picture = menu
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        bank = bytearray(16384)
        bank[0:len(self.pats)] = self.pats
        bank[PAL_AT:PAL_AT + len(self.sprite_palette)] = self.sprite_palette
        if menu:                                               # setup puts it up: flag, then its palette
            bank[PAL_AT + 0x80] = 1
            bank[PAL_AT + 0x100:PAL_AT + 0x300] = menu[1]
        self.extra_banks = {11: bytes(bank), 12: self.page + bytes(8192)}
        for i in range(L2_BANKS if self.with_backdrops else 0):   # Layer 2: the menu's picture, then whatever is unpacked
            part = menu[0][i * 16384:(i + 1) * 16384] if menu else b''
            self.extra_banks[L2_BANK + i] = part + bytes(16384 - len(part))       # Layer 2 itself: a circuit's picture is unpacked into it
        self.extra_banks.update(self.backdrop_banks)


# ---------------------------------------------------------------------------------------------
# Verification (PLAYBOOK 6): the recording runs the original game; at each hook the original and the
# patched code run from the same state and are compared.
# ---------------------------------------------------------------------------------------------
# What differs by design, and why it cannot matter (games/3d_stock_car_championship.md "Divergent state"):
#   the attribute cells under a car (the six colour writes are gone: the sprite carries the colour), and
#   the six bytes in each car's record where the game keeps the cells' old attributes to put them back.
# The patched game's own copy of those bytes is carried from event to event (the "shadow"), and the patched
# code runs on it, so anything else that came to depend on them would show as a difference.
from .hooklib import CMP                          # every register but R, T and MEMPTR
# R: the game has no LD A,R (nor LD A,I) anywhere in its 48K, so R has no consumer and the hooks do not
# restore it (ENGINE_CONTRACT: an evidence-backed exception; unit_tests checks the "no LD A,R" claim).

DRAW, DRAW_END = 0xC55A, 0xC912                   # "draw all cars": 0xC55A to its RET at 0xC911
WAIT = 0xC57C                                     # its HALT: the frame wait
CLS, CLS_ON, TRACK, TRACK_ON = 0xF9D0, 0xF9D4, 0xD27B, 0xD27E
BEFORE_TRACK = 0xBEE1                             # the clear that is called from 0xBEDE returns here
DONE = 0xC90D
CARS, NCARS = 0xD900, 0xF994
KEPT = tuple(CARS + 0x100 * n + k for n in range(4) for k in range(0x52, 0x58))   # attributes kept under a car
ATTRS = (0x5800, 0x5B00)
PRINTER = (0x5B00, 0x5C00)                        # the hooks' own stack while the game's memory is paged out
LIVERY = (0, 0, 0, 0, 1, 0, 2, 3)                 # by ink, as the hook's table
KEEPERS = (0xC8A7, 0xC8B0, 0xC8B9, 0xC8C8, 0xC8D1, 0xC8DA)   # the only readers of attributes: each keeps one cell
GAME_PAGES = {0x54: 4, 0x55: 5, 0x56: 0, 0x57: 1}
SITE_KIND = {DRAW: 'draw', CLS: 'cls', TRACK: 'track'}


def image_of(high, mid):
    """The game's own heading -> image rule (0xC35D), on the accepted heading (IX+0x0B), (IX+0x0A)."""
    a, top = high, mid >> 7
    if a == 0:
        return a + top
    a += 1
    if a < 0x0C:
        return a
    if a == 0x0C:
        return a + top
    a += 1
    if a == 0x0E:
        return a + top
    a += 1
    if a < 0x1A:
        return a
    return a + top


class NextState:
    """The part of the Next the hooks drive: sprites, Layer 2 and its palette, the pages, the sound chips."""

    def __init__(self, patch):
        self.nr = {0x07: 0, 0x08: 0, 0x69: 0x80 if patch.menu_picture else 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pages = {}
        for bank, data in patch.extra_banks.items():
            self.pages[2 * bank] = bytearray(data[:8192])
            self.pages[2 * bank + 1] = bytearray(data[8192:])
        self.mmu = [None] * 4                     # slots 4-7: None = the game's own page
        self.l2pal = bytearray(patch.menu_picture[1] if patch.menu_picture else bytes(512))
        self.pal_at = 0
        self.select = 0
        self.chip, self.reg = 0xFF, 0
        self.ay = {0xFF: {}, 0xFE: {}}
        self.uploaded = bytearray()
        self.events = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg in GAME_PAGES:
            self.mmu[reg - 0x54] = None if val == GAME_PAGES[reg] else val
        elif reg == 0x40:
            self.pal_at = 2 * val
        elif reg == 0x44 and self.nr.get(0x43) == 0x10:
            self.l2pal[self.pal_at % 512] = val
            self.pal_at += 1
        self.events.append(('nr', reg, val))

    def out(self, port, value):
        self.events.append(('out', port, value))
        if port == 0x243B:
            self.select = value
        elif port == 0x253B:
            self.nextreg(self.select, value)
        elif port == 0xFFFD:
            if value >= 0xFC:
                self.chip = value
            else:
                self.reg = value
        elif port == 0xBFFD:
            self.ay.setdefault(self.chip, {})[self.reg] = value
        elif port & 0xFF == 0x5B:
            self.uploaded.append(value)              # a sprite pattern byte

    def inp(self, port):
        self.events.append(('in', port))
        return self.nr.get(self.select, 0) if port == 0x253B else 0xFF

    def layer2(self):
        return b''.join(bytes(self.pages[2 * L2_BANK + i]) for i in range(2 * L2_BANKS))

    def sprite(self, i):
        """-> None if hidden, else (x, y, pattern, palette offset) of a 4-bit sprite."""
        a = self.attr[i]
        if not a[3] & 0x80:
            return None
        return (a[0] | (a[2] & 1) << 8, a[1], (a[3] & 0x3F) << 1 | (a[4] >> 6 & 1), a[2] >> 4)


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def _overlays(patch, get, alt, ns, shadow):
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return get(a) if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v
            else:
                s.romw = getattr(s, 'romw', []) + [a]   # the game itself writes below 0x4000 (ignored, as on a 48K)

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if a >= 0x8000:
                page = ns.mmu[(a >> 13) - 4]
                if page is not None:
                    return ns.pages[page][a & 0x1FFF]
            v = psite.get(a)
            if v is not None:
                return v
            v = s.ov.get(a)
            if v is not None:
                return v
            v = shadow.get(a)
            return get(a) if v is None else v

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', []) + [a]
            elif a >= 0x8000 and ns.mmu[(a >> 13) - 4] is not None:
                ns.pages[ns.mmu[(a >> 13) - 4]][a & 0x1FFF] = v
            else:
                if a in psite:
                    s.sitew = True                   # the read above would go on returning the patch
                s.ov[a] = v
    return O, P


def _machine(Sim, mem, regs, ns, slot):
    from . import z80n
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)

    class Tr:
        def read_port(s, registers, port):
            return ns.inp(port)

        def write_port(s, registers, port, value, *x):
            ns.out(port, value)
    z80n.install(sim, ns.nextreg, strict=False)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=4000000):
    """Run to stop(R). The game's frame wait (the HALT at 0xC57C, and no other) is stepped over, in both runs
    alike: the handler is an empty IM 2 one."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        if mem[R[24]] == 0x76:
            if R[24] != WAIT:
                return False                         # a HALT anywhere else would hang the machine
            R[24] = (R[24] + 1) % 65536
            continue
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


AY_PORTS = (0x243B, 0x253B, 0xFFFD, 0xBFFD)
PICTURE_REGS = set(range(0x34, 0x3A)) | {0x07, 0x40, 0x43, 0x44, 0x54, 0x55, 0x56, 0x57, 0x69}


def expected_sprites(peek):
    """What the four sprites must be after "draw all cars", from the game's own memory: None = hidden."""
    out = []
    for n in range(4):
        rec = CARS + 0x100 * n
        if n >= peek(NCARS) or peek(rec + 0x5F) >= IMAGES:
            out.append(None)
            continue
        livery = LIVERY[peek(rec + 0x3F) & 7]
        out.append((peek(rec + 0x08) + 32, peek(rec + 0x05) + 28,
                    IMAGES * livery + image_of(peek(rec + 0x0B), peek(rec + 0x0A)), livery))
    return out


def _lit(peek, x, y):
    if not (0 <= x < 256 and 0 <= y < 192):
        return True
    return peek(0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x >> 3) >> (7 - (x & 7)) & 1


def event(patch, kind, get, R, ns, alt, Sim, shadow, start=None):
    """One hook event: original and patched from the same state. -> (failures, car pixels checked).
    kind: 'draw' (0xC55A to its return), 'cls' (0xF9D0 to 0xF9D4), 'track' (0xD27B to 0xD27E), 'done' (0xC90D to
    the routine's return: unit tests only)."""
    f, sp0, npx = [], R[12], 0
    w = lambda a: get(a) | get(a + 1) << 8
    if kind in ('draw', 'done'):
        ret = w(sp0)
        stop = lambda r: r[24] == ret and r[12] == (sp0 + 2) % 65536
    elif kind == 'cls':
        stop = lambda r: r[24] == CLS_ON
    else:
        stop = lambda r: r[24] == TRACK_ON
    O, P = _overlays(patch, get, alt, ns, shadow)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState.__new__(NextState), 'o')
    ns.events = []
    speed, was = ns.nr.get(0x07, 0), [list(a) for a in ns.attr]
    held = bytes(ns.pages[2 * DATA_BANK][INDEX_ROOM - 2:INDEX_ROOM]) if 2 * DATA_BANK in ns.pages else None
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if not _run(so, stop):
        return [('original did not return',)], 0
    if not _run(sp_, stop):
        return [('patched did not return', sp_.registers[24])], 0
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', []) != getattr(o, 'romw', []):
        f.append(('patched code wrote ROM', len(getattr(o, 'romw', [])), len(getattr(p, 'romw', []))))
    if getattr(p, 'sitew', False):
        f.append(('patched code wrote a patch site',))
    if any(m is not None for m in ns.mmu):
        f.append(('memory left paged', list(ns.mmu)))
        ns.mmu = [None] * 4
    if ns.nr.get(0x07, 0) != speed:
        f.append(('CPU speed not put back', ns.nr.get(0x07)))
    dead = range(ro[12] - 32, ro[12])               # below the final SP: dead stack (the hooks push 22 bytes at most)
    keys = set(o.ov) | set(p.ov)
    own = set(KEPT) | set(range(*ATTRS))
    md = [a for a in keys if a not in own and a not in dead and not PRINTER[0] <= a < PRINTER[1]
          and o[a] != (p.ov[a] if a in p.ov else get(a))]
    if md:
        f.append(('memory differs', len(md), ['%04X' % a for a in sorted(md)[:4]]))
    # The patched game never colours a cell: whatever it writes to an attribute is what the cell already held
    # (the routine putting back what it kept). A colour write left in would write the car's ink here.
    tinted = [a for a, v in p.ov.items() if ATTRS[0] <= a < ATTRS[1] and v != (shadow[a] if a in shadow else get(a))]
    if tinted and kind in ('draw', 'done'):
        f.append(('patched code changed an attribute', len(tinted), '%04X' % tinted[0]))
    for a, v in p.ov.items():                       # the patched game's own attributes and kept bytes, carried on
        if a in own:
            shadow[a] = v
    ports = [e for e in ns.events if e[0] in ('in', 'out')]
    if any(e[1] not in AY_PORTS for e in ports):
        f.append(('port access other than the Next registers and the sound chips',))
    if not patch.engine_sound and kind in ('draw', 'done') and ports:
        f.append(('port access with the engine option off',))
    peek = lambda a: o[a]
    if kind in ('draw', 'done'):
        if any(e[0] == 'nr' and not (0x34 <= e[1] <= 0x39 or e[1] == 0x08) for e in ns.events):
            f.append(('NEXTREG other than sprite attributes',))
        want = expected_sprites(peek)
        got = [ns.sprite(i) for i in range(4)]
        if got != want:
            f.append(('sprites are not on the cars', want, got))
        for i, s in enumerate(want):                # every attribute byte: no mirror, rotation or scale, 4-bit pattern
            if s is not None and ns.attr[i] != [s[0] & 255, s[1], s[3] << 4 | s[0] >> 8, 0xC0 | s[2] >> 1, 0x80 | (s[2] & 1) << 6]:
                f.append(('sprite attributes are not the plain 4-bit ones', i, list(ns.attr[i])))
        for n, s in enumerate(want):                # ... and the car the game drew is there, under its sprite
            if s is None or kind == 'done':         # ('done' alone: the cars are not drawn in it)
                continue
            image = s[2] % IMAGES
            for r, row in enumerate(patch.plain_rows[image]):
                for k in range(16):
                    if row >> (15 - k) & 1:
                        npx += 1
                        if not _lit(peek, s[0] - 32 + k, s[1] - 28 + r):
                            f.append(('the game\'s car is not where its sprite is', n))
                            break
                else:
                    continue
                break
        if any(ns.attr[i] != was[i] for i in range(4, 128)):
            f.append(('other sprites changed',))
        if patch.engine_sound:
            bad = [e for e in ns.events if e[0] == 'out' and e[1] == 0xFFFD and not (e[2] in (0xFF, 0xFE) or e[2] <= 10)]
            if bad:
                f.append(('sound chip register out of range', bad[:2]))
    else:
        odd = sorted({e[1] for e in ns.events if e[0] == 'nr'} - PICTURE_REGS)
        if odd:
            f.append(('NEXTREG the picture hooks have no business with', ['%02X' % r for r in odd]))
        if any(ns.sprite(i) for i in range(4)) and kind == 'cls':
            f.append(('sprite visible after the screen clear',))
        if kind == 'cls' and patch.engine_sound is not None:
            loud = [(c, r) for c in (0xFF, 0xFE) for r in (8, 9, 10) if ns.ay[c].get(r, 0)]
            if loud:
                f.append(('sound left on after the screen clear', loud))
        if any(0x4000 <= a < 0x5B00 for a in p.ov):
            f.append(('patched code wrote the screen',))
        key = None
        if patch.with_backdrops:
            if kind == 'track':
                key = w(0xD4B9)
            elif w(sp0) != BEFORE_TRACK:
                key = MENU_KEY
        if key is None:
            if kind == 'cls' and ns.nr.get(0x69):
                f.append(('Layer 2 on after the clear before a track',))
        elif key in patch.pictures:
            data, pal = patch.pictures[key]
            loads = [i for i, e in enumerate(ns.events) if e[:2] == ('nr', 0x44)]
            if held == key.to_bytes(2, 'little'):
                if loads:
                    f.append(('a picture Layer 2 already held was unpacked again',))
            elif not loads or ('nr', 0x69, 0) not in ns.events[:loads[0]]:
                f.append(('Layer 2 was not off while the picture was unpacked',))
            if ns.nr.get(0x69) != 0x80:
                f.append(('Layer 2 not on',))
            if ns.layer2() != data:
                f.append(('Layer 2 does not hold the picture', '%04X' % key))
            if bytes(ns.l2pal) != pal:
                f.append(('Layer 2 palette is not the picture\'s', '%04X' % key))
            if bytes(ns.pages[2 * DATA_BANK][INDEX_ROOM - 2:INDEX_ROOM]) != key.to_bytes(2, 'little'):
                f.append(('the note of which picture Layer 2 holds is wrong',))
        elif ns.nr.get(0x69):
            f.append(('Layer 2 on with no picture for this',))
    return f, npx


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX (original game); at every hook site run original and patched code from the same state and
    compare. Returns (Counter, examples[, states]); failure keys end in '!'."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    own = set(KEPT) | set(range(*ATTRS))
    printer = set(range(*PRINTER))
    colour = set(COLOUR_WRITES)
    st = {'frame': 0, 'on': False, 'draw': None, 'R': None}
    ns = NextState(patch)
    cnt = collections.Counter()
    watch = set(SITE_KIND) | set(INTERIORS) | colour | {DONE}
    states, shadow, readers = [], {}, collections.Counter()

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __getitem__(s, a):
            if st['on'] and type(a) is int:
                if a in own:
                    pc = st['R'][24]
                    readers[pc] += 1
                    if not (pc in KEEPERS if a < ATTRS[1] else DRAW <= pc < DRAW_END):
                        fail('attributes or a car\'s kept bytes read by other code', ('%04X' % pc, '%04X' % a))
                elif a in printer and not PRINTER[0] <= st['R'][24] < PRINTER[1]:
                    fail('the game read the printer buffer', ('%04X' % st['R'][24],))
            return G(s, a)

        def __setitem__(s, a, v):
            if st['on'] and type(a) is int:
                if a in site_bytes:
                    fail('game wrote a patch site', ('%04X' % a,))
                elif a in own:
                    if st['draw'] is None:
                        shadow[a] = v               # written outside the draw routine: the patched game does the same
                elif a in printer:
                    fail('the game wrote the printer buffer', ('%04X' % st['R'][24],))
            S(s, a, v)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            st['R'] = R
            st['mem'] = mem
            get = lambda a: G(mem, a)
            for a in own:
                shadow[a] = get(a)
            st['on'] = True

            def mk(fn):
                def g():
                    pc = R[24]
                    d = st['draw']
                    if d is not None and pc == d[0] and R[12] == d[1]:
                        st['draw'] = d = None
                    if pc in watch:
                        cnt[pc] += 1
                        kind = SITE_KIND.get(pc)
                        if kind:
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((kind, list(R), bytes(G(mem, a) for a in range(65536)), dict(shadow)))
                            fl, npx = event(patch, kind, get, R, ns, alt, _rw(), shadow)
                            c[kind] += 1
                            c['car pixels checked under their sprites'] += npx
                            for k in fl:
                                fail('%s: %s' % (kind, k[0]), k[1:])
                            if kind == 'draw':
                                st['draw'] = (get(R[12]) | get(R[12] + 1) << 8, (R[12] + 2) % 65536)
                        elif pc in colour and d is None:
                            fail('a colour write ran outside the draw routine', ('%04X' % pc,))
                        elif pc == DONE:
                            if d is None:
                                # the routine's last loop, called on its own (the cars are placed, not drawn): the
                                # hook runs here too, and must leave the same state
                                fl, npx = event(patch, 'done', get, R, ns, alt, _rw(), shadow)
                                c['done'] += 1
                                for k in fl:
                                    fail('done: %s' % (k[0],), k[1:])
                                st['draw'] = (get(R[12]) | get(R[12] + 1) << 8, (R[12] + 2) % 65536)
                            elif collect and R[0] == 1 and c['collected done'] < collect:
                                c['collected done'] += 1
                                states.append(('done', list(R), bytes(G(mem, a) for a in range(65536)), dict(shadow)))
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

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
    # a site whose first instruction is one or two bytes: the original runs the rest of the three itself
    for site, sequel in ((DONE, 0xC90E), (CLS, 0xF9D2), (TRACK, 0xD27D)):
        if cnt[site] != cnt[sequel]:
            c['%04X reached other than from %04X!' % (sequel, site)] += 1
    if cnt[0xC911] != c['draw'] + c['done'] and not stop:
        c['the draw routine\'s RET reached %d times for %d calls!' % (cnt[0xC911], c['draw'])] += 1
    for a in (0xC90F, 0xC910, 0xF9D1, 0xD27C):
        if cnt[a]:
            c['jump into a patched instruction (%04X)!' % a] += 1
    c['attribute cells and kept bytes where the patched game differs at the end'] = sum(
        1 for a in own if shadow[a] != G(st['mem'], a)) if 'mem' in st else 0
    c['readers of the kept bytes and attributes (addresses)'] = len(readers)
    c['frames'] = st['frame']
    if not c['draw']:
        c['the recording reached no car draw: nothing was verified!'] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def variant(patch, sound=None, backdrops=None):
    """The same applied patch with an option changed: what the other builds of the .nxc hold."""
    import copy
    q = copy.copy(patch)
    if sound is not None:
        q.engine_sound = bool(sound)
        code = bytearray(q.rom_code)
        code[q.syms['engines'] - ROM_ORG] = int(q.engine_sound)
        q.rom_code = bytes(code)
        page = bytearray(q.page)
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
        q.page = bytes(page)
    if backdrops is False:
        q.with_backdrops, q.pictures, q.menu_picture = False, {}, None
        q.sites = [x for x in q.sites if x[0] != TRACK]
        bank = bytearray(q.extra_banks[11])
        bank[PAL_AT + 0x80] = 0
        q.extra_banks = {11: bytes(bank), 12: q.extra_banks[12]}
    return q


def negative_patches(patch):
    """Broken copies, each of which a different check must catch: the sprite one pixel off its car; a colour
    write left in the game (the car tints its cell again)."""
    import copy
    tint = copy.copy(patch)
    tint.sites = [x for x in patch.sites if x[0] != COLOUR_WRITES[0]]
    return [negative_patch(patch), tint]


def setup_check(patch, R):
    """Run the setup stub as the loader does and look at what it leaves: the patterns, the palettes, Layer 2."""
    f, ns = [], NextState(patch)
    ns.nr, ns.l2pal = {}, bytearray(512)
    base = bytearray(65536)
    base[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra
    base[0xCFF0], base[0xCFF1] = 0xF0, 0xFF
    O, P = _overlays(patch, base.__getitem__, _alt(patch), ns, {})
    r = list(R)
    r[24], r[12] = 0xD000, 0xCFF0
    sim = _machine(_rw(), P(), r, ns, 'p')
    if not _run(sim, lambda x: x[24] == 0xFFF0):
        return [('setup did not return',)]
    if bytes(ns.uploaded) != patch.pats:
        f.append(('setup did not upload the car patterns', len(ns.uploaded)))
    pal, which, at = {0x00: {}, 0x10: {}, 0x20: {}}, 0, 0
    for e in ns.events:
        if e[0] != 'nr':
            continue
        if e[1] == 0x43:
            which = e[2]
        elif e[1] == 0x40:
            at = 2 * e[2]
        elif e[1] == 0x44:
            pal.setdefault(which, {})[at] = e[2]
            at += 1
        elif e[1] == 0x41:
            pal.setdefault(which, {})[at] = e[2]
            at += 2
    if bytes(pal[0x20].get(i, 0) for i in range(len(patch.sprite_palette))) != patch.sprite_palette:
        f.append(('setup did not load the sprite palette',))
    if pal[0x00].get(32) != 0xE3 or pal[0x00].get(48) != 0xE3:
        f.append(('black paper is not the see-through colour',))
    if patch.menu_picture:
        if bytes(pal[0x10].get(i, 0) for i in range(512)) != patch.menu_picture[1]:
            f.append(('setup did not load the menu picture\'s palette',))
        if ns.nr.get(0x69) != 0x80:
            f.append(('setup did not turn Layer 2 on for the menu',))
        if ns.layer2() != patch.menu_picture[0]:
            f.append(('Layer 2 does not start with the menu picture',))
    elif ns.nr.get(0x69):
        f.append(('setup turned Layer 2 on in a build without pictures',))
    if any(ns.sprite(i) for i in range(128)):
        f.append(('setup left a sprite showing',))
    if ns.nr.get(0x15) != 0x09 or ns.nr.get(0x70) != 0x10 or ns.nr.get(0x12) != L2_BANK:
        f.append(('layer order, Layer 2 mode or its bank not set',))
    return f


def negative_patch(patch):
    """Broken copy: every sprite one pixel right of its car (the sprite check must fail)."""
    import copy
    q = copy.copy(patch)
    code = bytearray(q.rom_code)
    at = code.index(bytes.fromhex('2e087ec620'))      # ld l,0x08 / ld a,(hl) / add a,32
    code[at + 4] = 33
    q.rom_code = bytes(code)
    page = bytearray(q.page)
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    q.page = bytes(page)
    return q


def unit_tests(patch, states, neg=None):
    """states from verify(collect=n): (kind, registers, 64K memory, the patched game's attributes and kept bytes). Cases the recording does not reach: every
    image and livery, one to four cars, hidden cars, the screen's edges; every picture; the text screens;
    interrupts off; the builds with an option off. neg: a broken patch that must FAIL."""
    c = collections.Counter()
    Sim = _rw()

    class Memory(bytearray):
        shadow = None                                # the patched game's attributes and kept bytes at that moment

    def one(pt, kind, R, mem, attrs=None):
        ns = NextState(pt)
        if attrs:
            ns.attr = [list(a) for a in attrs]
        return event(pt, kind, mem.__getitem__, R, ns, _alt(pt), Sim, dict(getattr(mem, 'shadow', None) or {}))

    def note(name, fl):
        if fl:
            c[name + ' FAILED!'] += 1
            c['%s: %s' % (name, fl[0][0])] += 1
        else:
            c[name + ' ok'] += 1

    by = collections.defaultdict(list)
    for kind, R, mem, shadow in states:
        by[kind].append((R, Memory(mem)))
        by[kind][-1][1].shadow = shadow
    for kind in ('draw', 'done', 'cls', 'track'):
        if not by[kind]:
            c['no %s state collected!' % kind] += 1

    # the claims the R exception and the overlay rest on
    if states:
        mem = by[states[0][0]][0][1]
        if any(mem[a] == 0xED and mem[a + 1] in (0x5F, 0x57) for a in range(0x5B00, 0xFFFF)):
            c['the game holds an LD A,R or LD A,I: R must be preserved!'] += 1
        else:
            c['no LD A,R or LD A,I in the game ok'] += 1
    for livery in range(LIVERIES):
        for image in range(IMAGES):
            pat = patch.pats[(livery * IMAGES + image) * 128:][:128]
            bare = [(k, r) for r, row in enumerate(patch.plain_rows[image]) for k in range(16)
                    if row >> (15 - k) & 1 and not (pat[(r + 4) * 8 + k // 2] >> (0 if k & 1 else 4)) & 15]
            if bare:
                c['painted car leaves the game\'s car showing (livery %d image %d)!' % (livery, image)] += 1
            else:
                c['painted car covers the game\'s car ok'] += 1

    quiet = variant(patch, sound=False)
    base = variant(quiet, backdrops=False)
    loud_base = variant(patch, backdrops=False)
    for R, mem in by['draw']:
        note('draw, engine option off', one(quiet, 'draw', R, mem)[0])
        note('draw, no pictures', one(loud_base, 'draw', R, mem)[0])
        for bad in (neg if isinstance(neg, (list, tuple)) else [neg] if neg else []):
            fl = one(bad, 'draw', R, mem)[0]
            c['negative control detected' if fl else 'negative control NOT DETECTED!'] += 1

    # the hook alone, on car records set by hand (the screen is not redrawn, so no pixel check: plain_rows off)
    for R, mem in by['done'][:2]:
        for cars in (1, 2, 3, 4):
            for heading in range(0, 24):
                for half in (0, 0x80):
                    for x, y in ((0, 0), (120, 90), (240, 184), (255, 100)):
                        m = bytearray(mem)
                        m[NCARS] = cars
                        for n in range(4):
                            rec = CARS + 0x100 * n
                            m[rec + 0x08], m[rec + 0x05] = (x + 7 * n) & 255, (y + 3 * n) & 255
                            m[rec + 0x0B], m[rec + 0x0A] = (heading + n) % 24, half
                            m[rec + 0x3F] = 4 + (n + heading) % 4
                            m[rec + 0x5F] = 0x1C if (heading + n) % 7 == 0 else 0
                            m[rec + 0x01], m[rec + 0x10] = (37 * heading + 11 * n) & 255, 0xC0 if n == heading % 4 else 0
                        note('hook on set cars', one(patch, 'done', R, m)[0])
                        note('hook on set cars, engine option off', one(quiet, 'done', R, m)[0])

    for name, pt in (('setup', patch), ('setup, no pictures', base)):
        if states:
            note(name, setup_check(pt, states[0][1]))

    # every picture, a track with none, and the same one twice (the second is not unpacked again)
    for R, mem in by['track'][:1]:
        ns = NextState(patch)
        for key in list(patch.pictures) + [0x1234] + list(patch.pictures)[:1] * 2:
            if key == MENU_KEY:
                continue
            m = bytearray(mem)
            m[0xD4B9], m[0xD4BA] = key & 255, key >> 8
            if key == 0x1234:
                ns.nr[0x69] = 0                      # the clear before a track has turned Layer 2 off
            fl = event(patch, 'track', m.__getitem__, R, ns, _alt(patch), Sim, {})[0]
            note('track picture', fl)
        note('track, no pictures', one(base, 'track', R, mem)[0])

    # the clears: before a track, and a text screen (any other caller), interrupts on and off
    for R, mem in by['cls'][:1]:
        for ret in (BEFORE_TRACK, 0xBE24, 0xC010):
            for iff in (0, 1):
                m, r = bytearray(mem), list(R)
                m[r[12]], m[r[12] + 1] = ret & 255, ret >> 8
                r[26] = iff
                attrs = [[0, 0, 0, 0x80, 0] for _ in range(128)]
                note('clear', one(patch, 'cls', r, m, attrs)[0])
                note('clear, no pictures', one(base, 'cls', r, m, attrs)[0])
        # a text screen after a race: Layer 2 holds a circuit's picture, the menu's must come back
        circuit = next(k for k in patch.pictures if k != MENU_KEY)
        ns = NextState(patch)
        m, r = bytearray(mem), list(R)
        m[0xD4B9], m[0xD4BA] = circuit & 255, circuit >> 8
        for track_R, track_mem in by['track'][:1]:
            tm = bytearray(track_mem)
            tm[0xD4B9], tm[0xD4BA] = circuit & 255, circuit >> 8
            note('race then text screen', event(patch, 'track', tm.__getitem__, track_R, ns, _alt(patch), Sim, {})[0])
        m[r[12]], m[r[12] + 1] = 0x24, 0xBE
        note('race then text screen', event(patch, 'cls', m.__getitem__, r, ns, _alt(patch), Sim, {})[0])
    return c


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    for option, value in (('publisher', 'Ace Software, 1988'), ('fix_label', 'Colour'), ('colours_label', 'Backgrounds')):
        if not getattr(a, option, None):               # only what is unset: an override on the command line stays
            setattr(a, option, value)
    say('Game      : %s' % name)
    say('Engine    : stock_car_3d (3D Stock Car Championship: sprites over the game\'s cars, painted circuits, engines)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = printer buffer, never touched in the reference RZX)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    ok = not bad

    def build(suffix, label, sound, backdrops, painted):
        nonlocal ok
        patch = StockCar3dPatch(sound=sound, backdrops=backdrops, painted=painted)
        path = os.path.join(out, name + suffix)
        conv = zt.convert(z80, path, None, True, quiet=True, patch=patch)
        wrong = check(path, z80, patch, (conv[1], conv[1] + len(conv[2])))
        data = bytearray(open(path, 'rb').read())
        if any(data[18 + b] for b in range(48, 112)) and not data[8]:
            data[8] = 1                              # "needs 2MB": the converter writes 0 whatever the banks
            open(path, 'wb').write(data)
        say('%-10s: %s  %s  boot %s' % (label, os.path.basename(path), md5(path),
                                         'OK' if not wrong else 'MISMATCH %s' % str(wrong[:3])[:200]))
        ok = ok and not wrong
        return patch, path

    # The base keeps the game's look: its own car shapes in its own colours, as sprites. Each option is one change.
    base, spr = build('_sprites.nex', 'Sprites', False, False, False)
    _, painted = build('_painted.nex', 'Painted', False, False, True)
    _, engines = build('_engines.nex', 'Engines', True, False, False)
    _, back = build('_backgrounds.nex', 'Background', False, True, False)
    _, painted_back = build('_painted_backgrounds.nex', 'Painted+bg', False, True, True)
    _, engines_back = build('_engines_backgrounds.nex', 'Engines+bg', True, True, False)
    patch, _ = build('_everything.nex', 'Everything', True, True, True)
    # Backgrounds adds banks above a 1MB Next's: the packager makes it an option offered only on a 2MB one (SET3).
    # The painted cars are a toggle so that they are offered on any Next.
    name_of = os.path.basename
    json.dump({'default': name_of(spr), 'loading': None, 'plain': name_of(plain),
               'colours': {'Backgrounds': {'default': name_of(back), 'loading': None}},
               'toggles': {'Enhanced colours': {'logic': False, 'default': name_of(painted), 'loading': None,
                                                'what': 'The four cars painted, each in its own livery',
                                                'colours': {'Backgrounds': {'default': name_of(painted_back), 'loading': None}}},
                           'Engines': {'logic': False, 'default': name_of(engines), 'loading': None,
                                       'what': 'An engine note for every car, crash and skid noise',
                                       'colours': {'Backgrounds': {'default': name_of(engines_back), 'loading': None}}}}},
              open(os.path.join(out, name + '_outputs.json'), 'w'), indent=1)
    states = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1, os.path.basename(s2)))
            r = s2
        for label, pt in (('every option', patch), ('base', base)):
            c, ex, st = verify(pt, r, stop=getattr(a, 'quick', None), collect=3)
            if pt is patch:
                states += st
            fails = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fails
            say('Verify    : %s (%s)  %d frames, draws %d, clears %d, tracks %d, %d car pixels under their sprites -> %s' % (
                os.path.basename(r), label, c['frames'], c['draw'], c['cls'], c['track'],
                c['car pixels checked under their sprites'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
            for k, v in ex.items():
                say('            %s: %s' % (k, str(v)[:200]))
    if list(a.rzx or []) and not states:
        say('Unit      : no machine state was collected from the recordings -> FAIL')
        ok = False
    if states:
        u = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        good = sum(v for k, v in u.items() if k.endswith(' ok'))
        say('Unit      : %d cases ok, negative control %d/%d -> %s' % (
            good, u['negative control detected'], u['negative control detected'] + u['negative control NOT DETECTED!'],
            'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in sorted(u.items()):
            if not k.endswith('!'):
                say('            %s: %d' % (k, v))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok

