"""Auf Wiedersehen Monty (Gremlin Graphics, 1987, 128K) - engine 'auf_wiedersehen_monty': figures as hardware sprites
over the game's own figure pixels (overlay). Facts and decisions: games/auf_wiedersehen_monty.md; hooks:
asm/auf_wiedersehen_monty_hooks.asm.

The figure loop 0xA2AD (41645, called from the update at 41523) builds for each of five records at 42030 (13 bytes:
x, y, colour, composite pointer, shift entry, frame, ..., +9 bit 7 = drawn as stored) a 3 x 3 block of composite
cells at 33285 + 72 i (column-major, 24 bytes a column): the background's cells copied, then the record's 16 x 16
image (0x6000 + frame * 32) ORed in, shifted to x & 7, mirrored through 0xFE00 when +9 bit 7 is clear, and masked
off scenery ink through 0xFF00. Before each cell it paints the cell's attribute with the record's colour where the
room map (23420) leaves it empty (41725): the colour clash; that store becomes a NOP. The cell renderer then copies
changed cells to the screen. Nothing else reads the composite cells (scan: the renderer, the drawers' own
read-modify-write, the background copy). A hook after the loop shows sprite i for record i in its own ink; the
clear-screen routine and the room draw hide them.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR, TAIL_MAX = 0x5C7C, 224             # the recording's start: write-first there (scan); 0x5B7C on is the room map


def tail_for(snap):
    """(address, room) for the start-up tail in this snapshot's state. Taken inside the figure loop (IX in figure k's
    composite cells, k < 4: the TOSEC [128K] release, k = 2), figures k+1..4's cells are copied afresh from the
    background before anything reads them: the tail goes there. Otherwise the recording's start (0x5C7C)."""
    k = (snap.ix - COMP) // 72 if COMP <= snap.ix < COMP + 72 * NFIG else None
    if k is not None and k < NFIG - 1 and 41645 <= snap.pc < 42030:
        a = COMP + 72 * (k + 1)
        return a, COMP + 72 * NFIG - a
    return TAIL_ADDR, TAIL_MAX
FIGS, NFIG, GFX = 42030, 5, 0x6000
COMP = 33285                                   # composite cells: figure i at COMP + 72 i
DRAW_WRITES = (41853, 41866, 41879, 41896, 41909)   # the drawers' ORed stores into the composite cells
FIG_LOOP, FIG_CALL, FIG_RET = 41645, 41523, 41526
RECORD = 'auf_wiedersehen_monty'
_HERE = os.path.dirname(os.path.abspath(__file__))

SITES = {   # addr: (original, symbol or new bytes, resume, kind)
    FIG_CALL: ('cdada2', 'e_fig', FIG_RET, 'figures'),
    34894: ('210040', 'e_cls', 34897, 'clear screen'),
    42878: ('cdbca7', 'e_room', 42881, 'room draw'),
    41725: ('12', '00', None, 'painter store'),
}
CALL_SITES = {FIG_CALL, 42878}                 # CALL hook: the original CALL's target replaced, the return address kept
HOOKS = {a: s for a, s in SITES.items() if s[2] is not None}
INTERIORS = (41524, 41525, 34895, 34896, 42879, 42880)
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all registers but R, T, MEMPTR


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_auf_wiedersehen_monty(snap):
    """The 128K release at its figure loop: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory)."""
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    sig, a = bytes.fromhex(sg['bytes']), sg['addr']
    banks = getattr(snap, 'banks', None)
    if banks is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return bytes(snap.memory[a:a + len(sig)]) == sig
    if not getattr(snap, 'is128', False):
        return False
    return bytes(banks[2][a - 0x8000:a - 0x8000 + len(sig)]) == sig


