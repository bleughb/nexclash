"""Monty on the Run (Gremlin Graphics, 1985, 48K) - engine 'monty_on_the_run': figures as hardware sprites over the
game's own XOR pixels (overlay). Facts and decisions: games/monty_on_the_run.md; hooks: asm/monty_on_the_run_hooks.asm.

Two plotters XOR a figure's previous image at its old place and its current image at its new one (16 rows x 3 bytes,
bottom row first, pre-shifted): 0xB47F the four enemy slots (positions 46963, records 46987, images in a buffer whose
pointer 47019 / 47021 swaps), 0xF689 Monty (65282 / 65283, image 65286). Before an enemy's XOR the attribute painter
0xB59B colours the empty cells under it (the colour clash); its three stores become NOPs. Hooks after each XOR show
the figure's sprites (two 16 x 16 each for the 24-pixel image; enemies in their own ink, Monty white); the room
set-up and a new game hide them. The game never reads figure pixels or those colours back (survey readers: the
plotters' own XOR, a crumbling AND, an ink cycle), so its logic is the original's.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
NEWPOS, REC, BUFPTR, NSLOT = 46963, 46987, 47021, 4
MX, MY, MIMG = 65282, 65283, 65286
NSPR, MONTY_PAL = 10, 0x0F
EN_PLOT, EN_PLOT_END = 46325, 46491          # the enemy plotter's code (its pixel writes)
PAINTER, PAINTER_END = 46491, 46579
MO_PLOT, MO_PLOT_END = 63196, 63280          # Monty's plotter (its pixel writes)
MOVER = (40280, 40288)                         # 0x9D44: a 4 x 72 block of the screen slid up a row a frame (LDI x 4)
RECORD = 'monty_on_the_run'
_HERE = os.path.dirname(os.path.abspath(__file__))

SITES = {   # addr: (original, new bytes or hook symbol, resume, kind)
    46313: ('2173b7', 'e_en', 46316, 'enemies'),
    63169: ('2a02ff', 'e_mo', 63172, 'Monty'),
    57984: ('f32100c0', 'e_rm', 57988, 'room'),
    37386: ('f3214393', 'e_ng', 37390, 'new game'),
    43363: ('f3ed56', 'e_mn', 43366, 'menu'),
    46542: ('12', '00', None, 'painter store'),
    46552: ('12', '00', None, 'painter store'),
    46562: ('12', '00', None, 'painter store'),
}
HOOKS = {a: s for a, s in SITES.items() if s[2] is not None}
INTERIORS = tuple(a + k for a, s in HOOKS.items() for k in range(3, len(s[0]) // 2)) + \
    tuple(a + k for a, s in HOOKS.items() for k in range(1, min(3, len(s[0]) // 2)))
SEQUELS = {57985: 57984, 37387: 37386, 43364: 43363}   # the original's next instruction after a 1-byte DI: not a jump in
PAINT_CALL, PAINT_RET = 46325, 46328          # CALL 46491 in the plotter: the patched painter as an event
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all registers but R, T, MEMPTR


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_monty_on_the_run(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


class MontyOnTheRunPatch:
    name = 'Monty on the Run figures -> hardware sprites over the XOR figures (altrom, stateless, painter stores off)'

    def __init__(self, prof=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
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
        self.sites = []
        for a, (old, new, resume, kind) in SITES.items():
            old = bytes.fromhex(old)
            if resume is None:
                nb = bytes.fromhex(new)
            else:
                nb = b'\xC3' + self.syms[new].to_bytes(2, 'little') + bytes(len(old) - 3)
            self.sites.append((a, old, nb))
        self.extra_banks = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Monty on the Run patch expects the 48K snapshot')
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
        self.extra_banks = {12: self.page + bytes(8192)}


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
        self.sel = 0                    # NextReg select (port 0x243B)

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
        elif port == 0x243B:
            self.sel = val
        else:
            self.ports.append((port & 0xFF, val))

    def visible(self, i):
        return bool(self.attr[i][3] & 0x80)

    def pixels(self, i, out=None):
        """Ink pixels of a visible 4-bit sprite in ULA coordinates, inside the 256 x 192 screen."""
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

    def palette(self, i):
        return self.attr[i][2] >> 4


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
        if top - 64 <= a < top and (a in p.ov or a in o.ov):     # dead stack below the live SP
            continue
        if 0x5800 <= a < 0x5B00 and pc == PAINT_CALL:
            if a in p.ov:
                fl.append('patched painter wrote an attribute (%04X)' % a)
                break
            skipped += vo != get(a)
            continue
        if vo != vp:
            fl.append('memory %04X: original %02X, patched %02X' % (a, vo, vp))
            break
    return fl, sp.registers[25] - so.registers[25], skipped


def expected(get, slot):
    """What a hook leaves in figure `slot` (0-3 an enemy, 4 Monty): [(sprite, attributes, 128 pattern bytes)] or []
    (hidden)."""
    if slot < NSLOT:
        x, y = get(NEWPOS + 2 * slot), get(NEWPOS + 2 * slot + 1)
        img = (get(BUFPTR) | get(BUFPTR + 1) << 8) + 48 * slot
        col = get(REC + 8 * slot + 4)
        pal = (col & 7) | (8 if col & 0x40 else 0)
        first = 2 * slot
    else:
        x, y = get(MX), get(MY)
        img = get(MIMG) | get(MIMG + 1) << 8
        pal, first = MONTY_PAL, 8
        if x >= 240:                     # column 30 / 31: Monty's row helper 59065 refuses it, nothing is drawn
            return []
    vis = [16 <= (y - j) & 255 < 176 for j in range(16)]
    if not any(vis):
        return []

    def p4(v):
        return bytes((0x10 if v & (0x80 >> 2 * k) else 0) | (1 if v & (0x40 >> 2 * k) else 0) for k in range(4))
    pa, pb = bytearray(), bytearray()
    for j in range(16):
        r = (img + 3 * (15 - j)) & 0xFFFF
        if vis[j]:
            pa += p4(get(r)) + p4(get(r + 1))
            pb += p4(get(r + 2)) + bytes(4)
        else:
            pa += bytes(8)
            pb += bytes(8)
    X = (x & 0xF8) + 32
    Y = (191 - y) & 255
    out = []
    for k, pat in enumerate((pa, pb)):
        XX = X + 16 * k
        out.append((first + k, [XX & 255, (Y + 32) & 255, pal << 4 | XX >> 8, 0xC0 | (first + k), 0x80], bytes(pat)))
    return out


# ---------------------------------------------------------------------------------------------
# Verification against a recording
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, progress=None, collect=0):
    """Replay the RZX on the original; an event at every hook and at every painter call; every figure's XOR pixels
    against its sprites after each enemy and Monty hook. -> (Counter, examples)."""
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
            h.lay = collections.defaultdict(dict)     # figure 0-3 enemies, 4 Monty: {screen address: mask}
            h.lost = set()
            h.slot = None

        def on_sim(h, sim):
            h.R, h.mem = sim.registers, sim.memory
            h.reset()
            c['segments'] += 1
            h.lost = set(range(NSLOT + 1))             # a segment's start: what is on its screen is not tracked yet

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
            fig = None
            if EN_PLOT <= pc < EN_PLOT_END:
                fig = h.slot
            elif MO_PLOT <= pc < MO_PLOT_END:
                fig = NSLOT
            if fig is not None:
                d = old ^ v
                if d:
                    L = h.lay[fig]
                    L[a] = L.get(a, 0) ^ d
                    if not L[a]:
                        del L[a]
            elif MOVER[0] <= pc < MOVER[1]:            # the lift block slides a column of the screen, figures' pixels
                for i, L in h.lay.items():               # in it too: such a figure is unchecked to the next room
                    if a in L and i not in h.lost:
                        h.lost.add(i)
                        c['figures in a sliding block (unchecked to the next room)'] += 1
            elif h.kind(pc) == 'xor':                  # another XOR plot (an object, an item): figures' pixels stay
                c['other XOR plots over the screen'] += 1
            elif h.kind(pc) == 'and':                  # the crumbling AND: a figure's pixels survive where kept
                for i, L in h.lay.items():               # pixels it eats: the game's next XOR of that image turns
                    if a in L and L[a] & ~v:              # them on again as strays; the sprite shows the figure whole
                        if i not in h.lost:
                            h.lost.add(i)
                            c['figures eaten by the crumbling AND (unchecked to the next room)'] += 1
            else:
                for i, L in h.lay.items():             # another writer replaces the byte: the figure's pixels
                    if L.pop(a, None):                    # in it are gone from the screen
                        c['other writes over figure pixels'] += 1
                        c['  over figure pixels: writer %04X' % pc] += 1

        def kind(h, pc):
            """How the instruction at pc writes the screen: 'xor' / 'and' (LD (HL),A after XOR / AND (HL) or (IX+d)),
            or 'set' (a replacement)."""
            g = h.get
            if g(pc) not in (0x77, 0x12, 0x02):     # LD (HL),A / LD (DE),A / LD (BC),A
                return 'set'
            if g(pc - 1) == 0xAE or (g(pc - 3) in (0xDD, 0xFD) and g(pc - 2) == 0xAE):
                return 'xor'
            if g(pc - 1) == 0xA6 or (g(pc - 3) in (0xDD, 0xFD) and g(pc - 2) == 0xA6):
                return 'and'
            return 'set'

        def before(h, pc):
            if pc == PAINT_CALL:                       # the enemy being plotted: (IX - 46987) / 8
                h.slot = h.cur_slot()
                c['enemy plots'] += 1
                fl, t, skipped = event(patch, pc, h.get, h.R, h.ns, alt, psite, stop=PAINT_RET)
                c['attribute bytes not painted'] += skipped
                for k in fl:
                    h.fail('painter: %s' % k)
            if pc in HOOKS:
                kind = HOOKS[pc][3]
                c[kind] += 1
                cnt[pc] += 1
                if collect and len(states) < collect and pc in (46313, 63169) and c[kind] % 53 == 1:
                    states.append((pc, list(h.R), bytes(h.get(a) for a in range(65536))))
                if pc in (57984, 37386):
                    h.lost.clear()
                fl, t, _ = event(patch, pc, h.get, h.R, h.ns, alt, psite)
                if pc in (57984, 37386, 43363) and any(h.ns.visible(s) for s in range(NSPR)):
                    h.fail('%s left a sprite shown' % kind)
                c['hook T (28 MHz, patched minus original)'] += t
                c['hook T %s' % kind] += t
                for k in fl:
                    h.fail('%s: %s' % (kind, k))
                if pc == 46313:
                    h.compare(range(NSLOT))
                elif pc == 63169:
                    h.compare([NSLOT])
            elif pc in INTER:
                cnt[pc] += 1

        def cur_slot(h):
            ix = h.ix()
            k = ix - REC
            return k // 8 if 0 <= k < 8 * NSLOT and k % 8 == 0 else None

        def ix(h):
            from skoolkit.simulator import IXh, IXl
            return h.R[IXh] << 8 | h.R[IXl]

        def compare(h, figs):
            c['figure checks'] += 1
            for i in figs:
                if i in h.lost:
                    c['figure checks skipped (segment start)'] += 1
                    continue
                truth = layer_pixels(h.lay.get(i, {}))
                sprs = (2 * i, 2 * i + 1) if i < NSLOT else (8, 9)
                got = set()
                for s in sprs:
                    h.ns.pixels(s, got)
                if truth != got:
                    h.fail('figure %d != sprite' % i, (sorted(truth - got, key=str)[:3], sorted(got - truth, key=str)[:3], len(truth), len(got)))
                else:
                    c['sprite pixels compared'] += len(got)
            for s in range(NSPR, 128):
                if h.ns.visible(s):
                    h.fail('sprite %d shown' % s)

    cnt = collections.Counter()
    states = []
    h = H()
    c['frames'] = play_rzx(rzx_path, h, stop=stop)
    for a in INTER:
        if cnt[a] != (cnt[SEQUELS[a]] if a in SEQUELS else 0):
            c['jump into a patched instruction (%04X)!' % a] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


def unit_tests(patch, states):
    """Every slot, colour and edge position at the enemy and Monty hooks, from states the recording reached:
    registers and memory as the original's (event), the sprites as expected()."""
    c = collections.Counter()
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    places = ((0, 0), (8, 31), (7, 32), (120, 100), (231, 175), (240, 190), (255, 191), (64, 205), (16, 220), (100, 10))
    for pc, R, mem in states[:8]:
        for col in (0x45, 0x07, 0x40, 0x02, 0xC7):
            for x, y in places:
                m = bytearray(mem)
                figs = range(NSLOT) if pc == 46313 else [NSLOT]
                for i in figs:
                    if i < NSLOT:
                        m[NEWPOS + 2 * i], m[NEWPOS + 2 * i + 1] = (x + 24 * i) & 255, y
                        m[REC + 8 * i + 4] = col
                    else:
                        m[MX], m[MY] = x, y
                ns = NextState()
                ns.nr[7] = (x + y + col) % 4                     # entered at each CPU speed in turn
                for s in range(NSPR):
                    ns.attr[s] = [9, 9, 0, 0xC0 | s, 0x80]           # shown before: a hidden result must hide it
                fl, _, _ = event(patch, pc, m.__getitem__, R, ns, alt, psite)
                bad = list(fl)
                for i in figs:
                    want = expected(m.__getitem__, i)
                    sprs = (2 * i, 2 * i + 1) if i < NSLOT else (8, 9)
                    if not want:
                        if any(ns.visible(s) for s in sprs):
                            bad.append('figure %d left shown' % i)
                        continue
                    for s, attrs, pat in want:
                        if ns.attr[s] != attrs or bytes(ns.pat[s * 256:s * 256 + 128]) != pat:
                            bad.append('sprite %d %s, expected %s' % (s, ns.attr[s], attrs))
                k = '%s hook' % ('enemy' if pc == 46313 else 'Monty')
                c[k + (' FAIL!' if bad else ' ok')] += 1
                if bad and c['  example'] < 3:
                    c['  example'] += 1
                    c['  %s col=%02X x=%d y=%d: %s' % (k, col, x, y, bad[:2])] += 1
    for pc in (57984, 37386, 43363):                   # the hide hooks, from every collected state, all ten shown first
        for _, R, mem in states[:8]:
            ns = NextState()
            for s in range(NSPR):
                ns.attr[s] = [9, 9, 0, 0xC0 | s, 0x80]
            R2 = list(R)
            R2[24] = pc
            fl, _, _ = event(patch, pc, mem.__getitem__, R2, ns, alt, psite)
            bad = list(fl) + ['sprite %d left shown' % s for s in range(NSPR) if ns.visible(s)]
            k = '%s hook' % SITES[pc][3]
            c[k + (' FAIL!' if bad else ' ok')] += 1
            if bad and c['  example'] < 3:
                c['  example'] += 1
                c['  %s: %s' % (k, bad[:2])] += 1
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
    no_paint.sites = [s for s in patch.sites if s[0] != 46542]
    return [('enemy hook leaves the CPU at 28 MHz', _broken(patch, 'neg_spd', b'\0\0\0')),
            ('sprites one row high', _broken(patch, 'neg_y', b'\x3D')),        # DEC A before LD B,A
            ('ink lost in the pattern upload', _broken(patch, 'neg_pix', b'\xE6\x00')),
            ('enemy hook never shows the sprites', _broken(patch, 'neg_en', b'\0\0\0')),
            ('Monty hook never shows the sprites', _broken(patch, 'neg_mo', b'\0\0\0')),
            ('room set-up leaves the sprites', _broken(patch, 'neg_room', b'\0\0\0')),
            ('new game leaves the sprites', _broken(patch, 'neg_new', b'\0\0\0')),
            ('menu leaves the sprites', _broken(patch, 'neg_menu', b'\0\0\0')),
            ('enemy hook resumes one byte late', _broken(patch, 'neg_end', b'\xC3\x6D\xB4')),
            ('one painter store left on', no_paint)]


