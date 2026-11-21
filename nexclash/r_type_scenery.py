"""R-Type scenery painting sheets and paint records (owner request 2026-11-20).

The scenery is drawn on Layer 2 from the game's cells (l2scroll.asm put_cell). The runtime knows a
staged cell only by its content (attribute + 8 bytes), so a painting is per distinct cell of a level:
every place that cell is used shows the same paint. The cells are those of r_type_masks.py (every
distinct cell of the level's block stream, sorted by content); their index n is both the mask entry
and the paint record.

Sheets, one per level (written by `r_type_colour.py sheets`, painted and imported like the sprite
sheets, docs/COLOURS.md):

  r_type_<LEVEL>_PAINTING_SCENERY.png + _layout.json.gz
      the whole level as the game scrolls it, in bands of 80 columns (640 pixels) one under the
      other. A distinct cell is bright (paintable) the first time it appears, faded after.

Defaults are what the build draws: ink and paper as the attribute says (bright = +8), black ink or
paper opaque black (8); black pixels that connect to open sky are see-through (grey). Paint a pixel
grey to make it see-through, or a colour to make it solid.

Keys: 'S<level>:<attribute and 8 bytes, 18 hex>:<line>', check = that line's byte; bit 0 = the
leftmost pixel. The colour map holds them next to the sprite keys.

Runtime (ship.asm scn_find, from put_cell): records of 40 bytes (8 lines x 4 bytes of nibbles,
left pixel high, 0 = default; then 8 see-through masks, bit 7 = leftmost), REC_PER_PAGE to a page,
from page SCN_PG0 (banks 64-71, always in the build); level n's cell i is record first(n) + i
(first stored at 8190 of the level's mask key page, l2scroll.scenery_banks).
"""
import gzip
import json
from pathlib import Path

SCN_BANK0 = 64
SCN_BANKS = 8
SCN_PG0 = SCN_BANK0 * 2
REC = 40
REC_PER_PAGE = 8192 // REC          # 204
BAND = 80                           # cells across one band of the sheet
TOP = 9                             # swatch row height (coloursheet SW + 4)


def key(level, cell, line):
    attr, rows = cell
    return 'S%d:%02X%s:%d' % (level, attr, bytes(rows).hex().upper(), line)


def levels():
    """{level: (cells {(cx, cy): cell}, width in cells, sorted distinct cells, masks {cell: mask})}."""
    from . import r_type_masks as SM, r_type as R
    raw = b''.join(R.images(R.source()))
    out = {}
    for lv in range(1, 9):
        data = raw[lv * 65536:(lv + 1) * 65536]
        cells, width = SM.level_cells(data)
        table, _ = SM.level_masks(data)
        out[lv] = (cells, width, sorted(table), table)
    return out


def defaults(cell, mask):
    """8x8 default colour indexes of a cell as put_cell draws it (0 = see-through)."""
    attr, rows = cell
    bright = 8 if attr & 0x40 else 0
    ink = attr & 7
    ink = ink + bright if ink else 8
    pap = (attr >> 3) & 7
    pap = pap + bright if pap else 8
    out = []
    for y in range(8):
        line = []
        for x in range(8):
            v = ink if rows[y] & (0x80 >> x) else pap
            if v == 8 and mask[y] & (0x80 >> x):
                v = 0
            line.append(v)
        out.append(line)
    return out


def _colour(cmap, k, bit, dflt):
    """Colour index of one pixel with the map applied (0 = see-through)."""
    e = cmap.get(k)
    if not e:
        return dflt
    if len(e) > 3 and e[3] & (0x80 >> bit):
        return 0
    return e[2][bit] or dflt


