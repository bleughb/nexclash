"""Atic Atac (Ultimate Play The Game, 1983, 48K) - engine 'atic_atac': every figure a hardware sprite.

Game facts (games/atic_atac.md, stages 0-2; asm/atic_atac_hooks.asm has the hook design):
  Every figure is ONE whole image drawn by pure XOR with two row blitters (0x9EDC = the "main" set
  0x9F97, 0x9F21 = the "alt" set 0x9FC1), one CALL site each in the row loop 0x9E9B. Graphic = id ->
  pointer table 0xA4BE (index id - 1) -> height byte h, then h rows of 2 bytes, drawn upward from
  line y; pixel x = L (shift x & 7). No logic reads figure pixels (and no logic reads an attribute
  the figure painter writes).
Build: converted writes go to a 1-bit SHADOW screen (page 26 at slot 3, shadow address = screen
  address | 0x2000), so ULA ^ shadow == the original screen at every moment; every shown image
  (key = graphic, x, y) is a few hardware sprites whose patterns come from a pattern STORE built here
  (pages 32-, one tile row = 2 patterns = 256 bytes; ink = index 1, enclosed paper + outline = index
  2 black, 0 transparent); the figure painter's attribute writes are NOPs (the colour is the sprite's).

This module: game facts, the pattern store, the patch object, the build (`auto`), the differential
verification (a Model of the patched machine: shadow page, hook RAM, sprite hardware; the expected
shown images come from the ORIGINAL's plots, independently of the store) and the unit tests.
"""
import collections
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

ROM_ORG = 0x2000
ALT_PAGE = 24                       # alt ROM copy source (bank 12)
SHPG = 26                           # shadow page (slot 3 during hooks): shadow 0x6000-0x77FF, tables 0x7800-
GPG, GP6, GP7 = 11, 0, 1            # the game's pages at slots 3 / 6 / 7
WPG = 28                            # work page (slot 7 during a setup hook): GADR 0x0000, build grid, built patterns
GADR_OFF, GB_OFF, OB_OFF = 0x0000, 0x0200, 0x0600
STPG = 32                           # first pattern store page (banks 16-)
SH, DIR, ENT, PAIRS = 0x6000, 0x7800, 0x7C00, 0x7ED0
NENT, ESZ, MAXP = 24, 26, 14       # asm/atic_atac_hooks.asm (ENT + NENT * ESZ <= PAIRS)
MAXH = 24                           # tallest graphic whose rows can be drawn one by one (the row mask: 3 bytes)
HOOK_RAM = (0x5B80, 0x5C00)         # variables + hook stack (printer buffer, never touched by the game)
V_OP1 = 0x5B84
HSTK_MIN = 0x5BA7 + 18              # lowest SP allowed in a hook (variables end + an interrupt's room)
TAIL_ADDR = 0x5B00
GTAB = 0xA4BE                       # graphic pointer table, index id - 1
OPSITES = (0x99D7, 0x9A36, 0x9A78, 0x9ADD, 0x9B88)       # run-time op bytes (00 / B6 / AE) of the drawers
OPWRITERS = (0x99CD, 0x9A0E, 0x9A54, 0x9ACF, 0x9B61)     # their LD (op),A
PAINTER = (0xA07D, 0xA093, 0xA0A6, 0xA0BA, 0xA0D8, 0xA113)   # the figure painter's LD (HL),D
# (address, original bytes, hook symbol, 'call' / 'jp'); a drawer site's first byte is the run-time op
SITES = ((0x9EA0, 'cddc9e', 'h_rowa', 'call'), (0x9EA9, 'cd219f', 'h_rowb', 'call'),
         (0x9F97, '1a3218', 'h_setm', 'jp'), (0x9FC1, '1a3219', 'h_seta', 'jp'),
         (0x8093, '210040', 'h_clear', 'jp'), (0x9C75, 'b677e1', 'h_line', 'jp'),
         (0x99D7, '00772c', 'h_o1', 'jp'), (0x9A36, '00772c', 'h_o2', 'jp'), (0x9A78, '00772c', 'h_o3', 'jp'),
         (0x9ADD, '00772c', 'h_o4', 'jp'), (0x9B88, '00772c', 'h_o5', 'jp'), (0xA1E6, '771324', 'h_txt', 'jp'))
# bytes the hooks rely on: the blitters they fall back to, the row advance, the self-modified JR
# opcodes, the game's own bytes next to a patched instruction, the continuations
FACTS = ((0x9EDC, 'ebd556235e23eb'), (0x9F21, 'ebd556235e23eb'), (0x9EE4, '18'), (0x9F29, '18'),
         (0x9F03, '257c2fe607c0'), (0x9F9A, '5e'), (0x9F9B, '0e00'), (0x9FC4, '5e'), (0x9FC5, '32115e'),
         (0x8096, '01c018af'), (0x9C78, 'c9'), (0x99DA, '10f9'), (0x9A39, '79a7'), (0x9A7B, '79a7'),
         (0x9AE0, '10f9'), (0x9B8B, '79a7'), (0xA1E9, '10fad1'), (0x9EA3, 'd9'), (0x9EAC, 'd918'))
# where each forked segment ends (None: the routine's own return, with the return address at sp + off)
SEG_END = {0x9EA0: 0x9EA3, 0x9EA9: 0x9EAC, 0x9F97: 0x9F9B, 0x9FC1: 0x9FC5, 0x99D7: 0x99DA, 0x9A36: 0x9A39,
           0x9A78: 0x9A7B, 0x9ADD: 0x9AE0, 0x9B88: 0x9B8B, 0xA1E6: 0xA1E9}
SEG_RET = {0x8093: 0, 0x9C75: 2}    # return address at sp + n; the hook / original run until it is popped
CMP = list(range(0, 15)) + list(range(16, 25)) + [26, 27, 28]    # all registers but R, T, MEMPTR (AF' incl.)

