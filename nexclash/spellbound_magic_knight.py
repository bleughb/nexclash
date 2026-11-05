"""Spellbound (Mastertronic Added Dimension 1986, 128K edition) engine 'spellbound_magic_knight' (record spellbound_magic_knight; the pilot's 'spellbound', renamed 2026-11-04: spellbound_dizzy is another game). Additive module: reachable only
through is_spellbound_magic_knight(). Game facts and decisions: games/spellbound_magic_knight.md.

  Snapshot: rzx/s0.z80, the archive's file stepped from PAUSE 0 in 128 BASIC to RANDOMIZE USR 26627 (0x6803).
  Knight: composed box blitted by 0xA59F at 0xA63B; characters, objects: masked cell plots in the room build, before the
  screen is copied to bank 7 as the room's clean copy; smoke at 0x732D; balls, an XOR plot at 0xAB3B. All sprites. Game code
  runs the same instructions in the same order, so the verifier runs original and patched machines in lockstep over the
  recording, hook instructions not counted, and compares the whole 128K every frame.
"""
import collections
import copy
import hashlib
import json
import os

RECORD = 'spellbound_magic_knight'
SIG = (0xA63B, bytes.fromhex('cd9fa5'))
SIG2 = (0x90BD, bytes.fromhex('fdcb41ce0832b1ac'))
ROM_ORG = 0x386E
ALT_PAGE, HPG, GP4, GP5, STORE, NSTORE = 24, 26, 4, 5, 28, 16
KSLOT = 122
BSLOT, BPAT, BINK = 118, 124, 13
RFIRST = 48
V_SP, V_K, V_A, V_NS, V_NP, V_HID, V_HASC, V_OL, V_DROP = 0, 2, 3, 6, 7, 8, 9, 10, 11
SPRTAB, CACHE = 0x100, 0x500
HSTK = 0x1440
PAGE_ORG = 0x9440
CBLACK, CWHITE = 8, 15
# index 0 transparent, 1-7 colours, 8 black, 9-15 bright colours
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
# A colour map may carry its own sprite palette under the key 'palette' (16 bytes, RRRGGGBB, as NextReg 0x41 takes
# them); the setup routine loads it in place of PALETTE. Only these entries may differ: dim blue, red, magenta, green and
# cyan, which no figure the map leaves unpainted can show (objects in the game's table use 0, 6, 7 and the bright inks,
# smoke 15, balls 13, outlines 8 and 15, the fill 8). The verifier checks that at every plot and commit.
PAL_FREE = (1, 2, 3, 4, 5)
SITES = [  # (addr, original, kind, symbol)
    (0xA63B, 'cd9fa5', 'cd', 'e_kn'),
    (0x72E9, 'cd19ad', 'cd', 'e_ch'),
    (0x94E4, 'cd14ad', 'cd', 'e_ob'),
    (0x732D, 'cd0fad', 'cd', 'e_sm'),
    (0x733C, 'cdf077', 'cd', 'e_sx'),
    (0x8E42, 'cd3bab', 'cd', 'e_ba'),
    (0x8E6B, 'cd3bab', 'cd', 'e_ba'),
    (0x8F55, 'cd3bab', 'cd', 'e_ba'),
    (0x6FA9, '3ac262', 'c3', 'e_rm'),
    (0x90F1, 'cd3c91', 'cd', 'e_wn'),
    (0x934E, '210000', 'c3', 'e_wp'),
]
# (address, original, register holding the value): stores that become NOP, one instruction for one
PAINT = [(0xA68A, 0x71, 3), (0xA696, 0x71, 3), (0xA6A2, 0x71, 3),                # the Knight's cells
         (0x9502, 0x73, 5), (0x9508, 0x73, 5), (0x9511, 0x73, 5), (0x9517, 0x73, 5),  # an object's cells
         (0x7307, 0x77, 0), (0x7309, 0x77, 0)]                                   # a character's cells
BALLSTORE = [(0xAB5E, 0x77, None), (0xAB63, 0x77, None)]                         # the ball's XOR
DATA_SITES = [(0xA5A0, 0x05, 0x65)] + [(a, o, 0) for a, o, _ in PAINT + BALLSTORE]
BALLSITES = (0x8E42, 0x8E6B, 0x8F55)
SMOKE_ATTR = 0x47
TABLE_CHECK = ((39085, None),)
SCREEN_PIX = (0x4000, 0x5800)
GTAB = 0xC544
LINES = 0x6680
KX, KY, KSHIFT, KFACE, KCOL = 25720, 25355, 25357, 25723, 25360
OBJCOL, CHCOL = 23695, 0x7303
BLIT_SPAN = (0xA59F, 0xA5C8)
PLOT_SPAN = (0xAD0F, 0xAD76)
PLOT_HELPER = (0xB32D, 0xB331)     # a helper the plotter calls
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'spellbound_magic_knight_colours.json')
# Figures whose ink index is white take a black ring; the rest a white one.
CMP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27]
# Bytes allowed to differ between original and patched: the pictures and the buffers built from them.
EXCL_B5 = [(0x0000, 0x1800), (0x5D05 - 0x4000, 0x5DC5 - 0x4000), (0x5DE5 - 0x4000, 0x5DF1 - 0x4000),
           (0x63FD - 0x4000, 0x643D - 0x4000), (0x64FA - 0x4000, 0x655A - 0x4000)]
ATTR = (0x1800, 0x1B00)           # bank 5 offsets: compared against what the NOPs would have painted
EXCL_B7 = [(0x2000, 0x3800)]      # 0xE000-0xF7FF: the room's clean copy


def is_spellbound_magic_knight(snap):
    if snap.machine == '48K':
        return False
    return all(bytes(snap.memory[a:a + len(s)]) == s for a, s in (SIG, SIG2))


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def load_colours(path=COLOURS):
    """The engine's map {key: [check, kind, [8 nibbles], mask]} (+ 'palette'); a file in coloursheet.save's form
    ({"note", "entries"}: selftest's empty map for the recolour guard) is read with coloursheet.load (import,
    2026-11-04: the pilot never ran that guard)."""
    if not os.path.exists(path):
        return {}
    d = json.load(open(path))
    if isinstance(d.get('entries'), dict):
        from . import coloursheet as cs
        out = cs.load(path)
        if 'palette' in d:
            out['palette'] = d['palette']
        return out
    return d


def load_colours_build():
    from .recolour import build_colours_path
    return load_colours(build_colours_path(COLOURS))


def set_palette(colours):
    """The sprite palette a colour map asks for: its 'palette' entry, else PALETTE. ValueError if it is not 16 bytes, or
    if it changes an entry outside PAL_FREE."""
    p = (colours or {}).get('palette')
    if p is None:
        return list(PALETTE)
    p = list(p)
    if len(p) != 16 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in p):
        raise ValueError('a colour map palette is 16 bytes')
    bad = [i for i in range(16) if p[i] != PALETTE[i] and i not in PAL_FREE]
    if bad:
        raise ValueError('a colour map palette may change only entries %s, not %s' % (list(PAL_FREE), bad))
    return p


def store_pages(colours):
    """Colour map -> NSTORE pages: 8 bytes per address 0xC000-0xFFFF: [1, check, 4 nibble bytes, clear mask, 0]."""
    st = bytearray(NSTORE * 8192)
    for k, e in (colours or {}).items():
        if k == 'palette':
            continue
        a = int(k, 16)
        if not 0xC000 <= a <= 0xFFFF:
            continue
        i = a - 0xC000
        nib = e[2]
        st[8 * i:8 * i + 8] = bytes([1, e[0] & 255] + [nib[2 * n] << 4 | nib[2 * n + 1] for n in range(4)] +
                                    [e[3] if len(e) > 3 else 0, 0])
    return bytes(st)


