"""Lode Runner (Software Projects, 1984) 128K release - rework v3: loderunner_v2 with R preserved and the Enhanced colours.

Jon Attree's rework (2026-11-08), a copy of loderunner_v2 (its record and builds stay as published). What changes:
  - every hook leaves R as the original (card patch.preserve-r): asm/loderunner_v3_hooks.asm, profile lode_runner_v3; verify compares
    R (hooklib.CMP_R). The figure paints are a CALL of a copy of 0x856E without its write, so R, flags and time are the original's;
  - modes: LodeRunnerPatch(mode=) 'default' (the published picture), 'enhanced' (scenery on a hardware tilemap in bank 7, painted sprites,
    their palette in the profile's "enhanced" block; hooks at 0x8501, 0x984A and the clear), 'backdrop' (enhanced + a Layer 2 picture
    behind the ULA, a display-only toggle: nothing in the hooks changes). Colours follow rules over the game's own graphics (profile
    "enhanced"), so no picture of the game is stored; the backdrop is read from a file the builder supplies, never in this repo.
    To change the runner's colour: profile "enhanced"/"sprite_palette"/"runner", then rebuild the set; nothing else;
  - verify keeps a model of the tilemap: at every frame each cell's entry is what the tile the ULA holds there asks for.

v2's notes follow.
Dean's notes on the engine follow.

Lode Runner (Software Projects, 1984; 48K) - XOR engine: runner and guards off the ULA.

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




# ---------------------------------------------------------------------------------------------
# Build: hooks in game RAM (0xA460, asm/loderunner_hooks.asm), 30 4-bit patterns in bank 11
# ---------------------------------------------------------------------------------------------
import json

HOOK_ORG = 0xA460
TAIL_ADDR, MAX_TAIL = 0xA400, 0x60             # tail 0xA400-0xA45F at most (79 bytes today)
FREE_RAM = (0xA33C, 0xAA00)                     # zero, never read or written (RZX + free runs)
RECORDS = [RUNNER_REC] + [GUARD_REC + GUARD_SIZE * k for k in range(7)]
NSLOT, NPAT = 8, 30
# CALL sites: original bytes, hook symbol, event kind
CALL_SITES = {0x9A5C: ('cd1297', 'e_draw', 'dr'), 0x970C: ('cd1297', 'e_draw', 'dr'),
              0x9E1B: ('cd1297', 'e_drawr', 'drr'), 0x96B6: ('cd1297', 'e_hide', 'hd'),
              0x8E5F: ('cd0185', 'e_trun', 'tr'), 0x8E74: ('cd0185', 'e_tgrd', 'tg')}
JP_SITES = {0x854F: ('060411', 'e_fade', 'fd', 0x8554), 0x8541: ('110140', 'e_cls', 'cl', 0x8544)}
PAINT_SITES = (0x9EDB, 0x978C, 0x8E64, 0x8E79, 0x966E)     # CALL 0x856E (figure colour) -> CP 255 / NOP
PAINT_ORIG = 'cd6e85'
SCREEN_PATCHES = [(0x975B, '77', '00'), (0x9761, '77', '00')]
ERASE_SITES = (0x9A47, 0x9E03)                  # plotter calls left as they are (writes removed)
# from the first byte of an event to where the figure is consistent again (frame checks wait)
PENDING = {0x9A47: 0x9A5F, 0x9E03: 0x9E1E, 0x96B6: 0x96B9, 0x970C: 0x970F, 0x8E5F: 0x8E62,
           0x8E74: 0x8E77}
INTERIORS = tuple(a + k for a in list(CALL_SITES) + list(PAINT_SITES) for k in (1, 2)) + \
    (0x8550, 0x8542, 0x8543)                    # 0x8551 (LD DE,0) is checked separately
PLOT_READS = (0x9759, 0x975F)                   # the plotter reads the screen (result overwritten)
CELL_XOR = (0x986B, 0x986D)
FADE_RD, FADE_WR = 0x855C, 0x855D
# The fade reads 0x0000-0x6BFF as AND masks (LD A,(DE) at 0x855B: screen and attributes too, passes 3-4)
# and ANDs every byte of 0x4000-0x5AFF (AND (HL) at 0x855C): the results go only to 0x4000-0x5AFF, and
# its only exit (0x8569 JP 0x8541) is the full clear of 0x4000-0x5AFF - nothing it reads reaches logic.
FADE_READS = (0x855B, 0x855C)
CLEAR_WR = (0x8547, 0x854C)
TILE_WR = 0x8537
ATTR_GET = 0x858B                               # LD A,(HL) in 0x856C / 0x856E with A = 255
ATTR_HARMLESS = {0x9668: 'guard: CP 71 selects a figure paint the build removes; A, F overwritten at '
                         '0x9671-0x9674'}
SPECCY = PALETTE
# Enhanced
TILE_SITE, TILE_END = 0x8501, 0x8504            # PUSH AF / BC / DE -> JP e_tile (the print's stack: 6 bytes on at 0x8504)
XOR_SITE, XOR_END = 0x984A, 0x984D              # the cell XOR's inner entry (0x983E comes here; the gold's XOR calls it direct): PUSH BC / DE / HL -> JP e_xor
EDIT_SITE, EDIT_END = 0x8C83, 0x8C86            # LD HL,0x8D9D (the editor's legend) -> JP e_edit
TILES = 0xA900                                  # 256 bytes: tile -> tilemap entry (0: stays on the ULA)
TEND_SITE, TEND_END = 0x853C, 0x853F            # POP HL / DE / BC -> JP e_tend (the end of the print: back to the incoming speed)
XEND_SITE, XEND_END = 0x9872, 0x9875            # POP HL / DE / BC at the end of the cell XOR -> JP e_xend
HOOK_RAM = (0xA3F0, 0xA3F9)                     # R saves
EDIT_SWAP = {0x8E60, 0x8E61, 0x8E75, 0x8E76, 0x8E65, 0x8E66, 0x8E7A, 0x8E7B}   # the CALL operands the editor gives back
EDIT_SITES = {0x8E5F, 0x8E74, 0x8E64, 0x8E79}
PAGE_TM, PAGE_S2 = 14, 10
MAP_COLS = 40
BD_BANKS = (13, 14, 15)                         # Layer 2, listed (zero) in every build so the toggle needs no added bank
BD_PAL = 0x1000                                 # bank 11: 512 bytes of Layer 2 palette
TILE_DEFS = 0x0500                              # bank 7: definitions, after the 1,280-byte map
MODES = ('default', 'enhanced', 'backdrop')
TILE_ORDER = (5, 33, 34, 35, 36, 37, 39, 31)    # tiles that get a definition, in entry order from 1 (HUD bar, bricks, ladder, bar, ..)


def rgb9(c):
    """(r, g, b) 0-255 -> the two bytes of NextReg 0x44 (RRRGGGBB, 0000000B), nearest 9-bit colour."""
    r, g, b = (round(v * 7 / 255) for v in c)
    return bytes([r << 5 | g << 2 | b >> 1, b & 1])


def enhanced_cmap(peek, prof):
    """The sprite colour map of the Enhanced set, from rules on the game's own graphics: head, body and legs by ink row; a dark
    edge on paper bits touching ink, inside the 8 x 8, which only shows on the backdrop."""
    idx = prof['enhanced']['sprite_index']
    out = {}
    for kind, fam in (('R', 'runner'), ('G', 'guard')):
        for gfx in FIG_FRAMES:
            rows = [peek(GFX + 8 * gfx + r) for r in range(8)]
            lit = [r for r in range(8) if rows[r]]
            top, bot = (min(lit), max(lit)) if lit else (0, 7)
            for r in range(8):
                nib = []
                for b in range(8):
                    if rows[r] >> (7 - b) & 1:
                        part = 'head' if r - top < 2 else 'legs' if bot - r < 3 else 'body'
                        nib.append(idx[fam + '_' + part])
                    else:
                        near = any(0 <= r + j < 8 and 0 <= b + k < 8 and rows[r + j] >> (7 - b - k) & 1
                                   for j in (-1, 0, 1) for k in (-1, 0, 1))
                        nib.append(idx['edge'] if near else 0)
                out['%s%04X' % (kind, GFX + 8 * gfx + r)] = (rows[r], 0, nib, 0)
    return out


def enhanced_tile(g, rule):
    """One 4-bit tile definition (32 bytes) from the graphic's 8 bytes and its rule: ink colour per row ('ink', one list of 8), paper
    colour per row ('paper'), and column overrides of the ink ('ink_col': {column: colour}); missing or 0: transparent, the ULA shows."""
    out = bytearray(32)
    ink, paper = rule.get('ink', [0] * 8), rule.get('paper', [0] * 8)
    cols = {int(k): v for k, v in rule.get('ink_col', {}).items()}
    for r in range(8):
        for b in range(8):
            c = (cols.get(b) or ink[r]) if g[r] >> (7 - b) & 1 else paper[r]
            out[r * 4 + b // 2] |= (c << 4) if b % 2 == 0 else c
    return bytes(out)


def tile_table(prof):
    """256 bytes: tile -> entry."""
    t = bytearray(256)
    for k, a in enumerate(TILE_ORDER):
        t[a] = k + 1
    return bytes(t)


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'lode_runner_v3.json')


def load_profile():
    return json.load(open(_profile_path()))


ROM_ORG = 0x386E          # alt ROM image 1: the start-up register block (keypad code of ROM 1, never run here)
ALT_PAGE = 24             # the alt image's 0x2000-0x3FFF page (bank 12), copied by the stub
ISR_STACK = 16            # the 128K music handler: bytes below the interrupted SP (`isr`, 3000-frame free run)


def rom128_1():
    """ROM 1 as the ROM path check (nextboot.rom_paths) takes a 128K recording's: SkoolKit's 128K ROM 1 (the ROM
    the release runs with: the 48K BASIC ROM + keypad code at 0x386E-0x3CFF) with its 6 call sites into the keypad
    code below 0x386E as Sinclair's 48K ROM has them (the Next's ROM 3 has no keypad). The game never runs ROM
    code; only the fade reads these bytes, as AND masks. SkoolKit's copies; never in this repo."""
    from skoolkit import ROM48, ROM128, read_bin_file
    from .nextboot import KEYPAD_CODE
    r1, r48 = read_bin_file(ROM128[1], 16384), read_bin_file(ROM48, 16384)
    return bytes(r48[a] if a < KEYPAD_CODE else r1[a] for a in range(16384))


