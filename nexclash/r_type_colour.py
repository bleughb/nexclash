"""R-Type colour sheets and recolour for the Layer 2 + sprite prototype (owner request 2026-11-16).

Colours stay the game's own until the user paints a sheet; painting and import follow the normal
process (nexclash docs/COLOURS.md: coloursheet sheets, read-back, three-way merge, recolour bundle).
Until R-Type has an evidence record, run the import with this module instead of `nexclash.py
recolour` (same code path: nexclash.recolour.run with this engine):

    python r_type_colour.py sheets [-o DIR]                          the sheets, one pair per level
    python r_type_colour.py recolour BUILD.nex PAINTED.png [-o OUT_painted.nex] [--onto MAP | --replace]
    python r_type_colour.py figures PATCH.json                       names / layers / outlines into the registry
    python r_type_colour.py restyle BUILD.nex                        BUILD_styled.nex with the registry's outlines

Keys: one per graphics byte, 'LL:AAAA' = level byte (7 19C, '0'..'9') : address of the byte in the
unpacked graphic stream; check = the byte's value; bit 0 = leftmost pixel. Defaults: ink = the
cell's ink (black ink on coloured paper = opaque black), coloured paper drawn, black paper clear
(paintable: paint_clear). Grey = transparent (clear=True). Flash colours (8EB1 ink override) are not
painted: a forced-ink draw keeps the forced colour.

Runtime (l2sprites_body.asm col_lookup): colour data only in banks 24..27 and 32..47, which the
game never maps. Pages 64-65: a directory per level (count, first) then the sorted cell addresses;
pages 66..95: 40-byte records per painted cell (8 lines x 4 bytes of nibbles, left pixel high, 0 =
default; then 8 transparent masks, bit 7 = leftmost). Pages 48..55 (banks 24-27): graphics with an outline
(r_type_figures.json), pre-rendered one pixel bigger on every side with their border (outline_pages). Patterns are converted once per graphic, so
the lookup costs only at conversion. The graphic stream is unpacked per level into the same
addresses: the level is part of every key.

The sheets are built from the whole-recording figure corpus (continuation/assets.json.gz: objects
joined by the game's own 9-byte object / owner, capture_assets.py); a later recording that reaches
more figures gives a second sheet read into the same colours file.
"""
import collections
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


RECORD = 'r_type'
COLOURS = str(ROOT / 'docs' / 'profiles' / (RECORD + '_colours.json'))
COLOUR_BANKS = list(range(24, 28)) + list(range(32, 48))   # 24-27: outline pre-renders
DIR_PAGE, REC_PAGE0, LAST_PAGE = 64, 66, 95     # directory: pages 64-65; records 66-95
PRE_DIR, PRE_PAT0, PRE_LAST = 48, 49, 55      # outlined graphics (banks 24-27): directory, then 128-byte patterns
PRE_ENTRY = 12
REC = 40
PER_PAGE = 8192 // REC
DIR_ENTRIES = (16384 - 64) // 2
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6,
           0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]       # l2scroll.asm col_tab
LEVEL_NAMES = {0x30: 'TEXT'}
ART_BANKS = (3, 4, 6, 7)        # the same in every snapshot of the recording: packed level data
NOTE = ('R-Type colour map (docs/COLOURS.md): key = level:graphics byte (hex; check = its value), 8 '
        'nibbles (0 = the cell default), optional 4th = transparent mask')
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': COLOURS, 'clear': True, 'note': NOTE}


def level_name(lv):
    return LEVEL_NAMES.get(lv, 'LEVEL%d' % (lv - 0x30))


def level_byte(name):
    """Inverse of level_name: 'TEXT' -> 0x30, 'LEVEL3' -> 0x33."""
    inv = {v: k for k, v in LEVEL_NAMES.items()}
    return inv[name] if name in inv else 0x30 + int(name[5:])


def corpus():
    from . import r_type as R
    return R.corpus(R.source())


def defaults(attr):
    """(ink index or 0, paper index or 0) for a cell attribute, as the sprite converter draws it."""
    bright = 8 if attr & 0x40 else 0
    paper = (attr >> 3) & 7
    pap = paper + bright if paper else 0
    ink = attr & 7
    if ink:
        return ink + bright, pap
    return (8 if pap else 0), pap


