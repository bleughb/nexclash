"""Everyone's a Wally (Mikro-Gen; 48K code in a 128K snapshot) engine 'wally'. Additive module:
reachable only through is_wally().

Game facts (analysis passes over wally.z80 and Dean's RZX; details in games/everyones_a_wally.md):
  every render rebuilds a back buffer (pixels 0x6B00-0x7AFF = screen lines 64-191, row = 32 bytes,
  attributes 0xFC00-0xFDFF) from a clean copy, plots the figures into it, then 47611 copies it to
  the screen with unrolled LDI (pixels, then attributes from 47637). Plotters run with interrupts
  off and SP pointing into graphics. No game logic reads buffer/attribute/screen bytes.
  A 45286  gang member, IY = descriptor (+0 frame, +5 x, +10 y, +30 attr, +35/+40 gfx), 16x32
           masked (rows: mask L, mask R, gfx L, gfx R), then paints 2-3 x 4-5 attribute cells.
  B 43168  masked 16x16 object, A = frame (gfx 33656 + A*32), position (43064/43065).
  C 43069  OR-only 16x16 object (same gfx block); stays on the ULA.
  61329    paints the attributes of the last B/C plot with (62063).
Hooks (asm/wally_hooks.asm): A and B become 4-bit sprites (A: 2, B: 1), C and 61329-after-C run
unchanged, 61329 after a converted B only sets that sprite's colour; commit at 47637.
"""
import collections
import json
import os

from .rainbow import NextState, _machine, _run, boot_check as _rb_boot_check, mem64, _BankMem

PAGE_S = 26
ALT_PAGE = 24
ROM_ORG = 0x386E
PAGE_ORG = 0x0100
SPRTAB, NIBTAB, PALMAP = 0x1800, 0x1A00, 0x1C00
V_N, V_PREV, V_PAR, V_LAST = 0, 1, 2, 3
MAXS = 32
TAIL_ADDR = 0x6B00          # back buffer: write-first in Dean's RZX
BUF = (0x6B00, 0x7B00)
ATTRBUF = (0xFC00, 0xFE00)
SITES_ORIG = {45286: bytes.fromhex('D9FD5E'), 43168: bytes.fromhex('D9F5ED'),
              43069: bytes.fromhex('F3D9F5'), 61329: bytes.fromhex('F5D93A'),
              47637: bytes.fromhex('010002')}
