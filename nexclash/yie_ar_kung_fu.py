"""Yie Ar Kung-Fu (Imagine 1985, 128K edition): fighters, thrown stars, chain and hit spark -> 4-bit hardware sprites.
Game facts: games/yie_ar_kung_fu.md; hook source: asm/yie_ar_kung_fu_hooks.asm. Original and patched machines replay the recording
in lockstep; hook instructions are not counted, so game code stays in step."""
import collections
import copy
import hashlib
import json
import os
from pathlib import Path

RECORD = 'yie_ar_kung_fu'
SIG = (0xB3F9, bytes.fromhex('01fd7f'))
ROM_ORG = 0x386E
HB = 0xE000
CODE0 = 0x0600
BITS = 0x00F0
STORE = 28
NSTORE = 32
ALT_PAGE, HPG = 24, 26
V_RING = 0x0004
V_GBODY, V_GROUND = 0x003B, 0x003C
GROUND = 0x5800 + 22 * 32 + 2
ULA_COLOURS = (0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF)
TAB = 0x1800
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'yie_ar_kung_fu_colours.json')
# Group colours: index 0 transparent, 1 ink, 2 body, 3 outline. 0 hero, 1 opponent, 2 objects and chain, 3 spark.
# The game's own colours in play: black ink on the lawn's cyan paper (attribute 0x28); the production build leaves the optional outline disabled.
BLACK, CYAN, WHITE = 0x00, 0x16, 0xFF
GROUPS_DEFAULT = [[0, BLACK, CYAN, WHITE]] * 3 + [[0, BLACK, CYAN, WHITE]]
# Overlay (2026-11-26): every pixel store stays, so the screens hold what the original's hold and the thrown-star hit
# test (0xF622: drawing-screen cell vs clean copy) and the random generator read the original's bytes; the sprites
# cover the figures. Only the spark's attribute stores go (its coloured cell would clash); nothing reads them.
NOP_SITES = [(0xB90B, 0x77), (0xB914, 0x77), (0xB91B, 0x77), (0xB948, 0x12)]
SITES = [(0xB4EC, 'cdd8b5', 'CD', 'e_plot'), (0xB528, 'cdd8b5', 'CD', 'e_plot'), (0xB3F9, '01fd7f', 'CD', 'e_flip'),
         (0xF563, 'cd6cf5', 'CD', 'e_star'), (0xEF25, '22e3bd', 'CD', 'e_chain'), (0xEFAB, '2ae3bd', 'C3', 'e_cwipe'),
         (0xB908, '3ac8b9', 'CD', 'e_spark'), (0xB91C, 'cd90f4', 'CD', 'e_spoff'),
         (0xAAAF, '21ff5a', 'C3', 'e_wa'), (0xAAE9, '3acfbd', 'C3', 'e_wb'), (0xB547, '3abfbd', 'CD', 'e_cave'),
         (0xB9B3, '218da9', 'C3', 'e_rng')]
L2BANK, L2PG = 30, 60           # Layer 2 over the sprites: the Feedle caves (asm c_cave), transparent elsewhere
CAVE_X = ((0, 40), (216, 256))
CAVE_Y = (144, 188)
CMP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27]
RNG_READ = 0xB9AE
CLEAN = 0x5B00                  # clean copy of the screen's lower two thirds, from 0x4800
ZONE = (64, 192)
HALT = 0xB3E2
OBJI, FPTR = 48570, 47088


def is_yie_ar_kung_fu(snap):
    a, b = SIG
    try:
        m = snap.ram(-1)
    except Exception:
        return False
    if len(m) != 0x20000:
        return False
    bank2 = snap.memory.banks[2]
    return bytes(bank2[a - 0x8000:a - 0x8000 + len(b)]) == b and bytes(bank2[0xB4EC - 0x8000:0xB4EF - 0x8000]) == bytes.fromhex('cdd8b5')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


# The first eleven banks follow the opponent overlay. The last two distinguish
# Oolong from Blues when the game draws both using the resident player frames.
PAINT_BANK = 33
FIGHTERS = ('Buchu', 'Star', 'Nuncha', 'Pole', 'Feedle', 'Chain', 'Club', 'Fan', 'Sword', 'Tonfun', 'Blues', 'Oolong', 'Blues resident')
ARCADE = [0, 0, 191, 250, 214, 173, 255, 19, 192, 242, 252, 89, 188, 212, 182, 254]
RECOLOUR = dict(game=RECORD, output='sprites', colours=COLOURS, clear=False,
                note='Arcade fighter colours. Keys are fighter number and unmirrored graphics-byte address.')


def load_colours(path=COLOURS):
    from . import coloursheet, recolour
    return coloursheet.load(recolour.build_colours_path(path))


def paint_banks(cmap):
    atlas = {PAINT_BANK + i: bytearray(16384) for i in range(len(FIGHTERS))}
    for key, entry in cmap.items():
        fighter, address = (int(v, 16) for v in key.split(':'))
        if not 0 <= fighter < len(FIGHTERS):
            raise ValueError('unknown fighter in colour key ' + key)
        base = 0x8100 if fighter >= 11 else 0x6C80
        # A pixel key points to the ink byte, one after its mask.
        offset = 2 * (address - 1 - base)
        pixels = entry[2]
        if not 0 <= offset <= 16380 or len(pixels) != 8 or any(not 0 <= n <= 15 for n in pixels):
            raise ValueError('invalid colour entry ' + key)
        atlas[PAINT_BANK + fighter][offset:offset + 4] = bytes(
            pixels[i] * 16 + pixels[i + 1] for i in range(0, 8, 2))
    return atlas


def colour_identity(peek):
    digest = hashlib.md5(bytes(peek(a) for a in range(0x8100, 0xA100))).hexdigest()
    return dict(schema=1, game=RECORD, engine=RECORD, keys='fighter:ink-address/v1',
                inputs={'resident graphics': digest}, geometry=None)


