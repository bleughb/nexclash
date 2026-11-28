"""Dynamite Dan (Mirrorsoft, 1985, 48K) engine 'dynamite_dan'. Additive module: reachable only through
is_dynamite_dan(). Details in games/dynamite_dan.md.

Dan: plotter 0xD1CE (reached by JP from every state handler, one CALL at 0xD184). Frame f = 0xC875 from
table 0x632A, 3 x 28 bytes, ink only in rows 2-25; x cell 0xC873, y pixel 0xC872. It ORs the frame into the
screen and never paints attributes, so Dan takes each cell's colour. 0xC880 odd: the frame source is the
saved background (Dan flickers while hit). 0xDBED x 2 rows are plotted: 14 (13 on a floor), 12..1 sinking
in water, so the sprites' clip window ends with the plot. Logic reads the screen and attributes under Dan.
Overlay: the ULA is left exactly as the original draws it and two sprites cover Dan's ink.
Enhanced also overlays the four E96B enemy tables, keeping the ULA plot and collision reads intact.
Airship (room 43): fixed scenery, so its hull and cables are static sprites above Dan, copies of the ULA.
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
RECORD = 'dynamite_dan'
FRTAB = 0x632A
SAVED = (0x62D6, 0x632A)       # Dan's background buffer, 84 bytes
SCREEN = (0x4000, 0x5800)
NFRAMES = 8
NPAT = 16
TRANSP = 0xE3
DAN_DEFAULT = 13               # palette index: bright cyan, the ink of an empty cell (attribute 0x45)
# sheet palette, indices 1-15; 0 unused. Bright magenta is 0xE7, as 0xE3 is the transparent index.
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
# Skin, skin shadow, leather, orange, steel, navy, olive, brass, ice, jade.
PALETTE += [0xF5, 0xCD, 0x88, 0xF0, 0x92, 0x2A, 0x90, 0xD4, 0xBB, 0x56]
ENHANCED = 'dynamite_dan_v14'
SITES_ORIG = {0xD1CE: '3a80c8', 0xE801: '210040', 0xE820: '210040', 0xE60B: '368021b040'}
SITE_SYM = {0xD1CE: 'e_dan', 0xE801: 'e_c1', 0xE820: 'e_c2', 0xE60B: 'e_end'}
SITE_KIND = {0xD1CE: 'dan', 0xE801: 'cls', 0xE820: 'cls', 0xE60B: 'end'}
SITE_NEXT = {0xD1CE: 0xD1D1, 0xE801: 0xE804, 0xE820: 0xE823, 0xE60B: 0xE610}
INTERIORS = (0xD1CF, 0xD1D0, 0xE802, 0xE803, 0xE821, 0xE822, 0xE60C, 0xE60E, 0xE60F)
SEQUEL = (0xE60D, 0xE60B)      # the second original instruction of the 0xE60B site

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')
ENHANCED_COLOURS = COLOURS.replace('_colours', '_enhanced_colours')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_dynamite_dan(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def derive_start(z80, out):
    """The snapshot stops in BASIC at PAUSE 0 (a .nex runs on ROM3): run it on the toolkit's machine,
    a key held, to the game's entry RANDOMIZE USR 51200 -> a snapshot with PC = 0xC800."""
    from .machine import Machine, parse_inputs
    from skoolkit.simutils import PC, T
    m = Machine(z80)
    regs = m.sim.registers
    for _ in range(20):
        m.frame(frozenset())
    m.held = parse_inputs('SPACE')

    class Done(Exception):
        pass

    def tr(fc, pc):
        if pc == 0xC800:
            raise Done()
    try:
        for _ in range(100000):
            m.sim.exec_frame(100000, None, tr)
            regs[T] = 0
    except Done:
        pass
    if regs[PC] != 0xC800:
        raise ValueError('the loader did not reach 0xC800')
    open(out, 'wb').write(m.z80_bytes())
    return out


# ---------------------------------------------------------------------------------------------
# Airship foreground (room 43): sprites 2.. over Dan, pixel copies of the ULA's hull and cables
# ---------------------------------------------------------------------------------------------

AIRSHIP = 0x2B
FG_N = 9
FG_SPR, FG_PAT = 2, 16
HULL_CELLS = {(c, r) for c in range(12, 21) for r in (5, 6)}
CABLE_CELLS = {(12, 2), (13, 2), (13, 3), (13, 4), (19, 2), (20, 2), (19, 3), (19, 4)}
FG_TILES = [(12, 5), (14, 5), (16, 5), (18, 5), (20, 5), (12, 2), (12, 4), (19, 2), (19, 4)]
SPECCY = ((0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6), (0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF))
FG_TABLE_AT = 0x1F00           # bank 11 offset: X, Y, attr 2 per foreground sprite


def ula_colour(peek, x, y):
    b = peek(0x4000 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + (x >> 3))
    at = peek(0x5800 + (y >> 3) * 32 + (x >> 3))
    v = at & 7 if b & (128 >> (x & 7)) else (at >> 3) & 7
    return SPECCY[1 if at & 64 else 0][v]


