"""Target Renegade (Imagine 1988, 128K) engine 'renegade'. Additive module: reachable only through
is_renegade(). Game facts and decisions: games/target_renegade.md.

Game facts (analysis of the reference snapshot and Dean's RZX):
  The .z80 is the 128K BASIC loader at its last PAUSE 0 (then POKEs done, RANDOMIZE USR 40576).
  40576: DI, relocate 0xC708 -> 0x5B08 (2296 bytes), OUT (0x1FFD),4 - decoded as 7FFD on a 128K
  (bank 4, ROM 0) -, JP 23340. In play: 7FFD = 0 (ROM 0, bank 0 at C000), IM 2 (I = 0x9F, dummy
  handler 0xBFBF: JP / EI / RET), interrupts off except around the frame HALT.
  Main loop 55168: logic ... 59531 draw every figure into the back buffer (masked, with an undo
  stack), HALT, 24040 music (bank 3), 62565 copy buffer -> screen (stack blit, beeper toggles),
  56332 restore the buffer from the undo stack, JP 55168.
  Back buffer: 0xC000-0xCFFF (bank 0) = screen char rows 1-16 in screen layout (two 2K thirds),
  line y (0-127) -> address word at 0xD000 + 2y (low byte | column).
  Plotters: 55276 (as stored) / 55722 (mirrored by the table 0xD100 - a bit reverse except
  58 -> 76). HL -> part record: [-2] y offset, [-1] x offset, [0..1] graphic (bit 0 cleared);
  D = y, E = x (byte columns). Graphic: width W (bytes), height R (lines), then W*R (mask,
  graphic) pairs, rows serpentine (odd rows from the right). Byte-column aligned, no shifts.
  Callers: 59568 (object chains of the sorted display list 0xD200, from 59561) and 59441 (the
  extras of 59404).
"""
import collections
import json
import os

ENTRY = 40576                    # USR target of the loader
LOADER_PC = 7997                 # ROM PAUSE in the loader snapshot
PLOT, PLOT_M = 55276, 55722
PLOT_RET = {55721: PLOT, 56220: PLOT_M}
COMMIT = 62565                   # buffer -> screen copy (game frame end)
RESTORE = 56332                  # restore the buffer from the undo stack (right after the copy)
DRAW_ALL = 59531                 # draws every figure (buffer is clean scenery at its entry)
OBJ_CALL = 59561                 # CALL 59568: one display-list entry (A = object record low byte)
EXTRAS = 59404
YTAB, MIRTAB = 0xD000, 0xD100
BUF = (0xC000, 0xD000)
SCREEN_ROW0 = 1                  # buffer line 0 = screen line 8
CMP = list(range(0, 15)) + list(range(16, 25)) + [26, 27, 28]
# sprite palette: index 0 transparent, 1-7 colours, 8 black, 9-15 bright colours (as midres)
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
CBLACK = 8
INK, BODY = 8, 7                 # default colours (Dean 2026-10-14: all characters grey = colour 7)
RGB16 = None

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'target_renegade_colours.json')
SIG = (PLOT, bytes.fromhex('e5d52b2b7a962387577b96235fe5'))


def is_renegade(snap):
    a, sig = SIG
    return snap.machine != '48K' and bytes(snap.memory[a:a + len(sig)]) == sig and \
        bytes(snap.memory[ENTRY:ENTRY + 4]) == bytes.fromhex('f311085b')


def cidx(c, bright):
    return CBLACK if c == 0 else c + 8 * bright


def ink_of(attr):
    return cidx(attr & 7, (attr >> 6) & 1)


def paper_of(attr):
    return cidx((attr >> 3) & 7, (attr >> 6) & 1)


def rgb(idx):
    from . import coloursheet as cs
    global RGB16
    if RGB16 is None:
        RGB16 = cs.palette_rgb(PALETTE)
    return RGB16[idx]


def rotl(v):
    return ((v << 1) | (v >> 7)) & 255


def entry_check(m, g):
    return m ^ rotl(g)


# ---------------------------------------------------------------------------------------------
# The plot model (checked against the game over the whole RZX: 24669 plots, every byte equal)
# ---------------------------------------------------------------------------------------------

def plot_params(get, R, pc):
    """Registers at a plot entry -> dict(gfx, W, R, x (byte column, may be < 0 or > 31), y (buffer
    line), mir)."""
    hl = R[6] << 8 | R[7]
    mir = pc == PLOT_M
    yoff, xoff = get((hl - 2) & 0xFFFF), get((hl - 1) & 0xFFFF)
    gfx = (get(hl) | get((hl + 1) & 0xFFFF) << 8) & 0xFFFE
    W, Rr = get(gfx), get((gfx + 1) & 0xFFFF)
    y = (R[4] - yoff) & 127                 # doubled as the 0xD000 table index (mod 256)
    x = ((R[5] + xoff + 1 - W) if mir else (R[5] - xoff)) & 255
    if x >= 128:
        x -= 256
    return dict(gfx=gfx, W=W, R=Rr, x=x, y=y, mir=int(mir))


def entry_index(W, r, k, mir):
    """Column k (0 = leftmost on screen) of row r -> graphic entry index (serpentine rows)."""
    i = k if r % 2 == 0 else W - 1 - k
    return W - 1 - i if mir else i


def stored_index(W, r, c):
    """Stored (unmirrored) column c of row r -> entry index."""
    return r * W + (c if r % 2 == 0 else W - 1 - c)


def plot_writes(get, p):
    """Buffer writes of a plot: {address: new byte} (the game's own result)."""
    out = {}
    W, gfx = p['W'], p['gfx']
    for r in range(p['R']):
        yy = p['y'] + r
        if yy > 127:
            break
        lo, hi = get(YTAB + 2 * yy), get(YTAB + 2 * yy + 1)
        for k in range(W):
            xx = p['x'] + k
            if not 0 <= xx < 32:
                continue
            j = 2 + 2 * (r * W + entry_index(W, r, k, p['mir']))
            m, g = get((gfx + j) & 0xFFFF), get((gfx + j + 1) & 0xFFFF)
            if p['mir']:
                m, g = get(MIRTAB + m), get(MIRTAB + g)
            a = (lo | xx) + 256 * hi
            out[a] = (get(a) & m) | g
    return out


def buf_addr(get, x, y):
    return (get(YTAB + 2 * y) | x) + 256 * get(YTAB + 2 * y + 1)


# ---------------------------------------------------------------------------------------------
# Colour sheets (PLAYBOOK 3b)
# ---------------------------------------------------------------------------------------------

def group_of(slot):
    if slot == 'extra':
        return 'Extras'
    if slot == 'other':
        return 'Other'
    if slot in (0, 1):
        return 'Players'
    if 2 <= slot <= 5:
        return 'Enemies'
    return 'Objects'


GROUPS = ('Players', 'Enemies', 'Objects', 'Extras', 'Other')


def ckey(gfx, j):
    """Colour-map key of entry j of graphic gfx: address of its mask byte."""
    return '%04X' % ((gfx + 2 + 2 * j) & 0xFFFF)


def pixel_code(m, g, bit):
    b = 0x80 >> bit
    return 1 if g & b else (0 if m & b else 2)


def sheet_part(d):
    """A plot (capture) -> coloursheet part: every bit of its graphics bytes (paper bits code 0);
    defaults as the build draws them unpainted: ink black, body grey (7)."""
    W, Rr, gfx, data = d['W'], d['R'], d['gfx'], d['data']
    pixels, entries = [], {}
    for r in range(Rr):
        for c in range(W):
            j = stored_index(W, r, c)
            m, g = data[2 * j], data[2 * j + 1]
            k = ckey(gfx, j)
            entries.setdefault(k, [entry_check(m, g), 1])
            # screen column of this stored column
            for b in range(8):
                code = pixel_code(m, g, b)
                dflt = (INK if code == 1 else BODY) if code else 0
                pixels.append((c * 8 + b, r, k, b, code, dflt))
    vis = sum(1 for k in range(W) if 0 <= d['x'] + k < 32) * min(Rr, 128 - d['y'])
    return dict(id=gfx, size=vis, w=8 * W, h=Rr, x=d['x'] * 8, y=d['y'], mir=d['mir'],
                group=d['group'], fam=d['fam'], role=None, pixels=pixels, entries=entries)