def recolour(nex, cmap):
    from . import recolour as rc
    banks = rc.banks(nex)
    patch = YiePatch(colours=cmap)
    if (banks.get(13, b'')[CODE0:CODE0 + len(patch.page_code)] != patch.page_code
            or banks.get(12, b'')[ROM_ORG-0x2000:patch.regblock-0x2000] != patch.page[ROM_ORG-0x2000:patch.regblock-0x2000]
            or hashlib.md5(banks.get(2, b'')[0x100:0x2100]).hexdigest() != '6b125f57dc57b258192311efb9fe3b2c'):
        raise ValueError('wrong Yie Ar Kung-Fu graphics or hook code')
    for a, old, new in patch.sites:
        if banks.get(2 if a < 0xC000 else 7, b'')[a % 16384:a % 16384 + len(new)] != new:
            raise ValueError('wrong Yie Ar Kung-Fu hook at %04X' % a)
    hp = bytearray(banks[13])
    hp[V_GBODY] = patch.hpage[V_GBODY]
    setup = bytes.fromhex(patch.prof['hooks']['setup'])
    stub = bytearray(banks[10])
    if stub[0x1000:0x1000 + len(setup)] != setup:
        raise ValueError('wrong palette setup')
    start = 0x1000 + len(setup)
    stub[start:start+64] = patch.palette()
    updated, changed = rc.splice(nex, {10: stub, 13: hp, **patch.atlas})
    return updated, {'banks changed': changed, 'paint entries': len(cmap)}


def tab_bytes():
    t = bytearray(1024)
    for k in range(4):
        for v in range(256):
            hi = (v >> (7 - 2 * k)) & 1
            lo = (v >> (6 - 2 * k)) & 1
            t[k * 256 + v] = hi << 4 | lo
    return bytes(t)