# Next palette (RRRGGGBB) of the 16 palette offsets (ink + 8 * BRIGHT); sprite colour index 1 = ink,
# 2 = black (outline, enclosed paper), 0 = transparent (0xE3 on every offset)
ZXCOL = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'atic_atac.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_atic_atac(snap):
    """48K, the game's signature at its 0x9EDC blitter (the loader state has it too)."""
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['hex'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


# ---------------------------------------------------------------------------------------------
# Graphics -> the pattern store
# ---------------------------------------------------------------------------------------------

def graphic(peek, gid):
    """Graphic address and height of id gid (1-255); ids past the 211 real table entries read the
    data that follows the table (the game does too)."""
    p = GTAB + 2 * (gid - 1)
    a = peek(p) | peek(p + 1) << 8
    return a, peek(a)


def rows_of(peek, a, hc):
    """The bottom hc rows (16 bits each, bottom row first, as the game draws them upward)."""
    return [peek((a + 1 + 2 * i) & 0xFFFF) << 8 | peek((a + 2 + 2 * i) & 0xFFFF) for i in range(hc)]


def kept_rows(h):
    """Rows kept of a graphic of height h: the bottom 192 (nothing above line 0 can show)."""
    return min(h, 192)


def build_image(rows, hc):
    """Image grid [row][col], hc + 2 rows x 18 columns: row 0 = the outline row above the top ink
    row, column 0 = the outline column left of the figure. Values: 1 ink, 2 black (outline and the
    paper the ink encloses: 4-connected flood from outside through non-ink), 0 transparent. The
    outline = the 4-neighbours (left / right / up / down only, no diagonal corner pixels) of ink /
    enclosed paper (Dean 2026-10-26)."""
    H, W = hc + 2, 18
    ink = [[0] * W for _ in range(H)]
    for i in range(hc):
        v = rows[i]
        for j in range(16):
            if v >> (15 - j) & 1:
                ink[hc - i][1 + j] = 1
    out = [[False] * W for _ in range(H)]
    stack = [(r, c) for r in range(H) for c in range(W) if r in (0, H - 1) or c in (0, W - 1)]
    while stack:
        r, c = stack.pop()
        if out[r][c] or ink[r][c]:
            continue
        out[r][c] = True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if 0 <= r + dr < H and 0 <= c + dc < W:
                stack.append((r + dr, c + dc))
    shape = [[bool(ink[r][c]) or not out[r][c] for c in range(W)] for r in range(H)]
    img = [[0] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            if ink[r][c]:
                img[r][c] = 1
            elif shape[r][c]:
                img[r][c] = 2
            elif any(shape[r + dr][c + dc] for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
                     if 0 <= r + dr < H and 0 <= c + dc < W):
                img[r][c] = 2
    return img


def tile_rows(img):
    """Pattern store bytes of an image: per tile row (16 image rows) the left 16x16 4-bit pattern
    (128 bytes, left pixel in the high nibble) then the right one."""
    H = len(img)
    T = (H + 15) // 16
    out = bytearray()
    for tr in range(T):
        for tc in range(2):
            for k in range(16):
                r = 16 * tr + k
                row = img[r] if r < H else [0] * 18
                for b in range(8):
                    c = 16 * tc + 2 * b
                    hi = row[c] if c < 18 else 0
                    lo = row[c + 1] if c + 1 < 18 else 0
                    out.append(hi << 4 | lo)
    return bytes(out), T


def build_store(peek):
    """-> (directory 1024 bytes: id x (page, tile-row index, tile rows, hc), {page: 8192 bytes},
    {graphic address: (id, h, hc, tile rows)})."""
    pages, dirb, seen = {}, bytearray(1024), {}
    cur, row = STPG, 0
    for gid in range(1, 256):
        a, h = graphic(peek, gid)
        if h == 0:
            continue
        if a not in seen:
            hc = kept_rows(h)
            data, T = tile_rows(build_image(rows_of(peek, a, hc), hc))
            if row + T > 32:
                cur, row = cur + 1, 0
            pg = pages.setdefault(cur, bytearray(8192))
            pg[row * 256:row * 256 + len(data)] = data
            seen[a] = (cur, row, T, hc, gid, h)
            row += T
        pgn, r0, T, hc = seen[a][:4]
        dirb[4 * gid:4 * gid + 4] = bytes((pgn, r0, T, hc))
    return bytes(dirb), {p: bytes(d) for p, d in pages.items()}, seen


def palette():
    """256 bytes: per palette offset k: 0xE3 (transparent), ink colour k, black, 13 x black."""
    out = bytearray()
    for k in range(16):
        out += bytes([0xE3, ZXCOL[k], 0x00]) + bytes(13)
    return bytes(out)


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

def static_check(code, org=ROM_ORG):
    """Decode the hook code: no EXX / EX AF,AF' / IY / LD I / IM / DI / EI / RETN, nothing at
    0x3D00-0x3DFF (DivMMC trap, LEARNINGS 1.4). Returns a list of findings."""
    from .simrun import disasm
    bad = []
    if org + len(code) > 0x3D00:
        bad.append(('code reaches 0x3D00', org + len(code)))
    mem = bytearray(65536)
    mem[org:org + len(code)] = code
    a = org
    while a < org + len(code):
        if mem[a] == 0xED and mem[a + 1] in (0x91, 0x92):           # Z80N NEXTREG nn,n / nn,A
            a += 4 if mem[a + 1] == 0x91 else 3
            continue
        text, n = disasm(mem, a)
        t = text.upper()
        if t.startswith(('EXX', 'EX AF', 'DI', 'EI', 'IM ', 'RETN', 'LD I,')) or 'IY' in t:
            bad.append((text, a))
        a += n
    return bad


class AticAtacPatch:
    name = 'Atic Atac figures -> hardware sprites (altrom 0x2000- + shadow page 26 at slot 3; XOR shadow)'

    def __init__(self, prof=None, edit=None, peek=None):
        """edit: {ROM address: bytes} over the hook code (negative controls); peek: the game's memory
        (the pattern store, the drawer ops)."""
        from .build import rom48
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.edit = edit or {}
        code = bytearray.fromhex(h['rom'])
        for a, d in self.edit.items():
            code[a - ROM_ORG:a - ROM_ORG + len(d)] = d
        self.rom_code = bytes(code)
        self.setup_code = bytes.fromhex(h['setup'])
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hook code too long (must end below 0x3D00)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        page = bytearray(rom48()[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = HOOK_RAM[0] - TAIL_ADDR
        self.stub_extra = b''
        self.extra_banks = {}
        self.dirb, self.store, self.seen = bytes(1024), {}, {}
        self.ops = bytes(5)
        self.sites = []
        self.interiors = set()
        self.peek = None
        self._sites(bytes(5))
        if peek is not None:
            self.prepare(peek)

    def _sites(self, ops):
        s = []
        for a, old, sym, kind in SITES:
            o = bytearray.fromhex(old)
            if a in OPSITES:
                o[0] = ops[OPSITES.index(a)]
            new = bytes([0xCD if kind == 'call' else 0xC3]) + self.syms[sym].to_bytes(2, 'little')
            s.append((a, bytes(o), new))
        for k, a in enumerate(OPWRITERS):
            s.append((a, bytes([0x32]) + OPSITES[k].to_bytes(2, 'little'),
                      bytes([0x32]) + (V_OP1 + k).to_bytes(2, 'little')))
        for a in PAINTER:
            s.append((a, b'\x72', b'\x00'))
        self.sites = s
        self.interiors = {a + k for a, old, new in s for k in range(1, len(old))} | {0x9F9A, 0x9FC4}

    def check(self, peek):
        """Refuse a snapshot that is not the expected version (or is already patched)."""
        for a, old, new in self.sites:
            cur = bytes(peek(a + k) for k in range(len(old)))
            if a in OPSITES:
                if cur[0] not in (0x00, 0xB6, 0xAE) or cur[1:] != old[1:]:
                    raise ValueError('unexpected drawer code at %d (%s)' % (a, cur.hex()))
            elif cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected version of the '
                                 'game, or already patched' % (a, cur.hex(), old.hex()))
        for a, hx in FACTS:
            want = bytes.fromhex(hx)
            cur = bytes(peek(a + k) for k in range(len(want)))
            if cur != want:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), hx))

    def prepare(self, peek):
        """The pattern store, the directory and the setup data from the game's memory; the banks."""
        self.check(peek)
        self.peek = peek
        self.ops = bytes(peek(a) for a in OPSITES)
        self._sites(self.ops)
        self.dirb, self.store, self.seen = build_store(peek)
        self.gaddr = {g: graphic(peek, g)[0] for g in range(1, 256)}
        wk = bytearray(8192)
        for g, a in self.gaddr.items():
            wk[GADR_OFF + 2 * g:GADR_OFF + 2 * g + 2] = a.to_bytes(2, 'little')
        self.work = bytes(wk)
        self.stub_extra = self.setup_code + self.ops + palette()
        shp = bytearray(8192)
        shp[DIR - SH:DIR - SH + 1024] = self.dirb
        self.extra_banks = {ALT_PAGE // 2: self.page + bytes(8192), SHPG // 2: bytes(shp) + bytes(8192),
                            WPG // 2: self.work + bytes(8192)}
        for pg, data in self.store.items():
            b = self.extra_banks.setdefault(pg // 2, bytearray(16384))
            k = (pg & 1) * 8192
            b[k:k + 8192] = data
        self.extra_banks = {b: bytes(d) for b, d in self.extra_banks.items()}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('this patch is for the 48K version')
        from .build import rom48
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        mem = bytes(rom48()) + bytes(ram)               # the unpatched game (the patch keeps its peek)
        self.prepare(mem.__getitem__)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        # the hook RAM starts as the verifier's model does: zero (the .z80's loader bytes there are dead
        # once the game runs: nothing reads 0x5B00-0x5BFF, RZX scan) + the drawer ops the setup copies
        ram[HOOK_RAM[0] - 0x4000:HOOK_RAM[1] - 0x4000] = bytes(HOOK_RAM[1] - HOOK_RAM[0])
        ram[V_OP1 - 0x4000:V_OP1 - 0x4000 + 5] = self.ops
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[0:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])

    def alt_image(self):
        from .build import rom48
        alt = bytearray(rom48())
        alt[0x2000:0x4000] = self.page
        return bytes(alt)


# ---------------------------------------------------------------------------------------------
# Verification: the patched machine's state outside the original's memory
# ---------------------------------------------------------------------------------------------
WIDTH_PX = 32


def scr_xy(a):
    """(column, line) of a pixel-area address 0x4000-0x57FF."""
    return a & 31, ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)


