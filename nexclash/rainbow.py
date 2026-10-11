"""Rainbow Islands (128K) engine: every figure drawn by the game's sprite-list walker becomes Next
hardware sprites (engine 'rainbow'). Additive module: reachable only through identify_rb().

Game facts (verified by the 128K analysis passes over Dean's two recordings):
  renderer 58851 re-blits the whole 176-line play area from a back buffer (0x9F00) every game frame,
  then the list walker 59504 (list IY=0x6D3C, descriptors 0xB800+code-6, dispatch 59539 JP (IX))
  draws each piece (<= 24 x 8 px, one char-row band) with unrolled masked AND/OR plotters that all
  end with JP 59543. Erase = the next frame's blit. No game logic reads screen pixels.
  The walker runs with interrupts disabled and SP pointing into graphics data.
Hooks: alt ROM stubs at 0x386E map Next RAM page 26 at slot 0, which holds the hook bodies, state,
canvases and tables (asm/rainbow_hooks.asm). Each piece is drawn by the ORIGINAL plotter twice
into canvases (0x00 -> ink, 0xFF -> mask|ink); columns E-2..E+5 become four 4-bit patterns shown as
sprites 4n..4n+3 (empty ones hidden); the render end (59087) hides the sprites left over from the previous frame. The walker is called
once per 8-line band from inside the blit, so the piece counter is reset at render start (58851).
"""
import collections
import json
import os

PAGE_S = 26                 # Next RAM page (bank 13 lower half): hook bodies, state, tables
PAGE_T = 27                 # plotter layout tables (bank 13 upper half), slot 1 while converting
PAGE_C1, PAGE_C2 = 28, 29   # canvas page 29 (bank 14) over the screen for the register run
STORE_PG, STORE_PAGES = 32, 32   # pattern store: Next pages 32-63 (256K), slot 1 during lookup
ALT_PAGE = 24               # alt ROM copy source (bank 12), as for the other altrom builds
ROM_ORG = 0x386E
PAGE_ORG = 0x0100
NIBTAB, CLASSTAB, MIRTAB, PI = 0x1000, 0x1200, 0x0F00, 0x1300     # asm: same names
CODE_END_MAX = 0x0D00       # WBG conversion buffer starts here
V_S, V_FRM, V_HITS = 0x00, 0x24, 0x2A
NSPR_MAX = 128
TAIL_ADDR = 0x9F00          # back buffer: write-first in both of Dean's recordings
MAXP = 32
SITES_ORIG = {58851: bytes.fromhex('FD213C6D'), 59539: bytes.fromhex('26F5DDE9'),
              59543: bytes.fromhex('A7C279E8'), 59087: bytes.fromhex('3AE2E5'),
              65172: bytes.fromhex('3A80BE'), 65274: bytes.fromhex('F1FBC9'),   # IM2 handler
              65029: bytes.fromhex('CD925C'), 65076: bytes.fromhex('CD5B5C'),   # main loop: sprites off
              60853: bytes.fromhex('876F2600'), 60839: bytes.fromhex('3D6F2600'),  # cell drawer: base tile,
              60965: bytes.fromhex('3D878787'),                                     # full overlay, masked item
              59547: bytes.fromhex('2A82E8')}                                       # walker: band done
CLIST, ATTRB, V_NP = 0x1B00, 0x1C80, 0x01
V_TICK, LIMIT = 0x2E, 3     # frame limiter (asm s_lim)
# Collectables (2026-10-11): item cells of the back buffer (cell drawer 60633..60965) become sprites.
# Shadow map in page 27 (slot 1): CODES = item code per cell (0 none, FF several objects -> ULA),
# BATTR = base tile colour (bit 7 = known). Cell index = 32*k + col, back-buffer cell 0x9F00+256k+col.
CODES, BATTR, NCELLS, RCNT = 0x3000, 0x3300, 704, 0x3D00
EXP, V_NI, V_IP, V_FMAX = 0x1F00, 0x3B, 0x3C, 0x51
ILIST, IMAX, IPAGE = 0x3600, 80, 28   # item list (page 27, 16 bytes each), max items, pattern cache page
CODE2 = 0x1F20              # second page-26 code block (item commit), up to 0x1FFF
ITEM_PAL = 15               # sprite palette offset of the item sprites: Spectrum ink colours
ITEM_SITES = {60853: 60857, 60839: 60843, 60965: 60969}      # hook site -> resume address
ITEM_GFX = 0xF600           # (mask, gfx) pairs, 16 bytes per code: 0xF600 + ((code-1)*16 & 255)
# Spectrum ink colours (Next default ULA palette levels): normal 1-7, bright 1-7 (RRRGGGBB)
SPECTRUM_INK = (0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6)
SPECTRUM_INK_BRIGHT = (0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF)
SIG = None                  # walker head bytes: profile 'signature'

# 4-wide zig-zag plotters entered on a leftward row write columns E-3..E (every other dispatch target
# writes within E-2..E+5): the hook shifts their window one byte left (asm s_pc, V_OFF). Found from
# Dean's hardware video of the Insect Island boss (2026-09-29); neither verified RZX reaches them.
LEFT4 = (59906, 59951, 59996, 60041)


def window_off(ix):
    """Window start = E - window_off(ix); the window is 8 bytes (4 sprites)."""
    return 3 if ix in LEFT4 else 2


