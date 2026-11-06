"""Nightshade Enhanced set v3: painted by parts, the parts placed where the Amstrad CPC version divides each figure.

Each graphic (header: bit 7 rows reversed, bit 6 mirrored, low nibble the width in bytes; then height; then rows of
(mask, ink) byte pairs, bottom row first) is classed pixel by pixel in its stored orientation:
  line   ink touching the outside (4-neighbours),       detail  ink touching an enclosed hole,
  fill   other ink,                                     hole    non-ink enclosed by the figure (eyes, mouths).
Each figure family names its parts (body, feet, spikes, eyes ...) and gives each a colour. A part is chosen per pixel
from the pixel's class, then from the family's part rules (row bands in the stored orientation: feet, spikes, flame
tips, a scythe blade). The hero has per-graphic part maps (HERO_UP, HERO_LO): hood, face, arms, tunic, belt, buckle,
legs, boots, collar, read off the CPC hero (the CPC divides him hood / face / arms / tunic and belt / legs / feet).
A pixel's code 1-7 = ink + 2 * plane0 + 4 * plane1: ink parts take odd codes, non-ink parts even ones, and families
that share a palette offset (the offsets table is the v2 one, unchanged) share its codes, allocated by colour.
The two planes are stored as graphics in the game's own format (mask 0, ink = the plane's bits) and turned to each
orientation by the game's own flip routine (0xE353) on a copy of memory, so at run time the game's own plot loop
shifts and places them exactly as it places the ink: a flip or a shift cannot misplace a colour, a part map included.
No outlines: an edge of ink takes its part's own colour (no white or light rim); the game's black mask edge stays.
The hero's offsets are 8 + his health colour (12 green, 14 yellow, 15 white): the tunic carries it, and his skin and
mail tint with it (healthy, sallow, sickly).
"""
from . import nightshade_paint_v2 as V2

GTAB = V2.GTAB
FLIPR = V2.FLIPR
FIG_TYPES = V2.FIG_TYPES
ORIENTS = V2.ORIENTS
graphic = V2.graphic
_orient = V2._orient


def C(r, g, b):
    """RRRGGGBB from 0-7, 0-7, 0-3"""
    return r << 5 | g << 2 | b


def _r(a, b):
    return list(range(a, b + 1))


# Regions, in the stored orientation, data rows counted from the bottom row (0). A region is f(x, r, g) with g the
# graphic's facts: g.w (pixels), g.h, g.ink (set), g.main (its largest 4-connected ink part), g.run(x, r) (the length
# of the row's ink run through the pixel).
def top(n):
    return lambda x, r, g: r >= g.h - n


def bottom(n):
    return lambda x, r, g: r < n


def horns(n, run):
    """thin ink in the top n rows: horns, spikes, crown points (a run of at most `run` pixels)"""
    return lambda x, r, g: r >= g.h - n and g.run(x, r) <= run


def upper_half():
    return lambda x, r, g: r >= g.h // 2


def minor():
    """ink outside the graphic's largest connected part (a dome's crescent)"""
    return lambda x, r, g: (x, r) not in g.main


class Facts:
    def __init__(self, ink, w, h):
        self.ink, self.w, self.h = ink, 8 * w, h
        left, best = set(ink), set()
        while left:
            p = left.pop()
            comp, st = {p}, [p]
            while st:
                x, r = st.pop()
                for q in ((x + 1, r), (x - 1, r), (x, r + 1), (x, r - 1)):
                    if q in left:
                        left.discard(q)
                        comp.add(q)
                        st.append(q)
            if len(comp) > len(best):
                best = comp
        self.main = best

    def run(self, x, r):
        a = b = x
        while (a - 1, r) in self.ink:
            a -= 1
        while (b + 1, r) in self.ink:
            b += 1
        return b - a + 1


