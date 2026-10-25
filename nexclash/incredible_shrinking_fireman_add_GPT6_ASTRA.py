"""The Incredible Shrinking Fireman (Mastertronic, 1986; 48K) - engine `incredible_shrinking_fireman_add_GPT6_ASTRA`.

Phase A (this file so far): capture of every figure the game draws, the colour sheets.

    python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA sheet R.rzx [MORE.rzx] --z80 GAME.z80 -o PREFIX
    python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA colours PREFIX_PAINTING_SPRITES_painted.png

Figures (games/incredible_shrinking_fireman-add-GPT6_ASTRA.md):
  0xB950 moves object A (A = 0 fireman, 1 / 2 the room's two enemies) of the 8-byte table at 0xBCF7
  (x, y, frame, -, dx, dy, attribute, attribute keep-mask) to (x + dx, y + dy) showing frame (0xBCF6),
  XORing old ^ new graphic into the screen in ONE pass (delta draw); frame 0 is blank (appear /
  disappear). Then 0xBC5F paints the figure's 2 x 3 (3 x 4 unaligned) cells: attr = (scr ^ E) & D ^ E,
  E = attribute, D = keep-mask, cells flagged by bit 6 in the map at 0xBD44 left alone.
  Graphics: 16 x 24 px, 2 bytes per line top down, at base (0xBD42, 0x9C40 in every recording) +
  ((3 * frame) & 255) * 16 - the game's 8-bit multiply: frames >= 86 wrap.
Colour-map keys: G + the graphics byte's address; default colour = the ink the game gives the figure
(fireman: white; enemies: their room's bright ink).
"""
# Phase-A capture adapted from the existing add-OPUS module; no conversion claims.
import collections
import json
import os

PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
BLACK = 8                                   # index 0 is transparent: black figures use 8
PLOT, OBJ, NEWF, GBASE, ATTRMAP = 0xB950, 0xBCF7, 0xBCF6, 0xBD42, 0xBD44
W, H = 16, 24
GROUPS = ('Fireman', 'Enemies')
STATIC_GROUP = 'From the code (not in the recordings)'
_HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = 'incredible_shrinking_fireman-add-GPT6_ASTRA'
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'incredible_shrinking_fireman_colours-add-GPT6_ASTRA.json')
NOTE = ('Incredible Shrinking Fireman figure colours, read back from the PAINTING_SPRITES sheet '
        '(python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA colours). Key = G + graphics byte + source ink (D for diamond); '
        'address; check = that byte, 8 nibbles = colours of its bits (0 = the game\'s ink).')


def gfx_addr(base, frame):
    """Address of a frame's 48 bytes: the plotter's own (8-bit) arithmetic."""
    return (base + ((3 * frame) & 255) * 16) & 0xFFFF


def ink_index(attr):
    """Spectrum attribute -> sheet palette index of its ink (black -> BLACK)."""
    ink = attr & 7
    if not ink:
        return BLACK
    return ink + (8 if attr & 64 else 0)


def figure_part(peek, base, frame, group, ink):
    a0 = gfx_addr(base, frame)
    pixels, entries = [], {}
    for line in range(H):
        for half in range(2):
            a = (a0 + line * 2 + half) & 0xFFFF
            v = peek(a)
            key = 'G%04X_I%02d' % (a, ink)
            for bit in range(8):
                if v >> (7 - bit) & 1:
                    pixels.append((half * 8 + bit, line, key, bit, 1, ink))
                    entries[key] = [v, 'G']
    return dict(id=(base, frame), size=1, w=W, h=H, x=0, y=0, mir=0, group=group, role=group,
                pixels=pixels, entries=entries)


def capture(rzxs):
    """Replay the recordings (C simulator) -> {(group, base, frame, ink): info} of every drawing seen."""
    from . import rzx as RZ
    seen = collections.OrderedDict()

    def on_pc(pc, sim):
        m, R = sim.memory, sim.registers
        a = R[0]
        o = m[OBJ + 8 * a:OBJ + 8 * a + 8]
        f, base = m[NEWF], m[GBASE] | m[GBASE + 1] << 8
        if not f:
            return
        group = GROUPS[0] if a == 0 else GROUPS[1]
        k = (group, base, f, ink_index(o[6]))
        e = seen.get(k)
        if e is None:
            e = seen[k] = dict(group=group, base=base, frame=f, inks=collections.Counter(), count=0,
                               gfx=bytes(m[gfx_addr(base, f) + i & 0xFFFF] for i in range(48)))
        e['inks'][ink_index(o[6])] += 1
        e['count'] += 1
    errs = []
    for path in rzxs:
        n, err = RZ.trace(path, (PLOT,), on_pc)
        errs.append((path, n, err))
    return seen, errs


