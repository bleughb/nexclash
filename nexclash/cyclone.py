"""Cyclone (Vortex Software, 1985; 48K) - engine `cyclone` (phase A: colour sheets).

Tile-map game (games/cyclone.md): every figure is composited into tiles, then 0x762C draws the map.
Figures that become sprites (user, 2026-10-21): the helicopter, its shadow, the aircraft and the
aircraft's shadow; depth as the original (behind scenery in front), shadows dithered as drawn.

    python -m nexclash.cyclone sheet cyclone.rzx [MORE.rzx ...] -o cyclone      (colour sheets)
    python -m nexclash.cyclone colours cyclone_PAINTING_SPRITES_painted.png     (read back)

Graphics (all 3 x 3 cells = 24 x 24 px, 72 bytes, column-major):
  helicopter  body 0xE8E8 + 72 * (b + 1), b = heading 0x7507 (+8 RES 4 when 0x7504 != 0), copied to
              0x6950 by 0x8CCD; the rotor is XORed in per frame (0x8CD2, deltas at 0x6700 / 0x7000).
              Columns of 24 bytes, top down. Drawn by 0x86AF at the altitude offset.
  shadow      0xED68 + 72 * (b + 1) (same b), drawn by 0x7ADC: columns of 3 cells, bottom up; a cell
              whose first byte is 0xFF is not drawn.
  aircraft    0xDDB8 + 72 * (b + 1), b = heading / 4 (+8 RES 4 with 0x7504), copied by 0x89B2 to tiles
              60-68: columns of 3 cells, top down. Its shadow = the same bytes AND 0xAA / 0x55
              (alternate bytes, 0x89BA) in tiles 51-59.
Colour-map keys: H/S/A/a + the graphics byte's address (a = aircraft shadow); R + 0x6950 offset for
rotor pixels (bits not in the body byte).
"""
import os

PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
BLACK = 8                                   # index 0 is transparent: black figures use 8
HELI_BODY, SHADOW, AIRCRAFT, HELI_BUF = 0xE8E8, 0xED68, 0xDDB8, 0x6950
PC_BODY, PC_HELI, PC_SHADOW, PC_AIR = 0x8CCD, 0x86AF, 0x7BE5, 0x89B2
GROUPS = ('Helicopter', 'Helicopter shadow', 'Aircraft', 'Aircraft shadow')
STATIC_GROUP = 'From the code (not in the recordings)'
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'cyclone_colours.json')
NOTE = ('Cyclone figure colours, read back from cyclone_PAINTING_SPRITES.png (python -m nexclash.cyclone '
        'colours). Key = H helicopter / S its shadow / A aircraft / a aircraft shadow + graphics byte '
        'address, R + offset in 0x6950 for rotor pixels; check = that byte, 8 nibbles = colours of its '
        'bits (0 = default).')


def cell_order(bottom_up):
    """Byte offset of each (column, line) of a 24 x 24 figure stored as 9 cells, column-major."""
    out = {}
    for c in range(3):
        for k in range(3):
            row = 2 - k if bottom_up else k
            for y in range(8):
                out[(c, row * 8 + y)] = (c * 3 + k) * 8 + y
    return out


def _part(group, pid, pixels, x=0, y=0):
    return dict(id=pid, size=1, w=24, h=24, x=x, y=y, mir=0, group=group, role=group,
                pixels=pixels, entries={})


def block_part(peek, kind, b):
    """Shadow ('S'), aircraft ('A') or aircraft shadow ('a') block b (0-15) -> part."""
    base = (SHADOW if kind == 'S' else AIRCRAFT) + 72 * (b + 1)
    order = cell_order(kind == 'S')
    pixels, entries = [], {}
    for (c, line), off in order.items():
        a = base + off
        if kind == 'S' and peek(base + off - off % 8) == 0xFF:
            continue                                         # cell not drawn
        v = peek(a)
        if kind == 'a':
            v &= 0xAA if off % 2 == 0 else 0x55
        key = '%s%04X' % (kind, a)
        for bit in range(8):
            if v >> (7 - bit) & 1:
                pixels.append((c * 8 + bit, line, key, bit, 1, BLACK))
                entries[key] = [peek(a), kind]
    group = {'S': GROUPS[1], 'A': GROUPS[2], 'a': GROUPS[3]}[kind]
    p = _part(group, (kind, b), pixels)
    p['entries'] = entries
    return p


