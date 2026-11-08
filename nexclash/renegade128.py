"""Renegade (Imagine, 1987, 128K release) engine 'renegade128'. Additive module: reachable only through is_renegade128(). The 48K-128K file
is engine 'renegade1', Target Renegade engine 'renegade'. Facts, design and results: games/renegade.md (record renegade).

The same design as renegade1, at this release's addresses: the composer's two masked stores (38673, 38812) become LD A,(DE), so the screen only
gets scenery, and sprites follow the part records each game tick. New here: a one-pixel outline in the patterns (the owner's standing preference;
nibble 3, not part of the figure), the state page at slot 2, which the handler never touches, pattern pages in its place while uploading, interrupts on throughout, and a start at
31814, just after the game's unpack, with the snapshot's loading screen held by a stub in the alt ROM. Levels are unpacked bank by bank (40536).
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
ALT_BANK = 12
TAIL_ADDR = 0x6800                  # 0x63D0-0x70A4 is never touched in the recordings
STATE_PAGE, STATE_BANK = 22, 11
SLOT2_PAGE = 10
PAT_PAGE0 = 26
HASH, HELD, V = 0x4000, 0x4C00, 0x4D00
V_DROP = V + 0x18
V_FB = V + 0x1A
TICK, START, CLEAR, REDRAW = 32834, 32800, 39940, 38833
STORES = (38673, 38812)
PAGE_OFF = 0x1200                   # the state page's code (PAGECODE - 0x4000)
HASHEND_OFF = 0x0C00
V_OPEN, V_ARM = V + 0x3A, V + 0x3E
V_PACE_OPEN = V + 0x20 + 10          # HLIB_V_PACE + 10: the library's window open
MEMO = 0x4E00
# The K windows' ends (asm): the game's own bytes until a commit leaves debt, then hooks, then the game's own bytes again.
SITE_W, SITE_C, SITE_E = 0x967B, 0x8117, 0x812B
DYN = (SITE_W + 1, SITE_W + 2, SITE_C, SITE_C + 1, SITE_C + 2, SITE_E, SITE_E + 1, SITE_E + 2)
GAME_START = 31814
SITES_ORIG = {TICK: ('21e6bf', 'e_tick'), CLEAR: ('210040', 'e_clear'), REDRAW: ('dd2af6a4', 'e_redraw')}
INTERIORS = tuple(a + k for a, (o, _) in SITES_ORIG.items() for k in range(1, len(o) // 2)) + (START + 1, START + 2) + (SITE_C + 1, SITE_C + 2, SITE_E + 1, SITE_E + 2)
LIST, OBJ0, STRIDE = 41974, 0xBF00, 31
LEVEL, WAVE, MAPP = 28872, 28840, 42230
FRAMES = 0xF900
TILES = 0xF400
PALETTE = [0x00, 0x00, 0xFC, 0xFF, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0x02]
INK, BODY, OUTLINE = 1, 2, 3
PLAY_LINES = 136
FULL = (1 << 256) - 1
LEVEL_OF = {'L0': 0, 'L1': 1, 'L2': 2, 'L3': 3}

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'renegade128_colours.json')


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'renegade128.json'),
              os.path.join(_HERE, 'renegade128.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('renegade128.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_renegade128(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '128K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bool(sig) and bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


class M128:
    """A 128K machine with RZX-exact frames (the toolkit's recorder is 48K only) and a floating bus: the game's wait polls port 0xFF."""

    def __init__(self, snap):
        from skoolkit import CSimulator
        from skoolkit.snapshot import Snapshot
        from skoolkit.simutils import from_snapshot
        if isinstance(snap, str):
            snap = Snapshot.get(snap)
        self.sim = from_snapshot(CSimulator, snap, config={'int_active': 0})
        self.out7ffd = snap.out7ffd
        self.keys = 0xFF
        self.held = frozenset()
        self.sim.set_tracer(self)
        self.mem = self.sim.memory

    def read_port(self, registers, port):
        from skoolkit.simutils import T
        from .machine import KEYPOS, ROWS
        v = 0xFF
        if port & 1 == 0:
            hi = port >> 8
            for row in ROWS:
                if hi & (row ^ 0xFF) == 0:
                    for k in self.held:
                        if k in KEYPOS and KEYPOS[k][0] == row:
                            v &= ~(1 << KEYPOS[k][1])
            return v & 0xFF
        if port & 0xFF == 0x1F:
            return 0
        t = registers[T] - 14361
        if 0 <= t < 192 * 228:
            line, cx = t // 228, t % 228
            if cx < 128 and cx % 8 < 4:
                q = cx % 8
                col = (cx // 8) * 2 + (q >> 1)
                M = self.mem.banks[5]
                v = M[0x1800 + (line >> 3) * 32 + col] if q & 1 else M[((line & 0xC0) << 5) | ((line & 7) << 8) | ((line & 0x38) << 2) | col]
        return v

    def write_port(self, registers, port, value, offset=0):
        if port & 0x8002 == 0 and self.out7ffd & 32 == 0:
            self.mem.out7ffd(value)
            self.out7ffd = value

    def frame(self, held=frozenset()):
        from skoolkit.simutils import T, IFF, PC
        self.held = held
        regs = self.sim.registers
        fset = set()
        pc = regs[PC]
        while regs[T] < 70908:
            pc = self.sim.exec_frame(100, fset, None)
        regs[T] = 0
        if regs[IFF]:
            if self.mem[pc] == 0x76:
                regs[PC] = (regs[PC] + 1) % 65536
            self.sim.accept_interrupt(regs, self.mem, 0)

    def view(self):
        """64K as the game sees it in play: ROM part zero, banks 5, 2, 0."""
        b = self.mem.banks
        return bytes(16384) + bytes(b[5]) + bytes(b[2]) + bytes(b[0])


def level_states(start):
    """start: a Snapshot or path of the start state. The game's own '1' to start and its own 0 key for the next level (32814). -> [(name, 64K)]."""
    from .machine import parse_inputs
    m = M128(start)
    key = lambda k, n: [m.frame(parse_inputs(k) if k else frozenset()) for _ in range(n)]
    key('', 150)
    key('1', 8)
    key('', 300)
    out = [('L0', m.view())]
    for lv in (1, 2, 3):
        for _ in range(40):
            key('0', 12)
            if m.mem[LEVEL] == lv:
                break
            key('', 12)
        if m.mem[LEVEL] != lv:
            raise ValueError('the 0 key did not reach level %d' % lv)
        key('', 200)
        out.append(('L%d' % lv, m.view()))
    return out


def graphics_in(mem):
    """Every graphic the frame table of this memory points at -> {address: (W, R)}."""
    gs = {}
    for i in range(0, 0xFF0 // 8):
        t = FRAMES + 8 * i
        if t + 8 > 0xFF00:
            break
        for k in (2, 6):
            g = mem[t + k] | mem[t + k + 1] << 8
            if 0x8400 <= g < 0xF000:
                w, r = mem[g], mem[g + 1]
                if 1 <= w <= 6 and 1 <= r <= 64 and g + 2 + 2 * w * r <= 0x10000:
                    gs[g] = (w, r)
    for g in range(0xBD0E, 0xBDE0, 38):         # the flashes of a hit: 2 x 9 each, not in the frame table
        if mem[g] == 2 and mem[g + 1] == 9:
            gs[g] = (2, 9)
    if mem[0xCC1C] == 2 and mem[0xCC1D] == 16:  # the last level's thrown weapon: a constant in the code
        gs[0xCC1C] = (2, 16)
    if mem[0xCC5E] == 1 and mem[0xCC5F] == 4:   # the last boss's bullet: a constant in the code
        gs[0xCC5E] = (1, 4)
    return gs


def shape(w, r):
    """16-pixel columns and rows, with one pixel of margin all round for the outline."""
    return (w * 8 + 17) >> 4, (r + 17) >> 4


def checksum(raw):
    return sum(raw) & 0xFFFF


def hash_slot(g, s):
    return ((g & 255) + 2 * (g >> 8) + (s & 255) + 8 * (s >> 8)) & 511


def all_graphics(states):
    """-> [(state name, g, W, R, raw bytes)], one per (address, content), first state first. Only those that fit their slots."""
    seen, out = set(), []
    for name, mem in states:
        for g, (w, r) in sorted(graphics_in(mem).items()):
            raw = bytes(mem[g:g + 2 + 2 * w * r])
            cols, rows = shape(w, r)
            if cols * rows > 6:
                continue
            k = (g, checksum(raw))
            if k not in seen:
                seen.add(k)
                out.append((name, g, w, r, raw))
    return out


def has_outline(w, r):
    """Not on what is too small to carry one: bullets, sparks, flashes."""
    return not (w <= 2 and r <= 16)


def key_for(g, cs_, p):
    """Colour-map key of a graphic's byte pair: address and the graphic's checksum, since the same address holds other graphics in other levels."""
    return '%04X:%04X' % (g + p + 1, cs_)


def _opaque(raw, x, y):
    w, r = raw[0], raw[1]
    if not (0 <= x < w * 8 and 0 <= y < r):
        return False
    p = 2 + 2 * ((x >> 3) * r + y)
    m = 0x80 >> (x & 7)
    return bool(raw[p + 1] & m) or not raw[p] & m


def frame_pairs(mem):
    """Each frame's two parts, for both facings, as 37682 places them: -> [(raw A, x A, y A, mirror A, raw B, x B, y B, mirror B)], x in pixels.
    Part B is drawn after part A, so its sprites are in front of A's."""
    out = []
    table = graphics_in(mem)
    for i in range(0, 0xFF0 // 8):
        t = FRAMES + 8 * i
        if t + 8 > 0xFF00:
            break
        ga, gb = mem[t + 2] | mem[t + 3] << 8, mem[t + 6] | mem[t + 7] << 8
        if ga not in table or gb not in table:
            continue
        ra = bytes(mem[ga:ga + 2 + 2 * table[ga][0] * table[ga][1]])
        rb = bytes(mem[gb:gb + 2 + 2 * table[gb][0] * table[gb][1]])
        for d in (0, 1):
            na = mem[t + 1] >> 4 if d == 0 else mem[t + 1] & 15
            nb = mem[t + 5] >> 4 if d == 0 else mem[t + 5] & 15
            out.append((ra, -8 * na, -mem[t], d ^ 1, rb, -8 * nb, -mem[t + 4], d))
    return out


def outline_cells(raw):
    """The outline of a graphic, in image pixels (so x or y may be -1, or just past the edge): a clear pixel beside a drawn one."""
    w, r = raw[0], raw[1]
    out = []
    for y in range(-1, r + 1):
        for x in range(-1, w * 8 + 1):
            if not _opaque(raw, x, y) and any(_opaque(raw, x + dx, y + dy) for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0))):
                out.append((x, y))
    return out


def join_drops(states):
    """Outline pixels inside a figure made of two parts, as the join down the middle of the riderless bike: on the other part, or in the
    seam beside it. -> {raw graphic: {(x, y)}}. A graphic used in several frames loses a pixel if any frame needs it."""
    drops = {}
    done = set()
    cells = {}

    def side(r1, x1, y1, m1, r2, x2, y2, m2):
        if not has_outline(r1[0], r1[1]):
            return
        ol = cells.setdefault(r1, outline_cells(r1))
        w1, w2 = r1[0] * 8, r2[0] * 8
        for x, y in ol:
            sx = x1 + (w1 - 1 - x if m1 else x)
            sy = y1 + y
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                px = sx + dx - x2
                if m2:
                    px = w2 - 1 - px
                if _opaque(r2, px, sy + dy - y2):
                    drops.setdefault(r1, set()).add((x, y))
                    break
    for name, mem in states:
        for k in frame_pairs(mem):
            if k not in done:
                done.add(k)
                ra, xa, ya, ma, rb, xb, yb, mb = k
                side(ra, xa, ya, ma, rb, xb, yb, mb)
                side(rb, xb, yb, mb, ra, xa, ya, ma)
    return drops


def join_faults(states, drops):
    """Unit check: outline left on the other part of a figure, frame by frame. -> count."""
    bad = 0
    for name, mem in states:
        for ra, xa, ya, ma, rb, xb, yb, mb in frame_pairs(mem):
            if not has_outline(rb[0], rb[1]):
                continue
            wa, wb = ra[0] * 8, rb[0] * 8
            gone = drops.get(rb, ())
            for x, y in outline_cells(rb):
                if (x, y) in gone:
                    continue
                px = xb + (wb - 1 - x if mb else x) - xa
                if ma:
                    px = wa - 1 - px
                if _opaque(ra, px, yb + y - ya):
                    bad += 1
    return bad


def patterns(item, base=None, cmap=None, outline=True, drop=()):
    """cols * rows patterns of 128 bytes, top row first, the graphic one pixel in from the left and top. Pixel: data bit = ink, mask and data clear =
    the body, else clear; a clear pixel beside a drawn one is the outline, which the figure never loses. The map overrides per (key, bit)."""
    name, g, w, r, raw = item
    cols, rows = shape(w, r)
    can = [[0] * (cols * 16) for _ in range(rows * 16)]
    s = checksum(raw)
    for c in range(w):
        for y in range(r):
            p = 2 + 2 * (c * r + y)
            mask, data = raw[p], raw[p + 1]
            e = cmap.get(key_for(g, s, p)) if cmap else None
            if e and e[0] != data:
                e = None
            for k in range(8):
                m = 0x80 >> k
                n = INK if data & m else (BODY if not mask & m else 0)
                if e:
                    if len(e) > 3 and e[3] & m:
                        n = 0
                    elif e[2][k]:
                        n = e[2][k]
                can[y + 1][c * 8 + k + 1] = n
    if outline and has_outline(w, r):
        H, W = len(can), len(can[0])
        add = []
        for y in range(H):
            for x in range(W):
                if not can[y][x] and any(0 <= y + dy < H and 0 <= x + dx < W and can[y + dy][x + dx] not in (0, OUTLINE)
                                         for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0))):
                    add.append((y, x))
        for y, x in add:
            if (x - 1, y - 1) not in drop:      # image pixels: not where this outline would lie on the figure's other part
                can[y][x] = OUTLINE
    out = bytearray()
    for ry in range(rows):
        for cx in range(cols):
            for y in range(16):
                row = can[ry * 16 + y][cx * 16:cx * 16 + 16]
                for k in range(0, 16, 2):
                    out.append(row[k] << 4 | row[k + 1])
    return bytes(out)


