"""Match Day (Ocean, 1985; Jon Ritman / Chris Clarke; 48K) - pure-XOR engine, phase A half.

The game draws every figure by XOR straight to the screen (no masks, no back buffer), and each
draw ERASES AND REDRAWS in one pass (old image XOR new image per byte):
  players  35653 (0x8B45), IX = object (27 bytes; 16 on the pitch at 0xB4FC.., the walk-on figure
           0xB6AC): builds the new image in one of the object's two buffers (IX+0x14 / +0x16, bit 5
           of IX+0 picks) with 0x8DEC (HL = graphics, B = rows / 2, 2 bytes a row, shifted by A&6 into
           3 bytes a row; 28-row frames at 0xC460 + 56n, or 14 rows (+28) + 18 leg rows at 0xDDC0 + 36n),
           then 0x8ECE dispatches on the old/new row counts to the XOR loops 0x8EF0-0x9165
           (unrolled, clipped at the edges), then paints the cells 0x9168-0x9348 via 0x934E /
           0x9369 / 0x937D: the old cells back to the pitch ink (0x93A5), the new ones IX+0x0F
           (bottom 1-2 cell rows: SOCKS) and IX+0x0E (3 cell rows above: STRIP). The controlled
           player's IX+0x0F is set to the strip colour (0x82C4 / 0x82CD: socks indicator).
  ball     0x9FCF: shadow (1 row, B=1) then ball (5 rows) by 0xA046 (XOR old and new, 2 bytes a
           row; graphics pre-shifted at 0xA111 + 14 * (x & 7)); off screen = address 0x2000 (ROM).
Everything else on the pitch is scenery and stays on the ULA: pitch lines and goals are XOR line /
block writers (0xE73B-0xE956, 0xEC50, 0xEF14, 0xF049, 0xF198; scan: they only XOR), the crowd
(0x9936 LDI copier, 0x99DF), clock and score. No routine reads figure pixels (an2 pass, 6210 frames:
every non-figure reader of a figure byte is one of those XOR writers).

Design (games/match_day.md): figure XOR writes go to a 1-bit shadow (ULA XOR shadow == the original
screen), the figure cell paints are dropped, the figures are hardware sprites in the colours of
their object (STRIP = IX+0x0E, SOCKS = IX+0x0F at run time, so the team colours the menu sets and
the socks indicator keep working) plus the fixed colours the user paints.

CLI:
    python -m nexclash.matchday sheet Z80 RZX [-o match_day]      PAINTING + REFERENCE sheets
    python -m nexclash.matchday preview Z80 RZX --at F,F,... [-o p.png]   original | planned
    python -m nexclash.matchday colours PAINTED.png [--layout L]  -> docs/profiles/match_day_colours.json
"""
import collections
import os

PLOT, BUILD, BALL, BALL_ROWS = 0x8B45, 0x8DEC, 0x9FCF, 0xA044
FIG_XOR = (0x8EF0, 0x9168)          # player XOR loops (screen writes)
BALL_XOR = (0xA046, 0xA06D)
CELL_PAINT = (0x934E, 0x938A)        # the figure cell paints
# scenery writers that XOR (pitch lines, goals, markers): leave the figures' bits alone; every other
# non-figure screen write OVERWRITES (screen clears 0x87DF / 0xEFB3, crowd 0x9936.., text): the
# shadow model clears the figure bits of that byte (original byte = the written value)
SCENERY_XOR = ((0xE73B, 0xE957), (0xEC50, 0xECB2), (0xEF3F, 0xEF75), (0xF049, 0xF0BB), (0xF198, 0xF1CA))
OBJ0, OBJ_N, OBJ_SIZE, WALKON = 0xB4FC, 16, 27, 0xB6AC
FRAMES, FRAME_TAB, UPPERS, UPPER_TAB = 120, 0xC460, 18, 0xDDC0   # 28-row frames, 18-row upper bodies
DIVE0 = 72                           # frames 72..: the keeper's dive, drawn in two halves (2k left, 2k+1 right)
STATIC_GROUP = 'From the code (not in the recording yet)'
STRIP, SOCKS = 1, 2                  # palette roles: the object's IX+0x0E / IX+0x0F colour

