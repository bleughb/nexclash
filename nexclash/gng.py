"""Ghosts 'n Goblins (Elite 1986, 48K) - figures as hardware sprites.

Each tick the game redraws the play area in bands (no back buffer) and plots figures straight on the screen, in order of
depth. Three plot loops' stores become NOPs and their LD (49060),SP a JP to a hook that gives sprites. games/ghosts_n_goblins.md.
"""
import collections
import hashlib
import json
import os
import zlib

PAGE = 24                   # hook page at MMU slot 1 (bank 12, first half)
PLANE = 26                  # colour nibbles: 8 pages (banks 13-16)
CHECK = 34                  # check bytes: 2 pages (bank 17)
PLANE_BANKS = range(13, 18)
GB = 0xC000
TAIL_ADDR = 0x5B00          # scan: write-first on every recording, from the snapshot on
SPSAVE = 49060
M3, O3, X2 = 36520, 37110, 37003
M3_RET = 36601             # the masked loop's RET: its hook leaves registers as the loop does, without running the loop
ENTRIES = {M3: ('e_m3', M3_RET, 'm3'), O3: ('e_o3', 37114, 'o3'), X2: ('e_x2', 37007, 'x2')}
STORES_M3 = (36533, 36539, 36546, 36552, 36557, 36563)
STORES = STORES_M3 + (37150, 37154, 37159, 37163, 37168, 37172) + (37012, 37016, 37021, 37025)
TICK, TICK_BACK = 36415, 36419
CLS, CLS_BACK = 36061, 36064
CLS2, CLS2_BACK = 23963, 23966
INIT, INIT_TARGET = 24841, 25202
HUD = 26657                 # JP 32789: the weapon in the score bar, the one masked plot that stays on the ULA
HUD_THEME = ((27520, 0x70, 0x47), (26631, 0x0F, 0x45))  # LD BC operands: text and weapon attributes only
# v1.4: the object dispatcher's LD (49028),A -> JP e_object. The hook keeps the original write, every register, the
# incoming CPU speed and the original R effect, records the object for intermediate positions, and returns to 35899.
OBJECT, OBJECT_BACK, OBJECT_OLD = 35896, 35899, bytes.fromhex('3284BF')
HIDDEN_ROM_BANKS = (46, 47)  # 8K pages 92-95: z80tonex's whole-ROM sources; the colour plane must never cover them
INTERIORS = tuple(a + k for a in list(ENTRIES) + [TICK] for k in (1, 2, 3)) + (CLS + 1, CLS + 2, CLS2 + 1, CLS2 + 2, INIT + 1, INIT + 2, HUD + 1, HUD + 2)
INTERIORS += (OBJECT + 1, OBJECT + 2)
PALETTE = [0x00, 0x16, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0xFC, 0xB4, 0xB6, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFF]
_R_SP, _R_PC, _R_T, _R_IFF = 12, 24, 25, 26
CMP = list(range(0, 13)) + [14, 15] + list(range(16, 25)) + [26, 27]   # all but T, MEMPTR
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'ghosts_n_goblins_colours.json')
KIND_ROW = {'m3': 10, 'o3': 6, 'x2': 4}
# per kind, line 0 columns 0-2, line 1 columns 0-2: (graphics offset, mask offset or None); as the three loops read them
LAYOUT = {'m3': [[(5, 4), (3, 2), (1, 0)], [(6, 4), (7, 2), (9, 8)]],
          'o3': [[(2, None), (1, None), (0, None)], [(3, None), (4, None), (5, None)]],
          'x2': [[(0, None), (1, None)], [(2, None), (3, None)]]}


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'ghosts_n_goblins.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_gng(snap):
    if len(snap.ram(-1)) != 49152:
        return False
    sig = load_profile()['signature']
    b = bytes.fromhex(sig['bytes'])
    m = snap.memory
    return bytes(m[sig['addr'] + k] for k in range(len(b))) == b


def load_colours(path=None):
    """The colour map; its stored check values are null (the repo keeps only the painting, keyed by image id and
    byte offset): each is filled from the image's own byte (gng_art.catalog(), read from the player's game)."""
    from .recolour import build_colours_path
    p = path or build_colours_path(COLOURS)
    if p and os.path.exists(p):
        from .coloursheet import load
        return fill_checks(load(p))
    return {}


def fill_checks(cmap):
    """cmap with every null check value set to the graphic's byte at that offset (gng_art.catalog())."""
    if not any(e[0] is None for e in cmap.values()):
        return cmap
    from . import gng_art
    raw = {q['id']: bytes.fromhex(q['data']) for q in gng_art.catalog()}
    for k, e in cmap.items():
        if e[0] is None:
            i, o = k.split(':')
            e[0] = raw[i][int(o, 16)]
    return cmap


def strip_checks(path):
    """Write the colour map at path with its check values null (run after importing a painted sheet, which writes
    them): no byte of the game's graphics is kept in the repo."""
    d = json.load(open(path))
    for e in d['entries'].values():
        e[0] = None
    open(path, 'w').write(json.dumps(d, indent=0) + '\n')


# ---------------------------------------------------------------------------------------------
# The colour plane
# ---------------------------------------------------------------------------------------------

