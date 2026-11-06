"""Quazatron (Hewson, 1986, 48K) engine 'quazatron': colour v1.0, built around a scrolling Layer 2 canvas.
Opt-in (unproven): NEXCLASH_REWORK=quazatron. Facts and design: games/quazatron.md; hooks: asm/quazatron_hooks.asm.

Session 1 (2026-11-06) builds the scenery path: the game's background has a colour twin on a 320 x 256 Layer 2
canvas that wraps; scroll moves become an origin change; colour = the role of the drawing list that last cleared a
pixel (tag strip mirror of the game's column strip); inks follow the game's attributes at the commit (C05A).
Session 2 (2026-11-06): the pace limiter (a debt of hook time repaid from the game's delay at DD80, t_dly; a pace
window on each scroll move with fast scroll off), an image-keyed sprite pattern cache, a faster ink pass and paste;
the verifier checks sprites = model at every E656, the lock at every frame, the every-site clock matrix. The menu's
'Smooth scrolling' toggle is the fast+smooth build; 'Colour' is the main line.
Session 3 (2026-11-06): pace windows on the game's own E656 and scroll-step C05A (28 MHz, the original's time from
JNext-measured ratios, the debt repaid, the rest waited); the scroll moves run in the hook page; a monochrome gate
(V_MONO): the .nxc base is the monochrome build, Colour its Enhanced colours set; ROLETAB in sprite store page S0.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24               # bank 12: the alt ROM image's page (z80tonex.altrom_fill)
HPAGE = 26                  # bank 13: hook code and state, mapped at slot 2 inside hooks
L2BANK = 18                 # Layer 2 canvas: banks 18-22 (cleared by setup, not in the .nex)
TAIL_ADDR = None            # z80tonex picks (checked below 0xC000)
SETUP = 0xD000
CMP = list(range(0, 24)) + [26, 27]     # all but T, MEMPTR (R compared: hooklib.CMP_R style)
REWORK = 'quazatron'

# sites: address -> (original bytes, instruction to write: opcode, hook symbol)
SITES = {
    0xBE2E: ('cd7db0', 0xCD, 't_list'),
    0xBE82: ('cd44c0', 0xCD, 't_clr'),
    0xBFEC: ('cda5c1', 0xCD, 't_paste'),
    0xBFFB: ('cda5c1', 0xCD, 't_paste'),
    0xE10E: ('21ff94', 0xC3, 't_sd'),
    0xE11D: ('210084', 0xC3, 't_su'),
    0xE12C: ('210283', 0xC3, 't_sl'),
    0xE146: ('21fd95', 0xC3, 't_sr'),
    0xC05A: ('110083', 0xC3, 't_c05a'),
    0xB2C9: ('210040', 0xC3, 't_cls'),
    0xB1FB: ('ed5363b2', 0xC3, 't_prn'),
    0xE0DF: ('cd56e6', 0xCD, 't_spr'),
    0xE1A9: ('cd38be', 0xCD, 't_bs'),
    0xE6E6: ('c32dbd', 0xC3, 't_isr'),
    0xDD8A: ('672e00', 0xC3, 't_dly'),       # the pace limiter: the game's delay loop starts shorter by the debt
}
INTERIORS = (0xBE2F, 0xBE30, 0xBE83, 0xBE84, 0xBFED, 0xBFEE, 0xBFFC, 0xBFFD, 0xE10F, 0xE110, 0xE11E, 0xE11F, 0xE12D,
             0xE12E, 0xE147, 0xE148, 0xC05B, 0xC05C, 0xB2CA, 0xB2CB, 0xB1FC, 0xB1FD, 0xB1FE, 0xE0E0, 0xE0E1, 0xE1AA, 0xE1AB, 0xE6E7, 0xE6E8,
             0xDD8B, 0xDD8C)

# hook page layout (asm EQUs)
ROLETAB = 0xD800            # session 3: in sprite store page S0 (0xD800 at slot 6), sprite_store() puts it
ROLETAB_OFF = 0x1800
PALINIT_OFF = 0x80          # in the setup block (0xD080)
DECKPAL_OFF = 0x1100        # in sprite store page S0 (0xD100 at slot 6)
FLAGS_OFF = 0x1200          # in S0 (0xD200): 40 x 32 canvas cells, 0xFF = rewrite at the first commit
V_OX, V_OY, V_L2ON, V_DECKP = 0x4BC4, 0x4BC6, 0x4BC7, 0x4BC8
V_FAST, V_SMOOTH, V_DX, V_DY = 0x4BE8, 0x4BE9, 0x4BEA, 0x4BEC
V_MONO = 0x4CE0              # session 3: 1 = monochrome (the .nxc base), 0 = colour
TAGS = 0x4D00

# --- the painting (our own; docs: games/quazatron.md "Colour") -------------------------------------------------
# Layer 2 palette: 0-15 the ZX inks (the ink a cell's attribute gives), 16-19 the deck's floor / wall / ramp / fringe
# (per paper colour, DECK), 20 arrow panels, 21 objects, 22 pads.
R_FLOOR, R_WALL, R_RAMP, R_FRINGE, R_FACE, R_ARROW, R_OBJECT, R_PAD, R_SCREEN, R_CONSOLE = range(16, 26)
# v3 (approved 2026-11-06): every scenery list's role (pilot work/s1/scenery_lists.png, mockup3.py ROLE3)
_F, _W, _R, _FR, _A, _O, _PD, _C = R_FLOOR, R_WALL, R_RAMP, R_FRINGE, R_ARROW, R_OBJECT, R_PAD, R_CONSOLE
ROLE = {0x9670: _FR, 0x9692: _FR, 0x96B4: _W, 0x96CD: _W, 0x96E0: _W, 0x96FE: _W, 0x9719: _W, 0x9737: _W,
        0x974F: _F, 0x976D: _F, 0x978B: _W, 0x97A2: _W, 0x97BE: _W, 0x97DB: _W, 0x97F7: _F, 0x9811: _W,
        0x9829: _F, 0x9848: _F, 0x9867: _R, 0x987F: _W, 0x988B: _W, 0x98A8: _W, 0x98C0: _W, 0x98DD: _W,
        0x98F6: _F, 0x9914: _F, 0x9930: _W, 0x9948: _W, 0x995C: _W, 0x9978: _W, 0x9990: _W, 0x99AB: _W,
        0x99C3: _F, 0x99E1: _F, 0x99FF: _R, 0x9A27: _R, 0x9A67: _A, 0x9AA6: _A, 0x9AD4: _O, 0x9AF2: _O,
        0x9B10: _C, 0x9B4C: _C, 0x9B88: _F, 0x9B9E: _F, 0x9BB4: _PD, 0x9BC2: _PD}
# per paper colour: floor, wall (face paper), ramp, fringe, face (the ink inside a wall part)
DECK = {4: ((110, 230, 110), (70, 150, 105), (150, 200, 90), (30, 80, 60), (35, 95, 70)),
        5: ((110, 225, 245), (60, 130, 175), (120, 190, 230), (30, 60, 110), (35, 80, 120)),
        7: ((225, 225, 225), (140, 140, 165), (190, 190, 210), (70, 70, 90), (85, 85, 105)),
        6: ((245, 230, 110), (180, 135, 60), (230, 190, 90), (100, 70, 30), (115, 85, 40)),
        3: ((240, 140, 240), (160, 80, 165), (220, 120, 200), (80, 40, 90), (100, 50, 105)),
        2: ((245, 140, 120), (165, 80, 75), (230, 120, 100), (90, 40, 40), (105, 50, 50)),
        1: ((140, 160, 255), (80, 95, 185), (120, 140, 230), (30, 30, 100), (50, 60, 125)),
        0: ((200, 200, 200), (120, 120, 120), (160, 160, 160), (50, 50, 50), (75, 75, 75))}
ACCENT = ((225, 180, 80), (255, 110, 60), (235, 80, 235), (70, 215, 225), (60, 75, 95))   # arrow, object, pad, screen, bezel
ZXRGB = [(0, 0, 0), (0, 0, 5), (5, 0, 0), (5, 0, 5), (0, 5, 0), (0, 5, 5), (5, 5, 0), (5, 5, 5),
         (0, 0, 0), (0, 0, 7), (7, 0, 0), (7, 0, 7), (0, 7, 0), (0, 7, 7), (7, 7, 0), (7, 7, 7)]   # RGB333


def rgb333(c):
    return tuple(min(7, (v * 7 + 127) // 255) for v in c)


def pal9(r, g, b):
    """Two NR 0x44 bytes. Never the global transparency 0xE3 (opaque play area)."""
    b1 = r << 5 | g << 2 | b >> 1
    if b1 == 0xE3:
        b1 = 0xE2
    return bytes([b1, b & 1])


def palinit():
    out = b''.join(pal9(*c) for c in ZXRGB)
    out += b''.join(pal9(*rgb333(c)) for c in DECK[4])
    out += b''.join(pal9(*rgb333(c)) for c in ACCENT)
    out += bytes(64 - len(out))
    assert len(out) == 64
    return out


def deckpal():
    out = b''.join(b''.join(pal9(*rgb333(c)) for c in DECK[p]) for p in range(8))
    assert len(out) == 80
    return out


def roletab():
    t = bytearray([R_FLOOR] * 192)
    for a, r in ROLE.items():
        t[(a - 0x9600) >> 3] = r
    return bytes(t)


# --- profile, detection ---------------------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'quazatron.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_quazatron(snap):
    """Quazatron's signature (B07D, the list drawer), 48K, and the opt-in: NEXCLASH_REWORK=quazatron."""
    if os.environ.get('NEXCLASH_REWORK') != REWORK:
        return False
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def _whole_rom_page(code=b''):
    """Image of 0x2000-0x3FFF for alt ROM image 1: Sinclair's ROM with `code` at ROM_ORG (its 0xFF area)."""
    from .build import rom48
    rom = rom48()
    if any(b != 0xFF for b in rom[ROM_ORG:ROM_ORG + len(code) + 20]):
        raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
    page = bytearray(rom[0x2000:0x4000])
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    return bytes(page)


