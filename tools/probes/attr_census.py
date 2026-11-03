"""Attribute census: which attribute bytes a screen window shows across a whole recording, sampled
every N frames (C simulator, a 135K-frame RZX in ~8 min). Answers the colour questions of the
design stage: one background attribute or several, which ink / paper the play area uses, whether
figures sit on cells of their own colour (clash) - before choosing a colour rule.

Invocation: python tools/probes/attr_census.py GAME.rzx [--rows 1-15] [--cols 2-29] [--every 50]
            [--stop N] [--top 20]  (rows / cols inclusive, in character cells)
Limits: strips autosave snapshots first. Samples the attribute file only (0x5800-0x5AFF), after
            the frame, every N frames; a colour shown for less than N frames can be missed. 48K.
Origin: Nemesis the Warlock 2026-11-03 (paper always cyan, ink black / red per cell -> sprite
            colours from the room attribute 51800; games/nemesis_the_warlock.md "Engine").
Smoke test: Chuckie Egg, rows 0-23, cols 0-31, every 50, stop 3000: 60 samples, 35 distinct sets, the
            commonest seen 6 times, starting 00 x106 (selftest.py smoke_attr_census).
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def census(rzx_path, rows=(0, 23), cols=(0, 31), every=50, stop=None):
    """-> (Counter of sorted (attr, cells) tuples per sample, number of samples)."""
    import tempfile
    from nexclash import rzx
    tmp = os.path.join(tempfile.mkdtemp(prefix='attr_census_'), 'stripped.rzx')
    if rzx.strip(rzx_path, tmp):                # autosave snapshots desync a replay (LEARNINGS 2.4)
        rzx_path = tmp
    sets = collections.Counter()
    n = [0]

    def f(frame, m):
        if frame % every:
            return
        c = collections.Counter(m[0x5800 + 32 * r + k] for r in range(rows[0], rows[1] + 1)
                                for k in range(cols[0], cols[1] + 1))
        sets[tuple(sorted(c.items()))] += 1
        n[0] += 1
    rzx._replay(rzx_path, f, stop=stop)
    return sets, n[0]


def _range(s):
    a, b = s.split('-')
    return int(a), int(b)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('rzx')
    ap.add_argument('--rows', type=_range, default=(0, 23))
    ap.add_argument('--cols', type=_range, default=(0, 31))
    ap.add_argument('--every', type=int, default=50)
    ap.add_argument('--stop', type=int)
    ap.add_argument('--top', type=int, default=20)
    a = ap.parse_args(argv)
    sets, n = census(a.rzx, a.rows, a.cols, a.every, a.stop)
    print('samples: %d (every %d frames), distinct attribute sets: %d' % (n, a.every, len(sets)))
    for k, v in sets.most_common(a.top):
        print('%6d  %s' % (v, '  '.join('%02X x%d (ink %d paper %d%s)' % (
            at, c, at & 7, (at >> 3) & 7, ' bright' if at & 0x40 else '') for at, c in k)))


if __name__ == '__main__':
    main()
