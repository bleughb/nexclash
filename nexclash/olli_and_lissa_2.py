"""Olli and Lissa II: Halloween (Silverbird, 1987; 48K) engine 'olli_and_lissa_2'.
Additive module: reachable only through is_olli_and_lissa_2(). Facts, design, results: games/olli_and_lissa_2.md.

The game plays with interrupts off. Each pass of its loop it draws every moving figure into a copy of the screen (one
routine, the adder here: it first saves what is under the figure) and then copies each figure's rectangle to the
screen and puts the copy back (the player here). The build changes nothing of the game: at each JP of the adder a hook
puts the figure's picture into sprite patterns no sprite shows and stages the figure; at the CALL of the player the
staged figures' sprites are switched on and every other one off; at the CALLs of the fade to black (the title starts
with one) and of the scene played on a black screen every sprite goes off (asm/olli_and_lissa_2_hooks.asm). The adder runs at
28 MHz and its own time is waited out; the player runs as the original.
"""
import collections
import hashlib
import json
import os

from . import hooklib

ROM_ORG = 0x2800
ALT_PAGE, WORK, CPAGE = 24, 26, 28
TC0, NTC = 40, 8                        # the tile cache's pages (asm TC0, NTC): plain tiles made once a picture
A_, F_, SP_, R_, PC_, T_, IFF_ = 0, 1, 12, 15, 24, 25, 26
CMP = list(hooklib.CMP_R)
T_LINE, LINES = 224, 312                # the 48K's frame
ADDER, PLAYER = 0x92E7, 0x9453
FADE, SCENE = 0x9AC4, 0x82B9
# every JP of the adder (a tail call: it returns to the caller's caller)
SITES = {0x82B6: ('e_fig', True), 0x8887: ('e_fig', True), 0x8AFD: ('e_fig', True), 0x8D6D: ('e_fig', True), 0x9052: ('e_fig', True)}
# the CALLs before which the sprites change: (the hook, the CALL's opcode, the routine, the pass's figures dropped?)
PLAYS = {0x80F2: ('e_play', 0xCD, PLAYER, False), 0x8646: ('e_fade', 0xCD, FADE, True), 0x815C: ('e_fade', 0xCD, FADE, True),
         0x8101: ('e_scene', 0xC4, SCENE, True), 0x81DD: ('e_scene', 0xCD, SCENE, True), 0x9950: ('e_fade', 0xCD, FADE, True)}     # (0x9950: the title's first instruction)
