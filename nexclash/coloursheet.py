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
Colour map: {key: [check, kind, [8 nibbles]]}; nibble 0 = the default colour. Engines that let the
user paint pixels TRANSPARENT (read(..., clear=True); Dizzy 1, Dean 2026-10-14: an enclosed area that
should show the scenery, e.g. inside a handle) add a 4th element: a bit mask (bit 0 =
0x80, as the nibbles) of the key's pixels painted transparent; the sheet shows them grey.
Engines that draw PAINTED CLEAR pixels opaque (write(..., paint_clear=True); Dizzy 1, Dean 2026-10-14:
outlines, "required in MANY future games") give every bit of a plot's graphics bytes, clear bits as
code 0: the sheet shows them grey (transparent) inside the figure's box; a clear bit with a colour
nibble shows and draws in that colour, and painting it grey again sets the nibble back to 0. Only
bits of the graphics bytes a plot draws can be painted (an outline beyond a graphic's byte span needs
a wider graphic in the engine); the read-back reports paint outside them. The layout records it.
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


def owners(comp, clear=False):
    """Composite pixels as drawn (later parts on top, clear pixels draw nothing) ->
    {(x, y): (part index, pixel index)}. clear (paint_clear): the clear pixels too, under every
    opaque pixel (a clear pixel never hides another part's ink or opaque pixel)."""
    own = {}
    for want in ((False, True) if clear else (True,)):
        for n, p in enumerate(comp['parts']):
            for i, (c, r, key, bit, code, dflt) in enumerate(p['pixels']):
                if bool(code) == want:
                    own[(p['dx'] + (p['w'] - 1 - c if p['dmir'] else c),
                         p['dy'] + (p['h'] - 1 - r if p.get('vmir') else r))] = (n, i)
    return own


