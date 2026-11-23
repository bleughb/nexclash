"""Cybernoid (Hewson, 1988, 128K) engine 'cybernoid'. Additive module: reachable only through is_cybernoid().
Facts, design and results: games/cybernoid.md.

Figures are XOR images in three plotters: 32957 small, 41469 big, 42203 tile (figure callers only; other callers are scenery
and stay on the ULA). A plot toggles an image (graphic, y, x), as XOR does. Three painters colour a figure's cells where the
room map is empty; that is the clash: the map keeps scenery's colour, so a figure over scenery takes scenery's. No game logic
reads the figures' pixels or the painted cells. Retained plot loops omit screen writes; the small plot and painter
use equivalent paths with explicit SMC, register, spill and R accounting.
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x2800
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
STATE_PAGE, STATE_BANK = 22, 11
ALT_BANK = 12
PAT_S, PAT_B, PAT_T, PAT_P = 26, 27, 30, 36
EX, EY, GL, GH, ES, C1, C2 = 0x000, 0x100, 0x200, 0x300, 0x400, 0x500, 0x600    # state page offsets
N = 128
N_BIG, N_SHOWN = 24, 104
G_S, G_B, G_T, G_P = 60513, 50937, 54393, 31308
NB, NT = 18, 170
BLANK_B = range(50937, 51129)
BLANK_T = (54393,)
BLANK_S = tuple(range(61089, 61153)) + (61217,)

ENTRY_SITES = {32957: ('f5c5d5', 'e_s'), 41469: ('f5c5d5', 'e_b'), 42054: ('f5c5d5', 'e_a2'), 42107: ('f5c5d5', 'e_a3'),
               42157: ('f5c5d5', 'e_a1'), 31263: ('f5c5e5', 'e_p'), 26282: ('0e0021', 'e_c1'), 26304: ('0e0021', 'e_c2'), 25972: ('af321a', 'e_tick')}
# CALL 42203 sites that draw figures. The other callers (28060, 29979, 30198, 30215, 34811, 38974, 39010) are scenery.
T_FIG = (35425, 35460, 36993, 37043, 37102, 37152, 38755, 38795, 41077, 41223)
T_SCENERY = (28060, 29979, 30198, 30215, 34811, 38974, 39010)
T_ROWS = (42261, 42266, 42280, 42285)
ROWS = (33013, 33018, 33032, 33037, 41579, 41584, 41589, 41604, 41609, 41614, 41784, 41789, 41794, 41809, 41814, 41819,
        42007, 42012, 42017, 42032, 42037, 42042)
SMC_OPS = (41678, 41718, 41881, 41939)                   # the 119 the clipping paths write back into their row writes
SHOT_WRITE, SHOT_PAINT = 31282, 31302           # LD (HL),A ; LD (HL),71
PAINTS = {42081: 0x71, 42088: 0x71, 42095: 0x71, 42135: 0x71, 42142: 0x70, 42184: 0x71, 42191: 0x71}
INTERIORS = tuple(a + k for a in ENTRY_SITES for k in (1, 2))
# Each entry site covers 2 or 3 one- or two-byte instructions: the original runs these as often as the site itself.
SEQUELS = {32958: 32957, 32959: 32957, 41470: 41469, 41471: 41469, 42055: 42054, 42056: 42054, 42108: 42107, 42109: 42107,
           42158: 42157, 42159: 42157, 31264: 31263, 31265: 31263, 26284: 26282, 26306: 26304, 25973: 25972}
TICK = 25972
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
FIXED = [None, None, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'cybernoid_colours.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'cybernoid.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_cybernoid(snap):
    """Machine + the profile's signature bytes. The code at the signature is what the sites depend on."""
    try:
        s = load_profile()['signature']
        b = bytes.fromhex(s['bytes'])
        ram = snap.ram()
        if len(snap.ram(-1)) != 131072:
            return False
        return bytes(ram[s['addr'] - 16384:s['addr'] - 16384 + len(b)]) == b
    except (AttributeError, KeyError, ValueError):
        return False


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def images():
    """(kind, index, graphic address, bytes per row, rows, page, offset, patterns)."""
    out = []
    for i in range(64):
        out.append(('s', i, G_S + i * 16, 2, 8, PAT_S, i * 128, 1))
    for i in range(NB * 4):
        out.append(('b', i, G_B + i * 48, 3, 16, PAT_B + (i >> 5), (i & 31) * 256, 2))
    for i in range(NT):
        out.append(('t', i, G_T + i * 32, 2, 16, PAT_T + (i >> 5), (i & 31) * 256, 2))
    for i in range(4):
        out.append(('p', i, G_P + i, 1, 1, PAT_P, i * 128, 1))
    return out


def nibble(v, k, e):
    n = 1 if (v >> (7 - k)) & 1 else 0
    if e:
        if len(e) > 3 and e[3] & (0x80 >> k):
            return 0
        if e[2][k]:
            return e[2][k]
    return n


def image_pattern(peek, im, cmap=None):
    """128 or 256 bytes. s: 16 x 8 on one pattern. b: 16 + 8 wide. t: 8 + 8 wide, so each column has its own colour."""
    kind, _, g, w, h, _, _, np_ = im
    canvas = [[[0] * 16 for _ in range(16)] for _ in range(np_)]
    for r in range(h):
        for b in range(w):
            a = g + r * w + b
            v = peek(a)
            e = cmap.get('%04X' % a) if cmap else None
            if e and e[0] != v:
                e = None
            if kind == 't':
                pat, col = b, 0
            elif kind == 'p':
                pat, col = 0, 0
            elif kind == 'b' and b == 2:
                pat, col = 1, 0
            else:
                pat, col = 0, b
            for k in range(8):
                canvas[pat][r][col * 8 + k] = nibble(v, k, e)
    out = bytearray()
    for pat in canvas:
        for row in pat:
            for k in range(0, 16, 2):
                out.append(row[k] << 4 | row[k + 1])
    return bytes(out)


def blank_images(peek):
    """Addresses whose image draws nothing: must be what blankq in the hooks says."""
    out = set()
    for im in images():
        if not any(peek(im[2] + k) for k in range(im[3] * im[4])):
            out.add(im[2])
    return out


