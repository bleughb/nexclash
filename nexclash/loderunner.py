"""Lode Runner (Software Projects, 1984; 48K) - XOR engine: runner and guards off the ULA.

Facts (games/lode_runner.md):
  Tiles: 8x8 graphics table at 0x7800 (256 x 8 bytes): font, scenery, and the figure frames 16-30.
  0x8501 prints a tile (overwrite, LD (HL),A at 0x8537): A = graphic, B = column, C = row.
  Figure plotter 0x9712 (pure XOR, 8 lines x 2 bytes, writes 0x975B / 0x9761): A = graphic,
  B = x pixel, C = y pixel; it rewrites 0x974E (shift) and 0x975D (second byte on/off) itself.
  Callers (code): 0x96B6 (guard dies: erase), 0x970C (guard respawn: draw graphic 30), 0x9A47 /
  0x9A5C (move: erase old, draw new), 0x9E03 / 0x9E1B (runner). IX = the figure's record at every
  call: 0xA174 runner (15 bytes), 0xA183 + 17 n guards.
  Level start: the figures are PRINTED as tiles (graphic 30) - runner, then each guard -
  and the first XOR erase removes that print (CALLs 0x8E5F / 0x8E74).
  Cell XOR 0x983E (dig 240-246, refill 249-251, 33): scenery, stays on the ULA.
  Figure colour = cell attributes: 0x9EC5 paints the cells a figure covers (A = (0xA12F): 71 runner,
  67 guard; via 0x856E, write 0x858F); 0x8F91 restores the scenery colour.
  Fade 0x854F (AND with ROM bytes, 4 passes) then clear 0x8541: the only non-XOR writers over figures.

This module: facts, the colour-sheet capture (PLAYBOOK 3b), the preview. CLI:
    python -m nexclash.loderunner sheet RZX --z80 Z80 [-o lode_runner]
    python -m nexclash.loderunner preview Z80 RZX --at F,F,... [-o preview.png]
    python -m nexclash.loderunner colours PAINTED.png [--layout L]
"""
import collections
import os

GFX = 0x7800                               # 8x8 graphics table
PLOT = 0x9712                              # figure XOR plotter
PLOT_W1, PLOT_W2 = 0x975B, 0x9761          # its screen writes
TILE = 0x8501                              # tile print
TILE_RUNNER, TILE_GUARD = 0x8E62, 0x8E77   # return addresses of the level-start figure prints (CALLs at 0x8E5F / 0x8E74)
FIG_FRAMES = range(16, 31)                 # figure graphics
RUNNER_REC = 0xA174
GUARD_REC, GUARD_SIZE = 0xA183, 17
ATTR_SET = 0x856E                          # A = attribute, B = column, C = row (A = 255: read)
FIG_ATTR_RET = 0x9EDE                      # 0x9EC5's CALL: a figure painting its cell
FIG_ATTR = 0xA12F
CLEAR = 0x8541
FADE = 0x854F

# Next palette (RRRGGGBB), as dizzy1 / midres: 0 transparent, 1-7 blue..white, 8 black, 9-15 bright
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
RUNNER_COL, GUARD_COL = 15, 11             # bright white (attr 71), bright magenta (attr 67)
GROUPS = ('Runner', 'Guards')
STATIC_GROUP = 'From the code (not in the recording yet)'
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'lode_runner_colours.json')
NOTE = ('Lode Runner figure colours, read back from lode_runner_PAINTING_SPRITES.png (python -m '
        'nexclash.loderunner colours). Key = kind + graphics byte (R = runner, G = guard; address in the '
        'table at 0x7800), check = that byte, 8 nibbles = colours of its bits (0 = default).')


def kind_of_ix(ix):
    return 'R' if ix == RUNNER_REC else 'G'


def part(peek, kind, gfx, x, y, group=None):
    """One figure drawing -> coloursheet part: 8x8, every bit of the graphic's 8 bytes (paper code 0:
    paintable outlines)."""
    dflt = RUNNER_COL if kind == 'R' else GUARD_COL
    pixels, entries = [], {}
    for r in range(8):
        a = GFX + 8 * gfx + r
        g = peek(a)
        key = '%s%04X' % (kind, a)
        entries[key] = [g, 1]
        for bit in range(8):
            pixels.append((bit, r, key, bit, 1, dflt) if g >> (7 - bit) & 1 else (bit, r, key, bit, 0, 0))
    if not any(q[4] for q in pixels):
        return None
    return dict(id=(kind, gfx), size=8, w=8, h=8, x=x, y=y, mir=0,
                group=group or ('Runner' if kind == 'R' else 'Guards'), pixels=pixels, entries=entries)


