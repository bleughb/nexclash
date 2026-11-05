"""Robin of the Wood: the optional Enhanced colour set, painted by parts.

The default build's opaque pixels (original ink plus the closed-shape fill) are kept exactly; only
their colours change. Each figure graphic is classed pixel by pixel in its stored orientation:
  ink    the game's own drawn pixels: the part's light tone
  fill   closed seams and interior: the part's dark tone
  thin   strokes one or two pixels wide (opened away from the body): weapons, staffs
  hole   enclosed interior components: faces, eyes
and each pixel is given a part (hair, face, tunic, helmet, robe, ...) by figure type, from the
figure's own geometry (head found from the opened body, face on the facing side). Colour comes
from the part, never from the game's attribute bands, so a figure looks the same at every
vertical phase. Mirrored variants are the mirror of the classified base, checked pixel for pixel.
Each figure type has its own sprite palette bank; items and arrows keep bank 0 as in the default.
No outline and no white edge highlight are used; every opaque pixel stays opaque.
"""
from collections import Counter, deque
from functools import lru_cache

def rgb(r, g, b):
    return (r, g, b)               # 3-bit levels, RRRGGGBBB

# Palette bank per figure type (bank 0 stays the default's, used by items and arrows).
BANK = {'robin': 3, 'guard': 4, 'ent': 5, 'bishop': 6, 'witch': 7, 'creature': 8}
BANKS = 9

# part: (ink tone, fill tone)
PARTS = {
    'robin': {
        'hair':  (rgb(1, 1, 0), rgb(2, 1, 1)),     # brown-black hair (73,36,36), darker strands (36,36,0): reads on black
        'face':  (rgb(6, 4, 3), rgb(7, 5, 4)),     # skin, features in a darker skin
        'shade': (rgb(5, 3, 2), rgb(6, 4, 3)),     # the face's lower, shadowed rows in a darker skin
        'hood':  (rgb(1, 6, 1), rgb(0, 4, 0)),     # Lincoln green hood
        'tunic': (rgb(1, 6, 1), rgb(0, 4, 0)),     # and tunic
        'feature': (rgb(3, 1, 1), rgb(3, 1, 1)),   # eye, nose and mouth: the drawing's own ink inside the face
        'legs':  (rgb(3, 5, 1), rgb(2, 3, 0)),     # olive hose
        'boots': (rgb(5, 3, 1), rgb(3, 1, 0)),     # brown boots
        'bow':   (rgb(5, 3, 1), rgb(4, 2, 0)),     # brown bow
        'blade': (rgb(5, 5, 6), rgb(3, 3, 4)),     # steel blade
    },
    'guard': {
        'helmet': (rgb(5, 5, 6), rgb(4, 4, 5)),    # light steel helmet
        'face':   (rgb(5, 3, 2), rgb(7, 5, 4)),    # skin
        'mail':   (rgb(4, 4, 4), rgb(2, 2, 2)),    # grey mail, a shade apart from the helmet: coif, torso, sleeves
        'hose':   (rgb(3, 3, 4), rgb(2, 2, 3)),    # blue-grey mail leggings
        'shield': (rgb(6, 1, 1), rgb(4, 0, 0)),    # the shield, red as one piece, its drawn rim the lighter red
        'boots':  (rgb(3, 2, 1), rgb(2, 1, 0)),    # dark leather
        'weapon': (rgb(5, 3, 1), rgb(3, 2, 0)),    # crossbow / pike wood
    },
    'ent': {
        'leaves': (rgb(2, 6, 1), rgb(1, 4, 0)),    # leafy crown
        'face':   (rgb(2, 1, 0), rgb(3, 2, 1)),    # dark bark face
        'eyes':   (rgb(7, 5, 0), rgb(7, 5, 0)),    # amber eyes
        'bark':   (rgb(5, 3, 1), rgb(3, 2, 0)),    # bark body
        'roots':  (rgb(4, 2, 1), rgb(2, 1, 0)),    # roots and feet
    },
    'bishop': {
        'mitre':   (rgb(7, 6, 1), rgb(5, 4, 0)),   # gold mitre
        'face':    (rgb(5, 3, 2), rgb(7, 5, 4)),   # skin
        'robe':    (rgb(5, 1, 6), rgb(3, 0, 4)),   # rich purple robe
        'trim':    (rgb(7, 6, 1), rgb(5, 4, 0)),   # gold hem
        'crosier': (rgb(7, 6, 1), rgb(5, 4, 0)),   # gold crosier
    },
    'witch': {
        'hood':  (rgb(4, 3, 5), rgb(2, 1, 3)),     # violet hood and cloak, darker folds
        'face':  (rgb(4, 5, 2), rgb(5, 6, 3)),     # pale green face
        'cloak': (rgb(4, 3, 5), rgb(2, 1, 3)),
        'belt':  (rgb(5, 3, 1), rgb(3, 1, 0)),
        'feet':  (rgb(2, 1, 1), rgb(1, 1, 1)),
    },
    'creature': {
        'fur':   (rgb(6, 3, 1), rgb(4, 1, 0)),     # russet fur
        'legs':  (rgb(3, 1, 0), rgb(2, 1, 0)),
    },
}

