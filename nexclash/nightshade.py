"""Nightshade (Ultimate Play The Game, 1985, 48K) engine 'nightshade'. Additive module: reachable only
through is_nightshade(). Facts and design: games/nightshade.md. Hooks: asm/nightshade_hooks.asm.

Filmation II composes the play area in a mono back buffer (0xE5C6, 24 bytes a row, rows bottom-up) and an
attribute buffer, then blits both. Figures go through one masked plotter and have no colour in the buffer:
they show in whatever attribute the scenery gave the cell. The patch keeps every plot; a hook runs the
game's own plot loop a second time into a zeroed scratch buffer to learn the figure's ink, and at the blit
that ink AND the final buffer becomes 4-bit sprites in the figure's colour. The hero's colour box is not
painted (registers kept), so the scenery behind him keeps its colours.

verify() replays the recording through the original (SkoolKit rzxplay) and runs the real patched game beside
it on a Python simulator fed the same IN values, frames by the recording's fetch counts with hook fetches
left out. At every hook site: registers and all RAM except the patch's own (stub area, dead stack, the
hero's 8 attribute cells); at every blit: the sprite picture against an independent model (the original's
plot loop run in Python into a zero buffer, AND the original's final buffer, in the figure's colour).
"""
import collections
import json
import os

RECORD = 'nightshade'
_HERE = os.path.dirname(os.path.abspath(__file__))
TAIL_ADDR = 0x5B00
RAM_ORG = 0x5B4F
PAGE_ORG = 0x2000
H_PAGE = 26
H_BANK = 13
BUF = 0xE5C6
ATTRBUF = 0xF046
SAVESP = 0xBBAE
FW, FH = 0xBBC2, 0xBBC3
PLOOP = 0xE4C9
HFLAG, HIDX, HTAB = 0xBC8E, 0xBBF3, 0xC065
HERO_IX = (0xBC8E, 0xBC9E)
GTAB = 28318
HERO_CELLS = [0xF0C8 + 24 * i + k for i in range(4) for k in (0, 1)]
HERO_SCREEN = [0x5800 + 32 * (10 - i) + 17 + k for i in range(4) for k in (0, 1)]   # where the blit puts them
SITE_FIG, SITE_BL, SITE_CLS, SITE_HB = 0xE45E, 0xE200, 0xE59D, 0xBEC4
BL_END = 0xE206                  # the blit hook runs both blits (0xE148, then the original's 0xE203 CALL 0xE1AD) and returns here
SCR_ROOM = 0x3700 - 0x2B40       # scratch buffer and its spill, below the hook page's second code block
SITES_ORIG = {SITE_FIG: 'ed73aebb', SITE_BL: 'cd48e1', SITE_CLS: 'cda8e5', SITE_HB: 'cd98c8'}
SITE_SYM = {SITE_FIG: 's_fg', SITE_BL: 's_bl', SITE_CLS: 's_cls', SITE_HB: 's_hb'}
INTERIORS = (0xE45F, 0xE460, 0xE201, 0xE202, 0xE59E, 0xE59F, 0xBEC5, 0xBEC6)
# ULA bright colours in RRRGGGBB, sprite palette entry 16 * k + 1 = colour k (the figure's own)
BRIGHT = [0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
NIB_AT, POFF_AT = 0x0700, 0x0600       # in the hook page
LPAGE, PLTPAGE, PLANE_PAGE0 = 28, 29, 30   # bank 14: the figure records, the plane table; planes from page 30 (bank 15)
# Enhanced (off by default): painted by parts from each graphic's own pixels, nexclash/nightshade_paint.py.


def plane_banks(mem, swap=False, flip_lost=False, enhanced=False, maps_lost=False):
    """-> ({bank: 16K}, {(g, orientation): (page, address)}, planes, paint): the two colour planes of every figure
    graphic in its four orientations, packed into 8K pages from PLANE_PAGE0 (none straddles a page), and the table.
    The default build carries the v2 planes (nightshade_paint_v2, unused there) so its bytes stay as released; the
    Enhanced build carries the v3 set. Both have the same sizes, so the same table. maps_lost (a negative): the
    banks get the v3 planes made without the hero's part maps, the returned planes (the model's) keep them."""
    from . import nightshade_paint as NP
    from . import nightshade_paint_v2 as NP2
    cim = None
    if enhanced:
        pl, paint = NP.planes(mem)
        pl_b = NP.planes(mem, maps=False)[0] if maps_lost else pl
        cim = NP.code_images(mem, maps=not maps_lost)      # what the Enhanced hooks read (the planes: the model's)
    else:
        pl, paint = NP2.planes(mem)
        pl_b = pl
    pages, at, where = {}, {}, {}
    page, off = PLANE_PAGE0, 0
    for g in sorted(pl):
        for o in sorted(pl[g]):
            p0, p1 = pl_b[g][0x00 if flip_lost else o]
            if swap:
                p0, p1 = p1, p0
            n = len(p0) * 2
            if off + n > 8192:
                page, off = page + 1, 0
            buf = pages.setdefault(page, bytearray(8192))
            if cim is not None:             # Enhanced: the code image, the same size as the two planes
                im = cim[g][0x00 if flip_lost else o]
                if swap:                    # the planes swapped: code bits 1 and 2 exchanged
                    im = bytes((v & 0x99) | (v & 0x22) << 1 | (v & 0x44) >> 1 for v in im)
                assert len(im) == n
                buf[off:off + n] = im
            else:
                buf[off:off + n] = p0 + p1
            where[(g, o)] = (page, off)
            off += n
    plt = bytearray(8192)
    for t in NP.FIG_TYPES:
        g, w, h = NP.graphic(mem, t)
        for k, o in enumerate((0x00, 0x40, 0x80, 0xC0)):
            if (g, o) in where:
                pg, ad = where[(g, o)]
                ad = (ad - 2) & 0xFFFF          # the hook adds the plot's offset from G, header included
                plt[(t * 4 + k) * 3:(t * 4 + k) * 3 + 3] = bytes([pg, ad & 255, ad >> 8])
    banks = {14: bytes(8192) + bytes(plt)}
    for pg, buf in pages.items():
        b = pg // 2
        cur = bytearray(banks.get(b, bytes(16384)))
        cur[(pg & 1) * 8192:(pg & 1) * 8192 + 8192] = buf
        banks[b] = bytes(cur)
    if max(banks) >= 23:
        raise ValueError('colour planes reach bank 23, the loading screen\'s')
    return banks, where, pl, paint


def game_mem(z80):
    from skoolkit.snapshot import Snapshot
    m = bytearray(65536)
    m[0x4000:] = bytes(Snapshot.get(z80).memory[0x4000:0x10000])
    return m


CMP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27]


