"""Nightshade Enhanced set v2 (frozen 2026-11-04): the planes the default build carries, so its bytes stay as released (1cf6b276).

Each graphic (header: bit 7 rows reversed, bit 6 mirrored, low nibble the width in bytes; then height; then rows of
(mask, ink) byte pairs, bottom row first) is classed pixel by pixel in its stored orientation:
  line   ink touching the outside (4-neighbours),       detail  ink touching an enclosed hole,
  fill   other ink,                                     hole    non-ink enclosed by the figure (eyes, mouths, a face).
A part's colour is a code 1-7 = ink + 2 * plane0 + 4 * plane1. The two planes are stored as graphics in the
game's own format (mask 0, ink = the plane's bits) and turned to each of the four orientations by the game's
own flip routine (0xE353) on a copy of memory, so at run time the game's own plot loop shifts and places them
exactly as it places the ink: a flip or a shift cannot misplace a colour.
"""
from skoolkit.simulator import Simulator

GTAB = 28318
FLIPR = 58195                 # LD A,(IX+0) ... flips the graphic in place to (IX+7) bits 7, 6
FIG_TYPES = range(0x02, 0x98)
# mirrored (bit 6) is how the figures turn; bit 7 was never set at a plot in any recording, and the game's routine
# for it does not give a clean turn of this data: those figures keep their plain colour, counted by the verifier
ORIENTS = (0x00, 0x40)

# codes: 1 fill, 3 line, 5 detail, 7 accent (ink); 2 hole, 4 hole 2, 6 hole 3 (non-ink)
FILL, LINE, DETAIL, ACC, HOLE, HOLE2, HOLE3 = 1, 3, 5, 7, 2, 4, 6
# RRRGGGBB
K_, W_, LG, DG, R_, DR, OR_, Y_, BR, G_, DGN, C_, B_, M_, P_, SK = (0x00, 0xFF, 0xB6, 0x6D, 0xE0, 0x80, 0xF0, 0xFC,
                                                                0x88, 0x1C, 0x0C, 0x1F, 0x0B, 0xE3, 0x62, 0xF5)


def _r(a, b):
    return list(range(a, b + 1))


# (types, palette offset, {code: colour}, holes): holes 'none' leaves every enclosed gap as the game has it, 'all' fills
# them, an int fills only holes of at least that many pixels (a face, a mouth; not the gaps in a cloak or a swirl).
# The hero's offsets are 8 + his health colour (12, 14, 15).
HERO_UP = _r(0x20, 0x2F) + [0x16, 0x17, 0x1E, 0x1F]       # hood, cloak, face
HERO_LO = [t for t in _r(0x10, 0x1D) if t not in (0x16, 0x17)]   # tunic and legs
GROUPS = [
    ([0x04, 0x08], 1, {FILL: R_, LINE: DR, DETAIL: Y_, HOLE: W_}, 'all'),               # bible: red cover, gold, pages
    ([0x05, 0x09], 2, {FILL: Y_, LINE: OR_, DETAIL: Y_, HOLE: Y_}, 'none'),             # crucifix: gold
    ([0x06, 0x0A], 3, {FILL: LG, LINE: LG, DETAIL: W_, HOLE: C_}, 'all'),               # mirror: silver frame, glass
    ([0x07, 0x0B], 4, {FILL: LG, LINE: BR, DETAIL: DG, HOLE: DG}, 'none'),              # hammer: iron head, wooden handle
    ([0x02, 0x03], 4, {FILL: LG, LINE: BR, DETAIL: DG, HOLE: DG}, 'none'),              # other pickups
    ([0x60, 0x61, 0x62, 0x63, 0x90, 0x91], 5, {FILL: W_, LINE: C_, DETAIL: C_, HOLE: R_}, 4),     # ghost: red eyes
    ([0x64, 0x65, 0x66, 0x67, 0x92, 0x93], 6, {FILL: P_, LINE: M_, DETAIL: Y_, HOLE: SK}, 6),     # monk: robe, face
    ([0x68, 0x69, 0x6A, 0x6B, 0x94, 0x95], 7, {FILL: B_, LINE: LG, DETAIL: W_, HOLE: W_}, 6),     # reaper: robe, skull
    ([0x6C, 0x6D, 0x6E, 0x6F, 0x96, 0x97], 8, {FILL: W_, LINE: LG, DETAIL: Y_, HOLE: R_}, 'none'),     # skeleton
    (_r(0x70, 0x73) + _r(0x4C, 0x4F), 9, {FILL: G_, LINE: DGN, DETAIL: Y_, HOLE: R_}, 6),         # imp, slug: green
    (_r(0x74, 0x77) + _r(0x88, 0x8B), 10, {FILL: OR_, LINE: R_, DETAIL: Y_, HOLE: Y_}, 'none'),        # spiky head, fire demon
    (_r(0x44, 0x47), 10, {FILL: OR_, LINE: R_, DETAIL: Y_, HOLE: Y_}, 'none'),                    # explosion: as fire
    (_r(0x78, 0x7B) + _r(0x7C, 0x7F), 11, {FILL: M_, LINE: P_, DETAIL: Y_, HOLE: R_}, 'none'),         # demons, jester
    (_r(0x30, 0x33) + _r(0x50, 0x53) + [0x8C], 13, {FILL: W_, LINE: C_, DETAIL: W_, HOLE: W_}, 'none'),   # swirls
    (_r(0x34, 0x3F) + _r(0x54, 0x5F) + [0x8D, 0x8E, 0x8F], 2, {FILL: Y_, LINE: OR_, DETAIL: Y_, HOLE: Y_}, 'none'),  # shots: gold
    (_r(0x40, 0x43) + _r(0x48, 0x4B), 0, {FILL: C_, LINE: B_, DETAIL: W_, HOLE: W_}, 'none'),     # blobs, domes
    (_r(0x0C, 0x0F) + _r(0x80, 0x87), 13, {FILL: W_, LINE: C_, DETAIL: W_, HOLE: W_}, 'none'),    # sparkles
]
HOLES = {t: hm for types, off, cols, hm in GROUPS for t in types}
for _t in HERO_UP:
    HOLES[_t] = 8               # the face only