def composites(seen, peek=None):
    """One composite per (group, graphic, ink): figures are single plots, never joined. A graphic drawn by
    both groups appears in each. peek: the bank's frames the recordings never drew are added."""
    from . import coloursheet as cs
    comps, drawn = [], set()
    for (group, base, f, ink), e in seen.items():
        g = e['gfx']
        p = figure_part(lambda a: g[(a - gfx_addr(base, f)) & 0xFFFF], base, f, group,
                        ink)
        drawn.add((base, f))
        if p['pixels']:
            p['id'] = (base, f, ink)
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
        stem = prefix.removesuffix('-add-GPT6_ASTRA') + suffix
        png = stem + '-add-GPT6_ASTRA.png'
        n = cs.write(comps[suffix], png, stem + '_layout-add-GPT6_ASTRA.json', rgb16, colours,
                     unique=False)
        out.append((png, n))
    return out


def collectable_sheets(z80, prefix):
    """Room-table items all use the seven-byte diamond at 0xED14.

    0xECFF draws rows bottom to top (DEC B); retain that order in the keys.
    Default white is a proposal, pending the phase-A design answer.
    """
    peek = _peek(z80)
    pixels, entries = [], {}
    for y in range(7):
        addr = 60692 + 6 - y
        value = peek(addr)
        key = 'D%04X' % addr
        entries[key] = [value, 'D']
        for bit in range(8):
            pixels.append((bit, y, key, bit, int(bool(value & (128 >> bit))), 7))
    part = dict(id=(60692, 7), size=1, w=8, h=7, x=0, y=0, mir=0,
                group='Collectables', role='Collectables', pixels=pixels, entries=entries,
                dx=0, dy=0, dmir=0, vmir=0)
    comps = [dict(count=1, group='Collectables', parts=[part])]
    return sheets(dict(_PAINTING_SPRITES=comps, _REFERENCE_ALL_SPRITES=comps),
                  prefix.removesuffix('-add-GPT6_ASTRA') + '_COLLECTABLES', load_colours())


def plain(z80, output):
    """Plain baseline only: preserve the game's printer buffer across NEXLOAD."""
    from . import z80tonex as zt
    from .nextboot import check
    zt.convert(z80, output, tail_req=0x5E40, keep_printer_buffer=True)
    tail = zt.build_tail(zt.Z80Snapshot(z80), 0x5E40)[0]
    for nexload in (False, True):
        bad = check(output, z80, tail=(0x5E40, 0x5E40 + len(tail)), nexload=nexload)
        if bad:
            raise ValueError('Plain boot failed: %r' % bad)
    print('Plain boot: PASS, including NEXLOAD printer-buffer overwrite')


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
    ap = argparse.ArgumentParser(prog='python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', help='also show the frames the recordings never drew (from the code)')
    p.add_argument('-o', '--out', default=RECORD)
    p = sub.add_parser('plain', help='plain NEX baseline, with simulated boot checks')
    p.add_argument('z80')
    p.add_argument('-o', '--out', required=True)
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
        if any(err for _, _, err in errs):
            raise SystemExit('Recording desynchronised: sheets withheld')
        chosen, every = composites(seen, _peek(a.z80) if a.z80 else None)
        for png, n in sheets({'_PAINTING_SPRITES': chosen, '_REFERENCE_ALL_SPRITES': every}, a.out,
                             load_colours()):
            print('%s: %d figures' % (png, n))
        if a.z80:
            for png, n in collectable_sheets(a.z80, a.out):
                print('%s: %d figures' % (png, n))
        g = collections.Counter(k[0] for k in seen)
        print('graphics drawn per group:', dict(g))
        for k, e in seen.items():
            if len(e['inks']) > 1:
                print('  %s frame %d drawn in inks %s' % (k[0], k[2], dict(e['inks'])))
    elif a.cmd == 'plain':
        plain(a.z80, a.out)
    elif a.cmd == 'colours':
        lay = a.layout or a.png.replace('_painted-add-GPT6_ASTRA.png', '-add-GPT6_ASTRA.png').replace('-add-GPT6_ASTRA.png', '_layout-add-GPT6_ASTRA.json')
        ent, rep = cs.read(a.png, lay)
        cs.save(ent, a.out, NOTE)
        for k, v in rep.items():
            print('%-70s %d' % (k, v))
        print('->', a.out)


if __name__ == '__main__':
    main()