def _profile_path(enhanced=False):
    """the hooks: the default build's profile, or the Enhanced build's (code images, asm/nightshade_hooks_enh.asm)"""
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + ('_enh' if enhanced else '') + '.json')


def load_profile(enhanced=False):
    return json.load(open(_profile_path(enhanced)))


def is_nightshade(snap):
    if getattr(snap, 'machine', '48K') != '48K' and getattr(snap, 'is128', False):
        return False
    try:
        mem = snap.memory
        return all(mem[a + i] == b for a, h in SITES_ORIG.items() for i, b in enumerate(bytes.fromhex(h)))
    except Exception:
        return False


def palette(colours=None):
    """256 sprite palette entries: offset k, nibble 1 = the game's bright colour k (or a painted one)."""
    pal = bytearray(256)
    for k in range(8):
        pal[16 * k + 1] = (colours or BRIGHT)[k]
    return bytes(pal)


CIM_BPT, CIM_T2B = 0x0B00, 0x0F00     # in the hook page (0x2B00, 0x2F00): the Enhanced build's code-image tables


def cim_tables():
    """BP_k (4 x 256): the T2 page for pixel pair k's two bits of a buffer byte; T2 (4 x 256): for those two bits, a
    code byte's shown nibbles: an odd (ink) code shows where its bit is set, an even (gap) code where it is clear."""
    t = bytearray(0x800)
    for k in range(4):
        for v in range(256):
            bp = (2 if v & (0x80 >> (2 * k)) else 0) + (1 if v & (0x40 >> (2 * k)) else 0)
            t[256 * k + v] = ((0x2000 + CIM_T2B) >> 8) + bp
    for bp in range(4):
        bh, bl = bp >> 1, bp & 1
        for c in range(256):
            hi, lo = c >> 4, c & 15
            t[0x400 + 256 * bp + c] = (hi if (hi & 1) == bh else 0) << 4 | (lo if (lo & 1) == bl else 0)
    return bytes(t)


def nib_table():
    """4 page-aligned tables of 256: NIB_k[v] = pixels 2k, 2k+1 of byte v as two nibbles (1 = ink)"""
    t = bytearray(1024)
    for v in range(256):
        for k in range(4):
            hi = 1 if v & (0x80 >> (2 * k)) else 0
            lo = 1 if v & (0x40 >> (2 * k)) else 0
            t[256 * k + v] = hi << 4 | lo
    return bytes(t)


class NightshadePatch:
    name = 'Nightshade figures -> hardware sprites (game plot kept; RAM stubs, Next page at slot 1 during hooks)'

    def __init__(self, prof=None, edit=None, colours=None, enhanced=False, game=None):
        self.prof = prof or load_profile(enhanced)
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.ram_code = bytearray.fromhex(h['ram'])
        self.page_code = bytearray.fromhex(h['page'])
        self.page2_code = bytearray.fromhex(h['page2'])
        st = bytearray.fromhex(h['setup'])
        pt = self.syms['pal_tab'] - 0xD000
        from . import nightshade_paint as NP
        st[pt:pt + 256] = NP.palette() if enhanced else palette(colours)
        self.setup = st
        self.enhanced = enhanced
        self.poff = NP.offsets()
        self.banks_extra = {14: bytes(16384)}
        if enhanced:
            if game is None:
                raise ValueError('the Enhanced set is made from the game file: game=')
            self.page_code[self.syms['enh_flag'] - PAGE_ORG] = 1
        self.colours = colours
        if edit:
            edit(self)
        self.stub_extra = bytes(self.setup)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.keep_printer_buffer = True     # the .nex loader writes 0x5B00-0x5BFF after bank 5: the stubs are put back
        self.tail_addr = TAIL_ADDR
        self.max_tail = 0x4F
        pg = bytearray(16384)
        pg[0:len(self.page_code)] = self.page_code
        c2 = self.syms['code2'] - PAGE_ORG
        pg[c2:c2 + len(self.page2_code)] = self.page2_code
        if game is not None:        # the planes are in both builds, so the Enhanced set changes only bytes of the same banks
            self.banks_extra, self.where, pl, self.paint = plane_banks(
                game_mem(game), getattr(self, 'swap_planes', False), getattr(self, 'flip_lost', False),
                enhanced, getattr(self, 'maps_lost', False))
            self.planes_by = {(g, o): v for g, d in pl.items() for o, v in d.items()}
        pg[NIB_AT:NIB_AT + 1024] = nib_table()
        if enhanced and 'cimrec' in self.syms:     # the Enhanced hooks' tables and code, in the figure scratch they never use
            pg[CIM_BPT:CIM_BPT + 0x800] = cim_tables()
            c3 = bytes.fromhex(h['page3'])
            pg[0x1300:0x1300 + len(c3)] = c3
        pg[POFF_AT:POFF_AT + 256] = self.poff
        self.page = bytes(pg[:8192])
        self.extra_banks = {H_BANK: bytes(pg)}
        self.extra_banks.update(self.banks_extra)
        self.sites = []
        for a, old in SITES_ORIG.items():
            if a == SITE_HB and getattr(self, 'skip_hb', False):
                continue
            self.sites.append((a, bytes.fromhex(old), bytes([0xCD]) + self.syms[SITE_SYM[a]].to_bytes(2, 'little')
                               + (b'\x00' if a == SITE_FIG else b'')))
        self.sites.append((RAM_ORG, bytes(len(self.ram_code)), bytes(self.ram_code)))

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Nightshade patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