def capture(rzx_paths, stop=None, progress=None, keep_frames=()):
    """Replay the RZX(s) (original game); every plot, frame by frame (a frame ends at the commit
    62565), joined into the sheet's composites (one figure = one display-list entry with its chain;
    the extras each one). keep_frames: frame numbers whose commit state is kept for previews
    (-> second return value {frame: dict(scenery, screen, attrs, plots)})."""
    if isinstance(rzx_paths, str):
        rzx_paths = [rzx_paths]
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    from . import coloursheet as cs
    MG = Memory.__getitem__
    st = {'f': 0, 'slot': 'other', 'fig': 0, 'clean': None}
    frame = []
    shots = {}
    keep = set(keep_frames)
    col = cs.Collector(family=lambda p: p['fam'])

    def on_plot(pc, get, R):
        p = plot_params(get, R, pc)
        if not (1 <= p['W'] <= 8 and 1 <= p['R'] <= 128):
            return
        slot = st['slot']
        if slot in ('extra', 'other'):
            st['fig'] += 1                      # every plot its own figure
        if slot == 'other':
            sp = R[12]
            st.setdefault('other', collections.Counter())[get(sp) | get((sp + 1) & 0xFFFF) << 8] += 1
        n = 2 * p['W'] * p['R']
        frame.append(dict(p, group=group_of(slot), slot=slot, fam=(st['f'], st['fig']),
                          data=bytes(get((p['gfx'] + 2 + i) & 0xFFFF) for i in range(n))))

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: MG(mem, a)

            def mk(f):
                def g():
                    pc = R[24]
                    if pc == PLOT or pc == PLOT_M:
                        on_plot(pc, get, R)
                    elif pc == OBJ_CALL:
                        st['fig'] += 1
                        st['slot'] = (R[0] - 10) // 22 if (R[0] - 10) % 22 == 0 else 6 + R[0]
                    elif pc == EXTRAS:
                        st['slot'] = 'extra'
                    elif pc == DRAW_ALL:
                        st['slot'] = 'other'
                        st['clean'] = bytes(get(a) for a in range(*BUF))
                        frame.clear()
                    elif pc == COMMIT:
                        if st['f'] - st.get('memf', -10**6) > 1000:
                            st['mem'] = bytes(get(a) for a in range(0x4000, 0xC000))
                            st['memf'] = st['f']
                        at = bytes(get(0x5800 + i) for i in range(768))
                        col.add_frame([sheet_part(dict(d, attrs=at)) for d in frame])
                        if keep and st['f'] >= min(keep) and st['clean'] is not None:
                            st['shot'] = dict(scenery=st['clean'], plots=[dict(d) for d in frame], attrs=at,
                                              ytab=bytes(get(YTAB + i) for i in range(256)))
                        frame.clear()
                    elif pc == RESTORE and st.get('shot'):      # the copy is done: the screen shows the frame
                        want = min(keep)
                        keep.discard(want)
                        shots[want] = dict(st.pop('shot'), screen=bytes(get(0x4000 + i) for i in range(6912)))
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])
    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['f'] += 1
        if progress and st['f'] % 500 == 0:
            progress(st['f'])
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = next_frame, S, None
    try:
        for rzx_path in rzx_paths:
            frame.clear()
            try:
                rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                             (['--stop', str(stop)] if stop else []) + [_stripped(rzx_path)])
            except SystemExit:
                pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    if st.get('other'):
        print('plots outside the figure list, by return address:', dict(st['other']))
    if st.get('mem'):
        add_static(col, st['mem'])
    return col.composites(GROUPS + (STATIC_GROUP,)), shots


STATIC_GROUP = 'From the code (not drawn in the recording)'
FRAMES = 0x6900                  # frame table: word per frame -> parts [y off][x off][graphic word]...; bit 7 of
                                 # y off marks a frame's first part (= the end of the frame before)


def frame_parts(get, f):
    ptr = get(FRAMES + 2 * f) | get(FRAMES + 2 * f + 1) << 8
    if ptr < 0x4000:
        return []
    out, h = [], ptr
    for _ in range(12):
        g = (get(h + 2) | get(h + 3) << 8) & 0xFFFE
        W, Rr = get(g), get(g + 1)
        if not (1 <= W <= 8 and 1 <= Rr <= 128):
            return []
        out.append((get(h), get(h + 1), g, W, Rr))
        h += 4
        if get(h) & 0x80:
            return out
    return []


def add_static(col, mem):
    """Frames of the frame table (the graphics in memory) with a graphic no recording drew: one
    composite each, parts at their frame offsets (unmirrored), default colours black ink on yellow."""
    get = lambda a: mem[a - 0x4000] if 0x4000 <= a < 0xC000 else 0
    seen = set(col.maxsize)
    for f in range(256):
        parts = frame_parts(get, f)
        if not parts or all(g in seen for _, _, g, _, _ in parts):
            continue
        ys = [-(yo & 127) for yo, _, _, _, _ in parts]       # bit 7: a frame's first part (y works mod 128)
        xs = [-((xo - 256) if xo > 127 else xo) for _, xo, _, _, _ in parts]
        y0, x0 = min(ys), min(xs)
        ps = []
        for (yo, xo, g, W, Rr), y, x in zip(parts, ys, xs):
            d = dict(gfx=g, W=W, R=Rr, x=0, y=0, mir=0, group=STATIC_GROUP, fam=('static', f),
                     data=bytes(get(g + 2 + i) for i in range(2 * W * Rr)), attrs=bytes([0x30]) * 768)
            p = sheet_part(d)
            ps.append(dict(p, size=W * Rr, dx=8 * (x - x0), dy=y - y0, dmir=0, vmir=0))
            seen.add(g)
            col.maxsize[g] = max(col.maxsize.get(g, 0), W * Rr)
        col.comps[('static', f)] = dict(count=0, group=STATIC_GROUP, parts=ps)


def _stripped(path):
    import tempfile
    import skoolkit.rzxplay as rz
    from skoolkit.snapshot import Snapshot
    from . import rzx as RZ
    if sum(1 for b in rz.parse_rzx(path) if isinstance(b.obj, Snapshot)) <= 1:
        return path
    fd, tmp = tempfile.mkstemp(suffix='.rzx')
    os.close(fd)
    RZ.strip(path, tmp)
    return tmp


def sheet(comps, png, layout_path, colours=None, unique=False):
    from . import coloursheet as cs
    return cs.write(comps, png, layout_path, [rgb(i) for i in range(16)], colours or {}, unique=unique,
                    paint_clear=True)


def sheets(comps, prefix, colours=None):
    """<prefix>_PAINTING_SPRITES.png (+ _layout.json; every graphic once) and
    <prefix>_REFERENCE_ALL_SPRITES.png (every figure whole). -> [(path, figures)]."""
    out = []
    for name, unique in (('PAINTING_SPRITES', True), ('REFERENCE_ALL_SPRITES', False)):
        png = '%s_%s.png' % (prefix, name)
        out.append((png, sheet(comps, png, os.path.splitext(png)[0] + '_layout.json', colours, unique)))
    return out


def read_sheet(png, layout_path):
    from . import coloursheet as cs
    return cs.read(png, layout_path, clear=True)


NOTE = ('Target Renegade figure colours (python -m nexclash.renegade colours): key = address of the '
        'mask byte of a graphic entry (8 pixels) -> [check byte, kind 1, 8 nibbles (0 = default colour)'
        '(, transparent mask)]')


def save_colours(ent, path=COLOURS):
    from . import coloursheet as cs
    cs.save(ent, path, NOTE)


def load_colours(path=COLOURS):
    from . import coloursheet as cs
    return cs.load(path)


# ---------------------------------------------------------------------------------------------
# Build: patch, start state (loader run + front end), boot check
# ---------------------------------------------------------------------------------------------

GAME_ENTRY = 23340               # after the entry code (relocation + OUT (0x1FFD),4)
TAIL_ADDR = 0x6400               # write-first game RAM 0x6400-0x9EFF (RZX + free run)
FRONT, FRONT_END = 0x6480, 0x6500
HPG, QPG, SPG, SPG3, GPG7, ALT_PAGE, STORE, NSTORE = 26, 27, 10, 11, 1, 24, 28, 12
ROM_LO = 0x2000                  # NIB0/NIB1 0x2000-0x21FF, code from 0x2200
ROM_READ = (0x3500, 0x3509)      # ROM 0 bytes the game reads (sound data): never patched
SITES_ORIG = {55276: 'e5d52b', 55722: 'e5d52b', 59531: '2140ff', 62565: '2af7f4', 62751: 'ed7bf6',
              62821: '21ff5a', 58200: '3e3808', 56332: '210000', 62771: 'e5d5c5'}
SITE_SYM = {55276: 'e_pn', 55722: 'e_pm', 59531: 'e_dr', 62565: 'e_cm', 62751: 'e_cx', 62821: 'e_clr',
            58200: 'e_rd', 56332: 'e_rs', 62771: 'e_tx'}
