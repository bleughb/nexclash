"""Cyclone (Vortex Software, 1985; 48K) - engine `cyclone`: colour sheets, the sprite build, its verifier.

Tile-map game (games/cyclone.md): every figure is composited into tiles, then 0x762C draws the map.
Figures that become sprites (user, 2026-10-21): the helicopter, its shadow, the aircraft and the
aircraft's shadow; depth as the original (behind scenery in front), shadows dithered as drawn.

    python -m nexclash.cyclone sheet cyclone.rzx [MORE.rzx ...] -o cyclone      (colour sheets)
    python -m nexclash.cyclone colours cyclone_PAINTING_SPRITES_painted.png     (read back)
    python nexclash.py auto cyclone.z80 --rzx R [--rzx R ...] --no-record       (build + verify)

Build (games/cyclone.md "Phase B design"): the game's compositing runs unchanged; hooks snapshot the
strip's scenery and figures, and around the renderer show the scenery while the figures become
sprites (helicopter / aircraft with a 4-neighbour mask, shadows dithered). Debug hooks: PROF (T per PC
of the patched runs), KEYS (helicopter ink per render), CY_KEEP=1 (keep the hook page after a failure).

Graphics (all 3 x 3 cells = 24 x 24 px, 72 bytes, column-major):
  helicopter  body 0xE8E8 + 72 * (b + 1), b = heading 0x7507 (+8 RES 4 when 0x7504 != 0), copied to
              0x6950 by 0x8CCD; the rotor is XORed in per frame (0x8CD2, deltas at 0x6700 / 0x7000).
              Columns of 24 bytes, top down. Drawn by 0x86AF at the altitude offset.
  shadow      0xED68 + 72 * (b + 1) (same b), drawn by 0x7ADC: columns of 3 cells, bottom up; a cell
              whose first byte is 0xFF is not drawn.
  aircraft    0xDDB8 + 72 * (b + 1), b = heading / 4 (+8 RES 4 with 0x7504), copied by 0x89B2 to tiles
              60-68: columns of 3 cells, top down. Its shadow = the same bytes AND 0xAA / 0x55
              (alternate bytes, 0x89BA) in tiles 51-59.
Colour-map keys: H/S/A/a + the graphics byte's address (a = aircraft shadow); R + 0x6950 offset for
rotor pixels (bits not in the body byte).
"""
import os

PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
BLACK = 8                                   # index 0 is transparent: black figures use 8
HELI_BODY, SHADOW, AIRCRAFT, HELI_BUF = 0xE8E8, 0xED68, 0xDDB8, 0x6950
PC_BODY, PC_HELI, PC_SHADOW, PC_AIR = 0x8CCD, 0x86AF, 0x7BE5, 0x89B2
GROUPS = ('Helicopter', 'Helicopter shadow', 'Aircraft', 'Aircraft shadow')
STATIC_GROUP = 'From the code (not in the recordings)'
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'cyclone_colours.json')
NOTE = ('Cyclone figure colours, read back from cyclone_PAINTING_SPRITES.png (python -m nexclash.cyclone '
        'colours). Key = H helicopter / S its shadow / A aircraft / a aircraft shadow + graphics byte '
        'address, R + offset in 0x6950 for rotor pixels; check = that byte, 8 nibbles = colours of its '
        'bits (0 = default).')


def cell_order(bottom_up):
    """Byte offset of each (column, line) of a 24 x 24 figure stored as 9 cells, column-major."""
    out = {}
    for c in range(3):
        for k in range(3):
            row = 2 - k if bottom_up else k
            for y in range(8):
                out[(c, row * 8 + y)] = (c * 3 + k) * 8 + y
    return out


def _part(group, pid, pixels, x=0, y=0):
    return dict(id=pid, size=1, w=24, h=24, x=x, y=y, mir=0, group=group, role=group,
                pixels=pixels, entries={})


MASK_COL = 15                                # default colour of mask pixels (bright white)