def build(z80, out, edit=None, quiet=True, colours=None, enhanced=False):
    from . import z80tonex
    p = NightshadePatch(edit=edit, colours=colours, enhanced=enhanced, game=z80)
    z80tonex.convert(z80, out, tail_req=TAIL_ADDR, quiet=quiet, patch=p)
    return p


# ---------------------------------------------------------------------------------------------
# The patched machine
# ---------------------------------------------------------------------------------------------

class Patched:
    """The real patched game on a Python simulator: slot 1 paging, sprite ports, NEXTREG."""

    def __init__(self, patch, snap, frames, ins):
        from skoolkit.simutils import from_snapshot
        from .build import rom48
        from .dizzy6 import _rw_simulator
        from . import z80n
        self.patch = patch
        self.sim = from_snapshot(_rw_simulator(), snap, config={'int_active': 0})
        self.mem = self.sim.memory
        self.rom = bytes(rom48())
        self.mem[0:0x4000] = list(self.rom)
        self.pages = {}
        for b, data in patch.extra_banks.items():
            self.pages[2 * b], self.pages[2 * b + 1] = bytearray(data[:8192]), bytearray(data[8192:])
        self.map1 = self.map0 = 0xFF
        ram = bytearray(snap.memory[0x4000:0x10000]) if False else None
        for a, old, new in patch.sites:
            self.mem[a:a + len(new)] = list(new)
        self.nr = {0x15: 0, 0x07: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.sel_a = self.sel_p = 0
        self.apos = 0
        self.nr_sel = 0
        self.line = 0             # a model beam: one line further at every read of NR 0x1F
        self.pat_checked = True
        self.att_snap = None      # the screen at the first sprite attribute write of a blit hook
        self.ins = collections.deque(ins)
        self.c = collections.Counter()
        s = patch.syms
        self.entries = {s['s_fg']: 'figure hook', s['s_bl']: 'blit hook', s['s_hb']: 'hero box hook',
                        s['s_cls']: 'clear hook'}
        self.exits = {s['s_x'] + 4, s['s_xc'] + 4}
        self.inhook = False
        self.frames = frames
        self.fi = -1
        self.fc = self.next_frame()
        self.sim.set_tracer(self)
        z80n.install(self.sim, self.nextreg, strict=False)
        # setup: palette and sprite state as the stub leaves them (run the real setup code)
        self._run_setup()

    def _run_setup(self):
        R, mem = self.sim.registers, self.mem
        save = (list(R), bytes(mem[0xC000:0x10000]))
        mem[0xD000:0xD000 + len(self.patch.setup)] = list(self.patch.setup)
        mem[0xCFFE], mem[0xCFFF] = 0xFE, 0xCF          # return to 0xCFFE
        R[12], R[24] = 0xCFFE, 0xD000
        n = 0
        while R[24] != 0xCFFE and n < 200000:
            self.sim.opcodes[mem[R[24]]]()
            n += 1
        R[:] = save[0]
        mem[0xC000:0x10000] = list(save[1])
        self.c['setup ran'] += 1

    def nextreg(self, reg, val):
        if reg == 0x50:
            cur = self.map0
            if cur != 0xFF:
                self.pages[cur][:] = bytes(self.mem[0:0x2000])
            elif bytes(self.mem[0:0x2000]) != self.rom[0:0x2000]:
                self.c['ROM written!'] += 1
            self.mem[0:0x2000] = list(self.rom[0:0x2000]) if val == 0xFF else \
                list(self.pages.setdefault(val, bytearray(8192)))
            self.map0 = val
            if self.sim.registers[26]:
                self.c['slot 0 paged with interrupts on!'] += 1
        elif reg == 0x51:
            cur = self.map1
            if cur != 0xFF:
                self.pages[cur][:] = bytes(self.mem[0x2000:0x4000])
            elif bytes(self.mem[0x2000:0x4000]) != self.rom[0x2000:0x4000]:
                self.c['ROM written!'] += 1
            self.mem[0x2000:0x4000] = list(self.rom[0x2000:0x4000]) if val == 0xFF else \
                list(self.pages.setdefault(val, bytearray(8192)))
            self.map1 = val
        elif reg == 0x40:
            self.pal_i = val
        elif reg == 0x41:
            self.pal = getattr(self, 'pal', bytearray(256))
            self.pal[getattr(self, 'pal_i', 0)] = val
            self.pal_i = (getattr(self, 'pal_i', 0) + 1) & 255
        elif reg == 0x34:
            self.sel_a = val & 0x7F
        elif reg == 0x38:
            self.attr[self.sel_a][3] = val
        self.nr[reg] = val
        self.c['nr ok' if reg in (0x07, 0x15, 0x50, 0x51, 0x19, 0x1C, 0x34, 0x38, 0x40, 0x41, 0x43, 0x4B) else 'nr other!'] += 1

    def read_port(self, regs, port):
        if port == 0x253B and self.inhook:      # NEXTREG read from a hook: the beam (model), 50 Hz
            if self.nr_sel == 0x1E:
                return self.line >> 8
            if self.nr_sel == 0x1F:
                v = self.line & 255
                self.line = (self.line + 1) % 311
                return v
            if self.nr_sel == 0x05:
                return 0
            if self.nr_sel == 0x07:             # the CPU speed: bits 1-0 programmed (bits 5-4 as running)
                v = self.nr.get(0x07, 0) & 3
                return v | v << 4
            self.c['NEXTREG read other!'] += 1
            return 0
        if not self.ins:
            self.c['IN with no recorded value!'] += 1
            return 0xFF
        return self.ins.popleft()

    def write_port(self, regs, port, value, *x):
        p = port & 0xFF
        if port == 0x243B:
            self.nr_sel = value
        elif port == 0x303B:
            self.sel_a = value & 0x7F
            self.sel_p = ((value & 0x3F) << 8) | (0x80 if value & 0x80 else 0)
            self.apos = 0
            self.pat_checked = False
        elif p == 0x5B:
            if not self.pat_checked:            # a pattern upload: never into a pattern a shown sprite uses
                self.pat_checked = True
                n = (self.sel_p & 0x3FFF) >> 7
                if self.nr.get(0x15, 0) & 1 and any(a[3] & 0x80 and (a[3] & 0x3F) * 2 + (1 if a[4] & 0x40 else 0) == n
                                                    for a in self.attr):
                    self.c['pattern rewritten while a sprite shows it!'] += 1
            self.pat[self.sel_p & 0x3FFF] = value
            self.sel_p += 1
        elif p == 0x57:
            if self.att_snap is None:
                self.att_snap = bytes(self.mem[0x4000:0x5B00])
            self.attr[self.sel_a & 0x7F][self.apos] = value
            self.apos += 1
            if self.apos == 5 or (self.apos == 4 and not self.attr[self.sel_a & 0x7F][3] & 0x40):
                self.apos = 0
                self.sel_a = (self.sel_a + 1) & 0x7F
        elif p == 0x1F or p == 0x0B or p == 0x6B or p == 0x37 or p == 0xDF:
            self.c['OUT to a Next low-byte port'] += 1

    def next_frame(self):
        while True:
            self.fi += 1
            if self.fi >= len(self.frames):
                return 17000
            f = self.frames[self.fi]
            if f > 0:
                return f

    def run_to(self, target, limit=30000000):
        R, mem, ops = self.sim.registers, self.mem, self.sim.opcodes
        fc = self.fc
        entries, ints = self.entries, set(INTERIORS)
        n = 0
        while True:
            pc = R[24]
            if pc == target and not self.inhook:
                self.fc = fc
                return True
            if pc in entries:
                self.inhook = True
                self.spd_in = self.nr.get(0x07, 0)
                self.c[entries[pc]] += 1
                if R[26]:
                    self.c['interrupts on at a hook!'] += 1
            elif pc in ints:
                self.c['jump into a patched instruction!'] += 1
            op = mem[pc]
            if self.inhook:
                ops[op]()
                if pc in self.exits:
                    self.inhook = False
                    if self.nr.get(0x07, 0) != self.spd_in:
                        self.c['CPU speed not restored at a hook exit!'] += 1
            elif op == 0xDD or op == 0xFD:
                r0 = R[15]
                ops[op]()
                fc -= 2 - ((R[15] ^ r0) % 2)
            else:
                ops[op]()
                fc -= 2 if op == 0xCB or op == 0xED else 1
            n += 1
            if fc <= 0:
                R[25] = 0
                fc = self.next_frame()
                if R[26]:
                    if mem[pc] == 0x76:
                        R[24] = (R[24] + 1) % 65536
                    self.c['interrupts'] += 1
                    self.sim.accept_interrupt(R, mem, 0)
            if n > limit:
                self.fc = fc
                self.c['ran away!'] += 1
                return False

    def sprite_pixels(self):
        """{(x, y): colour index 0-7} of the visible sprites (screen pixels), later slots on top."""
        out = {}
        if not self.nr.get(0x15, 0) & 1:
            return out
        for a0, a1, a2, a3, a4 in self.attr:
            if not a3 & 0x80:
                continue
            x, y = (a0 | (a2 & 1) << 8) - 32, (a1 | (a4 & 1) << 8) - 32
            n = (a3 & 0x3F) * 2 + (1 if a4 & 0x40 else 0)
            if not a4 & 0x80:
                self.c['8-bit sprite!'] += 1
                continue
            base = n * 128
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + (k >> 1)]
                    nib = b >> 4 if not k & 1 else b & 15
                    if nib:
                        e = (a2 >> 4) * 16 + nib
                        out[(x + k, y + j)] = self.pal[e] if hasattr(self, 'pal') else e
        return out


