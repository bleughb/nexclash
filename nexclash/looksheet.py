"""`python -m nexclash.looksheet BUILD.nex --at F1,F2,.. [--profile P.json]` (or `--jns FILES`, or `--sheet
SHEET.png --layout SHEET_layout.json`) - look sheet with flags.

Every figure the build shows, at 4x, over black and over the game's scenery colours, beside a copy with
the flags marked. Figures come from JNext snapshots of the build at the given frames (the sprite layer as
the Next shows it: nexclash/jnext.py Frame.figures(), an anchor with its relatives and touching sprites
joined), from saved .jns files, or from a colour sheet and its layout (docs/COLOURS.md: each composite's
box). Duplicates are dropped. Scenery colours: --scenery '#RRGGBB,..', else the commonest non-black
colours of the ULA attribute cells in the captured frames.

Flags (Dean's look rules; refactor plan 13, 19, 21):
- CUT: a straight colour boundary longer than 2 px across flat areas: two different colours meet along a
  row or column for 3 or more pixels and each side is flat (the next pixel away from the cut has its
  side's colour), neither side a dark drawn line. Parts should follow the drawn lines, not row bands.
- VANISH: pixels in a colour that disappears against black (contrast ratio to black under 1.6; black
  itself is a drawn line or outline, not counted).
- RIM: a white outline: 50% or more of the figure's outer edge pixels white or near white around an inside
  that is mostly not white (a white figure is not a rim).
Marks on the flag copy (over grey): CUT magenta lines between the pixels, VANISH yellow, RIM cyan.
Writes looksheet.png and looksheet.json (per figure: size, colours, flags) and prints the result block.
Warns, never refuses. docs/CHECKS.md.
"""
import argparse
import hashlib
import json
import os
from . import jnext as J

SCALE = 4
WHITE = 220