def plane(cmap=None):
    """-> bytes: 4 * 16K of nibbles by graphics address from 0xC000, then 16K of check bytes."""
    n = bytearray(4 * 0x4000)
    c = bytearray(0x4000)
    for k, e in (cmap or {}).items():
        if ':' in k:
            continue
        a = int(k, 16)
        if not GB <= a < 0x10000:
            continue
        o = a - GB
        c[o] = e[0]
        for b in range(8):
            v = e[2][b] & 15
            n[4 * o + b // 2] |= v << 4 if b % 2 == 0 else v
    from .gng_art import atlas
    return bytes(n + c) + atlas(cmap)


def plane_banks(pl):
    out = {b: pl[(b - PLANE_BANKS[0]) * 16384:(b - PLANE_BANKS[0] + 1) * 16384].ljust(16384, b'\0') for b in range(PLANE_BANKS[0], PLANE_BANKS[0] + (len(pl) + 16383) // 16384)}
    for b in HIDDEN_ROM_BANKS:           # a plane reaching past them (the ground atlas) leaves them to the converter
        if b in out:
            assert not any(out[b]), 'colour plane data in a hidden-ROM bank'
            del out[b]
    return out


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

def _rom():
    from .build import rom48
    return rom48()


class GngPatch:
    name = "Ghosts 'n Goblins figures -> hardware sprites (hooks in a slot-1 RAM page, ROM font at its top)"

    def __init__(self, prof=None, page_code=None, colours=None, drop_sites=(), store_op=0, palette=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.code = page_code or bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.palette = list(palette or PALETTE)
        setup = bytearray.fromhex(h['setup'])
        po = self.syms['pal'] - 0xD000
        setup[po:po+16] = bytes(self.palette)
        self.stub_extra = bytes(setup)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 128
        self.slot1 = (PAGE, self.syms['regs'])
        self.altrom = (0x2000, 0x2000)
        self.ram_slot1_after_alt = True
        page = bytearray(8192)
        page[:len(self.code)] = self.code
        # the rest of the page is the ROM's: the game prints with its font, and on starting level 12 runs 3 bytes at 0x3828 (a stray pointer)
        rom = _rom()
        he = self.syms['hook_end'] - 0x2000
        page[he:0x2000] = rom[0x2000 + he:0x4000]
        self.page = bytes(page)
        self.colours = {} if colours is None else colours
        self.hud_theme = any(':' in k for k in self.colours)
        s = self.syms
        self.sites = []
        for a in STORES:
            if a not in drop_sites:
                self.sites.append((a, b'\x77', bytes([store_op])))
        for a, (sym, _, _) in ENTRIES.items():
            if a not in drop_sites:
                self.sites.append((a, bytes.fromhex('ED73A4BF'), b'\xC3' + s[sym].to_bytes(2, 'little') + b'\x00'))
        table = ((TICK, 'FD21 70BF', 'e_tick', b'\x00'), (CLS, '210040', 'e_cls', b''), (CLS2, '210040', 'e_cls2', b''),
                 (INIT, 'C37262', 'e_init', b''), (HUD, 'C31580', 'e_hud', b''))
        for a, old, sym, tail in table:
            if a not in drop_sites:
                self.sites.append((a, bytes.fromhex(old), b'\xC3' + s[sym].to_bytes(2, 'little') + tail))
        for a, old, themed in HUD_THEME:
            self.sites.append((a, bytes([old]), bytes([themed if self.hud_theme else old])))
        if 'e_object' in s and OBJECT not in drop_sites:
            self.sites.append((OBJECT, OBJECT_OLD, b'\xC3' + s['e_object'].to_bytes(2, 'little')))
        self.pl = None
        self.extra_banks = {PAGE // 2: self.page + bytes(8192)}

    def build_plane(self):
        cmap = load_colours() if self.colours is None else self.colours
        self.pl = plane(cmap)
        from . import gng_art as art
        if 'gc_atlas' in self.syms:      # hooks with carried-item ground clipping read the partial-pot pages
            self.pl = art.ground_atlas(self.pl, cmap, PLANE_BANKS[0] * 2)
        self.art_expected = art.PaintOracle(cmap)
        return self.pl

    def apply(self, snap):
        if snap.is128:
            raise ValueError("Ghosts 'n Goblins patch expects the 48K snapshot")
        self.sites = list(dict.fromkeys(self.sites))   # a caller re-adding the object site adds nothing
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError("unexpected code at %d (%s, expected %s) - not the expected version of Ghosts 'n Goblins" % (a, cur.hex(), old.hex()))
        pl = self.build_plane()
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {PAGE // 2: self.page + bytes(8192)}
        self.extra_banks.update(plane_banks(pl))


# ---------------------------------------------------------------------------------------------
# Next-side model
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patp = 0
        self.slot2 = 10
        self.speed = 0
        self.selected = 0
        self.bad = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x52:
            self.slot2 = val
        elif reg == 0x07:
            self.speed = val
        elif reg != 0x34:
            self.bad.append(('nextreg', reg))

    def out(self, port, val):
        if port == 0x243B:
            self.selected = val
        elif port == 0x253B:
            self.nextreg(self.selected, val)
        elif port & 0xFF == 0x3B and port >> 8 == 0x30:
            self.patp = ((val & 0x3F) << 8 | (val & 0x80)) % 16384
        elif port & 0xFF == 0x5B:
            self.pat[self.patp] = val
            self.patp = (self.patp + 1) % 16384
        else:
            self.bad.append(('out', port))

    def visible(self):
        """-> [(slot, pattern, x, y)] in slot order."""
        out = []
        for i, (a0, a1, a2, a3, a4) in enumerate(self.attr):
            if not a3 & 0x80:
                continue
            f = ((a3 & 0x3F) << 1) | ((a4 >> 6) & 1)
            if not a3 & 0x40 or not a4 & 0x80 or a4 & 0x3F or a2 & 0xFE:
                self.bad.append(('sprite form', i, (a0, a1, a2, a3, a4)))
            out.append((i, f, a0 + (a2 & 1) * 256 - 32, a1 - 32))
        return out


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


class _PMem:
    """Patched view: ROM below 0x2000, the hook page at 0x2000-0x3FFF, the plane at slot 2 when it is mapped there,
    game memory read through get; writes to an overlay."""

    def __init__(s, get, page, pl, ns, rom):
        s.get, s.page, s.pl, s.ns, s.rom, s.ov, s.romw = get, page, pl, ns, rom, {}, 0

    def __getitem__(s, a):
        if a < 0x2000:
            return s.rom[a]
        if a < 0x4000:
            return s.page[a - 0x2000]
        if a < 0x6000 and s.ns.slot2 != 10:
            off = (s.ns.slot2 - PLANE) * 0x2000 + (a & 0x1FFF)
            return s.pl[off] if 0 <= off < len(s.pl) else 0
        v = s.ov.get(a)
        return v if v is not None else s.get(a)

    def __setitem__(s, a, v):
        if a < 0x2000:
            s.romw += 1
        elif a < 0x4000:
            s.page[a - 0x2000] = v
        else:
            s.ov[a] = v

    def __len__(s):
        return 65536


def _machine(mem, regs, ns):
    from .simpool import machine
    from . import z80n
    sim = machine(_rw(), mem, regs, 'g')
    z80n.install(sim, ns.nextreg)

    class Tr:
        def read_port(s, regs_, port):
            if port == 0x253B:
                return ns.speed | (ns.speed << 4) if ns.selected == 7 else ns.nr.get(ns.selected, 0)
            ns.bad.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=2000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[_R_PC] != stop:
        ops[mem[R[_R_PC]]]()
        n += 1
        if n > limit:
            return False
    return True


class Engine:
    """Persistent patched state: hook page, Next state, for one replay."""

    def __init__(self, patch):
        self.patch = patch
        self.page = bytearray(patch.page)
        self.ns = NextState()
        self.rom = _rom()
        self.linecache = {}

    def hook(self, get, regs, start, stop, sp=None):
        """Run a hook from these registers to `stop`. -> (registers after, overlay, T, finished, ROM writes)."""
        mem = _PMem(get, self.page, self.patch.pl, self.ns, self.rom)
        r = list(regs)
        r[_R_PC] = start
        r[15] = (r[15] & 128) | ((r[15] + 1) & 127)  # patched JP at the original site
        if sp is not None:
            r[_R_SP] = sp
        sim = _machine(mem, r, self.ns)
        t0 = sim.registers[_R_T]
        done = _run(sim, stop)
        return list(sim.registers), mem.ov, sim.registers[_R_T] - t0, done, mem.romw

    def lines(self, f):
        """Pattern f -> 16 lines of (opaque mask, ink bits): 16 bits each. Ink = nibble 1; any other non-zero = body or painted."""
        b = bytes(self.ns.pat[f * 128:(f + 1) * 128])
        c = self.linecache.get(b)
        if c is None:
            c = []
            for y in range(16):
                op = ink = 0
                for k in range(16):
                    v = b[y * 8 + k // 2]
                    v = v >> 4 if k % 2 == 0 else v & 15
                    if v:
                        op |= 0x8000 >> k
                        if v not in (0, 2):
                            ink |= 0x8000 >> k
                c.append((op, ink))
            self.linecache[b] = c
        return c


def _scr(y, col):
    return (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | col


def scr_yx(a):
    h, l = a >> 8, a & 255
    return (h & 0x18) << 3 | (l & 0xE0) >> 2 | (h & 7), l & 31


def composite(eng, bare):
    """Sprites over the bare screen (6144 bytes) -> screen bytes. Sprites are always on a byte in x."""
    scr = bytearray(bare)
    for slot, f, x, y in eng.ns.visible():
        if x % 8:
            eng.ns.bad.append(('x', x))
        col = x >> 3
        for l, (op, ink) in enumerate(eng.lines(f)):
            if not op:
                continue
            yy = y + l
            if not 0 <= yy < 192:
                continue
            for k, sh in ((col, 8), (col + 1, 0)):
                if 0 <= k < 32:
                    m = op >> sh & 255
                    if m:
                        a = _scr(yy, k)
                        scr[a] = (scr[a] & ~m & 255) | (ink >> sh & 255)
    return bytes(scr)


def wrapped_bytes(a, kind, rows):
    """A figure over the left edge: the loop's DEC L crosses into the end of the cell row above, so the original also draws at the
    right edge. These bytes, as the loop steps; -> screen offsets (from 0x4000). The sprite just goes off the left edge."""
    w = 2 if kind == 'x2' else 3
    out = set()
    y, _ = scr_yx(a - 0x4000)
    for i in range(rows):
        for line in (0, 1):
            ln = y + 2 * i + line
            if ln >= 192:
                break
            base = _scr(ln, 0)
            for k in range(w):
                c = (a & 31) - k
                if c < 0:
                    out.add((base & 0xFF00) | ((base & 0xFF) + c & 255))
    return out


def truth_lines(get, kind, g, rows):
    """What the loop's bytes say: per line, per column (ink byte, opaque byte)."""
    out = []
    layout = LAYOUT[kind]
    for i in range(rows):
        p = g + i * KIND_ROW[kind]
        for row in layout:
            line = []
            for go, mo in row:
                d = get((p + go) & 0xFFFF)
                m = get((p + mo) & 0xFFFF) if mo is not None else 0xFF
                line.append((d, (d | ~m) & 255))
            out.append(line)
    return out


def sprite_lines(eng, slots):
    """The sprites just made -> {(line, column): (ink, opaque)} relative to the first."""
    first = slots[0]
    out = {}
    for slot, f, x, y in slots:
        ls = eng.lines(f)
        dx, dy = (x - first[2]) // 8, y - first[3]
        for l, (op, ink) in enumerate(ls):
            out[(dy + l, dx)] = (ink >> 8 & 255, op >> 8 & 255)
            out[(dy + l, dx + 1)] = (ink & 255, op & 255)
    return out


def check_plot(eng, slots, get, kind, g, rows, x, y, painted=None):
    """-> None or what differs: every line of the plot, at the plot's place; nothing else in the sprites' cells."""
    if not slots:
        return 'no sprites'
    if (slots[0][2], slots[0][3]) != (x * 8, y):
        return ('place', slots[0][2:], (x * 8, y))
    t = truth_lines(get, kind, g, rows)
    sp = sprite_lines(eng, slots)
    for l, line in enumerate(t):
        for c, (ink, op) in enumerate(line):
            if painted is not None:
                # Retain independent original-ink and position checks. Only the
                # explicitly painted opacity can differ from the original mask.
                ti=(l//16)*2+c//2;off=ti*128+(l%16)*8+(c%2)*4
                pop=0
                for bit in range(8):
                    v=painted[off+bit//2];v=v>>4 if bit%2==0 else v&15
                    if v:pop|=128>>bit
                if pop & ~op:return ('paint adds opacity',l,c,pop,op)
                op=pop
            if sp.get((l, c), (0, 0)) != (ink, op):
                return ('pixels', l, c, sp.get((l, c)), (ink, op))
    for (l, c), v in sp.items():
        if v != (0, 0) and (l >= len(t) or c >= len(t[0])):
            return ('extra', l, c, v)
    return None


# ---------------------------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------------------------

def replay_bare(patch, rzx_path, stop):
    """Replay with only the stores changed. -> per draw pass (screen, registers, memory digest). Screen bytes are left out of
    the digest; every other byte, stores restored. The score bar's weapon keeps its stores."""
    from . import rzx as RZ
    ticks = []
    done = [False]
    sites = [a for a, old, new in patch.sites if len(old) == 1 and a in STORES]
    op = {a: new[0] for a, old, new in patch.sites if len(old) == 1 and a in STORES}
    hud = [0]

    def on(pc, sim):
        M = sim.memory
        if not done[0]:
            for a in sites:
                M[a] = op[a]
            for a, old, new in patch.sites:
                if a in {x[0] for x in HUD_THEME}:M[a]=new[0]
            done[0] = True
        if pc == HUD:
            hud[0] = 1
            return
        if pc == M3:
            for a in STORES_M3:
                if a in op:
                    M[a] = 0x77 if hud[0] else op[a]
            hud[0] = 0
            return
        m = bytearray(M[0x5800:0x10000])
        for a in STORES:
            m[a - 0x5800] = 0x77
        for a, old, new in HUD_THEME:m[a-0x5800]=old
        if patch.hud_theme:
            # Exact inverse of the two display-only operands, limited to the
            # original score-bar attribute cells. No gameplay RAM is excluded.
            for off in list(range(30))+list(range(32,62)):
                if m[off]==0x47:m[off]=0x70
                elif m[off]==0x45:m[off]=0x0F
        ticks.append((zlib.compress(bytes(M[0x4000:0x5800]), 1), [sim.registers[i] for i in CMP], hashlib.md5(m).digest()))
    fc, err = RZ.trace(rzx_path, {M3, HUD, TICK}, on, stop=stop)
    return ticks, fc, err


def verify(patch, rzx_path, stop=None, collect=0, progress=None, stop_on_failure=False):
    from . import rzx as RZ
    if patch.pl is None:
        patch.build_plane()
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []

    class FirstFailure(Exception):
        pass

    def fail(k, *v):
        c[k + '!'] += 1
        if len(ex[k + '!']) < 5:
            ex[k + '!'].append(v)
        if stop_on_failure:
            raise FirstFailure()
    expect = [None]
    bare, fc2, err2 = replay_bare(patch, rzx_path, stop)
    if err2:
        try:
            fail('bare replay desync', err2)
        except FirstFailure:
            c['stopped at first failure'] = 1
            return c, ex, states
    eng = Engine(patch)
    s = patch.syms
    have = {x[0] for x in patch.sites}
    idx = [0]
    tmax = collections.Counter()
    tick_t = [0]
    plots = []
    pcs = set(ENTRIES) | {TICK, CLS, CLS2, INIT, HUD, M3_RET} | set(INTERIORS) | set(range(0x2000, s['hook_end']))
    pending_hud = [False]
    wrapped = set()
    seen_img = set()

    def simple_hook(sym, get, R, stop_pc, what, sp=None, keep=(), romok=False):
        regs = list(R)
        rr, ov, t, done, romw = eng.hook(get, regs, s[sym], stop_pc, sp=sp)
        if sp is not None:
            rr[_R_SP] = regs[_R_SP]
        if not done or ov or romw:
            fail(what + ' hook', done, sorted(ov.items())[:4], romw)
        regs[15] = (regs[15] & 128) | ((regs[15] + (2 if sym == 'e_tick' else 1)) & 127)
        for j in CMP:
            if j != _R_PC and j not in keep and rr[j] != regs[j]:
                fail('register changed by %s hook' % what, j, regs[j], rr[j])
        return rr

    def on(pc, sim):
        R, M = sim.registers, sim.memory
        get = M.__getitem__
        if pc in INTERIORS:
            fail('jump into a patched instruction', pc)
            return
        if 0x2000 <= pc < 0x4000:
            fail('the game runs ROM code where the hook page differs', pc)
            return
        if pc == M3_RET:
            if expect[0] is not None:
                for i in CMP:
                    if i != _R_PC and expect[0][i] != R[i]:
                        fail('register differs where the loop ends', i, expect[0][i], R[i])
                expect[0] = None
            return
        if pc == HUD:
            c['score bar plots'] += 1
            pending_hud[0] = True
            if HUD in have:
                regs = list(R)
                retpc = M[R[_R_SP]] | M[R[_R_SP] + 1] << 8
                sp = R[_R_SP]
                # the copy against the original, from one state, to the same return
                rr, ov, t, done, romw = eng.hook(get, regs, s['e_hud'], retpc)
                orig = bytearray(M)
                from skoolkit.simulator import Simulator
                os_ = Simulator(orig, dict())
                os_.registers[:] = regs
                os_.registers[_R_PC] = HUD
                n = 0
                while os_.registers[_R_PC] != retpc and n < 200000:
                    os_.opcodes[orig[os_.registers[_R_PC]]]()
                    n += 1
                for j in CMP:
                    if j != _R_PC and rr[j] != os_.registers[j]:
                        fail('score bar copy: register', j, rr[j], os_.registers[j])
                if not done or romw:
                    fail('score bar copy did not return', done, romw)
                diff = {a: orig[a] for a in range(0x4000, 0x10000) if orig[a] != M[a]}
                ov2 = {a: v for a, v in ov.items() if v != M[a]}
                for a in set(diff) | set(ov2):
                    if diff.get(a, M[a]) != ov2.get(a, M[a]):
                        fail('score bar copy: memory', a, diff.get(a), ov2.get(a))
                        break
            return
        if pc in ENTRIES:
            sym, back, kind = ENTRIES[pc]
            if pc == M3 and pending_hud[0]:
                pending_hud[0] = False
                return
            c['plots ' + kind] += 1
            if pc not in have:
                return
            if R[_R_IFF]:
                fail('interrupts on at a hook site', pc)
            if collect:
                kk = (sym, R[4] << 8 | R[5] if kind == 'm3' else R[6] << 8 | R[7])
                if kk not in seen_img and sum(1 for x in states if x[0] == sym) < collect:
                    seen_img.add(kk)
                    states.append((sym, list(R), bytes(M)))
            regs = list(R)
            n0 = eng.page[s['nsp'] - 0x2000]
            rr, ov, t, done, romw = eng.hook(get, regs, s[sym], back)
            c['hook T'] += t
            tick_t[0] += t
            tmax[sym] = max(tmax[sym], t)
            if not done:
                fail('hook did not return', pc)
                return
            if kind == 'm3':
                expect[0] = rr
            else:
                regs[15] = (regs[15] & 128) | ((regs[15] + 2) & 127)
                for i in CMP:
                    if i != _R_PC and rr[i] != regs[i]:
                        fail('register changed by hook', pc, i, regs[i], rr[i])
            sp = regs[_R_SP]
            extra = {k: v for k, v in ov.items() if k not in (SPSAVE, SPSAVE + 1)}
            if extra or ov.get(SPSAVE) != sp & 255 or ov.get(SPSAVE + 1) != sp >> 8:
                fail('game memory written by hook', pc, sorted(ov.items())[:6])
            if romw:
                fail('ROM written', pc)
            if eng.ns.slot2 != 10:
                fail('plane left mapped', pc, eng.ns.slot2)
                eng.ns.slot2 = 10
            if eng.ns.speed:
                fail('speed left high', pc)
            n1 = eng.page[s['nsp'] - 0x2000]
            if kind == 'm3':
                g, a, rows = regs[4] << 8 | regs[5], regs[6] << 8 | regs[7], regs[2] + 4 * (regs[19] - 1) + regs[18]
                col = (a & 31) - 2
            elif kind == 'o3':
                g, rows = regs[6] << 8 | regs[7], regs[3]
                t_ = 0xBE00 + 2 * regs[5]
                a = ((M[t_ + 1] << 8) | ((M[t_] + regs[4]) & 255))
                col = (a & 31) - 2
            else:
                g, a, rows = regs[6] << 8 | regs[7], regs[4] << 8 | regs[5], 4
                col = (a & 31) - 1
            y, _ = scr_yx(a)
            if n1 == n0:
                fail('figure with no sprite', pc, g, rows)
                return
            slots = [v for v in eng.ns.visible() if n0 <= v[0] < n1]
            painted = patch.art_expected.expected(kind,g,rows,get)
            bad = check_plot(eng, slots, get, kind, g, rows, col, y, painted)
            if bad:
                fail('sprite differs from the plot', kind, g, rows, bad)
            if painted is not None:
                nc = 1 if kind == 'x2' else 2
                for j, (_,pat,xx,yy) in enumerate(slots):
                    ti = (j//nc)*2+j%nc
                    if bytes(eng.ns.pat[pat*128:pat*128+128]) != painted[ti*128:ti*128+128]:
                        fail('uploaded artwork differs',kind,g,rows,j)
                        break
                c['exact painted patterns'] += len(slots)
            else:
                c['uncatalogued images'] += 1
            plots.append((col, y, 2 if kind == 'x2' else 3, 2 * rows, kind))
            if col < 0:
                wrapped.update(wrapped_bytes(a, kind, rows))
            for l in range(2 * rows):           # bands often leave columns 30, 31 alone: the original's figure stays there as a trail
                for k in range(max(col, 30), col + (2 if kind == 'x2' else 3)):
                    if y + l < 192:
                        wrapped.add(_scr(y + l, k))
            return
        if pc == CLS or pc == CLS2:
            c['screen clears'] += 1
            if pc in have:
                simple_hook('e_cls' if pc == CLS else 'e_cls2', get, R, CLS_BACK if pc == CLS else CLS2_BACK, 'clear', keep=(6, 7))
            if eng.ns.visible():
                fail('sprites left at a clear', pc)
            wrapped.clear()
            return
        if pc == INIT:
            c['level starts'] += 1
            if INIT in have:
                simple_hook('e_init', get, R, INIT_TARGET, 'level start')
            if eng.ns.visible():
                fail('sprites left at a level start', pc)
            return
        # the end of a draw pass
        i = idx[0]
        idx[0] += 1
        c['ticks'] += 1
        if i >= len(bare):
            fail('more ticks than the bare replay')
            return
        scr0, regs0, dig0 = bare[i]
        for k, j in enumerate(CMP):
            if regs0[k] != R[j]:
                fail('registers differ at a tick', i, j, regs0[k], R[j])
                break
        if hashlib.md5(bytes(M[0x5800:0x10000])).digest() != dig0:
            fail('memory differs at a tick', i)
        c['memory checks'] += 1
        if TICK in have:
            rr = simple_hook('e_tick', get, R, TICK_BACK, 'tick', keep=(10, 11))
            if rr[10] << 8 | rr[11] != 49008:
                fail('tick hook IY', rr[10], rr[11])
            if eng.page[s['nsp'] - 0x2000]:
                fail('tick hook left a count')
        c['tick T max'] = max(c['tick T max'], tick_t[0])
        tick_t[0] = 0
        c['most sprites'] = max(c['most sprites'], len(eng.ns.visible()))
        got = composite(eng, zlib.decompress(scr0))
        want = bytes(M[0x4000:0x5800])
        c['screens compared'] += 1
        if got != want:
            rects = plots
            real = 0
            for a in range(6144):
                if got[a] != want[a]:
                    y, x = scr_yx(a)
                    if any(p[0] <= x < p[0] + p[2] and p[1] <= y < p[1] + p[3] for p in rects):
                        c['bytes under a figure: something the original drew over it, or XOR (depth, not logic)'] += 1
                    elif a in wrapped:
                        c['bytes at the right edge: a figure the original wraps there, or left there'] += 1
                    else:
                        real += 1
                        if not ex['screen differs at a tick!'] or len(ex['screen differs at a tick!']) < 5:
                            ex['screen differs at a tick!'].append((i, y, x, got[a], want[a]))
            if real:
                c['screen differs at a tick!'] += 1
        plots.clear()
        if eng.ns.bad:
            fail('next state', eng.ns.bad[:3])
            eng.ns.bad = []
        if progress and i % 500 == 0:
            progress(i)
    try:
        fc, err = RZ.trace(rzx_path, pcs, on, stop=stop)
    except FirstFailure:
        c['stopped at first failure'] = 1
        return c, ex, states
    c['frames'] = fc
    if err:
        fail('replay desync', err)
    if idx[0] != len(bare):
        fail('tick counts differ', idx[0], len(bare))
    c.update({'T max %s' % k: v for k, v in tmax.items()})
    return c, ex, states


def RZ_first_snapshot(rzx_path):
    from .rzx import read_segments
    return read_segments(rzx_path)[0][0].memory


# ---------------------------------------------------------------------------------------------
# Unit tests: the loops' own code against the sprites, on cases the recordings may not reach
# ---------------------------------------------------------------------------------------------

def _loop_regs(kind, g, col, y, rows):
    """Registers at the loop's entry, as the callers set them. -> {reg index: value}"""
    u = y // 2
    c = u & 3
    first = 4 - c
    if kind == 'x2':
        a = 0x4000 + _scr(y, col + 1)
        return {6: g >> 8, 7: g & 255, 4: a >> 8, 5: a & 255, 2: first, 3: c}
    if kind == 'o3':
        return {6: g >> 8, 7: g & 255, 4: col + 2, 5: u, 3: rows}
    a = 0x4000 + (_scr(y, 0) & 0xFF00 | ((_scr(y, 0) & 255) + col + 2) & 255)
    if rows < first:
        b, xc, xb = rows, 1, 0
    else:
        b, xc, xb = first, ((rows - first) >> 2) + 1, (rows - first) & 3
    return {6: a >> 8, 7: a & 255, 4: g >> 8, 5: g & 255, 2: b, 19: xc, 18: xb}


def truth(m, kind, g, col, y, rows):
    """Run the original loop on a screen of 0x00, then of 0xFF. -> {(line, column): (ink, opaque)}: ink = set on 0x00; opaque =
    a bit the loop controls (it differs from the fill in one run or matches in both ways)."""
    from skoolkit.simulator import Simulator
    entry = {'m3': M3, 'o3': O3, 'x2': X2}[kind]
    runs = []
    for fill in (0, 255):
        mem = bytearray(m)
        mem[0x4000:0x5800] = bytes([fill]) * 0x1800
        sim = Simulator(mem, dict())
        R = sim.registers
        R[12] = 0xFF00
        mem[0xFF00], mem[0xFF01] = 0x34, 0x12
        for k, v in _loop_regs(kind, g, col, y, rows).items():
            R[k] = v
        R[_R_PC] = entry
        n = 0
        while R[_R_PC] != 0x1234:
            sim.opcodes[mem[R[_R_PC]]]()
            n += 1
            if n > 400000:
                raise ValueError('loop did not return')
        runs.append(bytes(mem[0x4000:0x5800]))
    out = {}
    w = 2 if kind == 'x2' else 3
    for l in range(2 * rows):
        for c in range(w):
            k = col + c
            if not 0 <= k < 32 or y + l >= 192:
                continue
            a = _scr(y + l, k)
            on0, on1 = runs[0][a], runs[1][a]
            if kind == 'x2':                # XOR: bits it flips
                ink = on0
                op = on0
            else:
                ink = on0
                op = on0 | (~on1 & 255)
            out[(l, c)] = (ink, op)
    return out


def _loop_exit(m, R):
    """The original masked loop from these registers to its RET. -> registers."""
    from skoolkit.simulator import Simulator
    mem = bytearray(m)
    sim = Simulator(mem, dict())
    sim.registers[:] = list(R)
    sim.registers[_R_PC] = M3
    n = 0
    while sim.registers[_R_PC] != M3_RET and n < 400000:
        sim.opcodes[mem[sim.registers[_R_PC]]]()
        n += 1
    return list(sim.registers)


def _plot_case(eng, m, kind, g, col, y, rows, c, what):
    sym = {'m3': 'e_m3', 'o3': 'e_o3', 'x2': 'e_x2'}[kind]
    back = {'m3': M3_RET, 'o3': 37114, 'x2': 37007}[kind]
    s = eng.patch.syms
    R = [0] * 29
    R[12] = 0xFF00
    for k, v in _loop_regs(kind, g, col, y, rows).items():
        R[k] = v
    n0 = eng.page[s['nsp'] - 0x2000]
    rr, ov, t, done, romw = eng.hook(m.__getitem__, R, s[sym], back)
    c[what] += 1
    if not done or romw or set(ov) - {SPSAVE, SPSAVE + 1}:
        c[what + ' hook!'] += 1
        return None
    want = _loop_exit(m, R) if kind == 'm3' else list(R)
    if kind != 'm3':
        want[15] = (want[15] & 128) | ((want[15] + 2) & 127)
    for i in CMP:
        if i != _R_PC and rr[i] != want[i]:
            c[what + ' register!'] += 1
    n1 = eng.page[s['nsp'] - 0x2000]
    slots = [v for v in eng.ns.visible() if n0 <= v[0] < n1]
    if not slots:
        c[what + ' no sprite!'] += 1
        return None
    if (slots[0][2], slots[0][3]) != (col * 8, y):
        c[what + ' place!'] += 1
    sp = sprite_lines(eng, slots)
    for key, v in truth(m, kind, g, col, y, rows).items():
        if sp.get(key, (0, 0)) != v:
            c[what + ' pixels!'] += 1
            break
    return slots


def unit_tests(patch, states, neg=None):
    c = collections.Counter()
    if patch.pl is None:
        patch.build_plane()
    kinds = {'e_m3': 'm3', 'e_o3': 'o3', 'e_x2': 'x2'}
    sym_regs = {'e_m3': lambda R: (R[4] << 8 | R[5]), 'e_o3': lambda R: (R[6] << 8 | R[7]), 'e_x2': lambda R: (R[6] << 8 | R[7])}
    eng = Engine(patch)
    s = patch.syms
    tick = lambda m: eng.hook(m.__getitem__, [0] * 12 + [0xFF00] + [0] * 16, s['e_tick'], TICK_BACK)
    images = []
    for sym, R, m in states:
        kind = kinds[sym]
        rows = {'m3': R[2] + 4 * (R[19] - 1) + R[18], 'o3': R[3], 'x2': 4}[kind]
        images.append((kind, sym_regs[sym](R), rows, m))
    # every image, in the middle of the screen
    for kind, g, rows, m in images:
        _plot_case(eng, m, kind, g, 12, 64, rows, c, 'image')
        tick(m)
    # positions and heights: edges of the screen, cell boundaries
    done = set()
    for kind, g, rows, m in images:
        if kind in done:
            continue
        done.add(kind)
        for col in (0, 1, 13, 29 if kind != 'x2' else 30):
            for y in (16, 18, 20, 22, 24, 64, 128, 190 - 2 * rows if rows < 8 else 170):
                _plot_case(eng, m, kind, g, col, y, rows, c, 'position')
                tick(m)
        for r2 in ((1, 2, 3, 4, 5, 7, 8, 9, 12, 15, 16) if kind != 'x2' else ()):
            _plot_case(eng, m, kind, g, 10, 40, r2, c, 'height')
            tick(m)
        if kind == 'm3':
            for col in (-2, -1):                # over the left edge: the sprite goes off it
                slots = _plot_case(eng, m, kind, g, col, 40, rows, c, 'left edge')
                tick(m)
    # the same address with other contents (armour, levels): a new upload
    kind, g, rows, m = images[0]
    mm = bytearray(m)
    _plot_case(eng, mm, kind, g, 8, 40, rows, c, 'contents')
    tick(mm)
    mm[g + 1] ^= 0x18
    mm[g + 10 * rows - 1] ^= 0x18
    _plot_case(eng, mm, kind, g, 8, 40, rows, c, 'contents')
    tick(mm)
    # eviction: more images than groups, tick after tick
    mi = bytearray(images[0][3])
    for j in range(80):
        g2 = 0xC000 + j * 0x80
        _plot_case(eng, mi, 'm3', g2, 2 + j % 20, 40, 8, c, 'eviction')
        if j % 3 == 2:
            tick(mi)
    tick(mi)
    tick(mi)
    if eng.ns.visible():
        c['hide after ticks!'] += 1
    # too many sprites in one pass: the hook stops, nothing breaks
    eng2 = Engine(patch)
    for j in range(70):
        R = [0] * 29
        R[12] = 0xFF00
        for k, v in _loop_regs('m3', 0xC000, 4, 40, 12).items():
            R[k] = v
        rr, ov, t, done2, romw = eng2.hook(mi.__getitem__, R, s['e_m3'], M3_RET)
        if not done2:
            c['too many: no return!'] += 1
    c['too many'] += 1
    if len(eng2.ns.visible()) > 124:
        c['too many: slots!'] += 1
    # bad rows
    eng3 = Engine(patch)
    for bad in (0, 17, 200):
        R = [0] * 29
        R[12] = 0xFF00
        R[2], R[19], R[18] = bad, 1, 0
        R[4], R[5] = 0xC0, 0
        R[6], R[7] = 0x48, 2
        rr, ov, t, done2, romw = eng3.hook(mi.__getitem__, R, s['e_m3'], M3_RET)
        c['bad rows'] += 1
        if not done2 or eng3.ns.visible():
            c['bad rows!'] += 1
    # the colour map: a colour, a wrong check, none
    g = images[0][1]
    m = images[0][3]
    kind = images[0][0]
    rows = images[0][2]
    if kind == 'm3' and g >= GB:
        addr = g + 1
        v = m[addr]
        cmap = {'%04X' % addr: [v, 'g', [3] * 8]}
        pg = GngPatch(colours=cmap, page_code=patch.code)
        pg.build_plane()
        e4 = Engine(pg)
        R = [0] * 29
        R[12] = 0xFF00
        for k, val in _loop_regs(kind, g, 10, 40, rows).items():
            R[k] = val
        e4.hook(m.__getitem__, R, s['e_m3'], M3_RET)
        vis = e4.ns.visible()
        data = e4.ns.pat[vis[1][1] * 128:vis[1][1] * 128 + 128]     # right sprite holds column 2: first line's byte
        c['colour map'] += 1
        if data[0] != 0x33 or data[1] != 0x33:
            c['colour map!'] += 1
        pw = GngPatch(colours={'%04X' % addr: [v ^ 1, 'g', [3] * 8]}, page_code=patch.code)
        pw.build_plane()
        e5 = Engine(pw)
        e5.hook(m.__getitem__, R, s['e_m3'], M3_RET)
        vis = e5.ns.visible()
        data = e5.ns.pat[vis[1][1] * 128:vis[1][1] * 128 + 128]
        c['colour map wrong check'] += 1
        if data[0] == 0x33 and data[1] == 0x33:
            c['colour map wrong check!'] += 1
    return c


# ---------------------------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------------------------

def _code_patch(patch, sym, old, new, count=1):
    code = bytearray(patch.code)
    o = patch.syms[sym] - 0x2000
    i = code.find(old, o)
    if i < 0:
        raise ValueError('control: %s not found after %s' % (old.hex(), sym))
    code[i:i + len(old)] = new
    return bytes(code)


def _ntab(patch):
    code = bytearray(patch.code)
    o = patch.syms['ntab'] - 0x2000
    for k in range(512):
        code[o + k] = (code[o + k] & 0xF0 if code[o + k] & 0xF0 != 0x20 else 0x10) | (code[o + k] & 15 if code[o + k] & 15 != 2 else 1)
    return bytes(code)


def negative_patches(patch):
    P = lambda **k: GngPatch(colours={}, **k)
    s = patch
    body = P()
    body.build_plane()
    corrupt = bytearray(body.pl)
    from . import gng_art as art
    for i, q in enumerate(art.catalog()):
        offset = (art.DATA_PAGE - 2 * PLANE_BANKS[0]) * 8192 + i * 1024 + 256
        for j in range(offset, offset + 512):
            v = corrupt[j]
            corrupt[j] = (0x10 if v >> 4 == 2 else v & 0xF0) | (1 if v & 15 == 2 else v & 15)
    body.pl = bytes(corrupt)
    return {
        'plot as the wrong kind': P(page_code=_code_patch(s, 'e_m3', b'\x0E\x00\xEB', b'\x0E\x01\xEB')),
        'loop stand-in: wrong H': P(page_code=_code_patch(s, 'e_m3', bytes.fromhex('7887846706'), bytes.fromhex('7887006706'))),
        'loop stand-in: wrong DE': P(page_code=_code_patch(s, 'e_m3', bytes.fromhex('110600195E'), bytes.fromhex('110700195E'))),
        'X off by a column': P(page_code=_code_patch(s, 'attrs', b'\xC6\x04\x6F', b'\xC6\x05\x6F')),
        'Y off by a line': P(page_code=_code_patch(s, 'attrs', b'\xC6\x20\x32', b'\xC6\x21\x32')),
        'tick hides nothing': P(page_code=_code_patch(s, 'e_tick', b'\xCD' + s.syms['hide'].to_bytes(2, 'little'), b'\0\0\0')),
        'clear hides nothing': P(page_code=_code_patch(s, 'hideall', b'\xCD' + s.syms['hide'].to_bytes(2, 'little'), b'\0\0\0')),
        'hook loses BC': P(page_code=_code_patch(s, 'e_x2', bytes.fromhex('C1') * 0 + bytes.fromhex('E1D1C1F1ED7BA4BF'), bytes.fromhex('E1D1E1F1ED7BA4BF'))),
        'hook writes game memory': P(page_code=_code_patch(s, 'plot', bytes.fromhex('ED53') + s.syms.get('sum', 0).to_bytes(2, 'little'), bytes.fromhex('ED530060'))),
        'plane left mapped': P(page_code=_code_patch(s, 'atlas_compare', bytes.fromhex('ED91520A'), bytes.fromhex('ED91521A'))),
        'speed left high': P(page_code=_code_patch(s, 'plot', b'\x3A' + s.syms['speed'].to_bytes(2,'little') + bytes.fromhex('ED9207'), bytes.fromhex('3E0100ED9207'))),
        'R advanced by one less': P(page_code=_code_patch(s, 'm3_r_target', bytes.fromhex('D60C'), bytes.fromhex('D60D'))),
        'score bar copy broken': P(page_code=_code_patch(s, 'e_hud', bytes.fromhex('D17EA3B2772D'), bytes.fromhex('D17EA3B2002D'))),
        'tick IY wrong': P(page_code=_code_patch(s, 'e_tick', bytes.fromhex('FD2170BF'), bytes.fromhex('FD2171BF'))),
        'no masked hook': P(drop_sites=(M3,)),
        'no draw pass hook': P(drop_sites=(TICK,)),
        'store changes a register': P(store_op=0x47),
        'body drawn as ink': body,
    }


def negative_real(patch, rzx_path, stop=3000, others=()):
    """-> {control: failures on the real recording}; recordings in others are tried if the first shows nothing."""
    res = {}
    for k, p in negative_patches(patch).items():
        n = 0
        for r in (rzx_path,) + tuple(others):
            c, ex, st = verify(p, r, stop=stop)
            n = sum(v for kk, v in c.items() if kk.endswith('!'))
            if n:
                break
        res[k] = n
    return res


# ---------------------------------------------------------------------------------------------
# Colours: recolour, identity, sheets
# ---------------------------------------------------------------------------------------------

NOTE = ("Ghosts 'n Goblins native ink colours: complete image identity + byte offset, eight flat palette indices per byte. "
        'Exact full-image checks distinguish graphics rewritten at the same address. Clipped images inherit their complete parent. '
        'Interior black detail remains; Enhanced removes only exterior black padding from unarmoured Arthur. Enhanced is an optional menu set, off by default.')
RECOLOUR = {'game': 'ghosts_n_goblins', 'output': 'enhanced', 'colours': 'docs/profiles/ghosts_n_goblins_colours.json', 'clear': False, 'note': NOTE}


def _unpatched(peek):
    old = {}
    for a, o, new in GngPatch(colours={}).sites:
        if bytes(peek(a + k) for k in range(len(new))) == new:
            for k in range(len(o)):
                old[a + k] = o[k]
    return lambda a: old.get(a, peek(a))


def colour_identity(peek):
    from . import gng_art
    return gng_art.identity()


def recolour(nex, cmap, palette=None):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build."""
    from .recolour import banks, nex_peek, splice
    cmap = fill_checks({k: list(v) for k, v in (cmap or {}).items()})    # a map as stored: null checks
    have = banks(nex)
    if not {5, 2, 0, PAGE // 2} | set(PLANE_BANKS) <= set(have):
        raise ValueError("not a Ghosts 'n Goblins sprite build")
    peek = nex_peek(nex)
    p = GngPatch(colours=cmap)
    for a, old, new in p.sites:
        if a in {x[0] for x in HUD_THEME}:
            allowed=next((o,t) for aa,o,t in HUD_THEME if aa==a)
            if peek(a) not in allowed:raise ValueError('Unexpected score-bar colour operand')
            continue
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    if have[PAGE // 2] != p.page + bytes(8192):
        raise ValueError("hook page differs from this version's (rebuild with nexclash.py auto)")
    p.build_plane()
    update = plane_banks(p.pl)
    if set(update) - set(have):
        raise ValueError('colour plane needs banks this .nex does not have')
    hudbank=bytearray(have[5])
    for a,old,themed in HUD_THEME:hudbank[a-0x4000]=themed if p.hud_theme else old
    update[5]=bytes(hudbank)
    pal = palette or (json.load(open(os.path.join(_HERE, '..', 'docs', 'profiles', 'ghosts_n_goblins_palette.json'))) if any(':' in k for k in cmap) else PALETTE)
    stub = bytearray(have[10]); po = p.syms['pal'] - 0xC000
    stub[po:po+16] = bytes(pal); update[10] = bytes(stub)
    out, changed = splice(nex, update)
    return out, {'banks changed': changed, 'map entries used': len(cmap), 'map entries ignored': 0}


def capture(rzx_paths):
    """Every image plotted on the recordings: {(kind, g, rows): bytes as first plotted}."""
    from . import rzx as RZ
    out = {}
    for path in rzx_paths:
        def on(pc, sim):
            R, M = sim.registers, sim.memory
            if pc == M3:
                k = ('m3', R[4] << 8 | R[5], R[2] + 4 * (R[19] - 1) + R[18])
            elif pc == O3:
                k = ('o3', R[6] << 8 | R[7], R[3])
            else:
                k = ('x2', R[6] << 8 | R[7], 4)
            if k not in out:
                out[k] = bytes(M[k[1]:k[1] + KIND_ROW[k[0]] * k[2]])
        RZ.trace(path, set(ENTRIES), on)
    return out


def image_part(kind, g, rows, data):
    px, ent = [], {}
    layout = LAYOUT[kind]
    w = len(layout[0]) * 8
    for i in range(rows):
        for ll, row in enumerate(layout):
            for c, (go, mo) in enumerate(row):
                o = i * KIND_ROW[kind]
                d = data[o + go]
                mk = data[o + mo] if mo is not None else 0xFF
                a = g + o + go
                key = '%04X' % a
                paintable = a >= GB
                if paintable:
                    ent[key] = [d, 'g']
                for b in range(8):
                    code = 1 if d >> (7 - b) & 1 else (2 if not mk >> (7 - b) & 1 else 0)
                    if paintable:
                        px.append((c * 8 + b, 2 * i + ll, key, b, code, code))
    return {'id': '%s_%04x_%d' % (kind, g, rows), 'size': 1, 'w': w, 'h': 2 * rows, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
            'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 'figures'}


def _legacy_sheets(z80, rzx_paths, out_dir, prefix='ghosts_n_goblins', colours=None, say=print):
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    imgs = capture(rzx_paths)
    seen = {}
    comps = []
    conflict = 0
    for (kind, g, rows), data in sorted(imgs.items(), key=lambda kv: -kv[0][2]):
        part = image_part(kind, g, rows, data)
        if not part['entries']:
            continue
        clash = [k for k, v in part['entries'].items() if k in seen and seen[k] != v[0]]
        if clash:
            conflict += 1
            continue
        new = [k for k in part['entries'] if k not in seen]
        if not new:
            continue
        for k, v in part['entries'].items():
            seen[k] = v[0]
        comps.append({'count': 1, 'group': 'figures', 'parts': [part]})
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    get = lambda a: mem[a & 0xFFFF]
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb, colours=cmap,
                  paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb, colours=cmap,
                  paint_clear=True, identity=ident)
    say('Sheets    : %d images seen, %d on the sheet, %d left off as other graphics at the same address; painting %d, reference %d' % (
        len(imgs), len(comps), conflict, n1, n2))
    return n1, n2


def sheets(z80, rzx_paths, out_dir, prefix='GHOSTS_N_GOBLINS', colours=None, say=print):
    from . import gng_art
    cmap = load_colours() if colours is None else colours
    palette = json.load(open(os.path.join(_HERE, '..', 'docs', 'profiles', 'ghosts_n_goblins_palette.json')))
    result = gng_art.sheets(out_dir, cmap, palette, prefix=prefix)
    say('Sheets    : %d complete editable images; %d recorded variants in reference' % result)
    return result


# ---------------------------------------------------------------------------------------------
# The whole run
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : gng (figure stores in three plot loops -> NOPs; each loop gives sprites; the ULA keeps the scenery; the score bar weapon keeps a copy of the loop)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    from . import gng_art
    gng_art.use_game(z80, list(a.rzx or []))   # the figure graphics come from the player's snapshot and recordings
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                        'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = GngPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                         'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ecm = load_colours()                         # the Enhanced palette goes with a map (an empty map: recolour's default)
    enhanced = GngPatch(colours=ecm, palette=json.load(open(os.path.join(_HERE, '..', 'docs', 'profiles', 'ghosts_n_goblins_palette.json'))) if ecm else None)
    enh = os.path.join(out, name + '_enhanced.nex')
    ce = zt.convert(z80, enh, None, True, quiet=True, patch=enhanced)
    bade = check(enh, z80, enhanced, (ce[1], ce[1] + len(ce[2])))
    say('Enhanced  : %s  %s  boot %s (optional menu set, off by default)' % (
        os.path.basename(enh), md5(enh), 'OK' if not bade else 'MISMATCH %s' % str(bade[:3])))
    ok = not bad and not bad2 and not bade
    states = []
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=40)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d ticks, %d screens compared, %d memory checks, clears %d, level starts %d, most sprites %d -> %s' % (
            os.path.basename(r), c['frames'], c['ticks'], c['screens compared'], c['memory checks'], c['screen clears'], c['level starts'], c['most sprites'],
            'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            plots: %s; score bar %d' % (', '.join('%s %d' % (k[6:], c[k]) for k in sorted(c) if k.startswith('plots ')), c['score bar plots']))
        say('            bytes under a figure, drawn over or XOR: %d; right edge, a figure wrapped or left there: %d' % (
            c['bytes under a figure: something the original drew over it, or XOR (depth, not logic)'],
            c['bytes at the right edge: a figure the original wraps there, or left there']))
        if c['hook T']:
            say('Speed     : hooks %d simulated T in %d ticks, most in a tick %d T; native elapsed timing measured separately; a tick is about %d frames' % (
                c['hook T'], c['ticks'], c['tick T max'], c['frames'] // max(c['ticks'], 1)))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(u.items())), 'PASS' if not uf else 'FAIL'))
        if a.rzx:
            rz = list(a.rzx)
            res = negative_real(patch, rz[0], stop=min(getattr(a, 'quick', None) or 4000, 4000), others=tuple(rz[1:]))
            miss = [k for k, n in res.items() if not n]
            ok = ok and not miss
            say('Negative  : %d of %d detected %s' % (len(res) - len(miss), len(res), miss or ''))
            for k, n in res.items():
                say('            %s: %d failures' % (k, n))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 4 and sys.argv[1] == 'sheet':
        sheets(sys.argv[2], sys.argv[4:], sys.argv[3])
