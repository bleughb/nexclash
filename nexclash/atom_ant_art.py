"""Atom Ant Enhanced: colour images from the Spec256 set, the player's own file, never in this repo. The set's code and art are
this release's, byte for byte (tiles 5DC2 up, figures C277 up), so each graphic takes its colours from its own address.
One byte a pixel; 255 is transparent (the set's "use the attribute" value: the ULA shows), SKIP leaves what is under it."""
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK, WORDS = 16384, 131072
MEM = WORDS * 9
SKIP, CLEAR = 0xFE, 0xFF
TILE_PAGE, FIRST_ART_PAGE = 44, 52
TILES = 0x5DC2
TYPE0 = (0xF877, 0xF8AF, 11, 3, 24, 4)     # table of bases, table of shift offsets, figures, bytes wide, rows, images a figure
TYPE1 = (0xF88D, 0xF8B7, 11, 4, 24, 4)
TYPE2 = (0xF8A3, None, 6, 3, 16, 1)


class Set256:
    def __init__(self, path):
        self.d = open(path, 'rb').read()

    def word(self, addr):
        return (5 if addr < 0x8000 else 2 if addr < 0xC000 else 0) * BANK + (addr & 0x3FFF)

    def master(self, addr):
        return self.d[self.word(addr) * 9 + 8]

    def pixels(self, addr):
        w = self.word(addr) * 9
        p = self.d[w:w + 8]
        out = []
        for k in range(8):
            bit = 0x80 >> k
            v = 0
            for i in range(8):
                if p[i] & bit:
                    v |= 1 << i
            out.append(v)
        return out


def palette(rgb):
    """256 RGB ints -> 512 bytes for NR 0x44. Index 255 is the transparent colour; any other that would match it is nudged."""
    out = bytearray()
    moved = []
    for i, c in enumerate(rgb):
        r, g, b = c >> 16 & 255, c >> 8 & 255, c & 255
        hi = (r >> 5) << 5 | (g >> 5) << 2 | b >> 6
        lo = (b >> 5) & 1
        if i == CLEAR:
            hi, lo = 0xE3, 0
        elif hi == 0xE3:
            hi = 0xE2
            moved.append(i)
        out += bytes((hi, lo))
    return bytes(out), moved


def tile_image(s, t):
    out = bytearray()
    for r in range(16):
        a = TILES + t * 32 + r * 2
        out += bytes(s.pixels(a)) + bytes(s.pixels(a + 1))
    return bytes(out)


def figure_image(s, base, wide, rows, stats):
    out = bytearray()
    for r in range(rows):
        for c in range(wide):
            at = base + (r * wide + c) * 2
            mk, g = s.pixels(at), s.pixels(at + 1)
            mm, gm = s.master(at), s.master(at + 1)
            for k in range(8):
                bit = 0x80 >> k
                m, v = mk[k], g[k]
                if m == 255 and v == 0:
                    out.append(SKIP)
                    continue
                if m not in (0, 255):
                    stats['mask not 0 or 255'] += 1
                if m == 255:
                    stats['paint under an open mask'] += 1
                if v == SKIP:
                    stats['value FE used'] += 1
                    v = 0xFD
                out.append(v)
    return bytes(out)


def compile_art(setpath, game_memory, panels=None, rgb=None):
    """-> (pages {page: 8192 bytes}, index bytes, images [(type, number, shift, page, addr, wide px, rows)], stats)."""
    s = Set256(setpath)
    w = lambda a: game_memory[a] | game_memory[a + 1] << 8
    stats = collections.Counter()
    pages = {}
    # tiles: 32 to a page
    for t in range(256):
        page = TILE_PAGE + (t >> 5)
        pages.setdefault(page, bytearray(8192))[(t & 31) << 8:((t & 31) << 8) + 256] = tile_image(s, t)
    page, at = FIRST_ART_PAGE, 0
    index = bytearray()
    images = []
    for ty, (table, shifts, n, wide, rows, each) in enumerate((TYPE0, TYPE1, TYPE2)):
        for f in range(n):
            base = w(table + 2 * f)
            for sh in range(each):
                addr = base + (w(shifts + sh * 2) if shifts else 0)
                img = figure_image(s, addr, wide, rows, stats)
                if at + len(img) > 8192:
                    page, at = page + 1, 0
                pages.setdefault(page, bytearray(8192))[at:at + len(img)] = img
                index += bytes((page, at & 255, 0x40 + (at >> 8)))
                images.append((ty, f, sh, page, at, wide * 8, rows))
                at += len(img)
    return {p: bytes(b) for p, b in pages.items()}, bytes(index), images, stats


def panel_pages(shots, hole_cells=()):
    """shots: the set's panel at moments of play, each 256 x 32 values then 768 attributes -> rows 160-191 for Layer 2: 8192 bytes for
    rows 160-191, and the cells left to the ULA: the digits the game prints."""
    size = 256 * 32 + 768
    all_ = [shots[i:i + size] for i in range(0, len(shots), size)]
    modal = bytearray(256 * 32)
    for i in range(256 * 32):
        modal[i] = collections.Counter(s[i] for s in all_).most_common(1)[0][0]
    play = [s for s in all_ if sum(a == b for a, b in zip(s[:256 * 32], modal)) > 0.9 * 256 * 32]
    holes = set(hole_cells)
    changed = set()
    for s_ in play:
        for i in range(256 * 32):
            if s_[i] != modal[i]:
                changed.add((i // 256 // 8, (i % 256) // 8))
    if changed - holes:
        raise ValueError('panel cells change that are not digit cells: %s' % sorted(changed - holes))
    out = bytearray(modal)
    for r, c in holes:
        for y in range(8):
            for x in range(8):
                out[(r * 8 + y) * 256 + c * 8 + x] = CLEAR
    return bytes(out), sorted(holes), len(play), len(all_)
