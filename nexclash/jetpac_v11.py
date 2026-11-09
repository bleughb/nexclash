"""Jetpac (Ultimate Play The Game, 1983, 16K) engine 'jetpac_v11': the opt-in rework of Dean's engine
'jetpac' that builds Jon Attree's published Jet Pac .nxc v1.1 (ported from his .nxc work, 2026-11-04;
games/jetpac.md "Rework v1.1"). It is Dean's jetpac as of d7abd1c with Jon's own rocket / fuel / flames fix
(format-study/jetpac, 2026-11-02: one IX, sprite groups by table bits, not Dean's round 2 pairs), the
whole alt ROM image written by the build, the Enhanced colour set (recolour) and the loading screen.
Reached only through engines.py with `--altrom-fill whole` on Jetpac's snapshot (the record pin's opt-in
rework); without it Dean's 'jetpac' builds the frozen record. Dean's files are not changed.

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
Hooks (asm/jetpac_v11_hooks.asm, alt ROM image 1, stateless; tables asm/jetpac_v11_tables.asm generated
by `python -m nexclash.jetpac_v11 tables`): each object owns 6 sprites (2 rows x up to 3 placements:
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
FLAME = (32652, 32687)
OBJ_ROCKET, FUELS, TICK = 23856, 23861, 24012
GROUP_BASE = {1: 102, 2: 108, 3: 114}   # object 6's other sprite groups (sections 1, 2, flames)
NSPR = 120
HALF_OFFSET = 7                         # palette offset of a half-filled section (no object has this ink)
LEVEL, PART = 24048, 23860
SITES_ORIG = {29263: '1a4732', 29344: 'cd2772', 29349: 'cd2472', 24717: 'cdb871',
              29279: 'cd2772', 29290: 'cd3c72', 29339: 'cd3f72', 29365: 'cd3c72', 29294: 'cd2472', 29287: 'd91807', 29368: 'd9af32'}
SITE_SYM = {29263: 'e_nw', 29344: 'e_e1', 29349: 'e_e2', 24717: 'e_cls',
            29279: 'e_p27', 29290: 'e_p3c', 29339: 'e_p3f', 29365: 'e_p3c', 29294: 'e_x1', 29287: 'e_x2', 29368: 'e_x3'}
SITE_OP = {29263: 0xC3, 29344: 0xCD, 29349: 0xCD, 24717: 0xCD,
           29279: 0xCD, 29290: 0xCD, 29339: 0xCD, 29365: 0xCD, 29294: 0xCD, 29287: 0xC3, 29368: 0xC3}
# The pace window (asm "Pace"): site -> (the original's next PC, SP change, 'pre' = opens the window / 'end' = closes it)
PACE_SITES = {29279: (29223, -2, 'pre'), 29290: (29244, -2, 'pre'), 29339: (29247, -2, 'pre'), 29365: (29244, -2, 'pre'),
              29294: (29223, -2, 'end'), 29287: (29297, 0, 'end'), 29368: (29373, 0, 'end')}
# Where a window's entry returns to: the plot's caller is at this stack offset from the site's SP
PLOT_STACK = {29279: 2, 29290: 0, 29339: 0, 29365: 0}
RAM_ORG = 0xB000                # hook RAM (bank 2): code, fixed bytes; the snapshot's block is zero
SCREEN_PATCHES = [(30532, '77', '00'), (30561, '77', '00'), (29171, '72', '00')]
INTERIORS = (29264, 29265, 29345, 29346, 29350, 29351, 24718, 24719,
             29280, 29281, 29291, 29292, 29340, 29341, 29366, 29367, 29295, 29296, 29288, 29289, 29369, 29370)
SITE_KIND = {29263: 'nw', 29344: 'er', 29349: 'er', 24717: 'cls', 29135: 'at'}
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6,
          0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, '..')


def _profile_path():
    for p in (os.path.join(_ROOT, 'docs', 'profiles', 'jetpac_v11.json'), os.path.join(_HERE, 'jetpac_v11.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('jetpac_v11.json profile not found')


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
    for a in EXPLO + FLAME:
        g[('s', a)] = image(m0, a)
    for L in range(8):
        mm = alien_mem(m0, L)
        for a in ALIEN_BUF:
            g[('a', a, L)] = image(mm, a)
    for L in range(16):
        for n in range(4):                      # 3 = the fuel, after the last part (26044: A = 24)
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


def groups(m0):
    """{graphic address: layout group} for what object 6 draws: sections 1, 2 and the flames."""
    g = {w16(m0, ITEM_TAB + 2 * (r + 4 * j)): j for r in range(4) for j in range(3)}
    g.update({a: 3 for a in FLAME})
    return g


def band_shapes(m0):
    """Patterns of the rocket sections: their upper 8 lines are nibble 15 (see the hooks)."""
    return {layout(image(m0, a))[:1] + layout(image(m0, a))[3:] for a, j in groups(m0).items() if j < 3}


def build(m0):
    """-> (patterns bytes, entries {gkey: (pat, cols, rows, xadj, group)})."""
    pats = bytearray()
    first = {}
    ent = {}
    grp = groups(m0)
    band = band_shapes(m0)
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
                            ink = 15 if (t, rows) in band and r >= 8 else 1
                            hi = ink if (x, r) in t else 0
                            lo_ = ink if (x + 1, r) in t else 0
                            pats.append(hi << 4 | lo_)
        ent[k] = (first[(t, rows)], cols, rows, x0, grp.get(k[1], 0) if k[0] == 's' else 0)
    if len(pats) > 128 * 128:
        raise ValueError('%d patterns > 128' % (len(pats) // 128))
    return bytes(pats), ent


def tables_asm(ent):
    """The hooks' lookup tables (asm/jetpac_v11_tables.asm)."""
    E = lambda e: 'db %d,%d,%d' % (e[0], (e[1] - 1) | (e[2] - 1) << 1 | e[4] << 2, e[3]) if e else 'db 255,0,0'
    out = ['; GENERATED by `python -m nexclash.jetpac_v11 tables` from the Jetpac snapshot - do not edit.',
           '; gtab: dw graphic address; db kind (0 entry follows, 1 alien by level, 2 carried part);',
           ';       kind 0: db pattern, layout (cols-1 | (rows-1)<<1 | group<<2), x adjust; kind 1/2: dw subtable, db 0',
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
        for n in range(4):
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


def palette_colour(offset, nibble):
    """The default build's palette: offset n, nibbles 1 and 15 = Spectrum colour n, except offset 7."""
    if offset == HALF_OFFSET:
        return 11 if nibble == 1 else 15
    return offset


def sprite_colours(attr, pat):
    """Visible 4-bit sprite -> {(x, y): Spectrum colour} in ULA coordinates."""
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return {}
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    n = (a3 & 0x3F) * 2 + (1 if a4 & 0x40 else 0)
    out = {}
    for j in range(16):
        for k in range(16):
            at = n * 128 + j * 8 + k // 2
            b = pat[at] if at < len(pat) else 0
            v = (b >> 4) if k % 2 == 0 else (b & 15)
            if v:
                out[(x + k, y + j)] = palette_colour(a2 >> 4, v)
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
    open(os.path.join(_ROOT, 'asm', 'jetpac_v11_tables.asm'), 'w').write(tables_text(pats, ent))
    print('%d graphics, %d patterns -> asm/jetpac_v11_tables.asm' % (len(ent), len(pats) // 128))


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
        # The WHOLE alt ROM image comes from the build: Sinclair's 48K ROM + hooks (2026-11-04, altrom_audit). The Next's
        # stub fills image 1 from the system ROM3 first, which is NextZXOS's, not Sinclair's: its IM 1 handler CALLs
        # 0x386E (0x004A) and its UDG print JPs to 0x387E (0x0B52), both into these hooks. Writing only 0x386E.. was
        # safe only while NextZXOS's DivMMC trap takes every 0x0038. altrom_low = Sinclair 0x0000-0x1FFF in page 25.
        self.altrom = (0x2000, 0x4000)
        self.hook_range = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[0:0x2000]))
        self.sites = []
        for a, old in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old),
                               bytes([SITE_OP[a]]) + self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.ram_code = bytes.fromhex(h['ram'])
        self.sites.append((RAM_ORG, bytes(len(self.ram_code)), self.ram_code))
        self.ram_vars = range(self.syms['HLIB_V_R'], self.syms['V_SPD'] + 1)
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
        have = open(os.path.join(_ROOT, 'asm', 'jetpac_v11_tables.asm')).read()
        if want != have:
            raise ValueError('asm/jetpac_v11_tables.asm was not made from this snapshot '
                             '(python -m nexclash.jetpac_v11 tables GAME.z80, then tools/asm2profile.py jetpac_v11)')
        self.num_patterns = len(self.pats) // 128
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        cmap = load_colours()
        if cmap:
            self.pats, used, _ = painted_patterns(m0, cmap)
            self.stub_extra = painted_setup(self.stub_extra, used)
        pats = self.pats + bytes(16384 - len(self.pats))
        self.extra_banks = {11: pats, 12: self.page + (self.altrom_low[1] if self.altrom_low else bytes(8192))}