def cell_part_pixels(cell, cx, cy):
    """Coloursheet pixels of one 8x8 cell placed at cell (cx, cy) of its plot."""
    ink, pap = defaults(cell['attribute'])
    px = []
    for line, byte in enumerate(cell['bits']):
        key = '%02X:%04X' % (cell['level'], (cell['address'] + 1 + line) & 0xFFFF)
        for bit in range(8):
            if byte & (0x80 >> bit):
                code, d = (1, ink) if ink else (0, 0)
            else:
                code, d = (2, pap) if pap else (0, 0)
            px.append((cx * 8 + bit, cy * 8 + line, key, bit, code, d))
    return px


def plain_cell(cell):
    """True when the corpus cell was drawn without an ink override (its ink is the attribute's)."""
    a = cell['attribute']
    return cell['ink'] == (((a & 7) + (8 if a & 64 else 0)) or 8)


def _bkey(c, line):
    return '%02X:%04X' % (c['level'], (c['address'] + 1 + line) & 0xFFFF)


def _content(data, p):
    """A plot's artwork without its level or address: size and every cell's attribute and pixels."""
    cells = data['cells']
    return (p['w'], p['h'], tuple((cx, cy, cells[ck]['attribute'], tuple(cells[ck]['bits']))
                                  for cx, cy, ck in p['cells']))


def content_groups(data):
    """{content: [plot keys]}, first = the lowest (level, address): the same artwork in the same
    colours is one graphic wherever and in whichever level it is stored. The same pixels in other
    colours are another graphic (levels that colour a figure differently keep their own)."""
    groups = collections.defaultdict(list)
    for pk, p in data['plots'].items():
        groups[_content(data, p)].append(pk)
    for g in groups.values():
        g.sort(key=lambda k: (data['plots'][k]['level'], data['plots'][k]['address']))
    return groups


def twins(data):
    """{graphics byte key: its canonical key}, for every byte of a graphic that is also stored
    elsewhere (the canonical copy is the lowest level and address). The sheets show only canonical
    keys; tables() gives every copy its canonical copy's colours."""
    cells, plots = data['cells'], data['plots']
    tw = {}
    for g in content_groups(data).values():
        rep = plots[g[0]]
        for pk in g[1:]:
            for (_, _, ck), (_, _, rk) in zip(plots[pk]['cells'], rep['cells']):
                for line in range(8):
                    a, b = _bkey(cells[ck], line), _bkey(cells[rk], line)
                    if a != b:
                        tw.setdefault(a, b)
    for k in list(tw):                  # overlapping plots: follow to the end of a chain
        seen = {k}
        while tw[k] in tw and tw[k] not in seen:
            seen.add(tw[k])
            tw[k] = tw[tw[k]]
    return tw


def expand(cmap, data=None):
    """The colour map with every copy of a graphic given its canonical copy's colours (a copy's own
    entry, painted before the sheets were shared, is kept)."""
    data = data or corpus()
    out = dict(cmap)
    for k, c in twins(data).items():
        if k not in out and c in cmap:
            out[k] = cmap[c]
    return out