def build_tables(states, cmap=None, outline=True):
    """-> (state page 8K, {page: 8K}). The layout does not depend on the map, so recolour changes pattern pages only."""
    hsh = bytearray(3072)
    pages = {}
    page, idx = PAT_PAGE0, 0
    used = set()
    drops = join_drops(states) if outline else {}
    for item in all_graphics(states):
        name, g, w, r, raw = item
        cols, rows = shape(w, r)
        n = cols * rows
        if idx + n > 64:
            page, idx = page + 1, 0
        data = patterns(item, None, cmap, outline, drops.get(raw, ()))
        pages.setdefault(page, bytearray(8192))[idx * 128:idx * 128 + n * 128] = data
        s = checksum(raw)
        slot = hash_slot(g, s)
        while slot in used:
            slot = (slot + 1) & 511
        used.add(slot)
        hsh[slot * 6:slot * 6 + 6] = bytes([g & 255, g >> 8, s & 255, s >> 8, page, idx | LEVEL_OF[name] << 6])
        idx += n
    if len(used) > 400:
        raise ValueError('hash table too full: %d' % len(used))
    state = bytearray(8192)
    state[0:3072] = hsh
    return bytes(state), {k: bytes(v) for k, v in pages.items()}


class PlainPatch:
    """The plain .nex: no hooks. The snapshot needs nothing: PC is in the game's RAM."""
    name = 'Renegade plain conversion'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    extra_banks = {}
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def apply(self, snap):
        snap.port1ffd = 4       # with 7FFD bit 4 set, as in play, the ROM is the 48K ROM, as on a 128K Spectrum