def write(comps, png, layout_path, rgb16, colours=None, width=WIDTH, unique=False, paint_clear=False):
    """The sheet (png) and its layout (json). colours: an existing map, shown instead of defaults.
    unique (the PAINTING sheet, Dean 2026-10-14): every graphics pixel (key, bit) once - a figure
    sharing graphics with one before it shows only its new pixels (box cropped to them), a figure
    with nothing new is left out; the largest figure of a group comes first, so shared pieces are
    shown on a whole figure. Without unique (the REFERENCE sheet): every figure whole.
    paint_clear: the clear pixels (code 0) inside each figure's box are listed too, paintable (the box
    is still the opaque pixels' box).
    Inside a box only the paintable pixels are grey (or coloured); the rest keeps the background
    colour (Dean 2026-10-14: the sheet shows exactly what can be painted)."""
    from PIL import Image
    cmap = colours or {}
    if unique:
        order = []
        for c in comps:
            if c['group'] not in order:
                order.append(c['group'])
        comps = sorted(comps, key=lambda c: (order.index(c['group']), -len(owners(c))))
    shown = set()
    boxes, x, y, rowh, last = [], 1, SW + 4, 0, None
    for comp in comps:
        own = owners(comp)
        allown = owners(comp, clear=True) if paint_clear else own
        if unique:
            new = {}
            for pos, (n, i) in own.items():
                q = comp['parts'][n]['pixels'][i]
                if (q[2], q[3]) not in shown:
                    new[pos] = (n, i)
            for n, i in new.values():
                q = comp['parts'][n]['pixels'][i]
                shown.add((q[2], q[3]))
            if not new:
                continue
            ox, oy = min(px for px, _ in new), min(py for _, py in new)
            x1, y1 = max(px for px, _ in new) + 1, max(py for _, py in new) + 1
            if paint_clear:                       # clear pixels in the box not shown before
                for (px, py), (n, i) in allown.items():
                    q = comp['parts'][n]['pixels'][i]
                    if not q[4] and ox <= px < x1 and oy <= py < y1 and (q[2], q[3]) not in shown:
                        new[(px, py)] = (n, i)
                        shown.add((q[2], q[3]))
            own = {(px - ox, py - oy): v for (px, py), v in new.items()}
            w, h = x1 - ox, y1 - oy
        else:
            ox = oy = 0
            w = max(px for px, _ in own) + 1
            h = max(py for _, py in own) + 1
            if paint_clear:
                own = {(px, py): v for (px, py), v in allown.items() if 0 <= px < w and 0 <= py < h}
        if comp['group'] != last and last is not None:
            x, y, rowh = 1, y + rowh + 4, 0            # each group starts a new row
        last = comp['group']
        if x + w > width - 1:
            x, y, rowh = 1, y + rowh + 2, 0
        boxes.append((comp, own, x, y, w, h, ox, oy))
        x += w + 2
        rowh = max(rowh, h)
    H = y + rowh + 2
    img = Image.new('RGB', (width, H), BG_RGB)
    for i in range(1, 16):
        for yy in range(1, 1 + SW):
            for xx in range(SW):
                img.putpixel((1 + (i - 1) * (SW + 2) + xx, yy), rgb16[i])
    lay = []
    for comp, own, bx, by, w, h, ox, oy in boxes:
        # grey only where painting is read back: the box's other pixels keep the background colour
        # (a part's gap, a pixel shown on an earlier figure; Dean 2026-10-14: "paintable only")
        for (px, py) in own:
            img.putpixel((bx + px, by + py), TRANSP_RGB)
        for (px, py), (n, i) in own.items():
            c, r, key, bit, code, dflt = comp['parts'][n]['pixels'][i]
            e = cmap.get(key) or [0, 0, [0] * 8]
            if len(e) > 3 and e[3] & (0x80 >> bit):
                continue                                  # painted transparent: stays grey
            v = e[2][bit] or dflt
            if v:                                         # (a clear pixel without a colour: grey)
                img.putpixel((bx + px, by + py), rgb16[v])
        parts = []
        for p in comp['parts']:
            keys = sorted({q[2] for q in p['pixels']})
            ki = {k: n for n, k in enumerate(keys)}
            parts.append(dict(id=str(p['id']), w=p['w'], h=p['h'], dx=p['dx'], dy=p['dy'], dmir=p['dmir'],
                              vmir=p.get('vmir', 0),
                              keys=keys, entries={k: p['entries'][k] for k in keys},
                              pixels=[v for q in p['pixels'] for v in (q[0], q[1], ki[q[2]], q[3], q[4], q[5])]))
        lay.append(dict(group=comp['group'], x=bx, y=by, w=w, h=h, ox=ox, oy=oy, count=comp['count'], parts=parts,
                        show=sorted([px + ox, py + oy] for px, py in own) if unique else None))
    img.save(png)
    out = dict(size=[width, H], palette=[list(c) for c in rgb16],
               colours={k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in cmap.items()},   # the map it shows
               swatches=[[1 + (i - 1) * (SW + 2), 1, i] for i in range(1, 16)], composites=lay)
    if paint_clear:
        out['paint_clear'] = True
    json.dump(out, open(layout_path, 'w'))
    return len(lay)


def _parts_of(comp):
    out = []
    for p in comp['parts']:
        f, keys = p['pixels'], p['keys']
        px = [(f[k], f[k + 1], keys[f[k + 2]], f[k + 3], f[k + 4], f[k + 5]) for k in range(0, len(f), 6)]
        out.append(dict(p, pixels=px))
    return out


def background(c):
    """True = the sheet's background colour (nothing to paint there), not paint."""
    return sum((a - b) ** 2 for a, b in zip(c, BG_RGB)) <= 3 * 12 ** 2


def nearest(c, rgb16):
    """-> (palette index 1-15, or 0 for the transparent grey; squared distance)."""
    best = min((sum((a - b) ** 2 for a, b in zip(c, rgb16[i])), i) for i in range(1, 16))
    dt = sum((a - b) ** 2 for a, b in zip(c, TRANSP_RGB))
    return (0, dt) if dt < best[0] else (best[1], best[0])


