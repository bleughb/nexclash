"""`python -m nexclash.paint` - the shared painter: an Enhanced colour set that follows the drawing
(refactor plan 19-22; docs/COLOURS.md PAINTER; card verify.paint-follows-drawing). The default first
step for an Enhanced set; block or row colouring only when the author asks for it (Dean, Jon 2026-11-04).

    python -m nexclash.paint regions SHEET_layout.json -o DIR      regions, part guesses, DIR/parts.json
    python -m nexclash.paint paint SHEET_layout.json [--parts DIR/parts.json] [--preset P.json]
                                   [--ref FIGURE=SCREENSHOT.png] [--fill-holes] -o DIR
    python -m nexclash.paint export BUILD.nex [--layout L] -o DIR  every image + palette + index
    python -m nexclash.paint import BUILD.nex EDITED.png [--layout L] [-o OUT_painted.nex]

regions / paint read a colour sheet's layout (docs/COLOURS.md; the REFERENCE layout beside it is used for
whole figures when it exists). `paint` writes DIR/<sheet>_painted.png with a copy of the sheet's layout
(so `python nexclash.py recolour BUILD.nex DIR/<sheet>_painted.png` makes the painted build), the colour
map (<sheet>_paint_colours.json), compare.png (original | regions | parts | painted), paint_report.json
and the look sheet with its flags (DIR/looksheet). `regions` writes regions.png (key frames numbered)
and DIR/parts.json, the labels file the author edits. `export` / `import`: the sprite sheet a painter edits anywhere; import = recolour onto
the build (patterns and palettes only, no recompile), with a warning per image whose silhouette changed.

How a figure is read (all in the figure's own pixels, no rows or boxes):
- classes: ink (code 1), mask (code 2: opaque non-ink), hole (enclosed paper the engine fills, given by
  an adapter: Robin's closed-shape fill; or, with --fill-holes, clear pixels the figure encloses), clear.
  DITHER: pixels in a checkerboard of two of them (a pattern area). The LINE class: of two opaque
  classes the one dark one (Target: Renegade's black ink, Nightshade's black mask), else the thinner;
  one class with holes is the line (Robin's ink). Line pixels in a solid 3x3 mass are a region (black
  hair); a line shape enclosed by one region is a region too (a face drawn solid inside the hood).
- regions: 4-connected areas of one kind (fill, dither, mass, hole) the line pixels close off.
- shape splits: a region is cut only at a NECK (its erosion falls apart: the width drops to 2 or less)
  or where a THIN protrusion leaves it (a limb: what an opening removes, 4+ pixels, 3+ long, touching
  the rest along 3 pixels or less). A split whose boundary is a straight run of 3+ pixels is undone
  (looksheet.cuts), so no colour change crosses a flat area.
- the same part in every frame: regions are matched to the family's key frame (place in the figure,
  share of it, kind, thin, and the overlap when the two figures are laid on each other, direct or
  mirrored, aligned at the top or the bottom); the key frame's labels carry over. A family = the
  figures of a sheet group that share graphics (one character), or the parts file's. Weak matches
  are reported (check them); a region with no match keeps its own guess.
- part guesses (suggestions; the author's labels win): the head is the solid region at the top (one
  with holes preferred), the face a region it encloses, or - when no line closes the face off - a band
  that follows the head's front contour round the drawn features (Robin's profile); thin regions are
  arms (upper) or legs (lower), bottom regions the feet, the largest the body. The family's `facing`
  label (R, L, F, B) fixes which side the face is on; B: no face.
- palette: the figure's original ink is the anchor hue (body; head and legs a shade of it), skin for
  face and arms; a preset {part: '#RRGGBB'} (parts file "colours", or --preset) or a reference
  screenshot (--ref) overrides. Colours are the sheet's palette indices (nearest). No white outline and
  no white edge highlight: lines keep their colour (a white line is darkened), the figure's edge ring
  takes its line's colour, white is used only when a preset asks for it. Any colour boundary that would
  still be a straight cut is merged away (resolve_cuts), on each figure and again after a shared
  graphic's votes (paint_map).
"""
import argparse
import collections
import json
import math
import os
import shutil

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
D4 = ((1, 1), (1, -1), (-1, 1), (-1, -1))
PARTS = ('head', 'face', 'hair', 'body', 'arm', 'legs', 'feet', 'detail', 'item')
SKIN = (232, 172, 124)
BROWN = (130, 72, 24)
MATCH_MAX = 0.9          # match cost above this: carried but reported as a weak match (check it)
CARRY_MAX = 2.5          # above this: unmatched, keeps its own guess (Nightshade: carrying beats guessing)
MIN_REGION = 3           # smaller regions are specks: they take the nearest region's part


# ---------------------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------------------

def components(pixels, nb=N4):
    left, out = set(pixels), []
    while left:
        p = left.pop()
        comp, st = {p}, [p]
        while st:
            x, y = st.pop()
            for dx, dy in nb:
                q = (x + dx, y + dy)
                if q in left:
                    left.discard(q)
                    comp.add(q)
                    st.append(q)
        out.append(comp)
    out.sort(key=lambda c: (min(y for _, y in c), min(x for x, _ in c)))
    return out


def lum(c):
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def dark(c):
    return c is not None and lum(c) < 0.16


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def hexrgb(v):
    v = v.strip().lstrip('#')
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def nearest_index(c, rgb16, avoid=()):
    """palette index 1-15 nearest to c (weighted RGB), not in avoid when another is possible"""
    def d(i):
        p = rgb16[i]
        rm = (c[0] + p[0]) / 2.0
        return (2 + rm / 256) * (c[0] - p[0]) ** 2 + 4 * (c[1] - p[1]) ** 2 + (2 + (255 - rm) / 256) * (c[2] - p[2]) ** 2
    order = sorted(range(1, 16), key=d)
    for i in order:
        if i not in avoid:
            return i
    return order[0]


def holes_in(P):
    """pixels inside P's box that P encloses (not reachable from the box edge without crossing P)"""
    xs, ys = [x for x, _ in P], [y for _, y in P]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    seen, st = {(x0, y0)}, [(x0, y0)]
    while st:
        x, y = st.pop()
        for dx, dy in N4:
            q = (x + dx, y + dy)
            if x0 <= q[0] <= x1 and y0 <= q[1] <= y1 and q not in seen and q not in P:
                seen.add(q)
                st.append(q)
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if (x, y) not in seen and (x, y) not in P}


def straight_cut(a, b):
    """True when regions a and b meet along a straight row or column of 3+ pixels (looksheet's CUT rule,
    applied to the two regions alone: each region is flat in its own colour)."""
    from .looksheet import cuts
    px = {p: (200, 0, 0) for p in a}
    px.update({p: (0, 200, 0) for p in b})
    return bool(cuts(px))


# ---------------------------------------------------------------------------------------------------------
# 1. Regions from the drawing
# ---------------------------------------------------------------------------------------------------------

class Figure:
    """One figure: cls {(x, y): 'ink' | 'mask' | 'hole' | 'clear'} (hole = enclosed paper the engine fills
    opaque, e.g. Robin's closed-shape fill; clear = a listed transparent pixel), colour
    {(x, y): (r, g, b)} as drawn today (None for clear). After segment(): regions [Region], line set,
    region_of {pixel: region index}."""

    def __init__(self, cls, colour, name='', line=None):
        self.cls, self.colour, self.name = dict(cls), dict(colour), name
        op = [p for p, c in self.cls.items() if c != 'clear']
        self.opaque = set(op)
        xs, ys = [x for x, _ in op] or [0], [y for _, y in op] or [0]
        self.box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
        self.line_cls = line
        self.facing = None           # author's label: 'R' / 'L' (profile, face to that side), 'F' front, 'B' back
        self.family = None           # its family's name (analyse): parts.json "colours" presets are keyed by it
        self.regions, self.line, self.region_of = [], set(), {}

    @property
    def w(self):
        return self.box[2] - self.box[0]

    @property
    def h(self):
        return self.box[3] - self.box[1]

    def anchor(self):
        """the figure's anchor hue: its commonest non-black opaque colour as drawn today"""
        cnt = collections.Counter(c for p, c in self.colour.items() if p in self.opaque and c and not dark(c))
        return cnt.most_common(1)[0][0] if cnt else (200, 200, 200)