def draw_level(lv, data, cmap, rgb, out_dir, prefix=None, ident=None):
    """One level's scenery painting sheet + layout (coloursheet format, one composite per band)."""
    from PIL import Image
    from nexclash import coloursheet as cs
    from .r_type_colour import level_name
    cells, width, _, masks = data
    lname = level_name(0x30 + lv)
    prefix = prefix or 'r_type_%s' % lname
    bands = (width + BAND - 1) // BAND
    W, bh = BAND * 8, 20 * 8
    H = TOP + bands * (bh + 4)
    img = Image.new('RGB', (W, H), cs.BG_RGB)
    for n in range(1, 16):
        for yy in range(1, 1 + cs.SW):
            for xx in range(cs.SW):
                img.putpixel((1 + (n - 1) * (cs.SW + 2) + xx, yy), rgb[n])
    shown, comps = set(), []
    for b in range(bands):
        bx, by = 0, TOP + b * (bh + 4)
        keys, entries, pixels, show, dim = [], {}, [], [], []
        ki = {}
        for cx in range(b * BAND, min(width, (b + 1) * BAND)):
            for cy in range(20):
                cell = cells.get((cx, cy))
                if cell is None or not cell[0] & 0x80:
                    continue            # empty, or open sky (no scenery bit: never on Layer 2)
                d = defaults(cell, masks[cell])
                first = cell not in shown
                shown.add(cell)
                ox, oy = (cx - b * BAND) * 8, cy * 8
                for line in range(8):
                    k = key(lv, cell, line)
                    if k not in ki:
                        ki[k] = len(keys)
                        keys.append(k)
                        entries[k] = [cell[1][line], 'g']
                    for bit in range(8):
                        dflt = d[line][bit]
                        ink = cell[1][line] & (0x80 >> bit)
                        code = 1 if ink else (2 if dflt else 0)
                        pixels += [ox + bit, oy + line, ki[k], bit, code, dflt]
                        v = _colour(cmap, k, bit, dflt)
                        col = rgb[v] if v else cs.TRANSP_RGB
                        if first:
                            show.append([ox + bit, oy + line])
                        else:
                            from .r_type_figures import _fade
                            col = _fade(col)
                            dim.append([ox + bit, oy + line] + list(col))
                        img.putpixel((bx + ox + bit, by + oy + line), col)
        part = dict(id='%s-band%d' % (lname, b), w=BAND * 8, h=bh, dx=0, dy=0, dmir=0, vmir=0, keys=keys,
                    entries=entries, pixels=pixels)
        comps.append(dict(group=0x30 + lv, x=bx, y=by, w=W, h=bh, ox=0, oy=0, count=1, parts=[part],
                          show=sorted(show), dim=dim, id='%s-S%d' % (lname, b + 1), family=None))
    name = prefix + '_PAINTING_SCENERY.png'
    img.save(Path(out_dir) / name)
    lay = dict(size=[W, H], palette=[list(c) for c in rgb],
               colours={k: [v[0], v[1], list(v[2])] + list(v[3:4]) for k, v in cmap.items() if k.startswith('S')},
               swatches=[[1 + (n - 1) * (cs.SW + 2), 1, n] for n in range(1, 16)], composites=comps,
               paint_clear=True, kind='scenery', sheet=lname, identify=prefix + '_SCENERY',
               note='R-Type scenery painting sheet: the level in bands of %d columns; faded cells (dim) '
                    'repeat a cell already shown and are not read back' % BAND)
    if ident:
        lay['identity'] = ident
    (Path(out_dir) / (prefix + '_PAINTING_SCENERY_layout.json')).unlink(missing_ok=True)
    (Path(out_dir) / (prefix + '_PAINTING_SCENERY_layout.json.gz')).write_bytes(
        gzip.compress(json.dumps(lay).encode(), mtime=0))
    return name, len(shown), bands


def sheets(out_dir, cmap, rgb, ident=None, say=print, only=None, prefix=None):
    for lv, data in levels().items():
        if only and only != lv:
            continue
        name, n, bands = draw_level(lv, data, cmap, rgb, out_dir, prefix=prefix, ident=ident)
        say('LEVEL%d   %3d scenery cells, %2d bands -> %s' % (lv, n, bands, name))


def banks(cmap):
    """{bank: 16384 bytes} for banks SCN_BANK0.. : every level's cells in mask-table order, a record
    each (zero = as the game colours it). -> (banks, painted record count)."""
    recs = bytearray(SCN_BANKS * 16384)
    g, painted = 0, 0
    for lv, (_, _, order, _) in levels().items():
        for cell in order:
            r = bytearray(REC)
            for line in range(8):
                e = cmap.get(key(lv, cell, line))
                if not e or e[0] != cell[1][line]:
                    continue
                cols = e[2]
                for x in range(8):
                    v = cols[x] & 15
                    r[line * 4 + x // 2] |= v << 4 if x % 2 == 0 else v
                r[32 + line] = (e[3] if len(e) > 3 else 0) & 255
            if any(r):
                painted += 1
                page, slot = divmod(g, REC_PER_PAGE)
                o = page * 8192 + slot * REC
                recs[o:o + REC] = r
            g += 1
    assert g <= SCN_BANKS * 2 * REC_PER_PAGE, g
    return {SCN_BANK0 + b: bytes(recs[b * 16384:(b + 1) * 16384]) for b in range(SCN_BANKS)}, painted