class HW:
    """Sprite hardware as the hooks drive it: attributes (NEXTREG 0x34-0x39), pattern RAM (port 0x303B
    slot select + port 0x5B data), the MMU slots 3 / 7 (0x53 / 0x57) and the CPU speed (0x07)."""
    OK_REGS = (0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x53, 0x57)

    def __init__(self):
        self.attr = [[0] * 5 for _ in range(128)]
        self.sel = 0
        self.pat = bytearray(16384)
        self.ptr = 0
        self.cpu = 0
        self.cur3, self.cur6, self.cur7 = GPG, GP6, GP7
        self.bad = []

    def nextreg(self, reg, val):
        if reg == 0x34:
            self.sel = val & 0x7F
        elif 0x35 <= reg <= 0x39:
            self.attr[self.sel][reg - 0x35] = val
        elif reg == 0x53:
            self.cur3 = val
        elif reg == 0x57:
            self.cur7 = val
        elif reg == 0x56:
            self.cur6 = val
        elif reg == 0x07:
            self.cpu = val
        else:
            self.bad.append(('NEXTREG %02X' % reg, val))

    def out(self, port, val):
        if port == 0x303B:
            self.ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.ptr] = val
            self.ptr = (self.ptr + 1) & 0x3FFF
        else:
            self.bad.append(('OUT %04X' % port, val))

    def copy(self):
        h = HW.__new__(HW)
        h.attr = [list(a) for a in self.attr]
        h.sel, h.ptr, h.cpu, h.cur3, h.cur6, h.cur7 = self.sel, self.ptr, self.cpu, self.cur3, self.cur6, self.cur7
        h.pat = bytearray(self.pat)
        h.bad = []
        return h

    def pixels(self, idx):
        """Sprite idx -> {(x, y): (palette offset, 4-bit value)} (screen coordinates; 4-bit sprites)."""
        a0, a1, a2, a3, a4 = self.attr[idx]
        if not a3 & 0x80 or not a4 & 0x80:
            return {}
        x0 = a0 + (a2 & 1) * 256 - 32
        y0 = a1 + (a4 & 1) * 256 - 32
        po = a2 >> 4
        base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
        out = {}
        pat = self.pat
        for j in range(16):
            for k in range(8):
                b = pat[base + j * 8 + k]
                if b >> 4:
                    out[(x0 + 2 * k, y0 + j)] = (po, b >> 4)
                if b & 15:
                    out[(x0 + 2 * k + 1, y0 + j)] = (po, b & 15)
        return out


class Model:
    """The patched machine beyond the original's memory: shadow page (+ the hook tables in it), hook RAM,
    the sprite hardware, and the attribute cells the figure painter's NOPs left different."""

    def __init__(self, patch, ops):
        self.patch = patch
        sh = bytearray(8192)
        sh[DIR - SH:DIR - SH + 1024] = patch.dirb
        self.sh = sh                                   # page 26
        self.hram = bytearray(HOOK_RAM[1] - HOOK_RAM[0])
        self.hram[V_OP1 - HOOK_RAM[0]:V_OP1 - HOOK_RAM[0] + 5] = bytes(ops)
        self.hw = HW()
        self.stale = {}                                # attribute cell offset -> the patched machine's value
        self.wk = bytearray(patch.work)                # page 28

    def copy(self):
        m = Model.__new__(Model)
        m.patch = self.patch
        m.sh, m.hram, m.wk = bytearray(self.sh), bytearray(self.hram), bytearray(self.wk)
        m.hw = self.hw.copy()
        m.stale = dict(self.stale)
        return m

    def page(self, n):
        if n == SHPG:
            return self.sh
        if n == WPG:
            return self.wk
        pg = self.patch.store.get(n)
        return pg


class _O:
    """Original machine memory: the replay's bytes (get) + an overlay of this run's writes."""

    def __init__(self, get):
        self.get, self.ov, self.romw = get, {}, set()

    def __getitem__(self, a):
        v = self.ov.get(a)
        return self.get(a) if v is None else v

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.ov[a] = v
        else:
            self.romw.add(a)

    def __len__(self):
        return 65536


class _P(_O):
    """Patched machine memory: alt ROM below 0x4000, the patch sites, the ULA (= original ^ shadow), the
    patched attributes (original except the stale cells), hook RAM, slot 3 / slot 7 pages from the model."""

    def __init__(self, get, model, alt, psite):
        _O.__init__(self, get)
        self.m, self.alt, self.psite = model, alt, psite
        self.hw = model.hw
        self.sh0 = bytes(model.sh[:6144])
        self.wp = set()                     # (page, offset) written in a mapped page
        self.hw_w = set()                   # hook RAM offsets written
        self.bad = []

    def __getitem__(self, a):
        if a < 0x4000:
            return self.alt[a]
        hw = self.hw
        if 0x6000 <= a < 0x8000 and hw.cur3 != GPG:          # a page mapped by the hook (before the
            pg = self.m.page(hw.cur3)                        # game RAM this run wrote there)
            return pg[a - 0x6000] if pg is not None else 0
        if a >= 0xE000 and hw.cur7 != GP7:
            pg = self.m.page(hw.cur7)
            return pg[a - 0xE000] if pg is not None else 0
        if 0xC000 <= a < 0xE000 and hw.cur6 != GP6:
            pg = self.m.page(hw.cur6)
            return pg[a - 0xC000] if pg is not None else 0
        v = self.ov.get(a)
        if v is not None:
            return v
        if a < 0x5800:
            return self.get(a) ^ self.sh0[a - 0x4000]
        if a < 0x5B00:
            return self.m.stale.get(a - 0x5800, self.get(a))
        if HOOK_RAM[0] <= a < HOOK_RAM[1]:
            return self.m.hram[a - HOOK_RAM[0]]
        w = self.psite.get(a)
        if w is not None:
            return w
        return self.get(a)

    def __setitem__(self, a, v):
        if a < 0x4000:
            self.romw.add(a)
        elif 0x6000 <= a < 0x8000 and self.hw.cur3 != GPG:
            if self.hw.cur3 == SHPG:
                self.m.sh[a - 0x6000] = v
                self.wp.add((SHPG, a - 0x6000))
            else:
                self.bad.append(('write to page %d' % self.hw.cur3, a))
        elif a >= 0xE000 and self.hw.cur7 != GP7:
            if self.hw.cur7 == WPG:
                self.m.wk[a - 0xE000] = v
                if a - 0xE000 < GB_OFF:
                    self.bad.append(('wrote the work page\'s GADR table', a))
            else:
                self.bad.append(('write to slot 7 page %d' % self.hw.cur7, a))
        elif 0xC000 <= a < 0xE000 and self.hw.cur6 != GP6:
            self.bad.append(('write to slot 6 page %d' % self.hw.cur6, a))
        elif HOOK_RAM[0] <= a < HOOK_RAM[1]:
            self.m.hram[a - HOOK_RAM[0]] = v
            self.hw_w.add(a)
        else:
            self.ov[a] = v


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _machine(Sim, mem, regs, slot, hw=None):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)
    if hw is not None:
        R = sim.registers
        ed = sim.after_ED

        def nn():
            p = R[24]
            hw.nextreg(mem[(p + 2) & 0xFFFF], mem[(p + 3) & 0xFFFF])
            R[15] = R2[R[15]]; R[24] = (p + 4) & 0xFFFF; R[25] += 20

        def na():
            p = R[24]
            hw.nextreg(mem[(p + 2) & 0xFFFF], R[0])
            R[15] = R2[R[15]]; R[24] = (p + 3) & 0xFFFF; R[25] += 17
        ed[0x91], ed[0x92] = nn, na

        class Tr:
            def read_port(s, regs_, port):
                hw.bad.append(('IN %04X' % port, 0))
                return 0xFF

            def write_port(s, regs_, port, value, *x):
                hw.out(port, value)
        sim.set_tracer(Tr())
    return sim


def _seg(pc, sp0, get):
    """Stop condition of the segment starting at hook site pc."""
    if pc in SEG_END:
        end = SEG_END[pc]
        return lambda R: R[24] == end
    if pc in SEG_RET:
        n = SEG_RET[pc]
        ret = get(sp0 + n) | get(sp0 + n + 1) << 8
        sp1 = (sp0 + n + 2) & 0xFFFF
        return lambda R: R[24] == ret and R[12] == sp1
    end = pc + (1 if pc in PAINTER else 3)          # one instruction: the op writers / the painter
    return lambda R: R[24] == end


def attr_cells(ov):
    return [a for a in ov if 0x5800 <= a < 0x5B00]