def composites(data):
    """{level: [composite]} for coloursheet.write: one composite per distinct figure (game object).
    Pixel keys are canonical (twins); each composite has `csig` (its artwork, level-free) and
    `levels` (the levels each of its graphics is drawn in, smallest set)."""
    cells, plots = data['cells'], data['plots']
    tw = twins(data)
    groups = content_groups(data)
    span, gid = {}, {}
    for n, (content, g) in enumerate(groups.items()):
        lv = {plots[k]['level'] for k in g}
        for k in g:
            span[k], gid[k] = lv, g[0]
    parts_cache = {}

    def part(pk):
        if pk not in parts_cache:
            p = plots[pk]
            px, ent, ok = [], {}, True
            for cx, cy, ck in p['cells']:
                c = cells[ck]
                ok &= plain_cell(c)
                px += cell_part_pixels(c, cx, cy)
                for line, byte in enumerate(c['bits']):
                    k = _bkey(c, line)
                    ent[tw.get(k, k)] = [byte, 'g']
            px = [q[:2] + (tw.get(q[2], q[2]),) + q[3:] for q in px]
            parts_cache[pk] = (dict(id=pk, size=len(p['cells']), w=p['w'], h=p['h'], pixels=px,
                                    entries=ent), ok)
        return parts_cache[pk]
    out = collections.defaultdict(list)
    for fig in data['figures']:
        built, ok = [], True
        for q in fig['parts']:
            base, pok = part(q['plot'])
            ok &= pok
            built.append(dict(base, x=q['x'], y=q['y'], dx=q['dx'], dy=q['dy'], mir=q['flip'] & 1,
                              dmir=q['flip'] & 1, vmir=(q['flip'] >> 1) & 1, group=fig['level']))
        if ok and any(px[4] for b in built for px in b['pixels']):
            # what makes the figure itself: its plots (graphic, size, place, flip) in drawing order
            shape = [dict(graphic='%04X' % plots[q['plot']]['address'], w=plots[q['plot']]['w'],
                          h=plots[q['plot']]['h'], dx=q['dx'], dy=q['dy'], flip=q['flip']) for q in fig['parts']]
            sig = hashlib.sha1(json.dumps([fig['level'], shape]).encode()).hexdigest()[:12]
            art = [[gid[q['plot']], q['dx'], q['dy'], q['flip']] for q in fig['parts']]
            csig = hashlib.sha1(json.dumps(art).encode()).hexdigest()[:12]
            levels = set.intersection(*[span[q['plot']] for q in fig['parts']])
            out[fig['level']].append(dict(count=fig['count'], group=fig['level'], parts=built,
                                          sig=sig, shape=shape, csig=csig, levels=levels,
                                          plots=[gid[q['plot']] for q in fig['parts']],
                                          shared=[len(span[q['plot']]) > 1 for q in fig['parts']]))
    return out


def byte_index(data):
    """{key: (level, cell attribute address, line, check byte)} for every graphics byte drawn."""
    idx = {}
    for c in data['cells'].values():
        for line, byte in enumerate(c['bits']):
            idx['%02X:%04X' % (c['level'], (c['address'] + 1 + line) & 0xFFFF)] = (
                c['level'], c['address'], line, byte)
    return idx


def art_md5(banks):
    """MD5 of the banks the levels are unpacked from ({bank: bytes})."""
    return hashlib.md5(b''.join(bytes(banks[b]) for b in ART_BANKS)).hexdigest()


class Peek:
    """The identity's view of a game: its unchanging banks (128K; recolour.nex_peek is 48K only)."""
    def __init__(self, banks):
        self.art = art_md5(banks)

    def __call__(self, a):
        raise NotImplementedError('R-Type identity uses whole banks')


def colour_identity(peek):
    """What a key means for this build (docs/COLOURS.md Identity): level byte + graphics byte, bit
    = pixel; inputs = the banks the levels are unpacked from (3, 4, 6, 7: identical in every
    snapshot of the recording); geometry = the figure corpus the sheets were drawn from."""
    from . import r_type as R
    geo = R.catalogue_md5()
    return {'schema': 1, 'game': RECORD, 'engine': 'r_type_l2sprites',
            'keys': 'r_type-1: LL:AAAA level byte : unpacked graphics byte, bit = pixel',
            'inputs': peek.art, 'geometry': geo}


def sheets(out_dir=None, colours=None, say=print):
    """Per level, two sheets in the same arrangement (r_type_figures.draw_level): the identification
    sheet (IDs, 2x) and the painting sheet (1:1 + _layout.json; every figure, a graphic paintable the
    first time it appears and faded after). The registry r_type_figures.json is updated too."""
    from nexclash import coloursheet as cs, z80tonex as Z
    out_dir = Path(out_dir or 'r_type_sheets')
    out_dir.mkdir(exist_ok=True)
    data = corpus()
    from . import r_type as R
    ident = colour_identity(Peek(R.source().banks))
    cmap = colours if colours is not None else cs.load(os.environ.get('NEXCLASH_COLOURS') or COLOURS)
    rgb = cs.palette_rgb(PALETTE)
    from . import r_type_figures as F
    F.update(out_dir, composites(data), cmap, rgb, say, ident)
    from . import r_type_scenery as SC
    SC.sheets(out_dir, cmap, rgb, ident, say)
    made = sorted(out_dir.glob('r_type_*_PAINTING_S*.png'))
    return made


