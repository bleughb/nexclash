"""Solomon's Key (U.S. Gold / Probe 1987, 48K) engine 'solomons_key'. Additive module: reachable only
through is_solomons_key().

Game facts (games/solomons_key.md): clean scenery at 0x5B00, compose buffer at 0x7300 (32 bytes per line, line L
column c = screen pixel row L, byte c). Main loop 37799: 38712 restores the last pass's dirty blocks from clean,
figures are masked plots into compose by 38093 (A = frame, E = x, D = y; 16 lines of 2 mask bytes, then of 2
graphics bytes, at 56866 + 64A), 38373 lists the dirty 3 x 16 block, 38551 copies each to the screen. Interrupts off
all game. Figures have no colour: they take the ink of the cells they cross.
Hooks (asm/solomons_key_hooks.asm, alt ROM image 1 at 0x386E: the whole image is Sinclair's ROM + the hooks; their state in
RAM page SPAGE at slot 6 only inside a hook): the plotter runs unchanged, so all game memory is identical; plots are logged;
the blit's source is the clean copy; after the blit the log is written as sprites. Every hook keeps R as the original's and
adds its own time to a debt that the pad (e_pad: the game's delay 39194 in the pass padding 38032) repays (2026-11-05).
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E            # hooks in alt ROM image 1
ALT_PAGE, ALT_BANK = 26, 13 # the image of 0x2000-0x3FFF the stub copies into alt ROM image 1
SPAGE, STATE_BANK = 24, 12  # the hooks' state page, at slot 6 inside a hook (asm SPAGE; the stack is in slot 7)
MTAB = 0x200                # in the state page: frame -> 0x80 for the mirrored frames (asm MTAB)
DEBT = 4                    # in the state page: debt, 3 bytes (1/256 step, steps of 21 T)
PAD, PAD_RET, PAD_END = 38046, 38049, 38052   # CALL 39194 in the pass padding 38032 (BC = 500): the operand -> e_pad
PAT_BANK = 11               # sprite patterns, uploaded once at start (pages 22, 23)
TAIL_ADDR = 0x9000          # tile map: cleared at every level build before any read (41886; scan: write-first on every recording)
GFX = 56866
NPAT = 128
NMAX = 64
PLOTD = 38146
CLEAN, COMPOSE = 0x5B00, 0x7300
E_PLOT, CONT_PLOT = 38093, 38096
CALL_BLIT, AFTER_BLIT = 37969, 37972
BLIT = 38551
RESTORE = 38730             # copies one 3 x 16 block clean -> compose
CLS, CONT_CLS = 39097, 39100
SRC = (38584, 38656)
SITES_ORIG = {38093: 'f5c5d5', 37970: '9796', 39097: '21ff5a', 38584: '73', 38656: '73', 38047: '1a99'}
INTERIORS = (39098, 39099)
SEQUELS = (38094, 38095)    # one-byte PUSHes: the original runs on through them, from 38093 only
SPECCY = [0x00, 0xFF, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC]
CMP = list(range(0, 13)) + list(range(14, 25)) + [26, 27]   # every register, R (15) included; not T, MEMPTR
BLIT_CMP = [i for i in CMP if i != 17]   # F': the blit's last ADD HL,BC sets H and bits 3, 5 from the source address; no code reads
                                         # F' before overwriting it (every EX AF,AF' site: games/solomons_key.md)
FLIP = 43300                # 43209 mirrors frames 48-58 in place; bit 0 = mirrored from the snapshot
FLIP_FRAMES = range(48, 59)

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'solomons_key_colours.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'solomons_key.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_solomons_key(snap):
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
# Patterns: 128 bytes per frame; 1 ink, 2 solid body (mask 0, graphic 0), 0 transparent
# ---------------------------------------------------------------------------------------------

def frame_rows(peek, a):
    """-> 16 (mask, graphic) rows of 16 bits, as the plotter reads them: words, low byte first in the left byte."""
    g = GFX + 64 * a
    out = []
    for r in range(16):
        # POP DE: E = first byte, D = second; the plotter's left byte is E for the 3-byte shifted form
        out.append((peek(g + 2 * r) << 8 | peek(g + 2 * r + 1), peek(g + 32 + 2 * r) << 8 | peek(g + 32 + 2 * r + 1)))
    return out


def gkey(a, r, b):
    return '%04X' % (GFX + 64 * a + 32 + 2 * r + b)


def nibble(m, g, k, e):
    """Mask row m, graphics row g, column k, colour map entry e of the graphics byte (or None)."""
    bit = k & 7
    ink = g >> (15 - k) & 1
    solid = not (m >> (15 - k) & 1)
    if e is not None:
        if len(e) > 3 and e[3] & (0x80 >> bit):
            return 0
        if e[2][bit]:
            return e[2][bit]
    return 1 if ink else (2 if solid else 0)


def pattern(peek, a, cmap=None):
    out = bytearray(128)
    rows = frame_rows(peek, a)
    for r, (m, g) in enumerate(rows):
        for k in range(16):
            e = None
            if cmap:
                key = gkey(a, r, k >> 3)
                e = cmap.get(key)
                if e is not None and e[0] != peek(int(key, 16)):
                    e = None
            v = nibble(m, g, k, e)
            out[r * 8 + k // 2] |= v << 4 if k % 2 == 0 else v
    return bytes(out)


def patterns(peek, cmap=None):
    return b''.join(pattern(peek, a, cmap) for a in range(NPAT))


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

def _whole_rom_page(code=b''):
    """Image of 0x2000-0x3FFF for alt ROM image 1: Sinclair's ROM with `code` at ROM_ORG (its 0xFF area)."""
    from .build import rom48
    rom = rom48()
    if any(b != 0xFF for b in rom[ROM_ORG:ROM_ORG + len(code) + 20]):
        raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
    page = bytearray(rom[0x2000:0x4000])
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    return bytes(page)


LOWT = 0x300                # in the state page: the dirty-block debt table (asm LOWT)
LOWC = 2.3                  # T a byte: the blit's extra contention reading a source row 104-191 from the clean copy
                            # (JNext 1.1.104: a build with only the source change +0.39 %, about 300 such bytes a pass)
T_BLK = 15.75                # the post loop's own time a dirty block (measured on the verifier)


def low_rows(d):
    """Source rows 104-191 of the dirty block at D, as the blit's geometry (block) gives it."""
    y, _ = block(0, d)
    return max(0, min(y + 15, 191) - max(y, 104) + 1)


def contention(d):
    """The build's extra blit time for the block at D, T (LOWC a byte, 3 bytes a row)."""
    return 3 * low_rows(d) * LOWC


def state_page():
    """The hooks' state page as the build starts it: zero, MTAB and LOWT."""
    st = bytearray(8192)
    for f in FLIP_FRAMES:
        st[MTAB + f] = 0x80
    for d in range(256):
        v = int(round((T_BLK + contention(d)) * 256 / 21.0))
        st[LOWT + d], st[LOWT + 0x100 + d] = v & 255, v >> 8
    return bytes(st)