# Sprite palette for the sheet (RRRGGGBB): 0 transparent, 1 STRIP role, 2 SOCKS role (colours the
# Spectrum never shows, so the read-back cannot confuse them with a fixed colour), 3-15 fixed
PALETTE = [0x00, 0xF5, 0x93, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0x1C, 0xFC, 0xFF]
FIXED = {'black': 3, 'blue': 4, 'red': 5, 'magenta': 6, 'green': 7, 'cyan': 8, 'yellow': 9, 'white': 10,
         'bright blue': 11, 'bright red': 12, 'bright green': 13, 'bright yellow': 14, 'bright white': 15}
WHITE = 10
SPEC_RGB = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0),
            (205, 205, 205)]
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'match_day_colours.json')
NOTE = ('Match Day figure colours, read back from match_day_PAINTING_SPRITES.png (python -m '
        'nexclash.matchday colours). Key = graphics byte address, check = that byte, 8 nibbles = '
        'palette index of its bits (0 = default; 1 = the object\'s strip colour, 2 = its socks '
        'colour, 3-15 fixed colours).')


def scr_xy(a):
    o = a - 0x4000
    return (o & 31), ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0)


def key(a):
    return '%04X' % a


def part(gfx, rows, data, dy, group, family, socks_from):
    """One 0x8DEC build (2 bytes a row) -> a coloursheet part. Every bit listed (paper = code 0,
    paint_clear: an outline or a filled gap can be painted); default STRIP above socks_from (figure
    row), SOCKS from it down; the ball group: white."""
    pixels, entries = [], {}
    for r in range(rows):
        for c in range(16):
            j = 2 * r + c // 8
            b = data[j]
            k = key(gfx + j)
            entries.setdefault(k, [b, 1])
            ink = b >> (7 - c % 8) & 1
            dflt = WHITE if group != 'Players' else (SOCKS if dy + r >= socks_from else STRIP)
            pixels.append((c, r, k, c % 8, 1 if ink else 0, dflt if ink else 0))
    return dict(id=(gfx, rows), size=rows, w=16, h=rows, x=0, y=dy, mir=0, group=group, fam=family,
                pixels=pixels, entries=entries)


