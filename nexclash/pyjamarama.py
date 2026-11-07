"""Pyjamarama (Mikro-Gen 1984, 48K) engine 'pyjamarama'. Additive module: reachable only through is_pyjamarama().

Game facts (games/pyjamarama.md): a pure XOR plotter 43758 (A = graphic, 43755 x, 43756 y; 16 x 16, 1 bit, at 37355 + 32A)
draws every figure on the screen; a second identical call rubs it out. Interrupts off in play; no reads of pixels by logic.
Hooks (asm/pyjamarama_hooks.asm, RAM page PAGE at 0x2000-0x3FFF): the plotter runs on with its three screen writes as NOPs, so
every register and all game memory stay the original's; (A, x, y) is toggled in a list, which becomes sprites at the delay
routine 44092. The player's attribute block is no longer painted (the three LD (HL),70 become one-M1 JR +0 instructions).
"""
import collections
import hashlib
import json
import os

PAGE = 24                   # hook page at MMU slot 1 (bank 12, first half)
PAT_PAGE = 26               # patterns: pages 26-29 (banks 13, 14), mapped at slot 3 only during an upload
HOME3 = 11
TAIL_ADDR = 0x8110          # zeros, the old USR 33040 target; never touched on any recording (work/scan)
GFX = 37355
XPOS, YPOS = 43755, 43756
ROWS = 36971
YMIN = 40
PLOT, PLOT_CONT, PLOT_RET = 43758, 43761, 43860
WAIT, WAIT_CONT = 44092, 44097
WIPE, WIPE_CONT = 57896, 57899
CLR, CLR_CONT = 44969, 44972
CLR_PIX_DONE, CLR_DONE = 44982, 44989
PAINT = (44902, 44908, 44920)
SAVE = (44900, 44906, 44918)
ATTR_READ = 49317
DYN = (43840, 43844, 43848)
SITES_ORIG = {43758: 'f3f5e5', 44092: 'c5f501', 57896: 'e5c5d5', 44969: '210040', 44902: '3646', 44908: '3646', 44920: '3646'}
INTERIORS = (44970, 44971, 44903, 44909, 44921, 44095, 44096)
SEQUELS = {43759: 43758, 43760: 43758, 44093: 44092, 44094: 44092, 57897: 57896, 57898: 57896}
ITEMS = [76] + list(range(79, 114))     # the lives icon and collectable items, static on the ULA
FIGURES = list(range(200))  # every figure and collectable below the HUD
PLAYER = set(range(76)) | {77, 78}
NPAT = len(FIGURES)
NMAX = 32
SAVED = 44587               # the player's saved attribute block, 3 bytes per row
# Sprite palette: index -> Next colour. 0 transparent, 1 bright white, 2 black, then the Spectrum's others.
SPECCY = [0x00, 0xFF, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC]
INK_SLOT = {(0, 0): 2, (1, 0): 3, (2, 0): 4, (3, 0): 5, (4, 0): 6, (5, 0): 7, (6, 0): 8, (7, 0): 9,
            (0, 1): 2, (1, 1): 10, (2, 1): 11, (3, 1): 12, (4, 1): 13, (5, 1): 14, (6, 1): 15, (7, 1): 1}
