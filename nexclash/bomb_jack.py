"""Bomb Jack (Elite Systems, 1986, 48K) engine 'bomb_jack'. Additive module: reachable only through
is_bomb_jack(). Facts and design: games/bomb_jack.md; hooks: asm/bomb_jack_hooks.asm.
Interrupts on at the game's main loop, off at every site: the game draws in its IM2 handler (0xC38C)."""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x6E00          # the screen copy: written (0xD98F) before any read, proven by `scan`, see games/
SITES = {0xD94B: ('cdb5d9', 'e_mov', 0xCD, 'mov'),
         0xD6E3: ('cd82e5', 'e_bmb', 0xCD, 'bmb'),
         0xC860: ('cd82e5', 'e_bmb', 0xCD, 'bmb'),
         0xC68B: ('cd46e6', 'e_bgo', 0xCD, 'bgo'),
         0xEC21: ('210040', 'e_cls', 0xC3, 'cls'),
         0xC362: ('110040', 'e_go', 0xC3, 'go'),
         0xC457: ('211df1', 'e_gov', 0xC3, 'gov'),
         0xD8A8: ('cd89d7', 'e_tl', 0xCD, 'tile'),
         0xD8CF: ('cd89d7', 'e_tl', 0xCD, 'tile'),
         0xD8F5: ('cd89d7', 'e_tl', 0xCD, 'tile')}
INTERIORS = tuple(a + k for a in SITES for k in (1, 2))
ST, XOLD, YOLD, XNEW, YNEW, GFX, CNT = 62121, 62122, 62124, 62126, 62128, 62130, 62132
SAVESP, SAVEP, BOMB0 = 64985, 64989, 62227
NSPR, NOBJ = 110, 11
SLOT_B, SLOT_F = 64, 88
TILEC = 0x6E40             # hook byte: next tile slot; live from the clear to 0xD98F, which rewrites the copy
TILES = 0x7AA0             # 15 platform tiles, 6 bytes each, 8 pixels wide
TILEX, TILEY = 62163, 62165
TILE_PAL = 0
BG = 0x2000                 # screen address + BG = the clean copy
# Graphics: 96-byte blocks (16 rows x 3 pairs mask, gfx; odd rows right to left). 0x5B00.. is copied from
# 0x7300 by 0xEB81 at boot: blocks are read from the snapshot through this map.
RANGES = [(0x5B00, 12, 0x7300), (0x7AFA, 56, 0x7AFA), (0x92FA, 30, 0x92FA)]
BOMB_GFX = 0x92FA
LABELS = (0x959A, 0x971A)   # score labels: plotted by 0xE582 on the ULA, never a figure: no patterns
# One sprite palette, indices 1-15 (docs/COLOURS.md); the same bytes are in the asm's setup, checked by the setup case.
PALETTE = bytes((0, 0x00, 0xFF, 0x03, 0xE0, 0xFC, 0x1C, 0x14, 0xC3, 0x62, 0xB6, 0xF8, 0xF0, 0xEC, 0xE8, 0x60))
I_BLK, I_WHT, I_BLU, I_RED, I_YEL, I_GRN, I_DGR, I_MAG, I_PUR, I_GRY = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
# (first block, end): figure kind by eye -> (group, default ink, default fill). Defaults only: the colour map overrides.
KINDS = [(0x5B00, 0x5E00, 'flyers', I_MAG, I_WHT), (0x5E00, 0x5F80, 'jack', I_BLU, I_WHT),
         (0x7AFA, 0x83FA, 'jack', I_BLU, I_WHT), (0x83FA, 0x86FA, 'walkers', I_PUR, I_WHT),
         (0x86FA, 0x887A, 'saucers', I_GRN, I_BLK), (0x887A, 0x89FA, 'balls', I_YEL, I_BLK),
         (0x89FA, 0x8B7A, 'jack', I_BLU, I_WHT), (0x8B7A, 0x8CFA, 'balls', I_YEL, I_BLK),
         (0x8CFA, 0x8FFA, 'birds', I_DGR, I_WHT), (0x92FA, 0x941A, 'bombs', I_RED, I_BLK),
         (0x941A, 0x959A, 'coins', I_YEL, I_BLK), (0x971A, 0x995A, 'stars', I_WHT, I_BLK),
         (0x995A, 0x99BA, 'balls', I_YEL, I_BLK)]