class Capture:
    """Python-simulator pass over the RZX: per frame the parts of every player draw (joined by the
    object: family = (draw number)), ball, shadow; the shadow model (figure XOR writes) and each
    object's placed image, for the preview."""

    def __init__(s, want_frames=()):
        from . import coloursheet as cs
        s.col = cs.Collector(family=lambda p: p.get('fam'))
        s.frame, s.n = 0, 0
        s.cur, s.parts, s.pending = None, [], []
        s.sh = bytearray(0x1800)
        s.objs = {}                     # ix -> {screen address: its figure bits} (XOR footprint, exact)
        s.cols = {}                     # ix -> (strip, socks) of its last draw
        s.ball = {}
        s.want = set(want_frames)
        s.shots = {}
        s.calls = collections.Counter()
        s.overwrites = collections.Counter()
        s.dive = {}

    def on_sim(s, sim):
        s.R, s.M = sim.registers, sim.memory

    def on_frame(s, n):
        s.frame = n
        if s.pending:
            s.col.add_frame(s.pending)
            s.pending = []
        if n in s.want:
            ula = bytes(s.M[0x4000:0x5B00])
            s.shots[n] = (ula, bytes(s.sh), {k: dict(v) for k, v in s.objs.items()}, dict(s.cols))

    def before(s, pc):
        R, M = s.R, s.M
        if pc == PLOT:
            sp = R[12]
            ix = R[8] << 8 | R[9]
            # identity = the object's buffer pair (IX+0x14..0x17): the depth sort swaps whole 27-byte
            # records, so the same figure changes IX between frames
            s.cur = dict(ix=ix, who=bytes(M[ix + 0x14:ix + 0x18]), ret=M[sp] | M[sp + 1] << 8, sp=sp, builds=[])
            s.calls[s.cur['ret']] += 1
        elif s.cur:
            if pc == BUILD:
                s.cur['builds'].append((R[6] << 8 | R[7], R[2], R[4] << 8 | R[5]))
            elif pc == s.cur['ret'] and R[12] == s.cur['sp'] + 2:
                s._done(s.cur)
                s.cur = None
        if pc == BALL_ROWS:
            hl = R[6] << 8 | R[7]
            ball_at = M[0xA0C0] | M[0xA0C1] << 8
            shadow_src = M[0xA0D3] | M[0xA0D4] << 8
            shadow_at = M[0xA0C2] | M[0xA0C3] << 8
            if ball_at >= 0x4000:
                d = bytes(M[hl - 9 + i] for i in range(10))
                s.pending.append(part(hl - 9, 5, d, 0, 'Ball', ('b', s.n), 99))
            if shadow_at >= 0x4000:
                d = bytes(M[shadow_src - 1 + i] for i in range(2))
                s.pending.append(part(shadow_src - 1, 1, d, 0, 'Ball shadow', ('s', s.n), 99))
            s.n += 1

    def _done(s, c):
        M = s.M
        ix = c['ix']
        if not c['builds']:
            return
        # one figure = the builds that fill one buffer, top row first in memory (the draw runs from
        # the buffer's end = the bottom row): the 0x8CDA path builds the frame's lower 14 rows
        # (legs) at the end and an upper body of 18 rows (0xDDC0 + 36n: arms, heading) before them;
        # two whole 28-row builds (the bottom-edge path 0x8C69: 0x9404 / 0x94AC) are two figures
        figs, run, end = [], [], None
        for gfx, b, dest in sorted(c['builds'], key=lambda t: t[2]):
            if run and dest != end:
                figs.append(run)
                run = []
            run.append((gfx, b))
            end = dest + 6 * b
        figs.append(run)
        x = M[ix + 5]
        for run in figs:
            s.n += 1
            rows = sum(2 * b for _, b in run)              # 0x8DEC copies TWO rows per B
            dy, parts = 0, []
            for gfx, b in run:
                d = bytes(M[gfx + i] for i in range(4 * b))
                parts.append(dict(part(gfx, 2 * b, d, dy, 'Players', ('p', s.n), rows - 8), x=x))
                dy += 2 * b
            # the goalkeeper's dive: two objects 16 px apart, the keeper + the spare object 0xB6AC,
            # each drawn every other frame -> one figure from the latest image of both halves
            dive = len(run) == 1 and run[0][0] < 0xDDC0 and (run[0][0] - 0xC460) // 56 >= DIVE0
            if dive and len(figs) == 1:
                s.dive[ix] = parts
                other = [k for k in s.dive if (k == WALKON) != (ix == WALKON)]
                if other:
                    both = sorted(s.dive[other[-1]] + parts, key=lambda p: p['x'])
                    s.n += 1
                    s.pending.extend(dict(p, fam=('d', s.n)) for p in both)
                    continue
            else:
                s.dive.pop(ix, None)
            s.pending.extend(parts)

    def on_write(s, a, v, pc, mem):
        if 0x4000 <= a < 0x5800:
            who = s.cur['who'] if FIG_XOR[0] <= pc < FIG_XOR[1] and s.cur else 'ball' if BALL_XOR[0] <= pc < BALL_XOR[1] else None
            if who is None:
                if s.sh[a - 0x4000] and not any(lo <= pc < hi for lo, hi in SCENERY_XOR):
                    s.sh[a - 0x4000] = 0
                    s.overwrites[pc] += 1
                    for fp in s.objs.values():
                        fp.pop(a, None)
                return
            d = s.M[a] ^ v
            s.sh[a - 0x4000] ^= d
            fp = s.objs.setdefault(who, {})
            nv = fp.get(a, 0) ^ d
            if nv:
                fp[a] = nv
            else:
                fp.pop(a, None)
            if who != 'ball':
                ix = s.cur['ix']
                s.cols[who] = (s.M[ix + 0x0E] & 7, s.M[ix + 0x0F] & 7)


def run_capture(z80, rzx, want=(), stop=None):
    from .simrun import run
    cap = Capture(want)
    run(z80, [rzx] if isinstance(rzx, str) else rzx, cap, stop=stop)
    return cap


ORDER = ['Players', 'Ball', 'Ball shadow', STATIC_GROUP]


