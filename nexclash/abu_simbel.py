"""Abu Simbel Profanation (Dinamic, 1985, 48K) engine 'abu_simbel'. Additive module: reachable only
through is_abu_simbel(). Facts and decisions: games/abu_simbel.md; hooks: asm/abu_simbel_hooks.asm.

Compiled BASIC with one figure plotter, 0xDD78, called for the player (0xAD1D) and the three enemies of
a room (0xB465). v1.0: the hook builds the figure's sprite pattern from the game's graphic, the colour map
and the plot's ink, then calls the plotter whole and unchanged at 28 MHz with page 31 in slot 2, so its
screen and attribute writes land in a page that is never shown; a pace window (x K_PLOT) gives the plot
the original's time. Logic reads attributes only, and only compares them with values >= 0x40; figures
paint cells below 0x40 with inks below 0x40, so leaving those writes out cannot change a decision (the
verify checks each part of that at run time).
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
MAPPAGE, STPAGE, GAMEPAGE7, GAMEPAGE5, SCRPAGE = 28, 31, 1, 5, 10
COLOUR_BANKS = (14, 15)
PAT_OFF = 0x1D10            # the pattern builder's code in page 31 (asm O_PAT)
ST_OFF = 0x1B00             # page 31: hook state from here up; the plotter's scratch screen below
TAIL_ADDR = 0x6000          # zero in the snapshot, untouched in every recording (work/scan logs)
PLOTTER = 0xDD78
PLOT_EI = 0xDE98            # the plotter's EI, a NOP in the build (the hook enables interrupts at its end)
GFX_LO, GFX_LEN = 0xC800, 0x1440
SPR_PLAY = 3
N_SPR = 4
SITE_PL, SITE_EN, SITE_CLS, SITE_CL2 = 0xAD1D, 0xB465, 0xBD36, 0xA361
ATTR_WRITE = 0xDED3
SITE_KIND = {SITE_PL: 'pl', SITE_EN: 'en', SITE_CLS: 'cls', SITE_CL2: 'cls'}
READ_DONE = 0xFEAB          # the collision helper has its three attributes in HL, C
# (address, original, symbol or literal new bytes)
CALLS = {SITE_PL: ('cd78dd', 'e_pl'), SITE_EN: ('cd78dd', 'e_en'), SITE_CLS: ('cd75e1', 'e_cls'),
         SITE_CL2: ('cd6b0d', 'e_cl2')}
NOPS = {PLOT_EI: ('fb', '00')}
INTERIORS = (0xAD1E, 0xAD1F, 0xB466, 0xB467, 0xBD37, 0xBD38, 0xA362, 0xA363)
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
from .hooklib import CMP_R as CMP   # every register, R included; not T, PC (checked by the stop), MEMPTR
FE_COMPARE_LIMIT = 0x40     # every compare of a stored attribute is against a value >= this (0xAFDC-0xB095, 0xFEB8)
K_PLOT = 104                # asm K_PLOT: the model's 28 MHz factor is K_PLOT / 16
FRAME_T, LINE_T, LINES = 69888, 224, 312

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'abu_simbel_colours.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'abu_simbel.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_abu_simbel(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def colour_table(cmap, get=None):
    """The map as the hook reads it: 4 bytes per graphics byte, 2 pixels a byte, bit 7's pixel in the top nibble.
    -> (table, entries used, entries refused because the check byte differs from the game's)."""
    t = bytearray(GFX_LEN * 4)
    used = bad = 0
    for key, e in (cmap or {}).items():
        a = int(key, 16)
        if not 0 <= a - GFX_LO < GFX_LEN:
            bad += 1
            continue
        if get is not None and get(a) != e[0]:
            bad += 1
            continue
        nib = e[2]
        for i in range(4):
            t[(a - GFX_LO) * 4 + i] = (nib[2 * i] & 15) << 4 | nib[2 * i + 1] & 15
        used += 1
    return bytes(t), used, bad


def colour_banks(table, pat=b''):
    """Banks 14 and 15: pages 28-30 the map, page 31 the hook's state (zero) and, at PAT_OFF, the pattern
    builder's code (the profile's hooks.pat)."""
    d = bytearray(bytes(table) + bytes(16384 * 2 - len(table)))
    o = 16384 + 8192 + PAT_OFF
    if any(d[16384 + 8192:]):
        raise ValueError('colour table runs into page 31')
    d[o:o + len(pat)] = pat
    return {14: bytes(d[:16384]), 15: bytes(d[16384:])}


def gfx_md5(get):
    return hashlib.md5(bytes(get(a) for a in range(GFX_LO, GFX_LO + GFX_LEN))).hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': 'abu_simbel', 'engine': 'abu_simbel', 'keys': 'as-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': gfx_md5(peek), 'geometry': None}


class PlainPatch:
    """The plain .nex: no hooks; the game uses the printer buffer, so the tail goes where nothing runs."""
    name = 'Abu Simbel Profanation plain conversion'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    extra_banks = {}
    uses_printer_buffer = True
    keep_printer_buffer = True
    tail_addr = TAIL_ADDR
    sites = []

    def apply(self, snap):
        pass


class AbuPatch:
    name = 'Abu Simbel Profanation figures -> hardware sprites (altrom, v1.0)'

    def __init__(self, prof=None, rom_code=None, colours=None, pat_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.pat_code = pat_code if pat_code is not None else bytes.fromhex(h['pat'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.keep_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        if PAT_OFF + len(self.pat_code) > 0x2000:
            raise ValueError('pattern builder too long for page 31')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.sites = []
        for a, (old, sym) in CALLS.items():
            self.sites.append((a, bytes.fromhex(old), b'\xCD' + self.syms[sym].to_bytes(2, 'little')))
        for a, (old, new) in NOPS.items():
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.colours = load_colours() if colours is None else colours
        self.table = bytes(GFX_LEN * 4)
        self.cinfo = {}

    def prepare(self, get):
        self.table, used, bad = colour_table(self.colours, get)
        self.cinfo = {'colour entries used': used, 'colour entries refused': bad}
        self.extra_banks = dict(colour_banks(self.table, self.pat_code))
        self.extra_banks[12] = self.page + bytes(8192)

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Abu Simbel patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + 128]):
            raise ValueError('tail site not empty in this snapshot')
        self.prepare(lambda a: ram[a - 0x4000])
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


# ---------------------------------------------------------------------------------------------
# Next-side state, original / patched overlays, one event
# ---------------------------------------------------------------------------------------------

class NextState:
    """The Next as the hook sees it: NextRegs (MMU slots 2, 5, 7, NR 7), sprite pattern / attribute ports,
    NextReg reads through 0x243B / 0x253B, and the video line from real time (hooklib.NextModel's model:
    time runs at the current clock, 28 MHz = K_PLOT / 16 times 3.5 MHz, the factor the asm's K assumes).
    Pages 28-31 persist across events (the hook's state, the pace limiter's debt)."""

    def __init__(self, patch, speed=0):
        self.nr = {0x57: GAMEPAGE7, 0x55: GAMEPAGE5, 0x52: SCRPAGE, 0x07: speed & 3}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_at = 0
        self.pages = {}
        b = colour_banks(patch.table, patch.pat_code)
        for k, bank in enumerate((14, 15)):
            self.pages[28 + 2 * k] = bytearray(b[bank][:8192])
            self.pages[29 + 2 * k] = bytearray(b[bank][8192:])
        self.events = []
        self.bad = []
        self.sel = 0
        self.fast = K_PLOT / 16.0
        self.sim = None
        self.real = 0.0
        self.t_last = 0

    # time
    def start(self, sim, t_frame):
        """A new event: the simulator, and the real time it starts at (T into the frame, from the recording)."""
        self.sim = sim
        self.real, self.t_last = float(t_frame % FRAME_T), sim.registers[25]

    def _mult(self):
        sp = self.nr[0x07] & 3
        return self.fast if sp == 3 else (1.0, 2.0, 4.0)[sp]

    def now(self):
        if self.sim is None:
            return self.real
        return self.real + (self.sim.registers[25] - self.t_last) / self._mult()

    def line(self):
        return int(self.now() // LINE_T) % LINES

    def nextreg(self, reg, val):
        if reg == 0x07 and self.sim is not None:
            self.real, self.t_last = self.now(), self.sim.registers[25]
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append((reg, val))

    def read_nr(self):
        if self.sel == 0x07:
            sp = self.nr[0x07] & 3
            return sp << 4 | sp
        if self.sel == 0x1E:
            return self.line() >> 8 & 1
        if self.sel == 0x1F:
            return self.line() & 255
        self.bad.append(('NextReg read', self.sel))
        return 0

    def out(self, port, val):
        if port & 0xFF == 0x5B:
            self.pat[self.pat_at & 0x3FFF] = val
            self.pat_at += 1
        elif port == 0x303B:
            self.pat_at = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port == 0x243B:
            self.sel = val
        else:
            self.bad.append(port)

    def image(self, s):
        """Sprite s -> {(x, y): nibble} of its non-transparent pixels, ULA coordinates."""
        a0, a1, a2, a3, a4 = self.attr[s]
        if not a3 & 0x80:
            return {}
        x = a0 + (a2 & 1) * 256 - 32
        y = a1 + (a4 & 1) * 256 - 32
        base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
        out = {}
        for j in range(16):
            for k in range(16):
                b = self.pat[base + j * 8 + k // 2]
                v = (b >> 4) if k % 2 == 0 else (b & 15)
                if v:
                    out[(x + k, y + j)] = v
        return out


class _Tr:
    def __init__(self, ns):
        self.ns = ns

    def read_port(self, regs, port):
        if port == 0x253B:
            return self.ns.read_nr()
        self.ns.bad.append(('in', port))
        return 0xFF

    def write_port(self, regs, port, value, *x):
        self.ns.out(port, value)


def _overlays(patch, get, alt, ns):
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return get(a) if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __init__(s):
            O.__init__(s)
            s.romw = 0

        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if a >= 0xE000:
                pg = ns.nr[0x57]
                if pg != GAMEPAGE7:
                    return ns.pages[pg][a - 0xE000]
            elif 0xA000 <= a < 0xC000:
                pg = ns.nr[0x55]
                if pg != GAMEPAGE5:
                    return ns.pages[pg][a - 0xA000]
            elif a < 0x6000:
                pg = ns.nr[0x52]
                if pg != SCRPAGE:
                    return ns.pages[pg][a - 0x4000]
            v = s.ov.get(a)
            if v is not None:
                return v
            v = psite.get(a)
            return get(a) if v is None else v

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw += 1
            elif a >= 0xE000 and ns.nr[0x57] != GAMEPAGE7:
                ns.pages[ns.nr[0x57]][a - 0xE000] = v
            elif 0xA000 <= a < 0xC000 and ns.nr[0x55] != GAMEPAGE5:
                s.romw += 1
            elif a < 0x6000 and ns.nr[0x52] != SCRPAGE:
                ns.pages[ns.nr[0x52]][a - 0x4000] = v
            else:
                s.ov[a] = v
    return O, P


def _machine(Sim, mem, regs, ns, slot, z80n=True):
    from .simpool import machine
    from . import z80n as Z
    sim = machine(Sim, mem, regs, slot)
    if z80n:
        Z.install(sim, ns.nextreg, strict=False)
    sim.set_tracer(_Tr(ns))
    return sim


def _run(sim, stop, limit=1500000, iff_ok=None):
    """Run to stop(R). iff_ok: the PCs at which interrupts may be on (the hook's entry, its last RET, the return
    point); anywhere else with IFF1 set counts in sim.iff_on (interrupts must stay off through the hook)."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    sim.iff_on = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if iff_ok is not None and R[26] and R[24] not in iff_ok:
            sim.iff_on += 1
        if n > limit:
            return False
    return True


def _pixels(ov):
    """Ink pixels in the final value of every screen byte an overlay wrote."""
    out = set()
    for a, v in ov.items():
        if 0x4000 <= a < 0x5800:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                if (v >> (7 - k)) & 1:
                    out.add(((a & 31) * 8 + k, y))
    return out


def hidden_cell(get, xx, yy):
    """The game's depth: a BRIGHT cell keeps its attribute, so with ink = paper a figure there cannot be seen."""
    a = get(0x5800 + 32 * (yy >> 3) + (xx >> 3))
    return bool(a & 0x40) and a & 7 == a >> 3 & 7


def expected_nibbles(get, table, g, x, y, ink):
    """What the sprite must show from the game's graphic and the colour table (paper bits only if painted)."""
    out = {}
    aligned = g & 31 == 0 and 0 <= g - GFX_LO < GFX_LEN
    ink = ink or 8
    for r in range(16):
        for b in range(2):
            v = get(g + 2 * r + b)
            for k in range(8):
                n = 0
                if aligned:
                    t = table[(g + 2 * r + b - GFX_LO) * 4 + k // 2]
                    n = (t >> 4) if k % 2 == 0 else t & 15
                if not n and v >> (7 - k) & 1:
                    n = ink
                if n and not hidden_cell(get, x + 8 * b + k, y + r):
                    out[(x + 8 * b + k, y + r)] = n
    return out


def event(patch, kind, get, R, ns, alt, Sim, speed=0, out=None):
    """One site, original and patched from one state, the hook entered at NR 7 = speed.
    -> (failures, sprite pixels compared, original T, patched real time in 3.5 MHz T)."""
    f = []
    w = lambda a: get(a) | get(a + 1) << 8
    pc0, sp0 = R[24], R[12]
    nxt = pc0 + 3

    def stop(r):
        return r[24] == nxt and r[12] == sp0
    O, P = _overlays(patch, get, alt, ns)
    o, p = O(), P()
    nso = NextState(patch)
    so = _machine(Sim, o, list(R), nso, 'o', z80n=False)
    before = [list(a) for a in ns.attr]
    ns.events, ns.bad = [], []
    ns.nr[0x07] = speed & 3
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    ns.start(sp_, R[25])
    t0o, r0p = so.registers[25], ns.now()
    plot = kind in ('pl', 'en')
    iff_ok = {patch.syms['e_pl'], patch.syms['e_en'], patch.syms['e_ei'] + 1, nxt} if plot else None
    from .z80n import Z80NError
    try:
        if not (_run(so, stop) and _run(sp_, stop, iff_ok=iff_ok)):
            return ['did not return'], 0, 0, 0
    except (Z80NError, KeyError, IndexError) as e:
        return [('patched code ran off the rails', str(e)[:60])], 0, 0, 0
    t_o, t_p = so.registers[25] - t0o, ns.now() - r0p
    ns.sim = None
    ro, rp = so.registers, sp_.registers
    if out is not None:
        out['regs'] = [rp[i] for i in CMP]
        out['speed'] = ns.nr[0x07] & 3
        out['attr'] = [list(x) for x in ns.attr]
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        from .hooklib import r_check
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff],
                  'R: add %s' % r_check(ro[15], rp[15]) if 15 in diff else ''))
    if p.romw:
        f.append(('patched code wrote ROM',))
    if ns.bad:
        f.append(('port other than sprites and NextReg reads', ns.bad[:3]))
    if sp_.iff_on:
        f.append(('interrupts on inside the hook', sp_.iff_on))
    if ns.nr[0x57] != GAMEPAGE7:
        f.append(('slot 7 left mapped', ns.nr[0x57]))
    if ns.nr[0x55] != GAMEPAGE5:
        f.append(('slot 5 left mapped', ns.nr[0x55]))
    if ns.nr[0x52] != SCRPAGE:
        f.append(('slot 2 left mapped', ns.nr[0x52]))
    if ns.nr[0x07] & 3 != speed & 3:
        f.append(('CPU speed not the incoming one', ns.nr[0x07], speed))
    allowed = {0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x52, 0x55, 0x57}
    if any(e[0] not in allowed for e in ns.events):
        f.append(('NEXTREG outside the hook\'s set',))
    dead = range(ro[12] - 64, ro[12])
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not 0x4000 <= a < 0x5B00 and a not in dead and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), [hex(a) for a in sorted(md)[:4]]))
    npx = 0
    if plot:
        if any(0x5B00 <= a < 0x6000 for a in o.ov):
            f.append(('the original plot wrote slot 2 above the attributes (page 31\'s state)',))
        s = SPR_PLAY if kind == 'pl' else w(0x971A)
        scr = [a for a in p.ov if 0x4000 <= a < 0x6000]
        if s >= N_SPR:      # the guard: drawn on the screen as the original
            if any(o[a] != p[a] for a in set(scr) | {a for a in o.ov if 0x4000 <= a < 0x5B00}):
                f.append(('guard: screen differs from the original',))
        else:
            if scr:
                f.append(('patched plot wrote the screen', len(scr), hex(scr[0])))
            px = [a for a in o.ov if 0x4000 <= a < 0x5800 and ns.pages[STPAGE][a - 0x4000] != o.ov[a]]
            if px:
                f.append(('plot in page 31 differs from the original\'s screen', len(px), hex(px[0])))
        ink0 = get(0x5C8F)
        y, x, g = get(0x9700), get(0x9701), w(0x9702)
        if ink0 >= FE_COMPARE_LIMIT:
            f.append(('figure attribute with BRIGHT or FLASH: the write matters to logic', hex(ink0)))
        for a in o.ov:
            if 0x5800 <= a < 0x5B00 and get(a) != o.ov[a] and get(a) >= FE_COMPARE_LIMIT:
                f.append(('figure repainted a cell logic can see', hex(a), hex(get(a))))
                break
        drawn = {(xx, yy) for xx, yy in _pixels(o.ov) if not hidden_cell(get, xx, yy)}
        if s >= N_SPR:
            if ns.attr != before:
                f.append(('guard: a sprite changed',))
        else:
            img = ns.image(s)
            want = expected_nibbles(get, patch.table, g, x, y, ink0 & 7)
            ink_shown = {xy for xy, n in img.items()}
            npx = len(drawn)
            # the original's own pixels against the sprite: positions, then colours from the model
            paper_painted = {xy for xy in want if xy not in drawn}
            if ink_shown - paper_painted != drawn:
                f.append(('sprite pixels differ from the original plot', len((ink_shown - paper_painted) ^ drawn)))
            if img != want:
                f.append(('sprite colours differ from the model', len(set(img.items()) ^ set(want.items()))))
            changed = [i for i in range(128) if ns.attr[i] != before[i] and i != s]
            if changed:
                f.append(('other sprites changed', changed[:4]))
    else:
        if any(ns.attr[i][3] & 0x80 for i in range(N_SPR)):
            f.append(('sprite visible after screen clear',))
        sd = [a for a in keys if 0x4000 <= a < 0x5B00 and o[a] != p[a]]
        if sd:
            f.append(('screen writes differ', len(sd)))
    return f, npx, t_o, t_p


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX with the C simulator; at every site run original and patched code from one state and compare.
    Also at every figure attribute write: neither the old value nor the new reaches the values logic compares, so
    leaving the write out cannot change a collision read (work/wholerun.py tests that end to end). Every entry to
    the plotter must come from one of the two hooked calls (the build's plotter has no EI), and the stack must be
    outside the slots the hook remaps (2 and 7).
    -> (Counter, examples[, states])."""
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    Sim = _rw()
    ns = NextState(patch)
    states = []
    site_new = {a: old for a, old, new in patch.sites}
    pcs = set(SITE_KIND) | {READ_DONE, ATTR_WRITE, PLOTTER} | set(INTERIORS)
    t = collections.Counter()

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append(tuple(info))

    def on_pc(pc, sim):
        R, mem = sim.registers, sim.memory
        if pc in INTERIORS:
            fail('jump into a patched instruction', (hex(pc),))
            return
        if pc == PLOTTER:
            ret = mem[R[12]] | mem[R[12] + 1] << 8
            if ret not in (SITE_PL + 3, SITE_EN + 3):
                fail('plotter entered other than from the two hooked calls', (hex(ret),))
            return
        if pc == ATTR_WRITE:
            hl = R[6] << 8 | R[7]
            if mem[hl] != R[0]:
                c['attribute cells painted by figures'] += 1
                if R[0] >= FE_COMPARE_LIMIT or mem[hl] >= FE_COMPARE_LIMIT:
                    fail('figure paint crosses the value logic compares', (hex(hl), mem[hl], R[0]))
            return
        if pc == READ_DONE:
            c['collision reads'] += 1
            return
        kind = SITE_KIND.get(pc)
        if not kind:
            return
        if not 0x6000 <= R[12] < 0xA000:
            fail('stack in a slot the hook remaps', (hex(R[12]),))
        for a, old in site_new.items():
            if bytes(mem[a + k] for k in range(len(old))) != old:
                fail('game wrote a patch site', (hex(a),))
        get = mem.__getitem__
        if collect and c['collected ' + kind] < collect:
            c['collected ' + kind] += 1
            states.append((kind, list(R), bytes(mem), [list(x) for x in ns.attr],
                           {k: bytes(v) for k, v in ns.pages.items()}))
        fl, npx, to, tp = event(patch, kind, get, R, ns, alt, Sim)
        c[kind] += 1
        c['sprite pixels compared'] += npx
        t[kind + ' orig'] += to
        t[kind + ' patched'] += int(tp)
        for k in fl:
            fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())
        if progress and c[kind] % 2000 == 0:
            progress(c[kind], c)
    frames, err = RZ.trace(rzx_path, pcs, on_pc, stop=stop)
    if err:
        fail('recording desynced', (err,))
    c['frames'] = frames
    for k, v in t.items():
        c['T ' + k] = v
    return (c, dict(ex), states) if collect else (c, dict(ex))


def pace_model(c):
    """The plots' time in the model against the original's, % (verify's T counters; + = slower)."""
    to = c['T pl orig'] + c['T en orig']
    tp = c['T pl patched'] + c['T en patched']
    return 100.0 * (tp / to - 1) if to else 0.0


# ---------------------------------------------------------------------------------------------
# Unit tests: edges, every player and enemy slot, the guards, a painted map, negative controls
# ---------------------------------------------------------------------------------------------

def unit_tests(patch, states, neg=None):
    """states from verify(collect=n). Positions x every shift and edge of the box; each enemy slot; an index out of
    the guard's range; a graphic outside the table; a painted map with a paper pixel; clears from every sprite on;
    every site at all four incoming clocks (hooklib.every_site); the model's pace over the states in a row; the
    negative controls (each must be detected)."""
    from .hooklib import every_site
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()

    def fresh(pt, kind_attrs, pages=None):
        ns = NextState(pt)
        if kind_attrs is not None:
            ns.attr = [list(a) for a in kind_attrs]
        if pages and STPAGE in pages:       # the captured state (pace debt, flips); the code stays the patch's own
            ns.pages[STPAGE][ST_OFF:PAT_OFF] = pages[STPAGE][ST_OFF:PAT_OFF]
        return ns

    def one(pt, kind, R, mem, attrs, pages=None, speed=0, out=None):
        ns = fresh(pt, attrs, pages)
        return event(pt, kind, mem.__getitem__, list(R), ns, _alt(pt) if pt is not patch else alt, Sim, speed, out)

    def pace(pt):
        """The states in a row, one NextState (the debt carries): plots' model time against the original's, %."""
        ns = fresh(pt, None)
        to = tp = 0
        bad = 0
        for kind, R, mem, attrs, pages in states:
            if kind in ('pl', 'en'):
                fl, _, a, b = event(pt, kind, bytes(mem).__getitem__, list(R), ns, _alt(pt) if pt is not patch else alt, Sim)
                to, tp, bad = to + a, tp + b, bad + bool(fl)
        return 100.0 * (tp / to - 1) if to else 0.0, bad

    seen = {}
    pm, _ = pace(patch)
    c['model pace over the states %s' % ('ok' if abs(pm) < 5.0 else 'FAIL!')] += 1   # a few plots: line steps
    c['  model pace %+.2f%%' % pm] += 1
    sites = list(range(len(states)))

    def run(i, clock):
        kind, R, mem, attrs, pages = states[i]
        out = {}
        fl = one(patch, kind, R, bytearray(mem), attrs, pages, clock, out)[0]
        if fl:
            c['every-site failures!'] += 1
        return out.get('speed'), (tuple(out.get('regs', ())), str(out.get('attr')), not fl)
    mc, rows = every_site(sites, run)
    for k, v in mc.items():
        c['every-site matrix: %s' % k] += v

    for kind, R, mem, attrs, pages in states:
        mem = bytearray(mem)
        if kind in ('pl', 'en'):
            for x in (8, 9, 10, 11, 12, 13, 14, 15, 16, 100, 127, 128, 233, 239, 240):
                for y in (0, 7, 8, 63, 64, 112, 120):
                    m2 = bytearray(mem)
                    m2[0x9701], m2[0x9700] = x, y
                    fl = one(patch, kind, R, m2, attrs, pages)[0]
                    c['position cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                    if fl and c['  ex'] < 3:
                        c['  ex'] += 1
                        c['  x %d y %d %s' % (x, y, str(fl[:2])[:120])] += 1
            for g in range(GFX_LO, GFX_LO + GFX_LEN, 0x20 * 13):
                m2 = bytearray(mem)
                m2[0x9702], m2[0x9703] = g & 255, g >> 8
                fl = one(patch, kind, R, m2, attrs, pages)[0]
                c['graphic cases %s' % ('ok' if not fl else 'FAIL!')] += 1
            for ink in range(0, 8):
                m2 = bytearray(mem)
                m2[0x5C8F] = ink
                fl = one(patch, kind, R, m2, attrs, pages)[0]
                c['ink cases %s' % ('ok' if not fl else 'FAIL!')] += 1
            if kind == 'en':
                for idx in (0, 1, 2):
                    m2 = bytearray(mem)
                    m2[0x971A], m2[0x971B] = idx, 0
                    fl = one(patch, kind, R, m2, attrs, pages)[0]
                    c['enemy slot cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                m2 = bytearray(mem)
                m2[0x971A], m2[0x971B] = 3, 0   # guard: index out of range -> no sprite, drawn on the screen
                fl = one(patch, kind, R, m2, attrs, pages)[0]
                c['enemy index guard %s' % ('ok' if not fl else 'FAIL!')] += 1
            # the depth rule on purpose: one cell of the box water (BRIGHT, ink = paper), one BRIGHT with ink != paper
            y0, x0 = mem[0x9700], mem[0x9701]
            for wat, other in ((0x49, 0x47), (0x7F, 0x45)):
                m2 = bytearray(mem)
                base = 0x5800 + 32 * (y0 >> 3) + (x0 >> 3)
                m2[base], m2[base + 33] = wat, other
                fl = one(patch, kind, R, m2, attrs, pages)[0]
                c['depth cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                for name in ('hidden cells shown', 'all BRIGHT cells hide'):
                    if neg and name in neg:
                        seen[name] = seen.get(name, 0) + bool(one(neg[name], kind, R, m2, attrs, pages)[0])
            if kind == 'en' and neg and 'enemy index wrong' in neg:
                m2 = bytearray(mem)
                m2[0x971A], m2[0x971B] = 2, 0
                seen['enemy index wrong'] = seen.get('enemy index wrong', 0) + bool(
                    one(neg['enemy index wrong'], kind, R, m2, attrs, pages)[0])
            m2 = bytearray(mem)                 # a graphic below the table: ink only, no map read
            m2[0x9702], m2[0x9703] = 0x00, 0xC0
            fl = one(patch, kind, R, m2, attrs, pages)[0]
            c['graphic below the table %s' % ('ok' if not fl else 'FAIL!')] += 1
            # painted map: ink bits, a paper bit made opaque
            g = mem[0x9702] | mem[0x9703] << 8
            if 0 <= g - GFX_LO < GFX_LEN:
                import copy
                q = copy.copy(patch)
                key = '%04X' % g
                q.table = colour_table({key: [mem[g], 'g', [9, 10, 11, 12, 13, 14, 15, 1]]})[0]
                fl = one(q, kind, R, mem, attrs, pages)[0]
                c['painted cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                # a table the build does not hold: the sprite must disagree with the model
                ns = fresh(patch, attrs, pages)
                ns.pages[28 + ((g - GFX_LO) * 4 >> 13)][((g - GFX_LO) * 4) & 0x1FFF] ^= 0xF0
                fl = event(patch, kind, mem.__getitem__, list(R), ns, alt, Sim)[0]
                c['wrong table in pages %s' % ('detected' if fl else 'NOT DETECTED!')] += 1
            if neg:
                for name, qp in neg.items():
                    if name in ('no hide', 'R wrong in the hide hooks', 'limiter never waits'):
                        continue
                    if name == 'speed forced to 3.5 at exit':
                        fl = one(qp, kind, R, mem, attrs, pages, speed=3)[0]
                    else:
                        fl = one(qp, kind, R, mem, attrs, pages)[0]
                    seen[name] = seen.get(name, 0) + bool(fl)
        else:
            at = [list(a) for a in attrs]
            for i in range(N_SPR):
                at[i][3] |= 0x80
            fl = one(patch, kind, R, mem, at, pages)[0]
            c['screen clear cases %s' % ('ok' if not fl else 'FAIL!')] += 1
            for name in ('no hide', 'R wrong in the hide hooks'):
                if neg and name in neg:
                    fl = one(neg[name], kind, R, mem, at, pages)[0]
                    seen[name] = seen.get(name, 0) + bool(fl)
    if neg and 'limiter never waits' in neg:
        pn, _ = pace(neg['limiter never waits'])
        seen['limiter never waits'] = int(pn < -10)
        c['  limiter never waits: model pace %+.1f%%' % pn] += 1
    for name in neg or {}:          # each broken build must be caught in at least one state
        c['negative control %s' % ('detected' if seen.get(name) else 'NOT DETECTED %s!' % name)] += 1
        c['  %s: caught in %d states' % (name, seen.get(name, 0))] += 1
    return c


def _clone(patch, rom_edit=None, site_edit=None, pat_edit=None):
    import copy
    q = copy.copy(patch)
    if rom_edit:
        page = bytearray(patch.page)
        for off, val in rom_edit:
            page[off - 0x2000] = val
        q.page = bytes(page)
    if pat_edit:
        pc = bytearray(patch.pat_code)
        for off, val in pat_edit:
            pc[off] = val
        q.pat_code = bytes(pc)
    if site_edit:
        q.sites = [(a, old, site_edit.get(a, new)) for a, old, new in patch.sites]
    return q


def _find(rom, pat, start=0):
    i = bytes(rom).find(bytes.fromhex(pat), start)
    if i < 0:
        raise ValueError('pattern %s not in the hooks' % pat)
    return i


def negative_patches(patch):
    """Broken builds that must be detected (on the recordings' states)."""
    rom, pat = patch.rom_code, patch.pat_code
    out = {}
    r = lambda h, k, v: _clone(patch, [(ROM_ORG + _find(rom, h) + k, v)])
    q = lambda h, k, v: _clone(patch, pat_edit=[(_find(pat, h) + k, v)])
    out['x off by one'] = q('7cc620', 2, 33)                    # ADD A,32 on x -> 33
    out['y off by one'] = q('7dc620', 2, 33)
    out['ink ignored'] = q('3a8f5ce607', 4, 0)                  # AND 7 -> AND 0
    out['hidden cells shown'] = q('cb7728', 2, 0x18)            # BIT 6,A: JR Z -> JR
    out['all BRIGHT cells hide'] = q('aae607', 2, 0)
    out['slot 5 left mapped'] = q('ed915505', 3, MAPPAGE)
    out['wrong image'] = q('eb2a0297', 2, 0x04)                 # the graphic one row on
    out['screen not redirected'] = r('3e1f321afb', 1, SCRPAGE)  # the plotter draws on the ULA again
    out['EI kept in the plotter'] = _clone(patch, site_edit={PLOT_EI: b'\xFB'})
    out['slot 2 left mapped'] = r('ed91520a', 3, STPAGE)
    out['R off by one'] = r('d616', 1, 0x17)                    # SUB R_FIX
    out['limiter never waits'] = r('3e68cd', 1, 16)             # LD A,K_PLOT: K = 1
    i = ROM_ORG + _find(rom, '3a10fbed9207')                  # HLIB_SPEED_OUT: XOR A: NOP: NOP for LD A,(latch)
    out['speed forced to 3.5 at exit'] = _clone(patch, [(i, 0xAF), (i + 1, 0), (i + 2, 0)])
    out['hook clobbers HL'] = r('fde1dde1e1d1c1', 4, 0)          # POP HL -> NOP
    out['slot 7 left mapped'] = r('ed915701fb', 3, STPAGE)
    out['enemy index wrong'] = r('3a1a97', 1, 0x1B)
    out['no hide'] = r('ed913800', 3, 0x80)
    out['R wrong in the hide hooks'] = r('3e75cd', 1, 0x76)
    return out


# ---------------------------------------------------------------------------------------------
# Colour sheets and recolour
# ---------------------------------------------------------------------------------------------

NOTE = ('Abu Simbel Profanation colour map (docs/COLOURS.md): key = graphics byte (hex address, check = its value), bit = '
        'pixel. Ink pixels default to the plot\'s attribute; a painted paper pixel draws opaque.')
RECOLOUR = {'game': 'abu_simbel', 'output': 'sprites', 'colours': 'docs/profiles/abu_simbel_colours.json', 'clear': False,
            'note': NOTE}


def recolour(nex, cmap):
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    need = set(COLOUR_BANKS) | {5, 2, 0, 12}
    if not need <= set(have):
        raise ValueError('not an Abu Simbel sprite build: banks %s missing' % sorted(need - set(have)))
    peek = nex_peek(nex)
    prof = load_profile()
    if gfx_md5(peek) != prof['gfx_md5']:
        raise ValueError('game graphics differ from the expected snapshot')
    p = AbuPatch(prof, colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    if have[12] != p.page + bytes(8192):
        raise ValueError('alt ROM image / hook code differs from this version\'s')
    p.prepare(peek)
    out, changed = splice(nex, {b: p.extra_banks[b] for b in COLOUR_BANKS})
    info = {'banks changed': changed}
    info.update({k: v for k, v in p.cinfo.items() if v})
    return out, info


def capture(rzx_paths):
    """Images the recordings plot, with the first ink: {(group, graphic): ink}."""
    from . import rzx as RZ
    seen = {}

    def on(pc, sim):
        m = sim.memory
        R = sim.registers
        ret = m[R[12]] | m[R[12] + 1] << 8
        k = ('player' if ret == SITE_PL + 3 else 'enemies', m[0x9702] | m[0x9703] << 8)
        seen.setdefault(k, m[0x5C8F] & 7)
    for r in rzx_paths:
        RZ.trace(r, [PLOTTER], on)
    return seen


def image_part(get, group, g, ink):
    px, ent = [], {}
    for r in range(16):
        for b in range(2):
            a = g + 2 * r + b
            v = get(a)
            key = '%04X' % a
            ent[key] = [v, 'g']
            for k in range(8):
                on = v >> (7 - k) & 1
                px.append((8 * b + k, r, key, k, 1 if on else 0, (ink or 8) if on else 0))
    return {'id': '%04X' % g, 'size': 1, 'w': 16, 'h': 16, 'x': 0, 'y': 0, 'mir': 0, 'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'pixels': px, 'entries': ent,
            'group': group}


def sheets(z80, rzx_paths, out_dir, prefix='abu_simbel', colours=None, say=print):
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    seen = capture(rzx_paths)
    comps = [{'count': 1, 'group': grp, 'parts': [image_part(get, grp, g, ink)]}
             for (grp, g), ink in sorted(seen.items(), key=lambda x: (x[0][0] != 'player', x[0][1]))]
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    say('Sheets    : %d images; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : abu_simbel (figure plotter 0xDD78 -> sprites)')
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=PlainPatch())
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = AbuPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, TAIL_ADDR, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                         'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        v = verify(patch, r, stop=getattr(a, 'quick', None), collect=2)
        c, ex, st = v
        states += st
        if c['pl'] + c['en'] >= 500 and abs(pace_model(c)) > 2.0:
            c['model pace beyond 2%!'] += 1
        fails = {k: n for k, n in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, player %d, enemies %d, clears %d, %d sprite pixels, attr paints %d, collision reads %d, '
            'T orig %d, model pace %+.2f%% -> %s' % (
                os.path.basename(r), c['frames'], c['pl'], c['en'], c['cls'], c['sprite pixels compared'],
                c['attribute cells painted by figures'], c['collision reads'],
                c['T pl orig'] + c['T en orig'], pace_model(c),
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, n in ex.items():
            say('            %s: %s' % (k, str(n)[:220]))
    if states:
        u = unit_tests(patch, states[:12], negative_patches(patch))
        uf = {k: n for k, n in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % ({k: v for k, v in u.items() if not k.startswith('  ')}, 'PASS' if not uf else 'FAIL %s' % uf))
        for k, n in u.items():
            if k.startswith('  '):
                say('            %s' % k.strip())
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def _main(argv):
    if argv[0] == 'sheet':
        return sheets(argv[1], argv[3:], argv[2])
    raise SystemExit('python -m nexclash.abu_simbel sheet Z80 OUTDIR RZX...')


if __name__ == '__main__':
    import sys
    _main(sys.argv[1:])