class PlainPatch:
    """The plain .nex: no hooks. Alt ROM image 1 = Sinclair's 48K ROM (+ the tail's register block in its 0xFF area), so the
    game's delay reads Sinclair's ROM bytes as on a 48K."""
    name = "Solomon's Key plain conversion, Sinclair's ROM as the alt ROM"
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
        self.extra_banks = {ALT_BANK: self.page + bytes(8192)}

    def apply(self, snap):
        pass


class SolomonsKeyPatch:
    name = "Solomon's Key figures -> hardware sprites (hooks in alt ROM image 1, state in a page at slot 7)"

    def __init__(self, prof=None, rom_code=None, colours=None, extra_sites=None, drop_sites=()):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 128
        self.regblock = ROM_ORG + len(self.code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = _whole_rom_page(self.code)
        self.state = state_page()
        self.colours = colours
        s = self.syms
        new = {38093: b'\xC3' + s['e_plot'].to_bytes(2, 'little'), 37970: s['e_cp'].to_bytes(2, 'little'),
               39097: b'\xC3' + s['e_cls'].to_bytes(2, 'little'), 38584: b'\x5B', 38656: b'\x5B',
               38047: s['e_pad'].to_bytes(2, 'little')}
        self.sites = [(a, bytes.fromhex(old), new[a]) for a, old in SITES_ORIG.items() if a not in drop_sites]
        self.extra_banks = {ALT_BANK: self.page + bytes(8192), STATE_BANK: self.state + bytes(8192)}
        self.pats = None

    def apply(self, snap):
        if snap.is128:
            raise ValueError("Solomon's Key patch expects the 48K snapshot")
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError("unexpected code at %d (%s, expected %s) - not the expected version of Solomon's Key"
                                 % (a, cur.hex(), old.hex()))
        cmap = load_colours() if self.colours is None else self.colours
        self.pats = patterns(lambda a: ram[a - 0x4000], cmap)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {PAT_BANK: self.pats + bytes(16384 - len(self.pats)), ALT_BANK: self.page + bytes(8192),
                            STATE_BANK: self.state + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Next-side model
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, pats):
        self.nr = {0x56: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = pats
        self.bad = []
        self.speed = 0              # NR 7 bits 1:0: the clock now
        self.speed_in = 0           # the clock a hook is entered at (the every-site matrix)
        self.sel = 7                # port 0x243B's register

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x07:
            self.speed = val & 3
        elif reg not in (0x34, 0x56):
            self.bad.append(('nextreg', reg))

    def visible(self):
        """-> [(frame, x, y)] in slot order. Anything but a plain 4-bit sprite is a failure for the caller."""
        out = []
        for i, (a0, a1, a2, a3, a4) in enumerate(self.attr):
            if not a3 & 0x80:
                continue
            f = ((a3 & 0x3F) << 1) | ((a4 >> 6) & 1)
            if not a3 & 0x40 or not a4 & 0x80 or a4 & 0x3F or a2 & 0xF6:
                self.bad.append(('sprite form', i, (a0, a1, a2, a3, a4)))
            out.append((f, a0 + (a2 & 1) * 256 - 32, a1 - 32, (a2 >> 3) & 1))
        return out


def _ula(y, col):
    return 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | col


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _rom(patch):
    """Alt ROM image 1 as the stub leaves it on the Next (nextboot.alt_image: Sinclair's ROM + the hooks)."""
    from .nextboot import alt_image
    return bytes(alt_image(patch))


class _PMem:
    """Patched view: alt ROM image 1 below 0x4000, the state page at 0xC000 while NR 0x56 maps it, patch sites, the
    screen from scr (patched screen differences), game memory read through get; writes to an overlay."""

    def __init__(s, get, page, psite, rom, scr=None, ns=None):
        s.get, s.page, s.psite, s.rom, s.ov, s.romw, s.scr, s.ns = get, page, psite, rom, {}, 0, scr, ns

    def mapped(s):
        return s.ns is not None and s.ns.nr.get(0x56, 0) == SPAGE

    def __getitem__(s, a):
        if a < 0x4000:
            return s.rom[a]
        if 0xC000 <= a < 0xE000 and s.mapped():
            return s.page[a - 0xC000]
        v = s.ov.get(a)
        if v is not None:
            return v
        v = s.psite.get(a)
        if v is not None:
            return v
        if s.scr is not None:
            v = s.scr.get(a)
            if v is not None:
                return v[0]
        return s.get(a)

    def __setitem__(s, a, v):
        if a < 0x4000:
            s.romw += 1
        elif 0xC000 <= a < 0xE000 and s.mapped():
            s.page[a - 0xC000] = v
        else:
            s.ov[a] = v

    def __len__(s):
        return 65536


def _machine(mem, regs, ns):
    """A simulator for patched or original code; Z80N from z80n.install (NEXTREG at its own 20 / 17 T: the pace
    accounting counts every hook's time)."""
    from .simpool import machine
    from . import z80n
    sim = machine(_rw(), mem, regs, 'p')
    z80n.install(sim, ns.nextreg)

    class Tr:
        def read_port(s, regs_, port):
            if port == 0x253B and ns.sel == 7:
                return ns.speed << 4 | ns.speed      # actual speed 5:4, programmed 1:0 (hooklib.NextModel)
            ns.bad.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            if port == 0x243B:
                ns.sel = value
            else:
                ns.bad.append(('out', port))
    sim.set_tracer(Tr())
    return sim


DIV = (1.0, 2.0, 4.0, 8.0)      # 3.5 MHz T an instruction's T takes at NR 7 = 0-3 (28 MHz: no wait states modelled)


def _runt(sim, stop, ns, limit=400000):
    """_run with real time: -> (returned, time in 3.5 MHz T), each instruction at the clock it starts at."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n, t = 0, 0.0
    while not stop(R):
        t0, d = R[25], DIV[ns.speed]
        ops[mem[R[24]]]()
        t += (R[25] - t0) / d
        n += 1
        if n > limit:
            return False, t
    return True, t


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
    """Persistent patched state: hook page, Next state, the patched screen's differences."""

    def __init__(self, patch, get):
        self.patch = patch
        self.page = bytearray(patch.state)          # the state page (0xC000 at slot 6 inside a hook)
        self.psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
        self.rom = _rom(patch)
        self.time = []              # (event, extra T over the original, debt change in T)
        self.cont = 0.0             # the blit's extra contention the debt adds (T, estimated: contention())
        self.gone = 0               # debt let go at the pads (T): over CAP after a long unpadded stretch
        snap = bytes(get(a) for a in range(65536)) if get else None
        self.pats = patterns(lambda a: snap[a], patch.colours or {}) if snap else None
        self.pmask = {}             # (frame, x & 7) -> [(row, byte, opaque mask, value)]
        self.ns = NextState(self.pats)
        self.scr = {}               # screen address -> (patched value, original value at the last blit)
        self.figs = []              # the model's log
        self.rest = []              # mid-pass restores: (E, D, figures logged by then)
        self.clean_prev = None      # the clean copy at the last blit
        self.tcost = []

    def rows(self, f, xs, mir=0):
        k = (f, xs, mir)
        v = self.pmask.get(k)
        if v is None:
            v = []
            b0 = f * 128
            for r in range(16):
                op, val = 0, 0
                for c in range(16):
                    b = self.pats[b0 + r * 8 + c // 2]
                    n = (b >> 4) if c % 2 == 0 else b & 15
                    if n:
                        s = 23 - xs - (15 - c if mir else c)
                        op |= 1 << s
                        if n != 2:
                            val |= 1 << s
                for j in range(3):
                    o, w = (op >> (16 - 8 * j)) & 255, (val >> (16 - 8 * j)) & 255
                    if o:
                        v.append((r, j, o, w))
            self.pmask[k] = v
        return v


CAP = 2048                  # e_pad: steps carried at most after a pad (asm CAP)


def debt_t(page):
    """The hooks' debt in the state page, in T (32 bits: 1/256 steps of 21 T)."""
    return int.from_bytes(bytes(page[DEBT:DEBT + 4]), 'little') * 21 / 256.0


def owed_steps(page):
    return int.from_bytes(bytes(page[DEBT + 1:DEBT + 4]), 'little')


def _r(r, n):
    """R after n more M1 cycles (bit 7 kept)."""
    return (r & 0x80) | ((r + n) & 0x7F)


def _time(eng, kind, extra, d0, fl):
    """The pace check: a hook's debt change must be its own time over the original's, to rounding (one 1/256 step)."""
    d = debt_t(eng.page) - d0
    eng.time.append((kind, round(extra, 1), d))
    if eng.ns.speed_in == 0 and abs(d - extra) > 3:
        fl.append(("%s: debt change is not the hook's time over the original" % kind, round(d, 2), extra))


def _speed(eng, kind, fl):
    if eng.ns.speed != eng.ns.speed_in:
        fl.append(('%s: exit speed is not the incoming one' % kind, eng.ns.speed, eng.ns.speed_in))
        eng.ns.speed = eng.ns.speed_in
    if eng.ns.sel != 7:
        fl.append(('%s: port 0x243B left on another register' % kind,))
        eng.ns.sel = 7


def _common(eng, kind, p, fl):
    if eng.ns.nr.get(0x56, 0) != 0:
        fl.append(('%s: slot 6 left on the state page' % kind,))
        eng.ns.nr[0x56] = 0
    if p.romw:
        fl.append(('%s: wrote ROM' % kind,))


def plot_event(eng, get, R):
    """From the original's state at 38093: at 38096 the same registers as after the three PUSHes (R included), the
    same stack, no other game memory written, the debt grown by the hook's own time (JP, hook, JP back)."""
    f = []
    log = get(PLOTD) == 115
    if log:
        eng.figs.append((R[0], R[5], R[4], 1 if R[0] in FLIP_FRAMES and get(FLIP) & 1 else 0))
    sp = R[12]
    ro = list(R)
    ro[12] = (sp - 6) & 0xFFFF
    ro[24] = CONT_PLOT
    ro[15] = _r(R[15], 3)
    p = _PMem(get, eng.page, eng.psite, eng.rom, ns=eng.ns)
    start = list(R)
    start[24] = eng.patch.syms['e_plot']
    start[15] = _r(R[15], 1)                     # the site's JP
    d0 = debt_t(eng.page)
    sim = _machine(p, start, eng.ns)
    k = eng.ns.speed = eng.ns.speed_in
    ok, tp = _runt(sim, lambda r: r[24] == CONT_PLOT, eng.ns)
    if not ok:
        return [('plot hook did not return',)]
    rp = sim.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('plot: registers differ', diff[:6], [ro[i] for i in diff[:3]], [rp[i] for i in diff[:3]]))
    want = {(sp - 1) & 0xFFFF: R[0], (sp - 2) & 0xFFFF: R[1], (sp - 3) & 0xFFFF: R[2], (sp - 4) & 0xFFFF: R[3],
            (sp - 5) & 0xFFFF: R[4], (sp - 6) & 0xFFFF: R[5]}
    if any(p[a] != v for a, v in want.items()):
        f.append(('plot: stack differs',))
    if [a for a in p.ov if not sp - 64 <= a < sp]:
        f.append(('plot: game memory written', len(p.ov)))
    _common(eng, 'plot', p, f)
    full = log and eng.page[0] >= NMAX * 3 and len(eng.figs) > NMAX
    _speed(eng, 'plot', f)
    _time(eng, 'plot ' + ('full' if full else 'figure' if log else 'scenery'), (10 - 33) / DIV[k] + tp, d0, f)
    return f


def cls_event(eng, get, R):
    eng.figs = []
    eng.rest = []
    eng.scr = {}
    sp = R[12]
    p = _PMem(get, eng.page, eng.psite, eng.rom, ns=eng.ns)
    start = list(R)
    start[24] = eng.patch.syms['e_cls']
    start[15] = _r(R[15], 1)
    d0 = debt_t(eng.page)
    hid = eng.page[1]
    sim = _machine(p, start, eng.ns)
    k = eng.ns.speed = eng.ns.speed_in
    ok, tp = _runt(sim, lambda r: r[24] == CONT_CLS, eng.ns)
    if not ok:
        return [('cls hook did not return',)]
    f = []
    ro = list(R)
    ro[6], ro[7], ro[24], ro[15] = 0x5A, 0xFF, CONT_CLS, _r(R[15], 1)
    diff = [i for i in CMP if ro[i] != sim.registers[i]]
    if diff:
        f.append(('cls: registers differ', diff[:6], [ro[i] for i in diff[:3]], [sim.registers[i] for i in diff[:3]]))
    if [a for a in p.ov if not sp - 64 <= a < sp]:
        f.append(('cls: game memory written', len(p.ov)))
    if eng.ns.visible():
        f.append(('cls: sprite visible', len(eng.ns.visible())))
    _common(eng, 'cls', p, f)
    _speed(eng, 'cls', f)
    _time(eng, 'cls %d' % hid, tp, d0, f)
    return f


def pad_event(eng, get, R):
    """From the original's state at 38046 (CALL 39194, BC = 500): original and patched run to 38049; the same registers
    (R and F included), no game memory written, and the debt changed by the patched time over the original's."""
    f = []
    sp = R[12]
    o = _OMem(get)
    so = _machine(o, list(R), NextState(eng.pats))
    t0 = so.registers[25]
    if not _run(so, lambda r: r[24] == PAD_RET and r[12] == sp, limit=2000000):
        return [('pad: original did not return',)]
    to = so.registers[25] - t0
    ro = list(so.registers)
    p = _PMem(get, eng.page, eng.psite, eng.rom, ns=eng.ns)
    start = list(R)
    start[12] = (sp - 2) & 0xFFFF
    p[start[12]], p[(start[12] + 1) & 0xFFFF] = PAD_RET & 255, PAD_RET >> 8
    start[24] = eng.patch.syms['e_pad']
    start[15] = _r(R[15], 1)                     # the CALL's M1, as the original's
    d0 = debt_t(eng.page)
    owed = owed_steps(eng.page)
    if owed < 499:
        path, gone = 'pad n', 0
    elif owed >= 65536:
        path, gone = 'pad b', owed - 499 - CAP
    elif owed - 499 >= CAP:
        path, gone = 'pad x', owed - 499 - CAP
    else:
        path, gone = 'pad c', 0
    sim = _machine(p, start, eng.ns)
    k = eng.ns.speed = eng.ns.speed_in
    ok, tp = _runt(sim, lambda r: r[24] == PAD_RET and r[12] == sp, eng.ns, limit=2000000)
    if not ok:
        return [('pad hook did not return',)]
    tp += 17 / DIV[k]
    to /= DIV[k]
    rp = sim.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('pad: registers differ', diff[:6], [ro[i] for i in diff[:3]], [rp[i] for i in diff[:3]]))
    md = [a for a in p.ov if not sp - 64 <= a < sp]
    if md:
        f.append(('pad: game memory written', len(md)))
    if eng.ns.nr.get(0x56, 0) != 0:
        f.append(('pad: slot 6 left on the state page',))
        eng.ns.nr[0x56] = 0
    eng.gone += 21 * gone
    _speed(eng, 'pad', f)
    _time(eng, path, tp - to - 21 * gone, d0, f)
    return f


class _OMem:
    """The original's view for an event: ROM (Sinclair's, through get) never written, writes to an overlay."""

    def __init__(s, get):
        s.get, s.ov = get, {}

    def __getitem__(s, a):
        v = s.ov.get(a)
        return s.get(a) if v is None else v

    def __setitem__(s, a, v):
        if a >= 0x4000:
            s.ov[a] = v

    def __len__(s):
        return 65536


def dirty_list(get):
    out = []
    a = 38390
    while get(a) != 255 and a < 38390 + 200:
        out.append((get(a), get(a + 1)))
        a += 2
    return out


def block(e, d):
    """The blit's own geometry: -> [(line, col)] of a 3 x 16 block."""
    y = d
    if y < 8:
        y += ((~y) & 7) + 1
    c = e >> 3
    return y, c


def reconcile(eng, get):
    """Before a blit: a screen byte something else has written since (the same in both builds) no longer differs."""
    for a in [a for a, (pv, ov) in eng.scr.items() if get(a) != ov]:
        del eng.scr[a]


def apply_blit(eng, get, blocks):
    """After the original's blit (get = original memory): the patched screen = the clean copy in every dirty block."""
    for e, d in blocks:
        y, c = block(e, d)
        for r in range(16):
            yy = y + r
            if yy > 191:
                continue
            base = CLEAN + yy * 32 + c
            for j in range(3):
                if c + j > 31:
                    continue
                sa = _ula(yy, c + j)
                v, o = get(base + j), get(sa)
                if v != o:
                    eng.scr[sa] = (v, o)
                else:
                    eng.scr.pop(sa, None)


def explained(eng, get, figs, line, col, want, c):
    """A byte where sprites and the original differ: only two one-pass effects of the original's order are accepted, each by
    recomputing the byte exactly. (1) A mid-pass restore (38730, a tile changes) wipes figures already in that block from the
    compose buffer, so the original drops them for a pass; a sprite stays. (2) Scenery stamped into the clean copy after this
    pass's restore reaches the original's screen one pass later; the build shows it at once."""
    n = 0
    for e, d, k in eng.rest:
        c0 = e >> 3
        if d <= line < d + 16 and c0 <= col < c0 + 3:
            n = max(n, k)

    def over(i):
        f, x, y, mir = figs[i]
        out = None
        for r, j, o, w in eng.rows(f, x & 7, mir):
            if y + r == line and (x >> 3) + j == col:
                out = (o, w)
        return out

    def fold(v):
        for i in range(n, len(figs)):
            ow = over(i)
            if ow:
                v = (v & ~ow[0]) | (ow[1] & ow[0])
        return v
    off = line * 32 + col
    now = get(CLEAN + off)
    if n and any(over(i) for i in range(min(n, len(figs)))) and fold(now) == want:
        c['bytes where the original dropped a figure for a pass'] += 1
        return 'dropped'
    if eng.clean_prev is not None and eng.clean_prev[off] != now and fold(eng.clean_prev[off]) == want:
        c['bytes where the original showed old scenery for a pass'] += 1
        return 'stale'
    return None


def composite(eng, get, c, fail, figs=()):
    """What a player sees, bit by bit: sprites over the patched screen = the original's screen."""
    vis = eng.ns.visible()
    op = {}
    for f, x, y, mir in vis:
        col0, xs = x >> 3, x & 7
        for r, j, o, w in eng.rows(f, xs, mir):
            yy = y + r
            if not 8 <= yy < 192 or not 0 <= col0 + j <= 31:
                continue
            sa = _ula(yy, col0 + j)
            po, pw = op.get(sa, (0, 0))
            op[sa] = (po | o, (pw & ~o) | (w & o))
    keys = set(op) | set(eng.scr)
    bad = 0
    dropped = False
    for sa in keys:
        s = eng.scr.get(sa)
        p = s[0] if s else get(sa)
        o, w = op.get(sa, (0, 0))
        if (p & ~o) | (w & o) != get(sa):
            line = (sa & 0x1800) >> 5 | (sa & 0x700) >> 8 | (sa & 0xE0) >> 2
            how = explained(eng, get, figs, line, sa & 31, get(sa), c)
            if how == 'dropped':
                dropped = True
            elif how is None:
                bad += 1
    c['bytes compared'] += len(keys)
    c['figure pixels'] += sum(bin(o).count('1') for o, w in op.values())
    if dropped:
        c['passes where the original dropped a figure'] += 1
    if bad:
        c['composite bytes wrong'] += bad
        fail('composite: sprites over the patched screen differ from the original', (bad, vis[:4]))
    return vis


def post_event(eng, get, R, c, fail):
    """At 37972, the blit done in the original: run the commit from `post`; check the log became the sprites."""
    figs, eng.figs = eng.figs, []
    sp = R[12]
    ret_regs = list(R)
    start = list(R)
    start[24] = eng.patch.syms['post']
    start[12] = (sp - 2) & 0xFFFF
    start[15] = _r(R[15], 1)                     # e_cp's own CALL 38551 before the blit
    p = _PMem(get, eng.page, eng.psite, eng.rom, eng.scr, ns=eng.ns)
    p[(sp - 2) & 0xFFFF] = AFTER_BLIT & 255
    p[(sp - 1) & 0xFFFF] = AFTER_BLIT >> 8
    d0 = debt_t(eng.page)
    hid = max(0, eng.page[1] - len(figs))
    sim = _machine(p, start, eng.ns)
    k = eng.ns.speed = eng.ns.speed_in
    ok, tp = _runt(sim, lambda r: r[24] == AFTER_BLIT and r[12] == sp, eng.ns)
    if not ok:
        fail('commit did not return')
        return
    eng.tcost.append(tp)
    tf = []
    _speed(eng, 'commit', tf)
    _common(eng, 'commit', p, tf)
    est = sum(contention(d) for e, d in dirty_list(get))
    eng.cont += est
    _time(eng, 'commit %d %d %d' % (min(len(figs), NMAX), hid, len(dirty_list(get))), 17 / DIV[k] + tp + est, d0, tf)
    for k in tf:
        fail(k[0], k[1:])
    diff = [i for i in CMP if ret_regs[i] != sim.registers[i]]
    if diff:
        fail('commit: registers differ', (diff[:6],))
    md = [a for a in p.ov if not sp - 64 <= a < sp]
    if md:
        fail('commit: game memory written', (len(md), md[:3]))
    if p.romw:
        fail('commit: wrote ROM')
    if len(figs) > NMAX:
        fail('more figures in a pass than the log holds', (len(figs),))
        figs = figs[:NMAX]
    vis = composite(eng, get, c, fail, figs)
    eng.rest = []
    if vis != figs:
        fail('sprites differ from the plots', (figs[:3], vis[:3]))
    c['most sprites'] = max(c['most sprites'], len(vis))
    if eng.ns.bad:
        fail('port / nextreg outside the model', (eng.ns.bad[:3],))
        eng.ns.bad = []
    for f, x, y, m in figs:
        if f >= NPAT:
            fail('frame above the patterns', (f,))


def full_blit(eng, snapshot, R, c, fail, after):
    """Run the patched blit + commit in full from the state before the CALL, on a copy; registers must equal the
    original's at the return, the screen the model. snapshot: memory before; after: memory after (original)."""
    get = snapshot.__getitem__
    pg = bytearray(eng.page)
    ns = NextState(eng.pats)
    ns.attr = [list(a) for a in eng.ns.attr]
    ns.nr = dict(eng.ns.nr)
    start = list(R)
    start[24] = eng.patch.syms['e_cp']
    start[15] = _r(R[15], 1)                     # the CALL's own M1 (the replay's state is before it)
    sp = R[12]
    p = _PMem(get, pg, eng.psite, eng.rom, eng.scr, ns=ns)
    p[(sp - 2) & 0xFFFF] = AFTER_BLIT & 255
    p[(sp - 1) & 0xFFFF] = AFTER_BLIT >> 8
    start[12] = (sp - 2) & 0xFFFF
    sim = _machine(p, start, ns)
    if not _run(sim, lambda r: r[24] == AFTER_BLIT and r[12] == sp):
        fail('full blit did not return')
        return None
    return sim, p, pg, ns


# ---------------------------------------------------------------------------------------------
# RZX replay: the C simulator with hooks at the sites; patched code runs from each state
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None, full_every=25, clock=0):
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    st = {'eng': None, 'pending': None, 'kept': None}
    cnt = collections.Counter()
    states = []
    frames = collections.Counter()
    callers = collections.Counter()
    levels = collections.Counter()
    site_orig = {a + k: v for a, old, new in patch.sites for k, v in enumerate(old)}

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append(tuple(info))

    def report(kind, fl):
        for k in fl:
            fail('%s' % (k[0],), k[1:])

    def cb(pc, sim):
        R, mem = sim.registers, sim.memory
        get = lambda a: mem[a & 0xFFFF]
        if st['eng'] is None:
            st['eng'] = Engine(patch, get)
            st['eng'].ns.speed_in = clock            # the game's clock (NR 7): 0 = 3.5 MHz as recorded
        eng = st['eng']
        cnt[pc] += 1
        if pc == E_PLOT:
            c['plots'] += 1
            if mem[PLOTD] == 115:
                c['figure plots'] += 1
                frames[R[0]] += 1
                callers[(mem[R[12]] | mem[(R[12] + 1) & 0xFFFF] << 8) - 3] += 1
            else:
                c['scenery plots'] += 1
            if collect and c['collected plot'] < collect and mem[PLOTD] == 115:
                c['collected plot'] += 1
                states.append(('plot', list(R), bytes(mem[a] for a in range(65536))))
            report('plot', plot_event(eng, get, list(R)))
        elif pc == CALL_BLIT:
            c['blits'] += 1
            levels[mem[41872]] += 1
            reconcile(eng, get)
            blocks = dirty_list(get)
            full = c['blits'] <= 20 or c['blits'] % full_every == 0
            st['pending'] = (blocks, list(R), bytes(mem[a] for a in range(65536)) if full else None)
            if collect and c['collected blit'] < collect:
                c['collected blit'] += 1
                states.append(('blit', list(R), bytes(mem[a] for a in range(65536))))
            for a, v in site_orig.items():
                if mem[a] != v:
                    fail('game wrote a patch site', (a,))
        elif pc == AFTER_BLIT and st['pending']:
            blocks, R0, snap = st['pending']
            st['pending'] = None
            scr0 = dict(eng.scr)
            apply_blit(eng, get, blocks)
            if snap is not None:
                c['full blits'] += 1
                res = None
                eng_scr = eng.scr
                eng.scr = scr0
                res = full_blit(eng, snap, R0, c, fail, get)
                eng.scr = eng_scr
                if res:
                    s2, p, pg, ns2 = res
                    diff = [i for i in BLIT_CMP if R[i] != s2.registers[i]]
                    if R[17] != s2.registers[17]:
                        c["full blits with F' differing (explained)"] += 1
                    if diff:
                        fail('full blit: registers differ', (diff[:6], [R[i] for i in diff[:3]], [s2.registers[i] for i in diff[:3]]))
                    sp = R[12]
                    md = [a for a, v in p.ov.items() if not (0x4000 <= a < 0x5800) and not sp - 64 <= a < sp and v != mem[a]]
                    if md:
                        fail('full blit: game memory differs', (len(md), md[:4]))
                    for a, v in p.ov.items():
                        if 0x4000 <= a < 0x5800:
                            s = eng_scr.get(a)
                            if (s[0] if s else mem[a]) != v:
                                fail('full blit: screen differs from the model', (a, v))
                                break
            post_event(eng, get, list(R), c, fail)
            eng.clean_prev = bytes(mem[CLEAN:CLEAN + 6144])
            if cnt[AFTER_BLIT] != cnt[CALL_BLIT]:
                fail('blit return count')
        elif pc == RESTORE:
            if eng.figs:
                eng.rest.append((R[5], R[4], len(eng.figs)))
                c['mid-pass restores after a figure'] += 1
        elif pc == CLS:
            c['clears'] += 1
            if collect and c['collected cls'] < collect:
                c['collected cls'] += 1
                states.append(('cls', list(R), bytes(mem[a] for a in range(65536))))
            report('cls', cls_event(eng, get, list(R)))
        elif pc == PAD:
            c['pads'] += 1
            if collect and c['collected pad'] < collect:
                c['collected pad'] += 1
                states.append(('pad', list(R), bytes(mem[a] for a in range(65536)), bytes(eng.page)))
            report('pad', pad_event(eng, get, list(R)))
        elif pc == PAD_END:
            if c['pads at the last pass'] != c['pads']:
                c['padded passes'] += 1
                c['padded passes ending with no debt'] += owed_steps(eng.page) < 499
            c['pads at the last pass'] = c['pads']

    pcs = {E_PLOT, CALL_BLIT, AFTER_BLIT, CLS, RESTORE, PAD, PAD_END} | set(INTERIORS) | set(SEQUELS)
    # the two source operands are data; everything else that could bypass a site:
    n, err = RZ.trace(rzx_path, pcs, cb, stop=stop)
    if err:
        c['recording desynced: %s!' % err[:80]] += 1
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    for a in SEQUELS:
        if cnt[a] != cnt[E_PLOT]:
            c['%d reached other than from 38093 (%d / %d)!' % (a, cnt[a], cnt[E_PLOT])] += 1
    c['frames'] = n
    eng = st['eng']
    if eng and eng.tcost:
        c['commit T max'] = max(eng.tcost)
        c['commit T mean'] = sum(eng.tcost) // len(eng.tcost)
    timing = {}
    if eng:
        tt = collections.defaultdict(list)
        for kind, extra, d in eng.time:
            tt[kind].append(extra)
        c['time over the original, hooks (T)'] = sum(x for k, v in tt.items() if not k.startswith('pad') for x in v)
        c['time of the pad hooks (T, repaid included)'] = sum(x for k, v in tt.items() if k.startswith('pad') for x in v)
        c['debt let go over CAP (T)'] = eng.gone
        c['debt left (T)'] = round(debt_t(eng.page))
        c['blit contention estimate (T)'] = round(eng.cont)
        timing = {k: (len(v), min(v), max(v)) for k, v in tt.items()}
    extra = {'frames': frames, 'callers': callers, 'levels': levels}
    extra['time'] = timing
    if collect:
        return c, dict(ex), states, extra
    return c, dict(ex), extra