def plotter_extents(peek):
    """Column extent (lo, hi) relative to E of every dispatch target in the 0xF300 table, measured
    by running the ORIGINAL plotter from a mid-screen address with both AF' carry values."""
    from skoolkit.simulator import Simulator
    base = bytearray(peek[a] for a in range(65536))
    targets = sorted({base[a] | base[a + 1] << 8 for a in range(0xF300, 0xF400, 2)})
    ext = {}
    for t in targets:
        if not 59567 <= t < 60200:              # table words that are not plotter code
            continue
        cols = set()

        class W(list):                          # records every write address
            def __setitem__(s, a, v):
                s.w.add(a)
                list.__setitem__(s, a, v)
        for cy in (0, 1):
            m = W(base)
            m.w = set()
            sim = Simulator(m, {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
            R = sim.registers
            R[16], R[17] = 0, cy
            if not _run(sim, (59543,), 5000):
                raise ValueError('plotter %d did not return' % t)
            cols |= {(a & 31) - 8 for a in m.w if 0x4000 <= a < 0x5800}
        ext[t] = (min(cols), max(cols))
    return ext


def plotter_layouts(peek):
    """For every plotter entry: window offset (off = -leftmost column), sprites (nspr = columns/2
    rounded up), stream length per AF' carry, and a layout table per carry: one byte per stream
    byte = target row*6 + column in the window (bits 5-0), bit 6 = mirrored (table page 245),
    bit 7 = mask byte. Derived by running the ORIGINAL plotter with single-bit streams."""
    from skoolkit.simulator import Simulator
    base = bytearray(peek[a] for a in range(65536))
    ext = plotter_extents(peek)
    lens = plotter_stream_lengths(peek)
    out = {}

    def run(t, cy, stream, fill):
        m = bytearray(base)
        m[0x4000:0x5800] = bytes([fill]) * 0x1800
        m[0x8000:0x8000 + len(stream)] = stream
        sim = Simulator(m, {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
        sim.registers[17] = cy
        if not _run(sim, (59543,), 5000):
            raise ValueError('plotter %d did not return' % t)
        return m
    for t, (lo, hi) in ext.items():
        if t not in lens:
            continue
        off, nspr = -lo, (hi - lo + 2) // 2
        lay = []
        for cy in (0, 1):
            n = lens[t][cy]
            b0, bf = run(t, cy, bytes(n), 0), run(t, cy, bytes(n), 0xFF)
            tb = bytearray()
            for j in range(n):
                st = bytearray(n)
                st[j] = 1
                m0, mf = run(t, cy, st, 0), run(t, cy, st, 0xFF)
                d0 = [a for a in range(0x4000, 0x5800) if m0[a] != b0[a]]
                df = [a for a in range(0x4000, 0x5800) if mf[a] != bf[a]]
                if d0:
                    role, (a,), v = 0, d0, m0[d0[0]]
                elif df:
                    role, (a,), v = 1, df, mf[df[0]] ^ bf[df[0]]
                else:
                    raise ValueError('plotter %d byte %d has no effect' % (t, j))
                if v not in (1, 0x80):
                    raise ValueError('plotter %d byte %d: value %02X' % (t, j, v))
                row, col = (a >> 8) - 0x48, (a & 31) - 8 + off
                if not (0 <= row <= 9 and 0 <= col < 2 * nspr):
                    raise ValueError('plotter %d byte %d outside window (%d, %d)' % (t, j, row, col))
                tb.append((row * 6 + col) | (0x40 if v == 0x80 else 0) | (role << 7))
            lay.append(bytes(tb))
        if max(lens[t]) > 256 - 64 * nspr - 8:
            raise ValueError('plotter %d stream too long for its store entry' % t)
        out[t] = {'off': off, 'nspr': nspr, 'len': lens[t], 'layout': [x.hex() for x in lay]}
    return out


def layout_convert(info, cy, stream, row0=0):
    """Python model of the hook's direct conversion -> (G, MG) as {(row, col): byte}."""
    G, M = {}, {}
    rev = [int('{:08b}'.format(i)[::-1], 2) for i in range(256)]
    for j, tb in enumerate(bytes.fromhex(info['layout'][cy])):
        v = stream[j]
        if tb & 0x40:
            v = rev[v]
        k = divmod(tb & 0x3F, 6)
        if tb & 0x80:
            M[k] = M.get(k, 0xFF) & 0 | v | G.get(k, 0)
        else:
            G[k] = v
            M[k] = M.get(k, 0xFF) | v
    return G, M


def plotter_stream_lengths(peek):
    """Graphics stream bytes consumed by every plotter entry (SP advance), AF' carry clear / set."""
    from skoolkit.simulator import Simulator
    base = bytearray(peek[a] for a in range(65536))
    out = {}
    for t in sorted({base[a] | base[a + 1] << 8 for a in range(0xF300, 0xF400, 2)}):
        if not 59567 <= t < 60176:
            continue
        ln = []
        for cy in (0, 1):
            sim = Simulator(bytearray(base), {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
            sim.registers[17] = cy
            if not _run(sim, (59543,), 5000):
                raise ValueError('plotter %d did not return' % t)
            ln.append(sim.registers[12] - 0x8000)
        out[t] = ln
    return out


COLOURS = {'white': 0xFF, 'black': 0x00, 'blue': 0x03, 'transparent': None}

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'rainbow_islands.json'),
              os.path.join(_HERE, 'rainbow_islands.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('rainbow_islands.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def colour(v):
    """'white' | 'black' | 'blue' | 'transparent' | '#RRGGBB' -> RRRGGGBB byte (None = transparent)."""
    v = v.strip().lower()
    if v in COLOURS:
        return COLOURS[v]
    if v.startswith('#') and len(v) == 7:
        r, g, b = int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)
        return (r >> 5) << 5 | (g >> 5) << 2 | (b >> 6)
    raise ValueError('unknown colour %r (white, black, blue, transparent or #RRGGBB)' % v)


class Config:
    """Colour selection. ink/outline apply to palette offset 0 (and every class without its own
    entry); class_colours = {'pages': {'D6': 1, ...}, 'palettes': {'1': {'ink': .., 'outline': ..}}}
    maps graphics-address high bytes to palette offsets 1-15 (the per-class hook; off by default)."""

    def __init__(self, ink='white', outline='black', class_colours=None):
        self.ink, self.outline = colour(ink), colour(outline)
        if self.ink is None:
            raise ValueError('ink cannot be transparent')
        self.cls = class_colours or {'pages': {}, 'palettes': {}}
        self.transparent_outline = self.outline is None
        for k, p in self.cls.get('palettes', {}).items():
            if 'outline' in p and (colour(p['outline']) is None) != self.transparent_outline:
                raise ValueError('outline transparency must be the same for every class (one table)')

    def nibtab(self):
        """(G nibble << 4 | MG nibble) -> 2 bytes of 4-bit pixels: 1 ink, 0 transparent, 2 outline."""
        out = 0 if self.transparent_outline else 2
        t = bytearray(512)
        for i in range(256):
            g, m = i >> 4, i & 15
            px = []
            for b in (8, 4, 2, 1):
                px.append(1 if g & b else (0 if m & b else out))
            t[i] = px[0] << 4 | px[1]
            t[256 + i] = px[2] << 4 | px[3]
        return bytes(t)

    def classtab(self):
        t = bytearray(256)
        for page, off in self.cls.get('pages', {}).items():
            off = int(off)
            if not 0 <= off <= 14:
                raise ValueError('palette offset must be 0-14 (15 = item sprites)')
            t[int(page, 16)] = off << 4
        return bytes(t)

    def palette(self):
        pal = bytearray(256)
        for k in range(16):
            p = self.cls.get('palettes', {}).get(str(k), {})
            ink = colour(p['ink']) if 'ink' in p else self.ink
            outl = colour(p['outline']) if 'outline' in p else self.outline
            pal[16 * k + 1] = ink
            pal[16 * k + 2] = 0 if outl is None else outl
        b = 16 * ITEM_PAL                       # item sprites: 1 black (outline / black ink),
        pal[b + 1] = 0x00                       # 2-8 ink 1-7, 9-15 bright ink 1-7
        pal[b + 2:b + 9] = bytes(SPECTRUM_INK)
        pal[b + 9:b + 16] = bytes(SPECTRUM_INK_BRIGHT)
        return bytes(pal)


def identify_rb(mem):
    """mem: 64K view with bank 0 at C000. True if the Rainbow Islands list walker is present."""
    sg = load_profile()['signature']
    a, sig = sg['addr'], bytes.fromhex(sg['bytes'])
    return bytes(mem[a:a + len(sig)]) == sig


class RainbowPatch:
    name = 'Rainbow Islands sprite-list walker -> hardware sprites (altrom + RAM page 26)'

    def __init__(self, cfg=None, prof=None):
        self.cfg = cfg or Config()
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.page_code = bytes.fromhex(h['page'])
        self.page_code2 = bytes.fromhex(h.get('page2', ''))
        self.setup = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = self.setup + self.cfg.palette()
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 64
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM stubs too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)                     # alt ROM image of 0x2000-0x3FFF (for nextboot)
        sp = bytearray(8192)
        sp[PAGE_ORG:PAGE_ORG + len(self.page_code)] = self.page_code
        if CODE2 + len(self.page_code2) > 0x2000:
            raise ValueError('second code block too long')
        sp[CODE2:CODE2 + len(self.page_code2)] = self.page_code2
        if PAGE_ORG + len(self.page_code) > CODE_END_MAX or ATTRB + 5 * NSPR_MAX > EXP:
            raise ValueError('page code overlaps the conversion buffers')
        sp[V_FRM] = 1
        sp[V_FMAX] = NSPR_MAX                       # figure sprite limit (render start: 128 - items)
        tp = bytearray(8192)                        # page 27: layout tables (slot 1 = 0x2000)
        at = 0
        self.plot = {int(k): v for k, v in self.prof['plotters'].items()}
        for t, pi in sorted(self.plot.items()):
            sp[PI + (t & 255)] = t >> 8
            sp[PI + 0x100 + (t & 255)] = pi['off'] | pi['nspr'] << 4
            for cy in (0, 1):
                lay = bytes.fromhex(pi['layout'][cy])
                sp[PI + 0x200 + 0x100 * cy + (t & 255)] = len(lay)
                a = 0x2000 + at
                sp[PI + 0x400 + 0x200 * cy + (t & 255)] = a & 255
                sp[PI + 0x500 + 0x200 * cy + (t & 255)] = a >> 8
                tp[at:at + len(lay)] = lay
                at += len(lay)
        if at > CODES - 0x2000:
            raise ValueError('layout tables overlap the item shadow map in page 27')
        sp[MIRTAB:MIRTAB + 256] = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))
        sp[NIBTAB:NIBTAB + 512] = self.cfg.nibtab()
        sp[CLASSTAB:CLASSTAB + 256] = self.cfg.classtab()
        for n in range(16):                         # item patterns: nibble -> 2 bytes, F per set bit
            sp[EXP + 2 * n] = (0xF0 if n & 8 else 0) | (0x0F if n & 4 else 0)
            sp[EXP + 2 * n + 1] = (0xF0 if n & 2 else 0) | (0x0F if n & 1 else 0)
        self.scratch = bytes(sp)
        self.tpage = bytes(tp)
        self.extra_banks = {12: self.page + bytes(8192), 13: self.scratch + self.tpage}
        s = self.syms
        self.sites = [(58851, SITES_ORIG[58851], b'\xC3' + s['e_rs'].to_bytes(2, 'little') + b'\x00'),
                      (59539, SITES_ORIG[59539], b'\xC3' + s['e_pc'].to_bytes(2, 'little') + b'\x00'),
                      (59543, SITES_ORIG[59543], b'\xC3' + s['e_af'].to_bytes(2, 'little') + b'\x00'),
                      (59087, SITES_ORIG[59087], b'\xC3' + s['e_re'].to_bytes(2, 'little')),
                      (65172, SITES_ORIG[65172], b'\xC3' + s['e_lim'].to_bytes(2, 'little')),
                      (65274, SITES_ORIG[65274], b'\xC3' + s['e_hx'].to_bytes(2, 'little')),
                      (65029, SITES_ORIG[65029], b'\xCD' + s['e_off2'].to_bytes(2, 'little')),
                      (65076, SITES_ORIG[65076], b'\xCD' + s['e_off1'].to_bytes(2, 'little')),
                      (60853, SITES_ORIG[60853], b'\xC3' + s['e_bt'].to_bytes(2, 'little') + b'\x00'),
                      (60839, SITES_ORIG[60839], b'\xC3' + s['e_ov'].to_bytes(2, 'little') + b'\x00'),
                      (60965, SITES_ORIG[60965], b'\xC3' + s['e_it'].to_bytes(2, 'little')),
                      (59547, SITES_ORIG[59547], b'\xC3' + s['e_bend'].to_bytes(2, 'little'))]

    def check_sites(self, bank0):
        for a, old, new in self.sites:
            cur = bytes(bank0[a - 0xC000:a - 0xC000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def patched_bank0(self, bank0):
        self.check_sites(bank0)
        b = bytearray(bank0)
        for a, old, new in self.sites:
            b[a - 0xC000:a - 0xC000 + len(new)] = new
        return bytes(b)

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('Rainbow Islands patch needs the 128K snapshot')
        if snap.port7ffd & 0x10 == 0:
            raise ValueError('snapshot selects ROM 0; the hooks need the 48K ROM (alt image 1)')
        snap.banks[0] = self.patched_bank0(snap.banks[0])


# ---------------------------------------------------------------------------------------------
# Boot check (128K): simulated Next boot of the built .nex against the patched snapshot
# ---------------------------------------------------------------------------------------------

def boot_check(nex, z80, patch=None, tail=None):
    import copy
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = nextboot.boot(nex, s.pc)
    R, mem, bad = st['R'], st['mem'], list(st['bad'])
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
    top = s.port7ffd & 7
    ram = s.banks[5] + s.banks[2] + s.banks[top]
    t0, t1 = tail if tail else (TAIL_ADDR, TAIL_ADDR + 80)
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not t0 <= a < t1]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    img = bytearray(rom48())
    if patch is not None:
        lo, hi = patch.altrom
        img[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
        regs = zt.build_tail(s, 0x8000, patch.slot1, True)[3]
        img[patch.regblock:patch.regblock + len(regs)] = regs
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
    view = bytes(mem[a] for a in range(0x4000))
    if view != bytes(img):
        d = [a for a in range(0x4000) if view[a] != img[a]]
        bad.append(('slots 0/1 differ from the expected ROM image', len(d), d[:6]))
    if st['p7ffd'] != s.port7ffd or not st['p1ffd'] & 4:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 2 * top, 2 * top + 1]:
        bad.append(('MMU', st['mmu']))
    if patch is not None and st['nr'].get(0x15) != 1:
        bad.append(('sprites not enabled by setup', st['nr'].get(0x15)))
    if isinstance(patch, RainbowPatch):         # Rainbow writes only the top 64 bytes of each pattern;
        z = setup_zeroes_patterns(patch)        # other engines (Wally) upload full patterns
        if z:
            bad.append(('setup', z))
    return bad


# ---------------------------------------------------------------------------------------------
# Differential verification against an RZX (Python simulator, 128K)
# ---------------------------------------------------------------------------------------------

CMP = list(range(0, 13)) + [14] + list(range(18, 25)) + [26, 27, 28]   # all but R, T, MEMPTR, AF'


class NextState:
    """Next-side state the patched code sees: page 26, NextRegs, sprite attributes, pattern RAM."""

    def __init__(self, patch):
        self.scratch = bytearray(patch.scratch)
        self.no_swapnib = getattr(patch, 'no_swapnib', False)     # negative control only
        self.pages = collections.defaultdict(lambda: bytearray(8192))
        self.pages[PAGE_T] = bytearray(getattr(patch, 'tpage', bytes(8192)))
        self.nr = {0x50: 0xFF, 0x51: 0xFF, 0x07: 0, 0x52: 10, 0x53: 11}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.pat_writes = 0
        self.sel = 0
        self.events = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def out(self, port, val):
        if port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
            self.pat_writes += 1
        else:
            self.events.append(('port', port, val))

    def sprite_pixels(self, i):
        """Visible 4-bit anchor sprite i -> list of (x, y, index) in ULA coordinates, else None."""
        a0, a1, a2, a3, a4 = self.attr[i]
        if not a3 & 0x80:
            return None
        x = a0 + (a2 & 1) * 256 - 32
        y = a1 + (a4 & 1) * 256 - 32
        base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
        out = []
        for j in range(16):
            for k in range(16):
                b = self.pat[base + j * 8 + k // 2]
                out.append((x + k, y + j, (b >> 4) if k % 2 == 0 else (b & 15)))
        return out


def staged(ns, first):
    """A copy of ns in which sprites first..V_S-1 show what the render-end commit will write:
    attributes from ATTRB, patterns from the piece's store entry (V_EPG / V_ENT+1 / V_NS)."""
    import copy
    t = copy.copy(ns)
    t.attr = [list(a) for a in ns.attr]
    t.pat = bytearray(ns.pat)
    n = ns.scratch[V_S] - first
    if n <= 0:
        return t
    pg, hi, nspr = ns.scratch[0x28], ns.scratch[0x27], ns.scratch[0x21]
    ent = ns.pages[pg][(hi - 0x20) * 256:(hi - 0x20) * 256 + 256]
    for k in range(n):
        i = first + k
        t.attr[i] = list(ns.scratch[ATTRB + 5 * i:ATTRB + 5 * i + 5])
        b = (i >> 1) * 256 + (i & 1) * 128
        t.pat[b:b + 64] = ent[256 - 64 * nspr + 64 * k:256 - 64 * nspr + 64 * k + 64]
    return t


class ItemShadow:
    """Python model of the item shadow map kept by the hooks at 60853 / 60839 / 60965 (page 27)."""

    def __init__(self):
        self.codes = bytearray(NCELLS)
        self.battr = bytearray(NCELLS)

    @staticmethod
    def cell(d, e):
        return (d - 0x9F) * 32 + e if 0x9F <= d <= 0xB4 and e < 32 else None

    def event(self, pc, a, d, e, iy, peek):
        """60853 base tile (A = tile): no item, colour = (0xF200 + (tile|128)) & 127.
        60839 full tile (A = code): code 1-14 = an item drawn opaque (0xF700 + 8*(code-1)), else
        another overlay (no item); colour: a spawned item (IY != 60699) keeps the cell's colour
        before it (attribute buffer), a composed cell's is unknown (the cell is blank anyway).
        60965 masked item (A = code 1-14): first item in the cell; a spawned one (IY != 60720)
        takes the attribute buffer as its cell colour; a second, different object -> FF (ULA)."""
        i = self.cell(d, e)
        if i is None:
            return None
        if pc == 60853:
            self.codes[i], self.battr[i] = 0, (peek(0xF200 | a | 128) & 127) | 128
        elif pc == 60839:
            item = 1 <= a <= 14
            self.codes[i] = a if item else 0
            self.battr[i] = peek(0xB500 + i) | 128 if item and iy != 60699 else 0
        elif not 1 <= a <= 14 or self.codes[i] not in (0, a):
            self.codes[i] = 0xFF
        elif self.codes[i] == 0:
            self.codes[i] = a
            if iy != 60720:
                self.battr[i] = peek(0xB500 + i) | 128
        return i

    def rcnt(self):
        return bytes(sum(1 for c in self.codes[32 * k:32 * k + 32] if c) for k in range(22))

    def same_as(self, page27):
        o = CODES - 0x2000
        r = RCNT - 0x2000
        return bytes(page27[o:o + NCELLS]) == bytes(self.codes) and \
            bytes(page27[o + BATTR - CODES:o + BATTR - CODES + NCELLS]) == bytes(self.battr) and \
            bytes(page27[r:r + 22]) == self.rcnt()


def item_index(attr):
    """Item ink pixel index from the cell's attribute-buffer byte: 1 black, 2-8 ink, 9-15 bright ink."""
    ink = attr & 7
    return 1 if ink == 0 else ink + 1 + (7 if attr & 64 else 0)


def item_pattern(peek, code, ink, vis):
    """64 bytes (rows 0-7 of a 4-bit pattern): gfx bit -> ink, mask 0 -> 1 (outline), else 0;
    rows not in vis are transparent."""
    g = ITEM_GFX | (((code - 1) * 16) & 255)
    out = bytearray(64)
    for j in range(8):
        if j not in vis:
            continue
        m, gf = peek(g + 2 * j), peek(g + 2 * j + 1)
        for x in range(8):
            b = 0x80 >> x
            v = ink if gf & b else (0 if m & b else 1)
            out[8 * j + x // 2] |= v << (0 if x & 1 else 4)
    return bytes(out)


def items_list(peek, shadow):
    """Render start (asm ibuild): every item cell with rows in the play area, in cell order, at most
    IMAX: dict(idx, code, col, y0 (screen row of pattern row 0), vis (rows on screen), g (gfx
    address), arow (screen char row of its attribute, None = not fixed), base, abuf, pattern)."""
    s, N = peek(48782), peek(58850)
    out = []
    for i in range(NCELLS):
        code = shadow.codes[i]
        if code in (0, 0xFF):
            continue
        if len(out) >= IMAX:
            break
        k, col = i >> 5, i & 31
        yu = 8 * k - s
        if yu < 0:
            yu += 176
        ys = yu - 176 if yu >= 168 else yu
        vis = [j for j in range(8) if (yu + j - 176 if yu + j >= 176 else yu + j) < N]
        if not vis:
            continue
        kk = (k - (s >> 3)) % 22
        b = shadow.battr[i]
        arow = kk + 2 if kk * 8 < N and b & 128 else None
        out.append({'idx': i, 'code': code, 'col': col, 'y0': (16 + ys) & 255, 'vis': vis,
                    'g': ITEM_GFX | (((code - 1) * 16) & 255), 'arow': arow, 'base': b & 127 if arow else 0,
                    'abuf': 0xB500 + i, 'ink': item_index(peek(0xB500 + i)),
                    'pattern': item_pattern(peek, code, item_index(peek(0xB500 + i)), vis)})
    return out


def item_record(it):
    """The ILIST record of an item (asm ibrec), byte 11 (pattern cache entry) as 0: the entry is
    checked through the pattern it holds."""
    rows = [(it['y0'] + j) >> 3 for j in it['vis']]
    y = it['y0'] + it['vis'][0]
    a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | it['col']
    return bytes([it['col'], it['y0'], sum(0x80 >> j for j in it['vis']), it['g'] & 255,
                  0xFF if it['arow'] is None else it['arow'], it['base'], it['abuf'] & 255, it['abuf'] >> 8,
                  rows[0], rows[-1], it['ink'], 0, a & 255, a >> 8, it['vis'][0], len(it['vis'])])


def record_ok(rec, it, page28):
    """Record (16 bytes from page 27) = model, and its pattern cache entry holds the item's pattern."""
    e = rec[11]
    want = item_record(it)
    return bytes(rec[:11]) == want[:11] and bytes(rec[12:16]) == want[12:16] and e < 128 and \
        bytes(page28[64 * e:64 * e + 64]) == it['pattern']


def items_fix(peek, items, row=None):
    """Screen writes of asm ifix: item rows (on screen char row `row`, or all) -> screen AND mask AND
    NOT gfx; attribute (on that char row) -> base colour while the screen shows the buffer value."""
    w = {}
    for it in items:
        for j in it['vis']:
            y = it['y0'] + j
            if row is not None and y >> 3 != row:
                continue
            a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | it['col']
            w[a] = w.get(a, peek(a)) & peek(it['g'] + 2 * j) & ~peek(it['g'] + 2 * j + 1) & 255
        r = it['arow']
        if r is not None and (row is None or r == row):
            a = 0x5800 + 32 * r + it['col']
            if w.get(a, peek(a)) == peek(it['abuf']):
                w[a] = it['base']
    return w


def item_patterns(entries, n):
    """Pattern numbers of the item sprites (asm items): each cache entry gets the next pattern
    after the figures' n on its first use this render; items with the same entry share it."""
    pm, out = {}, []
    for e in entries:
        if e not in pm:
            pm[e] = n + len(pm)
        out.append(pm[e])
    return out


def item_attrs(it, j, p):
    """Sprite attributes 0-4 of item sprite j with 4-bit pattern p (asm items)."""
    x = it['col'] * 8 + 32
    return [x & 255, (it['y0'] + 32) & 255, ITEM_PAL << 4 | x >> 8, 0xC0 | p >> 1, 0x80 | (p & 1) << 6]


def piece_plan(patch, ix, s_before, fmax=NSPR_MAX):
    """What the hook does with a piece: ('star' | 'ula' | 'sprites', nspr). fmax = 128 - item sprites."""
    if ix in (60176, 60180):
        return 'star', 0
    pi = patch.plot.get(ix)
    if pi is None or s_before + pi['nspr'] > fmax:
        return 'ula', 0
    return 'sprites', pi['nspr']


def _swapnib(R):
    """Z80N SWAPNIB (ED 23, 8 T): swap the nibbles of A; flags unchanged. SkoolKit would run it as a
    silent 2-byte NOP (NEXT_REGISTERS.md), so every simulator that runs the hooks installs this."""
    from skoolkit.simulator import R2
    R[0] = ((R[0] << 4) | (R[0] >> 4)) & 0xFF
    R[15] = R2[R[15]]
    R[25] += 8
    R[24] = (R[24] + 2) % 65536


def swapnib_selftest():
    """Run ED 23 for every A through the simulator hook: A swapped, F kept, PC += 2, T += 8."""
    from skoolkit.simulator import Simulator
    bad = 0
    for a in range(256):
        m = bytearray(65536)
        m[0x8000:0x8002] = b'\xED\x23'
        sim = Simulator(m, {'PC': 0x8000, 'A': a, 'F': a ^ 0x5A})
        sim.after_ED[0x23] = lambda R=sim.registers: _swapnib(R)
        t0 = sim.registers[25]
        sim.opcodes[0xED]()
        R = sim.registers
        bad += R[0] != ((a & 15) << 4 | a >> 4) or R[1] != a ^ 0x5A or R[24] != 0x8002 or R[25] - t0 != 8
    return bad


def setup_zeroes_patterns(patch):
    """Run the setup routine (0xD000) with pattern RAM full of garbage: all 16K must end zero,
    because the piece hook writes only the top 64 bytes of each 4-bit pattern."""
    import random
    from skoolkit.simulator import Simulator
    m = bytearray(65536)
    m[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra
    m[0x8000:0x8003] = b'\xCD\x00\xD0'
    ns = NextState(patch)
    rnd = random.Random(1)
    ns.pat[:] = bytes(rnd.randrange(256) for _ in range(16384))
    sim = _machine(Simulator, m, Simulator(m, {'PC': 0x8000, 'SP': 0x7FF0}).registers[:], ns)
    if not _run(sim, (0x8003,), 2000000):
        return 'setup did not return'
    nz = sum(1 for b in ns.pat if b)
    return 'pattern RAM not zeroed (%d bytes)' % nz if nz else None


def _machine(Sim, mem, regs, ns):
    sim = Sim(mem, {})
    sim.registers[:] = regs
    R, ed = sim.registers, sim.after_ED
    from skoolkit.simulator import R2

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na
    if not getattr(ns, 'no_swapnib', False):
        ed[0x23] = lambda: _swapnib(R)

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stops, limit=200000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[24] not in stops:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


def verify(patch, rzx_path, progress=None, stop=None):
    """Replay the RZX (original game). At every walker event run the original and the patched code
    from the same state and compare. Returns a Counter of results (keys ending in '!' = failures)."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    from .dizzy6 import _rw_simulator
    MG, MS = Memory.__getitem__, Memory.__setitem__
    Sim = _rw_simulator()
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = bytearray(16384)
    from .build import rom48
    alt[:] = rom48()
    alt[0x2000:0x4000] = patch.page
    psite = {}
    for a, old, new in patch.sites:
        for k, v in enumerate(new):
            psite[a + k] = v
    site_bytes = set(psite)
    st = {'sim': None, 'frame': 0, 'afp': None, 'n': 0, 'prev_vis': set(), 'render': False, 'figw': set(),
          'shadow': ItemShadow(), 'tmax': 0, 'tsum': 0, 'items': []}
    ns = NextState(patch)
    WATCH = set(range(58851, 58855)) | set(range(59539, 59547)) | {59547} | set(range(59087, 59090)) | \
        {65172, 65274, 65029, 65076} | set(range(60853, 60857)) | set(range(60839, 60843)) | \
        set(range(60965, 60969)) | {59548, 59549}
    cnt = collections.Counter()

    def fail(k, info):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class OMem:                     # original code, private overlay over the live memory
        def __init__(s, real):
            s.real, s.ov = real, {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return MG(s.real, a) if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class PMem(OMem):               # patched game on the Next: slot 0 = page 26 or alt ROM, slot 1 = alt ROM
        def __getitem__(s, a):
            if a < 0x4000:
                if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                    return ns.scratch[a]
                if a >= 0x2000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                    return ns.pages[ns.nr[0x51]][a - 0x2000]
                return alt[a]
            if a < 0x8000:
                pg = ns.nr.get(0x52 + ((a >> 13) & 1))
                if pg != 10 + ((a >> 13) & 1):
                    return ns.pages[pg][a & 0x1FFF]
            v = psite.get(a)
            if v is not None and (s.real.o7ffd & 7) == 0:
                return v
            v = s.ov.get(a)
            return MG(s.real, a) if v is None else v

        def __setitem__(s, a, v):
            if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                ns.scratch[a] = v
            elif 0x2000 <= a < 0x4000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                ns.pages[ns.nr[0x51]][a - 0x2000] = v
            elif a < 0x4000:
                fail('patched code wrote ROM/alt ROM', (a,))
            elif a < 0x8000 and ns.nr.get(0x52 + ((a >> 13) & 1)) != 10 + ((a >> 13) & 1):
                ns.pages[ns.nr[0x52 + ((a >> 13) & 1)]][a & 0x1FFF] = v
            else:
                s.ov[a] = v

    def xt(so, sp_):
        """Extra T of the patched code for this event (both machines start from the same T)."""
        if st.get('fr_on'):
            st['fx'] += sp_.registers[25] - so.registers[25]

    def compare(o, p, ro, rp, what, dead=()):
        diff = [i for i in CMP if ro[i] != rp[i] and i not in dead]
        if diff:
            fail(what + ': registers differ', (diff, [ro[i] for i in diff], [rp[i] for i in diff]))
        keys = set(o.ov) | set(p.ov)
        md = [a for a in keys if not 0x4000 <= a < 0x5800 and o[a] != p[a]]
        if md:
            fail(what + ': memory differs', (len(md), sorted(md)[:4]))
        if any(0x4000 <= a < 0x5B00 for a in p.ov):
            fail(what + ': patched code wrote the screen', (st.get('ix'),))
        return not diff and not md

    def ev_piece(real, R):
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        ok1 = _run(so, (59513, 59547))
        n_before = ns.scratch[V_S]
        ns.events = []
        h0 = ns.scratch[V_HITS] | ns.scratch[V_HITS + 1] << 8
        sp0 = ns.nr.get(0x07)                       # the piece hook must not change the CPU speed
        ov0 = ns.scratch[0x36]
        sp_ = _machine(Sim, p, list(R), ns)
        ok2 = _run(sp_, (59513, 59547))
        if not (ok1 and ok2):
            fail('piece: did not return', (ok1, ok2))
            return
        ro, rp = so.registers, sp_.registers
        xt(so, sp_)
        c['pieces'] += 1
        st['ix'] = (R[8] * 256 + R[9], R[12])
        plan, nspr = piece_plan(patch, R[8] * 256 + R[9], n_before, ns.scratch[V_FMAX])
        if plan != 'sprites':                       # passthrough: patched = original, screen included
            if [i for i in CMP if ro[i] != rp[i]] or o.ov != p.ov:
                fail('passthrough piece differs from the original', ())
        else:
            compare(o, p, ro, rp, 'piece')
        st['afp'] = (ro[16:18], rp[16:18]) if ro[16:18] != rp[16:18] else None
        if ns.nr.get(0x50) != 0xFF or ns.nr.get(0x51) != 0xFF or ns.nr.get(0x07) != sp0 or \
                ns.nr.get(0x52) != 10 or ns.nr.get(0x53) != 11:
            fail('piece: MMU / CPU speed not restored', (ns.nr.get(0x50), ns.nr.get(0x51), ns.nr.get(0x52),
                                                         ns.nr.get(0x53), ns.nr.get(0x07)))
        if any(e[0] == 'in' for e in ns.events):
            fail('piece: port read in hook', ())
        if plan == 'star':
            c['star pieces left on the ULA (60176/60180)'] += 1
            if ns.scratch[V_S] != n_before:
                fail('piece: counter changed for a star', ())
            return
        if plan == 'ula':
            c['pieces passed through to the ULA (sprites used up)'] += 1
            return
        if ns.scratch[V_S] != n_before + nspr:
            fail('piece: sprite counter', (n_before, nspr, ns.scratch[V_S]))
        h1 = ns.scratch[V_HITS] | ns.scratch[V_HITS + 1] << 8
        if ns.scratch[0x36] != ov0:
            c['overflow entries (4 ways in use)'] += 1
        c['pattern cache hits' if h1 != h0 else 'pattern cache misses'] += 1
        c['max sprites in a render'] = max(c['max sprites in a render'], n_before + nspr)
        # sprite pixels vs what the original drew (screen before = live memory, after = overlay)
        cov = {}
        stg = staged(ns, n_before)
        for i in range(n_before, n_before + nspr):
            px = stg.sprite_pixels(i)
            if px is None:
                continue
            for x, y, idx in px:
                if idx and 0 <= x < 256 and 0 <= y < 192:
                    cov[(x, y)] = idx
                elif idx:
                    c['sprite pixels off screen (not compared)'] += 1

        def bit(m, x, y):
            a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
            return (m[a] >> (7 - (x & 7))) & 1, a
        bad_px = 0
        for (x, y), idx in cov.items():
            after, a = bit(o, x, y)
            if idx == 1 and after != 1 or idx == 2 and after != 0:
                bad_px += 1
            c['sprite pixels ink' if idx == 1 else 'sprite pixels outline'] += 1
        for a in o.ov:
            if 0x4000 <= a < 0x5800:
                y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
                for k in range(8):
                    x = (a & 31) * 8 + k
                    before = (MG(real, a) >> (7 - k)) & 1
                    after = (o.ov[a] >> (7 - k)) & 1
                    if (x, y) in cov:
                        continue
                    if after != before:
                        if patch.cfg.transparent_outline and after == 0:
                            c['outline pixels dropped (transparent mode)'] += 1
                        else:
                            bad_px += 1
        if bad_px:
            fail('piece: sprite pixels differ from the original plot', (bad_px,))

    def ev_simple(real, R, stop_at, what, dead=()):
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        sp_ = _machine(Sim, p, list(R), ns)
        ns.events = []
        if not (_run(so, (stop_at,)) and _run(sp_, (stop_at,))):
            fail(what + ': did not return', ())
            return None
        xt(so, sp_)
        compare(o, p, so.registers, sp_.registers, what, dead)
        c[what] += 1
        if ns.nr.get(0x50) != 0xFF:
            fail(what + ': slot 0 not restored', ())
        return sp_

    def ev_render_start(real, R):
        """Render start: original = patched (all registers), and the item list (page 27), the item
        patterns (page 28), the item count and the figure limit equal the model of the shadow map."""
        peek = lambda a: MG(real, a)
        sh = st['shadow']
        if not sh.same_as(ns.pages[PAGE_T]):
            fail('render start: shadow map differs from the model', ())
        items = items_list(peek, sh)
        st['items'] = items
        st['bands'] = set()
        fx0 = st.get('fx', 0)
        sp_ = ev_simple(real, R, 58855, 'render start')
        st['fxi'] = st.get('fxi', 0) + st.get('fx', 0) - fx0
        if sp_ is not None:
            st['tsmax'] = max(st.get('tsmax', 0), sp_.registers[25] - R[25])
        ni = ns.scratch[V_NI]
        if ni != len(items) or ns.scratch[V_FMAX] != NSPR_MAX - len(items):
            fail('render start: item count / figure limit', (ni, len(items), ns.scratch[V_FMAX]))
        pg, pt = ns.pages[PAGE_T], ns.pages[IPAGE]
        for j, it in enumerate(items[:ni]):
            o = ILIST - 0x2000 + 16 * j
            if not record_ok(pg[o:o + 16], it, pt):
                fail('render start: item record / cached pattern differs from the model',
                     (j, bytes(pg[o:o + 16]).hex(), item_record(it).hex()))
        c['items listed'] += ni
        if any(sh.codes[i] == 0xFF for i in range(NCELLS)):
            c['renders with a several-object cell (left on the ULA)'] += 1

    def ev_band(real, R):
        """Walker end of a band (59547): original = patched (all registers, memory), and the screen
        changes = the item fix for this band's char row (from the walker's band address (59522))."""
        peek = lambda a: MG(real, a)
        ba = peek(59522) | peek(59523) << 8
        row = (ba >> 8 & 0x18) | (ba & 0xE0) >> 5
        exp = {a: v for a, v in items_fix(peek, st['items'], row).items() if v != peek(a)}
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        sp_ = _machine(Sim, p, list(R), ns)
        if not (_run(so, (59550,)) and _run(sp_, (59550,))):
            fail('band: did not return', ())
            return
        fx0 = st.get('fx', 0)
        xt(so, sp_)
        st['fxi'] = st.get('fxi', 0) + st.get('fx', 0) - fx0
        st['bands'].add(row)
        ro, rp = so.registers, sp_.registers
        diff = [k for k in CMP + [16, 17] if ro[k] != rp[k]]
        if diff:
            fail('band: registers differ', (diff,))
        md = [a for a in set(o.ov) | set(p.ov) if not 0x4000 <= a < 0x5B00 and o[a] != p[a]]
        if md:
            fail('band: memory differs', (len(md), sorted(md)[:4]))
        got = {a: v for a, v in p.ov.items() if 0x4000 <= a < 0x5B00 and v != peek(a)}
        if got != exp:
            fail('band: screen differs from the item model', (row, len(got), len(exp)))
        if ns.nr.get(0x50) != 0xFF or ns.nr.get(0x51) != 0xFF:
            fail('band: MMU not restored', ())
        c['bands checked'] += 1
        c['item screen bytes changed at band ends'] += len(exp)

    def ev_cell(real, R, pc):
        """Item shadow hooks 60853 / 60839 / 60965: patched = original (registers incl. F, memory),
        and the page-27 shadow map changes exactly as the Python model."""
        i = st['shadow'].event(pc, R[0], R[4], R[5], R[10] * 256 + R[11], lambda a: MG(real, a))
        fx0 = st.get('fx', 0)
        ev_simple(real, R, ITEM_SITES[pc], 'cell hook %d' % pc)
        st['fxi'] = st.get('fxi', 0) + st.get('fx', 0) - fx0
        if i is None:
            c['cell hook: not a back-buffer cell (ignored)'] += 1
        pg = ns.pages[PAGE_T]
        o = CODES - 0x2000
        if i is not None and (pg[o + i] != st['shadow'].codes[i] or pg[o + BATTR - CODES + i] != st['shadow'].battr[i]):
            fail('cell hook: shadow map differs from the model', (pc, i, pg[o + i], st['shadow'].codes[i]))
        if ns.nr.get(0x51) != 0xFF:
            fail('cell hook: MMU1 not restored', (pc,))

    def ev_render_end(real, R):
        n = ns.scratch[V_S]
        want = {}
        for pi_ in range(ns.scratch[V_NP]):
            pg, hi, nsp = ns.scratch[CLIST + 3 * pi_:CLIST + 3 * pi_ + 3]
            want[pi_] = (bytes(ns.pages[pg][(hi - 0x20) * 256 + 256 - 64 * nsp:(hi - 0x20) * 256 + 256]), nsp)
        exp_attr = [list(ns.scratch[ATTRB + 5 * i:ATTRB + 5 * i + 5]) for i in range(n)]
        peek = lambda a: MG(real, a)
        items = st['items']
        iw = items_fix(peek, items)
        # the model against the ORIGINAL screen: every modelled item row shows the item's pixels,
        # unless a figure was plotted over that byte during this render (the original draws figures
        # into the ULA screen; the patched game shows them as sprites in front of the item sprite)
        for it in items:
            for j in it['vis']:
                y = it['y0'] + j
                a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | it['col']
                m, gf = peek(it['g'] + 2 * j), peek(it['g'] + 2 * j + 1)
                if peek(a) & (~m | gf) & 255 == gf:
                    c['item rows on screen as modelled'] += 1
                elif a in st['figw']:
                    c['item rows under a figure the original plotted at render time'] += 1
                else:
                    fail('item model differs from the original screen', (it['idx'], it['code'], j, hex(a)))
        o, p = OMem(real), PMem(real)
        so = _machine(Sim, o, list(R), NextState(patch))
        sp_ = _machine(Sim, p, list(R), ns)
        ns.events = []
        t0 = sp_.registers[25]
        if not (_run(so, (59092,), 400000) and _run(sp_, (59092,), 400000)):
            fail('render end: did not return', ())
            return
        t = sp_.registers[25] - t0
        xt(so, sp_)
        st['tmax'] = max(st['tmax'], t)
        st['tsum'] += t
        ro, rp = so.registers, sp_.registers
        diff = [k for k in CMP if ro[k] != rp[k]]
        if diff:
            fail('render end: registers differ', (diff,))
        md = [a for a in set(o.ov) | set(p.ov) if not 0x4000 <= a < 0x5B00 and o[a] != p[a]]
        if md:
            fail('render end: memory differs', (len(md), sorted(md)[:4]))
        if any(0x4000 <= a < 0x5B00 for a in o.ov) or any(0x4000 <= a < 0x5B00 for a in p.ov):
            fail('render end: screen written here (items are fixed at band ends)', ())
        for it in items:                    # every item row and attribute was on a band this render
            need = {(it['y0'] + j) >> 3 for j in it['vis']} | ({it['arow']} if it['arow'] is not None else set())
            if not need <= st['bands']:
                fail('render end: item on a char row without a band end (not fixed)', (it['idx'], sorted(need - st['bands'])))
        c['render end'] += 1
        if ns.nr.get(0x50) != 0xFF:
            fail('render end: slot 0 not restored', ())
        ni = ns.scratch[V_NI]
        if ni != len(items):
            fail('items: sprite count differs from the model', (ni, len(items)))
        ents = [ns.pages[PAGE_T][ILIST - 0x2000 + 16 * j + 11] for j in range(ni)]
        for j, (it, pn) in enumerate(zip(items[:ni], item_patterns(ents, n))):
            if ns.attr[j] != item_attrs(it, j, pn):
                fail('items: sprite attributes differ from the model', (j, ns.attr[j], item_attrs(it, j, pn)))
            b = (pn >> 1) * 256 + (pn & 1) * 128
            if bytes(ns.pat[b:b + 64]) != it['pattern'] or any(ns.pat[b + 64:b + 128]):
                fail('items: committed pattern differs from the item graphics', (j, it['idx'], it['code']))
        c['item sprites'] += ni
        c['max item sprites in a render'] = max(c['max item sprites in a render'], ni)
        c['max sprites (items + figures) in a render'] = max(c['max sprites (items + figures) in a render'], ni + n)
        i = 0
        for pi_ in sorted(want):
            data, nsp = want[pi_]
            for k in range(nsp):
                b = (i >> 1) * 256 + (i & 1) * 128
                if bytes(ns.pat[b:b + 64]) != data[64 * k:64 * k + 64] or any(ns.pat[b + 64:b + 128]):
                    fail('commit: pattern differs from the staged entry', (i,))
                if ns.attr[ni + i] != exp_attr[i]:
                    fail('commit: attributes differ from the staged ones', (i, ns.attr[ni + i], exp_attr[i]))
                i += 1
        if i != n:
            fail('commit: sprite count', (i, n))
        if ns.nr.get(0x15) != 1 or ns.nr.get(0x51) != 0xFF:
            fail('commit: sprites not on / MMU1 not restored', (ns.nr.get(0x15), ns.nr.get(0x51)))
        c['commits checked'] += 1
        vis = {i for i in range(128) if ns.attr[i][3] & 0x80}
        if not vis <= set(range(ni + n)):
            fail('render end: sprite visible that no piece drew this frame', (n, sorted(vis - set(range(ni + n)))[:6]))
        c['max sprites in a render'] = max(c['max sprites in a render'], ni + n)

    def ev_end(real, R):
        c['walker calls (list ends)'] += 1
        if st['afp']:                               # AF' holds a canvas-derived byte: prove it dies
            ro_af, rp_af = st['afp']
            a, b = OMem(real), OMem(real)
            ma = _machine(Sim, a, list(R), NextState(patch))
            rb = list(R); rb[16:18] = rp_af
            mb = _machine(Sim, b, rb, NextState(patch))
            for step in range(100000):
                if all(ma.registers[i] == mb.registers[i] for i in CMP + [16, 17]):
                    if a.ov == b.ov:
                        c["AF' difference overwritten (converged)"] += 1
                    else:
                        fail("AF' convergence: memory differs", ())
                    break
                if ma.registers[24] != mb.registers[24] or ma.memory[ma.registers[24]] == 0x76:
                    fail("AF' used before overwritten", (step, ma.registers[24]))
                    break
                ma.opcodes[ma.memory[ma.registers[24]]]()
                mb.opcodes[mb.memory[mb.registers[24]]]()
            else:
                fail("AF' convergence: step limit", ())
            st['afp'] = None

    class HookMem(Memory):
        def __setitem__(s, a, v):
            if a in site_bytes and (s.o7ffd & 7) == 0 and st['sim'] is not None:
                fail('game wrote a patch site', (a,))
            if st['render'] and 0x4000 <= a < 0x5800 and 59567 <= st['sim'].registers[24] < 60221:
                st['figw'].add(a)
            MS(s, a, v)

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            memory.__class__ = HookMem
            super().__init__(memory, registers, state_, config)
            st['sim'] = self
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in WATCH and (mem.o7ffd & 7) == 0:
                        cnt[pc] += 1
                        if R[26] and pc not in (65029, 65076):
                            fail('interrupts enabled at a hook site', (pc,))
                        if pc == 59539:
                            ev_piece(mem, R)
                        elif pc in ITEM_SITES:
                            if st['render']:
                                fail('cell hook during a render (item list is built at render start)', (pc,))
                            ev_cell(mem, R, pc)
                        elif pc == 58851:
                            ev_render_start(mem, R)
                            st['render'], st['figw'] = True, set()
                        elif pc == 59087:
                            st['render'] = False
                            ev_render_end(mem, R)
                        elif pc == 59547:
                            ev_end(mem, R)
                            ev_band(mem, R)
                        elif pc == 65172:
                            st['fr_on'], st['f0'], st['facc'], st['fx'], st['fxi'] = True, R[25], 0, 0, 0
                            ns.scratch[V_TICK] = LIMIT - 1          # the recording ran this frame
                            ev_simple(mem, R, 65175, 'limiter: frame runs', dead=(1,))   # F: CP 3 next
                            if ns.nr.get(0x07) != 3:
                                fail('limiter: not 28 MHz for the frame', (ns.nr.get(0x07),))
                        elif pc in (65029, 65076):
                            ev_simple(mem, R, 23698 if pc == 65029 else 23643, 'sprites off (non-play)')
                            if ns.nr.get(0x15) != 0:
                                fail('sprites not switched off', (pc,))
                        elif pc == 65274:
                            if st.get('fr_on'):
                                ft = st['facc'] + R[25] - st['f0'] + st['fx']
                                st['fr_on'] = False
                                st['ftmax'] = max(st.get('ftmax', 0), ft)
                                c['game frames over 20 ms at 28 MHz'] += ft > 560000
                                c['game frames over 20 ms at 28 MHz without the item hooks'] += ft - st['fxi'] > 560000
                                c['patched game frame max (28 MHz us)'] = st['ftmax'] * 1000000 // 28000000
                                st['fimax'] = max(st.get('fimax', 0), st['fxi'])
                                c['item hooks per game frame max (28 MHz us)'] = st['fimax'] * 1000000 // 28000000
                                st['fisum'] = st.get('fisum', 0) + st['fxi']
                                st['fn'] = st.get('fn', 0) + 1
                                c['item hooks per game frame avg (28 MHz us)'] = st['fisum'] * 1000000 // 28000000 // st['fn']
                            ret = MG(mem, R[12] + 2) | MG(mem, R[12] + 3) << 8
                            ev_simple(mem, R, ret, 'handler exit')
                            if ns.nr.get(0x07) != 0:
                                fail('handler exit: not back to 3.5 MHz', (ns.nr.get(0x07),))
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if st.get('fr_on'):
            st['facc'] += st['sim'].registers[25]
        if progress and st['frame'] % 1000 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    # entry-point proof: patched instructions' interiors are only reached by fall-through
    if cnt[59539] != cnt[59541]:
        c['59541 reached other than from 59539!'] += 1
    if cnt[59543] != cnt[59544]:
        c['59544 reached other than from 59543!'] += 1
    if not 0 <= cnt[58851] - cnt[59087] <= 1:          # the recording may end mid-render
        c['render start/end counts differ (%d/%d)!' % (cnt[58851], cnt[59087])] += 1
    for a in (58852, 58853, 58854, 59088, 59089, 59540, 59542, 59545, 59546, 60856, 60842, 59548, 59549):
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    for site, inner in ((60853, (60854, 60855)), (60839, (60840, 60841)), (60965, (60966, 60967, 60968))):
        for a in inner:                     # instruction starts inside a JP: only by fall-through
            if cnt[a] != cnt[site]:
                c['%d reached other than from %d!' % (a, site)] += 1
    c['frames'] = st['frame']
    c['render end T max (28 MHz us)'] = st['tmax'] * 1000000 // 28000000
    c['render end T avg (28 MHz us)'] = st['tsum'] * 1000000 // 28000000 // max(c['render end'], 1)
    c['render start T max (28 MHz us)'] = st.get('tsmax', 0) * 1000000 // 28000000
    return c, dict(ex)


# ---------------------------------------------------------------------------------------------
# Unit tests for paths the recordings do not reach (edge columns, >= MAXP pieces, class colours)
# ---------------------------------------------------------------------------------------------

class _BankMem:
    """Stand-alone 128K memory view (bank at C000 = o7ffd & 7, 48K ROM below 0x4000)."""

    def __init__(self, banks, o7ffd, rom):
        self.banks, self.o7ffd, self.rom = [bytearray(b) for b in banks], o7ffd, rom

    def __getitem__(self, a):
        s = a >> 14
        if s == 0:
            return self.rom[a]
        b = (5, 2, self.o7ffd & 7)[s - 1]
        return self.banks[b][a & 0x3FFF]


def _pair(patch, bm, regs, n_before, scratch=None, pat=None, pages=None, stops=(59513, 59547), oregs=None):
    """Run original and patched code from one dispatch state (PC 59539) on views of bm.
    Returns (orig_regs, orig_overlay, patched_regs, patched_overlay, NextState, errors)."""
    from .dizzy6 import _rw_simulator
    from .build import rom48
    Sim = _rw_simulator()
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    ns = NextState(patch)
    if scratch is not None:
        ns.scratch[:] = scratch
    if pat is not None:
        ns.pat[:] = pat
    if pages is not None:
        for k, v in pages.items():
            ns.pages[k] = bytearray(v)
    ns.scratch[V_S] = n_before
    err = []

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return bm[a] if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                    return ns.scratch[a]
                if a >= 0x2000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                    return ns.pages[ns.nr[0x51]][a - 0x2000]
                return alt[a]
            if a < 0x8000:
                pg = ns.nr.get(0x52 + ((a >> 13) & 1))
                if pg != 10 + ((a >> 13) & 1):
                    return ns.pages[pg][a & 0x1FFF]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                ns.scratch[a] = v
            elif 0x2000 <= a < 0x4000 and ns.nr.get(0x51, 0xFF) != 0xFF:
                ns.pages[ns.nr[0x51]][a - 0x2000] = v
            elif a < 0x4000:
                err.append(('rom write', a))
            elif a < 0x8000 and ns.nr.get(0x52 + ((a >> 13) & 1)) != 10 + ((a >> 13) & 1):
                ns.pages[ns.nr[0x52 + ((a >> 13) & 1)]][a & 0x1FFF] = v
            else:
                s.ov[a] = v
    o, p = O(), P()
    so = _machine(Sim, o, list(oregs or regs), NextState(patch))
    sp_ = _machine(Sim, p, list(regs), ns)
    if not (_run(so, stops) and _run(sp_, stops)):
        err.append('did not return')
    return so.registers, o, sp_.registers, p, ns, err


def _pixels_ok(ns, first, bm, o, transparent=False):
    """Sprites first..first+3 against the original plot (before = bm, after = overlay o)."""
    cov = {}
    for i in range(first, min(first + 4, 128)):
        px = ns.sprite_pixels(i)
        for x, y, idx in px or ():
            if idx and 0 <= x < 256 and 0 <= y < 192:
                cov[(x, y)] = idx

    def at(m, x, y):
        a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
        return (m[a] >> (7 - (x & 7))) & 1
    bad = sum(1 for (x, y), idx in cov.items() if (idx == 1) != (at(o, x, y) == 1))
    for a in o.ov:
        if 0x4000 <= a < 0x5800:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                x = (a & 31) * 8 + k
                if (x, y) not in cov and ((bm[a] ^ o.ov[a]) >> (7 - k)) & 1:
                    if not (transparent and not (o.ov[a] >> (7 - k)) & 1):
                        bad += 1
    return bad


def _pix(ns, first, bm, o, **kw):
    return _pixels_ok(staged(ns, first), first, bm, o, **kw)


def unit_tests(patch, rzx_path, want=40, frames=3000):
    """Collect `want` dispatch states from the RZX, then for each: move the piece to edge columns,
    run with n = MAXP-1 and n = MAXP (passthrough), and a negative control (ink/outline swapped)."""
    import copy
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .build import rom48
    rom = rom48()
    states, seen, hstates, rstates, cstates = [], set(), [], [], {60853: [], 60839: [], 60965: []}

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    if R[24] == 65172 and (mem.o7ffd & 7) == 0 and len(hstates) < 6:
                        hstates.append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    if R[24] == 58851 and (mem.o7ffd & 7) == 0 and len(rstates) < 2 and R[25] % 7 == 0:
                        rstates.append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    if R[24] in cstates and (mem.o7ffd & 7) == 0 and len(cstates[R[24]]) < 3:
                        cstates[R[24]].append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    if R[24] == 59539 and (mem.o7ffd & 7) == 0 and len(states) < want:
                        ix = R[8] * 256 + R[9]
                        if ix not in (60176, 60180) and (ix, len(states) // 8) not in seen:
                            seen.add((ix, len(states) // 8))
                            states.append(([bytes(b) for b in mem.banks], mem.o7ffd, list(R)))
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])
    old = rzxplay.Simulator, rzxplay.CSimulator
    rzxplay.Simulator, rzxplay.CSimulator = S, None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0', '--stop', str(frames), rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.Simulator, rzxplay.CSimulator = old
    c = collections.Counter()
    bad_patch = copy.deepcopy(patch)
    sc = bytearray(bad_patch.scratch)
    t = bytearray(Config().nibtab())                               # ink and outline indices swapped
    for i in range(512):
        hi, lo = t[i] >> 4, t[i] & 15
        sw = {1: 2, 2: 1}
        t[i] = sw.get(hi, hi) << 4 | sw.get(lo, lo)
    sc[NIBTAB:NIBTAB + 512] = t
    bad_patch.scratch = bytes(sc)
    import random
    rnd = random.Random(7)
    peek0 = _BankMem(states[0][0], states[0][1], rom)
    for banks, o7, R in states:
        bm = _BankMem(banks, o7, rom)
        ix = R[8] * 256 + R[9]
        pi = patch.plot[ix]
        right = ix in (59717, 59759, 59801, 59843)                 # plotters that run leftwards
        cols = (2, 3, 16, 29, 31) if right else (0, 1, 16, 26, 29)
        for col in cols:
            r = list(R)
            r[5] = (r[5] & 0xE0) | col
            ro, o, rp, p, ns, err = _pair(patch, bm, r, 5)
            ok = not err and all(ro[i] == rp[i] for i in CMP) and not any(0x4000 <= a < 0x5B00 for a in p.ov)
            ok = ok and _pix(ns, 5, bm, o) == 0 and ns.scratch[V_S] == 5 + pi['nspr']
            width = {60105: 1, 60110: 2, 60115: 3, 60120: 4, 60125: 5, 60130: 6}.get(ix, 3)
            wraps = col - 2 < 0 if right else col + width > 32
            if wraps:                  # the ULA wraps into the next char row; the sprite clips
                c['edge column wraps on the ULA (sprite clips; not a game case) %s' % ('same' if ok else 'differs')] += 1
            else:
                c['edge column %s' % ('ok' if ok else 'FAIL!')] += 1
                if not ok:
                    c['  fail ix %d col %d' % (ix, col)] += 1
        for n, what in ((NSPR_MAX - pi['nspr'], 'last sprites'), (NSPR_MAX - pi['nspr'] + 1, 'passthrough')):
            ro, o, rp, p, ns, err = _pair(patch, bm, R, n)
            same = all(ro[i] == rp[i] for i in CMP + [16, 17]) and o.ov == p.ov and ns.scratch[V_S] == n \
                if what == 'passthrough' else _pix(ns, n, bm, o) == 0 and ns.scratch[V_S] == NSPR_MAX
            c['%s %s' % (what, 'ok' if same and not err else 'FAIL!')] += 1
        ro, o, rp, p, ns, err = _pair(bad_patch, bm, R, 3)
        visible = any(staged(ns, 3).attr[i][3] & 0x80 for i in range(3, 3 + pi['nspr']))   # (staged:
        # attributes reach the sprites only at the render-end commit; ns.attr made this n/a every time)
        if not visible:
            c['negative control n/a (piece has no pixels)'] += 1
        else:
            c['negative control %s' % ('detected' if _pix(ns, 3, bm, o) else 'NOT DETECTED!')] += 1
    # plotter layouts (direct conversion): profile = derivation from the game's plotters; window
    # covers every plotter's extent; the Python model of the hook's conversion reproduces the
    # plotter on random streams; negative control: one corrupted layout byte must be caught
    lay = plotter_layouts(peek0)
    c['plotter layout table %s' % ('ok' if {str(k): v for k, v in lay.items()} == patch.prof['plotters']
                                   else 'FAIL!')] += 1
    ext = plotter_extents(peek0)
    for t, (lo, hi) in ext.items():
        if t in patch.plot:
            pi = patch.plot[t]
            c['window covers plotter extent %s' % (
                'ok' if -pi['off'] <= lo and hi <= 2 * pi['nspr'] - 1 - pi['off'] else 'FAIL!')] += 1
    from skoolkit.simulator import Simulator
    base = bytearray(peek0[a] for a in range(65536))

    def truth(t, cy, stream):
        out = []
        for fill in (0, 0xFF):
            m = bytearray(base)
            m[0x4000:0x5800] = bytes([fill]) * 0x1800
            m[0x8000:0x8000 + len(stream)] = stream
            sim = Simulator(m, {'PC': t, 'SP': 0x8000, 'D': 0x48, 'E': 0x48, 'H': 245, 'L': 0})
            sim.registers[17] = cy
            _run(sim, (59543,), 5000)
            out.append(m)
        return out

    def model_ok(info, t, cy, stream):
        g, mg = truth(t, cy, stream)
        G, M = layout_convert(info, cy, stream)
        for row in range(10):
            for col in range(2 * info['nspr']):
                a = (0x48 + row) * 256 + 0x48 - info['off'] + col
                if row >= 8 and (row, col) not in G and (row, col) not in M:
                    continue
                if G.get((row, col), 0) != g[a] or M.get((row, col), 0xFF) != mg[a]:
                    return False
        return True
    for t, info in sorted(patch.plot.items()):
        for cy in (0, 1):
            n = info['len'][cy]
            good = all(model_ok(info, t, cy, bytes(rnd.randrange(256) for _ in range(n))) for _ in range(4))
            c['direct conversion = plotter (random streams) %s' % ('ok' if good else 'FAIL!')] += 1
    bad = dict(patch.plot[59699])
    lb = bytearray.fromhex(bad['layout'][0])
    lb[1] ^= 0x40                                               # one byte wrongly mirrored
    bad['layout'] = [lb.hex(), bad['layout'][1]]
    st_ = bytes(rnd.randrange(1, 255) for _ in range(bad['len'][0]))
    c['layout negative control %s' % ('detected' if not model_ok(bad, 59699, 0, st_) else 'NOT DETECTED!')] += 1
    rev_ok = all(base[0xF500 + i] == int('{:08b}'.format(i)[::-1], 2) for i in range(256))
    c['game table page 245 = bit reversal %s' % ('ok' if rev_ok else 'FAIL!')] += 1
    # LEFT4 plotters (only the boss spider uses them) on real graphics streams
    for banks, o7, R in states[:8]:
        bm = _BankMem(banks, o7, rom)
        for ix in LEFT4:
            for col in (3, 16, 28):
                r = list(R)
                r[8], r[9] = ix >> 8, ix & 255
                r[4] = (r[4] & 0xF8) | 2 * LEFT4.index(ix)     # entry for 8/6/4/2 rows: start row 0/2/4/6
                r[5] = (r[5] & 0xE0) | col
                ro, o, rp, p, ns, err = _pair(patch, bm, r, 5)
                ok = not err and all(ro[i] == rp[i] for i in CMP) and \
                    not any(0x4000 <= a < 0x5B00 for a in p.ov) and _pix(ns, 5, bm, o) == 0
                c['left-entry 4-wide plotter %s' % ('ok' if ok else 'FAIL!')] += 1
    # pattern store: a repeat piece HITS and draws exactly the original; a changed stream at the
    # same address MISSES; garbage store pages never hit. Negative controls: stream compare patched
    # out (stale image), corrupted patterns in the stored entry.
    cj = patch.syms['s_pc.cmpj']
    if patch.scratch[cj] != 0x20:
        raise ValueError('s_pc.cmpj is not JR NZ')

    def hits(ns):
        return ns.scratch[V_HITS] | ns.scratch[V_HITS + 1] << 8

    class Mod:
        def __init__(s, bm, ov):
            s.bm, s.ov = bm, ov

        def __getitem__(s, a):
            return s.ov.get(a, s.bm[a])
    garbage = {STORE_PG + k: bytes(rnd.randrange(256) for _ in range(8192)) for k in range(STORE_PAGES)}
    for si, (banks, o7, R) in enumerate(states):
        bm = _BankMem(banks, o7, rom)
        ro, o1, rp, p, ns, err = _pair(patch, bm, R, 3, pages=garbage if si < 4 else None)
        ok = not err and hits(ns) == 0 and _pix(ns, 3, bm, o1) == 0 and all(ro[i] == rp[i] for i in CMP)
        c['store first sighting misses%s %s' % (' (garbage store)' if si < 4 else '', 'ok' if ok else 'FAIL!')] += 1
        store = {k: v for k, v in ns.pages.items() if k >= STORE_PG}
        ro, o, rp, p, ns2, err = _pair(patch, bm, R, 5, scratch=ns.scratch, pages=store)
        ok = not err and all(ro[i] == rp[i] for i in CMP) and hits(ns2) == 1 and _pix(ns2, 5, bm, o) == 0
        c['store hit (registers, pixels) %s' % ('ok' if ok else 'FAIL!')] += 1   # (AF': verify proves it dies)
        sp0, ln = R[12], patch.plot[R[8] * 256 + R[9]]['len'][R[17] & 1]
        cb = sp0 + ln - 1 if ln > 16 else sp0 + 1              # beyond the hashed 16 bytes if possible
        chg = Mod(bm, {cb: bm[cb] ^ 0xFF})
        ro, o, rp, p, ns3, err = _pair(patch, chg, R, 5, scratch=ns.scratch, pages=store)
        ok = not err and hits(ns3) == 0 and _pix(ns3, 5, chg, o) == 0
        c['store changed stream -> miss %s' % ('ok' if ok else 'FAIL!')] += 1
        sc = bytearray(ns.scratch)
        sc[cj:cj + 2] = b'\x00\x00'
        ro, o, rp, p, ns4, err = _pair(patch, chg, R, 5, scratch=sc, pages=store)
        if ln <= 16:
            c['store no-compare negative control n/a (stream fully hashed)'] += 1
        elif {a: v for a, v in o.ov.items() if a < 0x5800} == {a: v for a, v in o1.ov.items() if a < 0x5800}:
            c['store no-compare negative control n/a (changed byte draws the same)'] += 1
        else:
            c['store no-compare negative control %s' % (
                'detected' if _pix(ns4, 5, chg, o) else 'NOT DETECTED!')] += 1
        pg, hi = ns.scratch[0x28], ns.scratch[0x27]               # V_EPG, V_ENT+1 of this piece
        stale = {k: bytearray(v) for k, v in store.items()}
        e0 = (hi - 0x20) * 256
        nsp = patch.plot[R[8] * 256 + R[9]]['nspr']
        for i in range(e0 + 256 - 64 * nsp, e0 + 256):
            stale[pg][i] ^= 0x11
        ro, o, rp, p, ns5, err = _pair(patch, bm, R, 5, scratch=ns.scratch, pages=stale)
        if not any(staged(ns, 3).attr[i][3] & 0x80 for i in range(3, 3 + nsp)):
            c['store stale-pattern negative control n/a (piece has no pixels)'] += 1
        else:
            c['store stale-pattern negative control %s' % (
                'detected' if _pix(ns5, 5, bm, o) else 'NOT DETECTED!')] += 1
    # frame limiter: tick < LIMIT-1 -> the interrupt returns at once, exactly like the original's
    # POP AF / EI / RET at 65274, tick counted, CPU at 3.5 MHz; tick = LIMIT-1 -> the frame runs
    # (reaches 65175 as the original, tick 0, 28 MHz). Control: the skip jump patched out.
    sl = patch.syms['s_lim.skip']
    for banks, o7, R in hstates:
        bm = _BankMem(banks, o7, rom)
        ret = bm[R[12] + 2] | bm[R[12] + 3] << 8
        for tick in range(LIMIT):
            sc = bytearray(patch.scratch)
            sc[V_TICK] = tick
            runs = tick == LIMIT - 1
            oR = list(R)
            if not runs:
                oR[24] = 65274                                 # original: straight to the exit
            ro, o, rp, p, ns, err = _pair(patch, bm, R, 0, scratch=sc, oregs=oR,
                                          stops=(65175,) if runs else (ret,))
            ok = not err and all(ro[i] == rp[i] for i in CMP + [24] if not (runs and i == 1)) and o.ov == p.ov and \
                ns.scratch[V_TICK] == (0 if runs else tick + 1) and ns.nr.get(0x07) == (3 if runs else 0)
            c['limiter %s %s' % ('frame runs' if runs else 'interrupt skipped', 'ok' if ok else 'FAIL!')] += 1
    if hstates:
        banks, o7, R = hstates[0]
        bm = _BankMem(banks, o7, rom)
        ret = bm[R[12] + 2] | bm[R[12] + 3] << 8
        sc = bytearray(patch.scratch)
        sc[V_TICK] = 0
        k = bytes(sc).find(b'\x38', patch.syms['s_lim'], sl)
        sc[k:k + 2] = b'\x00\x00'
        ro, o, rp, p, ns, err = _pair(patch, bm, R, 0, scratch=sc, stops=(65175, ret))
        c['limiter negative control (skip removed) %s' % (
            'detected' if rp[24] == 65175 else 'NOT DETECTED!')] += 1
    else:
        c['limiter states FAIL! (none collected)'] += 1
    # render-end commit: negative control through the verifier itself (a short replay with the
    # commit writing attribute 4 to the wrong register must fail the commit check)
    bc = copy.deepcopy(patch)
    sc = bytearray(bc.scratch)
    k = sc.find(b'\xED\x92\x39', patch.syms['s_re'])
    sc[k + 2] = 0x3A
    bc.scratch = bytes(sc)
    bc.extra_banks = {12: bc.page + bytes(8192), 13: bc.scratch + bc.tpage}
    cc, _ = verify(bc, rzx_path, stop=1500)
    c['commit negative control (attr 4 not written) %s' % (
        'detected' if any(k.startswith('commit: attributes') for k in cc) else 'NOT DETECTED!')] += 1
    # Z80N SWAPNIB in the simulator: exhaustive opcode test; negative control = the hooks run with
    # ED 23 as SkoolKit's silent NOP must produce wrong pixels
    c['SWAPNIB simulator self-test %s' % ('ok' if swapnib_selftest() == 0 else 'FAIL!')] += 1
    nop_patch = copy.deepcopy(patch)
    nop_patch.no_swapnib = True
    det = 0
    for banks, o7, R in states:
        bm = _BankMem(banks, o7, rom)
        ro, o, rp, p, ns, err = _pair(nop_patch, bm, R, 3)
        det += _pix(ns, 3, bm, o) > 0
    c['SWAPNIB-as-NOP negative control %s' % ('detected' if det else 'NOT DETECTED!')] += 1
    # pattern bottom halves: setup must zero pattern RAM; negative control = setup without its
    # OUT (0x5B) in the zero loop must be caught
    c['setup zeroes pattern RAM %s' % ('ok' if setup_zeroes_patterns(patch) is None else 'FAIL!')] += 1
    np_ = copy.deepcopy(patch)
    zb = patch.syms['setup.zb'] - 0xD000
    se = bytearray(np_.stub_extra)
    if se[zb:zb + 2] != b'\xD3\x5B':
        raise ValueError('setup.zb is not OUT (0x5B),A')
    se[zb:zb + 2] = b'\x00\x00'
    np_.stub_extra = bytes(se)
    c['setup-without-zeroing negative control %s' % (
        'detected' if setup_zeroes_patterns(np_) else 'NOT DETECTED!')] += 1
    # class colour hook: page -> palette offset in attr 2 bits 7-4
    cc = RainbowPatch(Config(class_colours={'pages': {'%02X' % (states[0][2][12] >> 8): 5},
                                            'palettes': {'5': {'ink': '#FF0000'}}}), patch.prof)
    banks, o7, R = states[0]
    ro, o, rp, p, ns, err = _pair(cc, _BankMem(banks, o7, rom), R, 0)
    t = staged(ns, 0)
    offs = {t.attr[i][2] >> 4 for i in range(4) if t.attr[i][3] & 0x80}
    c['class colour offset %s' % ('ok' if offs == {5} and cc.cfg.palette()[81] == 0xE0 else 'FAIL! %s' % offs)] += 1
    item_unit_tests(patch, rstates, cstates, rom, c, rzx_path)
    c['states'] = len(states)
    return c


def _with_bytes(patch, sym, old, new):
    """A copy of the patch whose page-26 code has `old` at symbol `sym` replaced by `new`."""
    import copy
    b = copy.deepcopy(patch)
    a = patch.syms[sym]
    sc = bytearray(b.scratch)
    if bytes(sc[a:a + len(old)]) != old:
        raise ValueError('%s is not %s' % (sym, old.hex()))
    sc[a:a + len(new)] = new
    b.scratch = bytes(sc)
    b.extra_banks = {12: b.page + bytes(8192), 13: b.scratch + b.tpage}
    return b


def item_unit_tests(patch, rstates, cstates, rom, c, rzx_path):
    """Collectables: cell hooks (every register incl. F, shadow map = model) on synthetic cases; render
    start (list + patterns), every band and the render end on synthetic shadow maps (wrapped top
    rows, partial bottom, X8 columns, unknown colour, several-object cell, star-changed attribute,
    the 64-item cap). Negative controls must be detected."""
    import random
    rnd = random.Random(11)

    class Mod:
        def __init__(s, bm, ov):
            s.bm, s.ov = bm, ov

        def __getitem__(s, a):
            return s.ov.get(a, s.bm[a])
    if not all(cstates.values()) or not rstates:
        c['item states FAIL! (not collected: %s)' % {k: len(v) for k, v in cstates.items()}] += 1
        return

    def cell_cases(pt):
        out = 0
        bad = 0
        for site, sts in cstates.items():
            for banks, o7, R0 in sts:
                bm = _BankMem(banks, o7, rom)
                for case in range(24):
                    r = list(R0)
                    r[24] = site
                    if site == 60853:
                        r[0] = rnd.randrange(256)
                    else:
                        r[0] = rnd.choice((0, 1, 2, 7, 13, 14, 15, 19, 255))
                    d, e = rnd.choice(((0x9F, 0), (0xB4, 31), (0xA5, 17), (0x9E, 3), (0xB5, 3), (0xA0, 32),
                                       (0xAA, rnd.randrange(32)), (0x9F + rnd.randrange(22), rnd.randrange(32))))
                    r[4], r[5] = d, e
                    iy = rnd.choice((60699, 60720, 0x6D3C, rnd.randrange(65536)))
                    r[10], r[11] = iy >> 8, iy & 255
                    r[1] = (r[1] & 0xFE) | rnd.randrange(2)
                    sh = ItemShadow()
                    pg = bytearray(patch.tpage)
                    for i in range(NCELLS):
                        sh.codes[i] = rnd.choice((0, 0, 0, 3, 7, 0xFF))
                        sh.battr[i] = rnd.randrange(256)
                    i0 = ItemShadow.cell(d, e)
                    if i0 is not None and site == 60965 and case % 3 == 0:
                        sh.codes[i0] = r[0]                    # same code again
                    o = CODES - 0x2000
                    pg[o:o + NCELLS] = sh.codes
                    pg[o + BATTR - CODES:o + BATTR - CODES + NCELLS] = sh.battr
                    pg[RCNT - 0x2000:RCNT - 0x2000 + 22] = sh.rcnt()
                    sh.event(site, r[0], d, e, iy, lambda a: bm[a])
                    ro, ov, rp, pv, ns, err = _pair(pt, bm, r, 0, pages={PAGE_T: pg}, stops=(ITEM_SITES[site],))
                    ok = not err and all(ro[k] == rp[k] for k in CMP + [16, 17]) and ov.ov == pv.ov and \
                        sh.same_as(ns.pages[PAGE_T]) and ns.nr.get(0x50) == 0xFF and ns.nr.get(0x51) == 0xFF
                    out += 1
                    bad += not ok
        return out, bad
    n, bad = cell_cases(patch)
    c['item cell hooks (registers incl. F, shadow = model) %s' % ('ok' if not bad else 'FAIL!')] += n
    for sym, old, new, what in (('s_ov.wr', b'\x7E\x70', b'\x00\x00', 'overlay does not clear the cell'),
                                ('s_ov.rla', b'\x17', b'\x00', 'carry not restored')):
        n, bad = cell_cases(_with_bytes(patch, sym, old, new))
        c['item cell hook negative control (%s) %s' % (what, 'detected' if bad else 'NOT DETECTED!')] += 1

    def render_case(pt, bm, R, sh, nfig):
        """render start -> every band -> render end on memory bm with shadow sh. Returns failures."""
        fails = []
        peek = lambda a: bm[a]
        pg = bytearray(patch.tpage)
        o = CODES - 0x2000
        pg[o:o + NCELLS] = sh.codes
        pg[o + BATTR - CODES:o + BATTR - CODES + NCELLS] = sh.battr
        pg[RCNT - 0x2000:RCNT - 0x2000 + 22] = sh.rcnt()
        items = items_list(peek, sh)
        r = list(R)
        r[24] = 58851
        ro, ov, rp, pv, ns, err = _pair(pt, bm, r, 0, pages={PAGE_T: pg}, stops=(58855,))
        if err or any(ro[k] != rp[k] for k in CMP + [16, 17]) or ov.ov != pv.ov:
            fails.append('render start registers/memory')
        if ns.scratch[V_NI] != len(items) or ns.scratch[V_FMAX] != NSPR_MAX - len(items):
            fails.append('count %d/%d' % (ns.scratch[V_NI], len(items)))
        for j, it in enumerate(items):
            q = ILIST - 0x2000 + 16 * j
            if not record_ok(ns.pages[PAGE_T][q:q + 16], it, ns.pages[IPAGE]):
                fails.append('record / pattern %d' % j)
        sc, pages = bytes(ns.scratch), {k: bytes(v) for k, v in ns.pages.items()}
        for row in range(2, 24):
            ba = 0x4000 | (row & 0x18) << 8 | (row & 7) << 5
            m2 = Mod(bm, {59522: ba & 255, 59523: ba >> 8})
            exp = {a: v for a, v in items_fix(lambda a: m2[a], items, row).items() if v != m2[a]}
            r = list(R)
            r[24] = 59547
            ro, ov, rp, pv, ns2, err = _pair(pt, m2, r, sc[V_S], scratch=sc, pages=pages, stops=(59550,))
            got = {a: v for a, v in pv.ov.items() if 0x4000 <= a < 0x5B00 and v != m2[a]}
            if err or any(ro[k] != rp[k] for k in CMP + [16, 17]) or got != exp or \
                    ns2.nr.get(0x50) != 0xFF or ns2.nr.get(0x51) != 0xFF:
                fails.append('band %d' % row)
        sc2 = bytearray(sc)
        sc2[V_NP] = 0
        r = list(R)
        r[24] = 59087
        ro, ov, rp, pv, ns3, err = _pair(pt, bm, r, nfig, scratch=sc2, pages=pages, stops=(59092,))
        got = {a: v for a, v in pv.ov.items() if 0x4000 <= a < 0x5B00 and v != bm[a]}
        if err or any(ro[k] != rp[k] for k in CMP) or got:
            fails.append('render end screen/registers')
        ents = [ns3.pages[PAGE_T][ILIST - 0x2000 + 16 * j + 11] for j in range(len(items))]
        for j, (it, pn) in enumerate(zip(items, item_patterns(ents, nfig))):
            b = (pn >> 1) * 256 + (pn & 1) * 128
            if ns3.attr[j] != item_attrs(it, j, pn) or bytes(ns3.pat[b:b + 64]) != it['pattern']:
                fails.append('sprite %d' % j)
        return fails, items

    def scenarios(bm):
        """(memory, shadow): wrap/partial/edge columns/colour cases; and the 64-item cap."""
        out = []
        s, N = 3, 155                       # scroll not a multiple of 8, play area 155 rows
        ov = {48782: s, 58850: N}
        sh = ItemShadow()
        k_wrap = ((s + 173) // 8) % 22       # 8k - s = 173 mod 176: rows 3-7 wrap to the top
        k_part = ((s + 149) // 8) % 22       # rows crossing the bottom of the play area
        for k, col, code, base in ((k_wrap, 0, 1, 0x47 | 128), (k_part, 31, 14, 0x0D | 128), (5, 27, 7, 0),
                                   (6, 28, 9, 0x30 | 128), (9, 12, 3, 0x05 | 128), (11, 4, 12, 0x46 | 128)):
            i = 32 * k + col
            sh.codes[i], sh.battr[i] = code, base
        sh.codes[32 * 7 + 7] = 0xFF                                  # several objects: left on the ULA
        i = 32 * 9 + 12                                              # attribute changed by a star
        kk = (9 - (s >> 3)) % 22
        ov[0x5800 + 32 * (kk + 2) + 12] = 0x42
        out.append((Mod(bm, ov), sh))
        sh2 = ItemShadow()                                           # 90 items: IMAX (80) listed
        for i in range(90):
            k, col = 2 + i // 32, i % 32
            sh2.codes[32 * k + col] = 1 + i % 14
            sh2.battr[32 * k + col] = 0x38 | 128
        out.append((Mod(bm, {48782: 0, 58850: 160}), sh2))
        return out
    nfail, ncase = [], 0
    for banks, o7, R in rstates:
        bm = _BankMem(banks, o7, rom)
        for m, sh in scenarios(bm):
            f, items = render_case(patch, m, R, sh, 5)
            ncase += 1
            nfail += f
            c['item render cases: items listed'] += len(items)
    c['item render path (start, %d bands, end; model) %s' % (22, 'ok' if not nfail else 'FAIL! %s' % nfail[:4])] += ncase
    banks, o7, R = rstates[0]
    bm = _BankMem(banks, o7, rom)
    m, sh = scenarios(bm)[0]
    rs = patch.syms['ifix.rsel']
    for sym, old, new, what in (('ifix.mand', b'\xDD\xA5', b'\x00\x00', 'mask not applied'),
                                ('ipbuild.inkx', b'\x07\x07\x07\x07\xB0', b'\x3E\x11\x00\x00\x00', 'ink drawn as outline'),
                                ('ipat.nb', patch.scratch[patch.syms['ipat.nb']:patch.syms['ipat.nb'] + 3], b'\x00\x00\x00',
                                 'pattern never built'),
                                ('ifix.rsel', patch.scratch[rs:rs + 2], b'\x00\x00', 'band fixes rows of other bands')):
        bp = _with_bytes(patch, sym, old, new)
        f, _ = render_case(bp, m, R, sh, 5)
        c['item render negative control (%s) %s' % (what, 'detected' if f else 'NOT DETECTED!')] += 1
    # list reuse (same scroll, no cell change): the second render start keeps the list but must
    # pick up an ink the game changed in the attribute buffer (51914 does in the bonus scene)
    def reuse_case(pt):
        banks, o7, R = rstates[0]
        bm = _BankMem(banks, o7, rom)
        m, sh = scenarios(bm)[0]
        pg = bytearray(patch.tpage)
        o = CODES - 0x2000
        pg[o:o + NCELLS] = sh.codes
        pg[o + BATTR - CODES:o + BATTR - CODES + NCELLS] = sh.battr
        pg[RCNT - 0x2000:RCNT - 0x2000 + 22] = sh.rcnt()
        r = list(R)
        r[24] = 58851
        ro, ov, rp, pv, ns, err = _pair(pt, m, r, 0, pages={PAGE_T: pg}, stops=(58855,))
        items0 = items_list(lambda a: m[a], sh)
        a0 = items0[0]['abuf']
        m2 = Mod(m, {a0: (m[a0] & 0xF8) | ((m[a0] & 7) + 1) % 8})
        items = items_list(lambda a: m2[a], sh)
        sc = bytearray(ns.scratch)
        sc[V_FRM] = (sc[V_FRM] + 1) & 255                      # next render
        ro, ov, rp, pv, ns2, err = _pair(pt, m2, r, 0, scratch=sc, pages={k: bytes(v) for k, v in ns.pages.items()},
                                         stops=(58855,))
        bad = bool(err) or ns2.scratch[0x97] != 0 or ns2.scratch[V_NI] != len(items)
        for j, it in enumerate(items):
            q = ILIST - 0x2000 + 16 * j
            bad |= not record_ok(ns2.pages[PAGE_T][q:q + 16], it, ns2.pages[IPAGE])
        return bad, items0[0]['ink'] != items[0]['ink']
    bad, changed = reuse_case(patch)
    c['item list reuse + ink refresh %s' % ('ok' if not bad and changed else 'FAIL!')] += 1
    bad, changed = reuse_case(_with_bytes(patch, 'ikeep.ref', b'\x28', b'\x18'))
    c['item render negative control (inks never refreshed) %s' % ('detected' if bad else 'NOT DETECTED!')] += 1
    # through the verifier: figures committed over the item sprite numbers must fail
    bc = _with_bytes(patch, 's_re.fo', b'\x81', b'\x00')
    cc, _ = verify(bc, rzx_path, stop=1500)
    c['item commit negative control (figure sprites not after the items) %s' % (
        'detected' if any(k.startswith(('commit: attributes', 'items: sprite attributes')) for k in cc)
        else 'NOT DETECTED!')] += 1


# ---------------------------------------------------------------------------------------------
# nexclash auto entry point for this engine
# ---------------------------------------------------------------------------------------------

def mem64(snap):
    """64K view of a SkoolKit 128K snapshot with bank 0 at C000 (where the engine code lives)."""
    b = snap.memory.banks
    return bytes(16384) + bytes(b[5]) + bytes(b[2]) + bytes(b[0])


def is_rainbow(snap):
    return snap.machine != '48K' and identify_rb(mem64(snap))


def auto(a, z80, name, out, say):
    """Plain + sprite .nex, boot checks, differential verification per RZX, unit tests."""
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    cls = json.load(open(a.class_colours)) if getattr(a, 'class_colours', None) else None
    cfg = Config(getattr(a, 'ink', None) or 'white', getattr(a, 'outline', None) or 'black', cls)
    say('Game      : %s' % name)
    say('Engine    : rainbow (Rainbow Islands 128K: sprite-list walker, full-redraw renderer)')
    say('Colours   : ink %s, outline %s%s' % (getattr(a, 'ink', None) or 'white',
                                              getattr(a, 'outline', None) or 'black',
                                              ', class colours from %s' % a.class_colours if cls else ''))
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, TAIL_ADDR, quiet=True)
    bad = boot_check(plain, z80, tail=(TAIL_ADDR, TAIL_ADDR + 80))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = back buffer, write-first in both RZX)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = RainbowPatch(cfg)
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    rzxs = list(a.rzx or [])
    for r in rzxs:
        segs = RZ.read_segments(r)
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1,
                                                                   os.path.basename(s2)))
            r = s2
        c, ex = verify(patch, r, stop=getattr(a, 'quick', None))
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        hm = c['pattern cache hits'] + c['pattern cache misses']
        say('Verify    : %s  %d frames, %d renders, %d pieces (max %d sprites/render, store hits %d%%), %d stars '
            "kept on ULA, AF' converged %d -> %s" % (os.path.basename(r), c['frames'], c['render start'],
                                         c['pieces'], c['max sprites in a render'],
                                         100 * c['pattern cache hits'] // max(hm, 1),
                                         c['star pieces left on the ULA (60176/60180)'],
                                         c["AF' difference overwritten (converged)"],
                                         'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            limiter: %d game frames checked (entry + exit), 28 MHz inside, 3.5 MHz outside' %
            c['limiter: frame runs'])
        say('            commits checked %d (patterns + attributes = staged), non-play sprites-off %d, '
            'overflow entries %d' % (c['commits checked'], c['sprites off (non-play)'],
                                     c['overflow entries (4 ways in use)']))
        say('            items: %d cell hooks (60853 %d / 60839 %d / 60965 %d), %d item sprites (max %d per render, '
            'max %d sprites in all), %d bands checked, %d item screen bytes fixed at band ends; item rows: %d as '
            'modelled on the original screen, %d under a figure' % (
                c['cell hook 60853'] + c['cell hook 60839'] + c['cell hook 60965'], c['cell hook 60853'],
                c['cell hook 60839'], c['cell hook 60965'], c['item sprites'], c['max item sprites in a render'],
                c['max sprites (items + figures) in a render'], c['bands checked'],
                c['item screen bytes changed at band ends'], c['item rows on screen as modelled'],
                c['item rows under a figure the original plotted at render time']))
        say('            timing (simulated T at 28 MHz, no wait states): render-end commit max %d us / avg %d us, '
            'render-start item list max %d us; item hooks per game frame avg %d / max %d us; whole game frame '
            '(original + hooks) max %d us, frames over 20 ms: %d (%d without the item hooks)'
            % (c['render end T max (28 MHz us)'], c['render end T avg (28 MHz us)'],
               c['render start T max (28 MHz us)'], c['item hooks per game frame avg (28 MHz us)'],
               c['item hooks per game frame max (28 MHz us)'], c['patched game frame max (28 MHz us)'],
               c['game frames over 20 ms at 28 MHz'], c['game frames over 20 ms at 28 MHz without the item hooks']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if rzxs:
        u = unit_tests(patch, r)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d states x (edge columns, last sprites, passthrough, negative control) + '
            'direct conversion vs %d plotter/carry cases (+ control) + %d left-entry 4-wide pieces + store '
            'hit/miss/garbage (+ 2 controls) + SWAPNIB + setup + class colour -> %s' % (
                u['states'], u['direct conversion = plotter (random streams) ok'],
                u['left-entry 4-wide plotter ok'], 'PASS' if not uf else 'FAIL %s' % uf))
        say('            items: %d cell-hook cases + %d render paths (start, 22 bands, end) + %d negative controls '
            '(%d detected); figure controls detected: ink/outline %d, stale pattern %d' % (
                u['item cell hooks (registers incl. F, shadow = model) ok'],
                u['item render path (start, 22 bands, end; model) ok'],
                sum(1 for k in u if k.startswith('item') and 'negative control' in k),
                sum(v for k, v in u.items() if k.startswith('item') and 'negative control' in k and k.endswith('detected')),
                u['negative control detected'], u['store stale-pattern negative control detected']))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
