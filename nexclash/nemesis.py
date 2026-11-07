"""Nemesis the Warlock (Martech 1987, 48K) engine 'nemesis'. Additive module: reachable only
through is_nemesis().

Game facts (games/nemesis_the_warlock.md): the play area is composed in a back buffer at 23798
(32 bytes per line; line L, column c = screen pixel row L, byte column c) and copied to the
screen rows 8-127, columns 2-29 by 32154. Figures are masked AND/OR plots into the buffer with a
save-under (IY): 31268 (right) / 31362 (left, bits mirrored), 32 lines x 4 bytes (mask at DE,
image DE+128) or x 3 bytes when (51930) = 4 / 5 (image DE+96); 31213 8 lines x 1 byte (image
DE+8, save area 32388). Interrupts are off all game.
Hooks (asm/nemesis_hooks.asm, RAM page PAGE at 0x2000-0x3FFF): the plotters run unchanged (all
game memory identical); plots are logged; after the copy the screen gets each figure's
save-under back (reverse order) and every figure is 2x2 4-bit sprites (1 ink, 2 paper = solid,
0 transparent; colours from the room attribute 51800), patterns cached by (graphic, width).
"""
import collections
import json
import os

PAGE = 24                   # 8K page at MMU slot 1 (bank 12, first half)
TAIL_ADDR = 0x5E00          # back buffer: written before it is read (scan 2026-11-02)
BUFBASE = 23798
ROOMATT = 51800
WIN_X, WIN_Y = (16, 240), (8, 128)          # copy window in pixels
SITES_ORIG = {31213: '0608dd', 31268: '3adaca', 31362: '3adaca', 32154: '21f85d', 37865: '210040',
              35321: 'ee5a77', 35334: 'ee5a77'}
SITE_SYM = {31213: 'e_p8', 31268: 'e_pr', 31362: 'e_pl', 32154: 'e_cp', 37865: 'e_cls', 35321: 'e_x1',
            35334: 'e_x2'}
SITE_KIND = {31213: 'p8', 31268: 'pr', 31362: 'pl', 32154: 'cp', 37865: 'cls', 35321: 'x1', 35334: 'x2'}
CONT = {'p8': 31219, 'pr': 31271, 'pl': 31365, 'cls': 37868, 'x1': 35324, 'x2': 35337}
NENT = 24                   # events per frame (asm NENT)
COPY_RET = 32379            # the copy routine's RET
INTERIORS = (31214, 31216, 31217, 31218, 31269, 31270, 31363, 31364, 32155, 32156,
             37866, 37867, 35322, 35335)
SEQUELS = {31215: 31213, 35323: 35321, 35336: 35334}   # a site's 2-byte first instruction: the original runs on
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6,
          0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