# ---------------------------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------------------------

def unit_tests(patch, states, neg=None):
    """From captured states: every frame, position edges, a full log, a scenery plot not logged, a clear; the setup."""
    c = collections.Counter()
    plots = [s for s in states if s[0] == 'plot']
    blits = [s for s in states if s[0] == 'blit']
    if not plots or not blits:
        c['no captured state!'] += 1
        return c
    _, R, mem = plots[0]
    get = mem.__getitem__
    eng = Engine(patch, get)

    def frame(figs, base=None):
        e = base or eng
        e.figs = []
        for f in e.ns.attr:
            f[3] = 0
        e.page = bytearray(patch.state)
        e.ns.bad = []
        fl = []
        for a, x, y in figs:
            r = list(R)
            r[0], r[5], r[4] = a, x, y
            fl += plot_event(e, get, r)
        return fl

    def commit(e=None):
        e = e or eng
        cc = collections.Counter()
        out = []
        r = list(blits[0][1])
        r[24] = AFTER_BLIT
        post_event(e, get, r, cc, lambda k, i=(): out.append((k, i)))
        return [o for o in out if not o[0].startswith('composite')]
    # every frame at the position edges: attributes as the model wants
    for a in range(NPAT):
        fl = frame([(a, 0, 8)]) + commit()
        c['frames ok' if not fl else 'frames FAIL!'] += 1
    for x, y in ((0, 0), (7, 7), (8, 8), (223, 100), (224, 100), (238, 176), (239, 176), (255, 191)):
        fl = frame([(3, x, y)]) + commit()
        got = eng.ns.visible()
        ok = not fl and got == [(3, x, y, 0)]
        c['edges ok' if ok else 'edges FAIL!'] += 1
    # overlap: order kept
    figs = [(a, 40 + a, 60) for a in range(15)]
    fl = frame(figs) + commit()
    c['plot order ok' if not fl and eng.ns.visible() == [f + (0,) for f in figs] else 'plot order FAIL!'] += 1
    # the player's mirrored frames, flag on and off, and a frame outside them
    m2 = bytearray(mem)
    for flag in (0, 1):
        m2[FLIP] = flag
        e3 = Engine(patch, get)
        fl = plot_event(e3, m2.__getitem__, _with(R, 50, 80, 80)) + plot_event(e3, m2.__getitem__, _with(R, 47, 120, 80))
        out = []
        r = list(blits[0][1])
        r[24] = AFTER_BLIT
        post_event(e3, m2.__getitem__, r, collections.Counter(), lambda k, i=(): out.append(k))
        ok = not fl and e3.ns.visible() == [(50, 80, 80, flag), (47, 120, 80, 0)]
        c['mirror flag ok' if ok else 'mirror flag FAIL!'] += 1
    # fewer next time: the rest hidden
    fl = frame([(1, 10, 10)]) + commit()
    c['rest hidden ok' if not fl and len(eng.ns.visible()) == 1 else 'rest hidden FAIL!'] += 1
    # a full log: the first NMAX shown, none lost silently
    figs = [(1, 8, 8)] * (NMAX + 3)
    fl = frame(figs)
    e2 = commit()
    c['log full: limit reported ok' if any('log holds' in o[0] for o in e2) else 'log full FAIL!'] += 1
    # scenery plot is not logged
    m2 = bytearray(mem)
    m2[PLOTD] = 91
    eng2 = Engine(patch, get)
    fl = plot_event(eng2, m2.__getitem__, list(R))
    c['scenery not logged ok' if not fl and not eng2.figs and eng2.page[0] == 0
      else 'scenery not logged FAIL!'] += 1
    # a clear hides everything and empties the log
    frame([(1, 8, 8), (2, 30, 30)]) + commit()
    frame([(1, 8, 8)])
    fl = cls_event(eng, get, list(R))
    c['clear ok' if not fl and not eng.ns.visible() and eng.page[0] == 0 else 'clear FAIL!'] += 1
    # the pad: every debt from none to over 499 steps, and the every-site matrix
    pads = [s_ for s_ in states if s_[0] == 'pad']
    if pads:
        _, Rp, memp, pg = pads[0]
        for steps in (0, 1, 2, 100, 498, 499, 500, 1000, 499 + CAP - 1, 499 + CAP, 499 + CAP + 1, 65000, 65535, 65536,
                      70000, 0xFFFFF0):
            e4 = Engine(patch, memp.__getitem__)
            e4.page[DEBT:DEBT + 4] = (77 | steps << 8).to_bytes(4, 'little')
            fl = pad_event(e4, memp.__getitem__, list(Rp))
            left = e4.page[DEBT + 1] | e4.page[DEBT + 2] << 8
            ok = not fl and left == max(0, steps - 499) + (e4.page[DEBT + 1] | e4.page[DEBT + 2] << 8) - left
            c['pad cases ok' if not fl else 'pad cases FAIL!'] += 1
    else:
        c['no pad state captured!'] += 1
    m, _ = clock_matrix(patch, states)
    for k, v in m.items():
        c['clock matrix %s' % k] += v
    # the setup: uploads the patterns, palette, clip, hides, sprites on
    fl = setup_check(patch, get)
    c['setup ok' if not fl else 'setup FAIL!'] += 1
    if fl:
        c['  setup %s' % str(fl[:3])[:150]] += 1
    return c