TILE_INK, TILE_FILL = I_BLK, I_GRY
GROUPS = ['jack', 'walkers', 'flyers', 'birds', 'saucers', 'bombs', 'balls', 'coins', 'stars', 'platforms']
COLOURS = None              # set below, after _HERE
NOTE = ('Bomb Jack colours, read back from a painted bomb_jack_PAINTING_SPRITES.png. Key = G + address of a graphics '
        'byte (figures) or T + address of a platform tile byte, check = that byte, 8 nibbles = colours of its bits '
        '(0 = default), bit mask = painted transparent.')
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'bomb_jack_colours.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'bomb_jack.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_bomb_jack(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def block_rows(peek, src):
    """16 rows of (mask, gfx) 24-bit values, top down, of the block stored at src."""
    out = []
    for row in range(16):
        ms = gs = 0
        for k in range(3):
            b = k if row % 2 == 0 else 2 - k
            p = src + row * 6 + k * 2
            ms |= peek(p) << (8 * (2 - b))
            gs |= peek(p + 1) << (8 * (2 - b))
        out.append((ms, gs))
    return out


def kind_of(addr):
    for lo, hi, group, ink, fill in KINDS:
        if lo <= addr < hi:
            return group, ink, fill
    return 'stars', I_WHT, I_BLK


def block_key(addr, row, col):
    """Colour-map key and bit of a block's pixel: the graphics byte it comes from."""
    b = col // 8
    k = b if row % 2 == 0 else 2 - b
    return 'G%04X' % (addr + row * 6 + k * 2 + 1), col % 8


def map_nibble(cmap, key, bit, check, default):
    """The pixel's palette index: the map's if its check byte is the graphics byte, 0 if painted transparent."""
    e = cmap.get(key)
    if e is None or e[0] != check:
        return default
    if len(e) > 3 and e[3] & (0x80 >> bit):
        return 0
    return e[2][bit] or default


def block_pixels(peek, addr, src, cmap):
    """24x16: (shape nibble: 1 gfx, 2 mask 0, 0 transparent; colour nibble) by [row][col]."""
    _g, ink, fill = kind_of(addr)
    rows = block_rows(peek, src)
    out = []
    for j, (m, g) in enumerate(rows):
        line = []
        for k in range(24):
            bit = 23 - k
            key, kb = block_key(addr, j, k)
            chk = g >> (8 * (2 - k // 8)) & 255
            if g >> bit & 1:
                line.append((1, map_nibble(cmap, key, kb, chk, ink)))
            elif not m >> bit & 1:
                line.append((2, map_nibble(cmap, key, kb, chk, fill)))
            else:
                line.append((0, 0))
        out.append(line)
    return out, rows


def _window(px, first):
    """16x16 from column `first`: (shape nibbles, colour nibbles)."""
    sh, co = [], []
    for line in px:
        for k in range(first, first + 16):
            a, b = line[k] if k < 24 else (0, 0)
            sh.append(a)
            co.append(b)
    return tuple(sh), tuple(co)


def tile_window(peek, t, cmap):
    sh, co = [], []
    for r in range(16):
        v = peek(TILES + 6 * t + r) if r < 6 else None
        for k in range(16):
            if v is None or k >= 8:
                sh.append(0)
                co.append(0)
            elif v >> (7 - k) & 1:
                sh.append(1)
                co.append(map_nibble(cmap, 'T%04X' % (TILES + 6 * t + r), k, v, TILE_INK))
            else:
                sh.append(2)
                co.append(map_nibble(cmap, 'T%04X' % (TILES + 6 * t + r), k, v, TILE_FILL))
    return tuple(sh), tuple(co)


def _bytes(w):
    return bytes(w[k] << 4 | w[k + 1] for k in range(0, 256, 2))


def build_patterns(peek, cmap=None):
    """-> (pattern bytes in colour, shape patterns for the checks, blocks table 4 x 98, tile patterns 15, count)."""
    cmap = cmap or {}
    seen, pats, table = {}, [], bytearray()

    def pid(w):
        if w not in seen:
            seen[w] = len(pats)
            pats.append(w)
        return seen[w]
    for base, n, src in RANGES:
        for i in range(n):
            addr = base + 96 * i
            if LABELS[0] <= addr < LABELS[1]:
                table += b'\xFF\xFF\xFF\xFF'
                continue
            px, rows = block_pixels(peek, addr, src + 96 * i, cmap)
            used = 0
            for m, g in rows:
                used |= (~m & 0xFFFFFF) | g
            s = format(used, '024b')
            first, last = (s.find('1'), s.rfind('1')) if used else (0, 0)
            a = pid(_window(px, first))
            b = pid(_window(px, first + 16)) if last - first + 1 > 16 else 0xFF
            table += bytes((a, first, b, 0))
    tiles = bytes(pid(tile_window(peek, t, cmap)) for t in range(15))
    if len(pats) > 128:
        raise ValueError('%d sprite patterns: more than fit' % len(pats))
    return (b''.join(_bytes(c) for _s, c in pats), b''.join(_bytes(s) for s, _c in pats), bytes(table), tiles, len(pats))


class BombJackPatch:
    name = 'Bomb Jack figures and bombs -> hardware sprites (altrom, plots on a blank figure)'

    def __init__(self, prof=None, rom_code=None, colours=None):
        self.colours = load_colours() if colours is None else colours
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True         # 0x5B00 holds graphics in this game: never the tail
        self.keep_printer_buffer = True         # NEXLOAD leaves its own bytes there; the snapshot's go back
        self.tail_addr = TAIL_ADDR
        self.max_tail = 200
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        # The WHOLE alt ROM image comes from the build (Sinclair's 48K ROM + hooks): the Next's ROM3 is NextZXOS's,
        # with no STMT-RET at 0x1B76, and this snapshot is in the middle of a BASIC line (PAUSE 0: CLS: RANDOMIZE USR).
        self.altrom = (0x2000, 0x4000)
        from .build import rom48
        rom = rom48()
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[:0x2000]))
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        self.sites = []
        for a, (old, sym, op, _k) in SITES.items():
            self.sites.append((a, bytes.fromhex(old), bytes([op]) + self.syms[sym].to_bytes(2, 'little')))
        self.extra_banks = {}
        self.pats = None
        self.page = None
        self.num_patterns = 128

    def fill(self, peek):
        """Patterns + block table from the snapshot's memory (the alt ROM page)."""
        from .build import rom48
        self.pats, self.shapes, table, tiles, self.npat = build_patterns(peek, self.colours)
        code = bytearray(self.rom_code)
        o = self.syms['blocks'] - ROM_ORG
        code[o:o + len(table)] = table
        o = self.syms['tiles'] - ROM_ORG
        code[o:o + len(tiles)] = tiles
        self.code = bytes(code)
        page = bytearray(rom48()[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
        if page[0x39FF - 0x2000] != 0xFF or page[0x3A00 - 0x2000] != 0xFF:
            raise ValueError('the IM 2 vector at 0x39FF must stay 0xFFFF')
        self.page = bytes(page)

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Bomb Jack patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.fill(lambda a: ram[a - 0x4000])
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        low = self.altrom_low[1] if self.altrom_low else bytes(8192)
        self.extra_banks = {11: self.pats + bytes(16384 - len(self.pats)), 12: self.page + low}


class BombJackPlain:
    """The plain build: no hook, but the same whole alt ROM image, or the BASIC line dies in NextZXOS's ROM3."""
    name = 'Bomb Jack, plain: Sinclair 48K ROM in the alt ROM'

    def __init__(self):
        from .build import rom48
        rom = rom48()
        self.stub_extra = b''
        self.setup_call = None
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.keep_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 200
        self.regblock = ROM_ORG
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[:0x2000]))
        self.page = bytes(rom[0x2000:0x4000])
        self.sites = []
        self.extra_banks = {}
        self.num_patterns = 0

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Bomb Jack patch expects the 48K snapshot')
        self.extra_banks = {12: self.page + self.altrom_low[1]}


# ---------------------------------------------------------------------------------------------
# Next-side model
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, pats):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = pats
        self.events = []
        self.pal = {}
        self.palx = 0
        self.tile = 0

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x40:
            self.palx = val
        elif reg == 0x41:
            self.pal[self.palx] = val
            self.palx = (self.palx + 1) & 255
        self.events.append((reg, val))

    def clone_attr(self):
        return [list(a) for a in self.attr]


_PCACHE = {}


def pattern_rows(pat, n):
    """Pattern n -> [(opaque 16 bits, ink 16 bits)] x 16."""
    k = (id(pat), n)
    v = _PCACHE.get(k)
    if v is None:
        v = []
        base = n * 128
        for j in range(16):
            op = ink = 0
            for i in range(16):
                b = pat[base + j * 8 + i // 2]
                x = b >> 4 if i % 2 == 0 else b & 15
                op = op << 1 | (x != 0)
                ink = ink << 1 | (x == 1)
            v.append((op, ink))
        _PCACHE[k] = v
    return v


def sprite_of(a):
    """(X, Y, palette offset, pattern) in ULA coordinates, or None when hidden."""
    if not a[3] & 0x80:
        return None
    x = a[0] + (a[2] & 1) * 256 - 32
    y = a[1] + (a[4] & 1) * 256 - 32
    n = (a[3] & 0x3F) * 2 + (1 if a[4] & 0x40 else 0)
    return x, y, a[2] >> 4, n


def scr_addr(y, col):
    return 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | col


def paint(masks, attr, pat):
    """Add a visible sprite to {screen byte: (opaque, ink)}; later calls cover earlier ones."""
    s = sprite_of(attr)
    if s is None:
        return
    x, y, _p, n = s
    rows = pattern_rows(pat, n)
    for j in range(16):
        op, ink = rows[j]
        if not op:
            continue
        yy = y + j
        if not 0 <= yy < 192:
            continue
        sh = 24 - (x & 7) - 16
        op24, ink24 = op << sh, ink << sh
        col = x >> 3
        for b in range(3):
            o8 = op24 >> (16 - 8 * b) & 255
            if not o8:
                continue
            i8 = ink24 >> (16 - 8 * b) & 255
            a = scr_addr(yy, (col + b) & 31)
            po, pi = masks.get(a, (0, 0))
            masks[a] = (po | o8, (pi & ~o8) | i8)


# ---------------------------------------------------------------------------------------------
# Event runner: original and patched from one state
# ---------------------------------------------------------------------------------------------

def _machine(Sim, mem, regs, ns, slot='o'):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot)
    z80n.install(sim, ns.nextreg)

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.events.append(('out', port, value))
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=120000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR
# after the move routine (0xD94E): A, F, B, C differ (they end on the last graphics pair). A and F are written
# at 0xD960-0xD963 before any read; BC is only decremented by LDI until its next load, and the erase path's EXX can
# carry it to BC': games/bomb_jack.md. The lockstep run frees BC and BC' only, counts frames where they differ, and
# would see any use of them as a register, RAM or IN-count difference.
DEAD_MOV = {0, 1, 2, 3}


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def _overlays(get, alt, psite, bgval=None):
    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            if v is not None:
                return v
            if bgval is not None and 0x6000 <= a < 0x7800:
                return bgval
            return get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', 0) + 1
            else:
                s.ov[a] = v
    return O, P


