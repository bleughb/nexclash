"""Mad Mix 2: the Enhanced tables from the Spec256 set the owner has. They derive from its painting, so they stay beside the snapshot,
never in this repo. `python -m nexclash.mad_mix_2_art GAME.z80 SET.256 PAL PANEL.ppm OUT.bin`

The index on Layer 2 is the set's own value v, so a star's inverse is a CPL. The set's v = 0xFF is the plain Spectrum pixel, ink or paper by
the master bit: 253 and 254, palette entries the flip keeps to the stage's attribute. 255 is transparent. Above 0xBF the set averages the
palette with the cell's ink, black in stage group 1. The tile store is stage group 1 only, the group the set holds. The panel is one picture,
the set's own screen; the game's text and lives are painted on it as it prints them, from the font and one life in the last page. 
"""
import json, struct, sys
from pathlib import Path
from skoolkit.snapshot import Snapshot

BK, REC, PAGE = 16384, 9, 8192
MAGIC = b'MM2E'
INK, PAPER, SKIP = 253, 254, 255
TILES_AT, TILES = 0xB515, 95
FIGS = 0xB36A
NFIGS = 105
FIRST_PAGE = 44              # bank 22 up


def at(a):
    return (5, 2, 0)[(a >> 14) - 1] * BK * REC + (a & 0x3FFF) * REC


