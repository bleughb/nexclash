"""Sabre Wulf (Ultimate Play The Game, 1984, 48K) engine 'sabre_wulf'. Additive module: reachable only through
is_sabre_wulf(). Facts, design and results: games/sabre_wulf.md.

Figures are XOR images; a plot toggles them. Object IX (38658 + 12i, 25 of them) has its image in (IX+0 frame, IX+3 x,
IX+4 bottom line) and the image it showed last in 38559-38561. 47529 toggles both, 47385 the object's, 47349 the saved.
Frame f: table 49028 -> width bytes, height, rows bottom up. No game logic reads the screen, other than the XOR itself and
the paint routine's own check of paper. Enemy speed depends on plot time (no frame cap): the row loops keep running,
LD (HL),A -> LD A,(HL), same T-states, nothing written.
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
STATE_PAGE, STATE_BANK = 22, 11
ALT_BANK = 12
PAT_PAGE0 = 26              # bank 13 up
FRTAB, OBJ = 0xE000, 0xEB00
UL, IXT, UOWN, REF, CACHED, VARS = 0xE700, 0xEC00, 0xEE00, 0xEF00, 0xF000, 0xF100
OBJW = 8                    # bytes per object in OBJ (asm)
GFX_TABLE, NFRAMES = 49028, 196
OBJ0, STRIDE, NOBJ = 38658, 12, 25
SAVED = 38559
PLANT = range(72, 80)       # frames whose bottom cell row the game paints bright green (42674)
GREEN = 12                  # palette entry of bright green

SITES_ORIG = {47529: ('cd69b9', 'e_mov'), 47385: ('cd69b9', 'e_tog'), 47349: ('cd39b9', 'e_old'),
              47908: ('dd6e03', 'e_col'), 47964: ('214040', 'e_clr')}
ROW_LOOPS = ((47629, 47756), (47756, 47883))
PAINT = 47948               # LD (HL),D in the paint loop -> CP (HL): 7 T and one access of the cell, as the write
INTERIORS = tuple(a + k for a in SITES_ORIG for k in (1, 2))
# The snapshot stops at PAUSE 0 in BASIC, in "PAUSE 0: RANDOMIZE USR 24576" in the edit line. A .nex runs on NextZXOS's ROM3,
# whose BASIC differs, so that return never reaches USR. Both builds start here: the same wait, then the game's entry.
START, ENTRY = 0x5D00, 24576
START_CODE = bytes([0xF3,
                    0xAF, 0xDB, 0xFE, 0xF6, 0xE0, 0x3C, 0x20, 0xF8,    # no key held
                    0xAF, 0xDB, 0xFE, 0xF6, 0xE0, 0x3C, 0x28, 0xF8,    # a key, as PAUSE 0
                    0xC3, ENTRY & 255, ENTRY >> 8])
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
FIXED = [None, None, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'sabre_wulf_colours.json')


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'sabre_wulf.json'),
              os.path.join(_HERE, 'sabre_wulf.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('sabre_wulf.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_sabre_wulf(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bool(sig) and bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


# ---------------------------------------------------------------------------------------------
# Frames -> patterns
# ---------------------------------------------------------------------------------------------

def frame_at(peek, f):
    """-> (graphics address, width bytes, height) or None for an empty frame."""
    if f >= NFRAMES:
        return None
    t = GFX_TABLE + 2 * f
    g = peek(t) | peek(t + 1) << 8
    if g < 0x6000:
        return None
    w, h = peek(g), peek(g + 1)
    return (g, w, h) if w and h else None


def frame_shape(w, h):
    return (1 if w <= 2 else 2), (1 if h <= 16 else 2)


def default_nibble(f, row_from_bottom):
    return GREEN if f in PLANT and row_from_bottom < 8 else 1


def frame_patterns(peek, f, cmap=None):
    """cols * rows patterns of 128 bytes, top row first. A pixel's nibble: the map's for (graphics byte, bit), else the
    default. A paper bit is transparent unless the map paints it. An entry whose check byte is not the graphic's is ignored."""
    g, w, h = frame_at(peek, f)
    cols, rows = frame_shape(w, h)
    canvas = [[0] * (cols * 16) for _ in range(rows * 16)]
    p = g + 2
    for r in range(h):                      # r = 0 is the bottom line, y = h - 1 - r from the top
        y = h - 1 - r
        for b in range(w):
            a = p + b
            v = peek(a)
            e = cmap.get('%04X' % a) if cmap else None
            if e and e[0] != v:
                e = None
            for k in range(8):
                ink = (v >> (7 - k)) & 1
                n = default_nibble(f, r) if ink else 0
                if e:
                    if len(e) > 3 and e[3] & (0x80 >> k):
                        n = 0
                    elif e[2][k]:
                        n = e[2][k]
                canvas[y][b * 8 + k] = n
        p += w
    out = bytearray()
    for ry in range(rows):
        for cx in range(cols):
            for y in range(16):
                row = canvas[ry * 16 + y][cx * 16:cx * 16 + 16]
                for k in range(0, 16, 2):
                    out.append(row[k] << 4 | row[k + 1])
    return bytes(out)


