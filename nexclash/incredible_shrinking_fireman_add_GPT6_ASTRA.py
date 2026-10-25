"""The Incredible Shrinking Fireman (Mastertronic, 1986; 48K) - engine `incredible_shrinking_fireman_add_GPT6_ASTRA`.

Capture, build, differential verification, and isolated per-pixel recolour.

    python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA sheet R.rzx [MORE.rzx] --z80 GAME.z80 -o PREFIX
    python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA colours PREFIX_PAINTING_SPRITES_painted.png

Figures (games/incredible_shrinking_fireman-add-GPT6_ASTRA.md):
  0xB950 moves object A (A = 0 fireman, 1 / 2 the room's two enemies) of the 8-byte table at 0xBCF7
  (x, y, frame, -, dx, dy, attribute, attribute keep-mask) to (x + dx, y + dy) showing frame (0xBCF6),
  XORing old ^ new graphic into the screen in ONE pass (delta draw); frame 0 is blank (appear /
  disappear). Then 0xBC5F paints the figure's 2 x 3 (3 x 4 unaligned) cells: attr = (scr ^ E) & D ^ E,
  E = attribute, D = keep-mask, cells flagged by bit 6 in the map at 0xBD44 left alone.
  Graphics: 16 x 24 px, 2 bytes per line top down, at base (0xBD42, 0x9C40 in every recording) +
  ((3 * frame) & 255) * 16 - the game's 8-bit multiply: frames >= 86 wrap.
Colour-map keys: G + graphics-byte address + source ink; D + address for diamonds; default colour = the ink the game gives the figure
(fireman: white; enemies: their room's bright ink).
"""
# Capture adapted from add-OPUS; runtime/verifier adapted from fireman.py.
import collections
import json
import os

PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
BLACK = 8                                   # index 0 is transparent: black figures use 8
PLOT, OBJ, NEWF, GBASE, ATTRMAP = 0xB950, 0xBCF7, 0xBCF6, 0xBD42, 0xBD44
W, H = 16, 24
GROUPS = ('Fireman', 'Enemies')
STATIC_GROUP = 'From the code (not in the recordings)'
_HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = 'incredible_shrinking_fireman-add-GPT6_ASTRA'
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'incredible_shrinking_fireman_colours-add-GPT6_ASTRA.json')
NOTE = ('Incredible Shrinking Fireman figure colours, read back from the PAINTING_SPRITES sheet '
        '(python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA colours). Key = G + graphics byte + source ink (D for diamond); '
        'address; check = that byte, 8 nibbles = colours of its bits (0 = the game\'s ink).')


def gfx_addr(base, frame):
    """Address of a frame's 48 bytes: the plotter's own (8-bit) arithmetic."""
    return (base + ((3 * frame) & 255) * 16) & 0xFFFF


def ink_index(attr):
    """Spectrum attribute -> sheet palette index of its ink (black -> BLACK)."""
    ink = attr & 7
    if not ink:
        return BLACK
    return ink + (8 if attr & 64 else 0)


def figure_part(peek, base, frame, group, ink):
    a0 = gfx_addr(base, frame)
    pixels, entries = [], {}
    for line in range(H):
        for half in range(2):
            a = (a0 + line * 2 + half) & 0xFFFF
            v = peek(a)
            key = 'G%04X_I%02d' % (a, ink)
            for bit in range(8):
                code = int(bool(v & (128 >> bit)))
                pixels.append((half * 8 + bit, line, key, bit, code, ink if code else 0))
                entries[key] = [v, 'G']
    return dict(id=(base, frame), size=1, w=W, h=H, x=0, y=0, mir=0, group=group, role=group,
                pixels=pixels, entries=entries)


def capture(rzxs):
    """Replay the recordings (C simulator) -> {(group, base, frame, ink): info} of every drawing seen."""
    from . import rzx as RZ
    seen = collections.OrderedDict()

    def on_pc(pc, sim):
        m, R = sim.memory, sim.registers
        a = R[0]
        o = m[OBJ + 8 * a:OBJ + 8 * a + 8]
        f, base = m[NEWF], m[GBASE] | m[GBASE + 1] << 8
        if not f:
            return
        group = GROUPS[0] if a == 0 else GROUPS[1]
        k = (group, base, f, ink_index(o[6]))
        e = seen.get(k)
        if e is None:
            e = seen[k] = dict(group=group, base=base, frame=f, inks=collections.Counter(), count=0,
                               gfx=bytes(m[gfx_addr(base, f) + i & 0xFFFF] for i in range(48)))
        e['inks'][ink_index(o[6])] += 1
        e['count'] += 1
    errs = []
    for path in rzxs:
        n, err = RZ.trace(path, (PLOT,), on_pc)
        errs.append((path, n, err))
    return seen, errs


