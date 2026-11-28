"""Gauntlet (US Gold, 1986; 48K code, the 128K's AY) engine 'gauntlet'. Additive module: reachable only through
is_gauntlet(). Facts, design, results: games/gauntlet.md.

The game draws blocks and projectile pixels into a hidden copy of the screen and sends it to the
screen with three stack copies. The build changes nothing of the game: before the first copy a hook looks every cell of
the 32 x 20 play window up by its 8 bytes and its attribute and shows a painted tile of the Next's tile layer over it
(asm/gauntlet_hooks.asm); the copies run at 28 MHz and their own time is waited out. "Steady speed" (an option of the
build) runs the game at 28 MHz and shows every update a fixed number of frames after the last.
"""
from . import l2pal
import collections
import hashlib
import json
import os

from . import hooklib

ROM_ORG = 0x2800
ALT_PAGE, WORK, TPAGE, EPAGE, DPAGE = 24, 26, 14, 28, 31
A_, F_, SP_, R_, PC_, T_, IFF_ = 0, 1, 12, 15, 24, 25, 26
CMP = list(hooklib.CMP_R)
STACK = 6                               # bytes below SP a hook writes on the game's stack
T_LINE, LINES = 228, 311                # the 128K's frame
PRE, C1, C2, C3, CL = 0x9CD9, 0x9CE1, 0x9CE9, 0x9CF1, 0x9CFE
LD0, LOAD, LOADED = 0x9203, 0x9247, 0x924A     # the level loader: its first CALL, its CALL of the ROM's loader, after it
TAPE_SITES = {LD0: ('cdffb4', 'e_ld0', 0xC3), LOAD: ('cd6b05', 'e_load', 0xCD)}
REWIND = (0xB494, 'dd21b7b4', 'c921b7b4')    # the "rewind tape to start of side 2, then press space" prompt: a RET in its place
TITLE_SIG = (0xFF00, bytes.fromhex('31005cdd2100861110523e80cd3bffcdf2c1'))     # the tape's loader, the front end loaded
TITLE_SITE = (0xFF12, '210000', 'e_main')       # its LD HL,0 after the front end returns: the two blocks from memory instead
MAIN_AT, B81_AT = 0x8400, 0x73DA        # where the loader puts side A's blocks 0x82 (the main game) and 0x81
MPAGE = 52                              # from here: those two blocks
LPAGE = 40                              # from here: the tape's level blocks, one after another
NBLK = 31
SITES_ORIG = {PRE: ('cdfbb8', 'e_pre'), C1: ('cd3b9d', 'e_c1'), C2: ('cda39d', 'e_c2'), C3: ('cd3b9d', 'e_c3'), CL: ('cdffb4', 'e_cl')}
SIGNATURE = (0x9CD7, bytes.fromhex('76f3cdfbb83e402100c0cd3b9d3e282100d8cda39d3e602100c8cd3b9d'))
KIND, WIDE, ROCK = 0x8CB6, 0x8DFB, 0x8EBF
SHOT_SITES = {KIND: ('ddcb0376', 'e_kind'), WIDE: ('f3f97a', 'e_wide'), ROCK: ('f3f97a', 'e_rock')}
SHOTPAGE = 58
# RGB samples from the painted character palette, then fire and stone.
SHOT_RGB = [(219, 73, 36), (146, 219, 219), (255, 219, 73), (146, 219, 109),
            (255, 146, 36), (182, 182, 146)]
ISR = 0xDADA
FRAMES = 0x8497                         # the game's frame counter
ROWS, COLS = 20, 32                     # the play window, in cells
SLOTS = [s for s in range(1, 256) if not 10 <= s < 60]     # usable definition slots (10-59 are the window's map bytes)
L2PAGE = 18                             # Layer 2: bank 9; its last page (lines 160-191) is the panel
PANEL = range(20, 24)                   # the status panel's rows: read from the screen, known by their bytes alone
ANY = 255                               # the attribute a panel cell is stored under
EPAGE4 = 57                             # the cell table's fourth page, at 0xE000 during a tile pass (the hooks have their own stack)
NLOW = 3 * 8192 // 15                   # cell entries in the three pages at 0x6000; the rest from 0xE000


def ent_addr(n):
    """Where cell entry n sits during a tile pass."""
    return 0x6000 + n * ENTRY if n < NLOW else 0xE000 + (n - NLOW) * ENTRY


