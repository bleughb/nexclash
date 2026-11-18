"""Heartland (Odin, 1986, 48K) engine 'heartland'. Additive module: reachable only through is_heartland(). Facts, design, results: games/heartland.md.

Every game step composes the play window in a back buffer at 0xC000: each figure is saved, then (buffer AND mask) OR graphic; the foreground
pieces go on top, the buffer is copied to the screen, the figures are put back. The build turns the plotters' buffer writes (and the paint of
bright white under a large figure) into reads of the same length and time, so the buffer never holds a figure and nothing else of the game
changes; three hooks note what each plotter was given, one hook at the screen copy shows the noted figures as sprites (asm/heartland_hooks.asm).
The snapshot is the tape's BASIC start: the game moves itself down by 0x6AC bytes when it runs, so every site is patched 0x6AC above its
address in play.
"""
import collections
import hashlib
import json
import os

from . import hooklib

ROM_ORG = 0x386E
ALT_PAGE, WORK = 24, 26               # ALT_PAGE: also the RAM copy the hooks map at slot 1 (the bodies from 0x2000)
OFF = 0x6AC                         # snapshot address = address in play + OFF (the LDIR at 0xE436)
TAIL_ADDR = 0x5E00                  # BASIC's spare memory in the snapshot; the game's own move overwrites it before any read
BIG, MIR, SMALL, PAINT, COPY, ACOPY, RANDOM, CLS, STEP = 0xA7D4, 0xA88D, 0xA837, 0xA790, 0xA56F, 0xA615, 0xBBF4, 0x5E61, 0xA4CA
SITES_ORIG = {BIG: ('010000', 'e_big'), MIR: ('010000', 'e_mir'), SMALL: ('010000', 'e_small'), PAINT: ('0603dd', 'e_paint'),
              COPY: ('2119ac', 'e_commit'), ACOPY: ('3aa5bc', 'e_acopy'), RANDOM: ('ed5fee', 'e_random'), CLS: ('110140', 'e_cls')}
EXIT = {BIG: 0xA7D7, MIR: 0xA890, SMALL: 0xA83A, PAINT: 0xA795, COPY: 0xA572, ACOPY: 0xA618, RANDOM: 0xBBFB, CLS: 0x5E64}
KIND = {BIG: 0, MIR: 1, SMALL: 2}
INTERIORS = tuple(a + k for a in SITES_ORIG for k in (1, 2)) + (PAINT + 3, PAINT + 4, RANDOM + 3)
STORES = {}                         # no store is changed: the game's memory and the screen bitmap stay the original's
BUF, BUF_END = 0xC000, 0xD200
ATTR, ATTR_END = 0xD440, 0xD680     # the attribute copy the step paints and sends to the screen
SAVES = ((0xD790, 0xD9BC), (0xDB54, 0xDC2C))   # what each plotter saved from the buffer: differs where figures overlap
FGLIST, LINES = 0xA10B, 0xAC19
COV, FGC, V_N, V_PREV, V_SET, V_STP = 0x8000, 0x9200, 0x9244, 0x9245, 0x9246, 0x924A
STASH, ENTS, ATTRS, PBUF, TLO, THI = 0x9280, 0x9840, 0x9880, 0x9B00, 0x9E00, 0x9F00
MAXE, NSPR = 8, 48
V_PN, V_PP, SA_B, SA_O, PREC, PACE = 0x9262, 0x9263, 0x9269, 0x926B, 0x9970, 0x9A70
CELLS = ((0x5959, ATTR + 0x99), (0x5A5A, ATTR + 0x19A))     # the attribute cells the random byte can read, and their bytes in the copy
SPARKS = (0xFCF8, 0xFCFC)
STACK = 96                          # bytes below SP a hook may use (the interrupt handler itself goes 38 deep)
CMP = list(hooklib.CMP_R)
A_, F_, SP_, R_, PC_, T_, IFF_ = 0, 1, 12, 15, 24, 25, 26
ISR = 0xF3F3                        # the game's interrupt in play (IM 2, I = 0xFF, a table of 0xF3): JP 0x60F3

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'heartland_colours.json')
KT, MT, LPL, SPL, SPLN, EPL, EPLN, HPL = 0x2C00, 0x2D00, 0x2E00, 0x2F00, 44, 0x2F90, 13, 0x3000      # tables in the code page (asm)
ETAB = 0xE154                       # the 13 frames the game shifts into its buffer for the hero (3 bytes x 33)
PLANE_PAGE0 = 28                    # colour blocks: pages 28 up (banks 14 up), one at slot 6 for one loop
LTAB, STAB = 0xE10C, 0xE16E         # the game's frame tables in play
DEFAULT_LINE = [0x000, 0x1FF, 0x000, 0x007, 0x1C0, 0x1CF, 0x038, 0x03F, 0x1F8, 0x005, 0x140, 0x145, 0x028, 0x02D, 0x168, 0x16D]   # 9-bit: as the first build's .pal


def load_colours(path=None):
    """The painted map (docs/profiles/heartland_colours.json): palette lines and, per graphic address, its ink pixels' colours."""
    p = path or COLOURS
    return json.load(open(p)) if os.path.exists(p) else None


def play_view(snap_ram):
    """Memory as the game has it in play, from the snapshot's 48K (offset 0x4000): the game moves 0x61AC up down to 0x5B00,
    then 0xBFE0-0xDD88 of that up to 0xE10C (graphics and tables)."""
    lo = bytearray(0x10000)
    for a in range(0x5B00, 0x5B00 + 33432):
        lo[a] = snap_ram[a + OFF - 0x4000]
    for k in range(7593):
        lo[57612 + k] = lo[49120 + k]
    return bytes(lo)


def shifted(mem, p, b):
    """A 3-byte frame's 34 lines moved right by b into 4 bytes, as 0xA95C leaves them in the shift buffer."""
    out = bytearray()
    for r in range(34):
        v = (mem[p + 3 * r] << 24 | mem[p + 3 * r + 1] << 16 | mem[p + 3 * r + 2] << 8) >> b
        out += bytes((v >> 24 & 255, v >> 16 & 255, v >> 8 & 255, v & 255))
    return bytes(out)


def sums(g):
    """The hook's keys for a shift buffer's content: (sum, sum of running sums, rotate-and-XOR), 8 bits each."""
    a = b = x = 0
    for v in g:
        x = ((x << 1 | x >> 7) & 255) ^ v
        a = (a + v) & 255
        b = (b + a) & 255
    return a, b, x


def which_frame(mem, g):
    """-> the address of the frame of 0xE154 whose shifted copy g is, by its bytes; None when it is none of them."""
    for f in range(EPLN):
        p = mem[ETAB + 2 * f] | mem[ETAB + 2 * f + 1] << 8
        if any(shifted(mem, p, b) == g for b in range(8)):
            return p
    return None


