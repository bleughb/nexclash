"""Game Over Enhanced: per-graphic colour tables, the font and the backdrops from the Spec256 sets (the player's own, never
in the repo), matched to the 128K release's graphics by content. One byte a pixel: 0 skip, 254 opaque black, 255 the plot's
ink, else a palette index. Layer 2's palette is the Spec256 palette at 9 bits; unused entries hold the 16 Spectrum colours."""
import json, os, collections
from pathlib import Path
from . import z80tonex as zt

C_PAGE = 44
BD_PAGE = {(1, 0): 52, (2, 0): 56}
FONT_PAGE = {1: 60, 2: 61}
FIRST_ASSET_PAGE = 62
LAST_PAGE = 91
SETS = {1: 'Game Over (Part 1) (English).256', 2: 'Game Over (Part 2) (English).256'}
FONT = {1: 0xAAEF, 2: 0xA977}
MEM, BASE, BG = 131072 * 9, 131072 * 9 + 32, 256 * 192
PALETTE = Path(__file__).resolve().parents[1] / 'docs/profiles/game_over_palette.json'
ZX_RGB = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
          (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]


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


def views_of(snap):
    banks = snap.banks
    code = {1: bytearray(banks[2]), 2: bytearray(banks[2])}
    for w, b in ((1, 4), (2, 6)):
        end = 0x10000 - 0x5C6
        code[w][0:0x4000 - 0x5C6] = banks[b][0x5C6:0x4000]
    return {1: banks[5] + bytes(banks[2]) + banks[0], 2: banks[5] + bytes(code[2]) + banks[3]}


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
    snap = zt.Z80Snapshot(str(z80))
    records = json.load(open(records_path))
    views = views_of(snap)
    pal = json.load(open(PALETTE))
    sets = {w: Set(os.path.join(setdir, SETS[w])) for w in (1, 2)}
    report = {'worlds': {}}
    built, fonts = {}, {}
    used = collections.Counter()
    for w in (1, 2):
        s, view = sets[w], views[w]
        known = [(p, h, wd) for k, p, h, wd, c in records[str(w)]]
        chain = walk(view, [k for k in known if k[0] >= 0xC000])
        allplots = dict(chain)
        for p, h, wd in known:
            allplots[p] = (h, wd)
        seen_rec = {k[0] for k in known}
        out, missing = {}, []
        prev = [0]
        for p, (h, wd) in sorted(allplots.items()):
            n = wd // 2
            data = view[p + 2 - 0x4000:p + 2 - 0x4000 + h * wd]
            a = locate(s, data, p + 2, prev)
            if a is None:
                missing.append(dict(kind='plot', p=hex(p), h=h, w=wd, seen=p in seen_rec))
                continue
            prev[0] = a - (p + 2)
            st = bytearray()
            for r in range(h):
                for c in range(n):
                    g = s.planes(a + r * wd + c)
                    m = s.planes(a + r * wd + n + c)
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
        built[w] = out
        # the font, 128 characters from code 0: one page of 8x8 streams
        base = FONT[w]
        st = bytearray()
        chars_ok, chars_missing = 0, []
        run = view[base + 32 * 8 - 0x4000:base + 96 * 8 - 0x4000]
        at = s.master.find(run)
        for ch in range(128):
            glyph = view[base + ch * 8 - 0x4000:base + ch * 8 + 8 - 0x4000]
            a = None
            if s.master[base + ch * 8 - 0x4000:base + ch * 8 + 8 - 0x4000] == glyph and any(glyph):
                a = base + ch * 8            # the sets keep the font where this release has it
            elif any(glyph):
                i = s.master.find(glyph)
                a = i + 0x4000 if i >= 0 else None
            if a is None:
                st += bytes((255 if glyph[r] & (128 >> b) else 0) for r in range(8) for b in range(8))
                if any(glyph) and 32 <= ch < 96:
                    chars_missing.append(ch)
                continue
            chars_ok += 1
            for r in range(8):
                g = s.planes(a + r)
                for b in range(8):
                    v = bitv(g, b)
                    if v == 255:
                        st.append(255 if (g[8] >> (7 - b)) & 1 else 0)
                    else:
                        st.append(v)
                        if v:
                            used[v] += 1
        fonts[w] = bytes(st)
        report['worlds'][w] = dict(plots=len(allplots), seen=len(seen_rec), matched=len(out), missing=missing,
                                   font_run_found=at >= 0, font_matched=chars_ok, font_missing=chars_missing)
    bds = {}
    for w, idx in backdrops:
        img = sets[w].backdrop(idx)
        bds[w, idx] = img
        for v, c in collections.Counter(img).items():
            if v:
                used[v] += c
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
        if v < 254 and e[0] == 0xE3:
            entries[v] = (0xE2, e[1])

    def near(rgb):
        best, bv = 1e9, 1
        for v in used:
            if v >= 192:
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
    for w in built:
        for p, r in built[w].items():
            r['stream'] = bytes(x if x >= 254 else rtab[x] for x in r['stream'])
        fonts[w] = bytes(x if x >= 254 else rtab[x] for x in fonts[w])
    bdr = bytes(remap.get(v, v) if v < 254 else near(((pal[v] >> 16) & 255, (pal[v] >> 8) & 255, pal[v] & 255)) for v in range(256))
    bds = {k: img.translate(bdr) for k, img in bds.items()}
    pages = {}
    for key, img in bds.items():
        for k in range(4):
            pages[BD_PAGE[key] + k] = bytes(img[(k * 32 * 256):((k + 1) * 32 * 256)])
    for w in (1, 2):
        pages[FONT_PAGE[w]] = fonts[w] + bytes(8192 - len(fonts[w]))
    page, off, cur = FIRST_ASSET_PAGE, 0, bytearray()
    tables = {}
    for w in (1, 2):
        t = bytearray()
        for p, r in sorted(built[w].items()):
            st = r['stream']
            if off + len(st) > 8192:
                pages[page] = bytes(cur) + bytes(8192 - len(cur))
                page += 1
                off, cur = 0, bytearray()
            t += p.to_bytes(2, 'little') + bytes((page,)) + off.to_bytes(2, 'little') + bytes((r['nb'],))
            r['page'], r['off'] = page, off
            cur += st
            off += len(st)
        tables[w] = bytes(t) + b'\0\0'
    if cur:
        pages[page] = bytes(cur) + bytes(8192 - len(cur))
    if page > LAST_PAGE:
        raise ValueError('assets reach page %d' % page)
    report['top_page'] = page
    report['table_bytes'] = {w: len(t) for w, t in tables.items()}
    report['pages_bytes'] = len(pages) * 8192
    return dict(pages=pages, tables=tables, l2pal=bytes(x for e in entries for x in e), zxtab=bytes(zxtab), report=report, built=built, fonts=fonts,
                top_page=page, pal=pal)