class Region:
    def __init__(self, pixels, kind, thin=False):
        self.pixels, self.kind, self.thin = set(pixels), kind, thin
        self.guess = self.label = None
        self.speck_of = None
        self.matched = None          # (key region index, cost) after matching
        self.holes = 0

    def centroid(self):
        n = float(len(self.pixels))
        return sum(x for x, _ in self.pixels) / n, sum(y for _, y in self.pixels) / n

    def bbox(self):
        xs, ys = [x for x, _ in self.pixels], [y for _, y in self.pixels]
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def dither_pixels(tone, pixels):
    """pixels in a checkerboard of two tones (ink, mask, or a filled hole): 3+ of 4 neighbours another
    tone, 2+ diagonals the same; kept only in areas of 6+ pixels"""
    d = set()
    for p in pixels:
        c = tone[p]
        x, y = p
        other = sum(1 for dx, dy in N4 if tone.get((x + dx, y + dy)) not in (None, c))
        same = sum(1 for dx, dy in D4 if tone.get((x + dx, y + dy)) == c)
        if other >= 3 and same >= 2:
            d.add(p)
    return set().union(*[c for c in components(d) if len(c) >= 6]) if d else set()


def thin_share(pix):
    if not pix:
        return 0.0
    blk = set()
    for (x, y) in pix:
        if (x + 1, y) in pix and (x, y + 1) in pix and (x + 1, y + 1) in pix:
            blk |= {(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)}
    return 1.0 - len(blk) / float(len(pix))


def choose_line(fig, dith, holes=()):
    """the line class. Two opaque classes: the thinner (+0.3 when its colour is dark): Target: Renegade's
    black ink, Nightshade's black mask. One class: it is the line when it is mostly thin and encloses
    holes of 4+ pixels (Robin's ink round his face); else None (a solid unmasked figure: its gaps are
    the lines)."""
    score, dk = {}, {}
    for c in ('ink', 'mask'):
        pix = {p for p in fig.opaque if fig.cls[p] == c and p not in dith}
        if not pix:
            continue
        cols = collections.Counter(fig.colour.get(p) for p in pix)
        col = cols.most_common(1)[0][0]
        dk[c] = dark(col)
        score[c] = thin_share(pix) + (0.3 if dk[c] else 0.0)
    if not score:
        return None
    if len(score) == 2 and sum(dk.values()) == 1:
        return next(c for c in dk if dk[c])      # the one dark class is the drawing's line
    if len(score) == 1:
        c, s = next(iter(score.items()))
        if len(holes) >= 4:              # the engine fills what this class encloses: it is the drawing's line
            return c
        return c if s >= 0.5 and len(holes_in(fig.opaque)) >= 4 else None
    return max(score, key=score.get)       # both or neither dark: the thinner