# Families: (types, palette offset, parts {name: colour}, classes {class: part or None}, holes, rules)
# holes: 'none' leaves every enclosed gap black, 'all' fills them, an int fills holes of at least that many pixels.
# rules: [(part, 'ink' | 'hole', region)], applied in order after the classes (later wins).
# Palette: the 1985 inlay's red and gold, warm browns, green monsters, pale bone; no white rims.
GOLD, DGOLD = C(7, 6, 0), C(5, 4, 0)
BONE, DBONE = C(6, 6, 2), C(4, 4, 1)
RED, DRED = C(6, 1, 0), C(3, 0, 0)
STEEL, DSTEEL = C(5, 5, 2), C(3, 3, 2)
WOOD = C(4, 2, 0)
FAMILIES = [
    # items
    ([0x04, 0x08], 1, {'cover': C(6, 0, 0), 'gilt': GOLD, 'page': C(7, 7, 2)},
     {'fill': 'cover', 'line': 'cover', 'detail': 'gilt', 'hole': 'page'}, 'all', []),                      # bible
    ([0x05, 0x09], 2, {'gold': GOLD, 'shade': DGOLD},
     {'fill': 'gold', 'line': 'gold', 'detail': 'shade', 'hole': None}, 'none', []),                        # crucifix
    ([0x06, 0x0A], 3, {'frame': STEEL, 'glass': C(3, 6, 3), 'glint': C(6, 7, 3)},
     {'fill': 'frame', 'line': 'frame', 'detail': 'frame', 'hole': 'glass'}, 'all', []),                    # mirror
    ([0x07, 0x0B], 4, {'iron': STEEL, 'haft': WOOD},
     {'fill': 'iron', 'line': 'iron', 'detail': 'iron', 'hole': None}, 'none',
     [('haft', 'ink', lambda x, r, g: x <= 13 and x + r <= 18)]),                                          # hammer
    ([0x02, 0x03], 4, {'iron': STEEL, 'haft': WOOD},
     {'fill': 'haft', 'line': 'haft', 'detail': 'iron', 'hole': None}, 'none', []),                         # pickups
    # the four bosses
    ([0x60, 0x61, 0x62, 0x63, 0x90, 0x91], 5, {'shroud': C(5, 6, 3), 'shade': C(3, 4, 3), 'eye': C(7, 1, 0),
                                               'wisp': C(3, 4, 3)},
     {'fill': 'shroud', 'line': 'shroud', 'detail': 'shade', 'hole': 'eye'}, 4,
     [('wisp', 'ink', bottom(14))]),                                                                        # ghost
    ([0x64, 0x65, 0x66, 0x67, 0x92, 0x93], 6, {'robe': C(4, 2, 0), 'fold': C(2, 1, 0), 'face': C(6, 4, 1),
                                               'rope': C(6, 5, 1)},
     {'fill': 'robe', 'line': 'robe', 'detail': 'rope', 'hole': 'face'}, 6, []),                             # mad monk
    ([0x68, 0x69, 0x6A, 0x6B, 0x94, 0x95], 7, {'robe': C(2, 1, 2), 'skull': BONE, 'blade': C(5, 5, 3),
                                               'haft': WOOD},
     {'fill': 'robe', 'line': 'robe', 'detail': 'skull', 'hole': None}, 6, []),                              # reaper
    ([0x6C, 0x6D, 0x6E, 0x6F, 0x96, 0x97], 8, {'bone': BONE, 'joint': DBONE, 'eye': C(6, 0, 0)},
     {'fill': 'bone', 'line': 'bone', 'detail': 'bone', 'hole': None}, 2,
     [('eye', 'hole', top(9))]),                                                                            # skeleton
    # monsters
    (_r(0x70, 0x73), 9, {'skin': C(2, 6, 0), 'dark': C(1, 3, 0), 'feet': C(5, 6, 0), 'maw': C(6, 0, 0)},
     {'fill': 'skin', 'line': 'skin', 'detail': 'dark', 'hole': 'maw'}, 6,
     [('feet', 'ink', bottom(4))]),                                                                         # gremlin
    (_r(0x4C, 0x4F), 9, {'skin': C(2, 6, 0), 'dark': C(1, 3, 0), 'feet': C(5, 6, 0), 'maw': C(6, 0, 0)},
     {'fill': 'skin', 'line': 'skin', 'detail': 'feet', 'hole': 'maw'}, 6, []),                              # slug
    (_r(0x74, 0x77), 10, {'flesh': C(7, 3, 0), 'tip': C(7, 6, 0), 'dark': C(4, 0, 0), 'glow': C(7, 6, 0)},
     {'fill': 'flesh', 'line': 'flesh', 'detail': 'flesh', 'hole': 'glow'}, 5,
     [('tip', 'ink', horns(8, 3)), ('tip', 'ink', bottom(3))]),                                             # spiky head
    (_r(0x88, 0x8B), 10, {'flesh': C(7, 3, 0), 'tip': C(7, 6, 0), 'dark': C(4, 0, 0), 'glow': C(7, 6, 0)},
     {'fill': 'flesh', 'line': 'flesh', 'detail': 'dark', 'hole': 'glow'}, 6,
     [('tip', 'ink', top(9))]),                                                                             # fire demon
    (_r(0x44, 0x47), 10, {'flesh': C(7, 3, 0), 'tip': C(7, 6, 0), 'dark': C(4, 0, 0), 'glow': C(7, 6, 0)},
     {'fill': 'flesh', 'line': 'tip', 'detail': 'tip', 'hole': None}, 'none', []),                           # explosion
    (_r(0x78, 0x7B), 11, {'hide': C(6, 1, 0), 'horn': C(6, 6, 2), 'dark': C(3, 0, 0), 'feet': C(4, 2, 0),
                          'eye': C(7, 6, 0)},
     {'fill': 'hide', 'line': 'hide', 'detail': 'dark', 'hole': None}, 2,
     [('feet', 'ink', bottom(3)), ('horn', 'ink', horns(8, 4)), ('eye', 'hole', upper_half())]),                                           # horned demon
    (_r(0x7C, 0x7F), 11, {'hide': C(6, 1, 0), 'horn': C(6, 6, 2), 'dark': C(3, 0, 0), 'feet': C(4, 2, 0),
                          'eye': C(7, 6, 0)},
     {'fill': 'hide', 'line': 'hide', 'detail': 'dark', 'hole': None}, 2,
     [('feet', 'ink', bottom(3)), ('horn', 'ink', horns(6, 3)), ('eye', 'hole', upper_half())]),                                           # crowned imp
    # magic and missiles
    (_r(0x30, 0x33) + _r(0x50, 0x53) + [0x8C], 13, {'swirl': C(4, 6, 3), 'core': C(6, 7, 3)},
     {'fill': 'swirl', 'line': 'swirl', 'detail': 'core', 'hole': None}, 'none', []),                        # swirls
    (_r(0x34, 0x3F) + _r(0x54, 0x5F) + [0x8D, 0x8E, 0x8F], 2, {'gold': GOLD, 'shade': DGOLD},
     {'fill': 'gold', 'line': 'gold', 'detail': 'shade', 'hole': None}, 'none', []),                         # shots
    (_r(0x40, 0x43) + _r(0x48, 0x4B), 0, {'jelly': C(3, 6, 2), 'rim': C(1, 4, 1), 'nucleus': C(6, 7, 1)},
     {'fill': 'jelly', 'line': 'jelly', 'detail': 'rim', 'hole': 'nucleus'}, 'none',
     [('rim', 'ink', minor()), ('rim', 'ink', bottom(3))]),                                                 # jellies
    (_r(0x0C, 0x0F) + _r(0x80, 0x87), 13, {'swirl': C(4, 6, 3), 'core': C(6, 7, 3)},
     {'fill': 'core', 'line': 'swirl', 'detail': 'core', 'hole': None}, 'none', []),                         # sparkles
]
# the reaper's scythe: the blade at the top left of the frames that carry it, its haft below
for _fam in FAMILIES:
    if _fam[0][0] == 0x68:
        _fam[5].extend([('blade', 'ink', lambda x, r, g: r >= g.h - 6 and x <= 12)])

