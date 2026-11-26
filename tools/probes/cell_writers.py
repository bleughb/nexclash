#!/usr/bin/env python3
"""Probe: who writes each screen cell - attribute values (and by which pc) and pixel-byte writers - over a recording.

    python tools/probes/cell_writers.py RECORDING.rzx [--rows 17-23] [--stop N] [--clash]

Invocation: any 48K / 128K RZX (screen at 0x4000). --rows picks character rows (default all 0-23). Output: one line
  per touched cell, `rRR cCC attrs <ink/paper xN ...> by <pcs> pixel writers <pc:count ...>`; --clash prints only
  cells with more than one attribute value AND a pixel writer other than the start-up drawing, the cells where two
  things of different colours can meet (the colour-clash question at design: docs/kb lessons clash-by-layer-and-no-clash).
Limits: a cell's writers are counted, not their pixels: two writers may still never overlap inside the cell; the
  128K shadow screen (bank 7) is not followed; whether a write was visible (DI, same value) is not judged.
Origin: Elite M4 HUD survey 2026-11-23 (scanner sticks reach the condition light's cells and the S cell; the bars
  switch whole cell rows: games/elite.md ## Probe).
Smoke test: Chuckie Egg, rows 0-23, 300 frames: the golden counts in selftest.py smoke_cell_writers.
"""
import argparse
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def cell_of_pixel(a):
    o = a - 0x4000
    y = ((o >> 5) & 0xC0) | ((o >> 8) & 7) | ((o >> 2) & 0x38)
    return y >> 3, o & 31


def census(rzx, rows=(0, 23), stop=None):
    """-> (attr {(row, col): Counter((value, pc))}, pix {(row, col): Counter(pc)}, frames)."""
    from nexclash import simrun
    lo, hi = rows
    attr, pix, frames = defaultdict(Counter), defaultdict(Counter), [0]

    class H:
        def on_write(self, a, v, pc, mem):
            if 0x4000 <= a < 0x5800:
                r, c = cell_of_pixel(a)
                if lo <= r <= hi:
                    pix[(r, c)][pc] += 1
            elif 0x5800 <= a < 0x5B00:
                r, c = (a - 0x5800) >> 5, a & 31
                if lo <= r <= hi:
                    attr[(r, c)][(v, pc)] += 1

        def on_frame(self, n):
            frames[0] = n

    simrun.play_rzx(rzx, H(), **({'stop': stop} if stop else {}))
    return attr, pix, frames[0]


def ink_paper(v):
    return '%s%d/%d' % ('B' if v & 0x40 else '', v & 7, (v >> 3) & 7)


def clash_cells(attr, pix, startup=1):
    """Cells with 2+ attribute values and a pixel writer that wrote more than `startup` times (not just the
    start-up drawing)."""
    out = []
    for cell in sorted(set(attr) | set(pix)):
        vals = {v for v, pc in attr.get(cell, ())}
        busy = [pc for pc, n in pix.get(cell, Counter()).items() if n > startup * 8]
        if len(vals) > 1 and busy:
            out.append(cell)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('rzx')
    ap.add_argument('--rows', default='0-23')
    ap.add_argument('--stop', type=int)
    ap.add_argument('--clash', action='store_true')
    a = ap.parse_args(argv)
    lo, hi = (int(x) for x in a.rows.split('-'))
    attr, pix, frames = census(a.rzx, (lo, hi), a.stop)
    print('frames', frames)
    cells = clash_cells(attr, pix) if a.clash else sorted(set(attr) | set(pix))
    for cell in cells:
        vals = Counter()
        for (v, pc), k in attr.get(cell, Counter()).items():
            vals[v] += k
        pcs = sorted({pc for v, pc in attr.get(cell, ())})
        print('r%02d c%02d attrs %-36s by %-24s pixel writers %s' % (
            cell[0], cell[1], ' '.join('%s x%d' % (ink_paper(v), k) for v, k in vals.most_common(6)),
            ' '.join('%04X' % x for x in pcs[:6]),
            ' '.join('%04X:%d' % (x, k) for x, k in pix.get(cell, Counter()).most_common(6))))


if __name__ == '__main__':
    main()
