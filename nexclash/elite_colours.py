"""Elite colours: the colour sheet and recolour for the 'elite' engine (games/elite.md ## M4, docs/COLOURS.md RECOLOUR).

What can be coloured: each ship model (the blueprint IY points at while its lines are drawn: shipcol[IY low byte] in the
alt ROM) and six draw categories (sun, planet, stars, messages, lasers, sights: the immediate of a labelled
`nextreg 0x7F,n` in the hooks). One colour per figure (design detail 1: a model is one colour), so each figure is ONE
colour-map key, bit 0: painting any pixel of a figure colours all of it (coloursheet.read: a changed copy of a key
beats the unchanged ones); two colours in one figure -> the first, reported.
Colours are Layer 2 bytes (RRRGGGBB) from PAL8: nibble k = PAL8[k - 1]; nibble 0 = the build's default (the asm's).
Only the alt ROM image (bank 12) changes, which the game never reads as data.
Figures on the sheet: ship drawings captured from the five recordings (probe ship_shapes.py, the biggest whole drawing
of each model, picked by eye where the biggest was the launch tunnel or a tangle; docs/profiles/elite_shapes.json.gz) and drawn shapes for the categories.
"""
import hashlib
import json
import math
import os

from . import coloursheet as cs

PAL8 = (0xFF, 0xE0, 0xFC, 0x4B, 0x1F, 0x1C, 0xF0, 0xE7, 0x5F, 0x7C, 0xB6, 0xA3, 0xEF, 0x3B, 0xDB)
BLUEPRINTS = tuple((0x61E3 + 23 * n) & 0xFF for n in range(23))      # IY low bytes (asm shipcol)
CATS = (('SUN', ('cs_sun',)), ('PLANET', ('cs_pla1', 'cs_pla2')), ('STARS', ('cs_sta',)),
        ('MESSAGES', ('cs_msg',)), ('LASERS', ('cs_las',)), ('SIGHTS', ('cs_sig',)))
KIND_SHIP, KIND_CAT = 1, 2
KEYS = 'elite-figure-v1'            # what a key means: S<lo> = shipcol[lo], C<name> = that category's sites; bit 0
ROM_BASE = 0x2000                   # bank 12 offset 0 = alt ROM address 0x2000
_HERE = os.path.dirname(os.path.abspath(__file__))
SHAPES = os.path.join(_HERE, '..', 'docs', 'profiles', 'elite_shapes.json')


def ship_key(lo):
    return 'S%02X' % lo


def sites(syms):
    """{key: [alt ROM addresses of its colour byte]}."""
    out = {ship_key(lo): [syms['shipcol'] + lo] for lo in BLUEPRINTS}
    for name, labels in CATS:
        out['C' + name] = [syms[s] + 3 for s in labels]        # ED 91 7F nn
    return out


def resolve(cmap, key):
    """Painted colour byte for key, or None (default)."""
    e = cmap.get(key)
    if not e or not e[2][0]:
        return None
    return PAL8[e[2][0] - 1]


def apply(img, base, cmap, syms, defaults):
    """img: bytearray of ROM bytes starting at address `base`; defaults {key: byte} (the asm's). Sets every colour byte
    (painted or default). Unknown keys are ignored (counted)."""
    used = 0
    for key, addrs in sites(syms).items():
        v = resolve(cmap, key)
        used += v is not None
        for a in addrs:
            img[a - base] = defaults[key] if v is None else v
    return used, len([k for k in cmap if k not in sites(syms)])


def defaults_of(code, base, syms):
    """{key: default byte} read from the assembled ROM code (first site of each key)."""
    d = {}
    for key, addrs in sites(syms).items():
        vals = {code[a - base] for a in addrs}
        if len(vals) != 1:
            raise ValueError('%s: its sites hold different colours %s' % (key, sorted(vals)))
        d[key] = vals.pop()
    return d


def colour_identity(peek):
    """Keys follow the blueprint records (0x61E3, 23 x 23 bytes: the same in all five snapshots; 0xA000-0xA7FF is
    not, so code is not used)."""
    blue = bytes(peek(a) for a in range(0x61E3, 0x61E3 + 23 * 23))
    return {'schema': 1, 'game': 'elite', 'engine': 'elite', 'keys': KEYS,
            'inputs': hashlib.md5(blue).hexdigest(), 'geometry': None}


def rgb16():
    return cs.palette_rgb(bytes((0,) + PAL8))


def _ring(r, fill=False):
    pts = set()
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            d = math.hypot(x, y)
            if (d <= r + 0.3) if fill else (r - 0.7 <= d <= r + 0.3):
                pts.add((x + r, y + r))
    return sorted(pts)


def _cat_shapes():
    """Drawn stand-ins for the categories (no capture needed): sun disc, planet ring, a star field, a text bar,
    two laser lines, the sights cross."""
    stars = [(3, 2), (17, 5), (9, 11), (26, 9), (5, 19), (21, 17), (14, 23), (29, 24)]
    laser = sorted({(int(x), int(y)) for t in range(41) for x, y in ((t * 0.6, 24 - t * 0.55), (40 - t * 0.6, 24 - t * 0.55))})
    sights = [(x, 6) for x in range(0, 5)] + [(x, 6) for x in range(8, 13)] + [(6, y) for y in range(0, 4)] + \
             [(6, y) for y in range(9, 13)]
    msg = [(x, y) for y in range(0, 7) for x in range(0, 40) if (x // 6 + y) % 3 != 2 and x % 6 != 5]
    return [('SUN', _ring(10, True)), ('PLANET', _ring(14)), ('STARS', stars), ('MESSAGES', msg),
            ('LASERS', laser), ('SIGHTS', sights)]


def figures(shapes=None):
    """[(key, kind, check, [(x, y)])] in sheet order: categories, then ships by blueprint number."""
    shapes = cs.load_layout(SHAPES) if shapes is None else shapes
    out = [('C' + n, KIND_CAT, 0, px) for n, px in _cat_shapes()]
    for n, lo in enumerate(BLUEPRINTS):
        s = shapes.get('%04X' % (0x61E3 + 23 * n))
        if s:
            out.append((ship_key(lo), KIND_SHIP, lo, [tuple(p) for p in s['px']]))
    return out


def comps(defaults, shapes=None):
    res = []
    for g, (key, kind, check, px) in enumerate(figures(shapes)):
        d = PAL8.index(defaults[key]) + 1 if defaults[key] in PAL8 else 1
        w = max(x for x, y in px) + 1
        h = max(y for x, y in px) + 1
        part = dict(id=key, size=len(px), w=w, h=h, dx=0, dy=0, dmir=0, vmir=0,
                    pixels=[(x, y, key, 0, 1, d) for x, y in px], entries={key: [check, kind]})
        res.append(dict(count=1, group=0 if kind == KIND_CAT else 1, parts=[part]))
    return res


def write_sheets(out_dir, name, defaults, cmap, identity, shapes=None):
    """<name>_PAINTING_SPRITES.png and <name>_REFERENCE_ALL_SPRITES.png (+ layouts): every figure whole on both."""
    os.makedirs(out_dir, exist_ok=True)
    c = comps(defaults, shapes)
    res = {}
    for kind in ('PAINTING_SPRITES', 'REFERENCE_ALL_SPRITES'):
        png = os.path.join(out_dir, '%s_%s.png' % (name, kind))
        lay = os.path.join(out_dir, '%s_%s_layout.json' % (name, kind))
        cs.write(c, png, lay, rgb16(), colours=cmap, width=256, unique=False, identity=identity)
        res[kind] = png
    return res