# ---------------------------------------------------------------------------------------------------------------
# The hero
# ---------------------------------------------------------------------------------------------------------------
# codes in his offsets: ink T tunic (health), A skin, S leather, H mail, K buckle (mail); non-ink B belt, R collar (mail),
# F the face's shading (its gaps below the brow)
HERO_CODE = {'T': 1, 'A': 3, 'S': 5, 'H': 7, 'K': 7, 'B': 2, 'R': 4, 'F': 6}
HERO_INK = 'TASHK'


def hero_colours(k):
    """{code: colour} for health colour k (7 white: healthy, 6 yellow: infected, 4 green: near death)"""
    tunic = {7: C(7, 7, 3), 6: C(7, 7, 0), 4: C(2, 7, 0)}[k]
    skin = {7: C(7, 5, 1), 6: C(6, 5, 1), 4: C(5, 6, 2)}[k]
    shade = {7: C(5, 3, 1), 6: C(4, 3, 1), 4: C(3, 4, 1)}[k]
    mail = C(5, 5, 2)
    leather = C(4, 2, 0)
    collar = mail                   # the collar is the coif's own mail (owner, 2026-11-04: no red collar)
    return {1: tunic, 3: skin, 5: leather, 7: mail, 2: C(3, 1, 0), 4: collar, 6: shade}


