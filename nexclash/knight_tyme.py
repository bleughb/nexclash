"""Knight Tyme (Mastertronic Added Dimension 1986, 128K edition) engine 'knight_tyme'. Additive module: reachable only
through is_knight_tyme(). Game facts and decisions: games/knight_tyme.md.

  Snapshot: title menu, PC in RAM, 7FFD = 0x10 (ROM 1, bank 0), IM 2 (0xFFFF -> JR via ROM 0x0000 -> 0xFFF4 -> 0xAF10).
  Knight: composed box blitted by 0xACBB at 0xAD54; characters and objects: masked cell plots in the room build,
  before the screen is copied to bank 7 as the room's clean copy. Everything is replaced by sprites; game code runs
  the same instructions in the same order, so the verifier runs original and patched machines in lockstep over the
  recording, hook instructions not counted, and compares the whole 128K every frame.
"""
import collections
import copy
import hashlib
import json
import os

RECORD = 'knight_tyme'
SIG = (0xAD54, bytes.fromhex('cdbbac'))
SIG2 = (0x8F84, bytes.fromhex('fdcb41ce0832acb2'))
ROM_ORG = 0x386E
ALT_PAGE, HPG, GP4, GP5, STORE, NSTORE = 24, 26, 4, 5, 28, 16
KSLOT = 122
RFIRST = 48
V_SP, V_K, V_A, V_NS, V_NP, V_HID, V_HASC, V_OL, V_DROP = 0, 2, 3, 6, 7, 8, 9, 10, 11
SPRTAB, CACHE = 0x100, 0x500
HSTK = 0x1440
PAGE_ORG = 0x9440
CBLACK, CWHITE = 8, 15
# index 0 transparent, 1-7 colours, 8 black, 9-15 bright colours
# index 2 is skin for the Bridge's crew: no figure's attribute has ink 2 without bright (checked by verify and at build)
CSKIN = 2
PALETTE = [0x00, 0x02, 0xF5, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
SITES = [  # (addr, original, kind, symbol)
    (0xAD54, 'cdbbac', 'cd', 'e_kn'),
    (0x706C, 'cd0fb3', 'cd', 'e_ch'),
    (0x941E, 'cd0ab3', 'cd', 'e_ob'),
    (0x6D7E, '3abc61', 'c3', 'e_rm'),
    (0x8FB8, 'cd0390', 'cd', 'e_wn'),
    (0x9218, '210000', 'c3', 'e_wp'),
    (0x6F0A, 'cdcc93', 'cd', 'e_ov'),
]
DATA_SITES = [(0xACBC, 0x05, 0x65), (0x6892, 0x01, 0x00)]
TABLE_CHECK = ((38986, bytes.fromhex('00170614')),)      # first entry of the window table
SCREEN_PIX = (0x4000, 0x5800)
GTAB = 0xC544
LINES = 0x6680
KX, KY, KSHIFT, KFACE, KCOL = 25694, 25157, 25159, 25697, 25162
OBJCOL, CHCOL = 23695, 0x7086
BLIT_SPAN = (0xACBB, 0xACE4)
PLOT_SPAN = (0xB30A, 0xB36C)
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'knight_tyme_colours.json')
# Figures whose ink index is white take a black ring; the rest a white one.
CMP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27]
# Bytes allowed to differ between original and patched: the pictures and the buffers built from them.
EXCL_B5 = [(0x0000, 0x1800), (0x5D05 - 0x4000, 0x5DC5 - 0x4000), (0x64E0 - 0x4000, 0x6540 - 0x4000)]
EXCL_B7 = [(0x2000, 0x3800)]      # 0xE000-0xF7FF: the room's clean copy


def is_knight_tyme(snap):
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


def store_pages(colours):
    """Colour map -> NSTORE pages: 8 bytes per address 0xC000-0xFFFF: [1, check, 4 nibble bytes, clear mask, 0]."""
    st = bytearray(NSTORE * 8192)
    for k, e in (colours or {}).items():
        a = int(k, 16)
        if not 0xC000 <= a <= 0xFFFF:
            continue
        i = a - 0xC000
        nib = e[2]
        st[8 * i:8 * i + 8] = bytes([1, e[0] & 255] + [nib[2 * n] << 4 | nib[2 * n + 1] for n in range(4)] +
                                    [e[3] if len(e) > 3 else 0, 0])
    return bytes(st)