def is_loderunner_v3(snap):
    """The 128K release with Dean's plotter (the 48K file goes to his `loderunner`)."""
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '128K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def map_entry(cmap, key, g):
    """The colour-map entry for key if its check byte is the graphics byte (else defaults)."""
    e = cmap.get(key)
    return e if e and e[0] == g else None


def pix_colour(g, bit, kind, e):
    """Palette index of pixel `bit` (0 = left) of graphics byte g: ink = map nibble or the kind's
    default (0 if painted transparent); paper = map nibble (an outline) or 0 (transparent)."""
    ink = g >> (7 - bit) & 1
    nib = e[2][bit] if e else 0
    if ink:
        clr = e[3] if e and len(e) > 3 else 0
        return 0 if clr & (0x80 >> bit) else (nib or (RUNNER_COL if kind == 'R' else GUARD_COL))
    return nib


def patterns(peek, cmap):
    """30 4-bit patterns (128 bytes): runner graphics 16-30, then guard 16-30; 8x8 at the top left."""
    out = bytearray()
    for kind in 'RG':
        for gfx in FIG_FRAMES:
            pat = bytearray(128)
            for r in range(8):
                a = GFX + 8 * gfx + r
                g = peek(a)
                e = map_entry(cmap, '%s%04X' % (kind, a), g)
                for bit in range(8):
                    c = pix_colour(g, bit, kind, e)
                    pat[r * 8 + bit // 2] |= (c << 4) if bit % 2 == 0 else c
            out += pat
    return bytes(out)


def colour_inputs_md5(peek):
    """MD5 + count of the graphics bytes the patterns come from (graphics 16-30)."""
    import hashlib
    b = bytes(peek(a) for a in range(GFX + 8 * 16, GFX + 8 * 31))
    return hashlib.md5(b).hexdigest(), len(b)


class LodeRunnerPatch:
    name = 'Lode Runner 128K runner + guards -> hardware sprites (hooks in RAM 0xA460; whole alt ROM image)'

    def __init__(self, prof=None, colours=None, mode='default', backdrop=None):
        if mode not in MODES:
            raise ValueError('mode ' + mode)
        self.mode, self.enhanced, self.backdrop = mode, mode != 'default', backdrop
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.code = bytes.fromhex(h['hooks'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        if self.syms['e_draw'] != HOOK_ORG or HOOK_ORG + len(self.code) != self.syms['hooks_end']:
            raise ValueError('profile hooks not assembled at 0x%04X' % HOOK_ORG)
        if HOOK_ORG + len(self.code) > FREE_RAM[1]:
            raise ValueError('hooks too long for the free RAM')
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr, self.max_tail = TAIL_ADDR, MAX_TAIL
        self.colours = {} if colours is None and self.enhanced else load_colours() if colours is None else colours
        self.table = tile_table(self.prof) if self.enhanced else None
        self.sites = []
        for a, (old, sym, _) in CALL_SITES.items():
            self.sites.append((a, bytes.fromhex(old), bytes([0xCD]) + self.syms[sym].to_bytes(2, 'little')))
        for a, (old, sym, _, _) in JP_SITES.items():
            if self.enhanced and a == 0x8541:
                sym = 'e_cls2'
            self.sites.append((a, bytes.fromhex(old), bytes([0xC3]) + self.syms[sym].to_bytes(2, 'little')))
        for a in PAINT_SITES:
            self.sites.append((a, bytes.fromhex(PAINT_ORIG), bytes([0xCD]) + self.syms['paint'].to_bytes(2, 'little')))
        self.sites.append((EDIT_SITE, bytes.fromhex('219d8d'), bytes([0xC3]) + self.syms['e_edit'].to_bytes(2, 'little')))
        if self.enhanced:
            self.sites.append((TILE_SITE, bytes.fromhex('f5c5d5'), bytes([0xC3]) + self.syms['e_tile'].to_bytes(2, 'little')))
            self.sites.append((TEND_SITE, bytes.fromhex('e1d1c1'), bytes([0xC3]) + self.syms['e_tend'].to_bytes(2, 'little')))
            self.sites.append((XEND_SITE, bytes.fromhex('e1d1c1'), bytes([0xC3]) + self.syms['e_xend'].to_bytes(2, 'little')))
            self.sites.append((XOR_SITE, bytes.fromhex('c5d5e5'), bytes([0xC3]) + self.syms['e_xor'].to_bytes(2, 'little')))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.pats = None
        self.num_patterns = NPAT
        rom = rom128_1()
        self.regblock = ROM_ORG
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)              # the whole image, from the build: ROM 1 + the register block
        self.page = bytes(rom[0x2000:0x4000])
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[0:0x2000]))
        self.dean_setup = self.stub_extra
        self.setup_call = 0xD000 + len(self.dean_setup)

    def psite(self):
        """{address: byte} of every RAM byte the patch changes (sites + hook code)."""
        d = {a + k: v for a, old, new in self.sites for k, v in enumerate(new)}
        d.update({HOOK_ORG + k: v for k, v in enumerate(self.code)})
        if self.table:
            d.update({TILES + k: v for k, v in enumerate(self.table)})
        return d

    def prepare(self, peek):
        for a, old, new in self.sites:
            cur = bytes(peek(a + k) for k in range(len(old)))
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s) - not the expected version '
                                 'of Lode Runner' % (a, cur.hex(), old.hex()))
        if any(peek(a) for a in range(TAIL_ADDR, HOOK_ORG + len(self.code))):
            raise ValueError('0x%04X-0x%04X is not zero in this snapshot (tail + hooks)'
                             % (TAIL_ADDR, HOOK_ORG + len(self.code) - 1))
        if self.enhanced and not self.colours:
            self.colours = enhanced_cmap(peek, self.prof)
        self.pats = patterns(peek, self.colours)
        b11 = bytearray(16384)
        b11[:len(self.pats)] = self.pats
        self.extra_banks = {11: bytes(b11), 12: self.page + self.altrom_low[1]}
        for b in BD_BANKS:
            self.extra_banks[b] = bytes(16384)
        if self.mode == 'backdrop':
            pix, pal = self.backdrop_data()
            for k, b in enumerate(BD_BANKS):
                self.extra_banks[b] = pix[k * 16384:(k + 1) * 16384]
            b11[BD_PAL:BD_PAL + 512] = pal
            self.extra_banks[11] = bytes(b11)

    def backdrop_data(self):
        """The Layer 2 picture and palette from the builder's file (320 x 200 bytes, the paper at 32, 4) and its 256-colour palette,
        dimmed so that figures and text read in front of it."""
        path, palpath = self.backdrop
        d = open(path, 'rb').read()
        if len(d) != 64000:
            raise ValueError('a backdrop is 64,000 bytes')
        pix = bytes(d[(4 + y) * 320 + 32 + x] for y in range(192) for x in range(256))
        rgb = [int(x) for x in open(palpath).read().split()]
        dim = self.prof['enhanced']['backdrop_dim']
        pal = bytearray()
        for i in range(256):
            c = rgb9(tuple(v * dim for v in rgb[3 * i:3 * i + 3]))
            if c[0] == 0xE3:
                c = bytes([0xE2, c[1]])                 # 0xE3 is the transparent colour
            pal += c
        return pix, bytes(pal)

    def stub_tables(self):
        """The set-up block with this mode's flags and palettes."""
        d = bytearray(self.dean_setup)
        base, sy = 0xD000, self.syms
        if self.enhanced:
            e = self.prof['enhanced']
            d[sy['FLAG_ENH'] - base] = 1
            spal = bytearray(32)
            for k, c in e['sprite_palette'].items():
                spal[2 * e['sprite_slot'][k]:2 * e['sprite_slot'][k] + 2] = rgb9(c)
            tpal = bytearray(32)
            for k, c in e['tile_palette'].items():
                tpal[2 * e['tile_index'][k]:2 * e['tile_index'][k] + 2] = rgb9(c)
            d[sy['SPAL'] - base:sy['SPAL'] - base + 32] = spal
            d[sy['TPAL'] - base:sy['TPAL'] - base + 32] = tpal
        if self.mode == 'backdrop':
            d[sy['FLAG_BD'] - base] = 1
        return bytes(d)

    def tiles_block(self, peek):
        """Bank 7's definitions: entry 0 empty, then TILE_ORDER, from the game's graphics and the profile's rules."""
        e = self.prof['enhanced']
        out = bytearray(32)
        for a in TILE_ORDER:
            g = bytes(peek(GFX + 8 * a + r) for r in range(8))
            out += enhanced_tile(g, {k: [e['tile_index'].get(x, 0) if isinstance(x, str) else x for x in v] if isinstance(v, list)
                                     else {c: e['tile_index'][n] for c, n in v.items()} for k, v in e['tiles'][str(a)].items()})
        return bytes(out)

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('the Lode Runner 128K rework expects the 128K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2])
        top = snap.banks[snap.port7ffd & 7]
        prn = bytes(snap.banks[5][0x1B00:0x1C00])
        copy = self.setup_call + 18
        s2 = self.syms['setup2']
        self.stub_extra = self.stub_tables() + bytes([0xCD, 0x00, 0xD0, 0x21, copy & 0xFF, copy >> 8, 0x11, 0x00, 0x5B,
                                                      0x01, 0x00, 0x01, 0xED, 0xB0, 0xCD, s2 & 0xFF, s2 >> 8, 0xC9]) + prn
        self.printer = prn
        self.prepare(lambda a: ram[a - 0x4000] if 0x4000 <= a < 0xC000 else top[a - 0xC000] if a >= 0xC000 else 0)
        for a, v in self.psite().items():
            if not 0x4000 <= a < 0xC000:
                raise ValueError('patch byte 0x%04X outside banks 5 / 2' % a)
            ram[a - 0x4000] = v
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        if self.enhanced:
            b7 = bytearray(snap.banks[7])
            if any(b7[:8192]):
                raise ValueError('bank 7 (first 8K) is not empty: needed for the tilemap')
            t = self.tiles_block(lambda a: ram[a - 0x4000])
            b7[TILE_DEFS:TILE_DEFS + len(t)] = t
            snap.banks[7] = bytes(b7)


# ---------------------------------------------------------------------------------------------
# Recolour (PLAYBOOK 3b): the patterns (bank 11) are the only colour-dependent bytes; the game
# never reads bank 11.
# ---------------------------------------------------------------------------------------------
# v3 has no recolour route: its Enhanced colours come from the profile's rules; the default build's patterns are Dean's defaults.


# ---------------------------------------------------------------------------------------------
# Differential test: original vs patched from the same state at every patch site, plus a model of
# the patched game's screen and attributes over the whole run
# ---------------------------------------------------------------------------------------------

def sprite_pixels(attr, pat):
    """Visible 4-bit sprite -> {(x, y): palette index} in ULA coordinates."""
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return {}
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    n = (a3 & 0x3F) * 2 + (1 if a4 & 0x40 else 0)
    out = {}
    for j in range(16):
        for k in range(16):
            i = n * 128 + j * 8 + k // 2
            b = pat[i] if i < len(pat) else 0
            c = (b >> 4) if k % 2 == 0 else (b & 15)
            if c:
                out[(x + k, y + j)] = c
    return out


class NextState:
    def __init__(self, pats):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytes(pats)
        self.events = []
        self.tm = bytearray(8192)                       # bank 7's first 8K (map, definitions)
        self.nr[0x52] = PAGE_S2

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def slot_pixels(self, s):
        return {p: c for p, c in sprite_pixels(self.attr[s], self.pat).items() if 0 <= p[0] < 256 and 0 <= p[1] < 192}

    def figure_ink(self, peek):
        """XOR of the visible slots' graphics ink (what the original's screen holds over the scenery)."""
        out = set()
        for s in range(NSLOT):
            a0, a1, a2, a3, a4 = self.attr[s]
            if not a3 & 0x80:
                continue
            n = (a3 & 0x3F) * 2 + (1 if a4 & 0x40 else 0)
            gfx = 16 + n % 15
            x, y = a0 + (a2 & 1) * 256 - 32, a1 - 32
            for r in range(8):
                g = peek(GFX + 8 * gfx + r)
                for b in range(8):
                    if g >> (7 - b) & 1:
                        out ^= {(x + b, y + r)}
        return out


def _machine(Sim, mem, regs, ns, slot='o'):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot)
    z80n.install(sim, ns.nextreg, strict=False)

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return ns.nr.get(7, 0) & 3 if port == 0x253B else 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.events.append(('out', port, value))
    sim.set_tracer(Tr())
    return sim


