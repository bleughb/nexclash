"""Altered Beast (Activision 1989, 128K) engine 'altered_beast'. Additive module: reachable only through
is_altered_beast(). Game facts and decisions: games/altered_beast.md.

  Snapshot: title menu, PC in RAM, 7FFD = 0 (ROM 0, never run or read), IM 2. Level 1 only is in memory;
  the level-one reload at game over restores the title snapshot. Later levels still need the original tape.
  Main loop: HALT, 0xAE40 CALL 0x60EB blit buffer -> screen, 0xAE43 CALL 0x6DE4 buffer := clean copy, logic,
  plots into the buffer. Figures are CELL aligned: a stream of records, flag 0 = empty (1 byte), else flag +
  8 graphics bytes + attribute. Masked plot: (buffer AND table 0x6900[g]) OR g; mirrored through table 0x6A00.
  Build: the blit reads the clean copy, the buffer stays exactly the original's, sprites come from a log.
"""
import collections
import hashlib
import json
import os

RECORD = 'altered_beast'
P_NORM, P_MIR, P_OP, P_BLIT = 0xD036, 0xCEEB, 0xD1D8, 0xAE40
P_FXA, P_FXB = 0xAFED, 0xB046    # end of the level: routines that write attributes into the buffer
FX_ROWS, FX_COLS = (0, 17), (21, 29)
BLIT, BLIT_RET = 0x60EB, 0xAE43
PIX, ATT, CPIX, CATT = 23332, 23334, 23954, 23956
PTR, W_, H_, YC, LIM, FLG = 23296, 23940, 23939, 23938, 53316, 23325
MASKT, REVT = 0x6900, 0x6A00
SITES_ORIG = {P_NORM: '3a835d', P_MIR: '3a835d', P_OP: 'cd10d2', P_BLIT: 'cdeb60', P_FXA: '2a265b', P_FXB: '2a265b'}
SITE_SYM = {P_NORM: ('c3', 'e_pn'), P_MIR: ('c3', 'e_pm'), P_OP: ('cd', 'e_op'), P_BLIT: ('cd', 'e_bl'),
            P_FXA: ('c3', 'e_fxa'), P_FXB: ('c3', 'e_fxb')}
STOP = {P_NORM: 0xD039, P_MIR: 0xCEEE, P_OP: 0xD1DB, P_BLIT: BLIT_RET, P_FXA: 0xAFF0, P_FXB: 0xB049}
INTERIOR = {a + k: a for a in SITES_ORIG for k in (1, 2)}
# Next interrupt fix (every build, plain too). The game's three interrupt handlers open EI; EXX; EX AF,AF', so a second
# interrupt is accepted after EXX: 37 T after the acknowledge starts. A 128K's /INT lasts 36 T and has ended; the Next
# core's lasts longer (measured on the Tang board, 2026-11-21: re-entered at 38 T, not at 42), so every interrupt ran
# the handler twice, a frame overran and an interrupt arrived with bank 1 paged for the music, whose IM 2 table is zero:
# JP 0 (crash on the board at the menu's first change, ~8 s). EI two instructions later (45 T) is the fix; EXX and
# EX AF,AF' do not read or change the interrupt state, so the handler is otherwise the same (int_fix_check).
INT_SITES = [(0x5F80, 'fbd908', 'd908fb'), (0x88CC, 'fbd908', 'd908fb'), (0x88FF, 'fbd908', 'd908fb')]
SCREEN = (0x4000, 0x5B00)
TAIL_ADDR = 0x5DD3               # dead stack below the snapshot's SP: never read before written (scan, game.md)
HPG, GP4, GP5, ALT_PAGE, STORE, NSTORE = 26, 4, 5, 24, 28, 40
ROM_LO = 0x2000
CLIP = (16, 239, 0, 151)         # sprite clip window = the play area the blit shows in full
V_N, V_PREV, V_NS, V_COL, V_NFREE, V_DROP, V_TEAR = 0, 1, 2, 3, 7, 8, 9
LOG, CE, FREE = 0x100, 0x300, 0xB00
MAXLOG, MAXSPR, NCE = 32, 128, 32
RUNTIME = (0x000, 0x1100)
HSTK = 0x1F00
CMP = list(range(0, 15)) + list(range(16, 25)) + [26, 27, 28]
# sprite palette: index 0 transparent, 1-7 colours, 8 black, 9-15 bright colours
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
# entries no figure's cell colours use (blue, bright blue, bright green, bright cyan: none in level 1): a colour map's
# 'palette' may change only these, so a figure the map does not paint keeps the game's colours
PAL_FREE = (1, 9, 12, 13)
BANK_NAMES = ('Original', 'Player_two', 'Zombies', 'Wolves', 'Wolf_flash', 'Sorcerer', 'Boss', 'Effects')
TYPE_TABLE, PAGE_TABLE = 0x1100, 0x1200


def figure_bank(ty, mode):
    if mode == 2:
        return 1
    if mode == 1:
        return 4
    ty &= 0x7F
    if ty in (2, 3):
        return 2
    if ty == 6:
        return 3
    if ty == 7:
        return 5
    if 9 <= ty <= 13:
        return 6
    if ty in (8, 19):
        return 7
    return 0


def paint_key(bank, addr):
    return '%d:%04X' % (bank, addr)


CBLACK = 8
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'altered_beast_colours.json')
ENHANCED = os.path.join(_HERE, '..', 'docs', 'profiles', 'altered_beast_enhanced.json')   # the Enhanced set's map
SIG = (0xCF0B, bytes.fromhex('0608c50669'))
SIG2 = (0xAE3F, bytes.fromhex('76cdeb60cde46d'))


def is_altered_beast(snap):
    if snap.machine == '48K':
        return False
    return all(bytes(snap.memory[a:a + len(s)]) == s for a, s in (SIG, SIG2))


def cidx(c, bright):
    return CBLACK if c == 0 else c + 8 * bright


def attr_colours(a):
    b = (a >> 6) & 1
    return cidx(a & 7, b), cidx((a >> 3) & 7, b)


def rgb(i):
    from . import coloursheet as cs
    return cs.palette_rgb(PALETTE)[i]


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'altered_beast.json')


def load_profile():
    return json.load(open(_profile_path()))


def pixel_tables():
    """TI0, TI1, TP0, TP1: index graphic nibble << 4 | mask nibble -> pattern-byte AND masks."""
    t = [bytearray(256) for _ in range(4)]
    for i in range(256):
        g, m = i >> 4, i & 15
        ink, pap = [], []
        for b in range(4):
            bit = 8 >> b
            ink.append(15 if g & bit else 0)
            pap.append(15 if not g & bit and not m & bit else 0)
        t[0][i] = ink[0] << 4 | ink[1]
        t[1][i] = ink[2] << 4 | ink[3]
        t[2][i] = pap[0] << 4 | pap[1]
        t[3][i] = pap[2] << 4 | pap[3]
    return b''.join(bytes(x) for x in t)


# ---------------------------------------------------------------------------------------------
# Colour map: key = graphics byte address (%04X) -> [check (the byte), kind 1, 8 nibbles (, clear mask)]
# ---------------------------------------------------------------------------------------------

NOTE = ('Altered Beast figure colours: key = address of a graphics byte (8 pixels) -> [the byte (check), '
        'kind 1, 8 nibbles (0 = default colour) (, transparent mask)]')


def save_colours(ent, path=COLOURS):
    from . import coloursheet as cs
    cs.save(ent, path, NOTE)


def load_colours(path=COLOURS):
    """coloursheet.load plus the file's top-level sprite 'palette' (RECOLOUR 'palette')."""
    from . import coloursheet as cs
    m = cs.load(path)
    pal = json.load(open(path)).get('palette') if os.path.exists(path) else None
    if pal is not None:
        m['palette'] = pal
    return m


def set_palette(colours):
    """One legacy palette or eight Enhanced banks. Bank zero keeps its original protected colours."""
    p = (colours or {}).get('palette')
    if p is None:
        return list(PALETTE)
    p = list(p)
    if len(p) not in (16, 16 * len(BANK_NAMES)) or any(not isinstance(v, int) or not 0 <= v <= 255 for v in p):
        raise ValueError('expected a 16 or 128 byte sprite palette')
    if any(p[i] or p[i + 8] for i in range(0, len(p), 16)):
        raise ValueError('each bank reserves index 0 for transparency and 8 for black')
    bad = [i for i in range(16) if p[i] != PALETTE[i] and i not in PAL_FREE]
    if bad:
        raise ValueError('a colour map palette may change only entries %s, not %s' % (list(PAL_FREE), bad))
    return p


def entries(colours):
    """The map's colour entries, without its palette."""
    return {k: v for k, v in (colours or {}).items() if k != 'palette'}


def loaded_palette(nrlog):
    """All sprite palette entries the setup loads: NextReg 0x41 writes after 0x43 = 0x20 and 0x40 = 0."""
    out, on = [], False
    for i, (reg, val) in enumerate(nrlog):
        if reg == 0x40 and val == 0 and i and nrlog[i - 1] == (0x43, 0x20):
            out, on = [], True
        elif on and reg == 0x41:
            out.append(val)
        elif on and reg in (0x40, 0x43):
            on = False
    return out


def load_colours_build():
    from . import recolour as rc
    p = rc.build_colours_path(COLOURS)
    return load_colours(p) if p and os.path.exists(p) else {}


def store_pages(colours, pages=NSTORE):
    """Colour map -> NSTORE pages: 8 bytes per address 0x6000-0xFFFF: [1, check, 4 nibble bytes, clear mask, 0]."""
    st = bytearray(pages * 8192)
    for k, e in (colours or {}).items():
        a = int(k, 16)
        if not 0x6000 <= a <= 0xFFFF:
            continue
        i = a - 0x6000
        nib = e[2]
        st[8 * i:8 * i + 8] = bytes([1, e[0] & 255] + [nib[2 * n] << 4 | nib[2 * n + 1] for n in range(4)] +
                                    [e[3] if len(e) > 3 else 0, 0])
    return bytes(st)


def banked_store(colours, hpage):
    """Pack only occupied 1 KiB graphics ranges into the existing 8 KiB colour pages."""
    hpage[TYPE_TABLE:TYPE_TABLE + 256] = bytes(figure_bank(t, 0) for t in range(256))
    pages = {}
    for key, entry in colours.items():
        group, addr = key.split(':')
        bank, a = int(group), int(addr, 16)
        if not (0 <= bank < len(BANK_NAMES) and 0x6000 <= a <= 0xFFFF):
            raise ValueError('invalid banked sprite key %s' % key)
        segment, offset = divmod(a - 0x6000, 1024)
        pages.setdefault((bank, segment), {})['%04X' % (0x6000 + offset)] = entry
    if len(pages) > NSTORE:
        raise ValueError('painting needs %d colour pages, capacity %d' % (len(pages), NSTORE))
    st = bytearray(NSTORE * 8192)
    for n, ((bank, segment), page) in enumerate(sorted(pages.items())):
        hpage[PAGE_TABLE + bank * 256 + segment] = STORE + n
        packed = bytearray(store_pages(page, 1))
        if bank == 1:
            for key, entry in page.items():
                clear = entry[3] if len(entry) > 3 else 0
                pixels = [0 if clear & (128 >> i) else v for i, v in enumerate(entry[2])]
                if all(v or clear & (128 >> i) for i, v in enumerate(pixels)):
                    offset = (int(key, 16) - 0x6000) * 8
                    packed[offset] = 2
                    packed[offset + 2:offset + 6] = bytes((a << 4) | b for a, b in zip(pixels[::2], pixels[1::2]))
        st[n * 8192:(n + 1) * 8192] = packed
    return st


def hook_page(colours=None):
    p = bytearray(8192)
    for i in range(128):
        p[FREE + i] = i
    p[V_NFREE] = 128
    p[V_COL] = 1 if colours else 0
    return bytes(p)


RELOAD = 0x75AA
RELOAD_ORIGINAL = bytes.fromhex('2114ac2284ff3e0732b9ffcd')
TICK = 0x75B6
PRESENT_LINE = 257
SMOOTH_CLIP = (16, 231, 0, 151)