# ---------------------------------------------------------------------------------------------
# The independent model: the original's plot loop into a zero buffer, in Python
# ---------------------------------------------------------------------------------------------

def figure_ink(mem, regs, data=None):
    """At 0xE45E in the original: (buffer offset, w, h, {offset: ink byte}) from running the game's own
    plot loop on a copy of memory, into a zeroed copy of the buffer at 0x4000."""
    from skoolkit.simulator import Simulator
    m = bytearray(mem[:65536])
    m[0x4000:0x4000 + 2760] = bytes(2760)
    bc = regs[2] * 256 + regs[3]
    de = regs[4] * 256 + regs[5]
    if data is not None:            # a colour plane: its bytes at 0x8000 in this copy, at the plot's offset into it
        pdata, off = data
        m[0x8000:0x8000 + len(pdata)] = pdata
        de = 0x8000 + off - 2       # off counts G's 2 header bytes
    w, h = m[FW], m[FH]
    scr = bc - BUF + 0x4000
    stop = 0x4FF0
    m[stop - 2], m[stop - 1] = stop & 255, stop >> 8
    m[SAVESP], m[SAVESP + 1] = (stop - 2) & 255, (stop - 2) >> 8
    sim = Simulator(m, {'PC': PLOOP, 'SP': de, 'A': h, 'BC': scr, 'HL': regs[6] * 256 + regs[7]})
    R, ops = sim.registers, sim.opcodes
    n = 0
    while R[24] != stop:
        ops[m[R[24]]]()
        n += 1
        if n > 200000:
            raise RuntimeError('figure_ink ran away')
    ink = {}
    for i in range(h):
        for j in range(w):
            ink[(i, j)] = m[scr + 24 * i + j]
    return bc - BUF, w, h, ink