def segment(fig, fill_holes=False):
    """-> fig with regions (shape-split), line pixels and region_of. fill_holes: clear pixels the figure
    encloses (eyes, mouths) are regions too (paint_clear sheets only)."""
    cls, op = fig.cls, fig.opaque
    hole = {p for p in op if cls[p] == 'hole'}
    if fill_holes and op:
        hole |= {p for p in holes_in(op) if cls.get(p) == 'clear'}
    tone = {p: cls[p] for p in op}
    tone.update({p: 'hole' for p in hole})
    dith = dither_pixels(tone, set(tone))
    if fig.line_cls is None:
        fig.line_cls = choose_line(fig, dith, hole)
    lc = fig.line_cls
    linep = {p for p in op if cls[p] == lc and p not in dith} if lc else set()
    core = {(x, y) for (x, y) in linep if all((x + dx, y + dy) in linep for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
    mass = set()
    for comp in components(core):
        grown = comp | {(x + dx, y + dy) for (x, y) in comp for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                        if (x + dx, y + dy) in linep}
        if len(grown) >= 9:
            mass |= grown
    fig.line = linep - mass
    groups = collections.defaultdict(set)
    for p in tone:
        if p in fig.line:
            continue
        kind = 'dither' if p in dith else 'mass' if p in mass else 'hole' if p in hole else 'fill' if lc else cls[p]
        groups[kind].add(p)
    raw = []
    for kind in sorted(groups):
        for comp in components(groups[kind]):
            raw.append((kind, comp))
    regs = []
    for kind, comp in raw:
        if len(comp) < MIN_REGION:
            regs.append(Region(comp, kind))
            continue
        for piece, thin in split_shape(comp):
            regs.append(Region(piece, kind, thin))
    # a drawn shape the line class makes inside one region (a face drawn solid inside the hood) is a part
    for r in list(regs):
        if len(r.pixels) >= 12:
            for comp in components(holes_in(r.pixels) & fig.line):
                if len(comp) >= 6:
                    regs.append(Region(comp, 'mass'))
                    fig.line -= comp
    regs.sort(key=lambda r: (r.bbox()[1], r.bbox()[0]))
    fig.regions = regs
    fig.region_of = {p: i for i, r in enumerate(regs) for p in r.pixels}
    for r in regs:
        r.holes = len(holes_in(r.pixels)) if len(r.pixels) >= MIN_REGION else 0
    _specks(fig)
    return fig


def split_shape(P, min_piece=6, min_limb=4):
    """A region -> [(pixels, thin)]: cut only where the drawn shape changes - a neck (the erosion falls
    apart) or a thin protrusion (what an opening removes). A cut along a straight run of 3+ pixels is
    undone."""
    E = {(x, y) for (x, y) in P if all((x + dx, y + dy) in P for dx, dy in N4)}
    if not E:
        return [(P, len(P) >= min_limb)]
    cores = [c for c in components(E) if len(c) >= 2]
    if not cores:
        return [(P, len(P) >= min_limb)]
    # necks: every pixel to its nearest core (multi-source BFS inside the region)
    owner = {}
    q = collections.deque()
    for i, c in enumerate(cores):
        for p in c:
            owner[p] = i
            q.append(p)
    while q:
        p = q.popleft()
        for dx, dy in N4:
            r = (p[0] + dx, p[1] + dy)
            if r in P and r not in owner:
                owner[r] = owner[p]
                q.append(r)
    pieces = [set() for _ in cores]
    for p, i in owner.items():
        pieces[i].add(p)
    pieces = _merge_small(pieces, min_piece)
    out = []
    for piece in pieces:
        e = E & piece
        opened = e | {(x + dx, y + dy) for (x, y) in e for dx, dy in N4 if (x + dx, y + dy) in piece}
        body, limbs = set(opened), []
        for comp in components(piece - opened):
            xs, ys = [x for x, _ in comp], [y for _, y in comp]
            ext = max(max(xs) - min(xs), max(ys) - min(ys)) + 1
            contact = sum(1 for (x, y) in comp if any((x + dx, y + dy) in opened for dx, dy in N4))
            if len(comp) >= min_limb and ext >= 3 and contact <= 3 and ext > contact:
                limbs.append(comp)
            else:
                body |= comp
        for lb in limbs:
            if straight_cut(lb, body):
                body |= lb
            else:
                out.append((lb, True))
        out.append((body, False))
    # undo any neck split whose boundary is straight across a flat area
    merged = True
    while merged and len(out) > 1:
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i][0], out[j][0]
                if _touch(a, b) and straight_cut(a, b):
                    out[i] = (a | b, out[i][1] and out[j][1])
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    return out


def _touch(a, b):
    small, big = (a, b) if len(a) < len(b) else (b, a)
    return any((x + dx, y + dy) in big for (x, y) in small for dx, dy in N4)


def _merge_small(pieces, n):
    pieces = [p for p in pieces if p]
    changed = True
    while changed and len(pieces) > 1:
        changed = False
        for i, p in enumerate(pieces):
            if len(p) < n:
                best = max((j for j in range(len(pieces)) if j != i),
                           key=lambda j: sum(1 for (x, y) in p for dx, dy in N4 if (x + dx, y + dy) in pieces[j]))
                pieces[best] |= p
                del pieces[i]
                changed = True
                break
    return pieces


def _specks(fig):
    """each speck (a region under MIN_REGION pixels) -> the nearest real region through the figure"""
    real = [i for i, r in enumerate(fig.regions) if len(r.pixels) >= MIN_REGION]
    if not real:
        return
    dist = {p: i for i in real for p in fig.regions[i].pixels}
    q = collections.deque(dist)
    allp = fig.opaque | set(fig.region_of)
    while q:
        p = q.popleft()
        for dx, dy in N4 + D4:
            r = (p[0] + dx, p[1] + dy)
            if r in allp and r not in dist:
                dist[r] = dist[p]
                q.append(r)
    for i, r in enumerate(fig.regions):
        if len(r.pixels) < MIN_REGION:
            r.speck_of = dist.get(next(iter(r.pixels)), real[0])


def adjacency(fig):
    """{region: {region}}: touching (8-neighbours) or across one line pixel"""
    adj = collections.defaultdict(set)
    ro = fig.region_of
    for p, i in ro.items():
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                q = (p[0] + dx, p[1] + dy)
                j = ro.get(q)
                if j is None or j == i:
                    continue
                if max(abs(dx), abs(dy)) == 1 or ((p[0] + dx // 2, p[1] + dy // 2) in fig.line):
                    adj[i].add(j)
    return adj


# ---------------------------------------------------------------------------------------------------------
# 3. Part guesses
# ---------------------------------------------------------------------------------------------------------

def guess(fig, kind='whole'):
    """suggested part per region (the author's labels win). kind: 'whole' figure, or one graphic of a
    figure drawn in pieces: 'upper' (no feet) or 'lower' (no head)."""
    x0, y0, x1, y1 = fig.box
    H, W = float(max(1, y1 - y0)), float(max(1, x1 - x0))
    area = float(max(1, len(fig.opaque)))
    R = fig.regions
    real = [i for i, r in enumerate(R) if r.speck_of is None]
    rel = lambda i: ((R[i].centroid()[0] - x0) / W, (R[i].centroid()[1] - y0) / H)
    n = lambda i: len(R[i].pixels)
    g = {}
    head = None
    if kind != 'lower':
        # the head: a solid region reaching the figure's top with its centre in the upper part; one with
        # holes (eyes, a face) wins over a larger one without
        top = [i for i in real if not R[i].thin and R[i].bbox()[1] <= y0 + max(1, 0.15 * H) and rel(i)[1] < 0.45
               and n(i) >= 0.04 * area and R[i].kind != 'mass']
        if top:
            mx = max(n(i) for i in top)
            holed = [i for i in top if R[i].holes and n(i) >= 0.5 * mx]
            head = max(holed or top, key=n)
    if head is not None:
        g[head] = 'head'
        hx0, hy0, hx1, hy1 = R[head].bbox()
        enc = holes_in(R[head].pixels)
        hp = R[head].pixels
        for i in real:
            if i == head or n(i) >= n(head):
                continue
            bx0, by0, bx1, by1 = R[i].bbox()
            edge = [p for p in R[i].pixels if any((p[0] + dx, p[1] + dy) not in R[i].pixels for dx, dy in N4)]
            against = sum(1 for (x, y) in edge if any((x + dx, y + dy) in hp for dx in (-2, -1, 0, 1, 2)
                                                       for dy in (-2, -1, 0, 1, 2)))
            inside = hx0 <= bx0 and bx1 <= hx1 and hy0 <= by0 and by1 <= hy1 + 1
            if fig.facing != 'B' and (R[i].pixels & enc or (not fig.facing and inside and against >= 0.6 * len(edge))):
                dk = dark(collections.Counter(fig.colour.get(p) for p in R[i].pixels).most_common(1)[0][0])
                g[i] = 'detail' if (n(i) < 4 or (R[i].kind == 'mass' and dk)) else 'face'
    if head is not None and 'face' not in g.values() and n(head) >= 20:
        _face_band(fig, head, g)
        R = fig.regions
        real = [i for i, r in enumerate(R) if r.speck_of is None]
    rest = [i for i in real if i not in g]
    body = max((i for i in rest if not R[i].thin and (kind != 'whole' or 0.25 <= rel(i)[1] <= 0.8)), key=n, default=None)
    if body is not None:
        g[body] = 'body'
    for i in real:
        if i in g:
            continue
        r = R[i]
        cx, cy = rel(i)
        if r.kind == 'mass' and n(i) < 0.05 * area:
            g[i] = 'detail'
        elif kind != 'upper' and r.bbox()[3] >= y1 - 1 and cy > (0.5 if kind == 'lower' else 0.75):
            g[i] = 'feet'
        elif r.thin:
            g[i] = 'arm' if kind == 'upper' or (kind == 'whole' and cy < 0.62) else 'legs'
        elif kind == 'lower':
            g[i] = 'legs' if cy > 0.35 else 'body'
        elif cy < 0.3:
            g[i] = 'head'
        elif cy < 0.62 or kind == 'upper':
            g[i] = 'body'
        else:
            g[i] = 'legs'
    for i, r in enumerate(R):
        r.guess = g.get(i) or (g.get(r.speck_of) if r.speck_of is not None else 'detail')
    return g


def _face_band(fig, head, g, depth=3):
    """A head with drawn features but no line round the face (Robin's profile): the face is a band that
    follows the head's own contour on the side the features are (each row: the pixels within `depth` of
    that row's front edge, the crown rows left as head), or an inset of the contour when the features sit
    in the middle (a front view). No features: a back view, no face. The band is a new region; it is
    dropped when its boundary is straight (looksheet.cuts)."""
    R = fig.regions
    hp = R[head].pixels
    x0, y0, x1, y1 = R[head].bbox()
    inner = {p for p in fig.line if x0 <= p[0] < x1 and y0 <= p[1] < y1}
    feat = [p for c in components(inner, N4 + D4) if len(c) <= 4 for p in c
            if sum((p[0] + dx, p[1] + dy) in hp for dx, dy in N4) >= 2]      # dots (eye, nostril), not folds
    if fig.facing == 'B' or (fig.facing is None and len(feat) < 2):
        return
    w = float(x1 - x0)
    if fig.facing:
        side = fig.facing
        if len(feat) < 2:                  # no dots: the face is below the crown, measured round the contour
            top = min(hp, key=lambda p: (p[1], p[0]))
            dist, q = {top: 0}, collections.deque([top])
            while q:
                p = q.popleft()
                for dx, dy in N4:
                    r = (p[0] + dx, p[1] + dy)
                    if r in hp and r not in dist:
                        dist[r] = dist[p] + 1
                        q.append(r)
            feat = [p for p, d in dist.items() if d >= (y1 - y0) // 2]
    else:
        fx = sum(p[0] for p in feat) / float(len(feat))
        side = 'R' if fx > x0 + 0.62 * w else 'L' if fx < x0 + 0.38 * w else 'F'
    if side == 'F':
        # from the front a face drawn solid in the line class inside the hood: the largest line shape in
        # the head's box that does not touch the figure's outside (its own drawn contour)
        cand = [c for c in components(inner) if len(c) >= 6 and not any(
            (x + dx, y + dy) not in fig.opaque for (x, y) in c for dx, dy in N4)]
        if cand:
            face = max(cand, key=len)
            fig.line -= face
            R.append(Region(face, 'mass'))
            i = len(R) - 1
            fig.region_of.update({p: i for p in face})
            g[i] = R[i].guess = 'face'
            return
    ext = {}
    for x, y in hp:
        a, b = ext.get(y, (x, x))
        ext[y] = (min(a, x), max(b, x))
    band = set()
    for x, y in hp:
        if min((x - fx_) ** 2 + (y - fy_) ** 2 for fx_, fy_ in feat) > 16:
            continue                       # the face is round its features (eye, nose, mouth): a curved edge
        a, b = ext[y]
        if (side == 'R' and b - x < depth) or (side == 'L' and x - a < depth) or (side == 'F' and a + 1 <= x <= b - 1):
            band.add((x, y))
    rest = hp - band
    if len(band) < 4 or len(rest) < 4 or straight_cut(band, rest):
        return
    R[head].pixels = rest
    R.append(Region(band, R[head].kind))
    i = len(R) - 1
    fig.region_of.update({p: i for p in band})
    g[i] = 'face'
    R[i].guess = 'face'


# ---------------------------------------------------------------------------------------------------------
# 2. The same part in every frame
# ---------------------------------------------------------------------------------------------------------

def features(fig):
    x0, y0, x1, y1 = fig.box
    W, H = float(max(1, x1 - x0)), float(max(1, y1 - y0))
    area = float(max(1, len(fig.opaque)))
    out = []
    for r in fig.regions:
        cx, cy = r.centroid()
        out.append(((cx - x0 + 0.5) / W, (cy - y0 + 0.5) / H, len(r.pixels) / area, r.kind, r.thin))
    return out


def _cost(a, b, mirror):
    ax = 1.0 - a[0] if mirror else a[0]
    c = 3.0 * math.hypot(ax - b[0], a[1] - b[1]) + 0.5 * abs(math.log((a[2] + 1e-3) / (b[2] + 1e-3)))
    return c + (1.0 if a[3] != b[3] else 0.0) + (0.3 if a[4] != b[4] else 0.0)


def _overlay(fig, key, mirror, anchor):
    """fig's pixels placed on the key figure: boxes aligned at the centre column and at the top or the
    bottom row (anchor), mirrored or not -> function pixel -> key pixel"""
    fx0, fy0, fx1, fy1 = fig.box
    kx0, ky0, kx1, ky1 = key.box
    dy = (ky0 - fy0) if anchor == 'top' else (ky1 - fy1)
    off = kx0 + ((kx1 - kx0) - (fx1 - fx0)) // 2
    if mirror:
        return lambda p: (off + (fx1 - 1 - p[0]), p[1] + dy)
    return lambda p: (off + (p[0] - fx0), p[1] + dy)


def match(fig, key):
    """match fig's regions to the key figure's: -> (mirrored?, {region: (key region, cost)}). The cost:
    where the region lies in its figure (relative to the box), its share of the figure, kind and thin,
    and how much of it lands on the key region when the figures are overlaid (direct or mirrored, aligned
    at the top or the bottom: the best overall wins). Specks are not matched (they follow their region)."""
    fa, fb = features(fig), features(key)
    kreal = [j for j, r in enumerate(key.regions) if r.speck_of is None]
    near = {}
    for j in kreal:
        for (x, y) in key.regions[j].pixels:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    near.setdefault((x + dx, y + dy), collections.Counter())[j] += 1 if dx or dy else 3
    best = None
    for mirror in (False, True):
        for anchor in ('top', 'bottom'):
            put = _overlay(fig, key, mirror, anchor)
            res, tot = {}, 0.0
            for i, r in enumerate(fig.regions):
                if r.speck_of is not None or not kreal:
                    continue
                hit = collections.Counter()
                for p in r.pixels:
                    c = near.get(put(p))
                    if c:
                        hit[c.most_common(1)[0][0]] += 1
                def cost(j):
                    return _cost(fa[i], fb[j], mirror) + 1.5 * (1.0 - hit[j] / float(len(r.pixels)))
                j = min(kreal, key=cost)
                res[i] = (j, cost(j) - 0.75)      # an exact overlay and place: about -0.75 .. 0
                tot += max(0.0, res[i][1]) * len(r.pixels)
            if best is None or tot < best[0]:
                best = (tot, mirror, res)
    return best[1], best[2]


def carry(figs, key_index, labels):
    """labels {key region: part} carried to every figure of the family. -> report lines (weak matches and
    unmatched regions)."""
    key = figs[key_index]
    rep = []
    for n, f in enumerate(figs):
        if n == key_index:
            for i, r in enumerate(f.regions):
                r.label = labels.get(i) or labels.get(str(i)) or r.guess
            continue
        mir, m = match(f, key)
        for i, r in enumerate(f.regions):
            if i in m:
                j, c = m[i]
                r.matched = (j, c)
                kl = labels.get(j) or labels.get(str(j)) or key.regions[j].guess
                if c <= CARRY_MAX:
                    r.label = kl
                    if c > MATCH_MAX:
                        rep.append('%s region %d (%d px at %d,%d): weak match to key region %d (cost %.2f), takes %s: '
                                   'check it' % (f.name, i, len(r.pixels), r.bbox()[0], r.bbox()[1], j, c, kl))
                else:
                    r.label = r.guess
                    rep.append('%s region %d (%d px at %d,%d): no match in the key frame (best %d, cost %.2f); '
                               'keeps its guess %s' % (f.name, i, len(r.pixels), r.bbox()[0], r.bbox()[1], j, c, r.guess))
        for i, r in enumerate(f.regions):
            if r.speck_of is not None:
                r.label = f.regions[r.speck_of].label
    return rep


# ---------------------------------------------------------------------------------------------------------
# 4. A palette
# ---------------------------------------------------------------------------------------------------------

def part_colours(fig, preset=None):
    """{part: rgb} for one figure: the anchor hue (its original ink) for the body, shades of it for head
    and legs, skin for face and arms; preset {part: rgb} wins."""
    a = fig.anchor()
    col = {'body': a, 'head': shade(a, 0.62), 'hair': (90, 50, 20), 'face': SKIN, 'arm': SKIN,
           'legs': shade(a, 0.45), 'feet': BROWN, 'detail': (0, 0, 0), 'item': a}
    col.update(preset or {})
    return col


def ref_colours(fig, png):
    """{region: rgb} sampled from a reference screenshot of the figure (a CPC / C64 / Spec256 frame),
    scaled to the figure's box: the commonest non-background colour under each region."""
    from PIL import Image
    im = Image.open(png).convert('RGB')
    bgc = im.getpixel((0, 0))
    x0, y0, x1, y1 = fig.box
    sx, sy = im.width / float(x1 - x0), im.height / float(y1 - y0)
    out = {}
    for i, r in enumerate(fig.regions):
        cnt = collections.Counter()
        for (x, y) in r.pixels:
            c = im.getpixel((min(im.width - 1, int((x - x0 + 0.5) * sx)), min(im.height - 1, int((y - y0 + 0.5) * sy))))
            if c != bgc:
                cnt[c] += 1
        if cnt:
            out[i] = cnt.most_common(1)[0][0]
    return out


def colour_figure(fig, rgb16, preset=None, ref=None):
    """-> {pixel: palette index} for every opaque pixel: regions in their part's colour (different parts
    that touch never share an index when the palette has another near one), the drawing's lines and a
    dither's line pixels in their own colour (a white line darkened), the edge ring in the line's colour,
    then resolve_cuts."""
    pc = part_colours(fig, preset)
    adj = adjacency(fig)
    rc = ref_colours(fig, ref) if ref else {}
    idx_of_part, idx = {}, {}
    order = sorted(range(len(fig.regions)), key=lambda i: -len(fig.regions[i].pixels))
    for i in order:
        r = fig.regions[i]
        part = r.label or r.guess or 'body'
        if i in rc:
            want = rc[i]
        else:
            want = pc.get(part, pc['body'])
        if i not in rc and part in idx_of_part:
            idx[i] = idx_of_part[part]
            continue
        avoid = {idx[j] for j in adj.get(i, ()) if j in idx and (fig.regions[j].label or fig.regions[j].guess) != part}
        if not (preset and part in preset):
            avoid |= {k for k in range(1, 16) if min(rgb16[k]) >= 230}       # no white unless asked for
        avoid |= {k for k in range(1, 16) if dark(rgb16[k])} if not dark(want) else set()
        idx[i] = nearest_index(want, rgb16, avoid)
        if i not in rc:
            idx_of_part.setdefault(part, idx[i])
    out = {}
    for i, r in enumerate(fig.regions):
        for p in r.pixels:
            out[p] = idx[i]
    white = {k for k in range(1, 16) if min(rgb16[k]) >= 230}
    for i, r in enumerate(fig.regions):
        if r.kind == 'dither':                 # a pattern keeps its pattern: the line class stays drawn
            for p in r.pixels:
                if fig.cls.get(p) == fig.line_cls and fig.colour.get(p) is not None:
                    out[p] = nearest_index(fig.colour[p], rgb16)
    for p in fig.line:
        c = fig.colour.get(p)
        if c is not None:                      # the drawing's lines keep their colour; never white (plan 21)
            v = nearest_index(c, rgb16)
            out[p] = v if v not in white else nearest_index(shade(rgb16[v], 0.45), rgb16, white)
    # the figure's edge ring (fill pixels between the outside and a drawn line) takes the line's colour:
    # no light rim round the figure (plan 21; Target: Renegade's mask ring)
    for p in list(out):
        if p in fig.region_of and any((p[0] + dx, p[1] + dy) not in fig.opaque for dx, dy in N4):
            ln = [(p[0] + dx, p[1] + dy) for dx, dy in N4 if (p[0] + dx, p[1] + dy) in fig.line]
            if ln and dark(fig.colour.get(ln[0])):
                out[p] = out.get(ln[0], nearest_index(fig.colour[ln[0]], rgb16))
    fig.merged_cuts = resolve_cuts(fig, out, rgb16)
    return out


def resolve_cuts(fig, idx, rgb16, rounds=200):
    """Any colour boundary that is still a straight cut across flat areas (looksheet.cuts: two regions of
    different kinds that abut without a line, a thick line beside a fill) is removed: on the smaller side
    (a region, or a connected line) the pixels of that colour take the other side's colour; each side is
    changed once, so nothing swings back. -> the number merged (reported; the author can still ask for
    the boundary). Lines (the drawing) are never changed."""
    from .looksheet import cuts
    lines = components(fig.line)

    def owner(p):
        i = fig.region_of.get(p)
        if i is not None:
            return frozenset(fig.regions[i].pixels)
        return next((frozenset(c) for c in lines if p in c), frozenset([p]))
    done, n = set(), 0
    for _ in range(rounds):
        acted = False
        for x0, y0, x1, y1 in cuts({p: rgb16[v] for p, v in idx.items()}):
            a, b = ((x0, y0 - 1), (x0, y0)) if y0 == y1 else ((x0 - 1, y0), (x0, y0))
            A, B = owner(a), owner(b)
            sides = sorted(((A, a, b), (B, b, a)), key=lambda t: len(t[0]))
            sides = [t for t in sides if t[1] in fig.region_of]     # the drawing's lines are never changed
            pick = next((t for t in sides if t[0] not in done), None)
            if pick is None:
                continue
            own, mine, other = pick
            old, new = idx[mine], idx[other]
            for q in own:
                if idx.get(q) == old:
                    idx[q] = new
            done.add(own)
            n += 1
            acted = True
            break
        if not acted:
            break
    return n


# ---------------------------------------------------------------------------------------------------------
# Colour sheets (docs/COLOURS.md): figures from a layout, the painted sheet, the colour map
# ---------------------------------------------------------------------------------------------------------

def sheet_figures(layout_path):
    """-> (layout, [(composite index, Figure, {pixel: (key, bit, code, default)})]). Whole figures: every
    pixel of each composite (not only the ones a unique painting sheet shows)."""
    from . import coloursheet as cs
    lay = json.load(open(layout_path))
    rgb16 = [tuple(c) for c in lay['palette']]
    base = lay.get('colours', {})
    pclear = bool(lay.get('paint_clear'))
    out = []
    for ci, comp in enumerate(lay['composites']):
        parts = cs._parts_of(comp)
        own = cs.owners(dict(parts=parts), clear=pclear)
        cls, col, keys = {}, {}, {}
        for (px, py), (n, i) in own.items():
            c, r, key, bit, code, dflt = parts[n]['pixels'][i]
            st = cs.state(base, key, bit)
            v = 0 if st == 'T' else ((st[1] if st != 'D' else 0) or dflt)
            cls[(px, py)] = 'ink' if code == 1 else 'mask' if code == 2 else 'clear'
            if code and st == 'T':
                cls[(px, py)] = 'clear'
            col[(px, py)] = rgb16[v] if v else None
            keys[(px, py)] = (key, bit, code, dflt)
        out.append((ci, Figure(cls, col, '%s #%d' % (comp['group'], ci)), keys))
    return lay, out


def families(lay, figs, parts_json=None):
    """[{name, figures: [list positions], key, labels}]: the parts file's, else one per sheet group (key =
    its largest figure)."""
    if parts_json and parts_json.get('families'):
        return parts_json['families']
    # one character = the figures of a sheet group that share graphics (joined through any shared part)
    par = list(range(len(figs)))

    def root(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    seen = {}
    for n, (ci, f, _) in enumerate(figs):
        comp = lay['composites'][ci]
        for p in comp['parts']:
            k = (comp['group'], p['id'])
            if k in seen:
                par[root(n)] = root(seen[k])
            else:
                seen[k] = n
    byf = collections.OrderedDict()
    for n in range(len(figs)):
        byf.setdefault(root(n), []).append(n)
    fams = []
    for ns in byf.values():
        key = max(ns, key=lambda n: len(figs[n][1].opaque))
        g = lay['composites'][figs[ns[0]][0]]['group']
        fams.append(dict(name='%s %d' % (g, sum(1 for f in fams if f['name'].startswith(g + ' ')) + 1),
                         figures=[figs[n][0] for n in ns], key=figs[key][0], labels={}))
    return fams


def analyse(layout_path, parts_json=None, fill_holes=False, line=None):
    lay, figs = sheet_figures(layout_path)
    fams = families(lay, figs, parts_json)
    pos = {ci: n for n, (ci, _, _) in enumerate(figs)}
    for fam in fams:
        for c in fam['figures']:
            if c in pos:
                figs[pos[c]][1].facing = fam.get('facing')
                figs[pos[c]][1].family = fam['name']
    for ci, f, _ in figs:
        f.line_cls = line
        segment(f, fill_holes)
        guess(f)
    rep = []
    for fam in fams:
        members = [figs[pos[c]][1] for c in fam['figures'] if c in pos]
        if not members or fam['key'] not in pos:
            continue
        k = [c for c in fam['figures'] if c in pos].index(fam['key'])
        rep += carry(members, k, {int(a): b for a, b in fam.get('labels', {}).items()})
    return lay, figs, fams, rep


def preset_for(presets, lay, ci, f):
    """A figure's preset: its family's (parts.json "colours" keyed by family name, as the template says), else its
    sheet group's, else "*"."""
    presets = presets or {}
    for k in (getattr(f, 'family', None), lay['composites'][ci]['group'], '*'):
        if k is not None and k in presets:
            return presets[k]
    return None


def paint_map(lay, figs, presets=None, refs=None):
    """-> (colour map, report): each (key, bit) the commonest index its figures give it (a graphic drawn in
    several figures gets one colour); today's default where the index equals it."""
    from . import coloursheet as cs
    rgb16 = [tuple(c) for c in lay['palette']]
    votes = collections.defaultdict(collections.Counter)
    meta = {}
    for ci, f, keys in figs:
        pre = preset_for(presets, lay, ci, f)
        idx = colour_figure(f, rgb16, pre, (refs or {}).get(ci))
        for p, v in idx.items():
            key, bit, code, dflt = keys[p]
            votes[(key, bit)][v] += 1
    for comp in lay['composites']:
        for p in comp['parts']:
            for k, e in p['entries'].items():
                meta.setdefault(k, list(e[:2]))
    cmap = cs._copy({k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in lay.get('colours', {}).items()})
    split = 0
    dflt = {}
    for ci, f, keys in figs:
        for p, (key, bit, code, d) in keys.items():
            dflt[(key, bit)] = (d, code)
    final = {kb: cnt.most_common(1)[0][0] for kb, cnt in votes.items()}
    # the majority of a shared graphic can bring a straight cut into a figure that voted otherwise: check
    # every figure again with the final colours (resolve_cuts; a few passes, shared pixels settle)
    merged = 0
    for _ in range(3):
        moved = 0
        for ci, f, keys in figs:
            idx = {p: final[keys[p][:2]] for p in keys if keys[p][:2] in final}
            before = dict(idx)
            merged += resolve_cuts(f, idx, rgb16)
            for p, v in idx.items():
                if before[p] != v:
                    final[keys[p][:2]] = v
                    moved += 1
        if not moved:
            break
    for kb, cnt in votes.items():
        if len(cnt) > 1:
            split += 1
        v = final[kb]
        d, code = dflt[kb]
        cs.set_state(cmap, kb[0], kb[1], 'D' if (code and v == d) else ('C', v), meta[kb[0]])
    return cmap, {'pixels painted': len(votes), 'pixels shared by figures painted differently (majority kept)': split,
                  'colour boundaries merged on the sheet (straight cuts)': merged}


# ---------------------------------------------------------------------------------------------------------
# Pictures
# ---------------------------------------------------------------------------------------------------------

def _region_rgb(i):
    h = (i * 0.61803) % 1.0
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


PART_RGB = {'head': (150, 150, 175), 'face': (240, 170, 120), 'hair': (100, 60, 20), 'body': (235, 235, 235),
            'arm': (255, 140, 0), 'legs': (90, 110, 200), 'feet': (140, 80, 20), 'detail': (255, 0, 255),
            'item': (200, 200, 40)}


def tile(fig, how, S=4, rgb16=None, idx=None, numbers=False):
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = fig.box
    im = Image.new('RGB', ((x1 - x0) * S, (y1 - y0) * S), (40, 60, 90))
    d = ImageDraw.Draw(im)
    for p in set(fig.cls) | set(fig.region_of):
        if not (x0 <= p[0] < x1 and y0 <= p[1] < y1):
            continue
        if how == 'original':
            c = fig.colour.get(p) if p in fig.opaque else None
        elif how == 'painted':
            c = rgb16[idx[p]] if p in idx else (fig.colour.get(p) if p in fig.opaque else None)
        elif p in fig.line:
            c = (0, 0, 0)
        elif p in fig.region_of:
            r = fig.regions[fig.region_of[p]]
            c = _region_rgb(fig.region_of[p] if r.speck_of is None else r.speck_of) if how == 'regions' else \
                PART_RGB.get(r.guess if how == "guess" else (r.label or r.guess), (255, 0, 255))
        else:
            c = None
        if c is not None:
            d.rectangle(((p[0] - x0) * S, (p[1] - y0) * S, (p[0] - x0) * S + S - 1, (p[1] - y0) * S + S - 1), fill=c)
    if numbers:
        for i, r in enumerate(fig.regions):
            if r.speck_of is None and len(r.pixels) >= 4:
                cx, cy = r.centroid()
                d.text(((cx - x0) * S - 3, (cy - y0) * S - 5), str(i), fill=(0, 0, 0))
    return im


def strip(rows, out, width=1800):
    """rows: [(label, [images])] -> one PNG, each row's images side by side, rows wrapped"""
    from PIL import Image, ImageDraw
    blocks = []
    for label, ims in rows:
        w = sum(i.width + 4 for i in ims)
        h = max(i.height for i in ims) + 12
        b = Image.new('RGB', (max(w, 60), h), (25, 25, 25))
        ImageDraw.Draw(b).text((1, 0), label, fill=(220, 220, 0))
        x = 0
        for i in ims:
            b.paste(i, (x, 12))
            x += i.width + 4
        blocks.append(b)
    lines, cur, cw = [], [], 0
    for b in blocks:
        if cur and cw + b.width + 8 > width:
            lines.append(cur)
            cur, cw = [], 0
        cur.append(b)
        cw += b.width + 8
    if cur:
        lines.append(cur)
    W = max([sum(b.width + 8 for b in ln) for ln in lines] or [1])
    H = sum(max(b.height for b in ln) + 8 for ln in lines) or 1
    im = Image.new('RGB', (W, H), (10, 10, 10))
    y = 0
    for ln in lines:
        x = 0
        for b in ln:
            im.paste(b, (x, y))
            x += b.width + 8
        y += max(b.height for b in ln) + 8
    im.save(out)


# ---------------------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------------------

def _whole_layout(layout):
    """the reference layout (every figure whole) beside a painting layout, else the layout itself"""
    from .recolour import reference_layout
    ref = reference_layout(layout)
    return ref if ref and os.path.exists(ref) else layout


def parts_template(lay, figs, fams):
    out = {'note': 'Label each family\'s key frame: region number (regions.png) -> part (%s). The labels '
                   'carry to every figure of the family; edit "figures" and "key" to regroup; "facing" R / L / '
                   'F / B puts the face on that side (B: none). "colours": '
                   '{part: "#RRGGBB"} per family name (or sheet group, or "*": a preset).' % ', '.join(PARTS),
           'families': [], 'colours': {}}
    pos = {ci: n for n, (ci, _, _) in enumerate(figs)}
    for fam in fams:
        kf = figs[pos[fam['key']]][1]
        labels = {str(i): (fam.get('labels', {}).get(str(i)) or r.guess) for i, r in enumerate(kf.regions)
                  if r.speck_of is None}
        out['families'].append(dict(name=fam['name'], figures=fam['figures'], key=fam['key'], facing=fam.get('facing'),
                                    labels=labels))
    return out


def cmd_regions(a, say=print):
    lay_path = _whole_layout(a.layout)
    pj = json.load(open(a.parts)) if a.parts else None
    lay, figs, fams, rep = analyse(lay_path, pj, a.fill_holes, a.line)
    os.makedirs(a.out, exist_ok=True)
    keys = {f['key'] for f in fams}
    rows = [(f.name + (' KEY' if ci in keys else ''), [tile(f, 'original'), tile(f, 'regions', numbers=ci in keys),
                                                    tile(f, 'parts')]) for ci, f, _ in figs]
    strip(rows, os.path.join(a.out, 'regions.png'))
    tp = os.path.join(a.out, 'parts.json')
    if not os.path.exists(tp) or a.parts and os.path.abspath(a.parts) == os.path.abspath(tp):
        json.dump(parts_template(lay, figs, fams), open(tp, 'w'), indent=1)
    nreg = sum(1 for _, f, _ in figs for r in f.regions if r.speck_of is None)
    nun = [x for x in rep if 'no match' in x]
    say('PAINT regions  %s: %d figures, %d families, %d regions (%d weak matches, %d unmatched)' % (
        os.path.basename(lay_path), len(figs), len(fams), nreg, len(rep) - len(nun), len(nun)))
    for line in nun[:30]:
        say('  ' + line)
    say('-> %s, %s (label the key frames, then paint --parts)' % (os.path.join(a.out, 'regions.png'), tp))
    return lay, figs, fams, rep


def cmd_paint(a, say=print):
    from . import coloursheet as cs
    from . import looksheet as LS
    lay_path = _whole_layout(a.layout)
    pj = json.load(open(a.parts)) if a.parts else None
    lay, figs, fams, rep = analyse(lay_path, pj, a.fill_holes, a.line)
    presets = {}
    for name, d in ((pj or {}).get('colours') or {}).items():
        presets[name] = {k: hexrgb(v) for k, v in d.items()}
    if a.preset:
        presets['*'] = {k: hexrgb(v) for k, v in json.load(open(a.preset)).items()}
    refs = {}
    for r in a.ref or ():
        n, p = r.split('=', 1)
        refs[int(n)] = p
    cmap, prep = paint_map(lay, figs, presets, refs)
    os.makedirs(a.out, exist_ok=True)
    rgb16 = [tuple(c) for c in lay['palette']]
    outs = []
    for lp in sorted({a.layout, lay_path}):
        stem = os.path.basename(lp)[:-len('_layout.json')] if lp.endswith('_layout.json') else \
            os.path.splitext(os.path.basename(lp))[0]
        png = os.path.join(a.out, stem + '_painted.png')
        tmp = os.path.join(a.out, '.tmp_layout.json')
        cs.redraw(lp, cmap, png, tmp)
        os.remove(tmp)
        shutil.copyfile(lp, os.path.join(a.out, stem + '_layout.json'))   # the map the sheet was drawn with
        outs.append(png)
    cj = os.path.join(a.out, os.path.basename(a.layout).replace('_layout.json', '') + '_paint_colours.json')
    cs.save(cmap, cj, 'nexclash.paint (follows the drawing)')
    idxs = {ci: colour_figure(f, rgb16, preset_for(presets, lay, ci, f), refs.get(ci)) for ci, f, _ in figs}
    strip([(f.name, [tile(f, 'original'), tile(f, 'regions'), tile(f, 'parts'), tile(f, 'painted', rgb16=rgb16,
                                                                                   idx=idxs[ci])])
           for ci, f, _ in figs], os.path.join(a.out, 'compare.png'))
    figs_ls = LS.figures_from_sheet(outs[-1], os.path.join(a.out, os.path.basename(lay_path)))
    for f in figs_ls:
        f['flags'] = LS.flags(f['px'])
    lsd = os.path.join(a.out, 'looksheet')
    os.makedirs(lsd, exist_ok=True)
    LS.sheet(figs_ls, [(0, 0, 0)], os.path.join(lsd, 'looksheet.png'))
    nc = sum(len(f['flags']['cuts']) for f in figs_ls)
    nv = sum(1 for f in figs_ls if f['flags']['vanish'])
    nr = sum(1 for f in figs_ls if f['flags']['rim'])
    report = dict(layout=os.path.basename(lay_path), figures=len(figs), families=[f['name'] for f in fams],
                  unmatched=rep, map_entries=len(cmap), looksheet=dict(cuts=nc, vanish_figures=nv, rim_figures=nr),
                  **{k: v for k, v in prep.items()})
    json.dump(report, open(os.path.join(a.out, 'paint_report.json'), 'w'), indent=1)
    say('PAINT  %s: %d figures, %d families, %d weak matches, %d unmatched regions (paint_report.json)' % (
        report['layout'], len(figs), len(fams), sum(1 for x in rep if 'weak' in x), sum(1 for x in rep if 'no match' in x)))
    for k, v in prep.items():
        say('  %s: %d' % (k, v))
    say('LOOK   CUT %d, VANISH %d figures, RIM %d figures (%s)' % (nc, nv, nr, os.path.join(lsd, 'looksheet.png')))
    for p in outs:
        say('-> %s' % p)
    say('-> %s, compare.png, paint_report.json' % cj)
    say('next: python nexclash.py recolour BUILD_sprites.nex %s' % outs[0])
    return report


def cmd_export(a, say=print):
    """every image of the build with its palette: the sheet (whole figures, the build's colours now), its
    layout (the index recolour reads) and an index json a person reads"""
    from . import coloursheet as cs
    from . import recolour as rc
    nex = open(a.nex, 'rb').read()
    name, mod = rc.pick(nex, a.game)
    lay = a.layout
    if not lay:
        raise ValueError('give --layout (the game\'s REFERENCE_ALL_SPRITES or PAINTING_SPRITES layout)')
    lay = _whole_layout(lay)
    rc.check_identity(mod, name, nex, [lay])
    cur, where = rc.current_map(nex, mod, a.nex)
    if cur is None:
        raise ValueError('no known colour map reproduces %s (recolour --onto)' % a.nex)
    os.makedirs(a.out, exist_ok=True)
    stem = os.path.join(a.out, '%s_SHEET' % name)
    cs.redraw(lay, cur, stem + '.png', stem + '_layout.json')
    L = json.load(open(stem + '_layout.json'))
    index = dict(game=name, build=os.path.basename(a.nex), colours=where,
                 palette=['#%02X%02X%02X' % tuple(c) for c in L['palette']],
                 swatches='row of 8x8 squares at the top: palette indices 1-15, left to right',
                 rules='one PNG pixel = one Spectrum pixel; paint only the grey and coloured pixels; keep the size',
                 images=[dict(n=i, group=c['group'], x=c['x'], y=c['y'], w=c['w'], h=c['h'],
                              graphics=[p['id'] for p in c['parts']]) for i, c in enumerate(L['composites'])])
    json.dump(index, open(stem + '_index.json', 'w'), indent=1)
    say('EXPORT %s: %d images, map from %s' % (name, len(index['images']), where))
    say('-> %s.png, %s_layout.json, %s_index.json' % (stem, stem, stem))
    return stem + '.png'


def silhouette_changes(png, layout_path):
    """[(image n, group, pixels that left the figure, pixels added outside it)] for an edited sheet"""
    from PIL import Image
    from . import coloursheet as cs
    lay = json.load(open(layout_path))
    im = Image.open(png).convert('RGB')
    if list(im.size) != lay['size']:
        raise ValueError('sheet is %dx%d, expected %dx%d (keep the size)' % (tuple(im.size) + tuple(lay['size'])))
    rgb16 = [tuple(c) for c in lay['palette']]
    out = []
    for n, comp in enumerate(lay['composites']):
        parts = cs._parts_of(comp)
        own = cs._shown(comp, parts, bool(lay.get('paint_clear')))
        ox, oy = comp.get('ox', 0), comp.get('oy', 0)
        shown = {}
        for (px, py), (k, i) in own.items():
            shown[(px - ox, py - oy)] = parts[k]['pixels'][i][4]
        lost = added = 0
        for y in range(comp['h']):
            for x in range(comp['w']):
                v = im.getpixel((comp['x'] + x, comp['y'] + y))
                fig = (x, y) in shown and shown[(x, y)] != 0
                now = not cs.background(v) and cs.nearest(v, rgb16)[0] != 0
                if fig and not now:
                    lost += 1
                elif now and (x, y) not in shown:
                    added += 1
        if lost or added:
            out.append((n, comp['group'], lost, added))
    return out


def cmd_import(a, say=print):
    from . import recolour as rc
    lay = a.layout or rc.find_layout(a.png)
    ch = silhouette_changes(a.png, lay)
    for n, g, lost, added in ch:
        say('WARNING: image %d (%s): silhouette changed - %d figure pixels painted out, %d pixels added outside '
            'the figure (recolour keeps the silhouette: those are reported and not used)' % (n, g, lost, added))
    return rc.run(a.nex, a.png, lay, a.game, a.output, say=say)


def selfcheck():
    """Synthetic figures (no game data): regions closed off by drawn lines, a neck split, no straight cut
    across a flat area, the head guessed from its holes, labels carried to a shifted mirrored frame, a
    row band refused. -> list of failures."""
    bad = []
    # a figure drawn in black lines (mask) around white ink: a head (with two eye holes) on a body, joined
    # by a 2-pixel neck, an arm sticking out of the body, a line across the body (two parts)
    cls, col = {}, {}
    W, K = (230, 230, 230), (0, 0, 0)
    head = {(x, y) for x in range(4, 11) for y in range(1, 7)}
    neck = {(7, 7), (8, 7)}
    body = {(x, y) for x in range(2, 13) for y in range(8, 18)}
    arm = {(x, 9) for x in range(13, 18)} | {(x, 10) for x in range(13, 18)}
    ink = (head - {(6, 3), (8, 3)}) | neck | body | arm
    ink -= {(x, 14) for x in range(2, 13)}            # a drawn line across the body (mask below)
    for p in ink:
        cls[p], col[p] = 'ink', W
    for (x, y) in list(ink) + [(x, 14) for x in range(2, 13)]:
        for dx, dy in N4 + D4:
            q = (x + dx, y + dy)
            if q not in ink and q not in cls:
                cls[q], col[q] = 'mask', K
    for x in range(2, 13):
        cls[(x, 14)], col[(x, 14)] = 'mask', K
    f = segment(Figure(cls, col, 'synthetic'))
    if f.line_cls != 'mask':
        bad.append('line class %r (want mask)' % f.line_cls)
    real = [r for r in f.regions if r.speck_of is None]
    sizes = sorted(len(r.pixels) for r in real)
    if len(real) != 4:
        bad.append('regions %s (want head, upper body, arm, lower body)' % sizes)
    for i, r in enumerate(f.regions):
        for j, s in enumerate(f.regions):
            if i < j and _touch(r.pixels, s.pixels) and straight_cut(r.pixels, s.pixels):
                bad.append('straight cut between regions %d and %d' % (i, j))
    guess(f)
    g = {r.guess for r in real}
    if 'head' not in g or 'arm' not in g:
        bad.append('guesses %s (want head and arm)' % sorted(g))
    hf = set().union(*[r.pixels for r in f.regions if r.guess in ('head', 'face')] or [set()])
    if not (hf >= head - {(6, 3), (8, 3)} - {(x, y) for x in (4, 10) for y in (1, 6)}) or hf & body:
        bad.append('head and face do not follow the head')
    # the same figure shifted and mirrored: labels carry
    m = {(30 - x, y + 2): c for (x, y), c in cls.items()}
    mc = {(30 - x, y + 2): c for (x, y), c in col.items()}
    f2 = segment(Figure(m, mc, 'mirrored'))
    guess(f2)
    labels = {i: 'lab%d' % i for i, r in enumerate(f.regions) if r.speck_of is None}
    rep = carry([f, f2], 0, labels)
    if rep:
        bad.append('unmatched on a mirrored copy: %s' % rep[:2])
    for r in f2.regions:
        if r.speck_of is None:
            src = [i for i, s in enumerate(f.regions) if {(30 - x, y + 2) for x, y in s.pixels} == r.pixels]
            if src and r.label != labels.get(src[0]):
                bad.append('label not carried: %s -> %s' % (labels.get(src[0]), r.label))
    # a flat box: never cut along a row (the old block colouring), however it is labelled
    box = {(x, y): 'ink' for x in range(8) for y in range(12)}
    fb = segment(Figure(box, {p: W for p in box}, 'box'))
    if len([r for r in fb.regions if r.speck_of is None]) != 1:
        bad.append('a flat box was split: %s' % [len(r.pixels) for r in fb.regions])
    # a dumbbell: two blobs joined by a 1-pixel neck split at the neck, the cut 1 pixel long
    db = {(x, y): 'ink' for x in range(5) for y in range(5)}
    db.update({(x, y): 'ink' for x in range(8, 13) for y in range(5)})
    db.update({(x, 2): 'ink' for x in range(5, 8)})
    fd = segment(Figure(db, {p: W for p in db}, 'dumbbell'))
    if len([r for r in fd.regions if r.speck_of is None]) != 2:
        bad.append('dumbbell not split at its neck: %s' % [len(r.pixels) for r in fd.regions])
    bad += _sheet_check(cls)
    bad += _family_presets_check()
    return bad


def _family_presets_check():
    """Two families in one sheet group, each with its own author colours (parts.json "colours" by family name): each
    figure takes its family's, a group preset reaches both. -> failures"""
    import tempfile
    from . import coloursheet as cs
    bad = []

    def part(pid, w, h, x0):
        px = [(x, y, '%s%d_%d' % (pid, y, x // 8), x % 8, 1, 15) for y in range(h) for x in range(w)]
        return dict(id=pid, size=max(8, w, h), w=w, h=h, x=x0, y=0, mir=0, group='Fig', pixels=px,
                    entries={'%s%d_%d' % (pid, y, c): [0, 1] for y in range(h) for c in range((w + 7) // 8)})
    col = cs.Collector()
    col.add_frame([part('a', 8, 8, 0)])
    col.add_frame([part('b', 16, 4, 40)])
    pal = cs.palette_rgb([0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF])
    with tempfile.TemporaryDirectory() as d:
        cs.write(col.composites(['Fig']), os.path.join(d, 'f.png'), os.path.join(d, 'f_layout.json'), pal, paint_clear=False)
        lay, figs, fams, _ = analyse(os.path.join(d, 'f_layout.json'))
    names = sorted(f['name'] for f in fams)
    if len(fams) != 2 or {getattr(f, 'family', None) for _, f, _ in figs} != set(names):
        return ['two families in one group: %s' % [(f['name'], f['figures']) for f in fams]]
    for _, f, _ in figs:
        for r in f.regions:
            r.label = 'body'
    rgb = [tuple(c) for c in lay['palette']]
    want = {names[0]: (255, 0, 0), names[1]: (0, 255, 0)}
    pre = {n: {'body': c} for n, c in want.items()}
    for ci, f, _ in figs:
        idx = colour_figure(f, rgb, preset_for(pre, lay, ci, f))
        got = {rgb[v] for v in idx.values()}
        near = min(range(16), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb[i], want[f.family])))
        if got != {rgb[near]}:
            bad.append('family %s painted %s, wanted its preset %s' % (f.family, sorted(got), rgb[near]))
    base = paint_map(lay, figs)[0]
    if paint_map(lay, figs, {'Fig': {'body': (255, 0, 0)}})[0] == base or paint_map(lay, figs, pre)[0] == base:
        bad.append('a group or family preset left the map unchanged')
    return bad


def _sheet_check(cls):
    """The synthetic figure on a colour sheet (coloursheet.write), painted, read back the way recolour
    reads it (coloursheet.changes: no conflicts, every change a palette colour), zero CUT on the look
    sheet; the negative control - the same figure coloured in two row bands - is flagged."""
    import tempfile
    from . import coloursheet as cs
    from . import looksheet as LS
    bad = []
    work = tempfile.mkdtemp(prefix='nexclash_paint_')
    pal = cs.palette_rgb([0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F,
                          0xFC, 0xFF])
    W = max(x for x, _ in cls) + 1
    H = max(y for _, y in cls) + 1
    px = [(x, y, 'S%02d%d' % (y, x // 8), x % 8, 1 if c == 'ink' else 2, 15 if c == 'ink' else 8)
          for (x, y), c in sorted(cls.items())]
    part = dict(id='S', size=H, w=W, h=H, x=10, y=10, mir=0, group='Fig', pixels=px,
                entries={k: [0, 1] for k in {q[2] for q in px}})
    col = cs.Collector()
    col.add_frame([part])
    png, lay = os.path.join(work, 'syn_PAINTING_SPRITES.png'), os.path.join(work, 'syn_PAINTING_SPRITES_layout.json')
    cs.write(col.composites(['Fig']), png, lay, pal, paint_clear=False)
    L, figs, _, _ = analyse(lay)
    cmap, rep = paint_map(L, figs)
    out = os.path.join(work, 'syn_PAINTING_SPRITES_painted.png')
    cs.redraw(lay, cmap, out, os.path.join(work, 'tmp.json'))
    base, chg, meta, conflicts, rrep = cs.changes(out, lay)
    if conflicts or not chg:
        bad.append('sheet read-back: %d changes, %d conflicts' % (len(chg), len(conflicts)))
    if any(st != 'D' and not (st[0] == 'C' and 1 <= st[1] <= 15) for st in chg.values()):
        bad.append('sheet read-back: a change that is not a palette colour')
    figs_ls = LS.figures_from_sheet(out, lay)
    if not figs_ls or any(LS.flags(f['px'])['cuts'] for f in figs_ls):
        bad.append('the painted synthetic sheet has a straight cut')
    band = {k: [v[0], v[1], list(v[2])] for k, v in cmap.items()}
    for q in px:                                            # negative control: two row bands
        if q[4] == 1:
            cs.set_state(band, q[2], q[3], ('C', 10 if q[1] < 11 else 12), [0, 1])     # across the body
    cs.redraw(lay, band, out, os.path.join(work, 'tmp.json'))
    if not any(LS.flags(f['px'])['cuts'] for f in LS.figures_from_sheet(out, lay)):
        bad.append('negative control: row-band colouring was not flagged')
    shutil.rmtree(work, ignore_errors=True)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m nexclash.paint', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('regions', 'paint'):
        p = sub.add_parser(name)
        p.add_argument('layout', help='the colour sheet layout (<game>_PAINTING_SPRITES_layout.json)')
        p.add_argument('--parts', help='the labels file (regions writes DIR/parts.json)')
        p.add_argument('--fill-holes', action='store_true', help='paint enclosed clear pixels too (paint_clear sheets)')
        p.add_argument('--line', choices=('ink', 'mask'), help='the line class (default: chosen per figure)')
        p.add_argument('-o', '--out', default='paint')
        if name == 'paint':
            p.add_argument('--preset', help='{part: "#RRGGBB"} for every figure')
            p.add_argument('--ref', action='append', help='FIGURE=PNG: colours sampled from a reference screenshot')
    p = sub.add_parser('export')
    p.add_argument('nex')
    p.add_argument('--layout', help='the game\'s sheet layout (REFERENCE_ALL_SPRITES preferred)')
    p.add_argument('--game')
    p.add_argument('-o', '--out', default='sheet')
    p = sub.add_parser('import')
    p.add_argument('nex')
    p.add_argument('png', help='the edited <game>_SHEET.png')
    p.add_argument('--layout')
    p.add_argument('--game')
    p.add_argument('-o', '--output')
    a = ap.parse_args(argv)
    try:
        {'regions': cmd_regions, 'paint': cmd_paint, 'export': cmd_export, 'import': cmd_import}[a.cmd](a)
    except ValueError as e:
        raise SystemExit('paint refused: %s' % e)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