def build(z80, out, name, say=print):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = MontyOnTheRunPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    return not bad and not bad2, patch


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : monty_on_the_run (two XOR plotters, sprites as an overlay, painter stores off)')
    ok, patch = build(z80, out, name, say)
    for r in list(a.rzx or []):
        c, ex, states = verify(patch, r, stop=getattr(a, 'quick', None), collect=8)
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        if not c['figure checks']:
            fails['no figure draw reached: nothing verified'] = 1
        u = unit_tests(patch, states)
        fails.update({k: v for k, v in u.items() if k.endswith('FAIL!')})
        missed = [name for name, q in negative_patches(patch)
                  if not ({k for k, v in verify(q, r, stop=min(getattr(a, 'quick', None) or 1800, 1800))[0].items() if k.endswith('!')}
                          or any(k.endswith('FAIL!') for k in unit_tests(q, states[:2])))]
        if missed:
            fails['negative controls not caught: %s' % ', '.join(missed)] = len(missed)
        say('Units     : %s; negative controls: %d of %d caught' % (
            ', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.startswith('  ')), len(negative_patches(patch)) - len(missed), len(negative_patches(patch))))
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d segments, %d enemy draws, %d Monty draws, %d rooms, %d figure checks, '
            '%d sprite pixels; %d attribute bytes not painted -> %s' % (
                os.path.basename(r), c['frames'], c['segments'], c['enemies'], c['Monty'], c['room'],
                c['figure checks'], c['sprite pixels compared'], c['attribute bytes not painted'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