def build_tables(peek, cmap=None):
    """-> (state page 8K, {page: 8K bytes}). Frames sharing a graphic and a colour rule share patterns and one
    canonical id (1..). The layout does not depend on the map, so recolour changes pattern pages only.
    State page (asm): FRTAB 8 bytes a frame (page, unit, flags, height, canonical, units); IXT: IX - 38658 -> 8i or
    0xFF; the cache's UL / UOWN / REF / CACHED and the variables start at zero."""
    state = bytearray(8192)
    pages = {}
    page, idx = PAT_PAGE0, 0
    seen = {}
    for f in range(NFRAMES):
        fa = frame_at(peek, f)
        if not fa:
            continue
        g, w, h = fa
        cols, rows = frame_shape(w, h)
        n = cols * rows
        key = (g, f in PLANT)
        if key in seen:
            pg, ix, cid = seen[key]
        else:
            if idx + n > 64:
                page, idx = page + 1, 0
            pg, ix, cid = page, idx, len(seen) + 1
            data = frame_patterns(peek, f, cmap)
            pages.setdefault(pg, bytearray(8192))[ix * 128:ix * 128 + n * 128] = data
            seen[key] = (pg, ix, cid)
            idx += n
        if f == 0 or cid > 255:
            raise ValueError('frame 0 drawn, or more than 255 graphics: the asm tables cannot hold it')
        state[f * 8:f * 8 + 6] = bytes([pg, ix, (cols - 1) | (rows - 1) << 1, h, cid, n])
    for k in range(512):
        state[IXT - 0xE000 + k] = OBJW * (k // STRIDE) if k % STRIDE == 0 and k // STRIDE < NOBJ else 0xFF
    return bytes(state), {k: bytes(v) for k, v in pages.items()}


def apply_start(snap):
    b = bytearray(snap.banks[5])
    o = START - 0x4000
    if any(b[o:o + len(START_CODE)]):
        raise ValueError('start stub area is not empty in this snapshot')
    b[o:o + len(START_CODE)] = START_CODE
    snap.banks[5] = bytes(b)
    snap.pc = START


START_STUB = False          # 2026-11-05: the whole alt ROM image (Sinclair's ROM) runs the snapshot's own BASIC return
                            # (PAUSE 0: RANDOMIZE USR 24576) as on a 48K, so neither build needs the stub; True = the
                            # 2026-11-03 start (games/sabre_wulf.md "Start-up")


def _whole_rom_page(code=b''):
    """Image of 0x2000-0x3FFF for alt ROM image 1: Sinclair's ROM with `code` at ROM_ORG (its 0xFF area)."""
    from .build import rom48
    rom = rom48()
    if any(b != 0xFF for b in rom[ROM_ORG:ROM_ORG + len(code) + 20]):
        raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
    page = bytearray(rom[0x2000:0x4000])
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    return bytes(page)


class PlainPatch:
    """The plain .nex: no hooks. Alt ROM image 1 = Sinclair's 48K ROM (+ the tail's 20-byte register block in its
    0xFF area), so the snapshot's BASIC (PAUSE 0: RANDOMIZE USR 24576) runs as on a 48K."""
    name = "Sabre Wulf plain conversion, Sinclair's ROM as the alt ROM"
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def __init__(self):
        self.regblock = ROM_ORG
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = _whole_rom_page()
        self.extra_banks = {ALT_BANK: self.page + bytes(8192)}

    def apply(self, snap):
        if START_STUB:
            apply_start(snap)


def row_sites(peek):
    """Every LD (HL),A after an XOR (HL) in the two row loops."""
    out = []
    for lo, hi in ROW_LOOPS:
        for a in range(lo, hi):
            if peek(a) == 0xAE and peek(a + 1) == 0x77:
                out.append(a + 1)
    return out


class SabreWulfPatch:
    name = 'Sabre Wulf: figures -> hardware sprites (altrom hooks, tables in Next pages at slots 6-7)'

    def __init__(self, prof=None, rom_code=None, colours=None):
        self.prof = prof or load_profile()
        self.colours = load_colours() if colours is None else colours
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
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
        self.page = _whole_rom_page(self.rom_code)
        self.sites = []
        for a, (old, sym) in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old), bytes([0xC3]) + self.syms[sym].to_bytes(2, 'little')))
        self.extra_banks = {}
        self.state = None
        self.pages = None
        self.num_patterns = 100

    def add_screen_sites(self, peek):
        have = {s[0] for s in self.sites} | getattr(self, 'drop', set())
        for a in row_sites(peek):
            if a not in have:
                self.sites.append((a, b'\x77', b'\x7e'))
        if PAINT not in have:
            self.sites.append((PAINT, b'\x72', b'\xbe'))

    def tables(self, peek):
        self.state, self.pages = build_tables(peek, self.colours)

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Sabre Wulf patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        peek = lambda a: ram[a - 0x4000]
        self.add_screen_sites(peek)
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.tables(peek)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        if START_STUB:
            apply_start(snap)
        self.extra_banks = {STATE_BANK: self.state + bytes(8192), ALT_BANK: self.page + bytes(8192)}
        for pg, data in self.pages.items():
            bank = pg // 2
            cur = self.extra_banks.get(bank, bytes(16384))
            o = (pg & 1) * 8192
            self.extra_banks[bank] = cur[:o] + data + cur[o + 8192:]