def fg_capture(start):
    """The room as the game draws it, run on the toolkit's machine from the start snapshot to the first
    plot of Dan in room 43 (Dan not drawn yet): -> [16 x 16 colours or TRANSP] per FG_TILES entry. Hull: every
    pixel between a row's first and last non-black pixel; cables: their ink."""
    from .machine import Machine, parse_inputs
    from skoolkit.simutils import T
    m = Machine(start)
    M, regs = m.sim.memory, m.sim.registers

    class Hit(Exception):
        pass

    class Stop(Exception):
        pass

    def tr(fc, pc):
        if pc == 0xD1CE and M[0xCFCA] == AIRSHIP:
            raise Hit()
        if regs[T] >= 69888:
            raise Stop()

    def frame(h):
        m.held, m.ins = h, []
        try:
            while True:
                m.sim.exec_frame(65000, None, tr)
        except Stop:
            pass
        regs[T] = 0
    try:
        for _ in range(30):
            frame(frozenset())
        for _ in range(6):
            frame(parse_inputs('ENTER'))
        for _ in range(600):
            frame(frozenset())
        raise ValueError('room 43 not reached')
    except Hit:
        pass
    peek = lambda a: M[a]
    px = {}
    for y in range(40, 56):
        xs = [x for x in range(96, 168) if ula_colour(peek, x, y)]
        if xs:
            for x in range(min(xs), max(xs) + 1):
                px[(x, y)] = ula_colour(peek, x, y)
    for c, r in CABLE_CELLS:
        for y in range(r * 8, r * 8 + 8):
            for x in range(c * 8, c * 8 + 8):
                v = ula_colour(peek, x, y)
                if v:
                    px[(x, y)] = v
    out = []
    for c, r in FG_TILES:
        out.append([[px.get((c * 8 + k, r * 8 + j), TRANSP) for k in range(16)] for j in range(16)])
    return out


def fg_bytes(tiles):
    pats = bytes(v for t in tiles for row in t for v in row)
    table = bytearray()
    for (c, r) in FG_TILES:
        x = 32 + c * 8
        table += bytes((x & 255, 32 + r * 8, x >> 8))
    return pats, bytes(table)


# ---------------------------------------------------------------------------------------------
# Patterns: 2f = rows 2-17, 2f + 1 = rows 18-25 of frame f, 16 columns from xoff[f], 8-bit RRRGGGBB
# ---------------------------------------------------------------------------------------------

def frame_addr(peek, f):
    return peek(FRTAB + 2 * f) | peek(FRTAB + 2 * f + 1) << 8


def frame_windows(peek):
    """xoff per frame: the first ink column, so that the frame's ink fits 16 columns."""
    out = []
    for f in range(NFRAMES):
        a = frame_addr(peek, f)
        cols = [c * 8 + b for r in range(28) for c in range(3) for b in range(8)
                if peek(a + r * 3 + c) & (128 >> b)]
        out.append(min(cols))
    return out


def colour_of(cmap, key, bit, byte):
    """(opaque?, 8-bit colour or None for the default) from the colour map, for one pixel."""
    e = cmap.get(key) if cmap else None
    if e is None or e[0] != byte:
        return None
    if len(e) > 3 and e[3] & (128 >> bit):
        return 'T'
    index = e[2][bit]
    if not 0 <= index < len(PALETTE):
        raise ValueError('%s pixel %d uses index %d outside the Dynamite Dan palette' % (key, bit, index))
    return index or None


def patterns(peek, cmap=None, xoff=None):
    xoff = xoff or frame_windows(peek)
    out = bytearray()
    for f in range(NFRAMES):
        a = frame_addr(peek, f)
        for first, n in ((2, 16), (18, 8)):
            for r in range(16):
                for col in range(16):
                    c = xoff[f] + col
                    px = TRANSP
                    if r < n and c < 24:
                        addr = a + (first + r) * 3 + c // 8
                        byte = peek(addr)
                        bit = c % 8
                        st = colour_of(cmap, '%04X' % addr, bit, byte)
                        ink = byte & (128 >> bit)
                        if st == 'T':
                            px = TRANSP
                        elif st is not None:
                            px = PALETTE[st]
                        elif ink:
                            px = PALETTE[DAN_DEFAULT]
                    out.append(px)
    return bytes(out)


def load_colours(enhanced=False):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(build_colours_path(ENHANCED_COLOURS if enhanced else COLOURS))


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

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
    """The plain .nex: no hooks. Alt ROM image 1 = Sinclair's 48K ROM (+ the tail's register block in its 0xFF area), so
    the snapshot's BASIC (PAUSE 0, then RANDOMIZE USR 51200) runs as on a 48K."""
    name = "Dynamite Dan plain conversion, Sinclair's ROM as the alt ROM"
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
        self.extra_banks = {12: self.page + bytes(8192)}

    def apply(self, snap):
        pass


class DanPatch:
    name = 'Dynamite Dan: Dan -> overlay hardware sprites (altrom, stateless hooks)'

    def __init__(self, prof=None, colours=None, start=None, enhanced=False):
        self.start = start
        self.fg = None
        self.enhanced = enhanced
        if enhanced and prof is None:
            with open(_profile_path().replace('.json', '_enhanced.json')) as f:
                prof = json.load(f)
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
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
        for a, old in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old), bytes([0xC3]) + self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        self.kinds = dict(SITE_KIND)
        self.next_pc = dict(SITE_NEXT)
        if enhanced:
            from .dynamite_dan_enemies import SITES
            for a, (old, sym, kind) in SITES.items():
                self.sites.append((a, bytes.fromhex(old), b'\xc3' + self.syms[sym].to_bytes(2, 'little')))
                self.kinds[a] = kind
                self.next_pc[a] = a + len(bytes.fromhex(old))
        self.extra_banks = {}
        self.pats = None
        self.colours = colours
        self.num_patterns = NPAT

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Dynamite Dan patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + 256]):
            raise ValueError('printer buffer is not empty in this snapshot (tail site)')
        peek = lambda a: ram[a - 0x4000]
        xoff = list(self.rom_code[self.syms['xoff'] - ROM_ORG:self.syms['xoff'] - ROM_ORG + NFRAMES])
        if xoff != frame_windows(peek):
            raise ValueError('frame windows %s, hooks hold %s' % (frame_windows(peek), xoff))
        cmap = self.colours if self.colours is not None else load_colours(self.enhanced)
        self.colours = cmap
        self.windows = xoff
        self.pats = patterns(peek, cmap, xoff)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        if self.fg is None:
            self.fg = fg_capture(self.start)
        fgp, table = fg_bytes(self.fg)
        self.fg_table = table
        self.pats += fgp
        b11 = bytearray(self.pats + bytes(16384 - len(self.pats)))
        b11[FG_TABLE_AT:FG_TABLE_AT + len(table)] = table
        self.extra_banks = {11: bytes(b11), 12: self.page + bytes(8192)}
        if self.enhanced:
            from . import dynamite_dan_enemies as enemies
            self.extra_banks.update(enemies.banks(peek, cmap))