FIGURES = ROOT / 'docs' / 'profiles' / 'r_type_figures.json'


def registry(path=None):
    from . import r_type_figures as F
    return F._load(Path(path or os.environ.get('RTYPE_FIGURES') or FIGURES))


def outline_colour(v):
    """Registry outline value -> palette index, or None (off). true / 'black' = 8 (opaque black)."""
    if v in (None, False, 0, 'off', 'none'):
        return None
    if v in (True, 'black', 'on'):
        return 8
    if isinstance(v, int) and 1 <= v <= 15:
        return v
    raise ValueError('outline %r: use true / "black" or a palette index 1-15' % (v,))


def outline_wanted(reg=None):
    """{(level byte, graphic address): palette index} for every family / figure with an outline."""
    reg = reg if reg is not None else registry()
    want = {}
    fams = reg.get('families', {})
    for fid, f in reg.get('figures', {}).items():
        v = f.get('outline')
        if v is None:
            v = fams.get(f.get('family'), {}).get('outline')
        col = outline_colour(v)
        if col is None:
            continue
        lv = level_byte(f['level'])
        for p in f['parts']:
            g = int(p['graphic'], 16)
            if want.get((lv, g), col) != col:
                raise ValueError('%s: graphic %04X has two outline colours (figures sharing it differ)'
                                 % (fid, g))
            want[(lv, g)] = col
    return want


def ring(pix, w, h, col):
    """pix {(x, y): index} on a w x h canvas -> the same with a border: every clear pixel outside
    the figure (4-connected to the canvas edge) with a visible pixel directly above, below, left or
    right (no diagonals) takes col. Enclosed holes and dither gaps are left alone."""
    N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
    opaque = {q for q, n in pix.items() if n}
    out = set()
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        q = stack.pop()
        if q in out or q in opaque or not (0 <= q[0] < w and 0 <= q[1] < h):
            continue
        out.add(q)
        stack += [(q[0] + dx, q[1] + dy) for dx, dy in N4]
    res = dict(pix)
    for q in out:
        if any((q[0] + dx, q[1] + dy) in opaque for dx, dy in N4):
            res[q] = col
    return res


def plot_canvas(p, cells, cmap, pad):
    """{(x, y): palette index} of a plot as the sprite converter draws it (painted map applied),
    shifted by pad pixels."""
    from nexclash import coloursheet as cs
    pix = {}
    for cx, cy, ck in p['cells']:
        c = cells[ck]
        for x, y, key, bit, code, d in cell_part_pixels(c, cx, cy):
            st = cs.state(cmap, key, bit)
            n = 0 if st == 'T' else (st[1] if st != 'D' else (d if code else 0))
            pix[(x + pad, y + pad)] = n
    return pix