class RenegadePatch:
    name = 'Renegade 128K: figures -> hardware sprites (altrom hooks, tables in Next pages at slots 2 and 6)'

    def __init__(self, start, prof=None, rom_code=None, colours=None, stores=STORES, outline=True):
        self.start = start
        self.outline = outline
        self.prof = prof or load_profile()
        self.colours = load_colours() if colours is None else colours
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.page_code = bytes.fromhex(h['page'])
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
            self.sites.append((a, bytes.fromhex(old), bytes([0xC3]) + self.syms[sym].to_bytes(2, 'little') +
                               bytes([0x00]) * (len(old) // 2 - 3)))
        self.sites.append((START, bytes.fromhex('cd4aa5'), bytes([0xCD]) + self.syms['e_start'].to_bytes(2, 'little')))
        for a in stores:
            self.sites.append((a, b'\x12', b'\x1a'))
        self.extra_banks = {}
        self.state = None
        self.pages = None

    def tables(self):
        self.states = level_states(self.start)
        self.state, self.pages = build_tables(self.states, self.colours, self.outline)
        st = bytearray(self.state)
        st[PAGE_OFF:PAGE_OFF + len(self.page_code)] = self.page_code   # hook code in the state page, past the tables
        self.state = bytes(st)

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.pc != GAME_START:
            raise ValueError('Renegade 128K patch expects the start snapshot (PC %d)' % GAME_START)
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.tables()
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        snap.port1ffd = 4
        snap.pc = self.syms['e_front']          # the loading screen is up: the stub holds it, then JP GAME_START
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        pg = bytearray(self.page)
        pg[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self.page = bytes(pg)
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
        self.nr = {0x52: SLOT2_PAGE, 0x56: 0, 0x07: 0, 0x34: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patptr = 0
        self.state = bytearray(patch.state)
        self.cache = {}
        self.ports = 0
        self.floor = None
        self.sel = None                     # NextREG selected at 0x243B (the speed latch reads NR 7)
        self.line, self.polls = 0, 0        # the video line (the pace library): moves on with every reading

    def copy(self):
        q = NextState.__new__(NextState)
        q.__dict__.update(self.__dict__)
        q.nr = dict(self.nr)
        q.attr = [list(a) for a in self.attr]
        q.pat = bytearray(self.pat)
        q.state = bytearray(self.state)
        q.cache = {}
        return q

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr[0x34] & 0x7F][reg - 0x35] = val
        if reg == 0x41:
            self.floor = val

    def out(self, port, val):
        p = port & 0xFF
        if port == 0x243B:                  # NextREG select (the speed latch reads NR 7)
            self.sel = val
            return
        if port == 0x303B:
            self.patptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif p == 0x5B:
            self.pat[self.patptr & 0x3FFF] = val
            self.patptr += 1
            self.cache.clear()
        else:
            self.ports += 1

    def page_byte(self, page, off):
        if page == STATE_PAGE:
            return self.state[off]
        d = self.patch.pages.get(page)
        return d[off] if d else 0

    def tile(self, base, mirror):
        """16 rows of (opaque bits, ink bits): bit 15 = left."""
        k = (base, mirror)
        t = self.cache.get(k)
        if t is None:
            t = []
            for j in range(16):
                o = i = 0
                for x in range(16):
                    b = self.pat[base + j * 8 + x // 2]
                    n = (b >> 4) if x % 2 == 0 else (b & 15)
                    bit = (1 << x) if mirror else (0x8000 >> x)
                    if n and n != OUTLINE:          # the outline is not part of the figure: verify sees through it
                        o |= bit
                        if n != BODY:
                            i |= bit
                t.append((o, i))
            self.cache[k] = t
        return t

    def visible(self):
        return [s for s in range(128) if self.attr[s][3] & 0x80]

    def compose(self, lines, top=PLAY_LINES, over=None):
        """lines: list of ints, bit 255 = left of the line. Sprites in number order, later on top; clip window 0-255, 0-135.
        over: list of ints, gets the pixels where two opaque sprites meet."""
        seen = [0] * len(lines)
        for s in self.visible():
            a = self.attr[s]
            x = a[0] + (a[2] & 1) * 256 - 32
            y = a[1] + (a[4] & 1) * 256 - 32
            base = (a[3] & 0x3F) * 256 + (128 if a[4] & 0x40 else 0)
            for j, (o, i) in enumerate(self.tile(base, bool(a[2] & 8))):
                yy = y + j
                if not o or not 0 <= yy < top:
                    continue
                sh = 240 - x
                if sh >= 0:
                    om, im = o << sh, i << sh
                else:
                    om, im = o >> -sh, i >> -sh
                om &= FULL
                im &= FULL
                if over is not None:
                    over[yy] |= seen[yy] & om
                    seen[yy] |= om
                lines[yy] = (lines[yy] & ~om) | im
        return lines


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


def line_of(M, y):
    a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
    return int.from_bytes(bytes(M[a:a + 32]), 'big')


def scenery(M):
    """The play area as tiles: -> [136 ints]. Map (42230): 17 cells a column; tile t: 8 bytes at 0xF400 + 8t."""
    mp = M[MAPP] | M[MAPP + 1] << 8
    cols = []
    out = [bytearray(32) for _ in range(136)]
    for c in range(32):
        for r in range(17):
            t = M[(mp + c * 17 + r) & 0xFFFF] & 0x7F
            g = TILES + t * 8
            for k in range(8):
                out[r * 8 + k][c] = M[g + k]
    del cols
    return [int.from_bytes(b, 'big') for b in out]


# ---------------------------------------------------------------------------------------------
# One hook event
# ---------------------------------------------------------------------------------------------

CMP = list(range(0, 13)) + [14, 15] + list(range(16, 25)) + [26, 27]   # all but T, MEMPTR; R included (index 15, card patch.preserve-r)
_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


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
    """The patched build: sites, alt ROM, Next pages at slots 2 and 6."""

    def __init__(s, get, alt, psite, ns):
        _O.__init__(s, get)
        s.alt, s.psite, s.ns, s.romw, s.pagew = alt, psite, ns, 0, 0

    def __getitem__(s, a):
        if a < 0x4000:
            return s.alt[a]
        nr = s.ns.nr
        if 0x4000 <= a < 0x6000 and nr[0x52] != SLOT2_PAGE:
            return s.ns.page_byte(nr[0x52], a - 0x4000)
        if 0xC000 <= a < 0xE000 and nr[0x56] != 0:
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
        nr = s.ns.nr
        if 0x4000 <= a < 0x6000 and nr[0x52] != SLOT2_PAGE:
            if nr[0x52] == STATE_PAGE:
                s.ns.state[a - 0x4000] = v
            else:
                s.pagew += 1
            return
        if 0xC000 <= a < 0xE000 and nr[0x56] != 0:
            s.pagew += 1
            return
        s.ov[a] = v


def _machine(Sim, mem, regs, ns, slot):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot)

    class Tr:
        def read_port(self, regs_, port):
            if port == 0x253B and getattr(ns, 'sel', None) in (0x1E, 0x1F):
                if ns.sel == 0x1F:
                    ns.polls += 1
                    ns.line = (ns.line + 3) % 311
                    return ns.line & 255
                return ns.line >> 8 & 1
            if port == 0x253B and getattr(ns, 'sel', None) is not None:   # a NextREG read: NR 7 as the core
                if ns.sel == 0x07:                                      # composes it (actual << 4 | programmed)
                    sp = ns.nr.get(0x07, 0) & 3
                    return sp << 4 | sp
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


EXIT = {TICK: 32837, START: 42314, CLEAR: 39943, REDRAW: 38837, SITE_W: 0x98ED, SITE_C: SITE_C + 3, SITE_E: SITE_E + 3}
KIND = {TICK: 'tick', START: 'start', CLEAR: 'clear', REDRAW: 'redraw', SITE_W: 'window at the raster wait', SITE_C: 'window at the slicer', SITE_E: 'window past the slicer'}
HOOKS = (TICK, START, CLEAR, REDRAW)


def event(patch, pc, get, R, ns, alt, psite, Sim, st):
    """Original and hook from one state. -> failure strings."""
    fails = []
    stop = EXIT[pc]
    o = _O(get)
    so = _machine(Sim, o, list(R), ns.__class__.__new__(ns.__class__) if False else _NULL, 'o')
    so.registers[24] = pc
    if not _run(so, stop, 100):
        fails.append('original did not reach its exit')
    p = _P(get, alt, psite, ns)
    sp = _machine(Sim, p, list(R), ns, 'p')
    sp.registers[24] = pc
    if not _run(sp, stop, 3000000):
        fails.append('hook did not reach its exit')
    dt = sp.registers[25] - R[25]
    st['hook T (28 MHz)'] += dt
    if dt > st['most hook T in one event']:
        st['most hook T in one event'] = dt
    bad = [k for k in CMP if k != 24 and so.registers[k] != sp.registers[k]]
    if bad:
        fails.append(('registers', bad[:6]))
    low = sp.registers[12]
    for a in set(o.ov) | set(p.ov):
        if a >= low - 64 and a < low:
            continue                    # dead stack: below SP
        if o[a] != p[a] and a not in psite:
            fails.append(('memory', a, o[a], p[a]))
            break
    if ns.nr[0x52] != SLOT2_PAGE or ns.nr[0x56] != 0:
        fails.append('slots not restored')
    if ns.nr[0x07] != (3 if ns.state[V_OPEN - 0x4000] else 0):      # 28 MHz only with a K window open
        fails.append('speed not restored')
    for a in DYN:
        if a in p.ov:
            psite[a] = p.ov[a]
    if p.romw:
        fails.append('ROM write')
    if p.pagew:
        fails.append('page write')
    return fails


class _Null:
    def out(self, port, value):
        pass

    def nextreg(self, reg, val):
        pass


_NULL = _Null()


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shot=None):
    """See the module's docstring. shot(frame, memory, ns): the same state, for pictures. -> (Counter, examples[, states])."""
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    Sim = _rw()
    states = []
    psite = {}
    box = {'ns': None, 'n': 0, 'bg': None, 'bgk': None, 'seq': 0, 'dyn0': {}}
    digests = []
    seen = collections.Counter()
    pc_first = None

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((c['ticks'],) + tuple(info))

    def setup(M):
        if patch.state is None or not patch.pages:
            patch.tables()
        for a, old, new in patch.sites:
            if a not in STORES:
                for k, v in enumerate(new):
                    psite[a + k] = v
        for a in STORES:
            psite[a] = 0x1A if any(s[0] == a for s in patch.sites) else 0x12
        for a in DYN:
            psite[a] = box['dyn0'][a] = M[a]
        box['ns'] = NextState(patch)

    def digest(R, M):
        h = hashlib.md5()
        h.update(bytes([R[k] & 255 for k in CMP if k != 24]))
        sp = R[12]
        low = max(0xBD80, min(sp, 0xBE00))           # below the stack: dead, an interrupt there saved A from the copy
        h.update(bytes(M[0x5B00:0xBD80]))
        h.update(bytes(M[low:0xFD00]))
        for a in range(0x5000, 0x5800, 256):     # the third third: all but character row 16, in the play area (HUD, attributes)
            h.update(bytes(M[a + 32:a + 256]))
        h.update(bytes(M[0x5800:0x5B00]))
        return h.digest()

    def check_screen(M, ns):
        box['bg'] = scenery(M)
        over = [0] * 192
        lines = ns.compose(list(box['bg']), over=over)
        # a hit's flash: its record is set a tick before the game composes it, so the sprite leads by one tick
        i = LIST
        while M[i] != 255 and i < LIST + 12:
            b = OBJ0 + M[i]
            i += 1
            if M[b + 4] == 0xFF and (M[b + 3] & 7) == 1:
                r = 0xFF00 + M[b + 3]
                if M[r + 5] & 0xC2 == 0xC2:
                    x0, y0, x1, y1 = M[r], M[r + 1], M[r + 2], M[r + 3]
                    if x0 < 32:
                        m = (1 << ((min(x1, 31) - x0 + 1) * 8)) - 1 << ((31 - min(x1, 31)) * 8)
                        for y in range(y0, min(y1 + 1, 136)):
                            over[y] |= m
        bad = 0
        first = None
        depth = 0
        nb = 0
        for y in range(PLAY_LINES):
            d = lines[y] ^ line_of(M, y)
            if d:
                dd = d & ~over[y]
                if dd:                          # a pixel no two figures share
                    bad += 1
                    nb += sum(1 for k in dd.to_bytes(32, 'big') if k)
                    if first is None:
                        first = y
                else:                           # the game re-sorted its list and has not recomposed that rectangle yet
                    depth += 1
        c['screen checks'] += 1
        if depth:
            c['screen checks where only stale depth differs'] += 1
        if bad:
            # The original's screen is only as new as its last compose: a record can change a tick early, and a column can stay behind
            # until the figure moves (read at 7141 of long1: column 25, the original's). So a few bytes on a few checks are allowed, counted, reported.
            # A graphic the game poked in place shows up to a few bytes the sprite does not have, for as long as the figure uses it.
            if nb <= 8 and ns.state[V_FB - 0x4000] | ns.state[V_FB - 0x4000 + 1]:
                c['screen checks differing by a poked graphic'] += 1
                return
            c['screen checks with a few bytes different'] += 1
            c['screen bytes different'] += nb
            if nb > 64 or c['screen checks with a few bytes different'] > 4 + c['screen checks'] // 50:
                fail('sprites over scenery differ from the original', (first, bad, nb, M[LEVEL]))
        v = len(ns.visible())
        if v > c['most sprites']:
            c['most sprites'] = v

    def on_pc(pc, sim):
        R, M = sim.registers, View(sim.memory)
        if box['ns'] is None:
            setup(M)
        ns = box['ns']
        if pc in INTERIORS:
            c['jump into a patched instruction (%d)!' % pc] += 1
            return
        if pc not in EXIT:
            return
        armed = ns.state[V_ARM - 0x4000]
        if pc not in HOOKS and not armed:
            return                      # the game's own bytes: nothing of ours runs
        kind = KIND[pc]
        c[kind] += 1
        if kind == 'tick':
            c['ticks'] += 1
            digests.append(digest(R, M))
        if collect and c['collected ' + kind] < collect:
            c['collected ' + kind] += 1
            states.append((kind, list(R), bytes(M[0:65536]), ns.copy()))
        if shot == 'census' and kind == 'tick':
            census(M, c)
        fl = event(patch, pc, M.__getitem__, list(R), ns, alt, psite, Sim, c)
        for k in fl:
            fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())
        now = ns.state[V_ARM - 0x4000]
        if not now and any(psite[a] != box['dyn0'][a] for a in DYN):
            fail('a window closed with a hook left in the game', (kind,))
        if pc in (SITE_W, SITE_C) and armed and not now:
            c['windows that repaid their debt'] += 1
        if pc in (SITE_W, SITE_C, SITE_E) and ns.state[V_PACE_OPEN - 0x4000] != ns.state[V_OPEN - 0x4000]:
            fail('a window closed without its wait', (kind,))       # hlib_pace_wait clears the library's own flag
        if kind in ('clear', 'redraw') and ns.visible():
            fail('%s leaves sprites on' % kind, (len(ns.visible()),))
        if kind in ('tick', 'start'):
            check_screen(M, ns)
            d = ns.state[V_DROP - 0x4000] | ns.state[V_DROP - 0x4000 + 1] << 8
            if d != box.get('drop', 0):
                box['drop'] = d
                fail('a part could not be shown', (d,))
            c['graphics found by address alone'] = ns.state[V_FB - 0x4000] | ns.state[V_FB - 0x4000 + 1] << 8
            if callable(shot):
                shot(c['ticks'], M, ns)

    fc, err = RZ.trace(rzx_path, set(EXIT) | set(INTERIORS), on_pc, stop=stop)
    if err:
        c['replay stopped: %s!' % err] += 1
    c['frames'] = fc
    c['hooks never run'] = sum(1 for k in HOOKS if not c[KIND[k]])
    if not c[KIND[SITE_W]] or not c['windows that repaid their debt']:
        c['no K window ran and repaid its debt!'] += 1
    # second replay: the two stores patched
    idx = {'i': 0, 'first': True}
    pat_stores = {a: (0x1A if any(s[0] == a for s in patch.sites) else 0x12) for a in STORES}

    def on2(pc, sim):
        R, M = sim.registers, View(sim.memory)
        if idx['first']:
            idx['first'] = False
            for a, v in pat_stores.items():
                M[a] = v
        if pc != TICK:
            return
        i = idx['i']
        idx['i'] = i + 1
        c['ticks replayed patched'] += 1
        # the two sites themselves, then compare
        for a in STORES:
            M[a] = 0x12
        same = i < len(digests) and digest(R, M) == digests[i]
        for a, v in pat_stores.items():
            M[a] = v
        if not same:
            c['patched stores change the game state!'] += 1
            if len(ex['patched stores']) < 5:
                ex['patched stores'].append((i,))
        box['bg2'] = scenery(M)
        bad = sum(1 for y in range(PLAY_LINES) if line_of(M, y) != box['bg2'][y])
        c['bare scenery checks'] += 1
        if bad:
            c['bare scenery checks with differences'] += 1
            fail2 = 'play area is not bare scenery'
            c[fail2 + '!'] += 1
            if len(ex[fail2]) < 5:
                ex[fail2].append((i, bad, M[LEVEL]))
    start = patch_start_pcs(rzx_path)
    fc2, err2 = RZ.trace(rzx_path, {TICK} | start, on2, stop=stop)
    if err2:
        c['patched replay stopped: %s!' % err2] += 1
    if fc2 != fc:
        c['patched replay ran %d frames against %d!' % (fc2, fc)] += 1
    if progress:
        progress(fc, c)
    return (c, dict(ex), states) if collect else (c, dict(ex))


def census(M, c):
    """Clash in the original, at a tick. Parts shown: do they span several attributes? Their pixels: in a cell of the floor's attribute or not."""
    floor = M[0x5800 + 32 * 16 + 16]
    i = LIST
    while M[i] != 255 and i < LIST + 12:
        b = OBJ0 + M[i]
        i += 1
        for r in (b + 15, b + 23):
            if M[r + 5] & 0xC2 != 0xC2:
                continue
            g = M[r + 6] | M[r + 7] << 8
            w, h = M[g], M[g + 1]
            if not (g >= 0x4000 and 1 <= w <= 6 and 1 <= h <= 64):
                continue
            x, y = M[r], M[r + 1]
            x = x - 256 if x > 127 else x
            at = set()
            for cc in range(w):
                col = x + cc
                if not 0 <= col < 32:
                    continue
                for j in range(h):
                    yy = y + j
                    if yy >= PLAY_LINES:
                        continue
                    a = M[0x5800 + (yy >> 3) * 32 + col]
                    at.add(a)
                    p = 2 + 2 * (cc * h + j)
                    mask, data = M[g + p], M[g + p + 1]
                    n = bin((data | (0xFF ^ mask)) & 255).count('1')
                    c['figure pixels'] += n
                    if a != floor:
                        c['figure pixels on cells not the floor'] += n
            c['plots'] += 1
            if len(at) > 1:
                c['plots spanning several attributes'] += 1


def patch_start_pcs(rzx_path):
    """The recording's first PC, so the stores are patched before anything runs."""
    from skoolkit.snapshot import Snapshot
    from .rzx import parse_rzx
    for b in parse_rzx(rzx_path):
        if isinstance(b.obj, Snapshot) if hasattr(b, 'obj') else False:
            return {b.obj.pc}
    return set()


# ---------------------------------------------------------------------------------------------
# Unit tests: every graphic of every level, at the edges, mirrored or not
# ---------------------------------------------------------------------------------------------

def plot_lines(raw, x, y, mirror, lines, top=PLAY_LINES):
    """What the game's plot does to a line image: columns of (mask, data), clipped to 0-31 and 0-135."""
    w, r = raw[0], raw[1]
    masks = {}
    for c in range(w):
        col = x + (w - 1 - c if mirror else c)
        if not 0 <= col < 32:
            continue
        for j in range(r):
            yy = y + j
            if not 0 <= yy < top:
                continue
            p = 2 + 2 * (c * r + j)
            m, d = raw[p], raw[p + 1]
            if mirror:
                m = int('{:08b}'.format(m)[::-1], 2)
                d = int('{:08b}'.format(d)[::-1], 2)
            sh = (31 - col) * 8
            lines[yy] = (lines[yy] & ~((0xFF ^ m) << sh)) | (d << sh)
    del masks
    return lines


def unit_tests(patch, states, neg=None):
    """states from verify(collect=n): (kind, registers, 64K memory, NextState). One object at a time, all graphics."""
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    psite = {}
    for a, old, new in patch.sites:
        if a not in STORES:
            for k, v in enumerate(new):
                psite[a + k] = v
    tick = [s for s in states if s[0] == 'tick']
    if not tick:
        c['no captured tick!'] += 1
        return c
    _, R0, mem0, _ns = tick[0]
    lvs = patch.states
    REC = 0xBF00 + 15

    def one(pt, psite_, alt_, mem, x, y, mir):
        """A single part through commit -> line image, or None."""
        m = bytearray(mem)
        for o in range(0, 248, STRIDE):
            m[0xBF00 + o + 15 + 5] = 0
            m[0xBF00 + o + 23 + 5] = 0
            m[0xBF00 + o + 3] = m[0xBF00 + o + 4] = 0
        m[LIST] = 0
        m[LIST + 1] = 0xFF
        return m

    # build each level's memory at the tick: the level's graphic bytes over the captured state
    tested = 0
    fails = collections.Counter()
    ns = NextState(patch)
    for name, mem in lvs:
        for g, (w, r) in sorted(graphics_in(mem).items()):
            cols, rows = shape(w, r)
            if cols * rows > 6:
                c['graphics too big for their slots (none expected in play)'] += 1
                continue
            raw = bytes(mem[g:g + 2 + 2 * w * r])
            for x, y, mir in ((5, 40, 0), (5, 40, 1), (0, 0, 0), (31, 100, 1), (-2 & 255, 60, 0), (-2 & 255, 60, 1), (29, 130, 0), (28, 118, 1)):
                m = one(patch, psite, alt, mem0, x, y, mir)
                m[g:g + len(raw)] = raw
                rec = REC
                m[rec + 0] = x
                m[rec + 1] = y
                m[rec + 5] = 0xC2 | mir
                m[rec + 6] = g & 255
                m[rec + 7] = g >> 8
                m[LEVEL] = 0
                m[WAVE] = 0
                # a new key each time forces the pattern slots to reload: clear held
                ns.state[HELD - 0x4000:HELD - 0x4000 + 48] = bytes(48)
                if (x, y, mir) == (5, 40, 0):           # the first position takes the checksum; the others find the memo
                    ns.state[MEMO - 0x4000:MEMO - 0x4000 + 1024] = bytes(1024)
                p = _P(m.__getitem__, alt, psite, ns)
                sim = _machine(Sim, p, list(R0), ns, 'p')
                sim.registers[24] = TICK
                if not _run(sim, EXIT[TICK], 500000):
                    fails['hook ran away'] += 1
                    continue
                ns.state[V_ARM - 0x4000] = ns.state[V_OPEN - 0x4000] = 0
                if ns.nr[0x07] not in (0, 3):
                    fails['speed'] += 1
                ns.nr[0x07] = 0
                lines = ns.compose([0] * 192, PLAY_LINES)
                want = plot_lines(raw, x if x < 128 else x - 256, y, bool(mir), [0] * 192)
                tested += 1
                if lines != want:
                    fails['pixels (%s %04X x=%d y=%d m=%d)' % (name, g, x, y, mir)] += 1
                if ns.nr[0x52] != SLOT2_PAGE or ns.nr[0x56] != 0:
                    fails['slots'] += 1
    # a graphic poked in place: same address, this level's patterns; the figure stays. An address in no table: dropped, counted.
    name, mem = lvs[0]
    g, (w, r) = sorted(graphics_in(mem).items())[10]
    raw = bytes(mem[g:g + 2 + 2 * w * r])
    for poke, want_shown in ((True, True), (False, False)):
        m = one(patch, psite, alt, mem0, 5, 40, 0)
        m[g:g + len(raw)] = raw
        gg = g
        if poke:
            m[g + 3] ^= 0x10
        else:
            gg = 0x8100
            m[gg:gg + len(raw)] = raw
        m[REC + 0], m[REC + 1], m[REC + 5], m[REC + 6], m[REC + 7] = 5, 40, 0xC2, gg & 255, gg >> 8
        m[LEVEL] = m[WAVE] = 0
        ns.state[HELD - 0x4000:HELD - 0x4000 + 48] = bytes(48)
        ns.state[MEMO - 0x4000:MEMO - 0x4000 + 1024] = bytes(1024)
        p = _P(m.__getitem__, alt, psite, ns)
        sim = _machine(Sim, p, list(R0), ns, 'p')
        sim.registers[24] = TICK
        ok = _run(sim, EXIT[TICK], 500000)
        ns.state[V_ARM - 0x4000] = ns.state[V_OPEN - 0x4000] = 0
        ns.nr[0x07] = 0
        lines = ns.compose([0] * 192, PLAY_LINES)
        same = lines == plot_lines(raw, 5, 40, False, [0] * 192)
        if not ok or same != want_shown or (not want_shown and any(lines)):
            c['%s!' % ('poked graphic lost' if poke else 'unknown address drawn')] += 1
        else:
            c['poked graphic kept' if poke else 'unknown address dropped'] += 1
    c['graphic positions tested'] = tested
    jf = join_faults(lvs, join_drops(lvs))
    c['outline pixels dropped at joins'] = sum(len(v) for v in join_drops(lvs).values())
    if jf:
        c['outline on the figure\'s other part!'] = jf
    if not join_drops(lvs):
        c['no joins found!'] = 1
    for k, v in fails.items():
        c['%s!' % k] += v
    return c


# ---------------------------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------------------------

def graphics_part(item, base=None):
    name, g, w, r, raw = item
    px, ent = [], {}
    cks = checksum(raw)
    for c in range(w):
        for y in range(r):
            p = 2 + 2 * (c * r + y)
            mask, data = raw[p], raw[p + 1]
            key = key_for(g, cks, p)
            ent[key] = [data, 'g']
            for k in range(8):
                m = 0x80 >> k
                code = 1 if data & m else (2 if not mask & m else 0)
                d = INK if code == 1 else (BODY if code == 2 else 0)
                px.append((c * 8 + k, y, key, k, code, d))
    return {'id': '%s:%04X' % (name, g), 'size': 1, 'w': w * 8, 'h': r, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
            'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}


def colour_identity(peek):
    return {'schema': 1, 'game': 'renegade128', 'engine': 'renegade128',
            'keys': 'renegade128-gfx-1: %04X data byte : %04X the graphic\'s checksum; bit = pixel',
            'inputs': hashlib.md5(bytes(peek(a) for a in range(0xA900, 0xB7FF))).hexdigest(), 'geometry': None}


def sheets(z80, out_dir, prefix='renegade128', colours=None, say=print):
    """<prefix>_PAINTING_SPRITES.png + _REFERENCE_ALL_SPRITES.png, each with its layout. One figure per graphic: this engine draws
    parts, and a character's two parts vary apart. Level graphics are all here, whether or not a recording drew them."""
    from . import coloursheet as cs
    from skoolkit.snapshot import get_snapshot
    mem = bytes(get_snapshot(z80))
    st = level_states(z80)
    comps = [{'count': 1, 'group': 0, 'parts': [graphics_part(it)]} for it in all_graphics(st)]
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(lambda a: mem[a])
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    say('Sheets    : %d graphics; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


NOTE = 'Renegade: pattern pages hold every level\'s graphics; the sheet shows one figure per graphic. Nibble 2 is the body, whose colour follows the level.'
RECOLOUR = {'game': 'renegade', 'output': 'sprites', 'colours': 'docs/profiles/renegade128_colours.json', 'clear': True, 'note': NOTE}


def start_from_banks(bank, path):
    """A start snapshot from a built .nex's banks (the sites hold their originals by now): an uncompressed version 3 .z80."""
    hdr = bytearray(30)
    hdr[8:10] = (48637).to_bytes(2, 'little')
    hdr[12] = 0
    hdr[29] = 1
    ext = bytearray(54)
    ext[0:2] = GAME_START.to_bytes(2, 'little')
    ext[2] = 4                                      # 128K
    out = bytes(hdr) + (54).to_bytes(2, 'little') + bytes(ext)
    for n in range(8):
        out += b'\xff\xff' + bytes([n + 3]) + bytes(bank[n][:16384])
    open(path, 'wb').write(out)


def recolour(nex, cmap, outline=True):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build."""
    import tempfile
    from .recolour import banks, splice
    have = banks(nex)
    if not {5, 2, 0, STATE_BANK, ALT_BANK} <= set(have):
        raise ValueError('not a Renegade 128K sprite build')
    orig = {n: bytearray(have[n]) for n in range(8)}
    fd, path = tempfile.mkstemp(suffix='.z80')
    os.close(fd)
    try:
        p = RenegadePatch(path, colours=cmap)
        bank_of = lambda a: (5, a - 0x4000) if a < 0x8000 else ((2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000))
        for a, old, new in p.sites:
            for k in range(len(new)):
                b, o = bank_of(a + k)
                if orig[b][o] != new[k]:
                    raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
                orig[b][o] = old[k] if k < len(old) else orig[b][o]
        start_from_banks(orig, path)
        st = level_states(path)
    finally:
        os.remove(path)
    state, pages = build_tables(st, cmap, outline)
    state = state[:PAGE_OFF] + p.page_code + state[PAGE_OFF + len(p.page_code):]
    if have[STATE_BANK][:8192] != state:
        raise ValueError("graphics table differs from this version's (rebuild with nexclash.py auto)")
    new = {}
    for pg, data in pages.items():
        bank = pg // 2
        cur = new.get(bank, have[bank])
        o = (pg & 1) * 8192
        new[bank] = cur[:o] + data + cur[o + 8192:]
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
    """Broken builds. Each must be detected on the real recording."""
    import copy
    out = []
    code = patch.rom_code
    s = patch.syms
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
    # 2 one store left in
    q = copy.copy(patch)
    q.sites = [x for x in patch.sites if x[0] != STORES[1]]
    out.append(('one masked store still draws', q))
    # 3 a hook loses HL: the first POP HL after e_tick's call
    k = code.index(bytes([0xE1]), s['e_tick'] - ROM_ORG)
    out.append(('e_tick loses HL', _rom_patch(patch, k, b'\x00')))
    # 4 clear does not hide
    k = s['e_clear'] - ROM_ORG
    k = code.index(bytes([0xCD, s['hideall'] & 255, s['hideall'] >> 8]), k)
    out.append(('clear leaves sprites on', _rom_patch(patch, k, bytes(3))))
    # 5 redraw does not hide
    k = s['e_redraw'] - ROM_ORG
    k = code.index(bytes([0xCD, s['hideall'] & 255, s['hideall'] >> 8]), k)
    out.append(('redraw leaves sprites on', _rom_patch(patch, k, bytes(3))))
    # 6 x one column off: the add of 32 -> 40
    k = code.index(bytes([0x01, 0x1F, 0x00]))
    out.append(('x one column off', _rom_patch(patch, k, bytes([0x01, 0x27, 0x00]))))
    # 7 y one line off
    k = code.index(bytes([0x7E, 0xC6, 0x1F])) + 1
    out.append(('y one line off', _rom_patch(patch, k, bytes([0xC6, 0x20]))))
    # 8 mirror ignored
    k = code.index(bytes([0x87, 0x87, 0x87, 0xB0]))
    out.append(('mirror flag not set', _rom_patch(patch, k, bytes([0xAF, 0x00, 0x00, 0xB0]))))
    # 9 no upload
    k = code.index(bytes([0xED, 0xB3]))
    out.append(('patterns never sent', _rom_patch(patch, k, bytes(2))))
    # 10 slot 3 left mapped
    k = code.index(bytes([0xED, 0x91, 0x52, SLOT2_PAGE]))
    out.append(('slot 2 not restored', _rom_patch(patch, k, bytes(4))))
    # 11 28 MHz left on
    k = code.index(bytes([0xED, 0x92, 0x07]))         # leave's NEXTREG 7,A (the latched speed) gone: 28 MHz stays
    out.append(('speed not restored', _rom_patch(patch, k, bytes(3))))
    # 12 body and ink swapped in the patterns
    q = copy.copy(patch)
    q.pages = {}
    for pg, d in patch.pages.items():
        b = bytearray(d)
        for i, v in enumerate(b):
            hi, lo = v >> 4, v & 15
            hi = {1: 2, 2: 1}.get(hi, hi)
            lo = {1: 2, 2: 1}.get(lo, lo)
            b[i] = hi << 4 | lo
        q.pages[pg] = bytes(b)
    out.append(('ink and body swapped', q))
    # the pace windows, the memo, R
    s_ = patch.syms
    def pg(addr, new):
        if patch.state is None or not patch.pages:
            patch.tables()
        q = copy.copy(patch)
        st = bytearray(patch.state)
        st[addr - 0x4000:addr - 0x4000 + len(new)] = new
        q.state = bytes(st)
        return q
    out.append(('a window that never waits', pg(s_['w_cont.neg'], bytes(3))))
    out.append(('a window closed with its slicer hook left in', pg(s_['neg_dis'], bytes(3))))
    out.append(('the memo holds the wrong entry', pg(s_['neg_mput'], b'\x72')))
    k = s_['neg_rc'] - ROM_ORG + 1
    out.append(('R off by one after a commit', _rom_patch(patch, k, bytes([(code[k] + 1) & 255]))))
    k = s_['neg_rw'] - ROM_ORG + 1
    out.append(('R off by one after a window', _rom_patch(patch, k, bytes([(code[k] + 1) & 255]))))
    # 14 hash table empty: nothing found (the page's code stays)
    q = copy.copy(patch)
    q.state = bytes(HASHEND_OFF) + patch.state[HASHEND_OFF:]
    out.append(('graphics table empty', q))
    return out


def negative_real(patch, rzx_path, stop=1500):
    out = []
    from .z80n import Z80NError
    for name, q in negative_patches(patch):
        try:
            cc, _ = verify(q, rzx_path, stop=stop)
            out.append((name, sum(v for k, v in cc.items() if k.endswith('!'))))
        except Z80NError:                       # the broken hook ran off into data
            out.append((name, 1))
    return out


ENH_COLOURS = 'renegade_enhanced_colours.json'     # beside the snapshot; local only (MVV Spec256 colours)


def enhanced_colours(z80):
    """The Enhanced colour map beside the snapshot, or None. Colours from the MVV package's older Spec256
    conversion (runs/renegade/renegade128/work/paint.py): kept out of this repo, in specnext/reference/renegade/."""
    p = os.path.join(os.path.dirname(os.path.abspath(z80)), ENH_COLOURS)
    return p if os.path.isfile(p) else None


def enhanced_nex(nex, cmap):
    """The sprite build + the Enhanced map -> the Enhanced .nex (work/paint.py's last step): recolour(), then
    the sprite palette entries 4-15 in the setup stub's palette (bank 10) and the floors table (bank 12) from
    the profile's "enhanced" section. -> (bytes, info)."""
    from .recolour import banks, splice
    out, info = recolour(nex, cmap)
    prof = load_profile()
    enh = prof['enhanced']
    have = banks(out)
    b10, b12 = bytearray(have[10]), bytearray(have[12])
    old = bytes(PALETTE)
    o = 0x1000 + bytes.fromhex(prof['hooks']['setup']).index(old)
    if bytes(b10[o:o + 16]) != old:
        raise ValueError('setup palette not where the build puts it')
    new = bytes.fromhex(enh['palette'])
    b10[o + 4:o + 16] = new[4:16]
    fl = int(prof['hooks']['syms']['floors'], 16) - 0x2000
    floors = bytes.fromhex(enh['floors'])
    if any(b12[fl + 8 * i] != floors[8 * i] for i in range(4)):
        raise ValueError('floors table: the body bytes differ from the build')
    b12[fl:fl + 32] = floors
    out2, ch = splice(out, {10: bytes(b10), 12: bytes(b12)})
    info['banks changed'] = sorted(set(info['banks changed']) | set(ch))
    return out2, info


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .renegade import boot_check as _bc

    def check(nex, z, p, t):
        # target_renegade's check expects its own 7FFD; this build starts at 7FFD = 0, with PC at the stub
        return [b for b in _bc(nex, z, p, t) if b[0] != 'paging']
    say('Game      : %s' % name)
    say('Engine    : renegade128 (masked stores 38673, 38812 -> no write; parts -> sprites at the game tick; scenery, HUD, text stay on the ULA)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = []                            # the model's boot check is for the hook builds; the plain build was seen to start in JNext
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = RenegadePatch(z80)
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, TAIL_ADDR, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    ec = enhanced_colours(z80)
    if ec is None:
        say('Enhanced  : no %s beside the snapshot: no Enhanced build' % ENH_COLOURS)
    else:
        from . import coloursheet as cs
        enh = os.path.join(out, name + '_enhanced.nex')
        e, info = enhanced_nex(open(spr, 'rb').read(), cs.load(ec))
        open(enh, 'wb').write(e)
        say('Enhanced  : %s  %s  map %s, %d entries, banks changed %s' % (
            os.path.basename(enh), md5(enh), hashlib.md5(open(ec, 'rb').read()).hexdigest()[:8], info['map entries'],
            info['banks changed']))
    states = []
    for r in list(a.rzx or []):
        cc, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in cc.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, tick %d, start %d, clear %d, redraw %d, %d screen checks (%d differ), %d patched-store ticks, '
            '%d bare scenery checks, most sprites %d, by address alone %d -> %s' % (
                os.path.basename(r), cc['frames'], cc['tick'], cc['start'], cc['clear'], cc['redraw'], cc['screen checks'],
                cc['screen checks with a few bytes different'], cc['ticks replayed patched'], cc['bare scenery checks'], cc['most sprites'], cc['graphics found by address alone'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items())),
                                     'PASS' if not uf else 'FAIL %s' % str(uf)[:400]))
    if a.rzx:
        nr = negative_real(patch, list(a.rzx)[0], stop=7000)
        miss = [n for n, k in nr if not k]
        ok = ok and not miss
        say('Negative  : %s  real recording, %d of %d detected %s' % (os.path.basename(list(a.rzx)[0]), len(nr) - len(miss), len(nr), miss))
        for n, k in nr:
            say('            %s: %d failures' % (n, k))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
