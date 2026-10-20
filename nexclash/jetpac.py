"""Jetpac (Ultimate Play The Game, 1983, 16K) engine 'jetpac'. Additive module: reachable only
through is_jetpac().

Game facts (games/jetpac.md has the details):
  30522  move-and-redraw plotter: per object, erase the old frame (CPL/AND, 30529-30532) and draw
         the new one (OR, 30559-30561) line by line upwards (29422), wrapping within the 32-byte
         row. Graphic = [y offset, W, H, W*H bytes, rows BOTTOM line first].
  29247  new-frame setup (IX = object 23808 + 8i): DE -> graphic, 29448 -> HL = screen address of
         the bottom line; 29263 is right after it (the draw hook).
  29344 / 29349  erase-only entries (object removed or changing graphic): hide.
  29135  paints (IX+3) over the figure's cells (29171 LD (HL),D): removed.
  24714  screen clear (every new screen): hide all.
  Graphics: Jetman ROM 30614-31640 (table 30458), rockets / fuel / items table 26563, explosion
  31692/31743/31794, aliens built per level (24048 & 7) into 24064/24115/24166/24217 by 26921,
  the carried rocket part pre-shifted into 24268/24319/24370/24421 by 28409 (part (23860), rocket
  (24048) >> 2).
  No game logic reads the screen (readers: the plotter itself, the laser eraser 28828, the HUD
  flash 25035/25048); collisions use coordinates.
Hooks (asm/jetpac_hooks.asm, alt ROM image 1, stateless; tables asm/jetpac_tables.asm generated
by `python -m nexclash.jetpac tables`): each object owns 6 sprites (2 rows x up to 3 placements:
2 columns + 1 copy wrapped to the left edge, as the ULA row wrap); colour = the object's (IX+3)
ink (palette offset ink + 8 * bright, index 1).
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00              # printer buffer: zero, never touched (scan)
OBJ0, NOBJ, SPO = 23808, 17, 6  # object table, objects, sprites per object
JET_TAB, ITEM_TAB = 30458, 26563
EXPLO = (31692, 31743, 31794)
ALIEN_BUF = (24064, 24115, 24166, 24217)
CARRY_BUF = (24268, 24319, 24370, 24421)
LEVEL, PART = 24048, 23860
SITES_ORIG = {29263: '1a4732', 29344: 'cd2772', 29349: 'cd2472', 24717: 'cdb871'}
SITE_SYM = {29263: 'e_nw', 29344: 'e_e1', 29349: 'e_e2', 24717: 'e_cls'}
SITE_OP = {29263: 0xC3, 29344: 0xCD, 29349: 0xCD, 24717: 0xCD}
SCREEN_PATCHES = [(30532, '77', '00'), (30561, '77', '00'), (29171, '72', '00')]
INTERIORS = (29264, 29265, 29345, 29346, 29350, 29351, 24718, 24719)
SITE_KIND = {29263: 'nw', 29344: 'er', 29349: 'er', 24717: 'cls', 29135: 'at'}
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6,
          0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, '..')


def _profile_path():
    for p in (os.path.join(_ROOT, 'docs', 'profiles', 'jetpac.json'), os.path.join(_HERE, 'jetpac.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('jetpac.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_jetpac(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


# ---------------------------------------------------------------------------------------------
# Graphics -> images -> patterns -> lookup tables
# ---------------------------------------------------------------------------------------------

w16 = lambda m, a: m[a] | m[a + 1] << 8


def image(m, a):
    """Graphic at a -> (W, H, {(x, r)}): x pixel from the byte column, r = 0 bottom line, or None."""
    W, H = m[a + 1], m[a + 2]
    if not (1 <= W <= 4 and 1 <= H <= 32):
        return None
    return W, H, {(8 * (k % W) + b, k // W) for k in range(W * H) for b in range(8)
                  if m[a + 3 + k] & (0x80 >> b)}


def _call(mem, pc, regs=None):
    from skoolkit.simulator import Simulator
    mem[0xFF00] = mem[0xFF01] = 0
    r = {'SP': 0xFF00, 'PC': pc}
    r.update(regs or {})
    s = Simulator(mem, r)
    n = 0
    while s.registers[24] != 0:
        s.opcodes[mem[s.registers[24]]]()
        n += 1
        if n > 3000000:
            raise RuntimeError('builder %d did not return' % pc)
    return mem


_BUILT = {}


def _memo(m0, *key):
    """alien_mem / carry_mem results per (snapshot memory, key): the unit tests ask for the same
    level / part thousands of times (Jetpac: 4,008 builder runs -> a few dozen)."""
    k = (hash(bytes(m0)),) + key
    if k not in _BUILT:
        _BUILT[k] = (alien_mem_ if key[0] == 'a' else carry_mem_)(m0, *key[1:])
    return _BUILT[k]


def alien_mem(m0, level):
    return _memo(m0, 'a', level)


def carry_mem(m0, level, part):
    return _memo(m0, 'c', level, part)


def alien_mem_(m0, level):
    mm = list(m0)
    mm[LEVEL] = level
    return _call(mm, 26921)


def carry_mem_(m0, level, part):
    mm = list(m0)
    mm[LEVEL], mm[PART] = level, part
    return _call(mm, 28409, {'A': (part << 3) & 56})


def graphics(m0):
    """{('s', addr) | ('a', addr, level) | ('c', addr, part, level): image} for every graphic."""
    g = {}
    for i in range(16):
        a = w16(m0, JET_TAB + 2 * i)
        g[('s', a)] = image(m0, a)
    for i in range(21):
        a = w16(m0, ITEM_TAB + 2 * i)
        g[('s', a)] = image(m0, a)
    for a in EXPLO:
        g[('s', a)] = image(m0, a)
    for L in range(8):
        mm = alien_mem(m0, L)
        for a in ALIEN_BUF:
            g[('a', a, L)] = image(mm, a)
    for L in range(16):
        for n in range(3):
            mm = carry_mem(m0, L, n)
            for a in CARRY_BUF:
                g[('c', a, n, L >> 2)] = image(mm, a)
    return g


def layout(img):
    """image -> (key, xadj, cols, rows, trimmed pixels {(x, r)}) or None (empty)."""
    W, H, px = img
    if not px:
        return None
    x0 = min(x for x, r in px)
    x1 = max(x for x, r in px)
    cols = (x1 - x0) // 16 + 1
    rows = (H - 1) // 16 + 1
    t = frozenset((x - x0, r) for x, r in px)
    return t, x0, cols, rows


def build(m0):
    """-> (patterns bytes, entries {gkey: (pat, cols, rows, xadj)})."""
    pats = bytearray()
    first = {}
    ent = {}
    for k, img in graphics(m0).items():
        if img is None:
            continue
        lo = layout(img)
        if lo is None:
            continue
        t, x0, cols, rows = lo
        if cols > 2 or rows > 2:
            raise ValueError('graphic %s too big for 2x2 sprites' % (k,))
        if (t, rows) not in first:
            first[(t, rows)] = len(pats) // 128
            for rr in range(rows):
                for cc in range(cols):
                    for j in range(16):             # pattern line j (top down) of row rr
                        r = 16 * rows - 1 - (16 * rr + j)      # data row (0 = bottom)
                        for x in range(16 * cc, 16 * cc + 16, 2):
                            hi = 1 if (x, r) in t else 0
                            lo_ = 1 if (x + 1, r) in t else 0
                            pats.append(hi << 4 | lo_)
        ent[k] = (first[(t, rows)], cols, rows, x0)
    if len(pats) > 128 * 128:
        raise ValueError('%d patterns > 128' % (len(pats) // 128))
    return bytes(pats), ent


def tables_asm(ent):
    """The hooks' lookup tables (asm/jetpac_tables.asm)."""
    E = lambda e: 'db %d,%d,%d' % (e[0], (e[1] - 1) | (e[2] - 1) << 1, e[3]) if e else 'db 255,0,0'
    out = ['; GENERATED by `python -m nexclash.jetpac tables` from the Jetpac snapshot - do not edit.',
           '; gtab: dw graphic address; db kind (0 entry follows, 1 alien by level, 2 carried part);',
           ';       kind 0: db pattern, layout (cols-1 | (rows-1)<<1), x adjust; kind 1/2: dw subtable, db 0',
           'gtab:']
    subs = []
    stat = sorted(k[1] for k in ent if k[0] == 's')
    for a in stat:
        e = ent[('s', a)]
        out.append('        dw %d : db 0 : %s' % (a, E(e)))
    for a in ALIEN_BUF:
        out.append('        dw %d : db 1 : dw sa%d : db 0' % (a, a))
        subs.append('sa%d:' % a)
        for L in range(8):
            subs.append('        ' + E(ent.get(('a', a, L))))
    for a in CARRY_BUF:
        out.append('        dw %d : db 2 : dw sc%d : db 0' % (a, a))
        subs.append('sc%d:' % a)
        for n in range(3):
            for r in range(4):
                subs.append('        ' + E(ent.get(('c', a, n, r))))
    out.append('        dw 0')
    return '\n'.join(out + subs) + '\n'