def read(png, layout_path, clear=False):
    """Painted sheet -> (colour map {key: [check, kind, 8 nibbles]}, report). Only the pixels a part
    shows are read; a pixel in today's colour keeps its default (nibble 0); clear pixels cannot be
    painted. The layout holds the map the sheet was drawn with; a pixel edits it only when its colour
    differs from what the sheet showed. A key shown twice: a changed colour beats an unchanged one
    (reported, with the figures that take it); two different changes -> the first, reported."""
    from PIL import Image
    lay = json.load(open(layout_path))
    rgb16 = [tuple(c) for c in lay['palette']]
    img = Image.open(png).convert('RGB')
    if list(img.size) != lay['size']:
        raise ValueError('sheet is %dx%d, expected %dx%d (save at the same size, no scaling)'
                         % (tuple(img.size) + tuple(lay['size'])))
    rep = collections.Counter()
    # start from the map the sheet was drawn with: only pixels whose colour CHANGED edit it (a shared
    # pixel may have a different default in each copy, so "looks unpainted" is not "default")
    base = {k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in lay.get('colours', {}).items()}
    ent = {k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in base.items()}
    clr = lambda e, bit: len(e) > 3 and bool(e[3] & (0x80 >> bit))
    changed = set()
    kept = collections.defaultdict(list)     # (key, bit) -> figures where it was left unpainted
    pclear = bool(lay.get('paint_clear'))
    for ci, comp in enumerate(lay['composites']):
        parts = _parts_of(comp)
        own = owners(dict(parts=parts), clear=pclear)
        ox, oy = comp.get('ox', 0), comp.get('oy', 0)
        if comp.get('show') is not None:             # painting sheet: only the pixels shown there
            keep = {tuple(p) for p in comp['show']}
            own = {k: v for k, v in own.items() if k in keep}
        elif pclear:                                 # whole figures: the clear pixels in the box
            own = {(x, y): v for (x, y), v in own.items()
                   if ox <= x < ox + comp['w'] and oy <= y < oy + comp['h']}
        for yy in range(comp['h']):
            for xx in range(comp['w']):
                v = img.getpixel((comp['x'] + xx, comp['y'] + yy))
                if (xx + ox, yy + oy) not in own and not background(v) and nearest(v, rgb16)[0]:
                    rep['paint on pixels no graphic draws (ignored)' if pclear else
                        'painted transparent pixels (ignored)'] += 1
        for (px, py), (n, i) in own.items():
            c, r, key, bit, code, dflt = parts[n]['pixels'][i]
            idx, dist = nearest(img.getpixel((comp['x'] + px - ox, comp['y'] + py - oy)), rgb16)
            if dist > 3 * 40 ** 2:
                rep['pixels not near a palette colour (kept default)'] += 1
                continue
            if not code:                             # a clear pixel (paint_clear): colour nibble or 0
                e = ent.setdefault(key, list(parts[n]['entries'][key]) + [[0] * 8])
                b0 = base.get(key) or [0, 0, [0] * 8]
                if idx == b0[2][bit]:
                    kept[(key, bit)].append(ci)
                    continue
                if (key, bit) in changed:
                    if e[2][bit] != idx:
                        rep['pixels painted differently in two places (first kept)'] += 1
                    continue
                changed.add((key, bit))
                e[2][bit] = idx
                rep['clear pixels painted opaque (outline)' if idx else
                    'painted clear pixels set back to transparent'] += 1
                continue
            if idx == 0 and not clear:
                rep['opaque pixels painted grey (kept default)'] += 1
                continue
            e = ent.setdefault(key, list(parts[n]['entries'][key]) + [[0] * 8])
            b0 = base.get(key) or [0, 0, [0] * 8]
            shown = 0 if clr(b0, bit) else (b0[2][bit] or dflt)        # 0 = shown transparent
            if idx == shown:
                kept[(key, bit)].append(ci)
                continue
            want = ('clear', 0) if idx == 0 else ('', 0 if idx == dflt else idx)
            if (key, bit) in changed:
                if (('clear', 0) if clr(e, bit) else ('', e[2][bit])) != want:
                    rep['pixels painted differently in two places (first kept)'] += 1
                continue
            changed.add((key, bit))
            if idx == 0:
                while len(e) < 4:
                    e.append(0)
                e[3] |= 0x80 >> bit
                e[2][bit] = 0
                rep['pixels painted transparent'] += 1
                continue
            if clr(e, bit):
                e[3] &= ~(0x80 >> bit)
            e[2][bit] = 0 if idx == dflt else idx
            rep['pixels recoloured' if idx != dflt else 'pixels painted back to the default'] += 1
    # the same graphics shown in several figures and painted in only some: the paint applies to all
    spread = {ci for (key, bit), cis in kept.items() if (key, bit) in changed for ci in cis}
    for (key, bit), cis in kept.items():
        if (key, bit) in changed:
            rep['pixels left unpainted in a figure but painted in another copy (paint applies to all)'] += len(cis)
    if spread:
        rep['figures that take paint from another copy: %s' % ', '.join(
            '%s at %d,%d' % (lay['composites'][ci]['group'], lay['composites'][ci]['x'], lay['composites'][ci]['y'])
            for ci in sorted(spread))] = len(spread)
    ent = {k: (e if len(e) > 3 and e[3] else e[:3]) for k, e in ent.items() if any(e[2]) or (len(e) > 3 and e[3])}
    rep['graphics bytes with colours'] = len(ent)
    return ent, rep