def hook_page(prof, fast=False, smooth=False, mono=False):
    """The 8K hook page (slot 2 inside hooks): code, tables, state, FLAGS 0xFF (every cell rewritten at the first
    commit), TAGS 0. fast / smooth: the fast-scroll option (scroll steps at 28 MHz) and the smooth display."""
    code = bytes.fromhex(prof['hooks']['page'])
    pg = bytearray(8192)
    pg[0:len(code)] = code
    put = lambda a, b: pg.__setitem__(slice(a - 0x4000, a - 0x4000 + len(b)), b)
    put(V_FAST, bytes([3 if fast else 0, 1 if smooth else 0]))
    put(V_MONO, bytes([1 if mono else 0]))
    put(V_DX, (32).to_bytes(2, 'little'))
    put(V_DY, bytes([32]))
    put(0x4BF3, (32).to_bytes(2, 'little') + bytes([32]))     # TX, TY
    put(V_OX, (32).to_bytes(2, 'little'))
    put(V_OY, bytes([32]))
    put(V_L2ON, bytes([0]))
    put(V_DECKP, bytes([0xFF]))
    return bytes(pg)


class PlainPatch:
    """The plain .nex: no hooks; alt ROM image 1 = Sinclair's 48K ROM (the game reads ROM 0x0000-0x03FF as its random
    table, B5A3)."""
    name = 'Quazatron plain conversion, Sinclair\'s ROM as the alt ROM'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def __init__(self):
        self.regblock = ROM_ORG
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = _whole_rom_page()
        self.extra_banks = {12: self.page + bytes(8192)}

    def apply(self, snap):
        pass