def _with(R, a, x, y):
    r = list(R)
    r[0], r[5], r[4] = a, x, y
    return r


def setup_check(patch, get):
    """Run the stub's setup on a small model: pages 22, 23 at slot 7, port uploads."""
    from .simpool import machine
    from skoolkit.simulator import R2
    pats = patterns(get, patch.colours or {})
    bank = pats + bytes(16384 - len(pats))
    code = patch.stub_extra
    nr = {'nr': {}, 'pat': bytearray(), 'pal': [], 'clip': [], 'hide': set(), 'sel': 0}

    class M:
        def __getitem__(s, a):
            if 0xD000 <= a < 0xD000 + len(code):
                return code[a - 0xD000]
            if a >= 0xE000:
                pg = nr['nr'].get(0x57, 21)
                if pg in (22, 23):
                    return bank[(pg - 22) * 8192 + a - 0xE000]
                return 0
            return 0

        def __setitem__(s, a, v):
            pass

        def __len__(s):
            return 65536
    mem = M()
    sim = machine(_rw(), mem, [0] * 30, 's')
    R, ed = sim.registers, sim.after_ED
    R[24], R[12] = 0xD000, 0x8000

    def reg(r, v):
        nr['nr'][r] = v
        if r == 0x41:
            nr['pal'].append(v)
        elif r == 0x19:
            nr['clip'].append(v)
        elif r == 0x34:
            nr['sel'] = v
        elif r == 0x38 and v == 0:
            nr['hide'].add(nr['sel'])

    def nn():
        p = R[24]
        reg(mem[p + 2], mem[p + 3])
        R[15] = R2[R[15]]; R[24] = p + 4

    def na():
        p = R[24]
        reg(mem[p + 2], R[0])
        R[15] = R2[R[15]]; R[24] = p + 3
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs_, port):
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            if port & 255 == 0x5B:
                nr['pat'].append(value)
            elif port != 0x303B:
                nr['clip'].append(('port', port))
    sim.set_tracer(Tr())
    ret = 0
    ops = sim.opcodes
    n = 0
    while R[24] != 0 and n < 2000000:
        ops[mem[R[24]]]()
        n += 1
    f = []
    if R[24] != 0:
        f.append('setup did not return')
    if bytes(nr['pat'][:len(pats)]) != pats:
        f.append(('patterns', len(nr['pat'])))
    if nr['pal'] != SPECCY:
        f.append(('palette', nr['pal']))
    if nr['clip'] != [0, 255, 8, 191]:
        f.append(('clip', nr['clip']))
    if len(nr['hide']) != 128:
        f.append(('hide', len(nr['hide'])))
    if nr['nr'].get(0x15) != 1 or nr['nr'].get(0x4B) != 0 or nr['nr'].get(0x57) != 21:
        f.append(('registers', nr['nr']))
    return f


