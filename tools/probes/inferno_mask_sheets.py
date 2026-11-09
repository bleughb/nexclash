#!/usr/bin/env python3
"""Inferno sprite sheets for reviewing the transparency masks.

python tools/probes/inferno_mask_sheets.py REFERENCE_DIR OUT_DIR

Reads each level's C100 actor table from InfernoN_end.z80. Per level, writes
sheet_LN_{original,B,G2,G3}.png; plus compare_closeups.png.
Magenta = transparent. original = the game's own pixels, black kept.
B = shipped rule: black is solid only when no 4-connected path reaches the canvas edge.
Gn = candidate: the outside can only enter black gaps at least n x n pixels wide.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from skoolkit.snapshot import get_snapshot

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nexclash.inferno import actor_descriptor, masked_image, raw_tile, solid_image, tile_pixels  # noqa: E402

BASE = [(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215), (0, 215, 0), (0, 215, 215), (215, 215, 0), (215, 215, 215)]
KEY = (255, 0, 255)


def rgb(c):
    """solid_image index: 1 black, 2-8 normal, 9-15 bright."""
    if c == 1:
        return (0, 0, 0)
    return BASE[c - 1] if c < 9 else tuple(255 if v else 0 for v in BASE[c - 8])


def gap_rule(w, h, px, k):
    """Black-as-solid unless a k x k block, entering from outside the canvas, can cover it."""
    if k == 1:
        return px
    W, H = w + 2 * k, h + 2 * k   # a clear margin, so blocks start outside
    clear = bytearray(b'\1' * (W * H))
    for y in range(h):
        for x in range(w):
            ink = px[y * w + x] > 1
            if ink:
                clear[(y + k) * W + x + k] = 0
    fits = bytearray(W * H)
    for y in range(H - k + 1):
        for x in range(W - k + 1):
            fits[y * W + x] = all(clear[(y + j) * W + x + i] for j in range(k) for i in range(k))
    seen, todo = bytearray(W * H), [0]
    while todo:
        at = todo.pop()
        if seen[at] or not fits[at]:
            continue
        seen[at] = 1
        x = at % W
        todo.extend(n for n, ok in ((at - 1, x), (at + 1, x + 1 < W), (at - W, at >= W), (at + W, at + W < W * H)) if ok)
    out = bytearray(W * H)
    for y in range(H):
        for x in range(W):
            if seen[y * W + x]:
                for j in range(k):
                    out[(y + j) * W + x:(y + j) * W + x + k] = b'\1' * k
    res = bytearray(px)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if px[i] <= 1:
                res[i] = 0 if out[(y + k) * W + x + k] else 1
    return bytes(res)


def original(key, left, top, w, h):
    px = bytearray(w * h)
    for x, y, raw in key:
        data = tile_pixels(raw)
        for r in range(8):
            at = (y * 8 - top + r) * w + x * 8 - left
            px[at:at + 8] = bytes(c + 1 if c < 8 else c for c in data[r * 8:r * 8 + 8])
    return bytes(px)


def paint(img, x, y, w, h, px, s):
    for j in range(h):
        for i in range(w):
            if px[j * w + i]:
                img.paste(rgb(px[j * w + i]), (x + i * s, y + j * s, x + (i + 1) * s, y + (j + 1) * s))


def actors(ram):
    seen, out = set(), []
    for image in range(256):
        try:
            d = actor_descriptor(ram, image)
            if not d['tiles']:
                continue
            key = tuple((x, y, raw_tile(ram, t)) for x, y, t in d['tiles'])
            left, top, w, h, px = solid_image(key)
            if w > 256 or h > 256:
                continue
        except (ValueError, IndexError):
            continue
        if key not in seen:
            seen.add(key)
            out.append((image, key, left, top, w, h, px))
    return out


def sheet(items, view, path, width=1400, s=3):
    x, y, row, spots = 4, 18, 0, []
    for it in items:
        w, h = it[4] * s, it[5] * s
        if x + max(w, 24) + 4 > width:
            x, y, row = 4, y + row + 18, 0
        spots.append((x, y, it))
        x += max(w, 24) + 8
        row = max(row, h)
    img = Image.new('RGB', (width, y + row + 8), KEY)
    draw = ImageDraw.Draw(img)
    for x, y, it in spots:
        draw.text((x, y - 12), '%02X' % it[0], fill=(255, 255, 255))
        paint(img, x, y, it[4], it[5], view(it), s)
    img.save(path)


def closeups(levels, out, wanted):
    views = [('original', lambda it: original(it[1], it[2], it[3], it[4], it[5])), ('B shipped', lambda it: it[6]),
             ('G2', lambda it: gap_rule(it[4], it[5], it[6], 2)), ('G3', lambda it: gap_rule(it[4], it[5], it[6], 3))]
    s, rows = 4, [next(it for it in levels[l] if it[0] == i) for l, i in wanted]
    W = 16 + sum(max(max(it[4] for it in rows) * s, 90) + 12 for _ in views)
    img = Image.new('RGB', (W, 30 + sum(it[5] * s + 12 for it in rows)), KEY)
    draw = ImageDraw.Draw(img)
    col = max(max(it[4] for it in rows) * s, 90) + 12
    for n, (name, _) in enumerate(views):
        draw.text((8 + n * col, 8), name, fill=(255, 255, 255))
    y = 26
    for it in rows:
        for n, (_, v) in enumerate(views):
            paint(img, 8 + n * col, y, it[4], it[5], v(it), s)
        y += it[5] * s + 12
    img.save(out / 'compare_closeups.png')


def main():
    ref, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    levels = {}
    for level in range(1, 7):
        items = actors(bytes(get_snapshot(str(ref / ('Inferno%d_end.z80' % level)))))
        levels[level] = items
        sheet(items, lambda it: original(it[1], it[2], it[3], it[4], it[5]), out / ('sheet_L%d_original.png' % level))
        sheet(items, lambda it: it[6], out / ('sheet_L%d_B.png' % level))
        sheet(items, lambda it: masked_image(it[1], it[0])[4], out / ('sheet_L%d_final.png' % level))
        for k in (2, 3):
            sheet(items, lambda it: gap_rule(it[4], it[5], it[6], k), out / ('sheet_L%d_G%d.png' % (level, k)))
        print('L%d: %d images' % (level, len(items)))
    wanted = [tuple(map(int, a.split(':'))) for a in sys.argv[3:]]
    if wanted:
        closeups(levels, out, wanted)


if __name__ == '__main__':
    main()