def event(patch, pc, get, R, ns, alt, Sim, seen=None):
    """One site from this state. -> list of failures (tuples), figure pixels checked."""
    kind = SITES[pc][3]
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    sp0 = R[12]
    nxt = {'cls': 0xEC24, 'go': 0xC365, 'gov': 0xC45A}.get(kind, pc + 3)

    def stop(r):
        return r[24] == nxt and r[12] == sp0
    O, P = _overlays(get, alt, psite)
    o, p = O(), P()
    tile0 = ns.tile
    if kind in ('tile', 'cls'):
        p.ov[TILEC] = ns.tile
    so = _machine(Sim, o, list(R), NextState(ns.pat), 'o')
    before = ns.clone_attr()
    ns.events = []
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if not _run(so, stop) or not _run(sp_, stop):
        return [('did not return',)], 0
    f = []
    if kind in ('tile', 'cls'):
        ns.tile = p.ov[TILEC]
    ro, rp = so.registers, sp_.registers
    dead = DEAD_MOV if kind == 'mov' else ()
    diff = [i for i in CMP if ro[i] != rp[i] and i not in dead]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access in hook',))
    if R[26]:
        f.append(('interrupts on at the site',))
    dstack = range(sp0 - 64, sp0)
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if a != TILEC and a not in dstack and not (kind == 'mov' and 0x4000 <= a < 0x5800) and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    npx = 0
    w = lambda m, a: m[a] | m[a + 1] << 8
    if kind == 'mov':
        state = get(ST)
        slot = SLOT_F + 2 * (NOBJ - get(CNT))
        for a in p.ov:
            if 0x4000 <= a < 0x5800 and p.ov[a] != get(a + BG) and known_block(get):
                f.append(('patched ULA is not the clean copy', a))
                break
        if state:
            masks = {}
            paint(masks, ns.attr[slot], ns.pat)
            paint(masks, ns.attr[slot + 1], ns.pat)
            scr = [a for a in o.ov if 0x4000 <= a < 0x5800]
            if {a for a in p.ov if 0x4000 <= a < 0x5800} != set(scr):
                f.append(('screen bytes written differ',))
            if state >= 3 or not known_block(get):
                if masks:
                    f.append(('sprite visible with nothing plotted',))
                if state < 3:
                    if any(o[a] != p[a] for a in scr):
                        f.append(('unknown graphics not left on the ULA',))
            else:
                for a in scr:
                    m_op, m_ink = masks.get(a, (0, 0))
                    if o.ov[a] != (get(a + BG) & ~m_op & 255) | m_ink:
                        f.append(('figure pixels differ from the original plot', a, o.ov[a]))
                        break
                    npx += bin(m_op).count('1')
                if any(a not in o.ov for a in masks):
                    f.append(('sprite pixels outside the plot',))
                key = w(o, GFX) if False else (get(GFX), get(XNEW) & 7)
                if seen is None or key not in seen:      # solid or see-through: the copy reads as all ones
                    if seen is not None:
                        seen.add(key)
                    Oc, _ = _overlays(get, alt, psite, 0xFF)
                    oc = Oc()
                    sc = _machine(Sim, oc, list(R), NextState(ns.pat), 'c')
                    if _run(sc, stop):
                        for a in scr:
                            m_op, m_ink = masks.get(a, (0, 0))
                            if oc[a] != (0xFF & ~m_op) | m_ink:
                                f.append(('solid pixels differ from the mask', a))
                                break
                if ns.attr[slot][2] >> 4:
                    f.append(('palette offset is not 0', ns.attr[slot][2] >> 4))
        changed = [i for i in range(128) if ns.attr[i] != before[i] and i not in (slot, slot + 1)]
    elif kind == 'bmb':
        slot = ((get(SAVEP) | get(SAVEP + 1) << 8) - BOMB0) // 48 + SLOT_B
        if not SLOT_B <= slot < SLOT_B + 24:
            f.append(('bomb save pointer out of range', get(SAVEP)))
            return f, 0
        masks = {}
        paint(masks, ns.attr[slot], ns.pat)
        if not masks:
            f.append(('bomb sprite not visible', slot))
        for a in o.ov:
            if 0x4000 <= a < 0x5800:
                m_op, m_ink = masks.get(a, (0, 0))
                if o.ov[a] != (get(a + BG) & ~m_op & 255) | m_ink:
                    f.append(('bomb pixels differ from the original plot', a))
                    break
                npx += bin(m_op).count('1')
        changed = [i for i in range(128) if ns.attr[i] != before[i] and i != slot]
    elif kind == 'tile':
        changed = [i for i in range(128) if ns.attr[i] != before[i] and i != tile0]
        scr = [a for a in o.ov if 0x4000 <= a < 0x5800]
        if tile0 >= 64 or R[0] >= 15:
            if ns.tile != tile0:
                f.append(('tile slot used without a slot or a tile',))
        else:
            if ns.tile != tile0 + 1:
                f.append(('tile counter not advanced',))
            masks = {}
            paint(masks, ns.attr[tile0], ns.pat)
            if {a for a in masks} != set(scr):
                f.append(('tile sprite is not where the tile is', tile0))
            for a in scr:
                m_op, m_ink = masks.get(a, (0, 0))
                if m_op != 255 or o.ov[a] != m_ink:
                    f.append(('tile pixels differ from the original plot', a))
                    break
                npx += 8
            if ns.attr[tile0][2] >> 4 != TILE_PAL:
                f.append(('tile palette offset',))
    elif kind == 'bgo':
        slot = ((get(SAVEP) | get(SAVEP + 1) << 8) - BOMB0) // 48 + SLOT_B
        if sprite_of(ns.attr[slot]) is not None:
            f.append(('bomb sprite still visible after collection', slot))
        changed = [i for i in range(128) if ns.attr[i] != before[i] and i != slot]
    else:
        if kind == 'cls':
            if any(sprite_of(a) for a in ns.attr[:NSPR]):
                f.append(('sprite visible after the clear',))
            if ns.nr.get(0x15, 1) & 1:
                f.append(('sprite layer on after the clear',))
            if ns.tile:
                f.append(('tile counter not reset',))
        elif kind == 'gov':
            if ns.nr.get(0x15, 1) & 1:
                f.append(('sprite layer on with GAME OVER up',))
        elif not ns.nr.get(0x15, 0) & 1:
            f.append(('sprite layer off after the level is shown',))
        changed = [] if kind == 'cls' else [i for i in range(128) if ns.attr[i] != before[i]]
    if changed:
        f.append(('other sprites changed', changed[:4]))
    return f, npx


