"""Colour sheets: the figures an engine turns into sprites, on a PNG the user paints, read back into
a colour map. Every game from Midnight Resistance on (Dean, 2026-10-13; PLAYBOOK 3b / 5).

The engine supplies PARTS (what one plot draws) grouped into COMPOSITES (the parts drawn together
as one figure in a game frame: legs + body, the halves of a vehicle). This module joins the plots
of a frame into composites, picks the fewest composites that show every graphics byte drawn, writes the sheet and reads the painted copy back. Sheet rules (Dean): one PNG pixel = one
Spectrum pixel, multi-part figures joined, a row of 8x8 swatches of the sprite palette (indices
1-15, left to right) at the top, no text; the layout JSON beside it says which part, colour-map key
and bit each pixel is, so the PNG needs nothing else.

Part dict (engine-built):
  id       hashable: the same graphic drawn again has the same id (cover: one per id is enough)
  size     how much of it this drawing shows (e.g. lines); cover wants each id at its max size
  w, h     staging size in pixels (as stored, unmirrored)
  x, y     screen position of this drawing (pixels; composites are found from these)
  mir      1 = drawn mirrored on screen
  vmir     optional: 1 = drawn upside down (shown as drawn; staging line r at h - 1 - r)
  role     optional: which piece of a figure this is (e.g. the plotting routine's caller); a
           role seen again starts a new figure (two explosions or two soldiers that touch stay two)
  repeat   optional: True = this role may appear several times in one figure (a tank's wheels)
  pixels   [(c, r, key, bit, code, default)]: staging column / line, colour-map key (str: one
           graphics byte = 8 pixels), bit 0-7 (0 = leftmost as stored), code 1 ink / 2 opaque
           non-ink / 0 clear, default = today's palette index (0 for clear)
  entries  {key: [check, kind]}: what the engine stores with the key's colours (check bytes etc.)
Colour map: {key: [check, kind, [8 nibbles]]}; nibble 0 = the default colour.
"""
import collections
import json

TRANSP_RGB = (100, 100, 100)        # transparent pixels on the sheet (not a palette colour)
BG_RGB = (150, 150, 175)            # between figures
SW = 8                              # swatch size
WIDTH = 160


