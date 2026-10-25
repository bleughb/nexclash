"""The Incredible Shrinking Fireman (Mastertronic, 1986; 48K) - engine `incredible_shrinking_fireman_add_opus`.

Phase A (this file so far): capture of every figure the game draws, the colour sheets.

    python -m nexclash.incredible_shrinking_fireman_add_opus sheet R.rzx [MORE.rzx] --z80 GAME.z80 -o PREFIX
    python -m nexclash.incredible_shrinking_fireman_add_opus colours PREFIX_PAINTING_SPRITES_painted.png

Figures (games/incredible_shrinking_fireman-add-OPUS.md):
  0xB950 moves object A (A = 0 fireman, 1 / 2 the room's two enemies) of the 8-byte table at 0xBCF7
  (x, y, frame, -, dx, dy, attribute, attribute keep-mask) to (x + dx, y + dy) showing frame (0xBCF6),
  XORing old ^ new graphic into the screen in ONE pass (delta draw); frame 0 is blank (appear /
  disappear). Then 0xBC5F paints the figure's 2 x 3 (3 x 4 unaligned) cells: attr = (scr ^ E) & D ^ E,
  E = attribute, D = keep-mask, cells flagged by bit 6 in the map at 0xBD44 left alone.
  Graphics: 16 x 24 px, 2 bytes per line top down, at base (0xBD42, 0x9C40 in every recording) +
  ((3 * frame) & 255) * 16 - the game's 8-bit multiply: frames >= 86 wrap.
Collectables (the diamonds): per room up to 5 entries (flag, column, y) via the table at 0xD6ED; 0xECCF
(room build) draws each with 0xECFF: 7 lines of 0xED14 written (not XORed) at (8 * C, B); a pickup
(option screen) zeroes the entry (0xED37) and the room is drawn again without it.
Colour-map keys: G + the graphics byte's address, D + address for the collectable; default colour =
the ink the game gives the figure (fireman: white; enemies: their room's bright ink; collectables:
their cell's ink).
"""
import collections
import json
import os

PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
BLACK = 8                                   # index 0 is transparent: black figures use 8
PLOT, OBJ, NEWF, GBASE, ATTRMAP = 0xB950, 0xBCF7, 0xBCF6, 0xBD42, 0xBD44
ITEM, ITEM_GFX, ITEM_H = 0xECFF, 0xED14, 7       # collectable: 7 lines at (8 * C, B), overwrite
W, H = 16, 24
GROUPS = ('Fireman', 'Enemies', 'Collectables')
STATIC_GROUP = 'From the code (not in the recordings)'
_HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = 'incredible_shrinking_fireman-add-OPUS'
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')
NOTE = ('Incredible Shrinking Fireman figure colours, read back from the PAINTING_SPRITES sheet '
        '(python -m nexclash.incredible_shrinking_fireman_add_opus colours). Key = G + graphics byte '
        'address; check = that byte, 8 nibbles = colours of its bits (0 = the game\'s ink).')


def gfx_addr(base, frame):
    """Address of a frame's 48 bytes: the plotter's own (8-bit) arithmetic."""
    return (base + ((3 * frame) & 255) * 16) & 0xFFFF


def ink_index(attr, mask=0):
    """Attribute (and the plotter's keep-mask) -> palette index of the figure's ink (black -> BLACK).
    Bright when the attribute or the keep-mask has bit 6: the room build sets BRIGHT on every cell,
    so a figure that keeps the cell's bright bit (the fireman, mask 0x40) shows bright."""
    ink = attr & 7
    if not ink:
        return BLACK
    return ink + (8 if (attr | mask) & 64 else 0)


def figure_part(peek, base, frame, group, ink):
    a0 = gfx_addr(base, frame)
    pixels, entries = [], {}
    for line in range(H):
        for half in range(2):
            a = (a0 + line * 2 + half) & 0xFFFF
            v = peek(a)
            key = 'G%04X' % a
            for bit in range(8):
                if v >> (7 - bit) & 1:
                    pixels.append((half * 8 + bit, line, key, bit, 1, ink))
                    entries[key] = [v, 'G']
    return dict(id=(base, frame), size=1, w=W, h=H, x=0, y=0, mir=0, group=group, role=group,
                pixels=pixels, entries=entries)


def item_part(peek, ink):
    pixels, entries = [], {}
    for line in range(ITEM_H):                   # byte j is drawn on line B - j: row 6 - j
        a = ITEM_GFX + ITEM_H - 1 - line
        v = peek(a)
        key = 'D%04X' % a
        for bit in range(8):
            if v >> (7 - bit) & 1:
                pixels.append((bit, line, key, bit, 1, ink))
                entries[key] = [v, 'D']
    return dict(id=('item', ITEM_GFX), size=1, w=8, h=ITEM_H, x=0, y=0, mir=0, group=GROUPS[2],
                role=GROUPS[2], pixels=pixels, entries=entries)