def event(patch, alt, psite, model, get, regs, pc, limit=3000000):
    """Run the original and the patched code from site pc to the end of the segment, both from the same
    state (get = the original machine's memory; the patched machine = it + the model). The model is
    updated. Returns (failures, so, o, p, stats)."""
    Sim = _rw()
    f = []
    sp0 = regs[12]
    stop = _seg(pc, sp0, get)
    o = _O(get)
    so = _machine(Sim, o, list(regs), 'o')
    R, ops, mem = so.registers, so.opcodes, so.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return [('original did not return', pc)], so, o, None, {}
    hw = model.hw
    hw.bad = []
    p = _P(get, model, alt, psite)
    sp_ = _machine(Sim, p, list(regs), 'p', hw)
    P, pops, pmem = sp_.registers, sp_.opcodes, sp_.memory
    n = 0
    minsp = 0x10000
    hook_sp = None
    fast = 0
    inter = patch.interiors
    while not stop(P):
        pcx = P[24]
        if pcx < 0x4000:
            if hook_sp is None:
                hook_sp = P[12]
            if 0x3D00 <= pcx < 0x3E00:
                f.append(('code fetched at 0x3D00-0x3DFF', pcx))
                break
            s = P[12]
            if HOOK_RAM[0] <= s <= HOOK_RAM[1]:
                if s < minsp:
                    minsp = s
                if s < HSTK_MIN:
                    f.append(('hook stack too deep for an interrupt', pcx, s))
                    break
            elif s < hook_sp - 4:
                f.append(('hook pushed below the game SP', pcx, s))
                break
        else:
            hook_sp = None
            if pcx in inter:
                f.append(('jump into a patched instruction', pcx))
                break
        t0 = P[25]
        pops[pmem[pcx]]()
        if hw.cpu == 3:
            fast += P[25] - t0
        n += 1
        if n > limit:
            f.append(('patched did not return', pc))
            break
    stats = {'T orig': so.registers[25] - regs[25], 'T patched': P[25] - regs[25] - fast + fast // 8,
             'minsp': minsp}
    ro, rp = so.registers, sp_.registers
    d = [i for i in CMP if ro[i] != rp[i]]
    if d:
        f.append(('registers differ', d, [(ro[i], rp[i]) for i in d][:4]))
    if hw.cur3 != GPG or hw.cur6 != GP6 or hw.cur7 != GP7:
        f.append(('slots 3 / 6 / 7 not given back', hw.cur3, hw.cur6, hw.cur7))
    if hw.cpu != 0:
        f.append(('left at 28 MHz', hw.cpu))
    for b in hw.bad:
        f.append(('unexpected hardware access',) + tuple(b))
    for b in p.bad:
        f.append(('bad write',) + tuple(b))
    if p.romw - o.romw:
        f.append(('patched code wrote ROM', sorted(p.romw - o.romw)[:3]))
    for a in o.ov:
        if HOOK_RAM[0] <= a < HOOK_RAM[1]:
            f.append(('the original wrote the hook RAM', a))
            break
    # memory: everything outside screen / attributes / hook RAM / the dead stack is equal
    spend = ro[12]
    dead = range(spend - 64, spend)
    for a in set(o.ov) | set(p.ov):
        if a < 0x5B00 or HOOK_RAM[0] <= a < HOOK_RAM[1] or a in dead or a in OPSITES:
            continue                    # (an op byte: the hook keeps it in V_OP1.., checked by the caller)
        if o[a] != p[a]:
            f.append(('memory differs', a, o[a], p[a]))
            break
    # the screen: ULA ^ shadow == the original, every byte either machine wrote
    sh = model.sh
    touched = {a for a in o.ov if 0x4000 <= a < 0x5800} | {a for a in p.ov if 0x4000 <= a < 0x5800}
    touched |= {0x4000 + off for pg, off in p.wp if pg == SHPG and off < 6144}
    for a in touched:
        want = o[a]
        have = p.ov.get(a)
        if have is None:
            have = get(a) ^ p.sh0[a - 0x4000]
        if (have ^ sh[a - 0x4000]) != want:
            f.append(('screen differs (ULA ^ shadow)', a, want, have ^ sh[a - 0x4000]))
            break
    for pg, off in p.wp:
        if off >= 0x1800 and not (DIR - SH <= off < 0x2000):
            f.append(('wrote the shadow page between the shadow and the tables', off))
            break
    # attributes: equal writes, except the figure painter's skipped ones; update the stale cells
    cells = set(attr_cells(o.ov)) | set(attr_cells(p.ov))
    for a in cells:
        c = a - 0x5800
        ov_ = o[a]
        pv = p.ov.get(a)
        if pv is None:
            pv = model.stale.get(c, get(a))
        if pc in PAINTER:
            pass
        elif pv != ov_ and (a in o.ov) != (a in p.ov):
            f.append(('attribute written by one machine only', a))
            break
        elif pv != ov_ and a in o.ov and a in p.ov:
            f.append(('attribute value differs', a, ov_, pv))
            break
        if pv != ov_:
            model.stale[c] = pv
        else:
            model.stale.pop(c, None)
    return f, so, o, p, stats


# ---------------------------------------------------------------------------------------------
# The expectation: which images must be shown, derived from the ORIGINAL's plots (not from the store)
# ---------------------------------------------------------------------------------------------
KIND = {0x9EA0: 'rowm', 0x9EA9: 'rowa', 0x9F97: 'setm', 0x9FC1: 'seta', 0x8093: 'clear', 0x9C75: 'line',
        0xA1E6: 'txt'}
KIND.update({a: 'obj' for a in OPSITES})
KIND.update({a: 'opw' for a in OPWRITERS})
KIND.update({a: 'paint' for a in PAINTER})
WATCH = set(KIND)


def expected_map(P):
    """{(x, y): 1 ink / 2 black} for the plotted pixels P: black = the paper P encloses (4-connected
    flood of the non-ink pixels from outside P's box) and the 4-neighbours (left / right / up / down,
    no diagonals) of ink and enclosed paper."""
    if not P:
        return {}
    x0 = min(x for x, y in P) - 1
    x1 = max(x for x, y in P) + 1
    y0 = min(y for x, y in P) - 1
    y1 = max(y for x, y in P) + 1
    seen, stack = set(), [(x0, y0)]
    while stack:
        q = stack.pop()
        if q in seen or q in P or not (x0 <= q[0] <= x1 and y0 <= q[1] <= y1):
            continue
        seen.add(q)
        x, y = q
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    shape = set(P) | {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
                      if (x, y) not in seen and (x, y) not in P}
    m = {q: 1 for q in P}
    for x, y in shape:
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in shape or q not in P:
                m.setdefault(q, 2)
    return m