def composites(seen, peek=None):
    """One composite per (group, graphic, ink): figures are single plots, never joined. A graphic drawn by
    both groups appears in each. peek: the bank's frames the recordings never drew are added."""
    from . import coloursheet as cs
    comps, drawn = [], set()
    for (group, base, f, ink), e in seen.items():
        g = e['gfx']
        p = figure_part(lambda a: g[(a - gfx_addr(base, f)) & 0xFFFF], base, f, group,
                        ink)
        drawn.add((base, f))
        if any(pixel[4] for pixel in p['pixels']):
            p['id'] = (base, f, ink)
            comps.append(dict(count=e['count'], group=group, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    if peek:
        base = peek(GBASE) | peek(GBASE + 1) << 8
        for f in range(1, 86):                       # every whole frame of the bank (3f < 256)
            if (base, f) in drawn:
                continue
            p = figure_part(peek, base, f, STATIC_GROUP, 7)
            if any(pixel[4] for pixel in p['pixels']):
                comps.append(dict(count=0, group=STATIC_GROUP, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    order = list(GROUPS) + [STATIC_GROUP]
    comps.sort(key=lambda c: (order.index(c['group']), c['parts'][0]['id']))
    maxsize = {c['parts'][0]['id']: 1 for c in comps}
    return cs.choose(comps, maxsize, order), comps


def sheets(comps, prefix, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix in ('_PAINTING_SPRITES', '_REFERENCE_ALL_SPRITES'):
        stem = prefix.removesuffix('-add-GPT6_ASTRA') + suffix
        png = stem + '-add-GPT6_ASTRA.png'
        n = cs.write(comps[suffix], png, stem + '_layout-add-GPT6_ASTRA.json', rgb16, colours,
                     unique=False, paint_clear=True)
        out.append((png, n))
    return out


def collectable_sheets(z80, prefix):
    """Room-table items all use the seven-byte diamond at 0xED14.

    0xECFF draws rows bottom to top (DEC B); retain that order in the keys.
    Default white is a proposal, pending the phase-A design answer.
    """
    peek = _peek(z80)
    pixels, entries = [], {}
    for y in range(7):
        addr = 60692 + 6 - y
        value = peek(addr)
        key = 'D%04X' % addr
        entries[key] = [value, 'D']
        for bit in range(8):
            pixels.append((bit, y, key, bit, int(bool(value & (128 >> bit))), 7 if value & (128 >> bit) else 0))
    part = dict(id=(60692, 7), size=1, w=8, h=7, x=0, y=0, mir=0,
                group='Collectables', role='Collectables', pixels=pixels, entries=entries,
                dx=0, dy=0, dmir=0, vmir=0)
    comps = [dict(count=1, group='Collectables', parts=[part])]
    return sheets(dict(_PAINTING_SPRITES=comps, _REFERENCE_ALL_SPRITES=comps),
                  prefix.removesuffix('-add-GPT6_ASTRA') + '_COLLECTABLES', load_colours())


def plain(z80, output):
    """Plain baseline only: preserve the game's printer buffer across NEXLOAD."""
    from . import z80tonex as zt
    from .nextboot import check
    zt.convert(z80, output, tail_req=0x5E40, keep_printer_buffer=True)
    tail = zt.build_tail(zt.Z80Snapshot(z80), 0x5E40)[0]
    for nexload in (False, True):
        bad = check(output, z80, tail=(0x5E40, 0x5E40 + len(tail)), nexload=nexload)
        if bad:
            raise ValueError('Plain boot failed: %r' % bad)
    print('Plain boot: PASS, including NEXLOAD printer-buffer overwrite')


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    p = path or build_colours_path(COLOURS)
    return cs.load(p) if os.path.exists(p) else {}


def _peek(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536])).__getitem__


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', help='also show the frames the recordings never drew (from the code)')
    p.add_argument('-o', '--out', default=RECORD)
    p = sub.add_parser('check', help='quick differential check of the isolated engine')
    p.add_argument('z80')
    p.add_argument('rzx')
    p.add_argument('--quick', type=int, default=2000)
    p.add_argument('--units', action='store_true')
    p.add_argument('-o', '--out', required=True)
    p = sub.add_parser('plain', help='plain NEX baseline, with simulated boot checks')
    p.add_argument('z80')
    p.add_argument('-o', '--out', required=True)
    p = sub.add_parser('colours', help='painted PAINTING sheet -> colours json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--out', default=COLOURS)
    p = sub.add_parser('build', help='build plain and sprite NEX files without replay')
    p.add_argument('z80')
    p.add_argument('-o','--out',required=True)
    p = sub.add_parser('recolour', help='painted sheet to a new NEX without replay')
    p.add_argument('nex'); p.add_argument('painted'); p.add_argument('--layout',required=True)
    p.add_argument('-o','--out',required=True)
    a = ap.parse_args(argv)
    from . import coloursheet as cs
    if a.cmd == 'sheet':
        seen, errs = capture(a.rzx)
        for path, n, err in errs:
            print('%s: %d frames%s' % (path, n, ', DESYNC: ' + err if err else ''))
        if any(err for _, _, err in errs):
            raise SystemExit('Recording desynchronised: sheets withheld')
        chosen, every = composites(seen, _peek(a.z80) if a.z80 else None)
        for png, n in sheets({'_PAINTING_SPRITES': chosen, '_REFERENCE_ALL_SPRITES': every}, a.out,
                             load_colours()):
            print('%s: %d figures' % (png, n))
        if a.z80:
            for png, n in collectable_sheets(a.z80, a.out):
                print('%s: %d figures' % (png, n))
        g = collections.Counter(k[0] for k in seen)
        print('graphics drawn per group:', dict(g))
        for k, e in seen.items():
            if len(e['inks']) > 1:
                print('  %s frame %d drawn in inks %s' % (k[0], k[2], dict(e['inks'])))
    elif a.cmd == 'build':
        from types import SimpleNamespace
        os.makedirs(a.out,exist_ok=True)
        if not auto(SimpleNamespace(rzx=[],quick=None),a.z80,os.path.splitext(os.path.basename(a.z80))[0],a.out,print):
            raise SystemExit(1)
    elif a.cmd == 'recolour':
        recolour_file(a.nex,a.painted,a.layout,a.out)
    elif a.cmd == 'check':
        from .z80tonex import Z80Snapshot
        patch = FiremanPatch()
        patch.apply(Z80Snapshot(a.z80))
        c, ex, states = verify(patch, a.rzx, stop=a.quick, collect=3,
                              progress=lambda n,c: print('frame', n, flush=True))
        u = unit_tests(patch,states,negative_patches(patch,states)) if a.units else {}
        result = {'counters':dict(c), 'examples':ex, 'units':dict(u)}
        with open(a.out,'w') as f:
            json.dump(result,f,indent=2)
        print(json.dumps(result,indent=2), flush=True)
        if any(k.endswith('!') for k in c) or any(k.endswith('!') for k in u):
            raise SystemExit(1)
    elif a.cmd == 'plain':
        plain(a.z80, a.out)
    elif a.cmd == 'colours':
        lay = a.layout or a.png.replace('_painted-add-GPT6_ASTRA.png', '-add-GPT6_ASTRA.png').replace('-add-GPT6_ASTRA.png', '_layout-add-GPT6_ASTRA.json')
        ent, rep = cs.read(a.png, lay)
        cs.save(ent, a.out, NOTE)
        for k, v in rep.items():
            print('%-70s %d' % (k, v))
        print('->', a.out)


import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5E40
HS = 0xF400
SLOTS = 48375
GFXPTR = 48450
PLOTTER = 47440
PLOT_END = 48220
ISR_SITE = 49804
DIA_SITE = 60656
ROOM = 49612
OBJTAB = 55021
DIA_GFX = 60692                 # 7 bytes: the collectable's rows
SPR_DIA = 0                     # sprites 0-4
SPR_SLOT = {0: (9, 10), 1: (7, 8), 2: (5, 6)}
PAT_DIA = 6
DIA_INDEX = 7                   # default white; collectables have per-pixel paint
STACK_DEAD = 64

# (address, original bytes, symbol or None, opcode or None, replacement bytes when no symbol)
SITES = [
    (48220, 'dde1c9', 'e_ep', 0xC3, b''),
    (ISR_SITE, 'd9e1d1', 'e_isr', 0xC3, b''),
    (50343, '210040', 'e_c1', 0xC3, b''),
    (50609, '210048', 'e_c2', 0xC3, b''),
    (DIA_SITE, 'cdffec', 'e_dia', 0xCD, b''),
]
RD_SITES = {49868: ('a', '1aa7c0'), 49872: ('a', '1aa7c0'), 49892: ('a', '1aa7c0'),
            49896: ('a', '1aa7c0'), 51159: ('a', '1aa7c0'), 51163: ('a', '1aa7c0'),
            51183: ('a', '1aa7c0'), 51187: ('a', '1aa7c0'), 51421: ('j', '1aa7c2e7c8'),
            51427: ('z', '1aa728d6')}
RD_SYM = {'a': 'rd_a', 'j': 'rd_j', 'z': 'rd_z'}
SCREEN_PATCHES = [(47897, '77', '00'), (47901, '77', '00'), (47905, '77', '00'), (60683, '77', '00')] + \
    [(a, 'dd7700', '000000') for a in (48047, 48059, 48071, 48083, 48165, 48174, 48183)]
PLOT_WRITERS = {47897, 47901, 47905, 48047, 48059, 48071, 48083, 48165, 48174, 48183}
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6]

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'incredible_shrinking_fireman-add-GPT6_ASTRA.json'),
              os.path.join(_HERE, 'incredible_shrinking_fireman-add-GPT6_ASTRA.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('incredible_shrinking_fireman-add-GPT6_ASTRA.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_fireman(snap):
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


# ---------------------------------------------------------------------------------------------
# Model of what the build must show (independent of the hook code)
# ---------------------------------------------------------------------------------------------

def frame_rows(peek, frame):
    a = (peek(GFXPTR) | peek(GFXPTR + 1) << 8) + 16 * ((3 * frame) & 255)     # 47742: 8-bit wrap
    return [peek(a + 2 * r) << 8 | peek(a + 2 * r + 1) for r in range(24)]


def image_pixels(rows, x, y):
    return {(x + c, y + r) for r, v in enumerate(rows) for c in range(16) if v >> (15 - c) & 1}


def diamond_rows(peek):
    return [peek(DIA_GFX + r) for r in range(7)]


def diamond_pattern(peek):
    """128 bytes: 16 x 16 4-bit pixels, the 8 x 7 diamond at the top left (colour index 4)."""
    out = bytearray(128)
    for r, v in enumerate(diamond_rows(peek)):
        for k in range(4):
            hi = (v >> (7 - 2 * k)) & 1
            lo = (v >> (6 - 2 * k)) & 1
            out[r * 8 + k] = (hi << 4 | lo) * DIA_INDEX
    return bytes(out)


def sprite_pixels(attr, pat):
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return set()
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
    out = set()
    for j in range(16):
        for k in range(16):
            b = pat[base + j * 8 + k // 2]
            if (b >> 4) if k % 2 == 0 else (b & 15):
                out.add((x + k, y + j))
    return out


def model_colour(e):
    """RRRGGGBB of the figure's ink (E bits 0-2: blue, red, green; bit 6: bright)."""
    lv = (7, 3) if e & 0x40 else (5, 2)
    r = lv[0] if e & 2 else 0
    g = lv[0] if e & 4 else 0
    b = lv[1] if e & 1 else 0
    return r << 5 | g << 2 | b


def clip(px):
    return {(x, y) for x, y in px if 0 <= x < 256 and 0 <= y < 192}


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

TABLE_FIRST_PAGE = 32
TABLE_PAGES = 48
GRAPHICS_BASE = 0x9C40
GRAPHICS_BYTES = 4128


def pixel_colour(cmap, key, value, bit, default):
    e = cmap.get(key)
    opaque = bool(value & (128 >> bit))
    if not e or e[0] != value:
        return default if opaque else 0
    if len(e) > 3 and e[3] & (128 >> bit):
        return 0
    return e[2][bit] or (default if opaque else 0)


def display_banks(peek, cmap):
    """Three 8K pages per source ink; every byte expands to four packed pixels.
    Contains all 256 wrapped frame offsets, including 32 bytes of spill at the end.
    """
    tables = bytearray(TABLE_PAGES * 8192)
    for ink in range(16):
        for offset in range(GRAPHICS_BYTES):
            addr = GRAPHICS_BASE + offset
            value = peek(addr)
            key = 'G%04X_I%02d' % (addr, ink)
            base = ink * 24576 + offset * 4
            for pair in range(4):
                tables[base+pair] = (pixel_colour(cmap,key,value,2*pair,ink) << 4 |
                                    pixel_colour(cmap,key,value,2*pair+1,ink))
    return {16+b: bytes(tables[b*16384:(b+1)*16384]) for b in range(24)}


def painted_diamond(peek, cmap):
    out = bytearray(128)
    for row in range(7):
        addr = DIA_GFX + 6 - row
        value = peek(addr)
        for pair in range(4):
            key = 'D%04X' % addr
            out[row*8+pair] = (pixel_colour(cmap,key,value,2*pair,7)<<4 |
                              pixel_colour(cmap,key,value,2*pair+1,7))
    return bytes(out)


class FiremanPatch:
    name = 'Incredible Shrinking Fireman figures + collectables -> hardware sprites (altrom hooks)'

    def __init__(self, prof=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom-add-GPT6_ASTRA'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup-add-GPT6_ASTRA'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.keep_printer_buffer = True
        self.cmap = load_colours()
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long (0x3D00+ is the DivMMC entry area)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        if self.rom_code[0x39FF - ROM_ORG:0x3A01 - ROM_ORG] != b'\xff\xff':
            raise ValueError('the IM 2 vector bytes 0x39FF / 0x3A00 must stay FF FF')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.sites = []
        for a, old, sym, op, extra in SITES:
            self.sites.append((a, bytes.fromhex(old), bytes([op]) + self.syms[sym].to_bytes(2, 'little') + extra))
        for a, (kind, old) in RD_SITES.items():
            o = bytes.fromhex(old)
            self.sites.append((a, o, b'\xcd' + self.syms[RD_SYM[kind]].to_bytes(2, 'little') + bytes(len(o) - 3)))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.pats = None
        self.num_patterns = 7

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Fireman patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for lo, n, what in ((TAIL_ADDR, 256, 'tail'), (HS, 32, 'hook state')):
            if any(ram[lo - 0x4000:lo - 0x4000 + n]):
                raise ValueError('%s area at 0x%04X is not zero in this snapshot' % (what, lo))
        self.pats = painted_diamond(lambda a: ram[a - 0x4000], self.cmap)
        self.display = display_banks(lambda a: ram[a - 0x4000], self.cmap)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        bank11 = bytearray(16384)
        bank11[0:128] = self.pats
        self.extra_banks = {11: bytes(bank11), 12: self.page + bytes(8192), **self.display}


# ---------------------------------------------------------------------------------------------
# Next-side state (sprite attributes, pattern memory, sprite palette) and the machines
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, pats=b''):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat[PAT_DIA * 128:PAT_DIA * 128 + len(pats)] = pats
        self.pal = {}
        self.pal_idx = 0
        self.sel = 0
        self.ptr = 0
        self.events = []
        self.lastf_uploads = 0

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x40:
            self.pal_idx = val
        elif reg == 0x41:
            if self.nr.get(0x43, 0) & 0x70 == 0x20:
                self.pal[self.pal_idx] = val
            self.pal_idx = (self.pal_idx + 1) & 255
        self.events.append(('nr', reg, val))

    def out(self, port, val):
        if port == 0x303B:
            self.ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.ptr] = val
            self.ptr = (self.ptr + 1) & 0x3FFF
        self.events.append(('out', port, val))

    def pixels(self, i):
        return sprite_pixels(self.attr[i], self.pat)

    def copy(self):
        n = NextState()
        n.nr = dict(self.nr)
        n.attr = [list(a) for a in self.attr]
        n.pat = bytearray(self.pat)
        n.pal = dict(self.pal)
        n.pal_idx, n.sel, n.ptr = self.pal_idx, self.sel, self.ptr
        return n


def _machine(Sim, mem, regs, ns, slot='o', nextn=True):
    from . import z80n
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)
    if nextn:
        z80n.install(sim, ns.nextreg)

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=400000, check=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        if check:
            check(R)
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    if check:
        check(R)
    return True


HOOK_HI = 0x3D00
STACK_BUDGET = 48               # bytes the hooks may use below the SP they were entered with


class IntSafe:
    """Interrupt safety of hooks that run with interrupts ON (BRIEFING A1: an interrupt may arrive after
    any instruction and its handler reads IX / IY / I and pushes on the stack): while the PC is in the
    hook, IY, I and the interrupt flags never change, IX only by the replayed POP IX, SP stays within
    STACK_BUDGET of its entry value, and every store goes to the stack or the flag span."""

    def __init__(self, mem):
        self.mem = mem
        self.ent = None
        self.bad = []
        self.prev = None
        self.hook_stores = 0

    def __call__(self, R):
        pc = R[24]
        inh = ROM_ORG <= pc < HOOK_HI
        if self.ent is not None:
            sp, ixh, ixl, iyh, iyl, i, f1, f2 = self.ent
            pp = self.prev
            popix = pp is not None and self.mem[pp] == 0xDD and self.mem[pp + 1] == 0xE1
            if (R[10], R[11], R[14], R[26], R[27]) != (iyh, iyl, i, f1, f2):
                self.bad.append(('IY / I / IFF changed inside a hook', pp))
            if (R[8], R[9]) != (ixh, ixl):
                if popix:               # the replayed POP IX (plotter end): IX is the game's own again
                    self.ent = (sp, R[8], R[9], iyh, iyl, i, f1, f2)
                else:
                    self.bad.append(('IX changed inside a hook', pp))
            if R[12] < sp - STACK_BUDGET:
                self.bad.append(('hook stack use', sp - R[12]))
        if inh and self.ent is None:
            self.ent = (R[12], R[8], R[9], R[10], R[11], R[14], R[26], R[27])
        elif not inh:
            self.ent = None
        self.prev = pc if inh else None


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


class World:
    """Persistent state of the patched world next to the live original: hook RAM (HS span), the
    Next hardware, the figures' pixel bytes the original has on the screen that the patched one
    does not (F, XOR plotter deltas), the model of what is drawn."""

    def __init__(self, pats):
        self.hs = bytearray(32)
        self.ns = NextState(pats)
        self.ns.nr[0x43] = 0x20                 # setup: sprite palette selected
        self.ns.pal = dict(enumerate(PALETTE))
        self.F = {}
        self.drawn = {}                 # slot -> (x, y, frame) the original has drawn
        self.dia = {}                   # index -> set of pixels the original drew (room table entry)
        self.touch = collections.Counter()
        self.pending = []               # plots entered but not yet at their end (an interrupt can nest them)


class _OriginalOverlay:
    """Stable memory type: simpool caches types, so per-event classes leak replay states."""
    def __init__(self, get, alt, psite, world):
        self.get, self.alt, self.psite, self.world = get, alt, psite, world
        self.ov = {}

    def __getitem__(self, a):
        v = self.ov.get(a)
        return self.get(a) if v is None else v

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.ov[a] = v

    def __len__(self):
        return 65536


class _PatchedOverlay(_OriginalOverlay):
    def __getitem__(self, a):
        world = self.world
        if 0xC000 <= a < 0xE000 and world.ns.nr.get(0x56, 0) >= TABLE_FIRST_PAGE:
            page = world.ns.nr[0x56]
            bank = world.display[page // 2]
            return bank[(page % 2)*8192 + a-0xC000]
        if a < 0x4000:
            return self.alt[a]
        v = self.psite.get(a)
        if v is not None:
            return v
        v = self.ov.get(a)
        if v is not None:
            return v
        if HS <= a < HS + 32:
            return world.hs[a - HS]
        if a < 0x5800:
            return self.get(a) ^ world.F.get(a, 0)
        return self.get(a)

    def __setitem__(self, a, v):
        if a < 0x4000:
            self.romw = getattr(self, 'romw', 0) + 1
        else:
            self.ov[a] = v


def _overlays(get, alt, psite, world):
    return (lambda: _OriginalOverlay(get, alt, psite, world),
            lambda: _PatchedOverlay(get, alt, psite, world))


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def _pix_of(ov, lo=0x4000, hi=0x5800):
    out = set()
    for a, v in ov.items():
        if lo <= a < hi:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                if (v >> (7 - k)) & 1:
                    out.add(((a & 31) * 8 + k, y))
    return out


def _model_screen(rows, x, y):
    """{address: byte} of an image's pixels as the plotter would XOR them (no wrap)."""
    out = {}
    for px, py in image_pixels(rows, x, y):
        if 0 <= px < 256 and 0 <= py < 192:
            a = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | px >> 3
            out[a] = out.get(a, 0) | 0x80 >> (px & 7)
    return out


def _slot_state(get, s):
    b = SLOTS + 8 * s
    return get(b), get(b + 1), get(b + 2)


def _diamond_entries(get):
    room = get(ROOM)
    p = get(OBJTAB + 2 * room) | get(OBJTAB + 2 * room + 1) << 8
    return [(get(p + 3 * i), get(p + 3 * i + 1), get(p + 3 * i + 2)) for i in range(5)]


def _dia_model(entry):
    """Pixels of one collectable (8 x 7 at x & 0xF8, y + 2) from the game's rows, set in `sprite`."""
    return entry


def expected_colours(get, frame, x, y, ink, cmap):
    addr = gfx_addr(get(GFXPTR) | get(GFXPTR+1)<<8, frame)
    pixels = {}
    for row in range(24):
        for half in range(2):
            a = addr + row*2 + half
            value = get(a)
            for bit in range(8):
                col = pixel_colour(cmap, 'G%04X_I%02d' % (a, ink), value, bit, ink)
                px, py = x+half*8+bit, y+row
                if col and 0 <= px < 256 and 0 <= py < 192:
                    pixels[px,py] = col
    return pixels


def sprite_colours(ns, index):
    a0,a1,a2,a3,a4 = ns.attr[index]
    if not a3 & 128:
        return {}
    x=a0+(a2&1)*256-32; y=a1+(a4&1)*256-32
    base=(a3&63)*256+(128 if a4&64 else 0)
    out={}
    for row in range(16):
        for col in range(16):
            b=ns.pat[base+row*8+col//2]
            ink=(b>>4) if col%2==0 else (b&15)
            if ink and 0<=x+col<256 and 0<=y+row<192:
                out[x+col,y+row]=ink
    return out


def expected_sprites(world, get):
    """-> {sprite index: set of pixels} the patched world must show (clipped to the screen)."""
    exp = {}
    for s, (i0, i1) in SPR_SLOT.items():
        cancelled = world.drawn.get(1) == world.drawn.get(2) and 1 in world.drawn and 2 in world.drawn
        if s in world.drawn and not (s in (1, 2) and cancelled):
            x, y, fr = world.drawn[s]
            exp[i0] = exp[i1] = clip(image_pixels(frame_rows(get, fr), x, y))
    return exp


def event(patch, kind, site, get, R, world, alt, Sim, extra=None):
    """One hook event from a live state. Returns a failure list. kinds: pl dia c rd isr."""
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    O, P = _overlays(get, alt, psite, world)
    f = []
    ns = world.ns
    world.display = patch.display
    before = ns.copy()
    ns.events = []
    sp0 = R[12]
    w = lambda a: get(a) | get(a + 1) << 8
    if kind == 'ep':
        # the live plot reaches its end: the screen delta, the drawn tuple and the flags take effect
        if not world.pending:
            return ['plot end without a plot']
        slot, d, post, hsw = world.pending.pop()
        world.drawn[slot] = post
        for a, v in hsw.items():
            world.hs[a - HS] = v
        return f
    if kind == 'isr':
        # the live original is at 49804 (the tick has run): EXX / POP HL / POP DE; the patched one
        # runs e_isr (sprite update) and replays them, then both are at 49807.
        if R[26]:
            world.touch['sprite update entered with interrupts enabled'] += 1
        if 0xC000 <= sp0 < 0xE000:
            return ['sprite update stack in mapped slot 6']
        o, p = O(), P()
        so = _machine(Sim, o, list(R), NextState(), 'o', nextn=False)
        sp_ = _machine(Sim, p, list(R), ns, 'p')
        stop = lambda r: r[24] == ISR_SITE + 3
        def irq_mapping_check(regs):
            if ns.nr.get(0x56, 0) != 0 and regs[26]:
                f.append(('MMU6 mapped with interrupts enabled',))
        if not (_run(so, stop) and _run(sp_, stop, check=irq_mapping_check)):
            return ['isr hook did not return']
        ro, rp = so.registers, sp_.registers
        world.touch['T original, kind isr'] += ro[25] - R[25]
        world.touch['T patched, kind isr'] += rp[25] - R[25]
        world.touch['T patched, isr, worst'] = max(world.touch['T patched, isr, worst'], rp[25] - R[25])
        diff = [i for i in CMP if ro[i] != rp[i]]
        if diff:
            f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
        if getattr(p, 'romw', 0):
            f.append(('patched code wrote ROM',))
        spend = rp[12]
        bad = [a for a in p.ov if not (HS <= a < HS + 32) and not spend - STACK_DEAD <= a < spend]
        if bad:
            f.append(('hook wrote outside its state', sorted(bad)[:4]))
        extra_ev = [e for e in ns.events if e[0] == 'in' or (e[0] == 'out' and e[1] != 0x303B and e[1] & 0xFF != 0x5B)]
        if extra_ev:
            f.append(('unexpected port access', extra_ev[:3]))
        for e in ns.events:
            if e[0] == 'nr' and e[1] not in (0x07, 0x56, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x40, 0x41, 0x43):
                f.append(('NEXTREG other than sprite / palette', e[1]))
                break
        for a in p.ov:
            if HS <= a < HS + 32:
                world.hs[a - HS] = p.ov[a]
        # sprite pixels against the model
        exp = expected_sprites(world, get)
        for s, (i0, i1) in SPR_SLOT.items():
            got = clip(ns.pixels(i0) | ns.pixels(i1))
            want = exp.get(i0, set())
            if i0 in exp:
                x_, y_, fr_ = world.drawn[s]
                ink_ = ink_index(get(SLOTS + 8*s + 6))
                colours = expected_colours(get, fr_, x_, y_, ink_, patch.cmap)
                actual = {**sprite_colours(ns,i0), **sprite_colours(ns,i1)}
                want = set(colours)
                if actual != colours:
                    f.append(('sprite per-pixel colours differ', s, len(set(actual.items()) ^ set(colours.items()))))
            if s in world.drawn and world.drawn[s][0] > 240:
                world.touch['slot x > 240 (ULA wraps, sprite clips)'] += 1
                continue
            if got != want:
                f.append(('slot %d sprite pixels differ from the original plot' % s, len(got ^ want), world.drawn.get(s), _slot_state(get, s), sorted(got - want)[:6], sorted(want - got)[:6], [ns.attr[i0], ns.attr[i1]], [get(a) for a in range(48374, 48400)], bytes(world.hs)[:12].hex()))
            world.touch['slot pixels compared'] += len(want)
        if ns.pal != dict(enumerate(PALETTE)):
            f.append(('fixed sprite palette changed',))
        if ns.nr.get(0x56, 0) != 0 or ns.nr.get(0x07, 0) != 0:
            f.append(('MMU6 / CPU speed not restored',))
        ent = _diamond_entries(get)
        for i in range(5):
            got = clip(ns.pixels(SPR_DIA + i))
            shown = world.hs[3 + i] and ent[i][0] != 0
            if shown:
                idv, x, y = ent[i]
                want = clip({(x & 0xF8) + c, y + 2 + r} for r, v in enumerate(diamond_rows(get))
                            for c in range(8) if v >> (7 - c) & 1) if False else set()
                want = {((x & 0xF8) + c, y + 2 + r) for r, v in enumerate(diamond_rows(get))
                        for c in range(8) if v >> (7 - c) & 1}
                want = clip(want)
                # the original must really have it on the screen: bytes of the 7 rows
                ok = True
                for r, v in enumerate(diamond_rows(get)):
                    py = y + 2 + r
                    if 0 <= py < 192 and x & 0xF8 < 256:
                        a = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | (x >> 3)
                        original_expected = v
                        for sx,sy,sf in world.drawn.values():
                            original_expected ^= _model_screen(frame_rows(get,sf),sx,sy).get(a,0)
                        if get(a) != original_expected:
                            ok = False
                if not ok:
                    world.touch['diamond original-screen consistency mismatch'] += 1
                    world.touch['  e.g. frame-less sample: entry %s' % (ent[i],)] += 0
                world.touch['diamond pixels compared'] += len(want)
                if got != want:
                    f.append(('diamond %d sprite pixels differ' % i, len(got ^ want)))
            elif got:
                f.append(('diamond %d sprite visible but not drawn / id 0' % i, len(got)))
        vis = [i for i in range(128) if ns.attr[i][3] & 0x80]
        okset = set(range(5)) | {j for pair in SPR_SLOT.values() for j in pair}
        if set(vis) - okset:
            f.append(('unexpected sprites visible', sorted(set(vis) - okset)[:4]))
        return f
    # --- events that run the original and the patched code from the same state
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(), 'o', nextn=False)
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if kind == 'pl':
        slot = R[0]
        ret = w(sp0)

        def stop(r):
            return r[24] == ret and r[12] == sp0 + 2
        stop_o = stop_p = stop
        b = SLOTS + 8 * slot
        pre = [get(b + k) for k in range(8)]
        newf = get(48374)
    elif kind == 'dia':
        nxt = site + 3

        def stop(r):
            return r[24] == nxt and r[12] == sp0
        stop_o = stop_p = stop
        slot = None
    elif kind == 'c':
        nxt = site + 3
        stop_o = stop_p = lambda r: r[24] == nxt or (r[24] in (50346, 50612))
        slot = None
    else:               # 'rd'
        size = len(patch_rd_old(site))
        r0 = list(R)
        lo, hi = site, site + size
        n_ = 0
        while True:
            so.opcodes[o[so.registers[24]]]()
            n_ += 1
            if not lo <= so.registers[24] < hi:
                break
        tgt, tsp = so.registers[24], so.registers[12]
        ro = so.registers
        isf = IntSafe(p)
        if not _run(sp_, lambda r: r[24] == tgt and r[12] == tsp, check=isf):
            return ['rd hook did not return']
        for b_ in isf.bad[:2]:
            f.append(b_)
        world.touch['hook instructions checked for interrupt safety'] += 1
        rp = sp_.registers
        world.touch['T original, kind rd'] += ro[25] - R[25]
        world.touch['T patched, kind rd'] += rp[25] - R[25]
        diff = [i for i in CMP if ro[i] != rp[i]]
        if diff:
            f.append(('rd registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
        if getattr(p, 'romw', 0):
            f.append(('patched code wrote ROM',))
        bad = [a for a in p.ov if not sp0 - STACK_DEAD <= a < sp0]
        if bad:
            f.append(('rd hook wrote memory', sorted(bad)[:4]))
        return f
    isf = IntSafe(p)
    if not (_run(so, stop_o) and _run(sp_, stop_p, check=isf)):
        return ['did not return']
    for b_ in isf.bad[:2]:
        f.append(b_)
    world.touch['hook instructions checked for interrupt safety'] += 1
    ro, rp = so.registers, sp_.registers
    world.touch['T original, kind ' + kind] += ro[25] - R[25]
    world.touch['T patched, kind ' + kind] += rp[25] - R[25]
    diff = [i for i in CMP if ro[i] != rp[i]]
    if kind == 'pl' and diff and set(diff) <= {1, 16, 17}:
        # F and AF' at the end of the plotter are leftovers of its working registers (CP L at 48195,
        # the EX AF,AF' loop), computed from the screen bytes it read - the patched build reads them
        # without the figure. Dead: convergence() scrambles both in the live game.
        world.touch["plot ends with a different F / AF' (screen-derived leftover, see convergence)"] += 1
        diff = []
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access in a plot / clear hook',))
    if any(e[0] == 'nr' for e in ns.events):
        f.append(('NEXTREG in a plot / clear hook',))
    spend = ro[12]
    dead = range(spend - STACK_DEAD, spend)
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not 0x4000 <= a < 0x5800 and not HS <= a < HS + 32 and a not in dead
          and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    # the patched code must not write the screen or the attributes
    if any(0x4000 <= a < 0x5800 for a in p.ov):
        f.append(('patched code wrote the bitmap',))
    hsw = {a for a in p.ov if HS <= a < HS + 32}
    if kind == 'pl':
        # original screen delta vs the model: old image ^ new image
        d = {a: o.ov[a] ^ get(a) for a in o.ov if 0x4000 <= a < 0x5800}
        d = {a: v for a, v in d.items() if v}
        ox, oy, ofr = pre[0], pre[1], pre[2]
        nx, ny = (ox + pre[4]) & 255, (oy + pre[5]) & 255
        small = abs((nx & 248) - (ox & 248)) <= 8 and ox <= 240 and nx <= 240
        want = collections.Counter()
        for a, v in _model_screen(frame_rows(get, ofr), ox, oy).items():
            want[a] ^= v
        for a, v in _model_screen(frame_rows(get, newf), nx, ny).items():
            want[a] ^= v
        want = {a: v for a, v in want.items() if v}
        d = {a: o.ov[a] ^ get(a) for a in o.ov if 0x4000 <= a < 0x5800}
        d = {a: v for a, v in d.items() if v}
        if os.environ.get('FM_DIST'):
            world.touch['DIST slot %d dy %s dx %s oldblank %s ox>200 %s ok %s' % (
                slot, 'nz' if pre[5] else 0, 'nz' if pre[4] else 0, not any(frame_rows(get, ofr)), ox > 200, d == want)] += 1
        if small and d != want:
            f.append(('plot delta differs from the model (old ^ new image)', len(set(d) ^ set(want)) + 1))
        if not small:
            world.touch['plot with a move beyond one cell or x > 240 (model not compared)'] += 1
        post = _slot_state(lambda a: o[a], slot)
        if post != (nx, ny, newf):
            f.append(('slot state after the plot is not the drawn tuple', post, (nx, ny, newf)))
        if p.ov.get(HS + slot) != 1:
            f.append(('slot flag not set by the plot',))
        world.pending.append((slot, d, post, {a: p.ov[a] for a in hsw}))
        world.touch['plots'] += 1
    elif kind == 'dia':
        stack_b = get(sp0 + 3)           # B of the outer BC (entries left): SP -> HL, BC
        idx = 5 - stack_b
        pix = _pix_of(o.ov)
        if 0 <= idx < 5:
            world.dia[idx] = pix
            if p.ov.get(HS + 3 + idx) != 1:
                f.append(('diamond flag not set', idx))
        else:
            f.append(('diamond index out of range', idx))
    elif kind == 'c':
        for a in o.ov:
            if 0x4000 <= a < 0x5800 and o.ov[a] == 0:
                world.F.pop(a, None)
        world.drawn.clear()
        world.dia.clear()
        for i in range(8):
            if p.ov.get(HS + i, 1) != 0:
                f.append(('flags not cleared by a screen clear', i))
                break
    if kind != 'pl':
        for a in hsw:
            world.hs[a - HS] = p.ov[a]
    return f


def patch_rd_old(site):
    return bytes.fromhex(RD_SITES[site][1])


# ---------------------------------------------------------------------------------------------
# The live replay
# ---------------------------------------------------------------------------------------------

KEEP = bool(os.environ.get('FM_KEEP'))
_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def preview_pair(get,world,frame):
    from PIL import Image,ImageDraw
    from .preview import _screen_img
    from .coloursheet import palette_rgb
    raw=bytes(get(a) for a in range(0x4000,0x5B00))
    clean=bytearray(raw)
    for a,v in world.F.items():
        if 0x4000<=a<0x5800:
            clean[a-0x4000]^=v
    left=_screen_img(raw,{})
    right=_screen_img(clean,{})
    rgb=palette_rgb(PALETTE)
    for i in range(128):
        for xy,ink in sprite_colours(world.ns,i).items():
            right.putpixel(xy,rgb[ink])
    canvas=Image.new('RGB',(520,214),(24,24,24))
    ImageDraw.Draw(canvas).text((4,3),'Frame %d: original / verified sprite model' % frame,fill='white')
    canvas.paste(left,(0,20)); canvas.paste(right,(264,20))
    return canvas


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX (original game); at every hook site run original and patched code from the
    same state and compare. Returns (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False}
    world = World(patch.pats)
    cnt = collections.Counter()
    EVENT = {PLOTTER: ('pl', None), PLOT_END: ('ep', None), 50343: ('c', 50343), 50609: ('c', 50609), DIA_SITE: ('dia', DIA_SITE),
             ISR_SITE: ('isr', ISR_SITE)}
    for a in RD_SITES:
        EVENT[a] = ('rd', a)
    WATCH = set(EVENT) | set(site_bytes) | {ISR_SITE}
    states = []
    preview_frames = {500,1500,2500,3500,8000,16000,24000,32000}
    previews = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        regs = None

        def __getitem__(s, a):
            value = G(s,a)
            if type(a) is int and st['on'] and a in world.F and s.regs is not None:
                pc=s.regs[24]
                if pc not in RD_SITES and not PLOTTER <= pc <= PLOT_END:
                    fail('unhandled read of removed pixels', (pc,a))
            return value

        def __setitem__(s, a, v):
            if st['on'] and type(a) is int:
                if a in site_bytes:
                    fail('game wrote a patch site', (a,))
                elif 0x4000 <= a < 0x5800 and s.regs[24] in PLOT_WRITERS | {60683}:
                    clean = G(s,a) ^ world.F.get(a,0)
                    world.F[a] = v ^ clean
                    if not world.F[a]:
                        del world.F[a]
                    world.touch['removed bitmap stores tracked at write time'] += 1
                elif a in world.F and a < 0x5800:
                    # any other writer (clear, redraw, scroller) replaces the byte in both worlds
                    del world.F[a]
                    world.touch['figure bytes overwritten by other writers'] += 1
            S(s, a, v)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            self.memory.regs = self.registers
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)

            def mk(fn):
                def g():
                    pc = R[24]
                    if pc == 49740:
                        st['t0'] = R[25]
                    elif pc == ISR_SITE and 't0' in st:
                        d = R[25] - st['t0']
                        world.touch['ISR entry to hook site, T total'] += d
                        world.touch['ISR entry to hook site, T max'] = max(world.touch['ISR entry to hook site, T max'], d)
                    if pc in WATCH:
                        cnt[pc] += 1
                        ev = EVENT.get(pc)
                        if ev:
                            kind, site = ev
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((kind, site, list(R), bytes(G(mem, a) for a in range(65536)),
                                               world.ns.copy(), bytes(world.hs), dict(world.F), dict(world.drawn)))
                            keep = (list(R), bytes(G(mem, a) for a in range(65536)), world.ns.copy(),
                                    bytes(world.hs), dict(world.F), dict(world.drawn), list(world.pending),
                                    dict(world.dia)) if KEEP else None
                            fl = event(patch, kind, site if site is not None else pc, get, R, world, alt, _rw())
                            if fl and KEEP and not os.path.exists('/tmp/fm/fail_%s.pkl' % kind):
                                import pickle
                                pickle.dump((kind, site, st['frame'], keep, fl), open('/tmp/fm/fail_%s.pkl' % kind, 'wb'))
                            c[kind] += 1
                            if kind == 'isr' and st['frame'] in preview_frames and os.environ.get('NEXCLASH_FIREMAN_PREVIEW'):
                                preview_frames.remove(st['frame'])
                                previews.append(preview_pair(get,world,st['frame']))
                            for k in fl:
                                fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k),
                                     k[1:] if isinstance(k, tuple) else ())
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if progress and st['frame'] % 1000 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = Sm
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    # no jump into the middle of a patched instruction: interior bytes run only after their site
    for a, old_, new in patch.sites:
        for k in range(1, len(old_)):
            if cnt[a + k] > cnt[a]:
                c['jump into a patched instruction (%d)!' % (a + k)] += 1
    for k, v in world.touch.items():
        c[k] += v
    c['frames'] = st['frame']
    if previews:
        from PIL import Image
        contact=Image.new('RGB',(previews[0].width,sum(im.height for im in previews)),(24,24,24))
        y=0
        for im in previews:
            contact.paste(im,(0,y)); y+=im.height
        contact.save(os.environ['NEXCLASH_FIREMAN_PREVIEW'])
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests (states from verify(collect=n)), negative controls
# ---------------------------------------------------------------------------------------------

def _isr_case(patch, base, alt, Sim, slots, dias=(), lastf=None, twice=True):
    """slots {s: (x, y, frame, E)}, dias [(i, id, x, y, shown)]. Runs the interrupt hook twice (the
    second time with the pattern cache hot). Returns (failures, pixels compared)."""
    kind, site, R, mem, ns, hs, Fd, dr = base
    m = bytearray(mem)
    world = World(patch.pats)
    world.ns = ns.copy()
    world.hs = bytearray(32)
    for s, (x, y, fr, e) in slots.items():
        b = SLOTS + 8 * s
        m[b], m[b + 1], m[b + 2], m[b + 6] = x, y, fr, e
        world.drawn[s] = (x, y, fr)
        world.hs[s] = 1
        world.hs[8 + s] = 0xFF if lastf is None else lastf
    m[ROOM] = 3                                     # a room whose table is a scratch span (the base state may be a menu)
    p = 0xF500
    m[OBJTAB + 6], m[OBJTAB + 7] = p & 255, p >> 8
    for k in range(15):
        m[p + k] = 0
    for i, idv, x, y, shown in dias:
        m[p + 3 * i], m[p + 3 * i + 1], m[p + 3 * i + 2] = idv, x, y
        world.hs[3 + i] = 1 if shown else 0
        # the original has it on the screen (7 overwritten rows)
        for r, v in enumerate(diamond_rows(m.__getitem__)):
            py = y + 2 + r
            if 0 <= py < 192 and (x >> 3) < 32:
                m[0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | x >> 3] = v
    fl = []
    n = 0
    for _ in range(2 if twice else 1):
        before = len(world.touch)
        fl += event(patch, 'isr', ISR_SITE, m.__getitem__, list(R), world, alt, Sim)
        n += world.touch['slot pixels compared'] + world.touch['diamond pixels compared']
    return fl, n


def _rd_case(patch, base, alt, Sim, site, de, slots, rnd):
    """Virtual read at one rd site: the original reads scenery ^ figures, the patched code scenery."""
    kind, site0, R, mem, ns, hs, Fd, dr = base
    m = bytearray(mem)
    for a in range(0x4000, 0x5800):
        m[a] = rnd.randrange(256)
    world = World(patch.pats)
    world.hs = bytearray(32)
    for s, (x, y, fr) in slots.items():
        b = SLOTS + 8 * s
        m[b], m[b + 1], m[b + 2] = x, y, fr
        world.drawn[s] = (x, y, fr)
        world.hs[s] = 1
        for a, v in _model_screen(frame_rows(m.__getitem__, fr), x, y).items():
            world.F[a] = world.F.get(a, 0) ^ v
            m[a] ^= v                               # the live (original) screen has the figure
    r = list(R)
    r[24] = site
    r[4], r[5] = de >> 8, de & 255
    sp = 0xB000
    r[12] = sp
    m[sp], m[sp + 1] = 0x00, 0x90
    return event(patch, 'rd', site, m.__getitem__, r, world, alt, Sim)


def _rd_diamond_case(patch, base, site, index, row):
    kind,site0,R,mem,ns,hs,F,drawn=base
    m=bytearray(mem); w=World(patch.pats)
    m[ROOM]=3; table=0xF500
    m[OBJTAB+6],m[OBJTAB+7]=table&255,table>>8
    m[table:table+15]=bytes(15)
    m[table+3*index:table+3*index+3]=bytes((1,80,80))
    w.hs[3+index]=1
    y=82+row; a=0x4000 | (y&0xC0)<<5 | (y&7)<<8 | (y&0x38)<<2 | 10
    value=m[DIA_GFX+6-row]
    m[a]=value; w.F[a]=value^0xA5
    r=list(R);r[24]=site;r[4],r[5]=a>>8,a&255;r[12]=0xB000
    m[0xB000:0xB002]=bytes((0,0x90))
    return event(patch,'rd',site,m.__getitem__,r,w,_alt(patch),_rw())


def unit_tests(patch, states, neg=None):
    import random
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    rnd = random.Random(1)
    isr = [s for s in states if s[0] == 'isr']
    if not isr:
        c['no ISR state for unit tests!'] += 1
        return c
    base = isr[len(isr) // 2]
    # 1. every frame x edge positions x slots, palette from E
    nfr = 256
    for s in range(1):
        for fr in range(nfr):
            for (x, y) in ((0, 0), (7, 100), (8, 167), (100, 168), (200, 191), (232, 20), (240, 80)):
                e = rnd.choice((0, 1, 2, 3, 4, 5, 6, 7, 0x40, 0x45, 0x47, 0x43))
                fl, n = _isr_case(patch, base, alt, Sim, {s: (x, y, fr, e)})
                c['all-frame edge cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                if fl and c['  fail example'] < 3:
                    c['  fail example'] += 1
                    c['  slot %d frame %d x %d y %d: %s' % (s, fr, x, y, str(fl[:1])[:200])] += 1
    # 2. all three slots at once, overlapping, flag combinations; hidden slots (flag 0) show nothing
    for k in range(60):
        slots = {s: (rnd.randrange(0, 241), rnd.randrange(0, 192), rnd.randrange(nfr), rnd.randrange(8))
                 for s in range(3) if rnd.random() < 0.7}
        fl, n = _isr_case(patch, base, alt, Sim, slots)
        c['multi-slot cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    fl, n = _isr_case(patch, base, alt, Sim, {})
    c['no slot shown cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    # 3. collectables: ids, positions, flags (shown, id 0, flag off)
    for k in range(80):
        dias = [(i, rnd.choice((0, 1, 5, 31)), rnd.randrange(0, 249), rnd.randrange(0, 185), rnd.random() < 0.7)
                for i in range(5)]
        fl, n = _isr_case(patch, base, alt, Sim, {}, dias)
        c['collectable cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    # 4. virtual read at every site over the cells around the figures
    rdb = [s for s in states if s[0] == 'rd'] or isr
    base_rd = rdb[0]
    sites = sorted(RD_SITES)
    for k in range(400):
        slots = {s: (rnd.randrange(0, 241), rnd.randrange(0, 150), rnd.randrange(nfr)) for s in range(3)
                 if rnd.random() < 0.8}
        site = sites[k % len(sites)]
        if slots:
            s0 = rnd.choice(list(slots))
            x, y, _ = slots[s0]
        else:
            x, y = rnd.randrange(0, 240), rnd.randrange(0, 150)
        px, py = x + rnd.randrange(-8, 24), y + rnd.randrange(-2, 26)
        px, py = max(0, min(255, px)), max(0, min(191, py))
        de = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | px >> 3
        fl = _rd_case(patch, base_rd, alt, Sim, site, de, slots, rnd)
        c['virtual read cases %s' % ('ok' if not fl else 'FAIL!')] += 1
        if fl and c['  rd fail example'] < 3:
            c['  rd fail example'] += 1
            c['  site %d de %04X slots %s: %s' % (site, de, slots, str(fl[:1])[:200])] += 1
    for index in range(5):
        for row in range(7):
            for site in RD_SITES:
                fl=_rd_diamond_case(patch,base_rd,site,index,row)
                c['collectable virtual read %s' % ('ok' if not fl else 'FAIL!')] += 1
    # Cache colour changes and exact cancellation of the two XOR enemies.
    for ink in (0,1,7,0x43,0x47):
        fl,_ = _isr_case(patch,base,alt,Sim,{1:(80,80,5,ink),2:(80,80,5,ink)})
        c['identical enemy cancellation %s' % ('ok' if not fl else 'FAIL!')] += 1
    # Every ink and source frame participates in coloured read-back through the real upload hook.
    import copy
    from .z80tonex import Z80Snapshot
    # Use the captured original memory and the broken patch's own display tables.
    q = copy.copy(patch)
    q.cmap = {}
    peek = base[3].__getitem__
    for ink in range(1,16):
        for off in range(48):
            a = gfx_addr(GRAPHICS_BASE, 5) + off
            q.cmap['G%04X_I%02d' % (a,ink)] = [peek(a), 'G', [1+(b+ink)%15 for b in range(8)]]
    q.display = display_banks(peek,q.cmap)
    for ink in range(1,16):
        attr = (ink&7) | (0x40 if ink>=8 else 0)
        fl,_ = _isr_case(q,base,_alt(q),Sim,{0:(100,80,5,attr)})
        c['synthetic per-pixel paint %s' % ('ok' if not fl else 'FAIL!')] += 1
    q2=copy.copy(q); q2.display=patch.display
    fl,_ = _isr_case(q2,base,_alt(q2),Sim,{0:(100,80,5,7)})
    c['negative control omitted paint: %s' % ('detected' if fl else 'NOT DETECTED!')] += 1
    for iff in (0, 1):
        base = list(isr[0])
        base[2] = list(base[2])
        base[2][26] = iff
        fl, _ = _isr_case(patch, tuple(base), alt, Sim, {0: (80, 80, 7, 2)})
        c['ISR entry IFF %d %s' % (iff, 'ok' if not fl else 'FAIL!')] += 1
    fl = setup_test(patch, isr[0][3])
    c['setup routine %s' % ('ok' if not fl else 'FAIL!')] += 1
    if fl:
        c['  setup: %s' % (fl,)] += 1
    # 5. negative controls: each broken patch must FAIL the same checks
    if neg:
        for name, bp, run in neg:
            bad = 0
            tot = 0
            for k in range(30):
                tot += 1
                bad += 1 if run(bp, k) else 0
            c['negative control %s: %s' % (name, 'detected' if bad else 'NOT DETECTED!')] += 1
    return c


def setup_test(patch, mem64):
    """Run the start-up routine (0xD000) with bank 11 behind NextReg $57 = 22: the diamond pattern lands in
    pattern 6, patterns 0-5 are cleared, the fixed palette is loaded, every sprite is hidden, sprites are on,
    $57 is back to 21 and nothing else is touched."""
    f = []
    ns = NextState()
    ns.pat[:] = bytes([0x77]) * 16384                   # garbage the routine must overwrite
    bank = bytearray(16384)
    bank[0:128] = patch.extra_banks[11][0:128] if patch.extra_banks else patch.pats
    base = bytearray(mem64)
    base[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra

    class M(list):
        def __getitem__(s, a):
            if type(a) is int and a >= 0xE000 and ns.nr.get(0x57) == 22 and a < 0x10000:
                return bank[a - 0xE000]
            return list.__getitem__(s, a)

        def __setitem__(s, a, v):
            if type(a) is int and a >= 0x4000:
                list.__setitem__(s, a, v)
    mem = M(base)
    regs = [0] * 28
    regs[12] = 0xB800
    regs[24] = 0xD000
    mem[0xB800], mem[0xB801] = 0xFE, 0xFF
    sim = _machine(_rw(), mem, regs, ns, 'o')
    if not _run(sim, lambda r: r[24] == 0xFFFE and r[12] == 0xB802, 100000):
        return ['setup did not return']
    if bytes(ns.pat[PAT_DIA * 128:PAT_DIA * 128 + 128]) != patch.pats:
        f.append('diamond pattern not uploaded')
    if any(ns.pat[:PAT_DIA * 128]):
        f.append('patterns 0-5 not cleared')
    if bytes(ns.pat[(PAT_DIA + 1) * 128:]) != bytes([0x77]) * (16384 - (PAT_DIA + 1) * 128):
        f.append('setup wrote beyond pattern 6')
    if ns.pal != dict(enumerate(PALETTE)):
        f.append('diamond colour')
    if ns.nr.get(0x4B) != 0 or ns.nr.get(0x15) != 1 or ns.nr.get(0x57) != 21:
        f.append(('transparency / sprites on / MMU7', ns.nr.get(0x4B), ns.nr.get(0x15), ns.nr.get(0x57)))
    if any(a[3] & 0x80 for a in ns.attr):
        f.append('a sprite is visible after setup')
    other = [e for e in ns.events if e[0] == 'nr' and e[1] not in (0x57, 0x43, 0x40, 0x41, 0x4B, 0x34, 0x38, 0x15)]
    if other:
        f.append(('other NextRegs', other[:2]))
    return f


def negative_patches(patch, states):
    """[(name, broken patch, run(patch, k) -> failure list)]. Each uses the broken patch's own bytes."""
    import copy
    out = []
    alt_good = _alt(patch)
    Sim = _rw()
    isr = [s for s in states if s[0] == 'isr']
    rdb = [s for s in states if s[0] == 'rd']
    if not isr:
        return out
    base = isr[len(isr) // 2]
    # (a) pixel conversion table with one wrong entry
    q = copy.copy(patch)
    q.display = dict(patch.display)
    q.display[26] = bytes([0x11]) * 16384
    q.display[27] = bytes([0x11]) * 16384

    def run_a(bp, k):
        fr = 3 + k
        fl, _ = _isr_case(bp, base, _alt(bp), Sim, {0: (100, 80, fr, 7)})
        return fl
    out.append(('wrong display colours', q, run_a))
    # (b) no virtual read: the rd sites are not patched
    q2 = copy.copy(patch)
    q2.sites = [t for t in patch.sites if t[0] not in RD_SITES]
    if rdb:
        import random
        rr = random.Random(7)

        def run_b(bp, k):
            slots = {0: (100, 60, 3 + k)}
            x, y, _ = slots[0]
            px, py = x + 2 + k % 6, y + 4 + k % 12
            de = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | px >> 3
            return _rd_case(bp, rdb[0], _alt(bp), Sim, 51159, de, slots, rr)
        out.append(('no virtual read', q2, run_b))
    bp = copy.copy(patch)
    pg = bytearray(patch.page)
    start = patch.syms['e_c1'] - 0x2000
    pg[start:start+3] = b'\xfd\x23\x00'  # INC IY / NOP replaces CALL hid
    bp.page = bytes(pg)
    clear_states = [s for s in states if s[0] == 'c']
    if clear_states:
        def run_irq(broken, k):
            kind, site, R, mem, ns, hs, F, drawn = clear_states[0]
            w = World(broken.pats); w.ns = ns.copy(); w.hs = bytearray(hs)
            w.F, w.drawn = dict(F), dict(drawn)
            return event(broken,kind,site,mem.__getitem__,R,w,_alt(broken),Sim)
        out.append(('IY corruption in interruptible hook', bp, run_irq))
    bp = copy.copy(patch)
    pg = bytearray(patch.page)
    di = patch.syms['e_isr'] - 0x2000 + 3
    assert pg[di] == 0xF3
    pg[di] = 0  # remove the interrupt guard, keeping this broken patch's display tables
    bp.page = bytes(pg)
    enabled = list(base)
    enabled[2] = list(base[2])
    enabled[2][26] = 1
    def run_unguarded(broken, k):
        fl, _ = _isr_case(broken, tuple(enabled), _alt(broken), Sim,
                          {0: (100, 80, 3 + k, 7)})
        return fl
    out.append(('MMU mapping without DI', bp, run_unguarded))
    return out


def convergence(rzx_path, stop=None):
    """Replay twice using the C simulator, scrambling plot scratch F/AF' in one run.
    Compare all RAM at each frame end, rather than merely the final game screen.
    """
    import hashlib
    import random
    import skoolkit.rzxplay as rp
    from . import rzx as rz
    def run(scramble):
        hashes=[]; count=[0]; rng=random.Random(5)
        original=rp.RZXTracer.next_frame
        def frame(tracer):
            hashes.append(hashlib.sha256(bytes(tracer.simulator.memory[0x4000:])).digest())
            return original(tracer)
        def plot(pc,sim):
            count[0]+=1
            if scramble:
                for i in (1,16,17):
                    sim.registers[i]=rng.randrange(256)
        rp.RZXTracer.next_frame=frame
        try:
            n,error=rz.trace(rzx_path,(PLOT_END,),plot,stop=stop)
            if error:
                raise ValueError('convergence replay desynchronised: '+error)
        finally:
            rp.RZXTracer.next_frame=original
        return hashes,count[0]
    h0,_=run(False); h1,n=run(True)
    first=next((i for i,(x,y) in enumerate(zip(h0,h1)) if x!=y),None)
    if first is None and len(h0)!=len(h1):
        first=min(len(h0),len(h1))
    return len(h0),n,first


RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': COLOURS,
            'clear': True, 'note': NOTE}


def recolour(nex, cmap):
    import hashlib
    from .recolour import banks, splice
    parts = banks(nex)
    prof = load_profile()
    expected = prof.get('recolour_invariants')
    if not expected:
        raise ValueError('recolour invariants have not been recorded for this build')
    if sorted(parts) != expected['banks']:
        raise ValueError('unexpected bank set')
    if hashlib.sha256(nex[:512]).hexdigest() != expected['header']:
        raise ValueError('unexpected NEX header')
    for b, digest in expected['code'].items():
        if hashlib.sha256(parts[int(b)]).hexdigest() != digest:
            raise ValueError('non-colour bank %s differs from verified build' % b)
    if any(parts[11][128:]):
        raise ValueError('unexpected bytes after diamond pattern')
    ram = bytes(16384) + parts[5] + parts[2] + parts[0]
    if hashlib.sha256(ram[GRAPHICS_BASE:GRAPHICS_BASE+GRAPHICS_BYTES]).hexdigest() != expected['graphics']:
        raise ValueError('graphics differ from the expected snapshot')
    updated = display_banks(ram.__getitem__, cmap)
    updated[11] = painted_diamond(ram.__getitem__, cmap) + parts[11][128:]
    data, changed = splice(nex, updated)
    return data, {'banks changed':changed}


def recolour_file(source, painted, layout, output):
    from . import coloursheet as cs
    if os.path.abspath(source) == os.path.abspath(output):
        raise ValueError('recolour output must be a new file')
    cmap, report = cs.read(painted, layout, clear=True)
    data, info = recolour(open(source,'rb').read(), cmap)
    with open(output,'wb') as f:
        f.write(data)
    stem = os.path.splitext(output)[0].removesuffix('-add-GPT6_ASTRA')
    cs.save(cmap, stem + '_colours-add-GPT6_ASTRA.json', NOTE)
    print(info, report)


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    sink=os.environ.get('NEXCLASH_FIREMAN_PROGRESS')
    if sink:
        original_say=say
        def say(message=''):
            original_say(message)
            with open(sink,'a') as log:
                log.write(message+'\n')
    say('Game      : %s' % name)
    say('Engine    : incredible_shrinking_fireman_add_GPT6_ASTRA (figures and collectables -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    stem = name.removesuffix('-add-GPT6_ASTRA')
    plain = os.path.join(out, stem + '_plain-add-GPT6_ASTRA.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, keep_printer_buffer=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain),
                                         'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = FiremanPatch()
    spr = os.path.join(out, stem + '_sprites-add-GPT6_ASTRA.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3, progress=lambda n,c: say('Progress  : frame %d' % n))
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames: %s -> %s' % (os.path.basename(r), c['frames'],
                                                     {k: v for k, v in c.items() if not k.endswith('!') and k != 'frames'},
                                                     'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        fr, n, first = convergence(r, getattr(a, 'quick', None))
        ok = ok and first is None
        say("F/AF' check: %d frames, F and AF' scrambled at %d plot ends -> memory identical at every frame end: %s" % (
            fr, n, 'YES' if first is None else 'NO, first difference in frame %s' % first))
    if states:
        u = unit_tests(patch, states, negative_patches(patch, states))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % ({k: v for k, v in u.items() if not k.startswith(' ')},
                                       'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in u.items():
            if k.startswith(' '):
                say('            %s' % k.strip())
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    main()