# The hero's part maps follow the artist's drawn lines, not rows or boxes (owner and Dean Woodyatt, 2026-11-04).
# Each graphic's ink falls into regions closed off by its mask lines (4-connected ink, work/v3/comps.py shows them).
# A map names regions by a seed pixel (x, data row from the bottom) in the stored orientation (splits apply in
# order, later wins): hood (mail), skin
# (forearms, hands, the face's ink); every other region is tunic: the torso with its sleeves, up to the line where the
# arm's own region starts. Where one drawn region holds two parts with no closed line between them, a split gives the
# rule, placed where the drawn shape changes: the back views' shoulder band (the solid band under the hood, above the
# point where the sleeve and back lines start, left of the hood's diagonal hem) is the coif's mail; 16's raised arm
# leaves that region along the arm strip's own edge lines (x <= 5); 2E's chin is the narrow block above the torso.
# collar = the collar's mask line under the hood (the coif's mail colour); face = the face's drawn outline, its gaps
# below the brow shaded; front = a silver buckle shows (else the belt's back, leather). The torso's lowest row, its
# narrow tip, is the buckle, and the mask beside and under it the belt. c: the hood row of the old split, kept for the
# negative that drops the maps.
FRONT_HOOD = [(12, 24), (10, 23), (13, 23)]
FRONT_FACE = [(11, 16), (14, 16), (13, 15)]
BACK_HOOD = [(15, 23), (13, 22), (16, 22)]
def _band(xs):
    """the back's shoulder band under the hood: rows 10 and up of the region, and row 9 up to the sleeve's vertical line
    (column xs), which starts just below it"""
    return ((8, 14), lambda x, r: x <= 14 and (r >= 10 or (r == 9 and x <= xs)), 'H')


