"""Green Beret (Imagine, 1986, 48K) engine 'green_beret'. Additive module: reachable only through is_green_beret().

Game facts (games/green_beret.md): each game loop blits the scenery onto the screen (0xA9B9), then 0xA5FE erases
and plots the figures straight onto the screen, with three plotters. A figure's light pixels are the cell's PAPER,
so a figure takes the colours of the cells it crosses. Hooks (asm/green_beret_hooks.asm): the original plot code
still runs, with slot 2 mapped to a scratch page so its writes miss the ULA; the hook also writes sprites.

Verify (PLAYBOOK 6): replay the recording in the Python simulator; at each hook site run the patched code from the
same state, with the Next-side state carried across (scratch page, sprites, patterns) and the patched ULA kept apart.
0xA5FE is compared whole: all registers at its return, all memory but the screen, then the picture: patched ULA +
sprites = the original's pixels, bit for bit, in the visible window. Sky lines above 104, where the original's own
figure pixels get smeared by the in-place scroll, are counted, not failed.
"""
import collections
import hashlib
import json
import os

from . import green_beret_art as art

ROM_ORG = 0x386E
ALT_PAGE = 24
SCRPAGE = 26
OVPAGE = 27
ULAPAGE = 10
TAIL_ADDR = 0x8342          # scenery-buffer row; the copier reads it before the game writes it, so restore_tail puts it back
DRAW_SITE, FEND_SITE = 0xA38F, 0xA392
PLOT, PLOT2, SMALL = 0xA7DF, 0xA8E8, 0xAFD8
AFTER = 0xC21A
WIPE1, WIPE2 = 0x64F4, 0x64E6
MINE, MINE_END = 0xAE5D, 0xAE9E
SITES_ORIG = {DRAW_SITE: 'cdfea5', FEND_SITE: 'cd1ac2', PLOT: '3a8ea7', PLOT2: 'ed733ca1', SMALL: 'ed733ca1',
              0xA82F: 'ed7b3ca1', 0xA86D: 'ed7b3ca1', 0xA919: 'ed7b3ca1', 0xB03A: 'ed7b3ca1',
              WIPE1: '210058', WIPE2: '01ff17', MINE: 'ed733ca1', MINE_END: 'ed7b3ca1'}
SITE_SYM = {DRAW_SITE: 'e_fs', FEND_SITE: 'e_fe', PLOT: 'e_plot', PLOT2: 'e_plt2', SMALL: 'e_smal',
            0xA82F: 'e_end', 0xA86D: 'e_end', 0xA919: 'e_end', 0xB03A: 'e_end2', WIPE1: 'e_wip1', WIPE2: 'e_wip2',
            MINE: 'e_mine', MINE_END: 'e_end3'}
# Original entry bytes, comparison PC and hook label. Each site jumps to a cycle-matched replacement.
INTRO = {0xA21D: ('2182ff', 0xA22A, 'intro_on'), 0xA4AE: ('cdafa9', 0xA4C6, 'intro_off')}
INTRO_COLUMN = 0x6658
INTRO_COLUMN_END = 0x666B
INTRO_ORIG = {INTRO_COLUMN: '2af76d2322f76d3e', 0x6661: '083e09087709083d20f9',
              0xA21D: '2182ff1183ff0157003600edb0',
              0xA4AE: 'cdafa9ed5361a1cdafa9ed5363a1cdafa9ed5365a1cdafa9', 0xA9AF: '5e235623c9'}
SITE_OP = {DRAW_SITE: 0xCD, FEND_SITE: 0xCD}
INTERIORS = (0xA390, 0xA391, 0xA393, 0xA394, 0xA7E0, 0xA7E1, 0xA8E9, 0xA8EA, 0xA8EB, 0xAFD9, 0xAFDA, 0xAFDB,
             0xA830, 0xA831, 0xA832, 0xA86E, 0xA86F, 0xA870, 0xA91A, 0xA91B, 0xA91C, 0xB03B, 0xB03C, 0xB03D,
             0x64F5, 0x64F6, 0x64E7, 0x64E8, 0xAE5E, 0xAE5F, 0xAE60, 0xAE9F, 0xAEA0, 0xAEA1)