def palette_indexes():
    """{family: {(part, tone): index 1..15}} and the 9-bit colour of every bank entry."""
    idx = {}; entries = {}
    for fam, parts in PARTS.items():
        seen = {}; n = 0; idx[fam] = {}
        for part, tones in parts.items():
            for tone, col in zip(('ink', 'fill'), tones):
                if col not in seen:
                    n += 1; seen[col] = n
                idx[fam][part, tone] = seen[col]
        if n > 15:
            raise ValueError('%s needs %d colours' % (fam, n))
        for col, i in seen.items():
            entries[16 * BANK[fam] + i] = col
    return idx, entries

INDEX, ENTRIES = palette_indexes()

def nine(col):
    r, g, b = col
    return (r << 6) | (g << 3) | b

def palette_bytes(default_palette):
    """The setup routine's palette data: the default's 48 entries, then the Enhanced banks."""
    out = bytearray(default_palette) + bytearray(2 * 16 * (BANKS - 3))
    for e, col in ENTRIES.items():
        v = nine(col); out[2 * e] = v >> 1; out[2 * e + 1] = v & 1
    return bytes(out)

# Facing of each graphic in its stored orientation: R, L (side, face to that side), F (front),
# B (back, no face), D (lying, head to the right), DL (lying, head to the left).
# Graphic addresses are those of the archive 128K release the build is locked to.
FACING = {
    # Robin, table 0x8C25
    0x8CC9: 'R', 0x8D2C: 'R', 0x8D8F: 'R', 0x8DF2: 'R', 0x8E55: 'R', 0x8EB8: 'R', 0x8F1B: 'R', 0x8F7E: 'R',
    0x8FE1: 'R', 0x9044: 'R', 0x90A7: 'R', 0x910A: 'R', 0x916D: 'F', 0x91D0: 'F', 0x9233: 'B', 0x9296: 'B',
    0x9EF8: 'F', 0x9F18: 'F', 0x9F38: 'R', 0x9F58: 'R', 0x9F78: 'F', 0x9F98: 'R', 0x9FB8: 'R', 0x9FD8: 'R',
    0x9FF8: 'R', 0xA035: 'F', 0xA055: 'R', 0xA075: 'R', 0xA095: 'R', 0xA0B5: 'D',
    # guards and escort, table 0x8C69: crossbow to the right, or shield in front and arm to the left
    0x9611: 'L', 0x9674: 'L', 0x96D7: 'L', 0x973A: 'L', 0x979D: 'L', 0x9863: 'L',
    0x98DB: 'F', 0x98FB: 'F', 0x991B: 'F',
    # witch, table 0x8C8F 6..15: hunched to the left; front; back
    0xA303: 'L', 0xA366: 'L', 0xA3C9: 'L', 0xA42C: 'L', 0xA48F: 'L', 0xA4F2: 'L', 0xA555: 'L', 0xA5B8: 'L',
    0xA61B: 'F', 0xA67E: 'B',
}
BOW = {0x9EF8, 0x9F18, 0x9F38, 0x9F58}
# Where the bow's drawn line lies in the archery frames whose bow is joined to the body by the fill
# The guards' framed shield, held in front of the body in the left-facing frames (read from the ink by eye);
# 979D shows it edge-on. The right-facing frames show the mailed torso and no shield.
SHIELD_BOX = {0x9611: (15, 16, 22, 25), 0x9674: (13, 17, 20, 25), 0x96D7: (13, 17, 20, 25), 0x973A: (14, 17, 21, 25),
              0x979D: (17, 17, 19, 26), 0x9863: (13, 17, 20, 25)}
