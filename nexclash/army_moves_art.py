"""Army Moves Enhanced: per-graphic colour tables and backdrops from the Spec256 sets (the player's own, never in the
repo), matched to the 128K release's graphics by content. One byte a pixel: 0 skip, 254 opaque black, 255 the plot's
ink, else a palette index. Layer 2's palette is the Spec256 palette at 9 bits; unused entries hold the 16 Spectrum colours."""
import json, os, collections
from pathlib import Path
from . import z80tonex as zt

C_PAGE, S_PAGE = 44, 48
# Backdrops: part 1's, part 2's jungle
BD_PAGE = {(1, 0): 52, (2, 0): 56}
FIRST_ASSET_PAGE = 60
LAST_PAGE = 91
SETS = {1: 'Army Moves (Part 1) (English).256', 2: 'Army Moves (Part 2) (English).256'}
MEM, BASE, BG = 131072 * 9, 131072 * 9 + 32, 256 * 192
PALETTE = Path(__file__).resolve().parents[1] / 'docs/profiles/army_moves_palette.json'
ZX_RGB = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
          (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]
# The ULA under the panel holes and on the menus: the Spec256 panel's greens, its digits made brighter.
ULA_RGB = [(0, 0, 0), (14, 96, 72), (205, 40, 30), (150, 40, 150), (30, 170, 60), (140, 205, 170), (170, 225, 110), (190, 255, 190),
           (0, 0, 0), (24, 130, 96), (255, 60, 40), (220, 60, 220), (60, 230, 90), (170, 255, 200), (200, 250, 130), (220, 255, 220)]


def rgb8(c):
    return ((c[0] >> 5) << 5) | ((c[1] >> 5) << 2) | (c[2] >> 6)


def nine(c):
    r, g, b = c[0] >> 5, c[1] >> 5, c[2] >> 5
    return ((r << 5) | (g << 2) | (b >> 1), b & 1)


class Set:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        d = self.d
        off = lambda a: (5, 2, 0)[(a >> 14) - 1] * 16384 * 9 + (a & 16383) * 9
        self.off = off
        self.master = bytes(d[off(a) + 8] for a in range(0x4000, 0x10000))

    def planes(self, a):
        o = self.off(a)
        return self.d[o:o + 9]

    def backdrop(self, i):
        if i == 0:
            return self.d[BASE:BASE + BG]
        at = BASE + BG + 8 + (i - 1) * BG
        return self.d[at:at + BG]


def bitv(pl, bit):
    return sum(((pl[p] >> (7 - bit)) & 1) << p for p in range(8))


def walk(view, known):
    """Records chained in memory from each known one: nothing is assumed about what a recording reached."""
    seen = {}
    for p, h, w in known:
        seen[p] = (h, w)
    todo = list(seen)
    while todo:
        p = todo.pop()
        h, w = seen[p]
        q = p + 2 + h * w
        if not 0xC000 <= q < 0xFFFE:
            continue
        hh, ww = view[q - 0x4000], view[q - 0x3FFF]
        if q in seen or not (1 <= hh <= 64 and 2 <= ww <= 62 and ww % 2 == 0):
            continue
        if q + 2 + hh * ww > 0x10000:
            continue
        seen[q] = (hh, ww)
        todo.append(q)
    return seen


def locate(s, data, a0, prev):
    """Where a graphic sits in the set: the address it has here, else the copy nearest the last one's offset; never the screen."""
    if s.master[a0 - 0x4000:a0 - 0x4000 + len(data)] == data:
        return a0
    locs = []
    i = s.master.find(data, 0x1B00)
    while i >= 0:
        locs.append(i + 0x4000)
        i = s.master.find(data, i + 1)
    if not locs:
        return None
    return min(locs, key=lambda l: abs((l - a0) - prev[0]))