def expected_sprites(figs, mem, enhanced=False, epal=None, poff=None):
    """{(x, y): RRRGGGBB} the sprites must show: each figure's ink AND the final buffer, later on top."""
    hero = (mem[HTAB + mem[HIDX]] & 7) if mem[HFLAG] else 7
    out = {}
    for o, w, h, ink, is_hero, ty, pl in figs:
        col = BRIGHT[hero if is_hero else 7]
        off = None
        if enhanced:
            off = poff[ty]
            if off == 0xFF:
                off = 8 + hero
        r0, c0 = divmod(o, 24)
        if c0 >= 22:                    # starts left of the window, in the hidden columns of the row below
            r0, c0 = r0 + 1, c0 - 24
        for (i, j), v in ink.items():
            if not 0 <= c0 + j < 22 or not 0 <= r0 + i < 112:
                continue
            bf = mem[BUF + o + 24 * i + j]
            vis = v & bf
            a = b = 0
            if enhanced:
                p0, p1 = pl[0][(i, j)], pl[1][(i, j)]
                shown = vis | ((p0 | p1) & ~(v | bf) & 255)
                a, b = p0 & shown, p1 & shown
            y = 127 - (r0 + i)
            for k in range(8):
                bit = 0x80 >> k
                code = (1 if vis & bit else 0) + (2 if a & bit else 0) + (4 if b & bit else 0)
                if code:
                    out[(56 + 8 * (c0 + j) + k, y)] = epal[16 * off + code] if enhanced else col
    return out


def _trace(path, pcs, on_pc, stop=None):
    """rzxplay with a hook at the given PCs: on_pc(pc, sim, frame index, fetch count left)."""
    import skoolkit.rzxplay as rp
    from types import SimpleNamespace
    from skoolkit import SkoolKitError
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    blocks = parse_rzx(path)
    while blocks and isinstance(blocks[-1].obj, Snapshot):
        blocks.pop()
    ctx = rp.RZXContext(None)
    for b in blocks:
        if isinstance(b.obj, rp.InputRecording):
            ctx.total_frames += len(b.obj.frames)
    if stop:
        ctx.total_frames = min(stop, ctx.total_frames)

    class Sink:
        def write(self, s):
            pass
    ctx.tracefile = Sink()
    pcs = frozenset(pcs)

    def hook(tf, context, fc, pc):
        if pc in pcs:
            on_pc(pc, context.simulator, context.simulator.tracer.frame_index, fc)
    old = rp.trace_exec
    rp.trace_exec = hook
    err = None
    try:
        opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=stop or 0, force=False)
        while blocks:
            rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
            if ctx.stop:
                break
    except SkoolKitError as e:
        err = str(e)
    finally:
        rp.trace_exec = old
    return ctx.frame_count, err