_BAND = _band(10)
HERO_UP = {
    0x1E: dict(c=13, hood=FRONT_HOOD, skin=FRONT_FACE + [(21, 13), (1, 12)], face=(11, 15, 13, 17),
               collar=(5, 15, 12, 12), front=True),
    0x28: dict(c=13, hood=FRONT_HOOD, skin=FRONT_FACE + [(2, 8), (19, 7)], face=(11, 15, 13, 17),
               collar=(5, 15, 12, 12), front=True),
    0x29: dict(c=13, hood=FRONT_HOOD, skin=FRONT_FACE + [(2, 7), (19, 7)], face=(11, 15, 13, 17),
               collar=(5, 15, 12, 12), front=True),
    0x2A: dict(c=13, hood=FRONT_HOOD, skin=FRONT_FACE + [(20, 9), (3, 8)], face=(11, 15, 13, 17),
               collar=(5, 15, 12, 12), front=True),
    0x2B: dict(c=13, hood=FRONT_HOOD, skin=FRONT_FACE + [(19, 9), (4, 6)], face=(11, 15, 13, 17),
               collar=(5, 15, 12, 12), front=True),
    0x2E: dict(c=12, hood=[(10, 24), (8, 23), (11, 23)], skin=[(5, 16), (7, 16), (20, 8), (3, 7)],
               splits=[((7, 12), lambda x, r: r >= 12, 'A')], face=(5, 9, 12, 16), collar=None, front=True),
    0x2F: dict(c=12, hood=[(11, 24), (9, 23)], skin=[(16, 16), (18, 15), (18, 8), (3, 6)],
               face=(16, 18, 14, 16), collar=(6, 14, 11, 11), front=True),
    0x16: dict(c=10, hood=BACK_HOOD, skin=[(22, 12), (20, 7)],
               splits=[_BAND, ((8, 14), lambda x, r: x <= 5, 'A')], face=None, collar=None, front=False),
    0x20: dict(c=10, hood=BACK_HOOD, skin=[(1, 11), (21, 7), (18, 6)], splits=[_BAND], face=None, collar=None,
               front=False),
    0x21: dict(c=10, hood=BACK_HOOD, skin=[(1, 9), (20, 7)], splits=[_BAND], face=None, collar=None, front=False),
    0x22: dict(c=10, hood=BACK_HOOD, skin=[(2, 8), (19, 7), (18, 6)], splits=[_BAND], face=None, collar=None,
               front=False),
    0x23: dict(c=10, hood=BACK_HOOD, skin=[(3, 7)], splits=[_band(11)], face=None, collar=None, front=False),
    0x26: dict(c=11, hood=[(14, 23), (12, 22), (15, 22)], skin=[(9, 15), (11, 14), (7, 13), (20, 8), (2, 7), (18, 7)],
               splits=[((13, 12), lambda x, r: r >= 10, 'H')], face=(7, 11, 12, 15), collar=None, front=True),
    0x27: dict(c=10, hood=[(13, 24), (11, 23), (14, 23)], skin=[(1, 9), (20, 7)],
               splits=[((18, 11), lambda x, r: r == 9 and x <= 17, 'H')], face=None, collar=(10, 14, 9, 9),
               front=False),
}
# Lower graphics: the skirt is its own region (tunic); legs and boots by region, a leg region that runs into its boot
# split where it widens from the ankle into the foot.
HERO_LO = {
    0x10: dict(skin=[(6, 9), (11, 8)], boots=[(9, 4)]),
    0x18: dict(skin=[(6, 9), (10, 7)], boots=[(9, 6)], splits=[((9, 6), lambda x, r: r >= 6, 'A')]),
    0x11: dict(skin=[(7, 9), (9, 9), (14, 7)], boots=[(7, 5)]),
    0x12: dict(skin=[(8, 9)], boots=[(4, 6), (15, 7)], splits=[((8, 9), lambda x, r: r <= 7, 'S')]),
    0x13: dict(skin=[(5, 12), (16, 8)], boots=[(1, 8), (12, 6)]),
    0x19: dict(skin=[(7, 9), (12, 8)], boots=[(6, 7)],
               splits=[((12, 8), lambda x, r: r <= 7, 'S'), ((6, 7), lambda x, r: r >= 7, 'A')]),
    0x1A: dict(skin=[(6, 9)], boots=[(4, 8), (12, 7)], splits=[((4, 8), lambda x, r: r >= 8, 'A')]),
    0x1B: dict(skin=[(3, 10), (6, 10), (18, 10), (1, 9), (16, 9)], boots=[],
               splits=[((1, 9), lambda x, r: r <= 6, 'S'), ((16, 9), lambda x, r: r <= 6, 'S')]),
}
HERO_TYPES = _r(0x10, 0x2F)
HERO_LO_T = [t for t in _r(0x10, 0x1D) if t not in (0x16, 0x17)]
HERO_UP_T = _r(0x20, 0x2F) + [0x16, 0x17, 0x1E, 0x1F]


def _inside(p, b):
    return b is not None and b[0] <= p[0] <= b[1] and b[2] <= p[1] <= b[3]


def ink_regions(ink):
    """{pixel: region (frozenset)}: the ink's 4-connected regions"""
    left, of = set(ink), {}
    while left:
        p = left.pop()
        comp, st = {p}, [p]
        while st:
            x, r = st.pop()
            for q in ((x + 1, r), (x - 1, r), (x, r + 1), (x, r - 1)):
                if q in left:
                    left.discard(q)
                    comp.add(q)
                    st.append(q)
        fc = frozenset(comp)
        for q in comp:
            of[q] = fc
    return of


