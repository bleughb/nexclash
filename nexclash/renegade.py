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
    """A plot (capture) -> coloursheet part: every bit of its graphics bytes (paper bits code 0)."""
    W, Rr, gfx, data = d['W'], d['R'], d['gfx'], d['data']
    pixels, entries = [], {}
    for r in range(Rr):
        for c in range(W):
            j = stored_index(W, r, c)
            m, g = data[2 * j], data[2 * j + 1]
            k = ckey(gfx, j)
            entries.setdefault(k, [entry_check(m, g), 1])
            # screen column of this stored column
            sc = d['x'] + (W - 1 - c if d['mir'] else c)
            line = SCREEN_ROW0 * 8 + d['y'] + r
            at = d['attrs'][((line >> 3) % 24) * 32 + (sc & 31)]
            for b in range(8):
                code = pixel_code(m, g, b)
                dflt = (ink_of(at) if code == 1 else paper_of(at)) if code else 0
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