def _masks(patch, sp):
    """Address ranges the patch owns: the tail and stubs, the dead stack below SP."""
    return [(0x5B00, 0x5B80), (sp - 64, sp)] + [(a, a + len(new)) for a, old, new in patch.sites if a != RAM_ORG]


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shots=None, model=True, speed=0):
    """-> (Counter, examples); failure keys end in '!'."""
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    segs = RZ.read_segments(rzx_path)
    if len(segs) != 1:
        raise ValueError('expects one segment (record --script), found %d' % len(segs))
    snap, rec = segs[0][0], segs[0][1]
    ins = [v for f in rec.frames for v in rec.data[f.start:f.end]]
    p = Patched(patch, snap, [f.fetch_counter for f in rec.frames], ins)
    p.nr[0x07] = speed          # the clock matrix: the game running at 3.5, 7, 14 or 28 MHz when each hook is entered
    st = {'figs': [], 'hero_before': None}
    from . import nightshade_paint as NP
    epal, epoff = NP.palette(), NP.offsets()     # the painter's own tables, not the build's bytes
    after = {SITE_HB: SITE_HB + 3}

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append(info)

    def compare(pc, R, mem, skip_hero):
        P = p.sim.registers
        diff = [i for i in CMP if R[i] != P[i]]
        if diff:
            fail('registers differ', (c['events'], hex(pc), diff, [R[i] for i in diff], [P[i] for i in diff]))
        masks = _masks(patch, R[12])
        lo = 0x4000
        bad = []
        for a0, a1 in sorted(masks) + [(0x10000, 0x10000)]:
            if bytes(mem[lo:a0]) != bytes(p.mem[lo:a0]):
                bad += [a for a in range(lo, a0) if mem[a] != p.mem[a]]
            lo = max(lo, a1)
        if skip_hero:
            hb = st['hero_before']
            for a in list(bad):
                if a in HERO_SCREEN:
                    bad.remove(a)
                elif a in HERO_CELLS:
                    bad.remove(a)
                    if pc == SITE_HB + 3 and hb is not None and p.mem[a] != hb[a]:
                        fail('hero cell not the scenery colour', (hex(pc), hex(a)))
        if bad:
            fail('memory differs', (c['events'], hex(pc), len(bad), [hex(a) for a in bad[:8]]))

    def on_pc(pc, sim, fi, fc):
        R, mem = sim.registers, sim.memory
        if pc == SITE_HB + 3 and st.get('in_hb'):
            st['in_hb'] = False
            if not p.run_to(pc):
                fail('patched run lost', (hex(pc),))
                return
            p.fi, p.fc = fi, fc
            compare(pc, R, mem, True)
            return
        if pc not in SITES_ORIG:
            return
        if not p.run_to(pc):
            fail('patched run lost', (hex(pc), hex(p.sim.registers[24])))
            return
        c['events'] += 1
        p.fi, p.fc = fi, fc
        compare(pc, R, mem, pc != SITE_HB or True)
        if R[26]:
            fail('interrupts on at a site', (hex(pc),))
        if pc == SITE_FIG:
            c['figure plots'] += 1
            ix = R[8] * 256 + R[9]
            if model:
                o, w, h, ink = figure_ink(mem, R)
                pl = None
                if patch.enhanced:
                    t = mem[ix]
                    g = mem[GTAB + 2 * t] | mem[GTAB + 2 * t + 1] << 8
                    ori = mem[g] & 0xC0
                    de = R[4] * 256 + R[5]
                    if (g, ori) in patch.planes_by:
                        pl = tuple(figure_ink(mem, R, (patch.planes_by[(g, ori)][k], de - g))[3] for k in (0, 1))
                    else:
                        pl = ({q: 0 for q in ink}, {q: 0 for q in ink})
                    c['figures painted' if (g, ori) in patch.planes_by else 'figures without planes'] += 1
                st['figs'].append((o, w, h, ink, ix in HERO_IX, mem[ix], pl))
                top = o + 2 + 24 * (h - 1) + w       # the scratch the plot reaches, from 2 bytes below it
                c['scratch reach max'] = max(c['scratch reach max'], top)
                if top + 64 > SCR_ROOM:
                    fail('scratch plot near the second code block', (hex(o), w, h))
            p.run_to(pc + 4)        # the hook returns to the NOP; the original's next is pc + 4
        elif pc == SITE_HB:
            st['hero_before'] = {a: mem[a] for a in HERO_CELLS}
            st['in_hb'] = True
            c['hero box calls'] += 1
        elif pc == SITE_CLS:
            p.run_to(0xE5A8)
            c['clears'] += 1
            if p.nr.get(0x15, 0) & 1:
                fail('sprites on after a clear', (hex(pc),))
            p.sim.registers[12] += 0  # the hook's JP leaves the CALL's return as the original
        elif pc == SITE_BL:
            st['in_bl'] = True
            p.att_snap = None
        if progress and c['events'] % 2000 == 0:
            progress(c)

    def at_bl_end(pc):
        st['in_bl'] = False
        if not p.run_to(pc):
            fail('patched run lost', (hex(pc),))
            return
        R, mem = tr['sim'].registers, tr['sim'].memory
        p.fi, p.fc = tr['fi'], tr['fc']
        compare(pc, R, mem, True)
        if True:
            if p.att_snap is not None and p.att_snap != bytes(p.mem[0x4000:0x5B00]):
                fail('sprites switched before the ULA picture was complete', (c['blits'],))
            p.att_snap = None
            hb = st['hero_before']
            if hb is not None and any(p.mem[a] != hb[a] for a in HERO_CELLS):
                fail('hero cell not the scenery colour', (c['blits'],))
            c['blits'] += 1
            got = p.sprite_pixels()
            if model:
                want = expected_sprites(st['figs'], mem, patch.enhanced, epal, epoff)
                if got != want:
                    miss = [k for k in want if k not in got]
                    extra = [k for k in got if k not in want]
                    wrong = [k for k in want if k in got and got[k] != want[k]]
                    fail('sprite picture differs', (c['blits'], len(want), len(miss), len(extra), len(wrong),
                                                    miss[:3], extra[:3], wrong[:3]))
                c['sprite pixels'] += len(want)
                c['hero sprite pixels in a colour other than white'] += sum(1 for v in want.values() if v != 0xFF)
            c['sprites shown'] += sum(1 for a in p.attr if a[3] & 0x80)
            if shots is not None:
                shots(c['blits'], mem, p, st['figs'])
            st['figs'] = []

    tr = {}

    def on_pc2(pc, sim, fi, fc):
        if pc == BL_END:
            if st.get('in_bl'):
                tr.update(sim=sim, fi=fi, fc=fc)
                at_bl_end(pc)
            return
        on_pc(pc, sim, fi, fc)

    frames, err = _trace(rzx_path, set(SITES_ORIG) | {SITE_HB + 3, BL_END}, on_pc2, stop=stop)
    if err:
        c['recording desynced!'] += 1
        ex['recording desynced'].append(err)
    c['frames'] = frames
    s = patch.syms
    pg = p.pages.get(H_PAGE) if p.map1 != H_PAGE else bytearray(p.mem[0x2000:0x4000])
    c['figure records full (left on the ULA colours)'] = pg[s['nfull'] - PAGE_ORG] | pg[s['nfull'] - PAGE_ORG + 1] << 8
    c['tiles past the 64 of a frame (not shown)'] = pg[s['ntrunc'] - PAGE_ORG] | pg[s['ntrunc'] - PAGE_ORG + 1] << 8
    c.update(p.c)
    return c, dict(ex)


