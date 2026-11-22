"""Monty is Innocent (Gremlin Graphics, 1985, 48K) - engine 'monty_is_innocent': figures as hardware sprites over the
game's own XOR pixels (overlay). Facts and decisions: games/monty_is_innocent.md; hooks: asm/monty_is_innocent_hooks.asm.

One plotter, 0xD52E (54574), XORs a figure's previous image at its old place ((24960) image, (24958) x, (24959) y;
y = 195: none) and its new image at its new place (HL, C x, B y), 24 rows x 3 bytes, bottom row first at screen row
191 - y, pre-shifted for x & 6 (+144 a step). It draws Sam Stoat (the player), Monty (in later rooms) and the guards (records at 24962, 8
bytes: +0 y, +1 x, +2/3 image, +6 ink), and also panel icons, room items and the ending, which stay on the ULA. The
guard routine's painter 0xD5D8 colours the white-ink cells under a guard with its ink (store 54766): the colour clash;
that store becomes a NOP. A hook at the plotter's entry shows the drawn figure's four sprites, chosen by the caller
(return address; guards by IX); the screen clear before a room and the ending (55506) hides them. The game reads
neither figure pixels nor those colours back for its logic (scan: the plotter's own XOR, the painter's own test).
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = None                               # the converter's choice: below SP (the printer buffer is in use)
GUARDS = 24962
NSPR, NFIG = 20, 5
PLOT, PLOT_RET, PLOT_END = 54574, 54577, 54629      # the plotter; its XOR writes lie in 54574..54628
PAINT, PAINT_END = 54744, 54781
MOVERS = {56133: 0, 55676: 0, 55142: 1, 55749: 1, 54958: None, 54900: None, 52381: 'erase'}  # return address: 0 Sam, 1 Monty,
# None a guard drawn, 'erase' a guard the gun caught (its image XORed off with old y 195, then marked dead)
RECORD = 'monty_is_innocent'
_HERE = os.path.dirname(os.path.abspath(__file__))

SITES = {   # addr: (original, new bytes or hook symbol, resume, kind)
    PLOT: ('e5c5d5', 'e_plot', PLOT_RET, 'plot'),
    55506: ('210040', 'e_cls', 55509, 'clear screen'),
    54766: ('77', '00', None, 'painter store'),
}
HOOKS = {a: s for a, s in SITES.items() if s[2] is not None}
INTERIORS = (54575, 54576, 55507, 55508)
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all registers but R, T, MEMPTR


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_monty_is_innocent(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    sig, a = bytes.fromhex(sg['bytes']), sg['addr']
    banks = getattr(snap, 'banks', None)
    if banks is not None:                       # the 48K game only: build() keeps the printer buffer (48K in the converter)
        if getattr(snap, 'is128', False):
            return False
        mem = bytes(banks[5]) + bytes(banks[2]) + bytes(banks[0])
        return mem[a - 0x4000:a - 0x4000 + len(sig)] == sig
    if getattr(snap, 'machine', '48K') != '48K':
        return False
    return bytes(snap.memory[a:a + len(sig)]) == sig


class MontyIsInnocentPatch:
    name = 'Monty is Innocent figures -> hardware sprites over the XOR figures (altrom, stateless, painter store off)'

    def __init__(self, prof=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.keep_printer_buffer = True          # the game runs code at 0x5B00 (JP 23296): NEXLOAD overwrites it
        self.tail_addr = TAIL_ADDR
        self.max_tail = None
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
        self.sites = []
        for a, (old, new, resume, kind) in SITES.items():
            old = bytes.fromhex(old)
            nb = bytes.fromhex(new) if resume is None else b'\xC3' + self.syms[new].to_bytes(2, 'little') + bytes(len(old) - 3)
            self.sites.append((a, old, nb))
        self.extra_banks = {}

    def apply(self, snap):
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Next-side state (as Monty on the Run's)
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.patp = 0
        self.ports = []
        self.sel = 0                    # NextReg select (port 0x243B)
        self.speeds = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if reg == 7:
            self.speeds.append(val)
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def port(self, port, val):
        if port & 0xFF == 0x5B:
            self.pat[self.patp % 16384] = val
            self.patp += 1
        elif port == 0x303B:
            self.patp = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port == 0x243B:
            self.sel = val
        else:
            self.ports.append((port & 0xFF, val))

    def visible(self, i):
        return bool(self.attr[i][3] & 0x80)

    def pixels(self, i, out=None):
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
        for j in range(16):
            p = base + j * 8
            for k in range(8):
                b = self.pat[p + k]
                for half, xx in ((b >> 4, x + 2 * k), (b & 15, x + 2 * k + 1)):
                    if half and 0 <= y + j < 192 and 0 <= xx < 256:
                        out.add((xx, y + j))
        return out


def screen_xy(a):
    return ((a & 31) * 8, ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38))


def layer_pixels(layer):
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
    def __init__(self, get, alt, psite):
        _Ov.__init__(self, get)
        self.alt, self.psite, self.romw = alt, psite, 0

    def __getitem__(self, a):
        if a < 0x4000:
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
        if self.ns is not None and port == 0x253B:    # NextReg read: NR 7 reads back the programmed speed in bits 1:0
            return self.ns.nr.get(self.ns.sel, 0)
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if self.ns is not None:
            self.ns.port(port, value)
        else:
            self.ports.append((port & 0xFF, value))


def _run(sim, stop, limit=400000):
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
    """-> (failures, hook T, attribute bytes the original wrote and the patch did not)."""
    from .simpool import machine
    from .z80n import install
    Sim = _rw()
    stop = stop if stop is not None else SITES[pc][2]
    fl = []
    ports = []
    o = _Ov(get)
    so = machine(Sim, o, list(R), 'o')
    so.set_tracer(_Ports(ports=ports))
    if not _run(so, stop):
        fl.append('original did not reach the resume point')
    p = _OvP(get, alt, psite)
    sp = machine(Sim, p, list(R), 'p')
    install(sp, ns.nextreg)
    sp.set_tracer(_Ports(ns=ns))
    n0 = len(ns.ports)
    speed = ns.nr.get(7, 0)
    try:
        reached = _run(sp, stop)
    except Exception as x:                     # a broken hook running away (a negative control)
        fl.append('hook crashed: %s' % str(x)[:80])
        return fl, 0, 0
    if not reached:
        fl.append('hook did not reach the resume point')
        return fl, 0, 0
    for i in CMP:
        if so.registers[i] != sp.registers[i]:
            fl.append('register %d: original %02X, patched %02X' % (i, so.registers[i], sp.registers[i]))
    if p.romw:
        fl.append('hook wrote the ROM')
    if ns.nr.get(7, 0) != speed:
        fl.append('speed not restored: entered at %d, left at %d' % (speed, ns.nr.get(7, 0)))
    if ports != ns.ports[n0:]:
        fl.append('port writes differ %s %s' % (ports[:3], ns.ports[n0:][:3]))
    del ns.ports[n0:]
    top = sp.registers[12]
    skipped = 0
    for a in set(o.ov) | set(p.ov):
        vo = o.ov.get(a, get(a))
        vp = p.ov.get(a, get(a))
        if top - 64 <= a < top and (a in p.ov or a in o.ov):
            continue
        if 0x5800 <= a < 0x5B00 and pc == PAINT:
            if a in p.ov:
                fl.append('patched painter wrote an attribute (%04X)' % a)
                break
            skipped += vo != get(a)
            continue
        if vo != vp:
            fl.append('memory %04X: original %02X, patched %02X' % (a, vo, vp))
            break
    return fl, sp.registers[25] - so.registers[25], skipped


def figure_of(get, R):
    """At the plotter's entry: (figure, ink, erased) of the figure being drawn, or None (an icon, an item, the
    ending). erased: the gun caught a guard and the game XORs its image off the screen."""
    from skoolkit.simulator import IXh, IXl
    sp = R[12]
    ret = get(sp) | get((sp + 1) & 0xFFFF) << 8
    if ret not in MOVERS:
        return None
    f = MOVERS[ret]
    if f not in (None, 'erase'):
        return f, 7, False
    k = (R[IXh] << 8 | R[IXl]) - GUARDS
    if not (0 <= k < 24 and k % 8 == 0):
        return None
    return 2 + k // 8, get(GUARDS + k + 6) & 7, f == 'erase'


def expected(get, R):
    """What the plot hook leaves for the figure being drawn: (figure, [(sprite, attributes, pattern)] or [] hidden),
    or None (not a figure)."""
    from skoolkit.simulator import B, C, H, L
    fi = figure_of(get, R)
    if fi is None:
        return None
    f, ink, erased = fi
    x, y = R[C], R[B]
    if y > 191 or erased:
        return f, []
    img = ((R[H] << 8 | R[L]) + 144 * ((x >> 1) & 3)) & 0xFFFF

    def p4(v):
        return bytes((0x10 if v & (0x80 >> 2 * k) else 0) | (1 if v & (0x40 >> 2 * k) else 0) for k in range(4))

    def pat(r0, right):
        out = bytearray()
        for j in range(16):
            r = r0 - j
            if r < 0 or y + r > 191:
                out += bytes(8)
                continue
            a = (img + 3 * r) & 0xFFFF
            out += p4(get(a + 2)) + bytes(4) if right else p4(get(a)) + p4(get(a + 1))
        return bytes(out)
    X, Y = (x & 0xF8) + 32, 200 - y
    out = []
    for k, (r0, right, dx, dy) in enumerate(((23, 0, 0, 0), (23, 1, 16, 0), (7, 0, 0, 16), (7, 1, 16, 16))):
        s = 4 * f + k
        XX = X + dx
        out.append((s, [XX & 255, (Y + dy) & 255, ink << 4 | XX >> 8, 0xC0 | s, 0x80], pat(r0, right)))
    return f, out


# ---------------------------------------------------------------------------------------------
# Verification against a recording
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, progress=None, collect=0):
    """Replay the RZX on the original; an event at every hook and every painter call; after every figure's plot,
    its XOR pixels against its four sprites. -> (Counter, examples)."""
    from .simrun import play_rzx
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    INTER = set(INTERIORS)

    class H:
        def __init__(h):
            h.R = h.mem = None
            h.frame = 0
            h.reset()

        def reset(h):
            h.ns = NextState()
            h.lay = collections.defaultdict(dict)     # figure: {screen address: XOR mask}
            h.lost = set(range(NFIG))                  # unknown until a first draw (old y 195) or a screen clear
            h.cur = None                               # (figure or None, return address) of the plot in progress
            h.prev = None                              # the last PC seen (an interior entered from its predecessor is no jump)
            h.resume = set()                           # PCs an interrupt will return to

        def on_sim(h, sim):
            h.R, h.mem = sim.registers, sim.memory
            h.reset()
            c['segments'] += 1

        def on_interrupt(h, sim, prev_pc):
            h.resume.add(h.R[24])
            h.resume.add(prev_pc)

        def on_desync(h, *a):
            h.fail('replay desynchronised', a[:2])

        def on_frame(h, n):
            h.frame = n
            if progress and n % 2000 == 0:
                progress(n, c)

        def fail(h, k, info=()):
            c[k + '!'] += 1
            if len(ex[k]) < 5:
                ex[k].append((h.frame,) + tuple(info))

        def get(h, a):
            m = h.mem
            return m.m[a] if hasattr(m, 'm') else m[a]

        def on_write(h, a, v, pc, mem):
            if a in psite:
                h.fail('game wrote a patch site', (a,))
            if not 0x4000 <= a < 0x5800:
                return
            old = h.get(a)
            if PLOT <= pc < PLOT_END and h.cur is not None:
                f = h.cur[0]
                if f is not None:
                    d = old ^ v
                    if d:
                        L = h.lay[f]
                        L[a] = L.get(a, 0) ^ d
                        if not L[a]:
                            del L[a]
                else:
                    c['other XOR plots (icons, items, the ending)'] += 1
            else:
                for i, L in h.lay.items():
                    if L.pop(a, None):
                        c['other writes over figure pixels'] += 1
                        c['  over figure pixels: writer %04X' % pc] += 1

        def before(h, pc):
            prev, h.prev = h.prev, pc
            if pc == PAINT:
                c['painter calls'] += 1
                sp = h.R[12]
                ret = h.get(sp) | h.get(sp + 1) << 8
                fl, t, skipped = event(patch, pc, h.get, h.R, h.ns, alt, psite, stop=ret)
                c['attribute bytes not painted'] += skipped
                for k in fl:
                    h.fail('painter: %s' % k)
            if pc in HOOKS:
                kind = HOOKS[pc][3]
                c[kind] += 1
                cnt[pc] += 1
                if pc == PLOT:
                    want = expected(h.get, h.R)
                    if collect and len(states) < collect and want is not None and c[kind] % 41 == 1:
                        states.append((pc, list(h.R), bytes(h.get(a) for a in range(65536))))
                    if want is not None:
                        f = want[0]
                        erased = figure_of(h.get, h.R)[2]
                        if h.get(24959) == 195 and not erased:  # first draw: nothing of this figure on the screen
                            h.lay[f] = {}
                            h.lost.discard(f)
                    sp = h.R[12]
                    h.cur = (want[0] if want else None, h.get(sp) | h.get(sp + 1) << 8)
                else:                                          # the screen clear: every figure gone
                    h.lay.clear()
                    h.lost = set()
                fl, t, _ = event(patch, pc, h.get, h.R, h.ns, alt, psite)
                c['hook T (28 MHz, patched minus original)'] += t
                c['hook T %s' % kind] += t
                for k in fl:
                    h.fail('%s: %s' % (kind, k))
                if pc == PLOT and want is not None:
                    c['figure plots'] += 1
                    for s, attrs, pat in want[1]:
                        if h.ns.attr[s] != attrs or bytes(h.ns.pat[s * 256:s * 256 + 128]) != pat:
                            h.fail('sprite %d not as expected' % s, (h.ns.attr[s], attrs))
                    if not want[1] and any(h.ns.visible(4 * want[0] + k) for k in range(4)):
                        h.fail('figure %d below the screen left shown' % want[0])
                elif pc != PLOT and any(h.ns.visible(s) for s in range(NSPR)):
                    h.fail('clear screen left a sprite shown')
                for s in range(NSPR, 128):
                    if h.ns.visible(s):
                        h.fail('sprite %d shown' % s)
            elif h.cur is not None and pc == h.cur[1]:         # the plotter returned: the figure's XOR pixels
                f = h.cur[0]
                h.cur = None
                if f is not None:
                    h.compare(f)
            elif pc in INTER:
                if prev != pc - 1 and pc not in h.resume:      # sequential, or an interrupt's return: not a jump in
                    cnt[pc] += 1
                h.resume.discard(pc)

        def compare(h, f):
            c['figure checks'] += 1
            if f in h.lost:
                c['figure checks skipped (segment start)'] += 1
                return
            truth = layer_pixels(h.lay.get(f, {}))
            got = set()
            for k in range(4):
                h.ns.pixels(4 * f + k, got)
            if truth != got:
                h.fail('figure %d != sprites' % f, (sorted(truth - got, key=str)[:3], sorted(got - truth, key=str)[:3], len(truth), len(got)))
            else:
                c['sprite pixels compared'] += len(got)

    cnt = collections.Counter()
    states = []
    h = H()
    c['frames'] = play_rzx(rzx_path, h, stop=stop)
    for a in INTER:
        if cnt[a]:
            c['jump into a patched instruction (%04X)!' % a] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


def unit_tests(patch, states):
    """Every figure, ink and edge position at the plot hook, from states the recording reached: registers and memory
    as the original's (event), the sprites as expected(); the clear-screen hook with all twenty shown first."""
    from skoolkit.simulator import B, C, IXh, IXl
    c = collections.Counter()
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    places = ((0, 0), (1, 16), (2, 100), (6, 160), (8, 168), (231, 169), (232, 191), (255, 192), (100, 250), (17, 63))
    for pc, R, mem in states[:8]:
        for ink in (0, 2, 5, 7):
            for x, y in places:
                m = bytearray(mem)
                R2 = list(R)
                R2[C], R2[B] = x, y
                for k in range(3):
                    m[GUARDS + 8 * k + 6] = (m[GUARDS + 8 * k + 6] & 0xF8) | ink
                ns = NextState()
                ns.nr[7] = (x + y + ink) % 4                 # entered at each CPU speed in turn
                for s in range(NSPR):
                    ns.attr[s] = [9, 9, 0, 0xC0 | s, 0x80]
                fl, _, _ = event(patch, pc, m.__getitem__, R2, ns, alt, psite)
                want = expected(m.__getitem__, R2)
                bad = list(fl)
                if want is not None:
                    f, sprs = want
                    if not sprs:
                        if any(ns.visible(4 * f + k) for k in range(4)):
                            bad.append('figure %d left shown' % f)
                    for s, attrs, pat in sprs:
                        if ns.attr[s] != attrs or bytes(ns.pat[s * 256:s * 256 + 128]) != pat:
                            bad.append('sprite %d %s, expected %s' % (s, ns.attr[s], attrs))
                c['plot hook' + (' FAIL!' if bad else ' ok')] += 1
                if bad and c['  example'] < 3:
                    c['  example'] += 1
                    c['  ink=%d x=%d y=%d: %s' % (ink, x, y, bad[:2])] += 1
    for _, R, mem in states[:8]:                       # the gun's call (52381): that guard's four sprites hidden
        for k in range(3):
            m = bytearray(mem)
            R2 = list(R)
            sp = R2[12]
            m[sp], m[sp + 1] = 52381 & 255, 52381 >> 8
            ix = GUARDS + 8 * k
            R2[IXh], R2[IXl] = ix >> 8, ix & 255
            ns = NextState()
            for s in range(NSPR):
                ns.attr[s] = [9, 9, 0, 0xC0 | s, 0x80]
            fl, _, _ = event(patch, PLOT, m.__getitem__, R2, ns, alt, psite)
            want = expected(m.__getitem__, R2)
            f = 2 + k
            bad = list(fl) + (['expected() did not hide guard %d' % k] if want != (f, []) else []) + \
                ['guard %d sprite %d left shown' % (k, 4 * f + j) for j in range(4) if ns.visible(4 * f + j)]
            c['gun hook' + (' FAIL!' if bad else ' ok')] += 1
            if bad and c['  example'] < 3:
                c['  example'] += 1
                c['  gun k=%d: %s' % (k, bad[:2])] += 1
    for _, R, mem in states[:8]:
        ns = NextState()
        for s in range(NSPR):
            ns.attr[s] = [9, 9, 0, 0xC0 | s, 0x80]
        R2 = list(R)
        R2[24] = 55506
        fl, _, _ = event(patch, 55506, mem.__getitem__, R2, ns, alt, psite, stop=55509)
        bad = list(fl) + ['sprite %d left shown' % s for s in range(NSPR) if ns.visible(s)]
        c['clear screen hook' + (' FAIL!' if bad else ' ok')] += 1
    return c