# ---------------------------------------------------------------------------------------------
# Next-side state and event runner (original vs patched from one state)
# ---------------------------------------------------------------------------------------------

def sprite_pixels(attr, pat):
    """Visible 8-bit anchor sprite -> {(x, y): colour} in ULA coordinates."""
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return {}
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    base = (a3 & 0x3F) * 256
    out = {}
    for j in range(16):
        for k in range(16):
            b = pat[base + j * 16 + k]
            if b != TRANSP:
                out[(x + (15 - k if a2 & 8 else k), y + j)] = b
    return out


class NextState:
    def __init__(self, pats, banks=None):
        self.banks = banks or {}
        self.pattern_cursor = 0
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(51 if banks else FG_SPR + FG_N)]
        for i, (c, r) in enumerate(FG_TILES):
            x = 32 + c * 8
            self.attr[FG_SPR + i][:3] = [x & 255, 32 + r * 8, x >> 8]
        self.clip = [0, 255, 0, 191]
        self.clipi = 0
        self.pat = bytearray(pats) + bytearray(16384 - len(pats))
        self.events = []
        self.speed = 0              # NR 7 bits 1:0: the clock now (set to the incoming clock at each event)
        self.speed_in = 0           # the clock a hook is entered at (verify clock=, the every-site matrix)
        self.sel = 8                # port 0x243B's register: the stub's last read leaves NR 8 (Codex review C8)

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if reg == 0x07:
            self.speed = val & 3
        if reg == 0x1C and val & 2:
            self.clipi = 0
        if reg == 0x19:
            self.clip[self.clipi] = val
            self.clipi = (self.clipi + 1) & 3
        if 0x35 <= reg <= 0x39:
            i = self.nr.get(0x34, 0) & 0x7F
            if i < len(self.attr):
                self.attr[i][reg - 0x35] = val
            else:
                self.events.append(('nr', 'sprite out of range', i))
        self.events.append(('nr', reg, val))

    def pixels(self, *ids):
        out = {}
        for i in ids:
            out.update(sprite_pixels(self.attr[i], self.pat))
        x1, x2, y1, y2 = self.clip
        return {k: v for k, v in out.items() if x1 <= k[0] <= x2 and y1 <= k[1] <= y2}


def _machine(Sim, mem, regs, ns, slot='o'):
    from .simpool import machine
    from .z80n import install
    sim = machine(Sim, mem, regs, slot)

    class Tr:
        def read_port(s, regs_, port):
            if port == 0x253B and ns.sel == 7:
                return ns.speed << 4 | ns.speed      # actual speed 5:4, programmed 1:0 (hooklib.NextModel)
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            if port == 0x243B:
                ns.sel = value
            elif ns.banks and port == 0x303B:
                ns.pattern_cursor = (value & 63) * 256
            elif ns.banks and port & 255 == 0x5B:
                ns.pat[ns.pattern_cursor] = value
                ns.pattern_cursor = (ns.pattern_cursor + 1) % 16384
            else:
                ns.events.append(('out', port, value))
    sim.set_tracer(Tr())
    install(sim, ns.nextreg)
    return sim


