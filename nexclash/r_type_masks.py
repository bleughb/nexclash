"""Scenery see-through masks (owner request 2026-11-17: no sharp 8x8 edges).

The whole of each level's scenery is drawn from its block stream (the same decoding as
background_contract.expected, verified against the game's own FEEB), then every black scenery pixel
that connects (up, down, left, right; across cells and blocks) to open sky is marked see-through.
Black enclosed by scenery, and coloured paper, stay solid. The runtime knows a staged cell only by
its content (attribute + 8 bytes), so the result is one 8-byte mask per distinct scenery cell of a
level: the majority over the places that cell is used (conflicts are counted and reported).

    py -3 r_type_masks.py [--stats]
"""
import collections
import json
import sys
from pathlib import Path

GAP = 2                         # black gaps this narrow between scenery parts stay solid


def word(data, a):
    return data[a] | data[a + 1] << 8


def level_cells(data):
    """{(cx, cy): (attr, bytes8)} for every drawn cell of the level (cy 0..19)."""
    base, end = word(data, 0xC4BC), word(data, 0xC4B4)
    columns = (end - base) // 5
    cells = {}
    for column in range(columns):
        for blockrow in range(5):
            tile = data[base + column * 5 + blockrow]
            source = (base - (((tile + 1) * 4) & 255) * 36) & 65535
            for sy in range(4):
                for sx in range(4):
                    cell = source + (sy * 4 + sx) * 9
                    attr = data[cell]
                    if attr == 0x36:
                        continue
                    x = column * 4 + (3 - sx if tile & 64 else sx)
                    row = blockrow * 4 + (3 - sy if tile & 128 else sy)
                    rows = [0] * 8
                    for py in range(8):
                        b = data[cell + 1 + py]
                        if tile & 64:
                            b = data[0x5D00 + b]
                        rows[7 - py if tile & 128 else py] = b
                    cells[(x, row)] = (attr, tuple(rows))
    return cells, columns * 4


def open_black(cells, width):
    """{(cx, cy): mask8} of see-through pixels (bit 7 = leftmost) of every scenery cell."""
    H, W = 160, width * 8
    solid = bytearray(W * H)        # 1 = blocks the flood (lit or coloured scenery)
    black = bytearray(W * H)        # 1 = black scenery pixel (a flood can pass and open it)
    for (cx, cy), (attr, rows) in cells.items():
        if not attr & 0x80:
            continue                # not scenery: open sky for the flood
        ink, paper = attr & 7, (attr >> 3) & 7
        for py, b in enumerate(rows):
            for bit in range(8):
                on = b & (0x80 >> bit)
                coloured = (ink if on else paper) != 0
                i = (cy * 8 + py) * W + cx * 8 + bit
                if coloured:
                    solid[i] = 1
                else:
                    black[i] = 1
    # a black run of up to GAP pixels with coloured scenery on both sides (across or down) is a wall:
    # narrow gaps between scenery parts stay solid (owner, 2026-11-17)
    wall = bytearray(solid)
    for y in range(H):
        x = 0
        while x < W:
            i = y * W + x
            if not black[i]:
                x += 1
                continue
            e = x
            while e < W and black[y * W + e]:
                e += 1
            if x > 0 and e < W and solid[i - 1] and solid[y * W + e] and e - x <= GAP:
                for k in range(x, e):
                    wall[y * W + k] = 1
            x = e
    for x in range(W):
        y = 0
        while y < H:
            i = y * W + x
            if not black[i]:
                y += 1
                continue
            e = y
            while e < H and black[e * W + x]:
                e += 1
            if y > 0 and e < H and solid[i - W] and solid[e * W + x] and e - y <= GAP:
                for k in range(y, e):
                    wall[k * W + x] = 1
            y = e
    seen = bytearray(W * H)
    stack = [i for i in range(W * H) if not solid[i] and not black[i]]   # sky
    for i in stack:
        seen[i] = 1
    while stack:
        i = stack.pop()
        x, y = i % W, i // W
        for j, ok in ((i - 1, x > 0), (i + 1, x < W - 1), (i - W, y > 0), (i + W, y < H - 1)):
            if ok and not seen[j] and not wall[j]:
                seen[j] = 1
                stack.append(j)
    out = {}
    for (cx, cy), (attr, rows) in cells.items():
        if not attr & 0x80:
            continue
        m = []
        for py in range(8):
            v = 0
            for bit in range(8):
                i = (cy * 8 + py) * W + cx * 8 + bit
                if black[i] and seen[i]:
                    v |= 0x80 >> bit
            m.append(v)
        out[(cx, cy)] = tuple(m)
    return out


def level_masks(data):
    """{(attr, rows): mask} by content for every distinct scenery cell (mask all zero when nothing
    is see-through), majority per pixel; plus stats."""
    cells, width = level_cells(data)
    opened = open_black(cells, width)
    votes = collections.defaultdict(list)
    for pos, m in opened.items():
        votes[cells[pos]].append(m)
    table, conflicts, opened_cells = {}, 0, 0
    for key, ms in votes.items():
        if len(set(ms)) > 1:
            conflicts += 1
        mask = []
        for py in range(8):
            v = 0
            for bit in range(8):
                if 2 * sum(1 for m in ms if m[py] & (0x80 >> bit)) > len(ms):
                    v |= 0x80 >> bit
            mask.append(v)
        if any(mask):
            opened_cells += 1
        table[key] = tuple(mask)        # every distinct cell: the runtime index is also its paint record
    return table, dict(width_cells=width, scenery_cells=len(opened), distinct=len(votes),
                       distinct_with_see_through=opened_cells, distinct_with_conflicts=conflicts)


def all_levels():
    from . import r_type as R
    raw = b''.join(R.images(R.source()))
    out = {}
    for level in range(1, 9):
        out[level] = level_masks(raw[level * 65536:(level + 1) * 65536])
    return out


if __name__ == '__main__':
    for level, (table, stats) in all_levels().items():
        print(level, json.dumps(stats))