def rgb9(c):
    r, g, b = [min(7, (x * 7 + 127) // 255) for x in c]
    if r == 7 and g == 0 and (b >> 1) == 3:
        r = 6
    return r, g, b


def build(z80, set256, pal_path, panel_ppm):
    mem = bytes(Snapshot.get(z80).memory[0:65536])
    d = Path(set256).read_bytes()
    pal = [tuple(int(x) for x in ln.split()) for ln in Path(pal_path).read_text().splitlines() if ln.strip()][:256]
    def val(a, b):
        o = at(a)
        return sum(((d[o + k] >> (7 - b)) & 1) << k for k in range(8))
    def same(a, n):
        return all(mem[a + i] == d[at(a + i) + 8] for i in range(n))
    used = set()
    used_font = set()
    rep = dict(tiles_differ=[], figs_differ=[], or_pixels=0)
    tiles = bytearray()
    for t in range(TILES):
        a = TILES_AT + t * 64
        if not same(a, 64):
            rep['tiles_differ'].append(t)
        for i in range(64):
            for b in range(8):
                v = val(a + i, b)
                if v == 0xFF:
                    tiles.append(INK if mem[a + i] & (0x80 >> b) else PAPER)
                else:
                    tiles.append(v)
                    used.add(v)
    store, index = [bytearray()], bytearray(NFIGS * 4)
    for i in range(NFIGS):
        e = FIGS + i * 4
        rows, w, p = mem[e], mem[e + 1], mem[e + 2] | mem[e + 3] << 8
        if not (1 <= rows <= 48 and w == 3 and 0x6000 <= p < 0x9000):
            raise ValueError('figure %d' % i)
        if not same(p, rows * 6):
            rep['figs_differ'].append(i)
        px = bytearray()
        for r in range(rows * 3):
            for b in range(8):
                vm, vg = val(p + r * 2, b), val(p + r * 2 + 1, b)
                if vm == 0xFF:
                    if vg:
                        rep['or_pixels'] += 1
                        px.append(vg if vg != 0xFF else INK)
                        used.add(vg)
                    else:
                        px.append(SKIP)
                elif vg == 0xFF:
                    px.append(INK if mem[p + r * 2 + 1] & (0x80 >> b) else PAPER)
                else:
                    px.append(vg)
                    used.add(vg)
        if len(store[-1]) + len(px) > PAGE:
            store.append(bytearray())
        index[i * 4:i * 4 + 4] = struct.pack('<BHB', len(store) - 1, len(store[-1]), rows)
        store[-1] += px
    pals = [pal[v] if v < 0xC0 else tuple(x >> 1 for x in pal[v]) for v in range(256)]
    for ch in range(0x20, 0x60):
        a = (0xA70A if ch >= 0x41 else (0xA93A if ch == 0x20 else 0xA86A)) + ch * 8
        for i in range(8):
            for b in range(8):
                used_font.add(val(a + i, b))
    reserved = used | used_font | {(~v) & 255 for v in used} | {INK, PAPER, SKIP, 0}
    free = [v for v in range(1, 253) if v not in reserved]
    ppm = Path(panel_ppm).read_bytes().split(b'\n', 3)[3]
    pan_of, l2 = {}, bytearray(b'\xff' * (256 * 192))
    for y in range(192):
        for x in range(256):
            if 32 <= x < 224 and 16 <= y < 160:      # the window
                continue
            c = tuple(ppm[(y * 256 + x) * 3:(y * 256 + x) * 3 + 3])
            if c == (0, 0, 0):
                l2[y * 256 + x] = 0
                continue
            if c not in pan_of:
                if free:
                    pan_of[c] = free.pop(0)
                    pals[pan_of[c]] = c
                else:
                    pan_of[c] = min(range(253), key=lambda i: sum((m - n) ** 2 for m, n in zip(pals[i], c)))
            l2[y * 256 + x] = pan_of[c]
    # the font: as A8C8 finds it; the plain pixel lets the screen's own attributes through
    glyph = bytearray()
    for ch in range(0x20, 0x60):
        base = 0xA70A if ch >= 0x41 else (0xA93A if ch == 0x20 else 0xA86A)
        a = base + ch * 8
        if not same(a, 8):
            rep.setdefault('font_differs', []).append(ch)
        for i in range(8):
            for b in range(8):
                v = val(a + i, b)
                if v == 0xFF:
                    glyph.append(SKIP)
                else:
                    glyph.append(v)
                    used_font.add(v)
    glyph = glyph.ljust(0x1000, b'\xff')
    for y in range(168, 192):
        glyph += l2[y * 256 + 0x68:y * 256 + 0x68 + 24]
    glyph = glyph.ljust(0x1240, b'\xff')
    blank = l2[170 * 256 + 0x68 + 28]
    glyph += bytes([blank]) * 576
    rep['life_blank'] = blank
    palette = bytearray()
    for v in range(256):
        r, g, b = rgb9(pals[v])
        palette += bytes((r << 5 | g << 2 | b >> 1, b & 1))
    palette[SKIP * 2:SKIP * 2 + 2] = bytes((0xE3, 0))
    palette[INK * 2:INK * 2 + 2] = bytes((0, 0))
    palette[PAPER * 2:PAPER * 2 + 2] = bytes((0xFF, 1))
    tp = (len(tiles) + PAGE - 1) // PAGE
    rep.update(colours=len(used), panel_colours=len(pan_of), free_left=len(free), tile_pages=tp, figure_pages=len(store))
    blob = MAGIC + struct.pack('<HH', tp, len(store)) + bytes(palette) + bytes(index) + bytes(l2) + bytes(tiles).ljust(tp * PAGE, b'\xff') + b''.join(bytes(x).ljust(PAGE, b'\xff') for x in store) + bytes(glyph).ljust(PAGE, b'\xff')
    return blob, rep


def load(path):
    d = Path(path).read_bytes()
    if d[:4] != MAGIC:
        raise ValueError('%s is not a Mad Mix 2 colour table' % path)
    tp, ns = struct.unpack('<HH', d[4:8])
    o = 8
    pal = d[o:o + 512]; o += 512
    index = d[o:o + NFIGS * 4]; o += NFIGS * 4
    l2 = d[o:o + 256 * 192]; o += 256 * 192
    tiles = d[o:o + tp * PAGE]; o += tp * PAGE
    store = [d[o + i * PAGE:o + (i + 1) * PAGE] for i in range(ns)]
    o += ns * PAGE
    return dict(palette=pal, index=index, panel=l2, tiles=tiles, tile_pages=tp, store=store, glyph=d[o:o + PAGE])


def main():
    z, st, pal, panel, out = sys.argv[1:6]
    blob, rep = build(z, st, pal, panel)
    Path(out).write_bytes(blob)
    print(json.dumps(rep))


if __name__ == '__main__':
    main()