# ---------------------------------------------------------------------------------------------
# Negative controls: broken builds that must be detected on the real recording
# ---------------------------------------------------------------------------------------------

def _code_patch(patch, sym, old, new, n=0):
    p = SolomonsKeyPatch(patch.prof, colours=patch.colours)
    code = bytearray(p.code)
    i = p.syms[sym] - ROM_ORG
    j = code.find(bytes.fromhex(old), i)
    for _ in range(n):
        j = code.find(bytes.fromhex(old), j + 1)
    if j < 0 or j > i + 200:
        raise ValueError('negative patch: %s not found near %s' % (old, sym))
    code[j:j + len(bytes.fromhex(old))] = bytes.fromhex(new)
    return SolomonsKeyPatch(patch.prof, bytes(code), colours=patch.colours)


def negative_patches(patch):
    """name -> broken patch. Each is a real fault a build could have."""
    out = {}
    # plot hook loses DE's y: logs E twice
    out['plot logs x as y'] = _code_patch(patch, 'e_plot', '2c72', '2c73')
    # plot hook changes a register: C clobbered before the pushes
    out['plot hook clobbers HL'] = _code_patch(patch, 'e_plot', 'e1ed4f', '00ed4f')
    # commit forgets the x carry: the sprite's bit 8
    out['commit loses x bit 8'] = _code_patch(patch, 'post', '3e008f', '3e00af')
    # commit sets the wrong half of the pattern (N6 dropped)
    out['commit drops N6'] = _code_patch(patch, 'post', 'e6010f0f', 'e6000f0f')
    # the rest of the sprites stay up
    out['old sprites stay'] = _code_patch(patch, 'hide', 'ed9238', '000000')
    # the player's mirror flag ignored: the AND (HL) with the table's bit
    out['mirror flag ignored'] = _code_patch(patch, 'e_plot', 'a677', '0077')
    # R one off after a plot (the delta D_PLOT + 1)
    q = SolomonsKeyPatch(patch.prof, colours=patch.colours)
    code = bytearray(q.code)
    k = code.index(bytes.fromhex('67c6'), q.syms['e_plot'] - ROM_ORG)
    code[k + 2] = (code[k + 2] + 1) & 0x7F
    out['R one off after a plot'] = SolomonsKeyPatch(patch.prof, bytes(code), colours=patch.colours)
    # the plot hook adds nothing to the debt (its CALL dadd gone)
    out['plot time not in the debt'] = _code_patch(patch, 'e_plot', 'cd' + '%02x%02x' % (patch.syms['dadd'] & 255, patch.syms['dadd'] >> 8),
                                                   '000000')
    # the pad's delay length wrong: C one less
    out['pad delay length wrong'] = _code_patch(patch, 'e_pad', '4ded91', '0ded91')
    # the pad leaves F as it found it, not as the LDIR does
    out['pad flags wrong'] = _code_patch(patch, 'e_pad', 'e6c1', 'e6ff')
    # a forced 3.5 MHz exit, with slot 7 left mapped: the plot's unmap becomes NEXTREG 7,0
    out['forced 3.5 MHz exit'] = _code_patch(patch, 'e_plot', '3a09c0', '3affc0')   # the exit's latch: a zero byte
    out['forced 3.5 MHz exit'].clock = 1
    # the blit still shows the compose buffer: figures on the ULA too
    n = SolomonsKeyPatch(patch.prof, colours=patch.colours, drop_sites=(38584, 38656))
    out['blit source not changed'] = n
    return out


