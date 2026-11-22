"""Arkanoid (Imagine, 1987, 48K) engine 'arkanoid'. Additive module: reachable only through is_arkanoid().

Game facts and design: games/arkanoid.md. Rendering model: XOR to the screen, erase + redraw just after
the frame wait 0x848F; an alien's erase reads its own XOR pixels (0x8917, overlap = hit), so this is an
OVERLAY (LEARNINGS 2.1d): every ULA write stays, and hardware sprites sit exactly on the figures' ink
pixels in the figure's own colour. Hooks (asm/arkanoid_hooks.asm) are stateless, in alt ROM image 1.

verify(): replay the RZX on the original. At each site run original and patched code from one state to
the common resume point, compare registers and memory. Independently of the hooks, follow the game's own
XOR writes per figure (parity) and compare them with the sprite pixels at every 0x848F entry.
"""
import collections
import copy
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00          # printer buffer: zero in the snapshot, never touched in the recordings
_HERE = os.path.dirname(os.path.abspath(__file__))
# Enhanced colours: a colour map gives each figure graphics byte its 8 pixels' palette indices (palette 0, entries
# 1-15 from the map). The hooks send them from RAM pages mapped only while a pattern goes out (asm: pix4c, enh).
CPAGE, DPAGE, NDATA, GBASE = 26, 28, 10, 0xA000      # colour routine page; data pages (4 bytes per graphics byte)
COLOUR_BANKS = tuple(range(CPAGE // 2, (DPAGE + NDATA) // 2))
STACK_FLOOR = 0x5E40        # 0x5E40 up to the game's lowest SP: never touched by the game (scan)

# addr: (original bytes, opcode of the new 3 bytes, hook symbol, resume PC, kind, bytes the site makes dead)
SITES = {
    0x93E7: ('ed73c8', 0xC3, 'e_bd', 0x93EB, 'ball', 4),
    0x9420: ('060311', 0xC3, 'e_bal', 0x9425, 'balls off', 5),
    0x8FD2: ('cd2994', 0xCD, 'e_b1', 0x9429, 'ball off', 3),
    0x9C63: ('22bc94', 0xC3, 'e_bn', 0x9C66, 'bat', 3),
    0x9BC6: ('ed53bc', 0xC3, 'e_bb', 0x9BCA, 'big bat', 4),
    0x9B7D: ('ed5bbc', 0xC3, 'e_bh', 0x9B81, 'bat off', 4),
    0x8879: ('ed73c8', 0xC3, 'e_a2', 0x887D, 'alien', 4),
    0x878C: ('ed73c8', 0xC3, 'e_a3', 0x8790, 'wide alien', 4),
    0x88D5: ('ed73c8', 0xC3, 'e_ah', 0x88D9, 'alien off', 4),
    0x8C75: ('22e394', 0xC3, 'e_cd', 0x8C78, 'capsule', 3),
    0x8C0E: ('ed5beb', 0xC3, 'e_ch', 0x8C12, 'capsule off', 4),
    0x8D9B: ('626bed', 0xC3, 'e_ld', 0x8DA1, 'laser', 6),
    0x8D28: ('ed73c8', 0xC3, 'e_lh', 0x8D2C, 'laser off', 4),
    0x8A19: ('c39d8d', 0xC3, 'e_lx', 0x8DA1, 'laser off 2', 3),
    0x8025: ('f3afd3', 0xC3, 'e_go', 0x8029, 'front end', 4),
    0x96A0: ('fd213a', 0xC3, 'e_wi', 0x96A4, 'wipe', 4),
}
INTERIORS = tuple(a + k for a, s in SITES.items() for k in range(1, s[5]))
SEQUELS = {0x8026: (0x8025,), 0x8027: (0x8025,), 0x9422: (0x9420,), 0x8D9C: (0x8D9B,), 0x8D9D: (0x8D9B, 0x8A19)}
SP_SAVED = {0x8D9B, 0x8A19}         # the hook takes its stack from 0x94C8 here (SP may be in the graphics)

# the game's XOR writers: PC -> figure class (ball / alien: one per IX)
WRITERS = {}
for _pc in (0x93F0, 0x93F4, 0x9447, 0x944B):
    WRITERS[_pc] = 'ball'
for _pc in (0x9C74, 0x9C78, 0x9C7D, 0x9C81, 0x9C07, 0x9C0B, 0x9C10, 0x9C14, 0x9C19, 0x9C1D):
    WRITERS[_pc] = 'bat'
for _pc in (0x8890, 0x8894, 0x87A3, 0x87A7, 0x87AC, 0x8916, 0x891E, 0x8A4A, 0x8A52, 0x8A5B):
    WRITERS[_pc] = 'alien'
for _pc in (0x8C83, 0x8C87, 0x8C9F, 0x8CA3):
    WRITERS[_pc] = 'capsule'
for _pc in (0x8D3C, 0x8D40, 0x8D45, 0x8D49, 0x8D4E, 0x8D52, 0x8DA6, 0x8DAA, 0x8DAF, 0x8DB3, 0x8DB8, 0x8DBC):
    WRITERS[_pc] = 'laser'
# per class, as XOR parity: Disrupt's copy makes one ball's erase run three times (0x8B88), and two balls or aliens that
# overlap cancel on the ULA, so one IX's writes do not stay with one sprite; the sprites' XOR must equal the writes' XOR
FIG_SPRITES = {'bat': (0, 1, 2, 3, 4, 5), 'capsule': (6,), 'laser': (13, 14),
               'alien': (7, 8, 9, 10, 11, 12), 'ball': (15, 16, 17)}
WAIT = 0x848F               # frame wait: every path passes here while a figure is on screen
WIPE = 0x96AF               # first write of the play area clear: figures not erased are gone
NSPR = 18
SPR_BAT, SPR_BTL, SPR_CAP, SPR_ALN, SPR_LAS, SPR_BAL = 0, 3, 6, 7, 13, 15   # as asm/arkanoid_hooks.asm
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'arkanoid.json'), os.path.join(_HERE, 'arkanoid.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('arkanoid.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_arkanoid(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


class ArkanoidPatch:
    name = 'Arkanoid ball/bat/aliens/capsule/laser -> hardware sprites over the XOR figures (altrom, stateless)'

    def __init__(self, prof=None, rom_code=None, colours=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.colours = dict(colours or {})
        self.palette = list(self.colours.pop('palette', [0] * 15)) if self.colours else None
        rom = bytearray(rom_code or bytes.fromhex(h['rom']))
        setup = bytearray(bytes.fromhex(h['setup']))
        if self.colours:                                 # the three switches the Enhanced set flips
            s = self.syms
            rom[s['pix4'] + 1 - ROM_ORG] = s['pix4c'] - (s['pix4'] + 2)
            if rom[s['sprpal'] - ROM_ORG] != 0xB5:
                raise ValueError('sprpal is not OR L')
            rom[s['sprpal'] - ROM_ORG] = 0x00
            if len(self.palette) != 15:
                raise ValueError('an Arkanoid colour map palette is 15 bytes (palette 0, entries 1-15)')
            setup[s['pal0'] - 0xD000:s['pal0'] - 0xD000 + 15] = bytes(self.palette)
        self.rom_code = bytes(rom)
        self.stub_extra = bytes(setup)
        self.pages = colour_pages(bytes.fromhex(h['enh']), self.colours)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.sites = [(a, bytes.fromhex(s[0]), bytes([s[1]]) + self.syms[s[2]].to_bytes(2, 'little'))
                      for a, s in SITES.items()]
        self.extra_banks = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Arkanoid patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + 256]):
            raise ValueError('printer buffer is not empty in this snapshot (tail site)')
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        bad = colour_problems(lambda a: ram[a - 0x4000], self.colours)
        if bad:
            raise ValueError('colour map does not fit this game: %s' % bad[:3])
        self.extra_banks = {12: self.page + bytes(8192)}
        for b in COLOUR_BANKS:
            self.extra_banks[b] = self.pages[2 * b] + self.pages[2 * b + 1]


def colour_pages(enh, colours):
    """{8K page: bytes} for COLOUR_BANKS: the colour routine in CPAGE, the map's 4 bytes per graphics byte after."""
    pages = {p: bytearray(8192) for p in range(CPAGE, DPAGE + NDATA)}
    pages[CPAGE][:len(enh)] = enh
    for a, e in colours.items():
        i = (a - GBASE) * 4
        if not 0 <= i < NDATA * 8192:
            raise ValueError('colour map entry 0x%04X outside the graphics' % a)
        pages[DPAGE + i // 8192][i % 8192:i % 8192 + 4] = bytes(e)
    return {p: bytes(v) for p, v in pages.items()}


def colour_problems(get, colours):
    """Entries that would change which pixels show: a value on a clear bit, or an ink bit left 0."""
    bad = []
    for a, e in sorted(colours.items()):
        v = get(a)
        nib = [x for b in e for x in (b >> 4, b & 15)]
        for k in range(8):
            if bool(nib[k]) != bool(v & (0x80 >> k)):
                bad.append('0x%04X pixel %d' % (a, k))
                break
    return bad


def load_colours(path):
    """A colour map file {"A000": [8 palette indices], ..., "palette": [15 bytes]} -> {address: 4 bytes, 'palette'}."""
    d = json.load(open(path))
    out = {}
    for k, v in d.items():
        if k == 'palette':
            out['palette'] = list(v)
        elif not k.startswith('_'):
            out[int(k, 16)] = bytes(v[2 * i] << 4 | v[2 * i + 1] for i in range(4))
    return out


# ---------------------------------------------------------------------------------------------
# Next-side state
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patp = 0
        self.ports = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def port(self, port, val):
        if port & 0xFF == 0x5B:
            self.pat[self.patp % 16384] = val
            self.patp += 1
        elif port == 0x303B:
            self.patp = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        else:
            self.ports.append((port & 0xFF, val))

    def pixels(self, i, out=None):
        """Ink pixels of a visible 4-bit sprite in ULA coordinates, inside the screen."""
        out = set() if out is None else out
        a0, a1, a2, a3, a4 = self.attr[i]
        if not a3 & 0x80:
            return out
        if not (a3 & 0x40 and a4 & 0x80):
            out.add('not a 4-bit sprite')
            return out
        x = a0 + (a2 & 1) * 256 - 32
        y = a1 + (a4 & 1) * 256 - 32
        base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
        pat = self.pat
        for j in range(16):
            p = base + j * 8
            for k in range(8):
                b = pat[p + k]
                if b:
                    if b >> 4 and 0 <= y + j < 192:
                        out.add((x + 2 * k, y + j))
                    if b & 15 and 0 <= y + j < 192:
                        out.add((x + 2 * k + 1, y + j))
        return out


SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]


def screen_xy(a):
    return ((a & 31) * 8, ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38))


def mask_pixels(layer):
    out = set()
    for a, m in layer.items():
        x, y = screen_xy(a)
        for k in range(8):
            if m >> (7 - k) & 1:
                out.add((x + k, y))
    return out


# ---------------------------------------------------------------------------------------------
# One event: original and patched code from the same state to the common resume point
# ---------------------------------------------------------------------------------------------

class _Ov:
    """64K view of the live memory; writes stay in ov."""

    def __init__(self, get):
        self.get = get
        self.ov = {}

    def __getitem__(self, a):
        v = self.ov.get(a)
        return self.get(a) if v is None else v

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.ov[a] = v

    def __len__(self):
        return 65536


class _OvP(_Ov):
    """The patched machine: alt ROM below 0x4000, site bytes patched."""

    def __init__(self, get, alt, psite, ns=None, pages=None):
        _Ov.__init__(self, get)
        self.alt, self.psite, self.romw = alt, psite, 0
        self.ns, self.pages = ns, pages or {}

    def __getitem__(self, a):
        if a < 0x4000:
            m = self.ns.nr.get(0x50 + (a >> 13), 0xFF) if self.ns is not None else 0xFF
            if m != 0xFF:
                return self.pages[m][a & 0x1FFF] if m in self.pages else 0
            return self.alt[a]
        v = self.psite.get(a)
        if v is not None:
            return v
        return _Ov.__getitem__(self, a)

    def __setitem__(self, a, v):
        if a < 0x4000:
            self.romw += 1
        else:
            self.ov[a] = v


class _Ports:
    def __init__(self, ns=None, ports=None):
        self.ns, self.ports = ns, ports

    def read_port(self, regs, port):
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if self.ns is not None:
            self.ns.port(port, value)
        else:
            self.ports.append((port & 0xFF, value))


def _run(sim, stop, limit=300000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[24] != stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def event(patch, pc, get, R, ns, alt, psite, stop=None):
    """-> (failure list, hook T, deepest stack address written by the hook)."""
    from .simpool import machine
    from .z80n import install
    Sim = _rw()
    stop = SITES[pc][3] if stop is None else stop
    fl = []
    ports = []
    o = _Ov(get)
    so = machine(Sim, o, list(R), 'o')
    so.set_tracer(_Ports(ports=ports))
    if not _run(so, stop):
        fl.append('original did not reach the resume point')
    p = _OvP(get, alt, psite, ns, getattr(patch, 'pages', None))
    sp = machine(Sim, p, list(R), 'p')
    install(sp, ns.nextreg)
    sp.set_tracer(_Ports(ns=ns))
    n0 = len(ns.ports)
    if not _run(sp, stop):
        fl.append('hook did not reach the resume point')
        return fl, 0, 0xFFFF
    for i in CMP:
        if so.registers[i] != sp.registers[i]:
            fl.append('register %d: original %02X, patched %02X' % (i, so.registers[i], sp.registers[i]))
    if p.romw:
        fl.append('hook wrote the ROM')
    if ports != ns.ports[n0:]:
        fl.append('port writes differ %s %s' % (ports[:3], ns.ports[n0:][:3]))
    del ns.ports[n0:]
    top = (get(0x94C8) | get(0x94C9) << 8) if pc in SP_SAVED else sp.registers[12]
    low = 0xFFFF
    for a in set(o.ov) | set(p.ov):
        vo = o.ov.get(a, get(a))
        vp = p.ov.get(a, get(a))
        if a in p.ov and top - 64 <= a < top:   # dead stack below the live SP
            low = min(low, a)
            continue
        if vo != vp:
            fl.append('memory %04X: original %02X, patched %02X' % (a, vo, vp))
            break
    return fl, sp.registers[25] - so.registers[25], low


def g4(get, colours, a):
    """The 4 pattern bytes one graphics byte becomes: the colour map's (Enhanced), else value 1 on each ink bit."""
    v = get(a)
    if not v:
        return bytes(4)
    e = colours.get(a) if colours else None
    if e and any(e):
        return bytes(e)
    return bytes((0x10 if v & (0x80 >> 2 * k) else 0) | (1 if v & (0x40 >> 2 * k) else 0) for k in range(4))


def pattern_model(pc, get, R, colours=None):
    """A draw site's pattern rows as the hooks send them: {pattern: {row: 8 bytes}}, from the graphics pointer."""
    w = lambda h, l: R[h] << 8 | R[l]
    z = bytes(4)
    q = lambda a: g4(get, colours, a & 0xFFFF)
    out = {}
    if pc == 0x93E7:                                     # ball: HL, 5 rows x 2
        n = {0xF6: SPR_BAL, 0x07: SPR_BAL + 1}.get(R[9], SPR_BAL + 2)
        g = w(6, 7)
        out[n] = {r: q(g + 2 * r) + q(g + 2 * r + 1) for r in range(5)}
    elif pc in (0x9C63, 0x9BC6):                         # bat: parts of 2 bytes, 8 rows then 4, stride 4 or 6
        big = pc == 0x9BC6
        g, st = (get(0x94BE) | get(0x94BF) << 8, 6) if big else (w(4, 5), 4)
        for p in range(3 if big else 2):
            h = g + 2 * p
            out[p] = {r: q(h + st * r) + q(h + st * r + 1) for r in range(8)}
            out[SPR_BTL + p] = {r: q(h + st * (8 + r)) + q(h + st * (8 + r) + 1) for r in range(4)}
    elif pc in (0x8879, 0x878C):                         # alien: HL, B rows, stride 2 or 3, padded to 16
        n = SPR_ALN + ((R[9] - 0x29) & 0xFF) // 8
        g, b = w(6, 7), R[2]
        if pc == 0x8879:
            out[n] = {r: (q(g + 2 * r) + q(g + 2 * r + 1)) if r < b else bytes(8) for r in range(16)}
        else:
            out[n] = {r: (q(g + 3 * r) + q(g + 3 * r + 1)) if r < b else bytes(8) for r in range(16)}
            out[n + 1] = {r: (q(g + 3 * r + 2) + z) if r < b else bytes(8) for r in range(16)}
    elif pc == 0x8C75:                                   # capsule: b0 b1 / b3 b2, 8 rows
        g = w(6, 7)
        out[SPR_CAP] = {}
        for i in range(4):
            h = g + 4 * i
            out[SPR_CAP][2 * i] = q(h) + q(h + 1)
            out[SPR_CAP][2 * i + 1] = q(h + 3) + q(h + 2)
    elif pc == 0x8D9B:                                   # laser: b0 b1 / b5 b4, then b2 / b3 alone
        g = get(0x94DF) | get(0x94E0) << 8
        out[SPR_LAS], out[SPR_LAS + 1] = {}, {}
        for i in range(4):
            h = g + 6 * i
            out[SPR_LAS][2 * i] = q(h) + q(h + 1)
            out[SPR_LAS][2 * i + 1] = q(h + 5) + q(h + 4)
            out[SPR_LAS + 1][2 * i] = q(h + 2) + z
            out[SPR_LAS + 1][2 * i + 1] = q(h + 3) + z
    return out


def pattern_check(patch, pc, get, R, ns):
    """-> ([(pattern, row, sent, model)], rows checked): every row the draw sent against pattern_model."""
    bad, n = [], 0
    for p, rows in pattern_model(pc, get, R, getattr(patch, 'colours', None)).items():
        for r, want in rows.items():
            got = bytes(ns.pat[p * 256 + 8 * r:p * 256 + 8 * r + 8])
            n += 1
            if got != want:
                bad.append((p, r, got.hex(), want.hex()))
    return bad, n


def compare_figures(lay, ns, c, fail, get, colours=True):
    """Each figure's XOR parity layer against its sprites' ink pixels; colour against the ULA, informational."""
    for key, spr in FIG_SPRITES.items():
        truth = mask_pixels(lay[key]) if key in lay else set()
        got = set()
        for i in spr:
            got ^= ns.pixels(i)
        if truth != got:
            fail('figure != sprite: %s' % (key,), (sorted(truth - got)[:4], sorted(got - truth, key=str)[:4]))
        else:
            c['sprite pixels compared'] += len(got)
            c['figures ' + key] += 1 if got and colours else 0
            for i in spr if colours else ():
                a = ns.attr[i]
                px = ns.pixels(i) if a[3] & 0x80 else None
                if px:
                    (x, y) = min(px)
                    same = (a[2] >> 4) & 7 == get(0x5800 + (y >> 3) * 32 + (x >> 3)) & 7
                    c['colour %s %s ULA ink' % (key, 'same as' if same else 'differs from')] += 1


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shot=None):
    """Replay the RZX on the original; events at every site, figure parity at every frame wait.
    -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    site_bytes = set(psite)
    SITE = {a for a, old, new in patch.sites}
    st = {'frame': 0, 'on': False, 'dirty': False, 'iff': 0, 'minsp': 0xFFFF, 'hookt': 0, 'low': 0xFFFF}
    ns = NextState()
    lay = {}
    cnt = collections.Counter()
    WATCH = set(SITES) | set(INTERIORS) | set(WRITERS) | {WAIT, WIPE, 0x8025, 0x83DF, 0x982A}
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['on'] and type(a) is int and a in site_bytes:
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
                        w = WRITERS.get(pc)
                        if w is not None:
                            a = (R[6] << 8 | R[7]) if G(mem, pc) == 0x77 else (R[4] << 8 | R[5])
                            if 0x4000 <= a < 0x5800:
                                d = lay.setdefault(w, {})
                                m = d.get(a, 0) ^ R[0] ^ G(mem, a)
                                if m:
                                    d[a] = m
                                else:
                                    d.pop(a, None)
                                st['dirty'] = True
                            c['writes ' + w] += 1
                        elif pc in (0x83DF, 0x982A):      # main loop heads: everything erased but the laser
                            if st['dirty']:
                                st['dirty'] = False
                                c['loop heads compared'] += 1
                                compare_figures(lay, ns, c, fail, get, False)
                        elif pc == WAIT:
                            if st['dirty']:
                                st['dirty'] = False
                                c['frames compared'] += 1
                                diff0 = sum(v for k, v in c.items() if k.startswith('colour') and 'differs' in k)
                                compare_figures(lay, ns, c, fail, get)
                                if shot:
                                    shot(st['frame'], get, ns, sum(v for k, v in c.items() if k.startswith('colour') and 'differs' in k) - diff0)
                        elif pc == WIPE and lay:
                            if any(lay.values()):
                                c['wipes over figures'] += 1
                            lay.clear()
                            st['dirty'] = True
                        if pc in SITES:
                            if pc == 0x8025 and lay:
                                if any(lay.values()):
                                    c['front end over figures'] += 1
                                lay.clear()
                                st['dirty'] = True
                            cnt[pc] += 1
                            kind = SITES[pc][4]
                            c[kind] += 1
                            if R[26]:
                                st['iff'] += 1
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((pc, list(R), bytes(G(mem, a) for a in range(65536)),
                                               [list(x) for x in ns.attr], bytes(ns.pat)))
                            if pc in SITE:
                                fl, t, low = event(patch, pc, get, R, ns, alt, psite)
                                st['hookt'] += t
                                st['low'] = min(st['low'], low)
                                for k in fl:
                                    fail('%s: %s' % (kind, k))
                                if pc in _END:
                                    bad = pattern_check(patch, pc, get, R, ns)
                                    c['pattern rows checked'] += bad[1]
                                    if bad[0]:
                                        fail('%s: pattern differs from the colour model' % kind, bad[0][:2])
                                st['dirty'] = True
                        elif pc in INTER:
                            cnt[pc] += 1
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    INTER = set(INTERIORS)
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
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    for a in INTER:
        if a in SEQUELS:        # the displaced instructions after a short first one: the replay's original runs them
            if cnt[a] != sum(cnt[b] for b in SEQUELS[a]):
                c['jump into a patched instruction (%04X)!' % a] += 1
        elif cnt[a]:
            c['jump into a patched instruction (%04X)!' % a] += 1
    c['frames'] = st['frame']
    c['hook T (28 MHz T, patched minus original)'] = st['hookt']
    c['events with interrupts on'] = st['iff']
    if st['low'] != 0xFFFF:
        c['lowest hook stack byte'] = st['low']
        if st['low'] < STACK_FLOOR:
            c['hook stack below the proven free range!'] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests: positions, widths and graphics the recordings may not reach, against the original's XOR
# ---------------------------------------------------------------------------------------------

# site -> where the original's XOR ends (registers in the state set the plot up)
_END = {0x93E7: 0x940C, 0x9C63: 0x9C95, 0x9BC6: 0x9C95, 0x8879: 0x88B9, 0x878C: 0x88B9, 0x8C75: 0x8CBA, 0x8D9B: 0x8DC0}
_FIG = {0x93E7: 'ball', 0x9C63: 'bat', 0x9BC6: 'bat', 0x8879: 'alien', 0x878C: 'alien', 0x8C75: 'capsule', 0x8D9B: 'laser'}


def _one_plot(patch, pc, R, mem, attrs, pat, alt, psite):
    """-> (failures, truth pixels, sprite pixels): the original's XOR run to its end against the hook's sprites."""
    from .simpool import machine
    get = mem.__getitem__
    Sim = _rw()
    o = _Ov(get)
    so = machine(Sim, o, list(R), 'o')
    so.set_tracer(_Ports(ports=[]))
    if not _run(so, _END[pc]):
        return ['original did not end'], set(), set()
    truth = {a: v ^ get(a) for a, v in o.ov.items() if 0x4000 <= a < 0x5800 and v != get(a)}
    ns = NextState()
    ns.attr = [list(a) for a in attrs]
    ns.pat[:] = pat
    fl, _, _ = event(patch, pc, get, R, ns, alt, psite)
    got = set()
    for i in FIG_SPRITES[_FIG[pc]]:
        ns.pixels(i, got)
    return fl, mask_pixels(truth), got


def unit_tests(patch, states, neg=None):
    """states from verify(collect=n). Every plot kind x graphics x positions, original XOR against the
    sprites; hide sites; negative controls run through the same cases when given."""
    c = collections.Counter()
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    def case(name, pc, R, mem, attrs, pat):
        fl, t, g = _one_plot(patch, pc, R, mem, attrs, pat, alt, psite)
        ok = not fl and t == g
        c['%s %s' % (name, 'ok' if ok else 'FAIL!')] += 1
        if ok and not t:
            c['%s: graphics all zero at the test pointer' % name] += 1
        if not ok and c['  example ' + name] < 2:
            c['  example ' + name] += 1
            c['  %s %s t-g %s g-t %s' % (name, fl[:2], sorted(t - g)[:3], sorted(g - t, key=str)[:3])] += 1
        return ok

    def scr(col, y):
        return 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col

    seen = set()
    for pc, R, m, attrs, pat in states:
        mem = bytearray(m)
        if pc not in _END or pc in seen:
            continue
        seen.add(pc)
        if pc == 0x93E7:
            for sh in range(8):
                for col, y in ((1, 8), (10, 7), (15, 60), (20, 63), (21, 127), (5, 170), (12, 186)):
                    r = list(R)
                    a, g = scr(col, y), 0xEB54 + 10 * sh
                    r[4], r[5], r[6], r[7] = a >> 8, a & 255, g >> 8, g & 255
                    case('ball', pc, r, mem, attrs, pat)
        elif pc in (0x9C63, 0x9BC6):
            big = pc == 0x9BC6
            for k in range(16):
                for col in (1, 2, 9, 15, 17):
                    r = list(R)
                    a = 0x50C0 + col
                    g = ((R[6] << 8 | R[7]) if big else (R[4] << 8 | R[5])) + (0x48 if big else 0x30) * (k - 8)
                    m2 = bytearray(mem)
                    if big:
                        m2[0x94BE], m2[0x94BF] = g & 255, g >> 8
                        m2[R[12]], m2[R[12] + 1] = g & 255, g >> 8
                        r[4], r[5], r[6], r[7] = a >> 8, a & 255, g >> 8, g & 255
                    else:
                        r[6], r[7], r[4], r[5] = a >> 8, a & 255, g >> 8, g & 255
                    case('big bat' if big else 'bat', pc, r, m2, attrs, pat)
        elif pc in (0x8879, 0x878C):
            wide = pc == 0x878C
            for rows in (11, 12, 15, 16):
                for k in range(4):
                    for col, y in ((2, 16), (7, 21), (15, 32), (20, 63), (10, 120), (3, 161)):
                        r = list(R)
                        a = scr(col, y)
                        g = (R[6] << 8 | R[7]) + 48 * k
                        r[4], r[5], r[6], r[7], r[2] = a >> 8, a & 255, g >> 8, g & 255, rows
                        case('wide alien' if wide else 'alien', pc, r, mem, attrs, pat)
        elif pc == 0x8C75:
            for k in range(14):
                for col, y in ((2, 8), (9, 13), (15, 40), (20, 63), (5, 120), (11, 175)):
                    r = list(R)
                    a = scr(col, y)
                    g = (R[6] << 8 | R[7]) + 16 * (k - 7)
                    r[4], r[5], r[6], r[7] = a >> 8, a & 255, g >> 8, g & 255
                    case('capsule', pc, r, mem, attrs, pat)
        elif pc == 0x8D9B:
            for k in range(4):
                for col, y in ((1, 16), (8, 24), (15, 64), (19, 120), (12, 168)):
                    r = list(R)
                    a = scr(col, y)
                    g = 0xB000 + 24 * k
                    r[4], r[5] = a >> 8, a & 255
                    m2 = bytearray(mem)
                    m2[0x94DF], m2[0x94E0] = g & 255, g >> 8
                    case('laser', pc, r, m2, attrs, pat)
    # hide sites: every sprite shown, then each off hook leaves its figure's sprites hidden
    OFF = {0x88D5: (7, 8), 0x8C0E: (6,), 0x9B7D: (0, 1, 2, 3, 4, 5), 0x8D28: (13, 14), 0x8A19: (13, 14),
           0x9420: (15, 16, 17), 0x96A0: tuple(range(NSPR)), 0x8025: tuple(range(NSPR))}
    for pc, R, m, attrs, pat in states:
        if pc in OFF and 'off %04X' % pc not in seen:
            seen.add('off %04X' % pc)
            mem = bytearray(m)
            ns = NextState()
            ns.attr = [[50, 50, 0, 0xC0 | i, 0x80] for i in range(128)]
            r = list(R)
            r[8], r[9] = 0x95, 0x29
            fl, _, _ = event(patch, pc, mem.__getitem__, r, ns, alt, psite)
            bad = [i for i in OFF[pc] if ns.attr[i][3] & 0x80]
            others = [i for i in range(NSPR) if i not in OFF[pc] and not ns.attr[i][3] & 0x80]
            c['off %04X %s' % (pc, 'ok' if not fl and not bad and not others else 'FAIL!')] += 1
    return c


# ---------------------------------------------------------------------------------------------
# Negative controls: each broken build must be DETECTED on the real recording
# ---------------------------------------------------------------------------------------------

def _broken(patch, sym, new):
    q = copy.copy(patch)
    a = patch.syms[sym] - 0x2000
    page = bytearray(patch.page)
    page[a:a + len(new)] = new
    q.page = bytes(page)
    return q


def negative_patches(patch):
    no_site = copy.copy(patch)
    no_site.sites = [s for s in patch.sites if s[0] != 0x8879]
    return [('sprites one row low', _broken(patch, 'neg_y', b'\xC6\x21')),
            ('ink lost in the pattern upload', _broken(patch, 'neg_pix', b'\x3E\x00')),
            ('ball draw hook never sets the sprite', _broken(patch, 'neg_ball', b'\0\0\0')),
            ('ball erase leaves the first ball shown', _broken(patch, 'neg_balh', b'\0\0\0')),
            ('play area wipe leaves the sprites', _broken(patch, 'neg_wipe', b'\0\0\0')),
            ('hook loses a register (DE)', _broken(patch, 'neg_de', b'\x11\x12\x00')),
            ('displaced store lost (capsule pointer)', _broken(patch, 'neg_capst', b'\0\0\0')),
            ('alien draw site not applied', no_site)]


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : arkanoid (XOR figures, sprites as an overlay, every ULA write kept)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = printer buffer)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = ArkanoidPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    hooks = collections.Counter()
    quick = getattr(a, 'quick', None)
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=quick, collect=3)
        states += st
        hooks.update({k: v for k, v in c.items() if k in {s[4] for s in SITES.values()}})
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, compared %d, %d sprite pixels; ball %d off %d/%d, bat %d big %d off %d, '
            'alien %d wide %d off %d, capsule %d off %d, laser %d off %d/%d, front end %d, wipe %d; hook T/frame %d -> %s' % (
                os.path.basename(r), c['frames'], c['frames compared'], c['sprite pixels compared'], c['ball'], c['balls off'],
                c['ball off'], c['bat'], c['big bat'], c['bat off'], c['alien'], c['wide alien'], c['alien off'],
                c['capsule'], c['capsule off'], c['laser'], c['laser off'], c['laser off 2'], c['front end'], c['wipe'],
                c['hook T (28 MHz T, patched minus original)'] // max(1, c['frames']),
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            speed: hook T/6 per frame %d (3.5 MHz estimate; no real-machine timing)' % (
            c['hook T (28 MHz T, patched minus original)'] // max(1, c['frames']) // 6))
        say('            colours: %s; interrupts on at %d events; lowest hook stack byte 0x%04X; wipes over figures %d, front end over figures %d' % (
            {k[7:]: v for k, v in c.items() if k.startswith('colour ')}, c['events with interrupts on'],
            c['lowest hook stack byte'], c['wipes over figures'], c['front end over figures']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
    never = [s[4] for s in SITES.values() if not hooks[s[4]]]
    if a.rzx:
        say('Hooks     : %s; never ran: %s' % (dict(hooks), never or 'none'))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % ({k: v for k, v in u.items() if k.endswith(' ok')}, 'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in u.items():
            if k.startswith('  '):
                say('            %s' % k[:220])
        if a.rzx:
            r = list(a.rzx)[0]
            neg = []
            for nm, q in negative_patches(patch):
                det = []

                def early(f, cq):
                    det.extend(k for k, v in cq.items() if k.endswith('!'))
                    if det:
                        raise _NegStop()
                try:
                    cq, _ = verify(q, r, stop=min(quick or NEG_FRAMES, NEG_FRAMES), progress=early)
                    det = det or [k for k, v in cq.items() if k.endswith('!')]
                except _NegStop:
                    pass
                neg.append((nm, bool(det)))
                ok = ok and bool(det)
                say('Negative  : %s -> %s' % (nm, 'DETECTED %s' % str(det[:2])[:140] if det else 'NOT DETECTED'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


NEG_FRAMES = 12000


class _NegStop(Exception):
    pass