def known_block(get):
    """Is (GFX) + variant one of the 98 blocks? The hook's own rule, stated independently."""
    a = (get(GFX) | get(GFX + 1) << 8) + 48 * (get(XNEW) & 6)
    return (any(b <= a < b + n * 96 and (a - b) % 96 == 0 for b, n, _ in RANGES)
            and not LABELS[0] <= a < LABELS[1])


def _rw():
    from .dizzy6 import _rw_simulator
    if not hasattr(_rw, 'c'):
        _rw.c = _rw_simulator()
    return _rw.c


def _prepare(patch, peek):
    if patch.page is None:
        patch.fill(peek)


def _snapshot_peek(z80):
    from skoolkit.snapshot import Snapshot
    m = Snapshot.get(z80).ram(-1)
    return lambda a: m[a - 0x4000]


def verify(patch, rzx_path, stop=None, collect=0, progress=None, z80=None):
    """Replay the RZX (original game); at every site run original and patched code from the same
    state. Only the opcodes at sites and their interiors are wrapped. -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    c = collections.Counter()
    ex = collections.defaultdict(list)
    st = {'frame': 0, 'mem': None}
    ns = NextState(patch.shapes)
    states = []
    seen = set()
    site_old = {a + k: v for a, old, new in patch.sites for k, v in enumerate(old)}
    alt = _alt(patch)
    INTER = set(INTERIORS)

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))
    Rw = _rw()

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            st['mem'] = mem
            get = mem.__getitem__

            def wrap(op, fn):
                def g():
                    pc = R[24]
                    if pc in SITES and mem[pc] == op:
                        kind = SITES[pc][3]
                        c['site %04X' % pc] += 1
                        if collect and c['collected ' + kind] < collect:
                            c['collected ' + kind] += 1
                            states.append((pc, list(R), bytes(mem), ns.clone_attr()))
                        fl, npx = event(patch, pc, get, R, ns, alt, Rw, seen)
                        c[kind] += 1
                        if kind == 'mov':
                            s = get(ST)
                            c['mov state 0' if not s else 'mov plot' if s < 3 else 'mov erase'] += 1
                            if s and s < 3:
                                g = (get(GFX) | get(GFX + 1) << 8) + 48 * (get(XNEW) & 6)
                                if not known_block(get):
                                    c['mov unknown graphics'] += 1
                                    c['  unknown %04X state %d obj %d' % (g, s, 11 - get(CNT))] += 1
                                else:
                                    c['  block %04X' % g] += 1
                        c['figure pixels compared'] += npx
                        for k in fl:
                            fail('%s: %s' % (kind, k[0]), k[1:])
                    elif pc in INTER:
                        fail('jump into a patched instruction', (pc,))
                    fn()
                return g
            for op in {0xCD, 0x21, 0x11} | {old[k] for a, old, new in patch.sites for k in (1, 2)}:
                ops[op] = wrap(op, ops[op])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        m = st['mem']
        if m is not None and st['frame'] > 1:
            for a, v in site_old.items():
                if m[a] != v and m[a - 1] != 0:
                    fail('game wrote a patch site', (a,))
                    break
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
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Lockstep: the whole patched game next to the original, on the recording's IN values
# ---------------------------------------------------------------------------------------------

def recording(rzx_path):
    """-> (embedded snapshot, input recording)."""
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    snap, rec = None, None
    for b in parse_rzx(rzx_path):
        if isinstance(b.obj, Snapshot) and snap is None:
            snap = b.obj
        elif getattr(b.obj, 'frames', None) is not None and rec is None:
            rec = b.obj
    return snap, rec


def composite(ula, attrs, pat, nspr=NSPR):
    """ULA pixels (6144 bytes, 0x4000..) with the visible sprites over them, as ink bits."""
    masks = {}
    for i in range(nspr):
        paint(masks, attrs[i], pat)
    out = bytearray(ula)
    for a, (op, ink) in masks.items():
        o = a - 0x4000
        out[o] = (out[o] & ~op & 255) | ink
    return out


def ns_dx(patch, a):
    """Column offset of the sprite's pattern in its 24-pixel figure: at most 8, boxes allow for it."""
    return 8 if a[0] & 7 else 0