def restart_setup(base, hooks, overlay=b''):
    # The entry bank is already in every NEX. Save the live pages on cold
    # boot, after the NXC loader has applied its colour and trainer choices.
    if len(base) > 0x200:
        raise ValueError('palette setup overlaps restart')
    startup = base.ljust(0x200, b'\0') + bytes.fromhex(hooks['restart'])
    return startup.ljust(0x400, b'\0') + (overlay or b'\xc9')


def smooth_edits(hooks, banked):
    prefix = 'enhanced.' if banked else ''
    def sym(name):
        return int(hooks['syms'][prefix + name], 16)
    def word(v):
        return v.to_bytes(2, 'little')
    smooth = bytes.fromhex(hooks['banked_smooth' if banked else 'smooth'])
    # Existing addresses and the register block survive installation. Split
    # preparation from upload, and forbid early eviction of visible patterns.
    return [
        (sym('smooth_bl'), None, smooth),
        (sym('pixout'), bytes.fromhex('0e00cd'), b'\xc3' + word(sym('smooth_paint'))),
        (sym('commit.upl'), b'\xaf', b'\xc9'),
        (sym('commit_call') + 1, word(sym('commit')), word(sym('smooth_upload'))),
        (sym('idle') + 6, b'\x16', b'\xc9'),
        (P_BLIT - 1, b'\x76', b'\x00'),
        (P_BLIT, b'\xcd' + word(sym('e_bl')), b'\xcd' + word(sym('smooth_bl'))),
        (0x5F80, bytes.fromhex('d908fb'), b'\xc3' + word(sym('smooth_irq'))),
        (TICK, b'\x23', b'\0'),
        *((a, bytes.fromhex('cda364'), b'\xcd' + word(sym('gauge_delay'))) for a in (0xB6D2, 0xB6E1)),
    ]


def smooth_installer(hooks):
    def table(banked):
        return b''.join(a.to_bytes(2, 'little') + len(data).to_bytes(2, 'little') + data
                        for a, _, data in smooth_edits(hooks, banked)) + bytes(2)
    code = bytes.fromhex(hooks['install'])
    first = table(False)
    return code + (0xD402 + len(code) + len(first)).to_bytes(2, 'little') + first + table(True)