def hero_parts(t, ink, mask, outside, w, h, maps=True):
    """{pixel: part letter} for a hero graphic. maps=False: no part maps (the v2 split: hood above, tunic below)."""
    parts = {}
    if t in HERO_UP:
        m = HERO_UP[t]
        if not maps:
            return {p: ('H' if p[1] >= m['c'] else 'T') for p in ink}
        reg = ink_regions(ink)
        for p in ink:
            parts[p] = 'T'
        for seeds, part in ((m['hood'], 'H'), (m['skin'], 'A')):
            for s in seeds:
                for q in reg[s]:
                    parts[q] = part
        for s, pred, part in m.get('splits', ()):
            for q in reg[s]:
                if pred(*q):
                    parts[q] = part
        tor = [p for p, v in parts.items() if v == 'T']
        if tor:
            br = min(r for x, r in tor)
            bx = [x for x, r in tor if r == br]
            if len(bx) <= 4:
                x0, x1 = min(bx), max(bx)
                for x in bx:
                    parts[(x, br)] = 'K' if m['front'] else 'S'
                for p in mask:
                    if br - 1 <= p[1] <= br and x0 - 3 <= p[0] <= x1 + 3:
                        parts[p] = 'B'
        if m['face']:
            x0, x1, r0, r1 = m['face']
            for p in mask:
                if x0 <= p[0] <= x1 and r0 <= p[1] < r1 and p not in outside:
                    parts[p] = 'F'
        if m['collar']:
            for p in mask:
                if _inside(p, m['collar']) and p not in outside:
                    parts[p] = 'R'
        return parts
    if t in HERO_LO:
        m = HERO_LO[t]
        if not maps:
            return {p: 'T' for p in ink}
        reg = ink_regions(ink)
        for p in ink:
            parts[p] = 'T'
        for seeds, part in ((m['skin'], 'A'), (m['boots'], 'S')):
            for s in seeds:
                for q in reg[s]:
                    parts[q] = part
        for s, pred, part in m.get('splits', ()):
            for q in reg[s]:
                if pred(*q):
                    parts[q] = part
        return parts
    return {p: 'T' for p in ink}


# ---------------------------------------------------------------------------------------------------------------
# Codes and the palette
# ---------------------------------------------------------------------------------------------------------------
FAM_OF = {}
for _i, _f in enumerate(FAMILIES):
    for _t in _f[0]:
        FAM_OF[_t] = _i


def _allocate():
    """{offset: {('ink' | 'hole', colour): code}}: per offset, ink colours take 1, 3, 5, 7 and hole colours 2, 4, 6,
    in the order the families name them (a family's first part, its body, takes code 1)."""
    alloc = {}
    for types, off, parts, cls, holes, rules in FAMILIES:
        a = alloc.setdefault(off, {})
        kinds = {}
        for c_, part in cls.items():
            if part is not None:
                kinds.setdefault(part, set()).add('hole' if c_ == 'hole' else 'ink')
        for part, kind, reg in rules:
            kinds.setdefault(part, set()).add(kind)
        for part in parts:
            for kind in sorted(kinds.get(part, ())):
                key = (kind, parts[part])
                if key not in a:
                    free = [c_ for c_ in ((1, 3, 5, 7) if kind == 'ink' else (2, 4, 6)) if c_ not in a.values()]
                    if not free:
                        raise ValueError('palette offset %d: too many %s colours' % (off, kind))
                    a[key] = free[0]
    return alloc


ALLOC = _allocate()


def palette():
    pal = bytearray(256)
    for off, a in ALLOC.items():
        if off in (12, 14, 15):
            raise ValueError('offset %d is reserved for the hero' % off)
        for (kind, col), code in a.items():
            pal[16 * off + code] = col
    for k in (4, 6, 7):
        for code, col in hero_colours(k).items():
            pal[16 * (8 + k) + code] = col
    return bytes(pal)