# ---------------------------------------------------------------------------------------------
# Differential test: original vs patched from the same state at every hook site
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, pats):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytes(pats)
        self.events = []
        self.sel = None                     # NextREG selected at 0x243B (the speed read takes NR 7)

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        self.events.append(('nr', reg, val))

    def group_pixels(self, base):
        """{(x, y): Spectrum colour 0-15} of the 6 sprites from base, inside the ULA area."""
        out = {}
        for s in range(base, base + SPO):
            for (x, y), c in sprite_colours(self.attr[s], self.pat).items():
                if 0 <= x < 256 and 0 <= y < 192:
                    out[(x, y)] = c
        return out

    def obj_pixels(self, i):
        return self.group_pixels(SPO * i)

    def all_pixels(self):
        out = {}
        for s in range(NSPR):
            for (x, y), c in sprite_colours(self.attr[s], self.pat).items():
                if 0 <= x < 256 and 0 <= y < 192:
                    out[(x, y)] = c
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
            if port == 0x253B and getattr(ns, 'sel', None) is not None:   # a NextREG read: NR 7 as the core
                if ns.sel == 0x07:                                      # composes it (actual << 4 | programmed)
                    sp = ns.nr.get(0x07, 0) & 3
                    return sp << 4 | sp
                return ns.nr.get(ns.sel, 0)
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            if port == 0x243B and hasattr(ns, 'sel'):                  # NextREG select
                ns.sel = value
                return
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


from .hooklib import CMP_R as CMP      # every register, R included (v0.1.7; card patch.preserve-r), not T / MEMPTR


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


