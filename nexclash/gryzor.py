"""Gryzor (Ocean 1987, 48K form) engine 'gryzor'. Additive module: reachable only through is_gryzor().

Game facts (games/gryzor.md): each tick the game blits the whole play area to the screen (39557), then plots figures
straight on the screen, masked. Five plot loops are figures: 4, 3 and 5 columns wide, a clipped 4-column one and a bullet
(2 x 4 lines). Objects set in the rock (40798, whole bytes) and their eyes (36118, AND only: they show the paper) stay on the ULA.
Bare figures have no colour: outlines are ink, bodies show the paper of the band they are in.
Hooks (asm/gryzor_hooks.asm): the plot loops' screen stores become NOPs, and each loop's LD (46081),SP gives the image,
position and size to sprites. Ported 2026-11-05 from Jon Attree's pilot engine (runs/gryzor, 2026-11-03) with the new
defaults: whole alt ROM image (the hooks' gate in its 0xFF area, their code in a RAM page mapped under it), 28 MHz hooks
restoring the caller's speed, R preserved (the star routine is a hook so that R follows the original's path), patterns
prepared at build time, the pace limiter.

Verify: two replays of each recording. The one with NOPs gives the bare screen, and registers and memory against the
other at every tick. The original replay runs each hook in a simulator from the real state, and at every tick the
sprites over the bare screen must equal the original's screen.
"""
import collections
import hashlib
import json
import os
import zlib

PAGE = 24                   # hook page, mapped at MMU slot 1 inside a hook (bank 12, first half)
STATE_PAGES = (10, 11)      # slots 2 + 3, the screen and low RAM
PLANE = 26                  # first colour plane page (bank 13)
PLANE_BANKS = range(13, 18)
STORE = 36                  # first prepared-pattern page (bank 18)
GB, GE = 0x6000, 0x10000    # plane covers these graphics addresses
B4, B4E = 0xB8C1, 0xB941    # bullets: (mask, graphics), odd addresses
TAIL_ADDR = 0x5B00          # scan: 0x5B00-0x6987 untouched on every recording
GATE = 0x386E
SPSAVE = 46081
ROWS = 46035
TICKS = (34749, 35468)      # CALL 39557
TICK_OPERANDS = (34750, 35469)
BLIT = 39557
CLS, CONT_CLS = 34509, 34512
CLR, CLR_OPERAND, CLR_TARGET = 32869, 32870, 42007
STARS_CALL, STARS_BACK, STARS_OPERAND, STAR_ROUTINE = 34849, 34852, 34850, 38168
STAR_TABLE, NSTARS = 38191, 20
# site -> (gate symbol, address after LD (46081),SP, address of the loop's LD SP,(46081), columns, kind)
ENTRIES = {40370: ('e_c4', 40374, 40443, 4, 'c'), 40188: ('e_clip', 40192, 40308, 4, 'clip'), 40709: ('e_c3', 40713, 40770, 3, 'c'),
           40539: ('e_c5', 40543, 40624, 5, 'c'), 37662: ('e_b4', 37666, 37713, 2, 'b4')}
EYE = 36151                 # the object eyes' loop: its LD (46081),SP, not patched: HL image, DE screen
EYE_CALL, EYE_BACK = 34764, 34767   # CALL 35792, which draws them
STORES = (40380, 40386, 40392, 40398, 40404, 40410, 40416, 40422,
          40206, 40216, 40226, 40236, 40246, 40256, 40266, 40276,
          40719, 40725, 40731, 40737, 40743, 40749,
          40549, 40555, 40561, 40567, 40573, 40579, 40585, 40591, 40597, 40603,
          37674, 37680, 37686, 37692)