def add_mask(p, fid):
    """User 2026-10-21: helicopter and aircraft get a mask - every pixel 4-adjacent (no diagonals)
    to ink, plus every pixel the mask encloses (no transparent pixel inside it), opaque (code 2).
    The part grows by 1 px on each side (26 x 26). Mask keys: M + figure id + line + byte."""
    ink = {(c + 1, r + 1) for c, r, *_ in p['pixels']}
    w = h = 26
    mask = set(ink)
    for x, y in ink:
        mask |= {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)}
    out, todo = set(), [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while todo:                                  # outside = transparent pixels reachable from the edge
        q = todo.pop()
        if q in out or q in mask or not (0 <= q[0] < w and 0 <= q[1] < h):
            continue
        out.add(q)
        x, y = q
        todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    px = [(c + 1, r + 1, k, b, code, d) for c, r, k, b, code, d in p['pixels']]
    for y in range(h):
        for x in range(w):
            if (x, y) not in out and (x, y) not in ink:
                key = 'M%s:%02d:%d' % (fid, y, x // 8)
                px.append((x, y, key, x % 8, 2, MASK_COL))
                p['entries'][key] = [0, 'M']
    return dict(p, w=w, h=h, pixels=px)


def block_part(peek, kind, b):
    """Shadow ('S'), aircraft ('A') or aircraft shadow ('a') block b (0-15) -> part."""
    base = (SHADOW if kind == 'S' else AIRCRAFT) + 72 * (b + 1)
    order = cell_order(kind == 'S')
    pixels, entries = [], {}
    for (c, line), off in order.items():
        a = base + off
        if kind == 'S' and peek(base + off - off % 8) == 0xFF:
            continue                                         # cell not drawn
        v = peek(a)
        if kind == 'a':
            v &= 0xAA if off % 2 == 0 else 0x55
        key = '%s%04X' % (kind, a)
        for bit in range(8):
            if v >> (7 - bit) & 1:
                pixels.append((c * 8 + bit, line, key, bit, 1, BLACK))
                entries[key] = [peek(a), kind]
    group = {'S': GROUPS[1], 'A': GROUPS[2], 'a': GROUPS[3]}[kind]
    p = _part(group, (kind, b), pixels)
    p['entries'] = entries
    return add_mask(p, 'A%04X' % base) if kind == 'A' else p


def heli_part(peek, body, buf):
    """Helicopter as drawn: buf = the 72 bytes at 0x6950, body = its body block's address."""
    pixels, entries = [], {}
    for c in range(3):
        for line in range(24):
            off = c * 24 + line
            v, bv = buf[off], peek(body + off)
            for bit in range(8):
                if v >> (7 - bit) & 1:
                    if bv >> (7 - bit) & 1:
                        key = 'H%04X' % (body + off)
                        entries[key] = [bv, 'H']
                    else:
                        key = 'R%02X' % off
                        entries[key] = [0, 'R']
                    pixels.append((c * 8 + bit, line, key, bit, 1, BLACK))
    p = _part(GROUPS[0], ('H', body, bytes(buf)), pixels)
    p['entries'] = entries
    return add_mask(p, 'H%04X' % body)


def capture(rzxs):
    """Replay the recordings (C simulator) -> {part id: part} of every figure drawing seen."""
    from . import rzx as RZ
    seen, state = {}, {'body': None}

    def on_pc(pc, sim):
        m, R = sim.memory, sim.registers
        hl = R[6] << 8 | R[7]
        if pc == PC_BODY:
            state['body'] = hl
        elif pc == PC_HELI and state['body'] is not None:
            buf = bytes(m[HELI_BUF:HELI_BUF + 72])
            k = ('H', state['body'], buf)
            if k not in seen:
                seen[k] = heli_part(m.__getitem__, state['body'], buf)
        elif pc == PC_SHADOW:
            b = (hl - SHADOW) // 72 - 1
            if ('S', b) not in seen:
                seen[('S', b)] = block_part(m.__getitem__, 'S', b)
        elif pc == PC_AIR:
            b = (hl - AIRCRAFT) // 72 - 1
            for kind in 'Aa':
                if (kind, b) not in seen:
                    seen[(kind, b)] = block_part(m.__getitem__, kind, b)
    errs = []
    for path in rzxs:
        n, err = RZ.trace(path, (PC_BODY, PC_HELI, PC_SHADOW, PC_AIR), on_pc)
        errs.append((path, n, err))
    return seen, errs


def composites(seen, peek=None):
    """One composite per figure (figures are never joined); blocks the recordings never drew are
    added from the code when peek is given."""
    from . import coloursheet as cs
    comps = []
    for k, p in seen.items():
        if not p['pixels']:
            continue
        comps.append(dict(count=1, group=p['group'], parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    if peek:
        for kind in 'SAa':
            for b in range(16):
                if (kind, b) not in seen:
                    p = block_part(peek, kind, b)
                    if not p['pixels']:
                        continue
                    p['group'] = STATIC_GROUP
                    comps.append(dict(count=0, group=STATIC_GROUP, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)]))
    maxsize = {c['parts'][0]['id']: 1 for c in comps}
    order = list(GROUPS) + [STATIC_GROUP]
    comps.sort(key=lambda c: (order.index(c['group']), str(c['parts'][0]['id'][:2])))
    return cs.choose(comps, maxsize, order), comps


def sheets(comps, prefix, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix, uniq in (('_PAINTING_SPRITES', False), ('_REFERENCE_ALL_SPRITES', False)):
        png = prefix + suffix + '.png'
        n = cs.write(comps[suffix], png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours,
                     unique=uniq)
        out.append((png, n))
    return out


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    p = path or build_colours_path(COLOURS)
    return cs.load(p) if os.path.exists(p) else {}


def _peek(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536])).__getitem__


# =============================================================================================
# Build: sites, patch, Next-side model, differential verify (games/cyclone.md "Phase B design")
# =============================================================================================
import collections
import json

ROM_ORG = 0x386E
ALT_PAGE = 24                   # alt ROM image page (bank 12)
HOOK_BANK, PG = 13, 26          # hook page: Next page 26 (bank 13 low) at slot 6 while a hook runs
TAIL_ADDR = 0x5D24              # 0x5C78-0x5FDB never read or written (RZX scans)
NSPR = 29
TILES, TATTR, AGFX, TGFX, MAP = 0xFCF8, 0xFE5F, 0xFB98, 0xFA00, 0xF74E
T_SH, T_AIR = 0x33, 0x3C
CANVAS_X, CANVAS_Y = 72, 32
SITES = {0x7F72: ('3a0575', 0xC3, 'e_s0', 's0'), 0x7F7A: ('000000', 0xCD, 'e_s1', 's1'),
         0x5B4E: ('cdaf86', 0xCD, 'e_h', 'h'), 0x9281: ('cdaf86', 0xCD, 'e_h', 'h'),
         0x762C: ('1e00dd', 0xC3, 'e_r', 'r'), 0x84D6: ('210040', 0xC3, 'e_c1', 'c'),
         0x8D0E: ('210058', 0xC3, 'e_c2', 'c')}
STOP = {0x7F72: 0x7F75, 0x7F7A: 0x7F7D, 0x5B4E: 0x5B51, 0x9281: 0x9284, 0x84D6: 0x84D9, 0x8D0E: 0x8D11}
INTERIORS = (0x7F73, 0x7F74, 0x762D, 0x762E, 0x84D7, 0x84D8, 0x8D0F, 0x8D10)   # 0x7F7B/C: NOPs
SEQUEL = {0x762E: 0x762C}      # reached straight after its site's own instruction: counts must match
PALETTE_ON = {1: 0x00, 2: 0xFF}                 # sprite palette 0: 1 = ink (black), 2 = mask (white)


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'cyclone.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_cyclone(snap):
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


class CyclonePatch:
    name = 'Cyclone helicopter, aircraft and their shadows -> hardware sprites (altrom + hook page 26 at slot 6)'

    def __init__(self, prof=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True          # the game's main loop lives at 0x5B00-0x5BFF
        self.keep_printer_buffer = True          # ... and NEXLOAD overwrites it: put it back
        self.tail_addr = TAIL_ADDR
        self.max_tail = 0x5FDC - TAIL_ADDR       # to 0x5FDB: never read or written (RZX scans)
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3AFF:
            raise ValueError('ROM hooks too long (the IM 2 vector at 0x3AFF must stay FF FF)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        hp = bytearray(8192)
        code = bytes.fromhex(h['code'])
        hp[0:len(code)] = code
        hp[0x1D00:0x1D10] = bytes.fromhex(h['tbl'])
        self.hook_page = bytes(hp)
        self.sites = [(a, bytes.fromhex(old), bytes([op]) + self.syms[sym].to_bytes(2, 'little'))
                      for a, (old, op, sym, k) in SITES.items()]
        self.extra_banks = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Cyclone patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {12: self.page + bytes(8192), HOOK_BANK: self.hook_page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Model of what the build must show (independent of the hook code)
# ---------------------------------------------------------------------------------------------

def _fill_holes(ink, n):
    """ink: set of (x, y) in an n x n window. -> mask = 4-dilation of ink, plus every pixel not
    4-connected to the window border through non-mask pixels; minus nothing (ink included)."""
    m = set(ink)
    for x, y in ink:
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= q[0] < n and 0 <= q[1] < n:
                m.add(q)
    out = set()
    todo = [(x, y) for x in range(n) for y in (0, n - 1)] + [(x, y) for y in range(n) for x in (0, n - 1)]
    while todo:
        q = todo.pop()
        if q in out or q in m or not (0 <= q[0] < n and 0 <= q[1] < n):
            continue
        out.add(q)
        x, y = q
        todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return {(x, y) for x in range(n) for y in range(n)} - out


class Model:
    """The verifier's own record of S0 / S1 / helicopter, taken from the ORIGINAL game's memory."""

    def __init__(self):
        self.flg, self.s0t, self.s0a, self.s1t, self.hb, self.va = 0, None, None, None, None, 0

    def sprites(self, peek):
        """{(x, y): 1 ink / 2 mask} the sprites must show at a render (peek = memory at its entry)."""
        out = {}
        tiles = [peek(TILES + i) for i in range(264)]
        mp = [peek(MAP + i) for i in range(506)]
        # aircraft shadow (bottom), canvas, aircraft (top)
        for base, mask in ((T_SH, False), (T_AIR, True)):
            got = _figure(mp, base, peek)
            if got is None:
                continue
            ink, x0, y0 = got
            pix = {}
            if mask:
                for p in _fill_holes(ink, 32):
                    pix[p] = 2
            for p in ink:
                pix[p] = 1
            for (x, y), v in pix.items():
                X, Y = x0 + x, y0 + y
                if 0 <= X < 184 and 0 <= Y < 176:
                    if base == T_SH:
                        out[(X, Y)] = v
                    else:
                        out.setdefault(('air', X, Y), v)
        canvas = self.canvas(tiles, mp)
        for (x, y), v in canvas.items():
            out[(CANVAS_X + x, CANVAS_Y + y)] = v
        for k in [k for k in out if k[0] == 'air']:
            out[(k[1], k[2])] = out.pop(k)
        return out

    def canvas(self, F, mp):
        if self.flg & 3 != 3:
            return {}
        ink, he = set(), set()
        top = 62 - self.va
        for c in range(3):
            for r in range(11):
                ti = 11 * c + r
                if mp[(5 + r) * 23 + 10 + c] != 0x5F + ti:
                    continue
                cell = slice(8 * ti, 8 * ti + 8)
                chg = F[cell] != self.s1t[cell]                 # the helicopter changed this cell
                if not chg and self.s1t[cell] == self.s0t[cell]:
                    continue
                for y in range(8):
                    f, s0, s1 = F[8 * ti + y], self.s0t[8 * ti + y], self.s1t[8 * ti + y]
                    L = 8 * r + y
                    sh = s1 & ~s0 & f
                    d = L - top
                    if self.flg & 4 and 0 <= d < 24:
                        hv = f & (~s1 | (s1 & self.hb[24 * c + d])) & 255 if chg else 0
                        other = 0
                    else:
                        hv, other = 0, f & ~s1 & 255
                    for b in range(8):
                        x, yy = 8 * (c + 1) + b, L + 8
                        if (sh | hv | other) >> (7 - b) & 1:
                            ink.add((x, yy))
                        if hv >> (7 - b) & 1:
                            he.add((x, yy))
        pix = {p: 1 for p in ink}
        if KEYS is not None:
            KEYS.append(frozenset(he))
        if self.flg & 4:
            wx, wy = 7, top + 8 - 1                  # 26 x 26 window at canvas (7, WB)
            m = _fill_holes({(x - wx, y - wy) for x, y in he}, 26)
            for x, y in m:
                p = (x + wx, y + wy)
                if p not in he:
                    pix[p] = 2
        return pix


def _figure(mp, base, peek):
    """First map cell (row-major) holding one of the 9 tiles base..base+8 -> its 3 x 3 figure:
    (ink {(x, y)} in a 32 x 32 window, window x0, y0) or None."""
    for i, v in enumerate(mp):
        if 0 <= v - base < 9:
            k = v - base
            arow, acol = i // 23 - k % 3, i % 23 - k // 3
            break
    else:
        return None
    ink = set()
    for k in range(9):
        r, c = arow + k % 3, acol + k // 3
        if 0 <= r < 22 and 0 <= c < 23 and mp[r * 23 + c] == base + k:
            for y in range(8):
                g = peek(TGFX + 8 * (base + k) + y)
                for b in range(8):
                    if g >> (7 - b) & 1:
                        ink.add((4 + 8 * (k // 3) + b, 4 + 8 * (k % 3) + y))
    return ink, acol * 8 - 4, arow * 8 - 4


# ---------------------------------------------------------------------------------------------
# Next side of the patched run
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, hook_page):
        self.nr = {0x56: 0, 0x07: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pidx = 0
        self.page = bytearray(hook_page)
        self.events = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def port(self, port, v):
        if port == 0x303B:
            self.pidx = (v & 0x3F) * 256 + (128 if v & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pidx & 0x3FFF] = v
            self.pidx += 1
        else:
            self.events.append(('out', port, v))

    def shown(self):
        """{(x, y): palette index} of every visible sprite, higher slots on top (ULA coordinates)."""
        out = {}
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            x = a0 + (a2 & 1) * 256 - 32
            y = a1 + (a4 & 1) * 256 - 32
            n = (a3 & 0x3F) << 1 | (a4 >> 6 & 1)
            base = n * 128
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    v = (b >> 4) if k % 2 == 0 else (b & 15)
                    if v:
                        out[(x + k, y + j)] = v + (a2 >> 4) * 16
        return out


def _machine(Sim, mem, regs, ns, slot='o'):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)
    R, ed = sim.registers, sim.after_ED

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na

    # Z80N instructions the hooks use (flags unaffected)
    def add_hl_a():
        v = (R[6] << 8 | R[7]) + R[0]
        R[6], R[7] = (v >> 8) & 255, v & 255
        R[15] = R2[R[15]]; R[24] = (R[24] + 2) % 65536; R[25] += 8

    def mul_de():
        v = R[4] * R[5]
        R[4], R[5] = v >> 8, v & 255
        R[15] = R2[R[15]]; R[24] = (R[24] + 2) % 65536; R[25] += 8
    ed[0x31], ed[0x30] = add_hl_a, mul_de

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.port(port, value)
    sim.set_tracer(Tr())
    return sim


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


def _overlays(get, alt, psite, ns, page):
    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return v if v is not None else get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if 0xC000 <= a < 0xE000 and ns.nr.get(0x56) == PG:
                return page[a - 0xC000]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', 0) + 1
            elif 0xC000 <= a < 0xE000 and ns.nr.get(0x56) == PG:
                page[a - 0xC000] = v
            else:
                s.ov[a] = v
    return O, P


PROF = None                     # {pc: T} when profiling (cy_prof)
KEYS = None                     # helicopter ink per render, when collecting (cache sizing)


def _run(sim, stop, limit=4000000, check=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        if check is not None:
            bad = check(R)
            if bad:
                return bad
        if PROF is not None and check is not None:
            pc, t0 = R[24], R[25]
            ops[mem[pc]]()
            PROF[pc] = PROF.get(pc, 0) + R[25] - t0
            n += 1
            continue
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return 'did not return'
    return None


def event(patch, kind, site, get, R, ns, model, alt, Sim, keep=None):
    """Original vs patched from one state at a hook site. -> (failures, info)."""
    I, IFF, SP, PC = 14, 26, 12, 24
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    sp0 = R[12]
    w = lambda a: get(a) | get(a + 1) << 8
    if kind == 'r':
        ret = w(sp0)

        def stop(r):
            return r[24] == ret and r[12] == sp0 + 2
    else:
        nxt = STOP[site]

        def stop(r):
            return r[24] == nxt and r[12] == sp0
    page = bytearray(ns.page)
    O, P = _overlays(get, alt, psite, ns, page)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    ns.events = []
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    iy, i_, iff = (R[10], R[11]), R[I], R[IFF]
    rb = patch.syms.get('rom_end', 0)

    def safe(r):
        # interrupt safety at every patched instruction (an IM 2 interrupt may arrive anywhere)
        if (r[10], r[11]) != iy or r[I] != i_ or r[IFF] != iff:
            return 'IY / I / IFF changed'
        pc, s = r[PC], r[SP]
        hook = pc < 0x4000 or 0xC000 <= pc < 0xE000
        if 0xC000 <= pc < 0xE000 and ns.nr.get(0x56) != PG:
            return 'code in slot 6 run with the page unmapped'
        if 0xC000 <= s < 0xE000:
            if ns.nr.get(0x56) != PG:
                return 'SP in slot 6 with the page unmapped'
            if s - 16 < 0xDF50 or s > 0xDFF0:
                return 'private stack out of its room (SP %04X PC %04X)' % (s, pc)
        elif s < sp0 - 48 and hook:
            return 'hook stack below the game stack room'
        return None
    f = []
    e1 = _run(so, stop)
    e2 = _run(sp_, stop, check=safe)
    if e1 or e2:
        return ['original: %s' % e1 if e1 else 'patched: %s' % e2], {}
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access other than sprite patterns',))
    if any(e[0] == 'nr' and e[1] not in (0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x56) for e in ns.events):
        f.append(('NEXTREG other than speed / MMU6 / sprite attributes',))
    if ns.nr.get(0x56) != 0 or ns.nr.get(0x07) != 0:
        f.append(('MMU6 or speed not restored', ns.nr.get(0x56), ns.nr.get(0x07)))
    spend = ro[12]
    dead = range(spend - 64, spend)
    keys = set(o.ov) | set(p.ov)
    scr = range(0x4000, 0x5B00) if kind == 'r' else range(0)
    md = [a for a in keys if a not in scr and a not in dead and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), ['0x%04X' % a for a in sorted(md)[:4]]))
    info = {}
    # the verifier's model, from the ORIGINAL memory
    if kind == 's0':
        model.flg = 1
        model.s0t = [get(TILES + i) for i in range(264)]
        model.s0a = [get(TATTR + i) for i in range(33)]
    elif kind == 's1':
        model.flg |= 2
        model.s1t = [get(TILES + i) for i in range(264)]
    elif kind == 'h':
        model.flg |= 4
        model.hb = [o[0x6950 + i] for i in range(72)]
        model.va = o[0x750D]
    elif kind == 'r':
        # screen: the original renderer on the strip's scenery, aircraft tiles blank
        ov = {}
        if model.flg & 3 == 3:
            ov.update({TILES + i: model.s0t[i] for i in range(264)})
            ov.update({TATTR + i: model.s0a[i] for i in range(33)})
        ov.update({AGFX + i: 0 for i in range(144)})
        Oe, _ = _overlays(lambda a: ov[a] if a in ov else get(a), alt, psite, ns, page)
        oe = Oe()
        se = _machine(Sim, oe, list(R), NextState(b''), 'c')
        e3 = _run(se, stop)
        if e3:
            return f + ['model render: %s' % e3], {}
        bad = [a for a in range(0x4000, 0x5B00) if oe[a] != p[a]]
        if bad:
            f.append(('screen differs from the model', len(bad), ['0x%04X' % a for a in bad[:4]]))
        want = model.sprites(get)
        got = {k: v for k, v in ns.shown().items()}
        if got != want:
            d = set(got.items()) ^ set(want.items())
            f.append(('sprite pixels differ from the model', len(d), sorted(d)[:4]))
        if keep is not None:
            keep.append((bytes(p[a] for a in range(0x4000, 0x5B00)), bytes(get(a) for a in range(0x4000, 0x5B00)),
                         dict(got), ro[25], rp[25]))
        info['px'] = len(want)
        info['mask miss'] = int(page[0x1485] != ns.page[0x1485])     # cache round robin moved
        info['mask'] = sum(1 for v in want.values() if v == 2)
        info['air'] = int(_figure([get(MAP + i) for i in range(506)], T_AIR, get) is not None)
    elif kind == 'c':
        if any(ns.attr[i][3] & 0x80 for i in range(NSPR)):
            f.append(('sprite visible after a screen clear',))
    if not f or os.environ.get('CY_KEEP'):
        ns.page[:] = page
    return f, info


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX (original game); at every hook site run original and patched code from the
    same state and compare. -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False}
    ns = NextState(patch.hook_page)
    model = Model()
    cnt = collections.Counter()
    WATCH = set(SITES) | set(INTERIORS)
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['on'] and type(a) is int and a in site_bytes and G(s, a) != v:
                fail('game wrote a patch site', (a,))
            S(s, a, v)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)

            def mk(fn):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        s = SITES.get(pc)
                        if s:
                            kind = s[3]
                            if collect and kind == 'r' and c['collected r'] < collect:
                                c['collected r'] += 1
                                states.append((kind, pc, list(R), bytes(G(mem, a) for a in range(65536)),
                                               _snap_ns(ns), _snap_model(model)))
                            fl, info = event(patch, kind, pc, get, R, ns, model, alt, _rw())
                            c[kind] += 1
                            for k, v in info.items():
                                c['%s %s' % (kind, k)] += v
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
        if progress and st['frame'] % 500 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = Sm
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    for a in INTERIORS:
        if (cnt[a] != cnt[SEQUEL[a]]) if a in SEQUEL else cnt[a]:
            c['jump into a patched instruction (0x%04X)!' % a] += 1
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


def _snap_ns(ns):
    return dict(nr=dict(ns.nr), attr=[list(a) for a in ns.attr], pat=bytes(ns.pat), page=bytes(ns.page))


def _snap_model(m):
    return dict(vars(m))


def _ns_from(patch, d):
    ns = NextState(d['page'])
    ns.page[0:0x0B00] = patch.hook_page[0:0x0B00]           # code
    ns.page[0x1D00:0x1D10] = patch.hook_page[0x1D00:0x1D10]  # nibble table
    ns.page[0x1486] = 0                                      # mask cache: none valid
    ns.nr, ns.attr, ns.pat = dict(d['nr']), [list(a) for a in d['attr']], bytearray(d['pat'])
    return ns


def _model_from(d):
    m = Model()
    m.__dict__.update({k: (list(v) if isinstance(v, list) else v) for k, v in d.items()})
    return m


# ---------------------------------------------------------------------------------------------
# Unit tests: paths the recording does not reach (altitudes, aircraft at the edges, no snapshot,
# helicopter over its shadow), and a negative control
# ---------------------------------------------------------------------------------------------

def _page_state(ns, model):
    """Hook page as the hooks would have left it after S0 / S1 / H with this model."""
    pg = ns.page
    put = lambda a, vals: pg.__setitem__(slice(a - 0xC000, a - 0xC000 + len(vals)), bytes(vals))
    put(0xD449, [model.flg])
    if model.s0t is not None:
        put(0xD000, model.s0t)
        put(0xD108, model.s0a)
    if model.s1t is not None:
        put(0xD130, model.s1t)
    if model.hb is not None:
        put(0xD400, model.hb)
        put(0xD448, [model.va])


def unit_tests(patch, states, neg=None):
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()

    def one(pt, R, mem, nsd, md, mod=None, mem_mod=None):
        mem = bytearray(mem)
        ns = _ns_from(pt, nsd)
        model = _model_from(md)
        if mod:
            mod(model)
        if mem_mod:
            mem_mod(mem)
        _page_state(ns, model)
        return event(pt, 'r', 0x762C, mem.__getitem__, list(R), ns, model, alt, Sim)

    def rec(name, fl):
        c['%s %s' % (name, 'ok' if not fl else 'FAIL!')] += 1
        if fl and c['  fail ' + name] < 2:
            c['  fail ' + name] += 1
            c['  %s: %s' % (name, str(fl[:2])[:160])] += 1

    for kind, pc, R, mem, nsd, md in states:
        if not md.get('flg', 0) & 7 == 7:
            continue
        # altitudes 0..62 (window rows), helicopter over its own shadow
        for va in (0, 1, 7, 8, 30, 54, 60, 61, 62):
            def m1(m, va=va):
                m.va = va
            rec('altitude', one(patch, R, mem, nsd, md, m1)[0])
        # no snapshot this cycle / shadow only / helicopter only
        for flg in (0, 1, 3):
            def m2(m, flg=flg):
                m.flg = flg
            rec('flags', one(patch, R, mem, nsd, md, m2)[0])
        # aircraft and shadow placed at edges and partly hidden
        for (ar, ac) in ((-2, -2), (-1, 5), (0, 0), (10, 10), (19, 20), (20, 21), (21, 22), (5, -1)):
            for hide in (None, 4):
                def mm(mem, ar=ar, ac=ac, hide=hide):
                    for i in range(506):
                        if 0x33 <= mem[MAP + i] <= 0x44:
                            mem[MAP + i] = 0x80
                    for base, dr in ((T_AIR, 0), (T_SH, 6)):
                        for k in range(9):
                            r, cc = ar + dr + k % 3, ac + k // 3
                            if 0 <= r < 22 and 0 <= cc < 23 and k != hide:
                                mem[MAP + r * 23 + cc] = base + k
                    for i in range(144):
                        mem[AGFX + i] = (0x5A, 0xFF, 0x81, 0x3C)[i % 4] if (i // 8) % 3 != 1 else 0x18
                rec('aircraft', one(patch, R, mem, nsd, md, None, mm)[0])
        if neg is not None:
            fl, info = one(patch, R, mem, nsd, md)
            fln, _ = one(neg, R, mem, nsd, md)
            if not info.get('px'):
                c['negative control n/a (nothing drawn)'] += 1
            else:
                c['negative control %s' % ('detected' if fln else 'NOT DETECTED!')] += 1
    return c


def negative_patch(patch):
    """Broken copy: ink and mask nibbles swapped in the hook page's table (pixel check must fail)."""
    import copy
    q = copy.copy(patch)
    hp = bytearray(patch.hook_page)
    t = hp[0x1D00:0x1D10]
    hp[0x1D00:0x1D10] = bytes(((b >> 4 ^ 3 if b >> 4 else 0) << 4) | ((b & 15) ^ 3 if b & 15 else 0) for b in t)
    q.hook_page = bytes(hp)
    return q


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : cyclone (Cyclone: helicopter, aircraft and shadows -> sprites; render-time hooks)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, keep_printer_buffer=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X; printer buffer put back: main loop there)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = CyclonePatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1,
                                                                   os.path.basename(s2)))
            r = s2
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, renders %d (%d with aircraft), S0 %d, S1 %d, helicopter %d, '
            'clears %d, %d sprite pixels (%d mask) -> %s' % (
                os.path.basename(r), c['frames'], c['r'], c['r air'], c['s0'], c['s1'], c['h'], c['c'],
                c['r px'], c['r mask'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
    if states:
        u = unit_tests(patch, states, negative_patch(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items())
                                                if not k.startswith('  ')), 'PASS' if not uf else 'FAIL'))
        for k, v in u.items():
            if k.startswith('  '):
                say('          %s' % k)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.cyclone')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX(s) -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', help='also show the blocks the recordings never drew (from the code)')
    p.add_argument('-o', '--out', default='cyclone')
    p = sub.add_parser('colours', help='painted PAINTING sheet -> colours json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--out', default=COLOURS)
    a = ap.parse_args(argv)
    from . import coloursheet as cs
    if a.cmd == 'sheet':
        seen, errs = capture(a.rzx)
        for path, n, err in errs:
            print('%s: %d frames%s' % (path, n, ', DESYNC: ' + err if err else ''))
        chosen, every = composites(seen, _peek(a.z80) if a.z80 else None)
        for png, n in sheets({'_PAINTING_SPRITES': chosen, '_REFERENCE_ALL_SPRITES': every}, a.out,
                             load_colours()):
            print('%s: %d figures' % (png, n))
        kinds = {}
        for k in seen:
            kinds[k[0]] = kinds.get(k[0], 0) + 1
        print('drawings seen:', kinds)
    elif a.cmd == 'colours':
        lay = a.layout or a.png.replace('_painted.png', '.png').replace('.png', '_layout.json')
        ent, rep = cs.read(a.png, lay)
        cs.save(ent, a.out, NOTE)
        for k, v in rep.items():
            print('%-70s %d' % (k, v))
        print('->', a.out)


if __name__ == '__main__':
    main()