def lockstep(patch, rzx_path, stop=None, on_frame=None, progress=None, trace_frame=None):
    """Both games, frame by frame, same fetch counts and IN values. Hook instructions are not counted
    (they roll R back), so the two stay in step exactly when the game's logic has not changed. Each
    frame end: registers, all RAM outside the ULA pixels, dead stack, and original ULA = patched ULA +
    sprites, where any difference must lie inside a figure's box: the original's later plot, bomb restore or
    fuse plot cuts the figure until its next plot; the sprite stays whole (per-event checks prove its pixels). -> Counter (failures end in !), examples."""
    from .machine import Machine
    from . import z80n
    c, ex = collections.Counter(), collections.defaultdict(list)
    snap, rec = recording(rzx_path)
    mo = Machine(snap)
    regs0 = list(mo.sim.registers)
    ram0 = bytes(mo.sim.memory)
    alt = _alt(patch)
    mo_ = bytearray(ram0)
    mp_ = bytearray(alt[:0x4000]) + bytearray(ram0[0x4000:])
    if bytes(mp_[0x4000:0x6000]) != bytes(ram0[0x4000:0x6000]):
        c['start state!'] += 1
    for a, old, new in patch.sites:
        mp_[a:a + len(new)] = new
    Rw = _rw()
    so, sp = Rw(mo_, {}), Rw(mp_, {})
    so.registers[:] = regs0
    sp.registers[:] = regs0
    ns = NextState(patch.shapes)
    z80n.install(sp, ns.nextreg)
    data = rec.data
    feed = [0, 0]

    class Feed:
        def __init__(s, i):
            s.i = i

        def read_port(s, regs, port):
            v = data[feed[s.i]]
            feed[s.i] += 1
            return v

        def write_port(s, regs, port, value, *x):
            pass
    so.set_tracer(Feed(0))
    sp.set_tracer(Feed(1))
    Ro, Rp = so.registers, sp.registers
    opso, opsp = so.opcodes, sp.opcodes
    lo, hi = ROM_ORG, patch.regblock
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))} | {TILEC}
    pat = patch.shapes
    n = 0
    dead = set()        # stack bytes the hooks themselves wrote

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((n,) + tuple(info))
    for fr in rec.frames:
        if not fr.fetch_counter:
            continue
        n += 1
        feed[0] = feed[1] = fr.start
        fc = fr.fetch_counter
        pco = Ro[24]
        tro = [] if trace_frame == n else None
        while fc > 0:
            pco = Ro[24]
            if tro is not None:
                tro.append((pco, tuple(Ro[:13])))
            op = mo_[pco]
            if op in (0xDD, 0xFD):
                r0 = Ro[15]
                opso[op]()
                fc -= 2 - ((Ro[15] ^ r0) % 2)
            else:
                opso[op]()
                fc -= 2 if op in (0xCB, 0xED) else 1
        fc = fr.fetch_counter
        pcp = Rp[24]
        trp = [] if trace_frame == n else None
        while fc > 0:
            pcp = Rp[24]
            op = mp_[pcp]
            if lo <= pcp < hi:
                r0, t0 = Rp[15], Rp[25]
                opsp[op]()
                Rp[15] = r0
                c['hook T'] += Rp[25] - t0
                dead.add(Rp[12])
                dead.add(Rp[12] + 1)
                continue
            if trp is not None:
                trp.append((pcp, tuple(Rp[:13])))
            if op in (0xDD, 0xFD):
                r0 = Rp[15]
                opsp[op]()
                fc -= 2 - ((Rp[15] ^ r0) % 2)
            else:
                opsp[op]()
                fc -= 2 if op in (0xCB, 0xED) else 1
        c['frames'] += 1
        if trace_frame == n:
            ex['trace'] = (tro, trp)
        if feed[0] != fr.end or feed[1] != fr.end:
            fail('IN values not used up', (feed[0] - fr.start, feed[1] - fr.start, fr.end - fr.start))
            return c, dict(ex)
        diff = [i for i in CMP if Ro[i] != Rp[i] and i not in (2, 3, 18, 19)]
        if diff:
            fail('registers differ', (diff, [Ro[i] for i in diff], [Rp[i] for i in diff], hex(Ro[24])))
            if c['registers differ!'] > 20:
                return c, dict(ex)
        if Ro[2] != Rp[2] or Ro[3] != Rp[3] or Ro[18] != Rp[18] or Ro[19] != Rp[19]:
            c['BC differs at a frame end (dead)'] += 1
        spr = Rp[12]
        real_sp = 0xFF00 <= spr or spr < 0x7000     # game's stacks; else SP is a data pointer in a plot
        if mo_[0x5800:] != mp_[0x5800:]:
            bad = [a for a in range(0x5800, 65536) if mo_[a] != mp_[a] and a not in site_bytes and a not in dead]
            if bad:
                fail('RAM differs', (len(bad), [hex(a) for a in bad[:4]], hex(Ro[24])))
                if c['RAM differs!'] > 20:
                    return c, dict(ex)
        if not real_sp:
            c['frames ending inside a plot (picture not compared)'] += 1
            if progress and n % 1000 == 0:
                progress(n, c)
            for R, mem, sim, pc in ((Ro, mo_, so, pco), (Rp, mp_, sp, pcp)):
                R[25] = 0
                if R[26]:
                    if mem[pc] == 0x76:
                        R[24] = (R[24] + 1) % 65536
                    sim.accept_interrupt(R, mem, 0)
            if stop and n >= stop:
                break
            continue
        ula_o = bytes(mo_[0x4000:0x5800])
        comp = composite(mp_[0x4000:0x5800], ns.attr, pat, NSPR if ns.nr.get(0x15, 1) & 1 else 0)
        if comp == ula_o:
            c['frames picture identical'] += 1
        else:
            boxes = []
            for o in range(NOBJ):
                sl = SLOT_F + 2 * o
                s = sprite_of(ns.attr[sl])
                if s:
                    boxes.append((s[0] - ns_dx(patch, ns.attr[sl]), s[1]))
                d = 63892 + 11 * o
                if mp_[d]:
                    boxes.append((mp_[d + 5] & 0xF8, mp_[d + 7] & 0xFE))
                    boxes.append((mp_[d + 1] & 0xF8, mp_[d + 3] & 0xFE))
            bad = 0
            for off in range(6144):
                if comp[off] != ula_o[off]:
                    a = off + 0x4000
                    y = (a >> 5 & 0xC0) | (a >> 8 & 7) | (a >> 2 & 0x38)
                    x = (a & 31) * 8
                    if not any(b[0] <= x < b[0] + 24 and b[1] <= y < b[1] + 16 for b in boxes):
                        bad += 1
            if bad and (0xEC21 <= Rp[24] < 0xEC38 or Rp[24] == 0xC36B):
                c['frames ending inside the clear or the reveal'] += 1
            elif bad:
                c['frames picture differs outside every figure box!'] += 1
                c['bytes outside the boxes'] += bad
                if len(ex['picture']) < 8:
                    ex['picture'].append((n, bad, hex(Rp[24])))
            else:
                c['frames picture differs inside figure boxes only'] += 1
        if on_frame:
            on_frame(n, mo_, mp_, ns)
        if progress and n % 1000 == 0:
            progress(n, c)
        # interrupt, as rzxplay
        for R, mem, sim, pc in ((Ro, mo_, so, pco), (Rp, mp_, sp, pcp)):
            R[25] = 0
            if R[26]:
                if mem[pc] == 0x76:
                    R[24] = (R[24] + 1) % 65536
                sim.accept_interrupt(R, mem, 0)
        if stop and n >= stop:
            break
    return c, dict(ex)


# ---------------------------------------------------------------------------------------------
# Unit tests: paths and graphics the recordings may not reach; broken builds
# ---------------------------------------------------------------------------------------------

def _case(pt, pc, R, mem, attrs, alt, Sim, seen=None):
    ns = NextState(pt.shapes)
    ns.attr = [list(a) for a in attrs]
    fl, npx = event(pt, pc, mem.__getitem__, R, ns, alt, Sim, seen)
    return fl, npx, ns