class SpellboundPatch:
    name = 'Spellbound figures -> hardware sprites (alt ROM stubs, page 26 at slot 4, plots undone, attribute paint off, room copy clean)'

    def __init__(self, prof=None, colours=None, rom_code=None, page_code=None, outline=True, sites=None, data_sites=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.page_code = page_code if page_code is not None else bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.colours = dict(colours) if colours is not None else load_colours_build()
        self.palette = set_palette(self.colours)
        self.stub_extra = bytes.fromhex(h['setup']) + bytes(self.palette)
        self.outline = outline
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock != self.syms['rom_end']:
            raise ValueError('hook code length differs from the profile symbols')
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hooks reach 0x3D00')
        self.slot1 = (ALT_PAGE, self.regblock)
        # The WHOLE alt ROM image comes from the build: Sinclair's 48K ROM + hooks (2026-11-04, altrom_audit). The Next's
        # stub fills image 1 from the system ROM3 first, which is NextZXOS's: its IM 1 handler CALLs 0x386E (0x004A) and
        # its UDG print JPs to 0x387E (0x0B52), both into these hooks; this game takes IM 1 interrupts at its start.
        # Writing only 0x386E.. was safe only while NextZXOS's DivMMC trap takes 0x0038. altrom_low: page 25.
        self.altrom = (0x2000, 0x4000)
        self.hook_range = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        _rom = rom48()
        self.page = bytearray(_rom[0x2000:0x4000])
        self.page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.altrom_low = (ALT_PAGE + 1, bytes(_rom[0:0x2000]))
        self.hpage = bytearray(16384)
        self.hpage[V_NP] = RFIRST
        self.hpage[V_HASC] = 1 if self.colours else 0
        self.hpage[V_OL] = 1 if outline else 0
        self.hpage[PAGE_ORG - 0x8000:PAGE_ORG - 0x8000 + len(self.page_code)] = self.page_code
        self.store = store_pages(self.colours)
        self.sites = []
        for a, old, op, sym in (sites if sites is not None else SITES):
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(op) + self.syms[sym].to_bytes(2, 'little')))
        self.data_sites = list(data_sites if data_sites is not None else DATA_SITES)
        self._banks()

    def _banks(self):
        low = getattr(self, 'altrom_low', None)
        self.extra_banks = {12: bytes(self.page) + (low[1] if low else bytes(8192)), 13: bytes(self.hpage)}
        for n in range(NSTORE // 2):
            self.extra_banks[14 + n] = self.store[16384 * n:16384 * (n + 1)]

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.port7ffd & 7 != 0:
            raise ValueError('Spellbound patch expects the 128K snapshot (7FFD bank 0)')
        ram = {5: bytearray(snap.banks[5]), 2: bytearray(snap.banks[2]), 0: bytearray(snap.banks[0])}

        def where(a):
            return (5, a - 0x4000) if a < 0x8000 else ((2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000))
        for a, old, new in self.sites:
            for k in range(len(old)):
                b, o = where(a + k)
                if ram[b][o] != old[k]:
                    raise ValueError('unexpected code at 0x%04X' % (a + k))
            for k, v in enumerate(new):
                b, o = where(a + k)
                ram[b][o] = v
        for a, old, new in self.data_sites:
            b, o = where(a)
            if ram[b][o] != old:
                raise ValueError('unexpected byte at 0x%04X' % a)
            ram[b][o] = new
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        self.page[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self._banks()
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[5]), bytes(ram[2]), bytes(ram[0])


# ---------------------------------------------------------------------------------------------
# The figure model (independent of the hook code)
# ---------------------------------------------------------------------------------------------

def ink_index(attr):
    c, b = attr & 7, (attr >> 6) & 1
    return CBLACK if c == 0 else c + 8 * b


def outline_of(ink):
    return (CBLACK, True) if ink & 7 == 7 else (CWHITE, False)


def _enclosed(opaque, w, h):
    seen, q = set(), [(-1, -1)]
    while q:
        p = q.pop()
        if p in seen or p in opaque or not (-1 <= p[0] <= w and -1 <= p[1] <= h):
            continue
        seen.add(p)
        x, y = p
        q += [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
    return [(x, y) for y in range(h) for x in range(w) if (x, y) not in opaque and (x, y) not in seen]


def figure_pixels(get, g, m, wb, h, attr, outline=True, colours=None):
    """{(x, y) relative to the figure's box: index}; x, y from -1. Ink in the figure's colour, the game's knocked-out
    paper black, then a one-pixel ring: white, or black on the ink of a white figure (the mask is its halo)."""
    ink = ink_index(attr)
    out = {}
    for y in range(h):
        for bx in range(wb):
            ga, gb, mb = g + y * wb + bx, get(g + y * wb + bx), get(m + y * wb + bx)
            nib, clr = [0] * 8, 0
            e = colours.get('%04X' % ga) if colours else None
            if e and e[0] & 255 == gb:
                nib, clr = e[2], e[3] if len(e) > 3 else 0
            for b in range(8):
                bit = 0x80 >> b
                if clr & bit:
                    continue
                if gb & bit:
                    c = nib[b] or ink
                elif mb & bit:
                    c = nib[b]
                else:
                    c = nib[b] or CBLACK
                if c:
                    out[(bx * 8 + b, y)] = c
    for p in _enclosed(out, wb * 8, h):      # see-through pixels the outside cannot reach: black, no outline inside
        out[p] = CBLACK
    if outline:
        oc, on_ink = outline_of(ink)
        rings = {}
        for y in range(-1, h + 1):
            for x in range(-1, wb * 8 + 1):
                if (x, y) in out:
                    continue
                for n in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    v = out.get(n)
                    if v and not (on_ink and v == CBLACK):
                        rings[(x, y)] = oc
                        break
        out.update(rings)
    return out


def unpainted_ink(get, g, m, wb, h, colours):
    """Ink bits of a figure that show the figure's own ink: no map entry for the byte, a wrong check byte, or nibble 0."""
    n = 0
    for y in range(h):
        for bx in range(wb):
            ga = g + y * wb + bx
            gb = get(ga)
            if not gb:
                continue
            e = colours.get('%04X' % ga) if colours else None
            nib, clr = ([0] * 8, 0) if not (e and e[0] & 255 == gb) else (e[2], e[3] if len(e) > 3 else 0)
            n += sum(1 for b in range(8) if gb & (0x80 >> b) and not clr & (0x80 >> b) and not nib[b])
    return n


def gfx_of(get, idx):
    t = GTAB + 4 * idx
    return get(t) + 256 * get(t + 1), get(t + 2) + 256 * get(t + 3)


def knight_state(get):
    """What the commit at 0xA63B shows: image, column, line, colour."""
    return dict(i=(get(KSHIFT) & 3) + (4 if get(KFACE) else 0), col=get(KX), y=get(KY), attr=get(KCOL))


def knight_addrs(kn):
    return 0xF9F4 + 96 * kn['i'], 0xFCF4 + 96 * kn['i']


def ball_pixels(get, ch):
    """A ball frame: ink at (x, y), a one-pixel white ring; x, y from -1."""
    out = {}
    g = 0xBA00 + 8 * ch
    for y in range(8):
        v = get(g + y)
        for x in range(8):
            if v & (0x80 >> x):
                out[(x, y)] = BINK
    rings = {}
    for y in range(-1, 9):
        for x in range(-1, 9):
            if (x, y) not in out and any(n in out for n in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                rings[(x, y)] = CWHITE
    out.update(rings)
    return out


def expected_layer(get, plots, kn, colours=None, outline=True, balls=()):
    """Plots in plot order (kind 0 char, 1 object, 2 smoke; idx, row, col, attr), the balls, then the Knight: {(x, y): index},
    and a code per pixel: 'i' ink, 'k' knocked-out black, 'r' ring over nothing, 'R' ring over a lower figure, 'b' ball ink."""
    lay, code = {}, {}

    def add(g, m, wb, h, attr, x0, y0):
        solid = figure_pixels(get, g, m, wb, h, attr, False, colours)
        for (x, y), v in (figure_pixels(get, g, m, wb, h, attr, outline, colours)).items():
            k = (x0 + x, y0 + y)
            if (x, y) in solid:
                bx, b = x // 8, x % 8
                code[k] = 'i' if get(g + y * wb + bx) & (0x80 >> b) else ('k' if not get(m + y * wb + bx) & (0x80 >> b) else 'f')
            else:
                code[k] = 'R' if code.get(k) in ('i', 'k', 'f', 'R', 'b') else 'r'
            lay[k] = v
    for p in plots:
        g, m = gfx_of(get, p['idx'])
        add(g, m, 2, {0: 32, 1: 16, 2: 24}[p['kind']], p['attr'], p['col'] * 8, p['row'] * 8)
    for ch, x0, y0 in balls:
        for (x, y), v in ball_pixels(get, ch).items():
            k = (x0 + x, y0 + y)
            if v == BINK:
                code[k] = 'b' if k not in code or code[k] == 'r' else 'R'
            else:
                code[k] = 'R' if code.get(k) in ('i', 'k', 'R', 'b') else 'r'
            lay[k] = v
    g, m = knight_addrs(kn)
    add(g, m, 3, 32, kn['attr'], kn['col'] * 8, kn['y'])
    return lay, code


# ---------------------------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------------------------

class _NS:
    """Next-side state of the patched machine."""

    def __init__(self, patch):
        self.nr = {0x07: 0, 0x54: GP4, 0x55: GP5, 0x15: 1}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.H = bytearray(patch.hpage[:8192])
        self.ports = 0

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
            return True
        if port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
            return True
        return False

    def sprite_layer(self):
        out = {}
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            x0 = a0 + (a2 & 1) * 256 - 32
            y0 = a1 + (a4 & 1) * 256 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    c = (b >> 4) if k % 2 == 0 else (b & 15)
                    if c:
                        out[(x0 + k, y0 + j)] = c
        return out


def rom48_image():
    from .build import rom48
    return bytes(rom48())


def rom3():
    """The system ROM3 the stub copies into alt image 1 before the build's bytes: NextZXOS's (enNextZX.rom, MD5
    8c34d957, from the card's /machines/next) when $NEXCLASH_NEXT_ROM / --next-rom names it (nextboot.system_rom3;
    imported 2026-11-04: the pilot read work/rom/enNextZX.rom), else Sinclair's stands in."""
    from . import nextboot
    return nextboot.system_rom3()[0]


def next_rom_modelled():
    from . import nextboot
    return nextboot.system_rom3()[0] != bytes(rom48_image())


def alt_image(patch):
    """Alt ROM image 1 as the Next's stub fills it (z80tonex.altrom_fill): the SYSTEM ROM3 copied first (NextZXOS's,
    with code at 0x386E-0x3CFE that its IM 1 handler and UDG print call), then bytes lo..hi of the patch page, then
    altrom_low over 0x0000-0x1FFF. Kept from the pilot, not nextboot.alt_image: that one gives a partial image
    Sinclair's ROM underneath (the 2026-11-04 default fill), so the previous-build negative (rom3_left: hooks only,
    as published before 1.1 with the ROM3 fill) would equal the good build. For this build both agree."""
    alt = bytearray(rom3())
    lo, hi = patch.altrom
    alt[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    low = getattr(patch, 'altrom_low', None)
    if low:
        alt[0:0x2000] = low[1]
    return bytes(alt)


def alt_outside_hooks(patch):
    """Addresses of the alt ROM image, outside the hook bytes, that are not Sinclair's 48K ROM (empty = whole image)"""
    alt, rom = alt_image(patch), rom48_image()
    h0, h1 = getattr(patch, 'hook_range', patch.altrom)
    return [a for a in range(0x4000) if not h0 <= a < h1 and alt[a] != rom[a]]


def rom3_left(patch):
    """The build before 2026-11-04 (published 0970da8d): only the hook bytes 0x386E.. written over NextZXOS's ROM3"""
    patch.altrom = patch.hook_range
    patch.altrom_low = None
    h0, h1 = patch.hook_range
    pg = bytearray(8192)                    # that build's page: zero but for the hooks (only they were copied)
    pg[h0 - 0x2000:h1 - 0x2000] = patch.page[h0 - 0x2000:h1 - 0x2000]
    patch.page = pg
    patch._banks()
    return patch


def game_machine(snap, trace_ports=None):
    """A Python simulator on the 128K with stock 48K ROM as ROM 1 (the Next's ROM 3 is the 48K ROM, not the 128's)."""
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    sim = from_snapshot(Simulator, snap, config={'int_active': 0})
    r = rom48_image()
    sim.memory.roms[1][:] = list(r)
    return sim


class _Ports:
    """Tracer: port reads from the recording, 7FFD; the patched machine also has the sprite ports."""

    def __init__(self, sim, snap, ns=None):
        self.sim, self.ns = sim, ns
        self.o7ffd = snap.out7ffd
        self.ins = []
        self.i = 0
        self.bad = 0

    def read_port(self, registers, port):
        if self.i < len(self.ins):
            self.i += 1
            return self.ins[self.i - 1]
        self.bad += 1
        return 255

    def write_port(self, registers, port, value, offset=0):
        if self.ns is not None and self.ns.out(port, value):
            return
        if port & 0x8002 == 0 and self.o7ffd & 32 == 0:
            self.sim.memory.out7ffd(value)
            self.o7ffd = value


ROMPC = [None]


def _patched_memory(mem, patch, ns, err):
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    lo, hi = getattr(patch, 'hook_range', patch.altrom)
    img = alt_image(patch)                  # what ROM 1 (alt image 1) holds on the Next, from NextZXOS's ROM3
    page, store = patch.page, patch.store
    H = ns.H
    nr = ns.nr

    class PM(Memory):
        def __getitem__(self, a):
            if a < 0x4000:
                if lo <= a < hi:
                    if not self.o7ffd & 16:
                        err.append(('alt ROM stub with ROM 0 selected', a))
                    return page[a - 0x2000]
                if not self.o7ffd & 16:
                    err.append(('read of ROM 0', a, ROMPC[0] and ROMPC[0][24], self.o7ffd))
                    return MG(self, a)
                return img[a]
            if 0x8000 <= a < 0xA000:
                if nr[0x54] == HPG:
                    return H[a - 0x8000]
            elif 0xA000 <= a < 0xC000 and nr[0x55] != GP5:
                pg = nr[0x55] - STORE
                if 0 <= pg < NSTORE:
                    return store[pg * 8192 + a - 0xA000]
                err.append(('slot 5 page', nr[0x55]))
                return 0
            return MG(self, a)

        def __setitem__(self, a, v):
            if 0x8000 <= a < 0xA000 and nr[0x54] == HPG:
                H[a - 0x8000] = v
                return
            if 0xA000 <= a < 0xC000 and nr[0x55] != GP5:
                err.append(('write to the colour store', a))
                return
            MS(self, a, v)
    mem.__class__ = PM


def patched_machine(snap, patch, err):
    from . import z80n
    sim = game_machine(snap)
    ns = _NS(patch)
    mem = sim.memory
    for a, old, new in patch.sites:
        for k, v in enumerate(new):
            mem[a + k] = v
    for a, old, new in patch.data_sites:
        mem[a] = new
    _patched_memory(mem, patch, ns, err)
    z80n.install(sim, ns.nextreg, strict=False)
    ROMPC[0] = sim.registers
    return sim, ns


def _cells(b5, row, col, lines):
    out = []
    for l in range(lines):
        y = row * 8 + l
        base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        out.extend(b5[base + col:base + col + 2])
    return out


def _frames(rzx_path):
    """-> [(snapshot, [(fetch, ins)])]"""
    from skoolkit.rzxplay import parse_rzx, InputRecording
    from skoolkit.snapshot import Snapshot
    import shutil
    import tempfile
    out, snap = [], None
    fd, tmp = tempfile.mkstemp(suffix='.rzx', dir=os.environ.get('TMPDIR'))
    os.close(fd)
    try:
        shutil.copy(rzx_path, tmp)
        for block in parse_rzx(tmp):
            o = block.obj
            if isinstance(o, InputRecording):
                out.append((o.snapshot if getattr(o, 'snapshot', None) else snap,
                            [(f.fetch_counter, list(o.data[f.start:f.end])) for f in o.frames]))
            else:
                snap = o
    finally:
        os.remove(tmp)
    return out


def _run_orig(sim, ports, fc, ins, watch=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    ports.ins, ports.i = ins, 0
    pc = R[24]
    while fc > 0:
        pc = R[24]
        op = mem[pc]
        if op in (0xDD, 0xFD):
            r0 = R[15]
            ops[op]()
            fc -= 2 - ((R[15] ^ r0) % 2)
        else:
            ops[op]()
            fc -= 2 if op in (0xCB, 0xED) else 1
    return pc


def _accept(sim, pc):
    R, mem = sim.registers, sim.memory
    R[25] = 0
    if R[26]:
        if mem[pc] == 0x76:
            R[24] = (R[24] + 1) % 65536
        sim.accept_interrupt(R, mem, 0)


STALE = {}
# registers read from the screen in the original (it differs here), in the lines before they are reloaded
STALE_SPANS = [(0x72EC, 0x72F1, (0, 1)), (0x94E7, 0x94E9, (0, 1)), (0x7330, 0x733F, (0, 1)), (0x77F0, 0x7810, (0, 1)),
               (0xAB3B, 0xAB6E, (0, 1, 5)), (0x8E45, 0x8EE5, (0, 1, 5)), (0x8F20, 0x8F5B, (0, 1, 5))]


# ---------------------------------------------------------------------------------------------
# Differential verification: lockstep over the recording
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=4, colours_model=None, grab=None):
    """-> (Counter, examples, captured states). Failure keys end in '!'. Both machines replay the recording; hook
    instructions (alt ROM stubs, page H code) are not counted, so game code stays in step with the original."""
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    st = {'frame': 0}

    def fail(k, *info):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + info)

    site_set = {a for a, _, _ in patch.sites}
    lo, hi = getattr(patch, 'hook_range', patch.altrom)      # hook instructions (uncounted); the image is wider
    _off = alt_outside_hooks(patch)
    if _off:
        c["alt ROM image bytes outside the hooks not Sinclair's!"] = len(_off)
        ex["alt ROM image bytes outside the hooks not Sinclair's"].append((0, [hex(a) for a in _off[:6]]))
    for snap, frames in _frames(rzx_path):
        so = game_machine(snap)
        po = _Ports(so, snap)
        so.set_tracer(po)
        err = []
        sp, ns = patched_machine(snap, patch, err)
        pp = _Ports(sp, snap, ns)
        sp.set_tracer(pp)
        Ro, Rp, mo, mp, op = so.registers, sp.registers, so.memory, sp.memory, sp.opcodes
        H = ns.H
        nr = ns.nr
        plots = []
        smoke = []
        balls = {}
        painted = {}
        PAINT_PC = {a: r for a, _, r in PAINT + BALLSTORE}

        def balls_now():
            return [balls[k] for k in sorted(balls) if balls[k]]
        changed = {i for i in range(16) if patch.palette[i] != PALETTE[i]}

        def palette_check(g, m, wb, h, attr, what):
            """A figure that shows its own ink must not show it in an entry the set's palette changed."""
            if not changed:
                return
            c['palette ink checks'] += 1
            if ink_index(attr) in changed and unpainted_ink(lambda a: mp[a], g, m, wb, h, patch.colours):
                fail('a figure shows a palette entry the set changed', what, hex(attr))
        hookT = [0]
        win = [None]
        rec = {'commits': 0}
        code_bytes = {a + k: None for a, old, new in patch.sites for k in range(len(old))}
        code_bytes.update({a: None for a, _, _ in patch.data_sites})

        def in_hook(pc):
            return lo <= pc < hi or (0x8000 <= pc < 0xA000 and nr[0x54] == HPG)

        def before_game(pc):
            """A patch site or a checkpoint is about to run in the patched machine."""
            if pc in PAINT_PC:
                ad = Rp[6] * 256 + Rp[7]
                rec['pend'] = (ad, mp[ad])
                c['stores made NOPs ran: %04X' % pc] += 1
                reg = PAINT_PC[pc]
                if reg is not None and 0x5800 <= ad < 0x5B00:
                    painted.setdefault(ad - 0x5800, set()).add(Rp[reg])
                return
            if pc in BALLSITES:
                n = ((Rp[9] - 0xE6) >> 3) & 3
                c['ball plots'] += 1
                balls[n] = None if Rp[0] < 116 else (Rp[0], mp[23677], mp[23678])
                return
            if pc == 0x72E9 or pc == 0x94E4 or pc == 0x732D:
                if not Rp[26]:
                    fail('interrupts off at a figure site', hex(pc))
                if pc == 0x94E4 and Rp[8] * 256 + Rp[9] == 25594:
                    c['object pictures left in a window'] += 1
                    return
                kind = {0x72E9: 0, 0x94E4: 1, 0x732D: 2}[pc]
                lines = {0: 32, 1: 16, 2: 24}[kind]
                st['cells'] = _cells(mp.banks[5], Rp[2], Rp[3], lines)
                st['cells_at'] = (Rp[2], Rp[3], lines)
                attr = {0: mp[CHCOL], 1: mp[OBJCOL], 2: SMOKE_ATTR}[kind]
                if kind == 2:
                    smoke[:] = [dict(kind=2, idx=Rp[0], row=Rp[2], col=Rp[3], attr=attr)]
                    st['smoke_new'] = True
                else:
                    plots.append(dict(kind=kind, idx=Rp[0], row=Rp[2], col=Rp[3], attr=attr))
                palette_check(*gfx_of(lambda a: mp[a], Rp[0]), 2, lines, attr, (kind, Rp[0]))
                c['plots %s' % ('character', 'object', 'smoke')[kind]] += 1
                st.setdefault('idx', collections.Counter())[(kind, Rp[0], attr)] += 1
            elif pc in (0x72EC, 0x94E7, 0x7330):
                # the plot ran and the hook put the cells back: the ULA is as the plot found it
                if st.get('cells') is not None:
                    if _cells(mp.banks[5], *st['cells_at']) != st['cells']:
                        fail('a plot left pixels on the ULA', st['cells_at'])
                    c['plots undone checks'] += 1
                    st['cells'] = None
                if pc == 0x7330 and st.pop('smoke_new', False) and not any(ns.attr[i][3] & 0x80 for i in range(KSLOT, 128)):
                    # a smoke frame's sprites: the plot's model, where no Knight tile can lie over it
                    p0 = smoke[0]
                    g0, m0 = gfx_of(lambda a: mp[a], p0['idx'])
                    lay = ns.sprite_layer()
                    want = figure_pixels(lambda a: mp[a], g0, m0, 2, 24, p0['attr'], patch.outline, patch.colours)
                    x0, y0 = p0['col'] * 8, p0['row'] * 8
                    c['smoke layer checks'] += 1
                    if any(lay.get((x0 + x, y0 + y)) != v for (x, y), v in want.items()):
                        fail('smoke sprites differ from its plot', p0)
            elif pc == 0x7122:
                painted.clear()      # the new room's attributes are all written: both machines agree again
            elif pc == 0x733C:
                smoke.clear()
                c['smoke ends'] += 1
            elif pc == 0xA63B:
                if not Rp[26]:
                    fail('interrupts off at the Knight site')
                c['commits'] += 1
                rec['commits'] += 1
                rec['kn'] = knight_state(lambda a: mp[a])
                palette_check(*knight_addrs(rec['kn']), 3, 32, rec['kn']['attr'], ('Knight', rec['kn']['i']))
                st['ktypes'] = st.get('ktypes', set()) | {rec['kn']['i']}
            elif pc == 0x6FA9 or pc == 0x934E:
                plots.clear()
                smoke.clear()
                balls.clear()
                c['room builds' if pc == 0x6FA9 else 'wipes'] += 1
            elif pc == 0x90F1:
                if not Rp[26]:
                    fail('interrupts off at the window site')
                c['windows'] += 1
                win[0] = (mp[25714], mp[25715], mp[25716], mp[25717])
            elif pc == 0x913C and win[0] is not None:
                # the hook has just run: no tile that touches the window is shown
                l, t, r_, b = win[0]
                win[0] = None
                if 'kn' in rec:
                    lay = ns.sprite_layer()
                    _, code = expected_layer(lambda a: mp[a], plots + smoke, rec['kn'], patch.colours, patch.outline, list(balls_now()))
                    for (x, y) in lay:
                        if l * 8 <= x <= r_ * 8 + 7 and t * 8 <= y <= b * 8 + 7 and code.get((x, y)) not in ('r', 'R'):
                            fail('a sprite shows over a window', x, y, (l, t, r_, b))
                            break
                c['window hide checks'] += 1
                st['hidden'] = True

        def hook_exit(pc, r0):
            """Back in game code: every register as the hook found it, but for what the displaced code sets."""
            want = list(r0)
            if pc == 0xA63E:                         # as the original's blit from 0x5D05 ends
                want[4], want[5] = 0x5D, 0x65
                want[0] = mp[0x5D64]
            elif pc == 0x6FAC:
                want[0] = mp[25282]
            elif pc == 0x9351:
                want[6], want[7] = 0, 0
            for i in CMP:
                if Rp[i] != want[i]:
                    fail('hook changed a register', hex(pc), i, Rp[i], want[i])
            c['hook exits checked'] += 1

        def run_patched(fc, ins):
            pp.ins, pp.i = ins, 0
            pc = Rp[24]
            r0 = st.get('r0')
            while fc > 0:
                pc = Rp[24]
                if lo <= pc < hi or (0x8000 <= pc < 0xA000 and nr[0x54] == HPG):
                    if r0 is None:
                        r0 = list(Rp)
                    r = Rp[15]
                    t = Rp[25]
                    o = mp[pc]
                    op[o]()
                    Rp[15] = r
                    hookT[0] += Rp[25] - t
                    continue
                if r0 is not None:
                    hook_exit(pc, r0)
                    r0 = None
                if rec.get('pend'):
                    ad, v = rec['pend']
                    rec['pend'] = None
                    if mp[ad] != v:
                        fail('a figure wrote to the screen or its colours', hex(ad), v, mp[ad])
                if pc in WATCH:
                    before_game(pc)
                o = mp[pc]
                if o in (0xDD, 0xFD):
                    r0_ = Rp[15]
                    op[o]()
                    fc -= 2 - ((Rp[15] ^ r0_) % 2)
                else:
                    op[o]()
                    fc -= 2 if o in (0xCB, 0xED) else 1
            st['r0'] = r0
            return pc
        WATCH = site_set | {0x7122, 0x913C, 0x72EC, 0x94E7, 0x7330} | set(PAINT_PC)

        def compare_memory():
            bad = []
            sp0 = Rp[12]
            # dead stack; in a blit or a plot the live return word is the hook's, so a little above SP as well
            dead = (sp0 - 64, sp0 + (16 if BLIT_SPAN[0] <= pcp <= BLIT_SPAN[1] or PLOT_SPAN[0] <= pcp <= PLOT_SPAN[1] or PLOT_HELPER[0] <= pcp <= PLOT_HELPER[1] else 0))
            for b in range(8):
                x, y = mo.banks[b], mp.banks[b]
                if x == y:
                    continue
                base = {5: 0x4000, 2: 0x8000}.get(b, 0xC000)
                ex_ = EXCL_B5 if b == 5 else (EXCL_B7 if b == 7 else [])
                for i in range(16384):
                    if x[i] != y[i]:
                        if any(s <= i < e for s, e in ex_):
                            continue
                        if b == 5 and ATTR[0] <= i < ATTR[1]:
                            if x[i] in painted.get(i - ATTR[0], ()):
                                continue
                            bad.append(('attribute', hex(i), x[i], y[i]))
                            if len(bad) > 4:
                                return bad
                            continue
                        a = base + i
                        if b in (5, 2, 0) and a in code_bytes:
                            continue
                        if b in (5, 2) and dead[0] <= a < dead[1]:
                            continue
                        bad.append((b, hex(i), x[i], y[i]))
                        if len(bad) > 4:
                            return bad
            return bad

        def compare_regs(pc):
            # the blit from the clean box and the plots show other bytes in A while they run; DE differs in the blit
            ret = mp[Rp[12]] + 256 * mp[(Rp[12] + 1) % 65536]
            if in_hook(pc) or BLIT_SPAN[0] <= pc <= BLIT_SPAN[1] or PLOT_SPAN[0] <= pc <= PLOT_SPAN[1] or PLOT_HELPER[0] <= pc <= PLOT_HELPER[1] or pc in (0xA63E,):
                c['register checks skipped in a blit or plot'] += 1
                return
            for i in CMP:
                if Ro[i] != Rp[i]:
                    if i in (16, 17) and c['ball plots']:
                        c["A', F' stale after a ball's XOR"] += 1
                        continue   # the XOR leaves a screen byte in A'; a later difference would show in the lockstep
                    if i in STALE.get(pc, ()) or any(lo_ <= pc <= hi_ and i in rs for lo_, hi_, rs in STALE_SPANS):
                        continue   # read from the screen, which differs; the next instructions reload it
                    fail('registers differ', hex(pc), i, Ro[i], Rp[i])
            if Ro[24] != Rp[24]:
                fail('PC differs', hex(Ro[24]), hex(Rp[24]))
            if Ro[12] != Rp[12]:
                fail('SP differs', hex(Ro[12]), hex(Rp[12]))

        def stable_check():
            """Between commits: the original's screen = the ULA + the sprites, pixel for pixel."""
            lay = ns.sprite_layer()
            exp, code = expected_layer(lambda a: mp[a], plots + smoke, rec['kn'], patch.colours, patch.outline, balls_now())
            c['layer checks'] += 1
            c['sprite pixels compared'] += len(exp)
            if lay != exp:
                d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
                fail('sprite layer differs from the figures', len(d), sorted(d)[:3], [(lay.get(k), exp.get(k)) for k in sorted(d)[:3]])
            bo, bp = mo.banks[5], mp.banks[5]
            b = 0
            ballink = {(x0 + x, y0 + y) for ch, x0, y0 in balls_now() for (x, y), v in ball_pixels(lambda a: mp[a], ch).items() if v == BINK}
            where = []
            for y in range(192):
                base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
                for cx in range(32):
                    o, p = bo[base + cx], bp[base + cx]
                    for i in range(8):
                        k = code.get((cx * 8 + i, y))
                        if k == 'R' or ((cx * 8 + i, y) in ballink and k != 'b'):
                            continue
                        bit = 0x80 >> i
                        if k is None or k == 'r':
                            good = not (o ^ p) & bit
                        elif patch.colours:
                            good = True
                        elif k == 'b':
                            good = bool((o ^ p) & bit)
                        elif k == 'f':
                            good = True        # a filled hole: the original shows the scenery through it
                        elif k == 'k':
                            good = not o & bit
                        else:
                            good = bool(o & bit)
                        if not good:
                            b += 1
                            where.append((cx * 8 + i, y, k))
            # the figures are not on the ULA: under each box the screen = the room's clean copy in bank 7
            b7 = mp.banks[7]
            boxes = [(p['col'], p['row'] * 8, 2, {0: 32, 1: 16, 2: 24}[p['kind']]) for p in plots + smoke] + [(rec['kn']['col'], rec['kn']['y'], 3, 32)]
            boxes += [(x >> 3, y, 2, 8) for _, x, y in balls_now()]
            # census: anything on the ULA that is not the clean copy, wherever it is
            cen = 0
            for y in range(192):
                base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
                for cx in range(32):
                    if bp[base + cx] != b7[0x2000 + base + cx]:
                        cen += 1
                        st.setdefault('census', collections.Counter())[(mp[23701], y >> 3)] += 1
            c['census bytes not the clean copy'] += cen
            n_on = 0
            for col, y0, w, h in boxes:
                for y in range(y0, min(192, y0 + h)):
                    base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
                    for cx in range(col, min(32, col + w)):
                        if bp[base + cx] != b7[0x2000 + base + cx]:
                            n_on += 1
            if n_on:
                fail('a figure is on the ULA', n_on, boxes[-1])
            if b:
                fail('screen + sprites differ from the original screen', b, where[:4], [(p['kind'], p['idx'], p['row'], p['col']) for p in plots + smoke], rec['kn'])
            c['screen checks'] += 1
            if grab is not None and grab.get('want') and st['frame'] >= grab['want'][0]:
                grab['got'].append((st['frame'], bytes(bo), bytes(bp), dict(lay), mp[23701]))
                grab['want'].pop(0)
            if H[V_DROP]:
                fail('figures dropped', H[V_DROP])
                H[V_DROP] = 0
            c['max sprites'] = max(c['max sprites'], sum(1 for a in ns.attr if a[3] & 0x80))
            c['max room plots'] = max(c['max room plots'], len(plots))
            c['max patterns'] = max(c['max patterns'], H[V_NP])

        for n, (fc, ins) in enumerate(frames):
            if stop is not None and st['frame'] >= stop:
                break
            pco = _run_orig(so, po, fc, ins)
            pcp = run_patched(fc, ins)
            st['frame'] += 1
            c['frames'] = st['frame']
            if po.bad or pp.bad:
                fail('port reads ran out', po.bad, pp.bad)
                po.bad = pp.bad = 0
            for e in err:
                fail(str(e[0]), hex(e[1]) if isinstance(e[1], int) else e[1], *[hex(x) for x in e[2:]])
            err.clear()
            if (nr[0x54], nr[0x55], nr[0x07]) != (GP4, GP5, 0) and not in_hook(pcp):
                fail('MMU / speed not restored', nr[0x54], nr[0x55], nr[0x07])
            if ns.ports:
                fail('port access in a hook', ns.ports)
                ns.ports = 0
            compare_regs(pcp)
            bad = compare_memory()
            if bad:
                fail('memory differs', bad[:4])
            if pcp == 0xA629 and rec['commits'] and not st.get('hidden') and n % every == 0:
                stable_check()
            if pcp == 0xA629:
                st['hidden'] = False
            if collect and len(states) < collect and pcp == 0xA629 and rec['commits'] and n % 200 == 0:
                states.append(dict(banks=[bytes(mp.banks[i]) for i in range(8)], regs=list(Rp), o7ffd=mp.o7ffd, H=bytes(H),
                                   attr=[list(a) for a in ns.attr], pat=bytes(ns.pat), plots=[dict(p) for p in plots]))
            _accept(so, pco)
            _accept(sp, pcp)
            if progress and st['frame'] % 2000 == 0:
                progress(st['frame'])
        c['hook T at 28 MHz'] += hookT[0]
    if 'idx' in st:
        c['figure graphics seen'] = len(st['idx'])
        ex['figure graphics seen (kind, idx)'] = [sorted(st['idx'])]
    if 'census' in st:
        ex['census (room, cell row)'] = [sorted(st['census'].items())[:40]]
    if 'ktypes' in st:
        c['Knight images seen'] = len(st['ktypes'])
    return c, ex, states


# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------

def _boot(nex, pc_stop, limit=5_000_000, nexload=False, sysrom=None):
    """nextboot.boot (refactor 884d31a) with the pilot's raster line model (its clone changed nextboot.py; imported
    2026-11-04 into the engine so shared behaviour stays as it is). Run the NEX from its entry point until PC == pc_stop. Returns the machine state dict.
    nexload: start with the printer buffer overwritten as NEXLOAD leaves it (NEXLOAD_PRINTER).
    sysrom: the system ROM3 (default Sinclair's: a check of the stub alone, as the engines' own boot
    checks expect; check() and rom_paths() pass system_rom3(), NextZXOS's when given; pass a different
    ROM to prove an image does not depend on it, BRIEFING C2 #5)."""
    from .nextboot import load_nex, NEXLOAD_PRINTER, system_roms
    from .dizzy6 import _rw_simulator
    from .build import rom48
    banks, sp, pc = load_nex(nex)
    pages = {}
    for b, data in banks.items():
        pages[2 * b] = bytearray(data[0:8192])
        pages[2 * b + 1] = bytearray(data[8192:16384])
    if nexload and 10 in pages:
        pages[10][0x1B00:0x1C00] = NEXLOAD_PRINTER
    rom = sysrom if sysrom is not None else rom48()
    others = system_roms()                     # NextZXOS's ROMs 0-2 when the 64K file is given
    st = {'mmu': [0xFF, 0xFF, 10, 11, 4, 5, 20, 21], 'nr': {0x8C: 0, 0x08: 0}, 'p7ffd': 0x00, 'p1ffd': 0,
          'alt': [bytearray(16384), bytearray(16384)], 'bad': [], 'sel': 0, 'ports': {}, 'nrlog': []}

    def page(n):
        return pages.setdefault(n, bytearray(8192))

    def romn():
        return ((st['p1ffd'] >> 2) & 1) << 1 | ((st['p7ffd'] >> 4) & 1)

    class Mem(list):
        def __getitem__(s, a):
            m = st['mmu'][a >> 13]
            if m == 0xFF:
                n, r = romn(), st['nr'][0x8C]
                if r & 0xC0 == 0x80:
                    return st['alt'][n & 1][a]
                if n != 3:
                    st['bad'].append(('read of ROM %d' % n, a))
                    return others[n][a] if others else 0
                return rom[a]
            return page(m)[a & 0x1FFF]

        def __setitem__(s, a, v):
            m = st['mmu'][a >> 13]
            if m == 0xFF:
                if st['nr'][0x8C] & 0xC0 == 0xC0:
                    st['alt'][romn() & 1][a] = v
                return
            page(m)[a & 0x1FFF] = v

    Sim = _rw_simulator()
    sim = Sim(Mem([0] * 65536), {'PC': pc, 'SP': sp})
    R, ed = sim.registers, sim.after_ED
    from skoolkit.simulator import R2

    def nextreg(reg, val):
        st['nr'][reg] = val
        st['nrlog'].append((reg, val))         # every NEXTREG write in order (palette uploads)
        if 0x50 <= reg <= 0x57:
            st['mmu'][reg - 0x50] = val
        elif reg == 0x08 and val & 0x80:
            st['p7ffd'] &= ~0x20

    def nn():
        p = R[24]
        nextreg(sim.memory[(p + 2) % 65536], sim.memory[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        nextreg(sim.memory[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs, port):
            if port == 0x253B and st['sel'] == 0x1F:    # the raster line: the setup holds the picture for frames
                st['line'] = (st.get('line', -1) + 1) % 312
                return min(st['line'], 255)
            return st['nr'].get(st['sel'], 0) if port == 0x253B else 0xFF

        def write_port(s, regs, port, value, *x):
            st['ports'][port] = value          # last value written to each port (e.g. 0x123B)
            if port == 0x243B:
                st['sel'] = value
            elif port in (0x7FFD, 0x1FFD) and not st['p7ffd'] & 0x20:
                st['p7ffd' if port == 0x7FFD else 'p1ffd'] = value
                b = st['p7ffd'] & 7
                st['mmu'][0:2] = [0xFF, 0xFF]
                st['mmu'][6:8] = [2 * b, 2 * b + 1]
    sim.set_tracer(Tr())
    ops, mem, n = sim.opcodes, sim.memory, 0
    while R[24] != pc_stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            raise RuntimeError('boot did not reach PC %d (at %d)' % (pc_stop, R[24]))
    st['R'], st['mem'] = R, mem
    return st


def boot_check(nex, z80, patch=None):
    """Boot the NEX in the Next model to the snapshot PC: registers, the NEX banks = the (patched) snapshot's, RAM, MMU,
    paging, $8C, alt ROM image 1."""
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = _boot(nex, s.pc, sysrom=rom3())       # the system ROM3 the stub copies first: NextZXOS's
    R, mem = st['R'], st['mem']
    bad = [b for b in st['bad'] if b[0] != 'read of ROM 0']   # the setup copies ROM 0 to alt image 0
    w = lambda h, l: R[h] * 256 + R[l]
    got = [w(2, 3), w(4, 5), w(6, 7), w(0, 1), w(8, 9), w(10, 11), w(18, 19), w(20, 21), w(22, 23),
           w(16, 17), R[12], R[14], R[27], R[26]]
    exp = [s.bc, s.de, s.hl, s.a * 256 + s.f, s.ix, s.iy, s.bc_, s.de_, s.hl_, s.a_ * 256 + s.f_,
           s.sp, s.i, s.im, s.iff1]
    bad += [('register', i, g, e) for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    banks, _, _ = nextboot.load_nex(nex)
    for b in range(8):
        if bytes(banks[b]) != bytes(s.banks[b]):
            bad.append(('NEX bank differs from the (patched) snapshot', b))
    if st['p7ffd'] != s.port7ffd:
        bad.append(('paging', hex(st['p7ffd'])))
    if patch is not None:
        img1 = alt_image(patch)
        if bytes(st['alt'][1]) != bytes(img1):
            bad.append(('alt image 1 differs from the modelled image (NextZXOS ROM3, then the build)',))
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
        if (0x15, 0x01) not in st['nrlog']:
            bad.append(('sprites not enabled',))
        if loaded_palette(st['nrlog']) != list(patch.palette):
            bad.append(('sprite palette differs from the colour map\'s', loaded_palette(st['nrlog']), list(patch.palette)))
    return bad


def loaded_palette(nrlog):
    """The 16 sprite palette entries the setup loads: NextReg 0x41 writes after 0x43 = 0x20 and 0x40 = 0."""
    out, on = [], False
    for i, (reg, val) in enumerate(nrlog):
        if reg == 0x40 and val == 0 and i and nrlog[i - 1] == (0x43, 0x20):
            out, on = [], True
        elif on and reg == 0x41:
            out.append(val)
        elif on and reg in (0x40, 0x43):
            on = False
    return out[:16]


def build(z80, out, name, say=print, outline=True):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    patch = SpellboundPatch(outline=outline)
    spr = os.path.join(out, name + ('_sprites.nex' if outline else '_noring_sprites.nex'))
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, SpellboundPatch(outline=outline))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    say('Colours   : %s' % ('%d colour-map entries' % len(patch.colours) if patch.colours else "no colour map: the game's own colours"))
    return (not bad and not bad2), (plain, spr), patch


def negative_patches():
    """-> [(name, patch)]: broken builds the lockstep must catch."""
    out = []
    base = SpellboundPatch(colours={})
    syms = base.syms

    def page_mod(name, f):
        pc = bytearray(base.page_code)
        f(pc)
        out.append((name, SpellboundPatch(colours={}, page_code=bytes(pc))))

    def rom_mod(name, f):
        rc = bytearray(base.rom_code)
        f(rc)
        out.append((name, SpellboundPatch(colours={}, rom_code=bytes(rc))))

    def at(sym):
        return syms[sym] - PAGE_ORG

    def rom_at(sym):
        return syms[sym] - ROM_ORG

    def rep_page(name, old, new, sym=None, nth=0):
        def f(pc):
            start = at(sym) if sym else 0
            i = -1
            for _ in range(nth + 1):
                i = bytes(pc).find(old, i + 1 if i >= 0 else start)
                if i < 0:
                    raise ValueError('pattern not in the page: %s' % name)
            pc[i:i + len(old)] = new
        page_mod(name, f)

    def rep_rom(name, old, new, sym=None):
        def f(rc):
            start = rom_at(sym) if sym else 0
            i = bytes(rc).find(old, start)
            if i < 0:
                raise ValueError('pattern not in the stubs: %s' % name)
            rc[i:i + len(old)] = new
        rom_mod(name, f)

    # 1 the blit shows the composed box: the original's byte kept
    out.append(('Knight blit from the composed box', SpellboundPatch(colours={}, data_sites=DATA_SITES[1:])))
    # 1b the attribute paint and the ball's XOR left in
    for n, f in (('the Knight paints his cells', [x for x in DATA_SITES if x[0] not in (0xA68A, 0xA696, 0xA6A2)]),
                 ('objects paint their cells', [x for x in DATA_SITES if x[0] not in (0x9502, 0x9508, 0x9511, 0x9517)]),
                 ('characters paint their cells', [x for x in DATA_SITES if x[0] not in (0x7307, 0x7309)]),
                 ('the ball XORs on the ULA', [x for x in DATA_SITES if x[0] not in (0xAB5E, 0xAB63)])):
        out.append((n, SpellboundPatch(colours={}, data_sites=f)))
    # 2 stub leaves DE as the clean blit left it
    rep_rom('DE not put back after the Knight blit', bytes.fromhex('11655D'), bytes.fromhex('000000'), 'e_kn2')
    # 3 A not put back
    rep_rom('A not put back after the Knight blit', bytes.fromhex('3A645D'), bytes.fromhex('000000'), 'e_kn2')
    # 4 cells not restored (first store in c_plot's loop)
    rep_page('plotted cells left on the ULA', bytes.fromhex('DD7E0077'), bytes.fromhex('DD7E0000'), 'c_plot')
    # 5 a stray store into game RAM
    out.append(('hook writes into game RAM', _ram_writer(base)))
    # 6 wrong ink index
    rep_page('wrong ink index', bytes.fromhex('C608'), bytes.fromhex('C607'), 'setcol')
    # 7 black paper transparent: game mask dropped
    rep_page('knocked-out paper not black', bytes.fromhex('3E08'), bytes.fromhex('3E00'), 'build')
    # 8 no outline pass
    rep_page('holes not filled', bytes.fromhex('CD') + syms['fillh'].to_bytes(2, 'little'), bytes(3), 'build')
    rep_page('outline flag ignored', bytes.fromhex('3A0A80B7C8'), bytes.fromhex('3A0A80AFC9'), 'build')
    # 9 wrong X
    rep_page('Knight X off by one', bytes.fromhex('111F0019'), bytes.fromhex('11200019'), 'c_kn')
    # 10 room figures not cleared on a new room
    rep_rom('room build leaves the figures', bytes.fromhex('CD') + syms['c_all'].to_bytes(2, 'little'), bytes(3), 'e_rm')
    # 11 window hides nothing
    rep_rom('window hides nothing', bytes.fromhex('CD') + syms['c_win'].to_bytes(2, 'little'), bytes(3), 'e_wn')
    # 11b smoke, balls
    rep_rom('smoke stays', bytes.fromhex('CD') + syms['c_sx'].to_bytes(2, 'little'), bytes(3), 'e_sx')
    rep_rom('balls not shown', bytes.fromhex('CD') + syms['c_ba'].to_bytes(2, 'little'), bytes(3), 'e_ba')
    # 12 object site missing
    rep_page('objects not built', bytes.fromhex('CD') + syms['build'].to_bytes(2, 'little'), bytes(3), 'c_plot')
    # 13 Knight's attributes: wrong pattern
    rep_page('Knight pattern off by one', bytes.fromhex('8147'), bytes.fromhex('3C47'), 'c_kn')
    # 14 speed left at 28 MHz
    rc = bytearray(base.rom_code)
    i = rc.find(bytes.fromhex('ED910700'), rom_at('e_kn2'))
    rc[i + 3] = 3
    out.append(('speed not restored', SpellboundPatch(colours={}, rom_code=bytes(rc))))
    # 15 slot 4 left mapped
    rc = bytearray(base.rom_code)
    i = rc.find(bytes.fromhex('ED915404'), rom_at('e_kn2'))
    rc[i + 3] = HPG
    out.append(('hook page left mapped', SpellboundPatch(colours={}, rom_code=bytes(rc))))
    # 16 (2026-11-04) the previous build's alt ROM: hooks only, over NextZXOS's ROM3; the lockstep model has no DivMMC
    # trap, so the IM 1 interrupts at the start reach ROM3's handler and its CALL 0x386E
    if next_rom_modelled():         # with Sinclair's ROM standing in for NextZXOS's ROM3 this build is the good one
        out.append(('alt ROM hooks only over ROM3 (previous build)', rom3_left(SpellboundPatch(colours={}))))
    return out


def _ram_writer(base):
    """A hook that stores one byte in game RAM (25000) at each Knight commit."""
    pc = bytearray(base.page_code)
    i = base.syms['c_kn'] - PAGE_ORG
    # the c_kn entry's LD HL,(V_SP) (5 bytes) replaced by a store and a shorter load is not possible in place: use the
    # first instruction of unhide's caller test LD A,(V_HID) = 3A 08 80 + OR A + CALL NZ: rewrite as a RAM store
    j = bytes(pc).find(bytes.fromhex('3A0880B7C4'), i)
    pc[j:j + 3] = bytes.fromhex('32A861')    # LD (25000),A
    return SpellboundPatch(colours={}, page_code=bytes(pc))


def run_negatives(rzx, stop, say=print):
    res = []
    for name, p in negative_patches():
        c, ex, _ = verify(p, rzx, stop=stop, every=1)
        fails = [k for k in c if k.endswith('!')]
        say('Negative  : %-44s %s %s' % (name, 'DETECTED' if fails else 'NOT DETECTED',
                                         (fails[0] if fails else '')))
        res.append((name, bool(fails)))
    return res


class _UPorts:
    def __init__(self, ns):
        self.ns = ns

    def read_port(self, registers, port):
        return 255

    def write_port(self, registers, port, value, offset=0):
        if not self.ns.out(port, value):
            raise ValueError('hook wrote port 0x%04X' % port)


def unit_tests(patch, states, negatives=()):
    """Cases a recording may not reach, run on the hook code in the patched machine model."""
    c = collections.Counter()
    fails = []
    from .simrun import disasm  # noqa: F401

    def fail(k, *info):
        c[k + '!'] += 1
        fails.append((k,) + info)
    from skoolkit.simulator import Simulator
    from . import z80n
    if not states:
        fail('no captured state')
        return c, fails
    for colours, label in (({}, 'plain'), (None, 'colours')):
        for gi, (idx, kind) in enumerate([(3, 1), (11, 1), (39, 1), (69, 0), (70, 0), (72, 0), (81, 0)]):
            for row, col, a in [(7, 0, 0x47), (20, 30, 0x42), (10, 15, 0x06)]:
                if kind == 0 and row > 20:
                    continue
                st = states[0]
                banks = [list(b) for b in st['banks']]
                from skoolkit.pagingtracer import Memory

                class _M:
                    pass
                mem_err = []
                p = SpellboundPatch(colours=colours if colours is not None else synthetic_colours(banks, idx))
                ns = _NS(p)
                ns.H[:] = st['H']
                ns.H[V_HASC] = 1 if p.colours else 0
                ns.attr = [list(x) for x in st['attr']]
                ns.pat[:] = st['pat']
                m = Memory(banks, st['o7ffd'], '128K')
                m.roms = (m.roms[0], list(rom48_image()))
                m.memory[0] = m.roms[1]
                _patched_memory(m, p, ns, mem_err)
                sim = Simulator(m, {})
                z80n.install(sim, ns.nextreg, strict=False)
                sim.set_tracer(_UPorts(ns))
                R = sim.registers
                from .simrun import disasm as _d  # noqa: F401
                # c_plot path: V_A, V_B, V_C, V_K set as the save stub would; screen untouched; run from e_ch2's ENTER
                ns.nr[0x54] = HPG
                ns.H[V_K] = kind
                ns.H[V_A], ns.H[V_A + 1], ns.H[V_A + 2] = idx, row, col
                ns.H[V_NS], ns.H[V_NP] = 0, RFIRST
                for i in range(KSLOT):
                    ns.attr[i] = [0, 0, 0, 0, 0]
                if kind == 0:
                    m[CHCOL] = a
                else:
                    m[OBJCOL] = a
                sp = 0x667C
                ns.H[V_SP], ns.H[V_SP + 1] = sp & 255, sp >> 8
                R[12] = HSTK + 0x8000
                # push a sentinel return
                sent = 0x0000
                R[12] -= 2
                ns.H[R[12] - 0x8000] = sent & 255
                ns.H[R[12] - 0x8000 + 1] = sent >> 8
                R[6], R[7] = 0x70, 0x6F
                R[24] = p.syms['c_plot']
                n = 0
                while R[24] != sent and n < 2000000:
                    sim.opcodes[m[R[24]]]()
                    n += 1
                if R[24] != sent:
                    fail('hook did not return', idx)
                    continue
                exp = {}
                g = lambda a_: m[a_]
                gg, mm = gfx_of(g, idx)
                for (x, y), v in figure_pixels(g, gg, mm, 2, 32 if kind == 0 else 16, a, True, p.colours).items():
                    exp[(col * 8 + x, row * 8 + y)] = v
                lay = {}
                sav = ns.attr[KSLOT:]
                ns.attr[KSLOT:] = [[0, 0, 0, 0, 0]] * (128 - KSLOT)
                lay = ns.sprite_layer()
                ns.attr[KSLOT:] = sav
                if lay != exp:
                    d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
                    fail('unit layer %s' % label, idx, kind, row, col, len(d), sorted(d)[:3], [(lay.get(q), exp.get(q)) for q in sorted(d)[:3]], (min(lay), max(lay)) if lay else None, (min(exp), max(exp)), ns.H[V_NP], ns.H[V_NS])
                for e in mem_err:
                    fail('unit memory', e)
                c['figure cases %s' % label] += 1
    # pool full: figures past the pattern limit are counted, no crash, no pattern overrun
    st = states[0]
    banks = [list(b) for b in st['banks']]
    from skoolkit.pagingtracer import Memory
    p = SpellboundPatch(colours={})
    ns = _NS(p)
    ns.H[:] = st['H']
    m = Memory(banks, st['o7ffd'], '128K')
    m.roms = (m.roms[0], list(rom48_image()))
    m.memory[0] = m.roms[1]
    err = []
    _patched_memory(m, p, ns, err)
    sim = Simulator(m, {})
    z80n.install(sim, ns.nextreg, strict=False)
    sim.set_tracer(_UPorts(ns))
    R = sim.registers
    ns.nr[0x54] = HPG
    ns.H[V_NS], ns.H[V_NP] = 0, RFIRST
    for k in range(50):
        ns.H[V_K] = 1
        ns.H[V_A], ns.H[V_A + 1], ns.H[V_A + 2] = 11, 7 + (k % 15), k % 30
        m[OBJCOL] = 0x46
        ns.H[V_SP], ns.H[V_SP + 1] = 0x7C, 0x66
        R[12] = HSTK + 0x8000 - 2
        ns.H[R[12] - 0x8000] = 0
        ns.H[R[12] - 0x8000 + 1] = 0
        R[6], R[7] = 0x94, 0xE7
        R[24] = p.syms['c_plot']
        n = 0
        while R[24] != 0 and n < 2000000:
            sim.opcodes[m[R[24]]]()
            n += 1
    if ns.H[V_NP] > BPAT:
        fail('patterns overran', ns.H[V_NP])
    c['pool full: dropped tiles counted'] = ns.H[V_DROP]
    c['pool full: patterns used'] = ns.H[V_NP]
    if not ns.H[V_DROP]:
        fail('pool test never filled the pool')
    for e in err:
        fail('pool memory', e)
    # a window's object picture (0x94AD, IX = 25594) runs the same plot site and stays on the ULA, no sprite
    for idx in (11, 30):
        st = states[0]
        res = []
        for patched in (False, True):
            banks = [list(b) for b in st['banks']]
            m = Memory(banks, st['o7ffd'], '128K')
            m.roms = (m.roms[0], list(rom48_image()))
            m.memory[0] = m.roms[1]
            ns = None
            if not patched:                          # the captured state holds the patched sites
                p = SpellboundPatch(colours={})
                for a_, old, new in p.sites:
                    for k_, v_ in enumerate(old):
                        m[a_ + k_] = v_
                for a_, old, new in p.data_sites:
                    m[a_] = old
            if patched:
                p = SpellboundPatch(colours={})
                ns = _NS(p)
                ns.H[:] = st['H']
                ns.attr = [list(x) for x in st['attr']]
                for a_, old, new in p.sites:
                    for k_, v_ in enumerate(new):
                        m[a_ + k_] = v_
                for a_, old, new in p.data_sites:
                    m[a_] = new
                _patched_memory(m, p, ns, err)
            sim = Simulator(m, {})
            if patched:
                z80n.install(sim, ns.nextreg, strict=False)
                sim.set_tracer(_UPorts(ns))
            R = sim.registers
            R[12] = 0x667A
            m[0x667A], m[0x667B] = 0x00, 0x60        # returns to 0x6000: stop there
            R[0], R[2], R[3] = idx, 10, 12           # A = object, B row, C column
            R[24] = 0x94AD
            R[26] = 1
            n = 0
            while R[24] != 0x6000 and n < 500000:
                sim.opcodes[m[R[24]]]()
                n += 1
            if R[24] != 0x6000:
                fail('window picture did not return', patched, hex(R[24]), hex(R[12]), n)
            res.append((bytes(banks[5][:0x1800]), [list(x) for x in ns.attr] if ns else None))
        if res[0][0] != res[1][0]:
            fail('window picture left the ULA', idx)
        if res[1][1] != [list(x) for x in st['attr']]:
            fail('window picture made a sprite', idx)
        c['window pictures on the ULA'] += 1
    return c, fails


def synthetic_colours(banks, idx):
    """A map for unit tests: one nibble painted on each graphics byte of this figure, a clear bit on the next."""
    m = {}
    get = lambda a: banks[0][a - 0xC000] if a >= 0xC000 else (banks[2][a - 0x8000] if a >= 0x8000 else banks[5][a - 0x4000])
    g, mk = gfx_of(get, idx)
    for k in range(16):
        a = g + k
        m['%04X' % a] = [get(a), 0, [2, 0, 0, 3, 0, 0, 0, 0] if k % 2 else [0, 0, 0, 0, 0, 0, 0, 4], 0x08 if k % 3 == 0 else 0]
    # wrong check byte: must be ignored
    a = g + 16
    m['%04X' % a] = [(get(a) + 1) & 255, 0, [5] * 8, 0]
    return m


# ---------------------------------------------------------------------------------------------
# Colour route
# ---------------------------------------------------------------------------------------------

COLOUR_BANKS = tuple([13] + [14 + n for n in range(NSTORE // 2)])
GROUPS = ['Knight', 'Characters', 'Objects', 'Smoke']
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/spellbound_magic_knight_colours.json', 'clear': True,
            'note': 'keys: graphics byte address 0xC000-0xFFFF, store pages 28-43, read at build time per figure'}


def colour_inputs_md5(peek):
    """MD5 of the game bytes the colours belong to: graphics table, characters, objects, the Knight's images."""
    return hashlib.md5(bytes(peek(a) for a in range(GTAB, 0xFFF4))).hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': RECORD, 'engine': 'spellbound_magic_knight', 'keys': 'spellbound-1: %04X graphics byte, bit = stored pixel',
            'inputs': colour_inputs_md5(peek), 'geometry': None}


def nex_peek(nex):
    from .recolour import nex_offsets
    d = bytes(nex)
    off = nex_offsets(d)
    bank = lambda b: d[off[b]:off[b] + 16384]
    ram = {5: bank(5), 2: bank(2), 0: bank(0)}
    return lambda a: ram[5][a - 0x4000] if a < 0x8000 else (ram[2][a - 0x8000] if a < 0xC000 else ram[0][a - 0xC000])


def recolour(nex, cmap):
    """nex bytes + map -> (nex bytes, info): rewrites the store banks and the flag in bank 13 only."""
    from .recolour import nex_offsets, splice
    off = nex_offsets(bytes(nex))
    need = set(COLOUR_BANKS) | {5, 2, 0, 10, 12}
    setup = bytes.fromhex(load_profile()['hooks']['setup'])
    if not need <= set(off):
        raise ValueError('not a Spellbound sprite build: banks %s missing' % sorted(need - set(off)))
    prof = load_profile()
    peek = nex_peek(nex)
    want = prof.get('colour_inputs')
    if want != colour_inputs_md5(peek):
        raise ValueError('game graphics differ from the expected snapshot (%s, expected %s)' % (colour_inputs_md5(peek), want))
    d = bytes(nex)
    bank = lambda b: d[off[b]:off[b] + 16384]
    p0 = SpellboundPatch(prof, colours={})
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    b12 = bank(12)
    lo, hi = p0.regblock - 0x2000, p0.regblock - 0x2000 + 20
    if b12[:lo] != bytes(p0.page[:lo]) or b12[hi:8192] != bytes(p0.page[hi:8192]):
        raise ValueError("hook code differs from this version's (rebuild with nexclash.py auto)")
    b13 = bytes(bank(13))
    if b13[PAGE_ORG - 0x8000:] != bytes(p0.hpage[PAGE_ORG - 0x8000:]):
        raise ValueError("hook page differs from this version's (rebuild with nexclash.py auto)")
    b10 = bytearray(bank(10))
    if bytes(b10[0x1000:0x1000 + len(setup)]) != setup:
        raise ValueError("setup routine differs from this version's (rebuild with nexclash.py auto)")
    p = SpellboundPatch(prof, colours=cmap)
    b10[0x1000 + len(setup):0x1000 + len(setup) + 16] = bytes(p.palette)
    nb = {b: p.extra_banks[b] for b in COLOUR_BANKS}
    nb[10] = bytes(b10)
    out, changed = splice(nex, nb)
    return out, {'banks changed': changed, 'colour-map entries': len([k for k in cmap if k != 'palette']),
                 'palette': 'the map\'s' if 'palette' in cmap else 'the game\'s'}


def sheet_part(get, g, m, wb, h, attr, pid, group, frame):
    """A figure -> a coloursheet part: every bit of its graphics bytes (clear bits code 0); default colours as drawn."""
    ink = ink_index(attr)
    pixels, entries = [], {}
    for y in range(h):
        for bx in range(wb):
            a = g + y * wb + bx
            v, mk = get(a), get(m + y * wb + bx)
            key = '%04X' % a
            entries.setdefault(key, [v, 1])
            for b in range(8):
                bit = 0x80 >> b
                code = 1 if v & bit else (0 if mk & bit else 2)
                dflt = ink if code == 1 else (CBLACK if code == 2 else 0)
                pixels.append((bx * 8 + b, y, key, b, code, dflt))
    return dict(id=pid, size=h, w=8 * wb, h=h, x=0, y=0, mir=0, group=group, fam=(frame, pid), role=None, pixels=pixels, entries=entries)


def capture(figures, peek):
    """figures: [(kind, idx, attr)], every graphic the recordings plotted; the Knight's eight images added."""
    from . import coloursheet as cs
    col = cs.Collector(family=lambda p: p['fam'])
    f = 0
    for i in range(8):
        f += 1
        col.add_frame([sheet_part(peek, 0xF9F4 + 96 * i, 0xFCF4 + 96 * i, 3, 32, 0x47, ('K', i), 'Knight', f)])
    for kind, idx, attr in figures:
        f += 1
        g, m = gfx_of(peek, idx)
        col.add_frame([sheet_part(peek, g, m, 2, {0: 32, 1: 16, 2: 24}[kind], attr, ('F', kind, idx), ('Characters', 'Objects', 'Smoke')[kind], f)])
    return col


def sheets(col, prefix, peek, colours=None):
    """<prefix>_PAINTING_SPRITES.png and <prefix>_REFERENCE_ALL_SPRITES.png with their layouts."""
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    comps = list(col.comps.values())
    ident = colour_identity(peek)
    res = []
    paint = cs.choose(comps, col.maxsize, GROUPS)
    png = prefix + '_PAINTING_SPRITES.png'
    res.append((png, cs.write(paint, png, prefix + '_PAINTING_SPRITES_layout.json', rgb16, colours or {}, unique=False, paint_clear=True, identity=ident)))
    full = sorted(comps, key=lambda c: (GROUPS.index(c['group']) if c['group'] in GROUPS else 99, str(c['parts'][0]['id'])))
    png = prefix + '_REFERENCE_ALL_SPRITES.png'
    res.append((png, cs.write(full, png, prefix + '_REFERENCE_ALL_SPRITES_layout.json', rgb16, colours or {}, unique=False, paint_clear=True, identity=ident)))
    return res


ENHANCED = os.path.join(_HERE, '..', 'docs', 'profiles', 'spellbound_magic_knight_enhanced.json')   # pilot work/enh.json
NEG_RUNS = (('t1.rzx', 1400), ('t_balls.rzx', None), ('t_chars.rzx', None))   # each negative: until one detects it


def _vjob(z80, rzx, enhanced, stop):
    p = SpellboundPatch(colours=load_colours(ENHANCED)) if enhanced else SpellboundPatch()
    c, ex, _ = verify(p, rzx, stop=stop, every=4)
    return dict(c), {k: str(v)[:400] for k, v in ex.items()}


def _njob(k, runs):
    name, p = negative_patches()[k]
    for rz, stop in runs:
        c, ex, _ = verify(p, rz, stop=stop, every=1)
        f = [x for x in c if x.endswith('!')]
        if f:
            return name, (os.path.basename(rz), f[0])
    return name, None


def _palette_negatives(z80, sprites_nex, rzxs, tmp):
    """The Enhanced set's own palette (pilot work/enh2/neg_palette.py): caught by the boot check (the palette the setup
    loads), by the engine refusing the map, or by the verifier (a figure in its own ink in an entry the set changed)."""
    from . import z80tonex as zt
    from .recolour import nex_offsets
    cm = load_colours(ENHANCED)
    T = os.path.join(tmp, 'negpal.nex')
    res = []
    p = SpellboundPatch(colours=cm)
    p.stub_extra = p.stub_extra[:-16] + bytes(PALETTE)
    zt.convert(z80, T, quiet=True, patch=p)
    res.append(('Enhanced palette not loaded', bool(boot_check(T, z80, SpellboundPatch(colours=cm)))))
    p = SpellboundPatch(colours=cm)
    e = bytearray(p.stub_extra)
    e[-16 + 2] ^= 1
    p.stub_extra = bytes(e)
    zt.convert(z80, T, quiet=True, patch=p)
    res.append(('skin entry wrong by one bit', bool(boot_check(T, z80, SpellboundPatch(colours=cm)))))
    out, _ = recolour(open(sprites_nex, 'rb').read(), cm)
    off = nex_offsets(out)
    b10 = bytearray(out[off[10]:off[10] + 16384])
    setup = len(bytes.fromhex(load_profile()['hooks']['setup']))
    b10[0x1000 + setup:0x1000 + setup + 16] = bytes(PALETTE)
    open(T, 'wb').write(out[:off[10]] + bytes(b10) + out[off[10] + 16384:])
    res.append(('recolour without the palette bank', bool(boot_check(T, z80, SpellboundPatch(colours=cm)))))
    for i, v in ((6, 0x6D), (15, 0xB6), (8, 0x24)):
        m = dict(cm)
        pal = list(cm['palette'])
        pal[i] = v
        m['palette'] = pal
        try:
            SpellboundPatch(colours=m)
            res.append(('map changes palette entry %d' % i, False))
        except ValueError:
            res.append(('map changes palette entry %d' % i, True))
    global PAL_FREE
    old = PAL_FREE
    PAL_FREE = (1, 2, 3, 4, 5, 6)
    m = dict(cm)
    pal = list(cm['palette'])
    pal[6] = 0x6D
    m['palette'] = pal
    try:
        p = SpellboundPatch(colours=m)
    finally:
        PAL_FREE = old
    hit = False
    for rz in [r for r in rzxs if os.path.basename(r) in ('t1.rzx', 't_rooms.rzx')] or rzxs[:1]:
        c, _, _ = verify(p, rz, every=4)
        if any(x.endswith('!') for x in c):
            hit = True
            break
    res.append(('an object shown in a changed entry (guard widened)', hit))
    return res


def auto(a, z80, name, out, say):
    """Plain, default sprite and Enhanced builds (the Enhanced colour map: ENHANCED) with boot checks; lockstep of both
    sets on every recording (in parallel), unit tests, the negatives (each on t1 1400 frames, then t_balls, then
    t_chars, until one detects it) and the Enhanced palette negatives. Build input: rzx/s0.z80 (the archive's file
    stepped from PAUSE 0 to PC 0x6803; games/spellbound_magic_knight.md Inputs)."""
    import concurrent.futures as cf
    import tempfile
    from . import z80tonex as zt, nextboot
    ok, (plain, spr), patch = build(z80, out, name, say)
    enh = os.path.join(out, name + '_enhanced.nex')
    cm = load_colours(ENHANCED)
    zt.convert(z80, enh, quiet=True, patch=SpellboundPatch(colours=cm))
    bad = boot_check(enh, z80, SpellboundPatch(colours=cm))
    ok = ok and not bad
    say('Enhanced  : %s  %s  boot %s' % (os.path.basename(enh), hashlib.md5(open(enh, 'rb').read()).hexdigest(),
                                         'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    say('ROM model : %s' % nextboot.rom_model())
    rzxs = list(a.rzx or [])
    quick = getattr(a, 'quick', None)
    good = ok
    if rzxs:
        by = {os.path.basename(r): r for r in rzxs}
        runs = [(by[n], s) for n, s in NEG_RUNS if n in by] or [(rzxs[0], 3000)]
        negs = negative_patches()
        with cf.ProcessPoolExecutor(min(24, os.cpu_count() or 4)) as ex:
            vf = [(r, e, ex.submit(_vjob, z80, r, e, quick)) for e in (False, True) for r in rzxs]
            nf = [ex.submit(_njob, k, runs) for k in range(len(negs))]
            c, exs, states = verify(patch, rzxs[0], stop=500, collect=2, every=50)
            u, f = unit_tests(patch, states)
            say('Unit      : %s %s' % ('PASS' if not f else 'FAILED', ' '.join('%s=%s' % kv for kv in sorted(u.items()))))
            for x in f[:6]:
                say('  ' + str(x)[:300])
            good = good and not f
            pn = _palette_negatives(z80, spr, rzxs, tempfile.mkdtemp(prefix='sb_'))
            for r, e, fu in vf:
                c, exs = fu.result()
                fails = [k for k in c if k.endswith('!')]
                say('Verify    : %s %s %s %s' % (os.path.basename(r), 'Enhanced' if e else 'default', 'IDENTICAL' if not fails
                                                 else 'FAILED', ' '.join('%s=%s' % (k, v) for k, v in sorted(c.items()))))
                for k in fails:
                    say('  %s %s' % (k, exs.get(k[:-1], '')))
                good = good and not fails
            n_ok = 0
            for fu in nf:
                nm, hit = fu.result()
                n_ok += bool(hit)
                say('Negative  : %-44s %s %s' % (nm, 'DETECTED' if hit else 'NOT DETECTED', hit or ''))
        if not next_rom_modelled():
            say("Negative  : alt ROM hooks only over ROM3 (previous build): not run, NextZXOS's ROM3 not modelled "
                "(set NEXCLASH_NEXT_ROM)")
        say('Negative  : %d/%d DETECTED' % (n_ok, len(negs)))
        for nm, hit in pn:
            say('Negative  : Enhanced palette: %-38s %s' % (nm, 'DETECTED' if hit else 'NOT DETECTED'))
        say('Negative  : Enhanced palette %d/%d DETECTED' % (sum(h for _, h in pn), len(pn)))
        good = good and n_ok == len(negs) and all(h for _, h in pn)
    say('Result    : %s' % ('PASSED' if good else 'FAILED'))
    return good