class AlteredBeastPatch:
    name = 'Altered Beast figures -> hardware sprites (alt ROM images 0 + 1, page 26 at slot 4, blit from the clean copy)'

    def __init__(self, prof=None, colours=None, rom_code=None, tables=None, smooth=False):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        cm = dict(colours) if colours is not None else load_colours_build()
        self.palette = set_palette(cm)
        self.banked = len(self.palette) > 16
        block = 'banked_' if self.banked else ''
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h[block + 'rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items() if not k.startswith('enhanced.')}
        if self.banked:
            self.syms.update({k.removeprefix('enhanced.'): int(v, 16) for k, v in h['syms'].items() if k.startswith('enhanced.')})
        self.stub_extra = bytes.fromhex(h[block + 'setup']) + bytes(self.palette)
        self.smooth = smooth
        self.stub_extra = restart_setup(self.stub_extra, h, smooth_installer(h) if smooth else b'')
        self.setup_call = 0xD200
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.colours = entries(cm)
        self.regblock = 0x2400 + len(self.rom_code)
        if self.regblock != self.syms['rom_end']:
            raise ValueError('hook code length differs from the profile symbols')
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hooks reach 0x3D00')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_LO, self.regblock + 20)
        pg = bytearray(8192)
        pg[0:0x400] = tables if tables is not None else pixel_tables()
        pg[0x400:0x400 + len(self.rom_code)] = self.rom_code
        self.page = pg
        self.hpage = bytearray(hook_page(self.colours))
        self.store = banked_store(self.colours, self.hpage) if self.banked else store_pages(self.colours)
        self.sites = [(a, bytes.fromhex(old), bytes.fromhex(SITE_SYM[a][0]) + self.syms[SITE_SYM[a][1]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]
        self.sites += [(a, bytes.fromhex(o), bytes.fromhex(n)) for a, o, n in INT_SITES]
        self.sites.append((RELOAD, RELOAD_ORIGINAL, bytes.fromhex(h['gameover'])))
        self.runtime_sites = []
        self.display_page = bytearray(self.page)
        if smooth:
            for a, old, new in smooth_edits(h, self.banked):
                if a >= 0x4000:
                    self.runtime_sites.append((a, old, new))
                    continue
                offset = a - ROM_LO
                if old and self.page[offset:offset + len(old)] != old:
                    raise ValueError('unexpected hook instruction at 0x%04X' % a)
                self.display_page[offset:offset + len(new)] = new
        self._banks()

    def _banks(self):
        self.extra_banks = {12: bytes(self.page) + bytes(8192), 13: bytes(self.hpage) + bytes(8192)}
        for n in range(NSTORE // 2):
            self.extra_banks[14 + n] = self.store[16384 * n:16384 * (n + 1)]

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.port7ffd & 7 != 0:
            raise ValueError('Altered Beast patch expects the 128K snapshot (7FFD bank 0)')
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
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        self.page[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self.display_page[self.regblock - ROM_LO:self.regblock - ROM_LO + len(regs)] = regs
        for a, old, _ in self.runtime_sites:
            b, o = where(a)
            if ram[b][o:o + len(old)] != old:
                raise ValueError('unexpected smooth install site at 0x%04X' % a)
        self._banks()
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[5]), bytes(ram[2]), bytes(ram[0])

    def alt_view(self, rom_get):
        lo, hi = self.altrom
        pg = self.display_page if self.smooth else self.page
        if self.smooth:
            hi = 0x3000 + len(bytes.fromhex(self.prof['hooks']['smooth']))
        return lambda a: pg[a - 0x2000] if lo <= a < hi else rom_get(a)


class PlainPatch:
    """The plain build includes the Next interrupt and level-one restart fixes."""
    name = 'Altered Beast, Next interrupt fix'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    extra_banks = {}
    altrom = None

    def __init__(self):
        h = load_profile()['hooks']
        self.setup_call = 0xD200
        self.stub_extra = restart_setup(b'\xc9', h)
        self.sites = [(a, bytes.fromhex(o), bytes.fromhex(n)) for a, o, n in INT_SITES]
        self.sites.append((RELOAD, RELOAD_ORIGINAL, bytes.fromhex(h['gameover'])))

    def apply(self, snap):
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            if bytes(ram[a - 0x4000:a - 0x4000 + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X' % a)
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])


def int_fix_check(z80, cases=40):
    """Each handler's entry, original against fixed, from varied registers: the same registers (interrupt state too) and
    memory after its three instructions. -> list of failures."""
    import random
    from skoolkit.simulator import Simulator
    from . import z80tonex as zt
    s = zt.Z80Snapshot(z80)
    ram = list(s.banks[5] + s.banks[2] + s.banks[0])
    rng, bad = random.Random(21), []
    for a, old, new in INT_SITES:
        for n in range(cases):
            regs = {k: rng.randrange(0x10000) for k in ('BC', 'DE', 'HL', '^BC', '^DE', '^HL', 'IX', 'IY')}
            regs.update(A=rng.randrange(256), F=rng.randrange(256), **{'^A': rng.randrange(256), '^F': rng.randrange(256)},
                        SP=0x5E2F, PC=a)
            out = []
            for code in (old, new):
                mem = [0] * 0x4000 + list(ram)
                mem[a:a + 3] = list(bytes.fromhex(code) if isinstance(code, str) else code)
                sim = Simulator(mem, regs, state={'iff': 0, 'im': 2})
                for _ in range(3):
                    sim.opcodes[mem[sim.registers[24]]]()
                R = list(sim.registers)
                R[25] = 0                                   # T: the same instructions, so equal; not compared
                out.append((R, mem, sim.registers[26] if len(sim.registers) > 26 else None))
            (r0, m0, i0), (r1, m1, i1) = out
            r0[24] = r1[24] = 0                             # both end at a + 3
            if r0 != r1 or m0[0x4000:a] != m1[0x4000:a] or m0[a + 3:] != m1[a + 3:]:
                bad.append(('handler 0x%04X differs' % a, n))
                break
    return bad


# ---------------------------------------------------------------------------------------------
# The plot model: what one logged figure draws (independent of the hook code)
# ---------------------------------------------------------------------------------------------

def _s8(v):
    return v - 256 if v & 0x80 else v


def plot_params(get, R, pc):
    """Plot parameters at a site, read from the game's own state (registers, variables)."""
    w = lambda a: get(a) | get(a + 1) << 8
    ix = R[8] * 256 + R[9]
    de = R[4] * 256 + R[5]
    ty = get((ix + 23) & 0xFFFF)
    if ty == 6:
        mode = 1 if get((ix + 26) & 0xFFFF) else 0
    elif ty == 64 and get(FLG):
        mode = 2
    else:
        mode = 0
    if pc == P_OP:
        kind, ptr, h = 2, R[6] * 256 + R[7], R[2]
    else:
        kind, ptr, h = (1 if pc == P_MIR else 0), w(PTR), get(H_)
    off = (ptr - w(PIX) + 128) & 0xFFFF
    # the plotter works the attribute address out on its own, with the column as 8 bits unsigned: a figure off
    # the left edge paints attributes 7 rows lower than its pixels (an original glitch at the margin)
    aptr = (w(ATT) + (get(YC) - 40) * 32 + get(23937)) & 0xFFFF if pc == P_OP else w(23300)
    return dict(kind=kind, mode=mode, de=de, W=get(W_), H=h, x=(off & 255) - 128, y=_s8(off >> 8), yc=get(YC),
                lim=get(LIM), ptr=ptr, ty=ty, ix=ix, aptr=aptr)


def plot_cells(get, p):
    """-> [(row on screen, column on screen, graphics address, stride, attribute as drawn)] for every
    non-empty visible cell, in the order the plotter draws them."""
    out = []
    W = p['W']
    if p['kind'] == 2:
        for r in range(p['H'] >> 3):
            for c in range(W):
                out.append((p['y'] + r, p['x'] + c, p['de'] + r * 8 * W + c, W, get(p['de'] + 144 + r * W + c)))
        return out
    a = p['de']
    for r in range(p['H']):
        v = (p['yc'] + r) & 255
        drawn = not ((v - 40) & 0x80) and bool((v - p['lim']) & 0x80)
        for c in range(W):
            f = get(a)
            if not f:
                a += 1
                continue
            if drawn:
                col = p['x'] + (-c if p['kind'] == 1 else c)
                at = get(a + 9)
                if p['mode'] == 1:
                    at = 7
                elif p['mode'] == 2:
                    at = {4: 5, 5: 4}.get(at, at)
                out.append((p['y'] + r, col, a + 1, 1, at))
            a += 10
    return out


def cell_bytes(get, kind, g, st):
    """Eight lines of a cell -> [(address of the stored byte, screen-order graphic, screen-order mask)]."""
    out = []
    for l in range(8):
        a = g + l * st
        v = get(a)
        if kind == 2:
            out.append((a, v, 0))
            continue
        m = get(MASKT + v)
        if kind == 1:
            v2, m = get(REVT + v), get(REVT + m)
            out.append((a, v2, m))
        else:
            out.append((a, v, m))
    return out


def plot_writes(get, p, buf, attr):
    """The plotter's effect in address space on dicts buf (pixels) and attr: the model of the game's plot."""
    base = get(PIX) | get(PIX + 1) << 8
    rd = lambda d, a: d[a] if a in d else get(a)
    for row, col, g, st, at in plot_cells(get, p):
        o = row * 256 + col
        for l, (a, v, m) in enumerate(cell_bytes(get, p['kind'], g, st)):
            ad = (base + o + l * 32) & 0xFFFF
            buf[ad] = (rd(buf, ad) & m) | v if p['kind'] != 2 else v
        attr[(p['aptr'] + (row - p['y']) * 32 + col - p['x']) & 0xFFFF] = at


def expected_layer(get, plots, colours=None, banked=False):
    """Sprites as the build should show them: plot order, clipped to the window -> ({(x, y): colour}, {(x, y): code})."""
    exp, code = {}, {}
    x0, x1, y0, y1 = CLIP
    for p in plots:
        bank = figure_bank(p['ty'], p['mode']) if banked else 0
        for row, col, g, st, at in plot_cells(get, p):
            ink, pap = attr_colours(at)
            for l, (a, v, m) in enumerate(cell_bytes(get, p['kind'], g, st)):
                y = row * 8 + l
                if not y0 <= y <= y1:
                    continue
                e = None
                if colours and (banked or not p['mode']):
                    e = colours.get(paint_key(bank, a) if banked else '%04X' % a)
                    if e is not None and e[0] != get(a):
                        e = None
                for b in range(8):
                    x = col * 8 + b
                    if not x0 <= x <= x1:
                        continue
                    bit = 0x80 >> b
                    sb = 7 - b if p['kind'] == 1 else b
                    nib = e[2][sb] if e else 0
                    k = 1 if v & bit else (2 if not m & bit else None)
                    if e and len(e) > 3 and e[3] & (0x80 >> sb):
                        if k is not None:
                            code[(x, y)] = 0       # made see-through by the map: the original draws it, the build not
                        continue
                    if k == 1:
                        c = nib or ink
                    elif k == 2:
                        c = nib or pap
                    elif nib:
                        c, k = nib, 0
                    else:
                        continue
                    exp[(x, y)], code[(x, y)] = bank * 16 + c, k
    return exp, code


# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------

def boot_check(nex, z80, patch=None, tail=None):
    """Boot the NEX in the Next model (nextboot.boot) to the snapshot PC: registers, the NEX banks = the
    (patched) snapshot's, RAM, MMU, paging (7FFD = 0, 1FFD = 0: ROM 0), $8C, alt ROM images."""
    import copy
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = nextboot.boot(nex, s.pc)
    R, mem = st['R'], st['mem']
    bad = [b for b in st['bad'] if not b[0] == 'read of ROM 0']
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
    ram = bytearray(s.banks[5] + s.banks[2] + s.banks[0])
    for a, _, new in getattr(patch, 'runtime_sites', ()):
        ram[a - 0x4000:a - 0x4000 + len(new)] = new
    t0, t1 = TAIL_ADDR, TAIL_ADDR + 96
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not t0 <= a < t1]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    if st['p7ffd'] != s.port7ffd or st['p1ffd'] != 0:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 0, 1]:
        bad.append(('MMU', st['mmu']))
    if patch is not None and patch.altrom is not None:
        lo, hi = patch.altrom
        img1 = bytearray(rom48())
        img1[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
        if bytes(st['alt'][1]) != bytes(img1):
            bad.append(('alt image 1 differs from ROM 3 + hooks',))
        if patch.smooth:
            hi = 0x3000 + len(bytes.fromhex(patch.prof['hooks']['smooth']))
        # In the gap after the register block the original ROM remains.
        parts = [(lo, patch.regblock + 20)]
        if patch.smooth:
            parts.append((0x3000, hi))
        if any(bytes(st['alt'][0][a:b]) != bytes(patch.display_page[a-ROM_LO:b-ROM_LO]) for a, b in parts):
            bad.append(('alt image 0 hook bytes differ',))
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
        if (0x15, 0x01) not in st['nrlog']:
            bad.append(('sprites not enabled',))
        if loaded_palette(st['nrlog']) != list(patch.palette):
            bad.append(('sprite palette differs from the colour map\'s', loaded_palette(st['nrlog']), list(patch.palette)))
    elif st['nr'].get(0x8C, 0) != 0:
        bad.append(('$8C', st['nr'].get(0x8C)))
    return bad


def static_check(code, org):
    """No hook instruction writes IX, IY, I or the interrupt state, no 0x3D00 fetch: only LD A,(IX+d) reads."""
    from .simrun import disasm
    mem = [0] * 65536
    mem[org:org + len(code)] = list(code)
    bad, a = [], org
    while a < org + len(code):
        t, n = disasm(mem, a)
        u = t.upper()
        if ('IX' in u or 'IY' in u) and not u.startswith('LD A,(IX'):
            bad.append((hex(a), t))
        if u in ('DI', 'EI', 'HALT') or u.startswith('IM ') or u.startswith('LD I,'):
            bad.append((hex(a), t))
        a += n
    if org + len(code) > 0x3D00:
        bad.append('code reaches 0x3D00')
    return bad


def build(z80, out, name, say=print):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, tail_req=TAIL_ADDR, quiet=True, patch=PlainPatch())
    bad = boot_check(plain, z80, PlainPatch())
    ib = int_fix_check(z80)
    say('Interrupt : EI two instructions later in the 3 handlers (Next /INT outlasts EI; EXX: INT_SITES): %s' % (
        'same state after each entry, 120 cases' if not ib else 'FAIL %s' % ib[:3]))
    bad += ib
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    patch = AlteredBeastPatch()
    sc = static_check(patch.rom_code, 0x2400)
    say('Static    : hook code %d bytes at 0x2400-0x%04X, no write of IX/IY/I/IFF: %s' % (
        len(patch.rom_code), patch.regblock + 20, 'PASS' if not sc else 'FAIL %s' % sc[:4]))
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, AlteredBeastPatch())
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    say('Colours   : %s' % ('%d colour-map entries' % len(patch.colours) if patch.colours else "no colour map: the game's own cell colours"))
    return (not bad and not bad2 and not sc), (plain, spr), patch


# ---------------------------------------------------------------------------------------------
# Differential verification
# ---------------------------------------------------------------------------------------------

class _NS:
    """Next-side state of the patched machine."""

    def __init__(self, patch):
        self.nr = {0x07: 0, 0x54: GP4, 0x55: GP5, 0x15: 1}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.rsel = 0
        self.events = []
        self.H = bytearray(patch.hpage)
        self.R = None
        self.ports = 0
        self.sel = 0                    # NextReg select (port 0x243B)

    def read(self, port):
        if port == 0x253B:              # NextReg read: NR 7 gives back the programmed speed in bits 1:0
            return self.nr.get(self.sel, 0)
        self.ports += 1
        return 0xFF

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x243B:              # NextReg select (a hook reads the caller's speed)
            self.sel = val
        elif port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
        else:
            self.ports += 1

    def sprite_layer(self, clip=CLIP):
        out = {}
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            x0 = a0 + (a2 & 1) * 256 - 32
            y0 = a1 + (a4 & 1) * 256 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            mir, ymir = a2 & 8, a2 & 4
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    c = (b >> 4) if k % 2 == 0 else (b & 15)
                    x, y = x0 + (15 - k if mir else k), y0 + (15 - j if ymir else j)
                    if c and clip[0] <= x <= clip[1] and clip[2] <= y <= clip[3]:
                        out[(x, y)] = (a2 & 0xF0) | c
        return out


class _SmoothVideo(_NS):
    """128K 50 Hz raster. Clock in 28 MHz T. Advance idle polling to the
    next relevant hardware edge, then let the Z80 execute its comparison."""
    LINE = 228 * 8
    FRAME = 311 * LINE

    def __init__(self, patch):
        from .dma import DMA
        super().__init__(patch)
        self.stage = bytearray(8192)
        self.clock = self.origin = 0
        self.shown = None
        self.patterns_on_screen = set()
        self.early_writes = 0
        self.dma = DMA(lambda a: self.mem[a], self.dma_write, self.out,
                       stall=lambda n: self.advance(8*n))
        self.tick_pc = patch.syms['wait_beat.tick']
        self.poll_pc = patch.syms['wait_beat.poll']
        self.wait_pc = patch.syms['wait_beat']
        self.first_poll = False

    def advance(self, cycles):
        self.clock += cycles

    def now(self):
        return self.clock + self.R[25] - self.origin

    def read(self, port):
        if port == 0x253B and self.sel in (0x1E, 0x1F):
            line = (self.now() // self.LINE) % 311
            return line >> 8 if self.sel == 0x1E else line & 255
        return super().read(port)

    def tick(self):
        # Interrupt 64 lines before ULA row zero.
        return ((self.now() + 64*self.LINE) // self.FRAME) & 255

    def poll(self, pc):
        if pc == self.wait_pc:
            self.first_poll = True
        elif pc == self.tick_pc:
            remaining = (self.R[2] - self.tick()) & 255
            if 0 < remaining < 128:
                self.advance(remaining*self.FRAME - (self.now() + 64*self.LINE) % self.FRAME)
        elif pc == self.poll_pc and self.first_poll:
            self.first_poll = False
            dest = PRESENT_LINE * self.LINE
            beam = self.now() % self.FRAME
            if beam // self.LINE != PRESENT_LINE:
                self.advance((dest - beam) % self.FRAME)

    def nextreg(self, reg, val):
        if reg == 0x26:
            self.shown = self.now()
        super().nextreg(reg, val)

    def dma_write(self, a, v):
        self.mem[a] = v

    def out(self, port, val):
        if port & 255 == 0x6B:
            self.dma.feed(val)
            return
        if port & 255 == 0x5B and self.pat_ptr // 128 in self.patterns_on_screen:
            self.early_writes += 1
        super().out(port, val)


class _OrigView:
    def __init__(self, get):
        self.get, self.ov = get, {}

    def __getitem__(self, a):
        v = self.ov.get(a)
        return v if v is not None else self.get(a)

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.ov[a] = v

    def __len__(self):
        return 65536


class _PatchedView(_OrigView):
    """The patched machine: alt ROM, patch sites, slot 4 = H when mapped, slot 5 = the colour store when mapped."""

    def __init__(self, get, ns, alt, psite, store, err):
        super().__init__(get)
        self.ns, self.alt, self.psite, self.store, self.err = ns, alt, psite, store, err

    def __getitem__(self, a):
        if a < 0x4000:
            return self.alt(a)
        if isinstance(self.ns, _SmoothVideo):
            if a == TICK:
                return self.ns.tick()
            page = self.ns.nr.get(0x50 + (a >> 13))
            if page == 86:
                return self.ns.stage[a & 8191]
            if page == 10 and a >= 0xA000:
                a = 0x4000 + (a & 8191)
        nr = self.ns.nr
        if 0x8000 <= a < 0xA000:
            if nr[0x54] == HPG:
                return self.ns.H[a - 0x8000]
        elif 0xA000 <= a < 0xC000:
            if nr[0x55] != GP5:
                pg = nr[0x55] - STORE
                if 0 <= pg < NSTORE:
                    return self.store[pg * 8192 + a - 0xA000]
                self.err.append(('slot 5: page', nr[0x55]))
                return 0
        if a not in self.ov:
            v = self.psite.get(a)
            if v is not None:
                return v
        return _OrigView.__getitem__(self, a)

    def __setitem__(self, a, v):
        nr = self.ns.nr
        if isinstance(self.ns, _SmoothVideo):
            page = nr.get(0x50 + (a >> 13))
            if page == 86:
                self.ns.stage[a & 8191] = v
                return
            if page == 10 and a >= 0xA000:
                a = 0x4000 + (a & 8191)
        if a < 0x4000:
            self.err.append(('ROM write', a))
            return
        if 0x8000 <= a < 0xA000 and nr[0x54] == HPG:
            self.ns.H[a - 0x8000] = v
            return
        if 0xA000 <= a < 0xC000 and nr[0x55] != GP5:
            self.err.append(('write to the colour store', a))
            return
        self.ov[a] = v


def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def _machine(Sim, mem, regs, ns, slot=None):
    from .rainbow import _machine as m
    sim = m(Sim, mem, regs, ns, slot)
    if isinstance(ns, _SmoothVideo):
        ns.mem = mem
        for op, cost in ((0x91, 20), (0x92, 17), (0x23, 8)):
            f = sim.after_ED[op]
            def timed(f=f, cost=cost):
                f()
                ns.advance(cost)
            sim.after_ED[op] = timed
    return sim


def _run_until(sim, stop, each=None, limit=4000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        if each is not None:
            each(R)
        n += 1
        if n > limit:
            return False
    return True


class _Dummy:
    hpage = bytes(8192)


def _safe(R, regs0, ns, err, base, depth=8):
    """After every hook instruction (PC in the alt ROM): IX, IY, I, IFF as at entry; SP on the hook stack
    (page H mapped) or on the game's stack; no fetch at 0x3D00-0x3DFF."""
    pc = R[24]
    if pc >= 0x4000:
        return
    if not base:
        base.extend(R[8:12])
    bad = None
    if list(R[8:12]) != base and not (ns.game_ix_ok and pc > 0):
        bad = 'IX/IY changed'
    elif R[14] != regs0[14] or R[26] != regs0[26]:
        bad = 'I / interrupt state changed'
    elif 0x3D00 <= pc < 0x3E00:
        bad = 'fetch in 0x3D00-0x3DFF'
    elif ns.nr[0x54] == HPG:
        if not 0x8000 + HSTK - 0x100 <= R[12] <= 0x8000 + HSTK and R[12] < regs0[12] - depth:
            bad = 'SP outside the hook stack'
    elif R[12] < regs0[12] - depth:
        bad = 'SP below the site SP - its depth'
    if bad:
        err.append(('interrupt-unsafe hook', bad, pc))


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """-> (Counter, examples, captured states). Failure keys end in '!'. Replays the ORIGINAL game; at every
    patch site the original and the patched code run from the same state and are compared."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    from . import rzx as RZ
    import tempfile
    MG, MS = Memory.__getitem__, Memory.__setitem__
    Sim = _sim_class()
    c = collections.Counter()
    ex = collections.defaultdict(list)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    site_bytes = {a + k: old[k] for a, old, new in patch.sites for k in range(len(old))}
    ns = _SmoothVideo(patch) if patch.smooth else _NS(patch)
    if patch.smooth:
        for a, old, new in patch.runtime_sites:
            psite.update({a + i: v for i, v in enumerate(new)})
    ns.game_ix_ok = False
    pscreen = {}
    st = {'frame': 0, 'in_blit': False, 'prev': None, 'plots': [], 'hookT': 0, 'gf': 0, 'maxT': 0, 'tog': 0}
    states = []
    frame_t = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    def pair(pc, mem, R):
        get = lambda a: MG(mem, a)
        regs = list(R)
        target = STOP[pc]
        err = []
        sp0 = regs[12]
        stop_ = lambda r: r[24] == target and r[12] == sp0
        o = _OrigView(get)
        so = _machine(Sim, o, list(regs), _NS(_Dummy), 'o')
        if pc == P_OP or pc == P_BLIT:
            so_stop = lambda r: r[24] == target and r[12] == sp0
        else:
            so_stop = stop_
        if not _run_until(so, so_stop):
            fail('original did not return', (pc,))
            return None
        p = _PatchedView(get, ns, patch.alt_view(get), psite, patch.store, err)
        sp_ = _machine(Sim, p, list(regs), ns, 'p')
        spd = st['spd'] = (st.get('spd', 0) + 1) % 4     # every hook entered at all four speeds in turn
        if patch.smooth:
            spd = 3
            ns.origin = sp_.registers[25]
            if pc == P_BLIT:
                # Use the original recorded TV intervals as an upper bound on
                # the game work at turbo, including original blit/ISR time.
                # The gauge loop removes 3000 iterations of 26 T per call.
                gap = st['frame'] - st.get('last_frame', st['frame'])
                ns.advance(max(0, (gap + 1)*70908 - st.pop('gauge', 0)*3000*26))
                ns.patterns_on_screen = {(a[3] & 63)*2 + ((a[4] >> 6) & 1)
                                         for a in ns.attr if a[3] & 128}
        ns.nr[0x07] = spd
        c['entry speed %d' % spd] += 1
        t0 = sp_.registers[25]
        ns.game_ix_ok = pc == P_BLIT                 # the blit itself loads IX (game code, same in both)
        base = []
        def step(r):
            _safe(r, regs, ns, err, base, 22 if pc == P_BLIT else 4)
            if patch.smooth and pc == P_BLIT:
                ns.poll(r[24])
        if not _run_until(sp_, stop_, each=step):
            fail('patched did not return', (pc,))
            return None
        ns.game_ix_ok = False
        if patch.smooth:
            ns.clock = ns.now()
            if pc == P_BLIT:
                if ns.shown is None or ns.dma.stats['jobs'] != c['commits'] + 1:
                    fail('missing scheduled screen transfer')
                else:
                    shown = ns.shown // ns.FRAME
                    if 'shown' in st:
                        delta = shown - st['shown']
                        want = (5, 6, 6)[(c['commits'] - 1) % 3]
                        c['shown interval %d' % delta] += 1
                        if delta != want:
                            fail('off beat', (delta, want))
                    st['shown'] = shown
                    end = ns.clock
                    if end // ns.FRAME != shown or ns.shown % ns.FRAME < 192 * ns.LINE:
                        fail('visible transfer', (ns.shown, end))
                    c['latest finish line'] = max(c['latest finish line'], end % ns.FRAME // ns.LINE)
                    if ns.early_writes:
                        fail('early visible pattern writes', (ns.early_writes,))
                        ns.early_writes = 0
        dt = (sp_.registers[25] - t0) - (so.registers[25] - regs[25])
        st['hookT'] += dt
        st['gfT'] = st.get('gfT', 0) + dt
        if pc == P_BLIT:
            c['hook T worst game frame'] = max(c['hook T worst game frame'], st['gfT'])
            st['gfT'] = 0
        c['hook T at 0x%04X' % pc] += dt
        for i in CMP:
            a, b = so.registers[i], sp_.registers[i]
            if i == 1 and pc == P_BLIT:              # bits 3 and 5 follow the last byte copied; the next LDI overwrites them
                a, b = a & 0xD7, b & 0xD7
            if a != b:
                fail('registers differ', (hex(pc), i, a, b))
        excl = SCREEN if pc == P_BLIT else (0, 0)
        keys = set(o.ov) | set(p.ov)
        dm = [a for a in keys if not excl[0] <= a < excl[1] and not (pc == P_BLIT and sp0 - 24 <= a < sp0) and
              o.ov.get(a, psite.get(a, get(a))) != p.ov.get(a, psite.get(a, get(a)))]
        if dm:
            fail('memory differs', (hex(pc), len(dm), [hex(a) for a in sorted(dm)[:4]]))
        if pc != P_BLIT and any(SCREEN[0] <= a < SCREEN[1] for a in p.ov):
            fail('screen written by a hook', (hex(pc),))
        if ns.nr.get(0x52, 10) != 10 or (ns.nr[0x54], ns.nr[0x55], ns.nr[0x07]) != (GP4, GP5, spd):
            fail('MMU / speed not restored', (hex(pc), ns.nr[0x54], ns.nr[0x55], ns.nr[0x07]))
            ns.nr.update({0x54: GP4, 0x55: GP5, 0x07: 0})
        if ns.ports:
            fail('port access in a hook', (hex(pc), ns.ports))
            ns.ports = 0
        for e in err:
            fail(str(e[0]), (hex(pc),) + tuple(e[1:]))
        for a, v in p.ov.items():
            if SCREEN[0] <= a < SCREEN[1]:
                pscreen[a] = v
        c['pairs 0x%04X' % pc] += 1
        return so, o, sp_, p

    def on_event(pc, mem, R):
        get = lambda a: MG(mem, a)
        for a in range(pc, pc + 3):
            if get(a) != site_bytes[a]:
                fail('site bytes changed in the game', (hex(pc),))
                return
        if mem.o7ffd & 7 != 0:
            fail('site reached with another bank at 0xC000', (hex(pc), mem.o7ffd))
        if pc in (P_FXA, P_FXB):
            st['fx'] = True
        elif pc != P_BLIT:
            pr = plot_params(get, R, pc)
            st['plots'].append(pr)
            c['types seen'] = 0
            st.setdefault('types', collections.Counter())[pr['ty']] += 1
            c['plots kind %d' % pr['kind']] += 1
            c['plots mode %d' % pr['mode']] += 1
        elif collect and len(states) < collect and st['plots'] and st['frame'] >= st.get('next_c', 0):
            st['next_c'] = st['frame'] + 300
            states.append(dict(R=list(R), mem=bytes(get(a) for a in range(65536)), H=bytes(ns.H), plots=[dict(p) for p in st['plots']]))
        res = pair(pc, mem, R)
        if res is not None and pc == P_BLIT:
            commit_checks(get, res)
        if pc == P_BLIT:
            st['plots'] = []
            st['fx'] = False

    def commit_checks(get, res):
        st['gf'] += 1
        c['commits'] += 1
        if 'last_frame' in st:
            c['original interval frames'] += st['frame'] - st['last_frame']
        st['last_frame'] = st['frame']
        plots = st['plots']
        w = lambda a: get(a) | get(a + 1) << 8
        base, abase, cl, cla = w(PIX), w(ATT), w(CPIX), w(CATT)
        # 1. the plot model against the game's own buffer: clean copy + the plots = the buffer, in address space
        buf, attr = {}, {}
        rd = get
        if st['tog'] % VERIFY_EVERY == 0:
            cl_diff = cl - base
            cla_diff = cla - abase
            mget = lambda a: get(a + cl_diff) if base <= a < base + 5120 else (get(a + cla_diff) if abase <= a < abase + 640 else get(a))
            for p in plots:
                plot_writes(mget, p, buf, attr)
            bad = 0
            for i in range(5120):                # the clean copy refreshes columns 2-29 only: the margins are stale
                if not 2 <= i & 31 <= 29:
                    continue
                a = base + i
                if buf.get(a, get(a + cl_diff)) != get(a):
                    bad += 1
            if bad:
                fail('clean copy + plot model differs from the game\'s buffer', (bad,))
                if DEBUG and DEBUG[0] > 0:
                    DEBUG[0] -= 1
                    print('frame', st['frame'], 'base %04X' % base, [dict(p) for p in plots])
                    print(' diffs', [('%04X' % (base + i), ((base + i - base) >> 8, (i & 31), i >> 5), '%02X' % buf.get(base + i, get(base + i + cl_diff)), '%02X' % get(base + i), '%02X' % get(base + i + cl_diff)) for i in range(5120) if 2 <= i & 31 <= 29 and buf.get(base + i, get(base + i + cl_diff)) != get(base + i)][:40])
            bad = 0
            fx = st.get('fx')
            if fx:
                c['frames with the level-end attribute effect'] += 1
            for i in range(640):
                if not 2 <= i & 31 <= 29:
                    continue
                if fx and FX_ROWS[0] <= i >> 5 < FX_ROWS[1] and FX_COLS[0] <= i & 31 < FX_COLS[1]:
                    continue
                a = abase + i
                if attr.get(a, get(a + cla_diff)) != get(a):
                    bad += 1
            if bad:
                fail('clean attributes + plot model differ from the game\'s buffer', (bad,))
                if DEBUG and DEBUG[0] > 0:
                    DEBUG[0] -= 1
                    print('frame', st['frame'], [(p['ty'], p['kind'], p['mode'], p['W'], p['H'], p['x'], p['y'], p['yc'], p['lim'], hex(p['de']), p['ix']) for p in plots])
                    print(' attr diffs', [((i >> 5), i & 31, '%02X' % attr.get(abase + i, get(abase + i + cla_diff)), '%02X' % get(abase + i), '%02X' % get(abase + i + cla_diff)) for i in range(640) if 2 <= i & 31 <= 29 and attr.get(abase + i, get(abase + i + cla_diff)) != get(abase + i)])
            # 2. the ULA play area is the clean copy
            bad = 0
            for row in range(19):
                for col in range(2, 30):
                    a = 0x5800 + row * 32 + col
                    want = get(abase + row * 32 + col) if fx and FX_ROWS[0] <= row < FX_ROWS[1] and FX_COLS[0] <= col < FX_COLS[1] \
                        else get(cla + row * 32 + col)
                    if pscreen.get(a, get(a)) != want:
                        bad += 1
                    for l in range(8):
                        y = row * 8 + l
                        sa = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col
                        if pscreen.get(sa, get(sa)) != get(cl + y * 32 + col):
                            bad += 1
            if bad:
                fail('ULA play area is not the scenery', (bad,))
            # 3. sprites = the plots in plot order, with the build's colours
            exp, code = expected_layer(get, plots, patch.colours, patch.banked)
            if patch.smooth:
                offset = max(0, 8 - get(0x5DA3)) & 0xFE   # even steps (no dither shimmer)
                if ns.nr.get(0x26) != offset:
                    fail('wrong ULA phase', (ns.nr.get(0x26), offset))
                exp = {(x-offset, y): v for (x, y), v in exp.items() if 16 <= x-offset <= 231}
            lay = ns.sprite_layer(SMOOTH_CLIP if patch.smooth else CLIP)
            c['sprite pixels compared'] += len(exp)
            if lay != exp:
                d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
                fail('sprite layer differs from the plots', (len(d), sorted(d)[:3], [(lay.get(k), exp.get(k)) for k in sorted(d)[:3]]))
            # 4. end to end: the original's buffer against ULA + sprites (ink / not ink); painted clear pixels excluded
            bad = wrap = 0
            for y in range(CLIP[2], CLIP[3] + 1):
                for x in range(CLIP[0], CLIP[1] + 1):
                    o = get(base + y * 32 + (x >> 3))
                    bit = 0x80 >> (x & 7)
                    k = code.get((x, y))
                    if k == 0:
                        continue
                    want = (k == 1) if k is not None else bool(get(cl + y * 32 + (x >> 3)) & bit)
                    if bool(o & bit) != want:
                        bad += 1
            if bad:
                # figures with a column outside 0-31 wrap to the neighbouring line in the buffer (a glitch at the
                # margin that the sprites do not copy): counted, not failed, when only such figures exist
                if any(cell[1] < 0 or cell[1] > 31 for p in plots for cell in plot_cells(get, p)):
                    c['margin wrap pixels (original only)'] += bad
                else:
                    fail('screen + sprites differ from the original buffer', (bad,))
            lo = sum(1 for p in plots for cell in plot_cells(get, p) if cell[0] == 19 and 9 <= cell[1] <= 26)
            c['figure cells in row 19 (7 lines, not on sprites)'] += lo
        st['tog'] += 1
        c['max sprites in a frame'] = max(c['max sprites in a frame'], sum(1 for a in ns.attr if a[3] & 0x80))
        c['max plots in a frame'] = max(c['max plots in a frame'], len(plots))
        if ns.H[V_DROP]:
            fail('figures dropped', (ns.H[V_DROP],))
            ns.H[V_DROP] = 0
        if ns.H[V_TEAR]:
            c['shown entries evicted before the upload'] += ns.H[V_TEAR]
            ns.H[V_TEAR] = 0
        if ns.H[V_N]:
            fail('log not empty after the commit')

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes

            class W(type(mem)):
                def __setitem__(s, a, v):
                    if SCREEN[0] <= a < SCREEN[1] and not st['in_blit']:
                        pscreen.pop(a, None)
                    MS(s, a, v)
            mem.__class__ = W

            def mk(f):
                def g():
                    pc = R[24]
                    prev, st['prev'] = st['prev'], pc
                    if patch.smooth and pc in (0xB6D2, 0xB6E1):
                        st['gauge'] = st.get('gauge', 0) + 1
                    if pc in INTERIOR and not (prev is not None and INTERIOR[pc] <= prev < pc):
                        fail('jump into a patched instruction', (hex(pc), prev))
                    if st['in_blit']:
                        if pc == BLIT_RET:
                            st['in_blit'] = False
                    elif pc in SITES_ORIG:
                        on_event(pc, mem, R)
                        if pc == P_BLIT:
                            st['in_blit'] = True
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])
    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        c['frames'] = st['frame']
        if progress and st['frame'] % 500 == 0:
            progress(st['frame'], c)
        return _nf(self)
    fd, tmp = tempfile.mkstemp(suffix='.rzx')
    os.close(fd)
    RZ.strip(rzx_path, tmp)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = next_frame, S, None
    try:
        try:
            rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else []) + [tmp])
        except SystemExit:
            pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
        os.remove(tmp)
    c['hook T per game frame'] = st['hookT'] // max(1, st['gf'])
    ex['types'] = sorted(st.get('types', {}).items())
    del c['types seen']
    return c, ex, states


DEBUG = []
VERIFY_EVERY = 1                 # every commit gets the full model and layer checks


# ---------------------------------------------------------------------------------------------
# Unit tests: paths the recordings do not reach, on captured states
# ---------------------------------------------------------------------------------------------

def _state_get(st):
    return lambda a: st['mem'][a & 0xFFFF]


def _log_entry(p, banked=False):
    x = p['x'] & 255
    return bytes([p['kind'] | p['mode'] << 4, p['de'] & 255, p['de'] >> 8, p['W'], p['H'], x, p['y'] & 255, p['yc'], p['lim'], p['ty'] if banked else 0])


def run_commit(patch, st, plots, H=None, ns=None):
    """Run the hook's commit in the simulator on a captured state with this log -> (ns, ok)."""
    get = _state_get(st)
    ns = ns or _NS(patch)
    ns.game_ix_ok = False
    ns.H[:] = H if H is not None else patch.hpage
    ns.H[V_N] = len(plots)
    for i, p in enumerate(plots):
        ns.H[LOG + 10 * i:LOG + 10 * i + 10] = _log_entry(p, patch.banked)
    ns.nr[0x54] = HPG
    err = []
    m = _PatchedView(get, ns, patch.alt_view(lambda a: 0), {}, patch.store, err)
    regs = list(st['R'])
    regs[12] = 0x8000 + HSTK - 2
    m[0x8000 + HSTK - 2], m[0x8000 + HSTK - 1] = 0xFE, 0xFF
    regs[24] = patch.syms['commit']
    s = _machine(_sim_class(), m, regs, ns, 'p')
    ok = _run_until(s, lambda r: r[24] == 0xFFFE)
    ns.nr[0x54] = GP4
    return ns, ok and not err


def unit_tests(patch, states, negatives=()):
    c = collections.Counter()
    fails = collections.defaultdict(list)

    def fail(k, *info):
        c[k + '!'] += 1
        if len(fails[k]) < 4:
            fails[k].append(info)

    def layer_check(name, p_, st, plots):
        ns, ok = run_commit(p_, st, plots)
        c['cases'] += 1
        if not ok:
            fail(name + ' did not return')
            return None
        exp, _ = expected_layer(_state_get(st), [q for q in plots if plot_ok(q)], p_.colours, p_.banked)   # the build's own map
        lay = ns.sprite_layer()
        if lay != exp:
            d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
            fail(name, len(d), sorted(d)[:3], [(lay.get(k), exp.get(k)) for k in sorted(d)[:3]])
        return ns

    if patch.banked:
        rom = bytearray(patch.rom_code)
        i = rom.index(bytes.fromhex('3A6380B077'))   # LD A,(V_BANK); OR B; LD (HL),A
        rom[i:i + 3] = bytes.fromhex('AF0000')
        banked_map = dict(patch.colours, palette=patch.palette)
        wrong_bank = AlteredBeastPatch(patch.prof, banked_map, bytes(rom))
        rom = bytearray(patch.rom_code)
        i = rom.index(bytes.fromhex('323680'))        # drop part's store of the mode, leaving mode zero
        rom[i:i + 3] = bytes(3)
        wrong_mode = AlteredBeastPatch(patch.prof, banked_map, bytes(rom))

    for st in states:
        plots = st['plots']
        get = _state_get(st)
        # every captured figure alone, then all together twice (second run: cache hits)
        for p in plots:
            layer_check('figure alone', patch, st, [p])
        ns = layer_check('all figures', patch, st, plots)
        if ns is not None:
            ns2, ok = run_commit(patch, st, plots, H=bytes(ns.H), ns=ns)
            c['cache hit cases'] += 1
            if not ok or ns2.sprite_layer() != expected_layer(get, [q for q in plots if plot_ok(q)], patch.colours, patch.banked)[0]:
                fail('cache hit differs')
        # position edges: each figure at the window's sides and top
        for p in plots[:6]:
            for dx in (-40, -6, -3, -1, 1, 3, 30):
                q = dict(p, x=p['x'] + dx)
                layer_check('x edge', patch, st, [q])
            for yc in (30, 36, 39, 40, 52, 56, 59):
                if p['kind'] == 2:
                    continue
                q = dict(p, yc=yc, y=yc - 40)
                layer_check('row limit', patch, st, [q])
            for lim in (56, 57, 60):
                if p['kind'] != 2:
                    layer_check('limit value', patch, st, [dict(p, lim=lim)])
            for mode in (1, 2):
                if p['kind'] != 2:
                    layer_check('colour mode', patch, st, [dict(p, mode=mode)])
            if p['kind'] != 2:
                layer_check('mirrored', patch, st, [dict(p, kind=1 - p['kind'], x=p['x'] + (p['W'] - 1 if p['kind'] == 0 else -(p['W'] - 1)))])
        # guards: too wide, the stream inside slot 4, too many figures
        p0 = next((p for p in plots if p['kind'] != 2), plots[0])
        for name, q in (('W 17 dropped', dict(p0, W=17)), ('W 0 dropped', dict(p0, W=0)),
                        ('stream in slot 4 dropped', dict(p0, de=0x8100))):
            ns, ok = run_commit(patch, st, [q])
            c['guard cases'] += 1
            if not ok or ns.H[V_DROP] != 1 or any(a[3] & 0x80 for a in ns.attr):
                fail(name, ns.H[V_DROP])
        # the pattern store under pressure: many distinct large figures, repeated commits, none dropped
        H = None
        ns = _NS(patch)
        big = [p for p in plots if p['kind'] != 2][:4] or [p0]
        for n in range(40):
            q = [dict(b, de=b['de'], r=n) for b in big]
            ns, ok = run_commit(patch, st, q, H=H, ns=ns)
            H = bytes(ns.H)
            c['pressure commits'] += 1
            if not ok:
                fail('pressure commit did not return')
        # a colour map: painted ink, painted clear pixel, transparent mask, wrong check byte
        # (the build's own map when it has one, e.g. the Enhanced set; else a synthetic one)
        if not patch.colours:
            cm = synthetic_colours(st, plots)
            pc = AlteredBeastPatch(patch.prof, colours=cm, rom_code=patch.rom_code)
            layer_check('colour map', pc, st, plots)
        else:
            cm, pc = patch.colours, patch
        c['map entries'] = max(c['map entries'], len(cm))
        ok_plots = [q for q in plots if plot_ok(q)]
        no_paint = bytearray(pc.hpage)
        no_paint[V_COL] = 0
        ns, ok = run_commit(pc, st, plots, H=no_paint)
        c['map negative cases'] += 1
        if ok and ns.sprite_layer() != expected_layer(get, ok_plots, cm, patch.banked)[0]:
            c['map negative detected'] += 1
        # a hit flash or player two shows the game's colours over a map; a hook that paints them anyway is caught
        if patch.banked:
            # Use one visible pose for every type/mode, including two players sharing one cache.
            q = dict(p0, x=10, y=2, yc=42, kind=0)
            cases = ((64, 0, 0), (64, 2, 1), (2, 0, 2), (130, 0, 2), (6, 0, 3), (6, 1, 4),
                     (7, 0, 5), (9, 0, 6), (13, 0, 6), (8, 0, 7), (1, 0, 0))
            ns = _NS(patch)
            for ty, mode, bank in cases:
                plot = dict(q, ty=ty, mode=mode)
                ns, ok = run_commit(patch, st, [plot], H=bytes(ns.H), ns=ns)
                got = {a[2] >> 4 for a in ns.attr if a[3] & 128}
                c['bank cases'] += 1
                if not ok or got != {bank} or ns.sprite_layer() != expected_layer(get, [plot], cm, True)[0]:
                    fail('bank selection or cached paint', ty, mode, got, bank)
            # Lose the attribute palette offset, keeping the painted patterns.
            for ty, mode, bank in cases:
                if not bank:
                    continue
                plot = dict(q, ty=ty, mode=mode)
                broken, ok = run_commit(wrong_bank, st, [plot])
                c['bank negative cases'] += 1
                if ok and broken.sprite_layer() != expected_layer(get, [plot], cm, True)[0]:
                    c['bank negative detected'] += 1
            nm = wrong_mode
        else:
            nm = AlteredBeastPatch(patch.prof, colours=cm, rom_code=_no_mode_skip(patch.rom_code))
        for p in [q for q in plots if q['kind'] != 2 and plot_ok(q)][:6]:
            for mode in (1, 2):
                q = [dict(p, mode=mode)]
                layer_check('colour mode over a map', pc, st, q)
                ns, ok = run_commit(nm, st, q)
                c['mode negative cases'] += 1
                if ok and ns.sprite_layer() != expected_layer(get, q, cm, patch.banked)[0]:
                    c['mode negative detected'] += 1
    return c, fails


def _palette_negatives(z80, cm, tmp):
    """The Enhanced set's own palette: caught by the boot check (the palette the setup loads) or by the engine refusing
    a map that changes an entry a figure's cell colours use."""
    from . import z80tonex as zt
    res = []
    T = os.path.join(tmp, 'negpal.nex')
    size = len(set_palette(cm))
    def flip(e, index):
        e[len(e) - size + index] ^= 1
        return e
    faults = [("the game's palette loaded instead", lambda e: e[:-size] + bytes(PALETTE) + e[len(e)-size+16:]),
              ('skin entry wrong by one bit', lambda e: flip(e, 1))]
    if size > 16:
        count = bytes.fromhex('06807EED9241')
        def short_load(e):
            i = e.index(count)
            e[i + 1] = 16
            return e
        faults += [('only bank zero loaded', short_load), ('zombie robe entry changed', lambda e: flip(e, 35))]
    for name, f in faults:
        p = AlteredBeastPatch(colours=cm)
        end = len(bytes.fromhex(p.prof['hooks']['banked_setup' if p.banked else 'setup'])) + size
        p.stub_extra = bytes(f(bytearray(p.stub_extra[:end]))) + p.stub_extra[end:]
        zt.convert(z80, T, quiet=True, patch=p)
        res.append((name, bool(boot_check(T, z80, AlteredBeastPatch(colours=cm)))))
    for i, v in ((3, 0x86), (6, 0xD1)):
        m = dict(cm)
        pal = list(set_palette(cm))
        pal[i] = v
        m['palette'] = pal
        try:
            AlteredBeastPatch(colours=m)
            res.append(('map changes palette entry %d' % i, False))
        except ValueError:
            res.append(('map changes palette entry %d' % i, True))
    return res


def _no_mode_skip(rom):
    """Negative control: bout's LD A,(V_MODE) / OR A / JR NZ,.def (the game's colours in a hit flash or for player
    two) taken out, so the map paints those figures too."""
    i = rom.find(bytes.fromhex('3A3680B720'))
    if i < 0:
        raise ValueError('negative control: the mode test in bout not found')
    return rom[:i] + bytes(6) + rom[i + 6:]


def plot_ok(p):
    return 1 <= p['W'] <= 16


def synthetic_colours(st, plots):
    get = _state_get(st)
    cm = {}
    n = 0
    for p in plots:
        for row, col, g, stride, at in plot_cells(get, p)[:6]:
            for a, v, m in cell_bytes(get, p['kind'], g, stride):
                n += 1
                nib = [(n + i) % 16 for i in range(8)]
                e = [get(a), 1, nib]
                if n % 3 == 0:
                    e.append(0x81)
                if n % 7 == 0:
                    e[0] = (get(a) + 1) & 255        # wrong check: must be ignored
                cm['%04X' % a] = e
    return cm


# ---------------------------------------------------------------------------------------------
# Negative controls: deliberately broken builds on the real recording
# ---------------------------------------------------------------------------------------------

def negative_patches(patch=None):
    prof = load_profile()
    good = bytes.fromhex(prof['hooks']['rom'])
    syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}

    def mod(name, f, tables=None):
        b = bytearray(good)
        f(b)
        return name, AlteredBeastPatch(prof, colours={}, rom_code=bytes(b), tables=tables)

    def at(sym):
        return syms[sym] - 0x2400

    def rep(old, new, start=0, end=None):
        def f(b):
            i = bytes(b).find(bytes.fromhex(old), start, end if end else len(b))
            if i < 0:
                raise ValueError('negative control: %s not found' % old)
            b[i:i + len(bytes.fromhex(new))] = bytes.fromhex(new)
        return f

    def nop(sym, n=3):
        def f(b):
            b[at(sym):at(sym) + n] = bytes(n)
        return f
    t = pixel_tables()
    swapped = t[0x200:0x400] + t[:0x200]
    out = [
        mod('ULA pixels from the buffer (figures stay on the ULA)', nop('neg_pix')),
        mod('ULA attributes from the buffer (clash stays)', nop('neg_att')),
        mod('buffer pointer not put back', rep('22245B', '000000', at('e_bl') + 30, at('commit'))),
        mod('HL not corrected after the blit', rep('E1B7ED52D1', 'E1000000D1', at('e_bl'), at('commit'))),
        mod('mirrored plots logged as stored', rep('3E01', '3E00', at('e_pm'), at('e_op'))),
        mod('opaque plots logged as masked', rep('3E02', '3E00', at('e_op'), at('logp'))),
        mod('player two colour swap ignored', rep('3E20', '3E00', at('logp'), at('e_bl'))),
        mod('hit colour ignored', rep('3E10', '3E00', at('logp'), at('e_bl'))),
        mod('level-end effect not flagged', nop('neg_fx', 4)),
        mod('row limit ignored', rep('3A44D0', '3E3C00', at('logp'), at('e_bl'))),
        mod('log holds one figure', rep('FE20', 'FE01', at('logp'), at('e_bl'))),
        mod('sprites one line low', rep('C620', 'C621', at('emit'))),
        mod('hook writes IY (interrupt safety)', rep('ED910703', 'FD210000', at('e_pn'), at('e_pm'))),
        mod('hook leaves 28 MHz on', rep('3A6280ED9207', '3E0300ED9207', at('e_op'), at('logp'))),
        mod('hook gives back 3.5 MHz, not the caller\'s speed', rep('3A6280ED9207', 'AF0000ED9207', at('e_op'), at('logp'))),
        ('ink and paper swapped', AlteredBeastPatch(prof, colours={}, rom_code=good, tables=swapped)),
    ]
    return out


def run_negatives(rzx, stop=600, say=print, rzx2=None, rzx3=None):
    jobs = []
    for name, p in negative_patches():
        if 'level-end' in name:
            if rzx3:
                jobs.append((name, p, rzx3, 16480))
        else:
            jobs.append((name, p, rzx2 if rzx2 and 'player two' in name else rzx, stop))
    detected = 0
    for (name, *_), (counts, _, _, _) in zip(jobs, recording_results(jobs)):
        failures = sorted(k for k in counts if k.endswith('!'))
        detected += bool(failures)
        say('            %-52s %s' % (name, 'DETECTED %s' % failures[:2] if failures else 'NOT DETECTED'))
    return len(jobs), detected


# ---------------------------------------------------------------------------------------------
# auto
# ---------------------------------------------------------------------------------------------

def scroll_negatives(z80, recording):
    """Mutate the installed instructions and require the specific detector."""
    import tempfile
    from . import z80tonex as zt
    tests = []
    for label, symbol, old, new, detector in [
            ('one frame late', 'wait_beat', '0606fe01', '0607fe01', 'off beat!'),
            ('DMA crosses visible line zero', 'wait_beat.poll', 'fe0120', 'fe3020', 'visible transfer!')]:
        p = AlteredBeastPatch(smooth=True)
        at = p.display_page.index(bytes.fromhex(old), p.syms[symbol] - ROM_LO)
        p.display_page[at:at+len(old)//2] = bytes.fromhex(new)
        c, _, _ = verify(p, recording, stop=440)
        tests.append((label, c[detector] > 0))
    with tempfile.TemporaryDirectory() as d:
        file = os.path.join(d, 'leak.nex')
        zt.convert(z80, file, quiet=True, patch=AlteredBeastPatch(smooth=True))
        tests.append(('smooth installer leaked into off build', bool(boot_check(file, z80, AlteredBeastPatch()))))
    return tests


def _recording(job):
    import time
    name, patch, recording, stop = job
    start = time.monotonic()
    result = verify(patch, recording, stop=stop, collect=3 if name == 'default' else 0)
    return (*result, time.monotonic() - start)


def recording_results(jobs):
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context
    with ProcessPoolExecutor(max_workers=min(len(jobs), os.cpu_count() or 1), mp_context=get_context('spawn')) as pool:
        return list(pool.map(_recording, jobs))


def scroll_outputs(a, z80, out, name, builds, say):
    from pathlib import Path
    from . import z80tonex as zt
    def path(suffix):
        return Path(out) / (name + suffix)
    manifest = dict(default=name + '_sprites.nex', plain=name + '.nex', colours={})
    toggle = dict(logic=True, what='Smooth scroll, changes the game logic pace to 5/6/6 frames', colours={})
    checks = []
    for edition, old in list(builds):
        enhanced = old.banked
        suffix = '_enhanced' if enhanced else ''
        patch = AlteredBeastPatch(colours=load_colours(ENHANCED) if enhanced else None, smooth=True)
        file = path(suffix + '_smooth.nex')
        zt.convert(z80, str(file), quiet=True, patch=patch)
        bad = boot_check(str(file), z80, patch)
        say('Smooth    : %s boot %s' % (file.name, str(bad[:3]) if bad else 'OK'))
        checks.append(not bad)
        if enhanced:
            manifest['colours']['Enhanced'] = dict(default=name + '_enhanced.nex')
            toggle['colours']['Enhanced'] = dict(default=file.name)
        else:
            toggle['default'] = file.name
        builds.append((edition + ' smooth', patch))
    manifest['toggles'] = {'Smooth scroll': toggle}
    path('_outputs.json').write_text(json.dumps(manifest, indent=1))
    if not getattr(a, 'pok', None):
        snap = zt.Z80Snapshot(z80)
        lines = []
        for label, addr, bank in [('credits', 0x63F1, 5), ('lives', 61350, 0), ('energy', 61330, 0)]:
            value = snap.banks[bank][addr & 16383]
            if value == 0:  # trainer already enabled in this snapshot
                continue
            if value != 0x3D:
                raise ValueError('unexpected trainer instruction at 0x%04X' % addr)
            lines += ['NInfinite ' + label, 'Z %d %d 0 61' % (8 if bank == 5 else 0, addr)]
        if lines:
            pok = path('_verified.pok')
            pok.write_text('\n'.join(lines + ['Y', '']))
            a.pok = str(pok)
    return all(checks)


def auto(a, z80, name, out, say):
    """Plain and default sprite builds, and the Enhanced set (NAME_enhanced.nex: the map ENHANCED, its palette) when that
    map exists; every recording verified against each sprite build; the negative controls on the recordings (whole runs
    only), the Enhanced palette negatives, unit tests on each build."""
    from . import z80tonex as zt
    say('Game      : %s' % name)
    say('Engine    : altered_beast (back-buffer composer, cell plotter; blit from the clean copy; every figure -> sprites)')
    ok, (plain, spr), patch = build(z80, out, name, say)
    builds = [('default', patch)]
    if os.path.exists(ENHANCED):
        cm = load_colours(ENHANCED)
        enh = os.path.join(out, name + '_enhanced.nex')
        ep = AlteredBeastPatch(colours=cm)
        zt.convert(z80, enh, quiet=True, patch=ep)
        bad = boot_check(enh, z80, AlteredBeastPatch(colours=cm))
        ok = ok and not bad and not static_check(ep.rom_code, 0x2400)
        say('Enhanced  : %s  %s  boot %s; %d colour-map entries, %d palette banks, bank zero entries %s changed' % (
            os.path.basename(enh), hashlib.md5(open(enh, 'rb').read()).hexdigest(), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300],
            len(ep.colours), len(ep.palette) // 16, [i for i in range(16) if ep.palette[i] != PALETTE[i]]))
        if ep.banked:
            import shutil
            shutil.copyfile(ENHANCED, os.path.splitext(enh)[0] + '_colours.json')
        builds.append(('Enhanced', ep))
        import tempfile
        with tempfile.TemporaryDirectory(prefix='ab_') as tmp:
            pn = _palette_negatives(z80, cm, tmp)
        for nm, hit in pn:
            say('Negative  : Enhanced palette: %-40s %s' % (nm, 'DETECTED' if hit else 'NOT DETECTED'))
        ok = ok and all(h for _, h in pn)
    ok = scroll_outputs(a, z80, out, name, builds, say) and ok
    states = []
    stop = getattr(a, 'quick', None)
    jobs = [(label, p, r, stop) for r in (a.rzx or []) for label, p in builds]
    if jobs:
        results = recording_results(jobs)
        for (bname, bp, r, _), (c, ex, st, elapsed) in zip(jobs, results):
            states += st
            fails = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fails
            say('Verify    : %s %s  %d frames, %d commits (max %d sprites, %d plots), %d sprite pixels, %.0fs -> %s' % (
                os.path.basename(r), bname, c['frames'], c['commits'], c['max sprites in a frame'], c['max plots in a frame'],
                c['sprite pixels compared'], elapsed, 'IDENTICAL' if not fails else 'FAILED %s' % fails))
            if bp.smooth:
                say('Pace      : %s %s, original %d frames / %d intervals, shown %s, latest completion line %d of 311' %
                    (os.path.basename(r), bname, c['original interval frames'], max(0, c['commits'] - 1),
                     {k.split()[-1]: v for k, v in c.items() if k.startswith('shown interval ')}, c['latest finish line']))
                for k in fails:
                    say('            %s: %s' % (k, ex[k[:-1]][:2]))
            if bname != 'default':
                say('            hook T per game frame %d, plots by mode %s' % (c['hook T per game frame'],
                    [c['plots mode %d' % mode] for mode in (0, 1, 2)]))
                continue
            say('            pairs: %s' % ', '.join('%s %d' % (k[6:], v) for k, v in sorted(c.items()) if k.startswith('pairs ')))
            say('            hook T per game frame %d (simulator T; the commit and logs run at 28 MHz); %s' % (
                c['hook T per game frame'], ', '.join('%s %d' % (k, v) for k, v in sorted(c.items())
                                                      if k.startswith(('margin', 'figure cells', 'shown', 'hook T', 'plots ', 'frames with')))))
            say('            figure types: %s' % ex.pop('types', ''))
            for k, v in ex.items():
                say('            %s: %s' % (k, str(v)[:300]))
    by = {os.path.basename(r): r for r in (a.rzx or [])}
    if 'ab_first.rzx' in by and not stop:
        for label, detected in scroll_negatives(z80, by['ab_first.rzx']):
            say('Negative  : %s: %s' % (label, 'DETECTED' if detected else 'NOT DETECTED'))
            ok = ok and detected
        say('Negative  : broken builds on the recordings (ab_first 1,500 frames; player two on ab_2p; level end on ab_level):')
        n, d = run_negatives(by['ab_first.rzx'], 1500, say=say, rzx2=by.get('ab_2p.rzx'), rzx3=by.get('ab_level.rzx'))
        say('Negative  : %d/%d DETECTED' % (d, n))
        ok = ok and n and d == n
    if states:
        sel = [s for s in states if any(p['kind'] != 2 and plot_ok(p) for p in s['plots'])][:3] or states[:3]   # masked figures
        for bname, bp in builds:
            if bp.smooth:
                continue  # full scheduled blits are exercised by verify
            u, f = unit_tests(bp, sel)
            if bp.banked:
                say('Unit      : Enhanced palette bank selections %d, wrong bank detected %d/%d' %
                    (u['bank cases'], u['bank negative detected'], u['bank negative cases']))
                ok = ok and 0 < u['bank negative detected'] == u['bank negative cases']
            uf = {k: v for k, v in u.items() if k.endswith('!')}
            neg_ok = (0 < u['map negative detected'] == u['map negative cases'] and
                      0 < u['mode negative detected'] == u['mode negative cases'])
            ok = ok and not uf and neg_ok
            say('Unit      : %s: %d layer cases, %d cache-hit, %d guard, %d pressure commits, colour map %d entries, map negative %d/%d, '
                'hit flash / player two over a map negative %d/%d -> %s' % (
                    bname, u['cases'], u['cache hit cases'], u['guard cases'], u['pressure commits'], u['map entries'],
                    u['map negative detected'], u['map negative cases'], u['mode negative detected'], u['mode negative cases'],
                    'PASS' if not uf and neg_ok else 'FAIL %s %s' % (uf, dict(f))))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Colour sheets and recolour (docs/COLOURS.md)
# ---------------------------------------------------------------------------------------------

GROUPS = ('Player', 'Zombies', 'Wolves', 'Boss', 'Graves', 'Others')


def group_of(ty):
    t = ty & 0x7F
    if t == 64:
        return 'Player'
    if t in (2, 3):
        return 'Zombies'
    if t in (6, 7):
        return 'Wolves'
    if t in (9, 10, 11, 12, 13):
        return 'Boss'
    if t == 1:
        return 'Graves'
    return 'Others'


def sheet_part(get, p, frame, banked=False):
    """A plot -> a coloursheet part: every bit of its graphics bytes (clear bits code 0); default colours as drawn."""
    bank = figure_bank(p['ty'], p['mode']) if banked else None
    W = p['W']
    cells = plot_cells(get, p)
    if not cells:
        return None
    rows = sorted({c[0] for c in cells})
    r0 = rows[0]
    pixels, entries = [], {}
    x0 = p['x'] - (W - 1) if p['kind'] == 1 else p['x']
    for row, col, g, st, at in cells:
        ink, pap = attr_colours(at)
        k = (W - 1 - (col - x0)) if p['kind'] == 1 else col - x0     # stored column
        for l in range(8):
            a = g + l * st
            v = get(a)
            m = 0 if p['kind'] == 2 else get(MASKT + v)
            key = paint_key(bank, a) if banked else '%04X' % a
            entries.setdefault(key, [v, 1])
            for b in range(8):
                bit = 0x80 >> b
                code = 1 if v & bit else (0 if m & bit else 2)
                dflt = ink if code == 1 else (pap if code == 2 else 0)
                pixels.append((k * 8 + b, (row - r0) * 8 + l, key, b, code, dflt))
    h = (rows[-1] - r0 + 1) * 8
    part_id = (p['de'], p['kind'] == 2)
    if banked:
        part_id += (bank,)
    return dict(id=part_id, bank=bank, size=h, w=8 * W, h=h, x=8 * x0, y=8 * r0, mir=int(p['kind'] == 1),
                group=group_of(p['ty']), fam=(frame, p['ix']), role=None, pixels=pixels, entries=entries)


def capture(rzx_paths, stop=None, progress=None, banked=False):
    """Replay the recordings (original game): every plot, frame by frame, joined into figures by object."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    from . import coloursheet as cs, rzx as RZ
    import tempfile
    MG = Memory.__getitem__
    col = cs.Collector(family=lambda p: p['fam'])
    st = {'f': 0, 'mem': None}
    frame = []

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: MG(mem, a)

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in (P_NORM, P_MIR, P_OP):
                        p = plot_params(get, R, pc)
                        d = sheet_part(get, p, st['f'], banked)
                        if d:
                            frame.append(d)
                    elif pc == P_BLIT:
                        if frame:
                            col.add_frame(list(frame))
                            frame.clear()
                        if st['mem'] is None:
                            st['mem'] = bytes(get(a) for a in range(65536))
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])
    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['f'] += 1
        if progress and st['f'] % 2000 == 0:
            progress(st['f'])
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = next_frame, S, None
    try:
        for path in ([rzx_paths] if isinstance(rzx_paths, str) else rzx_paths):
            fd, tmp = tempfile.mkstemp(suffix='.rzx')
            os.close(fd)
            RZ.strip(path, tmp)
            frame.clear()
            try:
                rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else []) + [tmp])
            except SystemExit:
                pass
            finally:
                os.remove(tmp)
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    return col, st['mem']


def sheets(col, prefix, peek, colours=None):
    """<prefix>_PAINTING_SPRITES.png (fewest whole figures showing every graphics byte) and
    <prefix>_REFERENCE_ALL_SPRITES.png (every figure) with their layouts."""
    from . import coloursheet as cs
    palette = set_palette(colours)
    if len(palette) > 16:
        result = []
        for bank, name in enumerate(BANK_NAMES):
            comps = [c for c in col.comps.values() if c['parts'][0]['bank'] == bank]
            if not comps:
                continue
            # Keep each exposed pose paintable. A smaller byte cover can hide individual bits behind other parts.
            full = sorted(comps, key=lambda c: (c['group'], str(c['parts'][0]['id'])))
            rgb16 = cs.palette_rgb(palette[bank * 16:bank * 16 + 16])
            cm = entries(colours)
            for suffix in ('PAINTING_SPRITES', 'REFERENCE_ALL_SPRITES'):
                path = '%s_%s_%s' % (prefix, name, suffix)
                n = cs.write(full, path + '.png', path + '_layout.json', rgb16, cm, unique=False,
                             paint_clear=True, identity=colour_identity(peek))
                layout = path + '_layout.json'
                with open(layout) as f:
                    data = json.load(f)
                data['palette_bank'] = bank
                data['build_palette'] = palette       # --replace uses the palette the sheet was issued with
                with open(layout, 'w') as f:
                    json.dump(data, f)
                result.append((path + '.png', n))
        return result
    rgb16 = cs.palette_rgb(palette)
    colours = entries(colours)                     # the sheets take entries; the palette is set above
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


COLOUR_BANKS = tuple([13] + [14 + n for n in range(NSTORE // 2)])
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/altered_beast_colours.json', 'clear': True, 'palette': True,
            'note': NOTE}


def sheet_palette(palette, layout):
    """A banked sheet can only paint entries belonging to its declared bank."""
    bank = layout.get('palette_bank')
    if bank is None and len(palette) == 16:
        return palette
    if len(palette) != 16 * len(BANK_NAMES) or type(bank) != int or not 0 <= bank < len(BANK_NAMES):
        raise ValueError('painting and build use different sprite banks')
    prefix = '%d:' % bank
    if any(not k.startswith(prefix) for c in layout['composites'] for part in c['parts'] for k in part['keys']):
        raise ValueError('painting contains keys from a different sprite bank')
    return palette[bank * 16:bank * 16 + 16]


def colour_inputs_md5(peek):
    """MD5 of the game bytes the colours belong to: the start state's banks 5 (above the screen), 2, 0, sites
    restored, and the HUD data as the snapshot holds it (the HUD build edits it; it is no sprite graphic)."""
    orig = {a + k: bytes.fromhex(v)[k] for a, v in SITES_ORIG.items() for k in range(3)}
    orig.update({RELOAD + i: v for i, v in enumerate(RELOAD_ORIGINAL)})
    hud = bytes.fromhex(load_profile().get('hud_orig', ''))
    orig.update({HUD_GLYPHS + i: v for i, v in enumerate(hud)})
    h = hashlib.md5()
    h.update(bytes(orig.get(a, peek(a)) for a in range(0x6000, 0x7800)))
    h.update(bytes(orig.get(a, peek(a)) for a in range(0xAC14, 0x10000)))
    return h.hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': RECORD, 'engine': 'altered_beast', 'keys': 'altered_beast-1: %04X graphics byte, bit = stored pixel',
            'inputs': colour_inputs_md5(peek), 'geometry': None}


def nex_peek(nex):
    from .recolour import nex_offsets
    d = bytes(nex)
    off = nex_offsets(d)
    bank = lambda b: d[off[b]:off[b] + 16384]
    ram = {5: bank(5), 2: bank(2), 0: bank(0)}
    return lambda a: ram[5][a - 0x4000] if a < 0x8000 else (ram[2][a - 0x8000] if a < 0xC000 else ram[0][a - 0xC000])


def recolour(nex, cmap):
    from .recolour import nex_offsets, splice
    d = bytearray(nex)
    off = nex_offsets(d)
    need = set(COLOUR_BANKS) | {5, 2, 0, 10, 12}
    if not need <= set(off):
        raise ValueError('not an Altered Beast sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    prof = load_profile()
    peek = nex_peek(nex)
    want = prof.get('colour_inputs')
    if want != colour_inputs_md5(peek):
        raise ValueError('game graphics differ from the expected snapshot (%s, expected %s)' % (colour_inputs_md5(peek), want))
    # Identify the binary independently of the supplied painting, including when pick() probes with {}.
    setup_start = 0x1000
    b10 = bytearray(bank(10))
    enhanced_setup = bytes.fromhex(prof['hooks']['banked_setup'])
    banked = b10[setup_start:setup_start + len(enhanced_setup)] == enhanced_setup
    start = setup_start + len(enhanced_setup)
    loaded = list(b10[start:start + 16 * len(BANK_NAMES)]) if banked else PALETTE
    if banked and 'palette' not in cmap:
        cmap = dict(cmap, palette=loaded)
    if banked != (len(set_palette(cmap)) > 16):
        raise ValueError('painting and build use different numbers of sprite palette banks')
    p0 = AlteredBeastPatch(prof, colours={'palette': loaded})
    for a, old, new in p0.sites:
        installed = bytes(peek(a + k) for k in range(len(new)))
        if a == RELOAD and installed == old:  # published 1.2
            continue
        if installed != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    b12 = bank(12)
    lo, hi = p0.regblock - 0x2000, p0.regblock - 0x2000 + 20
    if b12[:lo] != bytes(p0.page[:lo]) or b12[hi:8192] != bytes(p0.page[hi:8192]):
        raise ValueError('hook code differs from this version\'s (rebuild with nexclash.py auto)')
    setup = bytes.fromhex(prof['hooks']['banked_setup' if banked else 'setup'])
    if bytes(b10[0x1000:0x1000 + len(setup)]) != setup:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    p = AlteredBeastPatch(prof, colours=cmap)
    b10[0x1000 + len(setup):0x1000 + len(setup) + len(loaded)] = bytes(p.palette)
    nb = {b: p.extra_banks[b] for b in COLOUR_BANKS}
    nb[10] = bytes(b10)
    out, changed = splice(nex, nb)
    info = {'banks changed': changed, 'colour-map entries': len(p.colours),
            'palette': "the map's" if 'palette' in cmap else "the game's"}
    if banked:
        info['colour profile'] = 'docs/profiles/altered_beast_enhanced.json'
    return out, info


# ---------------------------------------------------------------------------------------------
# The HUD build: the score panel's text on black. Data only, no code: the panel art and the digit and lives
# glyphs lose their dither dots (a pixel with no horizontal neighbour), in the text's cells only
# ---------------------------------------------------------------------------------------------

PANEL = 0x98BD                   # 18 x 32 lines, copied once at game start by 0x6D1A to screen column 7, line 160
HUD_GLYPHS = 0x6218              # lives: player one 0x6218 + 32 n, player two 0x62B8 + 32 n, 2 x 16 lines (n = 0-4)
HUD_FONT = 0x6358                # digits 0-9, 8 lines each (0x61D8 + 8 * ASCII), printed by 0x5FD3 over the whole cell
HUD_END = HUD_FONT + 80
TEXT_COLS = list(range(0, 7)) + list(range(11, 18))
DIGIT_COLS = list(range(1, 7)) + list(range(11, 17))


def _undot(rows, lo, hi, cols):
    """rows: lines of bytes. In lines lo..hi-1 and these byte columns, clear each pixel with no horizontal neighbour."""
    w = len(rows[0])
    out = [bytearray(r) for r in rows]
    on = lambda y, x: 0 <= x < w * 8 and rows[y][x >> 3] & (0x80 >> (x & 7))
    for y in range(lo, hi):
        for c in cols:
            for k in range(8):
                x = c * 8 + k
                if on(y, x) and not on(y, x - 1) and not on(y, x + 1):
                    out[y][c] &= ~(0x80 >> k)
    return out


def hud_edits(get):
    """{address: new byte} from the snapshot's bytes."""
    ed = {}
    rows = [bytes(get(PANEL + y * 18 + x) for x in range(18)) for y in range(32)]
    new = _undot(rows, 6, 16, TEXT_COLS)
    new = [bytes(r) for r in new]
    new2 = _undot(new, 16, 24, DIGIT_COLS)
    for y in range(32):
        for x in range(18):
            ed[PANEL + y * 18 + x] = new2[y][x]
    for base in [HUD_GLYPHS + 32 * n for n in range(10)]:
        g = [bytes(get(base + 2 * l + k) for k in range(2)) for l in range(16)]
        g2 = _undot(g, 6, 16, [0, 1])
        for l in range(16):
            for k in range(2):
                ed[base + 2 * l + k] = g2[l][k]
    for n in range(10):
        g = [bytes([get(HUD_FONT + 8 * n + l)]) for l in range(8)]
        g2 = _undot(g, 0, 8, [0])
        for l in range(8):
            ed[HUD_FONT + 8 * n + l] = g2[l][0]
    return {a: v for a, v in ed.items() if get(a) != v}


class HudPatch(AlteredBeastPatch):
    name = AlteredBeastPatch.name + ' + HUD text on black (data only)'

    def apply(self, snap):
        get = lambda a: snap.banks[5][a - 0x4000] if a < 0x8000 else snap.banks[2][a - 0x8000]
        ed = hud_edits(get)
        super().apply(snap)
        b5, b2 = bytearray(snap.banks[5]), bytearray(snap.banks[2])
        for a, v in ed.items():
            if a < 0x8000:
                b5[a - 0x4000] = v
            else:
                b2[a - 0x8000] = v
        snap.banks[5], snap.banks[2] = bytes(b5), bytes(b2)
        self.hud_count = len(ed)


def build_hud(z80, out, name, say=print):
    from . import z80tonex as zt
    spr = os.path.join(out, name + '_hud_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=HudPatch())
    bad = boot_check(spr, z80, HudPatch())
    say('HUD build : %s  %s  boot %s' % (os.path.basename(spr), hashlib.md5(open(spr, 'rb').read()).hexdigest(), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    return spr


def hud_lockstep(rzx, z80, extra=None, say=print):
    """The recording replayed twice, without and with the HUD data, every frame's whole 128K compared: the edited
    bytes (the panel until the level build overwrites it), and the HUD's screen lines masked. Also the score digits on
    the screen against the score variables. extra: more pokes (a negative control). -> (frames, differing frames, digit mismatches)."""
    import zlib
    from . import rzx as RZ, z80tonex as zt
    z = zt.Z80Snapshot(z80)
    get = lambda a: z.banks[5][a - 0x4000] if a < 0x8000 else z.banks[2][a - 0x8000]
    ed = hud_edits(get)
    pokes = dict(ed)
    pokes.update(extra or {})

    def where(a):
        return (5, a - 0x4000) if a < 0x8000 else (2, a - 0x8000)
    glyph = [(where(a)) for a in sorted(ed) if a < 0x8000]
    panel = [where(a) for a in sorted(ed) if a >= 0x8000]
    # screen lines 160-191, columns 7-24, as bank 5 offsets
    hudscr = []
    for y in range(160, 192):
        o = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        hudscr.append((o + 7, o + 25))

    def digest(mem, frame):
        d = 0
        for b in range(8):
            buf = bytearray(mem.banks[b])
            if b == 5:
                for lo, hi in hudscr:
                    buf[lo:hi] = bytes(hi - lo)
                for _, o in glyph:
                    buf[o] = 0
            if b == 2 and frame <= 600:
                for _, o in panel:
                    buf[o] = 0
            d = zlib.crc32(buf, d)
        return d
    ref = []

    def f1(frame, mem):
        ref.append(digest(mem, frame))
    RZ._replay(_strip_tmp(rzx), f1)
    st = {'n': 0, 'bad': 0, 'first': None, 'dig': 0, 'seen': set(), 'done': False}
    font = [bytes(ed.get(HUD_FONT + 8 * n + l, get(HUD_FONT + 8 * n + l)) for l in range(8)) for n in range(10)]

    def cell(mem, col):
        out = []
        for l in range(8):
            y = 176 + l
            o = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col
            out.append(mem.banks[5][o])
        return bytes(out)

    def f2(frame, mem):
        if not st['done']:
            for a, v in pokes.items():
                b, o = where(a)
                mem.banks[b][o] = v
            st['done'] = True
        i = st['n']
        st['n'] += 1
        if i < len(ref) and digest(mem, frame) != ref[i]:
            st['bad'] += 1
            if st['first'] is None:
                st['first'] = frame
        b5 = mem.banks[5]
        if frame > 600:
            miss = False
            for var, c0 in ((23346, 8), (23383, 18)):
                v = b5[var - 0x4000] | b5[var - 0x4000 + 1] << 8
                st['seen'].add((c0, v))
                ds = [(v // 10 ** k) % 10 for k in (4, 3, 2, 1, 0)]
                cells = [cell(mem, c0 + k) for k in range(5)]
                if cells == [font[d] for d in ds]:
                    continue
                # a player out of lives: 0x668A flashes the game's own message blocks over his score cells, 0x66C7
                # prints the credit digit (30402) at the last of them. Exactly those bytes, nothing else, pass
                last = font[b5[30402 - 0x4000] % 10] if c0 == 8 else None
                msg = [[bytes(b5[a + l * w + k - 0x4000] for l in range(8)) for k in range(5)] for a, w in ((0x6C80, 6), (0x6CB0, 5))]
                if b5[30403 - 0x4000] and any(cells[:4] == m[:4] and cells[4] in (m[4], last) for m in msg):
                    st['msg'] = st.get('msg', 0) + 1
                    continue
                miss = True
            st['run'] = st.get('run', 0) + 1 if miss else 0
            st['dig'] = max(st['dig'], st['run'])
    try:
        RZ._replay(_strip_tmp(rzx), f2)
    except Exception as e:
        say('            %s: replay stopped: %s' % (os.path.basename(rzx), e))
        st['bad'] += 1
    st_msg[0] = st.get('msg', 0)
    return st['n'], st['bad'], st['first'], st['dig'], st['seen']


st_msg = [0]


def _strip_tmp(path):
    return path


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.altered_beast', description='Altered Beast figure colours and negative controls')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> the two sheets (+ layouts; game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('-o', '--output', default='altered_beast')
    p.add_argument('--stop', type=int)
    p.add_argument('--enhanced', action='store_true', help='one independently paintable sheet per palette bank')
    p.add_argument('--z80', required=True, help='the snapshot: the sheet identity comes from its start state, as the .nex holds it')
    p = sub.add_parser('hud', help='the labelled HUD build (+ its lockstep over recordings)')
    p.add_argument('--z80', required=True)
    p.add_argument('-o', '--output', required=True)
    p.add_argument('--rzx', nargs='*', default=[])
    p = sub.add_parser('negatives', help='broken builds on a recording')
    p.add_argument('rzx')
    p.add_argument('--stop', type=int, default=1500)
    p.add_argument('--rzx2', help='recording with two players (the player-two control)')
    p.add_argument('--rzx3', help='recording to the end of the level (the level-end control)')
    a = ap.parse_args(argv)
    if a.cmd == 'sheet':
        from . import z80tonex as zt
        col, mem = capture(a.rzx, a.stop, banked=a.enhanced)
        z = zt.Z80Snapshot(a.z80)
        peek = lambda x: z.banks[5][x - 0x4000] if x < 0x8000 else (z.banks[2][x - 0x8000] if x < 0xC000 else z.banks[0][x - 0xC000])
        for png, n in sheets(col, a.output, peek, load_colours(ENHANCED) if a.enhanced else load_colours_build()):
            print('%s figures -> %s' % (n, png))
    elif a.cmd == 'hud':
        build_hud(a.z80, a.output, 'altered_beast')
        for r in a.rzx:
            n, b, first, dig, seen = hud_lockstep(r, a.z80)
            sc1 = max(v for c, v in seen if c == 8)
            sc2 = max(v for c, v in seen if c == 18)
            print('Lockstep  : %s  %d frames, %d differ (first %s); score digits lag the variables by at most %d frames; '
                  'message-block frames %d; highest P1 %d, P2 %d' % (os.path.basename(r), n, b, first, dig, st_msg[0], sc1, sc2))
        if a.rzx:
            n, b, first, dig, seen = hud_lockstep(a.rzx[0], a.z80, extra={0x6905: 0x55})
            print('Negative  : a poke into the mask table: %d frames differ -> %s' % (b, 'DETECTED' if b else 'NOT DETECTED'))
            n, b, first, dig, seen = hud_lockstep(a.rzx[-1], a.z80, extra={HUD_FONT + 3: 0xFF})
            print('Negative  : a wrong byte in digit 0: digits wrong for %d frames -> %s' % (dig, 'DETECTED' if dig > 2 else 'NOT DETECTED'))
            n, b, first, dig, seen = hud_lockstep(a.rzx[-1], a.z80, extra={0x6C80 + 8: 0xFF})
            print('Negative  : a wrong byte in the message block: lockstep %d frames differ -> %s' % (b, 'DETECTED' if b else 'NOT DETECTED'))
    else:
        n, d = run_negatives(a.rzx, a.stop, rzx2=a.rzx2, rzx3=a.rzx3)
        print('Negative controls: %d/%d DETECTED' % (d, n))


if __name__ == '__main__':
    _main()
