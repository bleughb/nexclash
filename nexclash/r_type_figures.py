"""R-Type figure IDs, families and identification sheets (owner request 2026-11-16).

Every figure on the colour sheets gets a stable ID, so the user can name it and, later, choose its
place in the display stack (layer). Written by `r_type_colour.py sheets` next to the colour sheets:

  r_type_figures.json            the registry: every figure and family, all levels (read back on the
                                 next run, so IDs, names and layers survive a longer recording)
  r_type_<LEVEL>_IDENTIFY.png    every figure of the level, 2x, in today's colours, its ID beside it;
                                 for looking only (never read back), so text is allowed

IDs. A figure = one game object as drawn (its plots: graphic, size, place, flip; the colour sheets'
composites). Its signature is a hash of those plots and the level. Its ID is L<level>-<n> (L0 = the
TEXT level): n is handed out once, in drawing order of first appearance, and kept forever for that
signature; a new recording adds numbers after the highest one and never renumbers.
A family = the figures of one level that share any graphic (an object's animation frames, a ship
and its turret drawn from the same art): L<level>-F<n>, kept by matching graphics with the previous
run. A family is the unit a user names and layers; a figure may override both.

Registry format (schema 1), designed for an interactive page to read and write:
  game, schema, note, scale (identification sheet magnification), palette (16 RGB),
  layers: the layer choices (ids and labels; "original" = as the game draws, the default),
  levels: {LEVEL: {level byte, identify sheet file, width, height, figures [ids in sheet order]}},
  families: {Fid: {level, name, layer, figures [ids], graphics [hex addresses]}},
  figures: {id: {sig, level, family, name, layer, count (draws in the recording), size [w, h],
                 parts [{graphic, w, h, dx, dy, flip}], box [x, y, w, h] on the identify sheet,
                 keys (colour-map keys it shows), painted (keys with a colour)}}
  outline: false / true ("black", palette 8) / a palette index 1-15: a 1-pixel border around the
  figure's outer edge (pixels directly above, below, left or right, no diagonals; holes and dither
  gaps left alone), drawn outside the graphic: its sprites are pre-rendered one pixel bigger. Figures sharing a graphic share its border, so it is normally set per family.
  fill (families): false keeps a figure's enclosed black see-through (default: filled, r_type_colour.fill_map).
  name / layer / outline on a figure: null = the family's. Unknown fields are kept on rewrite.
Only `name` and `layer` are user data; everything else is regenerated. A page edits the JSON
(or exports a patch {figures|families: {id: {name, layer}}}) and `r_type_colour.py` reads it back.
"""
import json
from pathlib import Path

SCHEMA = 1
SCALE = 2
WIDTH = 640                      # identification sheet width in sheet pixels (before scaling)
LABEL_H = 9
LAYERS = [{'id': 'original', 'label': 'As the game draws it'},
          {'id': 1, 'label': '1 back'}, {'id': 2, 'label': '2'}, {'id': 3, 'label': '3 middle'},
          {'id': 4, 'label': '4'}, {'id': 5, 'label': '5 front'}]
BG = (40, 40, 48)
TEXT = (255, 255, 160)
FRAME = (110, 110, 120)


def level_tag(lv):
    return 'L%d' % (lv - 0x30)


def _load(path):
    """The registry: committed gzipped (path + '.gz'); a plain .json is read when no .gz exists."""
    import gzip
    gz = Path(str(path) + '.gz')
    if gz.exists():
        return json.loads(gzip.decompress(gz.read_bytes()))
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save(path, reg):
    import gzip
    Path(str(path) + '.gz').write_bytes(gzip.compress((json.dumps(reg, indent=1) + '\n').encode(), mtime=0))
    Path(path).unlink(missing_ok=True)