for _t in HERO_LO:
    HOLES[_t] = 'none'
# hero codes: tunic (lower part) FILL = health colour, LINE = its dark; hood and cloak (upper part) ACC light grey,
# DETAIL dark grey; face HOLE skin
HERO_COLS = {FILL: None, LINE: None, DETAIL: DG, ACC: LG, HOLE: SK, HOLE2: DR, HOLE3: K_}
DARK = {7: LG, 6: OR_, 4: DGN, 5: B_, 3: P_, 2: DR, 1: B_, 0: DG}
BRIGHT = [0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]


def palette():
    pal = bytearray(256)
    for types, off, cols, hm in GROUPS:
        for code, c in cols.items():
            pal[16 * off + code] = c
    for k in (4, 6, 7):
        for code, c in HERO_COLS.items():
            pal[16 * (8 + k) + code] = c if c is not None else (BRIGHT[k] if code == FILL else DARK[k])
    return bytes(pal)


def _check():
    seen = {}
    for types, off, cols, hm in GROUPS:
        if seen.setdefault(off, cols) != cols:
            raise ValueError('palette offset %d holds two colour sets' % off)
        if off in (12, 14, 15):
            raise ValueError('offset %d is reserved' % off)


_check()


def offsets():
    t = bytearray([13] * 256)      # anything else: offset 13's code 1, white
    for types, off, cols, hm in GROUPS:
        for x in types:
            t[x] = off
    for x in HERO_UP + HERO_LO:
        t[x] = 0xFF                 # the hero: 8 + health colour at the commit
    return bytes(t)


def graphic(mem, t):
    g = mem[GTAB + 2 * t] | mem[GTAB + 2 * t + 1] << 8
    w = mem[g] & 15
    h = mem[g + 1]
    return g, w, h


HERO_FACE = [0x1E] + _r(0x28, 0x2F)       # frames that show his face (front and side); the others show the hood's back
FACE_FROM = 11                              # the face is in the head, rows 11 and up of the upper part


