"""R-Type intro: the R-9 wireframe renderer (the owner's model, docs/profiles/r_type_r9_model.json.gz).
usage: python -m nexclash.r_type_r9 YAW PITCH ROLL [screenshot.png]   (320x256 screenshot to compare)

The model has two sets of lines. The STRUCTURE (kind 3) is the wireframe of each
enclosed volume; it is drawn at every angle except the exact side view. The DRAWINGS
(the original side view wrapped on the ship, and the top view on its upper surfaces)
are drawn at the exact side view - where they are the original picture - and, with
details=True, at other angles too.

Lines are hidden three ways:
  - facing: an edge whose surface faces away from the viewer is skipped;
  - strict edges (the side, top and front pictures) show only when their surface
    clearly faces the viewer (strict 2, the wing sheet: from either side);
  - solid: the ship's mesh is drawn into a depth buffer first, and a line pixel is
    plotted only if nothing of the ship is in front of it.
"""
import gzip, json, math, sys
from pathlib import Path
from PIL import Image

M = json.loads(gzip.decompress((Path(__file__).resolve().parents[1] / 'docs' / 'profiles' / 'r_type_r9_model.json.gz').read_bytes()))
SIN = [round(math.sin(2 * math.pi * i / 256) * 16384) for i in range(256)]
sin = lambda a: SIN[a & 255]
cos = lambda a: SIN[(a + 64) & 255]
fx = lambda a, b: (-1 if (a < 0) != (b < 0) else 1) * ((abs(a) * abs(b) + 8192) >> 14)
VIS_T, VIS_S, BIAS = 48, 64, 3.0
RECESS = 16000   # a recessed mark shows only within about 37 degrees of straight on (127 x 128 = square on)
FACE = 3200
NEAR = 4                                 # another part's outline closer than this in front of a firm part gives way to it (the port's rim across the gun's root)
FIRM_OWN = 3.5                           # ...but a firm part's own lines may run this far under another surface (the gun continuing into the wing)
FIRM = 0.75                              # depth allowance (pixels) between a firm part (a gun) and everything else      # a surface mark is hidden once its surface is turned this far away (127 x 128 = square on to the back)
W, H = 256, 192
GAP = (2, 1)      # silhouette first: how close (pixels) an outline / a detail pixel may run beside a line of higher rank


def matrix(y, p, r):
    cy, sy, cp, sp, cr, sr = cos(y), sin(y), cos(p), sin(p), cos(r), sin(r)
    t, u = fx(cp, cy), fx(sp, cy)
    m = [cy, -fx(sy, cr), fx(sy, sr),
         fx(cp, sy), fx(t, cr) - fx(sp, sr), -(fx(t, sr) + fx(sp, cr)),
         fx(sp, sy), fx(u, cr) + fx(cp, sr), fx(cp, cr) - fx(u, sr)]
    return [(v + 64) >> 7 for v in m]          # cut to 8 bits, as on the Next


def tz(s):
    return -((-s) >> 8) if s < 0 else s >> 8


def smp(i, c):
    """Where pixel i samples the solid: mirrored about the centre pixel c, like the lines."""
    return i + 0.5 if i > c else i - 0.5 if i < c else float(i)


def depth_buffer(m):
    """Two buffers: the whole ship, and the ship without the cockpit glass (what a line marked
    'through the glass' - the pilot - is tested against)."""
    g0, g1 = M.get('glass', (0, 0))
    zb = [1e9] * (W * H)
    zb2 = None
    # FIRM parts (the guns): thinner than the depth allowance, so they get an exact test of their own.
    # zbg = the firm parts alone, zbo = everything else.
    zbg, zbo = [1e9] * (W * H), [1e9] * (W * H)
    firm = [any(a <= t < b for a, b in M.get('firmtris', [])) for t in range(len(M['mtris']))]
    order = list(range(g0)) + list(range(g1, len(M['mtris']))) + list(range(g0, g1))
    pv = [(128 + (m[0] * v[0] + m[1] * v[1] + m[2] * v[2]) / 256,
           96 + (m[3] * v[0] + m[4] * v[1] + m[5] * v[2]) / 256,
           (m[6] * v[0] + m[7] * v[1] + m[8] * v[2]) / 256) for v in M['mverts']]
    for ti, (ia, ib, ic) in enumerate(M['mtris'][:g0] + M['mtris'][g1:] + M['mtris'][g0:g1]):   # the glass last
        if ti == len(M['mtris']) - (g1 - g0):
            zb2 = list(zb)
        zf = zbg if firm[order[ti]] else zbo
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = pv[ia], pv[ib], pv[ic]
        area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(area) < 1e-9:
            continue
        x0, x1 = max(0, int(min(ax, bx, cx)) - 1), min(W - 1, int(max(ax, bx, cx)) + 1)
        y0, y1 = max(0, int(min(ay, by, cy)) - 1), min(H - 1, int(max(ay, by, cy)) + 1)
        for j in range(y0, y1 + 1):
            py = float(j)
            for i in range(x0, x1 + 1):
                px = smp(i, 128)
                w0 = ((bx - px) * (cy - py) - (by - py) * (cx - px)) / area
                w1 = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) / area
                w2 = 1 - w0 - w1
                if w0 >= 0 and w1 >= 0 and w2 >= 0:
                    z = w0 * az + w1 * bz + w2 * cz
                    if z < zb[j * W + i]:
                        zb[j * W + i] = z
                    if z < zf[j * W + i]:
                        zf[j * W + i] = z
    return zb, zb2 or list(zb), zbg, zbo


