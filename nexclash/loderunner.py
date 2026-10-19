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
PAINT_ORIG, PAINT_NEW = 'cd6e85', 'feff00'
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


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'lode_runner.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_loderunner(snap):
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '48K':
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
    name = 'Lode Runner runner + guards -> hardware sprites (hooks in RAM 0xA460)'

    def __init__(self, prof=None, colours=None):
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
        self.colours = load_colours() if colours is None else colours
        self.sites = []
        for a, (old, sym, _) in CALL_SITES.items():
            self.sites.append((a, bytes.fromhex(old), bytes([0xCD]) + self.syms[sym].to_bytes(2, 'little')))
        for a, (old, sym, _, _) in JP_SITES.items():
            self.sites.append((a, bytes.fromhex(old), bytes([0xC3]) + self.syms[sym].to_bytes(2, 'little')))
        for a in PAINT_SITES:
            self.sites.append((a, bytes.fromhex(PAINT_ORIG), bytes.fromhex(PAINT_NEW)))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.pats = None
        self.num_patterns = NPAT

    def psite(self):
        """{address: byte} of every RAM byte the patch changes (sites + hook code)."""
        d = {a + k: v for a, old, new in self.sites for k, v in enumerate(new)}
        d.update({HOOK_ORG + k: v for k, v in enumerate(self.code)})
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
        self.pats = patterns(peek, self.colours)
        self.extra_banks = {11: self.pats + bytes(16384 - len(self.pats))}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('the Lode Runner patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        self.prepare(lambda a: ram[a - 0x4000] if a >= 0x4000 else 0)
        for a, v in self.psite().items():
            ram[a - 0x4000] = v
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


# ---------------------------------------------------------------------------------------------
# Recolour (PLAYBOOK 3b): the patterns (bank 11) are the only colour-dependent bytes; the game
# never reads bank 11.
# ---------------------------------------------------------------------------------------------
RECOLOUR = {'game': 'lode_runner', 'output': 'sprites', 'colours': 'docs/profiles/lode_runner_colours.json',
            'clear': True, 'note': NOTE}


def recolour(nex, cmap):
    """Built lode_runner_sprites.nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that
    is not this engine's build of the expected snapshot."""
    from .recolour import nex_offsets
    d = bytearray(nex)
    off = nex_offsets(d)
    need = {5, 2, 0, 10, 11}
    if not need <= set(off):
        raise ValueError('not a Lode Runner sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000] if a >= 0x4000 else 0
    prof = load_profile()
    want = prof.get('colour_inputs', {})
    if [want.get('md5'), want.get('bytes')] != list(colour_inputs_md5(peek)):
        raise ValueError('game graphics differ from the expected snapshot')
    p = LodeRunnerPatch(prof, colours=cmap)
    for a, v in p.psite().items():
        if peek(a) != v:
            raise ValueError('0x%04X does not hold this build\'s patch / hook byte' % a)
    if bank(10)[0x1000:0x1000 + len(p.stub_extra)] != p.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    p.pats = patterns(peek, cmap)
    new = p.pats + bytes(16384 - len(p.pats))
    changed = [11] if bank(11) != new else []
    d[off[11]:off[11] + 16384] = new
    return bytes(d), {'banks changed': changed, 'patterns': NPAT, 'map entries': len(cmap)}


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


def _machine(Sim, mem, regs, ns):
    from skoolkit.simulator import R2
    sim = Sim(mem, {})
    sim.registers[:] = regs
    R, ed = sim.registers, sim.after_ED

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]
        R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]
        R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.events.append(('out', port, value))
    sim.set_tracer(Tr())
    return sim


STACK_FLOOR = 0xAB03       # IM 2 table 0xAA00-0xAB00: an interrupt (2 bytes) below SP must stay above it
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


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


def _overlays(get, psite, canvas=None):
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
            v = s.ov.get(a)
            if v is not None:
                return v
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)
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
    end = JP_SITES[site][3] if kind in ('fd', 'cl') else site + 3

    def stop(r):
        return r[24] == end and r[12] == sp0
    O, P = _overlays(get, psite)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    before = [list(a) for a in ns.attr]
    ns.events = []
    sp_ = _machine(Sim, p, list(R), ns)
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
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access in hook',))
    if any(e[1] not in (0x34, 0x35, 0x36, 0x37, 0x38, 0x39) for e in ns.events if e[0] == 'nr'):
        f.append(('NEXTREG other than sprite attributes',))
    dead = range(sp0 - 64, sp0)
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not 0x4000 <= a < 0x5B00 and a not in dead and o[a] != p[a]]
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
    if kind in ('er', 'pt'):
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
    sc = _machine(Sim, oc, list(R), NextState(b''))
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


def verify(patch, z80, rzx=None, frames=6000, keys=None, stop=None, collect=0, progress=None):
    """Run the original game (RZX, or a free run); at every patch site run original and patched code
    from the same state and compare; keep the patched game's screen / attributes as a model and check
    every frame that ULA difference == the visible sprites' graphics, and that every read of the
    screen or the attributes by game code sees the same value. -> (Counter, examples, states)."""
    from . import simrun
    c = collections.Counter()
    ex = collections.defaultdict(list)
    site_bytes = set(patch.psite())
    cmap = patch.colours
    ns = NextState(patch.pats)
    st = {'ready': False, 'frame': 0, 'pending': {}, 'want': False, 'fading': False, 'paint': None, 'tprint': None}
    states = []
    cnt = collections.Counter()
    WATCH = set(CALL_SITES) | set(JP_SITES) | set(PAINT_SITES) | set(ERASE_SITES)
    INT = set(INTERIORS) | {0x8551}
    m0 = {}

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

    class H:
        def on_sim(self, sim):
            st['sim'] = sim
            st['ready'] = False
            m = st['raw'] = getattr(sim.memory, 'm', sim.memory)    # 48K: the list under simrun's watcher
            m0['oscr'] = bytearray(m[0x4000 + i] for i in range(6144))
            m0['pscr'] = bytearray(m0['oscr'])
            m0['oattr'] = bytearray(m[0x5800 + i] for i in range(768))
            m0['pattr'] = bytearray(m0['oattr'])
            st['ready'] = True

        def on_read(self, addr, pc, mem):
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
                if name == 'patterns shifted 1 px':
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
    q.sites = [(a, o, o if a == 0x854F else n) for a, o, n in patch.sites]
    out.append(('fade without the hook', q))
    return out


# ---------------------------------------------------------------------------------------------
# auto: plain + sprite build, boot checks, verification of each RZX + a free run, unit tests
# ---------------------------------------------------------------------------------------------
FREE_FRAMES = 6000
DECISIONS = {'engine': 'loderunner', 'strategy': 'RAM hooks 0xA460 (alt ROM read by the fade)',
             'tail': '0xA400', 'colours': 'docs/profiles/lode_runner_colours.json (none = defaults)'}


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
    say('Engine    : loderunner (Lode Runner: XOR plotter 0x9712 -> sprites: runner + guards)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X: zero, never touched)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = LodeRunnerPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (%d patterns, colour map %d entries)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200],
        patch.num_patterns, len(patch.colours)))
    ok = not bad and not bad2
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):           # selftest rebuild: build only
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    runs = [(r, None) for r in (a.rzx or [])] + ([] if getattr(a, 'quick', None) else [(None, free_keys())])
    states = []
    for r, keys in runs:
        frames = getattr(a, 'quick', None) or FREE_FRAMES
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
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