def lum(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast_black(c):
    return (lum(c) + 0.05) / 0.05


def dark(c):
    return contrast_black(c) < 1.6


def normal(px):
    x0, y0 = min(x for x, _ in px), min(y for _, y in px)
    return {(x - x0, y - y0): c for (x, y), c in px.items()}


def edge(px):
    return {p for p in px if any((p[0] + dx, p[1] + dy) not in px for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}


def cuts(px):
    """Straight colour boundaries over 2 px between flat areas: [(x0, y0, x1, y1)] in pixel-edge coordinates
    (a horizontal cut lies between rows y-1 and y from x0 to x1)."""
    out = []
    for axis in (0, 1):
        lines = {}
        for (x, y), c in px.items():
            a, b = ((x, y), (x, y + 1)) if axis == 0 else ((x, y), (x + 1, y))
            q = px.get(b)
            if q is None or q == c or dark(c) or dark(q):
                continue
            aa = (x, y - 1) if axis == 0 else (x - 1, y)
            bb = (x, y + 2) if axis == 0 else (x + 2, y)
            if px.get(aa) != c or px.get(bb) != q:          # a 1-px detail, not a flat area
                continue
            key, pos = (y + 1, x) if axis == 0 else (x + 1, y)
            lines.setdefault(key, []).append(pos)
        for k, ps in lines.items():
            ps.sort()
            run = [ps[0]]
            for v in ps[1:] + [None]:
                if v is not None and v == run[-1] + 1:
                    run.append(v)
                    continue
                if len(run) > 2:
                    out.append((run[0], k, run[-1] + 1, k) if axis == 0 else (k, run[0], k, run[-1] + 1))
                if v is not None:
                    run = [v]
    return out


def flags(px):
    e = edge(px)
    van = sorted(p for p, c in px.items() if dark(c) and c != (0, 0, 0))
    white = [p for p in e if min(px[p]) >= WHITE]
    inner = [c for p, c in px.items() if p not in e]
    rim = (len(e) >= 6 and len(white) >= 0.5 * len(e) and len(inner) >= 4 and
           sum(1 for c in inner if min(c) >= WHITE) < 0.3 * len(inner))
    return dict(cuts=cuts(px), vanish=van, rim=rim, rim_px=sorted(white) if rim else [], edge=len(e))


def figures_from_frames(frames):
    out, seen = [], set()
    for fr in frames:
        for g in fr.figures():
            if len(g) < 6:
                continue
            n = normal(g)
            h = hashlib.md5(repr(sorted(n.items())).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                out.append(dict(px=n, src=os.path.basename(fr.path)))
    return out


def figures_from_sheet(png, layout):
    """A colour sheet's composites (docs/COLOURS.md) as figure images: the box's pixels that are neither the
    sheet background nor the transparent grey."""
    from PIL import Image
    from .coloursheet import BG_RGB, TRANSP_RGB
    im = Image.open(png).convert('RGB')
    lay = json.load(open(layout))
    out = []
    for i, c in enumerate(lay['composites']):
        px = {}
        for y in range(c['h']):
            for x in range(c['w']):
                v = im.getpixel((c['x'] + x, c['y'] + y))
                if v != tuple(BG_RGB) and v != tuple(TRANSP_RGB):
                    px[(x, y)] = v
        if px:
            out.append(dict(px=normal(px), src='%s #%d' % (c.get('group'), i)))
    return out


def scenery_colours(frames, n=2):
    """The commonest non-black ULA colours in the attribute cells around the figures (all cells when a
    frame shows none), leaving out the global transparency colour (NR 0x14)."""
    from collections import Counter
    cnt = Counter()
    for fr in frames:
        g = fr.pal.get('global_transparency', 0xE3)
        tr = J.rgb333(g << 1 | (1 if g & 3 else 0))
        cells = set()
        for fig in fr.figures():
            xs = [x - J.PAPER[0] for x, _ in fig]
            ys = [y - J.PAPER[1] for _, y in fig]
            for cy in range(max(0, min(ys) // 8 - 1), min(24, max(ys) // 8 + 2)):
                for cx in range(max(0, min(xs) // 8 - 1), min(32, max(xs) // 8 + 2)):
                    cells.add(cy * 32 + cx)
        for cell in cells or range(768):
            for c in fr.attr_rgb(cell):
                if c != (0, 0, 0) and c != tr:
                    cnt[c] += 1
    return [c for c, _ in cnt.most_common(n)]


def tile(px, w, h, bg, marks=None):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (w * SCALE, h * SCALE), bg)
    d = ImageDraw.Draw(im)
    for (x, y), c in px.items():
        d.rectangle((x * SCALE, y * SCALE, x * SCALE + SCALE - 1, y * SCALE + SCALE - 1), fill=c)
    if marks:
        for (x, y) in marks['vanish']:
            d.rectangle((x * SCALE, y * SCALE, x * SCALE + SCALE - 1, y * SCALE + SCALE - 1), outline=(255, 255, 0))
        for (x, y) in marks['rim_px']:
            d.rectangle((x * SCALE + 1, y * SCALE + 1, x * SCALE + SCALE - 2, y * SCALE + SCALE - 2), outline=(0, 255, 255))
        for x0, y0, x1, y1 in marks['cuts']:
            d.line((x0 * SCALE, y0 * SCALE, x1 * SCALE - (1 if x1 > x0 else 0), y1 * SCALE - (1 if y1 > y0 else 0)),
                   fill=(255, 0, 255), width=2)
    return im


def sheet(figs, backs, out, width=1600):
    from PIL import Image, ImageDraw
    blocks = []
    for i, f in enumerate(figs):
        px = f['px']
        w, h = max(x for x, _ in px) + 1, max(y for _, y in px) + 1
        ts = [tile(px, w, h, b) for b in backs] + [tile(px, w, h, (70, 70, 70), f['flags'])]
        bw = sum(t.width + 4 for t in ts)
        blk = Image.new('RGB', (max(bw, 150), h * SCALE + 14), (30, 30, 30))
        x = 0
        for t in ts:
            blk.paste(t, (x, 12))
            x += t.width + 4
        fl = f['flags']
        txt = '#%d %dx%d%s%s%s' % (i, w, h, ' CUT %d' % len(fl['cuts']) if fl['cuts'] else '',
                                   ' VANISH %d' % len(fl['vanish']) if fl['vanish'] else '', ' RIM' if fl['rim'] else '')
        ImageDraw.Draw(blk).text((1, 0), txt, fill=(255, 255, 0) if len(txt.split()) > 2 else (200, 200, 200))
        blocks.append(blk)
    rows, row, rw = [], [], 0
    for b in blocks:
        if row and rw + b.width + 8 > width:
            rows.append(row)
            row, rw = [], 0
        row.append(b)
        rw += b.width + 8
    if row:
        rows.append(row)
    H = sum(max(b.height for b in r) + 8 for r in rows) or 1
    W = max([sum(b.width + 8 for b in r) for r in rows] or [1])
    im = Image.new('RGB', (W, H), (15, 15, 15))
    y = 0
    for r in rows:
        x = 0
        for b in r:
            im.paste(b, (x, y))
            x += b.width + 8
        y += max(b.height for b in r) + 8
    im.save(out)


def capture(build, prof, at, seed, out, card, home):
    d = os.path.join(out, 'frames')
    os.makedirs(d, exist_ok=True)
    s = J.Script(J.start_frame(build))
    s.start_line(build)
    s.start_keys(prof)
    s.frame_input(J.schedule(prof, max(at) + 2, seed))
    for f in at:
        s.at(f, '  save_snapshot "%s/f%06d.jns"\n  screenshot "%s/f%06d.png"\n' % (d, f, d, f))
    s.exit_at(max(at) + 2)
    J.run_all([(build, s.text(), d, max(at) + 5, card, home)])
    return [os.path.join(d, 'f%06d.jns' % f) for f in at if os.path.exists(os.path.join(d, 'f%06d.jns' % f))]


def hexrgb(v):
    v = v.strip().lstrip('#')
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('build', nargs='?', help='the build (.nex) to capture in JNext (with --at)')
    ap.add_argument('--at', help='frames to capture, e.g. 600,900,1200 (from the program start)')
    ap.add_argument('--profile', help='input profile JSON (nexclash/jnext.py; default generic)')
    ap.add_argument('--jns', nargs='+', help='JNext .jns snapshots instead of a capture')
    ap.add_argument('--sheet', help='a colour sheet PNG (with --layout) instead of a capture')
    ap.add_argument('--layout', help="the colour sheet's _layout.json")
    ap.add_argument('--scenery', help="background colours besides black, e.g. '#00C0C0,#C0C000'")
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--card', help='NextZXOS SD card image (default $NEXCLASH_JNEXT_CARD)')
    ap.add_argument('--jnext-home', help='HOME for JNext (default OUT/.jnext_home)')
    ap.add_argument('-o', '--out', default='looksheet', help='output folder (default ./looksheet)')
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    out = os.path.abspath(a.out)
    frames = []
    if a.sheet:
        base = os.path.splitext(a.sheet)[0]
        lay = a.layout or next((p for p in (base + '_layout.json', base.replace('_painted', '') + '_layout.json')
                                if os.path.exists(p)), base + '_layout.json')
        figs = figures_from_sheet(a.sheet, lay)
        src = os.path.basename(a.sheet)
    else:
        jns = a.jns or capture(a.build, J.load_profile(a.profile), [int(x) for x in a.at.split(',')], a.seed, out,
                               J.card(a.card), a.jnext_home)
        frames = [J.Frame(p) for p in jns]
        figs = figures_from_frames(frames)
        src = '%s (%s), %d snapshots' % (os.path.basename(a.build), J.md5(a.build)[:8], len(jns)) if a.build else '%d snapshots' % len(jns)
    scen = [hexrgb(v) for v in a.scenery.split(',')] if a.scenery else scenery_colours(frames)
    backs = [(0, 0, 0)] + scen
    for f in figs:
        f['flags'] = flags(f['px'])
    sheet(figs, backs, os.path.join(out, 'looksheet.png'))
    nc = sum(1 for f in figs if f['flags']['cuts'])
    nv = sum(1 for f in figs if f['flags']['vanish'])
    nr = sum(1 for f in figs if f['flags']['rim'])
    lines = ['LOOK  %s: %d figures, over black and %s' % (src, len(figs), ', '.join('#%02X%02X%02X' % c for c in scen) or 'no scenery colour'),
             'CUT    (straight colour cut > 2 px across flat areas): %d figures, %d cuts%s' % (
                 nc, sum(len(f['flags']['cuts']) for f in figs), _which(figs, 'cuts')),
             'VANISH (colour lost against black): %d figures, %d pixels%s' % (
                 nv, sum(len(f['flags']['vanish']) for f in figs), _which(figs, 'vanish')),
             'RIM    (white outline): %d figures%s' % (nr, _which(figs, 'rim')),
             'RESULT: %s (warns only); sheet %s' % ('flags on %d of %d figures' % (
                 sum(1 for f in figs if f['flags']['cuts'] or f['flags']['vanish'] or f['flags']['rim']), len(figs))
                 if nc or nv or nr else 'no flag', os.path.join(a.out, 'looksheet.png'))]
    J.result_block(lines, os.path.join(a.out, 'RESULT.txt'))
    json.dump([dict(src=f['src'], w=max(x for x, _ in f['px']) + 1, h=max(y for _, y in f['px']) + 1,
                    colours=sorted({'#%02X%02X%02X' % c for c in f['px'].values()}),
                    cuts=f['flags']['cuts'], vanish=len(f['flags']['vanish']), rim=f['flags']['rim']) for f in figs],
              open(os.path.join(out, 'looksheet.json'), 'w'), indent=1)
    return 0


def _which(figs, k):
    ids = ['#%d' % i for i, f in enumerate(figs) if f['flags'][k]]
    return (' (%s)' % ', '.join(ids[:12]) + (' ...' if len(ids) > 12 else '')) if ids else ''


def selfcheck():
    """Synthetic figures: a box cut in two by a straight row boundary (CUT), the same box split along a
    drawn black line (no CUT), dark blue pixels (VANISH), a white ring (RIM); a black outline and a white
    figure are not flagged."""
    bad = []
    R, G, K, W, B = (200, 0, 0), (0, 200, 0), (0, 0, 0), (255, 255, 255), (0, 0, 120)
    box = {(x, y): R if y < 4 else G for x in range(8) for y in range(8)}
    c = cuts(box)
    if c != [(0, 4, 8, 4)]:
        bad.append(('cut', c))
    lined = {(x, y): R if y < 4 else K if y == 4 else G for x in range(8) for y in range(9)}
    if cuts(lined):
        bad.append(('drawn line cut', cuts(lined)))
    vert = {(x, y): R if x < 3 else G for x in range(6) for y in range(6)}
    if cuts(vert) != [(3, 0, 3, 6)]:
        bad.append(('vertical', cuts(vert)))
    f = flags({(x, y): B for x in range(4) for y in range(4)})
    if len(f['vanish']) != 16 or f['cuts'] or f['rim']:
        bad.append(('vanish', f))
    ring = {(x, y): W if x in (0, 7) or y in (0, 7) else R for x in range(8) for y in range(8)}
    if not flags(ring)['rim'] or flags(box)['rim']:
        bad.append('rim')
    outline = {(x, y): K if x in (0, 7) or y in (0, 7) else R for x in range(8) for y in range(8)}
    if flags(outline)['vanish'] or flags({(x, y): W for x in range(8) for y in range(8)})['rim']:
        bad.append('black outline or white figure flagged')
    return bad


if __name__ == '__main__':
    raise SystemExit(main())