def offsets():
    """the v2 table: the hook page carries it in both builds"""
    t = V2.offsets()
    for types, off, parts, cls, holes, rules in FAMILIES:
        for x in types:
            if t[x] != off:
                raise ValueError('type %02X moved offset' % x)
    return t


def classes(ink, mask, w, h, holes):
    """-> ({pixel: class}, outside set). Classes as in v2: line, fill, detail (ink); hole (enclosed non-ink, filled
    per `holes`); masked pixels not classed are returned in `mask` for part rules."""
    W, H = 8 * w, h
    st, seen = [(-1, -1)], {(-1, -1)}
    while st:
        x, r = st.pop()
        for q in ((x + 1, r), (x - 1, r), (x, r + 1), (x, r - 1)):
            if -1 <= q[0] <= W and -1 <= q[1] <= H and q not in seen and q not in ink and q not in mask:
                seen.add(q)
                st.append(q)
    outside = set(seen)

    def n4(x, r):
        return ((x + 1, r), (x - 1, r), (x, r + 1), (x, r - 1))
    cand, edge = set(), set()
    for x in range(W):
        for r in range(H):
            p = (x, r)
            if p in ink or p in outside:
                continue
            if p in mask and any(q in outside for q in n4(x, r)):
                edge.add(p)
                continue
            cand.add(p)
    out_e = outside | edge
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
        if holes == 'all' or (holes != 'none' and len(comp) >= holes):
            hole |= comp
    cl = {}
    for p in ink:
        x, r = p
        if any(q in out_e for q in n4(x, r)):
            cl[p] = 'line'
        elif any(q in hole for q in n4(x, r)):
            cl[p] = 'detail'
        else:
            cl[p] = 'fill'
    for p in hole:
        cl[p] = 'hole'
    return cl, out_e


def paint_one(mem, t, maps=True):
    """-> (w, h, header, {pixel: code}) for type t"""
    g, w, h = graphic(mem, t)
    ink, mask = set(), set()
    for r in range(h):
        for c in range(w):
            m, v = mem[g + 2 + 2 * (r * w + c)], mem[g + 2 + 2 * (r * w + c) + 1]
            for b in range(8):
                if v & (0x80 >> b):
                    ink.add((8 * c + b, r))
                elif m & (0x80 >> b):
                    mask.add((8 * c + b, r))
    codes = {}
    if t in HERO_TYPES:
        cl, out_e = classes(ink, mask, w, h, 'none')
        for p, part in hero_parts(t, ink, mask, out_e, w, h, maps).items():
            codes[p] = HERO_CODE[part]
        return g, w, h, mem[g], codes
    fi = FAM_OF.get(t)
    if fi is None:
        cl, out_e = classes(ink, mask, w, h, 'none')
        return g, w, h, mem[g], {p: 1 for p in ink}
    types, off, parts, clmap, holes, rules = FAMILIES[fi]
    cl, out_e = classes(ink, mask, w, h, holes)
    part = {p: clmap[c_] for p, c_ in cl.items() if clmap.get(c_)}
    f = Facts(ink, w, h)
    for name, kind, reg in rules:
        for p in (ink if kind == 'ink' else [q for q, c_ in cl.items() if c_ == 'hole']):
            if reg(p[0], p[1], f):
                part[p] = name
    a = ALLOC[off]
    for p, name in part.items():
        if p not in ink and p not in mask and off != 5:
            continue                # a see-through gap (the scenery shows there) stays so; the ghost's eyes as in v2
        codes[p] = a[('ink' if p in ink else 'hole', parts[name])]
    return g, w, h, mem[g], codes


def paint_all(mem, maps=True):
    """-> {g: (w, h, base header byte, codes, first type)} for every figure graphic, keyed by its address"""
    res = {}
    for t in FIG_TYPES:
        g, w, h = graphic(mem, t)
        if g in res or not (1 <= w <= 5 and 1 <= h <= 64):
            continue
        g, w, h, hdr, codes = paint_one(mem, t, maps)
        res[g] = (w, h, hdr, codes, t)
    return res


def planes(mem, maps=True):
    """-> {g: {orientation: (plane0 data, plane1 data)}} in the game's graphic format, and the paint"""
    paint = paint_all(mem, maps)
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
