"""Phase A: Jetpac colour sheets from the game's own graphic tables (no recording reaches them all).
Graphic format (29223/29247): [y offset, W bytes, H lines, W*H bytes row-major, bit 7 = left]."""
import sys, json, os
sys.path.insert(0, '/home/claude/nexclash')
from nexclash import simrun, coloursheet as cs
from skoolkit.snapshot import get_snapshot

Z, OUT = sys.argv[1], sys.argv[2]
m0 = get_snapshot(Z)
w = lambda m, a: m[a] | m[a + 1] << 8
ZX = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
RGB = cs.palette_rgb(ZX)


def gfx(m, a):
    W, H = m[a + 1], m[a + 2]
    return W, H, [m[a + 3 + k] for k in range(W * H)]


def bits(W, H, data):
    return {(8 * (k % W) + b, H - 1 - k // W) for k in range(W * H) for b in range(8) if data[k] & (0x80 >> b)}


def trim(px):
    if not px:
        return px
    x0 = min(c for c, r in px); y0 = min(r for c, r in px)
    return {(c - x0, r - y0) for c, r in px}


def part(name, group, px, dflt, x=0, y=0, keyname=None):
    px = trim(px)
    wd = max(c for c, r in px) + 1; ht = max(r for c, r in px) + 1
    k = keyname or name
    pixels, entries = [], {}
    for r in range(ht):
        for c in range(wd):
            if (c, r) in px:
                key = '%s:%d:%d' % (k, r, c // 8)
                entries[key] = [0, 1]
                pixels.append((c, r, key, c % 8, 1, dflt))
    return dict(id=name, size=ht, w=wd, h=ht, x=x, y=y, mir=0, group=group, role=name,
                pixels=pixels, entries=entries)


figs = []          # (group, [parts]) one figure each
seen = []


def add(group, name, px, dflt):
    t = trim(px)
    mir = {(max(c for c, r in t) - c, r) for c, r in t}
    if t in seen or mir in seen:
        return
    seen.append(t)
    figs.append((group, [part(name, group, t, dflt)]))


# Jetman: table 30458, types 1-2 (walk, fly), dir 0/1, shift 0
for ty, nm in ((0, 'jetman_walk'), (1, 'jetman_fly')):
    for d in (0, 1):
        for s in range(4):
            a = w(m0, 30458 + 2 * (ty * 8 + d * 4 + s))
            add('Jetman', '%s_%d_%d' % (nm, d, s), bits(*gfx(m0, a)), 15)

# rockets: 26563 words 0-11 = 4 rockets x (bottom?, mid?, top?) -> join as drawn (stacked by y offset)
tab = [w(m0, 26563 + 2 * i) for i in range(22)]
for rk in range(4):
    ps, y = [], 0
    pieces = [tab[rk + 4 * j] for j in range(3)]
    stack = []
    for j, a in enumerate(pieces):
        stack.append((j, bits(*gfx(m0, a)), gfx(m0, a)[1])); seen.append(trim(bits(*gfx(m0, a))))
    # top part first (lowest y): j order 2,1,0 guessed; heights stacked
    yy = 0
    for j, px, H in sorted(stack, key=lambda t: -t[0]):
        ps.append(part('rocket%d_%d' % (rk, j), 'Rocket', px, 15, 0, yy))
        yy += H
    figs.append(('Rocket', ps))
# fuel + items
names = {12: 'fuel', 16: 'item_a', 17: 'item_b', 18: 'item_c', 19: 'item_d', 20: 'item_e'}
for i, nm in names.items():
    add('Fuel and items', nm, bits(*gfx(m0, tab[i])), {'fuel': 15, 'item_a': 14, 'item_b': 13, 'item_c': 13, 'item_d': 12, 'item_e': 15}[nm])

# aliens: built at run time into 24064.. from table 26949 by level (24048) & 7 -> run each level
from skoolkit.simulator import Simulator
for L in range(8):
    mm = list(m0)
    mm[24048] = L
    sim = Simulator(mm, {'SP': 0xFF00, 'PC': 26921})
    mm[0xFF00] = 0; mm[0xFF01] = 0      # return to 0
    n = 0
    while sim.registers[24] != 0 and n < 2000000:
        sim.opcodes[mm[sim.registers[24]]](); n += 1
    for a in sorted({w(m0, 30458 + 2 * i) for i in range(16, 32)}):
        W, Hh, data = gfx(mm, a)
        if 1 <= W <= 4 and 1 <= Hh <= 32:
            add('Aliens', 'alien%d_%d' % (L, a), bits(W, Hh, data), 2)

import json as _j
for fr in _j.load(open('cap1.json')):
    for p in fr:
        if p['gfx'] - 1 not in tab and not (24064 <= p['gfx'] - 1 < 24268) and not (30614 <= p['gfx'] - 1 < 31646):
            add('Explosion', 'expl_%d' % p['gfx'], bits(p['W'], p['H'], p['data']), 10)
comps = []
for g, ps in figs:
    col = cs.Collector()
    col.add_frame([dict(p, group=g) for p in ps])
    comps += list(col.comps.values())
print(len(comps), 'figures:', [c['parts'][0]['id'] for c in comps])
for nm, uq in (('PAINTING_SPRITES', True), ('REFERENCE_ALL_SPRITES', False)):
    png = '%s_%s.png' % (OUT, nm)
    cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', RGB, {}, unique=uq)
    print(png)