class Expect:
    """The images the hooks must show, from the ORIGINAL's plots: a plot belongs to the GROUP (graphic G of
    its id in the snapshot, x, base line): G itself toggles every row of the group, a one-row slice
    (height 1 at G + 2k, drawn at base - k: the appear / death effect) toggles row k. The group's image =
    the XOR of the pixels the original plotted into it; mask 0 = pending (the last image stays shown)
    until another owner plots or the owner reuses the entry. Plus the expected shadow (the converted
    rows' changes). Hook rules mirrored: flush of other owners' pending groups, 24 entries."""

    def __init__(self):
        self.ents = []               # {'key': (G, x, base), 'own', 'mask', 'col', 'P': XOR of plotted pixels,
                                     #  'img': (pixels, mask) last shown}
        self.acc = {'m': None, 'a': None}    # [entry or None, pixels, row events] of the plot in progress per set
        self.sh = bytearray(6144)
        self.bad = []

    def copy(self):
        e = Expect()
        ids = {}
        for x in self.ents:
            ids[id(x)] = dict(x)
            e.ents.append(ids[id(x)])
        e.acc = {k: (None if v is None else [ids.get(id(v[0])), set(v[1]), v[2]]) for k, v in self.acc.items()}
        e.sh = bytearray(self.sh)
        return e

    def close(self, k):
        v = self.acc[k]
        if v is not None:
            e = v[0]
            if e is not None:
                e['P'] = e['P'] ^ frozenset(v[1])
                if e['mask']:
                    e['img'] = (e['P'], e['mask'])
            self.acc[k] = None

    def before_setup(self, k):
        """A setup of set k: its previous plot is complete, and so is the other set's once it had rows
        (setups only happen outside the row loop; the 0x9FCA move sets up both before any row)."""
        self.close(k)
        o = 'a' if k == 'm' else 'm'
        if self.acc[o] is not None and self.acc[o][2]:
            self.close(o)

    @staticmethod
    def resolve(sp, gid, de, x, y, h):
        """-> (group key, G's height H, rows toggled, kind) or None (no image). sp = the snapshot."""
        if not gid:
            return None
        G, hs = graphic(sp, gid)
        H = min(hs, 192)
        if de == G and h == hs:
            return (G, x, y), H, (1 << H) - 1 if H <= MAXH else 1, 'stored'
        k2 = de - G
        if h == 1 and 0 <= k2 < 512 and not k2 & 1 and k2 // 2 < H <= MAXH and y + k2 // 2 < 256:
            k = k2 // 2
            return (G, x, y + k), H, 1 << k, 'slice'
        return None

    def setup(self, k, res, own, col):
        """A converted setup (x < 192, h > 0) of set k; res = resolve(...) or None."""
        if res is None:
            self.acc[k] = [None, set(), 0]          # rows still go to the shadow; no image
            return
        key, H, tm, kind = res
        self.ents = [e for e in self.ents if not (e['mask'] == 0 and e['own'] != own)]
        for e in self.ents:
            if e['key'] == key:
                e['mask'] ^= tm
                if e['mask']:
                    e['col'] = col
                break
        else:
            e = {'key': key, 'own': own, 'mask': tm, 'col': col, 'H': H, 'P': frozenset(), 'img': None}
            for i, x in enumerate(self.ents):
                if x['mask'] == 0 and x['own'] == own:
                    self.ents[i] = e
                    break
            else:
                if len(self.ents) < NENT:
                    self.ents.append(e)
                else:
                    self.bad.append(('entry table full: image not shown', key, len(self.ents)))
                    e = None
        self.acc[k] = [e, set(), 0]

    def clear(self):
        self.close('m')
        self.close('a')
        self.ents = []
        self.sh = bytearray(6144)

    def rows(self, k, o, get):
        """One row event of set k: the original's screen change = this row's pixels."""
        v = self.acc[k]
        if v is None:
            return
        v[2] += 1
        px = v[1]
        for a, nv in o.ov.items():
            if 0x4000 <= a < 0x5800:
                d = nv ^ get(a)
                if d:
                    self.sh[a - 0x4000] ^= d
                    cx, y = scr_xy(a)
                    for b in range(8):
                        if d >> (7 - b) & 1:
                            px ^= {(cx * 8 + b, y)}


def sprite_check(model, ex, sp, final=False):
    """The hooks' entry table, pair bitmap and sprite hardware against the expectation; every shown
    image's pixels (colour, ink / black / transparent) against the original's plots (rows above line 0,
    never plotted, from the snapshot's graphic sp). -> (failures, pixels compared)."""
    f = []
    sh, hw = model.sh, model.hw
    ents = []
    for e in range(NENT):
        b = ENT - SH + e * ESZ
        if sh[b] & 1:
            n = sh[b + 7]
            ents.append({'key': (sh[b + 1] | sh[b + 2] << 8, sh[b + 3], sh[b + 4]), 'own': sh[b + 5] | sh[b + 6] << 8,
                         'pend': bool(sh[b] & 2), 'mask': int.from_bytes(sh[b + 23:b + 26], 'little'),
                         'pairs': list(sh[b + 8:b + 8 + n]), 'n': n})
    got = sorted((e['key'], e['own'], e['pend'], e['mask']) for e in ents)
    want = sorted((e['key'], e['own'], e['mask'] == 0, e['mask']) for e in ex.ents)
    if got != want:
        f.append(('entries differ from the group model', len(got), len(want),
                  [g for g in got if g not in want][:2], [w for w in want if w not in got][:2]))
        return f, 0
    used = [q for e in ents for q in e['pairs']]
    if len(used) != len(set(used)) or any(q > 63 for q in used):
        f.append(('pairs shared or out of range', used))
        return f, 0
    bm = sum(1 << q for q in used)
    if int.from_bytes(sh[PAIRS - SH:PAIRS - SH + 8], 'little') != bm:
        f.append(('pair bitmap differs from the entries',))
    vis = {i for i in range(128) if hw.attr[i][3] & 0x80}
    if vis != {s for q in used for s in (2 * q, 2 * q + 1)}:
        f.append(('visible sprites differ from the entries\' pairs', sorted(vis)[:6]))
        return f, 0
    if bytes(sh[:6144]) != bytes(ex.sh):
        d = [i for i in range(6144) if sh[i] != ex.sh[i]]
        f.append(('shadow differs from the converted images', len(d), 0x4000 + d[0]))
    pix = 0
    busy = {id(v[0]) for v in ex.acc.values() if v is not None and v[0] is not None}
    exb = {x['key']: x for x in ex.ents}
    for e in ents:
        key = e['key']
        x = exb[key]
        if id(x) in busy:
            continue                            # its rows are being plotted
        if x['img'] is None:
            f.append(('image shown but its plot was not seen', key))
            continue
        P, mask = x['img']
        G, gx, yb = key
        if yb - x['H'] + 1 < 0:                 # rows above line 0: from the graphic
            P = set(P)
            for k in range(x['H']):
                if (mask >> k & 1 if x['H'] <= MAXH else mask) and yb - k < 0:
                    v = sp((G + 1 + 2 * k) & 0xFFFF) << 8 | sp((G + 2 + 2 * k) & 0xFFFF)
                    P |= {(gx + j, yb - k) for j in range(16) if v >> (15 - j) & 1}
        want = {q: v for q, v in expected_map(P).items() if 0 <= q[0] < 256 and 0 <= q[1] < 192}
        have = {}
        for q in e['pairs']:
            for s_ in (2 * q, 2 * q + 1):
                for xy, v in hw.pixels(s_).items():
                    if 0 <= xy[0] < 256 and 0 <= xy[1] < 192:
                        if xy in have:
                            f.append(('two sprites of one image overlap', key, xy))
                        have[xy] = v
        col = x['col']
        bad = [q for q in set(want) | set(have)
               if q not in have or q not in want or have[q] != (col, want[q])]
        pix += len(want)
        if bad:
            f.append(('sprite pixels differ from the original plot', key, mask, len(bad), sorted(bad)[:3],
                      [have.get(q) for q in sorted(bad)[:3]], [want.get(q) for q in sorted(bad)[:3]], col))
    return f, pix


# ---------------------------------------------------------------------------------------------
# One site event (shared by the replay and the unit tests)
# ---------------------------------------------------------------------------------------------

class Run:
    def __init__(self, patch):
        self.patch = patch
        self.alt = list(patch.alt_image())
        self.psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
        self.model = None
        self.exp = Expect()
        self.c = collections.Counter()
        self.peek = patch.peek

    def start(self, get):
        """The patched machine at the start of a replay: empty shadow, hook RAM, hidden sprites; its drawer
        ops those of the game now (what the setup copies in); the store against the recording's graphics."""
        ops = bytes(get(a) for a in OPSITES)
        self.model = Model(self.patch, ops)
        self.peek = get
        try:
            self.patch.check(get)
        except ValueError as e:
            return [('snapshot check', str(e))]
        return []

    def site(self, pc, regs, get):
        """Fork the site; returns failures (tuples). Counters in self.c."""
        patch, model, ex = self.patch, self.model, self.exp
        kind = KIND[pc]
        f = []
        if kind in ('setm', 'seta'):
            ex.before_setup(kind[-1])
        if kind in ('setm', 'seta', 'clear'):
            f += ex.bad
            ex.bad = []
            fs, px = sprite_check(model, ex, patch.peek)
            f += [('sprite check: ' + x[0],) + x[1:] for x in fs]
            self.c['sprite pixels compared'] += px
            self.c['sprite checks'] += 1
        fl, so, o, p, stats = event(patch, self.alt, self.psite, model, get, regs, pc)
        f += fl
        self.c['events ' + kind] += 1
        if p is not None:
            self.c['T extra'] += stats['T patched'] - stats['T orig']
            self.c['T extra ' + kind] += stats['T patched'] - stats['T orig']
            if stats['minsp'] < 0x10000:
                self.c['min hook sp'] = min(self.c['min hook sp'] or 0x10000, stats['minsp'])
        for k in range(5):
            if model.hram[V_OP1 - HOOK_RAM[0] + k] != (o[OPSITES[k]] if pc == OPWRITERS[k] else get(OPSITES[k])):
                f.append(('drawer op byte differs from the game\'s', k))
        if kind in ('rowm', 'rowa'):
            ex.rows(kind[-1], o, get)
        elif kind in ('setm', 'seta'):
            ix = regs[8] << 8 | regs[9]
            de = regs[4] << 8 | regs[5]
            if kind == 'setm':
                gid, x, y = get(24085), get(24086), get(24087)
            else:
                gid, x, y = get(ix), get(ix + 3), get(ix + 4)
            if gid and (get(GTAB + 2 * (gid - 1)) | get(GTAB + 2 * (gid - 1) + 1) << 8) != de:
                f.append(('graphic id does not match DE', gid, de))
            h = get(de)
            if x < 192 and h:                 # converted: a stored graphic, or a one-row slice of one
                sp = patch.peek
                res = Expect.resolve(sp, gid, de, x, y, h)
                if res is None:
                    f.append(('plot neither a stored graphic nor a one-row slice of one', gid, de, h))
                elif res[3] == 'stored':
                    n = min(h, 192)
                    if any(get(de + k) != sp(de + k) for k in range(1, 2 * n + 1)):
                        f.append(('graphic changed at run time', gid, de))
                    self.c['plots of a stored graphic'] += 1
                else:
                    G, k = res[0][0], (de - res[0][0]) // 2
                    if get(de + 1) != sp(de + 1) or get(de + 2) != sp(de + 2):
                        f.append(('slice row differs from the graphic', gid, de))
                    self.c['one-row slices'] += 1
                b = get(ix + 5)
                ex.setup(kind[-1], res, ix, (b & 7) | (8 if b & 0x40 else 0))
                self.c['max entries'] = max(self.c['max entries'], len(ex.ents))
        elif kind == 'clear':
            ex.clear()
            fs, px = sprite_check(model, ex, patch.peek)
            f += [('after the clear: ' + x[0],) + x[1:] for x in fs]
        if p is not None and kind not in ('setm', 'seta', 'clear'):
            if any(off >= 0x1800 for pg, off in p.wp):
                f.append(('a pixel hook wrote the hook tables', sorted(p.wp)[-1]))
        return f