def heli_part(peek, body, buf):
    """Helicopter as drawn: buf = the 72 bytes at 0x6950, body = its body block's address."""
    pixels, entries = [], {}
    for c in range(3):
        for line in range(24):
            off = c * 24 + line
            v, bv = buf[off], peek(body + off)
            for bit in range(8):
                if v >> (7 - bit) & 1:
                    if bv >> (7 - bit) & 1:
                        key = 'H%04X' % (body + off)
                        entries[key] = [bv, 'H']
                    else:
                        key = 'R%02X' % off
                        entries[key] = [0, 'R']
                    pixels.append((c * 8 + bit, line, key, bit, 1, BLACK))
    p = _part(GROUPS[0], ('H', body, bytes(buf)), pixels)
    p['entries'] = entries
    return p


def capture(rzxs):
    """Replay the recordings (C simulator) -> {part id: part} of every figure drawing seen."""
    from . import rzx as RZ
    seen, state = {}, {'body': None}

    def on_pc(pc, sim):
        m, R = sim.memory, sim.registers
        hl = R[6] << 8 | R[7]
        if pc == PC_BODY:
            state['body'] = hl
        elif pc == PC_HELI and state['body'] is not None:
            buf = bytes(m[HELI_BUF:HELI_BUF + 72])
            k = ('H', state['body'], buf)
            if k not in seen:
                seen[k] = heli_part(m.__getitem__, state['body'], buf)
        elif pc == PC_SHADOW:
            b = (hl - SHADOW) // 72 - 1
            if ('S', b) not in seen:
                seen[('S', b)] = block_part(m.__getitem__, 'S', b)
        elif pc == PC_AIR:
            b = (hl - AIRCRAFT) // 72 - 1
            for kind in 'Aa':
                if (kind, b) not in seen:
                    seen[(kind, b)] = block_part(m.__getitem__, kind, b)
    errs = []
    for path in rzxs:
        n, err = RZ.trace(path, (PC_BODY, PC_HELI, PC_SHADOW, PC_AIR), on_pc)
        errs.append((path, n, err))
    return seen, errs


def composites(seen, peek=None):
    """One composite per figure (figures are never joined); blocks the recordings never drew are
    added from the code when peek is given."""
    from . import coloursheet as cs
    comps = []
    for k, p in seen.items():
        if not p['pixels']:
            continue
        comps.append(dict(count=1, group=p['group'], parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    if peek:
        for kind in 'SAa':
            for b in range(16):
                if (kind, b) not in seen:
                    p = block_part(peek, kind, b)
                    if not p['pixels']:
                        continue
                    p['group'] = STATIC_GROUP
                    comps.append(dict(count=0, group=STATIC_GROUP, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    maxsize = {c['parts'][0]['id']: 1 for c in comps}
    order = list(GROUPS) + [STATIC_GROUP]
    comps.sort(key=lambda c: (order.index(c['group']), str(c['parts'][0]['id'][:2])))
    return cs.choose(comps, maxsize, order), comps


def sheets(comps, prefix, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix, uniq in (('_PAINTING_SPRITES', False), ('_REFERENCE_ALL_SPRITES', False)):
        png = prefix + suffix + '.png'
        n = cs.write(comps[suffix], png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours,
                     unique=uniq)
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
    ap = argparse.ArgumentParser(prog='python -m nexclash.cyclone')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', help='also show the blocks the recordings never drew (from the code)')
    p.add_argument('-o', '--out', default='cyclone')
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
        kinds = {}
        for k in seen:
            kinds[k[0]] = kinds.get(k[0], 0) + 1
        print('drawings seen:', kinds)
    elif a.cmd == 'colours':
        lay = a.layout or a.png.replace('_painted.png', '.png').replace('.png', '_layout.json')
        ent, rep = cs.read(a.png, lay)
        cs.save(ent, a.out, NOTE)
        for k, v in rep.items():
            print('%-70s %d' % (k, v))
        print('->', a.out)


if __name__ == '__main__':
    main()