def tables_text(pats, ent):
    return tables_asm(ent) + 'NPAT256 EQU %d\n' % ((len(pats) + 255) // 256)


def sprite_pixels(attr, pat):
    """Visible 4-bit sprite -> {(x, y)} ink pixels in ULA coordinates."""
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return set()
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    n = (a3 & 0x3F) * 2 + (1 if a4 & 0x40 else 0)
    out = set()
    for j in range(16):
        for k in range(16):
            b = pat[n * 128 + j * 8 + k // 2] if n * 128 + j * 8 + k // 2 < len(pat) else 0
            if (b >> 4) if k % 2 == 0 else (b & 15):
                out.add((x + k, y + j))
    return out


def main(argv=None):
    import argparse
    from skoolkit.snapshot import get_snapshot
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['tables'])
    ap.add_argument('z80')
    a = ap.parse_args(argv)
    m0 = list(get_snapshot(a.z80))
    pats, ent = build(m0)
    open(os.path.join(_ROOT, 'asm', 'jetpac_tables.asm'), 'w').write(tables_text(pats, ent))
    print('%d graphics, %d patterns -> asm/jetpac_tables.asm' % (len(ent), len(pats) // 128))


if __name__ == '__main__':
    main()


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

class JetpacPatch:
    name = 'Jetpac figures -> hardware sprites (altrom, stateless hooks)'

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
        self.max_tail = 128                 # 0x5B80-0x5B8D: loader leftover (never touched)
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
                               bytes([SITE_OP[a]]) + self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.pats = None
        self.num_patterns = 0

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Jetpac patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + self.max_tail]):
            raise ValueError('printer buffer 0x5B00-0x5B7F is not empty in this snapshot (tail site)')
        m0 = [0] * 0x4000 + list(ram)
        self.pats, ent = build(m0)
        want = tables_text(self.pats, ent)
        have = open(os.path.join(_ROOT, 'asm', 'jetpac_tables.asm')).read()
        if want != have:
            raise ValueError('asm/jetpac_tables.asm was not made from this snapshot '
                             '(python -m nexclash.jetpac tables GAME.z80, then tools/asm2profile.py jetpac)')
        self.num_patterns = len(self.pats) // 128
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        pats = self.pats + bytes(16384 - len(self.pats))
        self.extra_banks = {11: pats, 12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Differential test: original vs patched from the same state at every hook site
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, pats):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytes(pats)
        self.events = []

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def obj_pixels(self, i):
        """{(x, y): palette offset} of object i's sprites, inside the ULA area."""
        out = {}
        for s in range(SPO * i, SPO * i + SPO):
            a = self.attr[s]
            for x, y in sprite_pixels(a, self.pat):
                if 0 <= x < 256 and 0 <= y < 192:
                    out[(x, y)] = a[2] >> 4
        return out


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


def _run(sim, stop, limit=400000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


def _overlays(get, alt, psite, canvas=None):
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


def _screen_set(ov):
    out = set()
    for a, v in ov.items():
        if 0x4000 <= a < 0x5800:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                if (v >> (7 - k)) & 1:
                    out.add(((a & 31) * 8 + k, y))
    return out


def obj_index(ix):
    d = ix - OBJ0
    return d >> 3 if 0 <= d < 8 * NOBJ and not d & 7 else None


def event(patch, kind, get, R, ns, alt, Sim):
    """One hook event, original and patched from the same state. -> (failures, pixels compared)."""
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    sp0 = R[12]
    w = lambda a: get(a) | get(a + 1) << 8
    f = []
    if kind == 'nw':
        ret, end = w(sp0 + 2), sp0 + 4
    elif kind == 'cls':
        ret, end = R[24] + 3, sp0
    else:                                   # er, at: the routine's own caller
        ret, end = w(sp0), sp0 + 2

    def stop(r):
        return r[24] == ret and r[12] == end
    obj = obj_index(R[8] << 8 | R[9])
    O, P = _overlays(get, alt, psite)
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
    if any(e[1] not in (0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39) for e in ns.events if e[0] == 'nr'):
        f.append(('NEXTREG other than sprite attributes / CPU speed',))
    if ns.nr.get(0x07, 0) != 0:
        f.append(('hook left the CPU at 28 MHz',))
    dead = range(ro[12] - 64, ro[12])
    keys = set(o.ov) | set(p.ov)
    scr = (0x4000, 0x5B00) if kind != 'cls' else (0, 0)
    md = [a for a in keys if not scr[0] <= a < scr[1] and a not in dead and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    npx = 0
    changed = [i for i in range(128) if ns.attr[i] != before[i]]
    mine = set(range(SPO * obj, SPO * obj + SPO)) if obj is not None else set()
    if kind == 'cls':
        if any(ns.attr[i][3] & 0x80 for i in range(128)):
            f.append(('sprite visible after screen clear',))
        return f, 0
    if any(0x4000 <= a < 0x5B00 for a in p.ov):
        f.append(('patched code wrote the screen',))
    if kind == 'at':
        if changed:
            f.append(('sprites changed by the colour paint',))
        return f, 0
    if set(changed) - mine:
        f.append(('other sprites changed', sorted(set(changed) - mine)[:4]))
    if kind == 'er':
        if obj is not None and any(ns.attr[i][3] & 0x80 for i in mine):
            f.append(('sprite still visible after erase', obj))
        return f, 0
    # nw: the original's new figure, drawn on a zero screen, against the object's sprites
    Oc, _ = _overlays(get, alt, psite, (0x4000, 0x5800))
    oc = Oc()
    sc = _machine(Sim, oc, list(R), NextState(b''), 'c')
    if not _run(sc, stop):
        return f + ['canvas run did not return'], 0
    drawn = _screen_set(oc.ov)
    if obj is None:
        if drawn:
            f.append(('figure drawn but no object slot', len(drawn)))
        return f, 0
    got = ns.obj_pixels(obj)
    npx = len(drawn)
    if set(got) != drawn:
        f.append(('sprite pixels differ from the original plot', len(set(got) ^ drawn)))
    a3 = get((R[8] << 8 | R[9]) + 3)
    want = (a3 & 7) | ((a3 >> 3) & 8)
    if any(v != want for v in got.values()):
        f.append(('sprite colour is not the object ink',))
    return f, npx


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def verify(patch, z80, rzx=None, frames=6000, keys=None, stop=None, collect=0, progress=None):
    """Run the original game (RZX, or a free run with a key schedule); at every hook site and at
    the colour paint 29135 run original and patched code from the same state and compare.
    -> (Counter, examples, states)."""
    from . import simrun
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    ns = NextState(patch.pats)
    st = {'frame': 0}
    states = []
    cnt = collections.Counter()
    WATCH = set(SITE_KIND) | set(INTERIORS)

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class H:
        def on_sim(self, sim):
            st['sim'] = sim

        def on_write(self, addr, value, pc, mem):
            if addr in site_bytes:
                fail('game wrote a patch site', (addr, pc))

        def before(self, pc):
            if pc not in WATCH:
                return
            if pc in INTERIORS or pc == 29263:
                cnt[pc] += 1
                if pc in INTERIORS:
                    return
            sim = st['sim']
            R, mem = sim.registers, sim.memory
            get = mem.__getitem__
            kind = SITE_KIND[pc]
            if collect and c['collected ' + kind] < collect:
                c['collected ' + kind] += 1
                states.append((kind, list(R), bytes(get(a) for a in range(65536)),
                               [list(x) for x in ns.attr]))
            fl, npx = event(patch, kind, get, R, ns, alt, _rw())
            c[kind] += 1
            c['sprite pixels compared'] += npx
            for k in fl:
                fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k),
                     k[1:] if isinstance(k, tuple) else ())

        def on_frame(self, n):
            st['frame'] = n
            if progress and n % 1000 == 0:
                progress(n, c)

    c['frames'] = simrun.run(z80, [rzx] if rzx else None, H(), frames=frames, keys=keys, stop=stop)
    # 29264/29265 are instructions of the original (LD B,A / LD (24004),A after LD A,(DE) at 29263):
    # reached only straight after 29263; the CALL sites' interiors never
    if not cnt[29263] == cnt[29264] == cnt[29265]:
        c['29264/29265 reached other than from 29263!'] += 1
    for a in INTERIORS:
        if a not in (29264, 29265) and cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    return c, dict(ex), states


# ---------------------------------------------------------------------------------------------
# Unit tests: every graphic (all levels, carried parts) x edge positions x colours, erase and
# clear cases, the object guard, a negative control
# ---------------------------------------------------------------------------------------------

POS = ((0, 23), (7, 40), (100, 100), (200, 191), (238, 60), (247, 120), (255, 80), (128, 15))
INKS = (0x47, 0x02, 0x45)


def _setup_graphic(mem, m0, key):
    """Memory for graphic key (buffers, level, part) -> graphic start address."""
    if key[0] == 'a':
        src = alien_mem(m0, key[2])
        for a in range(ALIEN_BUF[0], ALIEN_BUF[-1] + 51):
            mem[a] = src[a]
        mem[LEVEL] = key[2]
    elif key[0] == 'c':
        src = carry_mem(m0, key[3] << 2, key[2])
        for a in range(CARRY_BUF[0], CARRY_BUF[-1] + 51):
            mem[a] = src[a]
        mem[LEVEL], mem[PART] = key[3] << 2, key[2]
    return key[1]


def _to_site(R, mem, gaddr, x, y, ink, ix):
    """From a captured 29263 state: re-enter 29247 with DE = graphic, object ix at (x, y) -> the
    state at 29263 (registers), memory updated in place."""
    Sim = _rw()
    mem[ix + 1], mem[ix + 2], mem[ix + 3] = x, y, ink
    r = list(R)
    r[24] = 29247
    r[4], r[5] = gaddr >> 8, gaddr & 255
    r[8], r[9] = ix >> 8, ix & 255
    from .simpool import machine, copy_back
    sim = machine(Sim, mem, r, 'site', copy=True)
    done = _run(sim, lambda q: q[24] == 29263, 5000)
    copy_back(sim, mem)
    if not done:
        return None
    return list(sim.registers)


def unit_tests(patch, states, neg=None, m0=None):
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    gk = sorted(k for k, v in graphics(m0).items() if v is not None and layout(v) is not None)

    def one(pt, kind, R, mem, attrs):
        ns = NextState(pt.pats)
        ns.attr = [list(a) for a in attrs]
        return event(pt, kind, mem.__getitem__, R, ns, alt, Sim)

    done = set()
    for kind, R, mem0, attrs in states:
        if kind in done:
            continue
        done.add(kind)
        if kind == 'nw':
            negd = []
            for key in gk:
                for x, y in POS:
                    for ink in INKS:
                        for ix in (OBJ0, OBJ0 + 8 * (NOBJ - 1)):
                            mem = bytearray(mem0)
                            g = _setup_graphic(mem, m0, key)
                            r = _to_site(R, mem, g, x, y, ink, ix)
                            if r is None:
                                c['graphic cases: setup did not reach 29263 FAIL!'] += 1
                                continue
                            fl, npx = one(patch, kind, r, mem, attrs)
                            c['graphic cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                            if fl and c['  fail example'] < 5:
                                c['  fail example'] += 1
                                c['  %s x %d y %d ink %d ix %d %s' % (key, x, y, ink, ix, str(fl[:2])[:150])] += 1
                            if neg is not None and npx and len(negd) < 40 and ink == 0x47 and ix == OBJ0:
                                fln, _ = one(neg, kind, r, mem, attrs)
                                negd.append(bool(fln))
            c['negative control detected'] += sum(negd)
            c['negative control NOT DETECTED!'] += len(negd) - sum(negd)
            # guard: IX not an object slot -> no sprite (the game never plots one)
            mem = bytearray(mem0)
            r = _to_site(R, mem, gk[0][1] if gk[0][0] == 's' else 30614, 100, 100, 0x47, OBJ0 + 4)
            fl, _ = one(patch, kind, r, mem, attrs)
            ok = all(k[0] == 'figure drawn but no object slot' for k in fl)
            c['IX outside the object table (guard: no sprite) %s' % ('ok' if ok else 'FAIL!')] += 1
        elif kind == 'er':
            for ix in (OBJ0, OBJ0 + 8 * (NOBJ - 1)):
                r = list(R)
                r[8], r[9] = ix >> 8, ix & 255
                at = [list(a) for a in attrs]
                for i in range(128):
                    at[i][3] |= 0x80
                fl, _ = one(patch, kind, r, bytearray(mem0), at)
                c['erase cases %s' % ('ok' if not fl else 'FAIL!')] += 1
        elif kind == 'cls':
            at = [list(a) for a in attrs]
            for i in range(SPO * NOBJ):     # sprites the hooks use; 102-127 stay hidden from setup
                at[i][3] |= 0x80
            fl, _ = one(patch, kind, list(R), bytearray(mem0), at)
            c['screen clear cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    return c


def negative_patch(patch):
    """Broken copy: every pattern shifted one pixel right (the pixel check must fail)."""
    import copy
    q = copy.copy(patch)
    p = bytearray(patch.pats)
    out = bytearray(len(p))
    for r in range(len(p) // 8):
        row = int.from_bytes(p[8 * r:8 * r + 8], 'big')
        out[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
    q.pats = bytes(out)
    return q


# free-run input for the differential test when there is no recording: menu 1 player, keyboard,
# start, then Jetman walks/flies/fires left and right (keys Q/W/E/R row, A/S fire, Z/X hover)
FREE_FRAMES = 6000
DECISIONS = {'engine': 'jetpac', 'strategy': 'altrom', 'verify': 'free run %d frames (no recording)' % 6000}


def free_keys(frames=FREE_FRAMES):
    k = ['10-12:1', '20-22:3', '30-32:5']
    f = 40
    while f < frames:
        k += ['%d-%d:Q+A+Z' % (f, f + 59), '%d-%d:W+A' % (f + 60, f + 119),
              '%d-%d:E+S+X' % (f + 120, f + 159), '%d-%d:R+D' % (f + 160, f + 229)]
        f += 230
    return ';'.join(k)


def auto(a, z80, name, out, say):
    import hashlib
    from skoolkit.snapshot import get_snapshot
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : jetpac (Jetpac: move-and-redraw plotter 30522 -> sprites, every figure)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = printer buffer, never touched)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = JetpacPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (%d patterns)' % (os.path.basename(spr), md5(spr),
        'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200], patch.num_patterns))
    ok = not bad and not bad2
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):           # selftest rebuild: build only
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    runs = [(r, None) for r in (a.rzx or [])] or [(None, free_keys())]
    states = []
    for r, keys in runs:
        frames = getattr(a, 'quick', None) or FREE_FRAMES
        c, ex, st = verify(patch, z80, r, frames=frames, keys=keys, stop=getattr(a, 'quick', None), collect=1)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!') and v}
        ok = ok and not fails
        say('Verify    : %s  %d frames, draws %d, erases %d, colour paints %d, clears %d, %d sprite pixels '
            '-> %s' % (os.path.basename(r) if r else 'free run (no recording)', c['frames'], c['nw'], c['er'],
                       c['at'], c['cls'], c['sprite pixels compared'],
                       'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, negative_patch(patch), list(get_snapshot(z80)))
        uf = {k: v for k, v in u.items() if k.endswith('!') and v}
        ok = ok and not uf
        say('Unit      : graphics %d (every graphic, all levels, carried parts x positions x colours), '
            'erase %d, clears %d, guard %d, negative control %d/%d -> %s' % (
                u['graphic cases ok'], u['erase cases ok'], u['screen clear cases ok'],
                u['IX outside the object table (guard: no sprite) ok'], u['negative control detected'],
                u['negative control detected'] + u['negative control NOT DETECTED!'],
                'PASS' if not uf else 'FAIL %s' % uf))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