class Capture:
    """simrun hooks: every figure drawing (XOR parity per (graphic, x, y): the screen's own model),
    one list of parts per RZX frame, and for the preview the 1-bit figure layer and the scenery
    attributes (all attribute writes but a figure painting its cells)."""

    def __init__(self):
        self.on = {}               # (gfx, x, y) -> kind: figures on the screen now
        self.frame_parts = []
        self.frames = []
        self.layer = bytearray(6144)               # figure pixels (XOR) - off the ULA in the build
        self.sattr = None                          # scenery attributes
        self.in_plot = None                        # (kind, sp) while 0x9712 / a figure print runs
        self.in_attr = None
        self.shots, self.want = {}, set()
        self.calls = collections.Counter()

    def on_sim(self, sim):
        self.sim = sim
        if self.sattr is None:
            self.sattr = bytearray(sim.memory[0x5800 + i] for i in range(768))

    def on_frame(self, n):
        self.frames.append(self.frame_parts)
        self.frame_parts = []
        if n in self.want:
            m = self.sim.memory
            self.shots[n] = (bytes(m[0x4000 + i] for i in range(6912)), bytes(self.layer), bytes(self.sattr),
                             dict(self.on))

    def _toggle(self, kind, gfx, x, y):
        k = (gfx, x, y)
        if k in self.on:
            del self.on[k]
        else:
            self.on[k] = kind
            p = part(lambda a: self.sim.memory[a], kind, gfx, x, y)
            if p:
                self.frame_parts.append(p)

    def before(self, pc):
        R, m = self.sim.registers, self.sim.memory
        sp = R[12]
        if self.in_plot and sp > self.in_plot[1]:
            self.in_plot = None
        if self.in_attr and sp > self.in_attr:
            self.in_attr = None
        if pc == PLOT:
            ret = m[sp] | m[sp + 1] << 8
            kind = kind_of_ix(R[8] << 8 | R[9])
            self.calls[(ret, kind)] += 1
            self._toggle(kind, R[0], R[2], R[3])
            self.in_plot = (kind, sp)
        elif pc == TILE:
            ret = m[sp] | m[sp + 1] << 8
            if ret in (TILE_RUNNER, TILE_GUARD):
                kind = 'R' if ret == TILE_RUNNER else 'G'
                self.calls[(ret, kind)] += 1
                self._toggle(kind, R[0], R[2] * 8, R[3] * 8)       # B = column, C = row
                self.in_plot = (kind, sp)
        elif pc == ATTR_SET:
            if (m[sp] | m[sp + 1] << 8) == FIG_ATTR_RET:
                self.in_attr = sp
        elif pc == CLEAR:
            self.on.clear()
            self.layer[:] = bytes(6144)

    def on_write(self, a, v, pc, mem):
        if 0x4000 <= a < 0x5800:
            if self.in_plot:
                self.layer[a - 0x4000] ^= mem[a] ^ v
            elif pc == 0x855D:                     # fade: screen AND (DE); the build's screen too
                R = self.sim.registers
                self.layer[a - 0x4000] &= mem[R[4] << 8 | R[5]]
        elif 0x5800 <= a < 0x5B00 and not self.in_attr:
            self.sattr[a - 0x5800] = v


def static_comps(peek, seen):
    """Figure frames the recording did not draw, per kind, as whole graphics."""
    out = {}
    for kind in ('R', 'G'):
        for f in FIG_FRAMES:
            if (kind, f) not in seen:
                p = part(peek, kind, f, 0, 0, STATIC_GROUP)
                if p:
                    out[('static', kind, f)] = dict(count=0, group=STATIC_GROUP,
                                                    parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)])
    return out


def capture(rzx, z80=None, stop=None, want=()):
    """-> (coloursheet composites, Capture)."""
    from . import simrun, coloursheet as cs
    cap = Capture()
    cap.want = set(want)
    simrun.run(z80, [rzx] if isinstance(rzx, str) else rzx, cap, stop=stop)
    col = cs.Collector(family=lambda p: None)
    for parts in cap.frames:
        col.add_frame(parts)
    if z80:
        mem = _mem(z80)
        for k, c in static_comps(mem.__getitem__, set(col.maxsize)).items():
            col.comps[k] = c
            col.maxsize[c['parts'][0]['id']] = 8
    return col.composites(list(GROUPS) + [STATIC_GROUP]), cap


