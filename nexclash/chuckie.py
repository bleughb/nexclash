"""Chuckie Egg (A&F Software, 1983, 48K) engine 'chuckie'. Additive module: reachable only
through is_chuckie().

Game facts (analysis passes over Chuckie_Egg_1983_A__F_Software_a.z80 and Dean's RZX; details in
games/chuckie_egg.md):
  39500  player AND duck plotter: A = frame (gfx 36336 + 32A, 16 rows x 2 bytes, top down),
         L = x pixel, H = 191 - top line. Builds the frame shifted in a 24x16 buffer (29344), ORs it
         with the background tiles composed from the map (29405), overwrites the 3x16 screen block
         (39758) and paints attribute 6 (39827). Caller return address 41238 / 41361 = duck.
  37532  hen plotter (one call per hen per frame): A = 0 -> erase = tile redraw (37727), else draw:
         gfx 36878 + 32A' (A' = A adjusted by x/y bit 2), 16 rows x 2 bytes drawn bottom up with OR
         from line 191 - H (37645/37653), x byte L / 8, nothing drawn when L >= 249; attribute 5
         (37707). Skips both when the hen overlaps the player. Caller DE = hen table entry 29527+4i.
  No game logic reads the screen (only the title scroller 43899 and the OR plotter itself);
  collision uses coordinates (39838) and the map (40500). Interrupts are enabled at every hook site.
Hooks (asm/chuckie_hooks.asm, all in alt ROM image 1, stateless): the plotters keep running, only
their screen pixel/attribute writes are removed; each plot sets one hardware sprite (hens 0-4,
duck 5, player 6); hen erase and screen clears hide sprites.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00          # printer buffer: zero in the snapshot, never touched in the RZX
BUF = (29344, 29392)        # player frame buffer: only the plotter reads it (written first)
GFX_P, GFX_H = 36336, 36878
HENTAB = 29527
SPR_DUCK, SPR_PLAY = 5, 6
NPAT = 48
DUCK_RETS = (41238, 41361)
TILES = (34032, 34032 + 2048)   # tile graphics (background); zeroed for the canvas run
SITES_ORIG = {39500: 'f5c5d5', 37635: 'cd0494', 37727: 'dd2e02', 43934: '21ff5a', 44700: '21ff5a',
              42403: '210040', 42946: '210040', 43442: '010018'}
SITE_SYM = {39500: 'e_pl', 37635: 'e_hd', 37727: 'e_he', 43934: 'e_c1', 44700: 'e_c2', 42403: 'e_c3',
            42946: 'e_c4', 43442: 'e_c5'}
SITE_OP = {37635: 0xCD}     # CALL; every other site JP
SCREEN_PATCHES = [(39697, '1ab6', '7e00'), (39827, '3606', '0000'), (37646, '77', '00'),
                  (37653, '77', '00'), (37707, '3605', '0000')]
# bytes that must never be executed as an instruction start (interiors of patched instructions)
INTERIORS = (39501, 39502, 37728, 37729, 39828, 37708, 43935, 43936, 44701, 44702, 42404, 42405,
             42947, 42948, 43443, 43444)
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6]

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'chuckie_egg.json'),
              os.path.join(_HERE, 'chuckie_egg.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('chuckie_egg.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_chuckie(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


# ---------------------------------------------------------------------------------------------
# Patterns: 0-31 player/duck frame A, 32-47 hen block A' (1 = ink, 0 = transparent)
# ---------------------------------------------------------------------------------------------

def frame_rows(peek, p):
    """16 rows of 16 bits (top down) for pattern p."""
    if p < 32:
        a = GFX_P + 32 * p
        return [peek(a + 2 * r) << 8 | peek(a + 2 * r + 1) for r in range(16)]
    a = GFX_H + 32 * (p - 32)
    return [peek(a - 2 * (15 - r)) << 8 | peek(a - 2 * (15 - r) + 1) for r in range(16)]


def patterns(peek):
    out = bytearray()
    for p in range(NPAT):
        for row in frame_rows(peek, p):
            for k in range(0, 16, 2):
                hi = (row >> (15 - k)) & 1
                lo = (row >> (14 - k)) & 1
                out.append(hi << 4 | lo)
    return bytes(out)


def sprite_pixels(attr, pat):
    """Visible 4-bit anchor sprite -> set of (x, y) ink pixels in ULA coordinates."""
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return set()
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
    out = set()
    for j in range(16):
        for k in range(16):
            b = pat[base + j * 8 + k // 2]
            if (b >> 4) if k % 2 == 0 else (b & 15):
                out.add((x + k, y + j))
    return out


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

class ChuckiePatch:
    name = 'Chuckie Egg player/duck/hens -> hardware sprites (altrom, stateless hooks)'

    def __init__(self, prof=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
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
        for a, old in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old),
                               bytes([SITE_OP.get(a, 0xC3)]) + self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.pats = None
        self.num_patterns = NPAT

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Chuckie Egg patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + 256]):
            raise ValueError('printer buffer is not empty in this snapshot (tail site)')
        self.pats = patterns(lambda a: ram[a - 0x4000])
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        pats = self.pats + bytes(16384 - len(self.pats))
        self.extra_banks = {11: pats, 12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Next-side state and event runner (original vs patched from one state)
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, pats):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(pats) + bytes(16384 - len(pats))
        self.events = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def pixels(self, i):
        return sprite_pixels(self.attr[i], self.pat)


def _machine(Sim, mem, regs, ns, slot='o'):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)
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
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.events.append(('out', port, value))
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=300000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


class _Pair:
    """Original / patched / canvas overlays over one live 48K memory (read through get)."""

    def __init__(self, patch, get, alt):
        self.patch, self.get, self.alt = patch, get, alt
        self.psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}


def _overlays(pair, canvas=None):
    get, alt, psite = pair.get, pair.alt, pair.psite

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            if v is not None:
                return v
            if canvas is not None and canvas[0] <= a < canvas[1]:
                return 0
            return get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', 0) + 1
            else:
                s.ov[a] = v
    return O, P


def _screen_set(ov, lo=0x4000, hi=0x5800):
    """Ink pixels written (value bits set) in the pixel area of an overlay -> {(x, y)}."""
    out = set()
    for a, v in ov.items():
        if lo <= a < hi:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                if (v >> (7 - k)) & 1:
                    out.add(((a & 31) * 8 + k, y))
    return out


def event(patch, kind, get, R, ns, alt, Sim):
    """Run one hook event (original and patched, plus a canvas run of the original) from the same
    state. kind: 'pl' (39500), 'hd' (37635), 'he' (37727), 'cls' (site). Returns failure list."""
    pair = _Pair(patch, get, alt)
    sp0 = R[12]
    w = lambda a: get(a) | get(a + 1) << 8
    f = []
    if kind == 'pl':
        ret = w(sp0)

        def stop(r):
            return (r[24] == ret and r[12] == sp0 + 2) or (r[12] > sp0 and not 39500 <= r[24] < 39935
                                                           and r[24] >= 0x4000)
        spr = SPR_DUCK if ret in DUCK_RETS else SPR_PLAY
        canvas = TILES
    elif kind in ('hd', 'he'):
        ret = w(sp0 + 8)
        end = sp0 + 10

        def stop(r):
            return r[24] == ret and r[12] == end
        de = w(sp0 + 4)
        idx = (de - HENTAB) >> 2 if 0 <= de - HENTAB < 20 else None
        spr = idx
        canvas = (0x4000, 0x5800)
    else:
        nxt = R[24] + 3

        def stop(r):
            return r[24] == nxt
        spr, canvas = None, None
    O, P = _overlays(pair)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    before = [list(a) for a in ns.attr]
    ns.events = []
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if not (_run(so, stop) and _run(sp_, stop)):
        return ['did not return'], 0
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access in hook',))
    if any(e[1] not in (0x34, 0x35, 0x36, 0x37, 0x38, 0x39) for e in ns.events):
        f.append(('NEXTREG other than sprite attributes',))
    spend = ro[12]
    dead = range(spend - 64, spend)                 # below the final SP: dead stack
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not 0x4000 <= a < 0x5B00 and a not in dead and o[a] != p[a]
          and not (kind == 'pl' and BUF[0] <= a < BUF[1])]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    if kind in ('he', 'cls'):
        sd = [a for a in keys if 0x4000 <= a < 0x5B00 and o[a] != p[a]]
        if sd:
            f.append(('screen writes differ', len(sd)))
    npx = 0
    if kind in ('pl', 'hd'):
        if any(0x5800 <= a < 0x5B00 for a in p.ov):
            f.append(('patched code wrote attributes',))
        # canvas run: original with background (player) / screen (hens) zero -> its exact pixels
        Oc, _ = _overlays(pair, canvas)
        oc = Oc()
        sc = _machine(Sim, oc, list(R), NextState(b''), 'c')
        if not _run(sc, stop):
            return f + ['canvas run did not return'], 0
        if kind == 'pl':
            region = {a for a in o.ov if 0x4000 <= a < 0x5800}
            drawn = _screen_set({a: oc.ov[a] for a in region if a in oc.ov})
            # patched screen = original screen without the figure: orig = patched | figure
            for a in region:
                if o.ov[a] != p.ov.get(a, -1) | (oc.ov.get(a, 0)):
                    f.append(('screen block: original != background | figure', a))
                    break
        else:
            drawn = _screen_set(oc.ov)
            if any(0x4000 <= a < 0x5800 for a in p.ov):
                f.append(('patched hen draw wrote the screen',))
        if spr is None:
            if drawn:
                f.append(('figure drawn but no sprite slot', len(drawn)))
        else:
            got = {(x, y) for x, y in ns.pixels(spr) if 0 <= x < 256 and 0 <= y < 192}
            npx = len(drawn)
            if got != drawn:
                f.append(('sprite pixels differ from the original plot', len(got ^ drawn)))
        changed = [i for i in range(128) if ns.attr[i] != before[i] and i != spr]
        if changed:
            f.append(('other sprites changed', changed[:4]))
    elif kind == 'he':
        if spr is not None and ns.attr[spr][3] & 0x80:
            f.append(('hen sprite still visible after erase', spr))
        changed = [i for i in range(128) if ns.attr[i] != before[i] and i != spr]
        if changed:
            f.append(('other sprites changed', changed[:4]))
    else:
        if any(ns.attr[i][3] & 0x80 for i in range(SPR_PLAY + 1)):
            f.append(('sprite visible after screen clear',))
    return f, npx


SITE_KIND = {39500: 'pl', 37635: 'hd', 37727: 'he', 43934: 'cls', 44700: 'cls', 42403: 'cls',
             42946: 'cls', 43442: 'cls'}


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX (original game); at every hook site run original and patched code from the
    same state and compare. Returns (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False}
    ns = NextState(patch.pats)
    cnt = collections.Counter()
    WATCH = set(SITE_KIND) | set(INTERIORS)
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
                        cnt[pc] += 1
                        kind = SITE_KIND.get(pc)
                        if kind:
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((kind, list(R), bytes(G(mem, a) for a in range(65536)),
                                               [list(x) for x in ns.attr]))
                            fl, npx = event(patch, kind, get, R, ns, alt, _rw())
                            c[kind] += 1
                            c['sprite pixels compared'] += npx
                            for k in fl:
                                fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k),
                                     k[1:] if isinstance(k, tuple) else ())
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
    if not (cnt[39500] == cnt[39501] == cnt[39502]):
        c['39501/39502 reached other than from 39500!'] += 1
    for a in INTERIORS:
        if a not in (39501, 39502) and cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


# ---------------------------------------------------------------------------------------------
# Unit tests: every frame, edge positions, guards, hens outside the table, negative control
# ---------------------------------------------------------------------------------------------

def unit_tests(patch, states, neg=None):
    """states from verify(collect=n): (kind, registers, 64K memory, sprite attrs). Player/duck:
    frames 0-31 x edge positions; hens: A' 0-15 (via DE), x incl. >= 249, entries outside the
    table; screen clears. neg: a broken patch that must FAIL."""
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()

    def one(pt, kind, R, mem, attrs, alt_=alt):
        ns = NextState(pt.pats)
        ns.attr = [list(a) for a in attrs]
        return event(pt, kind, mem.__getitem__, R, ns, alt_, Sim)

    for kind, R, mem, attrs in states:
        mem = bytearray(mem)
        if kind == 'pl':
            ret = mem[R[12]] | mem[R[12] + 1] << 8
            for duck in (False, True):
                m2 = bytearray(mem)
                r_ = DUCK_RETS[0] if duck else ret if ret not in DUCK_RETS else 40385
                m2[R[12]], m2[R[12] + 1] = r_ & 255, r_ >> 8
                for fr in range(32):
                    for x, y in ((0, 191), (1, 120), (7, 100), (8, 60), (100, 15), (232, 30), (239, 160),
                                 (240, 80), (247, 50), (255, 175)):
                        r = list(R)
                        r[0], r[6], r[7] = fr, y, x
                        fl, _ = one(patch, kind, r, m2, attrs)
                        wraps = x > 240 and any(row & ((1 << (x - 240)) - 1) for row in
                                                frame_rows(lambda a: m2[a], fr))
                        if wraps:
                            c['player/duck at x > 240: ULA wraps byte 3 to the left edge, sprite clips '
                              '(not a game case) %s' % ('same' if not fl else 'differs')] += 1
                        else:
                            c['player/duck cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                            if fl and c['  fail example'] < 3:
                                c['  fail example'] += 1
                                c['  %s fr %d x %d y %d %s' % ('duck' if duck else 'player', fr, x, y, fl[:2])] += 1
            if neg is not None:
                fl0, npx = one(patch, kind, list(R), mem, attrs)
                fl, _ = one(neg, kind, list(R), mem, attrs)
                if not npx:
                    c['negative control n/a (the original draws no pixels here)'] += 1
                else:
                    c['negative control %s' % ('detected' if fl else 'NOT DETECTED!')] += 1
        elif kind == 'hd':
            sp = R[12]
            for ap in range(16):
                for x in (0, 8, 100, 240, 248, 249, 255):
                    for h in (40, 100, 175):
                        for idx in (0, 4, 5):
                            m2 = bytearray(mem)
                            de = HENTAB + 4 * idx + (idx & 3)
                            m2[sp + 4], m2[sp + 5] = de & 255, de >> 8
                            hl = h << 8 | x
                            m2[sp], m2[sp + 1] = hl & 255, hl >> 8
                            r = list(R)
                            g = GFX_H + 32 * ap
                            r[4], r[5] = g >> 8, g & 255
                            r[6], r[7] = h, x
                            r[3] = 1 if x >= 249 else 2
                            fl, _ = one(patch, kind, r, m2, attrs)
                            if idx >= 5:            # no hen entry 5: the guard leaves the sprites alone
                                ok = all(k[0] == 'figure drawn but no sprite slot' for k in fl)
                                c['hen outside the table (guard: no sprite) %s' % ('ok' if ok else 'FAIL!')] += 1
                                continue
                            rows = frame_rows(lambda a: m2[a], 32 + ap)
                            if x == 248 and any(row & 0xFF for row in rows):
                                # byte 2 lands in column 32: the ULA wraps it (INC HL), the sprite clips
                                c['hen at x = 248: ULA wraps byte 2, sprite clips (not a game case) %s' % (
                                    'same' if not fl else 'differs')] += 1
                                continue
                            c['hen cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                            if fl and c['  hen fail example'] < 3:
                                c['  hen fail example'] += 1
                                c['  hen ap %d x %d h %d idx %d %s' % (ap, x, h, idx, fl[:2])] += 1
            if neg is not None:
                fl0, npx = one(patch, kind, list(R), mem, attrs)
                fl, _ = one(neg, kind, list(R), mem, attrs)
                if not npx:
                    c['negative control n/a (the original draws no pixels here)'] += 1
                else:
                    c['negative control %s' % ('detected' if fl else 'NOT DETECTED!')] += 1
        elif kind == 'he':
            for idx in (0, 4, 5, 7):
                m2 = bytearray(mem)
                de = HENTAB + 4 * idx + 2
                m2[R[12] + 4], m2[R[12] + 5] = de & 255, de >> 8
                at = [list(a) for a in attrs]
                for i in range(7):
                    at[i][3] |= 0x80
                fl, _ = one(patch, kind, list(R), m2, at)
                c['hen erase cases %s' % ('ok' if not fl else 'FAIL!')] += 1
        else:
            at = [list(a) for a in attrs]
            for i in range(7):
                at[i][3] |= 0x80
            fl, _ = one(patch, kind, list(R), bytearray(mem), at)
            c['screen clear cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    return c


def negative_patch(patch):
    """Broken copy: every pattern shifted one pixel right (pixel check must fail)."""
    import copy
    q = copy.copy(patch)
    p = bytearray(patch.pats)
    out = bytearray(len(p))
    for r in range(len(p) // 8):
        row = int.from_bytes(p[8 * r:8 * r + 8], 'big')
        out[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
    q.pats = bytes(out)
    return q


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : chuckie (Chuckie Egg: player/duck plotter 39500, hen plotter 37532 -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = printer buffer, never touched in the reference RZX)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = ChuckiePatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1,
                                                                   os.path.basename(s2)))
            r = s2
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, player/duck %d, hen draws %d, hen erases %d, clears %d, '
            '%d sprite pixels -> %s' % (os.path.basename(r), c['frames'], c['pl'], c['hd'], c['he'],
                                        c['cls'], c['sprite pixels compared'],
                                        'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, negative_patch(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : player/duck %d, hens %d, hen erase %d, clears %d, negative control %d/%d -> %s' % (
            u['player/duck cases ok'], u['hen cases ok'], u['hen erase cases ok'], u['screen clear cases ok'],
            u['negative control detected'], u['negative control detected'] + u['negative control NOT DETECTED!'],
            'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in u.items():
            if 'wraps' in k or 'n/a' in k or 'guard' in k:
                say('            %s: %d' % (k, v))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