FACE_BOX = {0xA744: (12, 8, 16, 13)}
CROSIER_BOX = {0xA6E1: (20, 2, 27, 10), 0xA7A7: (20, 2, 27, 10), 0xA744: (21, 2, 27, 9)}
BOW_BOX = {0x9EF8: (0, 0, 47, 6), 0x9F38: (25, 6, 34, 32), 0x9F58: (27, 0, 34, 40)}
# Robin's head in the fighting and archery frames (tiled 48x40 drawings), read from the ink by eye:
# (x0, y0, x1, y1, facing). The bitmap frames find the head from the body's narrowest row.
HEAD = {
    0x9EF8: (10, 7, 19, 14, 'F'), 0x9F18: (11, 12, 18, 18, 'F'), 0x9F38: (11, 11, 19, 17, 'F'),
    0x9F58: (10, 11, 16, 17, 'R'), 0x9F78: (14, 10, 21, 16, 'F'), 0x9F98: (13, 12, 20, 17, 'F'),
    0x9FB8: (12, 11, 19, 17, 'F'), 0x9FD8: (10, 12, 17, 18, 'F'), 0x9FF8: (15, 14, 23, 20, 'F'),
    0xA035: (13, 10, 20, 16, 'F'), 0xA055: (11, 13, 17, 18, 'F'), 0xA075: (10, 12, 17, 18, 'F'),
    0xA095: (10, 12, 16, 18, 'F'), 0x9296: (9, 3, 20, 10, 'B'),
}

def family_of(table, index):
    if table == 0x8C25: return 'robin'
    if table == 0x8C69: return 'guard'
    if index < 3: return 'ent'
    if index < 6: return 'bishop'
    if index < 16: return 'witch'
    return 'creature'

def n4(p):
    x, y = p
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))

def components(pixels):
    left = set(pixels); out = []
    while left:
        p = left.pop(); comp = {p}; q = deque([p])
        while q:
            for r in n4(q.popleft()):
                if r in left:
                    left.discard(r); comp.add(r); q.append(r)
        out.append(comp)
    return out

def opened(body):
    """Erode with a 3x3 square, then dilate: strokes under three pixels wide vanish."""
    sq = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    core = {(x, y) for x, y in body if all((x + dx, y + dy) in body for dx, dy in sq)}
    return {(x + dx, y + dy) for x, y in core for dx, dy in sq} & set(body)

def head_rows(core, top, lo, hi):
    """The neck: the narrowest row of the opened body between top+lo and top+hi."""
    width = {}
    for x, y in core:
        width.setdefault(y, []).append(x)
    best = None
    for y in range(top + lo, top + hi + 1):
        w = (max(width[y]) - min(width[y]) + 1) if y in width else 0
        if w and (best is None or w <= best[0]):
            best = (w, y)
    return best[1] if best else top + hi