class QuazatronPatch:
    name = 'Quazatron colour: scenery canvas on Layer 2 (session 1; droid sprites, smooth mode and pace to come)'

    def __init__(self, prof=None, fast=False, smooth=False, mono=False):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        setup = bytes.fromhex(h['setup'])
        if len(setup) > PALINIT_OFF:
            raise ValueError('setup code runs into its palette')
        self.stub_extra = setup + bytes(PALINIT_OFF - len(setup)) + palinit()
        self.fast, self.smooth = fast, smooth
        self.setup_call = SETUP
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = _whole_rom_page(self.rom_code)
        self.sites = [(a, bytes.fromhex(old), bytes([op]) + self.syms[sym].to_bytes(2, 'little'))
                      for a, (old, op, sym) in SITES.items()]
        self.extra_banks = {12: self.page + bytes(8192), 13: hook_page(self.prof, fast, smooth, mono) + bytes(8192)}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Quazatron patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


def build(z80, out, name='quazatron', say=print):
    """Plain and colour .nex with boot checks -> (ok, {kind: path})."""
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    ok, paths = True, {}
    banks, info = sprite_store(play_memory(z80))
    s0 = bytearray(banks[STORE_BANK][:8192])
    s0[DECKPAL_OFF:DECKPAL_OFF + 80] = deckpal()
    s0[FLAGS_OFF:FLAGS_OFF + 1280] = bytes([0xFF]) * 1280
    banks[STORE_BANK] = bytes(s0) + banks[STORE_BANK][8192:]
    say('Sprites   : %s' % info)
    builds = [('Plain', PlainPatch(), name + '.nex')]
    for kind, fast, smooth, mono, fn in (('Colour', False, False, False, name + '_colour.nex'),
                                         ('Fast+smooth', True, True, False, name + '_colour_fastscroll.nex'),
                                         ('Mono', False, False, True, name + '_mono.nex'),
                                         ('Mono+toggle', True, True, True, name + '_mono_fastscroll.nex')):
        patch = QuazatronPatch(fast=fast, smooth=smooth, mono=mono)
        patch.extra_banks.update(banks)
        builds.append((kind, patch, fn))
    for kind, patch, fn in builds:
        p = os.path.join(out, fn)
        conv = zt.convert(z80, p, None, True, quiet=True, patch=patch)
        if conv[1] >= 0xC000 or conv[1] + len(conv[2]) > 0xC000:
            raise ValueError('start-up tail at 0x%04X ends above 0xC000' % conv[1])
        bad = check(p, z80, patch, (conv[1], conv[1] + len(conv[2])))
        ok = ok and not bad
        paths[kind] = p
        say('%-10s: %s  %s  boot %s  (tail 0x%04X, %d bytes)' % (kind, fn, md5(p), 'OK' if not bad else
                                                                  'MISMATCH %s' % str(bad[:3])[:300], conv[1], len(conv[2])))
    return ok, paths


# --- verifier (session 1 start; session 2 completes it: clock matrix, sprites, per-frame lock, negatives) -----------
ULAPAGE, L2PAGE, PC, SP, TS = 10, 36, 24, 12, 25
SPOS_OFF = 0x1000          # SPOS (0xD000 at slot 6) in sprite store page S0
GPAT_ADDR = 0x4CB0         # each group's first pattern (asm GPAT)
SPEED_LATCHES = (0x4BC0, 0x4BE6, 0x4BE7, 0x4BF2)
CMPV = list(range(0, 13)) + [14, 15] + list(range(16, 25))       # all but T, IFF/IM, MEMPTR; R included
NESTED = ('t_list', 't_clr', 't_paste')                         # inside BE38: run as part of t_bs when it is the caller


class NextState:
    """The Next side the hooks see: NR 0x52 / 0x56 / 7 and the rest, the pages (hook page, sprite store, canvas),
    the Layer 2 enable, sprite attributes and patterns. Carried from event to event."""
    def __init__(self, patch):
        self.nr = {7: 0, 0x52: ULAPAGE, 0x56: 0}
        self.pages = {}
        for bank, data in patch.extra_banks.items():
            self.pages[2 * bank] = bytearray(data[:8192])
            self.pages[2 * bank + 1] = bytearray(data[8192:16384])
        for p in range(L2PAGE, L2PAGE + 10):
            self.pages[p] = bytearray(8192)
        self.sel = 0
        self.l2 = 0
        self.attr = [[0] * 5 for _ in range(128)]
        self.pat = bytearray(16384)
        self.sidx = self.aidx = self.ptr = 0

    def nextreg(self, reg, val):
        self.nr[reg] = val

    def read_port(self, regs, port):
        if port & 0xFFFF == 0x253B:
            v = self.nr.get(self.sel, 0)
            return (v & 3) * 17 if self.sel == 7 else v
        return 0xFF

    def write_port(self, regs, port, value, *x):
        p = port & 0xFFFF
        if p == 0x243B:
            self.sel = value
        elif p == 0x123B:
            self.l2 = value
        elif p == 0x303B:
            self.sidx, self.aidx, self.ptr = value & 0x7F, 0, (value & 0x3F) * 256
        elif p & 0xFF == 0x57:
            self.attr[self.sidx & 0x7F][self.aidx] = value
            self.aidx += 1
            if (self.aidx == 4 and not value & 0x40) or self.aidx == 5:
                self.sidx, self.aidx = (self.sidx + 1) & 0x7F, 0
        elif p & 0xFF == 0x5B:
            self.pat[self.ptr & 0x3FFF] = value
            self.ptr += 1

    def var(self, a, n=1):
        pg = self.pages[HPAGE]
        return pg[a - 0x4000] if n == 1 else pg[a - 0x4000] | pg[a - 0x3FFF] << 8

    def canvas(self, x, y):
        return self.pages[L2PAGE + (x >> 5)][(x & 31) * 256 + (y & 255)]


