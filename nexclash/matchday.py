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
SCENERY_XOR = ((0x5F2A, 0x5F30), (0x62D3, 0x62DD), (0xE73B, 0xEBEE), (0xEC50, 0xECB2), (0xEF3F, 0xEF75), (0xF049, 0xF0BB), (0xF198, 0xF1CA))
OBJ0, OBJ_N, OBJ_SIZE, WALKON = 0xB4FC, 16, 27, 0xB6AC
FRAMES, FRAME_TAB, UPPERS, UPPER_TAB = 116, 0xC460, 18, 0xDDC0   # 28-row frames, 18-row upper bodies
DIVE0 = 72                           # frames 72..: the keeper's dive, drawn in two halves (2k left, 2k+1 right)
CAMERA = 0xE60B                      # camera x (16 bit): screen x = world x - camera
PITCH_RGB = (0, 205, 0)              # the pitch's paper (green, not bright)
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
    """One 0x8DEC build (2 bytes a row) -> a coloursheet part. Every bit listed (paint_clear: a gap
    or an outline can be painted); ink defaults STRIP above socks_from (figure row), SOCKS from it
    down; paper enclosed by the figure (players: solid, Dean 2026-10-20) defaults the pitch green
    (code 2); the ball group: white ink."""
    rws = [data[2 * r] << 8 | data[2 * r + 1] for r in range(rows)]
    fm = enclosed_mask(rws) if group in ('Players', STATIC_GROUP) else [0] * rows
    pixels, entries = [], {}
    for r in range(rows):
        for c in range(16):
            j = 2 * r + c // 8
            b = data[j]
            k = key(gfx + j)
            entries.setdefault(k, [b, 1])
            ink = b >> (7 - c % 8) & 1
            if ink:
                dflt = WHITE if group not in ('Players', STATIC_GROUP) else (SOCKS if dy + r >= socks_from else STRIP)
                pixels.append((c, r, k, c % 8, 1, dflt))
            elif fm[r] >> (15 - c) & 1:
                pixels.append((c, r, k, c % 8, 2, 7))
            else:
                pixels.append((c, r, k, c % 8, 0, 0))
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
        s.drawn = {}                    # figure -> (IX, camera x 0xE60B at its last draw)
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
            s.shots[n] = (ula, bytes(s.sh), {k: dict(v) for k, v in s.objs.items()}, dict(s.cols), dict(s.drawn))

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
                    fl, fr = [(p['id'][0] - FRAME_TAB) // 56 for p in both]
                    if fl % 2 == 0 and fr == fl + 1:     # a matching pair (the lag mixes steps)
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
                s.drawn[who] = (ix, s.M[CAMERA] | s.M[CAMERA + 1] << 8, s.M[ix + 3])


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
        ula, sh, objs, cols, drawn = cap.shots[f]
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
                        figs.append([max(y for _, y in px), who, px])
                # keeper dive (Dean 2026-10-20: "torn in half"): the halves are drawn on alternate
                # frames; the spare half 0xB6AC goes where it would be at the keeper half's camera x
                spare = [g for g in figs if g[1] != 'ball' and drawn.get(g[1], (0,))[0] == WALKON]
                keeper = [g for g in figs if g[1] != 'ball' and drawn.get(g[1], (0,))[0] != WALKON
                          and drawn.get(g[1], (0, 0, 0))[2] >= DIVE0]
                if spare and keeper and drawn[spare[0][1]][2] >= DIVE0:
                    dx = drawn[spare[0][1]][1] - drawn[keeper[0][1]][1]
                    spare[0][2] = [(x + dx, y) for x, y in spare[0][2] if 0 <= x + dx < 256]
                for bottom, who, px in sorted(figs, key=lambda t: t[0]):
                    if who == 'ball':
                        for (x, y) in px:
                            im.putpixel((x, y), (255, 255, 255))
                        continue
                    strip, socks = cols.get(who, (7, 7))
                    # solid (Dean 2026-10-20, third answer): the enclosed paper in the pitch
                    # green - opaque (hides the lines behind), the colour of the background
                    for (x, y) in enclosed(px):
                        im.putpixel((x, y), PITCH_RGB)
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
    for f, (ula, sh, objs, cols, drawn) in sorted(cap.shots.items()):
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
    p = sub.add_parser('sheet', help='Z80 + RZX(s) -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('z80')
    p.add_argument('rzx', nargs='+')
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
        print('frames played: %d' % cap.frame)
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


# =============================================================================================
# The build (phase B): screen writes -> NOP, hooks in alt ROM image 1 (asm/matchday_hooks.asm)
# =============================================================================================
import json as _json

ROM_ORG = 0x2300                     # alt ROM: 0x22CB-0x3BFE never read (scan, both recordings);
                                     # 0x3BFF/0x3C00 = the IM 2 vector (FF FF) stays ROM
ALT_PAGE = 24
STATE_BANK, NIB_BANKS = 13, (14, 15)  # state page 26 (+27 unused), row tables pages 28-31
STATE_PG, NIB_PG = 26, 28
BALLTAB_OFF = 0x1800                 # in the state page
BALL0, BALLEND = 0xA108, 0xA188
FRAMEEND = 0xE048                    # end of the upper bodies (0xDDC0 + 36 * 18)
NFIG = 17
F_VIS, F_X, F_YT, F_BANK, F_SLOT, F_N, F_YB, F_FR, F_CAM, F_NEW, F_XS = 0, 1, 3, 5, 6, 7, 8, 9, 10, 12, 13   # asm records
GREEN = 7                            # fill: the pitch green (palette index 7 = 0x14 = ULA green paper)
FILL_ROWS_SOCKS = 20                 # frame rows 20-27 default SOCKS
SITES = {0x8DEC: ('e606fe', 'e_bd', 0xC3), 0x8D63: ('ddcb00', 'e_clr', 0xC3), 0x8B5C: ('cdce8e', 'e_pl', 0xCD),
         0x9D15: ('cdcf9f', 'e_ball', 0xCD), 0x817F: ('cd9898', 'e_frame', 0xCD),
         0xE62C: ('cdadef', 'e_cls', 0xCD), 0x819D: ('f33e00', 'e_exit', 0xC3)}
# the figure / ball XOR screen writes and the figure cell paints: LD (DE),A / LD (HL),A -> NOP
SCREEN_NOPS = [0x8EF9, 0x8F02, 0x8F0B, 0x8F3F, 0x8F44, 0x8F49, 0x8F61, 0x8F66, 0x8F6B, 0x8FB9, 0x8FBE,
               0x8FC3, 0x8FDB, 0x8FE0, 0x9000, 0x9009, 0x9013, 0x9036, 0x9040, 0x9045, 0x9068, 0x9072,
               0x90A0, 0x90A5, 0x90BD, 0x90C2, 0x90DF, 0x90E4, 0x90FC, 0x9119, 0x9131, 0x914E,
               0x9356, 0x935D, 0x9364, 0x9371, 0x9378, 0x9385, 0xA048, 0xA04D, 0xA05A, 0xA05F]
NOP_ORIG = {a: (0x77 if 0x934E <= a < 0x938A else 0x12) for a in SCREEN_NOPS}


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'match_day.json')


def load_profile():
    return _json.load(open(_profile_path()))


def is_matchday(snap):
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def enclosed_mask(rows, w=16):
    """rows (ints, w bits, bit w-1 = leftmost) -> per row the bits of paper enclosed by ink
    (not reachable from outside the box through paper, 4-connected)."""
    h = len(rows)
    ink = lambda x, y: rows[y] >> (w - 1 - x) & 1
    seen = set()
    st = [(x, y) for x in range(-1, w + 1) for y in (-1, h)] + [(x, y) for y in range(h) for x in (-1, w)]
    seen.update(st)
    while st:
        x, y = st.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if -1 <= q[0] <= w and -1 <= q[1] <= h and q not in seen:
                if 0 <= q[0] < w and 0 <= q[1] < h and ink(*q):
                    continue
                seen.add(q)
                st.append(q)
    out = []
    for y in range(h):
        m = 0
        for x in range(w):
            if not ink(x, y) and (x, y) not in seen:
                m |= 1 << (w - 1 - x)
        out.append(m)
    return out


def row_nibbles(peek, cmap):
    """{graphics row address: 8 bytes (16 nibbles, left pixel = high nibble)} for every frame row,
    upper-body row and ball row, and {address: (ink bits, fill bits)} (the verify model).
    Ink: the colour map's nibble, else STRIP (frame rows 0-19, upper bodies) / SOCKS (frame rows
    20-27) / white (ball); enclosed paper (players only): the colour map's nibble, else pitch green;
    a pixel painted transparent: 0."""
    nib, bits = {}, {}

    def emit(a, rows, dflt_of, fill):
        fm = enclosed_mask(rows) if fill else [0] * len(rows)
        for r, (v, f) in enumerate(zip(rows, fm)):
            ra = a + 2 * r
            out = []
            inkb = fillb = 0
            for x in range(16):
                ga = ra + x // 8
                bit = x % 8
                e = cmap.get(key(ga))
                if e is not None and e[0] != peek(ga):
                    e = None                      # graphics changed at that address: defaults
                n = e[2][bit] if e else 0
                clr = e is not None and len(e) > 3 and e[3] & (0x80 >> bit)
                ink = v >> (15 - x) & 1
                fl = f >> (15 - x) & 1
                if clr:
                    c = 0
                elif ink:
                    c = n or dflt_of(r)
                elif fl or n:
                    c = n or GREEN
                else:
                    c = 0
                out.append(c)
                if c and ink:
                    inkb |= 1 << (15 - x)
                elif c:
                    fillb |= 1 << (15 - x)
            nib[ra] = bytes(out[i] << 4 | out[i + 1] for i in range(0, 16, 2))
            bits[ra] = (inkb, fillb)

    rd = lambda a, n: [peek(a + 2 * r) << 8 | peek(a + 2 * r + 1) for r in range(n)]
    for f in range(FRAMES):
        emit(FRAME_TAB + 56 * f, rd(FRAME_TAB + 56 * f, 28), lambda r: SOCKS if r >= FILL_ROWS_SOCKS else STRIP, True)
    for u in range(UPPERS):
        emit(UPPER_TAB + 36 * u, rd(UPPER_TAB + 36 * u, 18), lambda r: STRIP, True)
    for a in range(BALL0, BALLEND, 2):
        emit(a, rd(a, 1), lambda r: WHITE, False)
    return nib, bits


def table_banks(peek, cmap, state_init):
    """Row tables -> {bank: 16K}: bank 13 = state page (initial records) + ball rows at 0x1000;
    banks 14-15 = frame / upper rows at (src - 0xC460) * 4."""
    nib, _ = row_nibbles(peek, cmap)
    st = bytearray(state_init) + bytes(16384 - len(state_init))
    for a in range(BALL0, BALLEND, 2):
        o = BALLTAB_OFF + (a - BALL0) * 4
        st[o:o + 8] = nib[a]
    t = bytearray(32768)
    for a in range(FRAME_TAB, FRAMEEND, 2):
        o = (a - FRAME_TAB) * 4
        t[o:o + 8] = nib[a]
    return {STATE_BANK: bytes(st), NIB_BANKS[0]: bytes(t[:16384]), NIB_BANKS[1]: bytes(t[16384:])}


def state_init():
    """Initial state page: every record F_SLOT = own slot (figures k, ball 34), F_NEW = 0xFF; the
    last-built images (0x1100, 17 x 96) 0xFF = none (the first draw always uploads)."""
    s = bytearray(0x1800)
    for k in range(NFIG + 2):
        r = 16 * k
        s[r + F_SLOT] = k if k < NFIG else 34
        s[r + F_NEW] = 0xFF
    s[0x1100:0x1100 + 17 * 96] = b'\xff' * (17 * 96)
    return bytes(s)


class MatchDayPatch:
    name = 'Match Day: players, ball and shadow -> hardware sprites (altrom, XOR writes removed)'

    def __init__(self, prof=None, colours=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True          # the game reads 0x5B00-0x5B72
        self.tail_addr = None
        self.max_tail = None
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3BFF:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.cmap = load_colours() if colours is None else colours
        self.sites = []
        for a, (old, sym, op) in SITES.items():
            self.sites.append((a, bytes.fromhex(old), bytes([op]) + self.syms[sym].to_bytes(2, 'little')))
        for a in SCREEN_NOPS:
            self.sites.append((a, bytes([NOP_ORIG[a]]), b'\x00'))
        self.extra_banks = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Match Day patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        peek = lambda a: ram[a - 0x4000]
        self.extra_banks = table_banks(peek, self.cmap, state_init())
        self.extra_banks[12] = self.page + bytes(8192)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


# =============================================================================================
# Verify: original vs patched from one state at every hook event; sprites vs each figure's own
# XOR footprint on the original screen (exact by linearity: the footprints XOR to the shadow)
# =============================================================================================
EV_SITES = {PLOT: 'obj', 0x8DEC: 'bd', 0x8D63: 'clr', 0x9D15: 'ball', 0x817F: 'frame', 0xE62C: 'cls', 0x819D: 'exit'}
ALLOWED_NR = {0x07, 0x53, 0x56, 0x40, 0x41, 0x43, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39}
HSTACK = (0x5BA8, 0x5C00)             # hook stack: printer buffer bytes the game never touches
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR
SHADOW_CALL_RET = 0xA02A              # 0xA046 called for the shadow (the ball falls through)
DEAD = 64


class NextState:
    def __init__(s, banks):
        s.nr = {0x53: 11, 0x56: 0, 0x07: 0, 0x43: 0}
        s.pages = {}
        for b in (STATE_BANK,) + NIB_BANKS:
            d = banks[b]
            s.pages[2 * b], s.pages[2 * b + 1] = bytearray(d[:8192]), bytearray(d[8192:])
        s.pat = bytearray(16384)
        s.pat_i = 0
        s.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        s.pal = [0] * 256
        s.pal_i = 0
        s.events = []

    def clone(s):
        import copy
        return copy.deepcopy(s)

    def nextreg(s, reg, val):
        s.events.append(('nr', reg, val))
        s.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            s.attr[s.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x40:
            s.pal_i = val
        elif reg == 0x41:
            s.pal[s.pal_i & 255] = val
            if not s.nr.get(0x43, 0) & 0x80:
                s.pal_i = (s.pal_i + 1) & 255

    def out(s, port, v):
        if port == 0x303B:
            s.pat_i = ((v & 0x3F) << 8) | (128 if v & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            s.pat[s.pat_i] = v
            s.pat_i = (s.pat_i + 1) & 0x3FFF
        else:
            s.events.append(('out', port, v))

    def page_of(s, a):
        if 0x6000 <= a < 0x8000:
            p = s.nr[0x53]
            if p != 11:
                return s.pages.get(p), a - 0x6000, p
        if 0xC000 <= a < 0xE000:
            p = s.nr[0x56]
            if p != 0:
                return s.pages.get(p), a - 0xC000, p
        return None, 0, None

    def st(s, a):
        return s.pages[STATE_PG][a - 0xC000]

    def st16(s, a):
        return s.st(a) | s.st(a + 1) << 8

    def visible(s):
        return [i for i in range(128) if s.attr[i][3] & 0x80]


def _sx(v):
    return v - 65536 if v & 0x8000 else v


class _Ov:
    """Original-run memory: overlay over the live 64K (get), writes recorded with their PC."""

    def __init__(s, get):
        s.get, s.ov, s.w = get, {}, []
        s.R = None

    def __getitem__(s, a):
        v = s.ov.get(a)
        return s.get(a) if v is None else v

    def __setitem__(s, a, v):
        if a >= 0x4000:
            pc = s.R[24] if s.R else 0
            top = None
            if BALL_XOR[0] <= pc < BALL_XOR[1]:
                sp = s.R[12]
                top = s[sp] | s[(sp + 1) & 0xFFFF] << 8
            s.w.append((a, v, pc, top))
            s.ov[a] = v

    def __len__(s):
        return 65536


class _Pv(_Ov):
    """Patched-run memory: alt ROM below 0x4000, Next pages at slots 3 / 6 when mapped."""

    def __init__(s, get, alt, psite, ns):
        _Ov.__init__(s, get)
        s.alt, s.psite, s.ns, s.romw, s.pagew = alt, psite, ns, 0, []

    def __getitem__(s, a):
        if a < 0x4000:
            return s.alt[a]
        pg, o, n = s.ns.page_of(a)
        if pg is not None:
            return pg[o]
        if n is not None:
            return 0xFF
        v = s.ov.get(a)
        if v is not None:
            return v
        v = s.psite.get(a)
        return s.get(a) if v is None else v

    def __setitem__(s, a, v):
        if a < 0x4000:
            s.romw += 1
            return
        pg, o, n = s.ns.page_of(a)
        if pg is not None:
            if n != STATE_PG:
                s.pagew.append(a)
            pg[o] = v
            return
        s.w.append((a, v, s.R[24] if s.R else 0, None))
        s.ov[a] = v


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _machine(mem, regs, ns, slot):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(_rw(), mem, regs, slot)
    R, ed = sim.registers, sim.after_ED
    mem.R = R

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]
        R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]
        R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s_, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s_, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=400000, each=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        if each is not None:
            each(R)
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


def _stopper(kind, get, R):
    sp0 = R[12]
    w = lambda a: get(a) | get(a + 1) << 8
    if kind in ('obj', 'ball', 'frame', 'cls'):
        if kind == 'obj':
            ret, end = w(sp0), sp0 + 2             # 0x8B45 entered by CALL or JP: return of its caller
        else:
            ret, end = R[24] + 3, sp0              # the patched CALL instruction completes
        return lambda r: r[24] == ret and r[12] == end
    if kind == 'bd':
        return lambda r: r[24] == 0x8DF0
    if kind == 'clr':
        return lambda r: r[24] == 0x8D67
    return lambda r: r[24] == 0x81A0             # exit


class Model:
    """The verifier's own record of every figure's footprint on the original screen."""

    def __init__(s):
        s.fp = {}                 # identity -> {addr: bits}
        s.dirty = set()           # footprints an overwriter cut into (the original shows debris)
        s.edge = set()            # footprints drawn by the original's edge dispatch (debris)
        s.img = {}                # figure -> the image the game built for it (screen pixels)

    def xor(s, who, a, d):
        fp = s.fp.setdefault(who, {})
        v = fp.get(a, 0) ^ d
        if v:
            fp[a] = v
        else:
            fp.pop(a, None)
        if not fp:
            s.dirty.discard(who)
            s.edge.discard(who)

    def overwrite(s, a):
        for who, fp in s.fp.items():
            if fp.pop(a, None) is not None:
                s.dirty.add(who)

    def pixels(s, who):
        return set(footprint_pixels(s.fp.get(who, {})))


def figk_of(get, ix):
    v = get(ix + 0x14) | get(ix + 0x15) << 8
    d = v - BUFBASE
    if d < 0 or d // 192 >= NFIG:
        return None
    return d // 192


BUFBASE = 0xB736


def image_ink(ns, get, rec, slot_field):
    """The image a record's pattern slot shows: (x, y) of its ink pixels, from the row addresses
    the hook claims (ROWSRC as uploaded is not kept: the pattern bytes are decoded against the
    game's own graphics bytes). Returns (ink set, fill set, problems)."""
    st = ns.pages[STATE_PG]
    slot = st[rec + slot_field]
    x = _sx(st[rec + 1] | st[rec + 2] << 8)
    yt = _sx(st[rec + 3] | st[rec + 4] << 8)
    n = st[rec + 7]
    return slot, x, yt, n


def decode_slot(ns, slot, rows=32, half=None):
    """256-byte pattern slot -> {(col, row): nibble} for the rows (two 16-row 4-bit patterns)."""
    out = {}
    base = slot * 256 + (128 if half == 1 else 0)
    for r in range(rows):
        for c in range(16):
            b = ns.pat[base + r * 8 + c // 2]
            v = (b >> 4) if c % 2 == 0 else (b & 15)
            if v:
                out[(c, r)] = v
    return out


def ink_of_slot(ns, slot, x, yt, bitsmap, rowsrc, half=None, nrows=32, rowsh=None):
    """Pattern pixels split by the source rows' ink bits (a row shifted by rowsh pixels relative to
    the image): -> (ink {(x,y)}, fill {(x,y)}, pixels not from the row table)."""
    dec = decode_slot(ns, slot, nrows, half)
    ink, fill, bad = set(), set(), 0
    for (c, r), v in dec.items():
        src = rowsrc[r] if r < len(rowsrc) else 0
        ib, fb = bitsmap.get(src, (0, 0))
        cs = c - (rowsh[r] if rowsh else 0)
        if not 0 <= cs < 16:
            bad += 1
            continue
        m = 1 << (15 - cs)
        p = (x + c, yt + r)
        if ib & m:
            ink.add(p)
        elif fb & m:
            fill.add(p)
        else:
            bad += 1
    return ink, fill, bad


def on_screen(px):
    return {(x, y) for x, y in px if 0 <= x < 256 and 0 <= y < 192}


class Verifier:
    """One replay: the original game runs; at every hook site the event runs original and patched
    from the same state (patched with the persistent Next state), then the checks."""

    def __init__(s, patch, bits=None):
        s.patch = patch
        s.alt = _alt(patch)
        s.psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
        s.ns = NextState(patch.extra_banks)
        s.model = Model()
        s.bits = bits
        s.rows = {}                 # pattern slot -> row addresses it was built from
        s.c = collections.Counter()
        s.ex = collections.defaultdict(list)
        s.frame = 0

    def fail(s, k, info=()):
        s.c[k + '!'] += 1
        if len(s.ex[k]) < 5:
            s.ex[k].append((s.frame,) + tuple(info))

    def note(s, k, n=1):
        s.c[k] += n

    # ---- the per-instruction interrupt-safety check of the patched run ----
    def _safety(s, R0):
        ns = s.ns
        ix, iy, i0, iff = R0[8:12], None, R0[14], R0[26]
        regs0 = tuple(R0[8:12])

        def each(R):
            if R[24] < 0x4000 or R[24] >= 0x2000 and False:
                pass
            if 0x2000 <= R[24] < 0x4000:
                if tuple(R[8:12]) != regs0 or R[14] != i0 or R[26] != iff:
                    s.fail('interrupt safety: IX / IY / I / IFF changed inside a hook', (hex(R[24]),))
                sp = R[12]
                if HSTACK[0] <= sp <= HSTACK[1]:
                    if sp - 26 < HSTACK[0]:
                        s.fail('interrupt safety: hook stack has < 26 free bytes', (hex(R[24]), hex(sp)))
                elif 0xC000 <= sp < 0xE000 and ns.nr[0x56] != 0:
                    s.fail('interrupt safety: stack in slot 6 while a Next page is mapped', (hex(R[24]),))
                if ns.nr[0x53] != 11:
                    s.fail('interrupt safety: slot 3 changed (the IM 2 handler reads 0x67xx there)', (hex(R[24]),))
                if ns.nr[0x56] not in (0, STATE_PG) + tuple(range(NIB_PG, NIB_PG + 4)):
                    s.fail('interrupt safety: unexpected page in slot 6', (hex(R[24]),))
        return each

    def event(s, kind, get, R):
        stop = _stopper(kind, get, R)
        o = _Ov(get)
        p = _Pv(get, s.alt, s.psite, s.ns)
        so = _machine(o, list(R), _Dummy(), 'o')
        s.ns.events = []
        sp_ = _machine(p, list(R), s.ns, 'p')
        s.at_draw = None

        def grab(r):
            if r[24] == 0x8ECE and s.at_draw is None:
                s.at_draw = list(r)
                s.flag93a2 = o[0x93A2]
        if not _run(so, stop, each=grab if kind == 'obj' else None):
            s.fail('%s: original did not return' % kind)
            return None
        if not _run(sp_, stop, each=s._safety(list(R))):
            s.fail('%s: patched did not return' % kind)
            return None
        ro, rp = so.registers, sp_.registers
        s.c['T %s original' % kind] += ro[25] - R[25]
        s.c['T %s patched' % kind] += rp[25] - R[25]
        diff = [i for i in CMP if ro[i] != rp[i]]
        if diff:
            s.fail('%s: registers differ' % kind, (diff, [ro[i] for i in diff], [rp[i] for i in diff]))
        if p.romw:
            s.fail('%s: patched code wrote ROM' % kind)
        if p.pagew:
            s.fail('%s: patched code wrote a row-table page' % kind)
        evs = s.ns.events
        if any(e[0] in ('in', 'out') for e in evs):
            s.fail('%s: port access other than the sprite pattern ports' % kind, (evs[:2],))
        if any(e[0] == 'nr' and e[1] not in ALLOWED_NR for e in evs):
            s.fail('%s: NEXTREG outside the allowed set' % kind)
        if kind not in ('frame', 'cls', 'exit') and any(e[0] == 'nr' and 0x34 <= e[1] <= 0x39 for e in evs):
            s.fail('%s: sprite attributes written outside e_frame / e_cls / e_exit' % kind)
        if s.ns.nr[0x53] != 11 or s.ns.nr[0x56] != 0 or s.ns.nr[0x07] != 0:
            s.fail('%s: hook left a page mapped / the speed up' % kind)
        dead = range(ro[12] - DEAD, ro[12])
        keys = set(o.ov) | set(p.ov)
        md = [a for a in keys if not 0x4000 <= a < 0x5B00 and a not in dead and o[a] != p[a]
              and not HSTACK[0] <= a < HSTACK[1]]
        if md:
            s.fail('%s: game memory differs' % kind, (len(md), [hex(a) for a in sorted(md)[:4]]))
        # screen: every write the patched run makes equals the original's; the original's other
        # screen writes are exactly the removed figure writes (NOP sites)
        pw = {w[0] for w in p.w if 0x4000 <= w[0] < 0x5B00}
        if any(o[a] != p[a] for a in pw):
            s.fail('%s: a screen write differs from the original' % kind)
        nop = set(SCREEN_NOPS)
        if any(0x4000 <= a < 0x5B00 and a not in pw and pc not in nop for a, v, pc, top in o.w):
            s.fail('%s: the original wrote the screen where the patched game did not' % kind)
        return o, p, ro

    def screen_writes(s, kind, o, get, R):
        """Apply the original's screen writes to the model. Figure XOR writes -> the figure's
        footprint; anything else on the screen in an event is unexpected."""
        cur = {}
        who = None
        if kind == 'obj':
            k = figk_of(get, R[8] << 8 | R[9])
            who = k
        for a, v, pc, top in o.w:
            if not 0x4000 <= a < 0x5B00:
                continue
            old = cur.get(a, get(a))
            cur[a] = v
            if a >= 0x5800:
                continue                  # attributes: the figure paints are removed, others run in both
            if FIG_XOR[0] <= pc < FIG_XOR[1]:
                if who is None:
                    s.fail('obj: figure drawn by an object that is no figure (no sprite)', (hex(pc),))
                    continue
                s.model.xor(who, a, old ^ v)
            elif BALL_XOR[0] <= pc < BALL_XOR[1]:
                s.model.xor('shadow' if top == SHADOW_CALL_RET else 'ball', a, old ^ v)
            elif not any(lo <= pc < hi for lo, hi in SCENERY_XOR):
                s.model.overwrite(a)      # crowd, clears, text: the original byte is the written value

    # ---- the checks ----
    def intended(s, o, R8, jforce=None):
        """The new image as the game built it: B rows of 3 buffer bytes ending at HL (bottom row,
        rightmost drawn byte), placed with its rightmost drawn byte at the screen address DE. The
        rightmost drawn buffer column j is 2 unless the figure is cut by the right edge (column 31:
        j = visible columns - 1). -> screen pixels."""
        hl, de, b = R8[6] << 8 | R8[7], R8[4] << 8 | R8[5], R8[2]
        col, yb = scr_xy(de)
        ix = R8[8] << 8 | R8[9]
        vis = o[ix + 2]
        j = vis - 1 if (col == 31 and vis < 3) else 2
        if jforce is not None:
            j = jforce
        px = set()
        for r in range(b):
            for c in range(3):
                v = o[(hl - 3 * r - (j - c)) & 0xFFFF]
                sc = col - (j - c)
                for bit in range(8):
                    if v >> (7 - bit) & 1:
                        px.add((sc * 8 + bit, yb - r))
        return on_screen(px)

    def check_obj(s, get, R, o):
        k = figk_of(get, R[8] << 8 | R[9])
        if k is None:
            return
        st = s.ns.pages[STATE_PG]
        vis = st[16 * k]
        ix = R[8] << 8 | R[9]
        newv = o[ix + 2]
        oldv = (o[0x93AC] - newv) & 0xFF
        if oldv != newv and min(oldv, newv) < 3:
            s.model.edge.add(k)           # the original dispatches its XOR loop on old + new columns
        want = s.intended(o, s.at_draw) if (s.at_draw is not None and newv) else set()
        s.model.img[k] = want
        fpx = on_screen(s.model.pixels(k))
        if fpx != want and s.at_draw is not None and s.flag93a2:
            col = scr_xy(s.at_draw[4] << 8 | s.at_draw[5])[0]
            if fpx == {q for q in want if q[0] >> 3 != col}:
                s.model.edge.add(k)       # debris from now on: the erase will not match either
                s.note('obj: original drops the image\'s third column (0x93A2 set by the shift-0 rebuild of the old image)')
                fpx = want
        if fpx != want:
            if k in s.model.dirty:
                s.note('obj: original screen has overwriter debris')
            elif k in s.model.edge:
                s.note('obj: original screen has edge-dispatch debris (the game XORs old + new columns by their sum)')
            else:
                s.fail('obj: the original screen differs from the image the game built', (k, len(fpx ^ want)))
        if not vis:
            if want:
                s.fail('obj: the game drew the figure but it is hidden', (k, len(want)))
            else:
                s.note('obj: hidden (nothing on screen)')
            return
        slot = st[16 * k + F_NEW]
        if slot == 0xFF:                  # the image is unchanged: the pattern on show
            slot = st[16 * k + F_SLOT]
            s.note('obj: image unchanged (no upload)')
        n = st[16 * k + 7]
        rows = [st[0x780 + 2 * r] | st[0x781 + 2 * r] << 8 for r in range(n)]
        sh = [(st[0x7C0 + r] ^ 0x80) - 0x80 for r in range(n)]
        s.rows[slot] = (rows, sh)
        x = _sx(st[16 * k + 1] | st[16 * k + 2] << 8)
        yt = _sx(st[16 * k + 3] | st[16 * k + 4] << 8)
        ink, fill, bad = ink_of_slot(s.ns, slot, x, yt, s.bits, rows, rowsh=sh)
        if any(sh):
            s.note('obj: rows of another shift in one image (stale build rows)')
        if bad:
            s.fail('obj: pattern nibbles not from the row table', (k, bad))
        got = on_screen(ink)
        if got != want:
            # the original culls a column at the right edge (its column count says 2 while a shifted
            # image spans 3): the sprite shows the whole built image (3 buffer columns) instead
            full = s.intended(o, s.at_draw, st[0x6F6])
            col = scr_xy(s.at_draw[4] << 8 | s.at_draw[5])[0]
            drawn_cols = set(range(col - o[ix + 2] + 1, col + 1))
            if got == full and want <= full and all((q[0] >> 3) not in drawn_cols for q in full - want):
                s.note('obj: sprite shows the image column the original culls at the screen edge')
                s.model.img[k] = full
            else:
                s.fail('obj: sprite ink differs from the image the game built', (k, len(got ^ want), x, yt, n))
        else:
            s.note('obj: sprite pixels compared', len(want))
            s.note('obj: fill pixels', len(fill))

    def check_ball(s):
        st = s.ns.pages[STATE_PG]
        slot = st[16 * NFIG + F_NEW]
        rows = [st[0x780 + 2 * r] | st[0x781 + 2 * r] << 8 for r in range(32)]
        if slot != 0xFF:
            s.rows[slot] = (rows, None)
        for who, rec, half, nr in (('ball', 16 * NFIG, 0, 5), ('shadow', 16 * NFIG + 16, 1, 1)):
            px = on_screen(s.model.pixels(who))
            vis = st[rec]
            if not vis:
                if px:
                    s.fail('ball: %s on screen but hidden' % who, (len(px),))
                continue
            x = _sx(st[rec + 1] | st[rec + 2] << 8)
            yt = _sx(st[rec + 3] | st[rec + 4] << 8)
            ink, fill, bad = ink_of_slot(s.ns, slot, x, yt, s.bits, rows[16 * half:16 * half + 16], half, 16)
            if bad or fill:
                s.fail('ball: pattern nibbles not from the row table', (who, bad, len(fill)))
            if on_screen(ink) != px:
                if who in s.model.dirty:
                    s.note('ball: differs where an overwriter cut the original (debris)')
                else:
                    s.fail('ball: %s sprite differs from the original plot' % who, (len(on_screen(ink) ^ px), x, yt))
            else:
                s.note('ball: sprite pixels compared', len(px))

    def check_frame(s):
        """After e_frame: exactly the visible records as sprites, in depth order, each showing the
        figure's footprint (the dive's spare half at the keeper half's camera position)."""
        st = s.ns.pages[STATE_PG]
        want = []
        for k in range(NFIG + 2):
            r = 16 * k
            if not st[r]:
                continue
            if k == NFIG + 1:
                slot = st[16 * NFIG + F_SLOT]
                pats, key = [2 * slot + 1], -1
            elif k == NFIG:
                slot = st[r + F_SLOT]
                pats = [2 * slot]
                key = st[16 * NFIG + 16 + F_YB] if st[16 * NFIG + 16] else st[r + F_YB]
            else:
                slot = st[r + F_SLOT]
                pats = [2 * slot] + ([2 * slot + 1] if st[r + 7] > 16 else [])
                key = st[r + F_YB]
            xs = _sx(st[r + F_XS] | st[r + F_XS + 1] << 8)
            yt = _sx(st[r + 3] | st[r + 4] << 8)
            want.append((key, k, [(p, xs + 32, yt + 32 + 16 * i) for i, p in enumerate(pats)]))
        shown = []
        for i in s.ns.visible():
            a = s.ns.attr[i]
            pat = ((a[3] & 0x3F) << 1) | (a[4] >> 6 & 1)
            shown.append((i, pat, a[0] | (a[2] & 1) << 8, a[1] | (a[4] & 1) << 8))
        exp = {(p, x & 0x1FF, y & 0x1FF) for _, _, sp in want for p, x, y in sp}
        got = {(p, x, y) for _, p, x, y in shown}
        if exp != got:
            s.fail('frame: sprites shown differ from the figure records', (sorted(exp ^ got)[:4],))
        order = {}
        for i, p, x, y in shown:
            order.setdefault(p, i)
        keys = []
        for key, k, sp in want:
            if sp[0][0] in order:
                keys.append((order[sp[0][0]], key))
        keys.sort()
        if any(keys[j][1] > keys[j + 1][1] for j in range(len(keys) - 1)):
            s.fail('frame: depth order (bottom y) not kept')
        # each shown image = the figure's footprint
        for k in range(NFIG):
            r = 16 * k
            px = s.model.img.get(k, set())
            if not st[r]:
                if px:
                    s.fail('frame: figure on the original screen but no sprite', (k, len(px)))
                continue
            slot = st[r + F_SLOT]
            x, xs = _sx(st[r + 1] | st[r + 2] << 8), _sx(st[r + F_XS] | st[r + F_XS + 1] << 8)
            yt = _sx(st[r + 3] | st[r + 4] << 8)
            rr, sh = s.rows.get(slot, ([], None))
            ink, fill, bad = ink_of_slot(s.ns, slot, x, yt, s.bits, rr, rowsh=sh)
            if on_screen(ink) != px:
                s.fail('frame: shown image differs from the figure', (k, len(on_screen(ink) ^ px)))
            elif xs != x:
                s.note('frame: dive spare half locked (%+d px)' % (xs - x))
            else:
                s.note('frame: figures compared')

    def check_hidden(s, kind):
        if s.ns.visible():
            s.fail('%s: sprites still visible' % kind, (len(s.ns.visible()),))


class _Dummy:
    def nextreg(s, *a):
        pass

    def out(s, *a):
        pass

    events = []


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay one RZX (original game); every hook event checked (Verifier). Returns (Counter,
    examples, states): states = up to `collect` captured 'obj' events (registers, 64K, footprints,
    Next state) for the unit tests."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    _, bits = row_nibbles(lambda a: 0, {}) if False else (None, None)
    v = Verifier(patch)
    st = {'busy': None, 'on': False}
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    interiors = {a + k for a, old, new in patch.sites if len(new) == 3 for k in (1, 2)} | {0x8D66}
    states = []
    scen = SCENERY_XOR

    class Mem(list):
        def __setitem__(s_, a, val):
            if st['on'] and type(a) is int:
                if a in site_bytes:
                    v.fail('game wrote a patch site', (hex(a),))
                if HSTACK[0] <= a < HSTACK[1]:
                    v.fail('game wrote the hook stack (printer buffer 0x5BA8-0x5BFF)', (hex(a),))
                if 0x4000 <= a < 0x5800 and st['busy'] is None:
                    pc = st['R'][24]
                    if not any(lo <= pc < hi for lo, hi in scen):
                        v.model.overwrite(a)
            S(s_, a, val)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            st['R'], st['on'] = R, True
            get = lambda a: G(mem, a)
            if v.bits is None:
                v.bits = row_nibbles(get, patch.cmap)[1]

            def mk(fn):
                def g():
                    pc = R[24]
                    b = st['busy']
                    if b is not None and pc == b[0] and R[12] == b[1]:
                        st['busy'] = b = None
                    prev, st['prev'] = st.get('prev'), pc
                    if b is None:
                        if pc in interiors and not (prev is not None and 0 < pc - prev <= 2 and prev in EV_SITES):
                            v.fail('jump into a patched instruction', (hex(pc),))
                        kind = EV_SITES.get(pc)
                        if kind:
                            if kind == 'obj' and collect and v.c['collected'] < collect and v.c['obj'] % 97 == 5:
                                v.c['collected'] += 1
                                states.append((list(R), bytes(G(mem, a) for a in range(65536)),
                                               {k: dict(f) for k, f in v.model.fp.items()}, set(v.model.dirty),
                                               v.ns.clone(), dict(v.rows)))
                            run_event(v, kind, get, R)
                            if kind in ('obj', 'ball', 'frame', 'cls'):
                                w = G(mem, R[12]) | G(mem, R[12] + 1) << 8
                                st['busy'] = (w, R[12] + 2) if kind == 'obj' else (pc + 3, R[12])
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        v.frame += 1
        if progress and v.frame % 1000 == 0:
            progress(v.frame, v.c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = Sm
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    v.c['frames'] = v.frame
    return v.c, dict(v.ex), states


def run_event(v, kind, get, R):
    """One event: the pair run + the checks for its kind."""
    v.c[kind] += 1
    res = v.event(kind, get, R)
    if res is None:
        return None
    o, p, ro = res
    v.screen_writes(kind, o, get, R)
    if kind == 'obj':
        v.check_obj(get, R, o)
    elif kind == 'ball':
        v.check_ball()
    elif kind == 'frame':
        v.check_frame()
    elif kind in ('cls', 'exit'):
        v.check_hidden(kind)
        v.model.img = {}                  # every figure forgotten (the hooks hid them all)
        v.model.dirty |= set(v.model.fp)  # what the original leaves on screen is not a figure now
    return res


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : matchday (Match Day: players 0x8B45, ball 0x9FCF -> sprites; XOR screen writes removed)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, None, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], conv[1]))
    patch = MatchDayPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (tail 0x%04X; colours: %d map entries)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200], conv[1],
        len(patch.cmap)))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1, os.path.basename(s2)))
            r = s2
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=40)
        states += st
        fails = {k: n for k, n in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, objects %d, builds %d, ball %d, frames %d, clears %d, exits %d, '
            '%d sprite pixels -> %s' % (os.path.basename(r), c['frames'], c['obj'], c['bd'], c['ball'], c['frame'],
                                        c['cls'], c['exit'],
                                        c['obj: sprite pixels compared'] + c['ball: sprite pixels compared'],
                                        'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, n in sorted(c.items()):
            if not k.endswith('!') and ':' in k:
                say('            %s: %d' % (k, n))
        if c['frames']:
            extra = sum(c['T %s patched' % k] - c['T %s original' % k] for k in EV_SITES.values())
            say('Speed     : hooks add %d T per game frame at 3.5 MHz rates (%d T total); they run at 28 MHz '
                '(NextReg 7 = 3): about %d T of a 69,888 T frame' % (extra // c['frames'], extra, extra // c['frames'] // 6))
        for k, e in ex.items():
            say('            %s: %s' % (k, str(e)[:240]))
    if states:
        neg, negsafe = negative_patches(patch)
        u = unit_tests(patch, states, neg, negsafe)
        uf = {k: n for k, n in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d cases, %d states -> %s' % (sum(n for k, n in u.items() if k.endswith(' ok')), len(states),
                                                       'PASS' if not uf else 'FAIL %s' % uf))
        for k, n in sorted(u.items()):
            say('            %s: %d' % (k, n))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# =============================================================================================
# Unit tests: every frame / upper body, edge positions, guards, full tables, negative controls
# =============================================================================================
def _case(patch, state, edit=None, ns_edit=None):
    """One 0x8B45 event from a captured state, with edits to its memory (IX fields) / Next state.
    -> (failures, counter)."""
    R, mem, fp, dirty, ns, rows = state
    m = bytearray(mem)
    ix = R[8] << 8 | R[9]
    if edit:
        edit(m, ix)
    v = Verifier.__new__(Verifier)
    v.patch, v.alt = patch, _alt(patch)
    v.psite = {a + k: b for a, old, new in patch.sites for k, b in enumerate(new)}
    v.ns = ns.clone()
    if ns_edit:
        ns_edit(v.ns)
    v.model = Model()
    v.model.fp = {k: dict(f) for k, f in fp.items()}
    v.model.dirty = set(dirty)
    v.bits = row_nibbles(lambda a: m[a], patch.cmap)[1]
    v.rows = dict(rows)
    v.c = collections.Counter()
    v.ex = collections.defaultdict(list)
    v.frame = 0
    res = run_event(v, 'obj', lambda a: m[a], list(R))
    fl = {k: n for k, n in v.c.items() if k.endswith('!')}
    if res is not None:
        o = res[0]
        for a, val in o.ov.items():
            m[a] = val
    after = (list(R), bytes(m), {k: dict(f) for k, f in v.model.fp.items()}, set(v.model.dirty), v.ns, dict(v.rows))
    return fl, v.c, after


def unit_tests(patch, states, neg=None, negsafe=None):
    c = collections.Counter()
    sts = [st for st in states]
    if not sts:
        c['no captured object state!'] += 1
        return c

    def w16(m, a, v):
        m[a], m[a + 1] = v & 255, v >> 8 & 255

    def run(name, st, edit=None, ns_edit=None, expect_ok=True):
        f, cc, _ = _case(patch, st, edit, ns_edit)
        ok = not f if expect_ok else bool(f)
        c['%s %s' % (name, 'ok' if ok else 'FAIL!')] += 1
        if not ok and c['  examples'] < 6:
            c['  examples'] += 1
            c['  %s: %s' % (name, str(f)[:160])] += 1
        return cc

    # a mid-pitch state of a visible figure to vary
    base = None
    for st in sts:
        R, mem = st[0], st[1]
        ix = R[8] << 8 | R[9]
        if figk_of(lambda a: mem[a], ix) is not None and mem[ix + 2] == 3 and 0x30 < mem[ix + 7] < 0x90:
            base = st
            break
    if base is None:
        c['no mid-pitch figure state captured!'] += 1
        return c
    R0, mem0 = base[0], base[1]
    cam = mem0[CAMERA] | mem0[CAMERA + 1] << 8

    def frame_edit(f, upper=None):
        def e(m, ix):
            m[ix + 3] = f
            if upper is None:
                m[ix] &= 0xFE
            else:
                m[ix] |= 1
                m[ix + 0x10] = upper
        return e
    for f in range(FRAMES):
        run('frame %d' % f if f < 0 else 'every frame (0-115)', base, frame_edit(f))
    for u in range(UPPERS):
        run('every upper body (0-17) on frame 10', base, frame_edit(10, u))

    def pos_edit(x, y=None):
        def e(m, ix):
            w16(m, ix + 5, (cam + 8 + x) & 0xFFFF)
            if y is not None:
                m[ix + 7] = y
        return e
    for x in (2, 7, 33, 100, 101, 102, 103, 200, 231, 232):
        run('x positions on screen (shifts 0-6)', base, pos_edit(x))

    def walk(name, xs, ys, frames=(None,), st=None):
        """The figure moves in small steps (as in play), each event from the state the last left."""
        st = st or base
        for i, x in enumerate(xs):
            y = ys[i] if ys else None
            f = frames[i % len(frames)]
            ed = (lambda m, ix, x=x, y=y, f=f: (pos_edit(x, y)(m, ix), f is not None and frame_edit(f)(m, ix)))
            fl, cc, st = _case(patch, st, ed)
            c['%s %s' % (name, 'ok' if not fl else 'FAIL!')] += 1
            c['  (debris of the original\'s edge dispatch in walks)'] += cc['obj: original screen has edge-dispatch debris (the game XORs old + new columns by their sum)']
            if fl and c['  examples'] < 6:
                c['  examples'] += 1
                c['  %s x %d: %s' % (name, x, str(fl)[:160])] += 1
        return st
    e = walk('walk off the left edge (x 40 -> -30)', list(range(40, -31, -2)), None, (0, 1, 2, 3))
    walk('walk back on at the left edge (x -30 -> 20)', list(range(-28, 21, 2)), None, (4, 5, 6, 7), e)
    e = walk('walk off the right edge (x 200 -> 270)', list(range(200, 271, 2)), None, (8, 9, 10, 11))
    walk('walk back on at the right edge (x 270 -> 220)', list(range(268, 219, -2)), None, (12, 13), e)
    e = walk('walk down over the bottom edge (y 0x80 -> 0xC0)', [60] * 33, list(range(0x80, 0xC1, 2)), (14, 15))
    walk('walk back up (y 0xC0 -> 0x90)', [60] * 24, list(range(0xBE, 0x8F, -2)), (14, 15), e)
    e = walk('walk down to the bottom path (y 0x90 -> 0xA8)', [20] * 13, list(range(0x90, 0xA9, 2)), (16, 17))
    walk('bottom-left corner (x 20 -> -24 at y 0xA8)', list(range(18, -25, -2)), [0xA8] * 22, (16, 17), e)
    walk('dive across the left edge (frames 72-93)', list(range(20, -21, -2)), None, tuple(range(72, 94)))

    # guard: an object whose buffers are no figure's -> no sprite, no state change
    def bad_ix(m, ix):
        w16(m, ix + 0x14, 0x9000)
    f, cc, _ = _case(patch, base, bad_ix)
    ok = all('no figure' in k or 'differs from the image' in k or 'hidden' in k for k in f) or not f
    c['guard: object outside the figure table (no sprite) %s' % ('ok' if ok else 'FAIL!')] += 1

    # table full: 16 palette banks in use -> a new strip / socks pair reuses bank 15, pixels still right
    def full(ns):
        st = ns.pages[STATE_PG]
        st[0x6C0] = 16
        for i in range(64):
            st[0x680 + i] = (i % 16) + 1 if i < 16 else 0
    run('palette banks full (16 in use)', base, lambda m, ix: (m.__setitem__(ix + 0x0E, 3), m.__setitem__(ix + 0x0F, 5)), full)

    # every captured state as it is
    for st in sts:
        run('captured states (as recorded)', st)

    if neg is not None:
        f, _, _ = _case(neg, base, lambda m, ix: (frame_edit(12)(m, ix), pos_edit(102)(m, ix)))
        c['negative control (pixels: x shift ignored) %s' % ('detected' if f else 'NOT DETECTED!')] += 1
    if negsafe is not None:
        f, _, _ = _case(negsafe, base)
        hit = any('interrupt safety' in k for k in f)
        c['negative control (interrupt safety: state page at slot 3) %s' % ('detected' if hit else 'NOT DETECTED!')] += 1
    return c


def _rom_variant(patch, old, new, label):
    import copy
    q = copy.copy(patch)
    code = bytearray(patch.rom_code)
    i = code.find(old)
    if i < 0 or code.find(old, i + 1) >= 0:
        raise ValueError('negative control %s: pattern not unique in the hook code' % label)
    code[i:i + len(old)] = new
    q.rom_code = bytes(code)
    page = bytearray(patch.page)
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    q.page = bytes(page)
    q.extra_banks = dict(patch.extra_banks)
    q.extra_banks[12] = q.page + bytes(8192)
    return q


def negative_patches(patch):
    """(pixel control, interrupt-safety control), both from the build's own tables and code:
    1. drawfig ignores the shift: LD A,(V_SH2) -> XOR A / NOP / NOP;
    2. e_bd maps its state page at slot 3 (the IM 2 handler's key table) instead of slot 6."""
    sh2 = patch.syms.get('V_SH2', 0xC6FC)
    neg = _rom_variant(patch, bytes([0x3A, sh2 & 255, sh2 >> 8, 0x5F, 0x16, 0x00]),
                       bytes([0xAF, 0x00, 0x00, 0x5F, 0x16, 0x00]), 'shift')
    sv = 0xC6E0
    # e_bd's ENTERST maps the state page at slot 3 instead of slot 6 (where the IM 2 handler reads
    # the key table): the hook would read / write slot 3 state with interrupts on
    enter = bytes([0xED, 0x91, 0x07, 0x03, 0xED, 0x91, 0x56, STATE_PG, 0xED, 0x73, sv & 255, sv >> 8])
    code = patch.rom_code
    if code[:12] != enter:                  # e_bd is the first routine: its ENTERST
        raise ValueError('negative control enter: e_bd does not start with ENTERST')
    bad = bytes([0xED, 0x91, 0x07, 0x03, 0xED, 0x91, 0x53, STATE_PG]) + code[8:12]
    q = _rom_variant(patch, code[:20], bad + code[12:20], 'enter')
    return neg, q


# =============================================================================================
# Recolour (PLAYBOOK 3b): the colours live only in the row tables (banks 13 ball rows, 14, 15),
# which the game never reads
# =============================================================================================
RECOLOUR = {'game': 'match_day', 'output': 'sprites', 'colours': 'docs/profiles/match_day_colours.json',
            'clear': True, 'note': NOTE}


def recolour(nex, cmap):
    """Built match_day_sprites.nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that
    is not this engine's build of the expected snapshot (patch sites, hook code, set-up code)."""
    from .recolour import nex_offsets, splice
    off = nex_offsets(nex)
    need = {5, 2, 0, 10, 12, STATE_BANK} | set(NIB_BANKS)
    if not need <= set(off):
        raise ValueError('not a Match Day sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(nex[off[b]:off[b] + 16384])
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000] if a >= 0x4000 else 0
    p0 = MatchDayPatch(colours={})
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    sig = load_profile()['signature']
    want = bytes.fromhex(sig['bytes'])
    got = bytes(peek(sig['addr'] + k) for k in range(len(want)))
    if bytes(g if (sig['addr'] + i) not in {a + k for a, o, n in p0.sites for k in range(len(n))} else w
             for i, (g, w) in enumerate(zip(got, want))) != want:
        raise ValueError('unexpected code at 0x%04X - not the expected version of the game' % sig['addr'])
    if bank(12)[:8192] != p0.page:
        raise ValueError('hook code differs from this version\'s (rebuild with nexclash.py auto)')
    if bank(10)[0x1000:0x1000 + len(p0.stub_extra)] != p0.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    out, changed = splice(nex, table_banks(peek, cmap, state_init()))
    return out, {'banks changed': changed, 'entries': len(cmap)}