FULL_RUNS = 20              # copy events run through e_cp in full; later ones start at post

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'nemesis_the_warlock.json'),
              os.path.join(_HERE, 'nemesis_the_warlock.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('nemesis_the_warlock.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_nemesis(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


class NemesisPatch:
    name = 'Nemesis the Warlock figures -> hardware sprites (hooks in a slot-1 RAM page)'

    def __init__(self, prof=None, page_code=None, colours=None):
        self.prof = prof or load_profile()
        self.colours = load_colours() if colours is None else colours
        h = self.prof['hooks']
        self.code = page_code or bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        if 0x2000 + len(self.code) != self.syms['page_end']:
            raise ValueError('profile page not assembled at 0x2000')
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 128
        self.slot1 = (PAGE, self.syms['regs'])
        page = bytearray(8192)
        page[:len(self.code)] = self.code
        self.page = bytes(page)
        self.sites = [(a, bytes.fromhex(old), b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]
        self.extra_banks = {PAGE // 2: self.page + bytes(8192)}
        self.cpages, self.ovr, self.cinfo = {}, {}, {}

    def prepare(self, peek):
        """Colour tables from the build's game memory (check bytes) -> extra banks 13-18."""
        self.cpages, self.ovr, self.cinfo = colour_tables(peek, self.colours, images(self.prof))
        for b in COLOUR_BANKS:
            self.extra_banks[b] = bytes(self.cpages[2 * b]) + bytes(self.cpages[2 * b + 1])

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Nemesis the Warlock patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        self.prepare(lambda a: ram[a - 0x4000] if a >= 0x4000 else 0)
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected version '
                                 'of Nemesis the Warlock' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


# ---------------------------------------------------------------------------------------------
# Next-side model: sprite attributes, 4-bit pattern memory, sprite palette
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.ptr = 0
        self.pal = {}
        self.bad = []
        self.sel = None                 # NextREG selected at port 0x243B (the speed latch reads NR 7)

    def copy(self):
        n = NextState()
        n.nr, n.attr, n.pat, n.ptr, n.pal = dict(self.nr), [list(a) for a in self.attr], \
            bytearray(self.pat), self.ptr, dict(self.pal)
        n.sel = self.sel
        return n

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x41:
            i = self.nr.get(0x40, 0)
            self.pal[i] = val
            if not self.nr.get(0x43, 0) & 0x80:
                self.nr[0x40] = (i + 1) & 255
        elif reg not in (0x34, 0x40, 0x43, 0x07, 0x50):
            self.bad.append(('nextreg', reg))

    def out(self, port, val):
        if port & 0xFF == 0x5B:
            self.pat[self.ptr & 0x3FFF] = val
            self.ptr += 1
        elif port == 0x303B:
            self.ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port == 0x243B:
            self.sel = val
        else:
            self.bad.append(('out', port))

    def layer(self):
        """Visible sprites -> {(x, y): nibble} inside the copy window (later sprites on top)."""
        out = {}
        for a0, a1, a2, a3, a4 in self.attr:
            if not a3 & 0x80:
                continue
            x0 = a0 + (a2 & 1) * 256 - 32
            y0 = a1 + ((a4 & 1) * 256 if a3 & 0x40 else 0) - 32
            base = (a3 & 0x3F) * 256 + (128 if a3 & 0x40 and a4 & 0x40 else 0)
            for py in range(16):
                y = y0 + (15 - py if a2 & 4 else py)
                if not WIN_Y[0] <= y < WIN_Y[1]:
                    continue
                for px in range(16):
                    b = self.pat[base + py * 8 + px // 2]
                    v = (b >> 4) if px % 2 == 0 else (b & 15)
                    if v:
                        x = x0 + (15 - px if a2 & 8 else px)
                        if WIN_X[0] <= x < WIN_X[1]:
                            out[(x, y)] = v
        return out


def _ula(y, col):
    return 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | col


def _rev(b):
    return int('{:08b}'.format(b)[::-1], 2)


def figure_writes(fig, peek):
    """Model of one plot: [(buffer address, mask byte, image byte, save-under address, wrapped)] in
    write order, bytes already mirrored for a left plot; wrapped = past column 31 (the byte lands on
    the next line's left edge: the hook leaves it on the ULA, as the original shows it)."""
    hl, iy, de, w, d = fig
    c0 = (hl - BUFBASE) & 31
    lines = 8 if w == 1 else 32
    img = de + {1: 8, 3: 96, 4: 128}[w]
    out = []
    k = 0
    for r in range(lines):
        for j in range(w):
            m, g = peek((de + r * w + j) & 0xFFFF), peek((img + r * w + j) & 0xFFFF)
            col = (w - 1 - j) if d else j
            if d:
                m, g = _rev(m), _rev(g)
            out.append(((hl + 32 * r + col) & 0xFFFF, m, g, (iy + k) & 0xFFFF, c0 + col > 31, r, j))
            k += 1
    return out


def _visible(a):
    o = (a - BUFBASE) & 0xFFFF
    y, c = o >> 5, o & 31
    if o < 4096 and y >= 8 and 2 <= c < 30:
        return y, c
    return None


def expected(figs, peek, ovr=None):
    """From the original state just after the copy, events = plots (tuples of 5) and XOR effects
    (('x', buffer address)): (expected ULA bytes {addr: v}, the original screen rebuilt from the
    background + events, expected sprite layer {(x, y): 1 ink / 2 paper})."""
    cur = {}
    get = lambda a: cur[a] if a in cur else peek(a)
    writes = [figure_writes(f, peek) if f[0] != 'x' else f for f in figs]
    ovr = ovr or {}
    fo = [ovr.get((f[2], f[3])) if f[0] != 'x' else None for f in figs]
    for ws in reversed(writes):                     # undo every event, last first
        if ws[0] == 'x':
            v = _visible(ws[1])
            if v:
                cur[_ula(*v)] = get(_ula(*v)) ^ 0x5A
            continue
        for a, m, g, s, wr, *_ in reversed(ws):
            v = _visible(a)
            if v and not wr:
                cur[_ula(*v)] = peek(s)
    bg = dict(cur)
    for ws in writes:                               # the XOR effects again: they stay on the ULA
        if ws[0] == 'x':
            v = _visible(ws[1])
            if v:
                cur[_ula(*v)] = get(_ula(*v)) ^ 0x5A
    scr = cur
    comp = dict(bg)
    gc = lambda a: comp[a] if a in comp else peek(a)
    lay = {}
    for ws, o, f in zip(writes, fo, figs):
        if ws[0] == 'x':
            v = _visible(ws[1])
            if v:
                comp[_ula(*v)] = gc(_ula(*v)) ^ 0x5A
            continue
        for a, m, g, s, wr, r, j in ws:
            v = _visible(a)
            if not v:
                continue
            sa = _ula(*v)
            comp[sa] = (gc(sa) & m) | g
            if wr:
                continue
            y, c = v
            for k in range(8):
                bit = 0x80 >> k
                px = 1 if g & bit else 2 if not m & bit else 0
                if o:                               # painted image: staging pixel of this screen pixel
                    sx = 8 * j + (7 - k if f[4] else k)
                    px = o.get((sx, r), px)
                if px:
                    lay[(c * 8 + k, y)] = px
    return scr, comp, lay


# ---------------------------------------------------------------------------------------------
# Patched runs
# ---------------------------------------------------------------------------------------------

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
    """Patched view: ROM below 0x2000, the hook page (persistent bytearray) at 0x2000-0x3FFF,
    patch sites, game memory read through get; game writes go to an overlay."""

    def __init__(s, get, page, psite, rom, ns=None, cpages=None):
        s.get, s.page, s.psite, s.rom, s.ov, s.romw = get, page, psite, rom, {}, 0
        s.ns, s.cp = ns, cpages or {}

    def __getitem__(s, a):
        if a < 0x2000:
            pg = s.ns.nr.get(0x50, 0xFF) if s.ns else 0xFF
            if pg == 0xFF:
                return s.rom[a]
            c = s.cp.get(pg)
            return c[a] if c else 0
        if a < 0x4000:
            return s.page[a - 0x2000]
        v = s.ov.get(a)
        if v is not None:
            return v
        v = s.psite.get(a)
        if v is not None:
            return v
        return s.get(a)

    def __setitem__(s, a, v):
        if a < 0x2000:
            s.romw += 1
        elif a < 0x4000:
            s.page[a - 0x2000] = v
        else:
            s.ov[a] = v

    def __len__(s):
        return 65536


def _machine(mem, regs, ns, slot='p'):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(_rw(), mem, regs, slot)
    R, ed = sim.registers, sim.after_ED

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs_, port):
            if port == 0x253B and ns.sel is not None:   # NextREG read: the hook's speed latch (NR 7)
                v = ns.nr.get(ns.sel, 0)
                return (v & 3) << 4 | (v & 3) if ns.sel == 0x07 else v
            ns.bad.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=2000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


class Engine:
    """Persistent patched state (hook page, Next state) + the model's figure log."""

    def __init__(self, patch):
        self.patch = patch
        self.page = bytearray(patch.page)
        self.ns = NextState()
        self.psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
        self.rom = _rom()
        self.figs = []
        self.tcost = []
        self.cpages, self.ovr = patch.cpages, patch.ovr

    def snapshot(self):
        return bytes(self.page), self.ns.copy(), list(self.figs)

    def restore(self, s):
        """Run-time state only: the page's bytes from code_end (this patch's code stays)."""
        k = self.patch.syms['code_end'] - 0x2000
        self.page[k:] = s[0][k:]
        self.ns, self.figs = s[1].copy(), list(s[2])


def plot_event(eng, kind, get, R):
    """Patched plot entry from the original's state at the site: same registers at the
    continuation, no game memory written; the model logs the figure."""
    f = []
    if kind == 'p8':
        fig = (R[6] << 8 | R[7], 32388, R[4] << 8 | R[5], 1, 0)
        ro = list(R)
        ro[2] = 8                       # B
        ro[8], ro[9] = 0, 8             # IXh, IXl
    else:
        m = get(51930)
        fig = (R[6] << 8 | R[7], R[10] << 8 | R[11], R[4] << 8 | R[5], 3 if m in (4, 5) else 4,
               1 if kind == 'pl' else 0)
        ro = list(R)
        ro[0] = m
    ro[24] = CONT[kind]
    if fig[1] >= 0x4000:            # save-under in ROM (IY = 0 at 0x7162): a permanent stamp = scenery
        eng.figs.append(fig)
    p = _PMem(get, eng.page, eng.psite, eng.rom, eng.ns, eng.cpages)
    sim = _machine(p, list(R), eng.ns)
    if not _run(sim, lambda r: r[24] == CONT[kind]):
        return ['plot hook did not return']
    rp = sim.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('plot: registers differ', diff[:6]))
    if [a for a in p.ov if not R[12] - 64 <= a < R[12]]:
        f.append(('plot: game memory written', len(p.ov)))
    return f


def xor_event(eng, kind, get, R):
    """Patched XOR effect (XOR 90 / LD (HL),A) from the original's state: same registers and the
    same game memory at the continuation; the model logs the event."""
    a = R[6] << 8 | R[7]
    eng.figs.append(('x', a))
    stop = (lambda r: r[24] == 35324) if kind == 'x1' else (lambda r: r[24] == 35337)
    o = _PMem(get, bytearray(8192), {}, eng.rom)
    so = _machine(o, list(R), NextState(), 'xo')
    p = _PMem(get, eng.page, eng.psite, eng.rom, eng.ns, eng.cpages)
    sim = _machine(p, list(R), eng.ns)
    if not (_run(so, stop) and _run(sim, stop)):
        return ['xor hook did not return']
    f = []
    diff = [i for i in CMP if so.registers[i] != sim.registers[i]]
    if diff:
        f.append(('xor: registers differ', diff[:6]))
    dead = range(R[12] - 64, R[12])
    md = [b for b in set(o.ov) | set(p.ov) if b not in dead and o[b] != p[b]]
    if md:
        f.append(('xor: game memory differs', md[:3]))
    return f


def cls_event(eng, get, R):
    eng.figs = []
    p = _PMem(get, eng.page, eng.psite, eng.rom, eng.ns, eng.cpages)
    sim = _machine(p, list(R), eng.ns)
    if not _run(sim, lambda r: r[24] == CONT['cls']):
        return ['cls hook did not return']
    f = []
    ro = list(R)
    ro[6], ro[7], ro[24] = 0x40, 0x00, CONT['cls']
    diff = [i for i in CMP if ro[i] != sim.registers[i]]
    if diff:
        f.append(('cls: registers differ', diff[:6]))
    if [a for a in p.ov if not R[12] - 64 <= a < R[12]]:
        f.append(('cls: game memory written', len(p.ov)))
    if any(a[3] & 0x80 for a in eng.ns.attr):
        f.append(('cls: sprite visible',))
    return f


def copy_event(eng, get, R, full, orig_end=None):
    """At the copy's RET (shortcut) or its entry (full). get = original memory AFTER the copy
    (shortcut) / BEFORE it (full). Returns (failures, sprite pixels compared)."""
    f = []
    sp0 = R[12]
    if full:
        # original: run the copy itself
        class O(dict):
            def __missing__(s, a):
                return get(a) if a >= 0x4000 else eng.rom[a]
        om = O()

        class OM:
            def __getitem__(s, a):
                return om[a]

            def __setitem__(s, a, v):
                if a >= 0x4000:
                    om[a] = v

            def __len__(s):
                return 65536
        from .simpool import machine
        so = machine(_rw(), OM(), list(R), 'o')
        ret = get(sp0) | get(sp0 + 1) << 8
        if not _run(so, lambda r: r[24] == ret and r[12] == sp0 + 2):
            return ['original copy did not return'], 0
        ro = list(so.registers)
        after = lambda a: om[a] if a in om else get(a)
        start = list(R)
    else:
        ret = get(sp0) | get(sp0 + 1) << 8
        ro = list(R)
        ro[24], ro[12] = ret, sp0 + 2
        after = get
        start = list(R)
        start[24] = eng.patch.syms['post']
    p = _PMem(after if not full else get, eng.page, eng.psite, eng.rom, eng.ns, eng.cpages)
    sim = _machine(p, start, eng.ns)
    if not _run(sim, lambda r: r[24] == ret and r[12] == sp0 + 2):
        return ['patched copy did not return'], 0
    rp = sim.registers
    t = rp[25] - start[25]
    eng.tcost.append(t)
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('copy: registers differ', diff[:6], [ro[i] for i in diff[:3]], [rp[i] for i in diff[:3]]))
    if p.romw:
        f.append(('patched code wrote ROM',))
    if eng.ns.nr.get(0x50, 0xFF) != 0xFF:
        f.append(('slot 0 not given back to the ROM', eng.ns.nr[0x50]))
    if eng.ns.bad:
        f.append(('port / nextreg outside the model', eng.ns.bad[:3]))
        eng.ns.bad = []
    figs, eng.figs = eng.figs, []
    scr, comp, lay = expected(figs, after, eng.ovr)
    dead = range(sp0 - 64, sp0 + 2)
    pv = (lambda a: p.ov[a] if a in p.ov else after(a))
    md = [a for a in p.ov if not 0x4000 <= a < 0x5800 and a not in dead and p.ov[a] != after(a)]
    if md:
        f.append(('copy: game memory differs', len(md), sorted(md)[:4]))
    # screen: window bytes = background model, everything else = original
    sd = [a for a in range(0x4000, 0x5800) if pv(a) != scr.get(a, after(a))]
    if sd:
        f.append(('copy: screen differs from the background model', len(sd), sd[:3]))
    cd = [a for a, v in comp.items() if v != after(a)]
    if cd:
        f.append(('model: original screen != background + figures (something else drew)', len(cd)))
    if len(figs) > NENT:
        f.append(('more than %d events in a frame' % NENT, len(figs)))
    got = eng.ns.layer()
    if got != lay:
        f.append(('sprite pixels differ from the model', len(set(got.items()) ^ set(lay.items()))))
    att = after(ROOMATT)
    br = 8 if att & 0x40 else 0
    want = {1: SPECCY[(att & 7) | br], 2: SPECCY[((att >> 3) & 7) | br]}
    if any(eng.ns.pal.get(k) != v for k, v in want.items()):
        f.append(('palette differs from the room attribute', att))
    return f, len(lay)


# ---------------------------------------------------------------------------------------------
# RZX replay
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None, cost=False):
    """Replay the RZX (original game); at every hook site run the patched code from the same
    state and compare. Returns (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False}
    eng = Engine(patch)
    cnt = collections.Counter()
    WATCH = set(SITE_KIND) | set(INTERIORS) | {COPY_RET} | set(SEQUELS)
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    def report(kind, fl):
        for k in fl:
            fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())

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
            get = lambda a: G(mem, a & 0xFFFF)
            pend = {}

            def mk(fn):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        kind = SITE_KIND.get(pc)
                        if kind == 'cp':
                            full = c['cp'] < FULL_RUNS
                            pend['cp'] = (list(R), eng.snapshot()) if full else None
                            if collect and c['collected cp'] < collect:
                                c['collected cp'] += 1
                                states.append(('cp', list(R), bytes(G(mem, a) for a in range(65536)),
                                               eng.snapshot()))
                            if full:
                                c['cp'] += 1
                                c['cp full'] += 1
                                fl, npx = copy_event(eng, get, R, True)
                                c['sprite pixels compared'] += npx
                                report('cp', fl)
                                pend['skip'] = True
                        elif pc == COPY_RET and cnt[32154]:
                            if pend.pop('skip', False):
                                pass
                            else:
                                c['cp'] += 1
                                fl, npx = copy_event(eng, get, R, False)
                                c['sprite pixels compared'] += npx
                                report('cp', fl)
                        elif kind in ('pr', 'pl', 'p8'):
                            c[kind] += 1
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((kind, list(R), bytes(G(mem, a) for a in range(65536)),
                                               eng.snapshot()))
                            report(kind, plot_event(eng, kind, get, R))
                        elif kind in ('x1', 'x2'):
                            c['xor'] += 1
                            report(kind, xor_event(eng, kind, get, R))
                        elif kind == 'cls':
                            c['cls'] += 1
                            report('cls', cls_event(eng, get, R))
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

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
    for a, site in SEQUELS.items():
        if cnt[a] != cnt[site]:
            c['%d reached other than after %d!' % (a, site)] += 1
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    if not 0 <= cnt[32154] - cnt[COPY_RET] <= 1:     # 1: the run stopped inside a copy
        c['copy RET reached other than from 32154 (%d / %d)!' % (cnt[COPY_RET], cnt[32154])] += 1
    c['frames'] = st['frame']
    if eng.tcost:
        c['hook T per copy (28 MHz T) max'] = max(eng.tcost)
        c['hook T per copy (28 MHz T) mean'] = sum(eng.tcost) // len(eng.tcost)
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests: positions / widths / directions the RZX may not reach, cache pressure, overflow,
# negative control
# ---------------------------------------------------------------------------------------------

def _unit_frame(patch, mem, R_cp, eng_state, figs_in, neg=False):
    """Plot figs_in (with the game's own plotters, original memory) then copy; check like the
    replay. Returns failures."""
    eng = Engine(patch)
    eng.restore(eng_state)
    eng.figs = []
    m = bytearray(mem)
    fl = []
    sp = R_cp[12]
    for fig in figs_in:
        if fig[0] == 'x':
            r = list(R_cp)
            r[6], r[7], r[0], r[24] = fig[1] >> 8, fig[1] & 255, m[fig[1]], 35334
            fl += xor_event(eng, 'x2', m.__getitem__, r)
            m[fig[1]] ^= 0x5A
            continue
        hl, iy, de, w, d = fig
        kind = 'p8' if w == 1 else ('pl' if d else 'pr')
        entry = {'p8': 31213, 'pr': 31268, 'pl': 31362}[kind]
        m[51930] = 4 if w == 3 else 0
        r = list(R_cp)
        r[6], r[7], r[4], r[5], r[10], r[11] = hl >> 8, hl & 255, de >> 8, de & 255, iy >> 8, iy & 255
        r[24] = entry
        r[12] = sp - 2
        m[sp - 2], m[sp - 1] = 0, 0          # return to 0 = stop
        fl += plot_event(eng, kind, m.__getitem__, r)
        so = _rw()(bytearray(m), {})
        so.registers[:] = r
        if not _run(so, lambda q: q[24] == 0):
            return ['unit plot did not return']
        m[0x4000:] = bytes(so.memory[0x4000:65536])
    # the copy, run in full on the original memory (plots done)
    r = list(R_cp)
    fl2, npx = copy_event(eng, m.__getitem__, r, True)
    return fl + fl2


def unit_tests(patch, states, neg=None):
    """states from verify(collect=n). From a captured copy state: figures at the window edges in
    every width / direction, a frame with more figures than slots in use (cache eviction), the
    16-figure limit; neg: a broken patch that must FAIL."""
    c = collections.Counter()
    cps = [s for s in states if s[0] == 'cp']
    plots = [s for s in states if s[0] in ('pr', 'pl')]
    if not cps or not plots:
        c['no captured copy / plot state!'] += 1
        return c
    kind, R, mem, es = cps[-1]
    de = plots[0][1][4] << 8 | plots[0][1][5]      # a real figure graphic
    de8 = 32412
    save = 0xC000
    for w in (4, 3):
        for d in (0, 1):
            for line in (-8, 0, 7, 8, 60, 96, 104):     # 32 lines from 104 end at the buffer's last line
                for col in (0, 1, 2, 15, 26, 27, 28, 29, 30):
                    hl = (BUFBASE + 32 * line + col) & 0xFFFF
                    fl = _unit_frame(patch, mem, R, es, [(hl, save, de, w, d)])
                    c['edge cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                    if fl and c['  fail example'] < 3:
                        c['  fail example'] += 1
                        c['  w %d d %d line %d col %d %s' % (w, d, line, col, str(fl[:2])[:150])] += 1
    for line in (0, 8, 64, 125):
        for col in (1, 2, 29, 31):
            hl = BUFBASE + 32 * line + col
            fl = _unit_frame(patch, mem, R, es, [(hl, 32388, de8, 1, 0)])
            c['8x8 cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    # overlapping figures, mixed directions, 16 in one frame (each its own save area)
    figs = [((BUFBASE + 32 * (10 + 6 * k) + 3 + k) & 0xFFFF, 0xC000 + 128 * k, de + 256 * (k % 3), 4 - (k % 2),
             k % 2) for k in range(16)]
    fl = _unit_frame(patch, mem, R, es, figs)
    c['16 overlapping figures %s' % ('ok' if not fl else 'FAIL!')] += 1
    if fl:
        c['  16 figures: %s' % str(fl[:2])[:150]] += 1
    # XOR effects: inside a figure after its plot, outside any figure, before a plot
    x0 = figs[0][0] + 32 * 5 + 1
    fl = _unit_frame(patch, mem, R, es, [('x', BUFBASE + 32 * 50 + 9), figs[0], ('x', x0), figs[1],
                                         ('x', x0 + 32)])
    c['xor effects %s' % ('ok' if not fl else 'FAIL!')] += 1
    if fl:
        c['  xor: %s' % str(fl[:2])[:150]] += 1
    # a permanent stamp (save-under IY = 0, 0x7162) under two figures: scenery, no sprite
    fl = _unit_frame(patch, mem, R, es, [(figs[0][0], 0, de, 4, 1)] + figs[:2])
    c['stamp (IY = 0) stays scenery %s' % ('ok' if not fl else 'FAIL!')] += 1
    fl = _unit_frame(patch, mem, R, es, figs + figs[:9])
    c['25 figures: limit reported %s' % ('ok' if any('more than 24' in str(x) for x in fl) else 'FAIL!')] += 1
    if neg is not None:
        fl = _unit_frame(neg, mem, R, es, figs[:4])
        c['negative control %s' % ('detected' if fl else 'NOT DETECTED!')] += 1
    return c


def colour_paint(de, w, get, seed=0):
    """Synthetic colour map over image (de, w): about a third of the pixels a colour 1-15, a sixth
    transparent (keys shared with any other image drawing the same bytes)."""
    cmap = {}
    for (x, r), (key, bit, ma, ga) in image_keys(de, w).items():
        h = (x * 7 + r * 13 + seed * 5 + de) % 12
        e = cmap.setdefault(key, [get(ga), 'g', [0] * 8, 0])
        if h < 4:
            e[2][bit] = 1 + (x + r + seed) % 15
        elif h < 6:
            e[3] |= 0x80 >> bit
    return cmap


def _painted(patch, cmap, get, imgs, strip=None, blank=False):
    prof = dict(patch.prof, colour_images=list(patch.prof.get('colour_images', [])) +
                ['%04X:%d' % i for i in imgs])
    p = NemesisPatch(prof, patch.code, colours=cmap)
    p.prepare(get)
    if strip:                       # the tables from a map without the transparent masks
        q = NemesisPatch(prof, patch.code, colours={k: v[:3] for k, v in cmap.items()})
        q.prepare(get)
        p.cpages = q.cpages
    if blank:
        p.cpages = {}
    return p


def colour_cases(patch, states):
    """Painted images through the hook's tables: every width / direction at the window edges, the
    transparent mask, a wrong check byte (ignored); negative controls: tables left out of the build,
    transparent masks left out."""
    c = collections.Counter()
    cps = [s for s in states if s[0] == 'cp']
    plots = [s for s in states if s[0] in ('pr', 'pl')]
    if not cps or not plots:
        c['no captured copy / plot state!'] += 1
        return c
    kind, R, mem, es = cps[-1]
    get = mem.__getitem__
    de = plots[0][1][4] << 8 | plots[0][1][5]
    de8 = 32412
    cmap = {}
    for i, (g, w) in enumerate(((de, 4), (de, 3), (de8, 1))):
        cmap.update(colour_paint(g, w, get, i))
    imgs = [(de, 4), (de, 3), (de8, 1)]
    p = _painted(patch, cmap, get, imgs)
    c['colour: images painted %d' % p.cinfo['images with colours']] += 1
    for w in (4, 3):
        for d in (0, 1):
            for line in (-8, 0, 60, 104):
                for col in (1, 2, 15, 28, 30):
                    hl = (BUFBASE + 32 * line + col) & 0xFFFF
                    fl = _unit_frame(p, mem, R, es, [(hl, 0xC000, de, w, d)])
                    c['colour cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                    if fl and c['  colour fail example'] < 3:
                        c['  colour fail example'] += 1
                        c['  colour w %d d %d line %d col %d %s' % (w, d, line, col, str(fl[:2])[:150])] += 1
    for col in (2, 17, 29):
        fl = _unit_frame(p, mem, R, es, [(BUFBASE + 32 * 40 + col, 32388, de8, 1, 0)])
        c['colour cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    figs = [((BUFBASE + 32 * (10 + 6 * k) + 3 + k) & 0xFFFF, 0xC000 + 128 * k, de, 4 - (k % 2), k % 2)
            for k in range(6)]
    fl = _unit_frame(p, mem, R, es, figs)
    c['colour overlapping figures %s' % ('ok' if not fl else 'FAIL!')] += 1
    bad = {k: [v[0] ^ 1] + v[1:] for k, v in cmap.items()}
    pb = _painted(patch, bad, get, imgs)
    c['colour: wrong check byte ignored %s' % ('ok' if not pb.ovr and
                                                 pb.cinfo['map entries ignored (check byte differs)'] else 'FAIL!')] += 1
    fl = _unit_frame(pb, mem, R, es, figs[:2])
    c['colour: wrong check byte -> default colours %s' % ('ok' if not fl else 'FAIL!')] += 1
    for what, kw in (('tables left out', {'blank': True}), ('transparent masks left out', {'strip': True})):
        n = _painted(patch, cmap, get, imgs, **kw)
        fl = _unit_frame(n, mem, R, es, figs[:2])
        c['colour negative (%s) %s' % (what, 'detected' if fl else 'NOT DETECTED!')] += 1
    return c


def negative_patch(patch):
    """Broken build: the nibble table's paper pixels (value 2) become transparent, so solid outlines
    vanish - the sprite pixel check must fail."""
    q = NemesisPatch(patch.prof)
    code = bytearray(q.code)
    i = q.syms['nib'] - 0x2000
    for k in range(i, i + 512):
        b = code[k]
        code[k] = (0 if b >> 4 == 2 else b & 0xF0) | (0 if b & 15 == 2 else b & 15)
    return NemesisPatch(patch.prof, bytes(code))


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : nemesis (Nemesis the Warlock: masked buffer plotters 31213 / 31268 / 31362 -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = back buffer, written before read)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = NemesisPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    say('Colours   : %s' % (', '.join('%s %d' % kv for kv in sorted(patch.cinfo.items())) if patch.colours
                            else 'no colour map: default colours (room ink / paper)'))
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=2, cost=True)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, copies %d (%d full), plots right %d left %d 8x8 %d, clears %d, '
            'xor effects %d, %d sprite pixels -> %s' % (os.path.basename(r), c['frames'], c['cp'], c['cp full'], c['pr'],
                                        c['pl'], c['p8'], c['cls'], c['xor'], c['sprite pixels compared'],
                                        'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        if c['hook T per copy (28 MHz T) max']:
            say('Speed     : post-copy hook %d T mean, %d T max at 28 MHz (~%d / %d T at 3.5 MHz; a frame is '
                '69,888 T)' % (c['hook T per copy (28 MHz T) mean'], c['hook T per copy (28 MHz T) max'],
                               c['hook T per copy (28 MHz T) mean'] // 6, c['hook T per copy (28 MHz T) max'] // 6))
    if states:
        u = unit_tests(patch, states, negative_patch(patch))
        cc = colour_cases(patch, states)
        u.update(cc)
        say('Colour    : %s' % ', '.join('%s %d' % (k, v) for k, v in sorted(cc.items()) if not k.startswith('  ')))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : edges %d, 8x8 %d, 16 figures %d, xor %d, stamp %d, negative control %d/%d -> %s' % (
            u['edge cases ok'], u['8x8 cases ok'], u['16 overlapping figures ok'], u['xor effects ok'],
            u['stamp (IY = 0) stays scenery ok'],
            u['negative control detected'], u['negative control detected'] + u['negative control NOT DETECTED!'],
            'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in u.items():
            if k.startswith('  '):
                say('           %s' % k)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Colour map (docs/COLOURS.md; card patch.runtime-colour-map): sheets, tables, recolour
# ---------------------------------------------------------------------------------------------
# Patterns are built at run time (build, on a cache miss) from (graphic, width). Per painted image
# the build stores an AND / OR stream, one pair per pattern byte in build's output order (4 patterns
# x 16 rows x 8 bytes): byte = (default AND a) OR o. Index (count, then g lo, g hi, w, page, address
# at slot 0) at the start of page CPG; streams after it, pages CPG..CPG+NCP-1, mapped at slot 0 only
# while build writes the patterns. Keys: the IMAGE byte ('%04X', check = its value; the mask byte
# beside it is fixed by the graphic), bit 0 = leftmost as stored. Pixel codes: 1 ink (palette 1 =
# room ink), 2 solid paper (palette 2 = room paper), 0 clear; palette 3-15 fixed (FIXED).
import hashlib

RECORD = 'nemesis_the_warlock'
CPG, NCP = 26, 12                       # colour pages (banks 13-18; 95 images); never mapped by the game
COLOUR_BANKS = tuple(range(CPG // 2, (CPG + NCP) // 2))
CIDX = 0x0400                           # streams start after the index (1 + 6 x <= 170 entries)
SLEN = 1024                             # stream bytes per image
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')
# palette 3-15: Spectrum colours (index into SPECCY); bright blue / bright cyan left out (16 > 15)
FIXED = [0, 1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 14, 15]
GOFF = {1: 8, 3: 96, 4: 128}            # image offset from the mask per width


def capture(rzx_path, stop=None):
    """Replay the RZX (C simulator): every figure image the plotters draw as a sprite (stamps with
    IY in ROM excluded) -> ({(de, w): {'count', 'frame', 'att': Counter of room attributes,
    'changed': graphics bytes differing from the first draw}}, frames, error)."""
    from .rzx import trace
    seen, fr = {}, [0]

    def on(pc, sim):
        if pc == 32154:
            fr[0] += 1
            return
        m, r = sim.memory, sim.registers
        de = r[4] << 8 | r[5]
        if pc == 31213:
            w = 1
        else:
            if (r[10] << 8 | r[11]) < 0x4000:
                return
            w = 3 if m[51930] in (4, 5) else 4
        lines = 8 if w == 1 else 32
        gb = bytes(m[(de + i) & 0xFFFF] for i in range(GOFF[w] + lines * w))
        e = seen.get((de, w))
        if e is None:
            e = seen[(de, w)] = {'count': 0, 'frame': fr[0], 'att': collections.Counter(), 'bytes': gb,
                                 'changed': 0}
        elif e['bytes'] != gb:
            e['changed'] += 1
        e['count'] += 1
        e['att'][m[ROOMATT]] += 1

    frames, err = trace(rzx_path, (31213, 31268, 31362, 32154), on, stop=stop)
    return seen, frames, err


def images(prof=None):
    """The images the game draws as sprites (whole-RZX capture, profile 'colour_images'): [(de, w)]."""
    out = []
    for s in (prof or load_profile()).get('colour_images', []):
        g, w = s.split(':')
        out.append((int(g, 16), int(w)))
    return out


def image_keys(de, w):
    """Staging pixel (x, r) of image (de, w) -> (key, bit, mask address, image address)."""
    lines = 8 if w == 1 else 32
    out = {}
    for r in range(lines):
        for x in range(8 * w):
            ga = (de + GOFF[w] + r * w + x // 8) & 0xFFFF
            out[(x, r)] = ('%04X' % ga, x & 7, (de + r * w + x // 8) & 0xFFFF, ga)
    return out


def load_colours():
    from . import coloursheet as cs
    from .recolour import build_colours_path
    p = build_colours_path(COLOURS)
    return cs.load(p) if os.path.exists(p) else {}


def colour_tables(get, cmap, imgs):
    """Colour map -> ({page: bytearray} pages CPG.., {(de, w): {(x, r): nibble, 0 = transparent}},
    info). A key whose check byte is not the graphic's byte (or get None) is ignored."""
    pages = {p: bytearray(8192) for p in range(CPG, CPG + NCP)}
    ovr, idx, info = {}, [], collections.Counter()
    pg, off = CPG, CIDX
    used, bad = set(), set()
    for de, w in imgs:
        o = {}
        for (x, r), (key, bit, ma, ga) in image_keys(de, w).items():
            e = cmap.get(key)
            if not e:
                continue
            if get is None or get(ga) != e[0]:
                bad.add(key)
                continue
            used.add(key)
            if len(e) > 3 and e[3] & (0x80 >> bit):
                o[(x, r)] = 0
            elif e[2][bit]:
                o[(x, r)] = e[2][bit]
        if not o:
            continue
        if off + SLEN > 8192:
            pg, off = pg + 1, 0
            if pg >= CPG + NCP:
                raise ValueError('colour tables need more than %d pages' % NCP)
        data = bytearray(SLEN)
        for i in range(0, SLEN, 2):
            data[i] = 0xFF
        for (x, r), v in o.items():
            q = (r // 16) * 2 + x // 16
            n = q * 128 + (r % 16) * 8 + (x % 16) // 2
            sh = 4 if not x & 1 else 0
            data[2 * n] &= ~(15 << sh) & 0xFF
            data[2 * n + 1] |= v << sh
        pages[pg][off:off + SLEN] = data
        idx.append((de, w, pg, off))
        ovr[(de, w)] = o
        off += SLEN
    if len(idx) * 6 + 1 > CIDX:
        raise ValueError('colour index full')
    p = pages[CPG]
    p[0] = len(idx)
    for i, (de, w, pgn, ad) in enumerate(idx):
        p[1 + 6 * i:7 + 6 * i] = bytes((de & 255, de >> 8, w, pgn, ad & 255, ad >> 8))
    info.update({'images with colours': len(idx), 'map entries used': len(used),
                 'map entries ignored (check byte differs)': len(bad),
                 'map entries for no known image': len(set(cmap) - used - bad)})
    return pages, ovr, info


def colour_inputs_md5(get, prof=None):
    """MD5 + count of the graphics bytes (mask + image) of every known image."""
    seen = set()
    for de, w in images(prof):
        seen.update((de + i) & 0xFFFF for i in range(GOFF[w] + (8 if w == 1 else 32) * w))
    return hashlib.md5(bytes(get(a) for a in sorted(seen))).hexdigest(), len(seen)


def colour_identity(peek, prof=None):
    """What a colour map / sheet layout means (docs/COLOURS.md "Identity"): key = image byte
    (%04X), bit = pixel (0 = leftmost as stored); geometry = the image list (profile colour_images)."""
    prof = prof or load_profile()
    geo = hashlib.md5(json.dumps(prof.get('colour_images', [])).encode()).hexdigest()
    return {'schema': 1, 'game': RECORD, 'engine': 'nemesis',
            'keys': 'nemesis-1: %04X image byte, bit = pixel; mask byte fixed by the graphic',
            'inputs': colour_inputs_md5(peek, prof)[0], 'geometry': geo}


NOTE = ('Nemesis the Warlock colour map (docs/COLOURS.md): key = image byte (hex address; check = its '
        'value); 8 nibbles, 0 = default (1 room ink / 2 room paper / clear); palette 3-15 fixed; optional '
        '4th = transparent mask')
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/%s_colours.json' % RECORD,
            'clear': True, 'note': NOTE}


def recolour(nex, cmap):
    """Built Nemesis sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is
    not this engine's build of the expected snapshot (sites, hook page, graphics)."""
    from .recolour import nex_offsets
    d = bytearray(nex)
    off = nex_offsets(d)
    need = set(COLOUR_BANKS) | {5, 2, 0, PAGE // 2}
    if not need <= set(off):
        raise ValueError('not a Nemesis the Warlock sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000] if a >= 0x4000 else 0
    prof = load_profile()
    want = prof.get('colour_inputs', {})
    got = colour_inputs_md5(peek, prof)
    if [want.get('md5'), want.get('bytes')] != list(got):
        raise ValueError('game graphics differ from the expected snapshot (%s / %d bytes, expected %s)'
                         % (got[0], got[1], want))
    p = NemesisPatch(prof, colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site %d does not hold this build\'s hook jump' % a)
    if bank(PAGE // 2) != p.extra_banks[PAGE // 2]:
        raise ValueError('hook page differs from this version\'s (rebuild with nexclash.py auto)')
    p.prepare(peek)
    changed = []
    for b in COLOUR_BANKS:
        if bank(b) != p.extra_banks[b]:
            changed.append(b)
        d[off[b]:off[b] + 16384] = p.extra_banks[b]
    info = {'banks changed': changed}
    info.update({k: v for k, v in p.cinfo.items() if v})
    return bytes(d), info


def image_part(get, de, w, ink, paper):
    """The coloursheet part of image (de, w): every staging pixel; code 1 ink (palette 1), 2 solid
    paper (palette 2), 0 clear (paintable: paint_clear)."""
    px, ent = [], {}
    for (x, r), (key, bit, ma, ga) in sorted(image_keys(de, w).items(), key=lambda t: (t[0][1], t[0][0])):
        b = 0x80 >> bit
        code = 1 if get(ga) & b else 2 if not get(ma) & b else 0
        px.append((x, r, key, bit, code, {1: 1, 2: 2, 0: 0}[code]))
        ent[key] = [get(ga), 'g']
    return {'id': '%04X:%d' % (de, w), 'size': 1, 'w': 8 * w, 'h': 8 if w == 1 else 32, 'x': 0, 'y': 0,
            'mir': 0, 'pixels': px, 'entries': ent}


def _start_mem(z80):
    from skoolkit.snapshot import get_snapshot
    return bytearray(get_snapshot(z80))


def sheet_palette(att):
    """16 Next colours of the sheet: 1 / 2 = the room attribute's ink / paper, 3-15 FIXED."""
    br = 8 if att & 0x40 else 0
    return [0, SPECCY[(att & 7) | br], SPECCY[((att >> 3) & 7) | br]] + [SPECCY[i] for i in FIXED]


def sheets(rzx_path, z80, out_dir, prefix='nemesis_the_warlock', colours=None, stop=None, say=print):
    """<prefix>_PAINTING_SPRITES.png (the fewest whole figures showing every graphics byte) +
    _REFERENCE_ALL_SPRITES.png (every image), each with its _layout.json; shown in the most common
    room colours (palette 1 / 2)."""
    from . import coloursheet as cs
    seen, frames, err = capture(rzx_path, stop)
    if err:
        say('capture   : stopped at frame %d: %s' % (frames, err))
    mem = _start_mem(z80)
    get = lambda a: mem[a & 0xFFFF]
    att = collections.Counter()
    comps = []
    for (de, w), e in sorted(seen.items(), key=lambda t: t[1]['frame']):
        att.update(e['att'])
        p = image_part(get, de, w, 1, 2)
        p.update(dx=0, dy=0, dmir=0, vmir=0, group=0)
        comps.append({'count': e['count'], 'group': 0, 'parts': [p]})
    cmap = colours if colours is not None else load_colours()
    rgb = cs.palette_rgb(sheet_palette(att.most_common(1)[0][0]))
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json',
                  rgb, colours=cmap, paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json',
                  rgb, colours=cmap, paint_clear=True, identity=ident)
    say('Sheets    : %d images seen in %d frames; painting sheet %d figures, reference %d; room attribute '
        'shown %d' % (len(seen), frames, n1, n2, att.most_common(1)[0][0]))
    return seen


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.nemesis')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX + snapshot -> the colour sheets (docs/COLOURS.md)')
    p.add_argument('rzx')
    p.add_argument('z80')
    p.add_argument('-o', '--out', default='.')
    p.add_argument('--stop', type=int)
    p = sub.add_parser('images', help='RZX -> the image list for the profile (colour_images, colour_inputs)')
    p.add_argument('rzx')
    p.add_argument('z80')
    a = ap.parse_args(argv)
    if a.cmd == 'sheet':
        sheets(a.rzx, a.z80, a.out, stop=a.stop)
    elif a.cmd == 'images':
        seen, frames, err = capture(a.rzx)
        if err or any(e['changed'] for e in seen.values()):
            raise SystemExit('capture: %s; graphics changed: %d' % (err, sum(e['changed'] for e in seen.values())))
        prof = load_profile()
        prof['colour_images'] = ['%04X:%d' % k for k in sorted(seen)]
        mem = _start_mem(a.z80)
        m, n = colour_inputs_md5(lambda x: mem[x & 0xFFFF], prof)
        prof['colour_inputs'] = {'md5': m, 'bytes': n}
        json.dump(prof, open(_profile_path(), 'w'), indent=1)
        print('profile: %d images, inputs %s / %d bytes' % (len(seen), m, n))


if __name__ == '__main__':
    main()