def negative_patches():
    """Broken builds: each must be DETECTED on the real recording. -> [(name, edit, enhanced)]"""
    def at3(p, pat, k, val):     # in the Enhanced build's code-image block (page3, written into the hook page)
        h = p.prof['hooks']
        c3 = bytearray.fromhex(h['page3'])
        i = c3.find(bytes.fromhex(pat))
        assert i >= 0 and c3.count(bytes.fromhex(pat)) == 1, pat
        c3[i + k] = val
        h['page3'] = c3.hex()

    def at(p, pat, k, val):
        code = p.page2_code if p.page2_code.count(bytes.fromhex(pat)) else p.page_code
        i = code.find(bytes.fromhex(pat))
        assert i >= 0 and p.page_code.count(bytes.fromhex(pat)) + p.page2_code.count(bytes.fromhex(pat)) == 1, pat
        code[i + k] = val

    def no_and(p):          # sprites show the whole ink, not what later plots left (the default row: AND (HL) -> OR (HL))
        at(p, 'a64f3a', 0, 0xB6)
    def y_off(p):           # one row low (LD A,160 / SUB L)
        at(p, '3ea091', 1, 161)
    def white_hero(p):      # the hero's colour lost (LD E,0xFF)
        at(p, '1eff', 1, 7)
    def paint_box(p):       # the hero box painted again: its site left as the original CALL
        p.skip_hb = True
    def no_hide(p):         # a clear leaves the sprites on (NEXTREG 0x15,0 -> 1)
        at(p, 'ed911500', 3, 1)
    def col22(p):           # the hidden margin columns shown (vis: ADD A,(HL) / CP 22)
        at(p, '86fe16', 2, 24)
    def r_off(p):           # R one count off after the figure hook (the game's random numbers)
        at(p, '3e73', 1, 0x74)
    def r_blit(p):          # R one count off after the blits (LD A,38 at the blit hook's entry)
        at(p, '3e26cd', 1, 39)
    def early(p):           # the switch before the blits: CALL wait -> CALL burst (the old flicker)
        w, b = p.syms['wait'], p.syms['burst']
        at(p, 'cd' + w.to_bytes(2, 'little').hex(), 1, b & 255)
    def one_half(p):        # one pattern buffer: the half not flipped (XOR 64 -> XOR 0)
        at(p, 'ee40', 1, 0)
    def enh_pal(p):         # Enhanced: one palette entry wrong (the horned demon's body)
        pt = p.syms['pal_tab'] - 0xD000
        p.setup[pt + 16 * 11 + 1] = 0x1F
    def enh_hero(p):        # Enhanced: the hero's health colour lost (ADD A,8 -> ADD A,0)
        at(p, 'c608', 1, 0)
    def enh_orient(p):      # Enhanced: every orientation given the stored one's planes
        p.flip_lost = True
    def enh_swap(p):        # Enhanced: the two planes swapped
        p.swap_planes = True
    def clock35(p):         # every exit forces 3.5 MHz (LD A,(vspd) / NEXTREG 0x07,A -> NEXTREG 0x07,0 / JR $+2): run at 28 MHz
        for code in (p.page_code, p.page2_code):
            i = 0
            while True:
                i = code.find(bytes.fromhex('3a'), i)
                if i < 0:
                    break
                if code[i + 3:i + 6] == bytes.fromhex('ed9207'):
                    code[i:i + 6] = bytes.fromhex('ed9107001800')    # NEXTREG 0x07,0 / JR $+2: 3 M1 as before
                i += 1

    def cim_shift(p):       # Enhanced code images: the figure's 2-pixel shift ignored (LD A,(IX+14) / AND 6 -> AND 0)
        at3(p, 'dd7e0ee606', 4, 0)

    def enh_maps(p):        # Enhanced: the hero's part maps dropped (legs and arms in the tunic colour, no belt)
        p.maps_lost = True

    def enh_group(p):       # Enhanced: the horned demon in the dome colours
        g = bytearray(p.poff)
        for t in range(0x78, 0x7C):
            g[t] = g[0x48]
        p.poff = bytes(g)
    return [('sprites not ANDed with the final buffer', no_and, False), ('sprites one row low', y_off, False),
            ('hero colour lost', white_hero, False), ('hero box painted', paint_box, False),
            ('sprites left on at a clear', no_hide, False), ('margin columns shown', col22, False),
            ('R off by one after a figure', r_off, False),
            ('R off by one after the blits', r_blit, False), ('sprites switched before the blits', early, False), ('one pattern buffer', one_half, False),
            ('Enhanced palette entry wrong', enh_pal, True), ('Enhanced hero health colour lost', enh_hero, True),
            ('Enhanced orientation ignored', enh_orient, True), ('Enhanced planes swapped', enh_swap, True),
            ('Enhanced horned demon in the dome colours', enh_group, True),
            ('Enhanced hero part maps dropped', enh_maps, True),
            ('every hook exit forces 3.5 MHz (verify at speed 3)', clock35, False),
            ('Enhanced code image shift ignored', cim_shift, True)]


# ---------------------------------------------------------------------------------------------
# Loading screen (runs/nightshade/loading/mk.py, round 2): the tape's screen shown from bank 5 by a stub in
# bank 23 (asm: MODULE ldscr), then bank 5's own bytes put back. Applied to the built .nex, every other byte kept.
# ---------------------------------------------------------------------------------------------

SCREEN_MD5 = '758792b8bacf59373fe58d6b709c9e48'    # the 6,912-byte block of all three Ultimate tapes
L_BANK, L_PIC, L_FINAL = 23, 0x0200, 0x3FD0       # entry bank; offsets of the screen copy and the exit


def tape_screen(path):
    """The 6,912-byte screen of a .tap (flag 255 block of 6,914 bytes, parity checked) or a .scr; else None."""
    import hashlib
    d = open(path, 'rb').read()
    cands = [d] if len(d) == 6912 else []
    i = 0
    while path.lower().endswith('.tap') and i + 2 <= len(d):
        n = d[i] | d[i + 1] << 8
        b = d[i + 2:i + 2 + n]
        i += 2 + n
        x = 0
        for v in b:
            x ^= v
        if n == 6914 and b[0] == 0xFF and x == 0:
            cands.append(b[1:-1])
    return next((s for s in cands if hashlib.md5(s).hexdigest() == SCREEN_MD5), None)


def find_screen(folder):
    """-> (file, screen) of the first .tap / .scr in folder that holds the loading screen, or (None, None)."""
    import glob
    for f in sorted(glob.glob(os.path.join(folder, '*'))):
        if f.lower().endswith(('.tap', '.scr')):
            s = tape_screen(f)
            if s is not None:
                return f, s
    return None, None


def add_loading(nex, screen, prof=None):
    """nex bytes -> nex bytes with the loading screen (mk.py exactly): bank 5's screen area = the tape's
    screen; new bank 23 = entry bank: stub code, bank 5's own screen bytes at 0x0200, the exit at 0x3FD0."""
    h = (prof or load_profile())['hooks']
    code, fin = bytes.fromhex(h['lstub']), bytes.fromhex(h['lfinal'])
    hd = bytearray(nex[:512])
    if hd[18 + L_BANK] or hd[139] != 10 or any(hd[18 + k] for k in range(L_BANK, 112)) or len(screen) != 6912:
        raise ValueError('loading screen: bank 23 or above in use, or entry bank not 10')
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
    pages[46], pages[47] = bytearray(b23[:8192]), bytearray(b23[8192:])
    pages[10] = bytearray(nex[512:512 + 8192])           # bank 5 = first bank in the file
    st = {'mmu': [0xFF, 0xFF, 10, 11, 4, 5, 46, 47], 'sel': 0x55, 'n': 0, 'shown': False, 'key': False}
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