def robin_head(head, top, neck, facing, body, inkset):
    """Robin's head painted to a face's contour, inside the head's own pixels:
    hair on the crown and behind; in profile the skin follows the drawn front edge (forehead, nose, chin) a few
    pixels deep; from the front the hair frames both sides; the jaw rows narrow and their corners are shaded;
    the drawing's own ink inside the skin is kept as features (eye, nose, mouth)."""
    out = {}
    ext = {}
    for x, y in head:
        a, b = ext.get(y, (x, x))
        ext[y] = (min(a, x), max(b, x))
    rows = neck - top
    for x, y in head:
        a, b = ext[y]
        up = y - top                   # rows from the crown
        down = neck - y                # rows above the neck
        if facing == 'B' or up < 3 or rows < 5:
            out[x, y] = 'hair'
            continue
        if facing in ('R', 'L'):
            depth = 5 if down >= 2 else 4 if down == 1 else 3
            front = b - x if facing == 'R' else x - a
            face = front < depth
            # under the chin the front edge falls back to the throat: that is the hood's collar, not face
            reach = max((ext[r][1] if facing == 'R' else -ext[r][0]) for r in ext if r < y)
            if face and up >= 5 and (reach - (b if facing == 'R' else -a)) >= 3:
                out[x, y] = 'tunic'
                continue
        else:
            inset = 1 if down >= 2 else 2 if down == 1 else 3
            if up == 3:
                inset = 2              # the hairline rounds the forehead's corners
            face = a + inset <= x <= b - inset
        out[x, y] = 'face' if face else 'hair'
    skin = {p for p, v in out.items() if v == 'face'}
    for x, y in skin:
        down = neck - y
        edge = any(q not in skin for q in n4((x, y)))
        if down == 0 or (down == 1 and edge):
            out[x, y] = 'shade'        # the jaw: chin row and its rounded corners in darker skin
    # features: the drawing's own isolated ink dots inside the skin (an eye, a nostril, the mouth's corner),
    # at most three, nearest the face's middle rows; other ink inside stays the skin's darker tone
    inner = [p for p in skin if out[p] == 'face' and p in inkset and all(q in skin for q in n4(p))
             and sum((p[0] + dx, p[1] + dy) in inkset for dx in (-1, 0, 1) for dy in (-1, 0, 1)) <= 2]
    mid = (top + 3 + neck) / 2
    for p in sorted(inner, key=lambda p: (abs(p[1] - mid), p))[:3]:
        out[p] = 'feature'
    return out