def add_static(col, mem):
    """Frames and upper bodies the recording never drew (every graphics byte must be paintable):
    28-row frames alone (dive frames 72.. as left/right pairs), 18-row upper bodies alone."""
    seen = {p['id'][0] for c in col.comps.values() for p in c['parts']}
    n = 0
    figs = []
    for f in range(FRAMES):
        a = FRAME_TAB + 56 * f
        if f >= DIVE0 and f % 2:
            continue
        pair = [f, f + 1] if f >= DIVE0 else [f]
        if all(FRAME_TAB + 56 * g in seen for g in pair):
            continue
        figs.append([(FRAME_TAB + 56 * g, 28, 16 * k) for k, g in enumerate(pair)])
    for u in range(UPPERS):
        if UPPER_TAB + 36 * u not in seen:
            figs.append([(UPPER_TAB + 36 * u, 18, 0)])
    for fig in figs:
        n += 1
        parts = []
        for gfx, rows, x in fig:
            d = bytes(mem[gfx:gfx + 2 * rows])
            p = part(gfx, rows, d, 0, 'Players', None, rows - 8 if rows == 28 else 99)
            parts.append(dict(p, group=STATIC_GROUP, dx=x, dy=0, dmir=0, vmir=0))
        if any(q[4] for p in parts for q in p['pixels']):
            col.comps[('static', n)] = dict(count=0, group=STATIC_GROUP, parts=parts)
    return n


def snapshot_memory(z80):
    from . import z80tonex as zt
    s = zt.Z80Snapshot(z80)
    return bytes(0x4000) + bytes(s.banks[5]) + bytes(s.banks[2]) + bytes(s.banks[0])


def sheets(col, out, colours=None):
    """PAINTING: the fewest whole figures that show every graphics byte (PLAYBOOK 3b); REFERENCE:
    every figure drawn."""
    from . import coloursheet as cs
    rgb = cs.palette_rgb(PALETTE)
    every = sorted([c for c in col.comps.values() if any(q[4] for p in c['parts'] for q in p['pixels'])], key=lambda c: (ORDER.index(c['group']), str(c['parts'][0]['id'])))
    res = []
    for suffix, sel in (('PAINTING_SPRITES', col.composites(ORDER)), ('REFERENCE_ALL_SPRITES', every)):
        png = '%s_%s.png' % (out, suffix)
        lay = os.path.splitext(png)[0] + '_layout.json'
        n = cs.write(sel, png, lay, rgb, colours, unique=False, paint_clear=True)
        res.append((png, n))
    return res


def addr_of(x, y):
    return 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)


def footprint_pixels(fp):
    """{screen address: bits} -> [(x, y)]."""
    out = []
    for a, bits in fp.items():
        col, y = scr_xy(a)
        for bit in range(8):
            if bits >> (7 - bit) & 1:
                out.append((col * 8 + bit, y))
    return out


def enclosed(px):
    """Paper pixels of a figure not reachable from outside its box through paper (4-connected):
    the gaps the original shows the pitch through."""
    ink = set(px)
    x0, x1 = min(x for x, _ in px) - 1, max(x for x, _ in px) + 1
    y0, y1 = min(y for _, y in px) - 1, max(y for _, y in px) + 1
    seen, st = {(x0, y0)}, [(x0, y0)]
    while st:
        x, y = st.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if x0 <= q[0] <= x1 and y0 <= q[1] <= y1 and q not in seen and q not in ink:
                seen.add(q)
                st.append(q)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
            if (x, y) not in ink and (x, y) not in seen and 0 <= x < 256 and 0 <= y < 192]