def palette_rgb(next8):
    """16 Next palette bytes (RRRGGGBB; blue's third bit = B1 OR B0) -> 16 RGB tuples."""
    out = []
    for v in next8:
        b3 = ((v & 3) << 1) | (1 if v & 3 else 0)
        out.append((((v >> 5) & 7) * 255 // 7, ((v >> 2) & 7) * 255 // 7, b3 * 255 // 7))
    return out


class Collector:
    """Feed it each game frame's parts in plot order (add_frame); composites() -> the sheet's."""

    def __init__(self, family=lambda p: p.get('group'), sig=lambda p: p['id']):
        self.family, self.sig = family, sig
        self.comps, self.maxsize = {}, {}

    def add_frame(self, parts):
        groups = []
        for d in parts:
            self.maxsize[d['id']] = max(self.maxsize.get(d['id'], 0), d['size'])
            box = (d['x'], d['y'], d['x'] + d['w'], d['y'] + d['h'])
            g = groups[-1] if groups else None
            fam = self.family(d)
            # joined: plotted right after a part of the same family, boxes touching (gap <= 1)
            if g and fam is not None and g['fam'] == fam and not _same_role_overlap(d, box, g) and \
                    box[0] <= g['box'][2] + 1 and \
                    g['box'][0] <= box[2] + 1 and box[1] <= g['box'][3] + 1 and g['box'][1] <= box[3] + 1:
                g['parts'].append(d)
                g['box'] = (min(g['box'][0], box[0]), min(g['box'][1], box[1]),
                            max(g['box'][2], box[2]), max(g['box'][3], box[3]))
            else:
                groups.append(dict(fam=fam, parts=[d], box=box))
        for g in groups:
            x0, y0, x1, _ = g['box']
            flip = sum(p['mir'] for p in g['parts']) * 2 > len(g['parts'])     # shown unmirrored
            parts = [dict(p, dx=(x1 - (p['x'] + p['w'])) if flip else p['x'] - x0, dy=p['y'] - y0,
                          dmir=int(bool(p['mir']) != flip), vmir=p.get('vmir', 0)) for p in g['parts']]
            key = tuple((self.sig(p), p['size'], p['dx'], p['dy'], p['dmir'], p['vmir']) for p in parts)
            if key in self.comps:
                self.comps[key]['count'] += 1
            else:
                self.comps[key] = dict(count=1, group=g['parts'][0]['group'], parts=parts)

    def composites(self, group_order=()):
        return choose(list(self.comps.values()), self.maxsize, group_order)


def _same_role_overlap(d, box, g):
    """True = d cannot join g: its role is already in g (unless the role repeats in one figure)."""
    if d.get('role') is None or d.get('repeat'):
        return False
    return any(p.get('role') == d['role'] for p in g['parts'])


def choose(comps, maxsize, group_order=()):
    """Fewest composites that show every colour-map key (graphics byte) any drawing showed (greedy:
    most keys not yet shown, then most parts at their largest drawing, then most often drawn), so a
    partial drawing of a graphic already shown whole adds nothing. Sorted by group, then first part."""
    keys = lambda c: {q[2] for p in c['parts'] for q in p['pixels'] if q[4]}
    full = lambda c: sum(1 for p in c['parts'] if p['size'] == maxsize.get(p['id'], p['size']))
    need = set().union(*[keys(c) for c in comps]) if comps else set()
    out = []
    while need:
        best = max(comps, key=lambda c: (len(keys(c) & need), full(c), c['count']))
        got = keys(best) & need
        if not got:
            break
        out.append(best)
        need -= got
    order = list(group_order)
    out.sort(key=lambda c: (order.index(c['group']) if c['group'] in order else len(order), c['parts'][0]['id']))
    return out


def owners(comp):
    """Composite pixels as drawn (later parts on top, clear pixels draw nothing) ->
    {(x, y): (part index, pixel index)}."""
    own = {}
    for n, p in enumerate(comp['parts']):
        for i, (c, r, key, bit, code, dflt) in enumerate(p['pixels']):
            if code:
                own[(p['dx'] + (p['w'] - 1 - c if p['dmir'] else c),
                     p['dy'] + (p['h'] - 1 - r if p.get('vmir') else r))] = (n, i)
    return own


def write(comps, png, layout_path, rgb16, colours=None, width=WIDTH):
    """The sheet (png) and its layout (json). colours: an existing map, shown instead of defaults."""
    from PIL import Image
    cmap = colours or {}
    boxes, x, y, rowh, last = [], 1, SW + 4, 0, None
    for comp in comps:
        own = owners(comp)
        w = max(px for px, _ in own) + 1
        h = max(py for _, py in own) + 1
        if comp['group'] != last and last is not None:
            x, y, rowh = 1, y + rowh + 4, 0            # each group starts a new row
        last = comp['group']
        if x + w > width - 1:
            x, y, rowh = 1, y + rowh + 2, 0
        boxes.append((comp, own, x, y, w, h))
        x += w + 2
        rowh = max(rowh, h)
    H = y + rowh + 2
    img = Image.new('RGB', (width, H), BG_RGB)
    for i in range(1, 16):
        for yy in range(1, 1 + SW):
            for xx in range(SW):
                img.putpixel((1 + (i - 1) * (SW + 2) + xx, yy), rgb16[i])
    lay = []
    for comp, own, bx, by, w, h in boxes:
        for yy in range(h):
            for xx in range(w):
                img.putpixel((bx + xx, by + yy), TRANSP_RGB)
        for (px, py), (n, i) in own.items():
            c, r, key, bit, code, dflt = comp['parts'][n]['pixels'][i]
            nib = (cmap.get(key) or [0, 0, [0] * 8])[2][bit]
            img.putpixel((bx + px, by + py), rgb16[nib or dflt])
        parts = []
        for p in comp['parts']:
            keys = sorted({q[2] for q in p['pixels']})
            ki = {k: n for n, k in enumerate(keys)}
            parts.append(dict(id=str(p['id']), w=p['w'], h=p['h'], dx=p['dx'], dy=p['dy'], dmir=p['dmir'],
                              vmir=p.get('vmir', 0),
                              keys=keys, entries={k: p['entries'][k] for k in keys},
                              pixels=[v for q in p['pixels'] for v in (q[0], q[1], ki[q[2]], q[3], q[4], q[5])]))
        lay.append(dict(group=comp['group'], x=bx, y=by, w=w, h=h, count=comp['count'], parts=parts))
    img.save(png)
    json.dump(dict(size=[width, H], palette=[list(c) for c in rgb16],
                   swatches=[[1 + (i - 1) * (SW + 2), 1, i] for i in range(1, 16)], composites=lay),
              open(layout_path, 'w'))
    return len(lay)


def _parts_of(comp):
    out = []
    for p in comp['parts']:
        f, keys = p['pixels'], p['keys']
        px = [(f[k], f[k + 1], keys[f[k + 2]], f[k + 3], f[k + 4], f[k + 5]) for k in range(0, len(f), 6)]
        out.append(dict(p, pixels=px))
    return out


def nearest(c, rgb16):
    """-> (palette index 1-15, or 0 for the transparent grey; squared distance)."""
    best = min((sum((a - b) ** 2 for a, b in zip(c, rgb16[i])), i) for i in range(1, 16))
    dt = sum((a - b) ** 2 for a, b in zip(c, TRANSP_RGB))
    return (0, dt) if dt < best[0] else (best[1], best[0])


def read(png, layout_path):
    """Painted sheet -> (colour map {key: [check, kind, 8 nibbles]}, report). Only the pixels a part
    shows are read; a pixel in today's colour keeps its default (nibble 0); clear pixels cannot be
    painted. A key shown twice: a painted colour beats an unpainted one; two different paints ->
    the first, reported."""
    from PIL import Image
    lay = json.load(open(layout_path))
    rgb16 = [tuple(c) for c in lay['palette']]
    img = Image.open(png).convert('RGB')
    if list(img.size) != lay['size']:
        raise ValueError('sheet is %dx%d, expected %dx%d (save at the same size, no scaling)'
                         % (tuple(img.size) + tuple(lay['size'])))
    rep = collections.Counter()
    ent = {}
    for comp in lay['composites']:
        parts = _parts_of(comp)
        own = owners(dict(parts=parts))
        for yy in range(comp['h']):
            for xx in range(comp['w']):
                if (xx, yy) not in own and nearest(img.getpixel((comp['x'] + xx, comp['y'] + yy)), rgb16)[0]:
                    rep['painted transparent pixels (ignored)'] += 1
        for (px, py), (n, i) in own.items():
            c, r, key, bit, code, dflt = parts[n]['pixels'][i]
            idx, dist = nearest(img.getpixel((comp['x'] + px, comp['y'] + py)), rgb16)
            if dist > 3 * 40 ** 2:
                rep['pixels not near a palette colour (kept default)'] += 1
                continue
            if idx == 0:
                rep['opaque pixels painted grey (kept default)'] += 1
                continue
            e = ent.setdefault(key, list(parts[n]['entries'][key]) + [[0] * 8])
            if idx == dflt:
                continue
            if e[2][bit] and e[2][bit] != idx:
                rep['pixels painted differently in two places (first kept)'] += 1
                continue
            if not e[2][bit]:
                e[2][bit] = idx
                rep['pixels recoloured'] += 1
    ent = {k: e for k, e in ent.items() if any(e[2])}
    rep['graphics bytes with colours'] = len(ent)
    return ent, rep


def save(ent, path, note):
    json.dump({'note': note, 'entries': {k: [e[0], e[1], ''.join('%X' % n for n in e[2])]
                                         for k, e in sorted(ent.items())}}, open(path, 'w'), indent=0)


def load(path):
    """-> {key: [check, kind, [8 nibbles]]}; {} when the file does not exist (default colours)."""
    import os
    if not os.path.exists(path):
        return {}
    d = json.load(open(path))['entries']
    return {k: [v[0], v[1], [int(ch, 16) for ch in v[2]]] for k, v in d.items()}