SCROLL = (0xAB18, 0xAB4E)   # the in-place scroll's LDIs: each screen byte := the next one
DEAD_STEPS = 12000          # instructions compared after a mine plot (roughly a TV frame)
WIN = (16, 239, 0, 191)
SKY = 104                   # above this line the blit does not restore the screen
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
PALETTE = [0x00, 0xFF, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4]   # slot 15 uses RGB333
RING_RGB = (109, 109, 109)  # RGB333 333, programmed by the Spectrum setup
PC, TS, SP, IFF = 24, 25, 12, 26
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR
GAME_SP = 41276
COLOUR_BANKS = tuple(range(14, 26))

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'green_beret_colours.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'green_beret.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_green_beret(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bool(sig) and bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def class_table(a=1, b=2):
    """index gggg mmmm -> [left byte, right byte]: a = body (mask 0, gfx 0), b = dark (gfx 1), 0 = clear."""
    t = bytearray(512)
    for i in range(256):
        g, m = i >> 4, i & 15
        ni = []
        for k in (8, 4, 2, 1):
            ni.append(b if g & k else (0 if m & k else a))
        t[i] = ni[0] << 4 | ni[1]
        t[256 + i] = ni[2] << 4 | ni[3]
    return bytes(t)


def page_image(a=1, b=2, prof=None):
    prof = prof or load_profile()
    p = bytearray(8192)
    code = bytes.fromhex(prof['hooks']['page'])
    if 0x19A0 + len(code) > 0x1C00:
        raise ValueError('hook page code too long')
    p[0x19A0:0x19A0 + len(code)] = code
    p[0x1C00:0x1E00] = class_table(a, b)
    p[0x1802] = 2           # frame counter: every cache entry looks idle at the start
    return bytes(p)


# ---------------------------------------------------------------------------------------------
# Images and the colour map
# ---------------------------------------------------------------------------------------------

def image_cells(gfx, kind, rows):
    """Which graphics byte each staging cell comes from: [(line, col, address, mask address or None)]."""
    out = []
    if kind == 0:
        raise ValueError('kind 0 needs image_cells0')
    if kind == 1:
        for y in range(rows):
            for k in range(2):
                col = k if not y & 1 else 1 - k
                w = gfx + 4 * y + 2 * k
                out.append((y, col, w + 1, w))
    else:
        for y in range(rows):
            for k in range(2):
                col = k if not y & 1 else 1 - k
                out.append((y, col, gfx + 2 * y + k, None))
    return out


def image_cells3(gfx, mask, rows):
    out = []
    for y in range(rows):
        for k in range(3):
            col = k if not y & 1 else 2 - k
            out.append((y, col, gfx + 3 * y + k, mask + 3 * y + k))
    return out


def image_cells0(gfx, mask, rows):
    out = []
    for y in range(rows):
        for k in range(4):
            col = k if not y & 1 else 3 - k
            out.append((y, col, gfx + 4 * y + k, mask + 4 * y + k))
    return out


def cells_of(img):
    gfx, mask, rows, kind = img
    if kind == 3:
        return image_cells3(gfx, mask, rows)
    return image_cells0(gfx, mask, rows) if kind == 0 else image_cells(gfx, kind, rows)


def images(prof=None):
    prof = prof or load_profile()
    return [tuple(x) for x in prof.get('colour_images', [])]


def colour_tables(get, cmap, prof=None):
    """Colour map -> (index page 8192 bytes, {page: 8192 bytes}, info). A plane per image with any override: per line 16
    colour bytes and 16 keep masks. An entry whose check byte is not the graphic's byte is ignored."""
    pages = {2 * b + k: bytearray(8192) for b in COLOUR_BANKS for k in (0, 1)}
    order = sorted(pages)
    idx, used, bad = [], set(), set()
    pi, off = 0, 0
    for img in images(prof):
        gfx, mask, rows, kind = img
        data = bytearray(32 * rows)
        for y in range(rows):
            data[32 * y + 16:32 * y + 32] = b'\xff' * 16
        any_ = False
        for y, col, a, _m in cells_of(img):
            key = '%04X' % a
            e = cmap.get(key)
            if not e:
                continue
            if e[0] != get(a):
                bad.add(key)
                continue
            used.add(key)
            for bit in range(8):
                o = 32 * y + 4 * col + bit // 2
                nib = 0xF0 if not bit & 1 else 0x0F
                if len(e) > 3 and e[3] & (0x80 >> bit):
                    data[o + 16] &= ~nib & 255
                    any_ = True
                elif e[2][bit]:
                    data[o + 16] &= ~nib & 255
                    data[o] |= (e[2][bit] << 4) if not bit & 1 else e[2][bit]
                    any_ = True
        if not any_:
            continue
        if off + len(data) > 8192:
            pi, off = pi + 1, 0
            if pi >= len(order):
                raise ValueError('colour tables need more than %d pages' % len(order))
        pages[order[pi]][off:off + len(data)] = data
        a = 0xC000 + off
        idx.append(bytes((gfx & 255, gfx >> 8, order[pi], a & 255, a >> 8)))
        off += len(data)
    index = bytearray(8192)
    index[0:2] = len(idx).to_bytes(2, 'little')
    b = b''.join(idx)
    index[2:2 + len(b)] = b
    info = {'images with colours': len(idx), 'map entries used': len(used),
            'map entries ignored (check byte differs)': len(bad),
            'map entries for no known image': len(set(cmap) - used - bad)}
    return bytes(index), pages, info


TRIM_KINDS = (0,)          # the figure plotter 0xA78F: player, enemies, dogs, explosions (games/green_beret.md "Edge")
TRIM_MIN_LINES = 12        # figures; not the 8-line weapons the player carries (0xCD54 / 0xCE54): the white bar between
                           # 0xCE54's two ends is the tube itself (mask only, no ink), not an edge


def image_pixels(get, img):
    """{(x, line): (gfx bit, mask bit)} of one image, x = cell column * 8 + bit (cells_of's columns)."""
    out = {}
    for y, col, a, m in cells_of(img):
        g = get(a)
        mm = get(m) if m is not None else 0xFF
        for b in range(8):
            out[(col * 8 + b, y)] = (g >> (7 - b) & 1, mm >> (7 - b) & 1)
    return out


def trim_pixels(get, img):
    """The edge rule (owner, 2026-11-06: "the white edges on the enemy need to be trimmed back closer to the character's
    outline"). The white body a figure shows is the original's mask, which shows the cell's paper; on several enemies
    it reaches 2-4 px past the drawn outline. A pixel that is not dark, lies OUTSIDE the figure (4-connected to the
    image's edge through pixels that are not dark: the dual of the 8-connected outline) is made transparent. Body
    inside the outline stays; 1.3 (owner, KS3 2026-11-27, no white outlines) also drops the 1 px white ring 1.0 kept
    outside it, so the black outline meets the scenery. Depends on the graphics bytes only, never the mask: one rule
    per graphics address, whatever mask a call passes. -> set of (x, line) as image_pixels."""
    if img[3] not in TRIM_KINDS or img[2] < TRIM_MIN_LINES:
        return set()
    px = image_pixels(get, img)
    return exterior(px).intersection(px)


def exterior(px):
    """Four-connected outside, including a one-pixel margin around the source rectangle."""
    w = 1 + max(x for x, _ in px)
    h = 1 + max(y for _, y in px)
    seen = {(-1, -1)}
    todo = list(seen)
    while todo:
        x, y = todo.pop()
        for u, v in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            q = u, v
            if -1 <= u <= w and -1 <= v <= h and q not in seen and not px.get(q, (0, 1))[0]:
                seen.add(q)
                todo.append(q)
    return seen


def ring_pixels(get, img):
    px = image_pixels(get, img)
    neighbours = {(x + dx, y + dy) for (x, y), (ink, _) in px.items() if ink
                  for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    return exterior(px) & neighbours


def trims_body(get, img):
    """trim_pixels when it takes away any body pixel this image shows with its own mask, else the empty set (no plane:
    the rule changes nothing there, e.g. the player's tight edge)."""
    cut = trim_pixels(get, img)
    if not cut:
        return cut
    px = image_pixels(get, img)
    return cut if any(px[p] == (0, 0) for p in cut) else set()


def trimmed_map(get, cmap, prof=None):
    """The colour map the build uses: the edge rule's transparent pixels under the painted map (a painted pixel wins).
    -> (map, number of graphics bytes with a trimmed pixel)."""
    out = {k: list(v) for k, v in cmap.items()}
    n = 0
    for img in images(prof):
        cut = trims_body(get, img)
        if not cut:
            continue
        for y, col, a, _m in cells_of(img):
            bits = 0
            for b in range(8):
                if (col * 8 + b, y) in cut:
                    bits |= 0x80 >> b
            if not bits:
                continue
            key = '%04X' % a
            e = out.get(key)
            if e is None:
                out[key] = [get(a), 'g', [0] * 8, bits]
            elif e[0] == get(a):
                free = 0
                for b in range(8):
                    if not e[2][b]:
                        free |= 0x80 >> b
                t = (e[3] if len(e) > 3 else 0) | (bits & free)
                out[key] = [e[0], e[1], list(e[2]), t]
            n += 1
    return out, n


ARCADE_COLOURS = 'docs/profiles/green_beret_arcade_colours.json'


def load_colours(path=None, banked=False):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    default = os.path.join(_HERE, '..', ARCADE_COLOURS) if banked else COLOURS
    return cs.load(path or build_colours_path(default))


def colour_inputs_md5(get, prof=None):
    seen = set()
    for img in images(prof):
        for y, col, a, m in cells_of(img):
            seen.add(a)
            if m is not None:
                seen.add(m)
    return hashlib.md5(bytes(get(a) for a in sorted(seen))).hexdigest(), len(seen)


def colour_identity(peek, prof=None):
    prof = prof or load_profile()
    geo = hashlib.md5(json.dumps(prof.get('colour_images', [])).encode()).hexdigest()
    return {'schema': 1, 'game': 'green_beret', 'engine': 'green_beret', 'keys': 'gb-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': colour_inputs_md5(peek, prof)[0], 'geometry': geo}


# ---------------------------------------------------------------------------------------------
# The patches
# ---------------------------------------------------------------------------------------------

def restore_tail(p, s):
    """The start-up tail puts the snapshot's bytes back before the game starts. TAIL_ADDR is a scenery-buffer row that
    the screen copier (0xA9C7) reads before the game writes it, at the start of play (nextboot.rom_paths: 0 to 26
    frames of the tail's bytes on screen). As Alien 8's: the tail jumps to code in the alt ROM image's free span after
    the register block, which copies the backup over the tail and runs the tail's register restore again, so no game
    memory is assumed dead. Call before extra_banks takes p.page; idempotent (check() applies a copy again)."""
    from . import z80tonex as zt
    from .build import rom48
    tail, _, restore, _ = zt.build_tail(s, p.tail_addr, p.slot1, True)
    backup = p.slot1[1] + 20
    entry = backup + len(tail)
    code = (b'\xF3\x21' + zt.w16(backup) + b'\x11' + zt.w16(p.tail_addr) + b'\x01' + zt.w16(len(tail)) + b'\xED\xB0'
            + tail[restore:])
    end = entry + len(code)
    if end > 0x3D00 or set(rom48()[backup:end]) != {0xFF}:
        raise ValueError('tail restore 0x%04X-0x%04X is not in the 48K ROM\'s free span' % (backup, end))
    page = bytearray(p.page)
    page[backup - 0x2000:entry - 0x2000] = bytes(s.read(p.tail_addr + i) for i in range(len(tail)))
    page[entry - 0x2000:end - 0x2000] = code
    p.page = bytes(page)
    p.altrom = (p.altrom[0], end)
    p.original_pc, p.tail_restore_bytes, s.pc = s.pc, len(tail), entry


LOADING_SCREEN = 'green_beret-loading.scr'   # the tape's loading screen, beside the snapshot (6912 bytes)


def start_screen(snap, screen):
    """The tape's loading screen in screen memory at the start (owner, KS3 2026-11-27): the original menu shows over
    it, but the [a2][a2] snapshot was saved with it gone (black, the tape loader's bytes in the top row, never run
    again: the game starts at 0x8273)."""
    if screen is not None:
        if len(screen) != 6912:
            raise ValueError('the loading screen must be 6912 bytes')
        snap.banks[5] = bytes(screen) + bytes(snap.banks[5][6912:])


class PlainPatch:
    """The plain .nex: no hooks. The game keeps code at 0x5B00, so the stub restores the printer buffer. The alt ROM
    (Sinclair's ROM) holds only the register block and restore_tail's code."""
    name = 'Green Beret plain conversion'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = True
    keep_printer_buffer = True
    tail_addr = TAIL_ADDR
    sites = []

    def __init__(self, screen=None):
        from .build import rom48
        self.screen = screen
        self.page = bytes(rom48()[0x2000:0x4000])
        self.slot1 = (ALT_PAGE, ROM_ORG)
        self.altrom = (ROM_ORG, ROM_ORG + 20)
        self.extra_banks = {12: self.page + bytes(8192)}

    def apply(self, snap):
        start_screen(snap, self.screen)
        restore_tail(self, snap)
        self.extra_banks = {12: self.page + bytes(8192)}


class GreenBeretPatch:
    name = 'Green Beret figures -> hardware sprites (altrom hooks, plots into a scratch page at slot 2)'

    def __init__(self, prof=None, rom_code=None, colours=None, trim=True, screen=None, enhanced=False):
        self.enhanced = enhanced
        self.trim = trim
        self.screen = screen
        self.trims = {}
        self.prof = prof or load_profile()
        if enhanced:
            self.prof = dict(self.prof, hooks=self.prof['arcade_hooks'])
        self.colours = load_colours(banked=enhanced) if colours is None else colours
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        if enhanced:
            self.rom_code += bytes.fromhex(h['intro'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = self.syms['intro_setup'] if enhanced else 0xD000
        if enhanced:
            self.stub_extra += art.palette_data()
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.keep_printer_buffer = True
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
            self.sites.append((a, bytes.fromhex(old), bytes([SITE_OP.get(a, 0xC3)]) +
                               self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        self.extra_banks = {}
        if enhanced:
            self.sites.append((INTRO_COLUMN, bytes.fromhex('2af76d'), b'\xc3' + self.syms['intro_column'].to_bytes(2, 'little')))
            for site, (old, _, label) in INTRO.items():
                self.sites.append((site, bytes.fromhex(old), b'\xc3' + self.syms[label].to_bytes(2, 'little')))
        self.scratch0 = page_image(prof=self.prof)
        self.index = bytes(8192)
        self.colour_pages = {}
        self.cinfo = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Green Beret patch expects the 48K snapshot')
        if self.enhanced:
            code = snap.banks[5] + snap.banks[2] + snap.banks[0]
            for addr, old in INTRO_ORIG.items():
                data = bytes.fromhex(old)
                if code[addr - 0x4000:addr - 0x4000 + len(data)] != data:
                    raise ValueError('unexpected intro routine at %04X' % addr)
        start_screen(snap, self.screen)
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        restore_tail(self, snap)
        self.prepare(lambda a: ram[a - 0x4000] if a >= 0x4000 else 0)

    def prepare(self, peek):
        self.peek = peek
        if self.enhanced:
            from .green_beret_intro import palettes, tile_data
            h = self.prof['hooks']
            data = tile_data(peek)
            self.stub_extra = (bytes.fromhex(h['setup']) + art.palette_data() + bytes.fromhex(h['introsetup'])
                               + palettes() + len(data).to_bytes(2, 'little') + data)
            cmap, n = trimmed_map(peek, self.colours, self.prof) if self.trim else (self.colours, 0)
            self.index, self.colour_pages, self.cinfo = colour_tables(peek, cmap, self.prof)
            table = bytearray(4096)
            for gfx, _, _, _ in images(self.prof):
                table[gfx >> 4] = art.group(gfx) << 4
            self.index = self.index[:4096] + table
            self.cinfo['graphics bytes with trimmed edge pixels'] = n
        else:
            self.index, self.colour_pages, self.cinfo = ring_tables(peek, self.colours, self.prof, self.trim)
        self.trims = {}
        if self.trim:
            for img in images(self.prof):
                cut = trims_body(peek, img)
                if cut:
                    self.trims[img[0]] = (img, frozenset(cut), bytes(peek(a) for _y, _c, a, _m in cells_of(img)))
        self.extra_banks = {12: self.page + bytes(8192), 13: self.scratch0 + self.index}
        for b in COLOUR_BANKS:
            self.extra_banks[b] = bytes(self.colour_pages[2 * b]) + bytes(self.colour_pages[2 * b + 1])


# ---------------------------------------------------------------------------------------------
# Next-side state
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, patch=None):
        self.nr = {7: 0, 0x52: ULAPAGE, 0x56: 0, 0x34: 0}
        self.pages = dict(getattr(patch, 'colour_pages', {}) or {}) if patch is not None else {}
        if patch is not None:
            self.pages[OVPAGE] = patch.index
        self.enhanced = bool(getattr(patch, "enhanced", False))
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.scratch = bytearray(8192)
        if patch is not None:
            self.scratch[:len(patch.scratch0)] = patch.scratch0
        self.ptr = 0
        self.uploads = 0
        self.fast = self.slow = 0
        self.mark = 0
        self.R = None
        self.sel = 0

    def nextreg(self, reg, val):
        if reg == 7 and self.R is not None:
            t = self.R[TS]
            if val & 3 == 3:
                self.slow += t - self.mark
            else:
                self.fast += t - self.mark
            self.mark = t
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr[0x34] & 0x7F][reg - 0x35] = val

    def read_port(self, regs, port):
        if port & 0xFFFF == 0x253B:
            v = self.nr.get(self.sel, 0)
            return (v & 3) << 4 | (v & 3) if self.sel == 7 else v
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if port & 0xFFFF == 0x243B:
            self.sel = value
        elif port & 0xFFFF == 0x303B:
            self.ptr = (value & 0x3F) * 256 + (128 if value & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.ptr & 0x3FFF] = value
            self.ptr += 1
            self.uploads += 1

    def composite(self):
        """{(x, y): palette index} of the visible sprites, in slot order, inside the clip window."""
        out = {}
        pat = self.pat
        for a in self.attr:
            if not a[3] & 0x80:
                continue
            x0 = a[0] + (a[2] & 1) * 256 - 32
            y0 = a[1] + (a[4] & 1) * 256 - 32
            base = (a[3] & 0x3F) * 256 + (128 if a[4] & 0x40 else 0)
            for j in range(16):
                y = y0 + j
                if not WIN[2] <= y <= WIN[3]:
                    continue
                for k in range(8):
                    b = pat[base + j * 8 + k]
                    if b:
                        x = x0 + 2 * k
                        if b >> 4 and WIN[0] <= x <= WIN[1]:
                            out[(x, y)] = (a[2] & 0xF0) | (b >> 4)
                        if b & 15 and WIN[0] <= x + 1 <= WIN[1]:
                            out[(x + 1, y)] = (a[2] & 0xF0) | (b & 15)
        return out


class Overlay:
    """Patched machine's memory: alt ROM, slot 2 (scratch or the patched ULA), slot 6 pages, written bytes, sites."""

    def __init__(self, patch, ns, ps, alt):
        self.psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
        self.ns, self.ps, self.alt = ns, ps, alt
        self.ov = {}
        self.get = None

    def __getitem__(self, a):
        if a < 0x4000:
            return self.alt[a]
        ns = self.ns
        if a < 0x6000:
            if ns.nr[0x52] == SCRPAGE:
                return ns.scratch[a - 0x4000]
            if a < 0x5800:
                return self.ps[a - 0x4000]
        elif 0xC000 <= a < 0xE000 and ns.nr[0x56]:
            return ns.pages[ns.nr[0x56]][a - 0xC000]
        v = self.ov.get(a)
        if v is not None:
            return v
        v = self.psite.get(a)
        if v is not None:
            return v
        return self.get(a)

    def __setitem__(self, a, v):
        if a < 0x4000:
            return
        if a < 0x6000:
            if self.ns.nr[0x52] == SCRPAGE:
                self.ns.scratch[a - 0x4000] = v
                return
            if a < 0x5800:
                self.ps[a - 0x4000] = v
                return
        self.ov[a] = v

    def __len__(self):
        return 65536


class HookRunner:
    """One simulator kept for the whole replay (building one per event costs ~3 ms)."""

    def __init__(self, patch, ns, ps):
        from skoolkit.simulator import Simulator
        from . import z80n
        from .build import rom48
        alt = bytearray(rom48())
        alt[0x2000:0x4000] = patch.page
        self.m = Overlay(patch, ns, ps, alt)
        self.sim = Simulator(self.m, {})
        self.sim.set_tracer(ns)
        z80n.install(self.sim, ns.nextreg)
        self.ns = ns

    def run(self, get, regs, stop, limit=400000):
        """Run patched code from regs until PC is in stop. -> (registers, memory written, ok)."""
        m, sim, ns = self.m, self.sim, self.ns
        m.get, m.ov = get, {}
        R = sim.registers
        R[:] = type(R)(R.typecode, regs) if hasattr(R, 'typecode') else regs
        ops, n = sim.opcodes, 0
        ns.R, ns.mark = R, R[TS]
        while R[PC] not in stop:
            ops[m[R[PC]]]()
            n += 1
            if n > limit:
                ns.R = None
                return list(R), m.ov, False
        ns.R = None
        return list(R), m.ov, True


def scr_addr(col, y):
    return 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col


def addr_xy(a):
    return a & 31, ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)


def _png(mem_get, ps, ns, path):
    from PIL import Image
    n = [(0, 0, 0), (0, 0, 192), (192, 0, 0), (192, 0, 192), (0, 192, 0), (0, 192, 192), (192, 192, 0), (192, 192, 192)]
    b = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]

    def ula(px_get):
        im = Image.new('RGB', (256, 192))
        px = im.load()
        for y in range(192):
            for col in range(32):
                v = px_get(scr_addr(col, y))
                at = mem_get(0x5800 + (y >> 3) * 32 + col)
                tab = b if at & 0x40 else n
                ink, paper = tab[at & 7], tab[at >> 3 & 7]
                for k in range(8):
                    px[col * 8 + k, y] = ink if v >> (7 - k) & 1 else paper
        return im
    left = ula(mem_get)
    right = ula(lambda a: ps[a - 0x4000])
    rp = right.load()
    for (x, y), c in ns.composite().items():
        if ns.enhanced:
            rp[x, y] = art.RGB[c >> 4][c & 15]
            continue
        if c == 15:
            rp[x, y] = RING_RGB
            continue
        v = PALETTE[c]
        rp[x, y] = ((v >> 5) * 255 // 7, ((v >> 2) & 7) * 255 // 7, (v & 3) * 85)
    sh = Image.new('RGB', (2 * 256 + 8, 192), (64, 64, 64))
    sh.paste(left, (0, 0))
    sh.paste(right, (264, 0))
    sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save(path)


# ---------------------------------------------------------------------------------------------
# The replay
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None, shots=None):
    """Replay the RZX (original game). shots: {frame: png path}. -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    has = {a for a, old, new in patch.sites}
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    ns = NextState(patch)
    ps = bytearray(0x1800)
    hr = HookRunner(patch, ns, ps)
    st = {'frame': 0, 'on': False, 'draw': None, 'small': None, 'fe': None, 'wipe': None}
    owrites = {}
    cnt = collections.Counter()
    WATCH = set(SITES_ORIG) | set(INTERIORS) | {AFTER, 0x64E9, 0x64F7, 0xB03E}
    if patch.enhanced:
        WATCH.update((INTRO_COLUMN, INTRO_COLUMN_END, INTRO_COLUMN + 1, INTRO_COLUMN + 2))
        WATCH.update(INTRO)
        WATCH.update(target for _, target, _ in INTRO.values())
        WATCH.update(a + offset for a in INTRO for offset in (1, 2))
    states = []
    shots = dict(shots or {})
    regs_of = {}
    holes = set()
    wraps = set()
    trims = set()
    trim_at = getattr(patch, 'trims', {}) or {}
    known0 = {i[0] for i in images(getattr(patch, 'prof', None)) if i[3] == 0}

    catalogue = {img[0]: img for img in images(patch.prof)}
    reference = {img: expected_pixels(patch.peek, img, patch.colours, patch.enhanced) for img in catalogue.values()}
    frame_pixels, source_pixels = {}, {}

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['on'] and type(a) is int:
                if a in site_bytes:
                    fail('game wrote a patch site', (a,))
                if 0x4000 <= a < 0x5800:
                    if st['draw'] is None and st['small'] is None:
                        pc = regs_of['R'][PC]
                        if SCROLL[0] <= pc <= SCROLL[1] and a < 0x57FF:
                            ps[a - 0x4000] = ps[a - 0x4000 + 1]
                            c['scroll bytes'] += 1
                        else:
                            ps[a - 0x4000] = v
                elif st['draw'] is not None and a not in owrites:
                    owrites[a] = G(s, a)
            S(s, a, v)

    def check_regs(kind, R, Rp, skip=()):
        for i in CMP:
            if R[i] != Rp[i] and i not in skip:
                fail('%s: register %d differs' % (kind, i), (R[i], Rp[i], R[PC]))

    def check_mapped(kind):
        if ns.nr[0x52] != ULAPAGE or ns.nr.get(7, 0) != 0 or ns.nr[0x56]:
            fail('%s: left slot 2, slot 6 or the speed changed' % kind, (ns.nr[0x52], ns.nr.get(7), ns.nr[0x56]))
            ns.nr[0x52], ns.nr[7], ns.nr[0x56] = ULAPAGE, 0, 0

    def dead_af(R1, Rp, mem):
        base = list(mem)
        res = []
        for r in (R1, [Rp[i] if i in (16, 17) else R1[i] for i in range(len(R1))]):
            m = list(base)
            s2 = Simulator(m, {})
            s2.registers[:] = type(s2.registers)(s2.registers.typecode, r) if hasattr(s2.registers, 'typecode') else r
            tr = NextState()
            s2.set_tracer(tr)
            ops2, RR = s2.opcodes, s2.registers
            for _ in range(DEAD_STEPS):
                ops2[m[RR[PC]]]()
            res.append((m, list(RR)))
        (m1, r1), (m2, r2) = res
        return m1 == m2 and all(r1[i] == r2[i] for i in CMP if i not in (16, 17))

    def picture(get, mem):
        actual = ns.composite()
        if actual != frame_pixels:
            fail('sprite composite differs from figure rasters',
                 (len(actual.keys() ^ frame_pixels.keys()), next((p for p in frame_pixels if actual.get(p) != frame_pixels[p]), None)))
        c['figure pixels checked in play'] += len(frame_pixels)
        # Compare the game's original ink/body classes to the ULA, independently of display colours.
        comp = source_pixels
        o = bytes(mem[0x4000:0x5800])
        cover = {scr_addr(x >> 3, y) - 0x4000 for x, y in comp}
        diff = [i for i in range(0x1800) if o[i] != ps[i]]
        npx = 0
        for i in cover.union(diff):
            ob, pb = o[i], ps[i]
            col, y = addr_xy(0x4000 + i)
            if 0x4000 + i in wraps:
                if ob != pb:
                    c['margin-wrap bytes: a figure at column 29+ leaks to the far side (original only)'] += 1
                continue
            for k in range(8):
                x = col * 8 + k
                if not (WIN[0] <= x <= WIN[1]):
                    continue
                bit = 7 - k
                oo, pp = (ob >> bit) & 1, (pb >> bit) & 1
                cl = comp.get((x, y))
                npx += 1
                if (x, y) in trims and not oo and (cl is None and pp or cl == 2):
                    # the edge rule: the original's mask erased this pixel (paper); the trimmed sprite shows what
                    # is under it (scenery, or a figure behind)
                    c['trimmed edge: shows the scenery or a figure behind (the original erased it)'] += 1
                elif cl == 2:
                    if not oo:
                        if y < SKY:
                            c['sky: dark sprite pixel the original lost'] += 1
                        elif (x, y) in holes:
                            c['dark pixels another small object erases in the original'] += 1
                        else:
                            fail('dark pixel the original has clear', (x, y))
                elif cl == 1:
                    if oo:
                        if y < SKY and pp:
                            c['sky: body covers a scenery pixel (OR path: the original has no mask there)'] += 1
                        elif y < SKY:
                            c['sky: body covers a smeared pixel'] += 1
                        else:
                            fail('body pixel the original has set', (x, y))
                    at = get(0x5800 + (y >> 3) * 32 + col)
                    if (at >> 3) & 15 != 15:
                        c['body pixels the original showed in another colour'] += 1
                    else:
                        c['body pixels the original showed in this colour'] += 1
                elif cl is None and oo != pp:
                    if y < SKY:
                        c['sky: pixels the original smears or trails, build has not'] += 1
                    elif not oo and (x, y) in holes:
                        c['holes the small plotter erases in fresh scenery (original only)'] += 1
                    else:
                        fail('picture differs', (x, y, oo, pp))
                elif cl is not None and cl > 2:
                    c['painted pixels (colour not modelled by the picture check)'] += 1
        c['picture pixels compared'] += npx
        c['sprite pixels shown'] += len(comp)
        if shots:
            for f in sorted(shots):
                if st['frame'] >= f:
                    _png(get, ps, ns, shots.pop(f))
                    c['shots'] += 1
                break

    def event(pc, R, mem, get):
        if patch.enhanced and pc in INTRO:
            _, target, label = INTRO[pc]
            rp, writes, ok = hr.run(get, list(R), {target})
            if not ok:
                fail(label + ' control flow')
            expected = (0x22, 0xA0) if label == 'intro_on' else (0x20, 0)
            if (ns.nr.get(0x43), ns.nr.get(0x6B)) != expected:
                fail(label + ' display registers')
            st['intro_regs'] = target, rp, dict(writes)
            c[label] += 1
        elif patch.enhanced and pc == INTRO_COLUMN:
            right = 19 + 4 * ((get(0x6DF7) + 1) & 31)
            rp, writes, ok = hr.run(get, list(R), {INTRO_COLUMN_END})
            if not ok or ns.nr.get(0x1B) != right:
                fail('intro reveal column')
            st['intro_regs'] = INTRO_COLUMN_END, rp, dict(writes)
            c['intro columns'] += 1
        elif patch.enhanced and st.get('intro_regs') and pc == st['intro_regs'][0]:
            _, rp, writes = st.pop('intro_regs')
            check_regs('intro transition', R, rp)
            if R[TS] != rp[TS] or any(get(a) != v for a, v in writes.items()):
                fail('intro transition timing or memory')
        if pc == DRAW_SITE and pc in has:
            if patch.enhanced and (ns.nr.get(0x6B, 0) or ns.nr.get(0x43, 0x20) != 0x20):
                fail('intro colours in gameplay')
            c['draw'] += 1
            if R[IFF]:
                c['draw with interrupts on'] += 1
            if collect and c['collected'] < collect:
                c['collected'] += 1
                states.append(('draw', list(R), bytes(G(mem, a) for a in range(65536))))
            u0, pl0 = ns.uploads, ()
            ns.fast = ns.slow = 0
            Rp, ov, ok = hr.run(get, list(R), {FEND_SITE})
            if not ok:
                fail('draw: patched code did not return')
            st['draw'] = (Rp, dict(ov), R[TS])
            owrites.clear()
            if ns.uploads != u0:
                c['draws with uploads'] += 1
            c['pattern bytes uploaded'] += ns.uploads - u0
            c['T hook 28MHz'] += ns.fast
            check_mapped('draw')
        elif pc == FEND_SITE:
            if st['draw'] is None:
                if pc in has:
                    fail('frame end without a frame start')
                return
            Rp, ov, t0 = st['draw']
            st['draw'] = None
            ax = st['ax'] = [i for i in (16, 17) if R[i] != Rp[i]]
            if ax:
                # the mine plotter's last read of the screen stays in AF'. Prove it dead: two runs from here,
                # one with the patched AF', must match in all registers but AF' and all memory
                c['AF\' differs after a mine plot'] += 1
                if not dead_af(list(R), Rp, mem):
                    fail('AF\' is used after a mine plot')
            check_regs('draw', R, Rp, ax)
            for a in set(ov) | set(owrites):
                if 0x4000 <= a < 0x5800 or a in site_bytes:
                    continue
                pre = owrites.get(a, G(mem, a))
                if ov.get(a, pre) != G(mem, a) and not (R[SP] - 64 <= a < R[SP]):
                    fail('draw: memory differs', (a, ov.get(a, pre), G(mem, a)))
            if pc in has:
                Rp2, ov2, ok = hr.run(get, list(R), {AFTER})
                if not ok:
                    fail('frame end: patched code did not reach the next routine')
                for a in ov2:
                    if not (R[SP] - 64 <= a < R[SP]):
                        fail('frame end: hook wrote game memory', (a, ov2[a]))
                st['fe'] = Rp2
                check_mapped('frame end')
                picture(get, mem)
                c['frame end'] += 1
                frame_pixels.clear()
                source_pixels.clear()
                holes.clear()
                wraps.clear()
                trims.clear()
        elif pc == AFTER and st['fe'] is not None:
            check_regs('frame end', R, st['fe'], st.get('ax') or ())
            st['fe'] = None
        elif pc in (WIPE1, WIPE2) and pc in has:
            if patch.enhanced and (ns.nr.get(0x6B, 0) or ns.nr.get(0x43, 0x20) != 0x20):
                fail('intro colours at screen wipe')
            c['wipe'] += 1
            nx = pc + 3
            Rp, ov, ok = hr.run(get, list(R), {nx})
            if not ok:
                fail('wipe: patched code did not continue')
            st['wipe'] = (nx, Rp)
            check_mapped('wipe')
            if any(a[3] & 0x80 for a in ns.attr):
                fail('sprites on show after a wipe')
        elif pc in (0x64E9, 0x64F7) and st['wipe'] is not None and st['wipe'][0] == pc:
            check_regs('wipe', R, st['wipe'][1])
            st['wipe'] = None
        elif pc == SMALL and st['draw'] is None and pc in has:
            # 0xAFA5 from 0xBDBB, outside the draw pass: no sprite, screen writes go to the scratch page
            c['small outside the draw pass'] += 1
            Rp, ov, ok = hr.run(get, list(R), {0xB03E})
            if not ok:
                fail('small: patched code did not return')
            st['small'] = Rp
            check_mapped('small')
        elif pc == 0xB03E and st['small'] is not None:
            check_regs('small', R, st['small'])
            st['small'] = None
        if st['draw'] is not None and pc in (PLOT, PLOT2, SMALL, MINE):
            if pc == PLOT:
                addr, screen = R[SP], R[6] << 8 | R[7]
            elif pc == PLOT2:
                addr, screen = R[6] << 8 | R[7], R[4] << 8 | R[5]
            elif pc == SMALL:
                addr, screen = R[22] << 8 | R[23], R[20] << 8 | R[21]
            else:
                addr, screen = R[6] << 8 | R[7], scr_addr((R[3] >> 3) & 31, 162)
            img = catalogue.get(addr)
            if img is None:
                fail('unlisted plot image', (pc, addr))
            else:
                col, y = addr_xy(screen)
                base, painted = reference[img]
                source_pixels.update(place(base, col, y))
                frame_pixels.update(place(painted, col, y))
        if st['draw'] is not None or pc in has:
            if pc == PLOT:
                c['plot'] += 1
                tr = trim_at.get(R[SP])
                if tr is not None:
                    img, cut, gbytes = tr
                    if img[1] != (R[2] << 8 | R[3]) or img[2] != 2 * R[16]:
                        c['plot of a trimmed graphic with another mask or height'] += 1
                    if bytes(get(a) for _y, _c, a, _m in cells_of(img)) != gbytes:
                        fail('graphics changed since the build (edge rule stale)', (R[SP],))
                    col, y0 = addr_xy(R[6] << 8 | R[7])
                    for xi, ln in cut:
                        trims.add((col * 8 + xi, y0 + ln))
                    c['plots with trimmed edge pixels'] += 1
                elif R[SP] not in known0:
                    c['plots of a graphic not in the profile (no edge rule)!'] += 1
                if R[7] & 31 >= 29:
                    col, y = addr_xy(R[6] << 8 | R[7])
                    for ln in range(2 * R[16]):
                        base = scr_addr(col, y + ln)
                        for k in range(4):
                            if col + k > 31:
                                wraps.add((base & 0xFF00) | ((base + k) & 255))
            elif pc == PLOT2:
                c['plot2'] += 1
            elif pc == SMALL:
                c['small'] += 1
                old = R[2] << 8 | R[3]
                if old >= 0x4000:
                    gp = R[6] << 8 | R[7]
                    col, y = addr_xy(old)
                    for ln, cols in enumerate(((0, 1), (1, 0), (0, 1))):
                        for k, cc in enumerate(cols):
                            v = get((gp + 2 * ln + k) & 0xFFFF)
                            for b in range(8):
                                if v >> (7 - b) & 1:
                                    holes.add(((col + cc) * 8 + b, y + ln))
            elif pc == MINE:
                c['mine'] += 1
            elif pc in (0xA82F, 0xA86D):
                c['plot end %04X' % pc] += 1

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            regs_of['R'] = R
            get = lambda a: G(mem, a)
            for a in range(0x1800):
                ps[a] = G(mem, 0x4000 + a)

            def mk(fn):
                def g():
                    pc = R[PC]
                    if pc in WATCH:
                        cnt[pc] += 1
                        event(pc, R, mem, get)
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
    for a in (*INTERIORS, *(a + k for a in (*INTRO, INTRO_COLUMN) if patch.enhanced for k in (1, 2))):
        if cnt[a]:
            c['jump into a patched instruction (%04X)!' % a] += 1
    for k in ('draw', 'plot', 'frame end'):
        if not c[k]:
            c['hook %s never ran!' % k] += 1
    for a in SITES_ORIG:
        if cnt[a] and a not in has:
            c['site %04X reached, its hook is not in this build!' % a] += 1
    c['frames'] = st['frame']
    for a in sorted(SITES_ORIG):
        c['site %04X runs' % a] = cnt[a]
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit cases: what the recordings may not reach
# ---------------------------------------------------------------------------------------------

def _case_regs(R0, site, hl=None, de=None, bc=None, sp=None, xa=None, xhl=None, xde=None):
    R = list(R0)
    R[PC] = site
    if hl is not None:
        R[6], R[7] = hl >> 8, hl & 255
    if de is not None:
        R[4], R[5] = de >> 8, de & 255
    if bc is not None:
        R[2], R[3] = bc >> 8, bc & 255
    if sp is not None:
        R[SP] = sp
    if xa is not None:
        R[16] = xa
    if xhl is not None:
        R[22], R[23] = xhl >> 8, xhl & 255
    if xde is not None:
        R[20], R[21] = xde >> 8, xde & 255
    return R


def expected_pixels(get, img, colours, enhanced):
    """Reference raster in source coordinates. Flood the padded bitmap from its corner and dilate the ink."""
    from PIL import Image, ImageDraw, ImageFilter
    raw = image_pixels(get, img)
    w, h = max(x for x, _ in raw) + 1, img[2]
    ink = Image.new('L', (w + 2, h + 2))
    for (x, y), (black, _) in raw.items():
        if black:
            ink.putpixel((x + 1, y + 1), 255)
    outside = ink.copy()
    ImageDraw.floodfill(outside, (0, 0), 1)
    dilated = ink.filter(ImageFilter.MaxFilter(3))
    base, shown = {}, {}
    for (x, y), (black, mask) in raw.items():
        value = 2 if black else 0 if mask else 1
        if img[3] == 0 and h >= 12 and outside.getpixel((x + 1, y + 1)) == 1:
            value = 0
        if value:
            base[x, y] = value
    shown.update(base)
    if not enhanced:
        for y in range(-1, h + 1):
            for x in range(-1, w + 1):
                p = x + 1, y + 1
                if outside.getpixel(p) == 1 and dilated.getpixel(p):
                    shown[x, y] = 15
    def paint(pos, e, bit, check):
        if e and e[0] == check:
            if len(e) > 3 and e[3] & (128 >> bit):
                shown.pop(pos, None)
            elif e[2][bit]:
                shown[pos] = e[2][bit]
    for y, col, a, _ in cells_of(img):
        for bit in range(8):
            paint((col*8 + bit, y), colours.get('%04X' % a), bit, get(a))
    if not enhanced:
        for x, y in shown.keys() - raw.keys():
            paint((x, y), colours.get('%04X:rim:%d:%d' % (img[0], y, x//8)), x%8, 0)
    group = art.group(img[0]) << 4 if enhanced else 0
    return base, {(x, y): group | value for (x, y), value in shown.items()}


def place(raster, col, y):
    return {(col*8 + x, y + row): value for (x, row), value in raster.items()
            if WIN[0] <= col*8 + x <= WIN[1] and WIN[2] <= y + row <= WIN[3]}


def unit_tests(patch, states, neg=None):
    """Geometry of all three plotters at the screen's edges, the cache, hide, colours, slot guards, the tail."""
    c = collections.Counter()

    def fail(k):
        c[k + '!'] += 1
    state = next((s for s in states if s[0] == 'draw'), None)
    if state is None:
        c['no captured draw state!'] += 1
        return c
    R0, mem = state[1], state[2]
    get = lambda a: mem[a & 0xFFFF]
    imgs = images(patch.prof) or [(0x8800, 0x8980, 24, 0)]
    k0 = [i for i in imgs if i[3] == 0]
    k1 = [i for i in imgs if i[3] == 1]
    k2 = [i for i in imgs if i[3] == 2]

    def start(q=None):
        q = q or patch
        ns = NextState(q)
        ps = bytearray(mem[0x4000:0x5800])
        hr = HookRunner(q, ns, ps)
        Rp, ov, ok = hr.run(get, _case_regs(R0, DRAW_SITE), {q.syms['e_fs'] + 0x100000, DRAW_ENTRY})
        return ns, ps, hr, ok

    if patch.enhanced:
        from skoolkit.simulator import Simulator

        def intro_sequence(q, clock):
            ns = NextState(q)
            ps = bytearray(mem[0x4000:0x5800])
            hr = HookRunner(q, ns, ps)
            ns.nr.update({7: clock, 0x43: 0x20, 0x6B: 0})
            for site, (_, target, label) in INTRO.items():
                r = _case_regs(R0, site)
                rp, writes, returned = hr.run(get, r, {target}, limit=128)
                expected = (0x22, 0xA0) if label == 'intro_on' else (0x20, 0)
                baseline = list(mem)
                sim = Simulator(baseline, {})
                sim.registers[:] = type(sim.registers)(sim.registers.typecode, r) if hasattr(sim.registers, 'typecode') else r
                sim.run(site, target)
                original = sim.registers
                if (not returned or (ns.nr[0x43], ns.nr[0x6B]) != expected or ns.nr[7] != clock
                        or any(rp[i] != original[i] for i in (*CMP, TS))
                        or any(writes.get(i, mem[i]) != baseline[i] for i in range(0x4000, 0x10000))
                        or ps != mem[0x4000:0x5800]):
                    return False
            return True

        def column_case(q, column):
            source = list(mem)
            source[0x6DF7:0x6DF9] = (0x5880 + column - 1).to_bytes(2, 'little')
            ns = NextState(q)
            hr = HookRunner(q, ns, bytearray(source[0x4000:0x5800]))
            regs = _case_regs(R0, INTRO_COLUMN, bc=32, de=0x5B27)
            regs[17] = (regs[17] & 0xFE) | (column & 1)
            rp, writes, ok = hr.run(source.__getitem__, regs, {INTRO_COLUMN_END})
            expected = source.copy()
            sim = Simulator(expected, {})
            sim.registers[:] = regs
            sim.run(INTRO_COLUMN, INTRO_COLUMN_END)
            return (ok and ns.nr[0x1B] == 19 + 4 * column
                    and all(rp[i] == sim.registers[i] for i in (*CMP, TS))
                    and all(writes.get(i, source[i]) == expected[i] for i in range(0x4000, 0x10000)))

        for column in range(2, 30):
            if not column_case(patch, column):
                fail('intro reveal column')
            c['intro reveal columns'] += 1
        # Same seven T as ADD A,19. A full-width clip exposes old black-on-black bitmap data.
        clip = bytes.fromhex('c613ed911c08')
        addr = ROM_ORG + patch.rom_code.index(clip, patch.syms['intro_column'] - ROM_ORG)
        if column_case(_clone(patch, [(addr, bytes.fromhex('3e9f'))]), 2):
            fail('missed negative intro clip')
        c['intro negative full-width clip'] += 1

        for clock in range(4):
            if not intro_sequence(patch, clock):
                fail('intro entry/exit state')
            c['intro clock pairs'] += 1
        for site, (_, _, label) in INTRO.items():
            # Keep the actual assembled path, but suppress just the tile enable or disable.
            address = patch.syms[label] + (5 if label == 'intro_off' else 0)
            broken = _clone(patch, [(address, bytes(4))])
            if intro_sequence(broken, 0):
                fail('missed negative ' + label)
            c['intro negative ' + label] += 1

    def figure(hr, ns, img, col, y, regs=None):
        gfx, mask, rows, kind = img
        scr = scr_addr(col, y)
        if kind == 0:
            R = _case_regs(R0, PLOT, hl=scr, bc=mask, sp=gfx, xa=rows // 2, de=0x1234)
            stop = {0xA7E2}
        elif kind == 1:
            R = _case_regs(R0, PLOT2, hl=gfx, de=scr, bc=0x1234)
            stop = {0xA8EC}
        elif kind == 3:
            R = _case_regs(R0, MINE, hl=gfx, bc=col * 8, de=0x1234)
            R[6], R[7] = gfx >> 8, gfx & 255
            hr.m.ov = {}
            old_get = get
            getm = lambda a: (mask & 255) if a == 0xAE70 else (mask >> 8) if a == 0xAE71 else old_get(a)
            return R, hr.run(getm, R, {0xAE61})
        else:
            R = _case_regs(R0, SMALL, hl=0x2222, de=0x3333, bc=0x1234, xhl=gfx, xde=scr)
            stop = {0xAFDC}
        return R, hr.run(get, R, stop)

    rasters = {img: expected_pixels(get, img, patch.colours, patch.enhanced)[1] for img in imgs}

    def expected(img, col, y):
        return place(rasters[img], col, y)

    # geometry
    k3 = [i for i in imgs if i[3] == 3]
    for imgset, n in ((k0[:6], 'plot geometry'), (k1[:4], 'plot2 geometry'), (k2[:2], 'small geometry'), (k3[:2], 'mine geometry')):
        for img in imgset:
            for col in (0, 1, 2, 13, 27, 28, 29):
                for y in ((162,) if img[3] == 3 else (56, 82, 104, 142)):
                    ns, ps, hr, ok = start()
                    R, (Rp, ov, ok2) = figure(hr, ns, img, col, y)
                    want = expected(img, col, y)
                    got = ns.composite()
                    if got != want:
                        fail(n + ' pixels')
                    for i in CMP:
                        if i not in (PC, 0) and R[i] != Rp[i] and i != SP:
                            fail(n + ' register %d' % i)
                    if img[3] == 0 and Rp[SP] != R[SP]:
                        fail(n + ' SP')
                    if img[3] and Rp[SP] != R[SP]:
                        fail(n + ' SP')
                    if ov and any(a != GAME_SP and a != GAME_SP + 1 for a in ov):
                        fail(n + ' game memory')
                    c[n] += 1
    # the edge rule: every figure image the profile lists, alone on a fresh frame, against the rule
    for img in imgs:
        y = 162 if img[3] == 3 else 100
        ns, ps, hr, ok = start()
        figure(hr, ns, img, 10, y)
        want = expected(img, 10, y)
        if ns.composite() != want:
            fail('edge rule: figure pixels')
        c['edge rule figures'] += 1
        c['opaque figure pixels'] += len(want)
        if not patch.enhanced:
            c['grey ring pixels'] += sum(v == 15 for v in want.values())

    # Change actual pattern RAM or the actual slot palette, then repeat the same comparison.
    img = next(img for img in k0 if rasters[img] and
               (patch.enhanced or any(v == 15 for v in rasters[img].values())))
    for fault in (('wrong group',) if patch.enhanced else ('missing rim pixel', 'extra rim pixel')):
        ns, _, hr, _ = start()
        figure(hr, ns, img, 10, 100)
        if fault == 'wrong group':
            for attr in ns.attr:
                if attr[3] & 0x80:
                    attr[2] ^= 0x10
        else:
            for attr in (a for a in ns.attr if a[3] & 0x80):
                base = (attr[3] & 63)*256 + (128 if attr[4] & 64 else 0)
                hit = False
                for offset in range(base, base+128):
                    for shift in (4, 0):
                        value = ns.pat[offset] >> shift & 15
                        if value == (15 if fault == 'missing rim pixel' else 0):
                            ns.pat[offset] ^= 15 << shift
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    break
        if ns.composite() == expected(img, 10, 100):
            fail('missed negative ' + fault)
        c['negative ' + fault] += 1
    # the every-site clock matrix (card patch.restore-speed): each hook entered at NR 7 = 0 (3.5 MHz) to 3 (28 MHz)
    # from the same state exits at that clock, with the same registers, game memory and sprites
    def at_clock(k, run):
        ns, ps, hr, ok = start()
        ns.nr[7] = k
        R, (Rp, ov, ok2) = run(hr, ns)
        return ns.nr[7], ok2, [Rp[i] for i in CMP], sorted(ov.items()), sorted(ns.composite().items()), \
            [list(a) for a in ns.attr]
    cases = [('plot', i) for i in k0[:4]] + [('plot2', i) for i in k1[:2]] + [('small', i) for i in k2[:2]] + \
            [('mine', i) for i in k3[:2]]
    for name, img in cases:
        y = 162 if img[3] == 3 else 100
        res = [at_clock(k, lambda hr, ns: figure(hr, ns, img, 10, y)) for k in range(4)]
        for k, r in enumerate(res):
            if r[0] != k:
                fail('clock matrix: %s exits at another clock' % name)
            if not r[1] or r[2:] != res[0][2:]:
                fail('clock matrix: %s results differ with the clock' % name)
            c['clock matrix cases'] += 1
    for name, site, stop in (('frame end', FEND_SITE, AFTER), ('wipe 1', WIPE1, WIPE1 + 3), ('wipe 2', WIPE2, WIPE2 + 3)):
        def run(hr, ns, site=site, stop=stop):
            figure(hr, ns, k0[0], 10, 100)
            R = _case_regs(R0, site)
            return R, hr.run(get, R, {stop})
        res = [at_clock(k, run) for k in range(4)]
        for k, r in enumerate(res):
            if r[0] != k:
                fail('clock matrix: %s exits at another clock' % name)
            if not r[1] or r[2:] != res[0][2:]:
                fail('clock matrix: %s results differ with the clock' % name)
            c['clock matrix cases'] += 1
    # the cache: more images than entries in one go: every figure right when drawn, frame by frame
    ns, ps, hr, ok = start()
    syn = ([i for i in k0 if i[2] == 24] * 40)[:40]
    for img in syn:
        fs_ = _case_regs(R0, DRAW_SITE)
        hr.run(get, fs_, {DRAW_ENTRY})
        figure(hr, ns, img, 10, 100)
        hr.run(get, _case_regs(R0, FEND_SITE), {AFTER})
        if ns.composite() != expected(img, 10, 100):
            fail('cache: wrong picture after eviction')
        c['cache eviction'] += 1
    fs_ = _case_regs(R0, DRAW_SITE)
    hr.run(get, fs_, {DRAW_ENTRY})
    u0 = ns.uploads
    figure(hr, ns, syn[-1], 12, 110)
    if ns.uploads != u0:
        fail('cache: no hit on the last image')
    c['cache hit'] += 1
    # the slot guard: never past sprite 127
    ns, ps, hr, ok = start()
    for i in range(40):
        figure(hr, ns, syn[0], 5, 100)
    if ns.scratch[0x1800] > 128:
        fail('slot guard')
    c['slot guard'] += 1
    # outside the draw pass: no sprite
    ns, ps, hr, ok = start()
    hr.run(get, _case_regs(R0, FEND_SITE), {AFTER})
    figure(hr, ns, (0xCF54, 0, 3, 2), 10, 100)
    if ns.composite():
        fail('small outside the draw pass made a sprite')
    c['outside draw'] += 1
    # hide: a wipe hides everything, the frame's own figures too
    ns, ps, hr, ok = start()
    figure(hr, ns, syn[1], 10, 100)
    hr.run(get, _case_regs(R0, WIPE1), {WIPE1 + 3})
    if any(a[3] & 0x80 for a in ns.attr) or ns.nr[0x52] != ULAPAGE:
        fail('wipe left sprites or slot 2')
    c['wipe hide'] += 1
    # a frame's end hides what was not plotted
    ns, ps, hr, ok = start()
    figure(hr, ns, syn[1], 10, 100)
    figure(hr, ns, syn[2], 20, 100)
    hr.run(get, _case_regs(R0, FEND_SITE), {AFTER})
    hr.run(get, _case_regs(R0, DRAW_SITE), {DRAW_ENTRY})
    figure(hr, ns, syn[1], 10, 100)
    hr.run(get, _case_regs(R0, FEND_SITE), {AFTER})
    if sum(1 for a in ns.attr if a[3] & 0x80) != 4:
        fail('frame end did not hide')
    c['frame hide'] += 1
    # colours: a painted pixel and a transparent one; a wrong check byte ignored; the plane unmapped after
    if k0:
        img = k0[0]
        y0, col0, a0, _ = cells_of(img)[0]
        y1, col1, a1, _ = cells_of(img)[1]
        g0 = get(a0)
        cm = {'%04X' % a0: [g0, 'g', [5] * 8], '%04X' % a1: [get(a1), 'g', [0] * 8, 0xFF]}
        q = GreenBeretPatch(colours=cm, enhanced=patch.enhanced)
        q.prepare(get)
        ns, ps, hr, ok = start(q)
        figure(hr, ns, img, 10, 100)
        got = ns.composite()
        want = place(expected_pixels(get, img, {}, patch.enhanced)[1], 10, 100)
        for b in range(8):
            want[(80 + 8 * col0 + b, 100 + y0)] = 5
            want.pop((80 + 8 * col1 + b, 100 + y1), None)
        if got != want:
            fail('colour map: picture')
        if ns.nr[0x56]:
            fail('colour map: slot 6 left mapped')
        c['colour map'] += 1
        q = GreenBeretPatch(enhanced=patch.enhanced, colours={'%04X' % a0: [(g0 + 1) & 255, 'g', [5] * 8]})
        q.prepare(get)
        ns, ps, hr, ok = start(q)
        figure(hr, ns, img, 10, 100)
        if ns.composite() != place(expected_pixels(get, img, {}, patch.enhanced)[1], 10, 100):
            fail('colour map: wrong check byte not ignored')
        c['colour check byte'] += 1
    return c


DRAW_ENTRY = 0xA5FE


def _clone(patch, edits, drop=()):
    import copy
    q = copy.copy(patch)
    rom = bytearray(patch.rom_code)
    for a, b in edits:
        rom[a - ROM_ORG:a - ROM_ORG + len(b)] = b
    q.rom_code = bytes(rom)
    page = bytearray(patch.page)
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(rom)] = rom
    q.page = bytes(page)
    q.sites = [s for s in patch.sites if s[0] not in drop]
    return q


def negative_patches(patch):
    s = patch.syms
    out = {}
    nop3 = bytes(3)
    # no hook installed: the ULA keeps the plot, sprites never shown
    out['plot hook never runs'] = _clone(patch, [], drop=(PLOT,))
    out['plot2 hook never runs'] = _clone(patch, [], drop=(PLOT2,))
    out['small hook never runs'] = _clone(patch, [], drop=(SMALL,))
    # the hook runs but CALL show is gone: scratch redirect only, figures vanish
    out['no sprites shown'] = _clone(patch, [(s['n_plot'], nop3)])
    out['plot2 sprites not shown'] = _clone(patch, [(s['n_plt2'], nop3)])
    out['small sprites not shown'] = _clone(patch, [(s['n_smal'], nop3)])
    # Move the origin in its actual representation (arcade immediate or default descriptors).
    if patch.enhanced:
        shifted = _clone(patch, [(s['n_y'] + 1, bytes([33]))])
    else:
        shifted = _clone(patch, [])
        index = bytearray(patch.index)
        for i in range(len(images(patch.prof))):
            index[4096 + 8 * (i + 1) + 1] += 1
        shifted.index = bytes(index)
    out['sprites one line low'] = shifted
    # body and dark swapped in the class table
    q = _clone(patch, [])
    if patch.enhanced:
        q.scratch0 = page_image(a=2, b=1, prof=patch.prof)
    else:
        remap = (0, 2, 1, *range(3, 16))
        swap = bytes(remap[n >> 4] << 4 | remap[n & 15] for n in range(256))
        q.colour_pages = {i: data.translate(swap) for i, data in patch.colour_pages.items()}
    out['pixel classes swapped'] = q
    # stale patterns: the cache key ignores the graphics address
    out['cache key ignores the graphics'] = _clone(patch, [(s['n_k0'], bytes(2)), (s['n_k1'], bytes(2))])
    # frame end hides nothing (the guard's RET NC instead of the compare)
    out['leftover sprites not hidden'] = _clone(patch, [(s['hide_rest'], bytes([0xC9]))])
    # a plot's end leaves slot 2 mapped
    out['plot end leaves slot 2 mapped'] = _clone(patch, [(s['n_end'] + 3, bytes([SCRPAGE]))])
    # no redirect: plots write the ULA: ULA figures under the sprites
    out['plots reach the ULA'] = _clone(patch, [(s['e_plot'] + 3, bytes([ULAPAGE]))])
    # the hook loses a register
    out['hook loses a register'] = _clone(patch, [(s['n_plot'] + 6, bytes(1))])
    # the old exit: NR 7 forced to 3.5 MHz (seen by the clock matrix at 7 MHz and above)
    out['exit forced to 3.5 MHz'] = _clone(patch, [(s['spd_out'] + 1, bytes([0x3E, 0x00, 0x00]))])
    # wipe does not hide
    out['wipe keeps sprites'] = _clone(patch, [(s['e_wip1'], nop3), (s['e_wip2'], nop3)])
    out['mine hook never runs'] = _clone(patch, [], drop=(MINE, MINE_END))
    out['mine sprites not shown'] = _clone(patch, [(s['n_mine'], nop3)])
    # the edge rule left out: the old wide white edges
    q = GreenBeretPatch(patch.prof, colours=patch.colours, trim=False, enhanced=patch.enhanced)
    q.prepare(patch.peek)
    out['edge rule left out'] = q
    return out


# ---------------------------------------------------------------------------------------------
# Colour sheets and recolour (docs/COLOURS.md)
# ---------------------------------------------------------------------------------------------
NOTE = ('Green Beret graphics bytes and rim margin keys. Each bit is one pixel. Swatch 15 is '
        'dark grey in Spectrum and navy in Enhanced. Canvas grey is transparent. See docs/COLOURS.md.')
RECOLOUR = {'game': 'green_beret', 'output': 'sprites', 'colours': 'docs/profiles/green_beret_colours.json', 'clear': True,
            'note': NOTE, 'outputs': ('sprites', 'sprites_loading', 'enhanced', 'enhanced_loading')}


def banked_page(page, prof):
    return page[:8192] == page_image(prof=dict(prof, hooks=prof['arcade_hooks']))


def colours_for_build(nex):
    from .recolour import banks
    return ARCADE_COLOURS if banked_page(banks(nex)[13], load_profile()) else RECOLOUR['colours']


def check_sheet(nex, layout):
    banked = colours_for_build(nex) == ARCADE_COLOURS
    groups = layout.get('group_palettes')
    if banked != (groups is not None):
        raise ValueError('use the sheet issued for the matching Green Beret palette mode')
    if banked:
        if groups != [[list(c) for c in row] for row in art.RGB]:
            raise ValueError('the sheet has different arcade swatches')
        for comp in layout['composites']:
            if any(art.group(int(p['id'].split(':')[0], 16)) != comp['group'] for p in comp['parts']):
                raise ValueError('the figure has a different palette group in this build')


def recolour(nex, cmap):
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    need = set(COLOUR_BANKS) | {5, 2, 0, 12, 13}
    if not need <= set(have):
        raise ValueError('not a Green Beret sprite build: banks %s missing' % sorted(need - set(have)))
    peek = nex_peek(nex)
    prof = load_profile()
    want = prof.get('colour_inputs', {})
    got = colour_inputs_md5(peek, prof)
    if [want.get('md5'), want.get('bytes')] != list(got):
        raise ValueError('game graphics differ from the expected snapshot (%s / %d bytes, expected %s)' % (got[0], got[1], want))
    banked = banked_page(have[13], prof)
    p = GreenBeretPatch(prof, colours=cmap, enhanced=banked)
    if banked and have.get(10, b'')[0x1000:0x1000 + len(p.stub_extra)] != p.stub_extra:
        raise ValueError('the arcade palette in this build differs from its issued swatches')
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    img, rb = p.page + bytes(8192), p.regblock + 20 - 0x2000    # restore_tail's bytes (per snapshot) sit in rb..0x3D00
    if have[12][:rb] != img[:rb] or have[12][0x1D00:] != img[0x1D00:]:
        raise ValueError('alt ROM image / hook code differs from this version\'s (rebuild with nexclash.py auto)')
    if have[13][:8192] != p.scratch0:
        raise ValueError('hook page differs from this version\'s (rebuild with nexclash.py auto)')
    p.prepare(peek)
    out, changed = splice(nex, {b: p.extra_banks[b] for b in (13,) + COLOUR_BANKS})
    info = {'banks changed': changed}
    info.update({k: v for k, v in p.cinfo.items() if v})
    return out, info


def image_part(get, img, banked=False, trim=True):
    """The coloursheet part of one image: body code 1, dark code 2, clear code 0."""
    gfx, mask, rows, kind = img
    px, ent = [], {}
    cut = trims_body(get, img) if trim else set()
    ring = ring_pixels(get, img) if trim and not banked else set()
    w = 32 if kind in (0, 3) else 16
    for y, col, a, m in cells_of(img):
        g = get(a)
        mm = get(m) if m is not None else 0xFF
        ent['%04X' % a] = [g, 'g']
        for bit in range(8):
            gb, mb = g >> (7 - bit) & 1, mm >> (7 - bit) & 1
            code, dflt = (2, 2) if gb else ((0, 0) if mb else (1, 1))
            if (col * 8 + bit, y) in cut:
                dflt = 0
            pos = col * 8 + bit, y
            if pos in ring:
                code = dflt = 15
            px.append((*pos, '%04X' % a, bit, code, dflt))
    if not banked:
        # These extra edge pixels have no source byte. Give each paintable margin byte a stable key.
        for x, y in sorted(ring - {(q[0], q[1]) for q in px}):
            key = '%04X:rim:%d:%d' % (gfx, y, x // 8)
            ent[key] = [0, 'g']
            px.append((x, y, key, x % 8, 15, 15))
        px = [(x + 1, y + 1, *rest) for x, y, *rest in px]
        w, rows = w + 2, rows + 2
    return {'id': '%04X:%d:%d' % (gfx, img[2], kind), 'size': 1, 'w': w, 'h': rows, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px,
            'entries': ent, 'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}


def ring_tables(get, cmap, prof, trim=True):
    """Store a padded 4bpp pattern per source frame. A cache entry holds up to four 16x16 tiles."""
    index = bytearray(8192)
    pages = {2*b + k: bytearray(8192) for b in COLOUR_BANKS for k in (0, 1)}
    used, bad = set(), set()
    for i, img in enumerate(images(prof)):
        gfx = img[0]
        part = image_part(get, img, trim=trim)
        pixels = {}
        for x, y, key, bit, _, colour in part['pixels']:
            e = cmap.get(key)
            if e and e[0] == part['entries'][key][0]:
                used.add(key)
                colour = 0 if len(e) > 3 and e[3] & (128 >> bit) else (e[2][bit] or colour)
            elif e:
                bad.add(key)
            if colour:
                pixels[x - 1, y - 1] = colour
        xs, ys = zip(*(pixels or {(0, 0): 0}))
        x0, y0 = min(xs), min(ys)
        w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
        if w > 32 or h > 32:
            raise ValueError('paint at %04X spans %dx%d, exceeding four hardware tiles' % (gfx, w, h))
        page, offset = 2 * COLOUR_BANKS[0] + i // 16, 512 * (i % 16)
        for (x, y), colour in pixels.items():
            xx = x - x0
            pages[page][offset + 16 * (y - y0) + xx // 2] |= colour << (0 if xx & 1 else 4)
        slot = (gfx - 0x8000) >> 3
        if index[slot]:
            raise ValueError('duplicate graphics lookup at %04X' % gfx)
        index[slot] = i + 1
        header = 4096 + 8 * (i + 1)
        index[header:header+7] = bytes((32+x0, 32+y0, (w+15)//16, h, page, 0xC0 + offset//256, gfx & 255))
    return bytes(index), pages, {'map entries used': len(used), 'map entries ignored (check byte differs)': len(bad),
                                 'map entries for no known image': len(set(cmap) - used - bad)}


def capture(rzx_paths):
    """The images the recordings draw (C simulator): {(gfx, mask, rows, kind): count}."""
    from . import rzx as RZ
    seen = collections.Counter()

    def on(pc, sim):
        R = sim.registers
        if pc == PLOT:
            seen[(R[SP], R[2] << 8 | R[3], 2 * R[16], 0)] += 1
        elif pc == PLOT2:
            seen[(R[6] << 8 | R[7], 0, 8, 1)] += 1
        elif pc == MINE:
            mem = sim.memory
            seen[(R[6] << 8 | R[7], mem[0xAE70] | mem[0xAE71] << 8, 6, 3)] += 1
        else:
            seen[(R[22] << 8 | R[23], 0, 3, 2)] += 1
    for r in rzx_paths:
        RZ.trace(r, [PLOT, PLOT2, SMALL, MINE], on)
    return seen


def sheets(z80, out_dir, prefix='green_beret', colours=None, say=print, banked=False):
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    prof = load_profile()
    comps = [{'count': 1, 'group': art.group(i[0]) if banked else 0, 'parts': [image_part(get, i, banked)]} for i in images(prof)]
    cmap = load_colours(banked=banked) if colours is None else colours
    rgb = art.RGB[0] if banked else cs.palette_rgb(PALETTE) + [RING_RGB]
    groups = art.RGB if banked else None
    if banked:
        comps.sort(key=lambda c: c['group'])
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get, prof)
    painting = cs.choose(comps, {}, range(len(art.GROUPS)) if banked else ())
    n1 = cs.write(painting, pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident, group_palettes=groups)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident, group_palettes=groups)
    say('Sheets    : %d images; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


def auto(a, z80, name, out, say):
    import hashlib as H
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : green_beret (four plotters -> sprites, their writes into a scratch page; scenery stays on the ULA)')
    md5 = lambda p: H.md5(open(p, 'rb').read()).hexdigest()
    beside = os.path.join(os.path.dirname(os.path.abspath(z80)), LOADING_SCREEN)
    screen = open(beside, 'rb').read() if os.path.exists(beside) else None
    say('Screen    : %s' % ('the tape\'s loading screen at the start and in the _loading builds (%s)' % LOADING_SCREEN
                            if screen else 'none (%s not beside the snapshot)' % LOADING_SCREEN))
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch(screen)
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp, keep_printer_buffer=True)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = GreenBeretPatch(screen=screen)
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch, keep_printer_buffer=True)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    enhanced = GreenBeretPatch(screen=screen, enhanced=True)
    enh = os.path.join(out, name + '_enhanced.nex')
    conv = zt.convert(z80, enh, None, True, quiet=True, patch=enhanced, keep_printer_buffer=True)
    bad3 = check(enh, z80, enhanced, (conv[1], conv[1] + len(conv[2])))
    say('Enhanced  : %s  %s  boot %s' % (os.path.basename(enh), md5(enh), 'OK' if not bad3 else bad3[:3]))
    if screen:
        for src in (spr, enh):
            load = src[:-4] + '_loading.nex'
            with open(src, 'rb') as f:
                head = bytearray(f.read(512))
                head[10], head[133] = 2, 50
                with open(load, 'wb') as target:
                    target.write(head + screen + f.read())
            say('Loading   : %s  %s' % (os.path.basename(load), md5(load)))
    ok = not bad and not bad2 and not bad3
    for variant in (patch, enhanced):
        if a.rzx:
            say('Replay    : %s' % ('Enhanced' if variant.enhanced else 'Spectrum with grey ring'))
            ok = verify_recordings(variant, a, say) and ok
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def verify_recordings(patch, a, say):
    ok = True
    states = []
    for r in list(a.rzx or []):
        cc, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in cc.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, draw %d, plot %d, plot2 %d, mine %d, small %d (outside draw %d), wipe %d, %d picture pixels -> %s' % (
            os.path.basename(r), cc['frames'], cc['draw'], cc['plot'], cc['plot2'], cc['mine'], cc['small'],
            cc['small outside the draw pass'], cc['wipe'], cc['picture pixels compared'],
            'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('Figures   : %s  %d visible sprite pixels checked' % (os.path.basename(r), cc['figure pixels checked in play']))
        if patch.enhanced:
            say('Intro      : %s entered %d, exited %d, columns %d' % (
                os.path.basename(r), cc['intro_on'], cc['intro_off'], cc['intro columns']))
        say('Cache     : %s  draws that uploaded %d of %d, pattern bytes %d, T at 28 MHz %d' % (
            os.path.basename(r), cc['draws with uploads'], cc['draw'], cc['pattern bytes uploaded'], cc['T hook 28MHz']))
        say('Clash     : %s  body pixels the original showed in another colour %d, in this colour %d' % (
            os.path.basename(r), cc['body pixels the original showed in another colour'],
            cc['body pixels the original showed in this colour']))
        say('Allowed   : %s  %s' % (os.path.basename(r), {k: v for k, v in cc.items() if k.startswith(('sky', 'holes', 'margin', 'dark pixels', 'trimmed', 'plots with', 'plot of'))}))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items())), 'PASS' if not uf else 'FAIL %s' % uf))
    return ok