CMP = list(range(0, 13)) + [14, 15] + list(range(16, 25)) + [26, 27]   # all architectural state including R; excluding T and MEMPTR

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'pyjamarama_colours.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'pyjamarama.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_pyjamarama(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from .recolour import build_colours_path
    p = path or build_colours_path(COLOURS)
    if p and os.path.exists(p):
        from .coloursheet import load
        return load(p)
    return {}


# ---------------------------------------------------------------------------------------------
# Patterns: 128 bytes per graphic. Default colour: the ink of the cell the game most often draws that graphic in.
# ---------------------------------------------------------------------------------------------

def default_inks():
    return {int(k): v for k, v in load_profile()['default_attr'].items()}


def default_slot(a, inks=None):
    at = (inks or default_inks()).get(a, 70)
    return INK_SLOT[(at & 7, (at >> 6) & 1)]


def rows(peek, a):
    g = GFX + 32 * a
    return [peek(g + 2 * r) << 8 | peek(g + 2 * r + 1) for r in range(16)]


def gkey(a, r, b):
    return '%04X' % (GFX + 32 * a + 2 * r + b)


def pattern(peek, a, cmap=None, inks=None):
    out = bytearray(128)
    d = default_slot(a, inks)
    for r, w in enumerate(rows(peek, a)):
        for k in range(16):
            ink = w >> (15 - k) & 1
            v = d if ink else 0
            if cmap:
                key = gkey(a, r, k >> 3)
                e = cmap.get(key)
                if e is not None and (e[0] is None or e[0] == peek(int(key, 16))):   # stored maps: null check
                    bit = k & 7
                    if len(e) > 3 and e[3] & (0x80 >> bit):
                        v = 0
                    elif e[2][bit]:
                        v = e[2][bit]
            out[r * 8 + k // 2] |= v << 4 if k % 2 == 0 else v
    return bytes(out)


def patterns(peek, cmap=None):
    inks = default_inks()
    return b''.join(pattern(peek, a, cmap, inks) for a in FIGURES)


def pattern_banks(pats):
    b = pats + bytes(32768 - len(pats))
    return {13: b[:16384], 14: b[16384:]}


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

class PyjamaramaPatch:
    name = 'Pyjamarama figures -> hardware sprites (hooks in a slot-1 RAM page)'

    def __init__(self, prof=None, page_code=None, colours=None, drop_sites=(), figures=None, palette=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.code = page_code or bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.palette = list(palette or SPECCY)
        setup = bytearray.fromhex(h['setup'])
        pal = self.syms['pal'] - 0xD000
        setup[pal:pal + 16] = bytes(self.palette)
        self.stub_extra = bytes(setup)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.slot1 = (PAGE, self.syms['regs'])
        self.altrom = (0x2000, 0x2000)  # full Sinclair image; no hook bytes in hidden ROM
        self.ram_slot1_after_alt = True  # state and self-modifying hooks remain writable
        s = self.syms
        page = bytearray(8192)
        page[:len(self.code)] = self.code
        o = s['pidx'] - 0x2000
        page[o:o + 256] = b'\xFF' * 256
        for i, a in enumerate(figures if figures is not None else FIGURES):
            page[o + a] = i
        o = s['slotof'] - 0x2000
        page[o:o + 256] = b'\xFF' * 256
        o = s['owner'] - 0x2000
        page[o:o + 128] = b'\xFF' * 128
        self.page = bytes(page)
        self.colours = load_colours() if colours is None else colours
        new = {43758: b'\xC3' + s['e_plot'].to_bytes(2, 'little'), 44092: b'\xC3' + s['e_wait'].to_bytes(2, 'little'),
               57896: b'\xC3' + s['e_wipe'].to_bytes(2, 'little'), 44969: b'\xC3' + s['e_clr'].to_bytes(2, 'little'),
               44902: b'\x18\x00', 44908: b'\x18\x00', 44920: b'\x18\x00'}
        self.sites = [(a, bytes.fromhex(old), new[a]) for a, old in SITES_ORIG.items() if a not in drop_sites]
        self.extra_banks = {PAGE // 2: self.page + bytes(8192)}
        self.pats = None

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Pyjamarama patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected version of Pyjamarama'
                                 % (a, cur.hex(), old.hex()))
        cmap = load_colours() if self.colours is None else self.colours
        self.pats = patterns(lambda a: ram[a - 0x4000], cmap)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = dict(pattern_banks(self.pats))
        self.extra_banks[PAGE // 2] = self.page + bytes(8192)


# ---------------------------------------------------------------------------------------------
# Next-side model
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self):
        self.nr = {0x53: HOME3, 7: 0}
        self.selected = 0
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.patmem = bytearray(16384)
        self.patptr = 0
        self.bad = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg not in (0x34, 0x53, 7):
            self.bad.append(('nextreg', reg))

    def out(self, port, v):
        if port == 0x243B:
            self.selected = v
        elif port == 0x253B:
            self.nextreg(self.selected, v)
        elif port == 0x303B:
            self.patptr = ((v & 63) << 8) | ((v & 0x80) >> 0)
        elif port & 0xFF == 0x5B:
            self.patmem[self.patptr & 0x3FFF] = v
            self.patptr += 1
        else:
            self.bad.append(('out', port))

    def visible(self):
        """-> [(slot in 128-byte units, x, y)]. Anything but a plain 4-bit sprite is a failure for the caller."""
        out = []
        for i, (a0, a1, a2, a3, a4) in enumerate(self.attr):
            if not a3 & 0x80:
                continue
            s = ((a3 & 0x3F) << 1) | ((a4 >> 6) & 1)
            if not a3 & 0x40 or not a4 & 0x80 or a4 & 0x3F or a2 & 0xFE:
                self.bad.append(('sprite form', i, (a0, a1, a2, a3, a4)))
            out.append((s, a0 + (a2 & 1) * 256 - 32, a1 - 32))
        return out


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _rom():
    from .build import rom48
    return rom48()


class _PMem:
    """Patched view: ROM below 0x2000, the hook page at 0x2000-0x3FFF, the patched screen, patch sites, a pattern page at slot 3
    while one is mapped; game memory read through get; writes to the site bytes kept, others to an overlay."""

    def __init__(s, eng, get):
        s.e, s.get, s.ov, s.romw = eng, get, {}, 0

    def __getitem__(s, a):
        e = s.e
        if a < 0x2000:
            return e.rom[a]
        if a < 0x4000:
            return e.page[a - 0x2000]
        if a < 0x5B00:
            return e.scr[a - 0x4000]
        if 0x6000 <= a < 0x8000:
            p = e.ns.nr.get(0x53, HOME3)
            if p != HOME3:
                b = e.patpages.get(p)
                return b[a - 0x6000] if b is not None else 0
        v = s.ov.get(a)
        if v is not None:
            return v
        v = e.psite.get(a)
        if v is not None:
            return v
        return s.get(a)

    def __setitem__(s, a, v):
        e = s.e
        if a < 0x2000:
            s.romw += 1
        elif a < 0x4000:
            e.page[a - 0x2000] = v
        elif a < 0x5B00:
            e.scr[a - 0x4000] = v
        elif a in DYN:
            e.psite[a] = v
        else:
            s.ov[a] = v

    def __len__(s):
        return 65536


def _machine(mem, regs, ns):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(_rw(), mem, regs, 'p')
    from . import z80n
    z80n.install(sim, ns.nextreg)

    class Tr:
        def read_port(s, regs_, port):
            if port == 0x253B:
                v = ns.nr.get(ns.selected, 0)
                return v | (v << 4) if ns.selected == 7 else v
            ns.bad.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=400000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


class Engine:
    """Persistent patched state: hook page, Next state, patched screen + attributes, the model's figure list."""

    def __init__(self, patch, get):
        self.patch = patch
        self.page = bytearray(patch.page)
        self.psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
        self.rom = _rom()
        self.scr = bytearray(get(a) for a in range(0x4000, 0x5B00))
        snap = bytes(get(a) for a in range(65536))
        self.gpeek = lambda a: snap[a]
        self.pats = patterns(self.gpeek, patch.colours or {})
        bk = pattern_banks(self.pats)
        self.patpages = {PAT_PAGE: bk[13][:8192], PAT_PAGE + 1: bk[13][8192:], PAT_PAGE + 2: bk[14][:8192], PAT_PAGE + 3: bk[14][8192:]}
        self.pidx = {a: patch.page[patch.syms['pidx'] - 0x2000 + a] for a in range(256)}
        self.ns = NextState()
        self.live = set()
        self.xcache = {}
        self.tplot = []
        self.twait = []
        self.pending = None
        self.lost = {}              # screen offset -> figure bits the original lost to a tile drawn over a live figure
        self.tiled = set()          # attribute offsets written by a tile since the player's block was saved

    def absolute(self, o, v, c):
        """A tile byte over the screen: both versions hold v; a live figure's bits there are gone from the original only."""
        self.scr[o] = v
        m = 0
        for a, x, y in self.live:
            for q, b in self.xor_bytes(a, x, y):
                if q == o:
                    m ^= b
        if m:
            self.lost[o] = m
            c['screen bytes the original overwrote on a live figure'] += 1
        else:
            self.lost.pop(o, None)

    def figure(self, a, y):
        return self.pidx[a] != 0xFF and y >= YMIN

    def xor_bytes(self, a, x, y):
        """-> [(offset into the screen, byte)] the original's XOR of this figure."""
        k = (a, x, y)
        v = self.xcache.get(k)
        if v is None:
            v = []
            xs = x & 7
            for r, w in enumerate(rows(self.gpeek, a)):
                ptr = self.gpeek(ROWS + 2 * (y + r)) | self.gpeek(ROWS + 2 * (y + r) + 1) << 8
                hl = ptr + (x >> 3)
                b = w << (8 - xs) if xs else w << 8
                if xs:
                    v.append((hl - 0x4000, b & 255))
                v.append((hl - 1 - 0x4000, (b >> 8) & 255))
                v.append((hl - 2 - 0x4000, (b >> 16) & 255))
            if len(self.xcache) < 60000:
                self.xcache[k] = v
        return v

    def composite(self):
        s = bytearray(self.scr)
        for a, x, y in self.live:
            for o, b in self.xor_bytes(a, x, y):
                s[o] ^= b
        for o, m in self.lost.items():
            s[o] ^= m
        return s


def plot_event(eng, get, R, c, fail):
    """At 43758 in the original: run the patched plotter to its RET on the patched screen; the result is compared at the RET."""
    a, x, y = R[0], get(XPOS), get(YPOS)
    incoming_speed = eng.ns.nr.get(7, 0)
    fig = eng.figure(a, y)
    start = list(R)
    start[24] = PLOT
    t0 = R[25]
    p = _PMem(eng, get)
    sim = _machine(p, start, eng.ns)
    if not _run(sim, lambda r: r[24] == PLOT_CONT):
        fail('plot hook did not return')
        return
    eng.tplot.append(sim.registers[25] - t0)
    if eng.ns.nr.get(7, 0) != incoming_speed:
        fail('plot: incoming speed not restored')
    if eng.ns.nr.get(0x53, HOME3) != HOME3:
        fail('slot 3 not put back')
    if not _run(sim, lambda r: r[24] == PLOT_RET):
        fail('plot did not return')
        return
    if fig:
        k = (a, x, y)
        if k in eng.live:
            eng.live.remove(k)
            c['figure erases'] += 1
        else:
            if len(eng.live) < NMAX:
                eng.live.add(k)
            c['figure draws'] += 1
    eng.pending = (list(sim.registers), p)


def plot_ret(eng, get, R, fail):
    rp, p = eng.pending
    eng.pending = None
    diff = [i for i in CMP if R[i] != rp[i]]
    if diff:
        fail('plot: registers differ', (diff[:6], [R[i] for i in diff[:3]], [rp[i] for i in diff[:3]]))
    md = [a for a, v in p.ov.items() if get(a) != v]
    if md:
        fail('plot: game memory differs', (len(md), md[:4]))
    if p.romw:
        fail('plot: wrote ROM')


def side_entry(eng, get, R, entry, cont, pushes, fail, name, hl=None):
    """A hook that replaces the first instructions of a routine: at `cont` the same registers + the same pushes; no game memory."""
    incoming_speed = eng.ns.nr.get(7, 0)
    start = list(R)
    start[24] = entry
    t0 = R[25]
    p = _PMem(eng, get)
    sim = _machine(p, start, eng.ns)
    if not _run(sim, lambda r: r[24] == cont):
        fail(name + ': hook did not return')
        return None
    rp = sim.registers
    if eng.ns.nr.get(7, 0) != incoming_speed:
        fail(name + ': incoming speed not restored')
    want = list(R)
    want[24] = cont
    original_m1 = 1 if name == 'clear' else 3
    want[15] = (R[15] & 128) | ((R[15] + original_m1) & 127)
    want[12] = (R[12] - 2 * len(pushes)) & 0xFFFF
    if hl is not None:
        want[6], want[7] = hl >> 8, hl & 255
    if name == 'wait':
        v = get(44095) | get(44096) << 8
        want[2], want[3] = v >> 8, v & 255
    diff = [i for i in CMP if want[i] != rp[i]]
    if diff:
        fail(name + ': registers differ', (diff[:6], [want[i] for i in diff[:3]], [rp[i] for i in diff[:3]]))
    sp = R[12]
    for i, (hi, lo) in enumerate(pushes):
        s = (sp - 2 * (i + 1)) & 0xFFFF
        if p[s] != R[lo] or p[(s + 1) & 0xFFFF] != R[hi]:
            fail(name + ': stack differs')
    md = [a for a in p.ov if not sp - 2 * len(pushes) <= a < sp]
    if md:
        fail(name + ': game memory written', (len(md), md[:4]))
    if p.romw:
        fail(name + ': wrote ROM')
    return rp[25] - t0


def check_sprites(eng, get, c, fail):
    """The Next's sprites = the model's list: position, and the pattern each slot really holds."""
    ns = eng.ns
    if ns.bad:
        fail('next: unexpected access', tuple(ns.bad[:3]))
        ns.bad.clear()
    vis = ns.visible()
    if ns.bad:
        fail('next: sprite form', tuple(ns.bad[:3]))
        ns.bad.clear()
    want = collections.Counter((pos[1], pos[2]) for pos in eng.live)
    got = collections.Counter((x, y) for s, x, y in vis)
    if want != got or len(vis) != len(eng.live):
        fail('sprites differ from the list', (sorted(want)[:4], sorted(got)[:4]))
        return
    lv = collections.defaultdict(list)
    for a, x, y in eng.live:
        lv[(x, y)].append(a)
    for s, x, y in vis:
        pm = bytes(ns.patmem[s * 128:s * 128 + 128])
        cands = lv[(x, y)]
        ok = any(eng.pats[eng.pidx[a] * 128:eng.pidx[a] * 128 + 128] == pm for a in cands)
        if not ok:
            fail('a sprite shows the wrong pattern', (s, x, y, cands[:3]))
    c['sprite pixels'] += sum(bin(b).count('1') for a, x, y in eng.live for b in rows(eng.gpeek, a))
    c['most sprites'] = max(c['most sprites'], len(vis))


def check_screen(eng, mem, c, fail, ex_b):
    want = bytes(mem[0x4000:0x5800])
    s = eng.composite()
    c['screens compared'] += 1
    if bytes(s[:6144]) != want:
        bad = [i for i in range(6144) if s[i] != want[i]]
        fail('screen: patched + figures differs from the original', (len(bad), [hex(0x4000 + i) for i in bad[:4]]))
    at = bytes(mem[0x5800:0x5B00])
    pa = bytes(eng.scr[6144:6912])
    if at != pa:
        bad = [i for i in range(768) if at[i] != pa[i]]
        c['attribute cells the original painted'] += len(bad)
        nb = [i for i in bad if at[i] != 70]
        if nb:
            fail('attributes differ other than the player paint', (len(nb), [(hex(0x5800 + i), at[i], pa[i]) for i in nb[:4]]))


def check_player_block(eng, get, fail):
    """Player drawn: the ULA holds what the original saved, not paint."""
    if not any(a in PLAYER for a, x, y in eng.live):
        return
    x, y = get(43898), get(43899)
    if get(44800) == 0:
        n = 4
    else:
        n = 5
    base = 0x5800 + (y & 0xF8) * 4 + (x >> 3) - 0x4000
    for i in range(n):
        for k in range(3 if x & 7 else 2):
            o = base + 32 * i + k
            if o < 6912 and o not in eng.tiled and eng.scr[o] != get(SAVED + 3 * i + k):
                fail('player block: not the saved attributes', (hex(o + 0x4000), eng.scr[o], get(SAVED + 3 * i + k)))
                return


def wipe_model(eng, get):
    """57896: each byte of 152 rows from line 40 is shifted out; attributes come by their own writer."""
    for y in range(40, 192):
        ptr = get(ROWS + 2 * y) | get(ROWS + 2 * y + 1) << 8
        o = ptr - 2 - 0x4000
        eng.scr[o:o + 32] = bytes(32)
    eng.lost.clear()


# writers of the screen other than the plotter: pc -> (address, value) from the registers
WRITERS = {
    49477: lambda R, g: (R[4] << 8 | R[5], R[0]),              # LD (DE),A   tile
    58588: lambda R, g: (R[6] << 8 | R[7], 0),                 # LD (HL),0   HUD panel clear
    57916: lambda R, g: (R[6] << 8 | R[7], R[4]),              # LD (HL),D   room colour
    49439: lambda R, g: (R[6] << 8 | R[7], R[3]),              # LD (HL),C   tile colour
    49339: lambda R, g: (R[6] << 8 | R[7], R[3]),              # LD (HL),C
    49346: lambda R, g: (R[6] << 8 | R[7], R[3]),              # LD (HL),C
    44654: lambda R, g: (R[6] << 8 | R[7], R[0]),              # LD (HL),A   player block restore
    44658: lambda R, g: (R[6] << 8 | R[7], R[0]),
    44668: lambda R, g: (R[6] << 8 | R[7], R[0]),
    49550: lambda R, g: (R[4] << 8 | R[5], R[0]),              # LD (DE),A   tile, upside down mode
    49511: lambda R, g: (R[6] << 8 | R[7], R[3]),              # LD (HL),C   its colour
    33368: lambda R, g: (R[6] << 8 | R[7], 66),                # LD (HL),66  room 8's coloured buttons
    33382: lambda R, g: (R[6] << 8 | R[7], 71),                # LD (HL),71
}
XORS = (59260, 59265, 59271, 59278, 59284, 59289)              # the screen line XOR 44 at 59257 (a room's flicker line)
BELT_START, BELT_RR = 60173, 60185                             # a row of the screen rotated right (conveyor)
LDI = (33758, 33760, 33762, 33826, 33828, 33830, 49392, 49409)


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    st = {'eng': None}
    cnt = collections.Counter()
    states = []
    frames = collections.Counter()
    callers = collections.Counter()
    rooms = collections.Counter()
    site_orig = {a + k: v for a, old, new in patch.sites for k, v in enumerate(old)}
    site_orig.update({a: 0x77 for a in DYN})

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append(tuple(info))

    def cb(pc, sim):
        R, mem = sim.registers, sim.memory
        get = lambda a: mem[a & 0xFFFF]
        if st['eng'] is None:
            st['eng'] = Engine(patch, get)
        eng = st['eng']
        cnt[pc] += 1
        if pc == PLOT:
            c['plots'] += 1
            if eng.figure(R[0], mem[YPOS]):
                c['figure plots'] += 1
                frames[R[0]] += 1
                callers[(mem[R[12]] | mem[(R[12] + 1) & 0xFFFF] << 8) - 3] += 1
                if mem[XPOS] > 240 or mem[YPOS] > 176:
                    c['figures past the screen edge'] += 1
            else:
                c['plots left on the ULA'] += 1
            plot_event(eng, get, list(R), c, fail)
            if collect and c['collected plot'] < collect:
                c['collected plot'] += 1
                states.append(('plot', list(R), bytes(mem[a] for a in range(65536))))
        elif pc == PLOT_RET:
            if eng.pending:
                plot_ret(eng, get, list(R), fail)
        elif pc == WAIT:
            c['waits'] += 1
            rooms[mem[58693]] += 1
            t = side_entry(eng, get, list(R), WAIT, WAIT_CONT, [(2, 3), (0, 1)], fail, 'wait')
            if t is not None and t > 60:
                eng.twait.append(t)
            check_sprites(eng, get, c, fail)
            check_screen(eng, mem, c, fail, ex)
            check_player_block(eng, get, fail)
            for a, v in site_orig.items():
                if mem[a] != v:
                    fail('game wrote a patch site', (a,))
            if collect and c['collected wait'] < collect and eng.live:
                c['collected wait'] += 1
                states.append(('wait', list(R), bytes(mem[a] for a in range(65536))))
        elif pc == WIPE:
            c['wipes'] += 1
            eng.live.clear()
            side_entry(eng, get, list(R), WIPE, WIPE_CONT, [(6, 7), (2, 3), (4, 5)], fail, 'wipe')
            check_sprites(eng, get, c, fail)
            wipe_model(eng, get)
        elif pc == CLR:
            c['clears'] += 1
            eng.live.clear()
            side_entry(eng, get, list(R), CLR, CLR_CONT, [], fail, 'clear', hl=16384)
            check_sprites(eng, get, c, fail)
        elif pc == CLR_PIX_DONE:
            eng.scr[:6144] = bytes(6144)
            eng.lost.clear()
        elif pc == CLR_DONE:
            eng.scr[6144:6912] = b'\x46' * 768
        elif pc in WRITERS:
            a, v = WRITERS[pc](R, get)
            if 0x4000 <= a < 0x5800:
                eng.absolute(a - 0x4000, v, c)
                c['other screen writes'] += 1
            elif 0x5800 <= a < 0x5B00:
                eng.scr[a - 0x4000] = v
                if pc not in (44654, 44658, 44668):
                    eng.tiled.add(a - 0x4000)
                c['other screen writes'] += 1
        elif pc in XORS:
            a = R[6] << 8 | R[7]
            eng.scr[a - 0x4000] ^= 44
            c['other screen writes'] += 1
        elif pc == BELT_START:
            eng.carry = eng.scr[(R[6] << 8 | R[7]) - 0x4000] & 1
        elif pc == BELT_RR:
            o = (R[6] << 8 | R[7]) - 0x4000
            v = eng.scr[o]
            eng.scr[o] = eng.carry << 7 | v >> 1
            eng.carry = v & 1
            c['other screen writes'] += 1
        elif pc in LDI:
            d = R[4] << 8 | R[5]
            if 0x4000 <= d < 0x5800:
                eng.absolute(d - 0x4000, mem[R[6] << 8 | R[7]], c)
                c['other screen writes'] += 1
            elif 0x5800 <= d < 0x5B00:
                eng.scr[d - 0x4000] = mem[R[6] << 8 | R[7]]
                eng.tiled.add(d - 0x4000)
                c['other screen writes'] += 1
        elif pc in PAINT:
            hl = R[6] << 8 | R[7]
            b0, b1 = eng.psite.get(pc, mem[pc]), eng.psite.get(pc + 1, mem[pc + 1])
            c['paint sites'] += 1
            if (b0, b1) == (0x18, 0):
                pass                    # JR +0: no store, same M1 count as LD (HL),70
            elif (b0, b1) == (0x36, 0x46):
                eng.scr[hl - 0x4000] = 0x46
            else:
                fail('paint site holds other code', (pc,))
        elif pc in SAVE or pc == ATTR_READ:
            hl = R[6] << 8 | R[7]
            c['attribute reads'] += 1
            if pc in SAVE:
                eng.tiled.discard(hl - 0x4000)
            if 0x4000 <= hl < 0x5B00 and eng.scr[hl - 0x4000] != mem[hl]:
                # the original read its own paint or a figure: the patched game would read something else
                fail('logic would read a different attribute', (pc, hl, mem[hl], eng.scr[hl - 0x4000]))

    pcs = ({PLOT, PLOT_RET, WAIT, WIPE, CLR, CLR_PIX_DONE, CLR_DONE, ATTR_READ} | set(WRITERS) | set(LDI) | set(XORS) | {BELT_START, BELT_RR} | set(PAINT) | set(SAVE)
           | set(INTERIORS) | set(SEQUELS))
    n, err = RZ.trace(rzx_path, pcs, cb, stop=stop)
    if err:
        c['recording desynced: %s!' % err[:80]] += 1
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    for a, b in SEQUELS.items():
        if cnt[a] != cnt[b] and abs(cnt[a] - cnt[b]) > 1:
            c['%d reached other than from %d (%d / %d)!' % (a, b, cnt[a], cnt[b])] += 1
    c['frames'] = n
    eng = st['eng']
    if eng and eng.tplot:
        c['plot hook T max'] = max(eng.tplot)
        c['plot hook T mean'] = sum(eng.tplot) // len(eng.tplot)
    if eng and eng.twait:
        c['commit T max'] = max(eng.twait)
        c['commit T mean'] = sum(eng.twait) // len(eng.twait)
    extra = {'frames': frames, 'callers': callers, 'rooms': rooms}
    if collect:
        return c, dict(ex), states, extra
    return c, dict(ex), extra


# ---------------------------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------------------------

def _state_engine(patch, snap):
    get = lambda a: snap[a & 0xFFFF]
    return Engine(patch, get), get


def _call_plot(eng, get, R, a, x, y):
    """The real hook, plotter included, for (a, x, y) from register state R, with 43755/6 read from an overlay."""
    r = list(R)
    r[0] = a
    p = _PMem(eng, get)
    p.ov[XPOS], p.ov[YPOS] = x, y
    r[24] = PLOT
    sim = _machine(p, r, eng.ns)
    if not _run(sim, lambda q: q[24] == PLOT_RET):
        return None, p
    return list(sim.registers), p


def _commit(eng, get, R):
    r = list(R)
    r[24] = WAIT
    p = _PMem(eng, get)
    sim = _machine(p, r, eng.ns)
    return _run(sim, lambda q: q[24] == WAIT_CONT)


def unit_tests(patch, states, neg=None):
    """From a captured state: every graphic's decision, position edges, parity, a full list, pattern recycling, clear, setup."""
    c = collections.Counter()
    snap = None
    R0 = None
    for kind, R, s in states:
        if kind == 'wait':
            R0, snap = R, s
            break
    if snap is None:
        c['no captured state!'] += 1
        return c
    sp = 0xF700
    R0 = list(R0)
    R0[12] = sp
    fresh = lambda: _state_engine(patch, snap)

    # every graphic, position edges: drawn then rubbed out; shown with the right pattern; ULA written only for items
    for a in range(200):
        eng, get = fresh()
        before = bytes(eng.scr)
        for x, y in ((0, 40), (7, 48), (8, 100), (233, 152), (120, 39)):
            eng.scr[:] = before
            r1, p = _call_plot(eng, get, R0, a, x, y)
            if r1 is None:
                c['plot did not return!'] += 1
                continue
            c['plot cases'] += 1
            isfig = eng.pidx[a] != 0xFF and y >= YMIN
            if isfig == (bytes(eng.scr) != before):
                c['ULA written for a figure, or not for an item!'] += 1
            _commit(eng, get, R0)
            vis = eng.ns.visible()
            if isfig:
                pm = [bytes(eng.ns.patmem[s * 128:s * 128 + 128]) for s, xx, yy in vis if (xx, yy) == (x, y)]
                if eng.pats[eng.pidx[a] * 128:eng.pidx[a] * 128 + 128] not in pm:
                    c['figure not shown with its pattern!'] += 1
            _call_plot(eng, get, R0, a, x, y)
            _commit(eng, get, R0)
            if bytes(eng.scr) != before:
                c['screen not restored by the second plot!'] += 1
            if any((xx, yy) == (x, y) for s, xx, yy in eng.ns.visible()):
                c['figure not hidden by the second plot!'] += 1

    # full list: NMAX shown, the next not shown, none lost
    eng, get = fresh()
    for i in range(NMAX + 3):
        _call_plot(eng, get, R0, 0, 8 + 4 * i, 48 + i)
    _commit(eng, get, R0)
    if len(eng.ns.visible()) != NMAX:
        c['full list: %d shown!' % len(eng.ns.visible())] += 1
    c['full-list cases'] += 1
    if eng.ns.bad:
        c['full list: unexpected access!'] += 1

    # pattern recycling: every figure graphic in turn, 16 kept on show: each shown slot always holds its graphic
    eng, get = fresh()
    keep = []
    order = list(FIGURES) * 2
    for n, a in enumerate(order):
        pos = (8 + (n % 28) * 8, 48 + (n % 16) * 6)
        _call_plot(eng, get, R0, a, pos[0], pos[1])
        keep.append((a, pos))
        if len(keep) > 16:
            b, q = keep.pop(0)
            _call_plot(eng, get, R0, b, q[0], q[1])
        _commit(eng, get, R0)
        c['recycle cases'] += 1
        vis = {(x, y): s for s, x, y in eng.ns.visible()}
        for b, q in keep:
            s = vis.get(q)
            if s is None or bytes(eng.ns.patmem[s * 128:s * 128 + 128]) != eng.pats[eng.pidx[b] * 128:eng.pidx[b] * 128 + 128]:
                c['recycling: a shown figure has the wrong pattern!'] += 1
                break
        if eng.ns.nr.get(0x53) != HOME3:
            c['recycling: slot 3 not put back!'] += 1

    # clear and wipe hide everything, whatever is on show
    for entry, cont in ((CLR, CLR_CONT), (WIPE, WIPE_CONT)):
        eng, get = fresh()
        for i in range(5):
            _call_plot(eng, get, R0, 141, 16 + 20 * i, 60)
        _commit(eng, get, R0)
        r = list(R0)
        r[24] = entry
        p = _PMem(eng, get)
        sim = _machine(p, r, eng.ns)
        if not _run(sim, lambda q: q[24] == cont):
            c['clear did not return!'] += 1
        if eng.ns.visible():
            c['clear left sprites on show!'] += 1
        c['clear cases'] += 1

    # setup: palette, all hidden, sprites on
    ns = NextState()
    ok = setup_check(patch, ns)
    if not ok:
        c['setup!'] += 1
    c['setup cases'] += 1
    return c


def setup_check(patch, ns):
    from .simpool import machine
    code = patch.stub_extra
    mem = bytearray(65536)
    mem[0xD000:0xD000 + len(code)] = code
    mem[0xD000 + len(code) + 8] = 0
    seen = []
    orig = ns.nextreg

    def rec(r, v):
        seen.append((r, v))
    ns.nextreg = rec
    R = [0] * 29
    R[12] = 0xF000
    R[24] = 0xD000
    mem[0xEFFE], mem[0xEFFF] = 0, 0xC0
    sim = _machine(mem, R, ns)
    if not _run(sim, lambda q: q[24] == 0xC000, 200000):
        return False
    ns.nextreg = orig
    pal = [v for r, v in seen if r == 0x41]
    hides = [v for r, v in seen if r == 0x38]
    return pal == patch.palette and len(hides) == 128 and not any(hides) and (0x15, 1) in seen


def _code_patch(patch, sym, old, new, span=160):
    p = PyjamaramaPatch(patch.prof, colours=patch.colours, palette=patch.palette)
    code = bytearray(p.code)
    i = p.syms[sym] - 0x2000
    j = code.find(bytes.fromhex(old), i)
    if j < 0 or j > i + span:
        raise ValueError('negative patch: %s not found near %s' % (old, sym))
    code[j:j + len(bytes.fromhex(old))] = bytes.fromhex(new)
    return PyjamaramaPatch(patch.prof, bytes(code), colours=patch.colours, palette=patch.palette)


def negative_patches(patch):
    """name -> broken patch. Each is a real fault a build could have."""
    out = {}
    out['figure writes stay on'] = _code_patch(patch, 'e_plot', 'af1802', '3e77' + '00')
    out['plot hook clobbers HL'] = _code_patch(patch, 'e_plot', 'e1d1c1f1', '00d1c1f1')
    out['commit loses x bit 8'] = _code_patch(patch, 'commit', '3e008f', '3e00af')
    out['commit drops the half slot'] = _code_patch(patch, 'commit', '3e001f1f', '3e00af00')
    out['old sprites stay'] = _code_patch(patch, 'commit', 'afed9238', '00000000')
    out['upload to the wrong half'] = _code_patch(patch, 'slotfor', 'f680', 'f600')
    out['list never removes'] = _code_patch(patch, 'toggle', '3d32', '0032', span=200)
    out['player paint stays'] = PyjamaramaPatch(patch.prof, colours=patch.colours, palette=patch.palette, drop_sites=(44902, 44908, 44920))
    out['room change leaves sprites'] = PyjamaramaPatch(patch.prof, colours=patch.colours, palette=patch.palette, drop_sites=(57896,))
    return out


def negative_real(patch, rzx_path, stop=4000):
    """Each broken build on a real recording: -> {name: failures}."""
    res = {}
    for name, q in negative_patches(patch).items():
        v = verify(q, rzx_path, stop=stop)
        c = v[0]
        res[name] = sum(n for k, n in c.items() if k.endswith('!'))
    return res


# ---------------------------------------------------------------------------------------------
# Colour sheets and recolour
# ---------------------------------------------------------------------------------------------

NOTE = ('Pyjamarama colour map (docs/COLOURS.md): key = graphics byte (hex address; check = its value); 8 nibbles, 0 = default (the ink '
        'of the cell the game most often draws that graphic in; the player bright yellow); 1-15 the fixed colours; optional 4th = '
        'transparent mask')
RECOLOUR = {'game': 'pyjamarama', 'output': 'sprites', 'colours': 'docs/profiles/pyjamarama_colours.json', 'clear': True, 'note': NOTE}
PALETTE = SPECCY


def colour_identity(peek):
    return {'schema': 1, 'game': 'pyjamarama', 'engine': 'pyjamarama', 'keys': 'pyjamarama-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': hashlib.md5(bytes(peek(a) for a in range(GFX, GFX + 32 * 200))).hexdigest(), 'geometry': None}


def recolour(nex, cmap):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build."""
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    if not {5, 2, 0, 13, 14, PAGE // 2} <= set(have):
        raise ValueError('not a Pyjamarama sprite build')
    peek = nex_peek(nex)
    p = PyjamaramaPatch(colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    if have[PAGE // 2] != p.page + bytes(8192):
        raise ValueError("hook page differs from this version's (rebuild with nexclash.py auto)")
    pats = patterns(peek, cmap)
    out, changed = splice(nex, pattern_banks(pats))
    used = [k for k in cmap if cmap[k][0] is None or cmap[k][0] == peek(int(k, 16))]
    return out, {'banks changed': changed, 'map entries used': len(used), 'map entries ignored': len(cmap) - len(used)}


def frame_part(peek, a, inks):
    px, ent = [], {}
    d = default_slot(a, inks)
    for r, w in enumerate(rows(peek, a)):
        for k in range(16):
            key = gkey(a, r, k >> 3)
            ent[key] = [peek(int(key, 16)), 'g']
            ink = w >> (15 - k) & 1
            if ink:
                px.append((k, r, key, k & 7, 1, d))
    return {'id': 'f%d' % a, 'size': 1, 'w': 16, 'h': 16, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent, 'dx': 0, 'dy': 0,
            'dmir': 0, 'vmir': 0, 'group': 'figures'}


def sheets(z80, out_dir, prefix='pyjamarama', colours=None, say=print):
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    inks = default_inks()
    comps = [{'count': 1, 'group': 'figures', 'parts': [frame_part(get, a, inks)]} for a in FIGURES]
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb, colours=cmap,
                  identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb, colours=cmap,
                  identity=ident)
    say('Sheets    : %d graphics; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


# ---------------------------------------------------------------------------------------------
# The whole run
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : pyjamarama (XOR plotter 43758: screen writes off for figures, parity list -> sprites at 44092)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                        'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], conv[1]))
    patch = PyjamaramaPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                         'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    enhmap = load_colours(os.path.join(_HERE, '..', 'docs', 'profiles', 'pyjamarama_enhanced.json'))
    enhpal = json.load(open(os.path.join(_HERE, '..', 'docs', 'profiles', 'pyjamarama_palette.json')))
    enhanced = PyjamaramaPatch(colours=enhmap, palette=enhpal)
    enh = os.path.join(out, name + '_enhanced.nex')
    ce = zt.convert(z80, enh, None, True, quiet=True, patch=enhanced)
    bade = check(enh, z80, enhanced, (ce[1], ce[1] + len(ce[2])))
    say('Enhanced  : %s  %s  boot %s (optional menu set, off by default)' % (
        os.path.basename(enh), md5(enh), 'OK' if not bade else 'MISMATCH %s' % str(bade[:3])))
    ok = not bad and not bad2 and not bade
    states = []
    for r in list(a.rzx or []):
        c, ex, st, extra = verify(patch, r, stop=getattr(a, 'quick', None), collect=2)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, plots %d (figures %d, ULA %d), waits %d, wipes %d, clears %d, screens compared %d, %d sprite '
            'pixels, most sprites %d, %d graphics, %d attribute reads, %d other screen writes -> %s' % (
                os.path.basename(r), c['frames'], c['plots'], c['figure plots'], c['plots left on the ULA'], c['waits'], c['wipes'], c['clears'],
                c['screens compared'], c['sprite pixels'], c['most sprites'], len(extra['frames']), c['attribute reads'],
                c['other screen writes'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            rooms %s' % sorted(extra['rooms'].items()))
        say('            %d screen bytes: the original drew a tile over a live figure and lost its bits; the sprite stays whole' % (
            c['screen bytes the original overwrote on a live figure']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:240]))
        if c['commit T max']:
            say('Speed     : plot hook %d T mean, %d max; commit %d T mean, %d max; raw CPU T states; hooks switch to 28 MHz' % (
                c['plot hook T mean'], c['plot hook T max'], c['commit T mean'], c['commit T max']))
    if any(x[0] == 'wait' for x in states):
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(u.items())), 'PASS' if not uf else 'FAIL'))
        if a.rzx:
            res = negative_real(patch, list(a.rzx)[0], stop=min(getattr(a, 'quick', None) or 4000, 4000))
            miss = [k for k, n in res.items() if not n]
            ok = ok and not miss
            say('Negative  : %s  %d of %d detected %s' % (os.path.basename(list(a.rzx)[0]), len(res) - len(miss), len(res), miss or ''))
            for k, n in res.items():
                say('            %s: %d failures' % (k, n))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 3 and sys.argv[1] == 'sheet':
        sheets(sys.argv[2], sys.argv[3])