class KnightTymePatch:
    name = 'Knight Tyme figures -> hardware sprites (alt ROM stubs, page 26 at slot 4, plots undone, room copy clean)'

    def __init__(self, prof=None, colours=None, rom_code=None, page_code=None, outline=True, sites=None, data_sites=None,
                 crew=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.page_code = page_code if page_code is not None else bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup']) + bytes(PALETTE)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.colours = dict(colours) if colours is not None else load_colours_build()
        self.outline = outline
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock != self.syms['rom_end']:
            raise ValueError('hook code length differs from the profile symbols')
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hooks reach 0x3D00')
        self.slot1 = (ALT_PAGE, self.regblock)
        # The WHOLE alt ROM image comes from the build: Sinclair's 48K ROM + hooks (2026-11-04, altrom_audit). The Next's
        # stub fills image 1 from the system ROM3 first, which is NextZXOS's: its IM 1 handler CALLs 0x386E (0x004A) and
        # its UDG print JPs to 0x387E (0x0B52), both into these hooks, and this game's IM 2 handler jumps to 0x0038.
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
        self.crew = None
        if self.prof.get('overlay') and (crew or _CREW.get('tiles')):
            self._put_crew(crew or _CREW['tiles'])
        self.store = store_pages(self.colours)
        self.sites = []
        for a, old, op, sym in (sites if sites is not None else SITES):
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(op) + self.syms[sym].to_bytes(2, 'little')))
        self.data_sites = list(data_sites if data_sites is not None else DATA_SITES)
        self._banks()

    def _put_crew(self, tiles):
        """The crew tiles (crew_tiles(): from the player's game) -> page 27 at 0x2000: count, sum, positions, pixels."""
        o, ov = 0x2000, self.prof['overlay']
        self.hpage[o] = len(tiles)
        self.hpage[o + 1], self.hpage[o + 2] = ov['sum'] & 255, ov['sum'] >> 8
        for i, (x, y, data) in enumerate(tiles):
            self.hpage[o + 0x10 + 4 * i:o + 0x14 + 4 * i] = bytes([x & 255, x >> 8, y & 255, y >> 8])
            self.hpage[o + 0x100 + 128 * i:o + 0x180 + 128 * i] = data
        self.crew = tiles

    def set_crew(self, tiles):
        self._put_crew(tiles)
        self._banks()

    def _banks(self):
        low = getattr(self, 'altrom_low', None)
        self.extra_banks = {12: bytes(self.page) + (low[1] if low else bytes(8192)), 13: bytes(self.hpage)}
        for n in range(NSTORE // 2):
            self.extra_banks[14 + n] = self.store[16384 * n:16384 * (n + 1)]

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.port7ffd & 7 != 0:
            raise ValueError('Knight Tyme patch expects the 128K snapshot (7FFD bank 0)')
        if self.prof.get('overlay') and self.crew is None:
            self.set_crew(crew_tiles(snap, self.prof))
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
        for a, s in TABLE_CHECK:
            for k, v in enumerate(s):
                b, o = where(a + k)
                if ram[b][o] != v:
                    raise ValueError('window table differs at 0x%04X' % (a + k))
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


def gfx_of(get, idx):
    t = GTAB + 4 * idx
    return get(t) + 256 * get(t + 1), get(t + 2) + 256 * get(t + 3)


def knight_state(get):
    """What the commit at 0xAD54 shows: image, column, line, colour."""
    return dict(i=(get(KSHIFT) & 3) + (4 if get(KFACE) else 0), col=get(KX), y=get(KY), attr=get(KCOL))


def knight_addrs(kn):
    return 0xF3F4 + 96 * kn['i'], 0xF6F4 + 96 * kn['i']


def overlay_pixels(tiles):
    """The crew (crew_tiles()): {(x, y): index} on the screen."""
    out = {}
    for x0, y0, b in tiles:
        for y in range(16):
            for x in range(16):
                v = b[y * 8 + x // 2]
                v = v >> 4 if x % 2 == 0 else v & 15
                if v:
                    out[(x0 - 32 + x, y0 - 32 + y)] = v
    return out


def overlay_sum(b5):
    t = 0
    for y in range(144, 168):
        a = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        t += sum(b5[a + 9:a + 24])
    return t & 0xFFFF


# The Bridge's two seated crew (room 1) are scenery the hook covers with sprite tiles. The tiles are derived from the
# player's own game at build time (no game graphics in this repository): room 1 is built from the snapshot in a
# simulator (0x6D7B with A = 1, 25020 nonzero: the room build without the room-entry message) up to the overlay site
# 0x6F0A, then the crew's pixels are read from that screen: each head flood-filled from a seed in its box and the hands
# on lines 148-151 skin (index 2); the ink of the shoulders' cyan cells (lines 152-159) white. The cells' sum and the
# tiles' MD5 must be the profile's (the approved build's), or the build refuses.
CREW_SEATS = (((87, 150), (80, 94, 145, 158), ((72, 78), (98, 107)), (80, 95)),
              ((168, 150), (161, 175, 145, 158), ((149, 157), (178, 184)), (160, 175)))
CREW_STEPS = 2000000           # instructions allowed for the room build (it takes about 94,000)
_CREW = {}                     # tiles already derived in this process (only ever the pinned MD5's)


def crew_md5(tiles):
    return hashlib.md5(b''.join(bytes([x & 255, x >> 8, y & 255, y >> 8]) + d for x, y, d in tiles)).hexdigest()


def _crew_from_screen(s):
    def ink(x, y):
        return bool(s[(((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)) + x // 8] & (0x80 >> (x % 8)))
    pix = {}
    for seed, hb, hands, cols in CREW_SEATS:
        head, todo = set(), [seed]
        while todo:
            x, y = todo.pop()
            if (x, y) in head or not (hb[0] <= x <= hb[1] and hb[2] <= y <= hb[3]) or not ink(x, y):
                continue
            head.add((x, y))
            todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        for p in head:
            pix[p] = CSKIN
        for a, b in hands:
            for y in range(148, 152):
                for x in range(a, b + 1):
                    if ink(x, y):
                        pix[(x, y)] = CSKIN
        for y in range(152, 160):
            for x in range(cols[0], cols[1] + 1):
                if ink(x, y) and (x, y) not in head:
                    pix[(x, y)] = CWHITE
    tiles = {}
    for (x, y), v in pix.items():
        tx, ty = (x - 72) // 16, (y - 144) // 16
        tiles.setdefault((tx, ty), {})[(x - 72 - tx * 16, y - 144 - ty * 16)] = v
    out = []
    for (tx, ty), d in sorted(tiles.items()):
        b = bytearray(128)
        for (x, y), v in d.items():
            b[y * 8 + x // 2] |= v << 4 if x % 2 == 0 else v
        out.append((72 + tx * 16 + 32, 144 + ty * 16 + 32, bytes(b)))
    return out


def _room_machine(snap):
    """A simulator on a copy of the game: a skoolkit snapshot (a recording's) or a z80tonex one (the build's)."""
    if hasattr(snap, 'banks') and isinstance(snap.banks, dict):
        from skoolkit.pagingtracer import Memory
        from skoolkit.simulator import Simulator
        m = Memory([list(snap.banks[b]) for b in range(8)], snap.port7ffd, '128K')
        m.roms = (m.roms[0], list(rom48_image()))
        m.memory[0] = m.roms[1 if snap.port7ffd & 16 else 0]
        return Simulator(m, {'SP': snap.sp, 'IY': snap.iy, 'IX': snap.ix}, config={'int_active': 0}), snap.port7ffd
    return game_machine(snap), snap.out7ffd


def crew_tiles(snap, prof=None):
    """The game's snapshot -> the crew tiles [(x, y, 128 bytes)] (sprite coordinates), checked against the profile."""
    ov = (prof or load_profile())['overlay']
    sim, o7ffd = _room_machine(snap)

    class _P:
        o = o7ffd

        def read_port(self, registers, port):
            return 255

        def write_port(self, registers, port, value, offset=0):
            if port & 0x8002 == 0 and self.o & 32 == 0:
                sim.memory.out7ffd(value)
                self.o = value
    sim.set_tracer(_P())
    m, R, ops = sim.memory, sim.registers, sim.opcodes
    m[23701], m[25020] = ov['room'], 2
    R[24], R[0], R[26] = 0x6D7B, ov['room'], 0
    n = 0
    while R[24] != 0x6F0A:
        if n >= CREW_STEPS:
            raise ValueError('the Bridge (room %d) did not build from this snapshot in %d instructions: no crew tiles'
                             % (ov['room'], CREW_STEPS))
        if m[R[24]] == 0x76:             # HALT: no interrupts here
            R[24] += 1
        else:
            ops[m[R[24]]]()
        n += 1
    b5 = bytes(m.banks[5]) if hasattr(m, 'banks') else bytes(m[0x4000 + a] for a in range(0x1B00))
    got = overlay_sum(b5)
    if got != ov['sum']:
        raise ValueError('the Bridge builds with crew cells unlike the approved game (sum %d, expected %d)' % (got, ov['sum']))
    tiles = _crew_from_screen(b5)
    if crew_md5(tiles) != ov['tiles_md5']:
        raise ValueError('crew tiles from this game (MD5 %s) differ from the approved build\'s (%s)'
                         % (crew_md5(tiles), ov['tiles_md5']))
    _CREW['tiles'] = tiles
    return tiles


def crew_from_hpage(b13, prof=None):
    """A sprite build's page 27 -> its crew tiles, checked against the profile (recolour keeps the build's own)."""
    o = 0x2000
    tiles = [(b13[o + 0x10 + 4 * i] | b13[o + 0x11 + 4 * i] << 8, b13[o + 0x12 + 4 * i] | b13[o + 0x13 + 4 * i] << 8,
              bytes(b13[o + 0x100 + 128 * i:o + 0x180 + 128 * i])) for i in range(b13[o])]
    if crew_md5(tiles) != (prof or load_profile())['overlay']['tiles_md5']:
        raise ValueError("crew tiles in this build differ from the approved build's (rebuild with nexclash.py auto)")
    return tiles


def use_game(path):
    """Derive the crew tiles once in this process (a worker's negatives are built before their recording runs)."""
    if not _CREW.get('tiles'):
        if path.lower().endswith('.rzx'):
            crew_tiles(_frames(path)[0][0])
        else:
            from . import z80tonex as zt
            crew_tiles(zt.Z80Snapshot(path))
    return _CREW['tiles']


def expected_layer(get, plots, kn, colours=None, outline=True):
    """Plots in plot order (kind 0 char, 1 object; idx, row, col, attr), then the Knight: {(x, y): index}, and a code per
    pixel: 'i' ink, 'k' knocked-out black, 'r' ring over nothing, 'R' ring over a lower figure."""
    lay, code = {}, {'rings': set()}

    def add(g, m, wb, h, attr, x0, y0):
        solid = figure_pixels(get, g, m, wb, h, attr, False, colours)
        ink = ink_index(attr)
        for (x, y), v in (figure_pixels(get, g, m, wb, h, attr, outline, colours)).items():
            k = (x0 + x, y0 + y)
            if (x, y) in solid:
                bx, b = x // 8, x % 8
                code[k] = 'i' if get(g + y * wb + bx) & (0x80 >> b) else 'k'
            else:
                code[k] = 'R' if code.get(k) in ('i', 'k', 'R', 'o') else 'r'
                code['rings'].add(k)
            lay[k] = v
    for p in plots:
        if p['kind'] == 2:
            for k, v in p['pixels'].items():
                lay[k], code[k] = v, 'o'
            continue
        g, m = gfx_of(get, p['idx'])
        add(g, m, 2, 32 if p['kind'] == 0 else 16, p['attr'], p['col'] * 8, p['row'] * 8)
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
        self.sel = None                     # NextREG selected at port 0x243B (HLIB_SPEED_IN reads NR 7)

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x243B:
            self.sel = val
            return True
        if port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
            return True
        if port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
            return True
        return False

    def nr_read(self):
        """Port 0x253B: the selected NextREG; NR 7 as the core composes it (bits 5:4 actual, 1:0 programmed)."""
        if self.sel == 0x07:
            sp = self.nr.get(0x07, 0) & 3
            return sp << 4 | sp
        return self.nr.get(self.sel, 0)

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
    """The build before 2026-11-04 (published ced9c858): only the hook bytes 0x386E.. written over NextZXOS's ROM3"""
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
        if port == 0x253B and self.ns is not None and self.ns.sel is not None:
            return self.ns.nr_read()        # a hook reading NR 7 (HLIB_SPEED_IN): no recorded input consumed
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
    hp2 = bytes(patch.hpage[0x2000:])
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
                if nr[0x55] == HPG + 1:
                    return hp2[a - 0xA000]
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


# ---------------------------------------------------------------------------------------------
# Differential verification: lockstep over the recording
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=4, colours_model=None):
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
        if patch.prof.get('overlay') and patch.crew is None:
            patch.set_crew(crew_tiles(snap, patch.prof))
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
        hookT = [0]
        win = [None]
        rec = {'commits': 0}
        code_bytes = {a + k: None for a, old, new in patch.sites for k in range(len(old))}
        code_bytes.update({a: None for a, _, _ in patch.data_sites})

        def in_hook(pc):
            return lo <= pc < hi or (0x8000 <= pc < 0xA000 and nr[0x54] == HPG)

        def before_game(pc):
            """A patch site or a checkpoint is about to run in the patched machine."""
            if pc == 0x706C or pc == 0x941E:
                if not Rp[26]:
                    fail('interrupts off at a figure site', hex(pc))
                if pc == 0x941E and Rp[8] * 256 + Rp[9] == 25568 or (pc == 0x941E and Rp[9] * 256 + Rp[8] == 25568):
                    c['object pictures left in a window'] += 1
                    return
                kind = 0 if pc == 0x706C else 1
                g = mp
                st['cells'] = _cells(mp.banks[5], Rp[2], Rp[3], 32 if kind == 0 else 16)
                st['cells_at'] = (Rp[2], Rp[3], 32 if kind == 0 else 16)
                attr = g[CHCOL] if kind == 0 else g[OBJCOL]
                plots.append(dict(kind=kind, idx=Rp[0], row=Rp[2], col=Rp[3], attr=attr))
                if ink_index(attr) == CSKIN:
                    fail('a figure has the ink the crew\'s skin replaced', attr)
                c['plots %s' % ('character' if kind == 0 else 'object')] += 1
                st.setdefault('idx', collections.Counter())[(kind, Rp[0], attr)] += 1
            elif pc in (0x706F, 0x9421):
                # the plot ran and the hook put the cells back: the ULA is as the plot found it
                if st.get('cells') is not None:
                    if _cells(mp.banks[5], *st['cells_at']) != st['cells']:
                        fail('a plot left pixels on the ULA', st['cells_at'])
                    c['plots undone checks'] += 1
                    st['cells'] = None
            elif pc == 0xAD54:
                if not Rp[26]:
                    fail('interrupts off at the Knight site')
                c['commits'] += 1
                rec['commits'] += 1
                rec['kn'] = knight_state(lambda a: mp[a])
                st['ktypes'] = st.get('ktypes', set()) | {rec['kn']['i']}
            elif pc == 0x6F0A:
                if not Rp[26]:
                    fail('interrupts off at the overlay site')
                if mp[23701] == patch.prof['overlay']['room']:
                    # the Bridge's scenery is fixed: its crew cells must match the profile, or the crew would silently
                    # go without tiles in the hook and in this model alike
                    if overlay_sum(mp.banks[5]) != patch.prof['overlay']['sum']:
                        fail('the Bridge built with crew cells unlike the profile', overlay_sum(mp.banks[5]))
                    else:
                        plots.append(dict(kind=2, pixels=overlay_pixels(patch.crew)))
                        c['crew overlays'] += 1
                        if len(ex['crew overlay frames']) < 20:
                            ex['crew overlay frames'].append(st['frame'])
            elif pc == 0x6D7E or pc == 0x9218:
                plots.clear()
                c['room builds' if pc == 0x6D7E else 'wipes'] += 1
            elif pc == 0x8FB8:
                if not Rp[26]:
                    fail('interrupts off at the window site')
                c['windows'] += 1
                win[0] = (mp[25765], mp[25766], mp[25767], mp[25768])
            elif pc == 0x9003 and win[0] is not None:
                # the hook has just run: no tile that touches the window is shown
                l, t, r_, b = win[0]
                win[0] = None
                if 'kn' in rec:
                    lay = ns.sprite_layer()
                    _, code = expected_layer(lambda a: mp[a], plots, rec['kn'], patch.colours, patch.outline)
                    for (x, y) in lay:
                        # a figure's outside ring may touch a window by one pixel; nothing else may be on it
                        if l * 8 <= x <= r_ * 8 + 7 and t * 8 <= y <= b * 8 + 7 and (x, y) not in code['rings']:
                            fail('a sprite shows over a window', x, y, (l, t, r_, b))
                            break
                c['window hide checks'] += 1
                st['hidden'] = True

        def hook_exit(pc, r0):
            """Back in game code: every register as the hook found it, but for what the displaced code sets."""
            want = list(r0)
            if pc == 0xAD57:                         # as the original's blit from 0x5D05 ends
                want[4], want[5] = 0x5D, 0x65
                want[0] = mp[0x5D64]
            elif pc == 0x6D81:
                want[0] = mp[25020]
            elif pc == 0x921B:
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
        WATCH = site_set | {0x9003, 0x706F, 0x9421}

        def compare_memory():
            bad = []
            sp0 = Rp[12]
            # dead stack; in a blit or a plot the live return word is the hook's, so a little above SP as well
            dead = (sp0 - 64, sp0 + (16 if BLIT_SPAN[0] <= pcp <= BLIT_SPAN[1] or PLOT_SPAN[0] <= pcp <= PLOT_SPAN[1] else 0))
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
            if in_hook(pc) or BLIT_SPAN[0] <= pc <= BLIT_SPAN[1] or PLOT_SPAN[0] <= pc <= PLOT_SPAN[1] or pc in (0xAD57,):
                c['register checks skipped in a blit or plot'] += 1
                return
            for i in CMP:
                if Ro[i] != Rp[i]:
                    if i == 0 and (0x706F <= pc <= 0x7074 or 0x9421 <= pc <= 0x9423):
                        continue   # A after a plot: the next instructions reload it
                    if i == 1 and (0x706F <= pc <= 0x7074 or 0x9421 <= pc <= 0x9423):
                        continue
                    fail('registers differ', hex(pc), i, Ro[i], Rp[i])
            if Ro[24] != Rp[24]:
                fail('PC differs', hex(Ro[24]), hex(Rp[24]))
            if Ro[12] != Rp[12]:
                fail('SP differs', hex(Ro[12]), hex(Rp[12]))

        def stable_check():
            """Between commits: the original's screen = the ULA + the sprites, pixel for pixel."""
            lay = ns.sprite_layer()
            exp, code = expected_layer(lambda a: mp[a], plots, rec['kn'], patch.colours, patch.outline)
            c['layer checks'] += 1
            c['sprite pixels compared'] += len(exp)
            if lay != exp:
                d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
                fail('sprite layer differs from the figures', len(d), sorted(d)[:3], [(lay.get(k), exp.get(k)) for k in sorted(d)[:3]])
            # the crew on their own: every crew pixel the model calls for is in the sprite layer, in its colour
            for p in plots:
                if p['kind'] == 2:
                    c['crew layer checks'] += 1
                    miss = [k for k, v in p['pixels'].items() if lay.get(k) != v and code.get(k) == 'o']
                    if miss:
                        fail('crew tiles missing or wrong in the sprite layer', len(miss), sorted(miss)[:3])
            bo, bp = mo.banks[5], mp.banks[5]
            b = 0
            where = []
            for y in range(192):
                base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
                for cx in range(32):
                    o, p = bo[base + cx], bp[base + cx]
                    for i in range(8):
                        k = code.get((cx * 8 + i, y))
                        if k == 'R':
                            continue
                        bit = 0x80 >> i
                        if k is None or k == 'r':
                            good = not (o ^ p) & bit
                        elif k == 'o':               # the crew's tiles recolour ULA ink, in both screens
                            good = bool(o & bit) and bool(p & bit)
                        elif patch.colours:
                            good = True
                        elif k == 'k':
                            good = not o & bit
                        else:
                            good = bool(o & bit)
                        if not good:
                            b += 1
                            where.append((cx * 8 + i, y, k))
            # the figures are not on the ULA: under each box the screen = the room's clean copy in bank 7
            b7 = mp.banks[7]
            boxes = [(p['col'], p['row'] * 8, 2, 32 if p['kind'] == 0 else 16) for p in plots if p['kind'] != 2] + [(rec['kn']['col'], rec['kn']['y'], 3, 32)]
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
                fail('screen + sprites differ from the original screen', b, where[:4], [(p['kind'], p.get('idx'), p.get('row'), p.get('col')) for p in plots], rec['kn'])
            c['screen checks'] += 1
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
                if e[0] == 'read of ROM 0' and len(e) > 2 and e[2] in (0xC10D, 0xC114) and e[3] & 7 == 1:
                    c['star map reads of ROM 0 (bank 1 code; alt image 0)'] += 1
                    continue
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
            if pcp == 0xAD48 and rec['commits'] and not st.get('hidden') and n % every == 0:
                stable_check()
            if pcp == 0xAD48:
                st['hidden'] = False
            if collect and len(states) < collect and pcp == 0xAD48 and rec['commits'] and n % 200 == 0:
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
    if 'ktypes' in st:
        c['Knight images seen'] = len(st['ktypes'])
    return c, ex, states


# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------

def boot_check(nex, z80, patch=None):
    """Boot the NEX in the Next model to the snapshot PC: registers, the NEX banks = the (patched) snapshot's, RAM, MMU,
    paging, $8C, alt ROM image 1."""
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = nextboot.boot(nex, s.pc, sysrom=rom3())       # the system ROM3 the stub copies first: NextZXOS's
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
    return bad


def build(z80, out, name, say=print, outline=True):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    patch = KnightTymePatch(outline=outline)
    spr = os.path.join(out, name + ('_sprites.nex' if outline else '_noring_sprites.nex'))
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, KnightTymePatch(outline=outline))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    say('Colours   : %s' % ('%d colour-map entries' % len(patch.colours) if patch.colours else "no colour map: the game's own colours"))
    return (not bad and not bad2), (plain, spr), patch


def negative_patches():
    """-> [(name, patch)]: broken builds the lockstep must catch."""
    out = []
    base = KnightTymePatch(colours={})
    syms = base.syms

    def page_mod(name, f):
        pc = bytearray(base.page_code)
        f(pc)
        out.append((name, KnightTymePatch(colours={}, page_code=bytes(pc))))

    def rom_mod(name, f):
        rc = bytearray(base.rom_code)
        f(rc)
        out.append((name, KnightTymePatch(colours={}, rom_code=bytes(rc))))

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
    out.append(('Knight blit from the composed box', KnightTymePatch(colours={}, data_sites=[DATA_SITES[1]])))
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
    rep_page('outline flag ignored', bytes.fromhex('3A0A80B7C8'), bytes.fromhex('3A0A80AFC9'), 'build')
    # 9 wrong X
    rep_page('Knight X off by one', bytes.fromhex('111F0019'), bytes.fromhex('11200019'), 'c_kn')
    # 10 room figures not cleared on a new room
    rep_rom('room build leaves the figures', bytes.fromhex('CD') + syms['c_all'].to_bytes(2, 'little'), bytes(3), 'e_rm')
    # 11 window hides nothing
    rep_rom('window hides nothing', bytes.fromhex('CD') + syms['c_win'].to_bytes(2, 'little'), bytes(3), 'e_wn')
    # the crew: not loaded; wrong tile place
    rep_rom('crew tiles not loaded', bytes.fromhex('CD') + syms['c_ov'].to_bytes(2, 'little'), bytes(3), 'e_ov')
    # crew tiles one pixel right, and one crew tile's skin in the wrong colour: hook data only, the model keeps the profile
    p = KnightTymePatch(colours={})
    p.hpage[0x2010] += 1
    p._banks()
    out.append(('crew tiles one pixel right', p))
    p = KnightTymePatch(colours={})
    o = 0x2100
    p.hpage[o:o + 128] = bytes(((v >> 4) == CSKIN and (CWHITE << 4) or (v & 0xF0)) | ((v & 15) == CSKIN and CWHITE or (v & 15)) for v in p.hpage[o:o + 128])
    p._banks()
    out.append(('crew skin in the wrong colour', p))
    # 12 object site missing
    rep_page('objects not built', bytes.fromhex('CD') + syms['build'].to_bytes(2, 'little'), bytes(3), 'c_plot')
    # 13 Knight's attributes: wrong pattern
    rep_page('Knight pattern off by one', bytes.fromhex('8147'), bytes.fromhex('3C47'), 'c_kn')
    # 14 speed left at 28 MHz
    rc = bytearray(base.rom_code)
    i = rc.find(bytes.fromhex('ED910700'), rom_at('e_kn2'))
    rc[i + 3] = 3
    out.append(('speed not restored', KnightTymePatch(colours={}, rom_code=bytes(rc))))
    # 15 slot 4 left mapped
    rc = bytearray(base.rom_code)
    i = rc.find(bytes.fromhex('ED915404'), rom_at('e_kn2'))
    rc[i + 3] = HPG
    out.append(('hook page left mapped', KnightTymePatch(colours={}, rom_code=bytes(rc))))
    # 16 (2026-11-04) the previous build's alt ROM: hooks only, over NextZXOS's ROM3; the lockstep model has no DivMMC
    # trap, so the IM 2 handler's JP 0x0038 reaches ROM3's IM 1 handler and its CALL 0x386E
    if next_rom_modelled():         # with Sinclair's ROM standing in for NextZXOS's ROM3 this build is the good one
        out.append(('alt ROM hooks only over ROM3 (previous build)', rom3_left(KnightTymePatch(colours={}))))
    return out


def _ram_writer(base):
    """A hook that stores one byte in game RAM (25000)  at each Knight commit."""
    pc = bytearray(base.page_code)
    i = base.syms['c_kn'] - PAGE_ORG
    # the c_kn entry's LD HL,(V_SP) (5 bytes) replaced by a store and a shorter load is not possible in place: use the
    # first instruction of unhide's caller test LD A,(V_HID) = 3A 08 80 + OR A + CALL NZ: rewrite as a RAM store
    j = bytes(pc).find(bytes.fromhex('3A0880B7C4'), i)
    pc[j:j + 3] = bytes.fromhex('22A861')    # LD (25000),HL: HL is the dead stack address here, never zero
    return KnightTymePatch(colours={}, page_code=bytes(pc))


def run_negatives(rzx, stop, say=print, crew_rzx=None, crew_stop=None):
    """Crew negatives run on crew_rzx (a recording that reaches the Bridge); a crew negative whose run never built the
    Bridge with its crew is NOT EXERCISED and counts as not detected."""
    res = []
    use_game(crew_rzx or rzx)
    for name, p in negative_patches():
        crew = name.startswith('crew')
        r, s = (crew_rzx or rzx, crew_stop if crew_rzx else stop) if crew else (rzx, stop)
        c, ex, _ = verify(p, r, stop=s, every=1)
        fails = [k for k in c if k.endswith('!')]
        if crew and not c['crew overlays']:
            say('Negative  : %-44s NOT EXERCISED (no Bridge with its crew in %s, %s frames)' % (name, os.path.basename(r), s))
            res.append((name, False))
            continue
        say('Negative  : %-44s %s %s%s' % (name, 'DETECTED' if fails else 'NOT DETECTED', (fails[0] if fails else ''),
                                           ('  [%s, %s frames, crew overlays=%d]' % (os.path.basename(r), s, c['crew overlays'])) if crew else ''))
        res.append((name, bool(fails)))
    return res


class _UPorts:
    def __init__(self, ns):
        self.ns = ns

    def read_port(self, registers, port):
        if port == 0x253B and self.ns.sel is not None:
            return self.ns.nr_read()
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
                p = KnightTymePatch(colours=colours if colours is not None else synthetic_colours(banks, idx))
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
    p = KnightTymePatch(colours={})
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
        R[6], R[7] = 0x94, 0x21
        R[24] = p.syms['c_plot']
        n = 0
        while R[24] != 0 and n < 2000000:
            sim.opcodes[m[R[24]]]()
            n += 1
    if ns.H[V_NP] > 128:
        fail('patterns overran', ns.H[V_NP])
    c['pool full: dropped tiles counted'] = ns.H[V_DROP]
    c['pool full: patterns used'] = ns.H[V_NP]
    if not ns.H[V_DROP]:
        fail('pool test never filled the pool')
    for e in err:
        fail('pool memory', e)
    # a window's object picture (0x93E7, IX = 25568) runs the same plot site and stays on the ULA, no sprite
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
                p = KnightTymePatch(colours={})
                for a_, old, new in p.sites:
                    for k_, v_ in enumerate(old):
                        m[a_ + k_] = v_
                for a_, old, new in p.data_sites:
                    m[a_] = old
            if patched:
                p = KnightTymePatch(colours={})
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
            R[24] = 0x93E7
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
GROUPS = ['Knight', 'Characters', 'Objects']
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/knight_tyme_colours.json', 'clear': True,
            'note': 'keys: graphics byte address 0xC000-0xFFFF, store pages 28-43, read at build time per figure'}


def colour_inputs_md5(peek):
    """MD5 of the game bytes the colours belong to: graphics table, characters, objects, the Knight's images."""
    return hashlib.md5(bytes(peek(a) for a in range(GTAB, 0xFAF4))).hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': RECORD, 'engine': 'knight_tyme', 'keys': 'knight_tyme-1: %04X graphics byte, bit = stored pixel',
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
    if not need <= set(off):
        raise ValueError('not a Knight Tyme sprite build: banks %s missing' % sorted(need - set(off)))
    prof = load_profile()
    peek = nex_peek(nex)
    want = prof.get('colour_inputs')
    if want != colour_inputs_md5(peek):
        raise ValueError('game graphics differ from the expected snapshot (%s, expected %s)' % (colour_inputs_md5(peek), want))
    d = bytes(nex)
    bank = lambda b: d[off[b]:off[b] + 16384]
    crew = crew_from_hpage(bank(13), prof) if prof.get('overlay') else None
    p0 = KnightTymePatch(prof, colours={}, crew=crew)
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
    p = KnightTymePatch(prof, colours=cmap, crew=crew)
    out, changed = splice(nex, {b: p.extra_banks[b] for b in COLOUR_BANKS})
    return out, {'banks changed': changed, 'colour-map entries': len(cmap)}


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
        col.add_frame([sheet_part(peek, 0xF3F4 + 96 * i, 0xF6F4 + 96 * i, 3, 32, 0x47, ('K', i), 'Knight', f)])
    for kind, idx, attr in figures:
        f += 1
        g, m = gfx_of(peek, idx)
        col.add_frame([sheet_part(peek, g, m, 2, 32 if kind == 0 else 16, attr, ('F', kind, idx), 'Characters' if kind == 0 else 'Objects', f)])
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


# ---------------------------------------------------------------------------------------------
# Loading screen (runs/knight_tyme/work/mkload.py, 2026-11-03): the tape's screen shown from bank 5 by a stub in
# bank 22 (asm: MODULE ldscr), then bank 5's own bytes put back. Applied to the built .nex, every other byte kept.
# ---------------------------------------------------------------------------------------------

SCREEN_MD5 = '82f0e3dfcfa58054ba0e428cada74b5b'    # the tape's 6,912-byte screen block
L_BANK, L_PIC, L_FINAL = 22, 0x0200, 0x3FD0       # entry bank; offsets of the screen copy and the exit


def _tape_blocks(d, tzx):
    """Data blocks of a .tap, or of a .tzx (standard 0x10, turbo 0x11, pure data 0x14; info blocks skipped)."""
    if not tzx:
        i = 0
        while i + 2 <= len(d):
            n = d[i] | d[i + 1] << 8
            yield d[i + 2:i + 2 + n]
            i += 2 + n
        return
    i = 10
    skip = {0x20: 3, 0x22: 1, 0x12: 5}
    while i < len(d):
        t = d[i]
        if t == 0x10:
            n = d[i + 3] | d[i + 4] << 8
            yield d[i + 5:i + 5 + n]
            i += 5 + n
        elif t in (0x11, 0x14):
            o = 16 if t == 0x11 else 8
            n = d[i + o] | d[i + o + 1] << 8 | d[i + o + 2] << 16
            yield d[i + o + 3:i + o + 3 + n]
            i += o + 3 + n
        elif t in skip:
            i += skip[t]
        elif t in (0x21, 0x30):
            i += 2 + d[i + 1]
        elif t == 0x32:
            i += 3 + (d[i + 1] | d[i + 2] << 8)
        elif t == 0x13:
            i += 2 + 2 * d[i + 1]
        else:
            return


def tape_screen(path):
    """The 6,912-byte loading screen of a .tap / .tzx (flag 255 block of 6,914 bytes, parity checked) or a .scr,
    when its MD5 is SCREEN_MD5; else None."""
    import hashlib
    d = open(path, 'rb').read()
    cands = [d] if len(d) == 6912 else []
    if path.lower().endswith(('.tap', '.tzx')):
        for b in _tape_blocks(d, path.lower().endswith('.tzx')):
            x = 0
            for v in b:
                x ^= v
            if len(b) == 6914 and b[0] == 0xFF and x == 0:
                cands.append(b[1:-1])
    return next((s for s in cands if hashlib.md5(s).hexdigest() == SCREEN_MD5), None)


def find_screen(folder):
    """-> (file, screen) of the first .tap / .scr in folder that holds the loading screen, or (None, None)."""
    import glob
    for f in sorted(glob.glob(os.path.join(folder, '*'))):
        if f.lower().endswith(('.tap', '.tzx', '.scr')):
            s = tape_screen(f)
            if s is not None:
                return f, s
    return None, None


def add_loading(nex, screen, prof=None):
    """nex bytes -> nex bytes with the loading screen (the pilot's loading script exactly): bank 5's screen area = the tape's
    screen; new bank 22 = entry bank: stub code, bank 5's own screen bytes at 0x0200, the exit at 0x3FD0."""
    h = (prof or load_profile())['hooks']
    code, fin = bytes.fromhex(h['lstub']), bytes.fromhex(h['lfinal'])
    hd = bytearray(nex[:512])
    if hd[18 + L_BANK] or hd[139] != 10 or any(hd[18 + k] for k in range(L_BANK, 112)) or len(screen) != 6912:
        raise ValueError('loading screen: bank 22 or above in use, or entry bank not 10')
    b = bytearray(16384)
    b[0:len(code)] = code
    b[L_PIC:L_PIC + 6912] = nex[512:512 + 6912]
    b[L_FINAL:L_FINAL + len(fin)] = fin
    hd[9] += 1
    hd[18 + L_BANK] = 1
    hd[139] = L_BANK
    return bytes(hd) + bytes(screen) + nex[512 + 6912:] + bytes(b)


def loading_check(base, nex, screen, frames_key=None):
    """The wrapped .nex against its base: header bytes 9 / 41 / 139 only, the rest of the file the base's,
    and the stub run on a model (NEXLOAD's entry state, the line register ticking, no key or a key at
    frames_key): it must show the screen, then reach page 20's 0xC000 with bank 5, every register, SP, the
    stack word, the MMU and port 0x243B as the base .nex would start. -> list of problems (empty = OK)."""
    from skoolkit.simulator import R2
    from .dizzy6 import _rw_simulator
    bad = []
    hd = [i for i in range(512) if base[i] != nex[i]]
    if hd != [9, 18 + L_BANK, 139]:
        bad.append(('header bytes differ', hd))
    if nex[512:512 + 6912] != bytes(screen) or nex[512 + 6912:len(base)] != base[512 + 6912:]:
        bad.append(('file differs outside the screen area',))
    pages = {}
    b23 = nex[len(base):]
    pages[2 * L_BANK], pages[2 * L_BANK + 1] = bytearray(b23[:8192]), bytearray(b23[8192:])
    pages[10] = bytearray(nex[512:512 + 8192])           # bank 5 = first bank in the file
    st = {'mmu': [0xFF, 0xFF, 10, 11, 4, 5, 2 * L_BANK, 2 * L_BANK + 1], 'sel': 0x55, 'n': 0, 'shown': False, 'key': False}
    pg = lambda n: pages.setdefault(n, bytearray(8192))

    class Mem(list):
        def __getitem__(s, a):
            m = st['mmu'][a >> 13]
            return 0xFF if m == 0xFF else pg(m)[a & 0x1FFF]

        def __setitem__(s, a, v):
            m = st['mmu'][a >> 13]
            if m != 0xFF:
                pg(m)[a & 0x1FFF] = v
    regs0 = {'A': 0x12, 'F': 0x34, 'B': 0x56, 'C': 0x78, 'D': 0x9A, 'E': 0xBC, 'H': 0xDE, 'L': 0xF0,
             'IX': 0x1357, 'IY': 0x2468, 'SP': 0xDFFC, 'PC': 0xC000}
    sim = _rw_simulator()(Mem([0] * 65536), dict(regs0))
    R, ed = sim.registers, sim.after_ED

    def nextreg(reg, val):
        if 0x50 <= reg <= 0x57:
            st['mmu'][reg - 0x50] = val

    def nn():
        p = R[24]
        nextreg(sim.memory[(p + 2) % 65536], sim.memory[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536
    ed[0x91] = nn

    class Tr:
        def read_port(s, regs, port):
            st['n'] += 1
            if port == 0x243B:
                return st['sel']
            if port == 0x253B:
                return (st["n"] // 2) % 312 & 0xFF if st["sel"] == 0x1F else 0
            if port & 0xFF == 0xFE:
                st['shown'] = True
                k = frames_key is not None and frames_key[0] <= st['n'] // 624 < frames_key[1]
                return 0xFE if k else 0xFF
            return 0xFF

        def write_port(s, regs, port, value, *x):
            if port == 0x243B:
                st['sel'] = value
    sim.set_tracer(Tr())
    ops, mem, n = sim.opcodes, sim.memory, 0
    while not (R[24] == 0xC000 and st['mmu'][6] == 20):
        ops[mem[R[24]]]()
        n += 1
        if n > 20_000_000:
            return bad + [('stub never left',)]
    got = {'A': R[0], 'F': R[1], 'B': R[2], 'C': R[3], 'D': R[4], 'E': R[5], 'H': R[6], 'L': R[7],
           'IX': R[8] * 256 + R[9], 'IY': R[10] * 256 + R[11]}
    bad += [('register', k, got[k], regs0[k]) for k in got if got[k] != regs0[k]]
    if R[12] != 0xDFFE or mem[0xDFFC] | mem[0xDFFD] << 8 != 0xC000:
        bad.append(('stack', hex(R[12])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 20, 21]:
        bad.append(('MMU', st['mmu']))
    if st['sel'] != 0x55:
        bad.append(('port 0x243B not put back', st['sel']))
    if bytes(pages[10][:6912]) != base[512:512 + 6912]:
        bad.append(('bank 5 screen not put back',))
    if not st['shown']:
        bad.append(('never polled the keyboard',))
    st['frames'] = st['n'] // 624
    return bad



NEG_STOP = 1500             # frames each negative control replays (games/knight_tyme.md "Results")


def _vjob(z80, rzx, stop, every):
    use_game(z80)
    c, ex, _ = verify(KnightTymePatch(), rzx, stop=stop, every=every)
    return dict(c), {k: str(v)[:400] for k, v in ex.items()}


def _njob(k, rzx, stop, z80):
    use_game(z80)
    name, p = negative_patches()[k]
    c, ex, _ = verify(p, rzx, stop=stop, every=1)
    return name, dict(c)


def auto(a, z80, name, out, say):
    """Plain + sprite build (the sprite .nex carries the tape's loading screen when the tape is beside the snapshot),
    lockstep on every recording (the first in this process, collecting unit-test states; the rest in parallel),
    unit tests, negatives on the last recording (the crew ones on the first, which builds the Bridge)."""
    import concurrent.futures as cf
    import shutil
    import tempfile
    from . import nextboot
    tmp = tempfile.mkdtemp(prefix='kt_')
    ok, (plain, base), patch = build(z80, tmp, name, say)
    shutil.copy(plain, os.path.join(out, os.path.basename(plain)))
    spr = os.path.join(out, os.path.basename(base))
    scr_file, scr = find_screen(os.path.dirname(os.path.abspath(z80)))
    nb = open(base, 'rb').read()
    if scr:
        w = add_loading(nb, scr)
        bad = loading_check(nb, w, scr) + loading_check(nb, w, scr, frames_key=(40, 60))
        open(spr, 'wb').write(w)
        ok = ok and not bad
        say('Loading   : screen from %s (md5 %s); %s  %s; loading stub %s' % (
            os.path.basename(scr_file), SCREEN_MD5[:8], os.path.basename(spr), hashlib.md5(w).hexdigest(),
            'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    else:
        open(spr, 'wb').write(nb)
        say('Loading   : no tape with the loading screen beside the snapshot: built without it (the approved build has it)')
    say('ROM model : %s' % nextboot.rom_model())
    rzxs = list(a.rzx or [])
    quick = getattr(a, 'quick', None)
    good = ok
    if rzxs:
        negs = negative_patches()
        n_ok = 0
        with cf.ProcessPoolExecutor(min(16, os.cpu_count() or 4)) as ex:
            vf = [(r, ex.submit(_vjob, z80, r, quick, 3)) for r in rzxs[1:]]
            nf = []
            for k, (nm, _) in enumerate(negs):
                r = rzxs[0] if nm.startswith('crew') else rzxs[-1]
                nf.append((nm, r, ex.submit(_njob, k, r, NEG_STOP, z80)))
            c, exs, states = verify(patch, rzxs[0], stop=quick, collect=4, every=3)
            res = [(rzxs[0], dict(c), {k: str(v)[:400] for k, v in exs.items()})] + [(r, *f.result()) for r, f in vf]
            for r, c, exs in res:
                fails = [k for k in c if k.endswith('!')]
                say('Verify    : %s %s %s' % (os.path.basename(r), 'IDENTICAL' if not fails else 'FAILED',
                                              ' '.join('%s=%s' % (k, v) for k, v in sorted(c.items()))))
                for k in fails:
                    say('  %s %s' % (k, exs.get(k[:-1], '')))
                good = good and not fails
            u, f = unit_tests(patch, states)
            say('Unit      : %s %s' % ('PASS' if not f else 'FAILED', ' '.join('%s=%s' % kv for kv in sorted(u.items()))))
            for x in f[:6]:
                say('  ' + str(x)[:300])
            good = good and not f
            for nm, r, fu in nf:
                _, c = fu.result()
                fails = [k for k in c if k.endswith('!')]
                if nm.startswith('crew') and not c.get('crew overlays'):
                    say('Negative  : %-44s NOT EXERCISED (no Bridge in %s)' % (nm, os.path.basename(r)))
                    continue
                n_ok += bool(fails)
                say('Negative  : %-44s %s %s  [%s]' % (nm, 'DETECTED' if fails else 'NOT DETECTED', fails[0] if fails else '',
                                                    os.path.basename(r)))
        if not next_rom_modelled():
            say("Negative  : alt ROM hooks only over ROM3 (previous build): not run, NextZXOS's ROM3 not modelled "
                "(set NEXCLASH_NEXT_ROM)")
        say('Negative  : %d/%d DETECTED' % (n_ok, len(negs)))
        good = good and n_ok == len(negs)
    say('Result    : %s' % ('PASSED' if good else 'FAILED'))
    return good