def negative_real(patch, rzx_path, stop=4000):
    """Each broken build on a real recording: -> {name: failures}."""
    res = {}
    for name, q in negative_patches(patch).items():
        v = verify(q, rzx_path, stop=stop, clock=getattr(q, 'clock', 0))
        c = v[0]
        res[name] = sum(n for k, n in c.items() if k.endswith('!'))
    return res


# ---------------------------------------------------------------------------------------------
# The tape's loading screen (TOSEC .tap block 5, a standard SCREEN$), held before the game: lunar_jetman's stub
# ---------------------------------------------------------------------------------------------

LOAD_BANK = 34


def tape_screen(tap):
    """The 6,912-byte SCREEN$ block of the TOSEC .tap (the data block after the header named 'screen$')."""
    d = open(tap, 'rb').read()
    i, blocks = 0, []
    while i < len(d):
        n = d[i] | d[i + 1] << 8
        blocks.append(d[i + 2:i + 2 + n])
        i += 2 + n
    for k, b in enumerate(blocks[:-1]):
        if b[0] == 0 and b[1] == 3 and b[2:12] == b'screen$   ' and len(blocks[k + 1]) == 6914:
            return blocks[k + 1][1:-1]
    raise ValueError('no SCREEN$ block in %s' % tap)


def loading_nex(nex, scr):
    """A sprite build with the tape's loading screen: bank 5's screen area holds the picture, bank 34 (asm loading,
    as lunar_jetman's: the hold, then bank 5's own screen put back) is the entry bank."""
    h = load_profile()['hooks']
    o = bytes(nex)
    if len(scr) != 6912:
        raise ValueError('loading screen: %d bytes, want 6912' % len(scr))
    hd = bytearray(o[:512])
    if hd[18 + LOAD_BANK] or hd[139] != 10:
        raise ValueError("not a solomons_key sprite build: bank 34 in use or entry bank %d" % hd[139])
    code, end = bytes.fromhex(h['loading']), bytes.fromhex(h['loadend'])
    stub = code + o[512:512 + 6912]
    stub += bytes(0x4000 - len(end) - len(stub)) + end
    hd[9] += 1
    hd[18 + LOAD_BANK] = 1
    hd[139] = LOAD_BANK
    off, parts = 512, []
    for k in [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112)):     # bank order in the file: 34 among the others
        if k == LOAD_BANK:
            parts.append(stub)
        elif o[18 + k]:
            parts.append(o[off:off + 16384])
            off += 16384
    body = b''.join(parts)
    return bytes(hd) + scr + body[6912:] + o[off:]


