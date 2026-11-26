"""Crystal Kingdom Dizzy (Codemasters, 1992, 128K) - engine 'crystal_kingdom_dizzy_sprites': white hardware sprites
over the game's masked objects (overlay). Facts and decisions: games/crystal_kingdom_dizzy.md; hooks:
asm/crystal_kingdom_dizzy_hooks.asm.

Every frame (interrupts off) the game puts back the backgrounds it saved (0xF433), then draws each object of its list
(record IX, 32 bytes at 0x7E00-0x7FFF) with a routine patched into the CALL at 0xF50C: masked with save-under
(width 1, 3 or 4 bytes, plain or mirrored through the bit-reverse table at 0x8000; (mask, graphics) pairs row by
row, two pixel lines a pass, IYl passes) or a plain copy (left to the ULA). Objects are monochrome and take the
cells' ink. The hook at 0xF433 hides every object sprite; the hook at 0xF508 shows the object's sprites from the
bytes the game is about to OR in. Every screen and attribute write stays, so the game's logic is the original's.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
RECORD = 'crystal_kingdom_dizzy_sprites'
_HERE = os.path.dirname(os.path.abspath(__file__))
RTPTR, REVT, NSPR = 0xF50D, 0x8000, 64
STPAGE = 26                     # the pattern cache page, mapped at 0x0000 inside the object hook only
ROUTINES = {0xF52D: (1, False, False), 0xF5EE: (3, False, True), 0xF63E: (4, False, False), 0xF6A4: (3, True, True),
            0xF718: (4, True, False)}     # width, mirrored, zigzag (odd lines stored right to left)
PLAIN = {0xF55D, 0xF5BE}        # plain copies: left to the ULA
PLOT_SPAN = (0xF52D, 0xF790)    # the draw routines (screen writes from here are the objects')

SITES = {   # addr: (original, opcode, hook symbol, resume, kind, length)
    0xF433: ('3aea83', 0xC3, 'e_rs', 0xF436, 'restore pass', 3),
    0xF508: ('ed4beb83', 0xC3, 'e_ob', 0xF50C, 'object', 3),     # LD BC,(33771): all four bytes checked, JP over three
    0xF8DD: ('3a38ff', 0xC3, 'e_rd', 0xF8E0, 'room drawn', 3),
    0xFBE1: ('7edd6f', 0xC3, 'e_wn', 0xFBE4, 'window', 3),
}
SEQUELS = {0xFBE2: 0xFBE1}      # the original's next instruction after a short displaced one: not a jump in
INTERIORS = tuple(a + k for a, s in SITES.items() for k in range(1, s[5])) + (0xF50B,)
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_crystal_kingdom_dizzy_sprites(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    sig, a = bytes.fromhex(sg['bytes']), sg['addr']
    banks = getattr(snap, 'banks', None)
    if banks is not None:                       # z80tonex.Z80Snapshot: banks, is128, port7ffd
        if not getattr(snap, 'is128', False) or snap.port7ffd & 7:
            return False
        mem = bytes(banks[5]) + bytes(banks[2]) + bytes(banks[0])
        return mem[a - 0x4000:a - 0x4000 + len(sig)] == sig
    if getattr(snap, 'machine', '48K') == '48K' or getattr(snap, 'out7ffd', 0) & 7:   # SkoolKit's Snapshot (engines.find)
        return False
    return bytes(snap.memory[a:a + len(sig)]) == sig


class CrystalKingdomDizzyPatch:
    name = 'Crystal Kingdom Dizzy objects -> white hardware sprites over the masked figures (altrom, stateless)'

    def __init__(self, prof=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hooks reach 0x3D00')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)
        self.hook_range = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        self.page = bytearray(rom[0x2000:0x4000])
        self.page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[0:0x2000]))
        self.sites = [(a, bytes.fromhex(s[0]), bytes([s[1]]) + self.syms[s[2]].to_bytes(2, 'little'))
                      for a, s in SITES.items()]
        self._banks()

    def _banks(self):
        self.extra_banks = {12: bytes(self.page) + self.altrom_low[1], STPAGE // 2: cache_page() + bytes(8192)}

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.port7ffd & 7 != 0:
            raise ValueError('Crystal Kingdom Dizzy patch expects the 128K snapshot (7FFD bank 0)')
        ram = {5: bytearray(snap.banks[5]), 2: bytearray(snap.banks[2]), 0: bytearray(snap.banks[0])}

        def where(a):
            return (5, a - 0x4000) if a < 0x8000 else ((2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000))
        for a, old, new in self.sites:
            for k in range(len(old)):
                b, o = where(a + k)
                if ram[b][o] != old[k]:
                    raise ValueError('unexpected code at 0x%04X' % (a + k))
            for k, v in enumerate(new):
                b, o = where(a + k)
                ram[b][o] = v
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        self.page[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self._banks()
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[5]), bytes(ram[2]), bytes(ram[0])


# ---------------------------------------------------------------------------------------------
# Next-side state and the object model
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


def cache_page():
    """The cache page as the build starts it: zero records, and at 0x1000 the expansion table (byte -> 4 pattern bytes,
    value 1 on each ink bit)."""
    p = bytearray(8192)
    for v in range(256):
        p[0x1000 + 4 * v:0x1004 + 4 * v] = bytes((0x10 if v & (0x80 >> 2 * k) else 0) | (1 if v & (0x40 >> 2 * k) else 0)
                                                 for k in range(4))
    return bytes(p)


def scr_addr(x, y):
    return 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)


def addr_xy(a):
    return ((a & 31) * 8, ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38))


def model(get, R):
    """The draw at 0xF508 as the game will do it: (routine, [(screen address, mask, graphics)]) or (routine, None)
    for a plain copy or an unknown routine. Rows = 2 x IYl; mirrored: drawn right to left, bytes reversed."""
    rt = get(RTPTR) | get(RTPTR + 1) << 8
    if rt not in ROUTINES:
        return rt, None
    w, mir, zig = ROUTINES[rt]
    hl, de, rows = R[6] << 8 | R[7], R[4] << 8 | R[5], 2 * R[11]
    x0, y0 = addr_xy(de)
    out = []
    for r in range(rows):
        for c in range(w):
            k = 2 * (r * w + c)
            mk, g = get((hl + k) & 0xFFFF), get((hl + k + 1) & 0xFFFF)
            col = w - 1 - c if zig and r & 1 else c
            if mir:
                col = w - 1 - col
                mk, g = get(REVT + mk), get(REVT + g)
            y = y0 + r
            if y < 192:
                out.append((scr_addr(x0 + 8 * col, y), mk, g))
    return rt, out


def slot_of(ix):
    return ((ix >> 5) & 15) if 0x7E00 <= ix <= 0x7FFF else None


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
    """The patched machine: alt ROM below 0x4000 (or the cache page at 0x0000 while MMU0 holds it), sites patched."""

    def __init__(self, get, alt, psite, ns=None, state=None):
        _Ov.__init__(self, get)
        self.alt, self.psite, self.romw = alt, psite, 0
        self.ns, self.state = ns, state

    def _cache(self, a):
        return a < 0x2000 and self.ns is not None and self.ns.nr.get(0x50, 0xFF) == STPAGE

    def __getitem__(self, a):
        if a < 0x4000:
            if self._cache(a):
                return self.state[a]
            return self.alt[a]
        v = self.psite.get(a)
        if v is not None:
            return v
        return _Ov.__getitem__(self, a)

    def __setitem__(self, a, v):
        if a < 0x4000:
            if self._cache(a):
                self.state[a] = v
            else:
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


def _run(sim, stop, limit=500000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[24] != stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


def _alt(patch):
    alt = bytearray(patch.altrom_low[1]) + bytearray(patch.page)
    return alt


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def event(patch, pc, get, R, ns, alt, psite, state=None):
    """-> (failures, hook T)."""
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
    p = _OvP(get, alt, psite, ns, state if state is not None else bytearray(cache_page()))
    sp = machine(Sim, p, list(R), 'p')
    install(sp, ns.nextreg)
    sp.set_tracer(_Ports(ns=ns))
    n0 = len(ns.ports)
    speed = ns.nr.get(7, 0)
    try:
        reached = _run(sp, stop)
    except Exception as x:                     # a broken hook running away (a negative control)
        fl.append('hook crashed: %s' % str(x)[:80])
        return fl, 0
    if not reached:
        fl.append('hook did not reach the resume point')
        return fl, 0
    if ns.nr.get(7, 0) != speed:
        fl.append('speed not restored: entered at %d, left at %d' % (speed, ns.nr.get(7, 0)))
    for i in CMP:
        if so.registers[i] != sp.registers[i]:
            fl.append('register %d: original %02X, patched %02X' % (i, so.registers[i], sp.registers[i]))
    if p.romw:
        fl.append('hook wrote the ROM')
    if ports != ns.ports[n0:]:
        fl.append('port writes differ %s %s' % (ports[:3], ns.ports[n0:][:3]))
    del ns.ports[n0:]
    top = sp.registers[12]
    for a in set(o.ov) | set(p.ov):
        vo = o.ov.get(a, get(a))
        vp = p.ov.get(a, get(a))
        if top - 64 <= a < top:
            continue
        if vo != vp:
            fl.append('memory %04X: original %02X, patched %02X' % (a, vo, vp))
            break
    return fl, sp.registers[25] - so.registers[25]


def verify(patch, rzx_path, stop=None, progress=None, collect=0):
    """Replay the RZX on the original; an event at every site; every masked draw's model checked against the game's
    own screen writes; at every restore pass each object's sprites against its last draw's graphics bits; any other
    screen write under a shown sprite fails. -> (Counter, examples[, states])."""
    from .simrun import play_rzx
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    SITE = {a for a, old, new in patch.sites}
    INTER = set(INTERIORS)
    cnt = collections.Counter()
    states = []

    class H:
        def __init__(h):
            h.R = h.mem = None
            h.frame = 0
            h.ns = NextState()
            h.truth = {}            # slot -> set of pixels of its last masked draw (None: left to the ULA)
            h.draw = None           # the draw in progress: (slot, predicted {addr: (mask, gfx)}, writes)
            h.shown = {}            # screen byte -> slot, for every pixel byte under a shown sprite
            h.state = bytearray(cache_page())   # the pattern cache page, as the hooks leave it

        def on_sim(h, sim):
            h.R, h.mem = sim.registers, sim.memory

        def on_frame(h, n):
            h.frame = n
            if progress and n % 1000 == 0:
                progress(n, c)

        def on_desync(h, *a):
            h.fail('replay desynchronised', a[:2])

        def fail(h, k, info=()):
            c[k + '!'] += 1
            if len(ex[k]) < 5:
                ex[k].append((h.frame,) + tuple(info))

        def get(h, a):
            return h.mem[a]

        def on_write(h, a, v, pc, mem):
            if a in psite:
                h.fail('game wrote a patch site', (a,))
            if not 0x4000 <= a < 0x5800:
                return
            if h.draw is not None and PLOT_SPAN[0] <= pc < PLOT_SPAN[1]:
                w = h.draw[2]
                w[a] = (w[a][0] if a in w else h.get(a), v)
                return
            s = h.shown.get(a)
            if s is not None:
                if PLOT_SPAN[0] <= pc < PLOT_SPAN[1]:   # a plain-copy object drawn where a masked one's sprite is:
                    c['plain object under a shown sprite (bytes)'] += 1   # the sprite stays in front (counted)
                else:
                    h.fail("a screen write under a shown sprite", ("%04X" % pc, "%04X" % a, s, "%04X" % (h.mem[h.R[12]] | h.mem[h.R[12] + 1] << 8), "%04X" % (h.mem[h.R[12] + 2] | h.mem[h.R[12] + 3] << 8)))
                    c["under sprite by %04X" % pc] += 1

        def before(h, pc):
            if pc in SITE or pc in (0xF433, 0xF508, 0xF8DD, 0xFBE1):
                if pc in (0xF8DD, 0xFBE1):     # the room drawn again, or a window: what was drawn is gone
                    h.truth = {}
                if pc == 0xF433:
                    h.check()
                elif pc == 0xF508:
                    ix = h.R[8] << 8 | h.R[9]
                    s = slot_of(ix)
                    rt, m = model(h.get, h.R)
                    if s is None:
                        h.fail('object record outside 0x7E00-0x7FFF', ('%04X' % ix,))
                    c['draws ' + ('masked' if m is not None else 'plain' if rt in PLAIN else 'unknown %04X' % rt)] += 1
                    if m is not None and 2 * h.R[11] > 32:
                        h.fail('object taller than its sprites (32 rows)', (2 * h.R[11],))
                    if m is not None and (h.R[5] & 31) + ROUTINES[rt][0] > 32:
                        h.fail('object past the right edge (the game wraps it, the sprites do not)', ('%04X' % rt,))
                    if m is not None and s is not None:
                        h.draw = (s, {a: (mk, g) for a, mk, g in m}, {})
                    elif s is not None:
                        h.truth[s] = None
                    if collect and len(states) < collect and c['draws masked'] % 37 == 1 and m is not None:
                        states.append((list(h.R), bytes(h.mem[a] for a in range(65536))))
                if pc in SITE:
                    kind = SITES[pc][4]
                    c[kind] += 1
                    cnt[pc] += 1
                    fl, t = event(patch, pc, h.get, h.R, h.ns, alt, psite, h.state)
                    c['hook T (28 MHz, patched minus original)'] += t
                    for k in fl:
                        h.fail('%s: %s' % (kind, k))
                    if pc != 0xF508:              # what is shown now, from the sprites the hooks left
                        h.shown = {}
                        for i in range(NSPR):
                            for (x, y) in h.ns.pixels(i):
                                if isinstance(x, int):
                                    h.shown[scr_addr(x, y)] = i // 4
            elif pc == 0xF50F and h.draw is not None:
                s, pred, writes = h.draw
                h.draw = None
                bad = [a for a, (mk, g) in pred.items() if writes.get(a, (None, None))[1] != ((writes.get(a, (h.get(a), 0))[0] & mk) | g)]
                extra = [a for a in writes if a not in pred]
                if bad or extra:
                    h.fail('the model differs from the game\'s drawing', (len(bad), len(extra), ['%04X' % a for a in (bad + extra)[:3]]))
                c['draws checked against the game'] += 1
                px = set()
                for a, (mk, g) in pred.items():
                    x, y = addr_xy(a)
                    for k in range(8):
                        if g & (0x80 >> k):
                            px.add((x + k, y))
                h.truth[s] = px
                for i in range(4):
                    for (x, y) in h.ns.pixels(4 * s + i):
                        if isinstance(x, int):
                            h.shown[scr_addr(x, y)] = s
            elif pc in INTER:
                cnt[pc] += 1

        def check(h):
            c['restore passes'] += 1
            for s in range(16):
                t = h.truth.get(s)
                got = set()
                for i in range(4):
                    h.ns.pixels(4 * s + i, got)
                want = t or set()
                if got != want:
                    h.fail('object %d != sprites' % s, (sorted(want - got)[:3], sorted(got - want, key=str)[:3]))
                else:
                    c['sprite pixels compared'] += len(got)
            for i in range(NSPR, 128):
                if h.ns.visible(i):
                    h.fail('sprite %d shown' % i)
            h.truth = {}

    h = H()
    c['frames'] = play_rzx(rzx_path, h, stop=stop)
    for a in INTER:
        if cnt[a] != (cnt[SEQUELS[a]] if a in SEQUELS else 0):
            c['jump into a patched instruction (%04X)!' % a] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


def build(z80, out, name, say=print):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    patch = CrystalKingdomDizzyPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    return not bad, patch


def auto(a, z80, name, out, say):
    """nexclash.py auto / patch: the sprite build, then for each recording the replay, the unit cases and the negative
    controls (a run that reaches no object draw, or misses a control, fails)."""
    say('Game      : %s' % name)
    say('Engine    : crystal_kingdom_dizzy_sprites (objects as white sprites over the masked figures, a pattern cache)')
    ok, patch = build(z80, out, name, say)
    for r in list(a.rzx or []):
        c, ex, states = verify(patch, r, stop=getattr(a, 'quick', None), collect=8)
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        if not c['draws checked against the game']:
            fails['no object draw reached: nothing verified'] = 1
        u = unit_tests(patch, states)
        fails.update({k: v for k, v in u.items() if k.endswith('FAIL!')})
        missed = [nm for nm, q in negative_patches(patch)
                  if not ({k for k, v in verify(q, r, stop=min(getattr(a, 'quick', None) or 1500, 1500))[0].items() if k.endswith('!')}
                          or any(k.endswith('FAIL!') for k in unit_tests(q, states[:2])))]
        if missed:
            fails['negative controls not caught: %s' % ', '.join(missed)] = len(missed)
        ok = ok and not fails
        say('Verify    : %s  %d frames; %s -> %s' % (os.path.basename(r), c['frames'],
            ', '.join('%s %d' % (k, v) for k, v in sorted(c.items()) if not k.endswith('!') and not k.startswith('  ') and k != 'frames')[:300],
            'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('Units     : %s; negative controls: %d of %d caught' % (
            ', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.startswith('  ')), len(negative_patches(patch)) - len(missed), len(negative_patches(patch))))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def _broken(patch, sym, new, at=0):
    import copy
    q = copy.copy(patch)
    a = patch.syms[sym] + at - 0x2000
    page = bytearray(patch.page)
    page[a:a + len(new)] = new
    q.page = bytes(page)
    return q


def negative_patches(patch):
    import copy
    no_site = copy.copy(patch)
    no_site.sites = [s for s in patch.sites if s[0] != 0xF508]
    return [('object hook leaves the CPU at 28 MHz', _broken(patch, 'neg_spd', b'\0\0\0')),
            ('sprites one row low', _broken(patch, 'neg_y', b'\xC6\x21')),
            ('ink lost in the pattern upload', _broken(patch, 'neg_pix', b'\xAF')),
            ('restore pass leaves the sprites', _broken(patch, 'neg_rs', b'\0\0\0')),
            ('room drawn again leaves the sprites', _broken(patch, 'neg_rd', b'\0\0\0')),
            ('window leaves the sprites', _broken(patch, 'neg_wn', b'\0\0\0')),
            ('cache never sends new patterns', _broken(patch, 'neg_new', b'\x3E\x00')),
            ('mirrored 3-byte objects drawn unmirrored', _broken(patch, 'rtab', b'\x02', at=15)),
            ('object site not applied', no_site)]


def unit_tests(patch, states):
    """Every masked routine (plain, mirrored, zigzag) x heights 1-16 passes x edge positions, from states the walks
    reached: registers and memory as the original's (event), the record's sprites = the model's graphics bits."""
    c = collections.Counter()
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    for R0, mem in states[:4]:
        for rt in ROUTINES:
            for iyl in (1, 2, 7, 8, 9, 16):
                for x, y in ((0, 0), (64, 100), (200, 60), (224, 8), (232, 150), (8, 170), (100, 186)):
                    if x + 8 * ROUTINES[rt][0] > 256:
                        x = 256 - 8 * ROUTINES[rt][0]     # the game never draws past the right edge (verify checks)
                    m = bytearray(mem)
                    m[RTPTR], m[RTPTR + 1] = rt & 255, rt >> 8
                    R = list(R0)
                    a = scr_addr(x, y)
                    R[4], R[5] = a >> 8, a & 255
                    R[11] = iyl
                    ns = NextState()                  # fresh sprites, so a fresh cache: every case sends its patterns
                    ns.nr[7] = (iyl + x + y) % 4      # entered at each CPU speed in turn
                    state = bytearray(cache_page())
                    get = m.__getitem__
                    fl, _ = event(patch, 0xF508, get, R, ns, alt, psite, state)
                    rt_, mod = model(get, R)
                    s = slot_of(R[8] << 8 | R[9])
                    want = set()
                    for ad, mk, g in mod:
                        ax, ay = addr_xy(ad)
                        for k in range(8):
                            if g & (0x80 >> k):
                                want.add((ax + k, ay))
                    got = set()
                    for i in range(4):
                        ns.pixels(4 * s + i, got)
                    bad = list(fl) + (['sprites differ: %d missing, %d extra' % (len(want - got), len(got - want))] if want != got else [])
                    k = 'routine %04X' % rt
                    c[k + (' FAIL!' if bad else ' ok')] += 1
                    if bad and c['  example'] < 3:
                        c['  example'] += 1
                        c['  %s iyl=%d x=%d y=%d: %s' % (k, iyl, x, y, bad[:2])] += 1
    for pc in (0xFBE1, 0xF8DD):                         # window and room drawn again: every sprite shown first, all hidden
        for n, (R0, mem) in enumerate(states[:4]):
            ns = NextState()
            ns.nr[7] = n % 4
            for s in range(NSPR):
                ns.attr[s] = [9, 9, 0, 0xC0 | s, 0x80]
            R = list(R0)
            R[24] = pc
            fl, _ = event(patch, pc, mem.__getitem__, R, ns, alt, psite, bytearray(cache_page()))
            bad = list(fl) + ['sprite %d left shown' % s for s in range(NSPR) if ns.visible(s)]
            k = '%s hook' % SITES[pc][4]
            c[k + (' FAIL!' if bad else ' ok')] += 1
            if bad and c['  example'] < 3:
                c['  example'] += 1
                c['  %s: %s' % (k, bad[:2])] += 1
    return c