# ---------------------------------------------------------------------------------------------
# auto (ENGINE_CONTRACT): plain, default and Enhanced builds, the replays and the negative controls
# ---------------------------------------------------------------------------------------------

NEG_STOP = 1500             # frames of the first recording each negative control replays (the margin one: all)


def _job(z80, rzx, enhanced, neg, stop):
    """One replay in a worker process -> (counter, examples as text)."""
    edit = negative_patches()[neg][1] if neg is not None else None
    p = NightshadePatch(edit=edit, enhanced=enhanced, game=z80)
    c, ex = verify(p, rzx, stop=stop)
    return dict(c), {k: str(v[:3])[:300] for k, v in ex.items()}


def unit_tests(patch=None, states=None, neg=None, z80=None, rzx=None, jobs=None):
    """Nightshade's negative controls (negative_patches), each a broken build replayed on the recording
    (NEG_STOP frames; the margin columns one over the whole recording) -> Counter; failures end in '!'.
    The paths the recordings do not reach go through the same hooks (games/nightshade.md "Open")."""
    import concurrent.futures as cf
    u = collections.Counter()
    negs = negative_patches()
    with cf.ProcessPoolExecutor(jobs or min(16, os.cpu_count() or 4)) as ex:
        fut = {k: ex.submit(_job, z80, rzx, negs[k][2], k, None if negs[k][0] == 'margin columns shown' else NEG_STOP)
               for k in range(len(negs))}
        for k, f in fut.items():
            c, _ = f.result()
            hit = any(x.endswith('!') for x in c)
            u['negative control detected' if hit else 'negative control NOT DETECTED!'] += 1
            u['neg %02d %s: %s' % (k, negs[k][0], 'DETECTED' if hit else 'NOT DETECTED')] = 1
    return u


def auto(a, z80, name, out, say):
    import hashlib
    import concurrent.futures as cf
    import tempfile
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    md5 = lambda b: hashlib.md5(b).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : nightshade (Filmation II: figure plot 0xE45E, blits 0xE200, clear 0xE59D, hero box 0xBEC4 '
        '-> 4-bit sprites over the kept plot; Enhanced painted by parts)')
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(open(plain, 'rb').read()),
                                         'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    ok = not bad
    scr_file, scr = find_screen(os.path.dirname(os.path.abspath(z80)))
    say('Loading   : %s' % ('screen from %s (md5 %s)' % (os.path.basename(scr_file), SCREEN_MD5[:8]) if scr else
                            'no tape with the loading screen beside the snapshot: built without it (the approved '
                            'build has it; put the [a][a].tap beside the .z80)'))
    tmp = tempfile.mkdtemp(prefix='ns_')
    for label, enh, suffix in (('Sprites', False, '_sprites'), ('Enhanced', True, '_enhanced')):
        p = NightshadePatch(enhanced=enh, game=z80)
        base = os.path.join(tmp, name + suffix + '.nex')
        conv = zt.convert(z80, base, TAIL_ADDR, True, quiet=True, patch=p)
        tail = (conv[1], conv[1] + len(conv[2]))
        b1 = check(base, z80, p, tail) + check(base, z80, p, tail, nexload=True)
        dst = os.path.join(out, name + suffix + '.nex')
        nb = open(base, 'rb').read()
        b2 = []
        if scr:
            wrapped = add_loading(nb, scr)
            b2 = loading_check(nb, wrapped, scr) + loading_check(nb, wrapped, scr, frames_key=(40, 60))
            open(dst, 'wb').write(wrapped)
        else:
            open(dst, 'wb').write(nb)
        ok = ok and not b1 and not b2
        say('%-10s: %s  %s  boot %s (with and without NEXLOAD)%s' % (
            label, os.path.basename(dst), md5(open(dst, 'rb').read()), 'OK' if not b1 else 'MISMATCH %s' % str(b1[:3])[:200],
            '' if not scr else '; base %s, loading stub %s' % (md5(nb)[:8], 'OK' if not b2 else 'MISMATCH %s' % str(b2[:3])[:200])))
    rzxs = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        if sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS)) > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            r = s2
        rzxs.append(r)
    stop = getattr(a, 'quick', None)
    if rzxs:
        with cf.ProcessPoolExecutor(min(2 * len(rzxs), os.cpu_count() or 4)) as ex:
            fut = [(r, enh, ex.submit(_job, z80, r, enh, None, stop)) for r in rzxs for enh in (False, True)]
            for r, enh, f in fut:
                c, exs = f.result()
                fails = {k: v for k, v in c.items() if k.endswith('!')}
                ok = ok and not fails
                say('Verify    : %s %s  %d frames, figure hook %d, blits %d, hero box %d, clear %d, figures painted %d, '
                    '%d sprite pixels -> %s' % (os.path.basename(r), 'Enhanced' if enh else 'default', c.get('frames', 0),
                                               c.get('figure hook', 0), c.get('blit hook', 0), c.get('hero box hook', 0),
                                               c.get('clear hook', 0), c.get('figures painted', 0), c.get('sprite pixels', 0),
                                               'IDENTICAL' if not fails else 'FAILED %s' % fails))
                for k, v in exs.items():
                    say('            %s: %s' % (k, v))
        u = unit_tests(z80=z80, rzx=rzxs[0])
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : negative controls on %s (%d frames each, the margin one all): %d/%d -> %s' % (
            os.path.basename(rzxs[0]), NEG_STOP, u['negative control detected'],
            u['negative control detected'] + u['negative control NOT DETECTED!'], 'PASS' if not uf else 'FAIL %s' % uf))
        for k in sorted(x for x in u if x.startswith('neg ')):
            say('            %s' % k[4:])
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