# ---------------------------------------------------------------------------------------------
# Colour sheets and recolour
# ---------------------------------------------------------------------------------------------

NOTE = ("Solomon's Key colour map (docs/COLOURS.md): key = graphics byte (hex address; check = its value); 8 nibbles, 0 = default "
        '(bright white ink, black solid body, transparent elsewhere); 1-15 the fixed colours; a paper bit with a nibble is drawn opaque; '
        'optional 4th = transparent mask')
RECOLOUR = {'game': 'solomons_key', 'output': 'sprites', 'colours': 'docs/profiles/solomons_key_colours.json', 'clear': True,
            'note': NOTE}
PALETTE = SPECCY


def figure_frames(z80=None):
    return load_profile().get('figure_frames', list(range(NPAT)))


def colour_identity(peek):
    return {'schema': 1, 'game': 'solomons_key', 'engine': 'solomons_key', 'keys': 'solomons-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': hashlib.md5(bytes(peek(a) for a in range(GFX, GFX + 64 * NPAT))).hexdigest(), 'geometry': None}


def recolour(nex, cmap):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this engine's build."""
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    if not {5, 2, 0, PAT_BANK, ALT_BANK, STATE_BANK} <= set(have):
        raise ValueError("not a Solomon's Key sprite build")
    peek = nex_peek(nex)
    p = SolomonsKeyPatch(colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    if have[ALT_BANK] != p.page + bytes(8192):
        raise ValueError("alt ROM image / hook code differs from this version's (rebuild with nexclash.py auto)")
    pats = patterns(peek, cmap)
    out, changed = splice(nex, {PAT_BANK: pats + bytes(16384 - len(pats))})
    used = [k for k in cmap if cmap[k][0] == peek(int(k, 16))]
    return out, {'banks changed': changed, 'map entries used': len(used), 'map entries ignored': len(cmap) - len(used)}


def frame_part(peek, a):
    px, ent = [], {}
    for r, (m, g) in enumerate(frame_rows(peek, a)):
        for k in range(16):
            key = gkey(a, r, k >> 3)
            ent[key] = [peek(int(key, 16)), 'g']
            ink = g >> (15 - k) & 1
            solid = not (m >> (15 - k) & 1)
            code = 1 if ink else (2 if solid else 0)
            px.append((k, r, key, k & 7, code, 1 if ink else (2 if solid else 0)))
    return {'id': 'f%d' % a, 'size': 1, 'w': 16, 'h': 16, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent, 'dx': 0, 'dy': 0,
            'dmir': 0, 'vmir': 0, 'group': 'figures'}


def sheets(z80, out_dir, prefix='solomons_key', colours=None, say=print):
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    comps = [{'count': 1, 'group': 'figures', 'parts': [frame_part(get, a)]} for a in figure_frames()]
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb, colours=cmap,
                  paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb, colours=cmap,
                  paint_clear=True, identity=ident)
    say('Sheets    : %d frames; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


# ---------------------------------------------------------------------------------------------
# The whole run
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say("Engine    : solomons_key (masked plotter 38093 into the compose buffer -> sprites; blit shows the clean copy)")
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                        'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = SolomonsKeyPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                         'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        c, ex, st, extra = verify(patch, r, stop=getattr(a, 'quick', None), collect=2)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, blits %d (%d full), plots %d figure %d scenery %d, clears %d, %d figure pixels, %d bytes '
            'compared, most sprites %d, frames %d -> %s' % (
                os.path.basename(r), c['frames'], c['blits'], c['full blits'], c['plots'], c['figure plots'], c['scenery plots'],
                c['clears'], c['figure pixels'], c['bytes compared'], c['most sprites'], len(extra['frames']),
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            %d passes, %d bytes: the original dropped a figure for a pass (mid-pass restore), the sprite stays; %d bytes: '
            'new scenery shown a pass sooner' % (c['passes where the original dropped a figure'],
                                                 c['bytes where the original dropped a figure for a pass'],
                                                 c['bytes where the original showed old scenery for a pass']))
        say('            callers %s' % ', '.join('%d:%d' % kv for kv in sorted(extra['callers'].items())))
        say('            levels %s' % sorted(extra['levels'].items()))
        say('            frames %s' % sorted(extra['frames']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:240]))
        if c['commit T max']:
            say('Speed     : commit %d T mean, %d T max, at 3.5 MHz (a pass is about 175,000 T)' % (c['commit T mean'], c['commit T max']))
        say('Pace      : hooks %d T over the original; pads %d T against the original (%d pads); %d of %d padded passes end with '
            'no debt; %d T left (paths %s)' % (c['time over the original, hooks (T)'], c['time of the pad hooks (T, repaid included)'], c['pads'],
                            c['padded passes ending with no debt'], c['padded passes'], c['debt left (T)'], extra.get('time')))
    if any(x[0] == 'blit' for x in states):
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


def clock_matrix(patch, states):
    """The every-site matrix (hooklib.every_site; card patch.restore-speed): each captured plot, clear and pad entry run with
    NR 7 = 0-3 from the same state: no hook writes NR 7, so each must exit at its clock, with the same results."""
    from .hooklib import every_site
    cases = [s_ for s_ in states if s_[0] in ('plot', 'cls', 'pad')]

    def run(n, k):
        st = cases[n]
        kind, R, mem = st[:3]
        get = mem.__getitem__
        eng = Engine(patch, get)
        if kind == 'pad':
            eng.page[:] = st[3]
        eng.ns.speed_in = k
        fl = {'plot': plot_event, 'cls': cls_event, 'pad': pad_event}[kind](eng, get, list(R))
        pg = bytearray(eng.page)
        pg[9] = 0                                    # vspd: the latch holds the incoming clock
        return eng.ns.speed, (tuple(map(str, fl)), bytes(pg), tuple(map(tuple, eng.ns.attr)), tuple(eng.ns.bad))
    return every_site(range(len(cases)), run)