def ink_bits(g, w, h):
    """[(x, y)] of a graphic's ink pixels, row by row."""
    return [(x, y) for y in range(h) for x in range(w * 8) if g[y * w + x // 8] >> (7 - x % 8) & 1]


def figure_colours(cmap, addr, g, w, h):
    """{(x, y): colour index} of a graphic's ink pixels and its palette line; ({}, 0) when it is not painted."""
    f = (cmap or {}).get('figures', {}).get('0x%04X' % addr)
    if not f:
        return {}, 0
    ink = f['ink']
    return {xy: int(ink[j], 16) if j < len(ink) else 1 for j, xy in enumerate(ink_bits(g, w, h))}, f['line']


def _block(cols, blocks):
    """Colours {(x, y): index} laid out as the patterns are: a 256-byte block = two 16 x 16 patterns side by side."""
    out = bytearray(256 * blocks)
    for (x, y), c in cols.items():
        if x >= 32 or y >= 16 * blocks:
            continue
        i = (y >> 4) * 256 + (x >> 4) * 128 + (y & 15) * 8 + ((x & 15) >> 1)
        out[i] |= c << 4 if not x & 1 else c
    return bytes(out)


def colour_tables(mem, cmap):
    """-> (LPL bytes, SPL bytes, {page: 8K}, palette of 256 9-bit words) for a painted map over the game's memory in play."""
    pal = [list(DEFAULT_LINE) for _ in range(16)]
    lpl, spl, epl, hpl, pages = bytearray(1), bytearray(3 * SPLN), bytearray(3 * EPLN), bytearray(1), {}
    if not cmap:
        return bytes(lpl), bytes(spl), bytes(epl), bytes(hpl), pages, [c for ln in pal for c in ln]
    for li, ln in enumerate(cmap['lines']):
        for k, (r, g, b) in enumerate(ln):
            pal[li + 1][3 + k] = (r * 7 + 127) // 255 << 6 | (g * 7 + 127) // 255 << 3 | (b * 7 + 127) // 255
    blob_l, blob_s, shifted_, keys = bytearray(), bytearray(), [], {}
    small_of = {}
    for n in range(SPLN):
        small_of.setdefault(mem[STAB + 2 * n] | mem[STAB + 2 * n + 1] << 8, []).append(n)
    for key, f in sorted(cmap['figures'].items()):
        addr = int(key, 16)
        if f['kind'] == 'shifted':      # the game shifts 34 lines of 3 bytes right by x AND 7 (7 - that, mirrored)
            cols, line = figure_colours(cmap, addr, mem[addr:addr + 102], 3, 34)
            for mir in (0, 1):
                blob = bytearray()
                for b in range(8):      # a block for each shift the buffer can hold
                    blob += _block({((31 - (x + b)) if mir else x + b, y): c for (x, y), c in cols.items()}, 3)
                shifted_.append((f['frame'], mir, line, bytes(blob)))
            for b in range(8):
                keys.setdefault(sums(shifted(mem, addr, b)), set()).add((b, f['frame'], shifted(mem, addr, b)))
        elif f['kind'] == 'large':
            g = mem[addr:addr + 136]
            cols, line = figure_colours(cmap, addr, g, 4, 34)
            k = len(blob_l) // 768
            blob_l += _block(cols, 3) + _block({(31 - x, y): c for (x, y), c in cols.items()}, 3)
            ent = [addr & 255, addr >> 8, line]
            for j in (k, k + 1):                # 10 blocks of 768 a page
                ent += [PLANE_PAGE0 + j // 10, 0xC0 + (j % 10) * 3]
            lpl += bytes(ent)
            lpl[0] += 1
        else:
            g = mem[addr:addr + 32]
            cols, line = figure_colours(cmap, addr, g, 2, 16)
            k = len(blob_s) // 2048             # 8 shifts of 256: 4 frames a page
            for sh in range(8):
                blob_s += _block({(x + sh, y): c for (x, y), c in cols.items()}, 1)
            for n in small_of.get(addr, []):
                spl[3 * n:3 * n + 3] = bytes((0x80 | k // 4, 0xC0 + (k % 4) * 8, line))
    if lpl[0] > 28:
        raise ValueError('more than 28 painted large graphics')
    nl = (len(blob_l) // 768 + 9) // 10
    for i in range(nl):
        pages[PLANE_PAGE0 + i] = bytes(blob_l[i * 7680:(i + 1) * 7680]).ljust(8192, b'\0')
    for n in range(SPLN):
        if spl[3 * n] & 0x80:
            spl[3 * n] = PLANE_PAGE0 + nl + (spl[3 * n] & 0x7F)
    for i in range((len(blob_s) + 8191) // 8192):
        pages[PLANE_PAGE0 + nl + i] = bytes(blob_s[i * 8192:(i + 1) * 8192]).ljust(8192, b'\0')
    pg = PLANE_PAGE0 + len(pages)
    for fn, mir, line, blob in shifted_:
        pages[pg] = blob.ljust(8192, b'\0')
        epl[3 * fn + mir], epl[3 * fn + 2] = pg, line
        pg += 1
    for key, who in sorted(keys.items()):
        if len({w[2] for w in who}) > 1:
            raise ValueError('two shifted frames share the keys %s' % (key,))
        sh, fn, _ = sorted(who)[0]
        hpl += bytes(key + (sh, fn))
        hpl[0] += 1
    return bytes(lpl), bytes(spl), bytes(epl), bytes(hpl), pages, [c for ln in pal for c in ln]




def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'heartland.json'), os.path.join(_HERE, 'heartland.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('heartland.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_heartland(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bool(sig) and bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def _whole_rom_page(stubs=b'', code=b''):
    """Image of 0x2000-0x3FFF: Sinclair's ROM with `stubs` at ROM_ORG (its 0xFF area; this part goes to alt ROM image 1)
    and `code` from 0x2000 (only in the RAM page the hooks map at slot 1)."""
    from .build import rom48
    rom = rom48()
    if any(b != 0xFF for b in rom[ROM_ORG:ROM_ORG + len(stubs) + 20]):
        raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
    page = bytearray(rom[0x2000:0x4000])
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(stubs)] = stubs
    page[0:len(code)] = code
    return bytes(page)


def work_page():
    """The hook page as the build starts: the two nibble tables, an empty stash, a foreground list that matches nothing."""
    pg = bytearray(8192)
    pg[FGC - 0x8000] = 0xFF
    pg[V_STP - 0x8000:V_STP - 0x8000 + 2] = STASH.to_bytes(2, 'little')
    pg[V_PP - 0x8000:V_PP - 0x8000 + 2] = PREC.to_bytes(2, 'little')
    for g in range(16):
        for m in range(16):
            px = [1 if g & (8 >> k) else 0 if m & (8 >> k) else 2 for k in range(4)]
            pg[TLO - 0x8000 + g * 16 + m] = px[0] << 4 | px[1]
            pg[THI - 0x8000 + g * 16 + m] = px[2] << 4 | px[3]
    return pg


class PlainPatch:
    """The plain .nex: no hooks. Alt ROM image 1 = Sinclair's 48K ROM, so the snapshot's BASIC (PAUSE 0, then RANDOMIZE USR 25000) runs as on a 48K."""
    name = 'Heartland plain conversion, Sinclair\'s ROM as the alt ROM'
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


class HeartlandPatch:
    name = 'Heartland figures -> hardware sprites (altrom stubs, bodies in a page at slot 1, state in a page at slot 4)'

    def __init__(self, prof=None, rom_code=None, stores=None, work=None, code=None, colours=None, z80=None, blank=0):
        self.prof = prof or load_profile()
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
        self.code = bytes.fromhex(h['code']) if code is None else code
        self.z80 = z80
        self.blank = blank              # empty colour pages, so the plain build has the banks the painted one has (.nxc sets)
        self.colours = colours          # a painted map: the Enhanced build (it needs the game's graphics: z80, or apply)
        self.planes = {}
        self.tables(None)
        if z80 is not None:
            from .z80tonex import Z80Snapshot
            sn = Z80Snapshot(z80)
            self.tables(play_view(bytes(sn.banks[5]) + bytes(sn.banks[2]) + bytes(sn.banks[0])))
        self.stores = STORES if stores is None else stores
        self.sites = []                 # addresses in play; the snapshot holds them OFF higher
        for a, (old, sym) in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old), b'\xC3' + self.syms[sym].to_bytes(2, 'little')))
        for a, (old, new) in self.stores.items():
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        for a, old, new in self.sites:  # the random byte reads address A * 257: no changed byte may sit at one
            if any((a + k) >> 8 == (a + k) & 255 for k in range(len(new))):
                raise ValueError('site 0x%04X changes a byte the random routine can read' % a)
        self.work = bytes(work_page() if work is None else work)
        self._banks()

    def tables(self, mem):
        """The code page's tables, the colour blocks' pages and the palette; mem = the game's memory in play, None = unpainted."""
        lpl, spl, epl, hpl, self.planes, pal = colour_tables(mem, self.colours) if mem is not None else colour_tables(None, None)
        page = bytearray(_whole_rom_page(self.rom_code, self.code))
        if len(self.code) > KT - 0x2000:
            raise ValueError('hook bodies run into their tables')
        for b in range(256):
            hi, lo = b >> 4, b & 15
            page[KT - 0x2000 + b] = (0 if hi == 1 else hi) << 4 | (0 if lo == 1 else lo)
            page[MT - 0x2000 + b] = (15 if hi == 1 else 0) << 4 | (15 if lo == 1 else 0)
        page[LPL - 0x2000:LPL - 0x2000 + len(lpl)] = lpl
        page[SPL - 0x2000:SPL - 0x2000 + len(spl)] = spl
        page[EPL - 0x2000:EPL - 0x2000 + len(epl)] = epl
        page[HPL - 0x2000:HPL - 0x2000 + len(hpl)] = hpl
        self.page = bytes(page)
        st = bytearray(bytes.fromhex(self.prof['hooks']['setup']))
        o = self.syms['pal9'] - 0xD000
        for i, c in enumerate(pal):
            st[o + 2 * i], st[o + 2 * i + 1] = c >> 1, c & 1
        self.stub_extra = bytes(st)
        self.palette = pal
        if not self.planes and self.blank:
            self.planes = {PLANE_PAGE0 + i: bytes(8192) for i in range(self.blank)}
        if hasattr(self, 'work'):
            self._banks()

    def _banks(self):
        self.extra_banks = {12: self.page + bytes(8192), 13: self.work + bytes(8192)}
        for pg, data in self.planes.items():
            cur = self.extra_banks.get(pg // 2, bytes(16384))
            o = (pg & 1) * 8192
            self.extra_banks[pg // 2] = cur[:o] + data + cur[o + 8192:]

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Heartland patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            o = a + OFF - 0x4000
            if bytes(ram[o:o + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a + OFF, bytes(ram[o:o + len(old)]).hex(), old.hex()))
        if bytes(ram[0xE436 - 0x4000:0xE436 - 0x4000 + 11]) != bytes.fromhex('21ac6111005b019882edb0'):
            raise ValueError('the game\'s move (0xE436) is not the expected one')
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + 256]):
            raise ValueError('tail area is not empty in this snapshot')
        for a, old, new in self.sites:
            o = a + OFF - 0x4000
            ram[o:o + len(new)] = new
        if self.colours and not self.planes:
            self.tables(play_view(bytes(snap.banks[5]) + bytes(snap.banks[2]) + bytes(snap.banks[0])))
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


# ---------------------------------------------------------------------------------------------
# The Next side, as a hook sees it
# ---------------------------------------------------------------------------------------------

class State:
    """What stays between hooks: the state page, sprite patterns and attributes, the sprite window."""
    def __init__(self, patch):
        self.work = bytearray(patch.work)
        self.pattern = bytearray(16384)
        self.attrs = [[0] * 5 for _ in range(128)]
        self.clip = [0, 255, 48, 191]
        self.t = collections.Counter()  # real time in hooks by site, 3.5 MHz T


class View:
    """64K as the hooks see it: the alt ROM image (or its RAM copy with the bodies, at slot 1), the game's RAM, the state
    page at slot 4 when NextReg 0x54 names it."""
    def __init__(self, mem, rom, page, work, planes=None):
        self.mem, self.rom, self.page, self.work, self.planes = mem, rom, page, work, planes or {}
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if a < 0x2000:
            return self.rom[a]
        if a < 0x4000:
            return self.page[a - 0x2000] if self.model.nr.get(0x51, 255) == ALT_PAGE else self.rom[a]
        if 0x8000 <= a < 0xA000 and self.model.nr.get(0x54, 4) == WORK:
            return self.work[a - 0x8000]
        if 0xC000 <= a < 0xE000 and self.model.nr.get(0x56, 0):
            return self.planes[self.model.nr[0x56]][a - 0xC000]
        return self.mem[a]

    def __setitem__(self, a, v):
        if a < 0x4000:
            if a >= 0x2000 and self.model.nr.get(0x51, 255) == ALT_PAGE:
                self.model.c['write to the code page!'] += 1
            return
        if 0x8000 <= a < 0xA000 and self.model.nr.get(0x54, 4) == WORK:
            self.work[a - 0x8000] = v
            return
        if 0xC000 <= a < 0xE000 and self.model.nr.get(0x56, 0):
            self.model.c['write to a colour page!'] += 1
            return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, st, speed=0):
        super().__init__(sim, speed)
        self.pattern, self.attrs = st.pattern, st.attrs
        self.st = st
        self.clipi = 0

    def nextreg(self, reg, v):
        if reg == 0x34:                 # without lockstep (NR 0x09 bit 4, off) this is not the attribute port's index
            self.nr[reg] = v
            return
        if reg == 0x1C and v & 2:
            self.clipi = 0
        elif reg == 0x19:
            self.st.clip[self.clipi & 3] = v
            self.clipi += 1
        super().nextreg(reg, v)


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def run_hook(patch, st, rom, mem, regs, site, ret=None, limit=4000000, irq=None):
    """Run the patched code from `site` (its JP into the hook) on a copy of the game's memory, to the site's exit or, for a
    hook that wraps the game's routine, to the routine's return (`ret` = (address, SP there)). irq = k: the game's interrupt
    is taken after k instructions (when interrupts are on there). -> (registers, the copy, model); model.n = instructions run."""
    from . import simpool
    m2 = bytearray(mem)
    for a, old, new in patch.sites:
        m2[a:a + len(new)] = new
    v = View(m2, rom, patch.page, st.work, patch.planes)
    s = simpool.machine(_rw(), v, list(regs), 'heartland-hook')
    model = Model(s, st)
    v.model = model
    R = s.registers
    R[PC_] = site
    stop, sp0 = EXIT[site], regs[SP_]
    n = 0
    while True:
        s.opcodes[v[R[PC_]]]()
        n += 1
        pc = R[PC_]
        if n == irq and R[IFF_]:
            model.irq = (pc, dict(model.nr))
            sp = (R[SP_] - 2) & 0xFFFF
            v[sp], v[sp + 1] = pc & 255, pc >> 8
            R[SP_], R[PC_], R[IFF_] = sp, ISR, 0
            continue
        if pc == stop and R[SP_] == sp0 and model.nr.get(0x51, 255) == 255 and not model.nr.get(0x56, 0):
            break
        if ret and pc == ret[0] and R[SP_] == ret[1] and model.nr.get(0x51, 255) == 255:
            break
        if n > limit:
            raise AssertionError('hook at %04X did not end (PC %04X)' % (site, pc))
    st.t[site] += model.now()
    model.n = n
    for a, old, new in patch.sites:
        m2[a:a + len(old)] = old
    return list(R), m2, model


def run_orig(rom, mem, regs, stop, sp=None, limit=4000000):
    """The original from the registers' PC until PC = stop (and SP = sp when given), on a copy. -> (registers, the copy)."""
    from . import simpool
    m2 = bytearray(rom) + bytearray(mem[0x4000:])
    s = simpool.machine(_rw(), m2, list(regs), 'heartland-orig')
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


def sprite_bits(st):
    """{(x, y) in the buffer: 0 the border, else colour index | palette line << 4} from the shown sprites, in order, inside
    the sprite window."""
    out = {}
    x1, x2, y1, y2 = st.clip
    for n, a in enumerate(st.attrs):
        if not a[3] & 0x80:
            continue
        x = a[0] | (a[2] & 1) << 8
        y = a[1]
        q = (a[3] & 63) * 2 + (1 if a[4] & 0x40 else 0)
        if not a[4] & 0x80:
            raise AssertionError('sprite %d is not a 4-bit pattern' % n)
        pat = st.pattern[q * 128:q * 128 + 128]
        for py in range(16):
            sy = y + py - 32
            if not y1 <= sy <= y2:
                continue
            for px in range(16):
                b = pat[py * 8 + px // 2]
                c = b >> 4 if not px & 1 else b & 15
                if c and x1 <= x + px - 32 <= x2:
                    out[(x + px - 32, sy - 48)] = 0 if c == 2 else c | (a[2] >> 4) << 4
    return out


def coverage(mem):
    """The pixels the foreground pieces own, from the game's list by its own plot rule (0xA09B): data OR NOT mask."""
    cov = bytearray(BUF_END - BUF)
    n = mem[FGLIST]
    for i in range(n):
        e = FGLIST + 1 + 4 * i
        a, p = mem[e] | mem[e + 1] << 8, mem[e + 2] | mem[e + 3] << 8
        w, h = mem[p + 1], mem[p + 2]
        d, k = p + 3, p + 256
        for _ in range(h):
            for _ in range(w):
                if BUF <= a < BUF_END:
                    cov[a - BUF] |= mem[d] | (~mem[k] & 255)
                a = (a & 0xFF00) | ((a + 1) & 255)
                d += 1
                k += 1
            a = ((a & 0xFF00) | ((a - w) & 255)) + 32
    return cov


_REV = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))


def expected_layer(figs, cov, lines, cmap=None, mem=None):
    """What the sprites must show: the noted figures in plot order by the plotters' rule, minus the pieces' pixels. A pixel
    is 0 (the mask's border) or its colour index | palette line << 4: the painted map's colour for that ink pixel of the
    graphic, counted in the graphic's own row order (so a shifted or mirrored figure is checked against the unshifted map)."""
    pic = {}
    for kind, buf, g, m, ident in figs:
        w, h = (3, 16) if kind == 2 else (4, 34)
        ink, line = None, 0
        if cmap and ident is not None and mem is not None:
            f = cmap['figures'].get('0x%04X' % ident)
            if f:
                ink, line = f['ink'], f['line']
        rank, j = {}, 0
        for row in range(h):
            for sx in range(w * 8):
                if g[row * w + sx // 8] >> (7 - sx % 8) & 1:
                    rank[(row, sx)] = j
                    j += 1
        a = buf
        for row in range(h):
            for k in range(w):
                gb, mb = g[row * w + k], m[row * w + k]
                col = k
                if kind == 1:
                    gb, mb, col = _REV[gb], _REV[mb], 3 - k
                at = (a & 0xFF00) | ((a + col) & 255)
                own = cov[at - BUF] if BUF <= at < BUF_END else 0
                y, x0 = (at - BUF) >> 5, ((at - BUF) & 31) * 8
                if not 0 <= y < lines:
                    continue
                for b in range(8):
                    bit = 128 >> b
                    if own & bit:
                        continue
                    if gb & bit:
                        r = rank[(row, k * 8 + (7 - b if kind == 1 else b))]
                        c = int(ink[r], 16) if ink and r < len(ink) else 1
                        pic[(x0 + b, y)] = c | line << 4
                    elif not mb & bit:
                        pic[(x0 + b, y)] = 0
            a += 32
    return pic


def paint_cells(mem, hl, x):
    """The cells 0xA790 paints for a figure at buffer address hl, x = its record's +9: [address in the copy]."""
    b = 4 if x & 7 else 3
    a = ATTR + 32 + ((hl >> 11) & 3) * 256 + ((hl >> 8) & 7) * 32 + (hl & 31)
    out = []
    for _ in range(4):
        out += [a + k for k in range(b)]
        a += 32
    return out


def in_play(m):
    """The game has moved itself: the routines are where the sites expect them."""
    return bytes(m[BIG:BIG + 3]) == b'\x01\x00\x00' and bytes(m[COPY:COPY + 3]) == b'\x21\x19\xac' and bytes(m[STEP:STEP + 3]) == b'\xcd\xe8\xa5'


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original (PLAYBOOK 6). At every hook site the patched code runs on a copy of the state, the Next side
    carried from site to site, and must leave every register (R too) and all the game's memory as the original does:
    the replaced instruction for the notes, the whole routine for the two copies, the random routine's byte. Only the
    attribute file may differ, by the paint the build keeps off the screen: there the build's must be the game's own copy
    run on colours without the paint. At every screen copy the sprites must be the noted figures by the plotters' rule
    (an independent model) and lie on the same pixels of the buffer. -> (Counter, examples, states)."""
    from . import rzx as RZ
    from .nextboot import alt_image
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    kept = collections.Counter()
    rom = bytes(alt_image(patch))
    st = State(patch)
    box = {'figs': [], 'sparks': set(), 'paint': [], 'oa': None, 'ba': None, 'orig_t': collections.Counter()}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(ex[key]) < 5:
            ex[key].append(detail)

    def same(name, pc, Ro, mo, Rp, mp, sp, screen=True):
        bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
        if bad:
            fail('registers after %s' % name, (c['frame'], bad))
        lo = 0x4000 if screen else 0x5B00
        if mp[lo:sp - STACK] != mo[lo:sp - STACK] or mp[sp:] != mo[sp:]:      # below SP: dead stack, the interrupt's too
            fail('%s writes game memory' % name, [hex(a) for a in range(lo, 65536) if mp[a] != mo[a] and not sp - STACK <= a < sp][:8])
        if screen is False and mp[0x4000:0x5800] != mo[0x4000:0x5800]:
            fail('%s writes the bitmap' % name, c['frame'])
        low = next((a for a in range(sp - STACK, sp) if mp[a] != mo[a]), sp)
        c['lowest stack byte a hook writes'] = min(c['lowest stack byte a hook writes'] or 65536, low)

    def on(pc, sim):
        if box.get('dead'):
            return
        try:
            on_(pc, sim)
        except AssertionError as e:     # a hook that never comes back: no use going on
            box['dead'] = True
            fail('a hook does not end', str(e))

    def on_(pc, sim):
        m, R = sim.memory, sim.registers
        if not in_play(m):
            return
        if pc == STEP:
            c['step'] += 1
            return
        if pc in SPARKS:                # the bolt: R-derived bytes XORed into three buffer lines after the figures
            box['sparks'].add((R[6] << 8 | R[7]) - BUF)
            return
        regs = list(R)
        mem = bytearray(m[0:65536])
        sp = regs[SP_]
        if collect and kept[pc] < collect:
            kept[pc] += 1
            states.append((pc, bytes(mem), tuple(regs), bytes(st.work)))
        if pc == CLS:                   # the whole screen cleared: the game leaves the play picture
            c['screen clear'] += 1
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc)
            Ro, mo = run_orig(rom, mem, regs, EXIT[pc])
            same('the hook at %04X' % pc, pc, Ro, mo, Rp, mp, sp)
            if any(a[3] & 0x80 for a in st.attrs):
                fail('sprites left on a cleared screen', c['screen clear'])
            box['figs'], box['paint'] = [], []
            return
        if pc in KIND or pc == PAINT:
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc)
            Ro, mo = run_orig(rom, mem, regs, EXIT[pc])
            same('the hook at %04X' % pc, pc, Ro, mo, Rp, mp, sp)
            if pc == PAINT:
                c['paint'] += 1
                box['paint'] += [(a, mem[a]) for a in paint_cells(mem, regs[6] << 8 | regs[7], mem[(regs[8] << 8 | regs[9]) + 9])]
                return
            c['plot'] += 1
            kind = KIND[pc]             # the plotter's arguments: HL = mask, DE = graphic, HL' = buffer
            g, mk, buf = regs[4] << 8 | regs[5], regs[6] << 8 | regs[7], regs[22] << 8 | regs[23]
            n = 48 if kind == 2 else 136
            ix = regs[8] << 8 | regs[9]
            if kind == 2:               # the frame the shift buffer was made from: the record's +13 through the game's table
                fn = mem[ix + 13]
                ident = (mem[STAB + 2 * fn] | mem[STAB + 2 * fn + 1] << 8) if fn < SPLN else None
            else:
                ident = g if g >= 0xE000 else which_frame(mem, bytes(mem[g:g + 136]))
            box['figs'].append((kind, buf, bytes(mem[g:g + n]), bytes(mem[mk:mk + n]), ident))
            return
        if pc == RANDOM:
            c['random'] += 1
            Ro, mo = run_orig(rom, mem, regs, EXIT[pc])
            # the build's memory: the original's, with the attribute file as the build's last copy left it
            mb = bytearray(mem)
            if box['oa'] is not None:
                for a, _ in CELLS:
                    if mem[a] == box['oa'][a - 0x5800]:
                        mb[a] = box['ba'][a - 0x5800]
            Rp, mp, model = run_hook(patch, st, rom, mb, regs, pc)
            for a, _ in CELLS:
                mp[a] = mem[a]
            same('the random byte', pc, Ro, mo, Rp, mp, sp)
            ad = Ro[6] << 8 | Ro[7]
            if 0x4000 <= ad < 0x5B00:
                c['random bytes read from the screen'] += 1
            if ad in (0x5959, 0x5A5A) and mb[ad] != mem[ad]:
                c['random bytes read where the paint is lifted'] += 1
            return
        ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
        if pc == COPY:
            c['copy'] += 1
            lines = 144 if mem[LINES] & 1 else 112
            figs, box['figs'] = box['figs'], []
            sparks, box['sparks'] = box['sparks'], set()
            Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, ret)
            if Rp[PC_] != ret[0]:       # the plain way out: the game's copy follows, as the original
                Rp, mp = run_orig(rom, mp, Rp, ret[0], ret[1])
                c['copy without figures'] += 1
            else:
                box['orig_t'][COPY] += Ro[T_] - regs[T_]
                ex['copy T by lines and figures'] = sorted(set(ex['copy T by lines and figures']) | {(lines, Ro[T_] - regs[T_])})[:6]
                tn = box.setdefault('tn', collections.Counter())
                tn['n'] += 1
            same('the screen copy', pc, Ro, mo, Rp, mp, sp)
            if model.nr.get(0x54, 4) != 4 or model.nr[7] & 3:
                fail('the screen copy leaves its page or its speed', (model.nr.get(0x54), model.nr[7]))
            if not model.burst_ok():
                fail('attributes split by pattern uploads', c['copy'])
            if model.c['write to the code page!'] or model.c['upload into a shown pattern!'] or model.c['write to a colour page!']:
                fail('a write to the code page or to a shown pattern', dict(model.c))
            c['figures'] += len(figs)
            c['most figures'] = max(c['most figures'], len(figs))
            c['most sprites'] = max(c['most sprites'], sum(1 for a in st.attrs if a[3] & 0x80))
            want = expected_layer(figs, coverage(mem), lines, patch.colours, mem)
            c['painted pixels'] += sum(1 for v in want.values() if v > 1)
            got = sprite_bits(st)
            c['sprite pixels compared'] += len(want)
            if want != got:
                d = [k for k in set(want) | set(got) if want.get(k) != got.get(k)]
                fail('the sprites are not the noted figures', (c['copy'], len(d), sorted(d)[:4], [(f[0], hex(f[1])) for f in figs]))
            for (x, y), v in want.items():      # each sprite pixel lies on the same pixel of the game's own picture
                a = y * 32 + (x >> 3)
                if mem[BUF + a] >> (7 - (x & 7)) & 1 != (1 if v else 0):
                    if a in sparks:
                        c['bolt pixels the original XORs into a figure'] += 1
                    else:
                        c['sprite pixels off the figure in the buffer'] += 1
                        fail('a sprite pixel is not on its figure', (c['copy'], x, y, v))
            return
        # the attribute copy
        c['attribute copy'] += 1
        paint, box['paint'] = box['paint'], []
        Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, ret)
        if Rp[PC_] != ret[0]:
            Rp, mp = run_orig(rom, mp, Rp, ret[0], ret[1])
        else:
            box['orig_t'][ACOPY] += Ro[T_] - regs[T_]
        same('the attribute copy', pc, Ro, mo, Rp, mp, sp, screen=False)
        me = bytearray(mem)             # the model: the game's copy run on the colours without the paint
        lifted = 0
        for a, v in reversed(paint):
            if ATTR <= a < ATTR_END and me[a] == v | 0x47:
                lifted += me[a] != v
                me[a] = v
        Re, me = run_orig(rom, me, regs, ret[0], ret[1])
        c['cells with the paint lifted'] += lifted
        if mp[0x5800:0x5B00] != me[0x5800:0x5B00]:
            fail('the attribute file is not the copy without the paint', (c['attribute copy'], [hex(a) for a in range(0x5800, 0x5B00) if mp[a] != me[a]][:6]))
        c['attribute cells that differ from the original\'s'] += sum(1 for a in range(0x5800, 0x5B00) if mp[a] != mo[a])
        for j, (a, _) in enumerate(CELLS):
            if st.work[SA_B - 0x8000 + j] != mp[a] and st.work[SA_O - 0x8000 + j] != st.work[SA_B - 0x8000 + j]:
                fail('the build\'s colour kept for the random byte is wrong', (hex(a), st.work[SA_B - 0x8000 + j], mp[a]))
            if mp[a] != mo[a] and (st.work[SA_B - 0x8000 + j], st.work[SA_O - 0x8000 + j]) != (mp[a], mo[a]):
                fail('the original\'s colour kept for the random byte is wrong', (hex(a), st.work[SA_O - 0x8000 + j], mo[a]))
        box['oa'], box['ba'] = bytes(mo[0x5800:0x5B00]), bytes(mp[0x5800:0x5B00])

    pcs = {STEP, COPY, ACOPY, PAINT, RANDOM, CLS, BIG, MIR, SMALL} | set(SPARKS)
    fc, err = RZ.trace(rzx_path, pcs, on, stop=stop)
    c['frames'] = fc
    if err:
        c['replay stopped!'] += 1
        ex['replay'].append(err)
    for site, name in ((COPY, 'screen copy'), (ACOPY, 'attribute copy')):
        c['T original ' + name] = box['orig_t'][site]
        c['T hook ' + name] = int(st.t[site])
    c['T hook notes'] = int(sum(st.t[k] for k in (BIG, MIR, SMALL, PAINT, RANDOM)))
    to, th = box['orig_t'][COPY] + box['orig_t'][ACOPY], sum(st.t.values())
    c['T original'], c['T hooks'] = to, int(th)
    if to and abs(th - to) > 0.01 * fc * 69888:     # within 1% of the recording's whole time
        fail('the hooks\' time is not the time of the copies they stand for', (to, int(th)))
    for k in (BIG, MIR, SMALL, PAINT, RANDOM, CLS):
        c['T hook at %04X' % k] = int(st.t[k])
    return c, dict(ex), states


def _differs(Ro, mo, Rp, mp, sp, screen=True):
    """What a hook left unlike the original: registers, or game memory outside the dead stack (and the attribute file when screen is False)."""
    bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
    lo = 0x4000 if screen else 0x5B00
    mem = [a for a in range(lo, 65536) if mp[a] != mo[a] and not sp - STACK <= a < sp][:6]
    if not screen:
        mem += [a for a in range(0x4000, 0x5800) if mp[a] != mo[a]][:3]
    return bad, mem


def unit_tests(patch, states, neg=None):
    """The paths the recordings do not reach, from captured states (site, memory, registers, state page)."""
    from .nextboot import alt_image
    c = collections.Counter()
    rom = bytes(alt_image(patch))
    by = collections.defaultdict(list)
    for pc, mem, regs, work in states:
        by[pc].append((bytearray(mem), list(regs), work))

    def fresh(work):
        st = State(patch)
        st.work = bytearray(work)
        return st

    def ok(name, cond):
        c[name if cond else name + '!'] += 1

    def w(st, a, v=None):
        if v is None:
            return st.work[a - 0x8000]
        st.work[a - 0x8000] = v

    # the screen copy with nothing noted and nothing shown: the game's own copy, one instruction replaced
    for mem, regs, work in by[COPY][:2]:
        st = fresh(work)
        w(st, V_N, 0)
        w(st, V_PREV, 0)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, COPY)
        Ro, mo = run_orig(rom, mem, regs, EXIT[COPY])
        ok('copy with no figures', Rp[PC_] == EXIT[COPY] and _differs(Ro, mo, Rp, mp, regs[SP_]) == ([], []) and not model.c['pattern bytes'])
        # figures gone since the last copy: every sprite off
        st = fresh(work)
        w(st, V_N, 0)
        w(st, V_PREV, 30)
        st.attrs[3][3] = 0xC1
        sp = regs[SP_]
        ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, COPY, ret)
        Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
        ok('copy after the figures left', _differs(Ro, mo, Rp, mp, sp) == ([], []) and not any(a[3] & 0x80 for a in st.attrs) and w(st, V_PREV) == 0)
        # 144 lines: the sprite window follows
        m2 = bytearray(mem)
        m2[LINES] |= 1
        st = fresh(work)
        Rp, mp, model = run_hook(patch, st, rom, m2, regs, COPY, ret)
        Ro, mo = run_orig(rom, m2, regs, ret[0], ret[1])
        ok('copy of 144 lines', _differs(Ro, mo, Rp, mp, sp) == ([], []) and st.clip == [0, 255, 48, 191])
        # a foreground list too long to keep: the coverage is made at every copy, and is the model's
        m2 = bytearray(mem)
        n0 = m2[FGLIST]
        if n0:
            for k in range(n0, 16):
                m2[FGLIST + 1 + 4 * k:FGLIST + 5 + 4 * k] = m2[FGLIST + 1:FGLIST + 5]
            m2[FGLIST] = 16
            st = fresh(work)
            Rp, mp, model = run_hook(patch, st, rom, m2, regs, COPY, ret)
            ok('foreground list of 16 pieces', bytes(st.work[0:BUF_END - BUF]) == bytes(coverage(m2)) and w(st, FGC) == 0xFF)
    # the attribute copy with no paint noted
    for mem, regs, work in by[ACOPY][:2]:
        sp = regs[SP_]
        ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
        st = fresh(work)
        w(st, V_PN, 0)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, ACOPY, ret)
        Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
        ok('attribute copy with no paint', Rp[PC_] == ret[0] and _differs(Ro, mo, Rp, mp, sp) == ([], []))
        # the three ways the game's copy goes, with the two readable cells painted
        sp = regs[SP_]
        ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
        for way, (mode, cnt, phase) in enumerate(((1, 9, 0), (0, 9, 3), (0, 9, 12), (0, 9, 8), (0, 1, 0))):
            m2 = bytearray(mem)
            m2[0xBCA5], m2[0xAC17], m2[0xAC18] = mode, cnt, phase
            st = fresh(work)
            w(st, V_PN, 0)
            st.work[V_PP - 0x8000:V_PP - 0x8000 + 2] = PREC.to_bytes(2, 'little')
            recs = []
            for _, cell in CELLS:
                v = 0x05 if cell == CELLS[0][1] else 0x02
                recs.append((cell, v))
                m2[cell] = v | 0x47
            for k, (cell, v) in enumerate(recs):
                st.work[PREC - 0x8000 + 3 * k:PREC - 0x8000 + 3 * k + 3] = bytes((cell & 255, cell >> 8, v))
            w(st, V_PN, len(recs))
            Rp, mp, model = run_hook(patch, st, rom, m2, regs, ACOPY, ret)
            Ro, mo = run_orig(rom, m2, regs, ret[0], ret[1])
            me = bytearray(m2)
            for cell, v in recs:
                me[cell] = v
            Re, me = run_orig(rom, me, regs, ret[0], ret[1])
            good = _differs(Ro, mo, Rp, mp, sp, screen=False) == ([], []) and mp[0x5800:0x5B00] == me[0x5800:0x5B00]
            for j, (a, _) in enumerate(CELLS):          # the random byte's answer for each cell is the original's colour
                good = good and (st.work[SA_B - 0x8000 + j] == mp[a] and st.work[SA_O - 0x8000 + j] == mo[a])
            ok('attribute copy, way %d' % way, good)
    # the random byte at every address, the build's memory the original's
    for mem, regs, work in by[RANDOM][:1]:
        bad = 0
        for h in range(256):
            m2 = bytearray(mem)
            r2 = list(regs)
            r2[R_] = (regs[R_] & 0x80) | ((h - 2) & 0x7F)
            m2[0xBBF7] = h & 0x80                       # the address is (R + 2) XOR this
            st = fresh(work)
            Rp, mp, model = run_hook(patch, st, rom, m2, r2, RANDOM)
            Ro, mo = run_orig(rom, m2, r2, EXIT[RANDOM])
            bad += _differs(Ro, mo, Rp, mp, r2[SP_]) != ([], []) or Ro[6] != h
        ok('random byte at 256 addresses', not bad)
        # the two cells: the original's colour while the build's is still there, the cell's own once written since
        for j, (a, _) in enumerate(CELLS):
            h = a >> 8
            m2 = bytearray(mem)
            r2 = list(regs)
            r2[R_] = (regs[R_] & 0x80) | ((h - 2) & 0x7F)
            m2[0xBBF7] = 0
            mo_ = bytearray(m2)
            mo_[a] = 0x47                               # the original's screen: painted
            m2[a] = 0x05                                # the build's: the room's colour
            st = fresh(work)
            w(st, SA_B + j, 0x05)
            w(st, SA_O + j, 0x47)
            Rp, mp, model = run_hook(patch, st, rom, m2, r2, RANDOM)
            Ro, mo = run_orig(rom, mo_, r2, EXIT[RANDOM])
            ok('random byte from a cell with the paint lifted', Rp[A_] == Ro[A_] == 0x47 and Rp[F_] == Ro[F_] and Rp[R_] == Ro[R_])
            m2[a] = mo_[a] = 0x31                       # something else wrote it since: the same byte in both
            st = fresh(work)
            w(st, SA_B + j, 0x05)
            w(st, SA_O + j, 0x47)
            Rp, mp, model = run_hook(patch, st, rom, m2, r2, RANDOM)
            Ro, mo = run_orig(rom, mo_, r2, EXIT[RANDOM])
            ok('random byte from a cell written since', Rp[A_] == Ro[A_] == 0x31)
    # more figures than the table holds, more shift-buffer copies than the stash holds, more cells than the paint list holds
    for site in (BIG, SMALL):
        for mem, regs, work in by[site][:1]:
            st = fresh(work)
            w(st, V_N, 0)
            st.work[V_STP - 0x8000:V_STP - 0x8000 + 2] = STASH.to_bytes(2, 'little')
            m2 = bytearray(mem)
            if site == BIG:                             # a large figure drawn from the shift buffer, as the fourth can be
                regs = list(regs)
                regs[4], regs[5], regs[6], regs[7] = 0xD6, 0x80, 0xD7, 0x08
            before = bytes(st.work)
            good = True
            for k in range(12):
                Rp, mp, model = run_hook(patch, st, rom, m2, regs, site)
                Ro, mo = run_orig(rom, m2, regs, EXIT[site])
                good = good and _differs(Ro, mo, Rp, mp, regs[SP_]) == ([], [])
            stp = st.work[V_STP - 0x8000] | st.work[V_STP - 0x7FFF] << 8
            good = good and w(st, V_N) == MAXE and STASH <= stp <= ENTS and st.work[ATTRS - 0x8000:PACE - 0x8000] == before[ATTRS - 0x8000:PACE - 0x8000] and st.work[PBUF - 0x8000:] == before[PBUF - 0x8000:]
            ok('twelve figures noted at %04X' % site, good)
    for mem, regs, work in by[PAINT][:1]:
        st = fresh(work)
        w(st, V_PN, 0)
        st.work[V_PP - 0x8000:V_PP - 0x8000 + 2] = PREC.to_bytes(2, 'little')
        before = bytes(st.work)
        good = True
        for k in range(7):
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, PAINT)
            Ro, mo = run_orig(rom, mem, regs, EXIT[PAINT])
            good = good and _differs(Ro, mo, Rp, mp, regs[SP_]) == ([], [])
        good = good and w(st, V_PN) == 64 and st.work[PREC + 192 - 0x8000:PACE - 0x8000] == before[PREC + 192 - 0x8000:PACE - 0x8000] and st.work[PBUF - 0x8000:] == before[PBUF - 0x8000:]
        ok('seven paints noted', good)
    # the game's interrupt inside a hook, at points spread over it: the same game memory, registers and sprites as the
    # interrupt taken right after the hook (its handler saves every register and touches neither of the hooks' slots)
    for site in (BIG, MIR, SMALL, PAINT, COPY, ACOPY, RANDOM, CLS):
        for mem, regs, work in by[site][:1]:
            if not regs[IFF_] or bytes(mem[ISR:ISR + 3]) != b'\xc3\xf3\x60':
                continue
            sp = regs[SP_]
            ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF) if site in (COPY, ACOPY) else None
            st0 = fresh(work)
            R0, m0, model0 = run_hook(patch, st0, rom, mem, regs, site, ret)
            ra = list(R0)                               # then the interrupt
            spa = (ra[SP_] - 2) & 0xFFFF
            m0[spa], m0[spa + 1] = ra[PC_] & 255, ra[PC_] >> 8
            back = ra[PC_]
            ra[SP_], ra[PC_], ra[IFF_] = spa, ISR, 0
            Ra, ma = run_orig(rom, m0, ra, back, (spa + 2) & 0xFFFF)
            n = model0.n
            for k in sorted({1, 2, 3, 5, n // 7, n // 5, n // 3, n // 2, 2 * n // 3, n - 9, n - 4, n - 2, n - 1} - {0}):
                if k >= n:
                    continue
                st1 = fresh(work)
                Rb, mb, model1 = run_hook(patch, st1, rom, mem, regs, site, ret, irq=k)
                lo = min(sp, Ra[SP_]) - STACK - 48
                skip = (R_, A_, F_, 6, 7) if site == RANDOM else (R_,)     # an interrupt before the read of R changes the byte, as in the original
                good = (getattr(model1, 'irq', None) is not None and [Ra[i] for i in CMP if i not in skip] == [Rb[i] for i in CMP if i not in skip]
                        and ma[0x4000:lo] == mb[0x4000:lo] and ma[max(sp, Ra[SP_]):] == mb[max(sp, Ra[SP_]):]
                        and st1.attrs == st0.attrs and st1.pattern == st0.pattern and st1.work[0:V_N - 0x8000 - 4] == st0.work[0:V_N - 0x8000 - 4]
                        and st1.work[V_N - 0x8000:V_N - 0x8000 + 3] == st0.work[V_N - 0x8000:V_N - 0x8000 + 3]
                        and st1.work[SA_B - 0x8000:SA_B - 0x8000 + 4] == st0.work[SA_B - 0x8000:SA_B - 0x8000 + 4])
                ok('interrupt inside the hook at %04X' % site, good)
    # a figure whose lines leave the buffer: no coverage byte read outside it, the game's memory untouched
    for mem, regs, work in by[COPY][:1]:
        st = fresh(work)
        e = ENTS - 0x8000
        st.work[e:e + 2] = (0xD1E0).to_bytes(2, 'little')     # the last buffer line
        w(st, V_N, max(1, w(st, V_N)))
        sp = regs[SP_]
        ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, COPY, ret)
        Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
        ok('figure across the buffer\'s end', _differs(Ro, mo, Rp, mp, sp) == ([], []))
    return c


def _code_patch(patch, sym, new, stub=False):
    """A copy of the build with bytes changed at a label of the hook code (negative controls)."""
    a = patch.syms[sym]
    if a >= ROM_ORG:
        rc = bytearray(patch.rom_code)
        rc[a - ROM_ORG:a - ROM_ORG + len(new)] = new
        return HeartlandPatch(patch.prof, bytes(rc), code=patch.code, colours=patch.colours, z80=patch.z80, blank=patch.blank)
    cd = bytearray(patch.code)
    cd[a - 0x2000:a - 0x2000 + len(new)] = new
    return HeartlandPatch(patch.prof, patch.rom_code, code=bytes(cd), colours=patch.colours, z80=patch.z80, blank=patch.blank)


def negative_patches(patch):
    """Broken builds a verify run on a recording must catch: [(name, patch)]."""
    out = [('a mirrored figure noted as a plain one', _code_patch(patch, 'note1.n_mir', b'\x3E\x00')),
           ('the foreground pieces do not clip the sprites', _code_patch(patch, 'commit.n_cov', b'\x00\x00\x00')),
           ('the paint is not lifted for the attribute copy', _code_patch(patch, 'acopy.n_lift', b'\x00')),
           ('the paint is not put back after the attribute copy', _code_patch(patch, 'acopy.n_again', b'\x00')),
           ('sprites one line low', _code_patch(patch, 'figure.n_y', b'\xC6\x51')),
           ('R one more after a note', _code_patch(patch, 'note.n_r', bytes((0x3E, patch.rom_code and (patch.code[patch.syms['note.n_r'] - 0x2000 + 1] + 1) & 255)))),
           ('sprites name the wrong pattern', _code_patch(patch, 'attr.n_q', b'\xF6\xC1')),
           ('the sprite window ends a line early', _code_patch(patch, 'show.n_win', bytes((0x3E, 48 + 110)))),
           ('the copy\'s time is not waited out', _code_patch(patch, 'commit.n_wait', b'\x00\x00\x00')),
           ('the attribute port\'s sprite is not selected', _code_patch(patch, 'show.n_sel', b'\x00\x00'))]
    wk = bytearray(patch.work)
    for k in range(256):                # no border: the mask's cleared pixels left clear
        for t in (TLO, THI):
            b = wk[t - 0x8000 + k]
            wk[t - 0x8000 + k] = (0 if b >> 4 == 2 else b & 0xF0) | (0 if b & 15 == 2 else b & 15)
    out.append(('patterns without the mask\'s border', HeartlandPatch(patch.prof, patch.rom_code, work=bytes(wk), code=patch.code, colours=patch.colours, z80=patch.z80)))
    if patch.colours and patch.planes:      # the painted build's own faults
        q = HeartlandPatch(patch.prof, patch.rom_code, code=patch.code, colours=patch.colours, z80=patch.z80)
        pg = bytearray(q.page)
        for i in range(pg[LPL - 0x2000]):   # a mirrored figure given the plain figure's colours
            e = LPL - 0x2000 + 1 + 7 * i
            pg[e + 5:e + 7] = pg[e + 3:e + 5]
        q.page = bytes(pg)
        q._banks()
        out.append(('a mirrored figure painted as a plain one', q))
        q = HeartlandPatch(patch.prof, patch.rom_code, code=patch.code, colours=patch.colours, z80=patch.z80)
        pg = bytearray(q.page)
        for n in range(SPLN):               # a small figure's colours not moved with its shift
            if pg[SPL - 0x2000 + 3 * n]:
                pg[SPL - 0x2000 + 3 * n + 1] ^= 1
        q.page = bytes(pg)
        q._banks()
        out.append(('a small figure\'s colours one shift out', q))
    return out


def negative_units(patch, states):
    """Broken builds only a unit case shows: -> [(name, caught)]."""
    out = []
    for name, sym, new, key in (('the random byte ignores the lifted paint', 'random.n_rnd', b'\x18', 'random byte from a cell with the paint lifted!'),):
        q = _code_patch(patch, sym, new)
        u = unit_tests(q, states)
        out.append((name, bool(u[key])))
    return out


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : heartland (the game\'s memory and bitmap stay the original\'s; the figures the plotters were given -> sprites at the screen copy)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    cmap = load_colours()
    ep = HeartlandPatch(colours=cmap, z80=z80) if cmap else None
    patch = HeartlandPatch(blank=len(ep.planes) if ep else 0)
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, TAIL_ADDR, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    builds = [('Verify', patch)]
    if cmap:                            # Enhanced (the .nxc's colour set): the painted map
        enh = os.path.join(out, name + '_enhanced.nex')
        conv = zt.convert(z80, enh, TAIL_ADDR, True, quiet=True, patch=ep)
        bad3 = check(enh, z80, ep, (conv[1], conv[1] + len(conv[2])))
        ok = ok and not bad3
        say('Enhanced  : %s  %s  boot %s  (%d painted graphics, %d palette lines, %d colour pages)' % (
            os.path.basename(enh), md5(enh), 'OK' if not bad3 else 'MISMATCH %s' % str(bad3[:3])[:200], len(cmap['figures']), len(cmap['lines']), len(ep.planes)))
        builds.append(('Painted', ep))
    states = []
    quick = getattr(a, 'quick', None)
    for label, pt in builds:
        for r in list(a.rzx or []):
            cc, ex, st = verify(pt, r, stop=quick, collect=3 if pt is patch else 0)
            states += st
            fails = {k: v for k, v in cc.items() if k.endswith('!')}
            ok = ok and not fails
            say('%-10s: %s  %d frames, %d steps, %d copies, %d screen clears, %d plots, %d paints, %d random bytes, most figures %d, most sprites %d, '
                '%d sprite pixels (%d painted), %d cells with the paint lifted -> %s' % (
                    label, os.path.basename(r), cc['frames'], cc['step'], cc['copy'], cc['screen clear'], cc['plot'], cc['paint'], cc['random'], cc['most figures'],
                    cc['most sprites'], cc['sprite pixels compared'], cc['painted pixels'], cc['cells with the paint lifted'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
            say('Pace      : %s  the two copies %d T in the original, the hooks %d T (%+.2f%% of the recording\'s time); bolt pixels the original XORs into a figure %d; '
                'random bytes read from the screen %d, where the paint is lifted %d; lowest stack byte a hook writes 0x%04X' % (
                    os.path.basename(r), cc['T original'], cc['T hooks'], 100.0 * (cc['T hooks'] - cc['T original']) / max(1, cc['frames'] * 69888),
                    cc['bolt pixels the original XORs into a figure'], cc['random bytes read from the screen'], cc['random bytes read where the paint is lifted'],
                    cc['lowest stack byte a hook writes']))
            for k, v in ex.items():
                if k != 'copy T by lines and figures':
                    say('            %s: %s' % (k, str(v)[:300]))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.endswith('!')), 'PASS' if not uf else 'FAIL %s' % uf))
    if a.rzx:
        r0 = list(a.rzx)[0]
        missed = []
        negs = negative_patches(builds[-1][1])
        for nm, q in negs:
            cc, _, _ = verify(q, r0, stop=quick or 1500)
            if not any(k.endswith('!') for k in cc):
                missed.append(nm)
        nu = negative_units(patch, states)
        missed += [nm for nm, caught in nu if not caught]
        ok = ok and not missed
        say('Negative  : %d broken builds (%s), %d detected%s' % (len(negs) + len(nu), os.path.basename(r0), len(negs) + len(nu) - len(missed),
                                                                 '' if not missed else '; NOT detected: ' + ', '.join(missed)))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