def ent_at(a):
    """(page, offset) of a table address."""
    return (EPAGE4, a - 0xE000) if a >= 0xE000 else (EPAGE + (a - 0x6000) // 8192, (a - 0x6000) % 8192)


ENTRY = 15                              # bytes a cell entry: next, 8 bytes, attribute, slot, palette << 4, page, number
E_SLOT = 11
CH = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_{|}~'
COLOURS_NAME = 'gauntlet_colours.json'  # the painted map, beside the snapshot (it holds the game's pictures: not in the repo)
T_COPY = {C1: 35796, C2: 10587, C3: 53684}
T_CLEAR = 34357                          # the clear of the hidden copy: its own time, T
FAST = 8.0                              # 28 MHz against 3.5
#          # the three copies' own time, T (they run the same instructions every time)
TAIL_ADDR = 0x5D00                      # BASIC's spare memory: no recording reads or writes 0x5CFC-0x5EFF
STEADY = 3                              # frames an update with the steady-speed option: the original's fastest
_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'gauntlet.json'), os.path.join(_HERE, 'gauntlet.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('gauntlet.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def play_view(snap):
    """64K of a SkoolKit 128K snapshot as the game sees it (ROM zeros)."""
    from .simrun import addr_view
    return bytes(addr_view(snap))


def is_gauntlet(snap):
    if getattr(snap, 'machine', '48K') == '48K':
        return False
    try:
        m = play_view(snap)
        return m[SIGNATURE[0]:SIGNATURE[0] + len(SIGNATURE[1])] == SIGNATURE[1] or m[TITLE_SIG[0]:TITLE_SIG[0] + len(TITLE_SIG[1])] == TITLE_SIG[1]
    except Exception:
        return False


def tape_sets():
    """The tapes the build accepts (profile tape_sets): [[md5 of the levels' side], ...]."""
    return [s['md5'] for s in load_profile()['tape_sets']]


def level_blocks(ts):
    """The 31 level blocks of a tape set's last file, in tape order: the first with flag 0x80, the rest 0xC0, each ending
    in its 0xFF mark and its checksum byte. ValueError when it does not hold them."""
    bl = [b for b in ts.blocks[-1] if b[0] in (0x80, 0xC0) and len(b) <= 0x1101]
    if len(bl) != NBLK or bl[0][0] != 0x80 or any(b[0] != 0xC0 for b in bl[1:]) or any(b[-2] != 0xFF for b in bl):
        raise ValueError('the tape does not hold the %d level blocks expected' % NBLK)
    return [bytes(b[1:]) for b in bl]          # as the ROM's loader stores them: the data and the checksum byte


def main_blocks(ts):
    """Side A's two blocks the loader takes after the front end: (flag 0x81's 2,881 bytes, flag 0x82's 30,583: the main
    game), or None when the set is the levels' side alone."""
    if len(ts.blocks) < 2:
        return None
    b81 = [b for b in ts.blocks[0] if b[0] == 0x81]
    b82 = [b for b in ts.blocks[0] if b[0] == 0x82]
    if len(b81) != 1 or len(b82) != 1 or len(b81[0]) != 2883 or len(b82[0]) != 30585:
        raise ValueError('side A does not hold the two blocks expected after the front end')
    return bytes(b81[0][1:-1]), bytes(b82[0][1:-1])


def load_colours(z80=None, path=None):
    """The painted map (the painting folder's sheet2colours.py): colours, and for each cell (8 bytes, attribute) its 64
    painted pixels. None when there is none beside the snapshot."""
    p = path or (os.path.join(os.path.dirname(os.path.abspath(str(z80))), COLOURS_NAME) if z80 else None)
    return json.load(open(p)) if p and os.path.exists(p) else None


def cell_keys(cell, attr):
    """The hook's chain number for a cell's 8 bytes and its attribute; None for a cell whose two sums are zero (a
    blank cell is one: it is never looked up)."""
    b = c = 0
    for v in cell:
        b ^= v
        b = ((b << 1) | (b >> 7)) & 255
        c = (c + v) & 255
    if not b and not c:
        return None
    return (b ^ attr) | (c & 3) << 8


def rgb9(c):
    r, g, b = c
    return (r * 7 + 127) // 255 << 6 | (g * 7 + 127) // 255 << 3 | (b * 7 + 127) // 255


def palette_lines(cmap):
    """The cells grouped into palette lines of at most 15 colours -> ([characters of each line], {pixels: line})."""
    sets = sorted({frozenset(px) for _, at, px in cmap['cells'] if at != ANY}, key=lambda s: (-len(s), sorted(s)))
    lines, line_of = [], {}
    for s in sets:
        for li, ln in enumerate(lines):
            if len(set(ln) | s) <= 15:
                ln += sorted(s - set(ln))
                line_of[s] = li
                break
        else:
            if len(lines) == 16:
                raise ValueError('the painted cells need more than 16 palette lines')
            lines.append(sorted(s))
            line_of[s] = len(lines) - 1
    return lines, line_of


def colour_tables(cmap, syms):
    """-> (chain heads for the state page, {page: 8K} of the cell table and the definitions, palette of 256 9-bit colours,
    {(cell bytes, attribute): (palette << 4, the definition's 32 bytes)} for the verifier)."""
    lines, line_of = palette_lines(cmap)
    pal = [0] * 256
    for li, ln in enumerate(lines):
        for k, ch in enumerate(ln):
            pal[li * 16 + 1 + k] = rgb9(cmap['colours'][CH.index(ch)])
    heads = bytearray(2048)
    table = bytearray(4 * 8192)                 # entry n at n * ENTRY here; split over the pages below
    defs = bytearray()
    panel, panel_at = bytearray(), []
    nd = 0
    want = {}
    n = 0
    for hx, attr, px in cmap['cells']:
        cell = bytes.fromhex(hx)
        k = cell_keys(cell, attr)
        if k is None:
            continue
        if n >= NLOW + 8192 // ENTRY:
            raise ValueError('too many painted cells for the cell table')
        if attr == ANY:                 # a panel cell: 64 pixels of Layer 2 (colour number + 1; 0 is the transparent one)
            at = n * ENTRY
            table[at:at + 2] = heads[2 * k:2 * k + 2]
            table[at + 2:at + 10] = cell
            table[at + 10], table[at + 11], table[at + 12] = attr, 0, 0
            table[at + 13], table[at + 14] = 0xFF, len(panel) // 64       # (the page is filled in below)
            heads[2 * k:2 * k + 2] = ent_addr(n).to_bytes(2, 'little')
            blk = bytes(1 + CH.index(ch) for ch in px)
            panel_at.append(at + 13)
            want[(cell, attr)] = blk
            panel += blk
            n += 1
            continue
        li = line_of[frozenset(px)]
        d = bytearray(32)
        for i, ch in enumerate(px):
            idx = 1 + lines[li].index(ch)
            d[i >> 1] |= idx << 4 if not i & 1 else idx
        at = n * ENTRY
        table[at:at + 2] = heads[2 * k:2 * k + 2]
        table[at + 2:at + 10] = cell
        table[at + 10], table[at + 11], table[at + 12] = attr, 0, li << 4
        table[at + 13], table[at + 14] = DPAGE + nd // 256, nd % 256
        heads[2 * k:2 * k + 2] = ent_addr(n).to_bytes(2, 'little')
        defs += d
        want[(cell, attr)] = (li << 4, bytes(d))
        n += 1
        nd += 1
    ndp = (len(defs) + 8191) // 8192
    if len(panel) > 8192:
        raise ValueError('too many painted panel cells for one page')
    for at in panel_at:
        table[at] = DPAGE + ndp
    low = bytes(table[:NLOW * ENTRY]).ljust(3 * 8192, b'\0')
    pages = {EPAGE + i: low[i * 8192:(i + 1) * 8192] for i in range(3)}
    pages[EPAGE4] = bytes(table[NLOW * ENTRY:NLOW * ENTRY + 8192]).ljust(8192, b'\0')
    for i in range(ndp):
        pages[DPAGE + i] = bytes(defs[i * 8192:(i + 1) * 8192]).ljust(8192, b'\0')
    if panel:
        pages[DPAGE + ndp] = bytes(panel).ljust(8192, b'\0')
    pal2 = [0x1C7] + [rgb9(c) for c in cmap['colours']]          # colour 0: the transparent magenta (0xE3)
    pal2 = l2pal.fix(pal2, '9bit', keep=(0,))                 # opaque 0xE3 -> 0xE7 (a Next shows it see-through)
    return bytes(heads), pages, pal, want, pal2 + [0] * (256 - len(pal2))


class Patch:
    name = 'Gauntlet: every cell of the play window a painted tile of the tile layer (alt ROM hooks, the game unchanged)'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = TAIL_ADDR

    def __init__(self, z80=None, mem=None, colours=None, rom=None, steady=0, times=None, blocks=None, main=None):
        self.prof = load_profile()
        h = self.prof['hooks']
        self.syms = sy = {k: int(v, 16) for k, v in h['syms'].items()}
        self.z80, self.colours, self.steady, self.blocks = z80, colours, steady, blocks
        if mem is None and z80 is not None:
            from skoolkit.snapshot import Snapshot
            mem = play_view(Snapshot.get(str(z80)))
        self.title = mem is not None and mem[TITLE_SIG[0]:TITLE_SIG[0] + len(TITLE_SIG[1])] == TITLE_SIG[1]
        self.main = main
        if self.title:
            if not (blocks and main):
                raise ValueError('this snapshot is the tape\'s front end: the build needs both sides of the tape (--tape SIDE_A --tape SIDE_B)')
        elif mem is None or mem[SIGNATURE[0]:SIGNATURE[0] + len(SIGNATURE[1])] != SIGNATURE[1]:
            raise ValueError('not the supported Gauntlet: the screen copies are not where they are expected')
        rc = bytearray(bytes.fromhex(h['rom']) if rom is None else rom)
        if rom is None:
            tm = dict(T_COPY if times is None else times)
            if not steady:              # the clear runs at 28 MHz with no wait: the time it saves is waited out here
                tm[C1] += int(T_CLEAR * (1 - 1 / FAST))
            for site, sym in ((C1, 'T_C1'), (C2, 'T_C2'), (C3, 'T_C3')):
                o = sy[sym] - ROM_ORG
                rc[o:o + 2] = hooklib.lines16(tm[site], T_LINE).to_bytes(2, 'little')
        lpages = {}
        if blocks:                      # the level blocks, one after another from LPAGE; a block may run into the next page
            blob = b''.join(blocks)
            at = 0
            for i, b in enumerate(blocks):
                o = sy['BLKT'] - ROM_ORG + 5 * i
                if rom is None:
                    rc[o:o + 5] = bytes((LPAGE + at // 8192,)) + (0x4000 + at % 8192).to_bytes(2, 'little') + len(b).to_bytes(2, 'little')
                at += len(b)
            for i in range((len(blob) + 8191) // 8192):
                lpages[LPAGE + i] = blob[i * 8192:(i + 1) * 8192].ljust(8192, b'\0')
        self.rom_code = bytes(rc)
        self.regblock = ROM_ORG + len(rc)
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        page = bytearray(rom48()[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(rc)] = rc
        self.page = bytes(page)
        work = bytearray(8192)
        work[sy['V_STEADY']] = steady
        self.want = {}
        self.planes = {}
        pal = [0] * 256
        pal2 = [0x1C7] + [0] * 255
        if colours:
            heads, self.planes, pal, self.want, pal2 = colour_tables(colours, sy)
            work[sy['BKT']:sy['BKT'] + len(heads)] = heads
        self.planes.update(lpages)
        self.planes[SHOTPAGE] = bytes(8192)
        self.work = bytes(work)
        self.palette = pal
        st = bytearray(bytes.fromhex(h['setup']))
        o = sy['pal9'] - 0xD000
        for i, c in enumerate(pal):
            st[o + 2 * i], st[o + 2 * i + 1] = c >> 1, c & 1
        o = sy['pal2'] - 0xD000
        for i, c in enumerate(pal2):
            st[o + 2 * i], st[o + 2 * i + 1] = c >> 1, c & 1
        self.palette2 = pal2
        o = sy['shotpal'] - 0xD000
        for colour in SHOT_RGB:
            value = rgb9(colour)
            st[o:o + 2] = bytes((value >> 1, value & 1))
            o += 2
        o = sy['pbuf'] - 0xD000
        st[o:o + 256] = mem[0x5B00:0x5C00]
        if steady:
            st[sy['speed'] - 0xD000 + 3] = 3
        self.stub_extra = bytes(st)
        self.sites = [(a, bytes.fromhex(old), b'\xCD' + sy[sym].to_bytes(2, 'little')) for a, (old, sym) in SITES_ORIG.items()
                      if not (steady and a == CL)]
        for site, (old, sym) in SHOT_SITES.items():
            self.sites.append((site, bytes.fromhex(old), b'\xC3' + sy[sym].to_bytes(2, 'little') + bytes(len(old) // 2 - 3)))
        if blocks:
            self.sites += [(a, bytes.fromhex(old), bytes((op,)) + sy[sym].to_bytes(2, 'little')) for a, (old, sym, op) in TAPE_SITES.items()]
            self.sites.append((REWIND[0], bytes.fromhex(REWIND[1]), bytes.fromhex(REWIND[2])))
        self.game_sites = list(self.sites)
        if self.title:                  # the main game is not in memory yet: its CALLs go into the block the hand-over copies
            img = bytearray(main[1])
            for a, old, new in self.game_sites:
                o = a - MAIN_AT
                if bytes(img[o:o + len(old)]) != old:
                    raise ValueError('unexpected code in the tape\'s main game at 0x%04X' % a)
                img[o:o + len(new)] = new
            self.image = bytes(img)
            pieces = [(MPAGE, 0x4000, B81_AT, main[0])]
            for k in range(0, len(img), 8192):
                pieces.append((MPAGE + 1 + k // 8192, 0x4000, MAIN_AT + k, bytes(img[k:k + 8192])))
            rc2 = bytearray(self.rom_code)
            for i, (pg, src, dst, data) in enumerate(pieces):
                o = sy['MAINT'] - ROM_ORG + 7 * i
                if rom is None:
                    rc2[o:o + 7] = bytes((pg,)) + src.to_bytes(2, 'little') + dst.to_bytes(2, 'little') + len(data).to_bytes(2, 'little')
                self.planes[pg] = data.ljust(8192, b'\0')
            self.rom_code = bytes(rc2)
            page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(rc2)] = rc2
            self.page = bytes(page)
            self.sites = [(TITLE_SITE[0], bytes.fromhex(TITLE_SITE[1]), b'\xC3' + sy[TITLE_SITE[2]].to_bytes(2, 'little'))]
        self.extra_banks = {12: self.page + bytes(8192), 13: self.work + bytes(8192)}
        for pg, data in self.planes.items():
            cur = self.extra_banks.get(pg // 2, bytes(16384))
            o = (pg & 1) * 8192
            self.extra_banks[pg // 2] = cur[:o] + data + cur[o + 8192:]

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('the Gauntlet patch expects the 128K snapshot')
        for a, old, new in self.sites:
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else snap.port7ffd & 7
            b = bytearray(snap.banks[bank])
            o = a & 0x3FFF
            if bytes(b[o:o + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, bytes(b[o:o + len(old)]).hex(), old.hex()))
            b[o:o + len(new)] = new
            snap.banks[bank] = bytes(b)


# ---------------------------------------------------------------------------------------------
# The Next side, as a hook sees it
# ---------------------------------------------------------------------------------------------

class State:
    """What stays between hooks: the state page, the tile layer's page, the cell table (its slot bytes change)."""
    def __init__(self, patch):
        self.work = bytearray(patch.work)
        self.tpage = bytearray(b'\xAA' * 8192)      # (bank 7 as the 128K left it: anything)
        self.table = {pg: bytearray(patch.planes.get(pg, bytes(8192))) for pg in (EPAGE, EPAGE + 1, EPAGE + 2, EPAGE4)}
        self.l2 = bytearray(b'\x55' * 8192)        # Layer 2's last page (lines 160-191), as anything left it
        self.l2x = bytearray(8192)                  # (its other pages: only cleared)
        self.shadow = bytearray(patch.planes[SHOTPAGE])
        self.attrs = [[0] * 5 for _ in range(128)]
        self.sprite_select = 0
        self.pattern = bytearray(16384)
        self.t = collections.Counter()
        self.line = 0.0
        self.t_in = 0.0


class View:
    """64K as the hooks see it: the alt ROM image, the state page at slot 0, the tile layer's page or a definitions page
    at slot 2, the cell table at slots 3-5, the game's memory."""
    def __init__(self, mem, rom, st, planes):
        self.mem, self.rom, self.st, self.planes = mem, rom, st, planes
        self.model = None

    def __len__(self):
        return 65536

    def _page(self, a):
        nr = self.model.nr
        if a < 0x2000:
            return ('work', None) if nr.get(0x50, 255) == WORK else ('rom', None)
        if a < 0x4000:
            return 'rom', None
        if a < 0x6000:
            p = nr.get(0x52, 10)
            if p == SHOTPAGE:
                return 'shadow', None
            return ('mem', None) if p == 10 else ('tile', None) if p == TPAGE else ('l2', p) if L2PAGE <= p < L2PAGE + 6 else ('def', p)
        if a < 0xC000:
            reg = 0x53 + (a - 0x6000) // 0x2000
            p = nr.get(reg, (11, 4, 5)[reg - 0x53])
            return ('table', p) if EPAGE <= p < EPAGE + 3 else ('def', p) if p in self.planes else ('mem', None)
        if a < 0xE000 and nr.get(0x56) == SHOTPAGE:
            return 'shadow', None
        if a >= 0xE000 and nr.get(0x57, 1) == EPAGE4:
            return 'table', EPAGE4
        return 'mem', None

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        kind, p = self._page(a)
        if kind == 'mem':
            return self.mem[a]
        if kind == 'shadow':
            return self.st.shadow[a & 8191]
        if kind == 'rom':
            return self.rom[a]
        if kind == 'work':
            return self.st.work[a]
        if kind == 'tile':
            return self.st.tpage[a - 0x4000]
        if kind == 'def':
            return self.planes[p][a & 0x1FFF]
        if kind == 'l2':
            return (self.st.l2 if p == L2PAGE + 5 else self.st.l2x)[a - 0x4000]
        return self.st.table[p][a & 0x1FFF]

    def __setitem__(self, a, v):
        kind, p = self._page(a)
        if kind == 'mem':
            self.mem[a] = v
        elif kind == 'shadow':
            self.st.shadow[a & 8191] = v
        elif kind == 'work':
            self.st.work[a] = v
        elif kind == 'tile':
            self.st.tpage[a - 0x4000] = v
        elif kind == 'table':
            self.st.table[p][a & 0x1FFF] = v
        elif kind == 'l2':
            (self.st.l2 if p == L2PAGE + 5 else self.st.l2x)[a - 0x4000] = v
        elif kind == 'def':
            self.model.c['write to a definitions page!'] += 1


class Model(hooklib.NextModel):
    def __init__(self, sim, st, speed=0):
        super().__init__(sim, speed, t_line=T_LINE, lines=LINES)
        self.attrs, self.pattern = st.attrs, st.pattern
        self.nr[0x34] = st.sprite_select
        self.real = st.line


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def run_hook(patch, st, rom, mem, regs, site, stop, sp_stop, limit=6000000, on_halt=None, plain=False, speed=None):
    """Run the patched code from `site` on a copy of the game's memory until PC = stop with SP = sp_stop and the ROM back
    at slot 0. on_halt(memory): called at every HALT the hook runs (a unit case's interrupt). -> (registers, copy, model)."""
    from . import simpool
    m2 = bytearray(mem)
    for a, old, new in patch.sites:
        m2[a:a + len(new)] = new
    v = View(m2, rom, st, patch.planes)
    s = simpool.machine(_rw(), v, list(regs), 'gauntlet-hook')
    model = Model(s, st, speed=(3 if patch.steady else 0) if speed is None else speed)   # speed: the caller's NR 7
    v.model = model
    R = s.registers
    R[PC_] = site
    n = 0
    while True:
        op = v[R[PC_]]
        if op == 0x76 and on_halt:
            on_halt(m2)
            R[PC_] = (R[PC_] + 1) & 0xFFFF
        else:
            s.opcodes[op]()
        n += 1
        if plain and model.nr.get(0x50, 255) != 255:
            model.c['the state page mapped with interrupts on!'] += 1
        if R[PC_] == stop and R[SP_] == sp_stop and model.nr.get(0x50, 255) == 255:
            break
        if n > limit:
            raise AssertionError('hook at %04X did not end (PC %04X)' % (site, R[PC_]))
    st.t[site] += model.now() - st.line
    st.t_in = st.line
    st.line = model.now()
    st.sprite_select = model.nr[0x34]
    model.n = n
    for a, old, new in patch.sites:
        m2[a:a + len(old)] = old
    return list(R), m2, model


def run_orig(rom, mem, regs, stop, sp=None, limit=6000000):
    from . import simpool
    m2 = bytearray(rom[:0x4000]) + bytearray(mem[0x4000:])
    s = simpool.machine(_rw(), m2, list(regs), 'gauntlet-orig')
    R = s.registers
    n = 0
    while True:
        s.opcodes[m2[R[PC_]]]()
        n += 1
        if R[PC_] == stop and (sp is None or R[SP_] == sp):
            break
        if n > limit:
            raise AssertionError('original from %04X did not reach %04X' % (regs[PC_], stop))
    return list(R), m2


def _group(ds):
    out = collections.defaultdict(list)
    for d, n in ds:
        out[n // 64 * 64].append(d)
    return out


def cell_at(mem, base, row, col):
    """(the cell's 8 bytes, its attribute) from a screen-shaped area at `base` (0x4000 the screen, 0xC000 the copy)."""
    o = base + ((row & 0x18) << 8 | (row & 7) << 5 | col)
    return bytes(mem[o + (k << 8)] for k in range(8)), mem[base + 0x1800 + row * 32 + col]


def want_layer(patch, mem):
    """What the tile layer must show for a state: the painted tile of each window cell of the hidden copy."""
    out = {}
    for row in range(ROWS):
        for col in range(COLS):
            w = patch.want.get(cell_at(mem, 0xC000, row, col))
            if w:
                out[(row, col)] = w
    return out


def original_shot(rom, mem, regs, rock):
    """Run the unmodified plotter over blank cells. Its bitmap writes are the reference mask."""
    wide = regs[PC_] == WIDE
    address = regs[4] * 256 + regs[5]
    col = address & 31
    row = ((address >> 8) & 24) + ((address & 255) >> 5)
    size = 2 if wide else 1
    cells = [(row + dy, col + dx) for dy in range(size) for dx in range(size)]
    blank = bytearray(mem)
    for y, x in cells:
        offset = 0xC000 + ((y & 24) << 8) + ((y & 7) << 5) + x
        blank[offset:offset + 2048:256] = bytes(8)
    _, result = run_orig(rom, blank, regs, 0x8EB4 if wide else 0x8EE8)
    mask = bytearray(256)
    for y, x in cells:
        lines, _ = cell_at(result, 0xC000, y, x)
        for k, v in enumerate(lines):
            start = ((y - row) * 8 + k) * 16 + (x - col) * 8
            mask[start:start + 8] = bytes((v >> bit) & 1 for bit in range(7, -1, -1))
    owner = regs[8] * 256 + regs[9]
    colour = mem[0xFFFF] if owner == 0x8430 else mem[0xFFFE] if owner == 0x8450 else 4 + int(rock)
    return (col * 8, row * 8, colour, bytes(mask)), cells


def shot_sprites(st):
    out = []
    for x, y, flags, pat, ext in st.attrs:
        if pat & 128:
            start = (pat & 63) * 256
            out.append((x + ((flags & 1) << 8) - 32, y - 32, flags >> 4,
                        bytes(st.pattern[start:start + 256])))
    return out


def want_panel(patch, mem):
    """Layer 2's last page for a state: each panel cell of the screen (known by its bytes alone) as its 64 painted
    pixels, any other cell clear."""
    out = bytearray(8192)
    n = 0
    for row in PANEL:
        for col in range(COLS):
            cell, at = cell_at(mem, 0x4000, row, col)
            blk = patch.want.get((cell, ANY))
            if blk and (col >= 16 or at & 7 != at >> 3 & 7):     # (ink = paper: the game hides the cell; the logo's half is shown steady)
                n += 1
                for k in range(8):
                    o = ((row - 20) * 8 + k) * 256 + col * 8
                    out[o:o + 8] = blk[k * 8:k * 8 + 8]
    return bytes(out), n


def layer(st):
    """{(row, col): (palette << 4, definition bytes)} of the window's cells the tile layer shows something for."""
    out = {}
    for row in range(ROWS):
        for col in range(COLS):
            e = ((row + 4) * 40 + col + 4) * 2
            slot, attr = st.tpage[e], st.tpage[e + 1]
            if slot:
                out[(row, col)] = (attr, bytes(st.tpage[slot * 32:slot * 32 + 32]))
    return out


def flat(m):
    return b''.join(bytes(p) for p in m.memory)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, timing=False, on_show=None, every=4):
    """Replay the original (PLAYBOOK 6). At each of the four sites the patched code runs on a copy of the state, the Next
    side carried from site to site, and must leave every register (R too) and all the game's memory as the original
    does. After the first copy's hook the tile layer must show, for every cell of the window, the painted tile of that
    cell of the hidden copy (an independent lookup of the painted map) or nothing; every `every`th frame the layer is
    checked against the visible screen's cells. -> (Counter, examples, states)."""
    from . import rzx as RZ
    from .nextboot import alt_image
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    kept = collections.Counter()
    rom = bytes(alt_image(patch))
    st = State(patch)
    sy = patch.syms
    box = {'t': collections.defaultdict(set), 'orig_t': 0, 'upd': 0, 'tcl': set()}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(ex[key]) < 5:
            ex[key].append(detail)

    def same(name, Ro, mo, Rp, mp, sp):
        bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
        if bad:
            fail('registers after %s' % name, bad)
        if mp[0x4000:sp - STACK] != mo[0x4000:sp - STACK] or mp[sp:] != mo[sp:]:
            fail('%s writes game memory' % name, [hex(a) for a in range(0x4000, 65536) if mp[a] != mo[a] and not sp - STACK <= a < sp][:8])

    draws = []
    backgrounds = {}
    after_plot = {}

    def on(pc, sim):
        if box.get('dead'):
            return
        try:
            on_(pc, sim)
        except AssertionError as e:
            box['dead'] = True
            fail('a hook does not end', str(e))

    def on_(pc, sim):
        m, R = sim.memory, sim.registers
        if pc == ISR:
            c['frames seen'] += 1
            if box.get('shot screen'):
                c['interrupts with shots checked'] += 1
                for cell, finished in box['shot screen'].items():
                    if cell_at(m, 0x4000, *cell) != finished:
                        fail('visible shot cell changed before the sprite commit', (c['frames seen'], cell))
                        break
            if c['frames seen'] % every or not box.get('shown'):
                return
            c['frames checked'] += 1
            scr = m.memory[1]
            got = layer(st)
            for (row, col), (attr, d) in got.items():
                o = (row & 0x18) << 8 | (row & 7) << 5 | col
                key = (bytes(scr[o + (k << 8)] for k in range(8)), scr[0x1800 + row * 32 + col])
                clean, composite = box.get('under shots', {}).get((row, col), (key, key))
                if patch.want.get(clean if key == composite else key) != (attr, d):
                    c['frames a tile is not the screen cell\'s'] += 1
                    if len(ex['frames a tile is not its screen cell\'s']) < 5:
                        ex['frames a tile is not its screen cell\'s'].append((c['frames seen'], row, col))
                    break
            return
        if pc in (0x8EB4, 0x8EE8):
            for cell in box.pop('plot cells', ()):
                after_plot[cell] = cell_at(m, 0xC000, *cell)
            return
        regs = list(R)
        mem = bytearray(flat(m))
        if bytes(mem[SIGNATURE[0]:SIGNATURE[0] + len(SIGNATURE[1])]) != SIGNATURE[1]:
            return
        sp = regs[SP_]
        if collect and kept[pc] < collect:
            kept[pc] += 1
            states.append((pc, bytes(mem), tuple(regs), bytes(st.work)))
        if pc == LOAD:                  # the game asks the tape for a block: the hook's bytes, checked when the tape's arrive
            c['blocks asked for'] += 1
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, LOADED, sp)
            box['load'] = bytes(mp[0xC000:0xD011])
            box['blkn'] = st.work[sy['V_BLKN']]
            other = [a for a in range(0x4000, 0xC000) if mp[a] != mem[a]][:4] + [a for a in range(0xD011, sp - STACK) if mp[a] != mem[a]][:4]
            if other:
                fail('the load writes outside the block\'s place', [hex(a) for a in other])
            end = max((i for i in range(0x1001) if box['load'][i]), default=0)      # the game's own test (0x924A): the last byte
            if box['load'][end] != 0xFF and box['load'][end - 1] != 0xFF:           # that is not 0 is the 0xFF mark, or the one before it is
                fail('a block the game would not accept', box['blkn'])
            if any(model.nr.get(r, d) != d for r, d in ((0x52, 10), (0x53, 11))) or regs[IFF_]:
                fail('the load leaves a page mapped, or runs with interrupts on', box['blkn'])
            return
        if pc == LOADED:                # the recording's own tape load has finished: the same bytes
            if box.get('load') is not None:
                c['blocks compared with the tape\'s load'] += 1
                if bytes(mem[0xC000:0xD011]) != box['load']:
                    fail('the block is not what the tape loaded', box['blkn'])
                box['load'] = None
            return
        if pc in SHOT_SITES:
            end = pc + (4 if pc == KIND else 3)
            target_sp = sp if pc == KIND else regs[6] * 256 + regs[7]
            Ro, mo = run_orig(rom, mem, regs, end, target_sp)
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, end, target_sp)
            same('shot site %04X' % pc, Ro, mo, Rp, mp, sp)
            if model.nr.get(0x52, 10) != 10 or model.nr[7] != (3 if patch.steady else 0):
                fail('shot capture did not restore the machine', hex(pc))
            box['uh'] = box.get('uh', 0) + st.line - st.t_in
            box['uo'] = box.get('uo', 0) + Ro[T_] - regs[T_]
            box['orig_t'] += Ro[T_] - regs[T_]
            if pc == KIND:
                box['rock'] = bool(mem[regs[8] * 256 + regs[9] + 3] & 64)
            else:
                shot, cells = original_shot(rom, mem, regs, box.get('rock', False))
                draws.append(shot)
                c['compact rock plots' if pc == ROCK else 'wide plots'] += 1
                box['plot cells'] = cells
                for cell in cells:
                    backgrounds.setdefault(cell, cell_at(mem, 0xC000, *cell))
            return
        if pc == CL:
            if patch.steady:
                return
            c['clears'] += 1
            Ro, mo = run_orig(rom, mem, regs, pc + 3, sp)
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, pc + 3, sp, plain=True)
            same('the clear', Ro, mo, Rp, mp, sp)
            box['tcl'].add(Ro[T_] - regs[T_])
            box['orig_t'] += Ro[T_] - regs[T_]
            box['uh'] = box.get('uh', 0) + (st.line - st.t_in)
            box['uo'] = box.get('uo', 0) + Ro[T_] - regs[T_]
            if model.nr[7] & 3:
                fail('the clear leaves its speed', model.nr[7])
            return
        if pc == PRE:
            c['updates'] += 1
            Ro, mo = run_orig(rom, mem, regs, 0xB8FB)
            if patch.steady:            # the wait runs the game's handler: here each HALT counts a frame, R is not compared
                def tick(m_):
                    c['frames waited (steady speed)'] += 1
                    m_[FRAMES] = (m_[FRAMES] + 1) & 255
                Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, 0xB8FB, (sp - 2) & 0xFFFF, on_halt=tick)
                mo[FRAMES] = mp[FRAMES]
                Rp[R_] = Ro[R_]
            else:
                Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, 0xB8FB, (sp - 2) & 0xFFFF)
            same('the wait before the copies', Ro, mo, Rp, mp, (sp - 2) & 0xFFFF)
            return
        if regs[IFF_]:
            fail('interrupts on at a copy', hex(pc))
        Ro, mo = run_orig(rom, mem, regs, pc + 3, sp)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, pc + 3, sp)
        same('the copy at %04X' % pc, Ro, mo, Rp, mp, sp)
        t = Ro[T_] - regs[T_]
        box['t'][pc].add(t)
        box['orig_t'] += t
        if model.nr[7] & 3 != (3 if patch.steady else 0):
            fail('a copy leaves its speed', model.nr[7])
        if pc == C1:
            box['on'] = box.get('on') or (model.nr.get(0x6B) == 0x81)
            if not box['on']:
                fail('the tile layer is not switched on by the first pass', model.nr.get(0x6B))
        if any(model.nr.get(r, d) != d for r, d in ((0x52, 10), (0x53, 11), (0x54, 4), (0x55, 5))):
            fail('a copy leaves a page mapped', {hex(r): model.nr.get(r) for r in (0x52, 0x53, 0x54, 0x55)})
        bad = {k: v for k, v in model.c.items() if k.endswith('!')}
        if bad:
            fail('a write where none may be', bad)
        box['uh'] = box.get('uh', 0) + (st.line - st.t_in)
        box['uo'] = box.get('uo', 0) + t
        if pc == C3:
            d = int(box.pop('uh') - box.pop('uo'))
            c['most T an update\'s copies take over the original'] = max(c['most T an update\'s copies take over the original'], d)
            c['most T an update\'s copies take under the original'] = max(c['most T an update\'s copies take under the original'], -d)
            c['updates more than 5000 T off the original'] += abs(d) > 5000
            box.setdefault('ds', []).append((d, box.get('shown_n', 0)))
            return
        if pc == C2:
            return
        # the tile layer after the pass
        c['tile passes'] += 1
        got = layer(st)
        want = want_layer(patch, mem)
        c['cells compared'] += (ROWS + 4) * COLS
        box['under shots'] = {}
        box['shot screen'] = after_plot.copy()
        for cell, finished in after_plot.items():
            if cell_at(mem, 0xC000, *cell) != finished:
                fail('original erased a shot before the sprite commit', (c['tile passes'], cell))
        after_plot.clear()
        for cell, clean in backgrounds.items():
            composite = cell_at(mem, 0xC000, *cell)
            box['under shots'][cell] = (clean, composite)
            want.pop(cell, None)
            if clean in patch.want:
                want[cell] = patch.want[clean]
                c['painted scenery cells under shots'] += 1
        visible = shot_sprites(st)
        if visible != draws:
            fail('sprites differ from the original shot drawings', (c['tile passes'], len(visible), len(draws),
                 [(a[:3], b[:3], a[3] == b[3]) for a,b in zip(visible, draws) if a != b][:2]))
        c['shots compared'] += len(draws)
        c['shots erased'] += max(0, box.get('previous shots', 0) - len(draws))
        c['max simultaneous shots'] = max(c['max simultaneous shots'], len(draws))
        box['previous shots'] = len(draws)
        draws.clear()
        backgrounds.clear()
        wp, np_ = want_panel(patch, mem)
        c['painted panel cells shown'] += np_
        if bytes(st.l2) != wp:
            fail('Layer 2 is not the painted panel', (c['tile passes'], [i for i in range(8192) if st.l2[i] != wp[i]][:4]))
        c['painted cells shown'] += len(got)
        box['shown_n'] = len(got)
        full = st.work[sy['V_FULL']]
        c['cells left unpainted for want of a free definition'] += full
        c['most distinct tiles in a pass'] = max(c['most distinct tiles in a pass'], len({v for v in got.values()}))
        if full:
            c['passes with no free definition'] += 1
            if any(want.get(k) != v for k, v in got.items()) or len(want) - len(got) != full:
                fail('the tile layer is not the painted cells (a pass with no free definition)', c['tile passes'])
        elif got != want:
            dk = [k for k in set(got) | set(want) if got.get(k) != want.get(k)]
            fail('the tile layer is not the painted cells', (c['tile passes'], len(dk), sorted(dk)[:4]))
        box['shown'] = True
        if on_show:
            on_show(c['tile passes'], mem, got, st)

    fc, err = RZ.trace(rzx_path, {PRE, C1, C2, C3, CL, ISR, 0x8EB4, 0x8EE8} | set(SHOT_SITES) | ({LOAD, LOADED} if patch.blocks else set()), on, stop=stop)
    c['frames'] = fc
    if err:
        c['replay stopped!'] += 1
        ex['replay'].append(err)
    if c['frames a tile is not the screen cell\'s'] > 0.002 * c['frames checked'] + 1:
        fail('tiles shown over a screen that is not their cells', c['frames a tile is not the screen cell\'s'])
    c['T original copies'] = box['orig_t']
    c['T hooks'] = int(sum(st.t[k] for k in (C1, C2, C3, CL, KIND, WIDE, ROCK)))
    # Pace: a screen with more than about 250 painted cells costs the pass up to 4,000 T more than the copies give back
    # (about a twentieth of a frame, once an update); over the recording the hooks take the copies' time to 0.5%.
    if any(T_COPY.values()) and not patch.steady and c['updates']:
        if c['updates more than 5000 T off the original'] > 0.01 * c['updates'] + 5 or abs(c['T hooks'] - box['orig_t']) > 0.005 * fc * LINES * T_LINE:
            fail('the copies do not take the original\'s time', (c['updates more than 5000 T off the original'], c['updates'], c['T hooks'], box['orig_t']))
    ex['update T over the original, by painted cells shown (in 64s)'] = sorted((k, int(sum(v) / len(v)), max(v), len(v)) for k, v in
                                                                                 _group(box.get('ds', [])).items())
    ex['clear T'] = sorted(box['tcl'])
    ex['copy T'] = sorted((hex(k), sorted(v)) for k, v in box['t'].items())
    return c, dict(ex), states


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites). -> problems."""
    from . import nextboot
    from . import z80tonex as zt
    s = zt.Z80Snapshot(str(z80))
    if patch is not None:
        patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, getattr(patch, 'slot1', None), patch is not None)[0])
    tail = zt.choose_tail_addr(s, size, TAIL_ADDR, False)[0]
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if tail <= a < tail + size or (nexload and patch is None and 0x5B00 <= a < 0x5C00):
                continue                # (a patched build's setup puts the printer buffer back: compared)
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _differs(Ro, mo, Rp, mp, sp):
    bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
    return bad, [a for a in range(0x4000, 65536) if mp[a] != mo[a] and not sp - STACK <= a < sp][:6]


def unit_tests(patch, states, neg=None):
    """The paths the recordings do not reach, from captured states (site, memory, registers, state page)."""
    from .nextboot import alt_image
    c = collections.Counter()
    rom = bytes(alt_image(patch))
    sy = patch.syms
    by = collections.defaultdict(list)
    for pc, mem, regs, work in states:
        by[pc].append((bytearray(mem), list(regs)))

    def ok(name, cond):
        c[name if cond else name + '!'] += 1

    def want_of(mem):
        return want_layer(patch, mem)

    def run_c1(st, mem, regs):
        sp = regs[SP_]
        Ro, mo = run_orig(rom, mem, regs, C1 + 3, sp)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, C1, C1 + 3, sp)
        return _differs(Ro, mo, Rp, mp, sp) == ([], [])

    if not patch.steady:                        # the clear entered at each faster speed gives the caller's speed back
        for mem, regs in by[CL][-2:]:
            sp = regs[SP_]
            Ro, mo = run_orig(rom, mem, regs, CL + 3, sp)
            for speed in (1, 2, 3):
                Rp, mp, model = run_hook(patch, State(patch), rom, mem, regs, CL, CL + 3, sp, plain=True, speed=speed)
                ok('the clear keeps the caller\'s speed', _differs(Ro, mo, Rp, mp, sp) == ([], []) and model.nr[7] & 3 == speed)
    for mem, regs in by[C1][-3:]:
        want = want_of(mem)
        # the first pass on a page full of what the 128K left: cleared, then the painted cells
        st = State(patch)
        ok('first pass clears the tile layer\'s page and Layer 2', run_c1(st, mem, regs) and layer(st) == want and st.work[sy['V_INIT']] == 1
           and bytes(st.l2) == want_panel(patch, mem)[0])
        # the panel changes on the screen (a digit): only that cell is drawn again, and it is the painted one
        m2 = bytearray(mem)
        for k in range(8):
            m2[0x5080 + 5 + (k << 8)], m2[0x5080 + 6 + (k << 8)] = m2[0x5080 + 6 + (k << 8)], m2[0x5080 + 5 + (k << 8)]
        ok('panel cell changed', run_c1(st, m2, regs) and bytes(st.l2) == want_panel(patch, m2)[0])
        run_c1(st, mem, regs)
        # a second pass over the same picture: the same slots, nothing uploaded again
        before = bytes(st.tpage)
        ok('same picture again', run_c1(st, mem, regs) and bytes(st.tpage) == before)
        # the pass counter wraps from 255 to 1
        st.work[sy['V_STAMP']] = 255
        ok('pass counter wraps', run_c1(st, mem, regs) and st.work[sy['V_STAMP']] == 1 and layer(st) == want)
        # every slot shown by "this" pass already: no free definition, the new cells stay clear, the game the same
        st = State(patch)
        st.work[sy['V_INIT']] = 1
        st.tpage[:] = bytes(8192)
        for s_ in range(256):
            st.work[sy['STAMPS'] + s_] = 1          # the stamp this pass will take
        same = run_c1(st, mem, regs)
        ok('no free definition', same and not layer(st) and st.work[sy['V_FULL']] == min(255, len(want)) % 256 or (same and not layer(st) and len(want) > 255))
        # every slot owned by a cell that is not on screen: each new cell takes one, its old owner loses it
        st = State(patch)
        st.work[sy['V_INIT']] = 1
        st.tpage[:] = bytes(8192)
        onscreen = {k for k in (cell_at(mem, 0xC000, r, cc) for r in range(ROWS) for cc in range(COLS))}

        ents = [i for i, (hx, attr, px) in enumerate(e for e in patch.colours['cells'] if cell_keys(bytes.fromhex(e[0]), e[1]) is not None)]
        cells = [e for e in patch.colours['cells'] if cell_keys(bytes.fromhex(e[0]), e[1]) is not None]
        off = [i for i in ents if (bytes.fromhex(cells[i][0]), cells[i][1]) not in onscreen][:len(SLOTS)]
        for slot, i in zip(SLOTS, off):
            at = ent_addr(i) + E_SLOT
            st.table[ent_at(at)[0]][ent_at(at)[1]] = slot
            st.work[sy['OWNER'] + 2 * slot:sy['OWNER'] + 2 * slot + 2] = at.to_bytes(2, 'little')
        same = run_c1(st, mem, regs)
        stale = sum(1 for slot, i in zip(SLOTS, off)
                    if st.table[ent_at(ent_addr(i) + E_SLOT)[0]][ent_at(ent_addr(i) + E_SLOT)[1]] == slot
                    and st.work[sy['STAMPS'] + slot] == st.work[sy['V_STAMP']])
        ok('slots taken from cells off the screen', same and layer(st) == want and not stale)
    # Both player records, every class, and both hostile shooters including
    # the shared impact. The last pass fills all 18 slots on the same scenery.
    if by[C1]:
        source, copy_regs = by[C1][0]
        mem = bytearray(source)
        st = State(patch)
        expected = []
        clear_tiles = want_of(mem)
        for index in range(18):
            owner = (0x8430, 0x8450)[index] if index < 2 else 0x5B20 + 4 * (index - 2)
            rock = index >= 2 and index % 2 == 1
            site = ROCK if rock and index % 4 == 3 else WIDE
            regs = list(copy_regs)
            regs[8:10] = divmod(owner, 256)
            regs[PC_] = KIND
            mem[owner + 3] = 0xC0 if rock else 0x80 if index >= 2 else 0
            run_hook(patch, st, rom, mem, regs, KIND, KIND + 4, regs[SP_])
            mem[owner + 3] &= ~64                # impact can discard the shooter's kind
            for hero in (range(4) if index < 2 else (0,)):
                mem[0xFFFF - min(index, 1)] = hero
                regs[PC_] = site
                regs[6:8] = divmod(0xDD79 if site == ROCK else 0xD081, 256)
                regs[4:6] = divmod(0xC0FE, 256)  # right edge, crosses a screen third
                if index < 2 and hero < 3:
                    trial = State(patch)
                    run_hook(patch, trial, rom, mem, regs, site, site + 3, regs[6] * 256 + regs[7])
                    run_c1(trial, mem, copy_regs)
                    ok('player shot matches the plotter and selected class',
                       shot_sprites(trial) == [original_shot(rom, mem, regs, rock)[0]])
                else:
                    _, _, model = run_hook(patch, st, rom, mem, regs, site, site + 3, regs[6] * 256 + regs[7])
                    expected.append(original_shot(rom, mem, regs, rock)[0])
                    ok('capture restores speed and pages', model.nr[7] == (3 if patch.steady else 0)
                       and model.nr[0x50] == 255 and model.nr[0x52] == 10)
                    # Let the real plotter write on top of every previous shot.
                    _, mem = run_orig(rom, mem, regs, 0x8EE8 if site == ROCK else 0x8EB4)
        ok('eighteen overlapping shots and clean scenery at the screen edge',
           run_c1(st, mem, copy_regs) and shot_sprites(st) == expected and layer(st) == clear_tiles)
        for address, word in ((0xDD79, 0), (0xDD99, 1), (0xDDB9, 2), (0xDDD9, 3)):
            memory = bytearray(source)
            regs[PC_] = ROCK
            regs[6:8] = divmod(address, 256)
            # Asymmetric source rows exercise both bytes of each stack word.
            memory[address:address + 16] = bytes((n * 29 + word) & 255 for n in range(16))
            trial = State(patch)
            regs[PC_] = KIND
            memory[owner + 3] = 0xC0
            run_hook(patch, trial, rom, memory, regs, KIND, KIND + 4, regs[SP_])
            regs[PC_] = ROCK
            run_hook(patch, trial, rom, memory, regs, ROCK, ROCK + 3, address)
            run_c1(trial, memory, copy_regs)
            ok('compact rock shape from live source bytes', shot_sprites(trial) == [original_shot(rom, memory, regs, True)[0]])
        ok('all eighteen slots hidden on the first empty copy',
           run_c1(st, source, copy_regs) and not shot_sprites(st))
    for mem, regs in by[TITLE_SITE[0]][:1]:
        # the front end has returned to the loader: both blocks where the loader puts them, the main game with this
        # build's CALLs, nothing else touched, the stack not used, then the jump to the main game
        st = State(patch)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, TITLE_SITE[0], MAIN_AT, regs[SP_])
        other = [a for a in range(0x4000, 0x10000) if mp[a] != mem[a] and not B81_AT <= a < B81_AT + len(patch.main[0])
                 and not MAIN_AT <= a < MAIN_AT + len(patch.image)]
        ok('main game handed over after the front end', bytes(mp[B81_AT:B81_AT + len(patch.main[0])]) == patch.main[0]
           and bytes(mp[MAIN_AT:MAIN_AT + len(patch.image)]) == patch.image and not other and model.nr.get(0x52, 10) == 10 and not Rp[IFF_])
        # and that image is the tape's main game but for this build's sites
        diff = [a for a in range(len(patch.image)) if patch.image[a] != patch.main[1][a]]
        inside = all(any(s_ <= MAIN_AT + a < s_ + len(new) for s_, old, new in patch.game_sites) for a in diff)
        ok('the main game is the tape\'s but for the build\'s sites', bool(diff) and inside)
    for mem, regs in by[LOAD][:1]:
        # the blocks in tape order: the first for flag 0x80, then each next 0xC0 block, the second again after the last
        st = State(patch)
        order = []
        for flag, want_n in [(0x80, 0)] + [(0xC0, n) for n in range(1, NBLK)] + [(0xC0, 1), (0xC0, 2), (0x80, 0), (0xC0, 1)]:
            r2 = list(regs)
            r2[16] = flag
            Rp, mp, model = run_hook(patch, st, rom, mem, r2, LOAD, LOADED, regs[SP_])
            b = patch.blocks[want_n]
            order.append(bytes(mp[0xC000:0xC000 + len(b)]) == b and st.work[sy['V_BLKN']] == want_n
                         and (Rp[8] << 8 | Rp[9]) == 0xC000 + len(b) and bytes(mp[0x4000:0xC000]) == bytes(mem[0x4000:0xC000]))
        ok('blocks in tape order, round again after the last', all(order))
    for mem, regs in by[PRE][-2:]:
        # steady speed: the hook waits, the game's handler counting, until the update is 3 frames after the last
        q = Patch(z80=patch.z80, colours=patch.colours, steady=STEADY)
        for done in (0, 1, 2, 3, 7):
            st = State(q)
            m2 = bytearray(mem)
            st.work[sy['V_LAST']] = (m2[FRAMES] - done) & 255
            halts = [0]

            def tick(m):
                halts[0] += 1
                m[FRAMES] = (m[FRAMES] + 1) & 255
            sp = regs[SP_]
            Rp, mp, model = run_hook(q, st, rom, m2, regs, PRE, 0xB8FB, (sp - 2) & 0xFFFF, on_halt=tick)
            Ro, mo = run_orig(rom, m2, regs, 0xB8FB)
            mo[FRAMES] = mp[FRAMES]
            regs_same = all(Ro[i] == Rp[i] for i in CMP if i not in (R_, IFF_))
            ok('steady speed waits out the frames', halts[0] == max(0, STEADY - done) and regs_same and bytes(mp[0x4000:sp - STACK]) == bytes(mo[0x4000:sp - STACK])
               and st.work[sy['V_LAST']] == mp[FRAMES] and not Rp[IFF_])
    return c


def title_state(z80):
    """(site, memory, registers, state page) for the hand-over's unit case: the title snapshot's own memory with the
    registers the snapshot has, at the loader's instruction after the front end."""
    from skoolkit.snapshot import Snapshot
    sn = Snapshot.get(str(z80))
    mem = bytearray(play_view(sn))
    regs = [0] * 30
    regs[SP_] = 0x5BFE
    regs[PC_] = TITLE_SITE[0]
    regs[IFF_] = 1
    return TITLE_SITE[0], bytes(mem), tuple(regs), b''


def _code_patch(patch, sym, new):
    rc = bytearray(patch.rom_code)
    a = patch.syms[sym] - ROM_ORG
    rc[a:a + len(new)] = new
    return Patch(z80=patch.z80, colours=patch.colours, rom=bytes(rc), steady=patch.steady, blocks=patch.blocks, main=patch.main)


NEG_STOP = {name: 100 for name in ('a shot remains after erase', 'a shot has the wrong colour', 'a shot is missed')}


def negative_patches(patch):
    """Broken builds a verify run on a recording must catch: [(name, patch)]."""
    r = patch.rom_code[patch.syms['e_pre.n_r'] - ROM_ORG + 1]
    return [('a shot remains after erase', _code_patch(patch, 'shotpass.erase', bytes(8))),
            ('a shot has the wrong colour', _code_patch(patch, 'save_shot.colour', bytes((0xF6, 1)))),
            ('a shot is missed', _code_patch(patch, 'shotpass.visible', bytes((0xAF,)))),
            ('a tile\'s palette line is not written', _code_patch(patch, 'onecell.n_pal', b'\x00\x00\x00')),
            ('only half the chains are looked in', _code_patch(patch, 'find.n_bk', b'\xE6\x01')),
            ('a hidden panel cell is shown', _code_patch(patch, 'tilepass.n_vis', b'\xF6\x01')),
            ('the window\'s time is not read during the pass', _code_patch(patch, 'tilepass.n_tick', b'\x00\x00\x00')),
            ('the first copy\'s time is not waited out', _code_patch(patch, 'c1_end.w', b'\x00' * 8)),
            ('R one more after the wait before the copies', _code_patch(patch, 'e_pre.n_r', bytes((0xC6, (r + 1) & 255)))),
            ('the clear leaves 28 MHz', _code_patch(patch, 'e_cl.n_spd', b'\x00\x00\x00'))] + (
        [('a level block is not copied', _code_patch(patch, 'e_load.n_cp', b'\x00\x00'))] if patch.blocks else [])


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    os.makedirs(out, exist_ok=True)
    say('Game      : %s' % name)
    cmap = load_colours(z80)
    if not cmap:
        say('Engine    : gauntlet: no %s beside the snapshot (the build is the painted tiles: there is nothing to build without it)' % COLOURS_NAME)
        say('Result    : FAILED')
        return False
    blocks = main = None
    if getattr(a, 'tape', None):        # the tape: the levels' 31 blocks, and for a start at the title side A's two blocks
        from . import tapeset
        try:
            ts, si = tapeset.load(list(a.tape), tape_sets())
            blocks = level_blocks(ts)
            main = main_blocks(ts)
        except ValueError as e:
            say('Tape      : %s' % e)
            say('Result    : FAILED')
            return False
        say('Tape      : %s: %d level blocks, %d bytes, answered from memory (no "start the tape" wait)%s' % (
            load_profile()['tape_sets'][si]['name'], len(blocks), sum(len(b) for b in blocks),
            '; the main game (%d + %d bytes) handed over from memory after the front end' % (len(main[0]), len(main[1])) if main else ''))
    else:
        say('Tape      : none given: the build asks for the tape when its levels run out (--tape SIDE_B.tzx puts them in)')
    try:
        patch = Patch(z80=z80, colours=cmap, blocks=blocks, main=main)
        steady = Patch(z80=z80, colours=cmap, steady=STEADY, blocks=blocks, main=main)
    except ValueError as e:
        say('Engine    : gauntlet: %s' % e)
        say('Result    : FAILED')
        return False
    lines, _ = palette_lines(cmap)
    say('Engine    : gauntlet (nothing of the game changes; each cell of the play window the game is about to show -> a painted tile of the '
        'tile layer: %d painted cells, %d palette lines, %d pages)' % (len(patch.want), len(lines), len(patch.planes)))
    ok = True
    plain = os.path.join(out, name + '.nex')
    zt.convert(str(z80), plain, TAIL_ADDR, quiet=True, keep_printer_buffer=True)   # stack in 0x5B00-0x5BFF (tape start)
    bad = boot_check(plain, z80, None)
    ok = ok and not bad
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    for label, suffix, pt, mk in (('Sprites', '_sprites', patch, lambda: Patch(z80=z80, colours=cmap, blocks=blocks, main=main)),
                                  ('Steady', '_steady', steady, lambda: Patch(z80=z80, colours=cmap, steady=STEADY, blocks=blocks, main=main))):
        nex = os.path.join(out, name + suffix + '.nex')
        zt.convert(str(z80), nex, patch=pt, quiet=True)
        bad = boot_check(nex, z80, mk())
        ok = ok and not bad
        say('%-10s: %s  %s  boot %s%s' % (label, os.path.basename(nex), md5(nex), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200],
                                         '' if label == 'Sprites' else '  (the game at 28 MHz, every update %d frames after the last)' % STEADY))
    states = []
    quick = getattr(a, 'quick', None)
    for r in list(getattr(a, 'rzx', None) or []):
        cc, ex, st = verify(patch, r, stop=quick, collect=3)
        states += st
        fails = {k: v for k, v in cc.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d updates, %d tile passes, %d cells compared, %d painted cells shown, most distinct tiles in a pass %d, '
            '%d cells left unpainted for want of a free definition, %d frames checked against the visible screen (%d off) -> %s' % (
                os.path.basename(r), cc['frames'], cc['updates'], cc['tile passes'], cc['cells compared'], cc['painted cells shown'],
                cc['most distinct tiles in a pass'], cc['cells left unpainted for want of a free definition'], cc['frames checked'],
                cc['frames a tile is not the screen cell\'s'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('Shots     : %d compared, %d slots erased, %d simultaneous at most, %d painted scenery cells under shots' %
            (cc['shots compared'], cc['shots erased'], cc['max simultaneous shots'], cc['painted scenery cells under shots']))
        say('Shot draws: %d wide, %d compact, %d interrupts checked with shots on screen' %
            (cc['wide plots'], cc['compact rock plots'], cc['interrupts with shots checked']))
        say('Pace      : %s  the copies and the clear %d T in the original, the hooks %d T (%+.3f%% of the recording\'s time); an update at most '
            '%d T over, %d T under; %d of %d more than 5000 T off' % (
                os.path.basename(r), cc['T original copies'], cc['T hooks'], 100.0 * (cc['T hooks'] - cc['T original copies']) / max(1, cc['frames'] * LINES * T_LINE),
                cc['most T an update\'s copies take over the original'], cc['most T an update\'s copies take under the original'],
                cc['updates more than 5000 T off the original'], cc['updates']))
        if blocks:
            say('Levels    : %s  %d blocks asked for, %d of them loaded from the tape in the recording and equal to the build\'s' % (
                os.path.basename(r), cc['blocks asked for'], cc['blocks compared with the tape\'s load']))
        cs, exs, _ = verify(steady, r, stop=min(quick or 3000, 3000))
        fs = {k: v for k, v in cs.items() if k.endswith('!')}
        ok = ok and not fs
        say('Steady    : %s  %d frames, %d updates: the hooks and the tile layer as the other build -> %s' % (
            os.path.basename(r), cs['frames'], cs['updates'], 'IDENTICAL' if not fs else 'FAILED %s' % fs))
        for k, v in list(ex.items()) + list(exs.items()):
            if not k.startswith('copy T') and not k.startswith('clear T') and not k.startswith('update T'):
                say('            %s: %s' % (k, str(v)[:300]))
    if patch.title:                     # the hand-over has no recording: its unit case runs from the snapshot itself
        states = states + [title_state(z80)]
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.endswith('!')), 'PASS' if not uf else 'FAIL %s' % uf))
    if getattr(a, 'rzx', None):
        r0 = list(a.rzx)[0]
        missed = []
        if patch.title:                 # the game's own hooks never run in the front end's recording (they are proven on the
            negs = [('the main game is not copied', _code_patch(patch, 'e_main.n_cp', b'\x00\x00'))]      # main game's): the hand-over's
            for nm, q in negs:
                if not any(k.endswith('!') for k in unit_tests(q, [title_state(z80)])):
                    missed.append(nm)
        else:
            negs = negative_patches(patch)
            for nm, q in negs:
                cc, _, _ = verify(q, r0, stop=NEG_STOP.get(nm, quick or 2500))
                if (not cc['sprites differ from the original shot drawings!'] if nm in NEG_STOP else not any(k.endswith('!') for k in cc)):
                    missed.append(nm)
        ok = ok and not missed
        say('Negative  : %d broken builds (%s), %d detected%s' % (len(negs), os.path.basename(r0), len(negs) - len(missed),
                                                                 '' if not missed else '; NOT detected: ' + ', '.join(missed)))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