def capture(rzxs):
    """Replay the recordings (C simulator) -> {(group, base, frame): info} of every drawing seen."""
    from . import rzx as RZ
    seen = collections.OrderedDict()

    def on_pc(pc, sim):
        m, R = sim.memory, sim.registers
        if pc == ITEM:
            y, col = R[2], R[3]
            at = m[0x5800 + (y >> 3) * 32 + col]
            k = (GROUPS[2], ITEM_GFX, 0)
            e = seen.get(k)
            if e is None:
                e = seen[k] = dict(group=GROUPS[2], base=ITEM_GFX, frame=0, inks=collections.Counter(),
                                   count=0, gfx=bytes(m[ITEM_GFX:ITEM_GFX + ITEM_H]))
            e['inks'][ink_index(at)] += 1
            e['count'] += 1
            return
        a = R[0]
        o = m[OBJ + 8 * a:OBJ + 8 * a + 8]
        f, base = m[NEWF], m[GBASE] | m[GBASE + 1] << 8
        if not f:
            return
        group = GROUPS[0] if a == 0 else GROUPS[1]
        k = (group, base, f)
        e = seen.get(k)
        if e is None:
            e = seen[k] = dict(group=group, base=base, frame=f, inks=collections.Counter(), count=0,
                               gfx=bytes(m[gfx_addr(base, f) + i & 0xFFFF] for i in range(48)))
        e['inks'][ink_index(o[6], o[7])] += 1
        e['count'] += 1
    errs = []
    for path in rzxs:
        n, err = RZ.trace(path, (PLOT, ITEM), on_pc)
        errs.append((path, n, err))
    return seen, errs


def composites(seen, peek=None):
    """One composite per (group, graphic): figures are single plots, never joined. A graphic drawn by
    both groups appears in each. peek: the bank's frames the recordings never drew are added."""
    from . import coloursheet as cs
    comps, drawn = [], set()
    for (group, base, f), e in seen.items():
        g = e['gfx']
        if group == GROUPS[2]:
            p = item_part(lambda a: g[a - ITEM_GFX], e['inks'].most_common(1)[0][0])
            comps.append(dict(count=e['count'], group=group, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
            continue
        p = figure_part(lambda a: g[(a - gfx_addr(base, f)) & 0xFFFF], base, f, group,
                        e['inks'].most_common(1)[0][0])
        drawn.add((base, f))
        if p['pixels']:
            comps.append(dict(count=e['count'], group=group, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    if peek:
        base = peek(GBASE) | peek(GBASE + 1) << 8
        for f in range(1, 86):                       # every whole frame of the bank (3f < 256)
            if (base, f) in drawn:
                continue
            p = figure_part(peek, base, f, STATIC_GROUP, 7)
            if p['pixels']:
                comps.append(dict(count=0, group=STATIC_GROUP, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    order = list(GROUPS) + [STATIC_GROUP]
    comps.sort(key=lambda c: (order.index(c['group']), c['parts'][0]['id']))
    maxsize = {c['parts'][0]['id']: 1 for c in comps}
    return cs.choose(comps, maxsize, order), comps


def sheets(comps, prefix, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix in ('_PAINTING_SPRITES', '_REFERENCE_ALL_SPRITES'):
        png = prefix + suffix + '.png'
        n = cs.write(comps[suffix], png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours,
                     unique=False)
        out.append((png, n))
    return out


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    p = path or build_colours_path(COLOURS)
    return cs.load(p) if os.path.exists(p) else {}


def _peek(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536])).__getitem__


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.incredible_shrinking_fireman_add_opus')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', help='also show the frames the recordings never drew (from the code)')
    p.add_argument('-o', '--out', default=RECORD)
    p = sub.add_parser('colours', help='painted PAINTING sheet -> colours json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--out', default=COLOURS)
    a = ap.parse_args(argv)
    from . import coloursheet as cs
    if a.cmd == 'sheet':
        seen, errs = capture(a.rzx)
        for path, n, err in errs:
            print('%s: %d frames%s' % (path, n, ', DESYNC: ' + err if err else ''))
        chosen, every = composites(seen, _peek(a.z80) if a.z80 else None)
        for png, n in sheets({'_PAINTING_SPRITES': chosen, '_REFERENCE_ALL_SPRITES': every}, a.out,
                             load_colours()):
            print('%s: %d figures' % (png, n))
        g = collections.Counter(k[0] for k in seen)
        print('graphics drawn per group:', dict(g))
        for k, e in seen.items():
            if len(e['inks']) > 1:
                print('  %s frame %d drawn in inks %s' % (k[0], k[2], dict(e['inks'])))
    elif a.cmd == 'colours':
        lay = a.layout or a.png.replace('_painted.png', '.png').replace('.png', '_layout.json')
        ent, rep = cs.read(a.png, lay)
        cs.save(ent, a.out, NOTE)
        for k, v in rep.items():
            print('%-70s %d' % (k, v))
        print('->', a.out)


if __name__ == '__main__':
    main()