def _broken(patch, sym, new):
    import copy
    q = copy.copy(patch)
    a = patch.syms[sym] - 0x2000
    page = bytearray(patch.page)
    page[a:a + len(new)] = new
    q.page = bytes(page)
    return q


def negative_patches(patch):
    import copy
    no_paint = copy.copy(patch)
    no_paint.sites = [s for s in patch.sites if s[0] != 54766]
    return [('plot hook leaves the CPU at 28 MHz', _broken(patch, 'neg_spd', b'\0\0\0')),
            ('the gun leaves the guard shown', _broken(patch, 'neg_kill', b'\0\0\0')),
            ('sprites at the wrong row', _broken(patch, 'neg_y', b'\x3C')),     # LD B,A made INC A: B keeps y
            ('ink lost in the pattern upload', _broken(patch, 'neg_pix', b'\xE6\x00')),
            ('plot hook never shows the sprites', _broken(patch, 'neg_fig', b'\0\0\0')),
            ('clear screen leaves the sprites', _broken(patch, 'neg_cls', b'\0\0\0')),
            ('plot hook resumes one byte late', _broken(patch, 'neg_end', b'\xC3\x32\xD5')),
            ('painter store left on', no_paint)]


def build(z80, out, name, say=print):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, keep_printer_buffer=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = MontyIsInnocentPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch, keep_printer_buffer=True)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    return not bad and not bad2, patch


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : monty_is_innocent (one XOR plotter, sprites as an overlay by caller, painter store off)')
    ok, patch = build(z80, out, name, say)
    for r in list(a.rzx or []):
        c, ex, states = verify(patch, r, stop=getattr(a, 'quick', None), collect=8)
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        if not c['figure checks']:
            fails['no figure plot reached: nothing verified'] = 1
        u = unit_tests(patch, states)
        fails.update({k: v for k, v in u.items() if k.endswith('FAIL!')})
        missed = [name for name, q in negative_patches(patch)
                  if not ({k for k, v in verify(q, r, stop=min(getattr(a, 'quick', None) or 1500, 1500))[0].items() if k.endswith('!')}
                          or any(k.endswith('FAIL!') for k in unit_tests(q, states[:2])))]
        if missed:
            fails['negative controls not caught: %s' % ', '.join(missed)] = len(missed)
        say('Units     : %s; negative controls: %d of %d caught' % (
            ', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.startswith('  ')), len(negative_patches(patch)) - len(missed), len(negative_patches(patch))))
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d segments, %d plots, %d figure plots, %d screen clears, %d painter calls, '
            '%d figure checks, %d sprite pixels; %d attribute bytes not painted -> %s' % (
                os.path.basename(r), c['frames'], c['segments'], c['plot'], c['figure plots'], c['clear screen'],
                c['painter calls'], c['figure checks'], c['sprite pixels compared'], c['attribute bytes not painted'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