def sround(v):
    """Round to the nearest whole number, halves away from zero (so +v and -v mirror exactly)."""
    return -math.floor(-v + 0.5) if v < 0 else math.floor(v + 0.5)


def raster(plot, x0, y0, z0, x1, y1, z1):
    """A line whose pixels mirror exactly about column 128 and row 96, whichever end it is drawn from
    (the same method as the viewer's line())."""
    adx, ady = abs(x1 - x0), abs(y1 - y0)
    if adx >= ady:
        if x0 > x1:
            x0, y0, z0, x1, y1, z1 = x1, y1, z1, x0, y0, z0
        dx, dy = x1 - x0, y1 - y0
        for i in range(dx + 1):
            v = (y0 - 96) * dx + i * dy
            plot(x0 + i, 96 + ((-1 if v < 0 else 1) * ((2 * abs(v) + dx) // (2 * dx)) if dx else y0 - 96), z0 + (z1 - z0) * i / dx if dx else min(z0, z1))
    else:
        if y0 > y1:
            x0, y0, z0, x1, y1, z1 = x1, y1, z1, x0, y0, z0
        dx, dy = x1 - x0, y1 - y0
        for i in range(dy + 1):
            v = (x0 - 128) * dy + i * dx
            plot(128 + (-1 if v < 0 else 1) * ((2 * abs(v) + dy) // (2 * dy)), y0 + i, z0 + (z1 - z0) * i / dy)


def render(y, p, r, cull=True, solid=True, details=False, only=None, declutter=True):
    """only='side': just the original side drawing (at any angle); only='rest': everything else.

    declutter (the same rule as the viewer's "Silhouette first" box): the ship's outer silhouette
    has priority. Lines are sorted into three ranks:
      0  outline pixels that lie on the edge of the whole ship (background beside them);
      1  the other outline pixels (one part's outline seen against another part);
      2  detail: sharp edges inside a part's outline, and surface features.
    A pixel of rank 1 is not drawn where it would lie directly alongside a rank 0 pixel, and a
    pixel of rank 2 is not drawn where it would lie directly alongside any pixel of rank 0 or 1
    already drawn. "Directly alongside" means the next pixel across the line's own direction (above or
    below for a line running mostly across the screen, left or right for one running mostly up
    the screen), so a line that MEETS another end-on is untouched, and only lines running
    side by side, which thicken into a blob, are thinned back to one pixel.

    The exception (user, 2026-11-19): in the DIRECT SIDE VIEW a line gives way only to lines of
    its OWN part (so the booster's rear end is still thinned), never to another part's - there
    the gun's muzzle above the booster, the marks along the hull's top and the booster's top line
    were being lost. Surface features belong to no part, so there they are all kept."""
    m = matrix(y, p, r)
    side = not M.get('plain') and abs(m[7]) == 128 and m[6] == 0 and m[8] == 0     # the exact side view
    # Rounded towards the centre (sign and magnitude), so the two halves of the ship
    # land as exact mirror images about screen column 128 / row 96.
    pts = [((128 + tz(m[0] * v[0] + m[1] * v[1] + m[2] * v[2])) & 255,
            (96 + tz(m[3] * v[0] + m[4] * v[1] + m[5] * v[2])) & 255,
            (m[6] * v[0] + m[7] * v[1] + m[8] * v[2]) / 256) for v in M['verts']]
    zb, zb2, zbg, zbo = depth_buffer(m) if solid else (None, None, None, None)
    firmp = set(M.get('firm', []))
    got = ({}, {})                           # outline pixels, detail pixels: (x, y) -> set of (direction (0 across, 1 up), part)
    cur = [0, 0, None, 0, False]
    own_only = m[6] == 0 and m[8] == 0       # looking straight along the ship's Y axis: the direct side view

    def plot(x, yy, z):
        if 0 <= x < W and 0 <= yy < H and (zb is None or (z <= (zb2 if cur[3] else zb)[yy * W + x] + BIAS and not (cur[4] and zb[yy * W + x] >= 1e8)
                                                  and (z <= zbo[yy * W + x] + FIRM_OWN if cur[2] in firmp else z <= zbg[yy * W + x] + (FIRM if cur[2] is None else -NEAR)))):   # (a firm part hides, and is hidden, exactly)   # (a mark ON a surface is never drawn outside the ship's own shape)
            got[cur[0]].setdefault((x, yy), set()).add((cur[1], cur[2]))

    def seg(rank, x0, y0, z0, x1, y1, z1, part=None, thru=0, on_surf=False):
        cur[0], cur[1], cur[2], cur[3], cur[4] = rank, 0 if abs(x1 - x0) >= abs(y1 - y0) else 1, part, thru, on_surf
        raster(plot, x0, y0, z0, x1, y1, z1)

    for a, b, qx, qy, qz, strict, *thru in M['edges']:
        is_side = (strict < 2 or strict == 4) and qx == 0 and qz == 0
        if only and is_side != (only == 'side'):
            continue
        if strict == 5:                      # a RECESSED mark (the gun port's rim): it sits back inside its opening, so
            if cull and qx * m[6] + qy * m[7] + qz * m[8] > -RECESS:    # it is seen only when looking nearly straight in
                continue
        elif strict == 3:                    # structure: everywhere but the exact side view
            if side:
                continue
            # A surface mark carries the outward direction of the surface it lies on (x127; none
            # = a free-standing line). It is hidden when that surface faces away from the viewer:
            # the ship is a solid, and a mark on the far side of a thin part must not show through.
            if cull and (qx or qy or qz) and qx * m[6] + qy * m[7] + qz * m[8] > FACE:
                continue
        elif strict not in (4, 5) and not (side or details or only == 'side'):          # the drawings: at the side view, or when asked for
            continue
        d = qx * m[6] + qy * m[7] + qz * m[8]
        if strict < 3 and cull and (abs(d) < VIS_S if strict == 2 else d > -VIS_S if strict else d > VIS_T):
            continue
        seg(1, *pts[a], *pts[b], None, thru[0] if thru else 0, bool(qx or qy or qz))
    if only != 'side':                       # the hull's outline as seen from here (model['sil'])
        pv = [(128 + (m[0] * v[0] + m[1] * v[1] + m[2] * v[2]) / 256,
               96 + (m[3] * v[0] + m[4] * v[1] + m[5] * v[2]) / 256,
               (m[6] * v[0] + m[7] * v[1] + m[8] * v[2]) / 256) for v in M['mverts']] if M.get('sil') else []
        front = lambda nx, ny, nz: nx * m[6] + ny * m[7] + nz * m[8] < -4      # faces the viewer (edge-on counts as away)
        for p, q, ax_, ay_, az_, bx_, by_, bz_, kind, _part, lift, thru in M.get('sil', []):
            fa, fb = front(ax_, ay_, az_), front(bx_, by_, bz_)
            if not (kind == 2 or (kind == 1 and (fa or fb)) or (kind == 0 and fa != fb)):
                continue
            # An outline lies where its own surface turns away from the viewer, where depth changes
            # fastest from pixel to pixel; it gets a larger allowance so it is not broken into dashes.
            seg(0 if kind == 2 or fa != fb else 1,
                128 + sround(pv[p][0] - 128), 96 + sround(pv[p][1] - 96), pv[p][2] - lift,
                128 + sround(pv[q][0] - 128), 96 + sround(pv[q][1] - 96), pv[q][2] - lift, _part, thru)
    if not (declutter and solid):
        return set(got[0]) | set(got[1])
    # the edge of the whole ship: an outline pixel with background directly above, below, left or
    # right of it (background = no ship surface there and no outline pixel either)
    bg = lambda x, yy: (x, yy) not in got[0] and (not (0 <= x < W and 0 <= yy < H) or zb[yy * W + x] >= 1e8)
    pix = {(x, yy) for x, yy in got[0] if bg(x - 1, yy) or bg(x + 1, yy) or bg(x, yy - 1) or bg(x, yy + 1)}   # rank 0
    # 'beside': a kept pixel of higher rank within `reach` pixels across the line's own direction
    # (in the direct side view: only one that a line of the same part runs through)
    parts_at = lambda k: {pt for g in got for _d, pt in g.get(k, ()) if pt is not None}
    def near(k, part, have):
        return k in have and (not own_only or (part is not None and part in parts_at(k)))
    def beside(x, yy, lines, have, reach):
        return all(any((near((x, yy + k), pt, have) or near((x, yy - k), pt, have)) if d == 0 else
                       (near((x + k, yy), pt, have) or near((x - k, yy), pt, have))
                       for k in range(1, reach + 1)) for d, pt in lines)
    for rank in (0, 1):
        have = set(pix)
        pix |= {k for k, lines in got[rank].items() if k not in have and not beside(*k, lines, have, 1 if own_only else GAP[rank])}   # (side view: only lines actually touching)
    return pix


if __name__ == '__main__':
    y, p, r = map(int, sys.argv[1:4])
    pix = render(y, p, r)
    print(len(pix), 'pixels in reference')
    if len(sys.argv) > 4:
        im = Image.open(sys.argv[4]).convert('RGB')
        got = {(x - 32, yy - 32) for yy in range(256) for x in range(320) if im.getpixel((x, yy)) != (0, 0, 0)}
        print(len(got), 'pixels in screenshot;', len(pix - got), 'missing,', len(got - pix), 'extra')