class AufWiedersehenMontyPatch:
    name = 'Auf Wiedersehen Monty figures -> hardware sprites over the composite figures (altrom, painter store off)'

    def __init__(self, prof=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False           # its 0x5B00-0x5BFF come back in the set-up (printer, from the snapshot)
        self.tail_addr, self.max_tail = TAIL_ADDR, TAIL_MAX   # set per snapshot in apply (tail_for)
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
            elif a in CALL_SITES:
                nb = b'\xCD' + self.syms[new].to_bytes(2, 'little')
            else:
                nb = b'\xC3' + self.syms[new].to_bytes(2, 'little') + bytes(len(old) - 3)
            self.sites.append((a, old, nb))
        self.extra_banks = {}

    def apply(self, snap):
        if not snap.is128 or snap.port7ffd & 0x17 != 0x10:
            raise ValueError('Auf Wiedersehen Monty patch expects the 128K snapshot (ROM 1, bank 0 at 0xC000)')
        b2 = bytearray(snap.banks[2])
        for a, old, new in self.sites:
            cur = bytes(b2[a - 0x8000:a - 0x8000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            b2[a - 0x8000:a - 0x8000 + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(b2) if i == 2 else bytes(snap.banks[i])) for i in range(8))
        self.tail_addr, self.max_tail = tail_for(snap)
        self.extra_banks = {12: self.page + bytes(8192)}
        setup = bytes.fromhex(self.prof['hooks']['setup'])
        assert self.syms['printer'] - self.setup_call == len(setup)
        self.stub_extra = setup + bytes(snap.banks[5][0x1B00:0x1C00])   # the game reads 0x5B00 on; NEXLOAD wrote it


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
        else:
            self.ports.append((port & 0xFF, val))

    def visible(self, i):
        return bool(self.attr[i][3] & 0x80)

    def pixels(self, i, out=None):
        """Ink pixels of a visible 4-bit sprite (X mirror honoured) in ULA coordinates, inside the 256 x 192 screen."""
        out = set() if out is None else out
        a0, a1, a2, a3, a4 = self.attr[i]
        if not a3 & 0x80:
            return out
        if not (a3 & 0x40 and a4 & 0x80):
            out.add('not a 4-bit sprite')
            return out
        x = a0 + (a2 & 1) * 256 - 32
        y = a1 + (a4 & 1) * 256 - 32
        mir = bool(a2 & 8)
        base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
        for j in range(16):
            p = base + j * 8
            for k in range(8):
                b = self.pat[p + k]
                for half, c in ((b >> 4, 2 * k), (b & 15, 2 * k + 1)):
                    xx = x + (15 - c if mir else c)
                    if half and 0 <= y + j < 192 and 0 <= xx < 256:
                        out.add((xx, y + j))
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
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if self.ns is not None:
            self.ns.port(port, value)
        else:
            self.ports.append((port & 0xFF, value))


def _run(sim, stop, limit=2000000):
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
    stop = SITES[pc][2] if stop is None else stop
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
    if not _run(sp, stop):
        fl.append('hook did not reach the resume point')
        return fl, 0, 0
    for i in CMP:
        if so.registers[i] != sp.registers[i]:
            fl.append('register %d: original %02X, patched %02X' % (i, so.registers[i], sp.registers[i]))
    if p.romw:
        fl.append('hook wrote the ROM')
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
        if 0x5800 <= a < 0x5B00 and pc == FIG_CALL:
            if a in p.ov:
                fl.append('patched figure loop wrote an attribute (%04X)' % a)
                break
            skipped += vo != get(a)
            continue
        if vo != vp:
            fl.append('memory %04X: original %02X, patched %02X' % (a, vo, vp))
            break
    return fl, sp.registers[25] - so.registers[25], skipped


def expected(get, i):
    """What the figure hook leaves in sprite i for record i: (attributes, 128 pattern bytes)."""
    r = FIGS + 13 * i
    x, y, col, frm, flags = get(r), get(r + 1), get(r + 2), get(r + 7), get(r + 9)
    img = GFX + 32 * frm
    pat = bytearray()
    for k in range(32):
        v = get(img + k)
        pat += bytes((0x10 if v & (0x80 >> 2 * q) else 0) | (1 if v & (0x40 >> 2 * q) else 0) for q in range(4))
    pal = (col & 7) | (8 if col & 0x40 else 0)
    X, Y = x + 32, y + 32
    a2 = pal << 4 | (0 if flags & 0x80 else 8) | X >> 8
    return [X & 255, Y & 255, a2, 0xC0 | i, 0x80 | Y >> 8], bytes(pat)


# ---------------------------------------------------------------------------------------------
# Verification against a recording
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, progress=None, collect=0):
    """Replay the RZX on the original; an event at every hook; after every figure loop, each figure's pixels as the
    game's own drawer ORed them into its composite cells must be ink in that figure's sprite. -> (Counter, examples)."""
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
            h.drawn = None                            # {figure: set of (x, y)} during a figure loop
            h.pos = None

        def on_sim(h, sim):
            h.R, h.mem = sim.registers, sim.memory
            h.reset()
            c['segments'] += 1

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
            if h.drawn is None or pc not in DRAW_WRITES or not COMP <= a < COMP + 72 * NFIG:
                return
            new = v & ~h.get(a) & 255                  # bits the drawer turns on: the figure's own pixels
            if not new:
                return
            i, off = divmod(a - COMP, 72)
            col, row = divmod(off, 24)
            x, y = h.pos[i]
            for k in range(8):
                if new >> (7 - k) & 1:
                    h.drawn[i].add(((x & 0xF8) + 8 * col + k, (y & 0xF8) + row))

        def before(h, pc):
            if pc in HOOKS:
                kind = HOOKS[pc][3]
                c[kind] += 1
                cnt[pc] += 1
                if collect and len(states) < collect and pc == FIG_CALL and c[kind] % 97 == 1:
                    states.append((pc, list(h.R), bytes(h.get(a) for a in range(65536))))
                fl, t, skipped = event(patch, pc, h.get, h.R, h.ns, alt, psite)
                c['hook T (28 MHz, patched minus original)'] += t
                c['hook T %s' % kind] += t
                c['attribute bytes not painted'] += skipped
                for k in fl:
                    h.fail('%s: %s' % (kind, k))
                if pc == FIG_CALL:
                    h.drawn = {i: set() for i in range(NFIG)}
                    h.pos = [(h.get(FIGS + 13 * i), h.get(FIGS + 13 * i + 1)) for i in range(NFIG)]
                    for i in range(NFIG):
                        want = expected(h.get, i)
                        if h.ns.attr[i] != want[0] or bytes(h.ns.pat[i * 256:i * 256 + 128]) != want[1]:
                            h.fail('sprite %d not as its record' % i, (h.ns.attr[i], want[0]))
                elif any(h.ns.visible(s) for s in range(NFIG)):
                    h.fail('%s left a sprite shown' % kind)
                for s in range(NFIG, 128):
                    if h.ns.visible(s):
                        h.fail('sprite %d shown' % s)
            elif pc == FIG_RET and h.drawn is not None:
                h.compare()
            elif pc in INTER:
                cnt[pc] += 1

        def compare(h):
            c['figure checks'] += 1
            for i in range(NFIG):
                truth = {p for p in h.drawn[i] if p[0] < 256 and p[1] < 192}
                got = h.ns.pixels(i)
                missing = truth - got
                if missing:
                    h.fail('figure %d pixels not in its sprite' % i, (sorted(missing)[:3], len(truth), len(got)))
                else:
                    c['figure pixels covered'] += len(truth)
                    c['sprite pixels the game masked off scenery (known)'] += len(got - truth)
            h.drawn = None

    cnt = collections.Counter()
    states = []
    h = H()
    c['frames'] = play_rzx(rzx_path, h, stop=stop)
    for a in INTER:
        if cnt[a]:
            c['jump into a patched instruction (%04X)!' % a] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


def unit_tests(patch, states):
    """Every record field the hook reads, at edge values, from states the recording reached: registers and memory
    as the original's (event), each sprite as expected(); the hide hooks with all five shown first."""
    c = collections.Counter()
    alt = _alt(patch)
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    cases = [(0, 0, 0x07, 0x80, 1), (8, 24, 0x47, 0x00, 5), (223, 120, 0x45, 0x80, 61), (224, 136, 0x02, 0x00, 125),
             (232, 152, 0x44, 0xFE, 189), (100, 16, 0x40, 0x01, 223), (17, 63, 0xC6, 0x7F, 18)]
    for pc, R, mem in states[:8]:
        for k, (x, y, col, flags, frm) in enumerate(cases):
            m = bytearray(mem)
            for i in range(NFIG):
                r = FIGS + 13 * i
                m[r], m[r + 1], m[r + 2], m[r + 7], m[r + 9] = (x + 8 * i) & 255 if x < 224 else x, y, col, frm, flags
            ns = NextState()
            fl, _, _ = event(patch, pc, m.__getitem__, R, ns, alt, psite)
            bad = list(fl)
            for i in range(NFIG):
                a, p = expected(m.__getitem__, i)
                if ns.attr[i] != a or bytes(ns.pat[i * 256:i * 256 + 128]) != p:
                    bad.append('sprite %d %s, expected %s' % (i, ns.attr[i], a))
            c['figure hook' + (' FAIL!' if bad else ' ok')] += 1
            if bad and c['  example'] < 3:
                c['  example'] += 1
                c['  case %d: %s' % (k, bad[:2])] += 1
    for pc in (34894, 42878):
        for _, R, mem in states[:8]:
            ns = NextState()
            for s in range(NFIG):
                ns.attr[s] = [9, 9, 0, 0xC0 | s, 0x80]
            R2 = list(R)
            R2[24] = pc
            stop = 42940 if pc == 42878 else None     # room draw: to the row routine's entry (the state is not a room's)
            fl, _, _ = event(patch, pc, mem.__getitem__, R2, ns, alt, psite, stop=stop)
            bad = list(fl) + ['sprite %d left shown' % s for s in range(NFIG) if ns.visible(s)]
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
    no_paint.sites = [s for s in patch.sites if s[0] != 41725]
    return [('sprites one row low', _broken(patch, 'neg_y', b'\xC6\x21')),          # ADD A,33
            ('ink lost in the pattern upload', _broken(patch, 'neg_pix', b'\xE6\x00')),
            ('mirror never set', _broken(patch, 'neg_mir', b'\xF6\x00')),            # OR 0
            ('figure hook never shows the sprites', _broken(patch, 'neg_fig', b'\0\0\0')),
            ('clear screen leaves the sprites', _broken(patch, 'neg_cls', b'\0\0\0')),
            ('room draw leaves the sprites', _broken(patch, 'neg_room', b'\0\0\0')),
            ('painter store left on', no_paint)]


class PlainPatch:
    """The original game, no hooks: only the snapshot's printer buffer put back after NEXLOAD (the game reads it)."""
    name = 'Auf Wiedersehen Monty 128K: the original game, no hooks'
    uses_printer_buffer = False
    hook_page_data = b''
    extra_banks = {}
    sites = []
    slot1 = None
    tail_addr, max_tail = TAIL_ADDR, TAIL_MAX

    def __init__(self):
        from . import z80tonex as zt
        self.setup_call = zt.STUB_ORG + 0x1000
        self.stub_extra = b''

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('expects the 128K snapshot')
        src = self.setup_call + 12
        code = b'\x21' + src.to_bytes(2, 'little') + b'\x11\x00\x5b' + b'\x01\x00\x01' + b'\xED\xB0' + b'\xC9'
        assert len(code) == 12
        self.stub_extra = code + bytes(snap.banks[5][0x1B00:0x1C00])
        self.tail_addr, self.max_tail = tail_for(snap)


def build(z80, out, name, say=print):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, None, True, quiet=True, patch=pp)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = AufWiedersehenMontyPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    return not bad and not bad2, patch


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : auf_wiedersehen_monty (composite figures, sprites as an overlay, painter store off)')
    ok, patch = build(z80, out, name, say)
    for r in list(a.rzx or []):
        c, ex = verify(patch, r, stop=getattr(a, 'quick', None))
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d segments, %d figure loops, %d screen clears, %d room draws, %d figure checks, '
            '%d figure pixels covered; %d attribute bytes not painted -> %s' % (
                os.path.basename(r), c['frames'], c['segments'], c['figures'], c['clear screen'], c['room draw'],
                c['figure checks'], c['figure pixels covered'], c['attribute bytes not painted'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