def _families(comps):
    """Union of figures sharing any graphic -> [set of figure indexes]."""
    parent = list(range(len(comps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner = {}
    for i, c in enumerate(comps):
        for p in c['shape']:
            g = p['graphic']
            if g in owner:
                parent[find(i)] = find(owner[g])
            else:
                owner[g] = i
    groups = {}
    for i in range(len(comps)):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=lambda g: min(g))


def _render(comp, cmap, rgb):
    """{(x, y): rgb} of a composite as the sprite build draws it (painted colours applied)."""
    from nexclash import coloursheet as cs
    out = {}
    for (x, y), (pi, xi) in cs.owners(comp).items():
        c, r, key, bit, code, dflt = comp['parts'][pi]['pixels'][xi]
        st = cs.state(cmap, key, bit)
        if st == 'T':
            continue
        n = st[1] if st != 'D' else dflt
        if code == 0 and st == 'D':
            continue
        out[(x, y)] = rgb[n]
    return out


def _font():
    from PIL import ImageFont
    try:
        return ImageFont.load_default()
    except Exception:            # noqa: BLE001
        return None


def update(out_dir, comps_by_level, cmap, rgb, say=print, ident=None):
    """Assign / keep IDs, write the registry and, per level, the identification and painting sheets."""
    from PIL import Image, ImageDraw
    from nexclash import coloursheet as cs
    out_dir = Path(out_dir)
    reg_path = out_dir / 'r_type_figures.json'
    old = _load(reg_path)
    old_figs = old.get('figures', {})
    old_fams = old.get('families', {})
    by_sig = {f['sig']: fid for fid, f in old_figs.items()}
    reg = dict(old)
    reg.update(schema=SCHEMA, game='r_type', note=__doc__.split('\n\n')[0], scale=SCALE,
               palette=[list(c) for c in rgb], layers=LAYERS)
    figs, fams, levels, ids_by_level = {}, {}, {}, {}
    font = _font()
    for lv, comps in sorted(comps_by_level.items()):
        tag = level_tag(lv)
        from .r_type_colour import level_name
        lname = level_name(lv)
        # figure IDs: keep known signatures, number new ones after the highest so far
        used = [int(fid.split('-')[1]) for fid in old_figs if fid.startswith(tag + '-')]
        nxt = max(used, default=0) + 1
        ids = []
        for c in comps:
            fid = by_sig.get(c['sig'])
            if fid is None:
                fid = '%s-%03d' % (tag, nxt)
                nxt += 1
            ids.append(fid)
        # families: keep an old family ID when the new family shares graphics with it
        fam_used = [int(k.split('-F')[1]) for k in old_fams if k.startswith(tag + '-F')]
        fnext = max(fam_used, default=0) + 1
        taken = set()
        for group in _families(comps):
            graphics = sorted({p['graphic'] for i in group for p in comps[i]['shape']})
            best, bestn = None, 0
            for k, f in old_fams.items():
                if k.startswith(tag + '-F') and k not in taken:
                    n = len(set(f.get('graphics', [])) & set(graphics))
                    if n > bestn:
                        best, bestn = k, n
            if best is None:
                best = '%s-F%02d' % (tag, fnext)
                fnext += 1
            taken.add(best)
            prev = old_fams.get(best, {})
            fam = dict(prev)
            fam.update(level=lname, name=prev.get('name', ''), layer=prev.get('layer', 'original'),
                       outline=prev.get('outline', False),
                       figures=sorted(ids[i] for i in group), graphics=graphics)
            fams[best] = fam
            for i in group:
                comps[i]['family'] = best
        for i, c in enumerate(comps):
            prev = old_figs.get(ids[i], {})
            keys = {q[2] for p in c['parts'] for q in p['pixels'] if q[4]}
            f = dict(prev)
            f.update(sig=c['sig'], level=lname, family=c['family'], name=prev.get('name'),
                     layer=prev.get('layer'), outline=prev.get('outline'), count=c['count'],
                     parts=c['shape'], keys=len(keys), painted=sum(1 for k in keys if k in cmap),
                     sheet=None, box=None)
            figs[ids[i]] = f
        ids_by_level[lv] = ids
    for sname, comps, ids, pre in plan_sheets(comps_by_level, ids_by_level):
        sheet, paint, order, place, height = draw_level(out_dir, sname, comps, ids, fams, old_figs, old_fams,
                                                        cmap, rgb, ident, preshown=pre, drop=True)
        lv = comps[0]['group'] if sname != COMMON else None
        levels[sname] = dict(level=lv, tag=level_tag(lv) if lv else 'C', identify=sheet, painting=paint,
                             width=WIDTH * SCALE, height=height * SCALE, figures=[ids[i] for i in order])
        for i in order:
            f = figs.get(ids[i])
            if f is None:               # a shared graphic on its own (COMMON sheet), not a figure
                continue
            f.update(sheet=sname, size=[place[i][2], place[i][3]],
                     box=[place[i][0] * SCALE, place[i][1] * SCALE, place[i][2] * SCALE, place[i][3] * SCALE])
        say('%-8s %3d of %3d figures -> %s, %s' % (sname, len(order), len(comps), sheet, paint))
    # figures no longer seen keep their entry (a shorter recording must not lose names)
    for fid, f in old_figs.items():
        if fid not in figs:
            figs[fid] = dict(f, unseen=True)
    for k, f in old_fams.items():
        if k not in fams:
            fams[k] = dict(f, unseen=True)
    reg.update(levels=levels, families=dict(sorted(fams.items())), figures=dict(sorted(figs.items())))
    _save(reg_path, reg)
    return reg


COMMON = 'COMMON'
ENEMY_LIKE = 0.6                        # similarity that sends a shared figure with a removed one


def arrangement(path=None):
    """The owner's sheet arrangement, colours/r_type_sheets.json: {sheet: {add, remove, after, order}}
    (COMMON remove: shared figures drawn on their own level's sheet instead, e.g. enemies)."""
    p = Path(path) if path else Path(__file__).resolve().parents[1] / 'docs' / 'profiles' / 'r_type_sheets.json'
    return json.loads(p.read_text()) if p.exists() else {}


def plan_sheets(comps_by_level, ids_by_level, arrange=None):
    """The sheets to draw: [(name, comps, ids, preshown)]. COMMON first: every figure made only of
    graphics drawn in more than one level (the same artwork in the same colours; r_type_colour
    twins), once, from the lowest level that draws it, plus any shared graphic no such figure shows,
    on its own. Then each level: its other figures, with the shared graphics faded (preshown: painted
    on COMMON). draw_level(drop=True) leaves out figures that show nothing not already shown."""
    from .r_type_colour import level_name
    arrange = arrangement() if arrange is None else arrange
    moved = set(arrange.get(COMMON, {}).get('add', []))
    home = set(arrange.get(COMMON, {}).get('remove', []))  # shared figures kept on their own level's sheet
    stay = set(arrange.get(COMMON, {}).get('keep', [])) | moved | set(arrange.get(COMMON, {}).get('order', []))
    allc = [(c, f) for lv in sorted(comps_by_level) for c, f in zip(comps_by_level[lv], ids_by_level[lv])]
    # a shared figure that looks like a removed one (another frame or colouring of that enemy) goes too
    hc = [c for c, f in allc if f in home]
    home_csig = {c['csig'] for c in hc}     # ... with their copies in other levels (shown once)
    for c, f in allc:
        if f not in home and f not in stay and all(c['shared']) and c['csig'] not in home_csig and \
                any(similarity(c, h) >= ENEMY_LIKE for h in hc):
            home.add(f)
            hc.append(c)
            home_csig.add(c['csig'])
    common, seen_csig, covered, singles = [], set(), set(), {}
    for lv in sorted(comps_by_level):
        for c, fid in zip(comps_by_level[lv], ids_by_level[lv]):
            if fid in home or (all(c['shared']) and c['csig'] in home_csig):
                covered.update(c['plots'])
            elif fid in moved:
                common.append((c, fid))
                covered.update(c['plots'])
            elif all(c['shared']):
                if c['csig'] not in seen_csig:
                    seen_csig.add(c['csig'])
                    common.append((c, fid))
                covered.update(c['plots'])
            else:
                for n, (g, sh) in enumerate(zip(c['plots'], c['shared'])):
                    if sh and g not in singles:
                        singles[g] = (c, fid, n)
    for g, (c, fid, n) in singles.items():
        if g in covered:
            continue
        part = dict(c['parts'][n], dx=0, dy=0, x=0, y=0)
        common.append((dict(c, parts=[part], shape=[dict(c['shape'][n], dx=0, dy=0)], plots=[g], shared=[True]),
                       '%s.%d' % (fid, n + 1)))
    pre = set()
    for c, _ in common:
        pre.update((q[2], q[3]) for p in c['parts'] for q in p['pixels'])
    out = [(COMMON, [c for c, _ in common], [f for _, f in common], frozenset())] if common else []
    for lv in sorted(comps_by_level):
        keep = [(c, f) for c, f in zip(comps_by_level[lv], ids_by_level[lv])
                if (f in home or not all(c['shared'])) and f not in moved]
        if keep:
            out.append((level_name(lv),
                        [c for c, _ in keep], [f for _, f in keep], frozenset(pre)))
    return out


def _idnum(fid):
    """Sort number of an ID: L3-036 -> 36.0, a single graphic L3-036.2 -> 36.2."""
    try:
        return float(fid.split('-', 1)[1])
    except ValueError:
        return 1e9


def _shape(comp):
    """Opaque pixels of a figure, set of (x, y), and its size."""
    from nexclash import coloursheet as cs
    pts = {q for q, (n, i) in cs.owners(comp).items() if comp['parts'][n]['pixels'][i][4]}
    if not pts:
        return set(), (0, 0)
    w = max(x for x, _ in pts) + 1
    h = max(y for _, y in pts) + 1
    return pts, (w, h)


def _alike(a, b):
    """Similarity of two shapes (0..1): best overlap, as drawn or mirrored either way."""
    (pa, (wa, ha)), (pb, (wb, hb)) = a, b
    if not pa or not pb or abs(wa - wb) > 8 or abs(ha - hb) > 8:
        return 0.0
    best = 0.0
    for fx in (False, True):
        for fy in (False, True):
            q = {((wb - 1 - x) if fx else x, (hb - 1 - y) if fy else y) for x, y in pb}
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    qq = {(x + dx, y + dy) for x, y in q}
                    best = max(best, len(pa & qq) / len(pa | qq))
    return best


def _art(comp):
    """(graphic start, end) ranges of a figure's plots in the unpacked stream, its size and its two
    main colour indexes."""
    from nexclash import coloursheet as cs
    ranges = []
    for sh, p in zip(comp['shape'], comp['parts']):
        cells = (sh['w'] // 8) * (sh['h'] // 8)
        filled = len({(q[0] // 8, q[1] // 8) for q in p['pixels']})
        start = int(sh['graphic'], 16)
        ranges.append((start, start + filled * 9 + (cells - filled)))
    pts, size = _shape(comp)
    cols = {}
    for q, (n, i) in cs.owners(comp).items():
        d = comp['parts'][n]['pixels'][i][5]
        if d:
            cols[d] = cols.get(d, 0) + 1
    return ranges, size, set(sorted(cols, key=cols.get, reverse=True)[:2])


def sheet_order(comps, ids):
    """Figure order shared by the identification and painting sheets. Families (shared graphics)
    stay together, and families are joined when they are one object's animation: their artwork is
    stored back to back (one figure's graphic starts where another's ends), at a similar size
    (within 4 pixels) and in the same main colours, or their shapes overlap by half or more as drawn
    or mirrored. Groups in order of their lowest ID, figures by ID inside. IDs never change."""
    num = lambda i: _idnum(ids[i])
    fams = {}
    for i, c in enumerate(comps):
        fams.setdefault(c['family'], []).append(i)
    keys = sorted(fams, key=lambda f: min(num(i) for i in fams[f]))
    rep = {f: comps[min(fams[f], key=num)] for f in keys}
    shapes = {f: _shape(rep[f]) for f in keys}
    art = {f: _art(rep[f]) for f in keys}
    parent = {f: f for f in keys}

    def find(f):
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    def stored_together(a, b):
        (ra, (wa, ha), ca), (rb, (wb, hb), cb) = art[a], art[b]
        if abs(wa - wb) > 4 or abs(ha - hb) > 4 or not (ca & cb):
            return False
        return any(abs(e1 - s2) <= 2 or abs(e2 - s1) <= 2 for s1, e1 in ra for s2, e2 in rb)
    for x in range(len(keys)):
        for y in range(x + 1, len(keys)):
            a, b = keys[x], keys[y]
            if find(a) != find(b) and (stored_together(a, b) or _alike(shapes[a], shapes[b]) >= 0.5):
                parent[find(b)] = find(a)
    clusters = {}
    for f in keys:
        clusters.setdefault(find(f), []).append(f)
    # groups in a chain of look-alikes (owner, 2026-11-20): after each group comes the remaining group
    # that looks most like it (shape as drawn or mirrored, main colours shared); when none does, the
    # one with the lowest ID
    simc = {}

    def fsim(a, b):
        k = (a, b) if a < b else (b, a)
        if k not in simc:
            simc[k] = _alike(shapes[a], shapes[b]) * (1.0 if art[a][2] & art[b][2] else 0.6)
        return simc[k]
    roots = sorted(clusters, key=lambda r: min(num(i) for f in clusters[r] for i in fams[f]))
    chain = [roots.pop(0)] if roots else []
    while roots:
        sims = [max(fsim(a, b) for a in clusters[chain[-1]] for b in clusters[r]) for r in roots]
        k = max(range(len(roots)), key=lambda n: sims[n])
        chain.append(roots.pop(k if sims[k] >= LOOKALIKE else 0))
    order = []
    for root in chain:
        for f in sorted(clusters[root], key=lambda f: min(num(i) for i in fams[f])):
            order += sorted(fams[f], key=num)
    return order


LOOKALIKE = 0.3                         # similarity (0..1) that puts two groups side by side


def similarity(a, b):
    """How alike two figures look (0..1): shape overlap as drawn or mirrored, less when they share
    neither of their two main colours."""
    return _alike(_shape(a), _shape(b)) * (1.0 if _art(a)[2] & _art(b)[2] else 0.6)


def _fade(c):
    """A colour faded toward the sheet background: a copy that is shown but not read back."""
    from nexclash import coloursheet as cs
    return tuple(int(b + (v - b) * 0.35) for v, b in zip(c, cs.BG_RGB))


def draw_level(out_dir, lname, comps, ids, fams, figs_reg, fams_reg, cmap, rgb, ident=None, prefix=None,
               preshown=frozenset(), drop=False):
    """Both sheets of a level, in the same order and arrangement:
    r_type_<LEVEL>_IDENTIFY.png  every figure at 2x with its ID, borders as built (never read back);
    r_type_<LEVEL>_PAINTING_SPRITES.png + _layout.json  the same figures at 1:1, no text. The first
    time a graphics pixel appears it is paintable; later copies of it (other frames, other figures
    sharing the graphic) are drawn faded and are not read back (the layout's `show` lists the
    paintable pixels, `dim` the faded ones). Painting coordinates are the identification sheet's / 2.
    -> (identify name, painting name, order, place {i: (x, y, w, h)}, height)"""
    import json as _json
    from PIL import Image, ImageDraw
    from nexclash import coloursheet as cs
    from .r_type_colour import outline_colour, ring
    out_dir = Path(out_dir)
    prefix = prefix or 'r_type_%s' % lname
    order = sheet_order(comps, ids)
    arr = arrangement().get(lname, {})
    if arr.get('order'):                # the owner's run of figures, after the `after` figure
        at = {ids[i]: i for i in order}
        run = [at[f] for f in arr['order'] if f in at]
        rest = [i for i in order if i not in set(run)]
        anchor = at.get(arr.get('after'))
        # a figure that looks like one of the run joins it, after the end of that look-alike stretch
        # of the run (the owner's order of the run itself is never broken up)
        follow = {i: [] for i in run}
        for i in list(rest):
            best = max(run, key=lambda j: similarity(comps[i], comps[j]), default=None)
            if best is not None and i != anchor and similarity(comps[i], comps[best]) >= 0.5:
                q = run.index(best)
                while q + 1 < len(run) and similarity(comps[run[q]], comps[run[q + 1]]) >= LOOKALIKE:
                    q += 1
                follow[run[q]].append(i)
                rest.remove(i)
        run = [x for j in run for x in [j] + follow[j]]
        k = rest.index(anchor) + 1 if anchor in rest else 0
        order = rest[:k] + run + rest[k:]
    if drop:                            # only figures that show a graphics pixel not shown before
        kept, sh = [], set(preshown)
        for i in order:
            px = {(q[2], q[3]) for p in comps[i]['parts'] for q in p['pixels']}
            if px - sh:
                kept.append(i)
                sh |= px
        order = kept
    top = cs.SW + 4
    place, x, y, rowh, last = {}, 2, top, 0, None
    for i in order:
        allpx = cs.owners(comps[i], clear=True)
        w = max(p[0] for p in allpx) + 1
        h = max(p[1] for p in allpx) + 1
        boxw = max(w, 6 * len(ids[i]) // SCALE + 2)
        if x + boxw + 2 > WIDTH:
            x, y, rowh = 2, y + rowh + 4, 0
        place[i] = (x, y + LABEL_H, w, h)
        x += boxw + 6
        rowh = max(rowh, h + LABEL_H)
    height = y + rowh + 4
    # identification sheet (2x, labels, borders)
    font = _font()
    img = Image.new('RGB', (WIDTH * SCALE, height * SCALE), BG)
    dr = ImageDraw.Draw(img)
    for n in range(1, 16):
        sx = 1 + (n - 1) * (cs.SW + 2)
        dr.rectangle([sx * SCALE, SCALE, (sx + cs.SW) * SCALE - 1, (1 + cs.SW) * SCALE - 1], fill=rgb[n])
    for i in order:
        bx, by, w, h = place[i]
        pix = _render(comps[i], cmap, rgb)
        ov = figs_reg.get(ids[i], {}).get('outline')
        if ov is None:
            ov = fams.get(comps[i]['family'], fams_reg.get(comps[i]['family'], {})).get('outline')
        col = outline_colour(ov)
        if col is not None:                 # the border the build draws, 1 pixel outside
            inv = {v: k for k, v in enumerate(rgb)}
            idx = {(px + 1, py + 1): inv.get(c, 8) for (px, py), c in pix.items()}
            idx = ring(idx, max(q[0] for q in idx) + 2, max(q[1] for q in idx) + 2, col)
            pix = {(px - 1, py - 1): rgb[k] for (px, py), k in idx.items() if k}
        dr.rectangle([bx * SCALE - 1, by * SCALE - 1, (bx + w) * SCALE, (by + h) * SCALE], outline=FRAME)
        for (px, py), c in pix.items():
            dr.rectangle([(bx + px) * SCALE, (by + py) * SCALE, (bx + px + 1) * SCALE - 1,
                          (by + py + 1) * SCALE - 1], fill=c)
        dr.text((bx * SCALE, (by - LABEL_H) * SCALE), ids[i], fill=TEXT, font=font)
    ident_name = prefix + '_IDENTIFY.png'
    img.save(out_dir / ident_name)
    # painting sheet (1:1, no text), coloursheet layout format
    pimg = Image.new('RGB', (WIDTH, height), cs.BG_RGB)
    for n in range(1, 16):
        for yy in range(1, 1 + cs.SW):
            for xx in range(cs.SW):
                pimg.putpixel((1 + (n - 1) * (cs.SW + 2) + xx, yy), rgb[n])
    shown, lay = set(preshown), []
    for i in order:
        comp = comps[i]
        bx, by, w, h = place[i]
        show, dim = [], []
        own = {p: v for p, v in cs.owners(comp, clear=True).items() if 0 <= p[0] < w and 0 <= p[1] < h}
        for (px, py), (n, k) in sorted(own.items(), key=lambda t: (t[0][1], t[0][0])):
            c, r, key, bit, code, dflt = comp['parts'][n]['pixels'][k]
            e = cmap.get(key) or [0, 0, [0] * 8]
            if len(e) > 3 and e[3] & (0x80 >> bit):
                col = cs.TRANSP_RGB
            else:
                v = e[2][bit] or dflt
                col = rgb[v] if v else cs.TRANSP_RGB
            if (key, bit) in shown:
                col = _fade(col)
                dim.append([px, py] + list(col))
            else:
                shown.add((key, bit))
                show.append([px, py])
            pimg.putpixel((bx + px, by + py), col)
        parts = []
        for p in comp['parts']:
            keys = sorted({q[2] for q in p['pixels']})
            ki = {kk: m for m, kk in enumerate(keys)}
            parts.append(dict(id=str(p['id']), w=p['w'], h=p['h'], dx=p['dx'], dy=p['dy'], dmir=p['dmir'],
                              vmir=p.get('vmir', 0), keys=keys, entries={kk: p['entries'][kk] for kk in keys},
                              pixels=[v for q in p['pixels'] for v in (q[0], q[1], ki[q[2]], q[3], q[4], q[5])]))
        lay.append(dict(group=comp['group'], x=bx, y=by, w=w, h=h, ox=0, oy=0, count=comp['count'], parts=parts,
                        show=sorted(show), dim=dim, id=ids[i], family=comp['family']))
    paint_name = prefix + '_PAINTING_SPRITES.png'
    pimg.save(out_dir / paint_name)
    out = dict(size=[WIDTH, height], palette=[list(c) for c in rgb],
               colours={k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in cmap.items()},
               swatches=[[1 + (n - 1) * (cs.SW + 2), 1, n] for n in range(1, 16)], composites=lay,
               paint_clear=True, identify=ident_name,
               note='R-Type painting sheet: same arrangement as the identification sheet (/2); faded pixels '
                    '(dim) are copies of graphics already shown and are not read back')
    if ident:
        out['identity'] = ident
    import gzip                         # committed layouts are gzipped (recolour.find_layout reads both)
    (out_dir / (prefix + '_PAINTING_SPRITES_layout.json')).unlink(missing_ok=True)
    (out_dir / (prefix + '_PAINTING_SPRITES_layout.json.gz')).write_bytes(
        gzip.compress(_json.dumps(out).encode(), mtime=0))
    return ident_name, paint_name, order, place, height


def apply(out_dir, patch, say=print):
    """Read back user data: patch = {figures|families: {id: {name, layer}}} (a page export or a
    hand-edited file). Only name, layer, outline and fill change; unknown IDs or layers are refused."""
    out_dir = Path(out_dir)
    reg_path = out_dir / 'r_type_figures.json'
    reg = _load(reg_path)
    ok_layers = {l['id'] for l in LAYERS}
    bad, n = [], 0
    for kind in ('figures', 'families'):
        for fid, change in patch.get(kind, {}).items():
            if fid not in reg.get(kind, {}):
                bad.append('%s %s: not in the registry' % (kind, fid))
                continue
            for field in ('name', 'layer', 'outline', 'fill'):
                if field not in change:
                    continue
                v = change[field]
                if field == 'layer' and v not in ok_layers and not (kind == 'figures' and v is None):
                    bad.append('%s %s: layer %r (choices %s)' % (kind, fid, v, sorted(map(str, ok_layers))))
                    continue
                if field == 'outline':
                    from .r_type_colour import outline_colour
                    try:
                        outline_colour(v)
                    except ValueError as e:
                        bad.append('%s %s: %s' % (kind, fid, e))
                        continue
                if field == 'fill' and v not in (True, False, None):
                    bad.append('%s %s: fill must be true or false' % (kind, fid))
                    continue
                if field == 'name' and v is not None and not isinstance(v, str):
                    bad.append('%s %s: name must be text' % (kind, fid))
                    continue
                reg[kind][fid][field] = v
                n += 1
    if bad:
        raise ValueError('nothing applied:\n  ' + '\n  '.join(bad))
    _save(reg_path, reg)
    say('%d name / layer change(s) applied to %s' % (n, reg_path.name))
    return reg