def is_blank(g):
    return 50937 <= g < 51129 or g in BLANK_T or g in BLANK_S


def build_tables(peek, cmap=None, code=None):
    """-> (state page 8K, {page: 8K bytes}). The layout does not depend on the map: recolour changes pattern pages only."""
    state = bytearray(8192)
    state[0xb00:0xe00] = bytes([255])*0x300
    state[0x1000:0x1300] = bytes([255])*0x300
    state[C1:C1 + N] = bytes([0xF0]) * N
    state[C2:C2 + N] = bytes([0xF0]) * N
    if code:
        state[0x800:0x800 + len(code)] = code
    pages = {}
    for im in images():
        d = image_pattern(peek, im, cmap)
        pg = pages.setdefault(im[5], bytearray(8192))
        pg[im[6]:im[6] + len(d)] = d
    return bytes(state), {k: bytes(v) for k, v in pages.items()}


class PlainPatch:
    """The plain .nex: no hooks. The snapshot stops at the IM 2 vector with the title up, so it needs no start stub."""
    name = 'Cybernoid plain conversion'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    extra_banks = {}
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def apply(self, snap):
        pass


class CybernoidPatch:
    name = 'Cybernoid: figures -> hardware sprites (altrom hooks, state and patterns in Next pages at slots 5-6)'

    def __init__(self, prof=None, rom_code=None, colours=None):
        self.prof = prof or load_profile()
        self.colours = {} if colours is None else colours
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.st_code = bytes.fromhex(h['st'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)
        from .build import rom48
        from skoolkit import ROM128
        rom = open(ROM128[1], "rb").read()
        # The 128K game executes no ROM code in 2800..rom_end; checked by recordings.
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.altrom_low = (ALT_PAGE + 1, rom[:8192])
        self.sites = []
        for a, (old, sym) in ENTRY_SITES.items():
            self.sites.append((a, bytes.fromhex(old), bytes([0xC3]) + self.syms[sym].to_bytes(2, 'little')))
        for c in T_FIG:
            self.sites.append((c + 1, (42203).to_bytes(2, 'little'), self.syms['e_t'].to_bytes(2, 'little')))
        for a in ROWS + SMC_OPS + (SHOT_WRITE,):
            self.sites.append((a, b'\x77', b'\x00'))
        self.sites.append((SHOT_PAINT, b'\x36\x47', b'\x3e\x47'))
        for a, v in PAINTS.items():
            self.sites.append((a, bytes([v]), b'\x00'))
        for a, old, label in [(0x70d3, 'f5c5d5', 'irq_in'), (0x7117, 'fbed4d', 'irq_out')]:
            self.sites.append((a, bytes.fromhex(old), b'\xc3' + self.syms[label].to_bytes(2, 'little')))
        self.extra_banks = {}
        self.state = None
        self.pages = None
        self.num_patterns = 128

    def tables(self, peek):
        bl = blank_images(peek)
        want = {g for g in bl if not is_blank(g)} | {im[2] for im in images() if is_blank(im[2]) and im[2] not in bl}
        if want:
            raise ValueError('the hooks\' blank images differ from this snapshot: %s' % sorted(want)[:5])
        self.state, self.pages = build_tables(peek, self.colours, self.st_code)
        timing = self.prof['timing']
        state = bytearray(self.state)
        state[0x900:0xa00] = bytes(timing['big_classes'])
        from .hooklib import lines16
        targets = b''.join(lines16(t, 228).to_bytes(2, 'little') for row in timing['big_table'] for t in row)
        state[0xa00:0xa00+len(targets)] = targets
        self.state = bytes(state)

    def apply(self, snap):
        if snap.is128 and snap.port7ffd & 7:
            raise ValueError('Cybernoid 128K entry must have bank 0 paged at C000')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        peek = lambda a: ram[a - 0x4000]
        for c in T_FIG:             # the tile sites rewrite a CALL's operand: CALL / CALL cc 42203, never a JP (no return)
            op = ram[c - 0x4000]
            if not (op == 0xCD or op & 0xC7 == 0xC4):
                raise ValueError('unexpected code at %d (%02x, expected a CALL 42203)' % (c, op))
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
        self.extra_banks = {STATE_BANK: self.state + bytes(8192), ALT_BANK: self.page + self.altrom_low[1]}
        for pg, data in self.pages.items():
            bank = pg // 2
            cur = self.extra_banks.get(bank, bytes(16384))
            o = (pg & 1) * 8192
            self.extra_banks[bank] = cur[:o] + data + cur[o + 8192:]


# ---------------------------------------------------------------------------------------------
# Next-side state
# ---------------------------------------------------------------------------------------------

def entry_sprites(i):
    if i < N_BIG:
        return (2 * i, 2 * i + 1)
    return (i + N_BIG,) if i < N_SHOWN else ()


class NextState:
    def __init__(self, patch):
        self.patch = patch
        self.nr = {0x55: 5, 0x56: 0, 0x07: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat[24*256:56*256] = patch.pages[26]
        self.pat[56*256:58*256] = patch.pages[36][:512]
        self.patptr = 0
        self.state = bytearray(patch.state)
        self.events = []
        self.dirty = True
        self.cache = {}

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
        q.dirty = True
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
            self.patptr += 1
            self.cache.clear()
        else:
            self.events.append(('out', port, val))

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
        x = a[0] + (a[2] & 1) * 256
        y = a[1] + (a[4] & 1) * 256
        return (x - 32, y - 32, rows)

    def entry_pixels(self, i):
        """Pixels the entry's sprites show in the play area."""
        out = set()
        for s in entry_sprites(i):
            r = self.sprite_rows(s)
            if r:
                x, y, rows = r
                for j, v in enumerate(rows):
                    if v and 32 <= y + j < 192:
                        for k in range(16):
                            if v & (0x8000 >> k) and 0 <= x + k < 256:
                                out.add((x + k, y + j))
        return out

    def on_entries(self):
        st = self.state
        return {i: (st[GL + i] | st[GH + i] << 8, st[EY + i], st[EX + i]) for i in range(N) if st[ES + i] == 2}


# ---------------------------------------------------------------------------------------------
# One hook event: original and patched from one state
# ---------------------------------------------------------------------------------------------

TSTAT = collections.Counter()      # T-states as if all at one speed; the hooks run at 28 MHz (about 6x, LEARNINGS 2.1f)
CMP = list(range(0, 25)) + [26, 27]   # all but R, T, MEMPTR
_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[:0x2000] = patch.altrom_low[1]
    alt[0x2000:0x4000] = patch.page
    return alt


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
    """The patched build: patch sites, alt ROM, Next pages at slots 5 and 6."""

    def __init__(s, get, alt, psite, ns):
        _O.__init__(s, get)
        s.alt, s.psite, s.ns, s.romw, s.pagew = alt, psite, ns, 0, 0

    def __getitem__(s, a):
        if a < 0x4000:
            return s.alt[a]
        if 0xA000 <= a < 0xE000:
            nr = s.ns.nr
            if a >= 0xC000:
                if nr[0x56] != 0:
                    return s.ns.page_byte(nr[0x56], a - 0xC000)
            elif nr[0x55] != 5:
                return s.ns.page_byte(nr[0x55], a - 0xA000)
        v = s.ov.get(a)
        if v is not None:
            return v
        v = s.psite.get(a)
        return s.get(a) if v is None else v

    def __setitem__(s, a, v):
        if a < 0x4000:
            s.romw += 1
            return
        if 0xA000 <= a < 0xE000:
            nr = s.ns.nr
            if a >= 0xC000:
                if nr[0x56] != 0:
                    if nr[0x56] == STATE_PAGE:
                        s.ns.state[a - 0xC000] = v
                    else:
                        s.pagew += 1
                    return
            elif nr[0x55] != 5:
                s.pagew += 1
                return
        s.ov[a] = v


def _machine(Sim, mem, regs, ns, slot):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot)

    from .hooklib import NextModel
    clock = NextModel(sim, speed=getattr(ns, 'nr', {}).get(7, 0), t_line=228, lines=311)
    clock.nr.update(getattr(ns, 'nr', {}))
    class Tr:
        def read_port(self, regs_, port):
            if port == 0x243B:
                return clock.sel
            if port == 0x253B:
                return clock.read_port(regs_, port)
            ns.events.append(('in', port))
            return 0xFF
        def write_port(self, regs_, port, value, *x):
            if port in (0x243B, 0x253B):
                clock.write_port(regs_, port, value)
            else:
                ns.out(port, value)
    def nr(reg, value):
        clock.nextreg(reg, value)
        ns.nextreg(reg, value)
    sim.set_tracer(Tr())
    z80n.install(sim, nr)
    sim.hook_clock = clock
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


def _pv(p, a, get):
    v = p.ov.get(a)
    return get(a) if v is None else v


class _NullNs:
    def __init__(self):
        self.events = []

    def out(self, port, value):
        pass

    def nextreg(self, reg, val):
        pass


class Model:
    """What the sprites should be, by the rules of the XOR plots and the painters, written apart from the hooks."""

    def __init__(self):
        self.on = {}            # (graphic, y, x) -> (colour left, colour right); colour None: not painted yet
        self.pixels = {}        # (graphic, y, x) -> its pixels, when the plot was checked
        self.last = None
        self.pend = None

    def toggle(self, key):
        """-> True if the image is now on."""
        if key in self.on:
            del self.on[key]
            self.last = None
            return False
        c = (None, None)
        if self.pend:
            if self.pend[0] == key[2] and self.pend[1] == key[1]:
                c = self.pend[2:]
            self.pend = None
        self.on[key] = c
        self.last = key
        return True

    def paint(self, x, y, c1, c2):
        hit = [k for k in self.on if k[1] == y and k[2] == x]
        for k in hit:
            self.on[k] = (c1, c2)
        if not hit:
            if self.last in self.on:
                self.on[self.last] = (c1, c2)
            else:
                self.pend = (x, y, c1, c2)
        self.last = None

    def clear(self):
        self.on.clear()
        self.pixels.clear()
        self.last = self.pend = None


def palof(attr):
    return ((attr & 7) | (8 if attr & 0x40 else 0)) << 4


def plot_keys(kind, R):
    """The images a plot toggles, in the hook's order, blank ones left out."""
    A, B, C, D, E, H, L = R[0], R[2], R[3], R[4], R[5], R[6], R[7]
    keys = []
    if kind == 'p':
        return [(G_P + (E & 3), D, E)]
    if kind == 's':
        g = G_S + ((A & 15) * 4 + (E & 3)) * 16
        if not is_blank(g):
            keys.append((g, D, E))
        return keys
    old = H << 8 | L
    if not is_blank(old):
        keys.append((old, B, C))
    if kind == 'b':
        if A < NB:
            g = G_B + (A * 4 + (E & 3)) * 48
            if not is_blank(g):
                keys.append((g, D, E))
    elif A < NT:
        g = G_T + A * 32
        if not is_blank(g):
            keys.append((g, D, E))
    return keys


def image_pixels(get, key):
    """The play-area pixels of an image with no sprite (past the 128): from the graphic, for the screen check."""
    g, y, x = key
    im = next(i for i in images() if i[2] == g)
    w, h = im[3], im[4]
    out = set()
    X = (x & 0x7C) * 2 - (256 * 2 if x >= 128 else 0)
    for r in range(h):
        for b in range(w):
            v = get(g + r * w + b)
            for k in range(8):
                if v >> (7 - k) & 1 and 0 <= X + b * 8 + k < 256 and 32 <= y + r < 192:
                    out.add((X + b * 8 + k, y + r))
    return out


def event(patch, kind, get, R, ns, model, alt, psite, Sim):
    """Run one hook event from the same state. kind: s, b, t (plots), a1, a2, a3 (painters), c (clears), k (tick).
    Returns (failures, pixels compared)."""
    sp0 = R[12]
    incoming_speed = ns.nr[7]
    ret = get(sp0) | get(sp0 + 1) << 8
    f = []
    o = _O(get)
    so = _machine(Sim, o, list(R), _NullNs(), 'o')
    ns.events = []
    p = _P(get, alt, psite, ns)
    Rp = list(R)
    if kind == 't':
        Rp[24] = patch.syms['e_t']
    sp_ = _machine(Sim, p, Rp, ns, 'p')
    low = [sp0]
    ivals = (R[8], R[9], R[10], R[11], R[14], R[26])

    def watch(r):
        if (sp0 - r[12]) & 0xFFFF < 0x8000 and (sp0 - r[12]) & 0xFFFF > (sp0 - low[0]) & 0xFFFF:
            low[0] = r[12]
        if (r[8], r[9], r[10], r[11], r[14], r[26]) != ivals:
            low.append('IX, IY, I or IFF changed in a hook')

    if kind in ('c', 'k'):
        back = {'c': (26287 if R[24] == 26282 else 26309), 'k': 25976}[kind]

        def stop(r):
            return r[24] == back
    else:
        def stop(r):
            return r[24] == ret and r[12] == (sp0 + 2) & 0xFFFF

    if not _run(so, stop, limit=20000):
        return ['original did not return'], 0
    try:
        if not _run(sp_, stop, watch):
            return ['patched did not return'], 0
    except Exception as e:
        return ['patched code raised %s' % str(e)[:80]], 0
    ro, rp = so.registers, sp_.registers
    TSTAT['original T'] += ro[25] - R[25]
    TSTAT['patched T'] += rp[25] - Rp[25]
    diff = [k for k in CMP if ro[k] != rp[k]]
    if diff:
        f.append(('registers differ', diff, [ro[k] for k in diff], [rp[k] for k in diff]))
    if p.romw or p.pagew:
        f.append(('patched code wrote ROM or a pattern page', p.romw, p.pagew))
    if len(low) > 1:
        f.append((low[1],))
    if (sp0 - low[0]) & 0xFFFF > 64:
        f.append(('hook stack too deep', (sp0 - low[0]) & 0xFFFF))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access other than the sprite ports', [e for e in ns.events if e[0] in ('in', 'out')][:3]))
    if ns.nr[0x55] != 5 or ns.nr[0x56] != 0 or ns.nr[0x07] != incoming_speed:
        f.append(('slots or speed not restored', ns.nr[0x55], ns.nr[0x56], ns.nr[0x07]))
    regs_ok = {0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x55, 0x56}
    if any(e[1] not in regs_ok for e in ns.events):
        f.append(('NEXTREG outside the hook set',))
    keys = set(o.ov) | set(p.ov)
    ignore = set(T_ROWS) | {s[0] + k for s in patch.sites for k in range(len(s[2]))}
    md = [a for a in keys if not 0x4000 <= a < 0x5B00 and not 0 < (ro[12] - a) & 0xFFFF <= 64 and a not in ignore
          and o[a] != _pv(p, a, get)]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4], [(o[a], _pv(p, a, get)) for a in sorted(md)[:4]]))
    if any(p.ov.get(a, get(a)) != get(a) for a in T_ROWS):
        f.append(('tile row writes not restored',))
    if kind in ('c', 'k'):
        sd = [a for a in keys if 0x4000 <= a < 0x5B00 and o.ov.get(a) != p.ov.get(a)]
        if sd:
            f.append(('screen writes differ', len(sd)))
        if kind == 'c':
            model.clear()
            if ns.on_entries() or any(a[3] & 0x80 for a in ns.attr):
                f.append(('sprite left on after a clear',))
        elif any(ns.attr[s][3] & 0x80 for i in range(N) if ns.state[ES + i] == 0 for s in entry_sprites(i)):
            f.append(('sprite of a free entry left on after the tick',))
        return f, 0
    if any(0x4000 <= a < 0x5B00 for a in p.ov):
        f.append(('patched code wrote the screen', sorted(a for a in p.ov if 0x4000 <= a < 0x5B00)[:3]))
    npx = 0
    if kind in ('s', 'b', 't', 'p'):
        want = _screen_xor(o.ov, get)
        if kind in ('s', 't') and R[5] & 0x7C == 0x7C:
            # A figure at the last column: the original's second byte wraps to column 0, 8 lines down. A sprite does not.
            drop = {q for q in want if q[0] < 8}
            TSTAT['last-column wrap pixels not shown'] += len(drop)
            want -= drop
        got = set()
        px = model.pixels
        ks = plot_keys(kind, R)
        if kind == 'p':
            model.pend = (R[5], R[4], 0xF0, 0xF0)
        for key in ks:
            if model.toggle(key):
                px[key] = None
            else:
                got ^= px.pop(key, None) or set()
        have = ns.on_entries()
        inv = {v: i for i, v in have.items()}
        for key in set(ks):
            if key in model.on:
                if key in inv:
                    if px.get(key) is None:
                        px[key] = ns.entry_pixels(inv[key]) if inv[key] < N_SHOWN else image_pixels(get, key)
                    got ^= px[key]
                else:
                    f.append(('an image on in the model has no entry', key))
        if kind == 'p':
            model.pend = model.last = None
        npx = len(want)
        if got != want:
            f.append(('sprite change differs from the original XOR', len(got ^ want), sorted(got ^ want)[:3], ks))
    else:
        c1, c2 = R[3], R[3] if kind != 'a3' else R[2]
        model.paint(R[5], R[4], palof(c1), palof(c2))
        have = ns.on_entries()
        inv = {v: i for i, v in have.items()}
    if ns.state[0x711]:
        f.append(('the image table was full',))
    if set(have.values()) != set(model.on):
        f.append(('images differ from the model', sorted(set(have.values()) ^ set(model.on))[:3]))
    for key, c in model.on.items():
        if c[0] is not None and key in inv:
            i = inv[key]
            if (ns.state[C1 + i], ns.state[C2 + i]) != c:
                f.append(('colour is not the painted one', key, ns.state[C1 + i], ns.state[C2 + i], c))
                break
            for s_, want_ in zip(entry_sprites(i), c):
                if ns.attr[s_][3] & 0x80 and ns.attr[s_][2] & 0xF0 != want_:
                    f.append(('sprite palette is not the painted one', key, ns.attr[s_][2], c))
                    break
    return f, npx