def classify(ink, mask, w, h, t):
    """ink, mask: sets of (x, r), r = data row from the bottom -> {pixel: code}.
    outside: neither ink nor mask, reached from the box's edge. A hole is non-ink inside the figure: masked
    pixels with no outside neighbour (the black areas between the lines) or pixels the ink encloses."""
    W, H = 8 * w, h
    hero_up = t in HERO_UP
    holes = HOLES.get(t, 'none')
    st, seen = [(-1, -1)], {(-1, -1)}
    while st:
        x, r = st.pop()
        for q in ((x + 1, r), (x - 1, r), (x, r + 1), (x, r - 1)):
            if -1 <= q[0] <= W and -1 <= q[1] <= H and q not in seen and q not in ink and q not in mask:
                seen.add(q)
                st.append(q)
    outside = seen
    def n4(x, r):
        return ((x + 1, r), (x - 1, r), (x, r + 1), (x, r - 1))
    cand, edge = set(), set()
    for x in range(W):
        for r in range(H):
            p = (x, r)
            if p in ink or p in outside:
                continue
            if p in mask and any(q in outside for q in n4(x, r)):
                edge.add(p)                 # the figure's black edge
                continue
            cand.add(p)
    outside = outside | edge
    hole = set()
    left = set(cand)
    while left:
        p = left.pop()
        comp, st = {p}, [p]
        while st:
            x, r = st.pop()
            for q in n4(x, r):
                if q in left:
                    left.discard(q)
                    comp.add(q)
                    st.append(q)
        if hero_up:
            if t in HERO_FACE:
                hole |= {q for q in comp if q[1] >= FACE_FROM}
        elif holes == 'all' or (holes != 'none' and len(comp) >= holes):
            hole |= comp
    codes = {}
    for x in range(W):
        for r in range(H):
            p = (x, r)
            if p in ink:
                if any(q in outside for q in n4(x, r)):
                    c = LINE
                elif any(q in hole for q in n4(x, r)):
                    c = DETAIL
                else:
                    c = FILL
                if hero_up:
                    c = DETAIL if c != FILL else ACC
                codes[p] = c
            elif p in hole:
                codes[p] = HOLE
    return codes


def paint_all(mem):
    """-> {g: (w, h, base header byte, codes)} for every figure graphic, keyed by its address"""
    res = {}
    for t in FIG_TYPES:
        g, w, h = graphic(mem, t)
        if g in res or not (1 <= w <= 5 and 1 <= h <= 64):
            continue
        ink, mask = set(), set()
        for r in range(h):
            for c in range(w):
                m, v = mem[g + 2 + 2 * (r * w + c)], mem[g + 2 + 2 * (r * w + c) + 1]
                for b in range(8):
                    if v & (0x80 >> b):
                        ink.add((8 * c + b, r))
                    elif m & (0x80 >> b):
                        mask.add((8 * c + b, r))
        res[g] = (w, h, mem[g], classify(ink, mask, w, h, t), t)
    return res


def _orient(mem, t, g, data, o):
    """data (pairs, base orientation, header as in mem) turned to orientation o by the game's own routine"""
    m = bytearray(mem[:65536])
    n = len(data)
    m[g + 2:g + 2 + n] = data
    rec, stop = 0x5B00, 0x5B40
    m[rec:rec + 16] = bytes(16)
    m[rec] = t
    m[rec + 7] = o
    m[stop - 2], m[stop - 1] = stop & 255, stop >> 8
    sim = Simulator(m, {'PC': FLIPR, 'SP': stop - 2, 'IX': rec})
    R = sim.registers
    k = 0
    while R[24] != stop:
        sim.opcodes[m[R[24]]]()
        k += 1
        if k > 500000:
            raise RuntimeError('flip ran away')
    if m[g] & 0xC0 != o & 0xC0:
        raise RuntimeError('orientation not reached')
    return bytes(m[g + 2:g + 2 + n])


def planes(mem):
    """-> {g: {orientation: (plane0 data, plane1 data)}} in the game's graphic format, and the paint"""
    paint = paint_all(mem)
    out = {}
    for g, (w, h, hdr, codes, t) in paint.items():
        p = [bytearray(2 * w * h), bytearray(2 * w * h)]
        for (x, r), code in codes.items():
            for k in (0, 1):
                if code >> (k + 1) & 1:
                    p[k][2 * (r * w + x // 8) + 1] |= 0x80 >> (x & 7)
        out[g] = {}
        for o in ORIENTS:
            out[g][o] = tuple(_orient(mem, t, g, bytes(pk), o) if (hdr & 0xC0) != o else bytes(pk) for pk in p)
    return out, paint