LOOP_PLAY = 0x80F2
CODE = (0x8000, 0x9DE9)                 # the game's code
SIGNATURE = (ADDER, bytes.fromhex('ed53fe925e2356ed530a94b72808235e2356ed53ba93'))
NSTG, PER_SET = 12, 64                  # figures staged at a time, patterns a set
KINDS = ((16, 2, False), (24, 3, False), (24, 3, True))    # (rows, bytes a row, masked) the hooks hold: the asm's V_KIND
YMAX = 176
FAST = 8.0
TAIL_ADDR = 0x5C00                      # 0x5B00-0x6A20: the recording never touches it
WINDOW_T = 500 * 312 * 224               # 10 seconds
BOTTOM = 191                            # the sprites' window is the whole display
TOP_Y = 174                             # a figure's box starts at line TOP_Y - y (a masked graphic a line below)
COLOURS_NAME = 'olli_and_lissa_2_colours.json'  # the painted map, beside the snapshot (it holds the figures: not in the repo)
WHITE, BLACK = 0x1FF, 0x000
_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'olli_and_lissa_2.json'), os.path.join(_HERE, 'olli_and_lissa_2.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('olli_and_lissa_2.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def play_view(snap):
    """64K of a SkoolKit 48K snapshot (ROM zeros)."""
    return bytes(16384) + bytes(snap.ram(-1))


def is_olli_and_lissa_2(snap):
    if getattr(snap, 'machine', '48K') != '48K':
        return False
    try:
        m = play_view(snap)
        return m[SIGNATURE[0]:SIGNATURE[0] + len(SIGNATURE[1])] == SIGNATURE[1]
    except Exception:
        return False


def load_colours(z80=None, path=None):
    """The painted map (the painting folder's sheet2colours.py). None when there is none beside the snapshot."""
    p = path or (os.path.join(os.path.dirname(os.path.abspath(str(z80))), COLOURS_NAME) if z80 else None)
    return json.load(open(p)) if p and os.path.exists(p) else None


# ---------------------------------------------------------------------------------------------
# A figure, as the game's adder and player draw it
# ---------------------------------------------------------------------------------------------

def box_of(rows, w, masked):
    """(sprites across, sprites down, rows of the box). A masked figure's box is its mask's: two rows more than the
    graphic, 32 across from a pixel left of it."""
    box = rows + 2 if masked else rows
    return (1 if w == 2 else 2), (box + 15) // 16, box


def kind_of(a, rows, w, y):
    """The asm's V_KIND for the adder's arguments, or None: a size, flags or a place the hooks do not hold."""
    if y >= YMAX or (a and not a & 1):
        return None
    k = (rows, w, bool(a))
    return KINDS.index(k) if k in KINDS else None


def figure(mem, g, m, rows, w):
    """{(column, row): 1 graphic | 2 cleared by the mask} in the figure's box. m = 0: no mask. A mask is 5 bytes a row,
    rows + 2 rows; the box starts at its bit 7: the graphic sits a pixel right of and a row below the box's corner."""
    out = {}
    if m:
        for r in range(rows + 2):
            mk = int.from_bytes(bytes(mem[m + r * 5:m + r * 5 + 5]), 'big')
            for c in range(32):
                if not mk >> (32 - c) & 1:
                    out[(c, r)] = 2
    dx, dy = (1, 1) if m else (0, 0)
    for r in range(rows):
        v = int.from_bytes(bytes(mem[g + r * w:g + (r + 1) * w]), 'big')
        for c in range(w * 8):
            if v >> (w * 8 - 1 - c) & 1:
                out[(c + dx, r + dy)] = 1
    return out


def fig_key(mem, g, rows, w):
    """A graphic by its bytes (the painted map's key)."""
    return hashlib.md5(bytes(mem[g:g + rows * w]) + bytes((rows, w))).hexdigest()[:16]


def placed(shape, x, y, masked):
    """A figure's pixels on the display: {(x, y): v}, inside the play area."""
    out = {}
    for (c, r), v in shape.items():
        px, py = x - (1 if masked else 0) + c, TOP_Y - y + r
        if 0 <= px < 256 and 0 <= py <= BOTTOM:
            out[(px, py)] = v
    return out


def _call(mem, regs, pc, jp=False):
    """The original's routine at pc, CALLed with these registers, on a copy. -> (registers, copy)."""
    r = list(regs)
    m2 = bytearray(mem)
    sp = (r[SP_] - 2) & 65535
    m2[sp:sp + 2] = b'\x00\x00'
    r[SP_], r[PC_] = sp, pc
    return run_orig(None, m2, r, 0, sp + 2)


def adder_times(mem):
    """The adder's own time, T: ({(kind, shift): T at the commonest class of y}, {kind: [class of y]}, {kind: [T more
    in each class]}). The time is a sum of a term in the kind and the shift and a term in the kind and y (the screen
    rows a figure crosses); x beyond the shift does not matter."""
    m = bytearray(mem)
    ptr, pic = TAIL_ADDR, TAIL_ADDR + 8
    m[ptr:ptr + 4] = pic.to_bytes(2, 'little') * 2

    def t(k, sh, y):
        rows, w, masked = KINDS[k]
        regs = [0] * 30
        regs[SP_] = 0xFFF0
        regs[A_] = 1 if masked else 0
        regs[2], regs[3], regs[4], regs[5], regs[6], regs[7] = y, 64 + sh, rows, w, ptr >> 8, ptr & 255
        return _call(m, regs, ADDER)[0][T_]

    base, cls, more = {}, {}, {}
    for k in range(len(KINDS)):
        by_y = [t(k, 0, y) for y in range(YMAX)]
        vals = sorted(set(by_y), key=lambda v: (-by_y.count(v), v))
        if len(vals) > 16:
            raise ValueError('the adder takes more than 16 different times by y')
        cls[k] = [vals.index(v) for v in by_y]
        more[k] = [v - vals[0] for v in vals]
        y0 = by_y.index(vals[0])
        for sh in range(8):
            base[(k, sh)] = t(k, sh, y0)
    return base, cls, more


def colour_tables(cmap, mem, syms):
    """-> (index bytes for PIDX, {page: bytes}, palette (256 9-bit colours), want {(graphic, rows, w): (line, {(c, r): nibble})}).
    A painted figure is known by its graphic's bytes; its tiles are stored as the sprites take them."""
    pal = [0] * 256
    pal[1], pal[2] = WHITE, BLACK
    for li, line in enumerate(cmap['lines']):
        for k, c in enumerate(line):
            pal[(li + 1) * 16 + 1 + k] = c
    by_key = {f['key']: f for f in cmap['figures']}
    index = bytearray()
    pages = {}
    want = {}
    page, at = CPAGE, 0
    for g in sorted(cmap.get('where', {}), key=lambda a: int(a)):
        for rows, w, masked in cmap['where'][g]:
            ga = int(g)
            f = by_key.get(fig_key(mem, ga, rows, w))
            if f is None or len(index) >= 255 * 8:
                continue
            tx, ty, box = box_of(rows, w, masked)
            px = {}
            rowsdata = f['pixels']
            for r in range(box):
                for c in range(tx * 16):
                    v = int(rowsdata[r][c], 16)
                    if v:
                        px[(c, r)] = v
            blob = bytearray()
            for tr in range(ty):
                for tc in range(tx):
                    for r in range(16):
                        for c in range(0, 16, 2):
                            blob.append(px.get((tc * 16 + c, tr * 16 + r), 0) << 4 | px.get((tc * 16 + c + 1, tr * 16 + r), 0))
            if at + len(blob) > 8192:
                page, at = page + 1, 0
            pages.setdefault(page, bytearray(8192))[at:at + len(blob)] = blob
            index += bytes((ga & 255, ga >> 8, rows, w, page)) + (0x4000 + at).to_bytes(2, 'little') + bytes((f['line'] + 1,))
            want[(ga, rows, w)] = (f['line'] + 1, px)
            at += len(blob)
    return bytes(index), {p: bytes(b) for p, b in pages.items()}, pal, want


class Patch:
    name = 'Olli and Lissa II: every moving figure as sprites on its own pixels (alt ROM hooks, the game unchanged)'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000                 # (in the stub's own bank: the game's copy of the screen is not there yet)
    tail_addr = TAIL_ADDR

    def __init__(self, z80=None, mem=None, colours=None, rom=None, times=None):
        self.prof = load_profile()
        h = self.prof['hooks']
        self.syms = sy = {k: int(v, 16) for k, v in h['syms'].items()}
        self.z80, self.colours = z80, colours
        if mem is None and z80 is not None:
            from skoolkit.snapshot import Snapshot
            mem = play_view(Snapshot.get(str(z80)))
        if mem is None or mem[SIGNATURE[0]:SIGNATURE[0] + len(SIGNATURE[1])] != SIGNATURE[1]:
            raise ValueError('not the supported Olli and Lissa II: the figure routine is not where it is expected')
        self.mem = bytes(mem)
        self.rom_code = bytes.fromhex(h['rom']) if rom is None else bytes(rom)
        self.regblock = ROM_ORG + len(self.rom_code)
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        page = bytearray(rom48()[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        work = bytearray(8192)
        for i in range(256):            # (graphic nibble << 4 | mask nibble) -> two pattern bytes
            gn, mn = i >> 4, i & 15
            px = [1 if gn >> (3 - k) & 1 else 0 if mn >> (3 - k) & 1 else 2 for k in range(4)]
            work[sy['TLO'] + i] = px[0] << 4 | px[1]
            work[sy['THI'] + i] = px[2] << 4 | px[3]
        self.times = adder_times(mem) if times is None else times
        base, cls, more = self.times
        for k in range(len(KINDS)):
            work[sy['YC'] + k * YMAX:sy['YC'] + (k + 1) * YMAX] = bytes(cls[k])
            for sh in range(8):
                for ci, mt in enumerate(more[k]):
                    o = sy['TT'] + ((k * 8 + sh) * 16 + ci) * 2
                    work[o:o + 2] = hooklib.lines16(base[(k, sh)] + mt, T_LINE).to_bytes(2, 'little')
        self.planes = {}
        self.want = {}
        pal = [0] * 256
        pal[1], pal[2] = WHITE, BLACK
        if colours:
            index, self.planes, pal, self.want = colour_tables(colours, mem, sy)
            work[sy['PIDX']:sy['PIDX'] + len(index)] = index
            work[sy['V_NP']] = len(index) // 8
        work[sy['V_TCP']] = TC0
        work[sy['V_TCA']:sy['V_TCA'] + 2] = sy['TFIRST'].to_bytes(2, 'little')
        self.work = bytes(work)
        self.palette = pal
        st = bytearray(bytes.fromhex(h['setup']))
        o = sy['pal9'] - 0xD000
        for i, c in enumerate(pal):
            st[o + 2 * i], st[o + 2 * i + 1] = c >> 1, c & 1
        o = sy['pbuf'] - 0xD000
        st[o:o + 256] = mem[0x5B00:0x5C00]
        self.stub_extra = bytes(st)
        alo = ADDER.to_bytes(2, 'little')
        self.sites = [(a, b'\xc3' + alo, b'\xC3' + sy[s].to_bytes(2, 'little')) for a, (s, jp) in SITES.items()]
        self.sites += [(a, bytes((op,)) + t.to_bytes(2, 'little'), bytes((op,)) + sy[s].to_bytes(2, 'little'))
                       for a, (s, op, t, drop) in PLAYS.items()]
        known = set(SITES) | set(PLAYS)
        for t in (ADDER, PLAYER, FADE, SCENE):   # every CALL or JP of the routines is one of the sites
            lo, hi = t & 255, t >> 8
            for a in range(CODE[0], CODE[1]):
                if mem[a] in (0xCD, 0xC3, 0xC4, 0xCC, 0xD4, 0xDC, 0xC2, 0xCA, 0xD2, 0xDA) and mem[a + 1] == lo and mem[a + 2] == hi \
                        and a not in known:
                    raise ValueError('a CALL of 0x%04X the build does not know, at 0x%04X' % (t, a))
        self.extra_banks = {12: self.page + bytes(8192), 13: self.work + bytes(8192), TC0 // 2: bytes(16384)}  # (the cache's index: zeros)
        for pg, data in self.planes.items():
            cur = self.extra_banks.get(pg // 2, bytes(16384))
            o = (pg & 1) * 8192
            self.extra_banks[pg // 2] = cur[:o] + data + cur[o + 8192:]

    def apply(self, snap):
        if snap.is128:
            raise ValueError('the Olli and Lissa II patch expects the 48K snapshot')
        for a, old, new in self.sites:
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            b = bytearray(snap.banks[bank])
            o = a & 0x3FFF
            if bytes(b[o:o + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, bytes(b[o:o + len(old)]).hex(), old.hex()))
            b[o:o + len(new)] = new
            snap.banks[bank] = bytes(b)


# ---------------------------------------------------------------------------------------------
# The Next side, as a hook sees it
# ---------------------------------------------------------------------------------------------

class State:
    """What stays between hooks: the state page, the sprites' patterns and attributes, where the ports stand."""
    def __init__(self, patch):
        self.work = bytearray(patch.work)
        self.pattern = bytearray(b'\xEE' * 16384)       # (as anything left them)
        self.tc = {TC0 + i: bytearray(8192) if i < 2 else bytearray(b'\xEE' * 8192) for i in range(NTC)}    # (the file holds the first two)
        self.attrs = [[0] * 5 for _ in range(128)]      # the setup switches every sprite off
        self.ports = (0, 0, 0)
        self.t = collections.Counter()
        self.line = 0.0
        self.t_in = 0.0


class View:
    """64K as the hooks see it: the alt ROM image, the state page at slot 0, a painted page at slot 2, the game."""
    def __init__(self, mem, rom, st, planes):
        self.mem, self.rom, self.st, self.planes = mem, rom, st, planes
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if a < 0x2000:
            return self.st.work[a] if self.model.nr.get(0x50, 255) == WORK else self.rom[a]
        if a < 0x4000:
            return self.rom[a]
        if a < 0x6000:
            p = self.model.nr.get(0x52, 10)
            if p in self.st.tc:
                return self.st.tc[p][a - 0x4000]
            if p != 10:
                return self.planes[p][a - 0x4000]
        return self.mem[a]

    def __setitem__(self, a, v):
        if a < 0x2000:
            if self.model.nr.get(0x50, 255) == WORK:
                self.st.work[a] = v
            return
        if a < 0x4000:
            return
        if a < 0x6000 and self.model.nr.get(0x52, 10) in self.st.tc:
            self.st.tc[self.model.nr.get(0x52, 10)][a - 0x4000] = v
            return
        if a < 0x6000 and self.model.nr.get(0x52, 10) != 10:
            self.model.c['write to a painted page!'] += 1
            return
        self.mem[a] = v


class Model(hooklib.NextModel):
    """The shared model with the sprites carried from hook to hook, and a 4-bit pattern known by its own half."""
    def __init__(self, sim, st):
        super().__init__(sim, 0, t_line=T_LINE, lines=LINES)
        self.real = st.line
        self.pattern, self.attrs = st.pattern, st.attrs
        self.pidx, self.aidx, self.abyte = st.ports
        self.st = st

    def halves(self):
        return {(a[3] & 63) * 2 + (a[4] >> 6 & 1) for a in self.attrs if a[3] & 0x80}

    def write_port(self, regs, port, value, *x):
        if port & 255 == 0x5B and port != 0x243B and port != 0x253B and port != 0x303B:
            if self.pidx >> 7 in self.halves():
                self.c['upload into a shown pattern!'] += 1
            self.pattern[self.pidx] = value
            self.pidx = (self.pidx + 1) & 0x3FFF
            self.c['pattern bytes'] += 1
            return
        super().write_port(regs, port, value, *x)

    def keep(self):
        self.st.ports = (self.pidx, self.aidx, self.abyte)


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def run_hook(patch, st, rom, mem, regs, site, stop, sp_stop, limit=6000000):
    """Run the patched code from `site` on a copy of the game's memory until PC = stop with SP = sp_stop and the ROM back
    at slot 0. -> (registers, copy, model)."""
    from . import simpool
    m2 = bytearray(mem)
    for a, old, new in patch.sites:
        m2[a:a + len(new)] = new
    v = View(m2, rom, st, patch.planes)
    s = simpool.machine(_rw(), v, list(regs), 'olli2-hook')
    model = Model(s, st)
    v.model = model
    R = s.registers
    R[PC_] = site
    n = 0
    while True:
        s.opcodes[v[R[PC_]]]()
        n += 1
        if R[PC_] == stop and R[SP_] == sp_stop and model.nr.get(0x50, 255) == 255:
            break
        if n > limit:
            raise AssertionError('hook at %04X did not end (PC %04X)' % (site, R[PC_]))
    st.t[site] += model.now() - st.line
    st.t_in = st.line
    st.line = model.now()
    model.keep()
    model.n = n
    for a, old, new in patch.sites:
        m2[a:a + len(old)] = old
    return list(R), m2, model


def run_orig(rom, mem, regs, stop, sp=None, limit=6000000):
    """The original from regs' PC until PC = stop (and SP = sp); with stop = 0, until SP = sp."""
    from . import simpool
    m2 = bytearray(mem) if rom is None else bytearray(rom[:0x4000]) + bytearray(mem[0x4000:])
    s = simpool.machine(_rw(), m2, list(regs), 'olli2-orig')
    R = s.registers
    n = 0
    while True:
        s.opcodes[m2[R[PC_]]]()
        n += 1
        if (stop == 0 or R[PC_] == stop) and (sp is None or R[SP_] == sp):
            break
        if n > limit:
            raise AssertionError('original from %04X did not reach %04X' % (regs[PC_], stop))
    return list(R), m2


def staged(st, sy):
    """The figures staged for the next play: [(x, y, sprites across, down, line, sprites, first pattern)]."""
    out = []
    for i in range(st.work[sy['V_NS']]):
        e = st.work[sy['STG'] + i * 8:sy['STG'] + i * 8 + 8]
        out.append((e[0] | e[1] << 8, e[2], e[3], e[4], e[5], e[6], e[7]))
    return out


def sprite_pixels(st, first=0, n=128, c=None):
    """What sprites first..first+n-1 show on the display, inside their window, a later one in front:
    {(x, y): palette line * 16 + nibble}."""
    out = {}
    for i in range(first, first + n):
        a = st.attrs[i]
        if not a[3] & 0x80:
            continue
        if not a[3] & 0x40 or not a[4] & 0x80:
            if c is not None:
                c['a shown sprite is not a 4-bit one!'] += 1
            continue
        X, Y = a[0] | (a[2] & 1) << 8, a[1] | (a[4] & 1) << 8
        p = (a[3] & 63) * 2 + (a[4] >> 6 & 1)
        line = a[2] >> 4
        for r in range(16):
            y = Y - 32 + r
            if not 0 <= y <= BOTTOM:
                continue
            for k in range(16):
                b = st.pattern[p * 128 + r * 8 + k // 2]
                v = b >> 4 if k % 2 == 0 else b & 15
                x = X - 32 + k
                if v and 0 <= x < 256:
                    out[(x, y)] = line * 16 + v
    return out


def screen_bit(mem, x, y):
    return mem[0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x >> 3] >> (7 - (x & 7)) & 1


def flat(m):
    return m.memory[0] + m.memory[1] + m.memory[2] + m.memory[3] if hasattr(m, 'memory') else bytes(m)


def site_stop(pc, mem, sp):
    """Where a site's hook must have left everything as the original: (PC, SP). A JP of the adder: back at its
    caller's caller. A CALL before which the sprites change: the routine's first instruction."""
    if pc in SITES:
        return mem[sp] | mem[(sp + 1) & 65535] << 8, (sp + 2) & 65535
    return PLAYS[pc][2], (sp - 2) & 65535


def taken(pc, regs):
    """A conditional CALL (CALL NZ) is a site only when it is taken."""
    return pc in SITES or PLAYS[pc][1] == 0xCD or not regs[F_] & 0x40


def fig_args(regs):
    return regs[A_], regs[6] << 8 | regs[7], regs[2], regs[3], regs[4], regs[5]


class Pass:
    """The figures the game draws between two copies to the screen, as the hooks should have them."""
    def __init__(self):
        self.figs = []                  # (graphic, mask, rows, w, x, y, sprites) the hooks stage, in order

    def add(self, mem, a, hl, y, x, rows, w):
        """-> 'staged' | 'left' | 'full'. The same rules as the hooks'."""
        k = kind_of(a, rows, w, y)
        if k is None:
            return 'left'
        g = mem[hl] | mem[hl + 1] << 8
        m = mem[hl + 2] | mem[hl + 3] << 8 if KINDS[k][2] else 0
        n = (lambda t: t[0] * t[1])(box_of(rows, w, bool(m)))
        if len(self.figs) >= NSTG or sum(f[6] for f in self.figs) + n > PER_SET:
            return 'full'
        self.figs.append((g, m, rows, w, x, y, n))
        return 'staged'


def want_pixels(patch, mem, figs, plain=False):
    """What the sprites should show for a pass's figures, a later one in front: {(x, y): line * 16 + nibble}."""
    out = {}
    for g, m, rows, w, x, y, n in figs:
        p = None if plain else patch.want.get((g, rows, w))
        if p:
            out.update({k: p[0] * 16 + v for k, v in placed(p[1], x, y, bool(m)).items()})
        else:
            out.update(placed(figure(mem, g, m, rows, w), x, y, bool(m)))
    return out


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original (PLAYBOOK 6). At each JP of the adder the patched code runs on a copy of the state, the Next
    side carried from site to site, and must leave every register (R too) and all the game's memory as the original
    does when the adder has returned; at each CALL before which the sprites change, when the routine starts. After the
    loop's play the sprites must show exactly the figures drawn since the last one, as a model of the adder has them
    (or as the painted map has them), and the model must be what the original has just copied to the screen; after
    the other CALLs no sprite may show. -> (Counter, examples, states)."""
    from . import rzx as RZ
    from .nextboot import alt_image
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    kept = collections.Counter()
    rom = bytes(alt_image(patch))
    st = State(patch)
    sy = patch.syms
    box = {'orig_t': 0, 'pass': Pass()}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(ex[key]) < 5:
            ex[key].append(detail)

    def on(pc, sim):
        if box.get('dead'):
            return
        try:
            on_(pc, sim)
        except AssertionError as e:
            box['dead'] = True
            fail('a hook does not end', str(e))

    def on_(pc, sim):
        m, R = sim.memory, sim.registers
        regs = list(R)
        if not taken(pc, regs):
            return
        mem = bytearray(flat(m))
        sp = regs[SP_]
        if regs[IFF_]:
            fail('interrupts on at a hook', hex(pc))
        stop_pc, stop_sp = site_stop(pc, mem, sp)
        key = (pc, regs[4], regs[5], regs[A_] & 1) if pc in SITES else (pc,)
        if collect and kept[key] < collect:
            kept[key] += 1
            states.append((pc, bytes(mem), tuple(regs), bytes(st.work)))
        Ro, mo = run_orig(rom, mem, regs, stop_pc, stop_sp)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, stop_pc, stop_sp)
        bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
        if bad:
            fail('registers after the hook at %04X' % pc, bad)
        if mp[0x4000:] != mo[0x4000:]:
            fail('the hook at %04X writes game memory' % pc, [hex(a) for a in range(0x4000, 65536) if mp[a] != mo[a]][:8])
        t = Ro[T_] - regs[T_]
        box['orig_t'] += t
        dd = box.setdefault('d', {}).setdefault(key, [0, 0, 10 ** 9, -10 ** 9])
        dv = int((st.line - st.t_in) - t)
        dd[0] += dv
        dd[1] += 1
        dd[2], dd[3] = min(dd[2], dv), max(dd[3], dv)
        box['cum'] = box.get('cum', 0) + dv     # how far the game is behind (+) or ahead of the original, so far
        if pc == LOOP_PLAY:
            box.setdefault('drift', []).append((box['orig_t'], box['cum']))
        if model.nr[7] & 3:
            fail('a hook leaves its speed', model.nr[7])
        if model.nr.get(0x52, 10) != 10:
            fail('a hook leaves a page mapped', model.nr.get(0x52))
        bad = {k: v for k, v in model.c.items() if k.endswith('!')}
        if bad:
            fail('a write where none may be', bad)
        P = box['pass']
        if pc in SITES:
            c['adds'] += 1
            r = P.add(mem, *fig_args(regs))
            c['adds ' + r] += 1
            if r in ('left', 'full'):
                c['figures left as the game draws them'] += 1
                if len(ex['left']) < 5:
                    ex['left'].append((c['adds'], hex(pc), r) + fig_args(regs))
            got = staged(st, sy)
            if len(got) != len(P.figs):
                fail('the stage does not hold the pass\'s figures', (c['adds'], hex(pc), len(got), len(P.figs)))
            return
        box['pass'] = Pass()
        if st.work[sy['V_NS']]:
            fail('figures stay staged after the hook at %04X' % pc, st.work[sy['V_NS']])
        if PLAYS[pc][3]:
            # the screen fades, goes black or is the title's: no sprite
            c['sprites off'] += 1
            if any(a[3] & 0x80 for a in st.attrs):
                fail('sprites stay on at %04X' % pc, sum(1 for a in st.attrs if a[3] & 0x80))
            return
        # the loop's play: the sprites are the pass's figures, and those are what the original copies to the screen
        c['plays'] += 1
        c['plays with figures'] += bool(P.figs)
        c['figures'] += len(P.figs)
        c['most figures at a time'] = max(c['most figures at a time'], len(P.figs))
        c['most sprites shown'] = max(c['most sprites shown'], sum(1 for a in st.attrs if a[3] & 0x80))
        got = sprite_pixels(st, c=c)
        want = want_pixels(patch, mem, P.figs)
        c['sprite pixels'] += len(got)
        c['painted figures'] += sum(1 for f in P.figs if (f[0], f[2], f[3]) in patch.want)
        if got != want:
            dk = [k for k in set(got) | set(want) if got.get(k) != want.get(k)]
            fail('the sprites are not the pass\'s figures', (c['plays'], hex(pc), len(P.figs), len(dk), sorted(dk)[:3]))
        _, ms = run_orig(rom, mem, regs, pc + 3, sp)        # the original's play, to its end
        plain = want_pixels(patch, mem, P.figs, plain=True)
        off = sum(1 for (px, py), v in plain.items() if screen_bit(ms, px, py) != (v == 1))
        if off:
            c['plays the original draws unlike the model'] += 1
            if len(ex['plays the original draws unlike the model']) < 5:
                ex['plays the original draws unlike the model'].append((c['plays'], hex(pc), len(P.figs), off, P.figs[:3]))
        if progress:
            progress(c['plays'], st, ms)

    fc, err = RZ.trace(rzx_path, set(SITES) | set(PLAYS), on, stop=stop)
    c['frames'] = fc
    if err:
        c['replay stopped!'] += 1
        ex['replay'].append(err)
    c['T original'] = box['orig_t']
    c['T hooks'] = int(sum(st.t.values()))
    c['left for want of room'] = st.work[sy['V_FULL']]
    c['left for their size'] = st.work[sy['V_ODD']]
    if c['figures left as the game draws them']:
        fail('figures left as the game draws them', (c['figures left as the game draws them'], c['adds left'], c['adds full']))
    if c['plays the original draws unlike the model']:
        fail('the original draws figures unlike the model', c['plays the original draws unlike the model'])
    if c['adds']:
        # a hook's time over the original is owed and given back in the adds' windows that follow. New pictures (a new
        # room, Olli's first steps) cost their tiles once: the game falls behind a little and makes it up over the
        # next seconds. The limits: 3 frames in any 10 seconds (0.6%), 0.2% over the recording
        dr = box.get('drift', [])           # (the hooks' and the original's time up to each play: the game's own
        j = 0                               # code between the sites takes the same in both)
        for i in range(len(dr)):            # the most the game gains or loses over any 10 seconds of the sites' time
            while dr[i][0] - dr[j][0] > WINDOW_T:
                j += 1
            off = int(dr[i][1] - dr[j][1])
            c['most T the game is ever behind the original'] = max(c['most T the game is ever behind the original'], off)
            c['most T the game is ever ahead of the original'] = max(c['most T the game is ever ahead of the original'], -off)
        if max(c['most T the game is ever behind the original'], c['most T the game is ever ahead of the original']) > 3 * LINES * T_LINE \
                or abs(c['T hooks'] - box['orig_t']) > 0.002 * fc * LINES * T_LINE:
            fail('the hooks do not take the original\'s time', (c['most T the game is ever behind the original'],
                                                                 c['most T the game is ever ahead of the original'], c['T hooks'], box['orig_t']))
    ex['hook time less the original, T (site, rows, bytes, masked): mean, least, most, calls'] = sorted(
        (tuple('%04X' % k[0] if i == 0 else k[i] for i in range(len(k))), v[0] // max(1, v[1]), v[2], v[3], v[1]) for k, v in box.get('d', {}).items())
    return c, dict(ex), states


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites). -> problems."""
    from . import nextboot
    from . import z80tonex as zt
    s = zt.Z80Snapshot(str(z80))
    if patch is not None:
        patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, getattr(patch, 'slot1', None), patch is not None)[0])
    tail = zt.choose_tail_addr(s, size, TAIL_ADDR, False)[0]
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if tail <= a < tail + size or (nexload and patch is None and 0x5B00 <= a < 0x5C00):
                continue                # (a patched build's setup puts the printer buffer back: compared)
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def unit_tests(patch, states, neg=None):
    """The paths the recordings do not reach, from captured states (site, memory, registers, state page)."""
    from .nextboot import alt_image
    c = collections.Counter()
    rom = bytes(alt_image(patch))
    sy = patch.syms

    def ok(name, cond):
        c[name] += 1
        if not cond:
            c[name + ' FAILED!'] += 1

    def both(st, pc, mem, regs):
        sp = regs[SP_]
        stop_pc, stop_sp = site_stop(pc, mem, sp)
        Ro, mo = run_orig(rom, mem, list(regs), stop_pc, stop_sp)
        Rp, mp, model = run_hook(patch, st, rom, mem, list(regs), pc, stop_pc, stop_sp)
        return ([(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]] or mp[0x4000:] != mo[0x4000:]), model

    plays = [s for s in states if s[0] == LOOP_PLAY]
    figs = [s for s in states if s[0] in SITES]
    by_kind = collections.defaultdict(list)
    for s in figs:
        k = kind_of(s[2][A_], s[2][4], s[2][5], s[2][2])
        if k is not None:
            by_kind[k].append(s)
    if not plays or not figs:
        return c
    ppc, pmem, pregs, _ = plays[0]

    def at(pc, st, flags=None):
        r = list(pregs)
        r[PC_] = pc
        if flags is not None:
            r[F_] = flags
        return both(st, pc, pmem, r)[0]

    def play(st):
        return at(ppc, st)

    def shown(st, P, mem):
        return sprite_pixels(st) == want_pixels(patch, mem, P.figs)

    def on(st):
        return sum(1 for a in st.attrs if a[3] & 0x80)

    def add(st, P, pc, mem, regs):
        bad, model = both(st, pc, mem, list(regs))
        P.add(mem, *fig_args(regs))
        return bad, model

    names = ('16 rows of 2 bytes', '24 rows of 3 bytes', '24 rows of 3 bytes with a mask')
    for k in sorted(by_kind):
        for pc, mem, regs, _ in by_kind[k][:3]:
            regs = list(regs)
            st = State(patch)
            P = Pass()
            b1, _ = add(st, P, pc, mem, regs)
            b3 = play(st)
            first = {(a[3] & 63) * 2 + (a[4] >> 6 & 1) for a in st.attrs if a[3] & 0x80}
            ok('%s: staged, shown at the play' % names[k], not (b1 or b3) and len(P.figs) == 1 and shown(st, P, mem) and bool(first))
            r2 = list(regs)
            r2[3] = (r2[3] + 3) & 255
            P = Pass()
            b1, model = add(st, P, pc, mem, r2)
            b3 = play(st)
            second = {(a[3] & 63) * 2 + (a[4] >> 6 & 1) for a in st.attrs if a[3] & 0x80}
            ok('the next pass: the other pattern set, no shown pattern written', not (b1 or b3) and shown(st, P, mem) and not first & second
               and not model.c['upload into a shown pattern!'])
            b3 = play(st)
            ok('a play with nothing drawn: every sprite off', not b3 and not on(st))
            # at the right edge: the ninth bit of x
            st = State(patch)
            P = Pass()
            r4 = list(regs)
            r4[3] = 230
            b1, _ = add(st, P, pc, mem, r4)
            b3 = play(st)
            ok('at the right edge', not (b1 or b3) and shown(st, P, mem) and any(a[2] & 1 for a in st.attrs if a[3] & 0x80))
            # sizes, places and flags the hooks do not hold: the adder as the original, nothing staged
            for name, i, v in (('a row more', 4, regs[4] + 1), ('a byte more a row', 5, regs[5] + 1), ('above the top of the screen', 2, YMAX + 4),
                               ('a mask asked for and not used', A_, 2)):
                st = State(patch)
                r3 = list(regs)
                r3[i] = v
                b1, model = both(st, pc, mem, r3)
                play(st)
                ok('%s: left to the game' % name, not b1 and st.work[sy['V_ODD']] == 1 and not model.c['pattern bytes'] and not on(st))
            # the stage full, the pattern set full
            st = State(patch)
            st.work[sy['V_NS']] = NSTG
            b1, model = both(st, pc, mem, regs)
            ok('no room in the stage: left to the game', not b1 and st.work[sy['V_FULL']] == 1 and not model.c['pattern bytes'])
            st = State(patch)
            st.work[sy['V_PN']] = PER_SET
            b1, model = both(st, pc, mem, regs)
            ok('no room in the pattern set: left to the game', not b1 and st.work[sy['V_FULL']] == 1 and not model.c['pattern bytes']
               and st.work[sy['V_NS']] == 0)
            # the tile cache full: the tiles made each time, nothing kept
            st = State(patch)
            P = Pass()
            st.work[sy['V_TCP']] = TC0 + NTC - 1
            st.work[sy['V_TCA']:sy['V_TCA'] + 2] = (0x6000).to_bytes(2, 'little')
            b1, _ = add(st, P, pc, mem, regs)
            b3 = play(st)
            ok('the tile cache full: made each time', not (b1 or b3) and shown(st, P, mem) and not any(st.tc[TC0][:0x800]))
            # the same figure through the other JPs (not every one is reached with every kind): the same hook
            for other in [a for a in SITES if a != pc]:
                st = State(patch)
                P = Pass()
                b1, _ = add(st, P, other, mem, regs)
                b3 = play(st)
                ok('through the JP at %04X' % other, not (b1 or b3) and shown(st, P, mem))
            # two figures: the later one in front
            st = State(patch)
            P = Pass()
            add(st, P, pc, mem, regs)
            r5 = list(regs)
            r5[3] = (r5[3] + 5) & 255
            b1, _ = add(st, P, pc, mem, r5)
            b3 = play(st)
            ok('two figures over each other: the later in front', not (b1 or b3) and len(P.figs) == 2 and shown(st, P, mem))
            # the screen fades, goes black, the title: shown figures off; figures of a pass that ends there are dropped
            for hpc, (h, op, target, drop) in PLAYS.items():
                if not drop:
                    continue
                st = State(patch)
                P = Pass()
                add(st, P, pc, mem, regs)
                play(st)
                was = on(st)
                add(st, Pass(), pc, mem, regs)
                b2 = at(hpc, st, flags=0)
                ok('the CALL at %04X: every sprite off, nothing staged' % hpc, not b2 and was and not on(st) and st.work[sy['V_NS']] == 0)
                b3 = play(st)
                ok('a play after it shows nothing', not b3 and not on(st))
            if PLAYS.get(0x8101, (0, 0))[1] == 0xC4:
                st = State(patch)
                P = Pass()
                add(st, P, pc, mem, regs)
                play(st)
                r = list(pregs)
                r[F_] = 0x40
                r[PC_] = 0x8101
                Ro, mo = run_orig(rom, pmem, r, 0x8104, r[SP_])
                Rp, mp, model = run_hook(patch, st, rom, pmem, r, 0x8101, 0x8104, r[SP_])
                ok('the CALL NZ not taken: nothing changes', Ro[:PC_] == Rp[:PC_] and mp[0x4000:] == mo[0x4000:] and shown(st, P, mem))
    return c


def _code_patch(patch, sym, new):
    rc = bytearray(patch.rom_code)
    a = patch.syms[sym] - ROM_ORG
    rc[a:a + len(new)] = new
    return Patch(z80=patch.z80, mem=patch.mem, colours=patch.colours, rom=bytes(rc), times=patch.times)


def _find(patch, sym, pat):
    """The address of the first `pat` in the hook code from a symbol on (a macro's own lines have no symbol)."""
    return ROM_ORG + patch.rom_code.index(pat, patch.syms[sym] - ROM_ORG)


def _code_at(patch, addr, new):
    rc = bytearray(patch.rom_code)
    rc[addr - ROM_ORG:addr - ROM_ORG + len(new)] = new
    return Patch(z80=patch.z80, mem=patch.mem, colours=patch.colours, rom=bytes(rc), times=patch.times)


def negative_patches(patch):
    """Broken builds a verify run on a recording must catch: [(name, patch)]."""
    r = patch.rom_code[patch.syms['fig_end.n_rout'] - ROM_ORG + 1]
    rpa = _find(patch, 'e_play', b'\xCD' + patch.syms['hlib_r_set'].to_bytes(2, 'little')) - 2      # LD A,R_PLAY
    rp = patch.rom_code[rpa - ROM_ORG + 1]
    cm = _find(patch, 'e_fade', b'\xCD' + patch.syms['commit'].to_bytes(2, 'little'))
    return [('R one more after an add', _code_patch(patch, 'fig_end.n_rout', bytes((0x3E, (r + 1) & 255)))),
            ('R one more after a play', _code_at(patch, rpa, bytes((0x3E, (rp + 1) & 255)))),
            ('the ninth bit of x is not set', _code_patch(patch, 'attrs.n_x8', b'\x00')),
            ('a figure\'s sprites are not switched on', _code_patch(patch, 'attrs.n_vis', b'\xF6\x40')),
            ('a play leaves the old sprites on', _code_patch(patch, 'commit.n_off', b'\x00\x00\x00\x00')),
            ('the pattern sets do not change over', _code_patch(patch, 'commit.n_set', b'\x00\x00\x00')),
            ('a figure is not staged', _code_patch(patch, 'sprite.n_st', b'\x00')),
            ('a pattern byte is not sent', _code_patch(patch, 'one.n_o', b'\x00')),
            ('the adder\'s time is not waited out', _code_patch(patch, 'fig_end.n_t', b'\x21\x00\x00')),
            ('the fade leaves the sprites on', _code_at(patch, cm, b'\x21\x00\x00'))]


NEG_UNIT = {'the ninth bit of x is not set', 'the fade leaves the sprites on'}  # (not reached in the first frames: their unit cases)
NEG_FRAMES = 2500


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    os.makedirs(out, exist_ok=True)
    say('Game      : %s' % name)
    cmap = load_colours(z80)
    try:
        patch = Patch(z80=z80)
        enh = Patch(z80=z80, colours=cmap, times=patch.times) if cmap else None
    except ValueError as e:
        say('Engine    : olli_and_lissa_2: %s' % e)
        say('Result    : FAILED')
        return False
    say('Engine    : olli_and_lissa_2 (nothing of the game changes; each figure the game draws into its copy of the screen -> '
        'sprites on the same pixels, switched on when the copy goes to the screen: 1 where the graphic is set, 2 where the mask clears)')
    ok = True
    plain = os.path.join(out, name + '.nex')
    zt.convert(str(z80), plain, TAIL_ADDR, quiet=True)
    bad = boot_check(plain, z80, None)
    ok = ok and not bad
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    builds = [('Sprites', '_sprites', patch, lambda: Patch(z80=z80, times=patch.times))]
    if enh:
        builds.append(('Enhanced', '_enhanced', enh, lambda: Patch(z80=z80, colours=cmap, times=patch.times)))
    for label, suffix, pt, mk in builds:
        nex = os.path.join(out, name + suffix + '.nex')
        zt.convert(str(z80), nex, patch=pt, quiet=True)
        bad = boot_check(nex, z80, mk())
        ok = ok and not bad
        say('%-10s: %s  %s  boot %s%s' % (label, os.path.basename(nex), md5(nex), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200],
                                         '' if pt is patch else '  (%d painted figures, %d palette lines, %d pages)' % (
                                             len(pt.want), len(cmap['lines']), len(pt.planes))))
    states = []
    quick = getattr(a, 'quick', None)
    for r in list(getattr(a, 'rzx', None) or []):
        for label, pt in [('Verify', patch)] + ([('Painted', enh)] if enh else []):
            cc, ex, st = verify(pt, r, stop=quick, collect=4 if pt is patch else 0)
            states += st
            fails = {k: v for k, v in cc.items() if k.endswith('!')}
            ok = ok and not fails
            say('%-10s: %s  %d frames, %d adds, %d plays (%d with figures), %d figures (%d painted), %d sprite pixels, most figures at a '
                'time %d, most sprites %d, %d plays the original draws unlike the model, sprites off at %d fades and scenes -> %s' % (
                    label, os.path.basename(r), cc['frames'], cc['adds'], cc['plays'], cc['plays with figures'], cc['figures'],
                    cc['painted figures'], cc['sprite pixels'], cc['most figures at a time'], cc['most sprites shown'],
                    cc['plays the original draws unlike the model'], cc['sprites off'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
            say('Pace      : %s  the adds and plays %d T in the original, the hooks %d T (%+.3f%% of the recording\'s time); over any '
                '10 seconds of the hooks\' time the game loses at most %d T on the original and gains at most %d T (a frame is %d T)' % (
                    os.path.basename(r), cc['T original'], cc['T hooks'],
                    100.0 * (cc['T hooks'] - cc['T original']) / max(1, cc['frames'] * LINES * T_LINE),
                    cc['most T the game is ever behind the original'], cc['most T the game is ever ahead of the original'], LINES * T_LINE))
            for k, v in ex.items():
                say('            %s: %s' % (k, str(v)[:1500]))
    if states:
        for label, pt in [('Verify', patch)] + ([('Painted', enh)] if enh else []):
            u = unit_tests(pt, states)
            uf = {k: v for k, v in u.items() if k.endswith('!')}
            ok = ok and not uf
            say('Unit      : %s: %s -> %s' % (label, ', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.endswith('!')),
                                             'PASS' if not uf else 'FAIL %s' % uf))
    if getattr(a, 'rzx', None):
        r0 = list(a.rzx)[0]
        negs = negative_patches(patch)
        missed = []
        for nm, q in negs:
            if nm in NEG_UNIT:
                cc = unit_tests(q, states)
            else:
                cc, _, _ = verify(q, r0, stop=min(quick or NEG_FRAMES, NEG_FRAMES))
            if not any(k.endswith('!') for k in cc):
                missed.append(nm)
        ok = ok and not missed
        say('Negative  : %d broken builds (%s), %d detected%s' % (len(negs), os.path.basename(r0), len(negs) - len(missed),
                                                                 '' if not missed else '; NOT detected: ' + ', '.join(missed)))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