def _mem(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536]))


def sheets(comps, prefix, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix, uniq in (('_PAINTING_SPRITES', True), ('_REFERENCE_ALL_SPRITES', False)):
        png = prefix + suffix + '.png'
        n = cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours, unique=uniq,
                     paint_clear=True)
        out.append((png, n))
    return out


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def scr_xy(a):
    o = a - 0x4000
    return (o & 31), ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0)


def preview(z80, rzx, at, out, colours=None):
    """Each shot: the original screen | the planned build (ULA without the figures and without their
    cell colours; figures as sprites on top in the default (or mapped) colours)."""
    from PIL import Image
    from . import simrun, coloursheet as cs
    rgb = cs.palette_rgb(PALETTE)
    cmap = colours or {}
    cap = Capture()
    cap.want = set(at)
    simrun.run(z80, [rzx], cap, stop=max(at) + 1)
    ink = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205)]
    br = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]
    peek = _mem(z80).__getitem__

    def ula(pix, att):
        im = Image.new('RGB', (256, 192))
        px = im.load()
        for a in range(6144):
            cx, y = scr_xy(0x4000 + a)
            at_ = att[(y >> 3) * 32 + cx]
            pal = br if at_ & 64 else ink
            for b in range(8):
                px[cx * 8 + b, y] = pal[at_ & 7] if pix[a] >> (7 - b) & 1 else pal[at_ >> 3 & 7]
        return im

    tiles = []
    for n in sorted(cap.shots):
        scr, layer, sattr, on = cap.shots[n]
        o = ula(scr[:6144], scr[6144:])
        p = ula(bytes(scr[i] ^ layer[i] for i in range(6144)), sattr)
        pp = p.load()
        for (gfx, x, y), kind in on.items():
            dflt = RUNNER_COL if kind == 'R' else GUARD_COL
            for r in range(8):
                a = GFX + 8 * gfx + r
                g = peek(a)
                e = cmap.get('%s%04X' % (kind, a))
                for bit in range(8):
                    c = (e[2][bit] if e else 0) or (dflt if g >> (7 - bit) & 1 else 0)
                    if c and 0 <= x + bit < 256 and 0 <= y + r < 192:
                        pp[x + bit, y + r] = rgb[c]
        t = Image.new('RGB', (520, 196), (40, 40, 40))
        t.paste(o, (2, 2))
        t.paste(p, (262, 2))
        tiles.append(t)
    sheet = Image.new('RGB', (2 * 520, ((len(tiles) + 1) // 2) * 196), (40, 40, 40))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * 520, (i // 2) * 196))
    sheet.save(out)
    return sorted(cap.shots), cap


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.loderunner')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx')
    p.add_argument('--z80')
    p.add_argument('-o', '--out', default='lode_runner')
    p = sub.add_parser('preview')
    p.add_argument('z80')
    p.add_argument('rzx')
    p.add_argument('--at', required=True)
    p.add_argument('-o', '--out', default='lode_runner_preview.png')
    p = sub.add_parser('colours', help='painted PAINTING sheet -> colours json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--out', default=COLOURS)
    a = ap.parse_args(argv)
    from . import coloursheet as cs
    if a.cmd == 'sheet':
        comps, cap = capture(a.rzx, a.z80)
        for png, n in sheets(comps, a.out, load_colours()):
            print('%s: %d figures' % (png, n))
        print('plot calls (return address, kind):', {('0x%04X' % r, k): v for (r, k), v in sorted(cap.calls.items())})
    elif a.cmd == 'preview':
        shots, cap = preview(a.z80, a.rzx, [int(x) for x in a.at.split(',')], a.out, load_colours())
        print('%s: shots %s' % (a.out, shots))
    elif a.cmd == 'colours':
        lay = a.layout or a.png.replace('_painted.png', '.png').replace('.png', '_layout.json')
        ent, rep = cs.read(a.png, lay, clear=True)
        cs.save(ent, a.out, NOTE)
        for k, v in rep.items():
            print('%-70s %d' % (k, v))
        print('->', a.out)


if __name__ == '__main__':
    main()