STACK_FLOOR = 0xAB01 + ISR_STACK   # IM 2 table 0xAA00-0xAB00: the music handler's 16 bytes below SP stay above it
LOW_SP = [0x10000]


def _run(sim, stop, limit=400000, track=False):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        if track and R[12] < LOW_SP[0]:
            LOW_SP[0] = R[12]
        n += 1
        if n > limit:
            return False
    return True


from .hooklib import CMP_R as CMP                # every register, R included (not T, MEMPTR)


def _overlays(get, psite, canvas=None, ns=None):
    class O:
        def __init__(s):
            s.ov = {}
            s.romw = 0

        def __getitem__(s, a):
            v = s.ov.get(a)
            if v is not None:
                return v
            if canvas is not None and canvas[0] <= a < canvas[1]:
                return 0
            return get(a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw += 1
            else:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if ns is not None and 0x4000 <= a < 0x6000 and ns.nr.get(0x52, PAGE_S2) == PAGE_TM:
                return ns.tm[a - 0x4000]
            v = s.ov.get(a)
            if v is not None:
                return v
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if ns is not None and 0x4000 <= a < 0x6000 and ns.nr.get(0x52, PAGE_S2) == PAGE_TM:
                ns.tm[a - 0x4000] = v
            else:
                O.__setitem__(s, a, v)
    return O, P


def _screen_set(ov):
    out = set()
    for a, v in ov.items():
        if 0x4000 <= a < 0x5800:
            cx, y = scr_xy(a)
            for k in range(8):
                if (v >> (7 - k)) & 1:
                    out.add((cx * 8 + k, y))
    return out


def slot_of(ix):
    try:
        return RECORDS.index(ix)
    except ValueError:
        return None


def site_kind(pc):
    if pc == TILE_SITE:
        return 'tl'
    if pc == XOR_SITE:
        return 'xr'
    if pc == EDIT_SITE:
        return 'ed'
    if pc == TEND_SITE or pc == XEND_SITE:
        return 'te'
    if pc in CALL_SITES:
        return CALL_SITES[pc][2]
    if pc in JP_SITES:
        return JP_SITES[pc][2]
    if pc in PAINT_SITES:
        return 'pt'
    if pc in ERASE_SITES:
        return 'er'
    return None


def expected_slot(get, kind, gfx, x, y, cmap):
    """{(x, y): colour} the hooks must show for figure `kind` ('R'/'G') graphic gfx at x, y, and the
    set of its ink pixels."""
    exp, ink = {}, set()
    if gfx not in FIG_FRAMES:
        return exp, ink
    for r in range(8):
        a = GFX + 8 * gfx + r
        g = get(a)
        e = map_entry(cmap, '%s%04X' % (kind, a), g)
        for b in range(8):
            c = pix_colour(g, b, kind, e)
            if c and 0 <= x + b < 256 and 0 <= y + r < 192:
                exp[(x + b, y + r)] = c
            if g >> (7 - b) & 1:
                ink.add((x + b, y + r))
    return exp, ink


def event(patch, get, R, ns, Sim, cmap):
    """One patch site reached, original and patched from the same state. -> (failures, pixels)."""
    site = R[24]
    kind = site_kind(site)
    psite = patch.psite()
    sp0 = R[12]
    end = {'tl': TILE_END, 'xr': XOR_END, 'ed': EDIT_END, 'te': TEND_END if site == TEND_SITE else XEND_END}.get(kind) or (JP_SITES[site][3] if kind in ('fd', 'cl') else site + 3)
    spend = sp0 - 6 if kind in ('tl', 'xr') else sp0 + 6 if kind == 'te' else sp0

    def stop(r):
        return r[24] == end and r[12] == spend
    O, _ = _overlays(get, psite)
    _, P = _overlays(get, psite, ns=ns)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    before = [list(a) for a in ns.attr]
    ns.events = []
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    low0 = LOW_SP[0]
    LOW_SP[0] = 0x10000
    if not (_run(so, stop) and _run(sp_, stop, track=True)):
        return ['did not return'], 0
    f = []
    if LOW_SP[0] < STACK_FLOOR:
        f.append(('hook stack too deep (IM 2 table below)', hex(LOW_SP[0])))
    LOW_SP[0] = min(low0, LOW_SP[0])
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if p.romw:
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') and e[1] not in (0x243B, 0x253B) for e in ns.events):
        f.append(('port access in hook',))
    if any(e[1] not in (0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x52, 0x6B, 0x07) for e in ns.events if e[0] == 'nr'):
        f.append(('NEXTREG other than sprite attributes and the map window',))
    if ns.nr.get(0x52, PAGE_S2) != PAGE_S2:
        f.append(('map window left open',))
    if kind == 'te' and ns.nr.get(7, 0) != ns.nr.get('clock', 0):
        f.append(('the print left the speed raised',))
    if kind == 'ed' and any(p[a] != get(a) for a in EDIT_SWAP):
        f.append(('the editor did not get the original prints and paints',))
    if kind in ('tl', 'xr'):
        ns.nr[7] = 0                                    # the replay's game runs on at its own speed; e_tend's latch is the hook's
    if kind in ('tl', 'xr') and any(o[a] != p[a] for a in range(spend, sp0)):
        f.append(('the print\'s stack differs',))
    dead = range(sp0 - 64, sp0)
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not 0x4000 <= a < 0x5B00 and a not in dead and not HOOK_RAM[0] <= a < HOOK_RAM[1] and a not in EDIT_SWAP and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    pscr = {a: v for a, v in p.ov.items() if 0x4000 <= a < 0x5800}
    patt = {a: v for a, v in p.ov.items() if 0x5800 <= a < 0x5B00}
    if patt:
        f.append(('patched code wrote attributes', len(patt)))
    changed = [i for i in range(128) if ns.attr[i] != before[i]]
    if kind in ('tr', 'tg'):
        oscr = {a: v for a, v in o.ov.items() if 0x4000 <= a < 0x5800}
        if set(pscr) != set(oscr) or any(pscr.values()):
            f.append(('level-start print: the build did not print the blank tile over the figure cell',))
    elif pscr:
        f.append(('patched code wrote the screen', len(pscr)))
    if kind in ('er', 'pt', 'tl', 'xr', 'ed', 'te'):
        if changed:
            f.append(('sprites changed', changed[:4]))
        return f, 0
    if kind in ('fd', 'cl'):
        if any(ns.attr[i][3] & 0x80 for i in range(NSLOT)):
            f.append(('sprite visible after fade / clear',))
        if set(changed) - set(range(NSLOT)):
            f.append(('other sprites changed',))
        return f, 0
    if kind == 'drr':
        slot, fk = 0, 'R'
    elif kind == 'tr':
        slot, fk = 0, 'R'
    elif kind == 'tg':
        hl = R[6] << 8 | R[7]
        k2 = hl - 0x919D
        slot = k2 // 2 if hl >> 8 == 0x91 and 0 < k2 < 2 * NSLOT and not k2 & 1 else None
        fk = 'G'
    else:
        slot = slot_of(R[8] << 8 | R[9])
        fk = 'R' if slot == 0 else 'G'
    if slot is None:                        # guard: no figure record -> no sprite changes
        if changed:
            f.append(('sprites changed for a non-figure', changed[:4]))
        return f + [('no figure slot',)], 0
    if set(changed) - {slot}:
        f.append(('other sprites changed', sorted(set(changed) - {slot})[:4]))
    if kind == 'hd':
        if ns.attr[slot][3] & 0x80:
            f.append(('sprite still visible after the guard died', slot))
        return f, 0
    # the original's figure drawn on a zero screen, against the slot's sprite
    Oc, _ = _overlays(get, psite, (0x4000, 0x5800))
    oc = Oc()
    sc = _machine(Sim, oc, list(R), NextState(b''), 'c')
    if not _run(sc, stop):
        return f + ['canvas run did not return'], 0
    drawn = _screen_set(oc.ov)
    if kind in ('tr', 'tg'):
        gfx, x, y = R[0], R[2] * 8, R[3] * 8
    else:
        gfx, x, y = R[0], R[2], R[3]
    exp, ink = expected_slot(get, fk, gfx, x, y, cmap)
    got = ns.slot_pixels(slot)
    if ink != drawn:
        f.append(('original plot is not graphic %d at %d,%d' % (gfx, x, y), len(ink ^ drawn)))
    if got != exp:
        f.append(('sprite pixels / colours differ from the original plot', len(set(got) ^ set(exp)) or
                  sum(1 for q in got if got[q] != exp.get(q))))
    return f, len(drawn)


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


class _raw_view:
    """Reads of simrun's watched 128K Memory without calling the hooks (the 48K path has the list `.m`)."""
    def __init__(self, mem):
        self.mem = mem
        self.get = type(mem).__mro__[1].__getitem__ if not hasattr(mem, 'm') else None
        if self.get is None:
            self.m = mem.m

    def __getitem__(self, a):
        return self.get(self.mem, a) if self.get is not None else self.m[a]


def verify(patch, z80, rzx=None, frames=6000, keys=None, stop=None, collect=0, progress=None):
    """Run the original game (RZX, or a free run); at every patch site run original and patched code
    from the same state and compare; keep the patched game's screen / attributes as a model and check
    every frame that ULA difference == the visible sprites' graphics, and that every read of the
    screen or the attributes by game code sees the same value. -> (Counter, examples, states)."""
    from . import simrun
    c = collections.Counter()
    ex = collections.defaultdict(list)
    site_bytes = set(patch.psite())
    site_bytes -= set(range(TILES, TILES + 256)) if patch.table else set()
    cmap = patch.colours
    ns = NextState(patch.pats)
    st = {'ready': False, 'frame': 0, 'pending': {}, 'want': False, 'fading': False, 'paint': None, 'tprint': None}
    states = []
    cnt = collections.Counter()
    WATCH = set(CALL_SITES) | set(JP_SITES) | set(PAINT_SITES) | set(ERASE_SITES)
    WATCH.add(EDIT_SITE)
    if patch.enhanced:
        WATCH |= {TILE_SITE, XOR_SITE, TEND_SITE, XEND_SITE}
    INT = set(INTERIORS) | {0x8551}
    INT |= {EDIT_SITE + 1, EDIT_SITE + 2}
    if patch.enhanced:
        INT |= {TILE_SITE + 1, TILE_SITE + 2, XOR_SITE + 1, XOR_SITE + 2, TEND_SITE + 1, TEND_SITE + 2, XEND_SITE + 1, XEND_SITE + 2}
    m0 = {}
    bytile = {}
    if patch.enhanced:
        st['raw0'] = None

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    def frame_check():
        if st['fading']:
            c['frame checks skipped (fade)'] += 1
            return
        diff = set()
        o, p = m0['oscr'], m0['pscr']
        for i in range(6144):
            d = o[i] ^ p[i]
            if d:
                cx, y = scr_xy(0x4000 + i)
                for b in range(8):
                    if d >> (7 - b) & 1:
                        diff.add((cx * 8 + b, y))
        want = ns.figure_ink(st['raw'].__getitem__)
        want = {q for q in want if 0 <= q[0] < 256 and 0 <= q[1] < 192}
        c['frame checks'] += 1
        if diff != want:
            fail('screen: ULA difference is not the visible sprites', (len(diff ^ want),))
        if patch.enhanced and not st.get('edit'):
            map_check()

    def map_check():
        # the scenery model: each cell's entry is the one the tile on the ULA asks for; an uncoloured cell, or a cell the table
        # does not hold (no such state is expected), has entry 0 and the ULA shows
        raw = st['raw']
        if st.get('inprint'):                           # inside a print or a cell XOR (or an interrupt there): the entry is set first
            c['map checks skipped (inside a print)'] += 1
            return
        if not bytile:
            for t in range(255, -1, -1):
                bytile[bytes(raw[GFX + 8 * t + r] for r in range(8))] = t
            for t in TILE_ORDER:
                bytile[bytes(raw[GFX + 8 * t + r] for r in range(8))] = t
        P = m0['pscr']
        for cy in range(24):
            base = (cy & 0x18) << 8 | (cy & 7) << 5
            row = (cy + 4) * MAP_COLS + 4
            for cx in range(32):
                b = bytes(P[base + r * 256 + cx] for r in range(8))
                t = bytile.get(b)
                want = patch.table[t] if t is not None else 0
                got = ns.tm[row + cx]
                if got != want:
                    fail('tile layer out of step with the ULA', (cx, cy, t, want, got, b.hex()))
                    c['map cells wrong'] += 1
                c['map cells checked'] += 1

    class H:
        def on_sim(self, sim):
            st['sim'] = sim
            st['ready'] = False
            m = st['raw'] = _raw_view(sim.memory)                 # 128K: the paged view without the watcher
            m0['oscr'] = bytearray(m[0x4000 + i] for i in range(6144))
            m0['pscr'] = bytearray(m0['oscr'])
            m0['oattr'] = bytearray(m[0x5800 + i] for i in range(768))
            m0['pattr'] = bytearray(m0['oattr'])
            st['ready'] = True

        def on_read(self, addr, pc, mem):
            if st['ready'] and addr != pc and 0x4000 <= addr < 0x6000 and (0x73CA <= pc < 0x7560 or 0x6060 <= pc < 0x6066):
                fail('music handler read the map window (slot 2)', (hex(pc), hex(addr)))
            if not st['ready'] or addr == pc or not 0x4000 <= addr < 0x5B00:
                return
            if pc in FADE_READS:
                c['fade reads (masks / targets; always followed by the clear)'] += 1
                return
            if addr < 0x5800:
                if pc in PLOT_READS or pc in CELL_XOR:
                    return
                if m0['pscr'][addr - 0x4000] != st['raw'][addr]:
                    fail('screen read sees a figure', (hex(pc), hex(addr)))
                c['screen reads (other)'] += 1
            else:
                raw = st['raw']
                if m0['pattr'][addr - 0x5800] == raw[addr]:
                    return
                R = st['sim'].registers
                sp = R[12]
                ret = raw[sp + 4] | raw[sp + 5] << 8 if pc == ATTR_GET else None
                if ret in ATTR_HARMLESS:
                    c['attribute reads that differ, harmless (0x%04X)' % ret] += 1
                else:
                    fail('attribute read differs', (hex(pc), hex(addr), hex(ret or 0)))

        def on_write(self, addr, value, pc, mem):
            if not st['ready']:
                return
            if 0x4000 <= addr < 0x6000 and (0x73CA <= pc < 0x7560 or 0x6060 <= pc < 0x6066):
                fail('music handler wrote the map window (slot 2)', (hex(pc), hex(addr)))
            if addr in site_bytes:
                fail('game wrote a patch site / hook byte', (hex(addr), hex(pc)))
            if not 0x4000 <= addr < 0x5B00:
                return
            if addr >= 0x5800:
                i = addr - 0x5800
                m0['oattr'][i] = value
                if st['paint'] is None:
                    m0['pattr'][i] = value
                return
            i = addr - 0x4000
            raw = st['raw']
            old = raw[addr]
            m0['oscr'][i] = value
            P = m0['pscr']
            if pc in (0x975B, 0x9761):
                return                                  # removed
            if pc == 0x986D:
                P[i] ^= old ^ value
            elif pc == FADE_WR:
                R = st['sim'].registers
                P[i] &= raw[R[4] << 8 | R[5]]
            elif pc == TILE_WR and st['tprint'] is not None:
                P[i] = 0                                # tile 32 (blank) instead of the figure
            else:
                if P[i] != old and pc not in CLEAR_WR:
                    fail('unclassified writer over a figure byte', (hex(pc), hex(addr)))
                P[i] = value

        def before(self, pc):
            sim = st['sim']
            R = sim.registers
            if pc == TILE_SITE or pc == XOR_SITE:
                st['inprint'] = True
            elif pc == 0x8540 or pc == 0x9875:
                st['inprint'] = False
            pend = st['pending']
            if pc in pend and R[12] == pend[pc]:
                del pend[pc]
                if pc in (0x8E62, 0x8E77):
                    st['tprint'] = None
            if st['paint'] is not None and pc == st['paint'][0] and R[12] == st['paint'][1]:
                st['paint'] = None
            if st['want'] and not pend:
                st['want'] = False
                frame_check()
            if pc in INT:
                cnt[pc] += 1
            if pc not in WATCH:
                return
            if st.get('edit') and pc in EDIT_SITES:     # the editor: these are the original's until the next clear
                c['editor: original prints and paints'] += 1
                return
            if pc == 0x854F:
                cnt['fade'] += 1
            get = st['raw'].__getitem__
            kind = site_kind(pc)
            if collect and c['collected ' + kind] < collect:
                c['collected ' + kind] += 1
                states.append((kind, list(R), bytes(get(a) for a in range(65536)),
                               [list(x) for x in ns.attr]))
            fl, npx = event(patch, get, R, ns, _rw(), cmap)
            c[kind] += 1
            c['sprite pixels compared'] += npx
            for k in fl:
                k = k if isinstance(k, tuple) else (k,)
                fail('%s at 0x%04X: %s' % (kind, pc, k[0]), k[1:])
            if pc in PENDING:
                pend[PENDING[pc]] = R[12]
                if pc in (0x8E5F, 0x8E74):
                    st['tprint'] = pc
            if pc in PAINT_SITES:
                st['paint'] = (pc + 3, R[12])
            if kind == 'fd':
                st['fading'] = True
            elif kind == 'cl':
                st['fading'] = False
                st['edit'] = False
            elif kind == 'ed':
                st['edit'] = True

        def on_frame(self, n):
            st['frame'] = n
            st['want'] = True
            if progress and n % 1000 == 0:
                progress(n, c)

    LOW_SP[0] = 0x10000
    c['frames'] = simrun.run(z80, [rzx] if rzx else None, H(), frames=frames, keys=keys, stop=stop)
    c['lowest SP in the patched code'] = LOW_SP[0]
    if cnt[0x8551] != cnt['fade']:
        c['0x8551 reached other than from 0x854F!'] += 1
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (0x%04X)!' % a] += 1
    return c, dict(ex), states


# ---------------------------------------------------------------------------------------------
# Unit tests: paths the recording does not reach, guard edges, colour map, negative controls
# ---------------------------------------------------------------------------------------------
POS_X = (0, 1, 7, 8, 100, 241, 247, 248)
POS_Y = (0, 7, 8, 100, 167, 175)
CELLS = ((0, 0), (31, 21), (17, 20), (5, 1))


def _ev(patch, R, mem, attrs, cmap=None):
    ns = NextState(patch.pats)
    ns.attr = [list(a) for a in attrs]
    fl, npx = event(patch, mem.__getitem__, R, ns, _rw(), patch.colours if cmap is None else cmap)
    return fl, npx, ns


def _names(fl):
    return [k[0] if isinstance(k, tuple) else k for k in fl]


def _all_visible(attrs):
    at = [list(a) for a in attrs]
    for s in range(NSLOT):
        at[s] = [40 + s, 50, 0, 0xC0 | s, 0x80]
    return at


def synthetic_map(peek, seed=5):
    """A colour map over every figure graphics byte of both kinds: random ink / paper nibbles, some
    pixels transparent, and one key with a wrong check byte (must be ignored). -> (map, expect(kind,
    a, bit) -> colour, computed independently of pix_colour)."""
    import random
    rnd = random.Random(seed)
    cm, spec = {}, {}
    keys = [(k, a) for k in 'RG' for a in range(GFX + 8 * 16, GFX + 8 * 31)]
    bad = keys[37]
    for kind, a in keys:
        g = peek(a)
        nib = [rnd.choice((0, 0, 3, 9, 14)) for _ in range(8)]
        clr = rnd.choice((0, 0, 0, 0x81, 0x18))
        chk = (g ^ 1) if (kind, a) == bad else g
        cm['%s%04X' % (kind, a)] = [chk, 1, nib] + ([clr] if clr else [])
        spec[(kind, a)] = (nib, clr, (kind, a) == bad)

    def expect(kind, a, bit):
        g = peek(a)
        nib, clr, isbad = spec[(kind, a)]
        dflt = RUNNER_COL if kind == 'R' else GUARD_COL
        ink = g & (0x80 >> bit)
        if isbad:
            return dflt if ink else 0
        if ink:
            return 0 if clr & (0x80 >> bit) else (nib[bit] or dflt)
        return nib[bit]
    return cm, expect


def unit_tests(patch, states, negs=()):
    c = collections.Counter()
    first = {}
    for kind, R, mem, attrs in states:
        first.setdefault(kind, (R, mem, attrs))
    if 'dr' not in first:
        c['no captured draw state FAIL!'] += 1
        return c
    R0, mem0, at0 = first['dr']
    mem = bytearray(mem0)
    peek = mem.__getitem__

    def rec(name, ok, info=''):
        c['%s %s' % (name, 'ok' if ok else 'FAIL!')] += 1
        if not ok and c['  fail example'] < 8:
            c['  fail example'] += 1
            c['  %s %s' % (name, str(info)[:160])] += 1

    def draw(site, ix, gfx, x, y, p=patch, cmap=None):
        R = list(R0)
        R[24], R[0], R[2], R[3], R[8], R[9] = site, gfx, x, y, ix >> 8, ix & 255
        return _ev(p, R, mem, at0, cmap)
    # every figure graphic x every slot x positions, at the move draw; the respawn draw for guards
    for ix in RECORDS:
        for gfx in FIG_FRAMES:
            for x in POS_X:
                for y in POS_Y:
                    fl, npx, _ = draw(0x9A5C, ix, gfx, x, y)
                    rec('draw cases (0x9A5C, 8 slots x 15 graphics x 48 positions)', not fl and npx, (ix, gfx, x, y, fl))
    for ix in RECORDS[1:]:
        for gfx in FIG_FRAMES:
            fl, npx, _ = draw(0x970C, ix, gfx, 104, 64)
            rec('respawn draw cases (0x970C)', not fl and npx, (ix, gfx, fl))
    for gfx in FIG_FRAMES:
        for x, y in ((0, 0), (248, 175), (99, 33)):
            fl, npx, _ = draw(0x9E1B, RECORDS[3], gfx, x, y)     # IX ignored: runner slot
            rec('runner draw cases (0x9E1B)', not fl and npx, (gfx, x, y, fl))
    # guard dies: slot hidden, the others kept
    for ix in RECORDS[1:]:
        R = list(R0)
        R[24], R[0], R[2], R[3], R[8], R[9] = 0x96B6, 20, 80, 80, ix >> 8, ix & 255
        fl, _, ns = _ev(patch, R, mem, _all_visible(at0))
        s = RECORDS.index(ix)
        ok = not fl and all(ns.attr[t][3] & 0x80 for t in range(NSLOT) if t != s)
        rec('guard death cases (0x96B6)', ok, (ix, fl))
    # guards: IX not a figure record -> no sprite; graphic outside 16-30 -> slot hidden
    for ix in (0xA175, 0xA184, RECORDS[-1] + GUARD_SIZE, 0x0000, 0xA173, 0xA194 + 1):
        fl, _, _ = draw(0x9A5C, ix, 20, 100, 100)
        rec('guard: IX not a figure record (no sprite)', _names(fl) == ['no figure slot'], (hex(ix), fl))
    for gfx in (0, 15, 31, 240):
        fl, _, ns = draw(0x9A5C, RECORDS[2], gfx, 100, 100)
        ok = all(n.startswith('original plot is not graphic') for n in _names(fl)) and not ns.attr[2][3] & 0x80
        rec('guard: graphic outside 16-30 (slot hidden)', ok, (gfx, fl))
    # level-start prints
    for site, R1 in (('tr', first.get('tr')), ('tg', first.get('tg'))):
        if R1 is None:
            c['no captured %s state FAIL!' % site] += 1
            continue
        Rs, ms, ats = R1
        mm = bytearray(ms)
        for b, cc in CELLS:
            hls = [Rs[6] << 8 | Rs[7]] if site == 'tr' else [0x919D + 2 * (k + 1) for k in range(7)]
            for hl in hls:
                R = list(Rs)
                R[0], R[2], R[3], R[6], R[7] = 30, b, cc, hl >> 8, hl & 255
                fl, npx, _ = _ev(patch, R, mm, ats)
                rec('level-start print cases (%s)' % ('runner' if site == 'tr' else '7 guards'), not fl and npx, (hex(hl), b, cc, fl))
        if site == 'tg':
            for hl in (0x919D, 0x919E, 0x91AD, 0x929F):          # not a guard slot: the original print
                R = list(Rs)
                R[0], R[2], R[3], R[6], R[7] = 30, 9, 9, hl >> 8, hl & 255
                fl, _, ns = _ev(patch, R, mm, ats)
                names = _names(fl)
                ok = 'no figure slot' in names and set(names) <= {'no figure slot', 'level-start print: the build '
                                                                  'did not print the blank tile over the figure cell'}
                rec('guard: level-start print outside the guard list (original print)', ok, (hex(hl), fl))
    # fade / clear: every slot hidden
    for k in ('fd', 'cl'):
        if k not in first:
            c['no captured %s state FAIL!' % k] += 1
            continue
        Rs, ms, ats = first[k]
        fl, _, ns = _ev(patch, list(Rs), bytearray(ms), _all_visible(ats))
        rec('%s cases' % ('fade' if k == 'fd' else 'screen clear'), not fl, fl)
    # figure colour paints: every site, colours 7 / 67 / 71, flags as the original's
    if 'pt' in first:
        Rs, ms, ats = first['pt']
        mm = bytearray(ms)
        for site in PAINT_SITES:
            for a in (7, 67, 71):
                for b, cc in CELLS:
                    R = list(Rs)
                    R[24], R[0], R[2], R[3] = site, a, b, cc
                    fl, _, _ = _ev(patch, R, mm, ats)
                    rec('paint cases (5 sites x 3 colours x 4 cells)', not fl, (hex(site), a, fl))
    else:
        c['no captured pt state FAIL!'] += 1
    # Enhanced: every tile printed at corners and a middle cell; the map entry, R and the stack checked; the XOR entry both ways
    if patch.enhanced:
        if 'tl' not in first or 'xr' not in first:
            c['no captured tl / xr state FAIL!'] += 1
        else:
            Rs, ms, ats = first['tl']
            mm = bytearray(ms)
            for a in range(256):
                for b, cc in ((0, 0), (31, 21), (17, 20), (0, 23)):
                    R = list(Rs)
                    R[0], R[2], R[3] = a, b, cc
                    fl, _, ns = _ev(patch, R, mm, ats)
                    i = (cc + 4) * MAP_COLS + 4 + b
                    rec('tile print cases (256 tiles x 4 cells)', not fl and ns.tm[i] == patch.table[a]
                        and sum(1 for v in ns.tm[:1280] if v) == (1 if patch.table[a] else 0), (a, b, cc, fl))
            Rs, ms, ats = first['xr']
            mm = bytearray(ms)
            for a in TILE_ORDER + (240, 246, 249):
                for b, cc in ((0, 0), (31, 21), (17, 20)):
                    R = list(Rs)
                    R[0], R[2], R[3] = a, b, cc
                    fl, _, ns = _ev(patch, R, mm, ats)
                    i = (cc + 4) * MAP_COLS + 4 + b
                    rec('cell XOR cases (the entry follows)', not fl and ns.tm[i] == patch.table[a], (a, b, cc, fl))
    # colour map: a synthetic map built into the patterns; expected colours computed independently
    cm, expect = synthetic_map(peek)
    pc_ = LodeRunnerPatch(patch.prof, colours=cm)
    pc_.prepare(peek)
    for ix in (RECORDS[0], RECORDS[4]):
        kind = 'R' if ix == RUNNER_REC else 'G'
        for gfx in FIG_FRAMES:
            fl, npx, ns = draw(0x9A5C, ix, gfx, 37, 51, pc_, cm)
            got = ns.slot_pixels(RECORDS.index(ix))
            want = {}
            for r in range(8):
                for b in range(8):
                    v = expect(kind, GFX + 8 * gfx + r, b)
                    if v:
                        want[(37 + b, 51 + r)] = v
            rec('colour map cases (synthetic map, wrong check byte ignored)', not fl and got == want, (kind, gfx, fl))
    # negative controls: broken patches with their own tables must be detected
    for name, neg in negs:
        det = tot = 0
        for ix in (RECORDS[0], RECORDS[5]):
            for gfx in (16, 22, 30):
                if name in ('patterns shifted 1 px', 'wrong R on exit'):
                    fl, _, _ = draw(0x9A5C, ix, gfx, 77, 88, neg)
                elif name == 'paint as NOP NOP NOP' and 'pt' in first:
                    Rs, ms, ats = first['pt']
                    R = list(Rs)
                    R[24], R[0], R[2], R[3] = PAINT_SITES[gfx % 5], 71, gfx - 10, 5
                    fl, _, _ = _ev(neg, R, bytearray(ms), ats)
                elif name == 'fade without the hook' and 'fd' in first:
                    Rs, ms, ats = first['fd']
                    fl, _, _ = _ev(neg, list(Rs), bytearray(ms), _all_visible(ats))
                else:
                    continue
                tot += 1
                det += bool(fl)
        c['negative control "%s" detected' % name] += det
        c['negative control "%s" NOT DETECTED!' % name] += tot - det
    return c


def negative_patches(patch):
    """Broken copies, each with its own tables: patterns one pixel right; the colour paints as three
    NOPs (flags differ); the fade site left original (sprites stay up)."""
    import copy
    out = []
    q = copy.copy(patch)
    p = bytearray(patch.pats)
    sh = bytearray(len(p))
    for r in range(len(p) // 8):
        row = int.from_bytes(p[8 * r:8 * r + 8], 'big')
        sh[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
    q.pats = bytes(sh)
    out.append(('patterns shifted 1 px', q))
    q = copy.copy(patch)
    q.sites = [(a, o, bytes(3) if a in PAINT_SITES else n) for a, o, n in patch.sites]
    out.append(('paint as NOP NOP NOP', q))
    q = copy.copy(patch)
    code = bytearray(patch.code)
    i = code.index(bytes([0x3E, (1 - 4 - 2) & 0x7F, 0xCD]))    # e_draw's LD A,D_PLOT / CALL hlib_r_set
    code[i + 1] = (code[i + 1] + 1) & 0x7F
    q.code = bytes(code)
    out.append(('wrong R on exit', q))
    q = copy.copy(patch)
    q.sites = [(a, o, o if a == 0x854F else n) for a, o, n in patch.sites]
    out.append(('fade without the hook', q))
    return out


def clock_matrix(patch, states, neg=False):
    """The every-site clock matrix (hooklib.every_site; refactor plan 4, owner 2026-11-04): each hook site, from a
    state the replays captured, entered at 3.5 / 7 / 14 / 28 MHz (NR 7 = 0-3), run to where the original resumes.
    The exit speed must be the incoming one and the result (CMP registers, every RAM byte, the sprite attributes)
    the same at every clock. Dean's hooks never write NR 7. neg=True: the negative control, a build whose draw hook
    forces 3.5 MHz on its way out (NEXTREG 7,0 before the JP to the plotter). -> (Counter, rows)."""
    import hashlib
    from .hooklib import every_site
    pt = patch
    if neg:
        import copy
        pt = copy.copy(patch)
        code = bytearray(patch.code)
        jp = bytes([0xC3]) + PLOT.to_bytes(2, 'little')
        i = code.index(jp)                              # e_draw's exit: JP PLOT
        stub = HOOK_ORG + len(code)
        code[i:i + 3] = bytes([0xC3]) + stub.to_bytes(2, 'little')
        code += bytes([0xED, 0x91, 0x07, 0x00]) + jp     # NEXTREG 7,0 / JP PLOT
        pt.code = bytes(code)
    psite = pt.psite()
    by = {}
    for kind, R, mem, attrs in states:
        site = R[24]
        if site in CALL_SITES or site in JP_SITES or site in (TILE_SITE, XOR_SITE, EDIT_SITE):
            by.setdefault(site, (R, mem, attrs))
    dr = by.get(0x9A5C)
    for site in (0x970C, 0x9E1B, 0x96B6):     # plotter CALL sites a replay may not reach: a captured draw's state,
        if site not in by and dr is not None:  # PC at that site (A, B, C, IX: a real figure; Dean's code there)
            R = list(dr[0])
            R[24] = site
            by[site] = (R, dr[1], dr[2])

    def run(site, clock):
        R, mem, attrs = by[site]
        end = JP_SITES[site][3] if site in JP_SITES else {TILE_SITE: 0x8540, XOR_SITE: 0x9875, EDIT_SITE: EDIT_END}.get(site, site + 3)
        sp0 = R[12]
        ns = NextState(patch.pats)
        O, P = _overlays(mem.__getitem__, psite, ns=ns)
        m = P()
        ns.attr = [list(a) for a in attrs]
        ns.nr[7] = clock
        sim = _machine(_rw(), m, list(R), ns, 'p')
        if not _run(sim, lambda r: r[24] == end and r[12] == sp0):
            return None, 'did not return'
        r = sim.registers
        ram = hashlib.md5(bytes(m[a] for a in range(0x4000, 0x10000) if not HOOK_RAM[0] <= a < HOOK_RAM[1])).hexdigest()   # the latch holds the clock
        return ns.nr.get(7, clock) & 3, (tuple(r[i] for i in CMP), ram, tuple(tuple(a) for a in ns.attr))
    return every_site(sorted(by), run)


def boot_check(nex, z80, patch=None, tail=None):
    """nextboot.check for this 128K build (the shared one compares bank 0 at 0xC000 and the 48K MMU; this game
    runs with bank 4 there, paging unlocked): registers, every 128K bank of the .nex against the (patched)
    snapshot, RAM 0x4000-0xFFFF with the snapshot's own bank at 0xC000 (the tail excepted), what slots 0/1
    show (the system ROM3 for the plain build; the whole alt ROM image - Sinclair's ROM + the register block -
    for the sprite build), $8C, paging as saved, MMU. Modelled on rainbow_z80n.boot_check. -> problems."""
    import copy
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    sysrom = nextboot.system_rom3()[0]
    st = nextboot.boot(nex, s.pc, sysrom=sysrom, nexload=patch is not None)
    R, mem, bad = st['R'], st['mem'], list(st['bad'])
    w = lambda h, l: R[h] * 256 + R[l]
    got = [w(2, 3), w(4, 5), w(6, 7), w(0, 1), w(8, 9), w(10, 11), w(18, 19), w(20, 21), w(22, 23),
           w(16, 17), R[12], R[14], R[27], R[26]]
    exp = [s.bc, s.de, s.hl, s.a * 256 + s.f, s.ix, s.iy, s.bc_, s.de_, s.hl_, s.a_ * 256 + s.f_,
           s.sp, s.i, s.im, s.iff1]
    bad += [('register', i, g, e) for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    banks, _, _ = nextboot.load_nex(nex)
    t0, t1 = tail if tail else (TAIL_ADDR, TAIL_ADDR + MAX_TAIL)
    for b in range(8):
        d = [i for i in range(16384) if banks[b][i] != s.banks[b][i]
             and not (b == 2 and t0 <= 0x8000 + i < t1)]
        if d:
            bad.append(('NEX bank differs from the (patched) snapshot', b, len(d), d[:4]))
    top = s.port7ffd & 7
    ram = s.banks[5] + s.banks[2] + s.banks[top]
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not t0 <= a < t1]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    if patch is not None:
        img = bytearray(patch.altrom_low[1] + patch.page)
        regs = zt.build_tail(s, 0x8000, patch.slot1, True)[3]
        img[patch.regblock:patch.regblock + len(regs)] = regs
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
    else:
        img = bytearray(sysrom)
        if st['nr'].get(0x8C, 0) != 0:
            bad.append(('$8C', st['nr'].get(0x8C)))
    view = bytes(mem[a] for a in range(0x4000))
    if view != bytes(img):
        d = [a for a in range(0x4000) if view[a] != img[a]]
        bad.append(('slots 0/1 differ from the expected ROM image', len(d), d[:6]))
    if st['p7ffd'] & 0x3F != s.port7ffd & 0x3F or not st['p1ffd'] & 4:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 2 * top, 2 * top + 1]:
        bad.append(('MMU', st['mmu']))
    if patch is not None and st['nr'].get(0x15) != 1:
        bad.append(('sprites not enabled by setup', st['nr'].get(0x15)))
    return bad


def setup_check(nex_bytes, pats, setup_at=0xD000, printer=None, tiles=None):
    """Simulate the set-up routine (0xD000, stub bank 10 at 0xC000) from the built .nex's own banks:
    every port and NEXTREG write. -> list of problems (empty = OK)."""
    from .recolour import banks
    from skoolkit.simulator import R2
    bk = banks(nex_bytes)
    pages = {}
    for b, d in bk.items():
        pages[2 * b], pages[2 * b + 1] = bytearray(d[:8192]), bytearray(d[8192:])
    mmu = [0xFF, 0xFF, 10, 11, 4, 5, 20, 21]
    log, stream = [], bytearray()

    class Mem(list):
        def __getitem__(s, a):
            m = mmu[a >> 13]
            return 0 if m == 0xFF else pages.setdefault(m, bytearray(8192))[a & 0x1FFF]

        def __setitem__(s, a, v):
            m = mmu[a >> 13]
            if m != 0xFF:
                pages.setdefault(m, bytearray(8192))[a & 0x1FFF] = v
    sim = _rw()(Mem([0] * 65536), {'PC': setup_at, 'SP': 0xDFF0})
    R, ed, mem = sim.registers, sim.after_ED, sim.memory
    mem[0xDFF0], mem[0xDFF1] = 0xFE, 0xFF                  # return address 0xFFFE = done

    def nr(reg, val):
        log.append(('nr', reg, val))
        if 0x50 <= reg <= 0x57:
            mmu[reg - 0x50] = val

    def nn():
        q = R[24]
        nr(mem[q + 2], mem[q + 3])
        R[15] = R2[R[15]]
        R[24] = q + 4

    def na():
        q = R[24]
        nr(mem[q + 2], R[0])
        R[15] = R2[R[15]]
        R[24] = q + 3
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs, port):
            return 0xFF

        def write_port(s, regs, port, value, *x):
            if port & 0xFF == 0x5B:
                stream.append(value)
            else:
                log.append(('out', port, value))
    sim.set_tracer(Tr())
    n = 0
    while R[24] != 0xFFFE:
        sim.opcodes[mem[R[24]]]()
        n += 1
        if n > 200000:
            return ['set-up did not return']
    bad = []
    if bytes(stream) != bytes(pats):
        bad.append('pattern upload != the built patterns (%d bytes sent, %d expected)' % (len(stream), len(pats)))
    if ('out', 0x303B, 0) not in log:
        bad.append('pattern slot not set to 0')
    regs = [(r, v) for k, r, v in log if k == 'nr']
    i = regs.index((0x40, 1)) if (0x40, 1) in regs else -1
    if i < 0 or [v for r, v in regs[i + 1:] if r == 0x41][:15] != PALETTE[1:]:
        bad.append('sprite palette indices 1-15 are not the Spectrum colours')
    if (0x43, 0x20) not in regs or (0x4B, 0) not in regs:
        bad.append('palette select / transparency index not set')
    hidden = {v for r, v in regs if r == 0x34}
    if hidden != set(range(128)):
        bad.append('not every sprite hidden at set-up')
    if printer is not None and bytes(pages[10][0x1B00:0x1C00]) != bytes(printer):
        bad.append('printer buffer not put back')
    if tiles is None and regs[-1] != (0x15, 1):
        bad.append('sprites not switched on last')
    if tiles is not None:
        want = {(0x6E, 0x80), (0x6F, 0x85), (0x6B, 0xA1), (0x4C, 0)}
        if not want <= set(regs):
            bad.append('tilemap not set up: %s' % sorted(want - set(regs)))
        if bytes(pages[14][TILE_DEFS:TILE_DEFS + len(tiles)]) != bytes(tiles):
            bad.append('tile definitions not in bank 7')
        if any(pages[14][:1280]):
            bad.append('map not empty at the start')
    if mmu[7] != 21:
        bad.append('MMU slot 7 not restored (%d)' % mmu[7])
    return bad


# ---------------------------------------------------------------------------------------------
# auto: plain + sprite build, boot checks, verification of each RZX + a free run, unit tests
# ---------------------------------------------------------------------------------------------
FREE_FRAMES = 6000
DECISIONS = {'engine': 'loderunner_v2', 'base': "Dean's loderunner (hooks, profile, colours read, not copied)",
             'input': 'the 128K release (AY music from bank 4 in the IM 2 handler)',
             'strategy': 'RAM hooks 0xA460 (Dean); whole alt ROM image: Sinclair\'s 48K ROM + the register block at '
                         '0x386E (the fade reads 0x0000-0x3FFF as masks)',
             'tail': '0xA400', 'colours': 'docs/profiles/lode_runner_colours.json (none = defaults)'}


def free128_keys(frames=FREE_FRAMES, seed=7):
    """The 128K menu (1 keyboard, 0 start, any key), then random runs and digs on its default keys I P Q A, N M."""
    import random
    rnd = random.Random(seed)
    k = ['260-266:1', '306-312:0', '372-378:SPACE', '720-724:P']
    f = 760
    while f < frames:
        d = rnd.randint(6, 40)
        k.append('%d-%d:%s' % (f, f + d, rnd.choice(['I', 'P', 'Q', 'A', 'I+N', 'P+M', 'I', 'P'])))
        f += d + rnd.randint(1, 6)
    return ';'.join(k)


def free_keys(frames=FREE_FRAMES, seed=7):
    """Key definition O P Q A M, Y, any key, 0 (start), any key; then random runs and digs."""
    import random
    rnd = random.Random(seed)
    k = ['10-12:O', '20-22:P', '30-32:Q', '40-42:A', '50-52:M', '70-72:Y', '120-122:SPACE', '200-202:0',
         '300-302:SPACE']
    f = 600
    while f < frames:
        d = rnd.randint(20, 120)
        k.append('%d-%d:%s' % (f, f + d, rnd.choice(['O', 'P', 'Q', 'A', 'O+M', 'P+M', 'O', 'P'])))
        f += d + rnd.randint(1, 10)
    return ';'.join(k)


def auto(a, z80, name, out, say):
    import hashlib
    from skoolkit.snapshot import Snapshot
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : loderunner_v2 (Lode Runner 128K: Dean\'s loderunner, XOR plotter 0x9712 -> sprites: runner + guards; whole alt ROM image)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = boot_check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X: zero, never touched)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = LodeRunnerPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (%d patterns, colour map %d entries)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200],
        patch.num_patterns, len(patch.colours)))
    sb = setup_check(open(spr, 'rb').read(), patch.pats, patch.setup_call, patch.printer)
    say('Set-up    : pattern upload (%d bytes = the built patterns), palette 1-15, transparency 0, 128 '
        'sprites hidden, sprites on, MMU restored, printer buffer put back -> %s' % (len(patch.pats), 'OK' if not sb else 'FAILED %s' % sb))
    ok = not bad and not bad2 and not sb
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):           # selftest rebuild: build only
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    runs = [(r, None) for r in (a.rzx or [])] + ([] if getattr(a, 'quick', None) else [(None, free_keys())])
    states = []
    from .simrun import rzx_frames
    for r, keys in runs:
        frames = getattr(a, 'quick', None) or (rzx_frames(r)[0] if r else FREE_FRAMES)   # v2: every recording whole
        c, ex, st = verify(patch, z80, r, frames=frames, keys=keys, stop=getattr(a, 'quick', None), collect=1)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!') and v}
        ok = ok and not fails
        say('Verify    : %s  %d frames, draws %d + %d, erases %d, deaths %d, prints %d + %d, paints %d, fades %d, '
            'clears %d, %d sprite pixels, %d frame checks (%d in fades), %d harmless attribute reads, lowest SP '
            '0x%04X -> %s' % (
                os.path.basename(r) if r else 'free run (keys, %d frames)' % frames, c['frames'], c['dr'], c['drr'],
                c['er'], c['hd'], c['tr'], c['tg'], c['pt'], c['fd'], c['cl'], c['sprite pixels compared'],
                c['frame checks'], c['frame checks skipped (fade)'],
                sum(v for k, v in c.items() if k.startswith('attribute reads that differ, harmless')),
                c['lowest SP in the patched code'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!') and v}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k[:-3] if k.endswith(' ok') else k, v)
                                                for k, v in sorted(u.items())
                                                if k.endswith(' ok') or k.endswith(' detected')),
                                       'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in sorted(u.items()):
            if k.startswith('  '):
                say('           %s' % k)
    if states:
        cm, rows = clock_matrix(patch, states)
        cn, _ = clock_matrix(patch, states, neg=True)
        sites = sorted({r['site'] for r in rows})
        bad = {k: v for k, v in cm.items() if k.endswith('!')}
        caught = sum(v for k, v in cn.items() if k.endswith('!'))
        ok = ok and not bad and caught > 0
        say('Clocks    : every-site matrix, %d hook sites (%s) x 4 incoming clocks = %d cases: exit speed = the incoming '
            'one, result the same at every clock -> %s; negative "forced 3.5 MHz exit" (draw hook) caught at %d cases -> %s' % (
                len(sites), ', '.join('0x%04X' % x for x in sites), cm['cases'], 'PASS' if not bad else 'FAIL %s' % bad,
                caught, 'DETECTED' if caught else 'NOT DETECTED!'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# The three modes: python -m nexclash.loderunner_v3 build GAME.z80 OUTDIR --backdrop FILE.B00 --palette FILE.pal
# ---------------------------------------------------------------------------------------------
def build_modes(z80, out, backdrop=None):
    from . import z80tonex as zt
    res = {}
    for mode in MODES:
        patch = LodeRunnerPatch(mode=mode, backdrop=backdrop)
        path = os.path.join(out, 'lr3_%s.nex' % mode)
        conv = zt.convert(z80, path, None, True, quiet=True, patch=patch)
        res[mode] = (path, patch, conv)
    return res


if __name__ == '__main__':
    import sys
    a = sys.argv[1:]
    if a and a[0] == 'build':
        r = build_modes(a[1], a[2], (a[a.index('--backdrop') + 1], a[a.index('--palette') + 1]) if '--backdrop' in a else None)
        for m, (p, pt, c) in r.items():
            print(m, p, boot_check(p, a[1], pt, (c[1], c[1] + len(c[2]))) or 'boot OK',
                  setup_check(open(p, 'rb').read(), pt.pats, pt.setup_call, pt.printer) or 'setup OK')


def replay_negatives(patch, z80, rzx, frames, edit_rzx=None, edit_frames=None):
    """Deliberately broken copies of this mode's patch, replayed: each must fail. -> {name: failures}."""
    import copy
    out = {}

    def broken(name, f, rec=None, n=None):
        q = copy.copy(patch)
        f(q)
        c, _, _ = verify(q, z80, rec or rzx, frames=n or frames, stop=n or frames)
        out[name] = sum(v for k, v in c.items() if k.endswith('!'))

    def code_edit(q, at_sym, old, new):
        code = bytearray(q.code)
        i = code.index(old, q.syms[at_sym] - HOOK_ORG)
        code[i:i + len(old)] = new
        q.code = bytes(code)
    bump = bytes([0x3E, (1 - 4 - 2) & 0x7F, 0xCD])
    broken('R off by one at the draw hook', lambda q: code_edit(q, 'e_draw', bump, bytes([0x3E, (2 - 4 - 2) & 0x7F, 0xCD])))
    broken('colour paint keeps its write', lambda q: code_edit(q, 'paint', bytes([0x00, 0xE1, 0xC1, 0xC9]), bytes([0x77, 0xE1, 0xC1, 0xC9])))
    broken('fade without the hook', lambda q: setattr(q, 'sites', [(a, o, o if a == 0x854F else n) for a, o, n in q.sites]))
    if edit_rzx:
        broken('editor keeps the sprite hooks', lambda q: setattr(q, 'sites', [(a, o, o if a == EDIT_SITE else n) for a, o, n in q.sites]),
               edit_rzx, edit_frames)
    if patch.enhanced:
        s2 = lambda addr: (lambda q: setattr(q, 'sites', [(a, o, o if a == addr else n) for a, o, n in q.sites]))
        broken('tile print without the map', s2(TILE_SITE))
        broken('cell XOR without the map', s2(XOR_SITE))
        broken('clear leaves the map', lambda q: setattr(q, 'sites', [(a, o, (bytes([0xC3]) + q.syms['e_cls'].to_bytes(2, 'little')) if a == 0x8541 else n) for a, o, n in q.sites]))

        def tab(q):
            t = bytearray(q.table)
            t[33] = t[35]
            q.table = bytes(t)
        broken('tile table: bricks as ladders', tab)
        mw = (0x4000 + 4 * 40 + 4).to_bytes(2, 'little')
        broken('map one column out', lambda q: code_edit(q, 'e_tile', bytes([0x11]) + mw, bytes([0x11]) + (0x4000 + 4 * 40 + 5).to_bytes(2, 'little')))
    return out