def pace_event(patch, pc, get, R, ns, alt, Sim):
    """A pace window site, original and patched from the same state to the original's next instruction: every register
    with R, memory, the speed: an entry latches the speed and goes to 28 MHz, an end gives the latch back."""
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    ret, dsp, role = PACE_SITES[pc]
    sp0 = R[12]

    def stop(r):
        return r[24] == ret and r[12] == (sp0 + dsp) & 0xFFFF
    O, P = _overlays(get, alt, psite)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    before = ns.nr.get(0x07, 0) & 3
    ns.events = []
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if not (_run(so, stop) and _run(sp_, stop)):
        return ['did not return']
    ro, rp = so.registers, sp_.registers
    f = []
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') for e in ns.events) or any(e[1] != 0x07 for e in ns.events if e[0] == 'nr'):
        f.append(('hook touched more than the CPU speed',))
    dead = range(ro[12] - 64, ro[12])
    md = [a for a in set(o.ov) | set(p.ov) if a not in dead and a not in patch.ram_vars and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    if role == 'pre':
        if ns.nr.get(0x07, 0) & 3 != 3:
            f.append(('window not at 28 MHz',))
        if p[patch.syms['V_SPD']] != before:
            f.append(("the caller's speed not latched",))
    elif ns.nr.get(0x07, 0) & 3 != get(patch.syms['V_SPD']):
        f.append(("the caller's speed not given back",))
    return f


def plot_event(patch, pc, get, R, alt, Sim, speed=0):
    """A draw from its entry to the plot's return, original and patched: registers with R, memory, the caller's speed back."""
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    sp0 = R[12]
    k = PLOT_STACK[pc]
    ret, end = get(sp0 + k) | get(sp0 + k + 1) << 8, sp0 + k + 2

    def stop(r):
        return r[24] == ret and r[12] == end
    O, P = _overlays(get, alt, psite)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    ns = NextState(patch.pats)
    ns.nr[0x07] = speed
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if not (_run(so, stop) and _run(sp_, stop)):
        return ['did not return']
    ro, rp = so.registers, sp_.registers
    f = []
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if ns.nr.get(0x07, 0) & 3 != speed:
        f.append(("the caller's speed not back at the plot's end",))
    dead = range(ro[12] - 64, ro[12])
    md = [a for a in set(o.ov) | set(p.ov) if not 0x4000 <= a < 0x5B00 and a not in dead and a not in patch.ram_vars and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    return f


def event(patch, kind, get, R, ns, alt, Sim, speed=0):
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
    ix = R[8] << 8 | R[9]
    obj = obj_index(ix)
    gaddr = (R[4] << 8 | R[5]) - 1 if kind == 'nw' else None
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
    if ns.nr.get(0x07, 0) & 3 != speed:
        f.append(('hook left the CPU at the wrong speed',))
    dead = range(ro[12] - 64, ro[12])
    keys = set(o.ov) | set(p.ov)
    scr = (0x4000, 0x5B00) if kind != 'cls' else (0, 0)
    md = [a for a in keys if not scr[0] <= a < scr[1] and a not in dead and a not in patch.ram_vars and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    npx = 0
    changed = [i for i in range(128) if ns.attr[i] != before[i]]
    base = SPO * obj if obj is not None else None
    if ix == OBJ_ROCKET and kind == 'er':
        base = GROUP_BASE[3]
    elif ix == OBJ_ROCKET and kind == 'nw':
        base = GROUP_BASE.get(_group(get, gaddr), base)
    mine = set(range(base, base + SPO)) if base is not None else set()
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
    got = ns.group_pixels(base)
    npx = len(drawn)
    if set(got) != drawn:
        f.append(('sprite pixels differ from the original plot', len(set(got) ^ drawn)))
    if ix == OBJ_ROCKET:
        want = _rocket_colours(get, gaddr, drawn)
    else:
        a3 = get(ix + 3)
        want = {p: (a3 & 7) | ((a3 >> 3) & 8) for p in drawn}
    if any(want.get(p) != v for p, v in got.items()):
        f.append(('sprite colour is not the game\'s',))
    return f, npx


def _group(get, gaddr):
    for j in range(3):
        if any(get(ITEM_TAB + 2 * (r + 4 * j)) | get(ITEM_TAB + 2 * (r + 4 * j) + 1) << 8 == gaddr for r in range(4)):
            return j
    return 3 if gaddr in FLAME else 0


def _rocket_colours(get, gaddr, drawn):
    """What the game paints on a plotted rocket piece (26488-26542), from the same fuel count and tick."""
    g = _group(get, gaddr)
    if g == 3:
        return {p: 10 for p in drawn}
    pods = get(FUELS)
    if pods >= 6:
        return {p: 15 if get(TICK) & 16 else 11 for p in drawn}
    bottom = max(y for _, y in drawn) if drawn else 0
    return {(x, y): 11 if pods >= 2 * g + 1 + (bottom - y) // 8 else 15 for x, y in drawn}


def _rom3_path():
    from . import nextboot
    return nextboot.NEXT_ROM or os.environ.get('NEXCLASH_NEXT_ROM') or os.environ.get('NEXCLASH_ROM3')


def rom3():
    """NextZXOS's ROM3 (48K BASIC: the last 16K of enNextZX.rom, MD5 8c34d957, from the card's /machines/next):
    `--next-rom` / $NEXCLASH_NEXT_ROM as the shared ROM model (nextboot.system_rom3), never in the repo."""
    p = _rom3_path()
    if not p:
        raise ValueError("jetpac_v11 verifies against NextZXOS's ROM3: give --next-rom or $NEXCLASH_NEXT_ROM (enNextZX.rom)")
    d = open(p, 'rb').read()
    if len(d) != 0x10000:
        raise ValueError('%s is not a 64K enNextZX.rom' % p)
    return d[-0x4000:]


def _alt(patch):
    """The alt ROM image as the Next's stub fills it (z80tonex.altrom_fill): the SYSTEM ROM3 copied first (NextZXOS's,
    with code at 0x386E-0x3CFE that its IM 1 handler and UDG print call), then bytes lo..hi of the patch page, then
    altrom_low over 0x0000-0x1FFF."""
    alt = bytearray(rom3())
    lo, hi = patch.altrom
    alt[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    low = getattr(patch, 'altrom_low', None)
    if low:
        alt[0:0x2000] = low[1]
    return alt


def alt_outside_hooks(patch, alt=None):
    """Addresses of the alt ROM image, outside the hook bytes, that are not Sinclair's 48K ROM (empty = whole image)"""
    from .build import rom48
    alt = alt if alt is not None else _alt(patch)
    rom = rom48()
    h0, h1 = getattr(patch, 'hook_range', patch.altrom)
    return [a for a in range(0x4000) if not h0 <= a < h1 and alt[a] != rom[a]]


def isr_event(get, R, alt, Sim, hooks=None):
    """An IM 1 interrupt (or RST 38) the original takes at 0x0038: the original ROM's handler and the patched alt ROM
    image's handler run from the same state to the return. -> failures. This is the path NextZXOS's DivMMC trap hides on
    the Next; here 0x0038 really reaches the alt ROM, as on any loader or machine without that trap."""
    sp0 = R[12]
    ret = get(sp0) | get(sp0 + 1) << 8

    def stop(r):
        return r[24] == ret and r[12] == sp0 + 2
    O, P = _overlays(get, alt, {})
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(b''))
    sp_ = _machine(Sim, p, list(R), NextState(b''), 'p')
    if not _run(so, stop, 20000):
        return ['original handler did not return']
    f = []
    if hooks:
        h0, h1 = hooks
        Rp, ops, pm = sp_.registers, sp_.opcodes, sp_.memory
        n = ran = 0
        while not stop(Rp) and n < 20000:
            if h0 <= Rp[24] < h1:
                ran += 1
            ops[pm[Rp[24]]]()
            n += 1
        if ran:
            f.append(('hook code ran', ran))
        if not stop(Rp):
            return f + ['alt ROM handler did not return']
    elif not _run(sp_, stop, 20000):
        return ['alt ROM handler did not return']
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff))
    md = [a for a in set(o.ov) | set(p.ov) if o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    if getattr(p, 'romw', 0):
        f.append(('alt ROM handler wrote ROM',))
    return f


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
    off = alt_outside_hooks(patch, alt)
    if off:
        c['alt ROM image bytes outside the hooks not Sinclair\'s!'] = len(off)
        ex['alt ROM image bytes outside the hooks not Sinclair\'s'].append((0, len(off), [hex(a) for a in off[:6]]))
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    ns = NextState(patch.pats)
    st = {'frame': 0}
    states = []
    cnt = collections.Counter()
    WATCH = set(SITE_KIND) | set(INTERIORS) | {0x0038} | set(PACE_SITES)

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class H:
        def on_sim(self, sim):
            st['sim'] = sim

        def on_write(self, addr, value, pc, mem):
            if addr in site_bytes or addr >= 0x8000:
                fail('game wrote a patch site or above 0x7FFF', (addr, pc))

        def on_read(self, addr, pc, mem):
            if addr >= 0x8000 and not st.get('busy'):     # the game's own reads, not this verifier's
                fail('game read above 0x7FFF (the hook RAM is there)', (addr, pc))

        def before(self, pc):
            if pc not in WATCH:
                return
            st['busy'] = True
            try:
                self.check(pc)
            finally:
                st['busy'] = False

        def check(self, pc):
            if pc in (29287, 29368):
                cnt[pc] += 1
            if pc in PACE_SITES:
                sim = st['sim']
                R, get = sim.registers, sim.memory.__getitem__
                if collect and pc in PLOT_STACK and c['collected %d' % pc] < collect:
                    c['collected %d' % pc] += 1
                    states.append((pc, list(R), bytes(get(a) for a in range(65536)), None))
                c['pace sites'] += 1
                ns_s = NextState(patch.pats)
                ns_s.nr[0x07] = 3 if PACE_SITES[pc][2] == 'end' else 0
                for k in pace_event(patch, pc, get, R, ns_s, alt, _rw()):
                    fail('pace site %d: %s' % (pc, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())
                if pc in PLOT_STACK:
                    c['draws from their entry'] += 1
                    for k in plot_event(patch, pc, get, R, alt, _rw()):
                        fail('draw from its entry %d: %s' % (pc, k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())
                return
            if pc == 0x0038:
                sim = st['sim']
                c['IM 1 interrupts (ROM 0x0038)'] += 1
                for k in isr_event(sim.memory.__getitem__, sim.registers, alt, _rw(), getattr(patch, 'hook_range', patch.altrom)):
                    fail('IM 1 handler: %s' % (k[0] if isinstance(k, tuple) else k), k[1:] if isinstance(k, tuple) else ())
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
    # the same for the pace sites' replayed instructions: 29288 (JR) after 29287 (EXX), 29369 / 29370 after 29368
    if cnt[29287] != cnt[29288] or not cnt[29368] == cnt[29369] == cnt[29370]:
        c['a pace site interior reached other than from its site!'] += 1
    for a in INTERIORS:
        if a not in (29264, 29265, 29288, 29369, 29370) and cnt[a]:
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
    rocket_g = groups(m0)
    for pc, R, mem0 in [(s[0], s[1], s[2]) for s in states if isinstance(s[0], int)]:
        for speed in (0, 1, 2, 3):                  # the caller's speed comes back whatever it was (card patch.restore-speed)
            fl = plot_event(patch, pc, mem0.__getitem__, R, alt, Sim, speed)
            c['speed cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    states = [s for s in states if not isinstance(s[0], int)]
    for kind, R, mem0, attrs in states:
        if kind in done:
            continue
        done.add(kind)
        if kind == 'nw':
            negd = []
            for key in gk:
                for x, y in POS:
                    for ink in INKS:
                        for ix in (OBJ0, OBJ0 + 8 * (NOBJ - 1)) + ((OBJ_ROCKET,) if key[1] in rocket_g else ()):
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
            for k_, v_ in rocket_cases(patch, R, mem0, m0, alt, Sim).items():
                c[k_] += v_
            fuel = [k for k in gk if k[0] == 'c' and k[2] == 3]
            c['PART=3 fuel graphics in the table'] += len(fuel)
            if len(fuel) != 16:
                c['PART=3 fuel graphics missing FAIL!'] += 1
        elif kind == 'er':
            for ix in (OBJ0, OBJ0 + 8 * (NOBJ - 1)):
                r = list(R)
                r[8], r[9] = ix >> 8, ix & 255
                at = [list(a) for a in attrs]
                for i in range(128):
                    at[i][3] |= 0x80
                fl, _ = one(patch, kind, r, bytearray(mem0), at)
                c['erase cases %s' % ('ok' if not fl else 'FAIL!')] += 1
            # the rocket: an erase is the flames; its sections stay
            r = list(R)
            r[8], r[9] = OBJ_ROCKET >> 8, OBJ_ROCKET & 255
            at = [list(a) for a in attrs]
            for i in range(128):
                at[i][3] |= 0x80
            ns = NextState(patch.pats)
            ns.attr = [list(a) for a in at]
            fl = event(patch, kind, bytearray(mem0).__getitem__, r, ns, alt, Sim)[0]
            kept = all(ns.attr[i][3] & 0x80 for b in (36, 102, 108) for i in range(b, b + SPO))
            gone = not any(ns.attr[i][3] & 0x80 for i in range(114, 120))
            c['rocket erase: flames hidden, sections kept %s' % ('ok' if not fl and kept and gone else 'FAIL!')] += 1
        elif kind == 'cls':
            at = [list(a) for a in attrs]
            for i in range(NSPR):           # sprites the hooks use; 120-127 stay hidden from setup
                at[i][3] |= 0x80
            fl, _ = one(patch, kind, list(R), bytearray(mem0), at)
            c['screen clear cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    return c


def rocket_cases(patch, R, mem0, m0, alt, Sim):
    """The rocket as the game draws it: routine 26419 (sections, fuel paint) and 26311 / 26347 (flight, flames),
    original on a zero screen and patched from the same state. Pixels equal the screen (rising: the graphics); a
    settled rocket's colour per pixel equals the attribute the game painted. Parts x fuel x rocket x flash, then take-off and landing."""
    c = collections.Counter()
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    def case(name, part, pods, level, tick, y, entry, itype, colours=True, rising=False):
        mem = bytearray(mem0)
        for a, v in ((OBJ_ROCKET, itype), (OBJ_ROCKET + 1, 168), (OBJ_ROCKET + 2, y), (OBJ_ROCKET + 3, 71),
                     (PART, part), (FUELS, pods), (LEVEL, level), (TICK, tick)):
            mem[a] = v
        for a in range(OBJ_ROCKET + 8, OBJ0 + 8 * NOBJ):
            mem[a] = 0
        sp = 23782
        mem[sp - 2], mem[sp - 1] = 0, 0x40      # returns to 0x4000
        r = list(R)
        r[12], r[24] = sp - 2, entry
        r[8], r[9] = OBJ_ROCKET >> 8, OBJ_ROCKET & 255
        stop = lambda q: q[24] == 0x4000 and q[12] == sp
        O, P = _overlays(mem.__getitem__, alt, psite, (0x4000, 0x5B00))
        o = O()
        so = _machine(Sim, o, list(r), NextState(b''), 'c')
        ns = NextState(patch.pats)
        ns.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        Pp = _overlays(mem.__getitem__, alt, psite, (0x4000, 0x5B00))[1]
        p = Pp()
        sp_ = _machine(Sim, p, list(r), ns, 'p')
        if not (_run(so, stop) and _run(sp_, stop)):
            c['%s: did not return FAIL!' % name] += 1
            return
        screen = _screen_set({a: v for a, v in o.ov.items() if 0x4000 <= a < 0x5800})
        if rising:          # the plotter leaves each section's lowest line to the frame before: on a zero
            screen = set()  # screen that line is absent, so the figure comes from the graphics
            yy = y - 1
            pieces = [(w16(m0, ITEM_TAB + 2 * ((level >> 2 & 3) + 4 * j)), yy - 16 * j) for j in range(part)]
            pieces.append((FLAME[0] if tick & 4 else FLAME[1], yy + 21))
            for a, bottom in pieces:
                for x, r in image(m0, a)[2]:
                    screen.add((168 + x, bottom - r))
        got = ns.all_pixels()
        fails = []
        if set(got) != screen:
            fails.append('pixels')
        if colours:
            for (x, y_), v in got.items():
                a = o[0x5800 + (y_ >> 3) * 32 + (x >> 3)]
                if v != (a & 7) | ((a >> 3) & 8):
                    fails.append('colour')
                    break
        else:
            fl = ns.group_pixels(GROUP_BASE[3])
            if any(v != 10 for v in fl.values()):
                fails.append('flame colour')
            want = 15 if tick & 16 else 11
            if pods >= 6 and any(v != want for s in (36, 102, 108) for v in ns.group_pixels(s).values()):
                fails.append('rocket flash')
        k = '%s %s' % (name, 'ok' if not fails else 'FAIL!')
        c[k] += 1
        if fails and c['  rocket fail example'] < 4:
            c['  rocket fail example'] += 1
            c['  %s part %d pods %d level %d tick %d: %s' % (name, part, pods, level, tick, fails)] += 1

    for level in (0, 4, 8, 12):         # rocket r = level >> 2
        for part in (1, 2, 3):
            for pods in (range(0, 7) if part == 3 else (0,)):
                for tick in (0, 16):
                    case('stacked rocket', part, pods, level, tick, 183, 26419, 9)
        for tick in (0, 4, 16, 20):
            case('take-off with flames', 3, 6, level, tick, 120, 26311, 10, False, True)
            case('landing with flames', 3, 0, level + 1, tick, 100, 26347, 11, False)
    return c


def pace_negatives(patch):
    """Broken copies of the pace hooks, each of which the replay must catch: {name: patch}. The bytes are the assembler's,
    found by the instruction: nextreg 7,3 (ED 91 07 03) in the entries, nextreg 7,a (ED 92 07) in the ends."""
    import copy
    out = {}
    syms = patch.syms

    def variant(name, fn):
        q = copy.copy(patch)
        b = bytearray(patch.ram_code)
        fn(b)
        q.sites = [(a, o, bytes(b) if a == RAM_ORG else n) for a, o, n in patch.sites]
        out[name] = q

    def nop(pat, start, count=1):
        def f(b):
            i = start - RAM_ORG
            for _ in range(count):
                i = b.index(pat, i)
                b[i:i + len(pat)] = bytes(len(pat))
        return f
    variant('window never opened', nop(bytes.fromhex('ed910703'), syms['e_p3c']))
    variant('window never closed', nop(bytes.fromhex('ed9207'), syms['e_x1']))

    def r_off(b):       # the delta in e_nw's R_SET, one off: push af / ld a,n / call hlib_r_set
        i = b.index(bytes.fromhex('f53e'), syms['e_nw'] - RAM_ORG)
        b[i + 2] = (b[i + 2] + 1) & 0x7F
    variant('R off by one after a draw', r_off)

    def r_off2(b):      # the same in an entry
        i = b.index(bytes.fromhex('f53e'), syms['e_p3c'] - RAM_ORG)
        b[i + 2] = (b[i + 2] + 1) & 0x7F
    variant('R off by one after an entry', r_off2)
    return out


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


def rom3_left_patch(patch=None):
    """The build before 2026-11-04 (published 11fdc5ab): only the hook bytes 0x386E.. written over NextZXOS's ROM3."""
    import copy
    q = copy.copy(patch or JetpacPatch())
    q.altrom = q.hook_range
    q.altrom_low = None
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


LOAD_BANK = 13                          # the loading screen's entry bank (pages 26, 27)
LOAD_SCREEN = 'jetpac_loading.scr'      # the tape's 6,912-byte screen (JETPAC.scr), beside the snapshot
ENH_COLOURS = 'jetpac_enhanced_colours.json'   # Spectrum Magic's jetpac_.zip Spec256 colours: local only


def _beside(z80, f):
    p = os.path.join(os.path.dirname(os.path.abspath(z80)), f)
    return p if os.path.isfile(p) else None


def loading_nex(nex, scr):
    """A built .nex -> the same with the loading screen (nexclash-patch build/all2/add_screen.py, bank 13, as
    the published patch): bank 5's screen area in the file = the screen, new bank 13 = the entry bank whose
    stub (asm ldscr) shows it for 250 frames or a key, puts bank 5's bytes back and falls into 0xC000 of
    bank 10. -> (bytes, problems): its proof_of_change, every byte outside these checked."""
    import struct
    hk = load_profile()['hooks']
    head, tail = bytes.fromhex(hk['ldhead']), bytes.fromhex(hk['ldtail'])
    orig = nex[512:512 + 6912]
    bank = head + bytes(0x200 - len(head)) + orig + bytes(0x3FD0 - 0x200 - 6912) + tail
    bad = []
    if struct.unpack_from('<HH', nex, 12) != (0xDFFE, 0xC000) or nex[10] or not nex[18 + 5] or nex[139] != 10 or \
            nex[140] or nex[141] or any(nex[18 + k] for k in range(LOAD_BANK, 112)):
        bad.append('start state, screen block, entry bank or bank %d+ not as the stub assumes' % LOAD_BANK)
    h = bytearray(nex[:512])
    h[9] += 1
    h[18 + LOAD_BANK] = 1
    h[139] = LOAD_BANK
    n = bytes(h) + scr + nex[512 + 6912:] + bank
    if [i for i in range(512) if nex[i] != n[i]] != [9, 18 + LOAD_BANK, 139]:
        bad.append('header bytes')
    if n[512 + 6912:len(nex)] != nex[512 + 6912:] or n[len(nex) + 0x200:len(nex) + 0x200 + 6912] != orig:
        bad.append("rest of the file or the stub's copy of bank 5")
    return n, bad


def auto(a, z80, name, out, say):
    import hashlib
    from skoolkit.snapshot import get_snapshot
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : jetpac_v11 (opt-in rework of jetpac, Jet Pac .nxc v1.1: plotter 30522 -> sprites, every figure; '
        'whole alt ROM image; Enhanced; loading screen)')
    from . import nextboot
    if not _rom3_path() and _beside(z80, 'enNextZX.rom'):     # selftest stages the card's ROM as an input
        nextboot.NEXT_ROM = _beside(z80, 'enNextZX.rom')
    say('ROM model : %s' % nextboot.rom_model())
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
    ec = _beside(z80, ENH_COLOURS)
    enh = os.path.join(out, name + '_enhanced.nex')
    if ec is None:
        say('Enhanced  : no %s beside the snapshot: no Enhanced build' % ENH_COLOURS)
    else:
        from . import coloursheet as cs
        e, info = recolour(open(spr, 'rb').read(), cs.load(ec))
        open(enh, 'wb').write(e)
        say('Enhanced  : %s  %s  map %s, %d entries, banks changed %s' % (
            os.path.basename(enh), md5(enh), md5(ec)[:8], info.get('map entries', 0), info.get('banks changed')))
    sc = _beside(z80, LOAD_SCREEN)
    if sc is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    else:
        scr = open(sc, 'rb').read()
        say('Loading   : screen md5 %s' % md5(sc))
        for f in [spr] + ([enh] if ec else []):
            n, lb = loading_nex(open(f, 'rb').read(), scr)
            open(f, 'wb').write(n)
            ok = ok and not lb and len(scr) == 6912
            say('            %s  %s  bank %d stub, %s' % (os.path.basename(f), md5(f), LOAD_BANK,
                                                         'the rest as built' if not lb else 'PROBLEM %s' % lb))
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
        say('Verify    : %s  %d frames, draws %d, erases %d, colour paints %d, clears %d, %d sprite pixels, '
            'IM 1 handler compared at %d interrupts -> %s' % (
                os.path.basename(r) if r else 'free run (no recording)', c['frames'], c['nw'], c['er'],
                c['at'], c['cls'], c['sprite pixels compared'], c['IM 1 interrupts (ROM 0x0038)'],
                       'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, negative_patch(patch), list(get_snapshot(z80)))
        uf = {k: v for k, v in u.items() if k.endswith('!') and v}
        ok = ok and not uf
        say('Unit      : graphics %d (every graphic, all levels, carried parts x positions x colours), '
            'speed cases %d, erase %d, clears %d, guard %d, negative control %d/%d -> %s' % (
                u['graphic cases ok'], u['speed cases ok'], u['erase cases ok'], u['screen clear cases ok'],
                u['IX outside the object table (guard: no sprite) ok'], u['negative control detected'],
                u['negative control detected'] + u['negative control NOT DETECTED!'],
                'PASS' if not uf else 'FAIL %s' % uf))
        q = rom3_left_patch(patch)              # the previous build (hooks only over NextZXOS's ROM3): must fail
        c, ex, _ = verify(q, z80, None, frames=getattr(a, 'quick', None) or FREE_FRAMES, keys=free_keys(),
                          stop=getattr(a, 'quick', None))
        fl = {k: v for k, v in c.items() if k.endswith('!') and v}
        ok = ok and bool(fl)
        say('Negative  : rom3_left (hooks only over the system ROM3) %s' % ('DETECTED %s' % str(fl)[:160] if fl else
                                                                           'NOT DETECTED!'))
        for nm, q in pace_negatives(patch).items():    # each caught on the first 1,000 frames
            c, ex, _ = verify(q, z80, None, frames=1000, keys=free_keys(), stop=1000)
            fl = {k: v for k, v in c.items() if k.endswith('!') and v}
            ok = ok and bool(fl)
            say('Negative  : %s %s' % (nm, 'DETECTED %s' % str(fl)[:160] if fl else 'NOT DETECTED!'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Recolour (docs/COLOURS.md RECOLOUR): a painted sheet -> per-pixel nibbles in the patterns (bank 11)
# and fixed palette slots in every palette offset, programmed at setup (bank 10). The hooks do not
# change: a pixel left unpainted stays nibble 1 or 15 (the object's run-time ink); nibbles 2-14 hold up to
# 13 fixed colours, the same in all 16 offsets, whatever ink the object has. One pattern = one shape,
# so a mirrored or re-shifted drawing of a figure takes the colours of the figure on the sheet.
# ---------------------------------------------------------------------------------------------
COLOURS = os.path.join(_ROOT, 'docs', 'profiles', 'jetpac_v11_colours.json')   # none: the default set
RECOLOUR = {'game': 'jetpac_v11', 'output': 'sprites', 'colours': 'docs/profiles/jetpac_v11_colours.json', 'clear': True,
            'note': 'Jetpac painted colours: key = sheet figure : line from the top : byte column, both trimmed'}
_SHEET_ITEMS = {'fuel': 12, 'item_a': 16, 'item_b': 17, 'item_c': 18, 'item_d': 19, 'item_e': 20}
_SHOW = b'\xED\x91\x15\x01'                 # nextreg 0x15,1 (setup: sprites on)


def load_colours():
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(build_colours_path(COLOURS))


def _sheet_image(m0, fid):
    """A sheet figure's id (tools/prototypes/jetpac_sheets.py) -> its image, or None."""
    if fid.startswith('jetman_'):
        kind, d, s = fid.split('_')[1:]
        a = w16(m0, JET_TAB + 2 * (('walk', 'fly').index(kind) * 8 + int(d) * 4 + int(s)))
    elif fid.startswith('rocket'):
        rk, j = fid[6:].split('_')
        a = w16(m0, ITEM_TAB + 2 * (int(rk) + 4 * int(j)))
    elif fid in _SHEET_ITEMS:
        a = w16(m0, ITEM_TAB + 2 * _SHEET_ITEMS[fid])
    elif fid.startswith('expl_'):
        a = int(fid[5:]) - 1
    elif fid.startswith('flame_'):
        a = int(fid[6:])
    elif fid.startswith('alien'):
        L, a = (int(x) for x in fid[5:].split('_'))
        return image(alien_mem(m0, L), a)
    else:
        return None
    return image(m0, a)


def _sheet_shape(t):
    """A pattern's pixels {(x, r from the bottom)} -> the sheet's: trimmed, r from the top."""
    top = max(r for _, r in t)
    return frozenset((x, top - r) for x, r in t)


def _map_by_shape(m0, cmap):
    """Colour map -> ({sheet shape: {(c, r): colour | 'T'}}, map keys of no figure)."""
    out, unknown = {}, []
    for key, e in cmap.items():
        fid, r, col = key.rsplit(':', 2)
        img = _sheet_image(m0, fid)
        if img is None or not img[2]:
            unknown.append(key)
            continue
        x0 = min(x for x, _ in img[2])
        d = out.setdefault(_sheet_shape(frozenset((x - x0, r_) for x, r_ in img[2])), {})
        for b in range(8):
            c = (int(col) * 8 + b, int(r))
            if len(e) > 3 and e[3] & (0x80 >> b):
                d[c] = 'T'
            elif e[2][b]:
                d[c] = e[2][b]
    return out, unknown


def painted_patterns(m0, cmap):
    """-> (patterns, [colours of nibbles 2..], info). Same order and count as build(): the lookup tables
    in the alt ROM still hold. A shape not on the sheet takes its mirror's paint."""
    by, unknown = _map_by_shape(m0, cmap)
    used = sorted({v for d in by.values() for v in d.values() if v != 'T'})
    if len(used) > 13:
        raise ValueError('%d fixed colours painted: 13 fit (nibbles 1 and 15 are the game\'s ink)' % len(used))
    slot = {v: 2 + n for n, v in enumerate(used)}
    pats = bytearray()
    first = {}
    kind = collections.Counter()
    band = band_shapes(m0)
    for k, img in graphics(m0).items():
        lo = layout(img) if img is not None else None
        if lo is None:
            continue
        t, x0, cols, rows = lo
        if (t, rows) in first:
            continue
        first[(t, rows)] = len(pats) // 128
        s = _sheet_shape(t)
        top = max(r for _, r in t)
        w = max(x for x, _ in s)
        if s in by:
            d, mir = by[s], False
        else:
            ms = frozenset((w - x, r) for x, r in s)
            d, mir = by.get(ms, {}), True
        kind['painted' if d and not mir else 'painted from its mirror' if d else 'unpainted'] += 1

        def nib(x, r):
            if (x, r) not in t:
                return 0
            v = d.get((w - x if mir else x, top - r))
            return (15 if isband and r >= 8 else 1) if v is None else 0 if v == 'T' else slot[v]
        isband = (t, rows) in band
        for rr in range(rows):
            for cc in range(cols):
                for j in range(16):
                    r = 16 * rows - 1 - (16 * rr + j)
                    for x in range(16 * cc, 16 * cc + 16, 2):
                        pats.append(nib(x, r) << 4 | nib(x + 1, r))
    return bytes(pats), used, {'shapes': dict(kind), 'map keys of no figure': len(unknown)}


def painted_setup(setup, used):
    """The setup routine + a loop writing the fixed colours to nibbles 2.. of all 16 palette offsets."""
    if setup.count(_SHOW) != 1:
        raise ValueError('set-up code differs from this version\'s')
    at = 0xD000 + len(setup)
    loop = b'\xED\x92\x40\x57\x7E\xED\x92\x41\x23\x7A\x3C'     # nextreg 40,a / ld d,a / ld a,(hl) / nextreg 41,a / inc hl / ld a,d / inc a
    row = b'\x06\x0D\x79\xC6\x02' + loop + bytes([0x10, (-(len(loop) + 2)) & 255])   # ld b,14 / ld a,c / add a,2 / djnz
    n = 3 + len(row) + 4 + 2 + 4 + 1
    tab = at + 2 + n
    row = b'\x21' + tab.to_bytes(2, 'little') + row + b'\x79\xC6\x10\x4F'            # ld hl,slots ... ld a,c / add a,16 / ld c,a
    code = b'\x0E\x00' + row + bytes([0x20, (-(len(row) + 2)) & 255]) + _SHOW + b'\xC9'  # ld c,0 / jr nz,row / sprites on / ret
    slots = bytes(SPECCY[v] for v in used).ljust(13, b'\0')
    return setup.replace(_SHOW, b'\xCD' + at.to_bytes(2, 'little') + b'\0') + code + slots


def recolour(nex, cmap):
    """Built jetpac_sprites.nex bytes + colour map -> (new .nex bytes, info). Rewrites banks 10 (setup) and 11
    (patterns), which the game never reads; refuses a .nex that is not this engine's build."""
    from .recolour import banks, splice
    b = banks(nex)
    need = {0, 2, 5, 10, 11, 12}
    if not need <= set(b):
        raise ValueError('not a Jetpac sprite build: banks %s missing' % sorted(need - set(b)))
    ram = bytearray(b[5] + b[2] + b[0])
    patch = JetpacPatch()
    for a, old, new in patch.sites:
        if bytes(ram[a - 0x4000:a - 0x4000 + len(new)]) != new:
            raise ValueError('%d does not hold this build\'s patch byte' % a)
        ram[a - 0x4000:a - 0x4000 + len(old)] = old
    m0 = [0] * 0x4000 + list(ram)
    pats, ent = build(m0)
    if tables_text(pats, ent) != open(os.path.join(_ROOT, 'asm', 'jetpac_v11_tables.asm')).read():
        raise ValueError('game graphics differ from the expected snapshot')
    if b[12][:8192] != patch.page:
        raise ValueError('hook page differs from this version\'s')
    setup = patch.stub_extra
    s10 = b[10][0x1000:]
    plain = s10[:len(setup)] == setup
    if not plain and painted_setup(setup, [])[:len(setup)] != s10[:len(setup)]:
        raise ValueError('set-up code differs from this version\'s')
    used = []
    if cmap:
        pats, used, info = painted_patterns(m0, cmap)
    else:
        info = {}
    code = painted_setup(setup, used) if cmap else setup
    longest = len(painted_setup(setup, []))
    if any(s10[longest:longest + 16]):
        raise ValueError('no room after the set-up code')
    new10 = b[10][:0x1000] + code.ljust(longest, b'\0') + b[10][0x1000 + longest:]
    out, changed = splice(nex, {10: new10, 11: pats + bytes(16384 - len(pats))})
    return out, dict(info, **{'banks changed': changed, 'fixed colours': used, 'map entries': len(cmap)})