def save(ent, path, note):
    json.dump({'note': note, 'entries': {k: [e[0], e[1], ''.join('%X' % n for n in e[2])]
                                         + (['%02X' % e[3]] if len(e) > 3 and e[3] else [])
                                         for k, e in sorted(ent.items())}}, open(path, 'w'), indent=0)


def load(path):
    """-> {key: [check, kind, [8 nibbles](, transparent mask)]}; {} when the file does not exist."""
    import os
    if not os.path.exists(path):
        return {}
    d = json.load(open(path))['entries']
    return {k: [v[0], v[1], [int(ch, 16) for ch in v[2]]] + ([int(v[3], 16)] if len(v) > 3 else [])
            for k, v in d.items()}


# ---------------------------------------------------------------------------------------------
# Pixel states, changes against the sheet's own map, three-way merge, redraw (recolour bundle;
# docs/COLOURS.md RECOLOUR, GPT6 review 2026-10-27). A pixel = (key, bit); its state in a map is
# 'D' (default: nibble 0, not transparent), ('C', n) (colour n) or 'T' (painted transparent).
# ---------------------------------------------------------------------------------------------

def state(cmap, key, bit):
    e = cmap.get(key)
    if not e:
        return 'D'
    if len(e) > 3 and e[3] & (0x80 >> bit):
        return 'T'
    return ('C', e[2][bit]) if e[2][bit] else 'D'


def set_state(cmap, key, bit, st, meta):
    """Set one pixel's state in cmap (in place); meta = [check, kind] for a new entry. An entry left
    with no colour and no transparent bit is removed (a reset to the default deletes the override)."""
    e = cmap.get(key)
    e = [e[0], e[1], list(e[2])] + list(e[3:4]) if e else list(meta[:2]) + [[0] * 8]
    m = e[3] if len(e) > 3 else 0
    e[2][bit] = st[1] if st not in ('D', 'T') else 0
    m = (m | 0x80 >> bit) if st == 'T' else (m & ~(0x80 >> bit))
    e = e[:3] + ([m] if m else [])
    if any(e[2]) or m:
        cmap[key] = e
    else:
        cmap.pop(key, None)


def _copy(cmap):
    return {k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in cmap.items()}


def _fig(lay, ci, px, py):
    c = lay['composites'][ci]
    return '%s figure at %d,%d pixel %d,%d' % (c['group'], c['x'], c['y'], px - c.get('ox', 0), py - c.get('oy', 0))