def unit_tests(patch, states, neg=None):
    """states from verify(collect=n): (pc, registers, 64K memory, sprite attrs)."""
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    mov = [s for s in states if s[0] == 0xD94B]
    bmb = [s for s in states if s[0] in (0xD6E3, 0xC860)]
    bgo = [s for s in states if s[0] == 0xC68B]
    cls = [s for s in states if s[0] == 0xEC21]

    def tally(name, fl, want=None):
        ok = not fl if want is None else want(fl)
        c['%s %s' % (name, 'ok' if ok else 'FAIL!')] += 1
        if not ok and c['  fail ' + name] < 3:
            c['  fail ' + name] += 1
            c['  %s %s' % (name, str(fl[:2])[:150])] += 1

    if mov:
        pc, R, m0, attrs = mov[0]

        def setup(gfx, x, y, ox=None, oy=None, state=1, cnt=11):
            m = bytearray(m0)
            m[ST] = state
            m[XNEW], m[YNEW] = x, y
            m[XOLD], m[YOLD] = x if ox is None else ox, y if oy is None else oy
            m[GFX], m[GFX + 1] = gfx & 255, gfx >> 8
            m[CNT] = cnt
            return m
        swapped = m0[63355]
        for base, n, _s in RANGES:
            for i in range(n):
                g = base + 96 * i
                if LABELS[0] <= g < LABELS[1] or (swapped and g in (0x887A, 0x995A)):
                    continue
                for col, y in ((1, 0), (13, 88), (25, 174), (3, 166)):
                    v = i % 4
                    x = col * 8 + 2 * v + (i & 1 if False else 0)
                    m = setup(g - 96 * v, x, y)
                    fl, _n, _ns = _case(patch, pc, list(R), m, attrs, alt, Sim)
                    tally('every block x edges', fl)
        # the move paths: new against old position, odd coordinates, every slot
        g = 0x7F7A
        for dx in (0, 2, -2, 6, -6):
            for dy in (0, 2, -2, 4, -4):
                for x, y in ((64, 64), (65, 67)):
                    m = setup(g - 48 * (x & 6), x, y, x + dx, y + dy)
                    m[GFX], m[GFX + 1] = g & 255, g >> 8
                    fl, _n, _ns = _case(patch, pc, list(R), m, attrs, alt, Sim)
                    tally('move paths', fl)
        for cnt in range(1, 12):
            m = setup(0x7F7A, 64, 64, cnt=cnt)
            fl, _n, _ns = _case(patch, pc, list(R), m, attrs, alt, Sim)
            tally('slots', fl)
        for s in (2, 3, 4, 255):
            at = [list(a) for a in attrs]
            at[SLOT_F][3] |= 0x80
            at[SLOT_F + 1][3] |= 0x80
            m = setup(0x7F7A, 64, 64, state=s)
            fl, _n, ns = _case(patch, pc, list(R), m, at, alt, Sim)
            tally('states 2, 3+', fl)
            if s >= 3 and (sprite_of(ns.attr[SLOT_F]) or sprite_of(ns.attr[SLOT_F + 1])):
                tally('states 2, 3+', ['sprite not hidden'])
        # 0xD917 has swapped the two coin images in RAM
        m = setup(0x887A, 64, 64)
        for k in range(96):
            m[0x887A + k], m[0x995A + k] = m[0x995A + k], m[0x887A + k]
        m[63355] = 1 - m[63355]
        fl, _n, _ns = _case(patch, pc, list(R), m, attrs, alt, Sim)
        tally('coin images swapped', fl)
        m = setup(0x7F7A, 64, 64, state=0)
        fl, _n, _ns = _case(patch, pc, list(R), m, attrs, alt, Sim)
        tally('state 0', fl)
        for g in (0x2710, 0x2770, 0x5F80, 0x8FFA, 0x92F9, 0x99BA, 0x7AFB, 0xC000, 0x959A):
            m = setup(g, 64, 64)
            fl, _n, _ns = _case(patch, pc, list(R), m, attrs, alt, Sim)
            tally('unknown graphics stay on the ULA', fl)
    if bmb:
        pc, R, m0, attrs = bmb[0]
        for idx in (0, 1, 12, 23):
            for frame in range(3):
                for x, y in ((0, 0), (192, 176), (96, 44), (24, 132)):
                    m = bytearray(m0)
                    p = BOMB0 + 48 * idx
                    m[SAVEP], m[SAVEP + 1] = p & 255, p >> 8
                    m[XNEW], m[YNEW] = x | frame * 2, y
                    m[GFX], m[GFX + 1] = BOMB_GFX & 255, BOMB_GFX >> 8
                    m[63362] = 8
                    r = list(R)
                    fl, _n, _ns = _case(patch, pc, r, m, attrs, alt, Sim)
                    tally('bomb plots', fl)
        for p in (BOMB0 - 48, BOMB0 + 48 * 24):
            m = bytearray(m0)
            m[SAVEP], m[SAVEP + 1] = p & 255, p >> 8
            ns = NextState(patch.shapes)
            ns.attr = [list(a) for a in attrs]
            before = ns.clone_attr()
            psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
            O, P = _overlays(m.__getitem__, alt, psite)
            q = P()
            sim = _machine(Sim, q, list(R), ns, 'p')
            _run(sim, lambda r: r[24] == pc + 3 and r[12] == R[12])
            tally('bomb pointer out of range: no sprite touched', [] if ns.attr == before else ['changed'])
    # platform tiles: every id, slot edges, tile counter full
    tl = [s for s in states if s[0] in (0xD8A8, 0xD8CF, 0xD8F5)]
    if tl:
        pc, R, m0, attrs = tl[0]
        for t in range(16):
            for count in (0, 63, 64):
                for x, y in ((5, 38), (193, 148)):
                    m = bytearray(m0)
                    m[TILEX], m[TILEX + 1], m[TILEY], m[TILEY + 1] = x, 0, y, 0
                    r = list(R)
                    r[0] = t
                    ns = NextState(patch.shapes)
                    ns.attr = [list(a) for a in attrs]
                    ns.tile = count
                    if t >= 15:
                        continue
                    fl, _n = event(patch, pc, m.__getitem__, r, ns, alt, Sim)
                    tally('platform tiles', fl)
    if bgo:
        pc, R, m0, attrs = bgo[0]
        for idx in (0, 23):
            m = bytearray(m0)
            p = BOMB0 + 48 * idx
            m[SAVEP], m[SAVEP + 1] = p & 255, p >> 8
            at = [list(a) for a in attrs]
            at[SLOT_B + idx][3] |= 0x80
            fl, _n, _ns = _case(patch, pc, list(R), m, at, alt, Sim)
            tally('bomb collected', fl)
    go = [s for s in states if s[0] == 0xC362]
    if go:
        pc, R, m0, attrs = go[0]
        fl, _n, _ns = _case(patch, pc, list(R), bytearray(m0), attrs, alt, Sim)
        tally('level shown', fl)
    if cls:
        pc, R, m0, attrs = cls[0]
        at = [list(a) for a in attrs]
        for i in range(NSPR):
            at[i][3] |= 0x80
        fl, _n, _ns = _case(patch, pc, list(R), bytearray(m0), at, alt, Sim)
        tally('clear with every sprite up', fl)
    # the IM 2 vector the game reads from the ROM
    tally('IM 2 vector 0x39FF', [] if alt[0x39FF] == 0xFF and alt[0x3A00] == 0xFF else ['vector changed'])
    tally('setup', _setup_case(patch))
    tally('colour patterns match the shapes', _colour_case(patch))
    if neg:
        for name, q in neg:
            hit = False
            qalt = _alt(q)
            for pc, R, m0, attrs in states:
                fl, _n, _ns = _case(q, pc, list(R), bytearray(m0), attrs, qalt, Sim)
                hit = hit or bool(fl)
            c['negative %s (unit states) %s' % (name, 'detected' if hit else 'not seen')] += 1
    return c