class YiePatch:
    name = 'Yie Ar Kung-Fu figures -> hardware sprites over the figures the game still draws (alt ROM stubs, page 26 at slot 7)'

    def __init__(self, prof=None, colours=None, rom_code=None, page_code=None, outline=False, sites=None, nops=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.page_code = page_code if page_code is not None else bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.groups = [list(g) for g in GROUPS_DEFAULT]
        self.atlas = paint_banks(colours or {})
        if colours:
            self.groups[:3] = [ARCADE] * 3
        self.stub_extra = bytes.fromhex(h['setup']) + self.palette()
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.outline = outline
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock != self.syms['rom_end']:
            raise ValueError('hook code length differs from the profile symbols')
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hooks reach 0x3D00')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = bytearray(8192)
        self.page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.hpage = bytearray(16384)
        self.hpage[V_RING] = 1 if outline else 0
        self.hpage[V_GBODY] = int(not colours)   # default colours: bodies in the ground's paper (asm ground_body)
        self.hpage[V_GROUND] = 0x01                         # no body colour written yet
        self.hpage[CODE0:CODE0 + len(self.page_code)] = self.page_code
        self.hpage[TAB:TAB + 1024] = tab_bytes()
        self.hpage[BITS:BITS + 4] = bytes([1, 2, 4, 8])
        self.sites = []
        for a, old, op, sym in (sites if sites is not None else SITES):
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(op) + self.syms[sym].to_bytes(2, 'little')))
        self.nops = list(nops if nops is not None else NOP_SITES)
        original = [(a + i, v) for a, old, _ in self.sites for i, v in enumerate(old)] + self.nops
        table = bytes(v for a, byte in original for v in (a >> 8, a & 255, byte)) + b'\0'
        table_offset = self.syms['rng_table'] - 0x2000
        if table_offset + len(table) > self.regblock - 0x2000:
            raise ValueError('RNG table exceeds its reserved space')
        self.page[table_offset:table_offset + len(table)] = table
        self._banks()

    def palette(self):
        out = bytearray(64)
        for g, cols in enumerate(self.groups[:4]):
            out[g * 16:g * 16 + len(cols)] = bytes(cols)
        return bytes(out)

    def _banks(self):
        self.extra_banks = {12: bytes(self.page) + bytes(8192), 13: bytes(self.hpage)}
        self.extra_banks.update(self.atlas)
        for b in range(L2BANK, L2BANK + 3):
            self.extra_banks[b] = bytes([0xE3]) * 16384

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.port7ffd & 7 != 7:
            raise ValueError('Yie Ar Kung-Fu patch expects the 128K snapshot (7FFD bank 7)')
        ram = {5: bytearray(snap.banks[5]), 2: bytearray(snap.banks[2]), 7: bytearray(snap.banks[7])}

        def where(a):
            return (5, a - 0x4000) if a < 0x8000 else ((2, a - 0x8000) if a < 0xC000 else (7, a - 0xC000))
        for a, old, new in self.sites:
            for k in range(len(old)):
                b, o = where(a + k)
                if ram[b][o] != old[k]:
                    raise ValueError('unexpected code at 0x%04X' % (a + k))
            for k, v in enumerate(new):
                b, o = where(a + k)
                ram[b][o] = v
        for a, old in self.nops:
            b, o = where(a)
            if ram[b][o] != old:
                raise ValueError('unexpected byte at 0x%04X' % a)
            ram[b][o] = 0
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        self.page[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self._banks()
        snap.banks[5], snap.banks[2], snap.banks[7] = bytes(ram[5]), bytes(ram[2]), bytes(ram[7])


# ---------------------------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------------------------

class _NS:
    """Next-side state of the patched machine."""

    def __init__(self, patch):
        self.nr = {0x07: 0, 0x56: 14, 0x57: 15, 0x15: 5, 0x43: 0x20}   # as the stub's set-up leaves them
        self.sel = 0                    # 0x243B selection (hlib_speed reads NR 7 through 0x253B)
        self.store = bytearray(NSTORE * 8192)
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.H = bytearray(patch.hpage[:8192])
        self.spal = bytearray(256)                 # sprite palette 0 as the hooks leave it (the stub's set-up first)
        self.spal[:64] = patch.palette()
        self.l2 = bytearray([0xE3]) * 49152      # Layer 2 256 x 192, one byte a pixel
        self.palhold = dict()

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if reg == 0x41 and (self.nr.get(0x43, 0) >> 4) & 7 == 2:   # sprite palette 0, 8-bit colour, auto-increment
            i = self.nr.get(0x40, 0)
            self.spal[i] = val
            if not self.nr.get(0x43, 0) & 0x80:
                self.nr[0x40] = (i + 1) & 255
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def read_nr(self):
        v = self.nr.get(self.sel, 0)
        return ((v & 3) << 4) | (v & 3) if self.sel == 0x07 else v      # NR 7 read: actual speed 5:4, programmed 1:0

    def out(self, port, val):
        if port == 0x243B:
            self.sel = val
            return True
        if port == 0x253B:
            self.nextreg(self.sel, val)
            return True
        if port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
            return True
        if port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
            return True
        return False

    def sprite_layer(self):
        """-> {(x, y): (colour index, slot)}, screen coordinates, slot order as the hardware's: higher on top.
        .under_ink: the pixels where a lower slot has an ink pixel (under a higher sprite's pixel)."""
        out = _Layer()
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            x0 = a0 + (a2 & 1) * 256 - 32
            y0 = a1 + (a4 & 1) * 256 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            mir = a2 & 8
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    c = (b >> 4) if k % 2 == 0 else (b & 15)
                    if c:
                        xy = (x0 + (15 - k if mir else k), y0 + j)
                        if xy in out and out[xy][0] == 1:
                            out.under_ink.add(xy)
                        out[xy] = (c, i)
        return out


def rom48_image():
    from .build import rom48
    return bytes(rom48())


def game_machine(snap):
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    sim = from_snapshot(Simulator, snap, config={'int_active': 0})
    sim.memory.roms[1][:] = list(rom48_image())
    return sim


class _Ports:
    def __init__(self, sim, snap, ns=None):
        self.sim, self.ns = sim, ns
        self.o7ffd = snap.out7ffd
        self.ins = []
        self.i = 0
        self.bad = 0

    def read_port(self, registers, port):
        if self.ns is not None and port == 0x243B:
            return self.ns.sel
        if self.ns is not None and port == 0x253B and self.ns.sel == 0x57:
            return (self.o7ffd & 7) * 2 + 1
        if self.ns is not None and port == 0x253B:      # a hook reading a NextReg: the Next, not the recording
            return self.ns.read_nr()
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


def _patched_memory(mem, patch, ns, err):
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    lo, hi = patch.altrom
    page = patch.page
    H = ns.H
    nr = ns.nr
    store = ns.store
    l2 = ns.l2

    class PM(Memory):
        def __getitem__(self, a):
            if a >= HB and nr[0x57] == HPG:
                return H[a - HB]
            if 0xC000 <= a < 0xE000 and nr[0x56] != 14:
                if L2PG <= nr[0x56] < L2PG + 6:
                    return l2[(nr[0x56] - L2PG) * 8192 + a - 0xC000]
                pg = nr[0x56] - STORE
                if 0 <= pg < NSTORE:
                    return store[pg * 8192 + a - 0xC000]
                err.append(('slot 6 page', nr[0x56]))
                return 0
            if a < 0x4000:
                if lo <= a < hi:
                    if not self.o7ffd & 16:
                        err.append(('alt ROM stub with ROM 0 selected', a))
                    return page[a - 0x2000]
                if not self.o7ffd & 16:
                    err.append(('read of ROM 0', a))
            return MG(self, a)

        def __setitem__(self, a, v):
            if a >= HB and nr[0x57] == HPG:
                H[a - HB] = v
                return
            if 0xC000 <= a < 0xE000 and nr[0x56] != 14:
                if L2PG <= nr[0x56] < L2PG + 6:
                    l2[(nr[0x56] - L2PG) * 8192 + a - 0xC000] = v
                    return
                pg = nr[0x56] - STORE
                if 0 <= pg < NSTORE:
                    store[pg * 8192 + a - 0xC000] = v
                else:
                    err.append(('slot 6 write', nr[0x56]))
                return
            MS(self, a, v)
    if not H[V_GBODY]:
        # Paint scratch is the unused half of hook bank 13. Only the enhanced
        # path maps it and the read-only colour atlas while building a tile.
        scratch = bytearray(8192)

        class PaintedMemory(PM):
            def __getitem__(self, a):
                if 0x4000 <= a < 0x6000 and nr.get(0x52) == 27:
                    return scratch[a - 0x4000]
                if 0x8000 <= a < 0xC000:
                    page = nr.get(0x54 + ((a - 0x8000) >> 13), 0)
                    if page // 2 in patch.atlas:
                        return patch.atlas[page // 2][(page % 2) * 8192 + a % 8192]
                return super().__getitem__(a)

            def __setitem__(self, a, v):
                if 0x4000 <= a < 0x6000 and nr.get(0x52) == 27:
                    scratch[a - 0x4000] = v
                else:
                    super().__setitem__(a, v)
        mem.__class__ = PaintedMemory
        return
    mem.__class__ = PM


def patched_machine(snap, patch, err):
    from . import z80n
    sim = game_machine(snap)
    ns = _NS(patch)
    mem = sim.memory
    for a, old, new in patch.sites:
        for k, v in enumerate(new):
            mem[a + k] = v
    for a, old in patch.nops:
        mem[a] = 0
    _patched_memory(mem, patch, ns, err)
    z80n.install(sim, ns.nextreg, strict=False)
    return sim, ns


def _frames(rzx_path):
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


def _accept(sim, pc):
    R, mem = sim.registers, sim.memory
    R[25] = 0
    if R[26]:
        if mem[pc] == 0x76:
            R[24] = (R[24] + 1) % 65536
        sim.accept_interrupt(R, mem, 0)


def _addr(line, col, base=0x4000):
    return base + (((line & 0xC0) << 5) | ((line & 7) << 8) | ((line & 0x38) << 2)) + col


def shown_bank(o7ffd):
    return 7 if o7ffd & 8 else 5


def clean_pixels(mem, line, col):
    return mem.banks[5][CLEAN - 0x4000 + (_addr(line, col) - 0x4800)]


class _Layer(dict):
    def __init__(self):
        super().__init__()
        self.under_ink = set()


SPARK_FLIPS = 4                 # screen flips after a spark until both screens have been drawn again


def cell_of(addr):
    """screen address -> (x, y) of its 8 x 8 cell's top left"""
    a = addr & 0x1FFF
    return (a & 31) * 8, ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)


# The original's figure stores (fighters, star, chain, spark): the pixels they change are figure pixels; any other
# store (the clean-copy restores, the Feedle level's edge arches 0xB5B8 / 0xB588 / 0xB5AA) makes its pixels scenery.
FIG_STORES = frozenset((0xB632, 0xB6AC, 0xB6C4, 0xB73A, 0xB7BA, 0xB7D7, 0xF571, 0xEF39, 0xEF76, 0xB92D))


def track_figure_pixels(sim):
    """Per screen byte, the bits the original's figure stores set last (bank 5 and bank 7 bitmaps). -> {bank: bytearray}"""
    own = {5: bytearray(0x1800), 7: bytearray(0x1800)}
    R = sim.registers
    MS = type(sim.memory).__setitem__

    class Tracked(type(sim.memory)):
        def __setitem__(self, a, v):
            if 0x4000 <= a < 0x5800:
                b, off = 5, a - 0x4000
            elif a >= 0xC000 and a < 0xD800 and (self.o7ffd & 7) in (5, 7):
                b, off = self.o7ffd & 7, a - 0xC000
            else:
                MS(self, a, v)
                return
            changed = self[a] ^ v
            if R[24] in FIG_STORES:
                own[b][off] |= changed
            else:
                own[b][off] &= ~changed & 255
            MS(self, a, v)
    sim.memory.__class__ = Tracked
    return own


def expected_vs_original(so_mem, sp_mem, o7ffd, lay, skip_chain=None, allowed=None, hole=None, own=None, l2=None):
    """The shown screen of the original against sprites over the patched screen, for the figure zone.
    A sprite ink pixel must be set in the original; a body pixel clear; outline and empty pixels as the clean copy shows.
    Exceptions, by design, both about the outline (the owner's white ring, which the game does not draw): it may lie on
    another figure's ink, where the original shows that ink, or on a scenery pixel the game's mask clears next to the
    figure (both hide the scenery there). And the spark: the game copies it over its whole cell, so a figure there
    loses those pixels until the game draws that screen again; sprites keep the figure whole. `hole` = the last
    spark's cell (x, y) while that lasts: in it, a figure pixel where the original shows the clean copy is allowed.
    Such pixels go to `allowed` as (x, y, kind). own (track_figure_pixels): a pixel off the clean copy that no figure
    store drew is the game's own scenery (the Feedle level's edge arches), not a figure to cover. -> list of (x, y,
    sprite code, original bit, clean bit)."""
    bad = []
    under = getattr(lay, 'under_ink', ())
    b = shown_bank(o7ffd)
    orig = so_mem.banks[b]
    for y in range(*ZONE):
        for col in range(32):
            a = _addr(y, col) - 0x4000
            o = orig[a]
            c = clean_pixels(so_mem, y, col)
            for i in range(8):
                x = col * 8 + i
                v = lay.get((x, y))
                if hole and v and v[0] in (1, 2) and hole[0] <= x < hole[0] + 8 and hole[1] <= y < hole[1] + 8:
                    if bool(o & (0x80 >> i)) == bool(c & (0x80 >> i)):
                        if allowed is not None:
                            allowed.append((x, y, 'spark hole'))
                        continue
                bit = 0x80 >> i
                ob, cb = bool(o & bit), bool(c & bit)
                if l2 is not None and l2[y * 256 + x] != 0xE3:  # Layer 2 (a cave) over the sprites: the original's ink
                    if not ob:
                        bad.append((x, y, 'Layer 2', ob, cb))
                    elif allowed is not None:
                        allowed.append((x, y, 'cave'))
                    continue
                if v is None or v[0] == 3:
                    if ob != cb:
                        if skip_chain and skip_chain(x, y):
                            continue
                        if own is not None and not own[b][a] & bit:
                            if allowed is not None:
                                allowed.append((x, y, 'scenery'))
                            continue
                        if v and ob and (x, y) in under:
                            if allowed is not None:
                                allowed.append((x, y, 'on ink'))
                            continue
                        if v and not ob and cb:
                            if allowed is not None:
                                allowed.append((x, y, 'masked'))
                            continue
                        bad.append((x, y, v[0] if v else 0, ob, cb))
                elif v[0] == 1:
                    if not ob:
                        if skip_chain and skip_chain(x, y):
                            continue
                        bad.append((x, y, 1, ob, cb))
                elif v[0] == 2:
                    if ob:
                        if skip_chain and skip_chain(x, y):
                            continue
                        bad.append((x, y, 2, ob, cb))
    return bad


# ---------------------------------------------------------------------------------------------
# Differential verification: lockstep over the recording
# ---------------------------------------------------------------------------------------------

HIDE_SITES = {0xAAAF: 'wipe A', 0xAAE9: 'wipe B', 0xB91C: 'spark off', 0xEFAB: 'chain wipe'}


def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=4, speed=0):
    """-> (Counter, examples, states). Failure keys end in '!'."""
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    st = {'frame': 0}

    def fail(k, *info):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + info)

    lo, hi = patch.altrom
    for snap, frames in _frames(rzx_path):
        so = game_machine(snap)
        own = track_figure_pixels(so)
        po = _Ports(so, snap)
        so.set_tracer(po)
        err = []
        sp, ns = patched_machine(snap, patch, err)
        ns.nr[0x07] = speed             # the player's CPU speed: every hook must give it back
        pp = _Ports(sp, snap, ns)
        sp.set_tracer(pp)
        Ro, Rp, mo, mp, op = so.registers, sp.registers, so.memory, sp.memory, sp.opcodes
        nr = ns.nr
        H = ns.H
        hook_t = [0]
        worst = [0]
        chain = [False]
        tick = [0]
        ENTRIES = {a: None for a, _, _ in patch.sites}
        code_bytes = {a + k: None for a, old, new in patch.sites for k in range(len(old))}
        interior = code_bytes.keys() - ENTRIES.keys()
        code_bytes.update({a: None for a, _ in patch.nops})

        def in_hook(pc):
            return lo <= pc < hi or (pc >= HB and nr[0x57] == HPG)

        clear_layer = bytes([0xE3]) * 49152
        caves = bytearray(clear_layer)
        for x0, source in ((0, 41500), (216, 41741)):
            for row in range(44):
                for dx in range(40):
                    if row >= 38 or mo[source + row * 6 + dx // 8] & (128 >> (dx % 8)):
                        caves[(144 + row) * 256 + x0 + dx] = 0
        cave_pending = cave_visible = False
        spark_rows = {5: set(), 7: set()}

        def check_shown(where):
            """Compare the original bitmap, sprite coverage and the entire visible Layer 2 mask."""
            expected = caves if cave_visible else clear_layer
            cells = spark_rows[shown_bank(po.o7ffd)]
            if cave_visible and cells:
                expected = bytearray(expected)
                for x, y in cells:
                    for row in range(y, y + 8):
                        start = row * 256 + x
                        expected[start:start + 8] = clear_layer[:8]
            if ns.l2 != expected:
                fail('sprite layer differs: cave mask', where, cave_visible)
            c['layer checks'] += 1
            bk = shown_bank(mp.o7ffd)
            if pp.o7ffd != po.o7ffd:
                fail('paging differs', hex(pp.o7ffd), hex(po.o7ffd))
                return
            if bytes(mp.banks[bk][:0x1800]) != bytes(mo.banks[bk][:0x1800]):
                fail('shown screen pixels differ from the original at a layer check', where)
            lay = ns.sprite_layer()
            chn = None
            if H[0x12]:
                # the chain is an XOR on the shown screen: on a figure it inverts; those pixels are not modelled, the rest are
                ys = set()
                for s in range(80, 112):
                    if ns.attr[s][3] & 0x80:
                        ys.add(ns.attr[s][1] - 32)
                if ys:
                    y0 = min(ys)
                    chn = lambda x, y: y0 <= y <= y0 + 6
                c['chain up at a layer check'] += 1
            ok_out = []
            hole = st['hole'][:2] if st.get('hole') else None
            bad = expected_vs_original(mo, mp, po.o7ffd, lay, chn, ok_out, hole, own, ns.l2)
            c['cave pixels over the sprites (Layer 2)'] += sum(1 for q in ok_out if q[2] == 'cave')
            c['game-drawn pixels off the clean copy, not figures (Feedle arches)'] += sum(1 for q in ok_out if q[2] == 'scenery')
            c['figure pixels in a spark\'s cell the original has wiped (by design)'] += sum(1 for q in ok_out if q[2] == 'spark hole')
            c['outline pixels on another figure\'s ink (by design)'] += sum(1 for q in ok_out if q[2] == 'on ink')
            c['outline pixels where the game masks the scenery (by design)'] += sum(1 for q in ok_out if q[2] == 'masked')
            if bad:
                fail('sprite layer differs from the original screen', where, len(bad), bad[:6])
            c['layer pixels compared'] += len(lay)
            if ns.H[V_GBODY]:            # default colours: every shown figure's body in the ground's paper
                at = mo.banks[bk][GROUND - 0x4000]
                want = ULA_COLOURS[(at >> 3) & 7 | (8 if at & 0x40 else 0)]
                for sl in range(128):
                    a = ns.attr[sl]
                    if a[3] & 0x80 and sl != 127:
                        got = ns.spal[(a[2] >> 4) * 16 + 2]
                        c['body colour checks'] += 1
                        if got != want:
                            fail('body colour is not the ground paper', where, sl, hex(got), hex(want))
                            break
            mx = 0
            per = collections.Counter()
            for s in range(128):
                a = ns.attr[s]
                if a[3] & 0x80:
                    yy = a[1] + (a[4] & 1) * 256 - 32
                    for l in range(yy, yy + 16):
                        per[l] += 1
            if per:
                worst[0] = max(worst[0], max(per.values()))

        def compare_state(pc):
            for i in CMP:
                if Ro[i] != Rp[i]:
                    fail('register differs', hex(pc), i, Ro[i], Rp[i])
            if Ro[24] != Rp[24]:
                fail('PC differs', hex(Ro[24]), hex(Rp[24]))
            if pp.o7ffd != po.o7ffd:
                fail('paging differs', hex(pp.o7ffd), hex(po.o7ffd))

        def compare_ram():
            c['RAM compares'] += 1
            for b in range(8):
                bo, bp = mo.banks[b], mp.banks[b]
                # the two screens' pixels, attributes in a spark; a stack that an interrupt may push A on; patch sites
                if bytes(bo) == bytes(bp):
                    continue
                for a in range(16384):
                    if bo[a] != bp[a]:
                        addr = a + (0x4000 if b == 5 else 0x8000 if b == 2 else 0xC000)
                        if b in (5, 7) and 0x1800 <= a < 0x1B00 and a == st.get('spark cell'):
                            continue
                        if b == 2 and 0xBF80 <= addr < min(Ro[12], Rp[12], 0xC000):
                            continue
                        if b == 2 and addr in code_bytes:
                            continue
                        if b == 7 and addr in code_bytes:
                            continue
                        fail('RAM differs', b, hex(addr), bo[a], bp[a])
                        return

        for n, (fc, ins) in enumerate(frames):
            if stop and n >= stop:
                break
            st['frame'] = n
            po.ins, po.i = ins, 0
            pp.ins, pp.i = ins, 0
            f1, f2 = fc, fc
            # lockstep: one game instruction in each, hook instructions run free
            pco = pcp = Ro[24]
            f = fc
            while f > 0:
                # patched: run hook code free
                pcp = Rp[24]
                if in_hook(pcp):
                    r0 = list(Rp)
                    spd0 = nr[0x07]
                    t0 = Rp[25]
                    while in_hook(Rp[24]):
                        r15 = Rp[15]
                        o = mp[Rp[24]]
                        op[o]()
                        Rp[15] = r15
                    hook_t[0] = Rp[25] - t0
                    if hook_t[0] > st.get('hook_max', 0):
                        st['hook_max'] = hook_t[0]
                    c['hook T total'] += hook_t[0]
                    if hook_t[0] > 280000:
                        c['hooks over 280000 T at 28 MHz'] += 1
                    Rp[25] = t0
                    c['hook returns'] += 1
                    if not Rp[26] and Ro[26]:
                        fail('hook left interrupts off', hex(Rp[24]))
                    if nr[0x57] != 15 or nr[0x56] != 14:
                        fail('hook page left mapped', hex(Rp[24]))
                    if nr[0x07] != spd0:
                        fail('speed not restored', hex(Rp[24]), nr[0x07], spd0)
                    pcp = Rp[24]
                    # a hook ended in place of the original's own instruction
                    t = st.get('site')
                    if t is not None:
                        # run the original over the displaced instruction
                        st['site'] = None
                        _run_one(so, Ro, mo)
                        for i in CMP:
                            if Rp[i] != Ro[i]:
                                fail('hook changed a register', hex(t), i, Rp[i], Ro[i])
                        c['hook exits checked'] += 1
                        # The displaced game opcode consumes one recorded fetch.
                        f -= 1
                        pco = pcp = t
                        if Rp[24] != Ro[24]:
                            fail('PC after a hook', hex(t), hex(Rp[24]), hex(Ro[24]))
                    continue
                pco = Ro[24]
                if pco != pcp:
                    fail('PC differs', hex(pco), hex(pcp))
                    f = 0
                    break
                if pcp == HALT and not st.get('halted'):
                    st['halted'] = True
                    tick[0] += 1
                    if tick[0] % every == 0 and n > 2:
                        check_shown('HALT')
                # Observe original game control flow independently of the installed cave hook.
                if pco == 0xB55A:
                    cave_pending = True
                    spark_rows[12 - shown_bank(po.o7ffd)].clear()
                elif pco == 0xB92D:
                    dest = Ro[4] * 256 + Ro[5]
                    bank = 5 if dest < 0x8000 else po.o7ffd & 7
                    if bank in spark_rows:
                        spark_rows[bank].add(cell_of(dest & 0xF8FF))
                elif pco == 0xB3F9:
                    cave_visible = bool(mo[48575]) and (cave_pending or cave_visible)
                    cave_pending = False
                elif pco in (0xAAAF, 0xAAE9):
                    cave_pending = cave_visible = False
                    for cells in spark_rows.values():
                        cells.clear()
                if pcp in ENTRIES:
                    if collect and pcp in HIDE_SITES and sum(1 for q in states if q[0] == pcp) < collect:
                        states.append((pcp, list(Rp), [bytes(mp.banks[b]) for b in range(8)], pp.o7ffd, snap, bytes(ns.H)))
                    c['site %04X' % pcp] += 1
                    if pcp == 0xB3F9:
                        st['spark'] = False
                        st['halted'] = False
                        if st.get('hole'):
                            st['hole'] = st['hole'][:2] + (st['hole'][2] - 1,) if st['hole'][2] > 1 else None
                    if pcp == 0xB908:
                        st['spark'] = True
                        st['hole'] = cell_of(mo[47566] + 256 * mo[47567]) + (SPARK_FLIPS,)
                    if pcp == 0xEFAB:
                        c['chain wipes'] += 1
                    if pcp == 0xB91C:
                        pass
                    if not Rp[26] and pcp not in (0xEFAB, 0xB9B3):
                        fail('interrupts off at a site', hex(pcp))
                    if pcp != 0xB9B3 and pp.o7ffd & 7 != 7:
                        fail('a site with another bank at slot 7', hex(pcp), hex(pp.o7ffd))
                    st['site'] = pcp
                    r15 = Rp[15]
                    o = mp[pcp]
                    op[o]()
                    continue
                if pcp == 0xB90C:
                    check_shown('spark')
                    c['spark layer checks'] += 1
                if pcp == 0xB948:      # first attribute store, before the sprite hook
                    st['spark cell'] = (Ro[4] * 256 + Ro[5]) & 0x3FFF
                if pcp == 0xB91F:
                    st.pop('spark cell', None)
                if pcp == 0xF622:
                    c['star hit tests'] += 1
                if pcp in interior:
                    fail('execution inside displaced instruction', hex(pcp))
                if pcp == RNG_READ:
                    # the real hook at B9B3 repairs the sampled value; the verifier only observes it
                    hl = Rp[6] * 256 + Rp[7]
                    vo, vp = mo[hl], mp[hl]
                    o = mo[pco]
                    so.opcodes[o]()
                    op[mp[pcp]]()
                    if vo != vp:
                        c['generator reads where bytes differ'] += 1
                    c['generator reads'] += 1
                    f -= 1
                    continue
                o = mo[pco]
                oo = mp[pcp]
                if o != oo and pcp not in code_bytes:
                    fail('code differs at', hex(pcp), o, oo)
                if o in (0xDD, 0xFD):
                    r0_ = Ro[15]
                    so.opcodes[o]()
                    op[oo]()
                    f -= 2 - ((Ro[15] ^ r0_) % 2)
                else:
                    so.opcodes[o]()
                    op[oo]()
                    f -= 2 if o in (0xCB, 0xED) else 1
                if Rp[12] != Ro[12]:
                    fail('SP differs', hex(pcp), hex(Ro[12]), hex(Rp[12]))
                    f = 0
            # end of frame
            while in_hook(Rp[24]):
                r15 = Rp[15]
                o = mp[Rp[24]]
                op[o]()
                Rp[15] = r15
            if po.i != len(ins) or pp.i != len(ins) or po.bad or pp.bad:
                fail('recorded input consumption differs', po.i, pp.i, po.bad, pp.bad)
            if n % every == 0:
                compare_state(Ro[24])
                compare_ram()
            c['frames'] += 1
            if err:
                fail('patched machine error', err[:3])
                err.clear()
            _accept(so, pco)
            _accept(sp, pcp)
            if Ro[24] != Rp[24]:
                fail('PC after interrupt', hex(Ro[24]), hex(Rp[24]))
            if progress and n % 500 == 0:
                progress(n)
            if any(k.endswith('!') for k in c) and sum(v for k, v in c.items() if k.endswith('!')) > 30:
                break
    c['most sprites on a line'] = worst[0]
    c['longest hook T at 28 MHz'] = st.get('hook_max', 0)
    return c, ex, states


def _run_one(sim, R, mem):
    op = mem[R[24]]
    sim.opcodes[op]()


def boot_check(nex, z80, patch=None):
    """Boot the NEX in the Next model to the snapshot PC: registers, NEX banks = the (patched) snapshot's, paging, alt ROM."""
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = nextboot.boot(nex, s.pc)
    R, mem = st['R'], st['mem']
    bad = list(st['bad'])
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
        lo, hi = patch.altrom
        img1 = bytearray(rom48())
        img1[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
        if bytes(st['alt'][1]) != bytes(img1):
            bad.append(('alt image 1 differs from ROM 3 + hooks',))
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
        if (0x15, 0x05) not in st['nrlog']:
            bad.append(('sprites and Layer 2 (LSU) not set up',))
        if st['ports'].get(0x123B) != 2 or st['nr'].get(0x43) != 0x20:
            bad.append(('Layer 2 visibility or sprite palette selection',))
        if (0x12, L2BANK) not in st['nrlog']:
            bad.append(('Layer 2 bank not set',))
    return bad


def build(z80, out, name, say=print, outline=False):   # Jon 2026-11-26: no white outlines on anything
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    patch = YiePatch(outline=outline, colours=load_colours())
    spr = os.path.join(out, name + ('_sprites.nex' if not outline else '_ring_sprites.nex'))
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, YiePatch(outline=outline, colours=load_colours()))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    return (not bad and not bad2), (plain, spr), patch


# ---------------------------------------------------------------------------------------------
# Unit cases, negative controls and the whole run (docs/ENGINE_TEMPLATES.md "New engine checklist")
# ---------------------------------------------------------------------------------------------

# Page H's run-time ranges (asm/yie_ar_kung_fu_hooks.asm): variables, plot/cache/frame tables (0x0000-0x05FF), the silhouette,
# ink and ring planes (0x1200-0x17FF), scratch tile and hook stack (0x1C00-0x1FFF). Code (CODE0-) and TAB are the build's.
H_RUNTIME = ((0x0000, CODE0), (0x1200, 0x1800), (0x1C00, 0x2000))

HIDE_SLOTS = {0xAAAF: range(128), 0xAAE9: range(128), 0xB91C: (127,), 0xEFAB: range(80, 112)}


def hide_run(patch, state, speed):
    """A hide hook from a state the recording reached, every sprite shown first (and the chain counted whole for the
    chain wipe), entered at CPU speed `speed`. -> (failures, the slots it had to hide that are still shown)."""
    pc, R, banks, o7ffd, snap, H = state
    err = []
    sim, ns = patched_machine(snap, patch, err)
    for b in range(8):
        sim.memory.banks[b][:] = banks[b]
    sim.memory.out7ffd(o7ffd)
    ports = _Ports(sim, snap, ns)
    ports.o7ffd = o7ffd
    sim.set_tracer(ports)
    for lo_, hi_ in H_RUNTIME:                  # only the run-time ranges: the patch's own code and tables stay its own
        ns.H[lo_:hi_] = H[lo_:hi_]
    if pc == 0xEFAB:
        ns.H[0x12] = 32
    wipe = pc in (0xAAAF, 0xAAE9)
    if wipe:                                    # caves shown: a wipe must take them off Layer 2
        ns.H[0x3A] = 1
        ns.H[0x35] = 1
        for y in range(*CAVE_Y):
            for x0, x1 in CAVE_X:
                ns.l2[y * 256 + x0:y * 256 + x1] = bytes(x1 - x0)
    for i in range(128):
        ns.attr[i] = [40, 40, 0, 0x80 | (i & 63), 0]
    ns.nr[0x07] = speed
    sim.registers[:] = R
    lo, hi = patch.altrom
    nr = ns.nr
    sim.opcodes[sim.memory[sim.registers[24]]]()            # the site's CALL / JP into the hook
    n = 0
    while lo <= sim.registers[24] < hi or (sim.registers[24] >= HB and nr[0x57] == HPG):
        sim.opcodes[sim.memory[sim.registers[24]]]()
        n += 1
        if n > 200000:
            return ['no return from the hook'], []
    bad = ['%s %s' % e for e in err[:2]]
    if nr[0x07] != speed:
        bad.append('speed not restored (%d, entered at %d)' % (nr[0x07], speed))
    if nr[0x57] != 15 or nr[0x56] != 14:
        bad.append('hook page left mapped')
    if wipe and (any(v != 0xE3 for v in ns.l2) or ns.H[0x3A]):
        bad.append('cave left on Layer 2')
    return bad, [i for i in HIDE_SLOTS[pc] if ns.attr[i][3] & 0x80]


def unit_tests(patch, states):
    """The hide hooks (two wipes, spark off, chain wipe) from captured states with every sprite shown, at the four
    CPU speeds (hooklib.hide_cases). -> Counter, failures end in '!'."""
    from . import hooklib
    c = collections.Counter()
    for pc, name in HIDE_SITES.items():
        mine = [q for q in states if q[0] == pc]
        if not mine:
            c['%s hook: no state captured' % name] += 1
            continue
        c.update(hooklib.hide_cases(mine, {pc: name}, lambda _pc, st, speed: hide_run(patch, st, speed)))
    return c


def _rom_mutated(patch, find, new, after_sym):
    rom = bytearray(patch.rom_code)
    at = rom.find(bytes.fromhex(find), patch.syms[after_sym] - ROM_ORG)
    if at < 0:
        raise AssertionError('negative-control site missing: %s' % find)
    rom[at:at + len(bytes.fromhex(new))] = bytes.fromhex(new)
    return YiePatch(prof=patch.prof, rom_code=bytes(rom), outline=patch.outline)


def _page_mutated(patch, find, new):
    page = bytearray(patch.page_code)
    at = page.find(bytes.fromhex(find))
    if at < 0 or page.find(bytes.fromhex(find), at + 1) >= 0:
        raise AssertionError('negative-control site not unique: %s' % find)
    page[at:at + len(bytes.fromhex(new))] = bytes.fromhex(new)
    return YiePatch(prof=patch.prof, page_code=bytes(page), outline=patch.outline)


def negative_patches(patch):
    """-> [(name, broken patch, how it must be caught: ('verify', failure key) or ('unit', hide site))]. Each control
    is caught only by its own failure."""
    no_plot = YiePatch(prof=patch.prof, outline=patch.outline,
                       sites=[x for x in SITES if x[0] not in (0xB4EC, 0xB528)])
    no_ink = YiePatch(prof=patch.prof, outline=patch.outline)
    no_ink.hpage[TAB:TAB + 1024] = bytes(1024)
    no_ink._banks()
    return [
        ('plot hook leaves the CPU at 28 MHz', _rom_mutated(patch, '3a34e0ed9207', '3a34e0000000', 'e_plot'),
         ('verify', 'speed not restored')),
        ('plot hook swaps HL and DE', _rom_mutated(patch, '3a34e0ed9207dde1e1d1', '3a34e0ed9207dde1d1e1', 'e_plot'),
         ('verify', 'hook changed a register')),
        ('fighter plot sites not applied', no_plot, ('verify', 'sprite layer differs')),
        ('ink lost in the pattern tables', no_ink, ('verify', 'sprite layer differs')),
        ('a wipe leaves the sprites shown', _page_mutated(patch, 'afed9234ed913800', 'afed923400000000'), ('unit', 0xAAAF)),
        ('spark off leaves the spark shown', _page_mutated(patch, 'ed91347fed913800', 'ed91347f00000000'), ('unit', 0xB91C)),
        ('bodies keep the lawn cyan on every level', _page_mutated(patch, 'ed92404f7bed924179c610', 'ed92404f7b00000079c610'),
         ('verify', 'body colour is not the ground paper')),
        ('cave hook not applied (clones in front of the caves)',
         YiePatch(prof=patch.prof, outline=patch.outline,
                  sites=[x for x in SITES if x[0] != 0xB547]), ('verify', 'sprite layer differs')),
    ]


def menu_builds(z80, out, name, sprites, args):
    """Build the menu choices from the supplied snapshot and the optional arcade paint."""
    from . import coloursheet, z80tonex
    source = z80tonex.Z80Snapshot(z80)
    screen = bytes(source.banks[7][:6912])
    if hashlib.md5(screen).hexdigest() != 'e402ee0387276c0f8640afc9a321e0df':
        raise ValueError('unexpected 128K loading screen in bank 7')
    for address in (44123, 44170):
        if source.banks[2][address - 0x8000] != 0x35:
            raise ValueError('trainer expects DEC (HL) at %04X' % address)
    if not getattr(args, 'pok', None):
        trainer = Path(out) / (name + '_verified.pok')
        trainer.write_text('NInfinite energy\nZ 8 44123 0 53\nNInfinite lives\nZ 8 44170 182 53\nY\n')
        args.pok = str(trainer)
    plain = Path(sprites).read_bytes()
    cmap = coloursheet.load(COLOURS.replace('_colours.json', '_enhanced_colours.json'))
    if not cmap:
        raise ValueError('missing arcade painting')
    enhanced, _ = recolour(plain, cmap)
    for choice, data in [('sprites', plain), ('enhanced', enhanced)]:
        stem = Path(out) / (name + '_' + choice)
        if choice == 'enhanced':
            stem.with_suffix('.nex').write_bytes(data)
        header = bytearray(data[:512])
        header[10] = 2
        Path(str(stem) + '_loading.nex').write_bytes(header + screen + data[512:])


def auto(a, z80, name, out, say):
    """The whole run: plain + sprite builds with boot checks, each recording verified (autosaves are not stripped:
    _frames keeps each segment's own snapshot, and the patched machine starts again from it), the speed matrix,
    hide cases and the negative controls. -> True on PASS."""
    say('Game      : %s' % name)
    say('Engine    : yie_ar_kung_fu (figures as sprites over the figures the game still draws; spark cell attributes removed)')
    ok, files, patch = build(z80, out, name, say)
    menu_builds(z80, out, name, files[1], a)
    rz, quick = list(getattr(a, 'rzx', None) or []), getattr(a, 'quick', None)
    if not rz:
        say('Verify    : none (no recording given): builds and boot checks only')
        say('Result    : %s (builds and boot checks only)' % ('PASSED' if ok else 'FAILED'))
        return ok
    states, reached = [], collections.Counter()
    for r in rz:
        c, ex, st = verify(patch, r, stop=quick, collect=4)
        states += st
        reached.update({k: v for k, v in c.items() if k.startswith('site ')})
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        if not c['hook returns'] or not c['layer checks']:
            fails['no hook or layer check reached: nothing verified!'] = 1
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d hook returns, %d layer checks (%d pixels), %d RAM compares -> %s' % (
            os.path.basename(r), c['frames'], c['hook returns'], c['layer checks'], c['layer pixels compared'],
            c['RAM compares'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            star tests %d, cave pixels %d, ground palette checks %d, generator raw differences %d/%d' %
            (c['star hit tests'], c['cave pixels over the sprites (Layer 2)'], c['body colour checks'],
             c['generator reads where bytes differ'], c['generator reads']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
    missing = ['%04X' % x[0] for x in SITES if not reached['site %04X' % x[0]]]
    if missing and not quick:
        ok = False
    say('Coverage  : sites not reached: %s' % (', '.join(missing) or 'none'))
    n = min(quick or 1500, 1500)
    for k in (1, 2, 3):
        c, _, _ = verify(patch, rz[0], stop=n, speed=k)
        bad = {x: v for x, v in c.items() if x.endswith('!')}
        ok = ok and not bad
        say('Speed     : entered at speed %d, %d frames: %s' % (k, c['frames'], 'IDENTICAL' if not bad else bad))
    u = unit_tests(patch, states)
    ok = ok and not any(k.endswith('!') for k in u) and not any('no state captured' in k for k in u)
    say('Unit      : %s' % ', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.startswith('  ')))
    caught = []
    for nm, broken, (how, what) in negative_patches(patch):
        hit = False
        if how == 'verify':
            for r in (sorted(rz, key=lambda path: 't3' not in os.path.basename(path)) if
                      'cave' in nm or 'cyan' in nm else rz):
                frames = 4400 if 'cave' in nm else 30000 if 'cyan' in nm else 3000   # Feedle t3 4191-; the courtyard later
                c, _, _ = verify(broken, r, stop=min(quick or frames, frames))
                if any(k.endswith('!') and what in k for k in c):
                    hit = True
                    break
        else:
            mine = [q for q in states if q[0] == what]
            hit = any(hide_run(broken, q, 0)[1] for q in mine[:2])
        caught.append(hit)
        say('Negative  : %s: %s' % (nm, 'DETECTED' if hit else 'MISSED'))
    ok = ok and all(caught)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