def changes(png, layout_path, clear=False):
    """What the user changed on a painted sheet, against the map the sheet was drawn with (its
    layout's 'colours'): -> (base map, {(key, bit): new state}, {key: [check, kind]}, conflicts, report).
    A pixel counts as changed only when its colour differs from what the sheet showed. conflicts =
    [((key, bit), [(figure, state), ...])]: one pixel shown in several figures and painted to two
    different states (recolour refuses those). Geometry and rules as read()."""
    from PIL import Image
    lay = json.load(open(layout_path))
    rgb16 = [tuple(c) for c in lay['palette']]
    img = Image.open(png).convert('RGB')
    if list(img.size) != lay['size']:
        raise ValueError('sheet is %dx%d, expected %dx%d (save at the same size, no scaling)'
                         % (tuple(img.size) + tuple(lay['size'])))
    base = {k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in lay.get('colours', {}).items()}
    rep = collections.Counter()
    pclear = bool(lay.get('paint_clear'))
    edits = collections.defaultdict(list)           # (key, bit) -> [(figure, state)]
    meta = {}
    unchanged = collections.defaultdict(int)
    for ci, comp in enumerate(lay['composites']):
        parts = _parts_of(comp)
        own = _shown(comp, parts, pclear)
        ox, oy = comp.get('ox', 0), comp.get('oy', 0)
        for yy in range(comp['h']):
            for xx in range(comp['w']):
                v = img.getpixel((comp['x'] + xx, comp['y'] + yy))
                if (xx + ox, yy + oy) not in own and not background(v) and nearest(v, rgb16)[0]:
                    rep['paint on pixels no graphic draws (ignored)' if pclear else
                        'painted transparent pixels (ignored)'] += 1
        for (px, py), (n, i) in own.items():
            c, r, key, bit, code, dflt = parts[n]['pixels'][i]
            meta.setdefault(key, list(parts[n]['entries'][key][:2]))
            idx, dist = nearest(img.getpixel((comp['x'] + px - ox, comp['y'] + py - oy)), rgb16)
            if dist > 3 * 40 ** 2:
                rep['pixels not near a palette colour (kept default)'] += 1
                continue
            b = state(base, key, bit)
            shown = 0 if b == 'T' else ((b[1] if b != 'D' else 0) or (dflt if code else 0))
            if idx == shown:
                unchanged[(key, bit)] += 1
                continue
            if idx == 0:
                if code and not clear:
                    rep['opaque pixels painted grey (kept default)'] += 1
                    continue
                st = 'T' if code else 'D'
            else:
                st = 'D' if (code and idx == dflt) else ('C', idx)
            edits[(key, bit)].append((_fig(lay, ci, px, py), st))
    chg, conflicts = {}, []
    for kb, lst in edits.items():
        sts = []
        for _, st in lst:
            if st not in sts:
                sts.append(st)
        if len(sts) > 1:
            conflicts.append((kb, lst))
            continue
        chg[kb] = sts[0]
        if unchanged.get(kb):
            rep['pixels left unpainted in a figure but painted in another copy (paint applies to all)'] += unchanged[kb]
    for kb, st in chg.items():
        rep['pixels painted transparent' if st == 'T' else 'pixels set to the default' if st == 'D'
            else 'pixels recoloured'] += 1
    return base, chg, meta, conflicts, rep


def _shown(comp, parts, pclear):
    """The pixels a composite shows on its sheet (as read() and write() place them)."""
    own = owners(dict(parts=parts), clear=pclear)
    ox, oy = comp.get('ox', 0), comp.get('oy', 0)
    if comp.get('show') is not None:
        keep = {tuple(p) for p in comp['show']}
        return {k: v for k, v in own.items() if k in keep}
    if pclear:
        return {(x, y): v for (x, y), v in own.items() if ox <= x < ox + comp['w'] and oy <= y < oy + comp['h']}
    return own


def merge(base, chg, meta, current):
    """Three-way merge on pixel states: base = the sheet's map, chg = the user's changes, current =
    the map the build holds now. -> (merged map, conflicts [((key, bit), base, user, current)]).
    Untouched pixels keep the current state; a change where current still equals base applies; a
    change current already holds is kept; anything else conflicts."""
    out, conflicts = _copy(current), []
    for (key, bit), u in sorted(chg.items()):
        b, c = state(base, key, bit), state(current, key, bit)
        if c == b:
            set_state(out, key, bit, u, meta[key])
        elif c != u:
            conflicts.append(((key, bit), b, u, c))
    return out, conflicts


def redraw(layout_path, cmap, png_out, layout_out):
    """Redraw a sheet from its own layout with another colour map: same size, same figures at the
    same places, same paintable pixels; the new layout records cmap as the map it shows (the next
    painting is read against it). No capture, no emulation."""
    from PIL import Image
    lay = json.load(open(layout_path))
    rgb16 = [tuple(c) for c in lay['palette']]
    img = Image.new('RGB', tuple(lay['size']), BG_RGB)
    for x, y, i in lay['swatches']:
        for yy in range(y, y + SW):
            for xx in range(x, x + SW):
                img.putpixel((xx, yy), rgb16[i])
    pclear = bool(lay.get('paint_clear'))
    for comp in lay['composites']:
        parts = _parts_of(comp)
        own = _shown(comp, parts, pclear)
        ox, oy = comp.get('ox', 0), comp.get('oy', 0)
        for (px, py) in own:
            img.putpixel((comp['x'] + px - ox, comp['y'] + py - oy), TRANSP_RGB)
        for (px, py), (n, i) in own.items():
            c, r, key, bit, code, dflt = parts[n]['pixels'][i]
            st = state(cmap, key, bit)
            if st == 'T':
                continue
            v = (st[1] if st != 'D' else 0) or dflt
            if v:
                img.putpixel((comp['x'] + px - ox, comp['y'] + py - oy), rgb16[v])
    img.save(png_out)
    lay['colours'] = {k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in cmap.items()}
    json.dump(lay, open(layout_out, 'w'))