# ---------------------------------------------------------------------------------------------
# The replay
# ---------------------------------------------------------------------------------------------

def guard_read(m, a):
    """An instruction outside the hooks reads screen / attribute byte a (0x4000-0x5AFF)."""
    if a < 0x5800:
        if m.sh[a - 0x4000]:
            return 'unhooked read of a figure byte'
    elif a - 0x5800 in m.stale:
        return 'unhooked read of an attribute the figure painter skipped'


def guard_write(m, a, site_bytes):
    """An instruction outside the hooks writes byte a."""
    if 0x4000 <= a < 0x5B00:
        if a < 0x5800:
            if m.sh[a - 0x4000]:
                return 'unhooked write of a figure byte'
        else:
            m.stale.pop(a - 0x5800, None)       # both machines write the same value
    elif a in site_bytes:
        return 'game wrote a patch site'
    elif HOOK_RAM[0] <= a < HOOK_RAM[1]:
        return 'game wrote the hook RAM'


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Differential test over an RZX (PLAYBOOK 6): at every hook site the original and the patched code
    run from the same state to the same point (registers, memory, ULA ^ shadow, attributes, hook rules);
    at every figure setup the shown sprites against the XOR-parity model and the original's plots;
    outside the hooks no instruction reads or writes a figure byte or reads a skipped attribute; no
    write to a patch site, no jump into a patched instruction. -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    run = Run(patch)
    c = run.c
    ex = collections.defaultdict(list)
    states = []
    st = {'f': 0, 'busy': None, 'prev': None, 'on': False}
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    inter = patch.interiors

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['f'],) + tuple(info))

    class W(list):
        def __getitem__(s, a):
            if st['on'] and st['busy'] is None and type(a) is int and 0x4000 <= a < 0x5B00:
                k = guard_read(run.model, a)
                if k:
                    fail(k, (a, st['prev']))
            return G(s, a)

        def __setitem__(s, a, v):
            if st['on'] and st['busy'] is None and type(a) is int:
                k = guard_write(run.model, a, site_bytes)
                if k:
                    fail(k, (a, st['prev']))
            S(s, a, v)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(W(memory), registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a & 0xFFFF)

            def mk(fn):
                def g():
                    pc = R[24]
                    b = st['busy']
                    if b is not None and b(R):
                        st['busy'] = b = None
                    if b is None:
                        if not st['on']:
                            st['on'] = True
                            for k in run.start(get):
                                fail(k[0], k[1:])
                        if pc in WATCH:
                            if collect and c['collected ' + KIND[pc]] < collect:
                                c['collected ' + KIND[pc]] += 1
                                states.append(capture(run, pc, R, mem))
                            for k in run.site(pc, list(R), get):
                                fail('%s %04X: %s' % (KIND[pc], pc, k[0]), k[1:])
                            st['busy'] = _seg(pc, R[12], get)
                        elif pc in inter and st['prev'] is not None and st['prev'] >= 0x4000 and \
                                not pc - 3 <= st['prev'] < pc:
                            fail('jump into a patched instruction', (pc, st['prev']))
                    st['prev'] = pc
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['f'] += 1
        if progress and st['f'] % 1000 == 0:
            progress(st['f'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = next_frame, Sm, None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    c['frames'] = st['f']
    if run.model is not None:
        run.exp.close('m')
        run.exp.close('a')
        fs, px = sprite_check(run.model, run.exp, run.patch.peek)
        for k in fs:
            fail('end: ' + k[0], k[1:])
    return (c, dict(ex), states) if collect else (c, dict(ex))


def capture(run, pc, R, mem):
    """A state for the unit tests: site, registers, 64K, the model, the expectation."""
    return (pc, list(R), bytes(list.__getitem__(mem, a) for a in range(65536)), run.model.copy(), run.exp.copy())


# ---------------------------------------------------------------------------------------------
# Unit tests: paths the recording does not reach, edge positions, every stored image, negative
# controls. States from verify(collect=N): (site, registers, 64K, Model, Expect).
# ---------------------------------------------------------------------------------------------
SENT = 0x0000                       # return address of a driven call (ROM: no game code returns there)


def drive(run, mem, regs, limit=3000000):
    """Run the ORIGINAL code from regs (PC) until it returns to SENT, forking every hook site as the
    replay does (run.model / run.exp updated) and guarding unhooked screen / attribute accesses.
    mem: 64K list (the original machine, modified in place). -> failures."""
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    f = []
    site_bytes = {a + k for a, old, new in run.patch.sites for k in range(len(new))}
    busy = [None]

    class W(list):
        def __getitem__(s, a):
            if busy[0] is None and type(a) is int and 0x4000 <= a < 0x5B00:
                k = guard_read(run.model, a)
                if k:
                    f.append((k, a))
            return G(s, a)

        def __setitem__(s, a, v):
            if busy[0] is None and type(a) is int:
                k = guard_write(run.model, a, site_bytes)
                if k:
                    f.append((k, a))
            if a >= 0x4000:
                S(s, a, v)
    w = W(mem)
    sim = Simulator(w, {})
    R, ops = sim.registers, sim.opcodes
    R[:] = regs
    get = lambda a: G(w, a & 0xFFFF)
    n = 0
    while R[24] != SENT:
        pc = R[24]
        if busy[0] is not None and busy[0](R):
            busy[0] = None
        if busy[0] is None and pc in WATCH:
            f += [('%s %04X: %s' % (KIND[pc], pc, k[0]),) + tuple(k[1:]) for k in run.site(pc, list(R), get)]
            busy[0] = _seg(pc, R[12], get)
        ops[G(w, pc)]()
        n += 1
        if n > limit:
            f.append(('driven call did not return',))
            break
    mem[:] = list(w)
    return f


def _restore(patch, st):
    """A Run of `patch` in the captured state: the run-time byte ranges of the shadow page (shadow,
    entries, pair bitmap, slice buffer) and the hook RAM from the capture, the patch's OWN tables
    (directory) - a copy of the whole page would put the good patch's tables back (Smash TV)."""
    pc, regs, mem, model, ex = st
    run = Run(patch)
    m = model.copy()
    m.patch = patch
    m.sh[DIR - SH:DIR - SH + 1024] = patch.dirb
    run.model, run.exp = m, ex.copy()
    run.peek = lambda a, _m=mem: _m[a & 0xFFFF]
    return run, list(mem), list(regs)


def _call(mem, regs, entry):
    """regs for a CALL entry from the current state: SENT pushed."""
    r = list(regs)
    sp = (r[12] - 2) & 0xFFFF
    mem[sp], mem[(sp + 1) & 0xFFFF] = SENT & 255, SENT >> 8
    r[12], r[24] = sp, entry
    return r


def _final(run):
    run.exp.close('m')
    run.exp.close('a')
    fs, px = sprite_check(run.model, run.exp, run.patch.peek)
    return fs + run.exp.bad, px


def seq_case(patch, st, ix, gid, steps, colour=0x46):
    """Plots of graphic id gid through 0x9F4A (the IX-only plot) with object record ix, one per step:
    ('full', x, y) = the graphic itself, ('slice', x, y, k) = the appear / death effect's one-row slice
    of row k (as 0x8CD8: table entry -> G + 2k, height byte 1 there, both put back after the plot).
    Every step checked (registers, memory, shadow, entries, sprite pixels). -> (failures, pixels)."""
    run, mem, regs = _restore(patch, st)
    f, px = [], 0
    G = graphic(lambda a: mem[a & 0xFFFF], gid)[0]
    e = GTAB + 2 * (gid - 1)
    for step in steps:
        mem[ix], mem[ix + 3], mem[ix + 4], mem[ix + 5] = gid, step[1], step[2], colour
        saved = None
        if step[0] == 'slice':
            a = G + 2 * step[3]
            saved = (mem[e], mem[e + 1], a, mem[a])
            mem[e], mem[e + 1], mem[a] = a & 255, a >> 8, 1
        r = _call(mem, regs, 0x9F4A)
        r[8], r[9] = ix >> 8, ix & 255
        f += drive(run, mem, r)
        if saved:
            mem[e], mem[e + 1], mem[saved[2]] = saved[0], saved[1], saved[3]
        fs, n = _final(run)
        f += fs
        px += n
    return f, px


def plot_case(patch, st, ix, gid, x, y, colour, rows=None):
    """gid drawn at (x, y) and erased (rows = (G, k): its one-row slice k instead)."""
    if rows is None:
        return seq_case(patch, st, ix, gid, [('full', x, y)] * 2, colour)
    return seq_case(patch, st, ix, gid, [('slice', x, y, rows[1])] * 2, colour)


def unit_tests(patch, states, neg=None):
    """-> (Counter: case names, failures end in '!'; examples). neg: [(name, broken patch)] that must FAIL."""
    c = collections.Counter()
    exs = []
    st0 = next((s for s in states if s[0] == 0x9FC1), None)
    if st0 is None:
        c['no captured setup state!'] += 1
        return c, exs
    mem0 = st0[2]
    peek = lambda a: mem0[a & 0xFFFF]
    ix = st0[1][8] << 8 | st0[1][9]

    def rec(name, f, px=0, allow=()):
        f = [x for x in f if not any(x[0].endswith(a) or a in x[0] for a in allow)]
        c['cases'] += 1
        c['sprite pixels compared'] += px
        if f:
            c[name + '!'] += 1
            if len(exs) < 8:
                exs.append((name, f[:2]))
        else:
            c[name] += 1

    # 1. every stored image (one id per graphic address) at edge positions and colours
    done = set()
    for gid in range(1, 256):
        ga, h = graphic(peek, gid)
        if h == 0 or ga in done or not 0x5B00 <= ga or \
                any(peek(ga + k) != patch.peek(ga + k) for k in range(2 * min(h, 192) + 1)):
            continue    # ids past the table pointing into the ROM, screen, stack or variables: no game image
        done.add(ga)
        for x, y, col in ((0, 191, 0x47), (7, 100, 0x02), (99, max(h - 1, 0), 0x45), (183, 150, 0x41),
                          (190, 3, 0x06)):
            f, px = plot_case(patch, st0, ix, gid, x, y, col)
            rec('stored image drawn + erased (edges, colours)', f, px)
    # 2. the appear effect's one-row slices: every row of the figures it is used for, every shift
    for gid in sorted({g for g in range(1, 212) if graphic(peek, g)[1]})[:24]:
        ga, h = graphic(peek, gid)
        for k in range(min(h, 24)):
            f, px = plot_case(patch, st0, ix, gid, 32 + (k % 8), 120, 0x46, rows=(ga, k))
            rec('one-row slice drawn + erased (every row, every shift)', f, px)
    # (case 4 below: a full table)
    # 2b. the effect as the game runs it: death = the figure, then its rows erased top-down by slices;
    # appear = slices bottom-up at the new place, then the move (erase the whole figure, draw it elsewhere);
    # every partial image built at run time; and slices in a random order (masks the game never makes)
    import random
    rnd = random.Random(7)
    for gid in (6, 1, 17, 33):
        ga, h = graphic(peek, gid)
        if not 0 < h <= MAXH:
            continue
        for x, y in ((40, 120), (101, h + 3), (150, h - 1)):     # (a slice line y - k is a byte: >= 0)
            steps = [('full', x, y)] + [('slice', x, y - k, k) for k in range(h - 1, -1, -1)]
            f, px = seq_case(patch, st0, ix, gid, steps)
            rec('death: figure erased row by row (top down)', f, px)
            steps = [('slice', x, y - k, k) for k in range(h)] + [('full', x, y), ('full', x + 3, y - 1)]
            f, px = seq_case(patch, st0, ix, gid, steps)
            rec('appear: rows bottom up, then the figure moves', f, px)
            ks = list(range(h)) * 2
            rnd.shuffle(ks)
            f, px = seq_case(patch, st0, ix, gid, [('slice', x, y - k, k) for k in ks[:h + 4]])
            rec('slices in a random order (any row mask)', f, px)
    # 3. the panel (x >= 192: the original blitter on the ULA), height 0
    for x in (192, 200, 247):
        f, px = plot_case(patch, st0, ix, 6, x, 100, 0x07)
        rec('panel position: not converted', f, px)
    # 4. a full entry table: the new image is not shown, nothing else breaks
    run, mem, regs = _restore(patch, st0)
    f = []
    for i in range(NENT + 2):
        mem[ix], mem[ix + 3], mem[ix + 4], mem[ix + 5] = 6, 8 * (i % 20), 40 + 4 * (i // 20), 0x47
        own = 0xE000 + 8 * i                    # a new owner per image (in graphics this test never draws)
        for k in range(8):
            mem[own + k] = mem[ix + k]
        r = _call(mem, regs, 0x9F4A)
        r[8], r[9] = own >> 8, own & 255
        f += drive(run, mem, r)
    fs, px = _final(run)
    full = [x for x in f + fs if 'entry table full' in x[0]]
    rec('entry table full: images past %d not shown, the rest exact' % NENT,
        f + fs + ([] if full else [('the table never filled',)]), px, allow=('entry table full',))
    # 5. the clear with every entry used and figures in the shadow
    stc = next((s for s in states if s[0] == 0x8093), None)
    if stc is not None:
        run2, mem2, regs2 = _restore(patch, stc)
        run2.model, run2.exp = run.model.copy(), run.exp.copy()
        run2.model.patch = patch
        f = run2.site(0x8093, regs2, lambda a: mem2[a & 0xFFFF])
        rec('play-area clear with a full table', f)
    # 6. the non-XOR writers over figure bits (seeded shadow), every drawer op
    for site in (0x9C75, 0xA1E6) + OPSITES:
        sts = [s for s in states if s[0] == site]
        for s in sts[:2]:
            for op in ((0x00, 0xB6, 0xAE) if site in OPSITES else (None,)):
                run, mem, regs = _restore(patch, s)
                if op is not None:
                    k = OPSITES.index(site)
                    mem[site] = op
                    run.model.hram[V_OP1 - HOOK_RAM[0] + k] = op
                hl = regs[6] << 8 | regs[7]
                for a in (hl, hl ^ 1, hl + 0x100):
                    if 0x4000 <= a < 0x5800:
                        run.model.sh[a - 0x4000] ^= 0xA5
                        run.exp.sh[a - 0x4000] ^= 0xA5
                get = lambda a, _m=mem: _m[a & 0xFFFF]
                f = run.site(site, list(regs), get)
                rec('%s over figure bits%s' % (KIND[site], '' if op is None else ' op %02X' % op), f)
    # 7. the text printer outside the pixel area
    for s in [s for s in states if s[0] == 0xA1E6][:1]:
        for h in (0x3F, 0x58, 0x5A, 0x80):
            run, mem, regs = _restore(patch, s)
            regs[6] = h
            f = run.site(0xA1E6, list(regs), lambda a, _m=mem: _m[a & 0xFFFF])
            rec('text printer outside the pixel area', f)
    # negative controls: each broken patch must fail the cases it breaks
    for name, q in (neg or []):
        f = []
        for gid, rows in ((6, None), (6, (graphic(peek, 6)[0], 3))):
            fl, px = plot_case(q, st0, ix, gid, 33, 120, 0x46, rows)
            f += fl
        fl, px = seq_case(q, st0, ix, 6, [('full', 50, 100), ('slice', 50, 83, 17), ('slice', 50, 84, 16)])
        f += fl
        c['negative controls'] += 1
        if f:
            c['negative controls detected'] += 1
        else:
            c['negative control NOT detected: %s!' % name] += 1
    return c, exs


def negative_patches(patch):
    """Broken builds: (1) every stored pattern one pixel right (its own store), (2) the directory's
    row counts one too many (its own table: sprite Y off by one), (3) the slice builder writes ink
    where black belongs (hook code)."""
    import copy
    out = []
    q = copy.copy(patch)
    q.store = {}
    for pg, d in patch.store.items():
        b = bytearray(len(d))
        for r in range(len(d) // 8):
            v = int.from_bytes(d[8 * r:8 * r + 8], 'big') >> 4
            b[8 * r:8 * r + 8] = v.to_bytes(8, 'big')
        q.store[pg] = bytes(b)
    out.append(('store shifted one pixel', q))
    q = copy.copy(patch)
    d = bytearray(patch.dirb)
    for g in range(256):
        if d[4 * g]:
            d[4 * g + 3] = (d[4 * g + 3] + 1) & 255
    q.dirb = bytes(d)
    out.append(('directory heights + 1', q))
    a = patch.syms['build']
    code = bytearray(patch.rom_code)
    i = code.index(bytes([0x3E, 0x02, 0x18]), a - ROM_ORG)      # .o2: LD A,2 (black) / JR .ow
    q = AticAtacPatch(patch.prof, edit={ROM_ORG + i: bytes([0x3E, 0x01])}, peek=patch.peek)
    out.append(('run-time builder: black written as ink', q))
    return out


# ---------------------------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------------------------
ENTRY = 24576                       # the game's entry (JP 24576 at the end of the loader's descramble)


def start_state(z80, out_z80):
    """The .z80 (loader state: descramble loop in the printer buffer) run to JP 24576 -> out_z80.
    Returns the frame it got there. The RZX needs no prerun: it carries its own mid-game snapshot."""
    from . import simrun
    from skoolkit.simutils import get_state
    from skoolkit.snapshot import write_snapshot
    f, sim = simrun.free_run(z80, 400, None, stop_pc=ENTRY)
    if sim.registers[24] != ENTRY:
        raise ValueError('the loader did not reach JP %d' % ENTRY)
    ram, regs, state, machine = get_state(sim)
    write_snapshot(out_z80, ram, regs, state, machine)
    return f


def boot_check(nex, z80, patch):
    """nextboot.check (48K) + the build's own banks: alt ROM page, directory in the shadow page, the
    pattern store pages, the setup's ops + palette. -> problems."""
    from .nextboot import check, load_nex
    banks = load_nex(nex)[0]
    bad = []
    pg = lambda n: banks.get(n // 2, bytes(16384))[(n & 1) * 8192:(n & 1) * 8192 + 8192]
    if pg(ALT_PAGE) != patch.page:
        bad.append(('alt ROM page differs',))
    if pg(SHPG)[DIR - SH:DIR - SH + 1024] != patch.dirb or any(pg(SHPG)[:DIR - SH]):
        bad.append(('shadow page: directory differs or shadow not empty',))
    if pg(WPG) != patch.work:
        bad.append(('work page (GADR) differs',))
    for n, d in patch.store.items():
        if pg(n) != d:
            bad.append(('store page %d differs' % n,))
    st = banks.get(10, b'')[0x1000:0x1000 + len(patch.stub_extra)]
    if st != patch.stub_extra:
        bad.append(('setup / ops / palette in the stub bank differ',))
    return bad


DECISIONS = json.loads('{"engine": "atic_atac", "strategy": "pure-XOR row blitters 0x9EDC / 0x9F21 -> 1-bit shadow screen (page 26 at slot 3; ULA ^ shadow = the original); non-XOR writers (room line 0x9C75, 5 drawers with run-time ops, text 0xA1E6) keep it exact; hooks in alt ROM image 1 at 0x2000, 28 MHz inside every hook", "start": "the .z80 (loader state) run to JP 24576 (frame 2); hook RAM 0x5B80-0x5BFF zeroed (loader bytes there are dead)", "figures": "every figure a hardware-sprite image (Dean 2026-10-26: decisions 1-5 = defaults); the panel\'s pocket icons (x >= 192) stay on the ULA", "images": "image group = (the id\'s graphic in the snapshot, x, base line) + row mask: a plot of the graphic toggles all rows, the appear / death effect\'s one-row slice (0x8CD8) row k; all rows = the stored image (207 images, pages 32-44), some = built by the hook (work page 28)", "outline": "solid: ink 1, enclosed paper (4-connected flood) + 1-px outline (4-neighbours: left / right / up / down, no diagonal corner pixels) black 2, else transparent (Dean 2026-10-26)", "colours": "palette offset = the figure\'s ink + 8 * BRIGHT (IX+5); the figure painter\'s 6 LD (HL),D become NOP", "tail": "0x5B00 (printer buffer: never touched in the RZX)"}')


def auto(a, z80, name, out, say):
    import hashlib
    import time
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : atic_atac (Atic Atac: XOR row blitters 0x9EDC / 0x9F21 -> shadow screen; every figure '
        'an outlined, solid hardware-sprite image)')
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (the loader as it is; tail 0x%04X)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    start = os.path.join(out, name + '_start.z80')
    fr = start_state(z80, start)
    say('Start     : loader run to JP %d (frame %d) -> %s' % (ENTRY, fr, os.path.basename(start)))
    from skoolkit.snapshot import Snapshot
    from .build import rom48
    sm = Snapshot.get(start).memory
    rom = rom48()
    mem0 = bytes(rom) + bytes(sm[a] for a in range(0x4000, 0x10000))
    patch = AticAtacPatch(peek=mem0.__getitem__)
    sc = static_check(patch.rom_code)
    say('Static    : hook code %d bytes at 0x%04X-0x%04X (alt ROM), no EXX / EX AF / IY / I / IM / DI / EI, '
        'nothing at 0x3D00: %s' % (len(patch.rom_code), ROM_ORG, ROM_ORG + len(patch.rom_code) - 1,
                                  'PASS' if not sc else 'FAIL %s' % sc[:3]))
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(start, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, start, patch, (conv[1], conv[1] + len(conv[2]))) + boot_check(spr, start, patch)
    say('Sprites   : %s  %s  boot %s  (%d stored images, %d tile rows in pages %d-%d; tail 0x%04X)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200],
        len(patch.seen), sum(v[2] for v in patch.seen.values()), min(patch.store), max(patch.store), conv[1]))
    ok = not bad and not bad2 and not sc
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'), indent=1)
    states = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, Snapshot))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1,
                                                                   os.path.basename(s2)))
            r = s2
        t = time.time()
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if isinstance(k, str) and k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s (%.0fs) %d frames: %d figure setups (%d of a stored graphic, %d one-row slices), %d rows, '
            '%d line / %d drawer / %d text / %d painter events, %d clears, %d sprite checks, %d sprite pixels, '
            'max %d entries -> %s' % (
                os.path.basename(r), time.time() - t, c['frames'], c['events setm'] + c['events seta'],
                c['plots of a stored graphic'], c['one-row slices'],
                c['events rowm'] + c['events rowa'], c['events line'], c['events obj'], c['events txt'],
                c['events paint'], c['events clear'], c['sprite checks'], c['sprite pixels compared'],
                c['max entries'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        gf = max(1, c['frames'])
        say('Speed     : hooks add %d T per frame on average (28 MHz parts / 8); a frame is 69,888 T; '
            'lowest hook SP 0x%04X' % (c['T extra'] // gf, c['min hook sp'] or 0))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:240]))
    if states:
        t = time.time()
        u, uex = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : (%.0fs) %d cases (every stored image at edges, one-row slices, panel, full table, '
            'clear, writers over figures, text outside the screen), %d sprite pixels, negative controls %d/%d -> %s' % (
                time.time() - t, u['cases'], u['sprite pixels compared'], u['negative controls detected'],
                u['negative controls'], 'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in uex[:5]:
            say('            example %s: %s' % (k, str(v)[:240]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