def _mem(get, alt, ns, psite):
    class M:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if a < 0x6000 and ns.nr[0x52] != ULAPAGE:
                return ns.pages[ns.nr[0x52]][a - 0x4000]
            if 0xC000 <= a < 0xE000 and ns.nr[0x56] != 0:
                if ns.nr[0x56] == ULAPAGE:
                    a -= 0x8000                 # the screen page at slot 6: the game's 0x4000-0x5FFF
                else:
                    return ns.pages[ns.nr[0x56]][a - 0xC000]
            v = s.ov.get(a)
            if v is None:
                v = psite.get(a)
            return get(a) if v is None else v

        def __setitem__(s, a, v):
            if a < 0x4000:
                return
            if a < 0x6000 and ns.nr[0x52] != ULAPAGE:
                ns.pages[ns.nr[0x52]][a - 0x4000] = v
            elif 0xC000 <= a < 0xE000 and ns.nr[0x56] not in (0, ULAPAGE):
                ns.pages[ns.nr[0x56]][a - 0xC000] = v
            else:
                s.ov[a - 0x8000 if 0xC000 <= a < 0xE000 and ns.nr[0x56] == ULAPAGE else a] = v

        def __len__(s):
            return 65536
    return M()


def _run(mem, regs, ns, stop_pc, stop_sp, slot, limit=3000000):
    from skoolkit.simulator import Simulator
    from .simpool import machine
    from . import z80n
    sim = machine(Simulator, mem, regs, slot)
    sim.set_tracer(ns)
    z80n.install(sim, ns.nextreg)
    R, ops, n = sim.registers, sim.opcodes, 0
    while not (R[PC] == stop_pc and R[SP] == stop_sp):
        ops[mem[R[PC]]]()
        n += 1
        if n > limit:
            return list(R), False
    return list(R), True


class _OrigNS(NextState):
    """The original's side: no pages mapped, no Next ports."""
    def __init__(self):
        self.nr = {7: 0, 0x52: ULAPAGE, 0x56: 0}
        self.pages, self.sel, self.l2 = {}, 0, 0
        self.attr = [[0] * 5 for _ in range(128)]
        self.pat = bytearray(16384)
        self.sidx = self.aidx = self.ptr = 0