def preview(z80, rzx, frames, out):
    """Original | planned: the ULA without the figures (ULA XOR shadow, figure cells left in the pitch
    colours) + every figure as a sprite, solid colours by role: STRIP above the bottom 8 rows of the
    figure, SOCKS in them (the game's colours of that object), ball white; drawn front-to-back by
    the figure's bottom y (nearer = lower = in front)."""
    from PIL import Image
    cap = run_capture(z80, rzx, frames, stop=max(frames) + 1)
    img = Image.new('RGB', (2 * 512 + 8, 392 * len(cap.shots)), (40, 40, 40))
    for n, f in enumerate(sorted(cap.shots)):
        ula, sh, objs, cols = cap.shots[f]
        for side in (0, 1):
            im = Image.new('RGB', (256, 192))
            for y in range(192):
                for x in range(256):
                    a = addr_of(x, y) - 0x4000
                    b = ula[a] ^ (sh[a] if side else 0)
                    at = ula[0x1800 + (y >> 3) * 32 + (x >> 3)]
                    ink, paper = at & 7, at >> 3 & 7
                    if side and paper == 4 and y >= 24:
                        ink = 7                     # pitch cells keep the pitch ink (white lines)
                    im.putpixel((x, y), SPEC_RGB[ink if b >> (7 - (x & 7)) & 1 else paper])
            if side:
                figs = []
                for who, fp in objs.items():
                    px = footprint_pixels(fp)
                    if px:
                        figs.append((max(y for _, y in px), who, px))
                strips = collections.Counter(c[0] for w, c in cols.items() if objs.get(w))
                for bottom, who, px in sorted(figs, key=lambda t: t[0]):
                    if who == 'ball':
                        for (x, y) in px:
                            im.putpixel((x, y), (255, 255, 255))
                        continue
                    strip, socks = cols.get(who, (7, 7))
                    # solid (Dean 2026-10-20): the enclosed paper in the opposite team's colours
                    opp = [c for c in strips if c != strip]
                    ostrip = opp[0] if opp else strip
                    osocks = next((c[1] for w, c in cols.items() if c[0] == ostrip and c[1] != c[0]), ostrip)
                    for (x, y) in enclosed(px):
                        c = SPEC_RGB[osocks if y > bottom - 8 else ostrip]
                        im.putpixel((x, y), tuple(min(255, v + 50) for v in c))
                    for (x, y) in px:
                        c = SPEC_RGB[socks if y > bottom - 8 else strip]
                        im.putpixel((x, y), tuple(min(255, v + 50) for v in c))
            img.paste(im.resize((512, 384), Image.NEAREST), (side * 520, n * 392))
    img.save(out)
    return sorted(cap.shots), cap


def check_model(z80, rzx, frames):
    """Per object footprints XORed together == the shadow; footprints of different objects that
    overlap (same byte) are the places where the original's figures cut into each other."""
    cap = run_capture(z80, rzx, frames, stop=max(frames) + 1)
    res = {}
    for f, (ula, sh, objs, cols) in sorted(cap.shots.items()):
        m = bytearray(0x1800)
        for fp in objs.values():
            for a, bits in fp.items():
                m[a - 0x4000] ^= bits
        res[f] = (sum(1 for i in range(0x1800) if m[i] != sh[i]), sum(1 for fp in objs.values() if fp))
    return res


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.matchday')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='Z80 + RZX -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('z80')
    p.add_argument('rzx')
    p.add_argument('-o', '--output', default='match_day')
    p.add_argument('--stop', type=int)
    p = sub.add_parser('preview')
    p.add_argument('z80')
    p.add_argument('rzx')
    p.add_argument('--at', required=True)
    p.add_argument('-o', '--output', default='match_day_preview.png')
    p = sub.add_parser('check')
    p.add_argument('z80')
    p.add_argument('rzx')
    p.add_argument('--at', required=True)
    p = sub.add_parser('colours')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--output', default=COLOURS)
    a = ap.parse_args(argv)
    if a.cmd == 'sheet':
        from . import coloursheet as cs
        cap = run_capture(a.z80, a.rzx, stop=a.stop)
        if cap.pending:
            cap.col.add_frame(cap.pending)
        add_static(cap.col, snapshot_memory(a.z80))
        for png, n in sheets(cap.col, a.output, cs.load(COLOURS)):
            print('%d figures -> %s' % (n, png))
        for ret, k in sorted(cap.calls.items()):
            print('  player plot from 0x%04X: %d calls' % (ret, k))
    elif a.cmd == 'preview':
        shots, _ = preview(a.z80, a.rzx, [int(x) for x in a.at.split(',')], a.output)
        print('%d shots -> %s' % (len(shots), a.output))
    elif a.cmd == 'check':
        for f, (bad, n) in check_model(a.z80, a.rzx, [int(x) for x in a.at.split(',')]).items():
            print('frame %d: %d figures on screen, %d shadow bytes differ from the footprints' % (f, n, bad))
    else:
        from . import coloursheet as cs
        lay = a.layout or os.path.splitext(a.png)[0] + '_layout.json'
        ent, rep = cs.read(a.png, lay, clear=True)
        cs.save(ent, a.output, NOTE)
        for k, v in sorted(rep.items()):
            print('%s: %d' % (k, v))
        print('-> %s' % a.output)


if __name__ == '__main__':
    _main()