# ---------------------------------------------------------------------------------------------
# Next-side state
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, patch):
        self.patch = patch
        self.nr = {0x56: 0, 0x57: 1, 0x07: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patptr = 0
        self.state = bytearray(patch.state)
        self.events = []
        self.cache = {}
        self.sel = 7                # port 0x243B's register (a hook selects 7 itself)
        self.speed_in = 0           # the clock a hook is entered at (verify clock=, the every-site matrix)
        self.written = set()        # pattern units written in this event

    def copy(self):
        q = NextState.__new__(NextState)
        q.patch = self.patch
        q.nr = dict(self.nr)
        q.attr = [list(a) for a in self.attr]
        q.pat = bytearray(self.pat)
        q.patptr = self.patptr
        q.state = bytearray(self.state)
        q.events = []
        q.cache = {}
        q.sel = self.sel
        q.speed_in = self.speed_in
        q.written = set()
        return q

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def out(self, port, val):
        p = port & 0xFF
        if port == 0x303B:
            self.patptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif p == 0x5B:
            self.pat[self.patptr & 0x3FFF] = val
            self.written.add((self.patptr & 0x3FFF) >> 7)
            self.patptr += 1
            self.cache.clear()
        elif port == 0x243B:
            self.sel = val
        else:
            self.events.append(('out', port, val))

    def inp(self, port):
        if port == 0x253B and self.sel == 7:
            s = self.nr.get(7, 0) & 3
            return s << 4 | s                   # actual speed 5:4, programmed 1:0 (hooklib.NextModel)
        self.events.append(('in', port))
        return 0xFF

    def units(self, i):
        """Pattern units sprite i shows, or None if it is off."""
        a = self.attr[i]
        if not a[3] & 0x80:
            return None
        return (a[3] & 0x3F) * 2 + (1 if a[4] & 0x40 else 0)

    def page_byte(self, page, off):
        if page == STATE_PAGE:
            return self.state[off]
        d = self.patch.pages.get(page)
        return d[off] if d else 0

    def sprite_rows(self, i):
        """Visible sprite -> (x, y, 16 rows of 16 bits: bit 15 = left), None if off."""
        a = self.attr[i]
        if not a[3] & 0x80:
            return None
        base = (a[3] & 0x3F) * 256 + (128 if a[4] & 0x40 else 0)
        rows = self.cache.get(base)
        if rows is None:
            rows = []
            for j in range(16):
                v = 0
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    if (b >> 4) if k % 2 == 0 else (b & 15):
                        v |= 0x8000 >> k
                rows.append(v)
            self.cache[base] = rows
        return (a[0] + (a[2] & 1) * 256 - 32, a[1] + (a[4] & 1) * 256 - 32, rows)

    def pixels(self, i):
        s = self.sprite_rows(i)
        if not s:
            return set()
        x, y, rows = s
        return {(x + k, y + j) for j, v in enumerate(rows) for k in range(16) if v & (0x8000 >> k)}


def obj_sprites(i):
    b = 4 * (NOBJ - 1 - i)
    return range(b, b + 4)


# ---------------------------------------------------------------------------------------------
# One hook event: original and patched from one state
# ---------------------------------------------------------------------------------------------

CMP = list(range(0, 13)) + list(range(14, 25)) + [26, 27]   # every register, R (15) included; not T, MEMPTR
_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _alt(patch):
    """Alt ROM image 1 as the stub leaves it on the Next (nextboot.alt_image: the whole image, Sinclair's ROM + hooks)."""
    from .nextboot import alt_image
    return alt_image(patch)


class _O:
    """The original: an overlay over the live memory."""

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
    """The patched build: patch sites, alt ROM, Next pages at slots 6 and 7."""

    def __init__(s, get, alt, psite, ns):
        _O.__init__(s, get)
        s.alt, s.psite, s.ns, s.romw, s.pagew = alt, psite, ns, 0, 0

    def __getitem__(s, a):
        if a < 0x4000:
            return s.alt[a]
        if a >= 0xC000:
            nr = s.ns.nr
            if a >= 0xE000:
                if nr[0x57] != 1:
                    return s.ns.page_byte(nr[0x57], a - 0xE000)
            elif nr[0x56] != 0:
                return s.ns.page_byte(nr[0x56], a - 0xC000)
        v = s.psite.get(a)
        if v is not None:
            return v
        v = s.ov.get(a)
        return s.get(a) if v is None else v

    def __setitem__(s, a, v):
        if a < 0x4000:
            s.romw += 1
            return
        if a >= 0xC000:
            nr = s.ns.nr
            if a >= 0xE000 and nr[0x57] != 1:
                if nr[0x57] == STATE_PAGE:
                    s.ns.state[a - 0xE000] = v
                else:
                    s.pagew += 1
                return
            if a < 0xE000 and nr[0x56] != 0:
                s.pagew += 1
                return
        s.ov[a] = v


def _machine(Sim, mem, regs, ns, slot):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot)

    class Tr:
        def read_port(self, regs_, port):
            return ns.inp(port)

        def write_port(self, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    z80n.install(sim, ns.nextreg)
    return sim


def _run(sim, stop, watch=None, limit=400000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        if watch:
            watch(R)
        n += 1
        if n > limit:
            return False
    return True


def _screen_xor(ov, get, lo=0x4000, hi=0x5800):
    out = set()
    for a, v in ov.items():
        if lo <= a < hi:
            d = v ^ get(a)
            if d:
                y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
                for k in range(8):
                    if (d >> (7 - k)) & 1:
                        out.add(((a & 31) * 8 + k, y))
    return out


def event(patch, kind, get, R, ns, alt, psite, Sim):
    """Run one hook event from the same state. kind: 'mov', 'tog', 'old', 'col', 'clr'. Returns (failures, pixels compared)."""
    sp0 = R[12]
    ret = get(sp0) | get(sp0 + 1) << 8

    def stop(r):
        return r[24] == ret and r[12] == sp0 + 2

    ix = R[8] << 8 | R[9]
    i = (ix - OBJ0) // STRIDE if (ix - OBJ0) % STRIDE == 0 and 0 <= ix - OBJ0 < NOBJ * STRIDE else None
    f = []
    o = _O(get)
    so = _machine(Sim, o, list(R), _NullNs(), 'o')
    before = [list(a) for a in ns.attr]
    pix0 = {} if i is None else {s: ns.pixels(s) for s in obj_sprites(i)}
    ns.events = []
    ns.written = set()
    ns.nr[0x07] = ns.speed_in                    # the hook is entered at the game's clock
    p = _P(get, alt, psite, ns)
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    low = [sp0]
    ivals = (R[8], R[9], R[10], R[11], R[14], R[26])

    def watch(r):
        if r[12] < low[0]:
            low[0] = r[12]
        if (r[8], r[9], r[10], r[11], r[14], r[26]) != ivals:
            low.append('IX, IY, I or IFF changed in a hook')

    if not _run(so, stop):
        return ['original did not return'], 0
    try:
        if not _run(sp_, stop, watch):
            return ['patched did not return'], 0
    except Exception as e:
        return ['patched code raised %s' % str(e)[:80]], 0
    ro, rp = so.registers, sp_.registers
    event.last = (list(rp), dict(p.ov))
    # A' after a plot holds the last row byte, which depends on the screen. aprime_probe() shows the game never reads it.
    diff = [k for k in CMP if ro[k] != rp[k] and not (k == 16 and kind in ('mov', 'tog', 'old'))]
    if diff:
        f.append(('registers differ', diff, [ro[k] for k in diff], [rp[k] for k in diff]))
    if p.romw or p.pagew:
        f.append(('patched code wrote ROM or a pattern page', p.romw, p.pagew))
    if len(low) > 1:
        f.append((low[1],))
    if sp0 - low[0] > 40:
        f.append(('hook stack too deep', sp0 - low[0]))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access other than the sprite ports', [e for e in ns.events if e[0] in ('in', 'out')][:3]))
    if ns.nr[0x56] != 0 or ns.nr[0x57] != 1 or ns.nr[0x07] != ns.speed_in:
        f.append(('slots or the incoming speed not restored', ns.nr[0x56], ns.nr[0x57], ns.nr[0x07], ns.speed_in))
        ns.nr[0x56], ns.nr[0x57], ns.nr[0x07] = 0, 1, ns.speed_in
    if ns.sel != 7:
        f.append(('port 0x243B left on another register', ns.sel))
        ns.sel = 7
    shown = {u for s_ in range(128) if (i is None or s_ not in obj_sprites(i)) for u in [ns.units(s_)] if u is not None}
    hit = shown & ns.written
    if hit:
        f.append(('a pattern unit another sprite shows was written', sorted(hit)[:4]))
    regs_ok = {0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x56, 0x57}
    if any(e[1] not in regs_ok for e in ns.events):
        f.append(('NEXTREG outside the hook set',))
    dead = range(ro[12] - 64, ro[12])
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not 0x4000 <= a < 0x5B00 and a not in dead and o[a] != _pv(p, a, get)]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    npx = 0
    if kind == 'clr':
        sd = [a for a in keys if 0x4000 <= a < 0x5B00 and o.ov.get(a) != p.ov.get(a)]
        if sd:
            f.append(('screen writes differ', len(sd)))
        if any(ns.attr[s][3] & 0x80 for s in range(128)):
            f.append(('sprite visible after a clear',))
        return f, 0
    if any(0x4000 <= a < 0x5B00 for a in p.ov):
        f.append(('patched code wrote the screen', sorted(a for a in p.ov if 0x4000 <= a < 0x5B00)[:3]))
    if kind == 'col':
        if i is None:
            return f, 0
    if i is None:
        f.append(('plot with IX not an object', ix))
        return f, 0
    changed = [s for s in range(128) if ns.attr[s] != before[s] and s not in obj_sprites(i)]
    if changed:
        f.append(('other sprites changed', changed[:4]))
    if kind != 'col':
        want = _screen_xor(o.ov, get)
        now = set()
        for s in obj_sprites(i):
            now ^= ns.pixels(s)
        was = set()
        for s in pix0:
            was ^= pix0[s]
        got = {(x, y) for x, y in (was ^ now) if 0 <= x < 256 and 0 <= y < 192}
        npx = len(want)
        if got != want:
            f.append(('sprite change differs from the original XOR', len(got ^ want), sorted(got ^ want)[:3]))
    col = get(ix + 5) if kind != 'col' else o[ix + 5]
    want_off = (col & 7) | (8 if col & 0x40 else 0)
    for s in obj_sprites(i):
        if ns.attr[s][3] & 0x80 and ns.attr[s][2] >> 4 != want_off:
            f.append(('palette offset is not the colour', s, ns.attr[s][2] >> 4, col))
            break
    return f, npx


def enh_event(ok, regs, pe, nse, ns, enh):
    """The Enhanced build's hook run against the default's (event.last): -> failures."""
    f = []
    if not ok:
        return [('did not return',)]
    rd, ovd = event.last
    d = [k for k in CMP if regs[k] != rd[k]]
    if d:
        f.append(('registers differ from the default build', d))
    if pe.ov != ovd:
        f.append(('memory differs from the default build', len(set(pe.ov.items()) ^ set(ovd.items()))))
    if nse.attr != ns.attr or nse.state != ns.state or nse.nr != ns.nr:
        f.append(('sprites or state differ from the default build',))
    st = nse.state
    for i in range(NOBJ):
        o = OBJ - 0xE000 + OBJW * i
        fr = st[o + 3]
        if not fr:
            continue
        e = fr * 8
        pg, unit, cid = st[e], st[e + 1], st[e + 4]
        data = (getattr(enh, 'expect', None) or enh.pages).get(pg, bytes(8192))
        for k, s_ in enumerate(obj_sprites(i)):
            u = nse.units(s_)
            if u is None:
                continue
            if st[UL - 0xE000 + 256 * k + cid] != u:
                f.append(('sprite unit is not the cached unit of its frame', i, k))
            elif bytes(nse.pat[u * 128:u * 128 + 128]) != data[(unit + k) * 128:(unit + k) * 128 + 128]:
                f.append(('pattern unit is not the colour set\'s bytes of the frame', i, k, fr))
    return f


def _pv(p, a, get):
    v = p.ov.get(a)
    return get(a) if v is None else v


class _NullNs:
    events = ()

    def out(self, port, value):
        pass

    def inp(self, port):
        return 0xFF

    def nextreg(self, reg, val):
        pass


# ---------------------------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------------------------

SITE_KIND = {47529: 'mov', 47385: 'tog', 47349: 'old', 47908: 'col', 47964: 'clr'}
LOOP_TOP = 39408            # back in the round robin: no plot is under way
PLAY_LINES = 16             # the panel above this line is the game's own text


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shot=None, clock=0, enh=None):
    """Replay the original (C simulator); at every hook site run original and patched from the same state and compare.
    Each loop top, once per frame: screen XOR all visible sprites = the scenery, unchanged since the last clear.
    shot(frame, memory, ns, clean screen, {attr address: value before the game painted it}): the same state, for pictures.
    enh: a second patch, the same build with a colour set (Enhanced): at every site its hooks run from the same state
    beside the default's, and must give the default's registers, memory, state page and sprite attributes, with each
    shown sprite's pattern unit holding that colour set's bytes of the frame its object shows (enh_event).
    -> (Counter, examples[, states])."""
    from . import rzx as RZ
    from skoolkit.snapshot import Snapshot
    from .z80tonex import Z80Snapshot
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    Sim = _rw()
    ns = None
    nse = [None]
    alte = _alt(enh) if enh is not None else None
    states = []
    st = {'frame': -1, 'base': None, 'last_t': 0, 'lastframe': -1}
    psite = {}
    fused = collections.Counter()
    pcs = set(SITE_KIND) | set(INTERIORS) | {LOOP_TOP}
    painted = {}
    if shot:
        pcs.add(PAINT)

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    def on_pc(pc, sim):
        nonlocal ns
        R, M = sim.registers, sim.memory
        if ns is None:
            peek = M.__getitem__
            if patch.state is None or not patch.pages:
                patch.add_screen_sites(peek)
                patch.tables(peek)
            else:
                patch.add_screen_sites(peek)
            for a, old, new in patch.sites:
                for k, v in enumerate(new):
                    psite[a + k] = v
            ns = NextState(patch)
            ns.speed_in = clock                  # the game's clock (NR 7): 0 = 3.5 MHz as recorded
        if pc in INTERIORS:
            c['jump into a patched instruction (%d)!' % pc] += 1
            return
        if pc == PAINT:
            painted.setdefault(R[6] << 8 | R[7], M[R[6] << 8 | R[7]])
            return
        if pc == LOOP_TOP:
            fr = c['loop tops']
            c['loop tops'] += 1
            t = R[25]
            if st['lastframe'] != st['frame'] or fr % 64 == 0:
                st['lastframe'] = st['frame']
                check_screen(M)
            return
        kind = SITE_KIND[pc]
        get = M.__getitem__
        if collect and c['collected ' + kind] < collect:
            c['collected ' + kind] += 1
            states.append((kind, list(R), bytes(M[:65536]), ns.copy()))
        if kind == 'mov':
            fused[M[SAVED]] += 1
            fused[M[R[8] << 8 | R[9]]] += 1
        elif kind == 'tog':
            fused[M[R[8] << 8 | R[9]]] += 1
        elif kind == 'old':
            fused[M[SAVED]] += 1
        if enh is not None:
            if nse[0] is None:
                if enh.state is None or not enh.pages:
                    enh.add_screen_sites(get)
                    enh.tables(get)
                nse[0] = NextState(enh)
                nse[0].speed_in = clock
            pe = _P(get, alte, psite, nse[0])
            nse[0].nr[0x07] = clock
            nse[0].written = set()
            sim = _machine(Sim, pe, list(R), nse[0], 'e')
            sp0 = R[12]
            ret = get(sp0) | get(sp0 + 1) << 8
            ok_e = _run(sim, lambda r: r[24] == ret and r[12] == sp0 + 2)
            re_ = list(sim.registers)
        fl, npx = event(patch, kind, get, list(R), ns, alt, psite, Sim)
        if enh is not None:
            for k in enh_event(ok_e, re_, pe, nse[0], ns, enh):
                fail('%s: Enhanced %s' % (kind, k[0]), k[1:])
            c['Enhanced events'] += 1
        c[kind] += 1
        c['sprite pixels compared'] += npx
        vis = sum(1 for s in range(100) if ns.attr[s][3] & 0x80)
        if vis > c['most sprites']:
            c['most sprites'] = vis
        if kind == 'clr':
            st['base'] = None
            painted.clear()
        for k in fl:
            fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())

    def check_screen(M):
        if ns is None:
            return
        cur = bytearray(M[0x4000:0x5800])
        for s in range(100):
            sr = ns.sprite_rows(s)
            if not sr:
                continue
            x, y, rows = sr
            bx, sh = x >> 3, x & 7
            for j, v in enumerate(rows):
                if not v:
                    continue
                yy = y + j
                if not 0 <= yy < 192:
                    continue
                base = ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2)
                w = v << (8 - sh)
                for k, b in ((0, w >> 16), (1, (w >> 8) & 255), (2, w & 255)):
                    if b and 0 <= bx + k < 32:
                        cur[base + bx + k] ^= b
        if shot:
            shot(st['frame'], M, ns, cur, painted)
        if st['base'] is None:
            st['base'] = cur
            c['scenery baselines'] += 1
            return
        c['screen checks'] += 1
        if cur != st['base']:
            base = st['base']
            bad = 0
            for a in range(6144):
                if cur[a] != base[a]:
                    y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
                    if y >= PLAY_LINES:
                        bad += 1
                        if c['screen check byte examples'] < 5:
                            c['screen check byte examples'] += 1
                            ex['screen bytes'].append((st['frame'], 0x4000 + a, cur[a], base[a]))
            if bad:
                fail('screen minus sprites changed outside the panel', (bad,))
            st['base'] = cur

    # frame counter: the C replay gives none per PC; use FRAMES (23672-3) only for reports
    def wrapped(pc, sim):
        st['frame'] = sim.memory[23672] | sim.memory[23673] << 8
        on_pc(pc, sim)

    fc, err = RZ.trace(rzx_path, pcs, wrapped, stop=stop)
    if err:
        c['replay stopped: %s!' % err] += 1
    if ns is not None:
        from .simrun import addr_view  # noqa: F401
    c['frames'] = fc
    c['frames seen'] = len(fused)
    c['hooks never run'] = sum(1 for k in ('mov', 'tog', 'old', 'col', 'clr') if not c[k])
    if progress:
        progress(fc, c)
    return (c, dict(ex), states) if collect else (c, dict(ex))


