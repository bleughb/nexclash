"""Finders Keepers (Mastertronic, 1985, 48K) - engine 'finders_keepers': figures as hardware sprites over the
game's own XOR pixels (overlay). Facts and decisions: games/finders_keepers.md; hooks: asm/finders_keepers_hooks.asm.

One plotter (0x9A05) draws all five figures (0 the Knight, 1-4 the room's creatures) from the table at 43632, 8 bytes
each: x, y, frame, ., dx, dy, colour, mask. A call XORs the old image (the entry's frame at the entry's place) with the
new one (frame 41328 at 41329, 41330; 16 x 16 from 43696 + 32 x frame; frame 0 blank), then writes the entry back.
Before the XOR it calls the attribute painter 0x9CD9 (the colour clash). The hook at that call shows the figure's
sprite and skips the painter for a figure with its own ink; a figure whose mask is 0 paints whole cells on purpose
and stays as the game draws it. The game never reads figure pixels or attributes back (scan readers: the plotter's
own XOR, LDIR fills, the painter itself), so with every pixel write kept the game's logic is the original's.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
IDX, NFRAME, NEWX, NEWY, PLOC = 41340, 41328, 41329, 41330, 41331
TABLE, GFX, NFIG = 43632, 43696, 5
PLOT, PLOT_END, PAINTER = 0x9A05, 0x9CD9, 0x9CD9
LOOP = 0x7058                   # main loop head: every figure's plot of the pass is done
RECORD = 'finders_keepers'
_HERE = os.path.dirname(os.path.abspath(__file__))

SITES = {   # addr: (original, opcode, hook symbol, resume, kind, length)
    0x9A3E: ('cdd99c', 0xCD, 'e_pt', 0x9AF3, 'plot', 3),
    0x7A26: ('872600', 0xC3, 'e_rm', 0x7A29, 'room', 3),
    0x88F7: ('af3272', 0xC3, 'e_cl', 0x88FB, 'erase all', 3),
}
INTERIORS = tuple(a + k for a, s in SITES.items() for k in range(1, s[5]))
SEQUELS = {0x7A27: 0x7A26, 0x88F8: 0x88F7}      # the original's next instruction after a short displaced one: not a jump in
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all registers but R, T, MEMPTR


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_finders_keepers(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def own_ink(colour, mask):
    """A figure the build shows as a sprite: its ink comes from its own colour (mask ink bits 0, mask not 0)."""
    return mask != 0 and not mask & 7


class FindersKeepersPatch:
    name = 'Finders Keepers figures -> hardware sprites over the XOR figures (altrom, stateless, painter skipped)'

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
        self.sites = [(a, bytes.fromhex(s[0]), bytes([s[1]]) + self.syms[s[2]].to_bytes(2, 'little'))
                      for a, s in SITES.items()]
        self.extra_banks = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Finders Keepers patch expects the 48K snapshot')
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
        for j in range(16):
            p = base + j * 8
            for k in range(8):
                b = self.pat[p + k]
                if b:
                    if b >> 4 and 0 <= y + j < 192:
                        out.add((x + 2 * k, y + j))
                    if b & 15 and 0 <= y + j < 192:
                        out.add((x + 2 * k + 1, y + j))
        return out


def screen_xy(a):
    return ((a & 31) * 8, ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38))


def image_layer(get, frame, x, y):
    """{screen address: mask} of frame at (x, y), as the plotter leaves it on the screen."""
    out = {}
    for r in range(16):
        yy = y + r
        if not 0 <= yy < 192:
            continue
        for c in range(2):
            v = get(GFX + 32 * frame + 2 * r + c)
            for k in range(8):
                if v & (0x80 >> k):
                    xx = x + c * 8 + k
                    if 0 <= xx < 256:
                        a = 0x4000 | ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2) | (xx >> 3)
                        out[a] = out.get(a, 0) | (0x80 >> (xx & 7))
    return out


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
            return self.ns.nr.get(getattr(self.ns, 'sel', 0), 0)
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


def event(patch, pc, get, R, ns, alt, psite):
    """-> (failures, hook T, attribute bytes the original painted and the patch did not, painted by the patch)."""
    from .simpool import machine
    from .z80n import install
    Sim = _rw()
    stop = SITES[pc][3]
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
        return fl, 0, 0, 0
    if not reached:
        fl.append('hook did not reach the resume point')
        return fl, 0, 0, 0
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
    skipped = painted = 0
    for a in set(o.ov) | set(p.ov):
        vo = o.ov.get(a, get(a))
        vp = p.ov.get(a, get(a))
        if top - 64 <= a < top and (a in p.ov or a in o.ov):     # dead stack below the live SP
            continue
        if 0x5800 <= a < 0x5B00:
            if a in o.ov and a not in p.ov:
                skipped += vo != get(a)
                continue
            painted += 1
        if vo != vp:
            fl.append('memory %04X: original %02X, patched %02X' % (a, vo, vp))
            break
    return fl, sp.registers[25] - so.registers[25], skipped, painted


def verify(patch, rzx_path, stop=None, every=1, progress=None, collect=0):
    """Replay the RZX on the original (each segment from its own snapshot); an event at every site; every figure's
    XOR pixels against its sprite at every main loop head. -> (Counter, examples)."""
    from .simrun import play_rzx
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    SITE = {a for a, old, new in patch.sites}
    INTER = set(INTERIORS)

    class H:
        def __init__(h):
            h.R = h.mem = None
            h.frame = 0
            h.reset()

        def reset(h):
            h.ns = NextState()
            h.lay = collections.defaultdict(dict)
            h.conv = {}
            h.dirty = False
            h.lost = set()

        def on_sim(h, sim):
            h.R, h.mem = sim.registers, sim.memory
            h.reset()
            c['segments'] += 1
            for i in range(NFIG):              # a segment starts from a snapshot: the figures on its screen
                e = TABLE + 8 * i
                if h.get(e + 2):
                    L = image_layer(h.get, h.get(e + 2), h.get(e), h.get(e + 1))
                    n = sum(bin(m).count('1') for m in L.values())
                    on = sum(bin(m & h.get(a)).count('1') for a, m in L.items())
                    h.lay[i] = L
                    if n and on * 10 < n * 9:          # the entry is not what the screen shows (a snapshot taken
                        h.lost.add(i)                  # in a transition): unchecked to the next room set-up
                        c['figures not on the screen at a segment start'] += 1
            sp = h.R[12]                       # snapshot taken inside a plot (the recorder saves at an interrupt):
            if any(PLOT <= h.get(sp + 2 * k) | h.get(sp + 2 * k + 1) << 8 < 0x9E00 for k in range(6)):
                h.lost.add(h.get(IDX))         # that figure's screen and entry disagree: unchecked to the next room
                c['figures mid-plot at a segment start'] += 1

        def on_desync(h, *a):
            h.fail('replay desynchronised', a[:2])

        def on_frame(h, n):
            h.frame = n
            if progress and n % 1000 == 0:
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
            if TABLE + 2 <= a < TABLE + 8 * NFIG and (a - TABLE) % 8 == 2 and not PLOT <= pc < PLOT_END + 0x100:
                h.lay.pop((a - TABLE) // 8, None)      # the game resets the figure (erased, or a new room's):
                c['figure resets by the game'] += 1    # what its old image left is the screen's, no figure's
            if not 0x4000 <= a < 0x5800:
                return
            old = h.get(a)
            if PLOT <= pc < PLOT_END:
                d = old ^ v
                if d:
                    L = h.lay[h.get(IDX)]
                    L[a] = L.get(a, 0) ^ d
                    if not L[a]:
                        del L[a]
                    h.dirty = True
            else:
                for i, L in h.lay.items():                 # another writer replaces the byte: the figure's
                    if L.pop(a, None):                        # pixels in it are gone from the screen
                        c['other writes over figure %s pixels' % ('sprite' if h.conv.get(i) else 'ULA')] += 1

        def before(h, pc):
            if pc == 0x9A3E:                   # what the figure must become, decided here whatever the patch does
                i = h.get(IDX)
                e = TABLE + 8 * i
                h.conv[i] = i < NFIG and own_ink(h.get(e + 6), h.get(e + 7))
                c['plots as sprite' if h.conv[i] else 'plots left to the ULA'] += 1
                if pc not in SITE:
                    c['plot'] += 1
            if pc in SITE:
                kind = SITES[pc][4]
                c[kind] += 1
                cnt[pc] += 1
                if pc == 0x9A3E and collect and len(states) < collect and c['plot'] % 97 == 1:
                    states.append((list(h.R), bytes(h.get(a) for a in range(65536))))
                if pc == 0x9A3E:
                    i = h.get(IDX)
                if pc == 0x7A26:
                    h.dirty = True
                    h.lost.clear()
                fl, t, skipped, painted = event(patch, pc, h.get, h.R, h.ns, alt, psite)
                c['hook T (28 MHz, patched minus original)'] += t
                c['attribute bytes not painted'] += skipped
                if pc == 0x9A3E and h.conv[i] and painted:
                    h.fail('the painter ran for a sprite figure', (i,))
                if pc == 0x9A3E and not h.conv[i] and skipped:
                    h.fail('a figure left to the ULA was not painted', (i,))
                for k in fl:
                    h.fail('%s: %s' % (kind, k))
            elif pc in INTER:
                cnt[pc] += 1
            elif pc == LOOP and h.dirty:
                h.dirty = False
                c['loop heads'] += 1
                if c['loop heads'] % every == 0:
                    h.compare()

        def compare(h):
            c['figure checks'] += 1
            for i in range(NFIG):
                truth = layer_pixels(h.lay.get(i, {}))
                if i in h.lost:
                    c['figure checks skipped (mid-plot segment start)'] += 1
                elif h.conv.get(i):
                    got = h.ns.pixels(i)
                    if truth != got:
                        h.fail('figure %d != sprite' % i, (sorted(truth - got)[:3], sorted(got - truth, key=str)[:3]))
                        if os.environ.get('FK_DEBUG') and c['debug shown'] < 3:
                            c['debug shown'] += 1
                            e = TABLE + 8 * i
                            print('DEBUG frame', h.frame, 'fig', i, 'attr', h.ns.attr[i], 'entry', [h.get(e + k) for k in range(8)],
                                  'truth', len(truth), 'got', len(got), 'lost', h.lost)
                    else:
                        c['sprite pixels compared'] += len(got)
                elif h.ns.visible(i):
                    h.fail('sprite %d shown for a figure left to the ULA' % i)
            for i in range(NFIG, 128):
                if h.ns.visible(i):
                    h.fail('sprite %d shown' % i)

    cnt = collections.Counter()
    states = []
    h = H()
    c['frames'] = play_rzx(rzx_path, h, stop=stop, keep_snapshots=True)
    for a in INTER:
        if cnt[a] != (cnt[SEQUELS[a]] if a in SEQUELS else 0):
            c['jump into a patched instruction (%04X)!' % a] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


def expected_sprite(get, i):
    """What the plot hook leaves in sprite i: None (hidden), or (attributes, 128 pattern bytes)."""
    e = TABLE + 8 * i
    col, mask, f = get(e + 6), get(e + 7), get(NFRAME)
    if not own_ink(col, mask) or not f:
        return None
    x, y = get(NEWX), get(NEWY)
    bright = (get(0x5800 + (y >> 3) * 32 + (x >> 3)) if mask & 0x40 else col) & 0x40
    pal = (col & 7) | (8 if bright else 0)
    pat = bytearray()
    for r in range(16):
        for cc in range(2):
            v = get(GFX + 32 * f + 2 * r + cc)
            pat += bytes((0x10 if v & (0x80 >> 2 * k) else 0) | (1 if v & (0x40 >> 2 * k) else 0) for k in range(4))
    return [(x + 32) & 255, y + 32, pal << 4 | (x + 32) >> 8, 0xC0 | i, 0x80], bytes(pat)


def unit_tests(patch, states):
    """Every colour / mask kind, frame and edge position at the plot hook, from states the recordings reached:
    registers and memory as the original's (event), the sprite as expected_sprite."""
    c = collections.Counter()
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    kinds = [(0x47, 0xB8), (0x05, 0xF8), (0x43, 0x38), (0x02, 0xC0), (0x28, 0x00), (0x00, 0x00), (0x06, 0x07), (0x47, 0x47)]
    for R, mem in states[:6]:
        for i in range(NFIG + 1):
            for col, mask in kinds:
                for f in (0, 1, 13, 52):
                    for x, y in ((0, 0), (7, 100), (223, 175), (224, 8), (240, 64), (255, 175)):
                        m = bytearray(mem)
                        m[IDX], m[NFRAME], m[NEWX], m[NEWY] = i, f, x, y
                        e = TABLE + 8 * min(i, NFIG - 1)
                        if i < NFIG:
                            m[e + 6], m[e + 7] = col, mask
                        ns = NextState()
                        ns.nr[7] = (x + y + f) % 4                      # entered at each CPU speed in turn
                        for k in range(NFIG):
                            ns.attr[k] = [9, 9, 0, 0xC0 | k, 0x80]       # shown before: a hidden result must hide it
                        fl, _, skipped, painted = event(patch, 0x9A3E, m.__getitem__, R, ns, alt, psite)
                        want = expected_sprite(m.__getitem__, i) if i < NFIG else None
                        bad = list(fl)
                        if i < NFIG:
                            if want is None and ns.visible(i):
                                bad.append('sprite left shown')
                            if want is not None and (ns.attr[i] != want[0] or bytes(ns.pat[i * 256:i * 256 + 128]) != want[1]):
                                bad.append('sprite %s, expected %s' % (ns.attr[i], want[0]))
                            if want is not None and painted or (not own_ink(col, mask) and skipped):
                                bad.append('painter wrong (painted %d, skipped %d)' % (painted, skipped))
                        k = 'plot hook %s' % ('figure index past the table' if i >= NFIG else 'sprite' if want else 'hidden or left')
                        c[k + (' FAIL!' if bad else ' ok')] += 1
                        if bad and c['  example'] < 3:
                            c['  example'] += 1
                            c['  %s i=%d col=%02X mask=%02X f=%d x=%d y=%d: %s' % (k, i, col, mask, f, x, y, bad[:2])] += 1
    for pc in (0x7A26, 0x88F7):                         # room set-up and erase-all, from every state, all sprites shown
        for n, st in enumerate(states[:8]):
            R, mem = st[-2], st[-1]
            ns = NextState()
            ns.nr[7] = n % 4
            for k in range(NFIG):
                ns.attr[k] = [9, 9, 0, 0xC0 | k, 0x80]
            R2 = list(R)
            R2[24] = pc
            fl, _, _, _ = event(patch, pc, mem.__getitem__, R2, ns, alt, psite)
            bad = list(fl) + ['sprite %d left shown' % k for k in range(NFIG) if ns.visible(k)]
            k = '%s hook' % SITES[pc][4]
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
    no_site = copy.copy(patch)
    no_site.sites = [s for s in patch.sites if s[0] != 0x9A3E]
    return [('plot hook leaves the CPU at 28 MHz', _broken(patch, 'neg_spd', b'\0\0\0')),
            ('sprites one row low', _broken(patch, 'neg_y', b'\xC6\x21')),
            ('ink lost in the pattern upload', _broken(patch, 'neg_pix', b'\x3E\x00')),
            ('plot hook never shows the sprite', _broken(patch, 'neg_skip', b'\0\0\0')),
            ('whole-cell figures made sprites too', _broken(patch, 'neg_own', b'\0\0')),
            ('room set-up leaves the sprites', _broken(patch, 'neg_room', b'\0\0\0')),
            ('erase-all leaves the sprites', _broken(patch, 'neg_clear', b'\0\0\0')),
            ('room hook loses a register (H)', _broken(patch, 'neg_disp', b'\x26\x01')),
            ('plot site not applied', no_site)]


def build(z80, out, name, say=print):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = FindersKeepersPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    return not bad and not bad2, patch


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : finders_keepers (one plotter, XOR figures, sprites as an overlay, painter skipped)')
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
        say('Verify    : %s  %d frames, %d segments, %d plots (%d as sprites), %d rooms, %d figure checks, %d sprite pixels; '
            '%d attribute bytes not painted -> %s' % (
                os.path.basename(r), c['frames'], c['segments'], c['plot'], c['plots as sprite'], c['room'],
                c['figure checks'], c['sprite pixels compared'], c['attribute bytes not painted'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