def compile_assets(z80, setdir, records_path, backdrops=tuple(BD_PAGE)):
    """-> dict(pages, tables {part: bytes}, palette, ula, zxtab, report)."""
    snap = zt.Z80Snapshot(str(z80))
    banks = snap.banks
    p2code = bytearray(banks[2])
    p2code[0:0x21FE] = banks[6][0x6A0:0x6A0 + 0x21FE]
    records = json.load(open(records_path))
    views = {1: banks[5] + banks[2] + banks[0], 2: banks[5] + bytes(p2code) + banks[3]}
    pal = json.load(open(PALETTE))
    sets = {pt: Set(os.path.join(setdir, SETS[pt])) for pt in (1, 2)}
    report = {'parts': {}}
    built = {}
    used = collections.Counter()
    for pt in (1, 2):
        s, view = sets[pt], views[pt]
        plots, tiles = [], {}
        known = []
        for kind, p, h, w, c in records[str(pt)]:
            if kind == 'plot':
                known.append((p, h, w))
            elif p != 0xA62A:
                tiles[p] = max(tiles.get(p, 0), h * w)
        chain = walk(view, [k for k in known if k[0] >= 0xC000])
        allplots = dict(chain)
        for p, h, w in known:
            allplots[p] = (h, w)
        out = {}
        missing = []
        prev = [0]
        for p, (h, w) in sorted(allplots.items()):
            n = w // 2
            data = view[p + 2 - 0x4000:p + 2 - 0x4000 + h * w]
            a = locate(s, data, p + 2, prev)
            if a is None:
                missing.append(dict(kind='plot', p=hex(p), h=h, w=w, seen=p in [k[0] for k in known]))
                continue
            prev[0] = a - (p + 2)
            st = bytearray()
            for r in range(h):
                for c in range(n):
                    g = s.planes(a + r * w + c)
                    m = s.planes(a + r * w + n + c)
                    for b in range(8):
                        v = bitv(g, b)
                        if v == 0:
                            st.append(254 if not (m[8] >> (7 - b)) & 1 else 0)
                        elif v == 255:
                            st.append(255 if (g[8] >> (7 - b)) & 1 else 254)
                        else:
                            st.append(v)
                            used[v] += 1
            out[p] = dict(kind='plot', nb=n, h=h, stream=bytes(st))
        for p, size in sorted(tiles.items()):
            data = view[p - 0x4000:p - 0x4000 + size]
            a = locate(s, data, p, prev)
            if a is None:
                missing.append(dict(kind='tile', p=hex(p), bytes=size, seen=True))
                continue
            prev[0] = a - p
            st = bytearray()
            for k in range(size):
                g = s.planes(a + k)
                for b in range(8):
                    v = bitv(g, b)
                    st.append(0 if v == 0 else 255 if v == 255 and (g[8] >> (7 - b)) & 1 else 0 if v == 255 else v)
                    if 0 < v < 255:
                        used[v] += 1
            out[p] = dict(kind='tile', nb=0, h=0, stream=bytes(st))
        built[pt] = out
        report['parts'][pt] = dict(records=len(allplots) + len(tiles), matched=len(out), missing=missing)
    # backdrops
    bds = {}
    for pt, idx in backdrops:
        img = sets[pt].backdrop(idx)
        bds[pt, idx] = img
        for v, c in collections.Counter(img).items():
            if v:
                used[v] += c
    # the two labels Imagine's release words differently from the sets: FUEL's own two colours
    fuel = built[1].get(0xA88C)
    if fuel:
        cols = collections.Counter(fuel['stream']).most_common()
        bgcol = next(c for c, _ in cols if c not in (0, 254, 255))
        textcol = 21 if 21 in [c for c, _ in cols] else cols[1][0]
        for pt in (1, 2):
            view = views[pt]
            for p in (0xA9E0, 0xA936):
                size = max((h * w for kind, q, h, w, c in records[str(pt)] if kind == 'tile' and q == p), default=0)
                if not size or p in built[pt]:
                    continue
                st = bytearray()
                wid = next(w for kind, q, h, w, c in records[str(pt)] if kind == 'tile' and q == p)
                for k in range(size):
                    byte = view[p - 0x4000 + k]
                    blank = not any(view[p - 0x4000 + (k // wid) * wid + j] != 0xFF and view[p - 0x4000 + (k // wid) * wid + j] != 0 for j in range(wid))
                    for b in range(8):
                        st.append(bgcol if (byte & (128 >> b)) or blank else textcol)
                built[pt][p] = dict(kind='tile', nb=0, h=0, stream=bytes(st))
                report.setdefault('labels', []).append(dict(part=pt, p=hex(p), note='label not in the set: drawn in FUEL label colours'))
                for m in report['parts'][pt]['missing']:
                    if m['p'] == hex(p):
                        m['label_style'] = True
    # palette: identity, 254 and 255 transparent; free entries take the Spectrum colours
    free = [v for v in range(1, 254) if v not in used]
    report['used_colours'] = len(used)
    report['free_entries'] = len(free)
    zxtab = bytearray(256)
    entries = [nine(((pal[v] >> 16) & 255, (pal[v] >> 8) & 255, pal[v] & 255)) for v in range(256)]
    entries[0] = (0, 0)
    entries[254] = entries[255] = (0xE3, 1)
    for z, rgb in enumerate(ZX_RGB):
        if rgb == (0, 0, 0):
            zxtab[z] = 0
            continue
        v = free.pop(0)
        zxtab[z] = v
        entries[v] = nine(rgb)
    for v, e in enumerate(entries):
        if v < 254 and e[0] == 0xE3:         # never the transparent colour
            entries[v] = (0xE2, e[1])
    # remap streams: 254/255 are markers; mix colours (192 up, shown half way to the attribute) to a plain index
    def near(rgb, avoid=()):
        best, bv = 1e9, 1
        for v in used:
            if v >= 192 or v in avoid:
                continue
            c = pal[v]
            d = sum((((c >> sh) & 255) - rgb[i]) ** 2 for i, sh in enumerate((16, 8, 0)))
            if d < best:
                best, bv = d, v
        return bv
    remap = {}
    for v in list(used):
        if v >= 192:
            c = pal[v]
            remap[v] = near(tuple((((c >> sh) & 255) + 191) // 2 for sh in (16, 8, 0)))
    rtab = bytes(remap.get(v, v) for v in range(256))
    for pt in built:
        for p, r in built[pt].items():
            # 254 and 255 are markers in the stream and stay; only colours below them are remapped
            r['stream'] = bytes(x if x >= 254 else rtab[x] for x in r['stream'])
    bdr = bytes(remap.get(v, v) if v < 254 else near(((pal[v] >> 16) & 255, (pal[v] >> 8) & 255, pal[v] & 255)) for v in range(256))
    bds = {key: img.translate(bdr) for key, img in bds.items()}
    # pages
    pages = {}
    for key, img in bds.items():
        for k in range(4):
            pages[BD_PAGE[key] + k] = bytes(img[(k * 32 * 256):((k + 1) * 32 * 256)])
    page, off, cur = FIRST_ASSET_PAGE, 0, bytearray()
    tables = {}
    for pt in (1, 2):
        t = bytearray()
        for p, r in sorted(built[pt].items()):
            st = r['stream']
            if len(st) > 8192:
                raise ValueError('record %04X is over a page' % p)
            if off + len(st) > 8192:
                pages[page] = bytes(cur) + bytes(8192 - len(cur))
                page += 1
                off, cur = 0, bytearray()
            r['hole'] = bool(pt == 1 and p >= 0xD400 and r['kind'] == 'plot')
            t += p.to_bytes(2, 'little') + bytes((page,)) + off.to_bytes(2, 'little') + bytes((r['nb'] | (0x80 if r['hole'] else 0),))
            r['page'], r['off'] = page, off
            cur += st
            off += len(st)
        tables[pt] = bytes(t) + b'\0\0'
    if cur:
        pages[page] = bytes(cur) + bytes(8192 - len(cur))
    if page > LAST_PAGE:
        raise ValueError('assets reach page %d' % page)
    if max(len(t) for t in tables.values()) > 0x300:
        raise ValueError('table too long')
    report['top_page'] = page
    report['pages_bytes'] = len(pages) * 8192
    return dict(pages=pages, tables=tables, l2pal=bytes(x for e in entries for x in e), ula=bytes(rgb8(c) for c in ULA_RGB),
                zxtab=bytes(zxtab), report=report, built=built, top_page=page)
