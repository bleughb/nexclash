"""Phantis / Game Over 2 part 1: the Enhanced colour table, from the Spec256 set the owner has. The output is derived from the
set's painting, so it stays beside the snapshot, never in this repo. `python -m nexclash.phantis_art GAME.z80 SET.256 PAL OUT.bin [RZX...]`

Every graphic of the game (3-byte header: rows x 2, width, ink; then graphics; then masks) found byte for byte in the set gets one
Layer 2 index per pixel. Index 0 in the set shows the background: black where the graphic has ink, a punch where only its mask is
set. 0xC0 and up mix the cell's ink into bits 3-5, as the set's renderer does. A pixel's stored row has 4 blank pixels each side for
the plot's 4-pixel shift. Not found: the graphic keeps the default colours; the report lists them.
"""
import json, struct, sys
from pathlib import Path
from skoolkit.snapshot import Snapshot

BK, REC = 16384, 9
BANKS = (5, 2, 0)
MAGIC = b'PHE1'
PAGE = 8192
L2_FIRST_PAGE = 44          # bank 22 up: above Layer 2's banks 16-21
ZX = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
      (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]


class Set256:
    def __init__(self, path):
        self.d = Path(path).read_bytes()
        self.master = b''.join(self._bank(b) for b in BANKS)

    def _bank(self, b):
        o = b * BK * REC
        return self.d[o + 8:o + BK * REC:REC]

    def plane_value(self, off, bit):
        b = BANKS[off // BK]
        o = b * BK * REC + (off % BK) * REC
        return sum(((self.d[o + k] >> (7 - bit)) & 1) << k for k in range(8))


def rgb9(c):
    r, g, b = [min(7, (x * 7 + 127) // 255) for x in c]
    if r == 7 and g == 0 and (b >> 1) == 3:      # would be the transparent colour E3
        r = 6
    return r, g, b


def candidates(mem):
    """(address, rows, width, ink) of everything shaped like a graphic's header."""
    for p in range(0x6000, 0xFF00):
        rows, w, ink = mem[p], mem[p + 1] & 0x7F, mem[p + 2]
        if rows < 2 or rows & 1 or rows > 96 or not 1 <= w <= 16:
            continue
        yield p, rows // 2, w, ink


def build(z80, set256, pal_path, seen=()):
    mem = bytes(Snapshot.get(z80).memory)
    s = Set256(set256)
    pal = [tuple(int(x) for x in ln.split()) for ln in Path(pal_path).read_text().splitlines() if ln.strip()][:256]
    assert len(pal) == 256 and all(len(c) == 3 for c in pal)
    found = {}
    words = {mem[a] | mem[a + 1] << 8 for a in range(0x4000, 0xFFFF)}
    for p, h, w, ink in candidates(mem):
        if p not in words and p not in seen:      # the game reaches a graphic through a pointer to it
            continue
        n = h * w * 2
        block = mem[p + 3:p + 3 + n]
        if n < 16 or len(set(block)) < 4 or p + 3 + n > 65536:
            continue
        q = s.master.find(block, 6912)
        if q < 0:
            continue
        found[p] = (h, w, ink, q)
    pixels = {}
    colours = {}
    def idx(rgb):
        if rgb not in colours:
            colours[rgb] = len(colours)
        return colours[rgb]
    for p, (h, w, ink, q) in sorted(found.items()):
        rows = []
        attr_ink = ink & 7 if ink != 255 else 7
        for r in range(h):
            row = [255] * 4
            for c in range(w):
                g, m = mem[p + 3 + r * w + c], mem[p + 3 + (h + r) * w + c]
                for bit in range(8):
                    v = s.plane_value(q + r * w + c, bit)
                    if v >= 0xC0:
                        v = (v & 0xC7) | (attr_ink << 3)
                    if v:
                        row.append(('c', pal[v]))
                    elif g & (0x80 >> bit):
                        row.append(0)
                    elif m & (0x80 >> bit):
                        row.append(254)
                    else:
                        row.append(255)
            row += [255] * 4
            rows.append(row)
        pixels[p] = rows
        for row in rows:
            for x in row:
                if isinstance(x, tuple):
                    idx(x[1])
    # the used colours: 16 Spectrum colours first (the default ink path keeps its indexes), then the set's
    used = sorted(colours)
    merged = 0
    slots = list(ZX) + used[:238]
    if len(used) > 238:
        merged = len(used) - 238
    def nearest(rgb):
        return min(range(len(slots)), key=lambda i: sum((a - b) ** 2 for a, b in zip(slots[i], rgb)))
    index_of = {rgb: (16 + i if i < 238 else nearest(rgb)) for i, rgb in enumerate(used)}
    palette = bytearray()
    for i in range(256):
        rgb = slots[i] if i < len(slots) else (0, 0, 0)
        r, g, b = rgb9(rgb)
        palette += bytes((r << 5 | g << 2 | b >> 1, b & 1))
    # lay out: no figure crosses an 8K page
    pages, index = [bytearray()], []
    for p in sorted(pixels):
        h, w, ink, q = found[p]
        data = bytearray()
        for row in pixels[p]:
            data += bytes(index_of[x[1]] if isinstance(x, tuple) else x for x in row)
        if len(pages[-1]) + len(data) > PAGE:
            pages.append(bytearray())
        off = len(pages[-1])
        pages[-1] += data
        index.append(struct.pack('<HBHB', p, L2_FIRST_PAGE + len(pages) - 1, off, w))
    report = dict(graphics=len(index), bytes=sum(len(x) for x in pages), pages=len(pages), colours=len(used), merged=merged)
    miss = sorted(set(a for a in seen if a not in found))
    report['seen'] = len(set(seen))
    report['seen_not_in_set'] = ['%04X' % a for a in miss]
    blob = MAGIC + struct.pack('<HH', len(index), len(pages)) + bytes(palette) + b''.join(index) + b''.join(bytes(x).ljust(PAGE, b'\xff') for x in pages)
    return blob, report


def load(path):
    d = Path(path).read_bytes()
    if d[:4] != MAGIC:
        raise ValueError('%s is not a Phantis colour table' % path)
    n, np_ = struct.unpack('<HH', d[4:8])
    pal = d[8:520]
    index = d[520:520 + n * 6]
    pages = [d[520 + n * 6 + i * PAGE:520 + n * 6 + (i + 1) * PAGE] for i in range(np_)]
    return dict(n=n, palette=pal, index=index, pages=pages)


def seen_in(z80, rzxs, site=0xC6DF):
    from .rzx import trace
    out = set()

    def on(pc, sim):
        m = sim.memory
        hl = sim.registers[6] << 8 | sim.registers[7]
        out.add(m[hl] | m[hl + 1] << 8)
    for r in rzxs:
        trace(str(r), {site}, on)
    return out


def main():
    z, st, pal, out = sys.argv[1:5]
    seen = seen_in(z, sys.argv[5:]) if len(sys.argv) > 5 else ()
    blob, rep = build(z, st, pal, seen)
    Path(out).write_bytes(blob)
    print(json.dumps(rep))


if __name__ == '__main__':
    main()