SITE_SYM = {45286: 'e_a', 43168: 'e_b', 43069: 'e_c', 61329: 'e_p', 47637: 'e_cm'}
# instruction interiors that must never be a PC (patched instruction split by the 3-byte JP)
INTERIORS = (45288, 45289, 43171, 43172, 43173, 61332, 61333, 47638, 47639)
# Next default ULA colours (RRRGGGBB): ink 0-7 normal, then bright
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'everyones_a_wally.json'),
              os.path.join(_HERE, 'everyones_a_wally.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('everyones_a_wally.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def pal_offset(attr):
    return (attr & 7) | ((attr & 0x40) >> 3)


class Config:
    """Sprite ink = the figure's Spectrum ink (A: its own attribute; B: the 61329 colour, else the
    attribute-buffer cell under its centre); outline = black (the paper of every figure)."""

    def __init__(self, outline=0x00):
        self.outline = outline

    def nibtab(self):
        t = bytearray(512)
        for i in range(256):
            g, m = i >> 4, i & 15
            px = [1 if g & b else (0 if m & b else 2) for b in (8, 4, 2, 1)]
            t[i] = px[0] << 4 | px[1]
            t[256 + i] = px[2] << 4 | px[3]
        return bytes(t)

    def palmap(self):
        return bytes(pal_offset(a) << 4 for a in range(256))

    def palette(self):
        pal = bytearray(256)
        for k in range(16):
            pal[16 * k + 1] = SPECCY[k]
            pal[16 * k + 2] = self.outline
        return bytes(pal)


def identify_wally(mem):
    sg = load_profile()['signature']
    a, sig = sg['addr'], bytes.fromhex(sg['bytes'])
    return bytes(mem[a:a + len(sig)]) == sig


def is_wally(snap):
    try:
        return snap.machine != '48K' and identify_wally(mem64(snap))
    except FileNotFoundError:
        return False


class WallyPatch:
    name = "Everyone's a Wally plotters A/B -> hardware sprites (altrom + RAM page 26)"

    def __init__(self, cfg=None, prof=None, page_code=None):
        self.cfg = cfg or Config()
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.page_code = page_code or bytes.fromhex(h['page'])
        self.setup = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = self.setup + self.cfg.palette()
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 80
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM stubs too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        sp = bytearray(8192)
        sp[PAGE_ORG:PAGE_ORG + len(self.page_code)] = self.page_code
        if PAGE_ORG + len(self.page_code) > SPRTAB:
            raise ValueError('page code overlaps the sprite table')
        sp[NIBTAB:NIBTAB + 512] = self.cfg.nibtab()
        sp[PALMAP:PALMAP + 256] = self.cfg.palmap()
        self.scratch = bytes(sp)
        self.extra_banks = {12: self.page + bytes(8192), 13: self.scratch + bytes(8192)}
        self.sites = [(a, old, b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]

    def _bank_of(self, a):
        return (5, 2, 0)[(a >> 14) - 1]

    def check_sites(self, banks):
        for a, old, new in self.sites:
            b = banks[self._bank_of(a)]
            cur = bytes(b[(a & 0x3FFF):(a & 0x3FFF) + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        if not snap.is128:
            raise ValueError("Everyone's a Wally patch expects the 128K snapshot")
        if snap.port7ffd & 0x17 != 0x10:
            raise ValueError('snapshot must select ROM 1 (48K BASIC) and bank 0 at C000')
        self.check_sites(snap.banks)
        for a, old, new in self.sites:
            k = self._bank_of(a)
            b = bytearray(snap.banks[k])
            b[(a & 0x3FFF):(a & 0x3FFF) + len(new)] = new
            snap.banks[k] = bytes(b)


def boot_check(nex, z80, patch=None):
    return _rb_boot_check(nex, z80, patch, tail=(TAIL_ADDR, TAIL_ADDR + 80))


# ---------------------------------------------------------------------------------------------
# Event runner: original vs patched from one state
# ---------------------------------------------------------------------------------------------

def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def _pair(patch, get, regs, ns, stops, alt=None):
    """Run original and patched code from one state (memory read through get(a)) until PC in stops.
    ns = the patched Next state (mutated). Returns (so, o, sp, p, err)."""
    from .build import rom48
    Sim = _sim_class()
    if alt is None:
        alt = bytearray(rom48())
        alt[0x2000:0x4000] = patch.page
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    err = []

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
        def __getitem__(s, a):
            if a < 0x4000:
                if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                    return ns.scratch[a]
                return alt[a]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x2000 and ns.nr.get(0x50) == PAGE_S:
                ns.scratch[a] = v
            elif a < 0x4000:
                err.append(('rom write', a))
            else:
                s.ov[a] = v
    o, p = O(), P()
    ns.events = []
    so = _machine(Sim, o, list(regs), NextState(patch))
    sp_ = _machine(Sim, p, list(regs), ns)
    if not (_run(so, stops) and _run(sp_, stops)):
        err.append('did not return')
    if ns.nr.get(0x50) != 0xFF or ns.nr.get(0x07, 0) != 0:
        err.append(('MMU / speed not restored', ns.nr.get(0x50), ns.nr.get(0x07)))
    if any(e[0] == 'in' for e in ns.events):
        err.append('port read in hook')
    return so, o, sp_, p, err


CMP = list(range(0, 13)) + [14, 16, 17] + list(range(18, 25)) + [26, 27, 28]   # all but R, T, MEMPTR


def _in(a, r):
    return r[0] <= a < r[1]


def _spr_pixels(ns, i):
    """Pixels of SPRTAB entry i (uncommitted sprite) as {(x, y): index}, x/y in ULA coordinates."""
    s = ns.scratch[SPRTAB + 5 * i:SPRTAB + 5 * i + 5]
    x = s[0] + (s[2] & 1) * 256 - 32
    y = s[1] - 32
    base = (s[3] & 0x3F) * 256 + (128 if s[4] & 0x40 else 0)
    out = {}
    for j in range(16):
        for k in range(16):
            b = ns.pat[base + j * 8 + k // 2]
            out[(x + k, y + j)] = (b >> 4) if k % 2 == 0 else (b & 15)
    return out


def check_plot(kind, get, so, o, sp_, p, ns, n_before, colour_attr=None):
    """Compare an A/B event. Returns list of failure keys (empty = identical)."""
    f = []
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    n_after = ns.scratch[V_N]
    converted = n_after != n_before
    if not converted:                       # passthrough: identical, buffers included
        if o.ov != p.ov:
            f.append(('passthrough differs', len(set(o.ov) ^ set(p.ov))))
        return f, 0
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not (_in(a, BUF) or _in(a, ATTRBUF)) and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    if any(_in(a, BUF) or _in(a, ATTRBUF) or 0x4000 <= a < 0x5B00 for a in p.ov):
        f.append(('patched code wrote the buffer/screen',))
    if n_after - n_before != (2 if kind == 'A' else 1):
        f.append(('sprite count', n_before, n_after))
    # pixels: sprites vs the original's buffer plot (buffer row y at 0x6300 + y*32)
    cov = {}
    for i in range(n_before, n_after):
        for xy, idx in _spr_pixels(ns, i).items():
            if idx:
                cov[xy] = idx
    bad = 0

    def bit(m, x, y):
        a = 0x6300 + y * 32 + (x >> 3)
        return (m[a] >> (7 - (x & 7))) & 1, a
    for (x, y), idx in cov.items():
        if not (0 <= x < 256 and 64 <= y < 192):
            bad += 1
            continue
        after, a = bit(o, x, y)
        if (idx == 1) != (after == 1) or idx not in (1, 2):
            bad += 1
    for a in o.ov:
        if _in(a, BUF):
            y, xb = (a - 0x6300) // 32, (a - 0x6300) % 32
            for k in range(8):
                x = xb * 8 + k
                if (x, y) not in cov and ((get(a) ^ o.ov[a]) >> (7 - k)) & 1:
                    bad += 1
    if bad:
        f.append(('sprite pixels differ from the original plot', bad))
    # colour: A = the attribute it painted; B = the attribute-buffer cell under its centre
    s2 = ns.scratch[SPRTAB + 5 * n_before + 2] >> 4
    if kind == 'A':
        painted = {o.ov[a] for a in o.ov if _in(a, ATTRBUF)}
        if len(painted) != 1 or pal_offset(painted.pop()) != s2:
            f.append(('A colour', s2))
    elif colour_attr is not None and pal_offset(colour_attr) != s2:
        f.append(('B colour', s2, colour_attr))
    return f, len(cov)


def _plot_stops(get, R):
    sp = R[12]
    return (get(sp) + 256 * get(sp + 1),)


def _b_centre_attr(get):
    x, y = get(43064), get(43065)
    return get(0xFB00 + ((y + 8) & 248) * 4 + (((x + 8) & 255) >> 3))


# ---------------------------------------------------------------------------------------------
# Differential verification against an RZX (the replay runs the ORIGINAL game)
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    import copy
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    from .build import rom48
    MG, MS = Memory.__getitem__, Memory.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'sim': None, 'frame': 0}
    ns = NextState(patch)
    cnt = collections.Counter()
    WATCH = set(SITES_ORIG) | set(INTERIORS) | {45287, 43169, 43170, 43070, 43071, 61330, 61331}
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class HookMem(Memory):
        def __setitem__(s, a, v):
            if a in site_bytes and st['sim'] is not None:
                fail('game wrote a patch site', (a,))
            MS(s, a, v)

    def event(pc, real, R):
        get = lambda a: MG(real, a)
        if pc != 43069 and R[26]:
            fail('interrupts enabled at a hook site', (pc,))
        if collect and pc in (45286, 43168) and c['collected %d' % pc] < collect:
            c['collected %d' % pc] += 1
            states.append((pc, list(R), [bytes(b) for b in real.banks], real.o7ffd, bytes(ns.scratch)))
        if pc in (45286, 43168):
            kind = 'A' if pc == 45286 else 'B'
            n0 = ns.scratch[V_N]
            cattr = _b_centre_attr(get) if kind == 'B' else None
            so, o, sp_, p, err = _pair(patch, get, R, ns, _plot_stops(get, R), alt)
            for e in err:
                fail('%s: %s' % (kind, e))
            f, npx = check_plot(kind, get, so, o, sp_, p, ns, n0, cattr)
            for k in f:
                fail('%s: %s' % (kind, k[0]), k[1:])
            if ns.scratch[V_N] != n0:
                c['%s converted' % kind] += 1
                c['sprite pixels compared'] += npx
            else:
                c['%s passed through to the ULA' % kind] += 1
        elif pc in (43069, 61329):
            what = 'C' if pc == 43069 else '61329'
            last = ns.scratch[V_LAST]
            so, o, sp_, p, err = _pair(patch, get, R, ns, _plot_stops(get, R), alt)
            for e in err:
                fail('%s: %s' % (what, e))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            if diff:
                fail(what + ': registers differ', (diff,))
            if pc == 61329 and last:
                c['61329 after a converted B (sprite coloured)'] += 1
                md = [a for a in set(o.ov) | set(p.ov) if not _in(a, ATTRBUF) and o[a] != p[a]]
                if md or any(_in(a, ATTRBUF) for a in p.ov):
                    fail('61329: memory differs', (sorted(md)[:4],))
                painted = {o.ov[a] for a in o.ov if _in(a, ATTRBUF)}
                s2 = ns.scratch[SPRTAB + 5 * (last - 1) + 2] >> 4
                if len(painted) != 1 or pal_offset(painted.pop()) != s2:
                    fail('61329: sprite colour differs from the painted attribute', (s2,))
            else:
                c[what + ' unchanged (ULA)'] += 1
                if o.ov != p.ov:
                    fail(what + ': memory differs', ())
            if ns.scratch[V_LAST]:
                fail(what + ': pending B not cleared', ())
        elif pc == 47637:
            n = ns.scratch[V_N]
            tab = [list(ns.scratch[SPRTAB + 5 * i:SPRTAB + 5 * i + 5]) for i in range(n)]
            so, o, sp_, p, err = _pair(patch, get, R, ns, (47640,), alt)
            for e in err:
                fail('commit: %s' % (e,))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            if diff or o.ov != p.ov:
                fail('commit: registers/memory differ', (diff,))
            c['commits'] += 1
            c['max sprites in a render'] = max(c['max sprites in a render'], n)
            for i in range(128):
                vis = bool(ns.attr[i][3] & 0x80)
                if i < n and ns.attr[i] != tab[i]:
                    fail('commit: sprite attributes differ from the table', (i,))
                if vis != (i < n):
                    fail('commit: visibility wrong', (i, n))

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            memory.__class__ = HookMem
            super().__init__(memory, registers, state_, config)
            st['sim'] = self
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        if pc in SITES_ORIG:
                            event(pc, mem, R)
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if progress and st['frame'] % 2000 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    for a, b in ((45286, 45287), (43168, 43169), (43168, 43170), (43069, 43070), (43069, 43071),
                 (61329, 61330), (61329, 61331)):
        if cnt[a] != cnt[b]:
            c['%d reached other than from %d!' % (b, a)] += 1
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests: edge positions, guards (passthrough), sprite-table full, hide path, negative control
# ---------------------------------------------------------------------------------------------

def unit_tests(patch, states, neg=None):
    """states from verify(collect=n). For each A/B state: x/y edge and guard positions, frames,
    N = 0 / MAXS-2 / MAXS-1 / MAXS, PAR 0/32. Same checks as verify. neg: a broken patch that must
    FAIL (negative control). Returns Counter."""
    from .build import rom48
    rom = rom48()
    c = collections.Counter()

    def one(pt, pc, R, banks, o7, scratch, xs, ys, frame, n, par):
        bm = _BankMem(banks, o7, rom)
        get = bm.__getitem__
        R = list(R)
        if pc == 45286:
            iy = R[10] * 256 + R[11]
            ad = {5: iy + 5, 10: iy + 10, 0: iy}
        else:
            ad = {5: 43064, 10: 43065}
            R[0] = frame
        wr = {}
        wr[ad[5]] = xs
        wr[ad[10]] = ys
        if pc == 45286:
            wr[ad[0]] = frame
        g2 = lambda a: wr[a] if a in wr else get(a)
        ns = NextState(pt)
        ns.scratch[0:0x100] = scratch[0:0x100]          # run-time state only; code/tables from pt
        ns.scratch[V_N], ns.scratch[V_PAR] = n, par
        kind = 'A' if pc == 45286 else 'B'
        cattr = _b_centre_attr(g2) if kind == 'B' else None
        so, o, sp_, p, err = _pair(pt, g2, R, ns, _plot_stops(g2, R))
        f, npx = check_plot(kind, g2, so, o, sp_, p, ns, n, cattr)
        guard = (ys < 64 or ys > (160 if kind == 'A' else 168) or xs > 240 or
                 n >= (MAXS - 1 if kind == 'A' else MAXS))
        conv = ns.scratch[V_N] != n
        if conv == guard:
            f.append(('guard/convert mismatch', xs, ys, n))
        return err + f, conv

    for pc, R, banks, o7, scratch in states:
        kind = 'A' if pc == 45286 else 'B'
        frames = range(8) if kind == 'A' else (44, 64, 118, 132)
        for xs in (0, 1, 7, 8, 223, 224, 232, 239, 240, 241, 255):
            for ys in ((63, 64, 65, 71, 72, 152, 153, 159, 160, 161) if kind == 'A'
                       else (63, 64, 65, 71, 72, 160, 167, 168, 169, 176)):
                for fr, n, par in ((frames[(xs + ys) % len(frames)], 0, 0),
                                   (frames[(xs * 3 + ys) % len(frames)], MAXS - 2, 32)):
                    f, conv = one(patch, pc, R, banks, o7, scratch, xs, ys, fr, n, par)
                    c['cases'] += 1
                    c['converted' if conv else 'passthrough'] += 1
                    for k in f:
                        c['%s: %s!' % (kind, k[0] if isinstance(k, tuple) else k)] += 1
        for n in (MAXS - 1, MAXS):
            f, conv = one(patch, pc, R, banks, o7, scratch, 100, 100, frames[0], n, 0)
            c['cases'] += 1
            c['full-table passthrough' if not conv else 'converted'] += 1
            for k in f:
                c['%s full: %s!' % (kind, k[0] if isinstance(k, tuple) else k)] += 1
        if neg is not None:
            f, conv = one(neg, pc, R, banks, o7, scratch, 100, 100, frames[1], 0, 0)
            c['negative control detected' if f else 'negative control NOT detected!'] += 1
    # commit: hide path (PREV > N) and full table
    if states:
        pc, R, banks, o7, scratch = states[0]
        bm = _BankMem(banks, o7, rom)
        for n, prev in ((0, 32), (3, 7), (MAXS, 5)):
            ns = NextState(patch)
            ns.scratch[:] = scratch
            ns.scratch[V_N], ns.scratch[V_PREV] = n, prev
            for i in range(128):
                ns.attr[i] = [0, 0, 0, 0x80, 0]          # all visible before
            tab = [[(7 * i + j) & 255 for j in range(3)] + [0xC0 | i, 0x80] for i in range(n)]
            for i, t in enumerate(tab):
                ns.scratch[SPRTAB + 5 * i:SPRTAB + 5 * i + 5] = bytes(t)
            R2 = list(R)
            R2[24] = 47637
            so, o, sp_, p, err = _pair(patch, bm.__getitem__, R2, ns, (47640,))
            ok = not err and all(ns.attr[i] == tab[i] for i in range(n)) and \
                all(not ns.attr[i][3] & 0x80 for i in range(n, prev)) and ns.scratch[V_PREV] == n \
                and ns.scratch[V_N] == 0
            c['commit cases'] += 1
            if not ok:
                c['commit (N=%d, prev=%d)!' % (n, prev)] += 1
    return c


def negative_patch(patch):
    """Broken copy: NIBTAB with ink and outline swapped (pixel check must fail)."""
    import copy
    q = copy.copy(patch)
    sp = bytearray(patch.scratch)
    t = bytearray(sp[NIBTAB:NIBTAB + 512])
    sw = {0: 0, 1: 2, 2: 1}
    for i in range(512):
        hi, lo = t[i] >> 4, t[i] & 15
        t[i] = sw[hi] << 4 | sw[lo]
    sp[NIBTAB:NIBTAB + 512] = t
    q.scratch = bytes(sp)
    return q


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    say('Game      : %s' % name)
    say("Engine    : wally (Everyone's a Wally: back-buffer renderer, plotters A/B -> sprites)")
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, TAIL_ADDR, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = back buffer, write-first in the RZX)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = WallyPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch)
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
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=6)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, A %d, B %d converted, %d commits (max %d sprites), '
            '%d pixels -> %s' % (os.path.basename(r), c['frames'], c['A converted'], c['B converted'],
                                 c['commits'], c['max sprites in a render'], c['sprite pixels compared'],
                                 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, negative_patch(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %d cases (%d converted, %d passthrough), %d commit cases, negative control '
            '%d/%d -> %s' % (u['cases'], u['converted'], u['passthrough'] + u['full-table passthrough'],
                             u['commit cases'], u['negative control detected'], len(states),
                             'PASS' if not uf else 'FAIL %s' % uf))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