def classify(family, addr, ink, body, seams):
    """{pixel: (part, tone)} for one graphic in its stored orientation (mirror False)."""
    body = set(body); inkset = set(ink)
    core = opened(body) or body
    top = min(y for x, y in core); bottom = max(y for x, y in core)
    left = min(x for x, y in core); right = max(x for x, y in core)
    H = max(1, bottom - top)
    thin = body - core
    thin_parts = [c for c in components(thin) if len(c) >= 5]
    interior = body - inkset - set(seams)
    holes = components(interior)
    face_dir = FACING.get(addr, 'R')
    part = {}

    def headbox(neck):
        hp = [p for p in core if p[1] <= neck]
        xs = [x for x, y in hp]
        return min(xs), max(xs)

    if family == 'robin':
        if face_dir == 'D':
            # lying: head is the right end of the body
            # the head lies at the right: the face is turned up, a profile along the head's upper edge,
            # the crown (right end) and the back of the head (below) in hair, the chin end shaded
            hx0 = right - 7
            colt = {}
            for x, y in body:
                if x >= hx0:
                    colt[x] = min(colt.get(x, y), y)
            for p in body:
                x, y = p
                if x >= hx0:
                    d = y - colt[x]
                    if x >= right - 1 or d >= 4:
                        part[p] = 'hair'
                    elif x == hx0 or d == 3:
                        part[p] = 'shade'
                    else:
                        part[p] = 'face'
                elif x <= left + 6:
                    part[p] = 'boots'
                elif x <= left + 14:
                    part[p] = 'legs'
                else:
                    part[p] = 'tunic'
        else:
            if addr in HEAD:
                hx0, top_h, hx1, neck, face_dir = HEAD[addr]
            else:
                btop = min(y for x, y in body)
                neck = head_rows(core, btop, 6, 11)
                hx0, hx1 = headbox(neck)
                top_h = btop
            waist = neck + round(0.45 * (bottom - neck))
            head = {p for p in body if top_h <= p[1] <= neck and hx0 - 1 <= p[0] <= hx1 + 1}
            part.update(robin_head(head, top_h, neck, face_dir, body, inkset))
            for p in body:
                x, y = p
                if p in head:
                    pass
                elif y <= neck:
                    part[p] = 'tunic'
                elif y >= bottom - 3:
                    part[p] = 'boots'
                elif y > waist:
                    part[p] = 'legs'
                else:
                    part[p] = 'tunic'
            weapon = 'bow' if addr in BOW else 'blade'
            if addr in BOW_BOX:
                bx0, by0, bx1, by1 = BOW_BOX[addr]
                for p in inkset:
                    if bx0 <= p[0] <= bx1 and by0 <= p[1] <= by1 and part.get(p) not in ('hair', 'face', 'shade', 'feature'):
                        part[p] = 'bow'
            for c in (thin_parts if addr in HEAD and addr != 0x9296 else ()):
                if len(c) >= 6 and not all(part.get(p) in ('boots', 'legs') for p in c):
                    for p in c:
                        part[p] = weapon
            for p, col in ink.items():
                if col == 13:
                    part[p] = 'blade'
            # a fill pixel closed between two strokes of the weapon belongs to the weapon
            for p in body - inkset:
                for w in ('blade', 'bow'):
                    if part.get(p) not in ('hair', 'face', 'shade', 'feature') and sum(part.get(q) == w for q in n4(p)) >= 2:
                        part[p] = w
    elif family == 'guard':
        neck = top + round(0.45 * H)
        helmet = top + round(0.24 * H)
        hp = [x for x, y in core if y <= neck]
        cx = (min(hp) + max(hp)) / 2 if hp else (left + right) / 2
        legs = top + round(0.76 * H)
        for p in body:
            x, y = p
            if y < helmet:
                part[p] = 'helmet'
            elif y <= neck:
                front = x >= cx if face_dir == 'R' else x <= cx if face_dir == 'L' else abs(x - cx) <= 3
                part[p] = 'face' if front and face_dir != 'B' else 'mail'
            elif y >= bottom - 1:
                part[p] = 'boots'
            elif y >= legs:
                part[p] = 'hose'
            else:
                part[p] = 'mail'
        for c in thin_parts:
            if len(c) >= 6 and min(y for x, y in c) > helmet:
                for p in c:
                    part[p] = 'weapon'
        if addr in SHIELD_BOX:
            bx0, by0, bx1, by1 = SHIELD_BOX[addr]
            for p in body:
                if bx0 <= p[0] <= bx1 and by0 <= p[1] <= by1:
                    part[p] = 'shield'
    elif family == 'ent':
        # by the game's own tile colours: yellow above the black face is the crown, below it the roots
        blacks = [p for p, c in ink.items() if c == 8]
        fy0 = min(y for x, y in blacks) if blacks else top + 8
        fy1 = max(y for x, y in blacks) if blacks else top + 16
        fx0 = min(x for x, y in blacks) if blacks else 0
        fx1 = max(x for x, y in blacks) if blacks else 0
        near = {p: c for p, c in ink.items()}
        for p in body:
            x, y = p
            if p in near:
                c = near[p]
            else:
                c = Counter(near[q] for q in ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)) if q in near)
                c = max(c, key=lambda k: (c[k], k)) if c else 3
            if fx0 <= x <= fx1 and fy0 <= y <= fy1:
                part[p] = 'face'
            elif c == 6 or c == 14:
                part[p] = 'leaves' if y < fy0 else 'roots'
            else:
                part[p] = 'bark'
        for h in holes:
            if all(fx0 <= x <= fx1 and fy0 <= y <= fy1 for x, y in h):
                for p in h:
                    part[p] = 'eyes'
        for p in body:
            if part[p] == 'face' and p not in inkset and fy0 <= p[1] <= fy0 + 4:
                part[p] = 'eyes'
    elif family == 'bishop':
        neck = top + round(0.42 * H)
        for p in body:
            x, y = p
            if y <= top + 2:
                part[p] = 'mitre'
            elif y >= bottom - 1:
                part[p] = 'trim'
            else:
                part[p] = 'robe'
        for h in holes:
            ys = [y for x, y in h]
            if len(h) >= 4 and max(ys) <= neck + 2 and min(ys) > top + 2:
                xs = sorted(x for x, y in h)
                # the face, or the gap beside the crosier's shaft
                w = xs[-1] - xs[0] + 1
                for p in h:
                    part[p] = 'face' if w >= 3 else 'robe'
        for c in thin_parts:
            if len(c) >= 6:
                for p in c:
                    part[p] = 'crosier'
        if addr in FACE_BOX:
            bx0, by0, bx1, by1 = FACE_BOX[addr]
            for p in interior:
                if bx0 <= p[0] <= bx1 and by0 <= p[1] <= by1:
                    part[p] = 'face'
        if addr in CROSIER_BOX:
            bx0, by0, bx1, by1 = CROSIER_BOX[addr]
            for p in body:
                if bx0 <= p[0] <= bx1 and by0 <= p[1] <= by1:
                    part[p] = 'crosier'
    elif family == 'witch':
        neck = top + round(0.36 * H)
        hp = [x for x, y in core if y <= neck]
        cx = (min(hp) + max(hp)) / 2 if hp else (left + right) / 2
        for p in body:
            x, y = p
            if y <= neck and y >= top + 3:
                if face_dir == 'F':
                    part[p] = 'face' if abs(x - cx) <= 3 else 'hood'
                elif face_dir == 'L':
                    part[p] = 'face' if x <= cx - 1 else 'hood'
                elif face_dir == 'R':
                    part[p] = 'face' if x >= cx + 1 else 'hood'
                else:
                    part[p] = 'hood'
            elif y <= neck:
                part[p] = 'hood'
            elif y >= bottom - 1:
                part[p] = 'feet'
            else:
                part[p] = 'cloak'
        for h in holes:
            if min(y for x, y in h) >= bottom - 4:
                for p in h:
                    part[p] = 'feet'
    else:  # creature
        for p in body:
            part[p] = 'legs' if p[1] >= bottom - 1 else 'fur'
    return {p: (part[p], 'ink' if p in inkset else 'fill') for p in body}

@lru_cache(maxsize=256)
def _base(family, addr, ink_items, body, seams):
    return classify(family, addr, dict(ink_items), body, seams)

def paint(family, addr, tiled, base_ink, base_body, base_seams, pixels, mirror):
    """{pixel: palette index 1..15} for a variant whose default opaque pixels are `pixels`.
    Raises if the Enhanced silhouette would differ from the default's."""
    codes = _base(family, addr, tuple(sorted(base_ink.items())), frozenset(base_body), frozenset(base_seams))
    k = 49 if tiled else 25
    if mirror:
        codes = {(k - x, y): v for (x, y), v in codes.items()}
    if set(codes) != set(pixels):
        raise ValueError('Enhanced silhouette differs at %04X mirror %d' % (addr, mirror))
    table = INDEX[family]
    return {p: table[codes[p]] for p in pixels}