INTERIORS = tuple(a + k for a in ENTRIES for k in (1, 2, 3)) + (CLS + 1, CLS + 2)
PALETTE = [0x00, 0x00, 0xFC, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFF]
CMP_R = list(range(0, 24)) + [26, 27]   # every register, R (15) included; not T / MEMPTR (hooklib.CMP_R)
CMP = CMP_R                             # ENGINE_CONTRACT: the registers compared (R included: patch.preserve-r)
_R_SP, _R_R, _R_PC, _R_T, _R_IFF = 12, 15, 24, 25, 26
SC_T = 1                    # as asm: contention estimate, T a screen access (pace target)
O_SITE = {'plot': 2, 'tick': 1, 'cls': 1, 'clr': 1}     # M1s the original runs from the site to the return point

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'gryzor_colours.json')
OUTLINE = os.path.join(_HERE, '..', 'docs', 'profiles', 'gryzor_outline.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'gryzor.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_gryzor(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from .recolour import build_colours_path
    p = path or build_colours_path(COLOURS)
    if p and os.path.exists(p):
        from .coloursheet import load
        return load(p)
    return {}


def outline_map(nibble=1, path=None):
    """The outline the owner approved (2026-11-03: a see-through pixel 4-next to an opaque one, inside the image's own
    bytes, bullets included), as a colour map with that nibble on the outline bits: 1 = black, the game's ink (owner,
    2026-11-05), 15 = the approved build's white. Entries are keyed and checked like any colour map."""
    m = json.load(open(path or OUTLINE))
    return {k: [e[0], e[1], [nibble if v else 0 for v in e[2]]] + e[3:] for k, e in m.items()}


# ---------------------------------------------------------------------------------------------
# The colour plane: pattern bytes per graphics byte pair, by address
# ---------------------------------------------------------------------------------------------

def graphics_memory(peek):
    """The game's generators write some graphics when a game starts (34662-34668; 41731 builds the mirror table the
    others use): their result, from any start."""
    from skoolkit.simulator import Simulator
    sim = Simulator(bytearray(peek(a) if a >= 0x4000 else 0 for a in range(65536)))
    R, M, ops = sim.registers, sim.memory, sim.opcodes
    for a in (41731, 41022, 41187):
        R[_R_SP] = 0xFF00
        M[0xFF00], M[0xFF01] = 0x34, 0x12
        R[_R_PC] = a
        n = 0
        while R[_R_PC] != 0x1234:
            ops[M[R[_R_PC]]]()
            n += 1
            if n > 5000000:
                raise ValueError('generator did not return')
    return bytes(M)


def nibble(data, mask, bit, e):
    """A pixel of a (graphics, mask) pair, with its colour map entry (or None): 1 ink, 2 body, 0 see-through."""
    if e is not None:
        if len(e) > 3 and e[3] & (0x80 >> bit):
            return 0
        if e[2][bit]:
            return e[2][bit]
    if data >> (7 - bit) & 1:
        return 1
    return 2 if not mask >> (7 - bit) & 1 else 0


def _entry(cmap, m, key):
    if not cmap:
        return None
    e = cmap.get('%04X' % key)
    if e is not None and e[0] is not None and e[0] != m[key]:   # stored maps: null check (the byte is the game's)
        return None
    return e


def _pixels(data, mask, e):
    out = bytearray(4)
    for k in range(8):
        v = nibble(data, mask, k, e)
        out[k // 2] |= v << 4 if k % 2 == 0 else v
    return out


def plane(m, cmap=None):
    """-> plane bytes for graphics memory m. Pairs at even addresses are (graphics, mask); bullets (mask, graphics)."""
    pl = bytearray(2 * (GE - GB) + 4)
    for a in range(GB, GE - 1, 2):
        pl[2 * (a - GB):2 * (a - GB) + 4] = _pixels(m[a], m[a + 1], _entry(cmap, m, a))
    for a in range(B4, B4E, 2):
        pl[2 * (a - GB):2 * (a - GB) + 4] = _pixels(m[a + 1], m[a], _entry(cmap, m, a + 1))
    return bytes(pl)


def plane_banks(pl):
    return {b: pl[(b - PLANE_BANKS[0]) * 16384:(b - PLANE_BANKS[0] + 1) * 16384].ljust(16384, b'\0') for b in PLANE_BANKS}


# ---------------------------------------------------------------------------------------------
# Prepared patterns (optimise.pattern-cache): what the hook's slow path writes, made at build time
# ---------------------------------------------------------------------------------------------

KIND_W = {'c3': 3, 'c4': 4, 'c5': 5, 'clip': 4, 'b4': 2}


def figures():
    return [tuple(x) for x in load_profile().get('figures', [])]


def shape_of(w, rows):
    return (w << 5 & 0xE0) | rows


def slow_patterns(pl, g, w, rows):
    """The bytes the hook's slow path (asm upload.slow) sends to pattern RAM for image g: w columns, rows of 2 lines."""
    lines, nrows, ncols = 2 * rows, (1 if rows < 9 else 2), (w + 1) // 2
    stride, pbase, lnow, out = 8 * w, 2 * (g - GB), 0, bytearray()
    zero = bytes(4)
    for rw in range(nrows if ncols == 2 else 1):
        for cl in range(ncols):
            cnow, pcur, lcur = 2 * cl, pbase, lnow
            for _ in range(8):
                for c in (cnow, cnow + 1):
                    out += zero if lines <= lcur or w - 1 < c else pl[pcur + 4 * c:pcur + 4 * c + 4]
                for c in (cnow, cnow + 1):
                    o = pcur + stride - 4 * (c + 1)
                    out += zero if lines <= lcur + 1 or w - 1 < c else pl[o:o + 4]
                pcur += stride
                lcur += 2
        pbase += stride * 8
        lnow += 16
    return bytes(out)


def store_images(prof=None):
    """The listed images [(g, w, rows)], each once (the profile's figures; clip and c4 share the image and shape)."""
    seen, out = set(), []
    for kind, g, rows in (prof or load_profile()).get('figures', []):
        k = (g, KIND_W[kind], rows)
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def store_pages(pl, prof=None):
    """-> ({page: 8192 bytes}, [(g, shape, page, offset, units)]): every listed image's patterns, packed so that none
    crosses a page."""
    pages, index, page, off = {}, [], STORE, 0
    for g, w, rows in store_images(prof):
        b = slow_patterns(pl, g, w, rows)
        if off + len(b) > 8192:
            page, off = page + 1, 0
        pages.setdefault(page, bytearray(8192))[off:off + len(b)] = b
        index.append((g, shape_of(w, rows), page, off, len(b) // 128))
        off += len(b)
    if len(index) > 128:
        raise ValueError('more than 128 listed images: the index holds 128')
    if page > STORE + 9:
        raise ValueError('prepared patterns need more than 10 pages')
    return {p: bytes(v) for p, v in pages.items()}, index


def store_banks(pages):
    out = {}
    for p, v in pages.items():
        b = out.setdefault(p // 2, [bytes(8192), bytes(8192)])
        b[p & 1] = v
    return {k: v[0] + v[1] for k, v in out.items()}


# ---------------------------------------------------------------------------------------------
# The patches
# ---------------------------------------------------------------------------------------------

def _rom():
    from .build import rom48
    return rom48()


def _rom_page(code=b'', at=GATE):
    """0x2000-0x3FFF of Sinclair's ROM, `code` at `at` (its 0xFF area)."""
    rom = _rom()
    if any(b != 0xFF for b in rom[at:at + len(code)]):
        raise ValueError('alt ROM gate range is not free ($FF) in the 48K ROM')
    page = bytearray(rom[0x2000:0x4000])
    page[at - 0x2000:at - 0x2000 + len(code)] = code
    return bytes(page)


class PlainPatch:
    """The plain .nex: no hooks. Alt ROM image 1 = Sinclair's 48K ROM (+ the tail's 20-byte register block in its
    0xFF area), as the sprite build has it."""
    name = 'Gryzor plain conversion, Sinclair\'s ROM as the alt ROM'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def __init__(self):
        self.regblock = GATE
        self.slot1 = (PAGE, self.regblock)
        self.altrom = (GATE, GATE + 20)
        self.page = _rom_page()
        self.extra_banks = {PAGE // 2: self.page + bytes(8192)}

    def apply(self, snap):
        pass


class GryzorPatch:
    name = 'Gryzor figures -> hardware sprites (gate in the alt ROM, hooks in a RAM page under it, colour plane in Next pages)'

    def __init__(self, prof=None, page_code=None, colours=None, drop_sites=(), plane_fn=None, store_op=0, no_store=False):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.code = page_code or bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        s = self.syms
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 128
        self.regblock = s['regs']
        self.slot1 = (PAGE, self.regblock)
        self.altrom = (s['gate_lo'], s['gate_end'])
        self.no_store = no_store
        self.colours = colours
        self.plane_fn = plane_fn or plane
        self.sites = []
        for a in STORES:
            if a not in drop_sites:
                self.sites.append((a, b'\x77', bytes([store_op if not isinstance(store_op, dict) else store_op.get(a, 0)])))
        for a, (sym, _, _, _, _) in ENTRIES.items():
            if a not in drop_sites:
                self.sites.append((a, bytes.fromhex('ED7301B4'), b'\xC3' + s[sym].to_bytes(2, 'little') + b'\x00'))
        for a in TICK_OPERANDS:
            if a not in drop_sites:
                self.sites.append((a, BLIT.to_bytes(2, 'little'), s['e_tick'].to_bytes(2, 'little')))
        if CLS not in drop_sites:
            self.sites.append((CLS, bytes.fromhex('210040'), b'\xC3' + s['e_cls'].to_bytes(2, 'little')))
        if CLR not in drop_sites:
            self.sites.append((CLR_OPERAND, CLR_TARGET.to_bytes(2, 'little'), s['e_clr'].to_bytes(2, 'little')))
        if STARS_CALL not in drop_sites:
            self.sites.append((STARS_OPERAND, STAR_ROUTINE.to_bytes(2, 'little'), s['e_star'].to_bytes(2, 'little')))
        self.pl = None
        self.store, self.index = {}, []
        self.page = self._page()
        self.extra_banks = {}

    def _page(self):
        """The 8K page image of 0x2000-0x3FFF: Sinclair's ROM, the hook code, and the prepared-pattern index."""
        s = self.syms
        page = bytearray(_rom_page())
        page[0:len(self.code)] = self.code
        if self.code[s['gate_lo'] - 0x2000:s['gate_hi'] - 0x2000] != page[s['gate_lo'] - 0x2000:s['gate_hi'] - 0x2000]:
            raise ValueError('gate bytes')
        idx = [] if self.no_store else self.index
        page[s['npx'] - 0x2000] = len(idx)
        for i, (g, sh, pg, off, units) in enumerate(idx):
            for sym, v in (('pxlo', g & 255), ('pxhi', g >> 8), ('pxsh', sh), ('pxpg', pg), ('pxol', off & 255),
                           ('pxoh', off >> 8), ('pxn', units)):
                page[s[sym] - 0x2000 + i] = v
        return bytes(page)

    def build_plane(self, peek):
        cmap = load_colours() if self.colours is None else self.colours
        self.pl = self.plane_fn(graphics_memory(peek), cmap)
        self.store, self.index = store_pages(self.pl, self.prof)
        self.page = self._page()
        return self.pl

    def banks(self):
        out = {PAGE // 2: self.page + bytes(8192)}
        out.update(plane_banks(self.pl))
        out.update(store_banks(self.store))
        return out

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Gryzor patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected version of Gryzor' % (a, cur.hex(), old.hex()))
        self.build_plane(lambda a: ram[a - 0x4000])
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = self.banks()


# ---------------------------------------------------------------------------------------------
# Next-side model
# ---------------------------------------------------------------------------------------------

class NextState:
    """Sprites, pattern RAM, MMU slots 1-3, NR 7 and a time model for the pace limiter's video line."""

    def __init__(self, patch=None):
        self.nr = {7: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patp = 0
        self.slots = {1: 0xFF, 2: 10, 3: 11}
        self.bad = []
        self.sel = 0
        self.R = None
        self.speed_in = 0
        self.rt = self.rt_mark = 0
        self.cur = 0
        self.t_entry = 0
        self.fast28 = 8.0
        self.uploads = 0

    def clone(self):
        import copy
        q = copy.copy(self)
        q.nr, q.slots = dict(self.nr), dict(self.slots)
        q.attr = [list(a) for a in self.attr]
        q.pat = bytearray(self.pat)
        q.bad = []
        q.R = None
        return q

    def now(self):
        m = self.fast28 if self.cur == 3 else (1.0, 2.0, 4.0)[self.cur]
        return self.rt + ((self.R[_R_T] if self.R is not None else self.rt_mark) - self.rt_mark) / m

    def line(self):
        return int((self.t_entry + self.now() - 14336) // 224) % 312

    def nextreg(self, reg, val):
        if reg == 7:
            if self.R is not None:
                self.rt = self.now()
                self.rt_mark = self.R[_R_T]
            self.cur = val & 3
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg in (0x51, 0x52, 0x53):
            self.slots[reg - 0x50] = val
        elif reg not in (0x34, 7):
            self.bad.append(('nextreg', reg))

    def read_port(self, regs, port):
        if port == 0x253B:
            if self.sel == 7:
                s = self.nr.get(7, 0) & 3
                return s << 4 | s               # actual speed 5:4, programmed 1:0 (hooklib.NextModel)
            if self.sel in (0x1E, 0x1F):
                ln = self.line()
                return ln >> 8 & 1 if self.sel == 0x1E else ln & 255
        self.bad.append(('in', port, self.sel))
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if port == 0x243B:
            self.sel = value
        elif port & 0xFF == 0x3B and port >> 8 == 0x30:
            self.patp = ((value & 0x3F) << 8 | (value & 0x80)) % 16384
        elif port & 0xFF == 0x5B:
            self.pat[self.patp] = value
            self.patp = (self.patp + 1) % 16384
            self.uploads += 1
        else:
            self.bad.append(('out', port))

    def visible(self):
        """-> [(pattern, x, y)] in slot order."""
        out = []
        for i, (a0, a1, a2, a3, a4) in enumerate(self.attr):
            if not a3 & 0x80:
                continue
            f = ((a3 & 0x3F) << 1) | ((a4 >> 6) & 1)
            if not a3 & 0x40 or not a4 & 0x80 or a4 & 0x3F or a2 & 0xFE:
                self.bad.append(('sprite form', i, (a0, a1, a2, a3, a4)))
            out.append((f, a0 + (a2 & 1) * 256 - 32, a1 - 32))
        return out


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def alt_image(patch):
    """Alt ROM image 1 as the stub leaves it (nextboot.alt_image: Sinclair's ROM + the gate and register block)."""
    from .nextboot import alt_image as ai
    return bytes(ai(patch))


class _PMem:
    """The build's view: alt ROM image 1 below 0x4000, the hook page at 0x2000-0x3FFF while slot 1 holds it, plane and
    store pages while slots 2 / 3 hold them, game memory through get; writes to an overlay."""

    def __init__(s, get, page, pl, store, ns, alt):
        s.get, s.page, s.pl, s.store, s.ns, s.alt, s.ov, s.romw, s.planew = get, page, pl, store, ns, alt, {}, 0, 0

    def __getitem__(s, a):
        if a < 0x2000:
            return s.alt[a]
        if a < 0x4000:
            return s.page[a - 0x2000] if s.ns.slots[1] == PAGE else s.alt[a]
        if a < 0x8000:
            p = s.ns.slots[(a >> 13)]
            if p not in STATE_PAGES:
                if p >= STORE:
                    st = s.store.get(p)
                    return st[a & 0x1FFF] if st else 0
                off = (p - PLANE) * 0x2000 + (a & 0x1FFF)
                return s.pl[off] if 0 <= off < len(s.pl) else 0
        v = s.ov.get(a)
        return v if v is not None else s.get(a)

    def __setitem__(s, a, v):
        if a < 0x2000:
            s.romw += 1
        elif a < 0x4000:
            if s.ns.slots[1] == PAGE:
                s.page[a - 0x2000] = v
            else:
                s.romw += 1
        elif a < 0x8000 and s.ns.slots[a >> 13] not in STATE_PAGES:
            s.planew += 1
        else:
            s.ov[a] = v

    def __len__(s):
        return 65536


def _machine(mem, regs, ns):
    from .simpool import machine
    from . import z80n
    sim = machine(_rw(), mem, regs, 'g')
    z80n.install(sim, ns.nextreg)
    sim.set_tracer(ns)
    return sim


def _run(sim, stop, limit=3000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    stop = stop if isinstance(stop, (set, frozenset)) else {stop}
    n = 0
    while R[_R_PC] not in stop:
        ops[mem[R[_R_PC]]]()
        n += 1
        if n > limit:
            return False
    return True


class Engine:
    """Persistent patched state: hook page, Next state, for one replay."""

    def __init__(self, patch, clock=0):
        self.patch = patch
        self.page = bytearray(patch.page)
        self.ns = NextState(patch)
        self.ns.speed_in = clock
        self.alt = alt_image(patch)
        self.linecache = {}

    def clone(self):
        import copy
        e = copy.copy(self)
        e.page = bytearray(self.page)
        e.ns = self.ns.clone()
        return e

    def hook(self, get, regs, start, stop, sp=None, ov=None, t_site=0, limit=3000000):
        """Run a hook from its gate entry with these registers to `stop`. -> (registers after, overlay, real time in 3.5 MHz T,
        finished, ROM / plane writes). The hook is entered at the game's clock (ns.speed_in)."""
        mem = _PMem(get, self.page, self.patch.pl, self.patch.store, self.ns, self.alt)
        if ov:
            mem.ov.update(ov)
        r = list(regs)
        r[_R_PC] = start
        if sp is not None:
            r[_R_SP] = sp
        sim = _machine(mem, r, self.ns)
        ns = self.ns
        ns.R = sim.registers
        ns.rt, ns.rt_mark, ns.t_entry = 0, sim.registers[_R_T], t_site
        ns.nr[7] = ns.cur = ns.speed_in
        done = _run(sim, stop, limit)
        t = ns.now()
        ns.R = None
        return list(sim.registers), mem.ov, t, done, mem.romw + mem.planew

    def lines(self, f, clear=()):
        """Pattern f -> 16 lines of (opaque mask, ink bits): 16 bits each. clear: nibbles counted as see-through."""
        b = bytes(self.ns.pat[f * 128:(f + 1) * 128])
        c = self.linecache.get((b, clear))
        if c is None:
            c = []
            for y in range(16):
                op = ink = 0
                for k in range(16):
                    v = b[y * 8 + k // 2]
                    v = v >> 4 if k % 2 == 0 else v & 15
                    if v and v not in clear:
                        op |= 0x8000 >> k
                        if v == 1:
                            ink |= 0x8000 >> k
                c.append((op, ink))
            self.linecache[(b, clear)] = c
        return c


def _scr(y, col):
    return (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | col


def scr_yx(a):
    h, l = a >> 8, a & 255
    return (h & 0x18) << 3 | (l & 0xE0) >> 2 | (h & 7), l & 31


def composite(eng, bare, attrs=None, c=None, clear=()):
    """Sprites over the bare screen (6144 bytes) -> screen bytes. Sprites are always byte-aligned in x here."""
    scr = bytearray(bare)
    for f, x, y in eng.ns.visible():
        if x % 8:
            eng.ns.bad.append(('x', x))
        col = x >> 3
        for l, (op, ink) in enumerate(eng.lines(f, clear)):
            if not op:
                continue
            yy = y + l
            if not 0 <= yy < CLIP_Y:
                continue
            for k, sh in ((col, 8), (col + 1, 0)):
                if 0 <= k < 32:
                    m = op >> sh & 255
                    if m:
                        a = _scr(yy, k)
                        scr[a] = (scr[a] & ~m & 255) | (ink >> sh & 255)
                        if c is not None and attrs is not None:
                            n = bin(m).count('1')
                            c['figure pixels'] += n
                            body = bin(m & ~(ink >> sh)).count('1')
                            c['body pixels'] += body
                            if (attrs[(yy >> 3) * 32 + k] >> 3) & 7 != 6:
                                c['body pixels on another paper'] += body
    return bytes(scr)


# ---------------------------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------------------------

AFTER_OBJECTS = (34755, 35474)      # return from 40775: the play area is complete, and nothing after may change it...
CLIP_Y = 168                        # lines 168-191 are ink = paper, cyan, always: the water hides figures there


def star_list(M):
    return [(M[STAR_TABLE + 2 * k] | M[STAR_TABLE + 2 * k + 1] << 8) for k in range(NSTARS)]


def replay_stars(rzx_path, stop):
    """The bytes the original's star routine finds, per call. It only flips bits on the screen, but how far it runs depends on
    them, so a figure on a star changes the fetch count, so R, and LD A,R (35115, 39152) gives the game other random numbers."""
    from . import rzx as RZ
    out = []

    def on(pc, sim):
        M = sim.memory
        out.append(bytes(M[a] for a in star_list(M)))
    RZ.trace(rzx_path, {STARS_CALL}, on, stop=stop)
    return out


def replay_bare(patch, rzx_path, stop, stars):
    """Replay with only the stores changed. -> per tick (screen, registers, memory digest), the bare star bytes per star
    call, [(tick, bytes changed in the play area since the objects were drawn)]. Screen bytes are left out of the digest;
    every other byte, stores restored. The star routine gets the original's bytes, so the replays stay in step - the star
    hook leaves R, A and F as the original's (checked at every call in verify) - then the screen gets what the hook does in
    the build: flip bit 5 of a byte holding 0 or 255."""
    from . import rzx as RZ
    ticks, changed, bstars = [], [], []
    done = [False]
    code = [(a, new[0]) for a, old, new in patch.sites if len(old) == 1 and a in STORES]
    held = [None]
    star = [0, None]

    def on(pc, sim):
        M = sim.memory
        if pc in (CLS, CLR):
            held[0] = None
            return
        if pc in AFTER_OBJECTS or pc in (STARS_BACK, EYE_BACK):
            if pc == STARS_BACK and star[1] is not None:
                for a, v in star[1]:
                    M[a] = v ^ 0x20 if v in (0, 255) else v
                star[1] = None
            held[0] = bytes(M[0x4000:0x50A0])
            return
        if not done[0]:
            for a, v in code:
                M[a] = v
            done[0] = True
        if held[0] is not None:
            now = bytes(M[0x4000:0x50A0])
            if now != held[0]:      # lines 0-31 are the score, the lives, and 40448's small wipe
                n = sum(1 for a in range(len(now)) if now[a] != held[0][a] and scr_yx(a)[0] >= 32)
                if n:
                    changed.append((len(ticks), n))
            held[0] = None
        if pc == EYE_CALL:
            return
        if pc == STARS_CALL:
            al = star_list(M)
            star[1] = [(a, M[a]) for a in al]
            bstars.append(bytes(M[a] for a in al))
            if star[0] < len(stars):
                for a, v in zip(al, stars[star[0]]):
                    M[a] = v
            star[0] += 1
            return
        m = bytearray(M[0x5800:0x10000])
        for a in STORES:
            m[a - 0x5800] = 0x77
        ticks.append((zlib.compress(bytes(M[0x4000:0x5800]), 1), [sim.registers[i] for i in CMP_R], hashlib.md5(m).digest()))
    fc, err = RZ.trace(rzx_path, set(TICKS) | set(AFTER_OBJECTS) | {STARS_CALL, STARS_BACK, EYE_CALL, EYE_BACK, CLS, CLR}, on, stop=stop)
    return ticks, bstars, changed, fc, err


def _orig_star(M, regs):
    """The original star routine from the CALL at 34849 on a copy of the state: -> (registers at 34852, T)."""
    from .simpool import machine
    from skoolkit.simulator import Simulator
    mem = bytearray(M[a] for a in range(65536))
    r = list(regs)
    sp = (r[_R_SP] - 2) & 0xFFFF
    mem[sp], mem[(sp + 1) & 0xFFFF] = STARS_BACK & 255, STARS_BACK >> 8
    r[_R_SP], r[_R_PC] = sp, STAR_ROUTINE
    r[_R_R] = (r[_R_R] & 0x80) | ((r[_R_R] + 1) & 0x7F)       # the CALL's M1
    sim = machine(Simulator, mem, r, 'u')
    t0 = sim.registers[_R_T]
    _run(sim, STARS_BACK)
    return list(sim.registers), sim.registers[_R_T] - t0


def _orig_loop(M, regs, site):
    """The original plot loop from its site to its LD SP,(46081) on a copy of the state: -> (registers there, T)."""
    from .simpool import machine
    from skoolkit.simulator import Simulator
    mem = bytearray(M[a] for a in range(65536)) if not isinstance(M, (bytes, bytearray)) else bytearray(M)
    sim = machine(Simulator, mem, list(regs), 'u')
    t0 = sim.registers[_R_T]
    if not _run(sim, ENTRIES[site][2], 200000):
        raise RuntimeError('loop did not end')
    return list(sim.registers), sim.registers[_R_T] - t0


def _accesses(site, regs, M):
    """The contended accesses the pace target counts for a plot: a screen read and write per byte drawn, and the popped
    bytes when the image is in 0x4000-0x7FFF (asm lsim)."""
    kind = ENTRIES[site][4]
    if kind == 'b4':
        rows, pops, drawn, img = 2, 4, 4, regs[8] << 8 | regs[9]
    elif kind == 'clip':
        rows, pops, drawn, img = M[ROWS], 8, bin(regs[3]).count('1'), regs[6] << 8 | regs[7]
    else:
        w = ENTRIES[site][3]
        rows, pops, drawn, img = regs[2], 2 * w, 2 * w, regs[6] << 8 | regs[7]
    return rows * (2 * drawn + (2 * pops if img < 0x8000 else 0))


def _rplus(r, n):
    return (r & 0x80) | ((r + n) & 0x7F)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, clock=0, clear=()):
    """Replay the recording (see the module docstring). clock: NR 7 every hook is entered at (the game's speed option);
    clear: pattern nibbles the screen compare counts as see-through (an outline set). -> (Counter, examples, states)."""
    from . import rzx as RZ
    if patch.pl is None:
        snap = RZ_first_snapshot(rzx_path)
        patch.build_plane(lambda a: snap[a])
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []

    def fail(k, *v):
        c[k + '!'] += 1
        if len(ex[k + '!']) < 5:
            ex[k + '!'].append(v)
    bare, bstars, changed, fc2, err2 = replay_bare(patch, rzx_path, stop, replay_stars(rzx_path, stop))
    if err2:
        fail('bare replay desync', err2)
    for t, n in changed:
        fail('bare play area changed after the objects', t, n)
    eng = Engine(patch, clock)
    s = patch.syms
    entries = {a: (s[v[0]], v[1], v[2], v[3], v[4]) for a, v in ENTRIES.items() if any(x[0] == a for x in patch.sites)}
    has_tick = any(x[0] in TICK_OPERANDS for x in patch.sites)
    has_cls = any(x[0] == CLS for x in patch.sites)
    has_clr = any(x[0] == CLR_OPERAND for x in patch.sites)
    has_star = any(x[0] == STARS_OPERAND for x in patch.sites)
    idx = [0]
    sidx = [0]
    tmax = collections.Counter()
    tick_t = [0, 0]                 # this tick: the build's hook time, the displaced original time (3.5 MHz T)
    deltas = []
    pcs = set(ENTRIES) | set(TICKS) | {CLS, CLR, EYE, STARS_CALL} | set(INTERIORS)
    eyes = set()
    div = (1.0, 2.0, 4.0, 8.0)[clock]

    def run_hook(kind, get, regs, start, stop_at, sp=None, ov=None, o_m1=0):
        """The hook from its gate entry, R as after the site's JP / CALL; -> (regs, ov, t, done, romw), and checks of
        speed, slots and R against the original's (R + o_m1 at the return point)."""
        r = list(regs)
        r[_R_R] = _rplus(r[_R_R], 1)
        rr, ov2, t, done, romw = eng.hook(get, r, start, stop_at, sp=sp, ov=ov, t_site=regs[_R_T] / div)
        c['hook calls'] += 1
        c['hook T (3.5 MHz T, real time)'] += t
        tmax[kind] = max(tmax[kind], t)
        c['T sum ' + kind] += t
        c['n ' + kind] += 1
        if not done:
            fail('hook did not return', kind)
        if eng.ns.nr.get(7, 0) & 3 != clock:
            fail('exit speed is not the incoming clock', kind, clock, eng.ns.nr.get(7))
        if eng.ns.slots != {1: 0xFF, 2: 10, 3: 11}:
            fail('slots left mapped', kind, dict(eng.ns.slots))
            eng.ns.slots = {1: 0xFF, 2: 10, 3: 11}
        if romw:
            fail('ROM or plane written', kind, romw)
        want = _rplus(regs[_R_R], o_m1 or 0)
        if o_m1 is not None and rr[_R_R] != want:
            from .hooklib import r_check
            fail('R differs at the return', kind, r_check(want, rr[_R_R]))
        return rr, ov2, t, done

    def on(pc, sim):
        R, M = sim.registers, sim.memory
        get = M.__getitem__
        if pc == EYE:
            c['object eyes'] += 1
            a = R[4] << 8 | R[5]
            y, x = scr_yx(a)
            for l in range(8):
                for k in (x, x + 1):
                    if k < 32:
                        eyes.add(_scr(y + l, k))
            return
        if pc == CLR:
            c['bitmap clears'] += 1
            c['IFF on at the bitmap clear'] += R[_R_IFF]
            if has_clr:
                regs = list(R)
                sp = (R[_R_SP] - 2) & 0xFFFF
                rr, ov, t, done = run_hook('clr', get, regs, s['e_clr'], CLR_TARGET, sp=sp, ov={sp: (CLR + 3) & 255, sp + 1: (CLR + 3) >> 8},
                                           o_m1=1)
                tick_t[0] += t
                rr[_R_SP] = regs[_R_SP]
                ov = {k: v for k, v in ov.items() if k not in (sp, sp + 1)}
                if ov or any(rr[j] != regs[j] for j in CMP_R if j not in (_R_PC, _R_R)):
                    fail('bitmap clear hook', done, sorted(ov.items())[:4])
            if eng.ns.visible():
                fail('sprites left at a bitmap clear', M[46062] | M[46063] << 8)
            return
        if pc in INTERIORS and pc not in ENTRIES and pc not in TICKS and pc != CLS:
            fail('jump into a patched instruction', pc)
            return
        if pc in ENTRIES:
            c['plots ' + ENTRIES[pc][0]] += 1
            if pc not in entries:
                return
            sym, back, end, w, kind = entries[pc]
            if R[_R_IFF]:
                fail('interrupts on at a hook site', pc)
            if collect and sum(1 for x in states if x[0] == pc) < collect:
                states.append((pc, list(R), bytes(M), eng.clone()))
            regs = list(R)
            want, t_orig = _orig_loop(M, regs, pc)
            up0 = eng.ns.uploads
            rr, ov, t, done = run_hook('plot', get, regs, sym, end, o_m1=None)
            if eng.ns.uploads != up0:
                c['plots that uploaded'] += 1
            acc = _accesses(pc, regs, M)
            pt = eng.page[s['ptT'] - 0x2000] | eng.page[s['ptT'] + 1 - 0x2000] << 8
            if pt - SC_T * acc != t_orig:
                fail('the hook\'s loop time differs from the original loop\'s', pc, pt - SC_T * acc, t_orig)
            tick_t[0] += t + 10
            tick_t[1] += t_orig + SC_T * acc
            if not done:
                return
            for i in CMP_R:             # SP: the loop's next instruction is LD SP,(46081), which the hook wrote
                if i not in (_R_PC, _R_SP) and rr[i] != want[i]:
                    fail('register differs from the original loop\'s at its end', pc, i, rr[i], want[i])
            sp = regs[_R_SP]
            if ov != {SPSAVE: sp & 255, SPSAVE + 1: sp >> 8}:
                extra = {k: v for k, v in ov.items() if k not in (SPSAVE, SPSAVE + 1)}
                if extra or ov.get(SPSAVE) != sp & 255 or ov.get(SPSAVE + 1) != sp >> 8:
                    fail('game memory written by hook', pc, sorted(ov.items())[:6])
            return
        if pc == CLS:
            c['screen clears'] += 1
            c['IFF on at the screen clear'] += R[_R_IFF]
            if has_cls:
                regs = list(R)
                rr, ov, t, done = run_hook('cls', get, regs, s['e_cls'], CONT_CLS, o_m1=1)
                tick_t[0] += t + 10
                if ov:
                    fail('cls hook wrote memory', sorted(ov.items())[:4])
                for i in CMP_R:
                    if i not in (_R_PC, _R_R, 6, 7) and rr[i] != regs[i]:
                        fail('register changed by cls hook', i)
                if rr[6] != 0x40 or rr[7] != 0:
                    fail('cls hook HL', rr[6], rr[7])
            if eng.ns.visible():
                fail('sprites left at a screen clear', M[46062] | M[46063] << 8)
            return
        if pc == STARS_CALL:
            k = sidx[0]
            sidx[0] += 1
            c['star calls'] += 1
            if R[_R_IFF]:
                fail('interrupts on at the star call', k)
            if k >= len(bstars):
                return
            if not has_star:            # the build runs the original routine on its own screen: its path, so R
                bm = bytearray(M[a] for a in range(65536))
                for a, v in zip(star_list(M), bstars[k]):
                    bm[a] = v
                if _orig_star(bm, R)[0][_R_R] != _orig_star(M, R)[0][_R_R]:
                    fail('star routine\'s R differs from the original\'s (a figure in a star byte)', k)
                return
            if collect and sum(1 for x in states if x[0] == pc) < collect:
                states.append((pc, list(R), bytes(M), eng.clone(), bstars[k]))
            want, t_orig = _orig_star(M, R)
            regs = list(R)
            sp = (R[_R_SP] - 2) & 0xFFFF
            al = star_list(M)
            ov0 = {sp: STARS_BACK & 255, sp + 1: STARS_BACK >> 8}
            for a, v in zip(al, bstars[k]):
                ov0[a] = v
            rr, ov, t, done = run_hook('star', get, regs, s['e_star'], STARS_BACK, sp=sp, ov=ov0, o_m1=None)
            orig_bytes = [M[a] for a in al]
            n0 = sum(1 for v in orig_bytes if v == 0)
            n255 = sum(1 for v in orig_bytes if v == 255)
            tick_t[0] += t
            tick_t[1] += t_orig + SC_T * (20 + n0 + n255)
            if not done:
                return
            if rr[_R_R] != want[_R_R]:
                fail('star hook R differs from the original', k, rr[_R_R], want[_R_R])
            for i in CMP_R:
                if i not in (_R_PC, _R_R) and rr[i] != want[i]:
                    fail('star hook register differs from the original', k, i, rr[i], want[i])
            exp = {}
            for a, v in zip(al, bstars[k]):
                exp[a] = v ^ 0x20 if v in (0, 255) else v
            got = {a: ov.get(a, bstars[k][i]) for i, a in enumerate(al)}
            if got != exp:
                fail('star hook screen', k)
            extra = {a: v for a, v in ov.items() if a not in exp and a not in (sp, sp + 1)}
            if extra:
                fail('star hook wrote game memory', k, sorted(extra.items())[:4])
            c['stars where a figure changed the original\'s path'] += sum(
                1 for a, v, b in zip(al, orig_bytes, bstars[k]) if (v == 0) != (b == 0))
            c['star bytes under a figure and an eye'] += sum(1 for a, v, b in zip(al, orig_bytes, bstars[k])
                                                          if a in eyes and v != b)
            return
        # a tick
        i = idx[0]
        idx[0] += 1
        c['ticks'] += 1
        if i > 0:
            deltas.append(tick_t[0] - tick_t[1])
        tick_t[0] = tick_t[1] = 0
        c['IFF on at a tick'] += R[_R_IFF]
        if i >= len(bare):
            fail('more ticks than the bare replay')
            return
        scr0, regs0, dig0 = bare[i]
        for k, j in enumerate(CMP_R):
            if regs0[k] != R[j]:
                fail('registers differ at a tick', i, j, regs0[k], R[j], pc)
                break
        if hashlib.md5(bytes(M[0x5800:0x10000])).digest() != dig0:
            fail('memory differs at a tick', i, pc)
        c['memory checks'] += 1
        if has_tick:
            regs = list(R)
            sp = (R[_R_SP] - 2) & 0xFFFF
            if collect and sum(1 for x in states if x[0] == pc) < collect:
                states.append((pc, list(R), bytes(M), eng.clone()))
            rr, ov, t, done = run_hook('tick', get, regs, s['e_tick'], BLIT, sp=sp, ov={sp: (pc + 3) & 255, sp + 1: (pc + 3) >> 8},
                                       o_m1=1)
            tick_t[0] += t
            ov = {k: v for k, v in ov.items() if k not in (sp, sp + 1)}
            if ov:
                fail('tick hook wrote memory', sorted(ov.items())[:4])
            rr[_R_SP] = regs[_R_SP]
            for j in CMP_R:
                if j not in (_R_PC, _R_R) and rr[j] != regs[j]:
                    fail('register changed by tick hook', j)
        c['tick T max'] = max(c['tick T max'], 0)
        attrs = bytes(M[0x5800:0x5B00])
        got = composite(eng, zlib.decompress(scr0), attrs, c, clear)
        want = bytes(M[0x4000:0x5800])
        c['most sprites'] = max(c['most sprites'], len(eng.ns.visible()))
        if attrs[21 * 32:] != bytes([0x6D]) * 96:
            c['ticks with other attributes in rows 21-23'] += 1
            if M[46062] | M[46063]:
                fail('water attributes changed', i)
        if got != want:
            stars = {a - 0x4000 for a in star_list(M)}
            where = [a for a in range(6144) if got[a] != want[a] and scr_yx(a)[0] < CLIP_Y]
            real = [a for a in where if not (a in stars and got[a] ^ want[a] == 0x20)]
            c['star bytes differing (a figure in the byte stopped the star in the original)'] += len(where) - len(real)
            n = len(real)
            real = [a for a in real if a not in eyes]
            c['bytes where a figure crosses an object eye (the eye was on top, now under)'] += n - len(real)
            if real:
                c['screens differing'] += 1
                fail('screen differs at a tick', i, len(real), scr_yx(real[0]), got[real[0]], want[real[0]], M[46062] | M[46063] << 8, pc)
        c['screens compared'] += 1
        eyes.clear()
        if eng.ns.bad:
            fail('next state', eng.ns.bad[:3])
            eng.ns.bad = []
        if eng.page[s['nrec'] - 0x2000] >= 40:
            fail('plot records full', i)
        if progress and i % 500 == 0:
            progress(i)
    fc, err = RZ.trace(rzx_path, pcs, on, stop=stop)
    c['frames'] = fc
    if err:
        fail('replay desync', err)
    if idx[0] != len(bare):
        fail('tick counts differ', idx[0], len(bare))
    if sidx[0] != len(bstars):
        fail('star call counts differ', sidx[0], len(bstars))
    c.update({'T max %s' % k: int(v) for k, v in tmax.items()})
    if deltas:
        deltas.sort()
        c['pace model: ticks'] = len(deltas)
        c['pace model: build over original, T a tick, mean'] = round(sum(deltas) / len(deltas), 1)
        c['pace model: worst tick T'] = int(deltas[-1])
        c['pace model: best tick T'] = int(deltas[0])
        mean = sum(deltas) / len(deltas)
        if mean < -112:
            fail('pace model: the build is faster than the original (mean T a tick)', round(mean))
        if mean > 1400:
            fail('pace model: the build is slower than the original by over 2 % of a tick (mean T a tick)', round(mean))
    c['hook T (3.5 MHz T, real time)'] = int(c['hook T (3.5 MHz T, real time)'])
    return c, ex, states


def RZ_first_snapshot(rzx_path):
    from .rzx import read_segments
    return read_segments(rzx_path)[0][0].memory


# ---------------------------------------------------------------------------------------------
# Unit tests: every image, every edge, against the game's own plot loop on 0x00 and 0xFF screens
# ---------------------------------------------------------------------------------------------

KIND_SITE = {'c4': 40370, 'c3': 40709, 'c5': 40539, 'b4': 37662, 'clip': 40188}


def _regs(site, gfx, scr, rows, mask=0, skip=0):
    """Registers at a site, for a plot of this image."""
    r = [0] * 30
    r[_R_SP] = 0xFF00
    r[_R_PC] = site
    r[14] = 0x39
    kind = ENTRIES[site][4]
    if kind == 'b4':
        r[6], r[7] = scr >> 8, scr & 255
        r[8], r[9] = gfx >> 8, gfx & 255
        r[4], r[5] = 0, 0
    else:
        r[6], r[7] = gfx >> 8, gfx & 255
        r[4], r[5] = scr >> 8, scr & 255
        r[2] = rows
        if kind == 'clip':
            r[3] = mask
            r[16] = mask        # A': the loop reloads C from it each row
            r[21] = skip        # E': columns off the left
    return r


def truth(m, site, gfx, scr, rows, mask=0, skip=0, regs_out=None):
    """The game's own loop from its site on a 0x00 and a 0xFF screen. -> (screen 0, screen FF); regs_out gets its
    registers at the end."""
    from .simpool import machine
    out = []
    for fill in (0, 0xFF):
        mem = bytearray(m)
        mem[0x4000:0x5800] = bytes([fill]) * 6144
        if ENTRIES[site][4] == 'clip':
            mem[ROWS] = rows
        sim = machine(_rw(), mem, _regs(site, gfx, scr, rows, mask, skip), 'u')
        if not _run(sim, ENTRIES[site][2]):
            raise RuntimeError('loop did not end')
        out.append(bytes(sim.memory[0x4000:0x5800]))
        if regs_out is not None:
            regs_out.append(list(sim.registers))
    return out


def _tick(eng, get):
    sp = 0xFEFE
    eng.hook(get, _regs(40370, 0x6000, 0x4000, 1), eng.patch.syms['e_tick'], BLIT, sp=sp)


def _unit_case(eng, m, site, gfx, scr, rows, mask=0, skip=0):
    """-> None or a difference. The hook must leave what the loop's own bits say, on both screens."""
    get = m.__getitem__
    s = eng.patch.syms
    for _ in range(2):      # two ticks: nothing on show
        _tick(eng, get)
    mem = bytearray(m)
    if ENTRIES[site][4] == 'clip':
        mem[ROWS] = rows
    regs = _regs(site, gfx, scr, rows, mask, skip)
    sym, end = s[ENTRIES[site][0]], ENTRIES[site][2]
    r1 = list(regs)
    r1[_R_R] = _rplus(r1[_R_R], 1)
    rr, ov, t, done, romw = eng.hook(mem.__getitem__, r1, sym, end)
    if not done:
        return 'no return'
    ro = []
    t0, tf = truth(m, site, gfx, scr, rows, mask, skip, ro)
    for i in CMP_R:
        if i not in (_R_PC, _R_SP) and rr[i] != ro[0][i]:
            return 'register %d %d %d' % (i, ro[0][i], rr[i])
    if {k for k in ov} - {SPSAVE, SPSAVE + 1} or romw:
        return 'memory %s' % sorted(ov)[:4]
    if eng.ns.slots != {1: 0xFF, 2: 10, 3: 11}:
        return 'slots'
    g0, gf = composite(eng, bytes(6144)), composite(eng, bytes([255]) * 6144)
    d = [a for a in range(6144) if (g0[a] != t0[a] or gf[a] != tf[a]) and scr_yx(a)[0] < CLIP_Y]
    if d:
        return 'pixels %d at %s' % (len(d), scr_yx(d[0]))
    return None


def _matrix_state(eng, rr, ov):
    """What a hook leaves that must not depend on the incoming clock: registers (R included), memory written, sprites,
    pattern RAM, the hook page but its speed latch and pace state."""
    s = eng.patch.syms
    pg = bytearray(eng.page)
    for a in range(s['vspd'], s['vspd'] + 1):
        pg[a - 0x2000] = 0
    for a in range(s['vpace'], s['vpace'] + 26):         # the limiter's 26 bytes of state
        pg[a - 0x2000] = 0
    for a in range(s['recs'] + 8 * 40, s['hstack']):     # the hook stacks: what the waits pushed
        pg[a - 0x2000] = 0
    return (tuple(rr[i] for i in CMP_R if i != _R_PC), tuple(sorted(ov.items())), tuple(map(tuple, eng.ns.attr)),
            hashlib.md5(bytes(eng.ns.pat)).hexdigest(), hashlib.md5(bytes(pg)).hexdigest(), tuple(sorted(eng.ns.slots.items())))


def clock_matrix(patch, states):
    """The every-site matrix (hooklib.every_site; card patch.restore-speed): each captured hook entry run at NR 7 = 0-3
    from the same state must exit at the same clock with the same results."""
    from .hooklib import every_site
    s = patch.syms
    cases = []
    for st in states:
        pc = st[0]
        cases.append(st)

    def run(i, k):
        st = cases[i]
        pc, regs, mem = st[0], st[1], st[2]
        eng = st[3].clone()
        eng.ns.speed_in = k
        get = mem.__getitem__
        r = list(regs)
        r[_R_R] = _rplus(r[_R_R], 1)
        if pc in ENTRIES:
            rr, ov, t, done, romw = eng.hook(get, r, s[ENTRIES[pc][0]], ENTRIES[pc][2])
        elif pc == STARS_CALL:
            sp = (r[_R_SP] - 2) & 0xFFFF
            ov0 = {sp: STARS_BACK & 255, sp + 1: STARS_BACK >> 8}
            ov0.update({a: v for a, v in zip(star_list(mem), st[4])})
            rr, ov, t, done, romw = eng.hook(get, r, s['e_star'], STARS_BACK, sp=sp, ov=ov0)
        else:
            sp = (r[_R_SP] - 2) & 0xFFFF
            rr, ov, t, done, romw = eng.hook(get, r, s['e_tick'], BLIT, sp=sp, ov={sp: (pc + 3) & 255, sp + 1: (pc + 3) >> 8})
        return eng.ns.nr.get(7, 0) & 3, (done, romw) + _matrix_state(eng, rr, ov)
    c, rows = every_site(range(len(cases)), run)
    sites = sorted({cases[r['site']][0] for r in rows})
    c['sites'] = len(sites)
    return c, rows


def store_check(patch, m):
    """Every listed image through the hook's prepared path and through its slow path (index emptied): the same bytes."""
    c = collections.Counter()
    slow = GryzorPatch(no_store=True)
    slow.pl = patch.pl
    slow.store, slow.index = patch.store, patch.index
    slow.page = slow._page()
    for g, sh, pg, off, units in patch.index:
        w, rows = sh >> 5, sh & 31
        kind = {3: 'c3', 4: 'c4', 5: 'c5', 2: 'b4'}[w]
        site = KIND_SITE[kind]
        got = []
        for p in (patch, slow):
            e = Engine(p)
            get = m.__getitem__
            for _ in range(2):
                _tick(e, get)
            e.hook(get, _regs(site, g, 0x4000 | _scr(48, 12), rows), p.syms[ENTRIES[site][0]], ENTRIES[site][2])
            got.append(bytes(e.ns.pat[0:units * 128]) if e.ns.uploads else None)
        c['store cases'] += 1
        want = slow_patterns(patch.pl, g, w, rows)
        if got[0] != got[1] or got[0] != want:
            c['prepared patterns differ from the slow path!'] += 1
    return c


def unit_tests(patch, states, neg=None):
    """Every image at the middle and across a third of the screen, 4-column images at each screen edge, cache eviction,
    a bad address, too many sprites, a synthetic colour map with a wrong check byte, the prepared patterns against the
    slow path, R with random values, and the every-site clock matrix."""
    import random
    c = collections.Counter()
    m = None
    for x in states:
        m = x[2]
        break
    if m is None:
        c['no state!'] += 1
        return c
    if patch.pl is None:
        patch.build_plane(m.__getitem__)
    eng = Engine(patch)
    figs = figures()

    def case(name, *a):
        c['cases'] += 1
        r = _unit_case(eng, m, *a)
        if r:
            c[name + '!'] += 1
            if c[name + '!'] <= 3:
                print('  unit', name, ['%x' % x for x in a], r)
    for kind, g, rows in figs:
        site = KIND_SITE[kind]
        for y in (48, 100):      # 48: the plot crosses into the second third
            case('middle', site, g, 0x4000 | _scr(y, 12), rows)
        if kind == 'c4':
            for col, mask in ((28, 255), (29, 231), (30, 195), (31, 129)):
                case('right edge', 40188, g, 0x4000 | _scr(64, col), rows, mask, 0)
            for skip, mask in ((1, 126), (2, 60), (3, 24)):
                a = 0x4000 | _scr(72, 0)
                a = (a & 0xFF00) | ((a & 255) - skip) & 255
                case('left edge', 40188, g, a, rows, mask, skip)
    # eviction: every image once more, reversed, with the cache long since rotated
    for kind, g, rows in reversed(figs):
        case('after eviction', KIND_SITE[kind], g, 0x4000 | _scr(48, 3), rows)
    # a bad address: no sprite, nothing else
    get = m.__getitem__
    s = patch.syms
    for _ in range(2):
        _tick(eng, get)
    r = _regs(40370, 0x5000, 0x4800, 16)
    want = _orig_loop(m, r, 40370)[0]
    r[_R_R] = _rplus(r[_R_R], 1)
    rr, ov, t, done, romw = eng.hook(get, r, s['e_c4'], 40443)
    if not done or eng.ns.visible() or any(rr[i] != want[i] for i in CMP_R if i not in (_R_PC, _R_SP)):
        c['bad address!'] += 1
    c['cases'] += 1
    # too many sprites: plots with no tick must stop at the limit, and return
    k = [x for x in figs if x[0] == 'c4' and x[2] == 16][0]
    for i in range(30):
        rr, ov, t, done, romw = eng.hook(get, _regs(40370, k[1], 0x4800, 16), s['e_c4'], 40443)
        if not done:
            c['no return when full!'] += 1
    if not 56 <= len(eng.ns.visible()) <= 64:
        c['sprite limit!'] += 1
    c['cases'] += 1
    # R: random values, bit 7 both ways; the plot hook must leave R as the loop does, never touch bit 7
    rnd = random.Random(7)
    for i in range(64):
        e = Engine(patch)
        r = _regs(40370, k[1], 0x4800, rnd.randrange(1, 17))
        r0 = rnd.randrange(256)
        r[_R_R] = r0
        want = _orig_loop(m, r, 40370)[0][_R_R]
        r[_R_R] = _rplus(r0, 1)
        rr, ov, t, done, romw = e.hook(get, r, s['e_c4'], 40443)
        c['R cases'] += 1
        if rr[_R_R] != want:
            c['R wrong after a plot!'] += 1
    # a synthetic colour map: a body bit painted, a wrong check byte ignored, a bit made see-through
    gm = graphics_memory(get)
    kind, g, rows = k[0], k[1], k[2]
    a = g + 2 * 40
    d, mk = gm[a], gm[a + 1]
    bits = [b for b in range(8) if not d >> (7 - b) & 1 and not mk >> (7 - b) & 1]
    if not bits:
        c['no body bit in the test image!'] += 1
        return c
    cm = {'%04X' % a: [d, 'g', [7 if b == bits[0] else 0 for b in range(8)]]}
    pl = plane(gm, cm)
    if ((pl[2 * (a - GB) + bits[0] // 2] >> (4 if bits[0] % 2 == 0 else 0)) & 15) != 7:
        c['map not in the plane!'] += 1
    pl2 = plane(gm, {'%04X' % a: [d ^ 1, 'g', [7] * 8]})
    if pl2 != plane(gm, {}):
        c['wrong check byte used!'] += 1
    if neg != 'map' and plane(gm, cm) == plane(gm, {}):
        c['map left out!'] += 1
    c['cases'] += 3
    c.update(store_check(patch, m))
    mc, rows_ = clock_matrix(patch, states)
    for kk, v in mc.items():
        c['matrix ' + kk] += v
    return c


def _code_patch(patch, sym, old, new, count=1, defines=None):
    """A copy of the hook page with bytes changed after symbol sym: a broken build for a control."""
    a = patch.syms[sym] - 0x2000
    pg = bytearray(patch.code)
    i = bytes(pg).index(bytes.fromhex(old), a)
    if i - a > 600:
        raise ValueError('pattern too far from %s' % sym)
    pg[i:i + len(bytes.fromhex(new))] = bytes.fromhex(new)
    return GryzorPatch(page_code=bytes(pg))


def _code_all(patch, old, new, lo=0x2000, hi=None):
    """Every occurrence of old in the page code between lo and hi -> new."""
    pg = bytearray(patch.code)
    o, n = bytes.fromhex(old), bytes.fromhex(new)
    i, k = lo - 0x2000, 0
    hi = (hi or 0x2000 + len(pg)) - 0x2000
    while True:
        i = bytes(pg).find(o, i, hi)
        if i < 0:
            break
        pg[i:i + len(n)] = n
        i += len(o)
        k += 1
    if not k:
        raise ValueError('pattern not found')
    return GryzorPatch(page_code=bytes(pg))


def _plane_swap(m, cmap=None):
    pl = bytearray(plane(m, cmap))
    for i, b in enumerate(pl):
        h, l = b >> 4, b & 15
        h = {1: 2, 2: 1}.get(h, h)
        l = {1: 2, 2: 1}.get(l, l)
        pl[i] = h << 4 | l
    return bytes(pl)


def _plane_seethrough(m, cmap=None):
    pl = bytearray(plane(m, cmap))
    for i, b in enumerate(pl):
        h, l = b >> 4, b & 15
        pl[i] = (0 if h == 2 else h) << 4 | (0 if l == 2 else l)
    return bytes(pl)


def negative_patches(patch):
    """(name, broken build, verify clock). Each must fail a full replay."""
    s = patch.syms
    w16 = lambda v: '%02X%02X' % (v & 255, v >> 8)
    out = [
        ('a store left in the build (40380)', GryzorPatch(drop_sites=(40380,)), 0),
        ('column one too far right', _code_patch(patch, 'attrs', 'C604', 'C605'), 0),
        ('line one too low', _code_patch(patch, 'attrs', 'C620', 'C621'), 0),
        ('bodies see-through', GryzorPatch(plane_fn=_plane_seethrough), 0),
        ('ink and body swapped', GryzorPatch(plane_fn=_plane_swap), 0),
        ('hook leaves DE wrong', _code_patch(patch, 'b_c4', 'ED5B' + w16(s['fde']), 'ED5B' + w16(s['fhl'])), 0),
        ('plane left mapped (slow path forced: no prepared patterns)', _slow(_code_patch(patch, 'unmap', 'ED91520A', 'ED915214')), 0),
        ('store page left mapped', _code_patch(patch, 'upload', 'ED91530B', 'ED915324'), 0),
        ('no hide or reset at the tick', _code_patch(patch, 'b_tick', 'CD' + w16(s['hide']), '210000'), 0),
        ('left clip ignored', _code_patch(patch, 'b_clip', '32' + w16(s['skip']), '210000'), 0),
        ('hook writes game memory', _code_patch(patch, 'b_c4', 'ED7301B4', 'ED7303B4'), 0),
        ('figures left at the level end', GryzorPatch(drop_sites=(CLR,)), 0),
        ('figures left at the menu', GryzorPatch(drop_sites=(CLS,)), 0),
        ('bullet not converted', GryzorPatch(drop_sites=(37662,)), 0),
        ('cache ignores the shape', _code_patch(patch, 'plot', 'BE28', 'BE18'), 0),
        ('a store writes game memory (40380: LD (DE),A)', GryzorPatch(store_op={40380: 0x12}), 0),
        # new for the 2026-11-05 build
        ('forced 3.5 MHz exit (replayed at 7 MHz)', _code_all(patch, '3A' + w16(s['vspd']) + 'ED9207', 'AF0000ED9207'), 1),
        ('missing cache invalidation (a replaced group keeps its old key)',
         _code_patch(patch, 'plot.inval', '773A', '003A'), 0),
        ('R not preserved (plot delta one off)', _code_patch(patch, 'b_c4', 'C6%02XCD' % _rd(patch, 'RD_P'), 'C6%02XCD' % ((_rd(patch, 'RD_P') + 1) & 255)), 0),
        ('star hook ignores the figures (R as the build\'s path)', _orig_off(patch), 0),
        ('limiter never waits', _code_patch(patch, 'hlib_pace_wait', '47', 'C9'), 0),
        ('slot 1 left on the hook page (plot exit)', _code_patch(patch, 'gx_c4', 'ED9151FF', 'ED915118'), 0),
        ('no star hook (the original routine on the build\'s screen)', GryzorPatch(drop_sites=(STARS_CALL,)), 0),
    ]
    return [x for x in out if x[1] is not None]


def _slow(p):
    """The same broken build with its prepared-pattern index emptied: every upload takes the slow path (the plane)."""
    p.no_store = True
    return p


def _rd(patch, name):
    """An R delta constant as assembled (read back from the plot hook's LD A,n before CALL hlib_r_set)."""
    s = patch.syms
    pg = patch.code
    a = s['b_c4'] - 0x2000
    call = bytes.fromhex('CD%02X%02X' % (s['hlib_r_set'] & 255, s['hlib_r_set'] >> 8))
    i = pg.index(call, a)
    return pg[i - 1]


def _orig_off(patch):
    """The star hook's orig routine returns the build's byte at once (as if no figure were drawn)."""
    s = patch.syms
    pg = bytearray(patch.code)
    a = s['orig'] - 0x2000
    pg[a:a + 4] = bytes.fromhex('32') + bytes([s['so'] & 255, s['so'] >> 8]) + b'\xC9'
    return GryzorPatch(page_code=bytes(pg))


def negative_real(patch, rzx_path, stop=4000, menu_rzx=None):
    """Each control on the recording; the menu's on one that reaches a game over (menu_rzx)."""
    res = {}
    for name, p, clock in negative_patches(patch):
        p.pl = None
        r = menu_rzx if menu_rzx and 'menu' in name else rzx_path
        c, ex, st = verify(p, r, stop=stop, clock=clock)
        res[name] = sum(v for k, v in c.items() if k.endswith('!'))
    return res


# ---------------------------------------------------------------------------------------------
# Colour route
# ---------------------------------------------------------------------------------------------

NOTE = ('Gryzor colour map (docs/COLOURS.md): key = graphics byte (hex address; check = its value); 8 nibbles, 0 = default '
        '(black ink, bright yellow body, see-through elsewhere); 1-15 the fixed colours; a see-through bit with a nibble is drawn '
        'opaque; optional 4th = transparent mask. Each of a figure\'s four shifted copies has its own bytes.')
RECOLOUR = {'game': 'gryzor', 'output': 'sprites', 'colours': 'docs/profiles/gryzor_colours.json', 'clear': True, 'note': NOTE}


def _unpatched(peek):
    """peek with this engine's sites back to the original bytes: the plane covers code addresses too, and is built before they change."""
    old = {}
    for a, o, new in GryzorPatch(colours={}).sites:
        if bytes(peek(a + k) for k in range(len(new))) == new:
            for k in range(len(o)):
                old[a + k] = o[k]
    return lambda a: old.get(a, peek(a))


def colour_identity(peek):
    gm = graphics_memory(_unpatched(peek))
    return {'schema': 1, 'game': 'gryzor', 'engine': 'gryzor', 'keys': 'gryzor-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': hashlib.md5(gm[GB:GE]).hexdigest(), 'geometry': None}


def recolour(nex, cmap):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build.
    The plane and the prepared patterns change; the hook page (with the store's index), game bytes and palette do not."""
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    p = GryzorPatch(colours=cmap)
    peek = nex_peek(nex)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    gm = graphics_memory(_unpatched(peek))
    p.pl = plane(gm, cmap)
    p.store, p.index = store_pages(p.pl, p.prof)
    p.page = p._page()
    nb = p.banks()
    if not set(nb) <= set(have):
        raise ValueError('not a Gryzor sprite build')
    if have[PAGE // 2] != nb[PAGE // 2]:
        raise ValueError('hook page differs from this version\'s (rebuild with nexclash.py auto)')
    out, changed = splice(nex, {b: v for b, v in nb.items() if b != PAGE // 2})
    used = [k for k in cmap if cmap[k][0] == gm[int(k, 16)]]
    return out, {'banks changed': changed, 'map entries used': len(used), 'map entries ignored': len(cmap) - len(used)}


def image_part(gm, kind, g, rows):
    px, ent = [], {}
    cols = 2 if kind == 'b4' else int(kind[1])
    w, h = cols * 8, 2 * rows
    for l in range(h):
        r = l // 2
        for c in range(cols):
            p = r * 2 * cols + (c if l % 2 == 0 else 2 * cols - 1 - c)
            if kind == 'b4':
                a = g + 2 * p + 1
                d, mk = gm[a], gm[a - 1]
            else:
                a = g + 2 * p
                d, mk = gm[a], gm[a + 1]
            key = '%04X' % a
            ent[key] = [d, 'g']
            for b in range(8):
                code = nibble(d, mk, b, None)
                px.append((c * 8 + b, l, key, b, code, code))
    return {'id': '%s_%04x_%d' % (kind, g, rows), 'size': 1, 'w': w, 'h': h, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
            'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 'figures'}


def sheets(z80, out_dir, prefix='gryzor', colours=None, say=print):
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    gm = graphics_memory(get)
    comps = [{'count': 1, 'group': 'figures', 'parts': [image_part(gm, *f)]} for f in figures() if f[0] != 'clip']
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb, colours=cmap,
                  paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb, colours=cmap,
                  paint_clear=True, identity=ident)
    say('Sheets    : %d images; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


# ---------------------------------------------------------------------------------------------
# The whole run
# ---------------------------------------------------------------------------------------------

def outline_check(nex, onex, cmap):
    """The outline build against the default: only plane and store banks differ, and only in nibbles that are 0
    (see-through) in the default and the map's nibble at the map's outline bits. -> (problems, changed nibbles)."""
    from .recolour import banks
    a, b = banks(nex), banks(onex)
    bad, n = [], 0
    if set(a) != set(b):
        bad.append('bank sets differ')
    for k in a:
        if a[k] == b.get(k):
            continue
        if not (k in PLANE_BANKS or k >= STORE // 2):
            bad.append('bank %d differs' % k)
            continue
        for i, (x, y) in enumerate(zip(a[k], b[k])):
            if x != y:
                for sh in (4, 0):
                    p, q = x >> sh & 15, y >> sh & 15
                    if p != q:
                        n += 1
                        if p != 0:
                            bad.append('bank %d byte %d: an opaque pixel changed' % (k, i))
    return bad[:10], n


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : gryzor (figure stores in five plot loops -> NOPs; each loop gives a sprite; ULA keeps the blitted scenery)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                        'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = GryzorPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                         'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    if os.path.exists(OUTLINE):
        nex = open(spr, 'rb').read()
        black = outline_map(1)
        onex, info = recolour(nex, black)
        opath = os.path.join(out, name + '_sprites_outline.nex')
        open(opath, 'wb').write(onex)
        back = recolour(onex, {})[0] == nex
        prob, n = outline_check(nex, onex, black)
        ok = ok and back and not prob
        say('Outline   : %s  %s  black outline (owner, 2026-11-05); %d nibbles 0 -> 1 in plane and store banks only; back to '
            'the default byte-exact: %s %s' % (os.path.basename(opath), md5(opath), n, back, prob or ''))
    states = []
    menu_rzx = None
    white = outline_map(15) if os.path.exists(OUTLINE) else None
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=1)
        if c['screen clears'] and not menu_rzx:
            menu_rzx = r
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d ticks, %d screens compared, %d memory checks, clears %d, %d, star calls %d, '
            'most sprites %d -> %s' % (
                os.path.basename(r), c['frames'], c['ticks'], c['screens compared'], c['memory checks'], c['screen clears'],
                c['bitmap clears'], c['star calls'], c['most sprites'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            plots: %s; plots that uploaded %d' % (
            ', '.join('%s %d' % (k[6:], c[k]) for k in sorted(c) if k.startswith('plots ') and k != 'plots that uploaded'),
            c['plots that uploaded']))
        say('            star bytes differing, a figure in the byte stopped the star in the original: %d; stars where a figure '
            'changed the original\'s path (R kept by the star hook) %d; under a figure and an eye %d' % (
                c['star bytes differing (a figure in the byte stopped the star in the original)'],
                c['stars where a figure changed the original\'s path'], c['star bytes under a figure and an eye']))
        say('            bytes where a figure crosses an object eye, which was on top and is now under: %d; eyes drawn %d' % (
            c['bytes where a figure crosses an object eye (the eye was on top, now under)'], c['object eyes']))
        say('            body pixels on a paper other than the figures\' own: %d of %d; figure pixels %d' % (
            c['body pixels on another paper'], c['body pixels'], c['figure pixels']))
        say('            IFF on: ticks %d, screen clears %d, bitmap clears %d' % (
            c['IFF on at a tick'], c['IFF on at the screen clear'], c['IFF on at the bitmap clear']))
        say('Speed     : hooks %d T real time (3.5 MHz T) in %d calls; most: %s; pace model: build over original %s T a '
            'tick (best %s, worst %s)' % (
                c['hook T (3.5 MHz T, real time)'], c['hook calls'],
                ', '.join('%s %d' % (k[6:], c[k]) for k in sorted(c) if k.startswith('T max ')),
                c['pace model: build over original, T a tick, mean'], c['pace model: best tick T'], c['pace model: worst tick T']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
        if white is not None and getattr(a, 'outline_verify', True):
            wp = GryzorPatch(colours=white)
            cw, exw, _ = verify(wp, r, stop=getattr(a, 'quick', None), clear=(15,))
            fw = {k: v for k, v in cw.items() if k.endswith('!')}
            ok = ok and not fw
            say('Outline   : %s  outline set (its white twin, the outline nibble as see-through): %d screens -> %s' % (
                os.path.basename(r), cw['screens compared'], 'IDENTICAL' if not fw else 'FAILED %s' % fw))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(u.items())), 'PASS' if not uf else 'FAIL'))
        if a.rzx and not getattr(a, 'no_negatives', False):
            res = negative_real(patch, list(a.rzx)[0], stop=min(getattr(a, 'quick', None) or 5000, 5000), menu_rzx=menu_rzx)
            miss = [k for k, n in res.items() if not n]
            ok = ok and not miss
            say('Negative  : %s  %d of %d detected %s' % (os.path.basename(list(a.rzx)[0]), len(res) - len(miss), len(res), miss or ''))
            for k, n in res.items():
                say('            %s: %d failures' % (k, n))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 3 and sys.argv[1] == 'sheet':
        sheets(sys.argv[2], sys.argv[3])