def aprime_probe(rzx_path, stop=None):
    """Is A' after a plot dead? Replay with A scrambled just before each row's final EX AF,AF' (so A' differs, as in the
    patched build). A dead register changes nothing: no desync, and the same memory at the end. -> (same, frames, message)."""
    from . import rzx as RZ
    import random
    last = {}
    rng = random.Random(1)

    def snap(pc, sim):
        last['m'] = bytes(sim.memory[0x5B00:0x10000])

    def tamper(pc, sim):
        if pc in (47737, 47864):
            sim.registers[0] = rng.randrange(256)
        else:
            snap(pc, sim)
    n0, e0 = RZ.trace(rzx_path, {LOOP_TOP}, snap, stop=stop)
    m0 = last.get('m')
    n1, e1 = RZ.trace(rzx_path, {LOOP_TOP, 47737, 47864}, tamper, stop=stop)
    return (n0 == n1 and e1 == e0 and last.get('m') == m0), n1, e1


# ---------------------------------------------------------------------------------------------
# Unit tests: every frame at every shift, panel edges, guards, the negative controls
# ---------------------------------------------------------------------------------------------

def unit_tests(patch, states, neg=None):
    """states from verify(collect=n): (kind, registers, 64K memory, NextState). neg: list of (name, broken patch)."""
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    def one(pt, kind, R, mem, ns, alt_=None, ps=None):
        n2 = ns.copy()
        n2.patch = pt
        n2.state[:1024] = pt.state[:1024]
        return event(pt, kind, mem.__getitem__, R, n2, alt_ or alt, ps or psite, Sim), n2

    movs = [x for x in states if x[0] == 'mov']
    if movs:
        kind, R, mem, ns = movs[0]
        mem = bytearray(mem)
        ix = R[8] << 8 | R[9]
        for f in range(NFRAMES):
            if not frame_at(mem.__getitem__, f):
                continue
            for x in (40, 41, 42, 43, 44, 45, 46, 47, 200):
                for y in (63, 135):
                    m2 = bytearray(mem)
                    m2[ix], m2[ix + 3], m2[ix + 4] = f, x, y
                    m2[SAVED] = 0
                    ns2 = ns.copy()
                    i = (ix - OBJ0) // STRIDE
                    o = OBJ - 0xE000 + OBJW * i
                    ns2.state[o:o + 3] = bytes(3)
                    for s in obj_sprites(i):
                        ns2.attr[s][3] = 0
                    (fl, npx), _ = one(patch, 'mov', list(R), m2, ns2)
                    c['frame x position cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                    if fl and c['  fail example'] < 3:
                        c['  fail example'] += 1
                        c['  frame %d x %d y %d %s' % (f, x, y, str(fl[:2])[:150])] += 1
    cols = [x for x in states if x[0] == 'col']
    if cols:
        kind, R, mem, ns = cols[0]
        mem = bytearray(mem)
        ix = R[8] << 8 | R[9]
        # IX outside the object table: the guard leaves the sprites alone, the paint still returns the same registers
        for bad in (OBJ0 - 12, OBJ0 + 5, OBJ0 + 12 * NOBJ):
            r = list(R)
            r[8], r[9] = bad >> 8, bad & 255
            (fl, _), _ = one(patch, 'col', r, mem, ns)
            c['IX outside the table %s' % ('ok' if not fl else 'FAIL!')] += 1
        # every colour, bright or not, with the object's image showing
        i = (ix - OBJ0) // STRIDE
        for col in range(0, 8):
            for br in (0, 0x40):
                m2 = bytearray(mem)
                m2[ix + 5] = col | br
                ns2 = ns.copy()
                o = OBJ - 0xE000 + OBJW * i
                ns2.state[o:o + 3] = bytes([50, 100, 100])
                (fl, _), n3 = one(patch, 'col', list(R), m2, ns2)
                seen = {n3.attr[s][2] >> 4 for s in obj_sprites(i) if n3.attr[s][3] & 0x80}
                ok = not fl and seen == {col | (8 if br else 0)}
                c['colour cases %s' % ('ok' if ok else 'FAIL!')] += 1
    for kind in ('tog', 'old', 'clr', 'col'):
        for kk, R, mem, ns in states:
            if kk == kind:
                (fl, _), _ = one(patch, kind, list(R), bytearray(mem), ns)
                c['%s state %s' % (kind, 'ok' if not fl else 'FAIL!')] += 1
    mc, _ = clock_matrix(patch, states)
    for k, v in mc.items():
        c['clock matrix %s' % k] += v
    for name, q in (neg or []):
        if getattr(q, 'real_only', False):
            continue
        if getattr(q, 'clock', 0):
            m, _ = clock_matrix(q, states)
            c['negative %s: %s' % (name, 'detected' if any(k.endswith('!') for k in m) else 'NOT DETECTED!')] += 1
            continue
        hit = False
        qa = _alt(q)
        qs = {a + k: v for a, old, new in q.sites for k, v in enumerate(new)}
        for kind, R, mem, ns in states:
            (fl, _), _ = one(q, kind, list(R), bytearray(mem), ns, qa, qs)
            if fl:
                hit = True
                break
        c['negative %s: %s' % (name, 'detected' if hit else 'NOT DETECTED!')] += 1
    return c


def clock_matrix(patch, states, sites=None):
    """The every-site matrix (hooklib.every_site; card patch.restore-speed): each captured hook entry run at NR 7 = 0-3
    from the same state must exit at its incoming clock with the same results: registers (CMP, R included), game
    memory written, sprite attributes, pattern RAM, the state page (less the speed latch). -> (Counter, rows)."""
    from .hooklib import every_site
    alt = _alt(patch)
    Sim = _rw()
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    cases = [s_ for s_ in states if sites is None or s_[0] in sites]

    def run(n, k):
        kind, R, mem, ns0 = cases[n]
        ns = ns0.copy()
        ns.patch = patch
        ns.speed_in = k
        get = bytes(mem).__getitem__
        sp0 = R[12]
        ret = get(sp0) | get(sp0 + 1) << 8
        p = _P(get, alt, psite, ns)
        ns.nr[0x07] = k
        sim = _machine(Sim, p, list(R), ns, 'p')
        ok = _run(sim, lambda r: r[24] == ret and r[12] == sp0 + 2)
        st = bytearray(ns.state)
        st[VARS - 0xE000] = 0                    # VSPD: the latch holds the incoming clock
        regs = tuple(sim.registers[j] for j in CMP)
        return ns.nr.get(7, 0), (ok, regs, tuple(sorted(p.ov.items())), tuple(map(tuple, ns.attr)), bytes(ns.pat),
                                 bytes(st), ns.nr[0x56], ns.nr[0x57])
    return every_site(range(len(cases)), run)


# ---------------------------------------------------------------------------------------------
# Colour route (docs/COLOURS.md): recolour rewrites pattern pages only; the game never reads them
# ---------------------------------------------------------------------------------------------

NOTE = ('Sabre Wulf colour map (docs/COLOURS.md): key = graphics byte (hex address; check = its value); 8 nibbles, 0 = '
        "default (the object's own ink at run time; plant bottom rows bright green); 2-15 fixed colours; a paper bit with a "
        'nibble is drawn opaque; optional 4th = transparent mask')
RECOLOUR = {'game': 'sabre_wulf', 'output': 'sprites', 'colours': 'docs/profiles/sabre_wulf_colours.json', 'clear': True, 'note': NOTE}
# Sheet palette. Entry 1 is the run-time colour, shown as a pink the game never uses: a pixel painted that follows the object.
PALETTE = [0x00, 0xE2] + FIXED[2:]


def graphics_bytes(peek):
    seen = set()
    for f in range(NFRAMES):
        fa = frame_at(peek, f)
        if fa:
            g, w, h = fa
            seen.update(range(g + 2, g + 2 + w * h))
    return sorted(seen)


def colour_identity(peek):
    return {'schema': 1, 'game': 'sabre_wulf', 'engine': 'sabre_wulf', 'keys': 'sabre-wulf-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': hashlib.md5(bytes(peek(a) for a in graphics_bytes(peek))).hexdigest(), 'geometry': None}


def recolour(nex, cmap):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build."""
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    if not {5, 2, 0, STATE_BANK, ALT_BANK} <= set(have):
        raise ValueError('not a Sabre Wulf sprite build')
    peek = nex_peek(nex)
    p = SabreWulfPatch(colours=cmap)
    p.add_screen_sites(lambda a: _orig_byte(peek, a))
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    if have[ALT_BANK] != p.page + bytes(8192):
        raise ValueError("alt ROM image / hook code differs from this version's (rebuild with nexclash.py auto)")
    state, pages = build_tables(peek, cmap)
    if have[STATE_BANK][:8192] != state:
        raise ValueError("frame table differs from this version's (rebuild with nexclash.py auto)")
    new = {}
    for pg, data in pages.items():
        bank = pg // 2
        cur = new.get(bank, have[bank])
        o = (pg & 1) * 8192
        new[bank] = cur[:o] + data + cur[o + 8192:]
    out, changed = splice(nex, new)
    used = [k for k in cmap if cmap[k][0] == peek(int(k, 16))]
    return out, {'banks changed': changed, 'map entries used': len(used), 'map entries ignored': len(cmap) - len(used)}


def _orig_byte(peek, a):
    """In a built .nex a row site holds LD A,(HL): read back as the original so the site list comes out the same."""
    v = peek(a)
    return 0x77 if v == 0x7E and peek(a - 1) == 0xAE else v


def frame_part(peek, f):
    g, w, h = frame_at(peek, f)
    px, ent = [], {}
    p = g + 2
    for r in range(h):
        y = h - 1 - r
        for b in range(w):
            a = p + b
            v = peek(a)
            key = '%04X' % a
            ent[key] = [v, 'g']
            for k in range(8):
                ink = (v >> (7 - k)) & 1
                d = (GREEN if default_nibble(f, r) == GREEN else 15) if ink else 0
                px.append((b * 8 + k, y, key, k, 1 if ink else 0, d))
        p += w
    return {'id': '%04X' % g, 'size': 1, 'w': w * 8, 'h': h, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
            'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}


def sheets(z80, out_dir, prefix='sabre_wulf', colours=None, say=print):
    """<prefix>_PAINTING_SPRITES.png (fewest whole figures showing every graphics byte) + _REFERENCE_ALL_SPRITES.png, each
    with its _layout.json. One figure per graphic of the frame table; the default colour is shown white, as it follows the object."""
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    comps, seen = [], set()
    for f in range(NFRAMES):
        fa = frame_at(get, f)
        if fa and fa[0] not in seen:
            seen.add(fa[0])
            comps.append({'count': 1, 'group': 0, 'parts': [frame_part(get, f)]})
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    say('Sheets    : %d graphics; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


def _rom_patch(patch, sym_off, new):
    import copy
    q = copy.copy(patch)
    code = bytearray(patch.rom_code)
    a = sym_off - ROM_ORG
    code[a:a + len(new)] = new
    q.rom_code = bytes(code)
    page = bytearray(patch.page)
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    q.page = bytes(page)
    return q


def negative_patches(patch):
    """Broken builds. Each must be detected on the real recording, or on the captured states."""
    import copy
    out = []
    s = patch.syms
    code = patch.rom_code

    def at(seq, sym, n=0):
        k = code.index(bytes(seq), s[sym] - ROM_ORG)
        for _ in range(n):
            k = code.index(bytes(seq), k + 1)
        return ROM_ORG + k
    # 1 patterns one pixel to the right
    q = copy.copy(patch)
    q.pages = {}
    for pg, d in patch.pages.items():
        b = bytearray(len(d))
        for r in range(len(d) // 8):
            row = int.from_bytes(d[8 * r:8 * r + 8], 'big')
            b[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
        q.pages[pg] = bytes(b)
    out.append(('patterns shifted one pixel', q))
    # 2 one row write left in
    q = copy.copy(patch)
    row = [x for x in patch.sites if x[1] == b'\x77']
    q.drop = {row[14][0]}
    q.sites = [x for x in patch.sites if x[0] != row[14][0]]
    out.append(('one row write still draws', q))
    # 3 leave gives HL and DE back swapped
    out.append(('hooks swap HL and DE', _rom_patch(patch, at([0xC1, 0xE1, 0xD1, 0xC5], 'leave'), bytes([0xC1, 0xD1, 0xE1, 0xC5]))))
    # 4 clear does not hide: its sprite-off goes to the select register
    out.append(('clear leaves sprites on', _rom_patch(patch, at([0xED, 0x91, 0x38, 0x00], 'e_clr'), bytes([0xED, 0x91, 0x34, 0x00]))))
    # 5 the move hook does not toggle the saved image (its second CALL: tog_sv)
    out.append(('move ignores the old image', _rom_patch(patch, at([0xCD], 'e_mov', 1), bytes(3))))
    # 6 no colour: palette offset always 0
    out.append(('colour ignored', _rom_patch(patch, at([0xDD, 0x7E, 0x05], 'apply'), bytes([0x3E, 0x00, 0x00]))))
    # 7 x off by one: the add a,32 in show
    out.append(('x one pixel off', _rom_patch(patch, at([0xC6, 0x20], 'show'), bytes([0xC6, 0x21]))))
    # 8 no upload: fetch's OTIR removed
    out.append(('patterns never uploaded', _rom_patch(patch, at([0xED, 0xB3], 'fetch'), bytes(2))))
    # 9 y one line off: add a,33
    out.append(('y one line off', _rom_patch(patch, at([0xC6, 0x21], 'show'), bytes([0xC6, 0x20]))))
    # 10 slot 7 not restored at leave
    out.append(('slot 7 not restored', _rom_patch(patch, at([0xED, 0x91, 0x57, 0x01], 'leave'), bytes(4))))
    # 11 forced 3.5 MHz exit: leave reads a zero byte (0xF1F0), not the latch: same M1s (detected at clocks 1-3)
    q = _rom_patch(patch, at([0x3A, 0x00, 0xF1], 'leave'), bytes([0x3A, 0xF0, 0xF1]))
    q.clock = 1                     # the game at 7 MHz: at 3.5 MHz it cannot differ
    out.append(('forced 3.5 MHz exit', q))
    # 12 R one off after a move
    k = code.index(bytes([0xCD, s['leave'] & 255, s['leave'] >> 8]), s['e_mov'] - ROM_ORG) - 2
    assert code[k] == 0x0E
    out.append(('R one off after a move', _rom_patch(patch, ROM_ORG + k, bytes([0x0E, (code[k + 1] + 1) & 0x7F]))))
    # 13 the cache replaces units of a frame an object shows (REF test dropped)
    q = _rom_patch(patch, at([0x1A, 0xB7, 0x20], 'fetch') + 2, bytes(2))
    q.real_only, q.stop = True, 10000   # needs a full cache: a long recording that visits many rooms (sw_roam1)
    out.append(('cache replaces a shown frame', q))
    # 14 frame table wrong for one common frame: the player's standing frames show another frame
    q = copy.copy(patch)
    st = bytearray(patch.state)
    for f in range(16, 32):
        st[f * 8:f * 8 + 8] = patch.state[50 * 8:50 * 8 + 8]
    q.state = bytes(st)
    q.real_only = True
    out.append(('player frames point elsewhere', q))
    return out


def negative_real(patch, rzx_path, stop=1500, rzx_long=None):
    """Each broken build through the whole verify on the real recording (a negative's own stop on rzx_long, its clock).
    -> [(name, number of failures)]."""
    out = []
    for name, q in negative_patches(patch):
        long_ = getattr(q, 'stop', None) and rzx_long
        cc, _ = verify(q, rzx_long if long_ else rzx_path, stop=q.stop if long_ else stop, clock=getattr(q, 'clock', 0))
        out.append((name, sum(v for k, v in cc.items() if k.endswith('!'))))
    return out


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : sabre_wulf (XOR plots 47529, 47385, 47349 -> sprites; scenery, panel, text stay on the ULA)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = SabreWulfPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        cc, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in cc.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, move %d, toggle %d, old %d, paint %d, clear %d, %d sprite pixels, %d screen checks, '
            'most sprites %d, frames drawn %d -> %s' % (
                os.path.basename(r), cc['frames'], cc['mov'], cc['tog'], cc['old'], cc['col'], cc['clr'],
                cc['sprite pixels compared'], cc['screen checks'], cc['most sprites'], cc['frames seen'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        same, n, e = aprime_probe(r, stop=getattr(a, 'quick', None))
        ok = ok and same
        say('A prime   : %s  scrambled in %d frames -> %s' % (os.path.basename(r), n, 'no effect' if same else 'CHANGES THE GAME %s' % e))
    if states:
        u = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.startswith('negative')),
                                     'PASS' if not uf else 'FAIL %s' % uf))
        nn = {k: v for k, v in u.items() if k.startswith('negative')}
        say('Negative  : %d of %d detected  %s' % (sum(1 for k in nn if k.endswith('detected')), len(nn),
                                                   [k for k in nn if not k.endswith('detected')]))
    if a.rzx:
        rl = [r for r in a.rzx if 'roam1' in os.path.basename(r)]
        nr = negative_real(patch, list(a.rzx)[0], stop=min(getattr(a, 'quick', None) or 2000, 2000), rzx_long=rl[0] if rl else None)
        miss = [n for n, k in nr if not k]
        ok = ok and not miss
        say('Negative  : %s  real recording, %d of %d detected %s' % (os.path.basename(list(a.rzx)[0]), len(nr) - len(miss), len(nr), miss))
        for n, k in nr:
            say('            %s: %d failures' % (n, k))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