def _colour_case(patch):
    """Opaque pixels of the colour patterns = the shapes (painted transparent aside); with no map, every pixel in
    its kind's default. The verify runs read the shapes, so this is what ties them to the bytes the build holds."""
    f = []
    for i in range(patch.npat * 128):
        c, s = patch.pats[i], patch.shapes[i]
        for sh in (4, 0):
            cn, sn = c >> sh & 15, s >> sh & 15
            if cn and not sn or (sn and not cn and not patch.colours):
                f.append('pattern %d' % (i // 128))
    if not patch.colours:
        e = _empty_table(patch)
        if e:
            f.append('default colours: %s' % e[:3])
    return f[:5]


def _empty_table(patch):
    bad = []
    o = patch.syms['blocks'] - ROM_ORG
    idx = 0
    for base, n, _s in RANGES:
        for i in range(n):
            addr = base + 96 * i
            a = patch.code[o + 4 * idx]
            idx += 1
            if a == 0xFF:
                continue
            _g, ink, fill = kind_of(addr)
            for k in range(128):
                c, s = patch.pats[a * 128 + k], patch.shapes[a * 128 + k]
                for sh in (4, 0):
                    cn, sn = c >> sh & 15, s >> sh & 15
                    if sn and cn != (ink if sn == 1 else fill):
                        bad.append(hex(addr))
    return bad


def _setup_case(patch):
    """The stub's setup: patterns reach sprite memory, palette, sprites hidden then on."""
    from skoolkit.simulator import Simulator
    from . import z80n
    Sim = _rw()
    mem = bytearray(65536)
    code = patch.stub_extra
    mem[0xD000:0xD000 + len(code)] = code
    pages = {22: patch.extra_banks[11][:8192], 23: patch.extra_banks[11][8192:16384]}
    ns = NextState(patch.shapes)
    sent = bytearray()

    def nr(reg, val):
        ns.nextreg(reg, val)
        if reg == 0x57 and val in pages:
            mem[0xE000:0x10000] = pages[val]
    sim = Sim(mem, {})
    z80n.install(sim, nr)

    class Tr:
        def read_port(s, r, port):
            return 0xFF

        def write_port(s, r, port, v, *x):
            if port & 255 == 0x5B:
                sent.append(v)
    sim.set_tracer(Tr())
    R = sim.registers
    R[24] = 0xD000
    R[12] = 0xFFF0
    mem[0xFFF0], mem[0xFFF1] = 0, 0
    n = 0
    while R[24] != 0 and n < 2000000:
        sim.opcodes[mem[R[24]]]()
        n += 1
    f = []
    if bytes(sent) != patch.extra_banks[11]:
        f.append('patterns')
    for n in range(1, 16):
        if ns.pal.get(n) != PALETTE[n]:
            f.append('palette index %d' % n)
    if ns.nr.get(0x15) != 1 or ns.nr.get(0x4B) != 0:
        f.append('sprite system registers')
    if any(a[3] & 0x80 for a in ns.attr):
        f.append('a sprite is visible')
    return f


def negative_patches(patch):
    """Broken builds -> [(name, patch)]: each must be DETECTED on the real recording."""
    import copy

    def edit(sym, off, new):
        q = copy.copy(patch)
        code = bytearray(patch.code)
        a = patch.syms[sym] - ROM_ORG + off
        code[a:a + len(new)] = new
        q.code = bytes(code)
        q.rom_code = q.code
        page = bytearray(patch.page)
        o = ROM_ORG - 0x2000
        page[o:o + len(q.code)] = q.code
        q.page = bytes(page)
        return q
    out = [('blank pointer never set: figure stays on the ULA', edit('neg_bl', 0, b'\0\0\0')),
           ('real graphics pointer not restored', edit('neg_gf', 0, b'\0\0\0')),
           ('saved SP not restored', edit('neg_sp', 0, b'\0\0\0\0')),
           ('sprite update skipped', edit('neg_mv', 0, b'\0\0\0')),
           ('sprites one row low', edit('neg_y', 1, b'\x21')),
           ('palette offset wrong', edit('neg_pa', 0, b'\x3E\x10')),
           ('bomb sprite never set', edit('neg_bm', 0, b'\x37\0\0')),
           ('collected bomb keeps its sprite', edit('neg_bg', 0, b'\0\0\0\0')),
           ('clear leaves sprites up', edit('neg_cl', 0, b'\0\0\0\0')),
           ('tile sprite never set', edit('neg_tl', 0, b'\0\0\0')),
           ('layer left on over GAME OVER', edit('neg_gv', 0, b'\0\0\0\0')),
           ('clear leaves the layer on', edit('neg_of', 0, b'\0\0\0\0')),
           ('layer never comes back', edit('neg_go', 0, b'\0\0\0\0')),
           ('clear loses A', edit('neg_ca', 0, b'\0') if False else _two(edit, 'neg_ca', 'neg_cb')),
           ('IM 2 vector overwritten', _vec(patch))]
    q = copy.copy(patch)
    p = bytearray(patch.shapes)
    for i in range(len(p)):
        hi, lo = p[i] >> 4, p[i] & 15
        hi = {1: 2, 2: 1}.get(hi, hi)
        lo = {1: 2, 2: 1}.get(lo, lo)
        p[i] = hi << 4 | lo
    q.shapes = bytes(p)
    out.append(('patterns: ink and fill swapped', q))
    q = copy.copy(patch)
    q.sites = [(a, old, old if a == 0xD94B else new) for a, old, new in patch.sites]
    out.append(('figure hook never runs', q))
    return out


def _two(edit, s1, s2):
    q = edit(s1, 0, b'\0')
    page = bytearray(q.page)
    code = bytearray(q.code)
    a = q.syms[s2] - ROM_ORG
    code[a] = 0
    page[ROM_ORG - 0x2000 + a] = 0
    q.code, q.page = bytes(code), bytes(page)
    return q


def _vec(patch):
    import copy
    q = copy.copy(patch)
    page = bytearray(patch.page)
    page[0x39FF - 0x2000] = 0
    q.page = bytes(page)
    return q


def negative_run(patch, rzx, frames=2300):
    """Every broken build on the real recording: site replay + lockstep. -> [(name, how detected)]
    GAME OVER comes late in the recording, so that one runs on all of it."""
    out = []
    for name, q0 in negative_patches(patch):
        q = q0
        frames_ = None if 'GAME OVER' in name else frames
        c, _ex = verify(q, rzx, stop=frames_)
        f1 = sorted(k for k in c if k.endswith('!'))
        c2, _ex2 = lockstep(q, rzx, stop=frames_)
        f2 = sorted(k for k in c2 if k.endswith('!'))
        out.append((name, f1, f2))
    return out


# ---------------------------------------------------------------------------------------------
# Colour sheets and recolour (docs/COLOURS.md). Every block is one whole figure and its pixels are known from the
# game's data, so the sheets come from the snapshot, recordings not needed: every figure is on them, seen in play or not.
# ---------------------------------------------------------------------------------------------

def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def block_part(peek, addr, src):
    group = kind_of(addr)[0]
    px, rows = block_pixels(peek, addr, src, {})
    pixels, entries = [], {}
    for j, line in enumerate(px):
        for k, (sh, col) in enumerate(line):
            if not sh:
                continue
            key, bit = block_key(addr, j, k)
            entries[key] = [rows[j][1] >> (8 * (2 - k // 8)) & 255, 1]
            pixels.append((k, j, key, bit, sh, col))
    return dict(id=addr, size=16, w=24, h=16, x=0, y=0, mir=0, group=group, pixels=pixels, entries=entries)


def tile_part(peek, t):
    pixels, entries = [], {}
    for r in range(6):
        a = TILES + 6 * t + r
        v = peek(a)
        key = 'T%04X' % a
        entries[key] = [v, 1]
        for k in range(8):
            ink = v >> (7 - k) & 1
            pixels.append((k, r, key, k, 1 if ink else 2, TILE_INK if ink else TILE_FILL))
    return dict(id=0x10000 + t, size=6, w=8, h=6, x=0, y=0, mir=0, group='platforms', pixels=pixels, entries=entries)


def capture(z80):
    """-> coloursheet composites: every block and tile, from the snapshot."""
    from . import coloursheet as cs
    peek = _snapshot_peek(z80)
    col = cs.Collector(family=lambda p: None)
    for base, n, src in RANGES:
        for i in range(n):
            addr = base + 96 * i
            if not LABELS[0] <= addr < LABELS[1]:
                col.add_frame([block_part(peek, addr, src + 96 * i)])
    for t in range(15):
        col.add_frame([tile_part(peek, t)])
    return col.composites(GROUPS)


def sheets(comps, prefix, colours=None, identity=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(PALETTE)
    out = []
    for suffix in ('_PAINTING_SPRITES', '_REFERENCE_ALL_SPRITES'):
        png = prefix + suffix + '.png'
        n = cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours, unique=False,
                     identity=identity)
        out.append((png, n))
    return out


def colour_inputs_md5(peek):
    """MD5 + count of every game byte the colour banks are built from: the blocks and the tiles."""
    import hashlib
    b = bytearray()
    for base, n, src in RANGES:
        b += bytes(peek(src + k) for k in range(96 * n))
    b += bytes(peek(TILES + k) for k in range(90))
    return hashlib.md5(bytes(b)).hexdigest(), len(b)


def colour_identity(peek):
    return {'schema': 1, 'game': RECOLOUR['game'], 'engine': 'bomb_jack',
            'keys': 'bomb_jack-gt-1: G%04X graphics byte at its run-time address / T%04X tile byte, bit = pixel',
            'inputs': colour_inputs_md5(peek)[0], 'geometry': None}


RECOLOUR = {'game': 'bomb_jack', 'output': 'sprites', 'colours': 'docs/profiles/bomb_jack_colours.json',
            'clear': True, 'note': NOTE}


def recolour(nex, cmap):
    """Built bomb_jack_sprites.nex bytes + colour map -> (new .nex bytes, info). Rewrites the patterns (bank 11) and,
    in bank 12, only the two tables that point at them; the game reads neither. Refuses another build."""
    from .recolour import nex_offsets
    d = bytearray(nex)
    off = nex_offsets(d)
    need = {5, 2, 0, 10, 11, 12}
    if not need <= set(off):
        raise ValueError('not a Bomb Jack sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000] if a >= 0x4000 else 0
    prof = load_profile()
    want = prof.get('colour_inputs', {})
    if [want.get('md5'), want.get('bytes')] != list(colour_inputs_md5(peek)):
        raise ValueError('game graphics differ from the expected snapshot')
    p = BombJackPatch(prof, colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('0x%04X does not hold this build\'s hook jump' % a)
    if bank(10)[0x1000:0x1000 + len(p.stub_extra)] != p.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    p.fill(peek)
    t0, t1 = p.syms['blocks'] - 0x2000, p.syms['tiles'] - 0x2000 + 15
    new12 = p.page + p.altrom_low[1]
    b12 = bank(12)
    if b12[:t0] != new12[:t0] or b12[t1:] != new12[t1:]:
        raise ValueError('hook code differs from this version\'s (rebuild with nexclash.py auto)')
    new11 = p.pats + bytes(16384 - len(p.pats))
    changed = [b for b, n in ((11, new11), (12, new12)) if bank(b) != n]
    d[off[11]:off[11] + 16384] = new11
    d[off[12]:off[12] + 16384] = new12
    return bytes(d), {'banks changed': changed, 'patterns': p.npat, 'map entries': len(cmap)}


def rom3_independent(nex, z80, patch, conv):
    """Boot checks with NEXLOAD's printer buffer, on Sinclair's ROM3 and on one that differs in every byte: slots 0-1
    must show Sinclair's ROM + the hooks either way. The recordings replay on Sinclair's ROM and this snapshot is
    in the middle of a BASIC line, so the replays alone cannot show what ROM the .nex really runs."""
    from .build import rom48
    from .nextboot import boot, check
    from . import z80tonex as zt
    tail = (conv[1], conv[1] + len(conv[2]))
    foreign = bytes(b ^ 0x5A for b in rom48())
    bad = check(nex, z80, patch, tail, nexload=True) + check(nex, z80, patch, tail, nexload=True, sysrom=foreign)
    st = boot(nex, zt.Z80Snapshot(z80).pc, nexload=True, sysrom=foreign)
    img = bytearray(rom48())
    img[0x2000:0x4000] = patch.page
    view = bytes(st['mem'][a] for a in range(0x4000))
    rb = patch.regblock
    d = [a for a in range(0x4000) if view[a] != img[a] and not rb <= a < rb + 20]
    if d:
        bad.append(('alt ROM is not the build\'s image', len(d), [hex(x) for x in d[:6]]))
    return bad


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : bomb_jack (Bomb Jack: masked plots from a clean copy -> sprites, plots run on a blank figure)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = BombJackPlain()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = rom3_independent(plain, z80, pp, conv)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = BombJackPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = rom3_independent(spr, z80, patch, conv)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    # broken build: the hook range only, the rest of the image left to the system ROM3 (what the first builds did)
    nb = BombJackPatch()
    nb.fill(_snapshot_peek(z80))
    nb.altrom, nb.altrom_low = (ROM_ORG, nb.regblock + 20), None
    tmp = os.path.join(out, name + '_negative_rom3.nex')
    fill, zt.ALTROM_FILL = zt.ALTROM_FILL, 'rom3'          # the old fill: since 2026-11-04 'whole' fills the rest anyway
    try:
        conv = zt.convert(z80, tmp, None, True, quiet=True, patch=nb)
    finally:
        zt.ALTROM_FILL = fill
    nb.altrom = (ROM_ORG, nb.regblock + 20)
    bad3 = rom3_independent(tmp, z80, nb, conv)
    os.remove(tmp)
    ok = ok and bool(bad3)
    say('Negative  : image left to the system ROM3: %s' % ('DETECTED' if bad3 else 'NOT DETECTED!'))
    states = []
    quick = getattr(a, 'quick', None)
    first = None
    for r in list(a.rzx or []):
        first = first or r
        c, ex, st = verify(patch, r, stop=quick, collect=2)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, plots %d (unknown graphics %d), erase %d, bombs %d, tiles %d, collected %d, clears %d, shown %d, game over %d, '
            '%d figure pixels -> %s' % (os.path.basename(r), c['frames'], c['mov plot'], c['mov unknown graphics'],
                                        c['mov erase'], c['bmb'], c['tile'], c['bgo'], c['cls'], c['go'], c['gov'], c['figure pixels compared'],
                                        'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        c2, ex2 = lockstep(patch, r, stop=quick)
        fails2 = {k: v for k, v in c2.items() if k.endswith('!')}
        ok = ok and not fails2
        say('Lockstep  : %s  %d frames, picture identical %d, inside figure boxes only %d, inside a plot %d, clear or '
            'reveal %d, BC differs %d, hook T/frame %d -> %s' % (os.path.basename(r), c2['frames'], c2['frames picture identical'],
                                     c2['frames picture differs inside figure boxes only'],
                                     c2['frames ending inside a plot (picture not compared)'],
                                     c2['frames ending inside the clear or the reveal'],
                                     c2['BC differs at a frame end (dead)'], c2['hook T'] // max(1, c2['frames']),
                                     'IDENTICAL' if not fails2 else 'FAILED %s' % fails2))
        for k, v in ex2.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k[:-3], v) for k, v in sorted(u.items())
                                                 if k.endswith(' ok')), 'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in sorted(u.items()):
            if k.startswith('  '):
                say('            %s: %d' % (k.strip(), v))
    if first and not quick:
        neg = negative_run(patch, first)
        miss = [n for n, f1, f2 in neg if not f1 and not f2]
        ok = ok and not miss
        for n, f1, f2 in neg:
            say('Negative  : %s: %s (replay %d, lockstep %d kinds)' % (n, 'DETECTED' if f1 or f2 else 'NOT DETECTED!',
                                                                     len(f1), len(f2)))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    import sys
    # python -m nexclash.bomb_jack sheet GAME.z80 PREFIX
    if len(sys.argv) == 4 and sys.argv[1] == 'sheet':
        for png_, n_ in sheets(capture(sys.argv[2]), sys.argv[3], load_colours(),
                               colour_identity(_snapshot_peek(sys.argv[2]))):
            print(png_, n_)