STOP = {59531: (59534,), 62821: (62824,), 58200: (58203,), 56332: (56335,), 62771: (62774,)}   # else: the return address
INTERIORS = tuple(a + k for a in SITES_ORIG for k in (1, 2)) + (62754,)
# page H (0x4000 at slot 2)
V_N, V_PREV, V_NS, V_COL, V_RR, V_NFREE, V_DROP, V_DIRTY = 0x000, 0x001, 0x002, 0x003, 0x006, 0x007, 0x008, 0x032
LOG, CE, FREE, SPRTAB, HSTK = 0x100, 0x300, 0x900, 0xA00, 0x1F00
MAXLOG, NCE, MAXSPR = 64, 48, 128
RUNTIME = (0x000, 0xC80)         # the run-time part of H (vars, log, cache, free stack, sprite table)
CLIP = (0, 255, 8, 135)          # sprite clip window (ULA coordinates): screen rows 1-16


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'target_renegade.json'),
              os.path.join(_HERE, 'target_renegade.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('target_renegade.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def nib_tables():
    """NIB0 / NIB1: index graphic nibble << 4 | mask nibble -> the 4 pixels' pattern bytes."""
    t0, t1 = bytearray(256), bytearray(256)
    for i in range(256):
        g, m = i >> 4, i & 15
        px = []
        for b in range(4):
            bit = 8 >> b
            px.append(INK if g & bit else (0 if m & bit else BODY))
        t0[i] = px[0] << 4 | px[1]
        t1[i] = px[2] << 4 | px[3]
    return bytes(t0 + t1)


def store_index(a):
    return (a - 0x6000) >> 1 if 0x6000 <= a < 0xC000 and not a & 1 else None


def store_pages(colours):
    """Colour map -> 12 pages (8-byte entries [1, check, 4 nibble bytes, transparent mask, 0])."""
    st = bytearray(NSTORE * 8192)
    for k, e in (colours or {}).items():
        i = store_index(int(k, 16))
        if i is None:
            continue
        nib = e[2]
        st[8 * i:8 * i + 8] = bytes([1, e[0] & 255] + [nib[2 * n] << 4 | nib[2 * n + 1] for n in range(4)] +
                                    [e[3] if len(e) > 3 else 0, 0])
    return bytes(st)


def hook_page(colours=None):
    p = bytearray(8192)
    for i in range(128):
        p[FREE + i] = i
    p[V_NFREE] = 128
    p[V_DIRTY] = 1                  # the first 59531 copies the scenery
    p[V_COL] = 1 if colours else 0
    return bytes(p)


class RenegadePatch:
    name = 'Target Renegade figures -> hardware sprites (alt ROM images 0 + 1, page 26 at slot 2, copy into page 27)'

    def __init__(self, prof=None, colours=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.front = bytes.fromhex(h['front'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup']) + bytes(PALETTE)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = FRONT - TAIL_ADDR
        self.colours = dict(colours) if colours is not None else load_colours_build()
        self.regblock = 0x2200 + len(self.rom_code)
        if self.regblock != self.syms['rom_end']:
            raise ValueError('hook code length differs from the profile symbols')
        if self.regblock + 20 > ROM_READ[0]:
            raise ValueError('ROM hooks reach 0x3500 (ROM bytes the game reads)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_LO, self.regblock + 20)
        pg = bytearray(8192)
        pg[0:512] = nib_tables()
        pg[0x200:0x200 + len(self.rom_code)] = self.rom_code
        self.page = pg                  # + the register block (apply)
        self.hpage = bytearray(hook_page(self.colours))
        self.store = store_pages(self.colours)
        self.sites = [(a, bytes.fromhex(old), (b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
                      for a, old in SITES_ORIG.items()]
        self._banks()

    def _banks(self):
        self.extra_banks = {12: bytes(self.page) + bytes(8192), 13: bytes(self.hpage) + bytes(8192)}
        for n in range(NSTORE // 2):
            self.extra_banks[14 + n] = self.store[16384 * n:16384 * (n + 1)]

    def check_sites(self, mem):
        for a, old, new in self.sites:
            cur = bytes((mem(a + k) if callable(mem) else mem[a + k]) for k in range(len(old)))
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.port7ffd & 7 != 4:
            raise ValueError('Target Renegade patch expects the 128K start snapshot (7FFD bank 4)')
        if snap.pc != FRONT:
            raise ValueError('the snapshot is not the Target Renegade start snapshot (PC %d)' % snap.pc)
        b0 = bytearray(snap.banks[0])           # code at 0xC000-0xFFFF in play = bank 0
        ram = {5: bytearray(snap.banks[5]), 2: bytearray(snap.banks[2]), 0: b0}

        def bank_of(a):
            return (5, a - 0x4000) if a < 0x8000 else ((2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000))
        self.check_sites(lambda a: ram[bank_of(a)[0]][bank_of(a)[1]])
        for a, old, new in self.sites:
            for k, v in enumerate(new):
                b, o = bank_of(a + k)
                ram[b][o] = v
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        self.page[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self._banks()
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[5]), bytes(ram[2]), bytes(ram[0])

    def alt_view(self, rom_get):
        """The alt ROM image as the game sees it: its ROM, the hook bytes at 0x2000-regblock+20."""
        lo, hi = self.altrom
        pg = self.page
        return lambda a: pg[a - 0x2000] if lo <= a < hi else rom_get(a)


def load_colours_build():
    from . import recolour as rc
    p = rc.build_colours_path(COLOURS)
    return load_colours(p) if p and os.path.exists(p) else {}


def loader_entry(z80, out_z80):
    """Run the BASIC loader (SPACE for its PAUSE 0) to PC 23340, after the entry code; save the
    state. -> (frame, registers list, 64K memory, 7FFD)."""
    from skoolkit.snapshot import Snapshot, write_snapshot
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot, get_state, PC, T, IFF
    s = Snapshot.get(z80)
    if s.pc != LOADER_PC:
        raise ValueError('not the Target Renegade loader snapshot (PC %d)' % s.pc)
    sim = from_snapshot(Simulator, s, config={'int_active': 0})
    mem, R, ops = sim.memory, sim.registers, sim.opcodes
    st = {'held': False}

    class Tr:
        border, outfe, outfffd, ay = s.border, s.border, 0, [0] * 16
        out7ffd = mem.o7ffd

        def read_port(self, regs, port):
            if port & 1 == 0 and st['held'] and not (port >> 8) & 0x80:
                return 0xFE                     # SPACE (row 0x7F, bit 0)
            return 0xFF

        def write_port(self, regs, port, value, offset=0):
            if port & 1 == 0:
                self.border, self.outfe = value & 7, value
            if port & 0x8002 == 0 and self.out7ffd & 32 == 0:     # 0x1FFD decodes as 7FFD (128K)
                mem.out7ffd(value)
                self.out7ffd = value
    sim.set_tracer(Tr())
    for f in range(400):
        st['held'] = 5 <= f < 15
        while R[T] < 70908:
            if R[PC] == GAME_ENTRY:
                ram, regs, state, machine = get_state(sim)
                write_snapshot(out_z80, ram, regs, state, machine)
                return f, list(R), bytes(mem[a] for a in range(65536)), mem.o7ffd
            ops[mem[R[PC]]]()
        R[T] -= 70908
        if R[IFF]:
            if mem[R[PC]] == 0x76:
                R[PC] = (R[PC] + 1) & 0xFFFF
            sim.accept_interrupt(R, mem, 0)
    raise ValueError('the loader did not reach %d' % GAME_ENTRY)


def make_start(entry_z80, start_z80, front):
    """Start snapshot = entry state (loading screen up) + front end at FRONT; PC = FRONT."""
    from skoolkit.snapshot import Snapshot, write_snapshot
    from skoolkit.simutils import from_snapshot, get_state
    from skoolkit.simulator import Simulator
    sim = from_snapshot(Simulator, Snapshot.get(entry_z80))
    for i, v in enumerate(front):
        sim.memory[FRONT + i] = v
    sim.registers[24] = FRONT

    class Tr:
        border = outfe = outfffd = 0
        ay = [0] * 16
    sim.set_tracer(Tr())
    ram, regs, state, machine = get_state(sim)
    write_snapshot(start_z80, ram, regs, state, machine)


FCMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


def front_tests(start_z80, entry_regs, entry_mem, front=None):
    """Run the front end: no key held, then a key (each of the eight rows' bit 0, and a key held
    from the start, which must be released first): it must reach 23340 with every register (R
    aside) and all RAM as the loader's own state, except the front end bytes (write-first RAM)."""
    from skoolkit.snapshot import Snapshot
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    out = {}
    cases = [('row %02X' % r, r, False) for r in (0xFE, 0xFD, 0xFB, 0xF7, 0xEF, 0xDF, 0xBF, 0x7F)]
    cases.append(('held at start', 0x7F, True))
    for name, row, held0 in cases:
        sim = from_snapshot(Simulator, Snapshot.get(start_z80), config={'int_active': 0})
        R, mem, ops = sim.registers, sim.memory, sim.opcodes
        if front is not None:
            for i, v in enumerate(front):
                mem[FRONT + i] = v
        n = [0]

        class Tr:
            border = outfe = outfffd = 0
            ay = [0] * 16

            def read_port(self, regs, port):
                n[0] += 1
                if port & 1:
                    return 0xFF
                if held0 and n[0] < 50:
                    return 0xFE                 # held (all rows read: port high byte 0)
                if n[0] < 100:
                    return 0xFF
                return 0xFE if (port >> 8) & (row ^ 0xFF) == 0 else 0xFF

            def write_port(self, regs, port, value, offset=0):
                pass
        sim.set_tracer(Tr())
        steps = 0
        while R[24] != GAME_ENTRY and steps < 100000:
            ops[mem[R[24]]]()
            steps += 1
        bad = []
        if R[24] != GAME_ENTRY:
            bad.append('did not reach %d' % GAME_ENTRY)
        if n[0] < 100:
            bad.append('left before a key was pressed')
        bad += ['register %d' % i for i in FCMP if R[i] != entry_regs[i]]
        for a in range(0x4000, 0x10000):
            if FRONT <= a < FRONT_END:
                continue
            if mem[a] != entry_mem[a]:
                bad.append(('ram', a, mem[a], entry_mem[a]))
                break
        out[name] = bad
    return out


def boot_check(nex, z80, patch=None, tail=None):
    """Boot the NEX in the Next model (nextboot.boot) to the snapshot PC: registers, the NEX banks =
    the (patched) snapshot's, RAM view, MMU, paging (7FFD = 4, 1FFD = 0: ROM 0), $8C, and the alt
    ROM images: image 1 = ROM 3 + the hook bytes, image 0 = ROM 0 + the hook bytes (the model knows
    only ROM 3: the reads of ROM 0 by the image-0 fill are expected and read as 0)."""
    import copy
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = nextboot.boot(nex, s.pc)
    R, mem = st['R'], st['mem']
    bad = [b for b in st['bad'] if not (patch is not None and b[0] == 'read of ROM 0')]
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
    if st['p7ffd'] != s.port7ffd or st['p1ffd'] != 0:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 2 * top, 2 * top + 1]:
        bad.append(('MMU', st['mmu']))
    if patch is not None:
        lo, hi = patch.altrom
        img1 = bytearray(rom48())
        img1[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
        if bytes(st['alt'][1]) != bytes(img1):
            bad.append(('alt image 1 differs from ROM 3 + hooks',))
        if bytes(st['alt'][0][lo:hi]) != bytes(patch.page[lo - 0x2000:hi - 0x2000]):
            bad.append(('alt image 0 hook bytes differ',))
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
        log = st['nrlog']
        if (0x15, 0x01) not in log:
            bad.append(('sprites not enabled',))
    elif st['nr'].get(0x8C, 0) != 0:
        bad.append(('$8C', st['nr'].get(0x8C)))
    return bad


# ---------------------------------------------------------------------------------------------
# Differential verification (the RZX replay runs the ORIGINAL game; at every patch site the original
# and the patched code run from the same state and are compared)
# ---------------------------------------------------------------------------------------------

SCREEN = (0x4000, 0x5B00)
COPY_RANGE = (62565, 62763)          # the copy routine (its screen writes go to page Q when patched)
EVENTS = set(SITES_ORIG) - {62751}   # 62751 is inside the copy (paired with it)
SITE_SPAN = {55276: 3, 55722: 3, 59531: 3, 62565: 3, 62751: 4, 62821: 3, 58200: 3, 56332: 3, 62771: 3}
PUSHES = {55276: 4, 55722: 4, 62771: 6}   # bytes the displaced PUSHes put on the game stack
INTERIOR = {a + k: a for a, n in SITE_SPAN.items() for k in range(1, n)}


class _NS:
    """Next-side state of the patched machine: NextRegs, sprite attributes, pattern RAM, pages
    H (hook page) and Q (where the patched copy writes)."""

    def __init__(self, patch):
        self.nr = {0x07: 0, 0x52: SPG, 0x53: SPG3, 0x57: GPG7, 0x15: 1}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.rsel = 0
        self.events = []
        self.H = bytearray(patch.hpage)
        self.Q = bytearray(8192)
        self.R = None

    def _pc(self):
        return self.R[24] if self.R is not None else 0

    def read(self, port):
        if self._pc() < 0x4000:
            self.events.append(('in', port))
        return self.nr.get(self.rsel, 0) if port == 0x253B else 0xFF

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def out(self, port, val):
        if port == 0x243B:
            self.rsel = val
        elif port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
        elif self._pc() < 0x4000:
            self.events.append(('port', port, val))

    def sprite_layer(self):
        """Visible sprites composited (higher number on top), clipped -> {(x, y): colour index}."""
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
                    if c and CLIP[0] <= x <= CLIP[1] and CLIP[2] <= y <= CLIP[3]:
                        out[(x, y)] = c
        return out


class _OrigView:
    """64K view of the replay's memory at the event (ROM as selected), writes in an overlay."""

    def __init__(self, get, fill=None):
        self.get, self.ov, self.fill = get, {}, fill

    def __getitem__(self, a):
        v = self.ov.get(a)
        if v is not None:
            return v
        if self.fill is not None and BUF[0] <= a < BUF[1]:
            return self.fill
        return self.get(a)

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.ov[a] = v

    def __len__(self):
        return 65536


class _PatchedView(_OrigView):
    """The patched machine: alt ROM (hook bytes), patch sites, MMU slots 2/3/7 as the hooks map them
    (H, Q, the screen at slot 3, colour store pages), the persistent patched screen overlay."""

    def __init__(self, get, ns, alt, psite, pscreen, store, err):
        super().__init__(get)
        self.ns, self.alt, self.psite, self.pscreen, self.store, self.err = ns, alt, psite, pscreen, store, err
        self.scr_w = {}

    def _scr(self, a):                         # a = screen address 0x4000-0x5FFF
        v = self.scr_w.get(a)
        if v is not None:
            return v
        v = self.pscreen.get(a)
        return v if v is not None else self.get(a)

    def __getitem__(self, a):
        if a < 0x4000:
            return self.alt(a)
        nr = self.ns.nr
        if a < 0x6000:
            m = nr[0x52]
            if m == SPG:
                return self._scr(a) if a not in self.ov else self.ov[a]
            if m == HPG:
                return self.ns.H[a - 0x4000]
            if m == QPG:
                return self.ns.Q[a - 0x4000]
            self.err.append(('slot 2: page', m))
            return 0
        if a < 0x8000 and nr[0x53] != SPG3:
            if nr[0x53] == SPG:
                return self._scr(a - 0x2000)
            self.err.append(('slot 3: page', nr[0x53]))
            return 0
        if a >= 0xE000 and nr[0x57] != GPG7:
            pg = nr[0x57] - STORE
            if 0 <= pg < NSTORE:
                return self.store[pg * 8192 + a - 0xE000]
            self.err.append(('slot 7: page', nr[0x57]))
            return 0
        if a not in self.ov:
            v = self.psite.get(a)
            if v is not None:
                return v
        return _OrigView.__getitem__(self, a)

    def __setitem__(self, a, v):
        nr = self.ns.nr
        if a < 0x4000:
            self.err.append(('ROM write', a))
            return
        if a < 0x6000:
            m = nr[0x52]
            if m == SPG:
                if a < SCREEN[1]:
                    self.scr_w[a] = v
                else:
                    self.ov[a] = v
            elif m == HPG:
                self.ns.H[a - 0x4000] = v
            elif m == QPG:
                self.ns.Q[a - 0x4000] = v
            else:
                self.err.append(('slot 2 write: page', m))
            return
        if a < 0x8000 and nr[0x53] != SPG3:
            if nr[0x53] == SPG and a - 0x2000 < SCREEN[1]:
                self.scr_w[a - 0x2000] = v
            else:
                self.err.append(('slot 3 write', nr[0x53], a))
            return
        if a >= 0xE000 and nr[0x57] != GPG7:
            self.err.append(('write to the colour store', a))
            return
        self.ov[a] = v


def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def _machine(Sim, mem, regs, ns, slot=None):
    from .rainbow import _machine as m
    return m(Sim, mem, regs, ns, slot)


def _run_until(sim, stop, limit=4000000, each=None):
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


def _safe(R, regs0, ns, err, base, depth=4):
    """After every hook instruction (PC in the alt ROM): IX, IY, I and the interrupt state as at the
    hook's entry (the copy pair runs game code in between: POP IX), SP on the hook stack (page H mapped) or at/above the site's SP - 4 (the plot hooks' two
    displaced PUSHes), no instruction fetch at 0x3D00-0x3DFF (DivMMC, BRIEFING A1)."""
    pc = R[24]
    if pc >= 0x4000:
        base.clear()
        return
    if not base:
        base.extend(R[8:12])
    bad = None
    if list(R[8:12]) != base:
        bad = 'IX/IY changed'
    elif R[14] != regs0[14] or R[26] != regs0[26]:
        bad = 'I / interrupt state changed'
    elif 0x3D00 <= pc < 0x3E00:
        bad = 'fetch in 0x3D00-0x3DFF'
    elif ns.nr[0x52] == HPG and 0x4000 <= R[12] < 0x6000:
        if not (0x4000 + HSTK - 0x200 <= R[12] <= 0x4000 + HSTK):
            bad = 'SP in page H outside the hook stack'
    elif R[12] < regs0[12] - depth and not 0x4000 <= R[12] < 0x6000:
        bad = 'SP below the site SP - its displaced PUSHes'
    if bad:
        err.append(('interrupt-unsafe hook', bad, pc))


def _stop_for(pc, get, R):
    if pc in STOP:
        s = STOP[pc][0]
        return lambda r: r[24] == s
    if pc in (PLOT, PLOT_M):
        s = pc + 3
        return lambda r: r[24] == s
    sp0 = R[12]
    ret = get(sp0) | get((sp0 + 1) & 0xFFFF) << 8
    return lambda r: r[24] == ret and r[12] == sp0 + 2


def truth(get, regs, pc):
    """The ORIGINAL plot on a buffer of 0x00 and of 0xFF -> {(x, y): 1 ink / 2 paper} (screen pixels)."""
    Sim = _sim_class()
    outs = []
    for fill in (0x00, 0xFF):
        m = _OrigView(get, fill)
        s = _machine(Sim, m, list(regs), _NS(_Dummy), 'm')
        if not _run_until(s, _stop_for(pc, get, regs) if pc not in (PLOT, PLOT_M) else
                          (lambda r, sp0=regs[12]: r[24] in PLOT_RET and r[12] == sp0)):
            return None
        outs.append({a: v for a, v in m.ov.items() if BUF[0] <= a < BUF[1]})
    z, f = outs
    inv = {}
    for y in range(128):
        lo, hi = get(YTAB + 2 * y), get(YTAB + 2 * y + 1)
        for x in range(32):
            inv[(lo | x) + 256 * hi] = (x, y)
    px = {}
    for a in set(z) | set(f):
        if a not in inv:
            continue
        xb, y = inv[a]
        for k in range(8):
            bit = 0x80 >> k
            if z.get(a, 0) & bit:
                px[(xb * 8 + k, 8 + y)] = 1
            elif not f.get(a, 0xFF) & bit:
                px[(xb * 8 + k, 8 + y)] = 2
    return px


class _Dummy:
    hpage = bytes(8192)


def colour_of(colours, get, p, x, y, code):
    """Expected colour of screen pixel (x, y) of plot p (plot_params dict) with pixel code (1 ink,
    2 body, 0 clear); None = transparent."""
    W = p['W']
    c = x - 8 * p['x']
    if p['mir']:
        c = 8 * W - 1 - c
    r = y - 8 - p['y']
    k, b = c >> 3, c & 7
    j = stored_index(W, r, k)
    key = (p['gfx'] + 2 + 2 * j) & 0xFFFF
    nib, clear = 0, False
    e = colours.get('%04X' % key) if colours and 0x6000 <= key < 0xC000 else None
    if e is not None and e[0] == entry_check(get(key), get(key + 1)):
        nib = e[2][b]
        clear = len(e) > 3 and bool(e[3] & (0x80 >> b))
    if clear:
        return None
    if code == 1:
        return nib or INK
    if code == 2:
        return nib or BODY
    return nib or None


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """-> (Counter, examples, captured states). Failure keys end in '!'."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    Sim = _sim_class()
    c = collections.Counter()
    ex = collections.defaultdict(list)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    site_bytes = {a + k: old[k] for a, old, new in patch.sites for k in range(len(old))}
    ns = _NS(patch)
    pscreen = {}
    st = {'frame': 0, 'in_copy': None, 'prev': None, 'clean': None, 'n': 0, 'frame_plots': [],
          'hookT': 0, 'maxT': 0, 'gf': 0}
    tcache = {}
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    def buffer_now(get):
        return bytes(get(a) for a in range(*BUF))

    def plot_truth(get, R, pc, p):
        whole = 0 <= p['x'] and p['x'] + p['W'] <= 32 and p['y'] + p['R'] <= 128
        key = None
        if whole:
            data = bytes(get((p['gfx'] + i) & 0xFFFF) for i in range(2 + 2 * p['W'] * p['R']))
            key = (p['gfx'], p['mir'], data)
            rel = tcache.get(key)
            if rel is not None:
                c['truth (cached)'] += 1
                return {(x + 8 * p['x'], y + 8 + p['y']): v for (x, y), v in rel.items()}
        px = truth(get, R, pc)
        c['truth runs'] += 1
        if px is None:
            fail('truth run did not return')
            return {}
        if key is not None:
            tcache[key] = {(x - 8 * p['x'], y - 8 - p['y']): v for (x, y), v in px.items()}
        return px

    def pair(pc, mem, R):
        get = lambda a: MG(mem, a)
        regs = list(R)
        stop_ = _stop_for(pc, get, R)
        err = []
        o = _OrigView(get)
        so = _machine(Sim, o, list(regs), _NS(_Dummy), 'o')
        if not _run_until(so, stop_):
            fail('original did not return', (pc,))
            return None
        alt = patch.alt_view(get)
        p = _PatchedView(get, ns, alt, psite, pscreen, patch.store, err)
        ns.events = []
        sp_ = _machine(Sim, p, list(regs), ns, 'p')
        t0 = sp_.registers[25]
        if not _run_until(sp_, stop_, each=lambda r, b=[]: _safe(r, regs, ns, err, b, PUSHES.get(pc, 0))):
            fail('patched did not return', (pc,))
            return None
        dt = (sp_.registers[25] - t0) - (so.registers[25] - regs[25])
        st['hookT'] += dt
        c['hook T at %d' % pc] += dt
        bad = [i for i in CMP if so.registers[i] != sp_.registers[i]]
        if bad:
            fail('registers differ', (pc, bad[:4]))
        excl = SCREEN if pc in (62565, 59531) else (0, 0)
        keys = (set(o.ov) | set(p.ov))
        dm = [a for a in keys if not excl[0] <= a < excl[1] and o.ov.get(a, get(a)) != p.ov.get(a, get(a))]
        if dm:
            fail('memory differs', (pc, len(dm), sorted(dm)[:4]))
        if pc not in (62565, 59531) and p.scr_w:
            fail('screen written by a hook', (pc, len(p.scr_w)))
        if (ns.nr[0x52], ns.nr[0x53], ns.nr[0x57], ns.nr[0x07]) != (SPG, SPG3, GPG7, 0):
            fail('MMU / speed not restored', (pc, ns.nr[0x52], ns.nr[0x53], ns.nr[0x57], ns.nr[0x07]))
            ns.nr.update({0x52: SPG, 0x53: SPG3, 0x57: GPG7, 0x07: 0})
        if any(e[0] in ('in', 'port') for e in ns.events):
            fail('port access in a hook', (pc, [e for e in ns.events if e[0] != 'nr'][:3]))
        for e in err:
            fail(str(e[0]), (pc,) + tuple(e[1:]))
        pscreen.update(p.scr_w)
        c['pairs %d' % pc] += 1
        return so, o, sp_, p

    def on_event(pc, mem, R):
        get = lambda a: MG(mem, a)
        for a in range(pc, pc + SITE_SPAN[pc]):
            if get(a) != site_bytes[a]:
                fail('site bytes changed in the game', (pc,))
                return
        if mem.o7ffd & 7 != 0 and pc != 62821:
            fail('site reached with another bank at 0xC000', (pc, mem.o7ffd))
        if pc in (PLOT, PLOT_M):
            pr = plot_params(get, R, pc)
            if R[26]:
                fail('interrupts on at a plot')
            px = plot_truth(get, R, pc, pr)
            st['frame_plots'].append((pr, px))
            st['n'] += 1
        elif pc == 59531:
            st['clean'] = buffer_now(get)
            st['n'] = 0
            st['frame_plots'] = []
        elif pc in (58200, 56332):
            st['n'] = 0
            if pc == 58200:
                st['frame_plots'] = []
        if collect and pc == 62565 and len(states) < collect and st['n'] and st['frame'] >= st.get('next_c', 0):
            st['next_c'] = st['frame'] + 400
            states.append(dict(R=list(R), mem=bytes(get(a) for a in range(65536)), H=bytes(ns.H),
                               plots=[pr for pr, px in st['frame_plots']]))
        res = pair(pc, mem, R)
        if res is None:
            return
        if pc == 62565:
            commit_checks(get, res)
        elif pc == 62821:
            if any(a[3] & 0x80 for a in ns.attr):
                fail('sprites shown after the screen clear')

    def commit_checks(get, res):
        so, o, sp_, p = res
        st['gf'] += 1
        c['commits'] += 1
        if st['n'] == 0:
            clean = buffer_now(get)
            plots = []
        else:
            clean = st['clean']
            plots = st['frame_plots']
        # 1. the ULA (patched screen) = scenery: the clean buffer in screen rows 1-16
        bad = 0
        for y in range(128):
            lo, hi = get(YTAB + 2 * y), get(YTAB + 2 * y + 1)
            sy = 8 + y
            sa = 0x4000 | ((sy & 0xC0) << 5) | ((sy & 7) << 8) | ((sy & 0x38) << 2)
            for x in range(32):
                b = clean[(lo | x) + 256 * hi - BUF[0]]
                v = pscreen.get(sa + x, get(sa + x))
                if v != b:
                    bad += 1
        if bad:
            fail('ULA play area is not the scenery', (bad,))
        # 2. sprites = the plots (truth pixels) in plot order, coloured as the build colours them
        exp, ecode = {}, {}
        for pr, px in plots:
            for yy in range(max(8 + pr['y'], CLIP[2]), min(8 + pr['y'] + pr['R'], 136, CLIP[3] + 1)):
                for xx in range(max(8 * pr['x'], CLIP[0]), min(8 * (pr['x'] + pr['W']), CLIP[1] + 1)):
                    code = px.get((xx, yy), 0)
                    col = colour_of(patch.colours, get, pr, xx, yy, code)
                    if col is not None:
                        exp[(xx, yy)], ecode[(xx, yy)] = col, code
        lay = ns.sprite_layer()
        c['sprite pixels compared'] += len(exp)
        c['max sprites in a frame'] = max(c['max sprites in a frame'], sum(1 for a in ns.attr if a[3] & 0x80))
        if lay != exp:
            d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
            fail('sprite layer differs from the plots', (len(d), sorted(d)[:3], [(lay.get(k), exp.get(k)) for k in sorted(d)[:3]]))
        # 3. end to end: the original screen after its copy vs ULA + sprites (ink / not ink); pixels
        # with painted colours on clear bits (outlines) are the user's change, not compared
        bad = 0
        for y in range(8, 136):
            sa0 = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            for x in range(256):
                a = sa0 + (x >> 3)
                bit = 0x80 >> (x & 7)
                orig = bool(o.ov.get(a, get(a)) & bit)
                code = ecode.get((x, y))
                if code == 0:
                    continue
                want = (code == 1) if code is not None else bool(pscreen.get(a, get(a)) & bit)
                if orig != want:
                    bad += 1
        if bad:
            fail('screen + sprites differ from the original screen', (bad,))
        if ns.H[V_DROP]:
            fail('parts dropped (cache full)', (ns.H[V_DROP],))

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes

            class W(type(mem)):
                def __setitem__(s, a, v):
                    if SCREEN[0] <= a < SCREEN[1]:
                        if st['in_copy'] is not None:
                            if a not in pscreen:
                                pscreen[a] = MG(s, a)       # the patched copy wrote page Q instead
                        else:
                            pscreen.pop(a, None)           # the same write happens patched
                    MS(s, a, v)
            mem.__class__ = W

            def mk(f):
                def g():
                    pc = R[24]
                    prev, st['prev'] = st['prev'], pc
                    if pc in INTERIOR and not (prev is not None and INTERIOR[pc] <= prev < pc):
                        fail('jump into a patched instruction', (pc, prev))
                    if st['in_copy'] is not None:
                        if pc == st['in_copy'][0] and R[12] == st['in_copy'][1]:
                            st['in_copy'] = None
                    elif pc in EVENTS:
                        on_event(pc, mem, R)
                        if pc == 62565:
                            sp0 = R[12]
                            st['in_copy'] = (MG(mem, sp0) | MG(mem, sp0 + 1) << 8, sp0 + 2)
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
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = next_frame, S, None
    try:
        try:
            rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                         (['--stop', str(stop)] if stop else []) + [_stripped(rzx_path)])
        except SystemExit:
            pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    c['hook T per game frame (3.5 MHz units, x1 not /8)'] = st['hookT'] // max(1, st['gf'])
    return c, ex, states


def _snap64(mem):
    from skoolkit.pagingtracer import Memory
    MG = Memory.__getitem__
    return {a: MG(mem, a) for a in range(0x4000, 0x10000)}


# ---------------------------------------------------------------------------------------------
# Unit tests: paths the RZX does not reach (guard edges, log / cache full, colour map, negative controls)
# ---------------------------------------------------------------------------------------------

def _fresh_H(patch, log):
    """Page H of `patch` (its own tables) with an empty cache and this log [(record, D, E, kind)]."""
    H = bytearray(patch.hpage)
    H[V_N] = min(len(log), MAXLOG)
    for i, (rec, d, e, kind) in enumerate(log[:MAXLOG]):
        H[LOG + 5 * i:LOG + 5 * i + 5] = bytes([rec & 255, rec >> 8, e, d, kind])
    return H


def run_commit(patch, st, log, mem_edit=None, ns=None, H=None):
    """The patched commit (62565 through the copy's return) from a captured state with this log.
    -> (ns, H, err)."""
    mem = bytearray(st['mem'])
    for a, v in (mem_edit or {}).items():
        mem[a] = v
    get = mem.__getitem__
    if ns is None:
        ns = _NS(patch)
    ns.H = H if H is not None else _fresh_H(patch, log)
    if len(log) > MAXLOG:
        ns.H[V_DROP] = 0
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    err = []
    p = _PatchedView(get, ns, patch.alt_view(get), psite, {}, patch.store, err)
    R = list(st['R'])
    s = _machine(_sim_class(), p, R, ns, 'commit')
    if not _run_until(s, _stop_for(62565, get, R), each=lambda r, b=[]: _safe(r, R, ns, err, b, 0)):
        err.append(('did not return',))
    return ns, ns.H, err


def guard(get, rec, kind):
    """Python model of the commit's guard: -> plot_params dict (converted) or None (no sprite)."""
    if rec < 0x6002:
        return None
    gfx = (get(rec) | get(rec + 1) << 8) & 0xFFFE
    if gfx < 0x6000:
        return None
    W, Rr = get(gfx), get(gfx + 1)
    if not (1 <= W <= 6 and 1 <= Rr <= 64):        # the plotter's unrolled rows: 6 bytes at most
        return None
    return gfx


def expected_parts(patch, st, log, mem_edit=None, colours=None, nmax=None):
    """Expected sprite layer of a log: the ORIGINAL plotter run per part (truth), composed in order."""
    mem = bytearray(st['mem'])
    for a, v in (mem_edit or {}).items():
        mem[a] = v
    get = mem.__getitem__
    exp, conv = {}, 0
    for i, (rec, d, e, kind) in enumerate(log[:MAXLOG]):
        if guard(get, rec, kind) is None:
            continue
        if nmax is not None and conv >= nmax:
            break
        conv += 1
        pc = PLOT_M if kind else PLOT
        R = list(st['R'])
        R[6], R[7], R[4], R[5] = rec >> 8, rec & 255, d, e
        R[26], R[24] = 0, pc
        pr = plot_params(get, R, pc)
        px = truth(get, R, pc)
        for yy in range(max(8 + pr['y'], CLIP[2]), min(8 + pr['y'] + pr['R'], 136, CLIP[3] + 1)):
            for xx in range(max(8 * pr['x'], CLIP[0]), min(8 * (pr['x'] + pr['W']), CLIP[1] + 1)):
                col = colour_of(colours, get, pr, xx, yy, px.get((xx, yy), 0))
                if col is not None:
                    exp[(xx, yy)] = col
    return exp, conv


def _synthetic(rng, W, Rr, at=0xB000, gat=None, yoff=40, xoff=1, q58=False):
    """A part record at `at` and a graphic (random masks / graphics, some bytes 58) -> {addr: byte}."""
    g = gat if gat is not None else at + 0x10
    ed = {at - 2: yoff, at - 1: xoff, at: g & 255, at + 1: g >> 8, g: W & 255, g + 1: Rr & 255}
    for i in range(2 * max(W, 1) * max(Rr, 1)):
        v = rng.randrange(256)
        if q58 and rng.random() < 0.1:
            v = 58
        ed[g + 2 + i] = v
    return ed


def unit_tests(patch, states, swapped=None, int_patch=None):
    import random
    rng = random.Random(7)
    u = collections.Counter()
    fails = collections.defaultdict(list)

    def chk(name, st, log, mem_edit=None, p=None, colours=None, nmax=None, want_drop=None, expect_fail=False):
        p = p or patch
        ns, H, err = run_commit(p, st, log, mem_edit)
        exp, conv = expected_parts(patch, st, log, mem_edit, colours if colours is not None else patch.colours, nmax)
        lay = ns.sprite_layer()
        bad = lay != exp or bool(err) or (want_drop is not None and H[V_DROP] != want_drop)
        u['cases'] += 1
        u['converted parts'] += conv
        u['passthrough parts'] += min(len(log), MAXLOG) - conv
        if expect_fail:
            u['negative cases'] += 1
            u['negative detected'] += bad
            return
        if bad:
            u[name + '!'] += 1
            if len(fails[name]) < 3:
                d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
                fails[name].append((len(d), err[:2], H[V_DROP]))
        return ns, H

    for st in states:
        log = [(H_rec, d, e, k) for H_rec, d, e, k in _log_of(st['H'])]
        chk('captured', st, log)
        # the same commit twice: the second one from the cache (hits)
        ns, H, err = run_commit(patch, st, log)
        ns2, H2, err2 = run_commit(patch, st, log, ns=ns, H=_relog(H, log))
        exp, _ = expected_parts(patch, st, log)
        u['cache hit cases'] += 1
        if ns2.sprite_layer() != exp or err2:
            u['cache hit!'] += 1
    st = states[0]
    # guard edges: W, R, mirrored, positions (clipping), the 0x6000 limits
    for W in (0, 1, 2, 6, 7):
        for Rr in (0, 1, 17, 64, 65):
            for kind in (0, 1):
                for x, y in ((14, 70), (-1, 60), (31, 60), (0, 127)):
                    ed = _synthetic(rng, W, Rr, q58=True)
                    d = (y + 40) & 255
                    e = (x + 1) & 255 if not kind else (x - 1 - 1 + W) & 255
                    chk('guard W%d R%d' % (W, Rr), st, [(0xB000, d, e, kind)], ed)
    for rec, g, nm in ((0x5E00, 0xB010, 'record below 0x6000'), (0xB000, 0x5E10, 'graphic below 0x6000'),
                       (0x6002, 0x6010, 'at 0x6000'), (0xB000, 0xE110, 'graphic in bank 0')):
        ed = _synthetic(rng, 3, 20, at=rec, gat=g)
        chk(nm, st, [(rec, 80, 12, 0), (rec, 80, 20, 1)], ed)
    # log full: 65 parts -> 64, the 65th dropped
    ed = _synthetic(rng, 1, 8)
    log = [(0xB000, (40 + 8 * (i // 30)) & 255, 1 + i % 30, i & 1) for i in range(65)]
    chk('log full', st, log, ed, want_drop=None)
    u['log full parts'] = 65
    # the plot hook's log: entry 64 logged, a 65th dropped (V_DROP), registers / memory as the original
    for n0 in (MAXLOG - 1, MAXLOG):
        for pc in (PLOT, PLOT_M):
            H = bytearray(patch.hpage)
            H[V_N] = n0
            ns = _NS(patch)
            ns.H = H
            mem = bytearray(st['mem'])
            get = mem.__getitem__
            R = list(st['R'])
            R[24], R[6], R[7], R[4], R[5] = pc, 0x9F, 0x12, 0x50, 0x0E
            err = []
            psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
            pv = _PatchedView(get, ns, patch.alt_view(get), psite, {}, patch.store, err)
            ov = _OrigView(get)
            so = _machine(_sim_class(), ov, list(R), _NS(_Dummy), 'o')
            _run_until(so, lambda r: r[24] == pc + 3)
            sp_ = _machine(_sim_class(), pv, list(R), ns, 'p')
            _run_until(sp_, lambda r: r[24] == pc + 3, each=lambda r, b=[]: _safe(r, R, ns, err, b, 4))
            u['plot hook cases'] += 1
            ok = not err and all(so.registers[i] == sp_.registers[i] for i in CMP) and ov.ov == pv.ov
            if n0 < MAXLOG:
                ok = ok and H[V_N] == MAXLOG and H[V_DROP] == 0 and \
                    bytes(H[LOG + 5 * n0:LOG + 5 * n0 + 5]) == bytes([0x12, 0x9F, 0x0E, 0x50, int(pc == PLOT_M)])
            else:
                ok = ok and H[V_N] == MAXLOG and H[V_DROP] == 1
            if not ok:
                u['plot hook log!'] += 1
    # patterns full: 40 distinct 4-pattern graphics -> 32 converted (128 patterns), 8 dropped
    ed, log = {}, []
    for i in range(40):
        a = 0x9000 + 0x110 * i
        ed.update(_synthetic(rng, 4, 32, at=a, gat=a + 0x10))
        log.append((a, 70, (i * 3) % 28 + 1, 0))
    chk('patterns full', st, log, ed, nmax=32, want_drop=8)
    # colour map: a synthetic map on a captured commit's graphics; wrong check bytes ignored
    log = _log_of(st['H'])
    cmap, wrong = synthetic_colours(st, log, rng)
    pc_ = RenegadePatch(colours=cmap)
    chk('colour map', st, log, p=pc_, colours=cmap)
    pw = RenegadePatch(colours=wrong)
    chk('colour map, wrong check bytes', st, log, p=pw, colours=wrong)
    u['map entries'] = len(cmap)
    # negative controls (each must FAIL): the map left out, ink / body swapped, IY written in a hook
    chk('neg: map left out', st, log, p=RenegadePatch(colours={}), colours=cmap, expect_fail=True)
    if swapped is not None:
        for s2 in states:
            chk('neg: swapped', s2, _log_of(s2['H']), p=swapped, expect_fail=True)
    if int_patch is not None:
        ns, H, err = run_commit(int_patch, st, log)
        u['negative cases'] += 1
        u['negative detected'] += any(e[0] == 'interrupt-unsafe hook' for e in err)
    return u, fails


def _log_of(H):
    out = []
    for i in range(H[V_N]):
        b = H[LOG + 5 * i:LOG + 5 * i + 5]
        out.append((b[0] | b[1] << 8, b[3], b[2], b[4]))
    return out


def _relog(H, log):
    H = bytearray(H)
    H[V_N] = min(len(log), MAXLOG)
    for i, (rec, d, e, kind) in enumerate(log[:MAXLOG]):
        H[LOG + 5 * i:LOG + 5 * i + 5] = bytes([rec & 255, rec >> 8, e, d, kind])
    return H


def synthetic_colours(st, log, rng):
    """Random colours (and some transparent / outline pixels) for the graphics of a log; and the same
    map with every check byte wrong."""
    get = st['mem'].__getitem__
    cmap, wrong = {}, {}
    for rec, d, e, k in log:
        gfx = guard(get, rec, k)
        if gfx is None:
            continue
        W, Rr = get(gfx), get(gfx + 1)
        for j in range(W * Rr):
            if rng.random() < 0.5:
                continue
            key = gfx + 2 + 2 * j
            nib = [rng.choice((0, 0, 0, 2, 5, 9, 14)) for _ in range(8)]
            tm = rng.choice((0, 0, 0, 0x81))
            e1 = [entry_check(get(key), get(key + 1)), 1, nib] + ([tm] if tm else [])
            cmap['%04X' % key] = e1
            wrong['%04X' % key] = [(e1[0] + 1) & 255] + e1[1:]
    return cmap, wrong


def swapped_patch():
    """Negative control: NIB tables with ink and body swapped."""
    p = RenegadePatch(colours={})
    t = bytearray(512)
    for i in range(256):
        g, m = i >> 4, i & 15
        px = [(BODY if g & (8 >> b) else (0 if m & (8 >> b) else INK)) for b in range(4)]
        t[i], t[256 + i] = px[0] << 4 | px[1], px[2] << 4 | px[3]
    p.page[0:512] = t
    return p


def int_patch():
    """Negative control: LD IY,0 in place of e_cm's NEXTREG $07,3 (4 bytes)."""
    p = RenegadePatch(colours={})
    a = p.syms['e_cm'] - 0x2000
    p.page[a:a + 4] = bytes.fromhex('FD210000')
    return p


# ---------------------------------------------------------------------------------------------
# auto: build both .nex files from the loader snapshot, boot checks, verification, unit tests
# ---------------------------------------------------------------------------------------------

def static_check(code, org):
    """Hook code never writes IX / IY / I or the interrupt state: no DD / FD prefix, DI, EI, LD I,A,
    IM, RETI / RETN (the game's IM 2 handler is a dummy, but an interrupt must stay harmless)."""
    from .simrun import disasm
    mem = [0] * 65536
    mem[org:org + len(code)] = code
    bad, a = [], org
    while a < org + len(code):
        op = mem[a]
        t, n = disasm(mem, a)
        if op in (0xDD, 0xFD, 0xF3, 0xFB) or (op == 0xED and mem[a + 1] in (0x47, 0x46, 0x56, 0x5E, 0x4D, 0x45)):
            bad.append((hex(a), t))
        a += n
    return bad


def build(z80, out, name, say=print):
    """Loader snapshot -> <name>_entry.z80 (loader run), <name>_start.z80 (+ front end), <name>.nex,
    <name>_sprites.nex. -> (ok, paths, patch, entry (regs, mem))."""
    import hashlib
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    entry = os.path.join(out, name + '_entry.z80')
    start = os.path.join(out, name + '_start.z80')
    f, regs, mem, o7 = loader_entry(z80, entry)
    prof = load_profile()
    front = bytes.fromhex(prof['hooks']['front'])
    if (regs[0] << 8 | regs[1]) != 0x0440:
        raise ValueError('loader entry AF %04X differs from the front end\'s restore (0x0440)' % (regs[0] << 8 | regs[1]))
    make_start(entry, start, front)
    say('Loader    : run to %d at frame %d (SPACE for PAUSE 0), 7FFD %02X -> %s' % (GAME_ENTRY, f, o7,
                                                                                 os.path.basename(start)))
    ft = front_tests(start, regs, mem)
    ftf = {k: v for k, v in ft.items() if v}
    say('Front end : loading screen, wait for a key, every register + RAM as the loader left them: %d cases %s'
        % (len(ft), 'PASS' if not ftf else 'FAIL %s' % ftf))
    plain = os.path.join(out, name + '.nex')
    zt.convert(start, plain, tail_req=TAIL_ADDR, quiet=True)
    bad = boot_check(plain, start)
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = RenegadePatch()
    sc = static_check(patch.rom_code, 0x2200)
    say('Static    : hook code %d bytes at 0x2200-0x%04X (ROM 0 bytes 0x3500-0x3508 untouched), no IX/IY/I/IFF/IM '
        'instructions: %s' % (len(patch.rom_code), patch.regblock + 20, 'PASS' if not sc else 'FAIL %s' % sc))
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(start, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, start, RenegadePatch())
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    say('Colours   : %s' % ('%d colour-map entries (docs/profiles/target_renegade_colours.json)' % len(patch.colours)
                            if patch.colours else 'no colour map: ink black, body grey (7)'))
    return (not ftf and not bad and not bad2 and not sc), (plain, spr, start), patch


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : renegade (Target Renegade: back-buffer composer, masked plotter + undo stack; every figure -> sprites)')
    ok, (plain, spr, start), patch = build(z80, out, name, say)
    from . import z80tonex as zt
    s = zt.Z80Snapshot(start)
    patch.apply(s)
    states = []
    for r in list(a.rzx or []):
        t = __import__('time').time()
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        np_ = c['pairs %d' % PLOT] + c['pairs %d' % PLOT_M]
        say('Verify    : %s  %d frames, %d plots, %d commits (max %d sprites), %d sprite pixels, %.0fs -> %s' % (
            os.path.basename(r), c['frames'], np_, c['commits'], c['max sprites in a frame'],
            c['sprite pixels compared'], __import__('time').time() - t, 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            pairs: %s' % ', '.join('%s %d' % (k[6:], v) for k, v in sorted(c.items()) if k.startswith('pairs ')))
        say('            hook cost: %d T per game frame in simulator T (the commit / scenery copy run at '
            '28 MHz: about 1/8 of that on the Next; plot hooks 3.5 MHz: %d T)' % (
                c['hook T per game frame (3.5 MHz units, x1 not /8)'],
                (c['hook T at %d' % PLOT] + c['hook T at %d' % PLOT_M]) // max(1, c['commits'])))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:240]))
    if states:
        u, f = unit_tests(patch, states, swapped_patch(), int_patch())
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf and u['negative detected'] == u['negative cases']
        say('Unit      : %d commit cases (%d parts converted, %d passthrough by the guard), %d cache-hit, %d plot-hook '
            'log cases, log full (65 parts), patterns full (40 parts: 32 + 8 dropped), colour map %d entries + wrong '
            'check bytes; negative controls %d/%d detected -> %s' % (
                u['cases'], u['converted parts'], u['passthrough parts'], u['cache hit cases'], u['plot hook cases'],
                u['map entries'], u['negative detected'], u['negative cases'], 'PASS' if not uf else 'FAIL %s %s' % (uf, dict(f))))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Recolour (PLAYBOOK 3b): colours live only in page H's V_COL byte (bank 13) and the colour store
# (banks 14-19); the game never reads either
# ---------------------------------------------------------------------------------------------

COLOUR_BANKS = (13, 14, 15, 16, 17, 18, 19)
RECOLOUR = {'game': 'target_renegade', 'output': 'sprites', 'colours': 'docs/profiles/target_renegade_colours.json',
            'clear': True, 'note': NOTE}


def colour_inputs_md5(peek):
    """MD5 of the game bytes the colours belong to (graphics and frame tables, 0x6500-0xBFFF of the
    start state: banks 5 and 2 after the front end)."""
    import hashlib
    return hashlib.md5(bytes(peek(a) for a in range(0x6500, 0xC000))).hexdigest()


def recolour(nex, cmap):
    from .recolour import nex_offsets
    d = bytearray(nex)
    off = nex_offsets(d)
    need = set(COLOUR_BANKS) | {5, 2, 0, 10, 12}
    if not need <= set(off):
        raise ValueError('not a Target Renegade sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    ram = {5: bank(5), 2: bank(2), 0: bank(0)}
    peek = lambda a: ram[5][a - 0x4000] if a < 0x8000 else (ram[2][a - 0x8000] if a < 0xC000 else ram[0][a - 0xC000])
    prof = load_profile()
    want = prof.get('colour_inputs')
    if want != colour_inputs_md5(peek):
        raise ValueError('game graphics differ from the expected snapshot (%s, expected %s)' % (colour_inputs_md5(peek), want))
    p0 = RenegadePatch(prof, colours={})
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site %d does not hold this build\'s hook jump' % a)
    b12 = bank(12)
    lo, hi = p0.regblock - 0x2000, p0.regblock - 0x2000 + 20
    if b12[:lo] != bytes(p0.page[:lo]) or b12[hi:8192] != bytes(p0.page[hi:8192]):
        raise ValueError('hook code differs from this version\'s (rebuild with nexclash.py auto)')
    if bank(10)[0x1000:0x1000 + len(p0.stub_extra)] != p0.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    p = RenegadePatch(prof, colours=cmap)
    from .recolour import splice
    out, changed = splice(nex, {b: p.extra_banks[b] for b in COLOUR_BANKS})
    return out, {'banks changed': changed, 'colour-map entries': len(cmap)}


# ---------------------------------------------------------------------------------------------
# Preview frames: the original screen | what stays on the ULA | ULA + the figures as sprites
# ---------------------------------------------------------------------------------------------

def _screen_rgb(pix, attrs, x, y):
    a = attrs[(y >> 3) * 32 + (x >> 3)]
    b = pix[((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)]
    on = b & (0x80 >> (x & 7))
    c = (a & 7) if on else ((a >> 3) & 7)
    v = 0xFF if a & 64 else 0xD7
    return ((v if c & 2 else 0), (v if c & 4 else 0), (v if c & 1 else 0))


def _ula_with_scenery(shot):
    """Screen pixels with the play area (rows 1-16) taken from the clean buffer."""
    pix = bytearray(shot['screen'][:6144])
    yt = shot['ytab']
    for y in range(128):
        sy = 8 + y
        for x in range(32):
            a = (yt[2 * y] | x) + 256 * yt[2 * y + 1] - BUF[0]
            pix[((sy & 0xC0) << 5) | ((sy & 7) << 8) | ((sy & 0x38) << 2) | x] = shot['scenery'][a]
    return bytes(pix)


def preview(shots, png, colours=None):
    from PIL import Image
    cmap = colours or {}
    n = len(shots)
    img = Image.new('RGB', (3 * 256 + 8, n * 192 + 4 * (n - 1)), (40, 40, 40))
    for row, f in enumerate(sorted(shots)):
        sh = shots[f]
        oy = row * 196
        ula = _ula_with_scenery(sh)
        at = sh['attrs']
        for y in range(192):
            for x in range(256):
                img.putpixel((x, oy + y), _screen_rgb(sh['screen'], at, x, y))
                c = _screen_rgb(ula, at, x, y)
                img.putpixel((260 + x, oy + y), c)
                img.putpixel((520 + x, oy + y), c)
        for d in sh['plots']:
            p = sheet_part(dict(d, attrs=at))
            for c, r, key, bit, code, dflt in p['pixels']:
                e = cmap.get(key)
                v = (e[2][bit] if e else 0) or dflt
                if e and len(e) > 3 and e[3] & (0x80 >> bit):
                    continue
                if not v:
                    continue
                sx = d['x'] * 8 + ((d['W'] * 8 - 1 - c) if d['mir'] else c)
                sy = 8 + d['y'] + r
                if 0 <= sx < 256 and 8 <= sy < 136:
                    img.putpixel((520 + sx, oy + sy), rgb(v))
    img.save(png)


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.renegade',
                                 description='Target Renegade figure colours: sheets to paint / read back')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> the two sheets (+ layout JSON; game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('-o', '--output', default='target_renegade')
    p.add_argument('--stop', type=int)
    p.add_argument('--preview', help='frames for a preview PNG, e.g. 900,2500,4000')
    p = sub.add_parser('colours', help='painted sheet -> docs/profiles/target_renegade_colours.json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--output', default=COLOURS)
    a = ap.parse_args(argv)
    if a.cmd == 'sheet':
        frames = [int(v) for v in a.preview.split(',')] if a.preview else ()
        comps, shots = capture(a.rzx, a.stop, keep_frames=frames)
        for png, n in sheets(comps, a.output, load_colours()):
            print('%d figures -> %s' % (n, png))
        if shots:
            preview(shots, a.output + '_PREVIEW.png', load_colours())
            print('preview -> %s_PREVIEW.png (original | ULA layer | ULA + sprites)' % a.output)
    else:
        lay = a.layout or os.path.splitext(a.png)[0] + '_layout.json'
        ent, rep = read_sheet(a.png, lay)
        save_colours(ent, a.output)
        for k, v in sorted(rep.items()):
            print('%s: %d' % (k, v))
        print('-> %s' % a.output)


if __name__ == '__main__':
    _main()