def verify(patch, rzx_path, stop=None, collect=0, progress=None, model_dir=None, clocks=0):
    """Differential test, session 1 start. Replays the original; at every site runs the original and the patched code
    from the same state to the return point and compares the registers (R included) and the game memory written
    (writes below the entry SP are dead stack); the Next side is carried. At every commit (C05A): the canvas under the
    view = the colour model (pilot work/s1/mockup3.py Model3, the v3 rules) pixel for pixel: paper = the list role,
    ink = the cell's attribute ink (a wall face's ink: the face tone on the deck), a console's OR ink = its screen.
    model_dir: the folder of the pilot's model (default $QUAZATRON_MODEL)."""
    import sys
    from . import rzx
    from .nextboot import alt_image
    from .build import rom48
    model_dir = model_dir or os.environ.get('QUAZATRON_MODEL')
    sys.path.insert(0, model_dir)
    sys.path.insert(0, os.path.dirname(model_dir.rstrip('/')))
    import mockup3 as M3
    import cmodel2 as cm
    cm.REPO = os.path.dirname(_HERE)
    model = M3.Model3()
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = alt_image(patch)
    rom = rom48()
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    sym = {v: k for k, v in patch.syms.items()}
    sites = {a: SITES[a][2] for a in SITES}
    ns = NextState(patch)
    span = [None]
    dbg_prev = [0]
    role_idx = {M3.F: R_FLOOR, M3.W: R_WALL, M3.R: R_RAMP, M3.FR: R_FRINGE, M3.A: R_ARROW, M3.O: R_OBJECT,
                M3.PD: R_PAD, M3.C: R_CONSOLE}

    def fail(k, e):
        c[k] += 1
        if len(ex[k]) < 5:
            ex[k].append(e)

    def event(pc, sim):
        r, m = sim.registers, sim.memory
        name = sites[pc]
        sp = r[SP]
        if name in NESTED and span[0] is not None and sp < span[0]:
            c['nested in t_bs (run inside it)'] += 1
            return
        if name not in NESTED and name != 't_isr':      # an interrupt inside BE38 does not end t_bs's span
            span[0] = sp if name == 't_bs' else None
        get = lambda a: m[a]
        regs = list(r)
        if name in ('t_list', 't_clr', 't_paste', 't_spr', 't_bs'):
            stop_pc, stop_sp = pc + 3, sp
        elif name in ('t_c05a', 't_isr'):
            stop_pc, stop_sp = m[sp] | m[sp + 1] << 8, sp + 2
        else:
            stop_pc, stop_sp = {'t_dly': 0xDD93, 't_sd': 0xE119, 't_su': 0xE128, 't_sl': 0xE137, 't_sr': 0xE151, 't_cls': 0xB2CC,
                                't_prn': 0xB1FF}[name], sp
        if name == 't_list' and os.environ.get('QZ_TAGDEBUG') and m[0xAF17] == 8 and not c.get('dbg'):
            before = c.get('tags differ from the model!', 0)
            check_tags(m, after_list=True)
            if c.get('tags differ from the model!', 0) > before:
                c['dbg'] = 1
                l = r[6] << 8 | r[7]
                for row in range(8):
                    mrow, trow = '', ''
                    for px in range(32):
                        v = model.sh[(0x8080 + row * 4 + (px >> 3)) * 8 + (px & 7)]
                        k = model.tagkey.get(v & 0xFFFF, ('n',))
                        mrow += ('#' if v & cm.INK else '') + (k[1][:2] if k[0] == 'role' else k[0][:2]) + ' '
                        trow += '%02d ' % ns.pages[HPAGE][TAGS - 0x4000 + px * 152 + row]
                    print('M', row, mrow)
                    print('T', row, trow)
                print('FIRST DIVERGENCE before list (the previous list is %04x)' % dbg_prev[0], 'this list %04x AF0E %d AF10 %d AF16 %d AF17 %d parts %s' % (
                    l, m[0xAF0E] | m[0xAF0F] << 8, m[0xAF10], m[0xAF16], m[0xAF17],
                    [(x, y, op, len(rw)) for x, y, op, rw in list_parts(m, l)]))
        if name == 't_list':
            dbg_prev[0] = r[6] << 8 | r[7]
        on = _OrigNS()
        mo = _mem(get, rom, on, {})
        ro, ok_o = _run(mo, regs, on, stop_pc, stop_sp, 'qo')
        if clocks and c['clock ' + name] < clocks:
            clock_matrix(name, pc, get, regs, stop_pc, stop_sp)
        mp = _mem(get, alt, ns, psite)
        rp, ok_p = _run(mp, regs, ns, stop_pc, stop_sp, 'qp')
        c[name] += 1
        if not ok_o or not ok_p:
            fail('did not return!', (name, hex(pc), ok_o, ok_p))
            return
        bad = [(i, ro[i], rp[i]) for i in CMPV if ro[i] != rp[i]]
        if bad:
            fail('registers differ!' if any(i != 15 for i, a, b in bad) else 'R differs!', (name, hex(pc), bad[:4]))
        lo = sp - 64
        keys = {a for a in set(mo.ov) | set(mp.ov) if not lo <= a < sp}
        diff = [a for a in keys if mo.ov.get(a, get(a)) != mp.ov.get(a, get(a))]
        if diff:
            fail('memory differs!', (name, hex(pc), [hex(a) for a in sorted(diff)[:6]], len(diff)))
        if name == 't_c05a' and ns.var(V_L2ON):
            check_canvas(m, mo)
        if name == 't_paste':
            check_tags(m)
        if name == 't_spr' and ns.var(V_L2ON):
            check_sprites(get)
        if ns.var(V_L2ON) and name in ('t_isr', 't_spr'):      # every frame, and every update's placing
            check_lock()
        if ns.var(V_MONO):          # session 3: monochrome never shows Layer 2 or a sprite, nor runs a scroll step fast
            if ns.var(V_L2ON) or ns.l2 & 2 or ns.nr.get(0x15, 0) & 1 or ns.var(0x4CE1):
                fail('monochrome shows Layer 2 or sprites, or scrolls fast!', (name, hex(pc), ns.var(V_L2ON), ns.l2, ns.nr.get(0x15)))
            else:
                c['monochrome: Layer 2, sprites and fast scroll off after the hook'] += 1

    def clock_matrix(name, pc, get, regs, stop_pc, stop_sp):
        """The every-site matrix (hooklib.every_site): this event's hook entered at 3.5, 7, 14 and 28 MHz from the same
        state exits at the incoming clock with the same registers, game memory and Next state."""
        import copy
        import hashlib
        from . import hooklib
        out = {}

        def run(site, k):
            n2 = copy.deepcopy(ns)
            n2.nr[7] = k
            m2 = _mem(get, alt, n2, psite)
            r2, ok = _run(m2, regs, n2, stop_pc, stop_sp, 'qc')
            hp = bytearray(n2.pages[HPAGE])
            for a in SPEED_LATCHES:             # the latched incoming clock itself (VSPD, VSPD2, GSPD, ISRSPD)
                hp[a - 0x4000] = 0
            h = hashlib.md5(b''.join(bytes(hp if x == HPAGE else n2.pages[x]) for x in sorted(n2.pages)) + bytes(n2.pat)
                            + repr(sorted(m2.ov.items())).encode() + repr([r2[i] for i in CMPV]).encode()
                            + repr(n2.attr).encode()).hexdigest()
            return n2.nr.get(7, 0) & 3, (ok, h)
        cc, rows = hooklib.every_site([name], run)
        c['clock ' + name] += 1
        c['clock matrix cases'] += cc['cases']
        for k, v in cc.items():
            if k.endswith('!'):
                fail('clock matrix: %s' % k, (name, hex(pc)))

    def sdxy():
        tx, ty, dx, dy = ns.var(0x4BF3, 2), ns.var(0x4BF5), ns.var(V_DX, 2), ns.var(V_DY)
        sx = (tx - dx) % 320
        if sx >= 160:
            sx -= 320
        sy = (ty - dy) & 255
        if sy >= 128:
            sy -= 256
        return sx, sy, dx, dy

    def spos(g):
        b = ns.pages[STORE_BANK * 2][SPOS_OFF + 4 * g:SPOS_OFF + 4 * g + 4]
        return b[0] | b[1] << 8, b[2] | b[3] << 8

    def check_sprites(get):
        """At every E656: each draw record (last first) -> its groups, as p_spr makes them: the painted image
        (sprite_store's table), the pattern bytes in the group's slot = that image, the base position = the record's."""
        s0 = ns.pages[STORE_BANK * 2]
        n = min(get(0xAF09), 7)
        groups = []

        def group(lst, rows, typ, x, y):
            if len(groups) >= 21:
                return
            idx = lst - 0x9C00
            if idx < 0 or idx >= 0x1400:
                return
            v = s0[idx >> 1]
            if v == 255:
                return
            if v < 4:
                if not 1 <= typ <= 32:
                    return
                v = 4 * (typ - 1) + v
            groups.append((v, (x + 24) & 0xFFFF, ((y - 256 if y >= 200 else y) - 8 + rows) & 0xFFFF))
        w = lambda a: get(a) | get(a + 1) << 8
        for k in range(n - 1, -1, -1):
            r = 0xA320 + 8 * k
            x, y = get(r + 2) | get(r + 3) << 8, get(r + 4)
            if get(r + 1) & 0x80:
                group(w(w(0xAF9C)), 0, 0, x, y)
                group(w(0xAF9E), get(0xAFA4), 0, x, y)
                group(w(w(0xAF9A)), 0, 0, x, y)
                group(w(w(0xDDAE)), 0, 0, x, y)
                group(w(w(0xAFA0)), 0, 0, x, y)
            else:
                group(get(r + 5) | get(r + 6) << 8, 0, get(r + 7), x, y)
        if ns.var(0x4BDE) != len(groups):
            fail('sprite group count differs from the records!', (len(groups), ns.var(0x4BDE)))
            return
        for g, (img, bx, by) in enumerate(groups):
            if spos(g) != (bx, by):
                fail('sprite base differs from the record!', (g, spos(g), (bx, by)))
            pat = ns.var(GPAT_ADDR + g)
            src = ns.pages[STORE_BANK * 2 + 1 + img // 10][(img % 10) * 768:(img % 10) * 768 + 768]
            if bytes(ns.pat[pat * 256:pat * 256 + 768]) != bytes(src):
                fail('sprite pattern is not the painted image!', (g, img, pat))
            else:
                c['sprite groups equal to the model'] += 1
        c['sprite checks (E656)'] += 1

    def check_lock():
        """At every frame (each ISR) and update: the scroll registers show the shown origin (DX, DY); every group's
        3 sprites sit at its base + (TX - DX, TY - DY): locked to the scenery the canvas shows. Off mode: no offset."""
        sx, sy, dx, dy = sdxy()
        if not patch.smooth and (sx or sy):
            fail('off mode: the shown origin is not the committed one!', (sx, sy))
        if (ns.nr.get(0x16, 0) | (ns.nr.get(0x71, 0) & 1) << 8) != (dx - 32) % 320 or ns.nr.get(0x17, 0) != (dy - 32) & 255:
            fail('Layer 2 scroll is not the shown origin!', (ns.nr.get(0x16), ns.nr.get(0x71), ns.nr.get(0x17), dx, dy))
        for g in range(ns.var(0x4BDF)):
            bx, by = spos(g)
            for i in range(3):
                a = ns.attr[3 * g + i]
                X = a[0] | (a[2] & 1) << 8
                Y = a[1] | (a[4] & 1) << 8
                if X != (bx + sx) & 0x1FF or Y != (by + sy + 16 * i) & 0x1FF or a[3] != 0xC0 | (ns.var(GPAT_ADDR + g) + i):
                    fail('sprite not locked to the scenery!', (g, i, X, Y, (bx + sx) & 0x1FF, (by + sy + 16 * i) & 0x1FF))
                    return
        c['frames locked (sprites + scroll = shown origin)'] += 1

    def check_tags(m, after_list=False):
        rows, sh, pg = m[0xAF17], model.sh, ns.pages[HPAGE]
        for row in range(rows):
            for px in range(32):
                v = sh[(0x8080 + row * 4 + (px >> 3)) * 8 + (px & 7)]
                key = model.tagkey.get(v & 0xFFFF, ('none',))
                exp = (24 if key[0] == 'screen' else R_FACE if key[0] == 'face' else 0) if v & cm.INK else \
                    role_idx.get(key[1]) if key[0] == 'role' else None
                if exp is None:
                    c['tag pixels the model cannot name'] += 1
                    continue
                got = pg[TAGS - 0x4000 + px * 152 + row]
                if got != exp:
                    fail('tags differ from the model!', (m[0xAF15], m[0xAF17], px, row, exp, got, key))
                else:
                    c['tag pixels equal'] += 1

    def check_canvas(m, mo):
        tx, ty = ns.var(0x4BF3, 2), ns.var(0x4BF5)
        sh = model.sh
        n_ok = 0
        for by in range(152):
            for bx in range(256):
                v = sh[(0x8300 + by * 32 + (bx >> 3)) * 8 + (bx & 7)]
                key = model.tagkey.get(v & 0xFFFF, ('none',))
                at = mo.ov.get(0x5800 + (by >> 3) * 32 + (bx >> 3), m[0x5800 + (by >> 3) * 32 + (bx >> 3)])
                atink = (at & 7) | (8 if at & 0x40 else 0)
                if v & cm.INK:
                    exp = 24 if key[0] == 'screen' else (20 if at & 7 == 0 else atink) if key[0] == 'face' else atink
                elif key[0] == 'role':
                    exp = role_idx[key[1]]
                else:
                    c['canvas pixels the model cannot name (snapshot bytes)'] += 1
                    continue
                got = ns.canvas((tx + bx) % 320, ty + by)
                if got != exp:
                    fail('canvas differs from the model!', (bx, by, exp, got, key))
                    c['canvas differs at commit %d, row band %d' % (c['commits checked'], by // 8)] += 1
                else:
                    n_ok += 1
        c['canvas pixels equal to the model'] += n_ok
        c['commits checked'] += 1

    mpcs = model.pcs()

    def hook(pc, sim):
        if pc in mpcs:
            model.on(pc, sim)
        if pc in sites:
            event(pc, sim)
    frames, err = rzx.trace(rzx_path, mpcs | set(sites), hook, stop=stop)
    c['frames'] = frames
    if err:
        fail('replay desync!', err)
    return c, dict(ex), []


def unit_tests(patch, states, neg=None):
    """Not built yet (session 2): the every-site clock matrix, negatives."""
    return collections.Counter({'unit tests not built!': 1})


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : quazatron (session 1: scenery canvas on Layer 2; UNPROVEN)')
    ok, paths = build(z80, out, name, say)
    for r in list(getattr(a, 'rzx', None) or []):
        cc, ex, st = verify(QuazatronPatch(), r, stop=getattr(a, 'quick', None))
        say('Verify    : %s -> %s' % (os.path.basename(r), dict(cc)))
        ok = False
    say('Result    : %s' % ('FAILED (not verified: session 2)' if True else 'PASSED'))
    return False


# --- droid sprites: painted by parts (our own design; pilot runs/quazatron/work/s1/paint2.py, mock-up v2) ----------
# Every figure the draw records (A320) show becomes up to 3 sprites (16 x 48, the list origin at box (8, 40)) of an
# image painted at build time. Enemy (A000 type 1-32): image 4 (t - 1) + frame, the body frame list + the type's
# number plate, coloured by the type's class (the plate's letter) and rank. Player (record byte 1 bit 7): one image per
# part list (chassis, drive, weapon, dome, second weapon), each part its own colours. Shots and blasts: one image per
# list. A region (ink-closed paper run) takes one colour; plate band ink takes the plate colour; other ink is black.
# The runtime lists at 0x9D02-0x9F91 (mirrors the game builds at start) come from the snapshot run to play in the
# simulator (keys 4, ENTER, fire); they were identical in 8 dumps of 3 recordings and 2 decks (games/quazatron.md).
STORE_BANK = 23             # pages 46.. : 46 = list -> image table, 47.. = images, 10 a page (768 bytes each)
S0 = 2 * STORE_BANK
IMG = 768
PLATE = {1: 'X9', 2: 'X8', 3: 'U9', 4: 'U8', 5: 'U7', 6: 'R8', 7: 'R7', 8: 'R6', 9: 'R5', 10: 'B7', 11: 'B6',
         12: 'B5', 13: 'L6', 14: 'L5', 15: 'D0', 16: 'L4', 17: 'L3', 18: 'B4', 19: 'B3', 20: 'S6', 21: 'L2', 22: 'B2',
         23: 'C5', 24: 'S4', 25: 'S3', 26: 'S2', 27: 'S1', 28: 'C3', 29: 'C2', 30: 'C1', 31: 'AB', 32: 'A1'}
ENEMY_FRAMES = (0x9EF1, 0x9F41, 0xA975, 0xA9C5)
PLATE_LIST = 0xDDB0
PLAYER_DOMES = (0x9EA1, 0x9EC8, 0xAE2F, 0xAE56)
DRIVES = (0xAE07, 0xAE14, 0xAE1A, 0xAE21)
SHOTS = (0x9E0D, 0x9E30, 0x9E51, 0x9E7B, 0xAA80, 0xAAA3, 0xAAC5, 0xAAE6, 0xAB07, 0xAB21)
BLASTS = (0xAA17, 0xAA35, 0xAA58, 0xABE1, 0xAC24, 0xAC6B, 0xACB5, 0xACC9, 0xACDB, 0xACF0, 0xACFC, 0xAD36, 0xAD5C,
          0xAD7F, 0xADC4, 0xADE7, 0xA78A)
CLASS = {
    'X': dict(dome=(200, 205, 215), glint=(255, 255, 255), band=(40, 50, 80), letters=(255, 255, 255), base=(120, 130, 150)),
    'U': dict(dome=(190, 140, 240), glint=(240, 220, 255), band=(50, 20, 80), letters=(255, 220, 120), base=(110, 70, 170)),
    'R': dict(dome=(240, 70, 60), glint=(255, 200, 160), band=(70, 10, 10), letters=(255, 230, 80), base=(150, 40, 40)),
    'B': dict(dome=(70, 130, 255), glint=(200, 230, 255), band=(10, 20, 80), letters=(110, 240, 255), base=(40, 70, 170)),
    'L': dict(dome=(165, 245, 160), glint=(235, 255, 225), band=(5, 55, 15), letters=(255, 255, 140), base=(15, 125, 35)),   # v3
    'D': dict(dome=(250, 150, 40), glint=(255, 230, 160), band=(80, 40, 0), letters=(255, 255, 255), base=(160, 80, 30)),
    'S': dict(dome=(240, 90, 200), glint=(255, 210, 245), band=(70, 10, 60), letters=(160, 255, 220), base=(150, 40, 120)),
    'C': dict(dome=(60, 220, 220), glint=(210, 255, 255), band=(0, 60, 70), letters=(255, 150, 80), base=(30, 130, 140)),
    'A': dict(dome=(250, 210, 60), glint=(255, 250, 200), band=(90, 60, 0), letters=(255, 80, 80), base=(170, 120, 30)),
}
PLAYER = dict(pdome=(120, 230, 255), pglint=(255, 255, 255), chassis=(245, 245, 235), marking=(255, 90, 60),
              drive=(90, 110, 160), weapon=(255, 70, 70), weapon_ink=(180, 50, 50), drive_ink=(90, 110, 160))
EFFECT = dict(shot=(255, 240, 120), blast=(255, 140, 40))


def _mix(c, k):
    return tuple(int(v + (255 - v) * k) for v in c) if k >= 0 else tuple(int(v * (1 + k)) for v in c)


def scheme(t):
    """Class = the plate letter; rank in the class (type order = strength): weaker lighter, stronger deeper."""
    s = dict(CLASS[PLATE[t][0]])
    same = sorted(k for k in PLATE if PLATE[k][0] == PLATE[t][0])
    k = same.index(t) / (len(same) - 1) if len(same) > 1 else 0.5
    s['dome'] = _mix(s['dome'], 0.3 - 0.55 * k)
    s['base'] = _mix(s['base'], 0.25 - 0.6 * k)
    s['outline'] = (0, 0, 0)
    return s


def list_parts(mem, a):
    n = mem[a]; a += 1; out = []
    for _ in range(n):
        x = mem[a] - 256 if mem[a] & 0x80 else mem[a]
        y = mem[a + 1] - 256 if mem[a + 1] & 0x80 else mem[a + 1]
        f = mem[a + 2]; h = f & 63
        out.append((x, y, 'mask' if f & 0x80 else 'set' if f & 0x40 else 'or', mem[a + 3:a + 3 + h]))
        a += 3 + h
    return out


def render(mem, a, cv, tag, dy=0):
    for pi, (x, y, op, rows) in enumerate(list_parts(mem, a)):
        for r, g in enumerate(rows):
            for b in range(8):
                gb = (g >> (7 - b)) & 1
                p = (x + b, y + r + dy)
                if op == 'mask' and gb:
                    cv[p] = (0, (tag, pi))
                elif op == 'or' and gb:
                    cv[p] = (1, (tag, pi))
                elif op == 'set':
                    cv[p] = (gb, (tag, pi))
    return cv


def regions(cv):
    paper = {p for p, (ink, t) in cv.items() if not ink}
    seen, regs = {}, []
    for p in sorted(paper, key=lambda q: (q[1], q[0])):
        if p in seen:
            continue
        st, px = [p], []
        seen[p] = len(regs)
        while st:
            q = st.pop(); px.append(q)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                r = (q[0] + d[0], q[1] + d[1])
                if r in paper and r not in seen:
                    seen[r] = len(regs); st.append(r)
        xs = [a for a, b in px]; ys = [b for a, b in px]
        regs.append((px, (min(xs), min(ys), max(xs), max(ys))))
    return regs


def paint_enemy(mem, t, frame):
    """{(x, y): rgb}: the body frame + the plate of type t, painted by regions."""
    m = bytearray(mem)
    a = (m[0x61B0] | m[0x61B1] << 8) + 2 * t
    f = m[0x61BC] | m[0x61BD] << 8
    m[0xDDCA:0xDDD2] = m[f + 8 * m[a]:f + 8 * m[a] + 8]
    m[0xDDD5:0xDDDD] = m[f + 8 * m[a + 1]:f + 8 * m[a + 1] + 8]
    cv = {}
    render(m, frame, cv, 0)
    render(m, PLATE_LIST, cv, 1)
    s = scheme(t)
    col = {}
    regs = regions(cv)
    dome = [r for r in regs if r[1][3] <= -17]
    base = [r for r in regs if r[1][1] >= -8]
    big_d = max(dome, key=lambda r: len(r[0]))[0] if dome else None
    big_b = max(base, key=lambda r: len(r[0]))[0] if base else None
    for px, bb in regs:
        c = (s['dome'] if px is big_d else s['glint'] if bb[3] <= -17 else s['base'] if px is big_b else
             _mix(s['base'], -0.4) if bb[1] >= -8 else s['letters'])
        for p in px:
            col[p] = c
    for p, (ink, tg) in cv.items():
        if ink:
            col[p] = s['band'] if tg[0] == 1 and tg[1] >= 2 else (0, 0, 0)
    return col


def paint_part(mem, lst, kind):
    cv = render(mem, lst, {}, 0)
    col = {}
    regs = regions(cv)
    big = max(regs, key=lambda r: len(r[0]))[0] if regs else None
    for px, bb in regs:
        if kind == 'dome':
            c = PLAYER['pdome'] if len(px) >= 6 else PLAYER['pglint']
        elif kind == 'chassis':
            c = PLAYER['chassis'] if px is big else PLAYER['marking']
        elif kind in ('shot', 'blast'):
            c = EFFECT[kind]
        else:
            c = PLAYER[kind]
        for p in px:
            col[p] = c
    for p, (ink, tg) in cv.items():
        if ink:
            col[p] = PLAYER[kind + '_ink'] if kind in ('drive', 'weapon') else (0, 0, 0)
    return col


def rgb332(c):
    r, g, b = (min(7, (v * 7 + 127) // 255) for v in c)
    v = r << 5 | g << 2 | b >> 1
    return 0xE2 if v == 0xE3 else v


def image_bytes(col):
    """16 x 48, origin at (8, 40), transparent 0xE3; pixels outside the box are dropped (counted by the caller)."""
    im = bytearray([0xE3] * IMG)
    lost = 0
    for (x, y), c in col.items():
        bx, by = x + 8, y + 40
        if 0 <= bx < 16 and 0 <= by < 48:
            im[by * 16 + bx] = rgb332(c)
        else:
            lost += 1
    return bytes(im), lost


def play_memory(z80):
    """The game's memory in play: the snapshot run in the simulator with the start keys (4, ENTER, fire)."""
    from .recorder import Recorder
    from .machine import parse_inputs
    r = Recorder(z80, log=lambda *a: None)
    st = lambda k, n: r.play([(frozenset() if k == '' else parse_inputs(k), n)])
    st('', 20); st('4', 5); st('', 10); st('ENTER', 5); st('', 100); st('K:FIRE', 8); st('', 200)
    return bytes(r.m.sim.memory[:65536])


def sprite_store(mem):
    """-> ({bank: bytes}, info). Page S0: (list - 0x9C00) >> 1 -> 0-3 enemy frame, 128+ image, 255 none."""
    w = lambda a: mem[a] | mem[a + 1] << 8
    table = bytearray([255] * 8192)
    images = []
    lost = 0
    for t in range(1, 33):
        for f in ENEMY_FRAMES:
            b, l = image_bytes(paint_enemy(mem, t, f)); images.append(b); lost += l
    for i, f in enumerate(ENEMY_FRAMES):
        table[(f - 0x9C00) >> 1] = i
    kinds = [(l, 'dome') for l in PLAYER_DOMES] + [(w(a), 'chassis') for a in range(0xA403, 0xA411, 2)] + \
            [(l, 'drive') for l in DRIVES] + [(w(a), 'weapon') for a in range(0xA411, 0xA433, 2)] + \
            [(l, 'shot') for l in SHOTS] + [(l, 'blast') for l in BLASTS]
    done = {}
    for lst, kind in kinds:
        if lst in done or not 0x9C00 <= lst < 0xB000 or lst in ENEMY_FRAMES:
            continue
        b, l = image_bytes(paint_part(mem, lst, kind)); lost += l
        done[lst] = len(images)
        table[(lst - 0x9C00) >> 1] = len(images)
        images.append(b)
    if len(images) > 255:
        raise ValueError('too many sprite images')
    table[ROLETAB_OFF:ROLETAB_OFF + 192] = roletab()      # p_tags reads it with S0 at slot 6 (session 3)
    pages = [bytes(table)]
    for k in range(0, len(images), 10):
        pg = b''.join(images[k:k + 10])
        pages.append(pg + bytes(8192 - len(pg)))
    if len(pages) % 2:
        pages.append(bytes(8192))
    banks = {STORE_BANK + i // 2: pages[i] + pages[i + 1] for i in range(0, len(pages), 2)}
    return banks, {'images': len(images), 'parts': len(done), 'pixels outside the box': lost, 'pages': len(pages)}