def _run(sim, stop, limit=400000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


CMP = list(range(0, 13)) + list(range(14, 25)) + [26, 27]   # every register, R (15) included; not T, MEMPTR


def _overlays(patch, get, alt, canvases=(), ns=None):
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            if v is not None:
                return v
            for lo, hi in canvases:
                if lo <= a < hi:
                    return 0
            return get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if ns and 0x4000 <= a < 0x6000:
                pg = ns.nr.get(0x52, 10)
                if pg != 10:
                    return ns.banks[pg // 2][(pg % 2) * 8192 + a - 0x4000]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', 0) + 1
            else:
                s.ov[a] = v
    return O, P


def _ink(ov):
    """Ink pixels written in the screen area of an overlay -> {(x, y)}."""
    out = set()
    for a, v in ov.items():
        if SCREEN[0] <= a < SCREEN[1]:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                if (v >> (7 - k)) & 1:
                    out.add(((a & 31) * 8 + k, y))
    return out


def event(patch, kind, site, get, R, ns, alt, Sim, check_ula=False):
    """One hook event: original and patched from the same state to the end of the site, plus (Dan) a
    canvas run of the ORIGINAL plotter on a blank screen and blank saved buffer, whose ink is what
    the sprites must show. -> (failures, ink pixels compared)."""
    nxt = patch.next_pc[site]
    stop = lambda r: r[24] == nxt
    sp0 = R[12]
    f = []
    O, P = _overlays(patch, get, alt, ns=ns)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    before = [list(a) for a in ns.attr]
    ns.events = []
    ns.speed = ns.speed_in
    sp = _machine(Sim, p, list(R), ns, 'p')
    if not (_run(so, stop) and _run(sp, stop)):
        return ['did not return'], 0
    ro, rp = so.registers, sp.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access in hook',))
    if ns.nr.get(0x52, 10) != 10:
        f.append(('ULA page not restored',))
    if any((e[1] != 0x52 or not patch.enhanced) and e[1] not in (0x07, 0x19, 0x1C, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39) for e in ns.events):
        f.append(('NEXTREG other than sprite attributes and the speed',))
    if ns.speed != ns.speed_in:
        f.append(('exit speed is not the incoming one', ns.speed, ns.speed_in))
    if ns.sel not in (7, getattr(ns, 'sel_in', 8)):  # a hook leaves NR 7 selected, or the selection as it found it
        f.append(('port 0x243B left on another register', ns.sel))
    ns.n_sel = getattr(ns, 'n_sel', 0) + 1          # the next hook finds 0x243B on NR 8, 0x53 or 7 in turn: a read selects 7
    ns.sel = ns.sel_in = (0x08, 0x53, 0x07)[ns.n_sel % 3]
    dead = range(sp0 - 64, min(sp0, ro[12]))                     # below SP: the hook's own pushes
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if a not in dead and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    npx = 0
    if kind == 'dan':
        ret = get(sp0) | get(sp0 + 1) << 8
        endstop = lambda r: (r[24] == ret and r[12] == sp0 + 2) or r[12] > sp0 + 2
        Oc, _ = _overlays(patch, get, alt, (SCREEN, SAVED))
        oc = Oc()
        sc = _machine(Sim, oc, list(R), NextState(b''), 'c')
        if not _run(sc, endstop):
            return f + ['canvas run did not return'], 0
        drawn = _ink(oc.ov)
        got = ns.pixels(0, 1)
        npx = len(drawn)
        if patch.enhanced:
            if ns.attr[11:] != before[11:] or ns.clip != [0, 255, 0, 191]:
                f.append(('Dan plot changed enemy visibility or the global clip',))
            wanted = {pos: PALETTE[DAN_DEFAULT] for pos in drawn}
            frame = get(0xC875)
            if not get(0xC880) & 1 and frame < 8:
                start = frame_addr(get, frame)
                for y in range(2, min(26, get(0xDBED)*2)):
                    for x in range(patch.windows[frame], min(24, patch.windows[frame]+16)):
                        a = start + 3*y + x//8
                        colour = colour_of(patch.colours, '%04X' % a, x%8, get(a))
                        pos = get(0xC873)*8+x, get(0xC872)+y
                        if colour == 'T':
                            wanted.pop(pos, None)
                        elif colour:
                            wanted[pos] = PALETTE[colour]
            if got != wanted:
                f.append(('painted Dan differs from original canvas and map', len(set(got.items()) ^ set(wanted.items()))))
            npx = len(wanted)
        elif set(got) != drawn:
            f.append(('sprite pixels differ from the original plot', len(set(got) ^ drawn)))
        room = get(0xCFCA)
        if room == AIRSHIP:
            for i in range(FG_N):
                if ns.attr[FG_SPR + i][3] != 0xC0 | (FG_PAT + i):
                    f.append(('airship foreground not shown in room 43', i))
                    break
            if check_ula:
                dx, dy = get(0xC873) * 8, get(0xC872)
                for i in range(FG_N):
                    fgp = sprite_pixels(ns.attr[FG_SPR + i], ns.pat)
                    if not fgp:
                        f.append(('airship foreground tile empty', i))
                    bad = [(x, y) for (x, y), v in fgp.items() if not (dx - 16 <= x < dx + 40 and dy - 8 <= y < dy + 36)
                           and ula_colour(get, x, y) != v]
                    if bad:
                        f.append(('foreground differs from the ULA', i, bad[:3]))
                        break
        else:
            if any(ns.attr[i] != before[i] for i in range(FG_SPR, FG_SPR + FG_N)):
                f.append(('airship foreground touched in another room',))
    elif kind in ('enemy', 'erase', 'load'):
        from . import dynamite_dan_enemies as en
        iy = R[10] * 256 + R[11]
        room = en.MENU if iy >> 8 == 0xCA else get(0xCFCA)
        base, groups = en.room_info(get, room)
        if kind == 'load':
            page = patch.extra_banks[(32 + room)//2]
            page = page[(room % 2)*8192:]
            count = page[0]
            if ns.pat[27*256:(27+count)*256] != page[0x400:0x400+count*256]:
                f.append(('room pattern upload differs', room))
        else:
            first = en.FIRST_SLOT + (iy - base)//8*4
            if not 11 <= first <= 47 or (iy-base) % 8:
                f.append(('unknown enemy record', room, iy))
            elif (kind == 'erase' or get(iy+4) & 64) and any(a[3] & 128 for a in ns.attr[first:first+4]):
                f.append(('erased enemy still visible', first))
            if any(a != before[i] for i, a in enumerate(ns.attr) if not first <= i < first+4):
                f.append(('another sprite changed',))
    elif kind in ('cls', 'end'):
        if any(a[3] & 0x80 for a in ns.attr):
            f.append(('sprite visible after screen clear',))
    return f, npx


def _alt(patch):
    """Alt ROM image 1 as the stub leaves it on the Next (nextboot.alt_image: the whole image, Sinclair's ROM + hooks)."""
    from .nextboot import alt_image
    return alt_image(patch)


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def verify(patch, rzx_path, stop=None, collect=0, progress=None, clock=0):
    """Replay the RZX (original game); at every hook site run original and patched code from the same
    state and compare. Returns (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False}
    ns = NextState(patch.pats, patch.extra_banks if patch.enhanced else None)
    ns.speed_in = clock                              # the game's clock (NR 7): 0 = 3.5 MHz as recorded
    cnt = collections.Counter()
    interiors = set(INTERIORS)
    if patch.enhanced:
        interiors.update((0xC838, 0xC839, 0xE54E, 0xE54F, 0xD2E8, 0xD2E9, 0xD2EA, 0xE96D, 0xE96E, 0xE96F))
    WATCH = set(patch.kinds) | interiors | {SEQUEL[0]}
    if patch.enhanced:
        WATCH.add(0xE96C)  # second displaced instruction, reached only from E96B
        WATCH.add(0xE9B9)  # after the unmodified ULA plot has written every cell
    pending = []
    paint_cache = {}
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['on'] and type(a) is int and a in site_bytes:
                fail('game wrote a patch site', (a,))
            S(s, a, v)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)

            def mk(fn):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        if pc == 0xE9B9 and pending:
                            first, x, y, w, h, group, edits = pending.pop()
                            from .dynamite_dan_enemies import check_picture
                            err, total = check_picture(ns, first, x, y, w, h, get, edits)
                            c['enemy pixels compared'] += total
                            c['enemy table %d' % group] += 1
                            if err:
                                fail('enemy differs from plotted ULA', (first, x, y, w, h, err))
                        kind = patch.kinds.get(pc)
                        if kind:
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((kind, pc, list(R), bytes(G(mem, a) for a in range(65536)),
                                               [list(x) for x in ns.attr]))
                            if R[26]:
                                fail('interrupts on at a hook site')
                            fl, npx = event(patch, kind, pc, get, R, ns, alt, _rw(), True)
                            if kind == 'enemy':
                                from . import dynamite_dan_enemies as en
                                iy = R[10]*256 + R[11]
                                room = en.MENU if iy >> 8 == 0xca else get(0xcfca)
                                base, groups = en.room_info(get, room)
                                if not get(iy+4) & 64:
                                    index = (iy-base)//8
                                    group = next(i for i in range(4) if index < sum(n for _,n in groups[:i+1]))
                                    key = (groups[group][0], group, get(iy+4) & 7)
                                    if key not in paint_cache:
                                        paint_cache[key] = en.frame_paint(get, patch.colours, *key)
                                    pending.append((11+index*4, R[4]*8, R[5]*8, R[2]*8, R[3]*8, group, paint_cache[key]))
                                else:
                                    c['suppressed enemy plots'] += 1
                            c[kind] += 1
                            c['%s 0x%04X' % (kind, pc)] += 1
                            c['sprite pixels compared'] += npx
                            for k in fl:
                                fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k),
                                     k[1:] if isinstance(k, tuple) else ())
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
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    if patch.enhanced and cnt[0xE96C] != cnt[0xE96B]:
        c['0xE96C reached other than from 0xE96B!'] += 1
    if pending and not stop:
        c['recording ended inside an enemy plot!'] += 1
    for a in interiors:
        if cnt[a]:
            c['jump into a patched instruction (0x%04X)!' % a] += 1
    if cnt[SEQUEL[0]] != cnt[SEQUEL[1]]:
        c['0xE60D reached other than from 0xE60B!'] += 1
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests and negative controls
# ---------------------------------------------------------------------------------------------

def unit_tests(patch, states, negs=()):
    """states from verify(collect=n): (kind, site, registers, 64K memory, sprite attrs). Dan: every frame x
    edge positions x visible / flicker x 13 / 14 row plots; clears; the end of the game (no recording
    reaches it). negs: [(name, broken patch)], each must fail on the real states."""
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()

    def one(pt, kind, site, R, mem, attrs, alt_=None, check_ula=False):
        ns = NextState(pt.pats, pt.extra_banks if pt.enhanced else None)
        ns.attr = [list(a) for a in attrs]
        ns.speed_in = getattr(pt, 'clock', 0)        # a speed negative is entered at 7 MHz: at 3.5 it cannot differ
        return event(pt, kind, site, mem.__getitem__, R, ns, alt_ or _alt(pt), Sim, check_ula)

    for kind, site, R, mem, attrs in states:
        mem = bytearray(mem)
        if kind == 'dan':
            for fr in range(NFRAMES):
                for x, y in ((0, 0), (1, 2), (15, 62), (16, 100), (28, 134), (29, 132), (3, 22)):
                    for inv in (0, 1):
                        for rows in (1, 2, 7, 12, 13, 14):
                            m2 = bytearray(mem)
                            m2[0xC875], m2[0xC873], m2[0xC872], m2[0xC880], m2[0xDBED] = fr, x, y, inv * 3, rows
                            m2[0xCFCA] = AIRSHIP if fr & 1 else 5
                            fl, _ = one(patch, kind, site, list(R), m2, attrs)
                            c['Dan cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                            if fl and c['  fail example'] < 3:
                                c['  fail example'] += 1
                                c['  fr %d x %d y %d inv %d rows %d %s' % (fr, x, y, inv, rows, fl[:2])] += 1
            at = [list(a) for a in attrs]
            for i in range(len(at)):
                at[i][3] |= 0x80
            r = list(R)
            r[24] = 0xE60B
            r[6], r[7] = 0xC8, 0x7E
            fl, _ = one(patch, 'end', 0xE60B, r, bytearray(mem), at)
            c['end-of-game hide cases %s' % ('ok' if not fl else 'FAIL!')] += 1
            for name, neg in negs:
                m2 = bytearray(mem)
                m2[0xC880] = 0
                if name == 'clip':
                    m2[0xDBED] = 8          # Dan half sunk
                at = attrs
                if name == 'foreground off':
                    m2[0xCFCA] = AIRSHIP
                    at = [list(a) for a in attrs]
                    for i in range(FG_N):
                        at[FG_SPR + i][3] = 0     # as after a room change
                if name == 'foreground pixels' and m2[0xCFCA] != AIRSHIP:
                    continue
                fl, _ = one(neg, kind, site, list(R), m2, at, None, name == 'foreground pixels')
                if name != 'clear':
                    c['negative control %s' % ('detected' if fl else 'NOT DETECTED!')] += 1
                    c['negative control %s %s' % (name, 'detected' if fl else 'NOT DETECTED!')] += 1
        elif kind == 'cls':
            at = [list(a) for a in attrs]
            for i in range(len(at)):
                at[i][3] |= 0x80
            fl, _ = one(patch, kind, site, list(R), bytearray(mem), at)
            c['screen clear cases %s' % ('ok' if not fl else 'FAIL!')] += 1
            for name, neg in negs:
                fl, _ = one(neg, kind, site, list(R), bytearray(mem), at)
                if name == 'clear':
                    c['negative control %s' % ('detected' if fl else 'NOT DETECTED!')] += 1
                    c['negative control %s %s' % (name, 'detected' if fl else 'NOT DETECTED!')] += 1
    m, _ = clock_matrix(patch, states)
    for k, v in m.items():
        c['clock matrix %s' % k] += v
    return c


def clock_matrix(patch, states):
    """The every-site matrix (hooklib.every_site; card patch.restore-speed): each captured hook entry run with NR 7 =
    0-3 from the same state: no hook writes NR 7, so each must exit at its clock with the same results."""
    from .hooklib import every_site
    alt = _alt(patch)
    Sim = _rw()

    def run(n, k):
        kind, site, R, mem, attrs = states[n]
        ns = NextState(patch.pats, patch.extra_banks if patch.enhanced else None)
        ns.attr = [list(a) for a in attrs]
        ns.speed_in = k
        fl, npx = event(patch, kind, site, bytes(mem).__getitem__, list(R), ns, alt, Sim)
        return ns.speed, (tuple(map(str, fl)), npx, tuple(map(tuple, ns.attr)), tuple(ns.clip))
    return every_site(range(len(states)), run)


def negative_patches(patch):
    """Broken copies: patterns one pixel right; the wrong window table; a hook that loses BC; a clear
    that leaves the sprites on."""
    import copy
    out = []
    q = copy.copy(patch)
    p = bytearray(patch.pats)
    s = bytearray(len(p))
    for r in range(len(p) // 16):
        row = p[16 * r:16 * r + 16]
        s[16 * r:16 * r + 16] = bytes([TRANSP]) + row[:15]
    q.pats = bytes(s)
    out.append(('pattern shifted', q))

    def rom(mutate):
        q = copy.copy(patch)
        pg = bytearray(patch.page)
        mutate(pg)
        q.page = bytes(pg)
        return q

    def xoff(pg):
        a = patch.syms['xoff'] - 0x2000
        for f in range(NFRAMES):         # every frame, so any captured state shows it
            pg[a + f] = (pg[a + f] + 2) & 0xFF
    out.append(('window table', rom(xoff)))

    def nopop(pg):
        a = patch.syms['e_dan'] - 0x2000
        k = bytes(pg[a:a + 250]).index(bytes.fromhex('e1c1f1'))
        pg[a + k + 1] = 0
    out.append(('register lost', rom(nopop)))

    def noclear(pg):
        for s_ in ('e_c1', 'e_c2'):
            a = patch.syms[s_] - 0x2000
            pg[a:a + 3] = bytes(3)
    out.append(('clear', rom(noclear)))

    def noclip(pg):
        if patch.enhanced:
            pg[patch.syms['clip_dan'] - 0x2000] = 0xC9
            return
        a = patch.syms['e_dan'] - 0x2000
        k = bytes(pg[a:a + 250]).index(bytes.fromhex('873d47'))   # ADD A,A / DEC A / LD B,A in the clip
        pg[a + k] = 0
    out.append(('clip', rom(noclip)))

    def noroom(pg):
        a = patch.syms['e_dan'] - 0x2000
        k = bytes(pg[a:a + 200]).index(bytes((0xFE, AIRSHIP)))
        pg[a + k + 1] = AIRSHIP ^ 0x40
    out.append(('foreground off', rom(noroom)))
    def r_off(pg):
        a = patch.syms['e_dan'] - 0x2000
        k = bytes(pg[a:a + 250]).index(bytes.fromhex('47c6'))     # RSET: LD B,A / ADD A,D_DAN
        pg[a + k + 2] = (pg[a + k + 2] + 1) & 0xFF
    out.append(('R one off after a plot', rom(r_off)))

    def forced(pg):
        a = patch.syms['e_dan'] - 0x2000
        k = bytes(pg[a:a + 250]).index(bytes.fromhex('e603f5'))    # the latch: AND 3 -> AND 0, so it exits at 3.5 MHz
        pg[a + k + 1] = 0
    q = rom(forced)
    q.clock = 1
    out.append(('forced 3.5 MHz exit', q))
    q = copy.copy(patch)
    p2 = bytearray(patch.pats)
    p2[FG_PAT * 256:(FG_PAT + FG_N) * 256] = bytes([TRANSP]) + bytes(p2[FG_PAT * 256:(FG_PAT + FG_N) * 256 - 1])
    q.pats = bytes(p2)
    out.append(('foreground pixels', q))
    return out


# ---------------------------------------------------------------------------------------------
# Colour route (docs/COLOURS.md): key = graphics byte %04X, bit = pixel, in the 16-wide window
# ---------------------------------------------------------------------------------------------

def colour_inputs_md5(peek):
    return hashlib.md5(bytes(peek(a) for a in range(0x633A, 0x65DA))).hexdigest()


def colour_identity(peek, enhanced=None):
    if enhanced is None:
        enhanced = peek(0xE96B) == 0xC3
    if enhanced:
        from .dynamite_dan_enemies import geometry, frames
        digest = hashlib.md5()
        digest.update(bytes.fromhex(colour_inputs_md5(peek)))
        for kind, f in frames(peek):
            a, w, h = geometry(peek, kind)
            digest.update(bytes(peek(a + f*w*h*8 + i) for i in range(w*h*8)))
        return dict(schema=1, game=RECORD, engine=RECORD, keys='Dan and unshifted enemy graphics address/bit',
                    inputs=digest.hexdigest(), geometry='four enemy tables v1')
    return {'schema': 1, 'game': RECORD, 'engine': RECORD,
            'keys': 'dynamite_dan-1: %04X graphics byte of a Dan frame, bit = pixel',
            'inputs': colour_inputs_md5(peek), 'geometry': None}


NOTE = ('Dynamite Dan colour map (docs/COLOURS.md): key = graphics byte of a Dan frame (hex address; check = its '
        'value); 8 nibbles, 0 = default (bright cyan on ink, transparent on paper); optional 4th = transparent mask')
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/%s_colours.json' % RECORD,
            'clear': True, 'note': NOTE}


def map_note(cmap):
    # Keep the old serialization, including its note, for the owner's 1.3 files.
    if any(max(row[2]) > 15 or int(key, 16) >= 0xAE60 for key, row in cmap.items()):
        return ('Dan and enemy graphics byte, eight palette indices. Wide rows use integer arrays. '
                'Zero inherits the source colour. The optional fourth field is the transparent mask.')
    return NOTE


def default_map_for_nex(nex):
    from .recolour import nex_peek
    from .coloursheet import load
    path = ENHANCED_COLOURS if nex_peek(nex)(0xE96B) == 0xC3 else COLOURS
    return load(path)


def recolour(nex, cmap):
    """Rebuild Dan's patterns in bank 11 and the Enhanced room pages when present. Refuses a .nex that is not this engine's build of the expected snapshot."""
    from .recolour import banks, nex_peek, splice
    b = banks(nex)
    if not {5, 2, 0, 11, 12} <= set(b):
        raise ValueError('not a Dynamite Dan sprite build: banks missing')
    peek = nex_peek(nex)
    p = DanPatch(colours={}, enhanced=peek(0xE96B) == 0xC3)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook jump" % a)
    if b[12] != p.page + bytes(8192):
        raise ValueError('alt ROM image / hook code differs from this version (rebuild with nexclash.py auto)')
    xoff = list(p.rom_code[p.syms['xoff'] - ROM_ORG:p.syms['xoff'] - ROM_ORG + NFRAMES])
    pats = patterns(peek, cmap, xoff)
    new = {11: pats + b[11][len(pats):]}
    if p.enhanced:
        from . import dynamite_dan_enemies as enemies
        new.update(enemies.banks(peek, cmap))
    out, changed = splice(nex, new)
    return out, {'banks changed': changed}


def sheets(z80, out_dir, prefix=RECORD, colours=None, say=print, enhanced=None):
    """<prefix>_PAINTING_SPRITES.png + _REFERENCE_ALL_SPRITES.png from the frames in the snapshot: all
    eight of Dan's frames, whole; every pixel of the 16-wide window is paintable (outlines too)."""
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    snap = Snapshot.get(z80)
    ram = bytes(snap.ram(-1)) if hasattr(snap, 'ram') else bytes(snap.memory[0x4000:])
    peek = lambda a: ram[a - 0x4000]
    xoff = frame_windows(peek)
    comps = []
    for f in range(NFRAMES):
        a = frame_addr(peek, f)
        px, ent = [], {}
        for r in range(24):
            for col in range(16):
                c = xoff[f] + col
                if c >= 24:
                    continue
                addr = a + (r + 2) * 3 + c // 8
                bit = c % 8
                ink = peek(addr) & (128 >> bit)
                key = '%04X' % addr
                px.append((col, r, key, bit, 1 if ink else 0, DAN_DEFAULT if ink else 0))
                ent[key] = [peek(addr), 'g']
        part = {'id': 'dan:%d' % f, 'size': 1, 'w': 16, 'h': 24, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
                'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}
        comps.append({'count': 1, 'group': 0, 'parts': [part]})
    if enhanced is None:
        enhanced = os.environ.get('NEXCLASH_REWORK') == ENHANCED
    if enhanced:
        from . import dynamite_dan_enemies as enemies
        comps += enemies.composites(peek)
    cmap = colours if colours is not None else load_colours(enhanced)
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(peek, enhanced)
    n1 = cs.write(comps if enhanced else cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json',
                  rgb, colours=cmap, paint_clear=True, identity=ident, all_swatches=True, width=384 if enhanced else 160)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json',
                  rgb, colours=cmap, paint_clear=True, identity=ident, all_swatches=True, width=384 if enhanced else 160)
    say('Sheets    : painting %d figures, reference %d' % (n1, n2))



# ---------------------------------------------------------------------------------------------
# v1.1 define keys (rework v11, NEXCLASH_REWORK=dynamite_dan_v11): QUIT and PAUSE definable on the game's own
# define-keys screen. Our code is asm/dynamite_dan_keys.asm (profile dynamite_dan_keys); the page text is rewritten
# from the player's own snapshot (no game bytes stored). Laid over the sprite build's RAM banks 5/2/0 (the bytes
# that differ from the snapshot only), so every other byte of the .nex is the v1.0 build's.
# ---------------------------------------------------------------------------------------------

KEYS_REWORK = 'dynamite_dan_v11'
KEYS_TEXT = 0xFD93              # the define-keys page's text records (row, column, characters; 0xFE between, 0xFF last)
KEYS_TEXT_END = 0xFE0C          # where the rewritten text ends and our data starts
KEYS_ALLOWED = (set(range(0xC835, 0xC837)) | set(range(0xC83A, 0xC83D)) | set(range(0xF2EE, 0xF2F1))
                | set(range(KEYS_TEXT, 0xFE2B)) | set(range(0xFF11, 0xFFA0)))


def _page_records(get, a):
    out = []
    while True:
        s = a
        a += 2
        while get(a) not in (0xFE, 0xFF):
            a += 1
        out.append(bytes(get(x) for x in range(s, a)))
        if get(a) == 0xFF:
            return out
        a += 1


def keys_ram(get):
    """{address: byte} of the v1.1 define-keys build over the snapshot's RAM (get = the original's peek): our blocks
    from the profile, and the page text with the Q / P warning record (row 7) dropped and "CHOOSE 3" made
    "CHOOSE 5". Only addresses whose byte changes; refuses a snapshot whose page is not the expected one."""
    h = json.load(open(os.path.join(_HERE, '..', 'docs', 'profiles', 'dynamite_dan_keys.json')))['hooks']
    new = {}
    ro = _page_records(get, KEYS_TEXT)
    if len(ro) != 6 or ro[2][:2] != b'\x07\x03' or b'\x27\x03\x27' not in ro[1]:
        raise ValueError('define-keys page text is not the expected one')
    text = b'\xFE'.join([ro[0], ro[1].replace(b'\x27\x03\x27', b'\x27\x05\x27'), ro[3], ro[4], ro[5]]) + b'\xFF'
    if KEYS_TEXT + len(text) != KEYS_TEXT_END:
        raise ValueError('define-keys page text: %d bytes, want %d' % (len(text), KEYS_TEXT_END - KEYS_TEXT))
    for i, v in enumerate(text):
        new[KEYS_TEXT + i] = v
    for key, at in (('c834', 0xC834), ('c83a', 0xC83A), ('f2ee', 0xF2EE), ('data', 0xFE0C), ('code', 0xFF11)):
        for i, v in enumerate(bytes.fromhex(h[key])):
            new[at + i] = v
    diff = {a: v for a, v in new.items() if get(a) != v}
    bad = sorted(a for a in diff if a not in KEYS_ALLOWED)
    hooks = set().union(*(range(a, SITE_NEXT[a]) for a in SITES_ORIG))
    if bad or set(diff) & hooks:
        raise ValueError('define keys would write outside its ranges: %s' % ['%04X' % a for a in (bad or sorted(set(diff) & hooks))])
    return diff


def define_keys(nex, z80):
    """The sprite build (.nex bytes) with the v1.1 define-keys bytes laid over banks 5/2/0 -> .nex bytes."""
    from . import z80tonex as zt
    from .recolour import banks, splice
    snap = zt.Z80Snapshot(z80)
    diff = keys_ram(snap.read)
    have = banks(nex)
    new = {b: bytearray(have[b]) for b in (5, 2, 0)}
    for a, v in diff.items():
        new[(5, 2, 0)[(a >> 14) - 1]][a & 0x3FFF] = v
    return splice(nex, {b: bytes(d) for b, d in new.items()})[0]

# ---------------------------------------------------------------------------------------------
# auto
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : dynamite_dan (Dan plotter 0xD1CE -> overlay sprites, ULA kept)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    st0 = os.path.join(out, name + '_start.z80')
    derive_start(z80, st0)
    say('Start     : the snapshot\'s own BASIC (PAUSE 0, then RANDOMIZE USR 51200) on Sinclair\'s ROM, the whole alt ROM '
        'image; %s (%s) is only the state the airship capture runs from' % (os.path.basename(st0), md5(st0)))
    src = z80
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(src, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = check(plain, src, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    enhanced = os.environ.get('NEXCLASH_REWORK') == ENHANCED
    patch = DanPatch(start=st0, enhanced=enhanced)
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(src, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, src, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    if enhanced or os.environ.get('NEXCLASH_REWORK') == KEYS_REWORK:   # v1.1: QUIT and PAUSE definable (the published default)
        data = define_keys(open(spr, 'rb').read(), src)
        open(spr, 'wb').write(data)
        say('Keys      : v1.1 define keys (QUIT, PAUSE) laid over the RAM banks: %s  %s' % (os.path.basename(spr), md5(spr)))
    if enhanced:
        from . import coloursheet as cs
        cmap = load_colours(True)
        cs.save(cmap, os.path.splitext(spr)[0] + '_colours.json', map_note(cmap))
        sheets(z80, out, name, cmap, say, enhanced=True)
    ok = not bad and not bad2
    states = []
    negs = negative_patches(patch) if a.rzx else []
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, Dan plots %d, clears 0xE801 %d, clears 0xE820 %d, end %d, %d sprite pixels -> %s' % (
            os.path.basename(r), c['frames'], c['dan'], c['cls 0xE801'], c['cls 0xE820'], c['end'],
            c['sprite pixels compared'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        if enhanced:
            say('Enemies   : %s' % {k: v for k, v in c.items() if k.startswith(('enemy', 'erase', 'load', 'suppressed'))})
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
    if states:
        u = unit_tests(patch, states, negs)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : Dan %d, clears %d, end %d, negative controls %d/%d -> %s' % (
            u['Dan cases ok'], u['screen clear cases ok'], u['end-of-game hide cases ok'], u['negative control detected'],
            u['negative control detected'] + u['negative control NOT DETECTED!'], 'PASS' if not uf else 'FAIL %s' % uf))
        if enhanced:
            from . import dynamite_dan_enemies as enemies
            say('Enemy unit: %s' % enemies.unit_tests(patch, states[0]))
        say('Clocks    : %d cases' % u['clock matrix cases'])
        for k, v in sorted(u.items()):
            if k.startswith('negative control ') and k not in ('negative control detected',):
                say('            %s: %d' % (k, v))
            if k.startswith('  '):
                say('            %s' % k)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
