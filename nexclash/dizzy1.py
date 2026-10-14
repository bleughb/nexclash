"""Dizzy: The Ultimate Cartoon Adventure (Dizzy 1, 48K) - XOR engine: every figure off the ULA.

The game draws every figure with two pure-XOR plotters (no masks, no undo buffers):
  plotter 1 (DZ) 58113: Dizzy only, frames 0-38 + pre-shifted copies 39-77 (+4 px), entered from
                        59488 (erase) and 59515 (draw); screen write 58184 (LD (HL),A; DE = graphics)
  plotter 2 (P2) 57983: everything else, byte-aligned, columns 1-30, 256-frame table at 53148 (data
                        at 43485); screen write 58080 (LD (DE),A; HL = graphics); optional attribute
                        XOR of the cells (B bit 0 before / bit 1 after, colour C) via 57901 -> 58702.
                        The game patches it: 58079 = XOR C (0xA9) or LD A,C (0x79, room renderer
                        only) and 58010 = row helper 57771 (whole frame) or 57797 (clipped rows,
                        types 6/7 from 56946 / 56972 / 57433 - not in the recording).
Callers of P2 (from the code, LEARNINGS 2.1): 54805 (object records, 256 x 20 bytes at 38365),
54958 (spider threads, frame 73), 58546 (room renderer), 60698 / 60723 (egg + rope), 60746 (item
name text), 62670 / 62691 (score digits), 62736 (lives). KEEP (stay on the ULA): room renderer,
HUD digits / lives, item name; every other caller converts (an unknown caller too).

Design (games/dizzy_ultimate_cartoon_adventure.md): converted writes go to a 1-bit shadow screen
(+ shadow attributes) instead of the ULA, so ULA XOR shadow == the original screen at every moment
(XOR is linear); the figure layer shows the shadow in the figures' colours. Logic that reads figure
pixels / cells gets the virtual value (collision 60228, attribute read 58712); overwriters clear the
shadow where they write (wipe 58634 / 58666), the rotator-style effects fold it back first.

This module: game facts, the colour-sheet capture (PLAYBOOK 3b), the preview. CLI:
    python -m nexclash.dizzy1 sheet RZX --z80 Z80 [-o dizzy1]
    python -m nexclash.dizzy1 preview Z80 RZX --at F,F,... [-o preview.png]
    python -m nexclash.dizzy1 colours PAINTED.png [--layout L]
"""
import collections
import os

P2_ENTRY, DZ_ENTRY = 57983, 58113
P2_WRITE, DZ_WRITE = 58080, 58184          # the screen write instructions
P2_ATTR = 58710                            # attribute XOR write (in 58702)
P2_TAB, P2_BASE = 53148, 43485
DZ_TAB, DZ_BASE = 24134, 24290
P2_W, P2_H, P2_XMODE, P2_ROWH = 57716, 57717, 58079, 58010
WIPE, WIPE_ATTR = 58634, 58666
OBJ_TABLE, OBJ_N, OBJ_SIZE = 38365, 256, 20

ROOM = 58549                               # return addresses (the caller's CALL + 3)
HUD = (62673, 62694, 62739)                # score digit erase / draw, lives
TEXT = (60749,)                            # item name line
KEEP = (ROOM,) + HUD + TEXT
DIZZY = (59491, 59518)
GROUPS = (('Dizzy', DIZZY), ('Objects, creatures and items', (54808,)), ('Spider threads', (54961,)),
          ('Egg and rope', (60505, 60509, 60530, 60552, 60555, 60570, 60602, 60627, 60650, 60671)))
OTHER, STATIC_GROUP = 'Other figures', 'From the code (not in the recording yet)'
DRAW_TYPES = (1, 2, 4, 5, 6, 8)            # object types whose handler plots (54766 / 54762 / 54811)

# Next palette (RRRGGGBB), same layout as Midnight Resistance: 0 transparent, 1-7 blue..white,
# 8 black, 9-15 bright blue..bright white
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
WHITE = 15                                 # bright white: the rooms' cells are bright
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'dizzy1_colours.json')
NOTE = ('Dizzy 1 figure colours, read back from dizzy1_PAINTING_SPRITES.png (python -m nexclash.dizzy1 '
        'colours). Key = graphics byte (G = plotter 2 address, D = Dizzy frame 0-38 address; the '
        'shifted copies 39-77 take the same keys), check = that byte, 8 nibbles = colours of its bits '
        '(0 = default).')


def spec_index(attr):
    """Spectrum attribute -> palette index of its ink (bright -> 9-15, ink 0 -> 8 black)."""
    ink, br = attr & 7, attr >> 6 & 1
    return 8 if ink == 0 else ink + 8 * br


def default_colour(dizzy, b, c):
    """Today's colour of a figure: Dizzy bright white; a P2 figure that paints its cells (B bits 0/1)
    the colour it shows on the game's bright white-ink cells (it XORs C = colour ^ 7 into them);
    else bright white."""
    if dizzy or not (b & 3):
        return WHITE
    return spec_index((c ^ 7) | 64)


def group_of(ret):
    for name, rets in GROUPS:
        if ret in rets:
            return name
    return OTHER


def frame_info(peek, n, dizzy):
    """-> (data address, bytes per row, rows) of frame n (None = empty frame, H byte 255)."""
    tab, base = (DZ_TAB, DZ_BASE) if dizzy else (P2_TAB, P2_BASE)
    off = peek(tab + 2 * n) | peek(tab + 2 * n + 1) << 8
    if off >> 8 == 255:
        return None
    a = (base + off) & 0xFFFF
    w, h = peek(a), peek(a + 1)
    return a + 4, (w // 2) if dizzy else (w + 1) // 2, h


def scr_xy(a):
    o = a - 0x4000
    return (o & 31), ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0)


INTERIOR = {}


def interior_masks(peek):
    """Graphics address -> bit mask (0x80 = bit 0) of the frame's ENCLOSED paper: paper pixels that
    cannot be reached from outside the frame through paper (4-connected) - Dizzy's eyes, the inside
    of a bottle (Dean 2026-10-14: figures solid by default). Every frame of both plotters (Dizzy's
    shifted copies give the same pixels shifted; no graphics byte belongs to two frames)."""
    if INTERIOR:
        return INTERIOR
    for dizzy, n in ((True, 78), (False, 256)):
        for f in range(n):
            fi = frame_info(peek, f, dizzy)
            if fi is None:
                continue
            ds, wb, h = fi
            W = wb * 8
            ink = [[peek(ds + r * wb + c // 8) >> (7 - c % 8) & 1 for c in range(W)] for r in range(h)]
            seen, st = {(-1, -1)}, [(-1, -1)]
            while st:
                x, y = st.pop()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if -1 <= nx <= W and -1 <= ny <= h and (nx, ny) not in seen:
                        if 0 <= nx < W and 0 <= ny < h and ink[ny][nx]:
                            continue
                        seen.add((nx, ny))
                        st.append((nx, ny))
            for r in range(h):
                for c in range(W):
                    if not ink[r][c] and (c, r) not in seen:
                        a = ds + r * wb + c // 8
                        INTERIOR[a] = INTERIOR.get(a, 0) | 0x80 >> (c % 8)
    return INTERIOR


def pixel_key(peek, dizzy, frame, gaddr, bit):
    """Graphics byte gaddr, bit -> (part id, staging column, row, colour-map key, key bit, check)."""
    if not dizzy:
        ds, wb, h = frame_info(peek, frame, False)
        j = gaddr - ds
        return ('G', frame), (j % wb) * 8 + bit, j // wb, 'G%04X' % gaddr, bit, peek(gaddr)
    f0 = frame % 39
    ds, wb, h = frame_info(peek, frame, True)
    j = gaddr - ds
    c, r = (j % wb) * 8 + bit, j // wb
    if frame >= 39:
        c -= 4                                 # the pre-shifted copy: same image, 4 px right
    ds0, wb0, _ = frame_info(peek, f0, True)
    ka = ds0 + r * wb0 + c // 8
    return ('D', f0), c, r, 'D%04X' % ka, c % 8, peek(ka)


def part_from_writes(peek, dizzy, frame, writes, group, ret, b, c):
    """writes: [(screen address, graphics address)] of one plot -> coloursheet part."""
    pixels, entries = [], {}
    pid, x0, y0 = None, None, None
    dflt = default_colour(dizzy, b, c)
    inter = interior_masks(peek)
    W = 8 * frame_info(peek, frame % 39 if dizzy else frame, dizzy)[1]
    for sa, ga in writes:
        g = peek(ga)
        im = inter.get(ga, 0)
        cx, sy = scr_xy(sa)
        for bit in range(8):
            ink = g >> (7 - bit) & 1
            pid, col, row, key, kb, chk = pixel_key(peek, dizzy, frame, ga, bit)
            if not 0 <= col < W:
                continue                       # a shifted copy's edge: no key (dz_keys)
            px = cx * 8 + bit
            if x0 is None:
                x0, y0 = px - col, sy - row
            entries[key] = [chk, 1]
            # ink: code 1, today's colour; enclosed paper: code 2 (opaque), black by default; other
            # paper: code 0, transparent unless painted (an outline: fill_mask)
            pixels.append((col, row, key, kb, 1, dflt) if ink else
                          (col, row, key, kb, 2, 8) if im >> (7 - bit) & 1 else (col, row, key, kb, 0, 0))
    if not any(q[4] for q in pixels):
        return None
    ds, wb, h = frame_info(peek, frame % 39 if dizzy else frame, dizzy)
    rows = len({p[1] for p in pixels if p[4]})    # as before clear pixels were listed (figure choice)
    return dict(id=pid, size=rows, w=8 * wb, h=h, x=x0, y=y0, mir=0, group=group, role=ret,
                pixels=pixels, entries=entries)


def static_part(peek, dizzy, frame, group=STATIC_GROUP):
    """The whole frame, as the plotter would draw it (every row)."""
    fi = frame_info(peek, frame, dizzy)
    if fi is None:
        return None
    ds, wb, h = fi
    writes = []
    for r in range(h):
        for k in range(wb):
            writes.append((0x4000 + k + 1 + (((r & 7) << 8) | ((r & 0x38) << 2) | ((r & 0xC0) << 5)),
                           ds + r * wb + k))
    return part_from_writes(peek, dizzy, frame, writes, group, None, 0, 0)


def object_frames(peek):
    """Every frame an object record can show, from the table (base frame of each drawing record)."""
    out = set()
    for i in range(OBJ_N):
        a = OBJ_TABLE + OBJ_SIZE * i
        if peek(a + 4) in DRAW_TYPES and (peek(a) or peek(a + 3)):
            out.add((peek(a + 3) + (peek(a + 6) & 63)) & 255)
    return out


class Capture:
    """simrun hooks: follow both plotters, keep the plots that make a figure visible (XOR parity per
    stamp), one list per RZX frame, and the 1-bit model of what moves off the ULA."""

    def __init__(self):
        self.cur = None            # (dizzy, ret, frame, b, c, stamp, writes)
        self.ret = None
        self.parity = set()
        self.frame_parts = []
        self.frames = []           # per RZX frame: [part]
        self.shadow = bytearray(6144)
        self.fill = bytearray(6144)
        self.dshadow = bytearray(6144)             # Dizzy (hardware sprites, in front)
        self.sattr = bytearray(768)
        self.shots = {}
        self.want = set()
        self.n = 0
        self.calls = collections.Counter()

    def on_sim(self, sim):
        self.sim = sim

    def on_frame(self, n):
        self.n = n
        self.frames.append(self.frame_parts)
        self.frame_parts = []
        if n in self.want:
            m = self.sim.memory
            self.shots[n] = (bytes(m[0x4000 + i] for i in range(6912)), bytes(self.shadow), bytes(self.sattr),
                             dict(self.colour), bytes(self.fill), bytes(self.dshadow))

    def before(self, pc):
        R, m = self.sim.registers, self.sim.memory
        if pc in (P2_ENTRY, DZ_ENTRY):
            sp = R[12]
            ret = m[sp] | m[sp + 1] << 8
            dizzy = pc == DZ_ENTRY
            conv = dizzy or ret not in KEEP
            self.calls[(pc, ret, conv)] += 1
            if not conv:
                self.cur, self.ret = None, ret
                return
            de, hl = R[4] << 8 | R[5], R[6] << 8 | R[7]
            rows = (m[P2_ROWH] | m[P2_ROWH + 1] << 8, m[57718]) if not dizzy else None
            stamp = (pc, R[0], de, hl, rows)
            self.cur = [dizzy, ret, R[0], R[2], R[3], stamp, []]
            self.ret = ret
        elif self.ret is not None and pc == self.ret:
            if self.cur is not None:
                dizzy, ret, frame, b, c, stamp, writes = self.cur
                f = m[57709]               # the frame as the plotter stored it (Dizzy: + 39 when shifted)
                if stamp in self.parity:
                    self.parity.discard(stamp)
                else:
                    self.parity.add(stamp)
                    p = part_from_writes(lambda a: m[a], dizzy, f, writes, group_of(ret), ret, b, c)
                    if p:
                        self.frame_parts.append(p)
            self.cur = self.ret = None
        elif self.cur is not None and pc in (P2_WRITE, DZ_WRITE):
            if pc == P2_WRITE:
                sa, ga = R[4] << 8 | R[5], R[6] << 8 | R[7]
            else:
                sa, ga = R[6] << 8 | R[7], R[4] << 8 | R[5]
            self.cur[6].append((sa, ga))
            o = sa - 0x4000
            if 0 <= o < 6144 and pc == P2_WRITE:   # an object's interior toggles with its ink
                self.fill[o] ^= interior_masks(lambda a: m[a]).get(ga, 0)
        elif pc == WIPE:
            self.parity.clear()

    # the 1-bit model (preview): converted writes go to the shadow, never to the screen
    colour = {}

    def on_write(self, a, v, pc, mem):
        if 0x4000 <= a < 0x5800:
            o = a - 0x4000
            if self.cur is not None and pc == DZ_WRITE:
                self.dshadow[o] ^= mem[a] ^ v
            elif self.cur is not None and pc == P2_WRITE:
                d = mem[a] ^ v
                self.shadow[o] ^= d
                cur = self.cur
                col = default_colour(cur[0], cur[3], cur[4])
                for bit in range(8):
                    if d >> (7 - bit) & 1:
                        self.colour[(o, bit)] = col
            elif pc == 58654:
                self.shadow[o] = 0
                self.fill[o] = 0
                self.dshadow[o] = 0
        elif 0x5800 <= a < 0x5B00:
            o = a - 0x5800
            if self.cur is not None and pc == P2_ATTR:
                self.sattr[o] ^= mem[a] ^ v
            elif pc == 58674:
                self.sattr[o] = 0


def capture(rzx, z80=None, stop=None, want=()):
    """-> (coloursheet composites, Capture)."""
    from . import simrun, coloursheet as cs
    cap = Capture()
    cap.want = set(want)
    simrun.run(z80, [rzx] if isinstance(rzx, str) else rzx, cap, stop=stop)
    col = cs.Collector(family=lambda p: p['group'] if p['group'] in ('Egg and rope',) else None)
    for parts in cap.frames:
        col.add_frame(parts)
    if z80:
        mem = _mem(z80)
        peek = mem.__getitem__
        for f in range(39):
            if ('D', f) not in col.maxsize:
                p = static_part(peek, True, f)
                if p:
                    col.comps[('static', 'D', f)] = dict(count=0, group=STATIC_GROUP, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)])
        for f in sorted(object_frames(peek) | {73, 160, 161, 162, 163, 164}):
            if ('G', f) not in col.maxsize:
                p = static_part(peek, False, f)
                if p:
                    col.comps[('static', 'G', f)] = dict(count=0, group=STATIC_GROUP, parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)])
                    col.maxsize[('G', f)] = p['size']
    order = [g[0] for g in GROUPS] + [OTHER, STATIC_GROUP]
    return col.composites(order), cap