def outlined_patterns(cmap, data=None, reg=None):
    """Outlined graphics pre-rendered one pixel bigger on every side, with their border, as 16x16
    4bpp patterns. -> ([entry dicts], info). The build copies these instead of converting the
    graphic; the sprites go one pixel up and left. Flash draws (forced ink) convert normally."""
    data = data or corpus()
    want = outline_wanted(reg)
    cells = data['cells']
    entries, seen, info = [], set(), collections.Counter()
    for p in data['plots'].values():
        col = want.get((p['level'], p['address']))
        if col is None:
            continue
        if not all(plain_cell(cells[ck]) for _, _, ck in p['cells']):
            continue
        k = (p['level'], p['address'], p['w'], p['h'])
        if k in seen:
            continue
        seen.add(k)
        wp, hp = p['w'] + 2, p['h'] + 2
        pnx, pny = (wp + 15) // 16, (hp + 15) // 16
        if pnx * pny > 72:
            info['outlined graphics too big (more than 72 sprites)'] += 1
            continue
        pix = ring(plot_canvas(p, cells, cmap, 1), wp, hp, col)
        tiles, pats = [], []
        for ty in range(pny):
            for tx in range(pnx):
                b = bytearray(128)
                for y in range(16):
                    for x in range(16):
                        n = pix.get((tx * 16 + x, ty * 16 + y), 0)
                        b[y * 8 + x // 2] |= n << (0 if x & 1 else 4)
                tiles.append(1 if any(b) else 0)
                if any(b):
                    pats.append(bytes(b))
        entries.append(dict(level=p['level'], address=p['address'], w=p['w'] // 8, h=p['h'] // 8,
                            pnx=pnx, pny=pny, tiles=tiles, patterns=pats))
        info['graphics outlined'] += 1
        info['border pixels'] += sum(1 for q, n in pix.items() if n == col and
                                     plot_canvas(p, cells, cmap, 1).get(q, 0) != col)
    return entries, dict(info)


def outline_pages(entries):
    """Directory page PRE_DIR (count, then 12-byte entries: level, address, w, h (cells), pnx, pny,
    tiles used, first pattern (2), tile-map offset (2); tile maps after the entries) and pattern pages
    PRE_PAT0.. (64 patterns each). -> {page: bytearray}"""
    pages = {p: bytearray(8192) for p in range(PRE_DIR, PRE_LAST + 1)}
    d = pages[PRE_DIR]
    n = len(entries)
    maps_at = 2 + PRE_ENTRY * n
    if maps_at + sum(len(e['tiles']) for e in entries) > 8192:
        raise ValueError('too many outlined graphics for the directory page')
    total = sum(len(e['patterns']) for e in entries)
    if total > 64 * (PRE_LAST - PRE_PAT0 + 1):
        raise ValueError('%d outlined patterns; the pages hold %d' % (total, 64 * (PRE_LAST - PRE_PAT0 + 1)))
    d[0:2] = bytes([n & 255, n >> 8])
    pat, mo = 0, maps_at
    for i, e in enumerate(entries):
        o = 2 + PRE_ENTRY * i
        d[o:o + PRE_ENTRY] = bytes([e['level'], e['address'] & 255, e['address'] >> 8, e['w'], e['h'],
                                    e['pnx'], e['pny'], len(e['patterns']), pat & 255, pat >> 8,
                                    mo & 255, mo >> 8])
        d[mo:mo + len(e['tiles'])] = bytes(e['tiles'])
        mo += len(e['tiles'])
        for b in e['patterns']:
            pg, off = PRE_PAT0 + pat // 64, (pat % 64) * 128
            pages[pg][off:off + 128] = b
            pat += 1
    return pages


GAP = 2                         # fill_map: see-through gaps this narrow count as inside
FILL = 8                        # opaque black (the converter's index for black ink on coloured paper)


def fill_map(data=None, reg=None):
    """Filled figures (owner request 2026-11-16): {key: entry} in colour-map form painting a graphic's
    enclosed see-through pixels opaque black. Per graphic (plot), its see-through pixels (black paper,
    black ink with no paper, empty cells) are flooded 4-connected from outside its box; those the flood
    cannot reach are inside the figure. A registry family with "fill": false is left see-through."""
    data = data or corpus()
    reg = reg if reg is not None else registry()
    skip = {(lv, g.upper()) for f in reg.get('families', {}).values() if f.get('fill') is False
            for lv in [f['level']] for g in f['graphics']}
    cells, out = data['cells'], {}
    for p in data['plots'].values():
        lname = level_name(p['level'])
        if (lname, '%04X' % p['address']) in skip:
            continue
        w, h = p['w'], p['h']
        solid = [[False] * w for _ in range(h)]
        where = {}
        for cx, cy, ck in p['cells']:
            c = cells[ck]
            ink, pap = defaults(c['attribute'])
            for line, byte in enumerate(c['bits']):
                key = '%02X:%04X' % (c['level'], (c['address'] + 1 + line) & 0xFFFF)
                for bit in range(8):
                    on = byte & (0x80 >> bit)
                    x, y = cx * 8 + bit, cy * 8 + line
                    if x < w and y < h:
                        solid[y][x] = bool(ink) if on else bool(pap)
                        where[(x, y)] = (key, bit, byte)
        # a gap of up to GAP see-through pixels with the figure on both sides (across or down) is a
        # wall for the outside flood, so narrow gaps between parts fill in (owner, 2026-11-17)
        wall = [row[:] for row in solid]
        for y in range(h):
            x = 0
            while x < w:
                if solid[y][x]:
                    x += 1
                    continue
                e = x
                while e < w and not solid[y][e]:
                    e += 1
                if x > 0 and e < w and e - x <= GAP:
                    for i in range(x, e):
                        wall[y][i] = True
                x = e
        for x in range(w):
            y = 0
            while y < h:
                if solid[y][x]:
                    y += 1
                    continue
                e = y
                while e < h and not solid[e][x]:
                    e += 1
                if y > 0 and e < h and e - y <= GAP:
                    for i in range(y, e):
                        wall[i][x] = True
                y = e
        seen = [[False] * w for _ in range(h)]
        stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
        while stack:
            x, y = stack.pop()
            if 0 <= x < w and 0 <= y < h and not seen[y][x] and not wall[y][x]:
                seen[y][x] = True
                stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        for (x, y), (key, bit, byte) in where.items():
            if not solid[y][x] and not seen[y][x]:
                e = out.setdefault(key, [byte, 'fill', [0] * 8, 0])
                e[2][bit] = FILL
    return out


def with_fill(cmap, data=None, reg=None):
    """The colour map with filled figures underneath: painted or cleared pixels win."""
    out = {k: [v[0], v[1], list(v[2]) + [0] * (8 - len(v[2])), v[3] if len(v) > 3 else 0]
           for k, v in fill_map(data, reg).items()}
    for k, v in cmap.items():
        if k in out and v[0] == out[k][0]:
            nib = list(v[2]) + [0] * (8 - len(v[2]))
            mask = v[3] if len(v) > 3 else 0
            fill = out[k][2]
            out[k] = [v[0], v[1], [n or (0 if mask & (0x80 >> i) else fill[i]) for i, n in enumerate(nib)],
                      mask]
        else:
            out[k] = v
    return out


def tables(cmap, data=None, reg=None, fill=True):
    """Colour map + registry outlines -> ({bank: 16384 bytes} for COLOUR_BANKS, info). Unknown keys
    and wrong check bytes are ignored and counted; more painted cells than the directory holds is an
    error."""
    data = data or corpus()
    cmap = expand(cmap, data)           # sheets paint one copy of a shared graphic: give it to all
    if fill:
        cmap = with_fill(cmap, data, reg)
    pre, oinfo = outlined_patterns(cmap, data, reg)
    idx = byte_index(data)
    recs = {}
    info = collections.Counter()
    for key, e in cmap.items():
        if key.startswith('S'):         # scenery: r_type_scenery.banks
            continue
        if key not in idx:
            info['map entries for no drawn graphics byte'] += 1
            continue
        lv, cell, line, check = idx[key]
        if e[0] != check:
            info['map entries with a wrong check byte'] += 1
            continue
        r = recs.setdefault((lv, cell), bytearray(REC))
        nib = list(e[2]) + [0] * (8 - len(e[2]))
        if any(n > 15 for n in nib):
            raise ValueError('%s: colour index above 15 (4-bit sprites)' % key)
        for j in range(4):
            r[line * 4 + j] = (nib[2 * j] << 4) | nib[2 * j + 1]
        r[32 + line] = (e[3] if len(e) > 3 else 0) & 0xFF
    recs = {k: v for k, v in recs.items() if any(v)}
    if len(recs) > DIR_ENTRIES or len(recs) > PER_PAGE * (LAST_PAGE - REC_PAGE0 + 1):
        raise ValueError('%d painted cells; the colour pages hold %d' % (len(recs), DIR_ENTRIES))
    pages = {p: bytearray(8192) for p in range(DIR_PAGE, LAST_PAGE + 1)}
    pages.update(outline_pages(pre))
    order = sorted(recs)
    n = 0
    for lv in range(0x30, 0x40):
        mine = [k for k in order if k[0] == lv]
        d = (lv - 0x30) * 4
        pages[DIR_PAGE][d:d + 4] = bytes([len(mine) & 255, len(mine) >> 8, n & 255, n >> 8])
        for k in mine:
            o = 64 + 2 * n
            pages[DIR_PAGE + o // 8192][o % 8192:o % 8192 + 2] = bytes([k[1] & 255, k[1] >> 8])
            page, off = REC_PAGE0 + n // PER_PAGE, (n % PER_PAGE) * REC
            pages[page][off:off + REC] = recs[k]
            n += 1
    info['painted cells'] = n
    info.update(oinfo)
    banks = {b: bytes(pages[2 * b]) + bytes(pages[2 * b + 1]) for b in COLOUR_BANKS}
    from . import r_type_scenery as SC
    sbanks, info['painted scenery cells'] = SC.banks(cmap)
    banks.update(sbanks)
    return banks, dict(info)


def load_colours():
    from nexclash import coloursheet as cs, recolour as rc
    return cs.load(rc.build_colours_path(COLOURS))


def nex_peek(nex):
    from nexclash import recolour as rc
    return Peek(rc.banks(nex))


def recolour(nex, cmap):
    """A built prototype .nex + colour map -> (new .nex bytes, info). Refuses a .nex that is not
    this prototype's build of R-Type (hook sites, hook code bank, packed art, colour banks)."""
    from nexclash import recolour as rc
    from . import r_type as L
    off = rc.nex_offsets(nex)
    from . import r_type_scenery as SC
    need = set(COLOUR_BANKS) | set(range(SC.SCN_BANK0, SC.SCN_BANK0 + SC.SCN_BANKS)) | {0, 2, 5, 12}
    if not need <= set(off):
        raise ValueError('not an R-Type Layer 2 sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(nex[off[b]:off[b] + 16384])
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000] if a >= 0x4000 else 0
    data = corpus()
    if nex_peek(nex).art != _expected_art():
        raise ValueError('packed art differs from Rtype.z80 (another release?)')
    if not any(bank(12)[:len(c)] == c for c in (L.hooks()['code'],)):
        raise ValueError("hook code differs from this prototype's (rebuild with l2scroll.py)")
    for addr, old, label, op in L.SITES + L.SPRITE_SITES:
        if peek(addr) != op:
            raise ValueError('hook site 0x%04X does not hold a hook jump' % addr)
    new, info = tables(cmap, data)
    out, changed = rc.splice(nex, new)
    info['banks changed'] = changed
    return out, info


def _expected_art():
    from . import r_type as R
    return art_md5(R.source().banks)


def import_painting(nex, painted, layout=None, output=None, onto=None, replace=False, say=print):
    """The normal recolour (nexclash.recolour.run) for an R-Type painting sheet, plus:
    - faded pixels (later copies of a graphic already shown) are not read back: they are cleared from
      a working copy first, and any that were painted are reported by figure ID;
    - both sheets of the level are redrawn in the bundle with the new colours (the shared redraw
      knows neither the faded copies nor the identification sheet)."""
    import shutil
    import tempfile
    from PIL import Image
    from nexclash import coloursheet as cs, recolour as rc
    rc.engines = lambda: {RECORD: sys.modules[__name__]}     # until R-Type has a record
    lay_path = Path(layout or rc.find_layout(painted))
    lay = cs.load_layout(lay_path)
    img = Image.open(painted).convert('RGB')
    painted_faded = collections.Counter()
    for comp in lay['composites']:
        for px, py, r, g, b in comp.get('dim', ()):
            xy = (comp['x'] + px, comp['y'] + py)
            if img.getpixel(xy) != (r, g, b):
                painted_faded[comp.get('id', '?')] += 1
            img.putpixel(xy, cs.BG_RGB)
    for fid, n in sorted(painted_faded.items()):
        say('NOTE: %d faded pixel(s) of %s were painted and are ignored: paint the bright copy of that graphic'
            % (n, fid))
    work = Path(tempfile.mkdtemp(prefix='rtype_paint_'))
    try:
        clean = work / Path(painted).name
        img.save(clean)
        plain = work / (clean.stem + '_layout.json')    # recolour.run reads the layout as plain JSON
        plain.write_text(json.dumps(lay))
        out = rc.run(nex, str(clean), layout=str(plain), output=output or str(
            Path(nex).with_name(Path(nex).stem + '_painted.nex')), onto=onto, replace=replace, say=say)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    # redraw both sheets of this level with the merged colours, as the bundle's sheets
    ostem = Path(out).with_suffix('')
    merged = cs.load(str(ostem) + '_colours.json')
    if lay.get('kind') == 'scenery':
        from . import r_type_scenery as SC
        lv = level_byte(lay['sheet']) - 0x30
        SC.sheets(Path(out).parent, merged, cs.palette_rgb(PALETTE), say=lambda *a: None, only=lv,
                  prefix='%s_r_type_%s' % (ostem.name, lay['sheet']))
        say('-> %s_r_type_%s_PAINTING_SCENERY.png (redrawn with the new colours)' % (ostem, lay['sheet']))
        return out
    lname = lay.get('identify', lay_path.name).split('_')[2]    # r_type_<SHEET>_IDENTIFY.png
    redraw_level(lname, merged, Path(out).parent, '%s_r_type_%s' % (ostem.name, lname))
    say('-> %s_r_type_%s_PAINTING_SPRITES.png / _IDENTIFY.png (redrawn with the new colours)' % (ostem, lname))
    return out


def redraw_level(lname, cmap, out_dir, prefix):
    """Both sheets of one level, with the registry's IDs, into out_dir as prefix_*."""
    from nexclash import coloursheet as cs, z80tonex as Z
    from . import r_type_figures as F
    reg = registry()
    by_sig = {f['sig']: k for k, f in reg['figures'].items()}
    comps_by_level, ids_by_level = composites(corpus()), {}
    for lv, comps in comps_by_level.items():
        ids_by_level[lv] = [by_sig[c['sig']] for c in comps]
        for c, fid in zip(comps, ids_by_level[lv]):
            c['family'] = reg['figures'][fid]['family']
    from . import r_type as R
    ident = colour_identity(Peek(R.source().banks))
    for sname, comps, ids, pre in F.plan_sheets(comps_by_level, ids_by_level):
        if sname == lname:
            F.draw_level(out_dir, lname, comps, ids, reg['families'], reg['figures'], reg['families'], cmap,
                         cs.palette_rgb(PALETTE), ident, prefix=prefix, preshown=pre, drop=True)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('sheets')
    s.add_argument('-o', '--out')
    fp = sub.add_parser('figures', help='apply names / layers: {figures|families: {id: {name, layer}}}')
    fp.add_argument('patch')
    fp.add_argument('-o', '--out')
    st = sub.add_parser('restyle', help='BUILD.nex -> BUILD_styled.nex with the current registry (outlines)')
    st.add_argument('nex')
    st.add_argument('--colours', help='colour map the build holds (default: its sidecar, else the default)')
    r = sub.add_parser('recolour')
    r.add_argument('nex')
    r.add_argument('painted')
    r.add_argument('-o', '--output')
    r.add_argument('--layout')
    r.add_argument('--onto')
    r.add_argument('--replace', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'sheets':
        sheets(a.out)
    elif a.cmd == 'restyle':
        from nexclash import coloursheet as cs, recolour as rc
        nex = Path(a.nex).read_bytes()
        side = Path(a.nex).with_name(Path(a.nex).stem + '_colours.json')
        cmap = cs.load(a.colours or (str(side) if side.exists() else COLOURS))
        new, info = tables(cmap)
        out, changed = rc.splice(nex, new)
        dst = Path(a.nex).with_name(Path(a.nex).stem + '_styled.nex')
        dst.write_bytes(out)
        print(dict(info, **{'banks changed': changed}), '->', dst)
    elif a.cmd == 'figures':
        from . import r_type_figures as F
        F.apply(a.out or FIGURES.parent, json.loads(Path(a.patch).read_text()))
    else:
        from nexclash import recolour as rc
        rc.engines = lambda: {RECORD: sys.modules[__name__]}     # until R-Type has a record
        import_painting(a.nex, a.painted, layout=a.layout, output=a.output, onto=a.onto, replace=a.replace)


if __name__ == '__main__':
    main(sys.argv[1:])