# ---------------------------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------------------------

SITE_KIND = {32957: 's', 41469: 'b', 31263: 'p', 42054: 'a2', 42107: 'a3', 42157: 'a1', 26282: 'c', 26304: 'c', TICK: 'k'}
ALL_KINDS = ('s', 'b', 't', 'p', 'a1', 'a2', 'a3', 'c', 'k')
WATCH_PAINT = 26541         # the room map is copied from the attributes: figures must not have painted any cell by then
TILE_OVER = 42312           # the tile overwrite plotter


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shot=None):
    """Replay the original (C simulator); at every hook site run original and patched from the same state and compare.
    Each tick: screen XOR all images = the scenery, changed only where a scenery routine worked.
    -> (Counter, examples[, states])."""
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    Sim = _rw()
    ns = None
    model = Model()
    model.pixels = {}
    states = []
    st = {'frame': 0, 'base': None, 'rects': []}
    psite = {}
    painted = {}
    hits = collections.Counter()
    pcs = set(SITE_KIND) | set(INTERIORS) | {42203, WATCH_PAINT, TILE_OVER}

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    def on_pc(pc, sim):
        nonlocal ns
        R, M = sim.registers, sim.memory
        if ns is None:
            peek = M.__getitem__
            patch.tables(peek)
            for a, old, new in patch.sites:
                for k, v in enumerate(new):
                    psite[a + k] = v
            ns = NextState(patch)
        if pc in INTERIORS:
            hits[pc] += 1
            return
        hits[pc] += 1
        get = M.__getitem__
        if pc == WATCH_PAINT:
            c['room maps copied'] += 1
            if any(M[a] != v for a, v in painted.items()):
                fail('the room map copied cells figures had painted', (len(painted),))
            return
        if pc == TILE_OVER:
            st['rects'].append((R[4], R[5]))
            return
        if pc == 42203:
            ret = M[R[12]] | M[R[12] + 1] << 8
            if ret - 3 in T_SCENERY:
                c['tile: scenery caller %d' % (ret - 3)] += 1
                st['rects'].append((R[4], R[5]))
                st['rects'].append((R[2], R[3]))
                return
            if ret - 3 not in T_FIG:
                fail('tile plotter from an unknown caller', (ret,))
                return
            kind = 't'
            c['tile: figure caller %d' % (ret - 3)] += 1
        else:
            kind = SITE_KIND[pc]
        if kind == 'c':
            st['base'] = None
            st['rects'] = []
            painted.clear()
        if kind in ('a1', 'a2', 'a3'):
            ly, lx = R[4], R[5] if R[5] < 128 else 0
            for r in range(3 if kind == 'a2' else 2):
                for k in range(3 if kind == 'a2' else 2):
                    a = 0x5800 + (((ly >> 3) + r) * 32 & 0x3FF) + ((lx >> 2) + k)
                    if a < 0x5B00:
                        painted.setdefault(a, M[a])
        if collect and c['collected ' + kind] < collect:
            c['collected ' + kind] += 1
            states.append((kind, list(R), bytes(M[a] for a in range(65536)), ns.copy(), dict(model.on), dict(model.pixels), model.last, model.pend))
        fl, npx = event(patch, kind, get, list(R), ns, model, alt, psite, Sim)
        c[kind] += 1
        c['sprite pixels compared'] += npx
        vis = sum(1 for s in range(128) if ns.attr[s][3] & 0x80)
        if vis > c['most sprites']:
            c['most sprites'] = vis
        n = len(model.on)
        if n > c['most images']:
            c['most images'] = n
        if ns.state[0x711] > c['table full']:
            c['table full'] = ns.state[0x711]
        for k in fl:
            fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())
        if kind == 'k':
            c['ticks'] += 1
            check_screen(M)

    def check_screen(M):
        cur = bytearray(M[a] for a in range(0x4000,0x5800))
        for key, pix in model.pixels.items():
            if pix:
                for x, y in pix:
                    a = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
                    cur[a] ^= 0x80 >> (x & 7)
        if st['base'] is None:
            st['base'] = cur
            st['rects'] = []
            c['scenery baselines'] += 1
            return
        c['screen checks'] += 1
        base = st['base']
        if cur != base:
            rects = st['rects']
            for a in range(6144):
                if cur[a] != base[a]:
                    y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
                    if y < 32:
                        continue                    # the panel
                    x = (a & 31) * 8
                    # a tile at the last column wraps to the next character row, as INC L does
                    if not any((ry <= y < ry + 16 and (rx & 0x7C) * 2 <= x < (rx & 0x7C) * 2 + 16)
                               or ((rx & 0x7C) == 0x7C and x == 0 and ry + 8 <= y < ry + 24) for ry, rx in rects):
                        c['screen bytes changed with no scenery routine'] += 1
                        if len(ex['screen bytes']) < 6:
                            ex['screen bytes'].append((st['frame'], 0x4000 + a, cur[a], base[a]))
            st['base'] = cur
        st['rects'] = []
        if shot:
            shot(st['frame'], M, ns, model)

    def wrapped(pc, sim):
        st['frame'] = c['ticks']
        on_pc(pc, sim)

    fc, err = RZ.trace(rzx_path, pcs, wrapped, stop=stop)
    if err:
        c['replay stopped: %s!' % err] += 1
    for a in INTERIORS:
        # the replay may stop between an entry and its next instruction: one short is not a jump in
        if hits[a] > hits[SEQUELS[a]] if a in SEQUELS else hits[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    c['frames'] = fc
    c['hooks never run'] = sum(1 for k in ALL_KINDS if not c[k])
    if progress:
        progress(fc, c)
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests: every image at the screen's edges, every colour, guards, the negative controls
# ---------------------------------------------------------------------------------------------

def _restore(state, q=None):
    kind, R, mem, ns, on, pix, last, pend = state
    n2 = ns.copy()
    if q is not None:
        n2.patch = q
    m = Model()
    m.on, m.pixels, m.last, m.pend = dict(on), dict(pix), last, pend
    return kind, list(R), bytearray(mem), n2, m


def unit_tests(patch, states, neg=None):
    """states from verify(collect=n). neg: list of (name, broken patch)."""
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    def one(kind, R, mem, ns, m, pt=patch, a=None, ps=None):
        return event(pt, kind, mem.__getitem__, R, ns, m, a or alt, ps or psite, Sim)

    def clean(ns, m):
        ns.state[ES:ES + N] = bytes(N)
        ns.state[0x702] = ns.state[0x703] = 0       # LAST, PV
        for s in range(128):
            ns.attr[s][3] = 0
        m.on.clear()
        m.pixels.clear()
        m.last = m.pend = None

    by = collections.defaultdict(list)
    for s in states:
        by[s[0]].append(s)
    # every image of each plotter, at the screen's edges and the 2-pixel steps, from a clean table: pixels, registers, memory
    for kind, frames, xs in (('s', range(16), (0, 1, 2, 3, 40, 119)),
                             ('b', range(NB), (0, 1, 2, 3, 60, 120, 121, 123, 124, 127, 128, 169, 170, 247, 248, 251, 252, 255)),
                             ('t', list(range(NT)), (0, 40, 120))):
        if not by[kind]:
            continue
        for f in frames:
            for x in xs:
                for y in (40, 176):
                    k, R, mem, ns, m = _restore(by[kind][0])
                    clean(ns, m)
                    R[0], R[4], R[5] = f, y, x
                    if kind != 's':
                        R[2], R[3], R[6], R[7] = y, x, G_B >> 8, G_B & 255     # blank old image
                    fl, npx = one(kind, R, mem, ns, m)
                    c['%s image x position cases %s' % (kind, 'ok' if not fl else 'FAIL!')] += 1
                    if fl and c['  fail example'] < 3:
                        c['  fail example'] += 1
                        c['  %s frame %d x %d y %d %s' % (kind, f, x, y, str(fl[:2])[:200])] += 1
    # every colour, bright or not, on an image showing; then the paint before the plot; then one at another position
    for kind in ('a1', 'a2', 'a3'):
        if not by[kind]:
            continue
        for col in range(8):
            for br in (0, 0x40):
                k, R, mem, ns, m = _restore(by[kind][0])
                R[3] = col | br
                R[2] = (7 - col) | br if kind == 'a3' else R[2]
                fl, _ = one(kind, R, mem, ns, m)
                c['colour cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    if by['s'] and by['a1']:
        k, R, mem, ns, m = _restore(by['a1'][0])
        clean(ns, m)
        R[3], R[4], R[5] = 0x45, 100, 40
        fl, _ = one('a1', R, mem, ns, m)
        k2, R2, _, _, _ = _restore(by['s'][0])
        R2[0], R2[4], R2[5] = 4, 100, 40
        fl2, _ = one('s', R2, mem, ns, m)
        i = next(iter(ns.on_entries()), None)
        ok = not fl and not fl2 and i is not None and ns.state[C1 + i] == palof(0x45)
        c['paint before plot %s' % ('ok' if ok else 'FAIL!')] += 1
        if not ok:
            c['  paint before plot: %s %s %s' % (str(fl)[:150], str(fl2)[:150], i)] += 1
    # the table full: the 65th image shows nothing and breaks nothing
    if by['s']:
        k, R, mem, ns, m = _restore(by['s'][0])
        clean(ns, m)
        for i in range(N):
            ns.state[ES + i] = 2
            ns.state[EX + i] = 200
            ns.state[EY + i] = i
            ns.state[GL + i] = 0x61
            ns.state[GH + i] = 0xEC
        before = [list(a) for a in ns.attr]
        R[0], R[4], R[5] = 4, 100, 40
        m.on = {}
        fl, _ = one('s', R, mem, ns, m)
        rest = [x for x in fl if not str(x[0]).startswith(('images differ', 'sprite change', 'the image table', 'an image on'))]
        ok = not rest and ns.state[0x711] == 1 and [list(a) for a in ns.attr] == before
        c['table full %s' % ('ok' if ok else 'FAIL!')] += 1
        # past the sprites: image 105 of the small pool keeps the XOR count, shows nothing
        k, R, mem, ns, m = _restore(by['s'][0])
        clean(ns, m)
        for i in range(N_BIG, N_SHOWN):
            ns.state[ES + i] = 2
            ns.state[EX + i] = 200
            ns.state[EY + i] = i
            ns.state[GL + i] = 0x61
            ns.state[GH + i] = 0xEC
            m.on[(0xEC61, i, 200)] = (None, None)
        R[0], R[4], R[5] = 4, 100, 40
        fl, _ = one('s', R, mem, ns, m)
        ok = not fl and any(ns.state[ES + i] == 2 for i in range(N_SHOWN, N)) and not any(ns.attr[s][3] & 0x80 for s in range(128))
        c['past the sprites %s' % ('ok' if ok else 'FAIL!')] += 1
    # a clear with images showing
    if by['c'] and by['s']:
        k, R, mem, ns, m = _restore(by['s'][0])
        clean(ns, m)
        R[0], R[4], R[5] = 4, 100, 40
        one('s', R, mem, ns, m)
        k, R, mem2, _, _ = _restore(by['c'][0])
        fl, _ = one('c', R, mem2, ns, m)
        c['clear with images %s' % ('ok' if not fl else 'FAIL!')] += 1
    for name, q in (neg or []):
        if getattr(q, 'real_only', False):
            continue
        hit = False
        qa = _alt(q)
        qs = {a + k: v for a, old, new in q.sites for k, v in enumerate(new)}
        for s in states:
            k, R, mem, ns, m = _restore(s, q)
            ns.state[0x800:0x800+len(q.st_code)] = q.st_code
            ns.pat[24*256:56*256] = q.pages[26]
            ns.pat[56*256:58*256] = q.pages[36][:512]
            fl, _ = one(k, R, mem, ns, m, q, qa, qs)
            if fl:
                hit = True
                break
        c['negative %s: %s' % (name, 'detected' if hit else 'NOT DETECTED!')] += 1
    return c


# ---------------------------------------------------------------------------------------------
# Colour route (docs/COLOURS.md): recolour rewrites pattern pages only; the game never reads them
# ---------------------------------------------------------------------------------------------

NOTE = ('Cybernoid colour map (docs/COLOURS.md): key = graphics byte (hex address; check = its value); 8 nibbles, 0 = default '
        "(the figure's own ink at run time); 2-15 fixed colours; a paper bit with a nibble is drawn opaque; optional 4th = "
        'transparent mask. Each preshift of a figure has its own bytes')
RECOLOUR = {'game': 'cybernoid', 'output': 'sprites', 'colours': 'docs/profiles/cybernoid_colours.json', 'clear': True, 'note': NOTE}
# Sheet palette. Entry 1 is the run-time colour, shown as a pink the game never uses.
PALETTE = [0x00, 0xE2] + FIXED[2:]


def graphics_bytes():
    seen = set()
    for im in images():
        seen.update(range(im[2], im[2] + im[3] * im[4]))
    return sorted(seen)


def colour_identity(peek):
    return {'schema': 1, 'game': 'cybernoid', 'engine': 'cybernoid', 'keys': 'cybernoid-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': hashlib.md5(bytes(peek(a) for a in graphics_bytes())).hexdigest(), 'geometry': None}


def _orig_byte(peek, a):
    return peek(a)


def recolour(nex, cmap):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build."""
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    if not {5, 2, 0, STATE_BANK, ALT_BANK} <= set(have):
        raise ValueError('not a Cybernoid sprite build')
    peek = nex_peek(nex)
    p = CybernoidPatch(colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    if have[ALT_BANK] != p.page + p.altrom_low[1]:
        raise ValueError("alt ROM image / hook code differs from this version's (rebuild with nexclash.py auto)")
    p.tables(peek)
    state, pages = p.state, p.pages
    if have[STATE_BANK][:8192] != state:
        raise ValueError("state page differs from this version's (rebuild with nexclash.py auto)")
    new = {}
    for pg, data in pages.items():
        bank = pg // 2
        cur = new.get(bank, have[bank])
        o = (pg & 1) * 8192
        new[bank] = cur[:o] + data + cur[o + 8192:]
    out, changed = splice(nex, new)
    used = [k for k in cmap if cmap[k][0] == peek(int(k, 16))]
    return out, {'banks changed': changed, 'map entries used': len(used), 'map entries ignored': len(cmap) - len(used)}


def image_part(peek, im):
    kind, idx, g, w, h = im[:5]
    px, ent = [], {}
    for r in range(h):
        for b in range(w):
            a = g + r * w + b
            v = peek(a)
            key = '%04X' % a
            ent[key] = [v, 'g']
            for k in range(8):
                ink = (v >> (7 - k)) & 1
                px.append((b * 8 + k, r, key, k, 1 if ink else 0, 15 if ink else 0))
    return {'id': '%s%d' % (kind, idx), 'size': 1, 'w': w * 8, 'h': h, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
            'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': kind}


def sheets(z80, out_dir, prefix='cybernoid', colours=None, say=print, tiles=None):
    """<prefix>_PAINTING_SPRITES.png + _REFERENCE_ALL_SPRITES.png, with _layout.json. One figure per image that draws anything;
    tiles only those figure callers use (tiles = indices), as the rest are scenery. Default colour shown white, as it follows
    the figure."""
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    comps = []
    for im in images():
        if is_blank(im[2]) or (im[0] == 't' and tiles is not None and im[1] not in tiles):
            continue
        comps.append({'count': 1, 'group': im[0], 'parts': [image_part(get, im)]})
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    say('Sheets    : %d images; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


# ---------------------------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------------------------

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


class _Fixed:
    """A patch whose tables stay as built: verify's patch.tables() must not put the good ones back."""

    def tables(self, peek):
        pass


def negative_patches(patch, peek=None):
    """Broken builds. Each must be detected on the real recording, or on the captured states."""
    import copy
    out = []
    s = patch.syms
    code = patch.rom_code

    def frozen(q):
        q.tables = lambda peek_: None
        return q
    if patch.pages is not None:
        # 1 patterns one pixel to the right
        q = frozen(copy.copy(patch))
        q.pages = {}
        for pg, d in patch.pages.items():
            b = bytearray(len(d))
            for r in range(len(d) // 8):
                row = int.from_bytes(d[8 * r:8 * r + 8], 'big')
                b[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
            q.pages[pg] = bytes(b)
        out.append(('patterns shifted one pixel', q))
    # The small bitmap loop is retired entirely; its SMC side effects still matter.
    k = code.index(b'\x32\xef\x80', s['e_s'] - ROM_ORG)
    out.append(('small preshift operand lost', _rom_patch(patch, ROM_ORG + k, bytes(3))))
    # One row write left in the big plotter.
    for a, nm in ((41589, 'big'),):
        q = copy.copy(patch)
        q.sites = [x for x in patch.sites if x[0] != a]
        out.append(('a %s row write still draws' % nm, q))
    # 3 one paint left in
    q = copy.copy(patch)
    q.sites = [x for x in patch.sites if x[0] != 42081]
    out.append(('a cell paint still writes', q))
    # 4 the big plotter's hook does not restore HL
    e = s['e_b'] - ROM_ORG
    k = code.index(bytes([0xE1, 0xD1, 0xC1, 0xF1]), e)
    out.append(('e_b loses HL', _rom_patch(patch, ROM_ORG + k, b'\x00')))
    # 5 a clear does not hide
    h = s['hide'] - ROM_ORG
    k = code.index(bytes([0xCD]) + s['hide'].to_bytes(2, 'little'), s['e_c2'] - ROM_ORG)
    out.append(('clear leaves sprites on', _rom_patch(patch, ROM_ORG + k, bytes(3))))
    # 5b a shot's write left in
    q = copy.copy(patch)
    q.sites = [x for x in patch.sites if x[0] != SHOT_WRITE]
    out.append(('a shot still draws', q))
    # 6 the tick does not hide
    k = code.index(bytes([0xCD]) + s['hide'].to_bytes(2, 'little'), s['e_tick'] - ROM_ORG)
    out.append(('tick leaves sprites on', _rom_patch(patch, ROM_ORG + k, bytes(3))))
    # 7 the old image is not toggled in the big plotter: call oldimg removed
    k = code.index(b'\xcd' + s['oldimg'].to_bytes(2, 'little'), s['e_b'] - ROM_ORG)
    out.append(('big plotter ignores the old image', _rom_patch(patch, ROM_ORG + k, bytes(3))))
    # 8 colour ignored: palb returns 0
    q = copy.copy(patch)
    k = patch.st_code.index(bytes([0xCB, 0x75]))
    q.st_code = patch.st_code[:k] + bytes(2) + patch.st_code[k + 2:]
    out.append(('bright ignored', q))
    # 9 x off: add a,32 in show -> 33
    k = code.index(bytes([0x3E, 0x20]), s['show'] - ROM_ORG)
    out.append(('x one pixel off', _rom_patch(patch, ROM_ORG + k, bytes([0x3E, 0x21]))))
    # 10 y off: add a,32 in show -> 33
    k = code.index(bytes([0xC6, 0x20]), s['show'] - ROM_ORG)
    out.append(('y one line off', _rom_patch(patch, ROM_ORG + k, bytes([0xC6, 0x21]))))
    # 11 no upload: the OTIR removed
    k = code.index(bytes([0xED, 0xB3]))
    out.append(('patterns never uploaded', _rom_patch(patch, ROM_ORG + k, bytes(2))))
    # 12 slot 6 not restored
    k = code.index(bytes([0xED, 0x91, 0x56, 0x00]))
    out.append(('slot 6 not restored', _rom_patch(patch, ROM_ORG + k, bytes(4))))
    # 12b the plot's return does not drop the speed
    k = code.index(b'\xed\x92\x07', s['tramp'] - ROM_ORG)
    out.append(('28 MHz left on', _rom_patch(patch, ROM_ORG + k, bytes(3))))
    # 13 the tile hook leaves the row writes off
    k = code.index(bytes([0x3E, 0x77]))
    out.append(('tile row writes stay off', _rom_patch(patch, ROM_ORG + k, bytes([0x3E, 0x00]))))
    # 14 a scenery tile caller converted as well is not caught by a hook but by the caller check; the tile hook skipping the toggle:
    e = s['e_t'] - ROM_ORG
    k = code.index(bytes([0xCD]) + s['bt'].to_bytes(2, 'little'), e)
    out.append(('tile hook draws no new image', _rom_patch(patch, ROM_ORG + k, bytes(3))))
    return out


def negative_real(patch, rzx_path, stop=1500):
    """Each broken build through the whole verify on the real recording. -> [(name, number of failures)]."""
    out = []
    for name, q in negative_patches(patch):
        cc, _ = verify(q, rzx_path, stop=stop)
        out.append((name, sum(v for k, v in cc.items() if k.endswith('!'))))
    return out



def boot_check(nex, z80, patch=None, tail=None):
    """128K entry check, including R and both loader entry paths.

    5B00..5BFF is scenery/printer workspace: the recorded ROM-path audit proves
    it is written before read. No other visible RAM is excluded.
    """
    from . import z80tonex as zt, nextboot, hooklib
    from skoolkit import CSimulator
    from skoolkit.simutils import from_memory
    from skoolkit.pagingtracer import Memory
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch.apply(s)
    regs = {k.upper(): getattr(s, k) for k in ('a','f','bc','de','hl','ix','iy','sp','i','r','pc')}
    regs.update({'^' + k.upper(): getattr(s, k + '_') for k in ('a','f','bc','de','hl')})
    exp = from_memory(CSimulator, Memory([list(s.banks[b]) for b in range(8)], s.port7ffd),
                      regs, {'iff': s.iff1, 'im': s.im}).registers
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(nex, s.pc, nexload=nexload)
        bad += [(nexload, 'register', i, exp[i], st['R'][i]) for i in hooklib.CMP_R if exp[i] != st['R'][i]]
        for a in range(0x4000, 0x10000):
            if 0x5B00 <= a < 0x5C00:
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append((nexload, 'RAM', a))
        bad += [(nexload, 'boot', b) for b in st['bad']]
    return bad

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    check = boot_check
    say('Game      : %s' % name)
    say('Engine    : cybernoid (XOR plots 32957, 41469, 42203 for figures -> sprites; scenery, panel, text stay on the ULA)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = CybernoidPatch(colours={})
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
        unexplained = cc['screen bytes changed with no scenery routine']
        ok = ok and not fails and not unexplained
        say('Verify    : %s  %d frames, ticks %d; small %d, big %d, tile %d, shot %d; paints %d, %d, %d; clears %d; %d sprite pixels, '
            '%d screen checks (%d bytes unexplained), most images %d, most sprites %d, table full %d -> %s' % (
                os.path.basename(r), cc['frames'], cc['k'], cc['s'], cc['b'], cc['t'], cc['p'], cc['a1'], cc['a2'], cc['a3'], cc['c'],
                cc['sprite pixels compared'], cc['screen checks'], unexplained, cc['most images'], cc['most sprites'],
                cc['table full'], 'IDENTICAL' if not fails and not unexplained else 'FAILED %s' % fails))
        say('            tile callers: %s' % ', '.join('%s %d' % (k[6:], v) for k, v in sorted(cc.items()) if k.startswith('tile:')))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
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
        nr = negative_real(patch, list(a.rzx)[0], stop=min(getattr(a, 'quick', None) or 2000, 2000))
        miss = [n for n, k in nr if not k]
        ok = ok and not miss
        say('Negative  : %s  real recording, %d of %d detected %s' % (os.path.basename(list(a.rzx)[0]), len(nr) - len(miss), len(nr), miss))
        for n, k in nr:
            say('            %s: %d failures' % (n, k))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