def _mem(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)                   # ROM not needed: the graphics are in RAM
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536]))


def sheets(comps, prefix, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix, uniq in (('_PAINTING_SPRITES', True), ('_REFERENCE_ALL_SPRITES', False)):
        png = prefix + suffix + '.png'
        n = cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours, unique=uniq,
                     paint_clear=True)          # outlines: paper bits are paintable (fill_mask)
        out.append((png, n))
    return out


def load_colours(path=COLOURS):
    from . import coloursheet as cs
    return cs.load(path)


def preview(z80, rzx, at, out):
    """Each shot: the original screen | the planned build (ULA without the converted figures, figure
    layer on top in the default colours)."""
    from PIL import Image
    from . import simrun
    cs_rgb = __import__('nexclash.coloursheet', fromlist=['x']).palette_rgb(PALETTE)
    cap = Capture()
    cap.want = set(at)
    simrun.run(z80, [rzx], cap, stop=max(at) + 1)
    ink = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205)]
    br = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]

    def ula(scr, shadow=None):
        im = Image.new('RGB', (256, 192))
        px = im.load()
        for a in range(6144):
            cx, y = scr_xy(0x4000 + a)
            v = scr[a] ^ (shadow[a] if shadow else 0)
            at_ = scr[6144 + (y >> 3) * 32 + cx]
            pal = br if at_ & 64 else ink
            for b in range(8):
                px[cx * 8 + b, y] = pal[at_ & 7] if v >> (7 - b) & 1 else pal[at_ >> 3 & 7]
        return im

    tiles = []
    for n in sorted(cap.shots):
        scr, sh0, sa, colr, fl, dsh = cap.shots[n]
        sh = bytes(sh0[i] ^ dsh[i] for i in range(6144))    # both leave the ULA
        # the simulation runs the ORIGINAL game: its screen holds the figures; the build's ULA is the
        # screen without them (XOR the shadow out), its attributes without the figures' cell colours
        o = ula(scr)
        p = ula(bytes(scr[i] ^ sh[i] for i in range(6144)) + bytes(scr[6144 + i] ^ sa[i] for i in range(768)))
        pp = p.load()
        for a in range(6144):
            if sh0[a] or fl[a]:
                cx, y = scr_xy(0x4000 + a)
                for b in range(8):
                    if sh0[a] >> (7 - b) & 1:
                        pp[cx * 8 + b, y] = cs_rgb[colr.get((a, b), WHITE)]
                    elif fl[a] >> (7 - b) & 1:
                        pp[cx * 8 + b, y] = cs_rgb[8]          # enclosed paper: solid black
        for a in range(6144):                                   # Dizzy on top (his sprites)
            if dsh[a]:
                cx, y = scr_xy(0x4000 + a)
                for b in range(8):
                    if dsh[a] >> (7 - b) & 1:
                        pp[cx * 8 + b, y] = cs_rgb[WHITE]
        t = Image.new('RGB', (520, 196), (40, 40, 40))
        t.paste(o, (2, 2))
        t.paste(p, (262, 2))
        tiles.append(t)
    cols = 2
    sheet = Image.new('RGB', (cols * 520, ((len(tiles) + cols - 1) // cols) * 196), (40, 40, 40))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 520, (i // cols) * 196))
    sheet.save(out)
    return sorted(cap.shots)


# ---------------------------------------------------------------------------------------------
# Build: hooks in alt ROM image 1 (0x2000-), shadow page PG at slot 3, Layer 2, colour plane
# ---------------------------------------------------------------------------------------------
ROM_ORG = 0x2000
ALT_PAGE = 24                      # alt ROM copy source (bank 12)
PG, GPG = 26, 11                   # shadow page; the game's page at slot 3
L2B, L2PG = 16, 32                 # Layer 2 banks 16-18 = pages 32-37
PLPG, NPL = 40, 15                 # plane pages 40-54 (banks 20-27): colours, interiors, transparent
PG2 = 27                           # fill shadow (enclosed paper of the drawn figures; display only)
PG3 = 28                           # Dizzy's shadow (he is hardware sprites 0-3, in front of Layer 2)
SPB = 15                           # sprite patterns: bank 15 (pages 30-31), uploaded by setup
QUADS = ((0, 0), (16, 0), (0, 16), (16, 16))   # TL, TR, BL, BR = sprites 0-3
P2LEN, DZLEN = 9663, 4760          # plane: plotter 2 graphics 43485-53147, Dizzy 24290-29049
HOOK_RAM = (0x5B40, 0x5BC0)        # variables + hook stack (printer buffer, never touched by the game)
HSTK_MIN = 0x5B58 + 18             # lowest SP allowed in a hook (variables end + an interrupt's room)
TAIL_ADDR = 0x5B00                 # never touched by the game (RZX scan); the plain build uses it too
PROFILE = os.path.join(_HERE, '..', 'docs', 'profiles', 'dizzy1_ultimate_cartoon_adventure.json')
SITES = ((57983, 'cb83326de1', 'e_p2'), (58076, '7e4f1a', 'e_p2w'), (58113, '326de1', 'e_dz'),
         (58182, '1aae77', 'e_dw'),
         (58702, 'f5cd3be5f1', 'e_at'), (58712, 'cd3be57ec9', 'e_ar'), (60244, '7ee6f0e1c1c9', 'e_c1'),
         (60251, '7ee60fe1c1c9', 'e_c2'), (58634, 'dd21d65c', 'e_wipe'), (58666, '21a058', 'e_wipea'),
         (55935, 'dd7e0bfe00', 'e_f3'), (57095, 'dd4e0b', 'e_f7'))
# bytes the hooks rely on: continuations, the attribute routine run as a copy (58683), the row
# helper and XOR mode the game sets, every caller of plotter 2 (KEEP decisions are return addresses)
FACTS = ((57988, 'ed436e'), (58116, 'cb3b30'), (58079, 'a91213'), (58010, 'abe1'), (58185, '231310'),
         (58683, '3ebf95e6f82600546f2929cb3b1911005819c9'), (58707, 'e67f'), (58710, '77c9'),
         (60247, 'e1c1c9'), (60254, 'e1c1c9'), (58638, '0690afc5'), (58669, '0e1223'),
         (55938, 'fe0028'), (57098, 'cb2106'), (58546, 'cd7fe2'), (62670, 'cd7fe2'), (62691, 'cd7fe2'),
         (62736, 'cd7fe2'), (60746, 'cd7fe2'), (60698, 'c37fe2'), (60723, 'c37fe2'), (54805, 'cd7fe2'),
         (54958, 'cd7fe2'), (59488, 'cd01e3'), (59515, 'cd01e3'))
CONT = {60244: 60247, 60251: 60254, 55935: 55938, 57095: 57098}   # segment sites; the rest: to RET
INTERIORS = {a + k for a, old, s in SITES for k in range(1, 3)}  # bytes 2-3 of each JP


def load_profile():
    import json
    return json.load(open(PROFILE))


def colour_entry(cmap, peek, dizzy, ga, bit):
    """Painted colour (1-15) of graphics bit (ga, bit), or 0 (default). Entries whose check byte is
    not the graphics byte at that address are ignored."""
    if not cmap:
        return 0
    if not dizzy:
        e = cmap.get('G%04X' % ga)
        return e[2][bit] if e and e[0] == peek(ga) else 0
    k = DZ_KEYS.get((ga, bit))
    if k is None:
        return 0
    e = cmap.get(k[0])
    return e[2][k[1]] if e and e[0] == k[2] else 0


def clear_entry(cmap, peek, dizzy, ga, bit):
    """True when graphics bit (ga, bit) was painted transparent (entry's 4th element)."""
    if not cmap:
        return False
    if not dizzy:
        e = cmap.get('G%04X' % ga)
        return bool(e and len(e) > 3 and e[0] == peek(ga) and e[3] & (0x80 >> bit))
    k = DZ_KEYS.get((ga, bit))
    e = cmap.get(k[0]) if k else None
    return bool(e and len(e) > 3 and e[0] == k[2] and e[3] & (0x80 >> k[1]))


def fill_mask(cmap, peek, dizzy, ga):
    """Bit mask (0x80 = bit 0) of graphics byte ga's opaque NON-ink pixels: the enclosed paper
    (interior_masks), plus every paper bit painted a colour and not transparent (an outline, Dean
    2026-10-14). The hooks draw these through the fill shadow (plane byte 4), which toggles with the
    ink, in the bit's colour (black by default)."""
    m = interior_masks(peek).get(ga, 0)
    if cmap:
        cand = sum(0x80 >> b for b in range(8) if colour_entry(cmap, peek, dizzy, ga, b) and
                   not clear_entry(cmap, peek, dizzy, ga, b))
        if cand:                    # (reads ga only then: colour_inputs_md5 lists the bytes read)
            m |= cand & ~peek(ga) & 255
    return m


DZ_KEYS = {}


def dz_keys(peek):
    """(graphics address, bit) of every Dizzy frame byte (78 frames) -> (key, key bit, check)."""
    if DZ_KEYS:
        return DZ_KEYS
    for f in range(78):
        ds, wb, h = frame_info(peek, f, True)
        W0 = 8 * frame_info(peek, f % 39, True)[1]
        for j in range(wb * h):
            for bit in range(8):
                # a shifted copy (f >= 39, 4 px right) is wider than its frame: its first and last 4
                # columns have no key (they are paper; before outlines the right edge wrapped onto
                # the next row's first byte, harmless while paper had no colour)
                if not 0 <= (j % wb) * 8 + bit - (4 if f >= 39 else 0) < W0:
                    continue
                _, c, r, key, kb, chk = pixel_key(peek, True, f, ds + j, bit)
                DZ_KEYS[(ds + j, bit)] = (key, kb, chk)
    return DZ_KEYS


def plane_pages(cmap, peek):
    """-> {page: 8K}: the plane, 8 bytes per graphics byte (plotter-2 graphics, then Dizzy's): 8 colour
    nibbles (0 = default), the fill mask (interior + painted paper), the transparent mask, 1 = has
    colours. Always built."""
    if cmap:
        dz_keys(peek)
    plane = bytearray(NPL * 8192)
    for idx in range(P2LEN + DZLEN):
        dizzy = idx >= P2LEN
        ga = DZ_BASE + idx - P2LEN if dizzy else P2_BASE + idx
        e = 8 * idx
        if cmap:
            nib = [colour_entry(cmap, peek, dizzy, ga, b) for b in range(8)]
            for k in range(4):
                plane[e + k] = nib[2 * k] << 4 | nib[2 * k + 1]
            plane[e + 5] = sum(0x80 >> b for b in range(8) if clear_entry(cmap, peek, dizzy, ga, b))
            plane[e + 6] = 1 if any(nib) else 0         # colours to expand (else the defaults)
        plane[e + 4] = fill_mask(cmap, peek, dizzy, ga)
    return {PLPG + p: bytes(plane[p * 8192:(p + 1) * 8192]) for p in range(NPL)}


def dz_image(peek, cmap, f):
    """Dizzy frame f (0-38) as drawn by the build: {(column, row): colour} - ink white (15) or
    painted, enclosed paper black (8) or painted, paper painted a colour (outline) in it,
    painted-transparent pixels left out."""
    ds, wb, h = frame_info(peek, f, True)
    img = {}
    for r in range(h):
        for c in range(wb * 8):
            a, b = ds + r * wb + c // 8, c % 8
            m = 0x80 >> b
            ink = peek(a) & m
            if not ink and not fill_mask(cmap, peek, True, a) & m:
                continue
            if clear_entry(cmap, peek, True, a, b):
                continue
            img[(c, r)] = colour_entry(cmap, peek, True, a, b) or (WHITE if ink else 8)
    return img


def dz_sprites(peek, cmap):
    """-> (table: per frame rows + 4 x (attr 3, attr 4), 16K of 4-bit patterns, pattern count)."""
    if cmap:
        dz_keys(peek)
    pats, index, table = [], {}, bytearray()
    for f in range(39):
        img = dz_image(peek, cmap, f)
        table.append(frame_info(peek, f, True)[2])
        for qx, qy in QUADS:
            pix = [img.get((qx + x, qy + y), 0) for y in range(16) for x in range(16)]
            if not any(pix):
                table += b'\x00\x00'
                continue
            key = bytes(pix)
            if key not in index:
                index[key] = len(pats)
                pats.append(bytes((pix[i] << 4) | pix[i + 1] for i in range(0, 256, 2)))
            n = index[key]
            table += bytes([0xC0 | (n >> 1), 0x80 | ((n & 1) << 6)])
    if len(pats) > 128:
        raise ValueError('Dizzy needs %d 4-bit sprite patterns, 128 fit' % len(pats))
    data = b''.join(pats)
    return bytes(table), data + bytes(16384 - len(data)), len(pats)


class Dizzy1Patch:
    name = 'Dizzy 1 figures -> Layer 2 (altrom 0x2000- + shadow page 26 at slot 3; XOR shadow)'

    def __init__(self, prof=None, colours=None, edit=None, peek=None):
        """colours: the colour map ({} = defaults; None = docs/profiles/dizzy1_colours.json);
        edit: {ROM address: bytes} over the hook code (negative controls); peek: snapshot memory
        (needed for a colour map: the plane is keyed by graphics address, checked against it)."""
        from .build import rom48
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        code = bytearray.fromhex(h['rom'])
        self.colours = load_colours() if colours is None else colours
        self.peek = peek
        self.plane = {}
        self.edit = edit or {}
        self.base_code = bytes(code)
        for a, d in self.edit.items():
            code[a - ROM_ORG:a - ROM_ORG + len(d)] = d
        self.rom_code = bytes(code)
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hook code too long (must end below 0x3D00)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        rom = rom48()
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.stub_extra = bytes.fromhex(h['setup']) + bytes([0xE3] + PALETTE[1:])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = HOOK_RAM[0] - TAIL_ADDR
        self.sites = [(a, bytes.fromhex(old), b'\xC3' + self.syms[s].to_bytes(2, 'little')) for a, old, s in SITES]
        if peek is not None:
            self.prepare(peek)

    def prepare(self, peek):
        """Plane (interiors + colour map) and Dizzy's sprites from the game's graphics; the .nex banks."""
        from .build import rom48
        self.peek = peek
        self.plane = plane_pages(self.colours, peek)
        table, self.patterns, self.num_patterns = dz_sprites(peek, self.colours)
        code = bytearray(self.base_code)
        t = self.syms['dztab'] - ROM_ORG
        code[t:t + len(table)] = table
        for a, d in self.edit.items():              # negative controls apply over the table too
            code[a - ROM_ORG:a - ROM_ORG + len(d)] = d
        self.rom_code = bytes(code)
        page = bytearray(rom48()[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.extra_banks = {12: self.page + bytes(8192), 13: bytes(16384),      # pages 26 / 27: shadows
                            14: bytes(16384), SPB: self.patterns}               # page 28: Dizzy's shadow
        for b in range(L2B, L2B + 3):
            self.extra_banks[b] = bytes(16384)            # Layer 2 starts transparent
        for pg, data in self.plane.items():
            b = self.extra_banks.setdefault(pg // 2, bytes(16384))
            k = (pg & 1) * 8192
            self.extra_banks[pg // 2] = b[:k] + data + b[k + 8192:]

    def check(self, peek):
        for a, old, new in self.sites:
            cur = bytes(peek(a + k) for k in range(len(old)))
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected version of the '
                                 'game, or already patched' % (a, cur.hex(), old.hex()))
        for a, hx in FACTS:
            want = bytes.fromhex(hx)
            cur = bytes(peek(a + k) for k in range(len(want)))
            if cur != want:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), hx))

    def apply(self, snap):
        if snap.is128:
            raise ValueError('this patch is for the 48K version')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        self.check(lambda a: ram[a - 0x4000])
        mem = bytes(16384) + bytes(ram)
        self.prepare(mem.__getitem__)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[0:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])

    def alt_image(self):
        from .build import rom48
        alt = bytearray(rom48())
        alt[0x2000:0x4000] = self.page
        return bytes(alt)


def static_check(code, syms, org=ROM_ORG):
    """Decode the hook code instruction by instruction (data blocks 'keep' and 'dztab' skipped):
    no EXX / EX AF,AF' / IY / LD I / IM / DI / EI / RETN, and nothing at 0x3D00-0x3DFF (DivMMC trap,
    LEARNINGS 1.4). Returns a list of findings."""
    from .simrun import disasm
    bad = []
    if org + len(code) > 0x3D00:
        bad.append(('code reaches 0x3D00', org + len(code)))
    mem = bytearray(65536)
    mem[org:org + len(code)] = code
    skip = {(syms['keep'], syms['keep'] + 12), (syms['dztab'], syms['dztab'] + 39 * 9)}
    a = org
    while a < org + len(code):
        blk = next((e for s, e in skip if s <= a < e), None)
        if blk:
            a = blk
            continue
        if mem[a] == 0xED and mem[a + 1] in (0x91, 0x92):     # Z80N NEXTREG nn,n / nn,A
            a += 4 if mem[a + 1] == 0x91 else 3
            continue
        text, n = disasm(mem, a)
        t = text.upper()
        if t.startswith(('EXX', "EX AF", 'DI', 'EI', 'IM ', 'RETN', 'LD I,')) or 'IY' in t:
            bad.append((text, a))
        a += n
    return bad


# ---------------------------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------------------------
CMP = list(range(0, 15)) + list(range(16, 25)) + [26, 27, 28]   # all but R, T, MEMPTR (AF' included)
CODE_END = None


class Model:
    """The patched machine's state that the original's memory does not hold: shadow page PG (screen
    0-6143, attributes 0x1800-), fill shadow PG2, Layer 2 pages, hook RAM; and the independent
    expectation of the ink / fill shadows and Layer 2 (Python, from the original's writes)."""

    def __init__(self, patch, peek):
        self.pages = {PG: bytearray(8192), PG2: bytearray(8192), PG3: bytearray(8192)}
        self.patch = patch
        self.spr = [[0] * 5 for _ in range(4)]     # Dizzy's sprites 0-3 as the hooks set them
        self.sel = 0
        self.dz = {'vis': 0, 'pend': 0, 'stamp': None}   # expected sprite state
        self.exp_sd = bytearray(6144)
        for k in range(6):
            self.pages[L2PG + k] = bytearray(8192)
        for p, d in patch.plane.items():
            self.pages[p] = bytearray(d)
        self.hram = None                          # filled from the first state (snapshot bytes)
        self.exp_sh = bytearray(6144)
        self.exp_fs = bytearray(6144)
        self.exp_l2 = bytearray(256 * 192)
        self.cmap = patch.colours
        self.peek = peek
        self.inter = interior_masks(peek)
        if self.cmap:
            dz_keys(peek)

    def writer(self, dizzy, ga, dflt):
        """(colours per bit, interior mask, transparent mask) of a graphics byte, as fillpix."""
        g = self.peek(ga)
        pix = [colour_entry(self.cmap, self.peek, dizzy, ga, b) or (dflt if g >> (7 - b) & 1 else 8)
               for b in range(8)]
        cl = sum(0x80 >> b for b in range(8) if clear_entry(self.cmap, self.peek, dizzy, ga, b))
        return pix, fill_mask(self.cmap, self.peek, dizzy, ga), cl

    def exp_write(self, o, new, fx, w=None):
        """As setsh: ink shadow byte o becomes `new`, fill ^= fx; pixels whose ink or uncovered fill
        changed: ink -> colour (0 if painted transparent); fill of this graphic's interior ->
        colour (0 if transparent), another's -> black; else 0."""
        pix, im, cl = w or ([0] * 8, 0, 0)
        oi, of = self.exp_sh[o], self.exp_fs[o]
        nf = of ^ fx
        self.exp_sh[o], self.exp_fs[o] = new, nf
        ch = (oi ^ new) | (fx & ~new & 255)
        if not ch:
            return
        cx, y = scr_xy(0x4000 + o)
        for b in range(8):
            m = 0x80 >> b
            if not ch & m:
                continue
            if new & m:
                v = 0 if cl & m else pix[b]
            elif nf & m:
                v = (0 if cl & m else pix[b]) if im & m else 8
            else:
                v = 0
            self.exp_l2[y * 256 + cx * 8 + b] = v

    def exp_fold(self, o):
        self.exp_sd[o] = 0
        if self.exp_sh[o] or self.exp_fs[o]:
            self.exp_write(o, 0, self.exp_fs[o])

    def dz_hide(self):
        self.dz.update(vis=0, pend=0)

    def dz_plot(self, a, e, l):
        """Expected sprite state after a Dizzy plot call (frame a, x e, y l)."""
        h = frame_info(self.peek, a, True)[2]
        if (l + h) & 255 >= 200:
            return                          # the original draws nothing
        st = (a, e, l)
        if self.dz['vis'] and not self.dz['pend'] and self.dz['stamp'] == st:
            self.dz['pend'] = 1             # the erase: still shown until the next draw
        else:
            self.dz.update(vis=1, pend=0, stamp=st)

    def sprite_failures(self):
        """The sprites as the hooks set them against the expected state: hidden, or the stamp's
        image (colours, interior, transparency) at x = 4E, y = 192 - L - rows; and that image's ink
        against Dizzy's shadow (the plotter's real pixels)."""
        f = []
        shown = {}
        pat = self.patch.patterns
        for k, (a0, a1, a2, a3, a4) in enumerate(self.spr):
            if not a3 & 0x80:
                continue
            x = a0 + (a2 & 1) * 256 - 32
            y = a1 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            for j in range(16):
                for i in range(16):
                    b = pat[base + j * 8 + i // 2]
                    c = (b >> 4) if i % 2 == 0 else (b & 15)
                    if c:
                        shown[(x + i, y + j)] = c
        if not self.dz['vis']:
            if shown:
                f.append(('Dizzy sprite shown while it should be hidden', len(shown)))
            return f
        a, e, l = self.dz['stamp']
        h = frame_info(self.peek, a, True)[2]
        X, Y = 4 * e, 192 - l - h          # (negative: partly above the screen)
        want = {(X + c, Y + r): v for (c, r), v in dz_image(self.peek, self.cmap, a).items()}
        if shown != want:
            f.append(('Dizzy sprite differs from his image', (a, e, l), len(set(shown.items()) ^ set(want.items()))))
        if not self.dz['pend']:
            ds, wb, _ = frame_info(self.peek, a, True)
            ink = {(X + c, Y + r) for r in range(h) for c in range(wb * 8)
                   if self.peek(ds + r * wb + c // 8) >> (7 - c % 8) & 1 and 0 <= Y + r < 192}
            sd = self.pages[PG3]
            have = set()
            for o in range(6144):
                if sd[o]:
                    cx, yy = scr_xy(0x4000 + o)
                    have |= {(cx * 8 + b, yy) for b in range(8) if sd[o] >> (7 - b) & 1}
            if have != ink:
                f.append(('Dizzy sprite not where the plotter drew him', (a, e, l), len(have ^ ink)))
        return f


class _Mem(list):
    """Patched machine memory: 64K list; slot 3 (0x6000-0x7FFF) shows Next page `cur` unless it is
    the game's page; records written addresses."""
    __slots__ = ('pages', 'cur', 'w', 'wp')

    def __getitem__(s, a):
        if type(a) is int and 0x6000 <= a < 0x8000 and s.cur != GPG:
            return s.pages[s.cur][a - 0x6000]
        return list.__getitem__(s, a)

    def __setitem__(s, a, v):
        if type(a) is int:
            if 0x6000 <= a < 0x8000 and s.cur != GPG:
                s.pages[s.cur][a - 0x6000] = v
                s.wp.add((s.cur, a - 0x6000))
                return
            s.w.add(a)
        list.__setitem__(s, a, v)


class _OMem(list):
    __slots__ = ('w',)

    def __setitem__(s, a, v):
        if type(a) is int:
            s.w.append((a, v))
        list.__setitem__(s, a, v)


def _stop(stop, R, sp0, ret):
    if stop is not None:
        return R[24] == stop
    return R[24] == ret and R[12] == (sp0 + 2) & 0xFFFF


def run_pair(patch, alt, mem, regs, model, site, check_int=True, limit=2000000, stop_at=None):
    """Run the original and the patched code from `site` (a hook site, PC = site) to the same point
    (segment continuation, or the routine's return). mem: the ORIGINAL's 64K (bytes/list).
    Returns (orig sim, patched sim, failures, original writes)."""
    from skoolkit.simulator import Simulator, R2
    fails = []
    sp0 = regs[12]
    ret = mem[sp0] | mem[(sp0 + 1) & 0xFFFF] << 8
    stop = stop_at if stop_at is not None else CONT.get(site)
    # original
    om = _OMem(mem)
    om.w = []
    so = Simulator(om, {})
    so.registers[:] = regs
    R, ops = so.registers, so.opcodes
    n = 0
    gw = []
    wpc = {P2_ENTRY: P2_WRITE, DZ_ENTRY: DZ_WRITE}.get(site)
    while not _stop(stop, R, sp0, ret):
        if R[24] == wpc:
            if site == DZ_ENTRY:
                sa, ga = R[6] << 8 | R[7], R[4] << 8 | R[5]
            else:
                sa, ga = R[4] << 8 | R[5], R[6] << 8 | R[7]
            gw.append((sa, R[0] ^ list.__getitem__(om, sa), ga))   # what the original changes
        ops[om[R[24]]]()
        n += 1
        if n > limit:
            fails.append(('original did not return', site))
            break
    # patched
    pm = _Mem(mem)
    pm[0:0x4000] = alt
    for a, old, new in patch.sites:
        pm[a:a + len(new)] = list(new)
    sh, sd = model.pages[PG], model.pages[PG3]
    for i in range(6144):
        if sh[i] ^ sd[i]:
            list.__setitem__(pm, 0x4000 + i, mem[0x4000 + i] ^ sh[i] ^ sd[i])
    for i in range(768):
        if sh[0x1800 + i]:
            list.__setitem__(pm, 0x5800 + i, mem[0x5800 + i] ^ sh[0x1800 + i])
    pm[HOOK_RAM[0]:HOOK_RAM[1]] = list(model.hram)
    pm.pages, pm.cur, pm.w, pm.wp = model.pages, GPG, set(), set()
    sp_ = Simulator(pm, {})
    P = sp_.registers
    P[:] = regs
    nr = {0x07: 0}

    def setreg(reg, val):
        nr[reg] = val
        if reg == 0x53:
            pm.cur = val
        elif reg == 0x34:
            model.sel = val
        elif 0x35 <= reg <= 0x39:
            if model.sel < 4:
                model.spr[model.sel][reg - 0x35] = val
            else:
                fails.append(('sprite %d written (Dizzy uses 0-3)' % model.sel, site))

    def nn():
        p = P[24]
        setreg(pm[(p + 2) & 0xFFFF], pm[(p + 3) & 0xFFFF])
        P[15] = R2[P[15]]; P[24] = (p + 4) & 0xFFFF; P[25] += 20

    def na():
        p = P[24]
        setreg(pm[(p + 2) & 0xFFFF], P[0])
        P[15] = R2[P[15]]; P[24] = (p + 3) & 0xFFFF; P[25] += 17
    sp_.after_ED[0x91], sp_.after_ED[0x92] = nn, na
    ops = sp_.opcodes
    keep = [P[i] for i in (10, 11, 14, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27)]
    n = 0
    minsp = 0x10000
    hook_sp = None
    fast = [0]
    tp0 = P[25]
    while not _stop(stop, P, sp0, ret):
        pc = P[24]
        if pc < 0x4000:
            if hook_sp is None:
                hook_sp = P[12]                   # SP at the hook's JP
        else:
            hook_sp = None
        if 0x3D00 <= pc < 0x3E00:
            fails.append(('code fetched at 0x3D00-0x3DFF', pc))
            break
        if pc in INTERIORS:
            fails.append(('jump into a patched instruction', pc))
            break
        t0 = P[25]
        ops[pm[pc]]()
        if nr.get(0x07, 0) == 3:
            fast[0] += P[25] - t0             # run at 28 MHz (counted as T / 8 on the Next)
        n += 1
        if check_int and pc < 0x4000:
            if [P[i] for i in (10, 11, 14, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27)] != keep:
                fails.append(('hook changed IY / I / alternate set / IFF / IM', pc))
            s = P[12]
            if HOOK_RAM[0] <= s <= HOOK_RAM[1]:
                minsp = min(minsp, s)
                if s < HSTK_MIN:
                    fails.append(('hook stack too deep for an interrupt', pc, s))
            elif s < hook_sp - 4:
                fails.append(('hook pushed below the game SP', pc, s))
        if n > limit:
            fails.append(('patched did not return', site))
            break
    if pm.cur != GPG:
        fails.append(('slot 3 not given back', site, pm.cur))
    if nr.get(0x07, 0) != 0:
        fails.append(('left at 28 MHz', site))
    model.hram = bytes(list.__getitem__(pm, a) for a in range(*HOOK_RAM))
    so.gw = gw
    so.t = so.registers[25] - regs[25]
    sp_.t = P[25] - tp0 - fast[0] + fast[0] // 8      # the Next's time, in 3.5 MHz T-states
    return so, sp_, fails, om.w, pm


def compare(so, sp_, om_w, pm, mem_after_orig, model):
    """Registers + memory: equal everywhere but the screen / attributes (there ULA ^ shadow ==
    the original) and the hook RAM. Returns failures."""
    f = []
    ro, rp = so.registers, sp_.registers
    d = [i for i in CMP if ro[i] != rp[i]]
    if d:
        f.append(('registers differ', d, [(ro[i], rp[i]) for i in d][:4]))
    sh, sd = model.pages[PG], model.pages[PG3]
    addrs = {a for a, v in om_w} | pm.w
    for a, v in om_w:
        if HOOK_RAM[0] <= a < HOOK_RAM[1]:
            f.append(('the original wrote the hook RAM (printer buffer)', a))
            break
    for a in addrs:
        if HOOK_RAM[0] <= a < HOOK_RAM[1] or a < 0x4000:
            continue
        o = so.memory[a]
        p = list.__getitem__(pm, a)
        if 0x4000 <= a < 0x5800:
            p ^= sh[a - 0x4000] ^ sd[a - 0x4000]
        elif 0x5800 <= a < 0x5B00:
            p ^= sh[0x1800 + a - 0x5800]
        if o != p:
            f.append(('memory differs', a, o, p))
            break
    for pg, off in pm.wp:
        if pg in (PG, PG3) and off < 6144:
            a = 0x4000 + off
            if (list.__getitem__(pm, a) ^ sh[off] ^ sd[off]) != so.memory[a]:
                f.append(('screen differs (ULA ^ shadow)', a))
                break
        elif pg == PG and 0x1800 <= off < 0x1B00:
            a = 0x5800 + off - 0x1800
            if (list.__getitem__(pm, a) ^ sh[off]) != so.memory[a]:
                f.append(('attribute differs (ULA ^ shadow)', a))
                break
        elif pg == PG and off >= 0x1B00:
            f.append(('wrote the shadow page outside shadow', off))
        elif pg == PG2 and off >= 6144:
            f.append(('wrote the fill page outside the fill shadow', off))
        elif pg == PG3:
            f.append(('wrote Dizzy\'s page outside his shadow', off))
        elif pg not in range(L2PG, L2PG + 6) and pg not in (PG, PG2):
            f.append(('wrote page %d' % pg, off))
    return f


def expect(model, site, regs, mem0, om_w, so, conv, dflt):
    """Independent expectation of the shadow / Layer 2 after one routine, from the ORIGINAL's run."""
    if site == DZ_ENTRY:
        model.dz_plot(regs[0], regs[5], regs[7])
        for sa, d, ga in so.gw:             # Dizzy: his own shadow, no Layer 2
            o = sa - 0x4000
            if 0 <= o < 6144:
                model.exp_sd[o] ^= d
        return
    if site == P2_ENTRY and model.dz['pend']:
        model.dz_hide()                     # erased and something else drawn first: hidden
    if site == WIPE:
        model.dz_hide()
    if site in (P2_ENTRY, DZ_ENTRY):
        dizzy = site == DZ_ENTRY
        # the original's screen writes (58080 / 58184) in order, with their graphics address
        for sa, d, ga in so.gw:
            o = sa - 0x4000
            if not 0 <= o < 6144 or not conv:
                continue                   # kept: the change goes to the ULA, the shadow stays
            w = model.writer(dizzy, ga, dflt)
            model.exp_write(o, model.exp_sh[o] ^ d, w[1], w)     # ink change + its interior
    elif site == WIPE:
        for i in range(8, 152):
            la = mem0[23750 + 2 * i] | mem0[23751 + 2 * i] << 8
            for c in range(1, 31):
                a = la + c - 0x4000
                if 0 <= a < 6144:
                    model.exp_fold(a)
    elif site in (55935, 57095):
        ix = regs[8] << 8 | regs[9]
        g = lambda k: mem0[(ix + k) & 0xFFFF]
        if site == 55935:
            if g(11) not in (0, 2, 3):
                return
            l0, nl, c0, nc = g(9), (g(10) - g(9) + 1) & 255, g(7), (g(8) - g(7) + 1) & 255
        else:
            l0, nl, c0, nc = g(11), 8, g(10), g(12)
        if nc == 0:
            return                         # the asm's fold does nothing for 0 columns
        for i in range(nl or 256):
            li = (l0 + i) & 255
            la = mem0[(23750 + 2 * li) & 0xFFFF] | mem0[(23751 + 2 * li) & 0xFFFF] << 8
            for c in range(nc):
                a = (la + c0 + c) & 0xFFFF
                if 0x4000 <= a < 0x5800:
                    model.exp_fold(a - 0x4000)


def check_l2(model, f, full=False, bytes_=None):
    """Layer 2 pages against the expectation (all, or the screen bytes given)."""
    pages = model.pages
    rng = range(6144) if full else (bytes_ or ())
    for o in rng:
        cx, y = scr_xy(0x4000 + o)
        pg = pages[L2PG + (y >> 5)]
        base = (y & 31) * 256 + cx * 8
        if bytes(pg[base:base + 8]) != bytes(model.exp_l2[y * 256 + cx * 8:y * 256 + cx * 8 + 8]):
            f.append(('Layer 2 differs from the expected figures', 0x4000 + o,
                      list(pg[base:base + 8]), list(model.exp_l2[y * 256 + cx * 8:y * 256 + cx * 8 + 8])))
            return
        sh = pages[PG][o]
        if sh != model.exp_sh[o]:
            f.append(('shadow differs from the expected figures', 0x4000 + o, sh, model.exp_sh[o]))
            return
        if pages[PG3][o] != model.exp_sd[o]:
            f.append(('Dizzy\'s shadow differs from the expected', 0x4000 + o, pages[PG3][o], model.exp_sd[o]))
            return
        if pages[PG2][o] != model.exp_fs[o]:
            f.append(('fill shadow differs from the expected figures', 0x4000 + o, pages[PG2][o], model.exp_fs[o]))
            return


FORK = {P2_ENTRY, DZ_ENTRY, 58702, 58712, 60244, 60251, WIPE, WIPE_ATTR, 55935, 57095}


def verify(patch, rzx, z80, stop=None, collect=0, progress=None):
    """Differential test over an RZX. Returns (counters, examples, collected states)."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    alt = list(patch.alt_image())
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    tf = collections.Counter()                     # extra T per RZX frame (patched - original)
    st = {'f': 0, 'busy': None, 'model': None, 'prev': None}
    G = list.__getitem__

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['f'],) + tuple(info))

    def event(pc, R, mem):
        model = st['model']
        if model is None:
            mem0 = bytes(mem)
            if not patch.plane:
                patch.prepare(lambda a: mem0[a])
            model = st['model'] = Model(patch, lambda a: mem0[a])
            model.hram = mem0[HOOK_RAM[0]:HOOK_RAM[1]]
            try:
                patch.check(lambda a: mem0[a])
            except ValueError as e:
                fail('snapshot check', (str(e),))
        if G(mem, 65022) | G(mem, 65023) << 8 != 56:
            fail('interrupt handler is not the ROM 0x0038 at a hook site', (pc,))
        mem0 = list(mem)                          # fast: the list's own buffer
        regs = list(R)
        sp0 = regs[12]
        conv, dflt = True, WHITE
        if pc == P2_ENTRY:
            ret = mem0[sp0] | mem0[sp0 + 1] << 8
            conv = ret not in KEEP
            dflt = default_colour(False, regs[2], regs[3])
            if mem0[P2_XMODE] not in (0xA9, 0x79, 0xB1):
                fail('plotter 2 mode byte unexpected', (mem0[P2_XMODE],))
            c['plotter 2 calls %s' % ('converted' if conv else 'kept on the ULA')] += 1
            if mem0[58010] | mem0[58011] << 8 != 57771:
                c['plotter 2 calls with the clipped-row helper'] += 1
        elif pc == DZ_ENTRY:
            c['Dizzy plotter calls'] += 1
        else:
            c['site %d' % pc] += 1
        ck = '%d %d' % (pc, (mem0[sp0] | mem0[sp0 + 1] << 8) if pc in (P2_ENTRY, DZ_ENTRY) else 0) + \
            (' %d' % (regs[5] & 1) if pc == DZ_ENTRY else '')
        if collect and c['collected ' + ck] < collect:    # per caller (plotter 2) / shift (Dizzy)
            c['collected ' + ck] += 1
            states.append((pc, regs, bytes(mem0), bytes(model.pages[PG]), model.hram, bytes(model.pages[PG2]),
                           bytes(model.pages[PG3]), [list(x) for x in model.spr], dict(model.dz)))
        pend0 = model.dz['pend']
        so, sp_, fl, om_w, pm = run_pair(patch, alt, mem0, regs, model, pc)
        tf[st['f']] += sp_.t - so.t
        c['T extra at %d' % pc] += sp_.t - so.t
        for k in fl:
            fail('%d: %s' % (pc, k[0]), k[1:])
        for k in compare(so, sp_, om_w, pm, None, model):
            fail('%d: %s' % (pc, k[0]), k[1:])
        expect(model, pc, regs, mem0, om_w, so, conv, dflt)
        touched = {off for pg, off in pm.wp if pg in (PG, PG2, PG3) and off < 6144}
        for pg, off in pm.wp:
            if L2PG <= pg < L2PG + 6:
                y = (pg - L2PG) * 32 + (off >> 8)
                x = off & 255
                touched.add(((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3))
        f2 = []
        check_l2(model, f2, bytes_=touched)
        if pc in (DZ_ENTRY, WIPE) or (pc == P2_ENTRY and pend0):
            f2 += model.sprite_failures()
            c['Dizzy sprite checks'] += 1
        for k in f2:
            fail('%d: %s' % (pc, k[0]), k[1:])
        c['figure pixels compared'] += 8 * len(touched)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(fn):
                def g():
                    pc = R[24]
                    if st['busy'] is not None:
                        b_ret, b_sp = st['busy']
                        if pc == b_ret and R[12] == b_sp:
                            st['busy'] = None
                    if st['busy'] is None and pc in FORK:
                        event(pc, R, mem)
                        if pc not in CONT:
                            sp0 = R[12]
                            st['busy'] = (G(mem, sp0) | G(mem, sp0 + 1) << 8, (sp0 + 2) & 0xFFFF)
                        else:
                            st['busy'] = (CONT[pc], R[12])
                    elif pc in INTERIORS and st['prev'] is not None and st['prev'] >= 0x4000 and \
                            st['prev'] not in range(pc - 3, pc):          # (an interrupt may return here)
                        fail('instruction inside a patch site entered by a jump', (pc, st['prev']))
                    st['prev'] = pc
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

        def accept_interrupt(self, registers, memory, prev_pc):
            return super().accept_interrupt(registers, memory, prev_pc)

    # global check: no instruction outside a forked routine reads or writes a screen byte / cell
    # that holds figure bits (they are not on the ULA in the build)
    class W(list):
        def __getitem__(s, a):
            if type(a) is int and 0x4000 <= a < 0x5B00 and st['busy'] is None and st['model'] is not None:
                sh = st['model'].pages[PG]
                if sh[a - 0x4000 if a < 0x5800 else 0x1800 + a - 0x5800]:
                    fail('unhooked read of a figure byte', (a,))
            return G(s, a)

        def __setitem__(s, a, v):
            if type(a) is int and 0x4000 <= a < 0x5B00 and st['busy'] is None and st['model'] is not None:
                sh = st['model'].pages[PG]
                if sh[a - 0x4000 if a < 0x5800 else 0x1800 + a - 0x5800]:
                    fail('unhooked write of a figure byte', (a,))
            if type(a) is int and st['model'] is not None and any(x <= a < x + len(o) for x, o, n in patch.sites):
                fail('game wrote a patch site', (a,))
            list.__setitem__(s, a, v)

    class Sw(Sm):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(W(memory), registers, state_, config)

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['f'] += 1
        if progress and st['f'] % 500 == 0:
            progress(st['f'])
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = next_frame, Sw, None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    c['frames'] = st['f']
    if tf:
        v = sorted(tf.values())
        c['extra T per frame (median)'] = v[len(v) // 2]
        c['extra T per frame (max)'] = v[-1]
        c['frames with hook work'] = len(v)
    if st['model'] is not None:
        f2 = []
        check_l2(st['model'], f2, full=True)
        for k in f2:
            fail('end: %s' % k[0], k[1:])
    return c, ex, states


# ---------------------------------------------------------------------------------------------
# Unit tests: paths the recording does not reach (or reaches without figures present), negative
# controls. States come from verify(collect=N): (site, registers, 64K, shadow page, hook RAM).
# ---------------------------------------------------------------------------------------------
EFFECT_END = 54710                 # every type-3 / type-7 branch ends with JP 54710


def _model_from(patch, st):
    """A Model in the captured state: shadows from it, Layer 2 consistent with them (ink white,
    uncovered fill black), the expectation equal to it."""
    pc, regs, mem, pg, hram = st[:5]
    pg2 = st[5] if len(st) > 5 else bytes(8192)
    model = Model(patch, lambda a: mem[a])
    model.pages[PG][:] = pg
    model.pages[PG2][:] = pg2
    if len(st) > 6:
        model.pages[PG3][:] = st[6]
        model.exp_sd[:] = st[6][:6144]
        model.spr = [list(x) for x in st[7]]
        model.dz = dict(st[8])
    model.hram = hram
    for o in range(6144):
        if pg[o] or pg2[o]:
            model.exp_sh[o], model.exp_fs[o] = pg[o], pg2[o]
            _l2_both(model, o, 0xFF)
    return model


def _l2_both(model, o, mask):
    """Layer 2 + expectation of byte o's pixels in `mask` from the shadows: ink white, fill black."""
    cx, y = scr_xy(0x4000 + o)
    for b in range(8):
        m = 0x80 >> b
        if mask & m:
            v = WHITE if model.exp_sh[o] & m else 8 if model.exp_fs[o] & m else 0
            model.exp_l2[y * 256 + cx * 8 + b] = v
            model.pages[L2PG + (y >> 5)][(y & 31) * 256 + cx * 8 + b] = v


def _seed(model, o, v):
    """Make byte o of the original screen hold figure bits v (they move to the shadow)."""
    model.pages[PG][o] ^= v
    model.exp_sh[o] ^= v
    _l2_both(model, o, v)


def case(patch, st, prep=None, stop_at=None):
    """One state through run_pair + compare + expectation + Layer 2 check -> failures."""
    pc, regs, mem, pg, hram = st[:5]
    mem, regs = list(mem), list(regs)
    if not patch.plane:
        patch.prepare(lambda a: mem[a])          # interiors (+ colours) from the game's graphics
    model = _model_from(patch, (pc, regs, mem, pg, hram) + tuple(st[5:]))
    if prep:
        prep(mem, regs, model)
    sp0 = regs[12]
    conv, dflt = True, WHITE
    if pc == P2_ENTRY:
        conv = (mem[sp0] | mem[sp0 + 1] << 8) not in KEEP
        dflt = default_colour(False, regs[2], regs[3])
    alt = list(patch.alt_image())
    so, sp_, fl, om_w, pm = run_pair(patch, alt, mem, regs, model, pc, stop_at=stop_at)
    f = list(fl) + compare(so, sp_, om_w, pm, None, model)
    expect(model, pc, regs, mem, om_w, so, conv, dflt)
    touched = {off for p_, off in pm.wp if p_ in (PG, PG2, PG3) and off < 6144}
    for p_, off in pm.wp:
        if L2PG <= p_ < L2PG + 6:
            y = (p_ - L2PG) * 32 + (off >> 8)
            touched.add(((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | ((off & 255) >> 3))
    check_l2(model, f, bytes_=touched)
    if pc in (DZ_ENTRY, WIPE, P2_ENTRY):
        f += model.sprite_failures()
    return f


def _pick(states, site, test=None):
    for s in states:
        if s[0] == site and (test is None or test(s)):
            return s
    return None


def unit_tests(patch, states, z80=None):
    """-> (Counter: 'name' passes / 'name!' fails, negative controls detected; examples)."""
    c = collections.Counter()
    exs = []

    def run(name, st, prep=None, stop_at=None, p=None, want_fail=False):
        if st is None:
            c['no state for ' + name + '!'] += 1
            return
        f = case(p or patch, st, prep, stop_at)
        c['cases'] += 1
        if want_fail:
            c['negative controls'] += 1
            if f:
                c['negative controls detected'] += 1
            else:
                c['negative control NOT detected: ' + name + '!'] += 1
        elif f:
            c[name + '!'] += 1
            exs.append((name, f[:2]))
        else:
            c[name] += 1

    ret = lambda s: s[2][s[1][12]] | s[2][s[1][12] + 1] << 8
    p2c = _pick(states, P2_ENTRY, lambda s: ret(s) not in KEEP)
    p2k = _pick(states, P2_ENTRY, lambda s: ret(s) == ROOM)
    p2h = _pick(states, P2_ENTRY, lambda s: ret(s) in HUD + TEXT)
    dz = _pick(states, DZ_ENTRY)

    def mode(v, at=None):
        def f(mem, regs, model):
            mem[P2_XMODE] = v
            if at is not None:
                mem[58709] = at
        return f

    # 1. plotter 2 in every mode, converted and kept (the RZX: XOR converted, LD / OR kept only)
    for v in (0xA9, 0xB1, 0x79):
        for at in (0xAE, 0x00):
            run('plotter 2 converted, mode %02X / attr %02X' % (v, at), p2c, mode(v, at))
            run('plotter 2 kept (room), mode %02X / attr %02X' % (v, at), p2k, mode(v, at))

    # 2. kept callers drawing over figure bits (the shadow under them stays exact)
    def over(v, at=None):
        def f(mem, regs, model):
            mode(v, at)(mem, regs, model)
            for o in range(0, 6144, 7):
                _seed(model, o, 0x5A)
            for i in range(0, 768, 5):
                model.pages[PG][0x1800 + i] ^= 0x07
        return f
    for v in (0xA9, 0xB1, 0x79):
        run('kept caller over figures, mode %02X' % v, p2k, over(v, 0x00))
        run('HUD caller over figures, mode %02X' % v, p2h, over(v))
        run('converted over figures, mode %02X' % v, p2c, over(v))
    run('Dizzy over figures', dz, over(0xA9))

    # 3. off the screen: plotter rows past line 191 (line table runs into game data), attribute
    # and collision addresses outside the screen
    def high(mem, regs, model):
        regs[6], regs[7] = 0, 175              # y + rows past line 191 (and < 200: the plotter draws)
    run('plotter 2 rows off the screen', p2c, high)
    run('Dizzy rows off the screen', dz, high)
    st = _pick(states, 58712)

    def attr_off(mem, regs, model):
        regs[7] = 200                          # L > 191: 58683 wraps outside the attributes
    run('attribute read outside the attributes', st, attr_off)
    run('attribute read over a figure cell', st, lambda m, r, md: [md.pages[PG].__setitem__(0x1800 + i, 0x45) for i in range(768)])
    for site in (60244, 60251):
        st = _pick(states, site)
        run('collision read over figure bits (%d)' % site, st,
            lambda m, r, md: _seed(md, ((r[6] << 8 | r[7]) - 0x4000) % 6144, 0xFF))
        run('collision read off the screen (%d)' % site, st, lambda m, r, md: (r.__setitem__(6, 0x80)))

    # 4. effects with figures inside their rectangle, every branch, run to the end of the effect
    def fx(kind):
        def f(mem, regs, model):
            ix = regs[8] << 8 | regs[9]
            if kind is not None:
                mem[ix + 11] = kind
            for o in range(6144):
                _seed(model, o, 0x81)
        return f
    s3 = _pick(states, 55935)
    for k in (0, 2, 3, 1):
        run('type-3 effect %d with figures inside' % k, s3, fx(k), stop_at=EFFECT_END)
    s7 = _pick(states, 57095)
    run('type-7 rotator with figures inside', s7, fx(None), stop_at=EFFECT_END)
    sw = _pick(states, WIPE)
    run('room wipe with figures everywhere', sw, fx(None))
    swa = _pick(states, WIPE_ATTR)
    run('attribute wipe with figure cells', swa, lambda m, r, md: [md.pages[PG].__setitem__(0x1800 + i, 0x47) for i in range(768)])

    # 5. colour map: synthetic map on the graphics these states draw, a wrong check byte (ignored)
    if z80:
        mem0 = _mem(z80)
        peek = mem0.__getitem__
        dz_keys(peek)
        cmap = {}
        import random
        rnd = random.Random(1)
        for n, ga in enumerate(range(P2_BASE, P2_BASE + P2LEN, 3)):
            cmap['G%04X' % ga] = [peek(ga), 1, [rnd.randrange(16) for _ in range(8)]] + \
                ([rnd.randrange(1, 256)] if n % 4 == 0 else [])              # some painted transparent
        for n, ((ga, bit), (key, kb, chk)) in enumerate(list(DZ_KEYS.items())[::5]):
            cmap.setdefault(key, [chk, 1, [rnd.randrange(16) for _ in range(8)]] +
                            ([rnd.randrange(1, 256)] if n % 3 == 0 else []))
        # Dizzy's paper: a black outline (paper next to ink), as painted; random colours on all his
        # paper need more than the 128 patterns (138), a real outline far fewer (Dean's: 95)
        im1 = interior_masks(peek)
        for f in range(39):
            ds, wb, h = frame_info(peek, f, True)
            W = wb * 8
            ink = lambda c_, r_: 0 <= c_ < W and 0 <= r_ < h and peek(ds + r_ * wb + c_ // 8) >> (7 - c_ % 8) & 1
            for r in range(h):
                for col in range(W):
                    a = ds + r * wb + col // 8
                    m = 0x80 >> (col % 8)
                    if (peek(a) | im1.get(a, 0)) & m:
                        continue
                    e = cmap.setdefault('D%04X' % a, [peek(a), 1, [0] * 8])
                    e[2][col % 8] = 8 if any(ink(col + dx, r + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) else 0
        bad = 'G%04X' % (P2_BASE + 1)
        cmap[bad] = [peek(P2_BASE + 1) ^ 0xFF, 1, [5] * 8]      # wrong check byte
        pm = Dizzy1Patch(colours=cmap, peek=peek)
        c['map entries'] = len(cmap)
        if any(pm.plane[PLPG][8:12]) or pm.plane[PLPG][13]:      # index 1 = the wrong-check entry
            c['wrong check byte used by the plane!'] += 1
        else:
            c['wrong check byte ignored'] += 1
        for name, s in (('converted', p2c), ('Dizzy', dz), ('Dizzy (shifted copy)', _pick(states, DZ_ENTRY, lambda s: s[1][5] & 1))):
            run('colour map: ' + name, s, p=pm)
        # negative controls: the plane without the map (the model expects the map's colours), and
        # the plane without the interiors (the model expects solid figures)
        nomap_c = Dizzy1Patch(colours=cmap, peek=peek)
        nomap_c.plane = plane_pages({}, peek)
        run('colour map left out of the build', p2c, p=nomap_c, want_fail=True)
        # outlines (painted paper bits, fill_mask): the random map paints paper bits too. Negative
        # controls: the plane's fill masks back to the interiors only (Layer 2 figures), and Dizzy's
        # patterns built from the map without its paper colours (the model expects the outlines)
        im0 = interior_masks(peek)
        nout = sum(bin(fill_mask(cmap, peek, False, P2_BASE + i) & ~im0.get(P2_BASE + i, 0)).count('1')
                   for i in range(P2LEN))
        c['outline pixels in the colour map: %d' % nout] += 1
        noout = Dizzy1Patch(colours=cmap, peek=peek)
        pl = {k: bytearray(v) for k, v in noout.plane.items()}
        for idx in range(P2LEN + DZLEN):
            ga = DZ_BASE + idx - P2LEN if idx >= P2LEN else P2_BASE + idx
            pl[PLPG + idx // 1024][(idx % 1024) * 8 + 4] = im0.get(ga, 0)
        noout.plane = {k: bytes(v) for k, v in pl.items()}
        run('outlines left out of the plane', p2c, p=noout, want_fail=True)

        def paper(key, kb):
            a = int(key[1:], 16)
            return not (peek(a) | im0.get(a, 0)) & (0x80 >> kb)
        cmap2 = {k: [e[0], e[1], [0 if paper(k, b) else v for b, v in enumerate(e[2])]] + list(e[3:])
                 for k, e in cmap.items()}
        nodz = Dizzy1Patch(colours=cmap2, peek=peek)
        nodz.colours = cmap                      # the model expects the map's outlines on Dizzy
        run('outlines left out of Dizzy\'s patterns', dz, p=nodz, want_fail=True)
        noint = Dizzy1Patch(colours={}, peek=peek)
        pl = {k: bytearray(v) for k, v in noint.plane.items()}
        for idx in range(P2LEN + DZLEN):
            pl[PLPG + idx // 1024][(idx % 1024) * 8 + 4] = 0
        noint.plane = {k: bytes(v) for k, v in pl.items()}
        inter = interior_masks(peek)

        def solid(s_):
            if ret(s_) in KEEP:
                return False
            fi = frame_info(lambda a: s_[2][a], s_[1][0], False)
            return bool(fi) and any(inter.get(fi[0] + k) for k in range(fi[1] * fi[2]))
        run('interiors left out of the build', _pick(states, P2_ENTRY, solid), p=noint, want_fail=True)

    # 6. Dizzy's sprite: erase = still shown (pending); pending + plotter 2 / wipe = hidden; a plot
    # the original does not draw (y + rows >= 200) changes nothing
    er = _pick(states, DZ_ENTRY, lambda s: ret(s) == 59491 and len(s) > 8 and s[8]['vis'])
    run('Dizzy erase keeps the sprite until the draw', er)

    def pending(mem, regs, model):
        h = bytearray(model.hram)
        h[0x5B61 - HOOK_RAM[0]] = 1             # V_VIS
        h[0x5B62 - HOOK_RAM[0]] = 1             # V_PEND
        model.hram = bytes(h)
        model.dz.update(vis=1, pend=1, stamp=(0, 20, 60))
        model.spr[0] = [64, 64, 0, 0xC0, 0x80]
    run('pending Dizzy + plotter 2: hidden', p2c, pending)
    run('pending Dizzy + room wipe: hidden', sw, pending)

    def off(mem, regs, model):
        regs[7] = 190                           # y + rows >= 200: the plotter returns at once
    run('Dizzy plot off the screen: nothing', dz, off)

    # 7. negative controls on the hooks
    S = patch.syms
    cv = patch.rom_code.index(b'\xcd' + S['virt'].to_bytes(2, 'little'), S['e_c1'] - ROM_ORG)
    nv = Dizzy1Patch(colours={}, edit={ROM_ORG + cv: b'\x7e\x00\x00'})          # raw read, no virtual
    st = _pick(states, 60244)
    run('no virtual read', st, lambda m, r, md: _seed(md, ((r[6] << 8 | r[7]) - 0x4000) % 6144, 0xFF),
        p=nv, want_fail=True)
    nf = Dizzy1Patch(colours={}, edit={S['fold']: b'\xc9'})                     # fold does nothing
    run('no fold before the type-7 rotator', s7, fx(None), stop_at=EFFECT_END, p=nf, want_fail=True)
    run('no fold at the room wipe', sw, fx(None), p=nf, want_fail=True)
    nk = Dizzy1Patch(colours={}, edit={S['keep']: bytes(12)})                   # KEEP list empty
    run('room renderer converted', p2k, p=nk, want_fail=True)
    hs = patch.rom_code.index(b'\x31\xc0\x5b', S['e_p2w'] - ROM_ORG)              # LD SP,HSTK in e_p2w
    ns = Dizzy1Patch(colours={}, edit={ROM_ORG + hs: b'\x31\x60\x5b'})          # hook stack too low
    run('hook stack too deep', p2c, p=ns, want_fail=True)
    y1 = patch.rom_code.index(b'\x3e\xe0', S['dzspr'] - ROM_ORG)                # LD A,224 (sprite Y)
    ny = Dizzy1Patch(colours={}, edit={ROM_ORG + y1: b'\x3e\xdf'})
    run('Dizzy sprite one pixel too high', _pick(states, DZ_ENTRY, lambda s: ret(s) == 59518), p=ny, want_fail=True)
    npat = Dizzy1Patch(colours={})
    npat.prepare(_mem(z80).__getitem__ if z80 else (lambda a: dz[2][a]))
    npat.patterns = bytes(16384)
    run('Dizzy patterns left out', _pick(states, DZ_ENTRY, lambda s: ret(s) == 59518), p=npat, want_fail=True)
    return c, exs


def layer2_boot(nex, z80):
    """Boot the .nex (nextboot) and check the Layer 2 setup: bank 16, visible (0x123B = 2), the 16
    palette entries (index 0 = 0xE3 transparent), and banks 16-18 zero in the file."""
    from . import nextboot
    s = __import__('nexclash.z80tonex', fromlist=['x']).Z80Snapshot(z80)
    st = nextboot.boot(nex, s.pc)
    bad = []
    if st['nr'].get(0x12) != L2B:
        bad.append(('Layer 2 bank', st['nr'].get(0x12)))
    if st['ports'].get(0x123B) != 2:
        bad.append(('port 0x123B', st['ports'].get(0x123B)))
    log = st['nrlog']
    try:
        i = log.index((0x43, 0x10))
        pal = [v for r, v in log[i + 2:] if r == 0x41][:16]
    except ValueError:
        pal = []
    if pal != [0xE3] + PALETTE[1:]:
        bad.append(('Layer 2 palette', pal))
    banks, _, _ = nextboot.load_nex(nex)
    for b in range(L2B, L2B + 3):
        if any(banks.get(b, b'\x01')):
            bad.append(('Layer 2 bank %d not zero in the .nex' % b,))
    return bad


# ---------------------------------------------------------------------------------------------
# Recolour (Dean 2026-10-14): a painted sheet -> dizzy1_sprites_painted.nex, a copy of the built
# dizzy1_sprites.nex with only its colour banks rewritten, in about a second; dizzy1.nex and
# dizzy1_sprites.nex stay untouched. The colours are display data only (the game never reads the
# sprite table in bank 12, bank 15 or banks 20-27; only the hooks' Layer 2 and sprite writes do), so
# the logic proof of the build stands; no further checks (Dean). Same map -> same bytes as a full
# build with it (checked once, 2026-10-14).
# ---------------------------------------------------------------------------------------------
COLOUR_BANKS = (12, SPB) + tuple(range(PLPG // 2, (PLPG + NPL + 1) // 2))   # 12, 15, 20-27


def colour_inputs_md5(peek):
    """MD5 + count of every game byte the colour banks are built from (graphics, frame tables),
    in address order. The profile keeps the snapshot's value: recolour refuses another game version."""
    import hashlib
    seen = set()

    def rec(a):
        seen.add(a)
        return peek(a)
    INTERIOR.clear()
    DZ_KEYS.clear()
    dummy = {'G0000': [0, 1, [0] * 8]}             # non-empty: walks Dizzy's keys too
    plane_pages(dummy, rec)
    dz_sprites(rec, dummy)
    INTERIOR.clear()
    DZ_KEYS.clear()
    return hashlib.md5(bytes(peek(a) for a in sorted(seen))).hexdigest(), len(seen)


def _nex_offsets(d):
    """.nex bytes -> {bank: file offset} (nexclash/z80tonex.write_nex layout)."""
    from . import z80tonex as zt
    if d[0:4] != b'Next':
        raise ValueError('not a .nex file')
    off, res = 512, {}
    for b in zt.BANK_FILE_ORDER:
        if d[18 + b]:
            res[b] = off
            off += 16384
    if off != len(d):
        raise ValueError('.nex size %d, banks say %d' % (len(d), off))
    return res


def recolour(nex, cmap):
    """Built dizzy1_sprites.nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is
    not this engine's build of the expected snapshot (patch sites, hook code, set-up code, game
    graphics, interiors)."""
    d = bytearray(nex)
    off = _nex_offsets(d)
    need = set(COLOUR_BANKS) | {5, 2, 0, 10}
    if not need <= set(off):
        raise ValueError('not a Dizzy 1 sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000] if a >= 0x4000 else 0
    prof = load_profile()
    want = prof.get('colour_inputs', {})
    got = colour_inputs_md5(peek)
    if [want.get('md5'), want.get('bytes')] != list(got):
        raise ValueError('game graphics differ from the expected snapshot (%s / %d bytes, expected %s)'
                         % (got[0], got[1], want))
    p0 = Dizzy1Patch(prof, colours={})
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site %d does not hold this build\'s hook jump' % a)
    for a, hx in FACTS:
        w = bytes.fromhex(hx)
        if bytes(peek(a + k) for k in range(len(w))) != w:
            raise ValueError('unexpected code at %d - not the expected version of the game' % a)
    p0.prepare(peek)
    t0, t1 = p0.syms['dztab'] - 0x2000, p0.syms['dztab'] - 0x2000 + 39 * 9
    b12, e12 = bank(12), p0.extra_banks[12]
    if b12[:t0] != e12[:t0] or b12[t1:] != e12[t1:]:
        raise ValueError('hook code differs from this version\'s (rebuild with nexclash.py auto)')
    s10 = bank(10)[0x1000:0x1000 + len(p0.stub_extra)]
    if s10 != p0.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    for pg in range(NPL):
        a = bank(PLPG // 2 + pg // 2)[(pg & 1) * 8192:(pg & 1) * 8192 + 8192]
        e = p0.plane[PLPG + pg]
        for i in range(4, 8192, 8):
            idx = pg * 1024 + i // 8
            if idx >= P2LEN + DZLEN:
                ok = a[i] == e[i]
            else:                                   # the interiors, + painted paper (an outline)
                ga = DZ_BASE + idx - P2LEN if idx >= P2LEN else P2_BASE + idx
                ok = a[i] & e[i] == e[i] and not a[i] & ~e[i] & peek(ga)
            if not ok:
                raise ValueError('interior masks differ (plane page %d)' % (PLPG + pg))
    p = Dizzy1Patch(prof, colours=cmap)
    p.prepare(peek)
    changed = []
    for b in COLOUR_BANKS:
        new = p.extra_banks[b]
        if bank(b) != new:
            changed.append(b)
        d[off[b]:off[b] + 16384] = new
    return bytes(d), {'banks changed': changed, 'patterns': p.num_patterns, 'map entries': len(cmap)}


def auto(a, z80, sprites, say, rzxs, boot):
    """Sprite build (Layer 2) + boot checks + differential verification of each RZX + unit tests.
    `boot` = nexclash.py's _boot (the shared Boot line). Returns True when everything passed."""
    import hashlib
    import time
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    mem0 = _mem(z80)
    p = Dizzy1Patch(peek=mem0.__getitem__)
    say('Colours   : %s; enclosed paper solid black unless painted' % (
        '%d colour-map entries (docs/profiles/dizzy1_colours.json)' % len(p.colours) if p.colours
        else 'no colour map: default colours'))
    sc = static_check(p.rom_code, p.syms)
    say('Static    : hook code %d bytes at 0x%04X-0x%04X (alt ROM), no EXX / EX AF / IY / I / IM / DI / EI, '
        'nothing at 0x3D00: %s' % (len(p.rom_code), ROM_ORG, ROM_ORG + len(p.rom_code) - 1,
                                  'PASS' if not sc else 'FAIL %s' % sc[:3]))
    conv = zt.convert(z80, sprites, None, True, quiet=True, patch=p)
    boot(say, z80, sprites, p, conv)
    lb = layer2_boot(sprites, z80)
    say('Layer 2   : %s' % ('bank 16, visible, palette 0-15 (0 transparent), banks 16-18 clear: OK' if not lb
                            else 'MISMATCH %s' % lb[:3]))
    say('Sprites   : %s  %s  (objects on Layer 2, Dizzy = hardware sprites 0-3 in front, %d patterns; '
        'hooks in the alt ROM, shadow pages at slot 3)' % (os.path.basename(sprites), md5(sprites), p.num_patterns))
    ok = not sc and not lb
    states = []
    for r in rzxs:
        t = time.time()
        c, ex, st = verify(p, r, z80, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s %s (%.0fs): %d frames, plotter 2 calls %d converted / %d kept, Dizzy %d, '
            '%d figure pixels compared' % (os.path.basename(r), 'PASSED' if not fails else 'FAILED %s' % fails,
                                           time.time() - t, c['frames'], c['plotter 2 calls converted'],
                                           c['plotter 2 calls kept on the ULA'], c['Dizzy plotter calls'],
                                           c['figure pixels compared']))
        say('            ' + ', '.join('%s %d' % kv for kv in sorted(c.items()) if kv[0].startswith(('site', 'plotter 2 calls with'))))
        say('Speed     : hooks add %d T per frame (median of %d frames with hook work), %d max; a frame is '
            '69,888 T (28 MHz hook parts counted / 8)' % (c['extra T per frame (median)'], c['frames with hook work'],
                                                         c['extra T per frame (max)']))
        for k, v in ex.items():
            say('            example %s: %s' % (k, str(v)[:240]))
    if states:
        u, uex = unit_tests(p, states, z80)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d cases (modes, kept over figures, off-screen, effects, wipes, colour map), negative '
            'controls %d/%d -> %s' % (u['cases'], u['negative controls detected'], u['negative controls'],
                                      'PASSED' if not uf else 'FAILED %s' % uf))
        for k, v in uex[:5]:
            say('            example %s: %s' % (k, str(v)[:240]))
    if not ok:
        say('RESULT    : sprite build FAILED verification - do not use; send this folder to the agent')
    return ok


def _warn_ignored(rep):
    """Paint the map cannot hold: say so (Dean's outlines were silently dropped once, 2026-10-14)."""
    n = sum(v for k, v in rep.items() if '(ignored)' in k or 'kept default' in k)
    if n:
        print('WARNING: %d painted pixels were NOT used (lines above); paint only on a figure\'s pixels or '
              'the paper inside its graphic\'s bytes, with the sheet\'s current _layout.json' % n)


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.dizzy1', description='Dizzy 1: colour sheets / preview / colours / recolour')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX -> PAINTING / REFERENCE sheets (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', required=True, help='the snapshot (start state; adds figures from the code)')
    p.add_argument('-o', '--output', default='dizzy1')
    p.add_argument('--stop', type=int)
    p = sub.add_parser('preview', help='original | planned build, at chosen RZX frames')
    p.add_argument('z80')
    p.add_argument('rzx')
    p.add_argument('--at', required=True)
    p.add_argument('-o', '--output', default='dizzy1_preview.png')
    p = sub.add_parser('colours', help='painted sheet -> docs/profiles/dizzy1_colours.json')
    p.add_argument('png')
    p.add_argument('--layout')
    p.add_argument('-o', '--output', default=COLOURS)
    p = sub.add_parser('recolour', help='painted sheet -> <input>_painted.nex (the input stays untouched)')
    p.add_argument('nex', help='dizzy1_sprites.nex as built by nexclash.py auto')
    p.add_argument('colours', help='the painted dizzy1_PAINTING_SPRITES.png, or a colours .json')
    p.add_argument('--layout', help='the painting layout (default: next to the PNG)')
    p.add_argument('-o', '--output', help='default: dizzy1_sprites_painted.nex next to the input')
    a = ap.parse_args(argv)
    if a.cmd == 'sheet':
        comps, cap = capture(a.rzx, a.z80, a.stop)
        for png, n in sheets(comps, a.output, load_colours()):
            print('%d figures -> %s' % (n, png))
        for (pc, ret, conv), k in sorted(cap.calls.items()):
            print('  %s from %d: %d calls%s' % ('Dizzy plotter' if pc == DZ_ENTRY else 'plotter 2', ret, k,
                                                '' if conv else ' (stays on the ULA)'))
    elif a.cmd == 'preview':
        shots = preview(a.z80, a.rzx, [int(x) for x in a.at.split(',')], a.output)
        print('%d shots -> %s' % (len(shots), a.output))
    elif a.cmd == 'recolour':
        import hashlib
        from . import coloursheet as cs
        a.output = a.output or os.path.splitext(a.nex)[0] + '_painted.nex'
        if os.path.abspath(a.output) in (os.path.abspath(a.nex), os.path.abspath(a.nex).replace('_sprites', '')):
            raise SystemExit('recolour refused: the output would overwrite an original build')
        cj = os.path.splitext(a.output)[0] + '_colours.json'
        if a.colours.lower().endswith('.png'):
            lay = a.layout or os.path.splitext(a.colours)[0] + '_layout.json'
            try:
                ent, rep = cs.read(a.colours, lay, clear=True)
            except ValueError as e:
                raise SystemExit('recolour refused: %s' % e)
            for k, v in sorted(rep.items()):
                print('%s: %d' % (k, v))
            _warn_ignored(rep)
            cs.save(ent, cj, NOTE)
        else:
            cs.save(cs.load(a.colours), cj, NOTE)
        cmap = cs.load(cj)
        try:
            out, info = recolour(open(a.nex, 'rb').read(), cmap)
        except ValueError as e:
            raise SystemExit('recolour refused: %s' % e)
        open(a.output, 'wb').write(out)
        print('%d map entries, %d Dizzy sprite patterns, banks changed %s' % (
            info['map entries'], info['patterns'], info['banks changed'] or 'none'))
        print('-> %s  %s' % (a.output, hashlib.md5(out).hexdigest()))
        print('-> %s (put it in docs/profiles/dizzy1_colours.json to make it the build default)' % cj)
    else:
        from . import coloursheet as cs
        lay = a.layout or os.path.splitext(a.png)[0] + '_layout.json'
        ent, rep = cs.read(a.png, lay, clear=True)       # grey on an opaque pixel = transparent
        cs.save(ent, a.output, NOTE)
        for k, v in sorted(rep.items()):
            print('%s: %d' % (k, v))
        _warn_ignored(rep)
        print('-> %s' % a.output)


if __name__ == '__main__':
    _main()
