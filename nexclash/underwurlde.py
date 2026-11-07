"""Underwurlde (Ultimate Play The Game, 1984, 48K) engine 'underwurlde'. Additive module: reachable only
through is_underwurlde(). Facts and design: games/underwurlde.md.

Every figure, furniture and icon goes through one XOR plotter: 38647 erase + draw (per object record IX, the old
image in 36577 / 36580 / 36581), 38442 draw, 38454 erase, each ends in the row plotters 38747 / 38881; 39015 paints
the cells with IX+5. Nothing but the plotter reads the screen. Build: the rows stop writing (LD (HL),A -> LD A,(HL),
same T); moving figures become sprites at the three entries, with patterns stored per id at build time; their
painter stops painting; anything else plotted is XORed to the ULA by the hook.
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x2000
ALT_PAGE = 24                   # alt ROM copy source (bank 12)
STPG = 26                       # first pattern store page (bank 13 upper half on)
TAIL_ADDR = 0x5B00
HOOK_RAM = (0x5B80, 0x5C00)
GFXTAB = 37682
OID, OX, OY = 36577, 36580, 36581
NIDS = 150
NSLOT = 24
GP7 = 1
# static things, plotted once and repainted: stay on the ULA. 44-47 + 84 mushrooms, plants, mounds (handler 44863),
# 60, 61, 85-87 stalactites (58914, per-cell colours), 116-126 furniture, 127 the lives figure, 140-149 the menu's.
NONFIG = {44, 45, 46, 47, 84, 60, 61, 85, 86, 87} | set(range(116, 128)) | set(range(137, 150))
ROWS = [(38754, 38860), (38888, 38994)]
SITES = [(38647, 'cd8996', 'cd', 'e_move'), (38442, 'cd8996', 'cd', 'e_draw'), (38454, 'cd5796', 'cd', 'e_erase'),
         (39015, 'dd6e01', 'c3', 'e_attr'), (39175, 'cdab99', 'cd', 'e_room'), (38269, 'cdc299', 'cd', 'e_cls')]
FACTS = [(38696, '79a72810'), (39055, '72'), (38251, '73')]
# one past the routine's setup CALL, for an event's end; 39015 ends at its RET; 39175, 38269 at the routine entered
ENDS = {38647: 38650, 38442: 38445, 38454: 38457, 39175: 39339, 38269: 39362}
CMP = list(range(0, 13)) + list(range(14, 25)) + [26, 27]   # all but T, MEMPTR
INK = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
# what a colour map's nibble means: sheet slot 1 = pattern index 15 (index 1 is the run-time ink)
SHEET = [0, 0xFF, 0x00, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
RECORD = 'underwurlde'
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')


# The archive snapshot's loader moves the game down one byte: DI, LDIR 0x6801 -> 0x6800, 0x8800 bytes, JP 30336. A build
# starts at its USR 26610 (a .nxc must stay close to the archive file), so its sites and hook bytes lie one byte up.
LDIR_LO, LDIR_HI = 0x6800, 0x6800 + 0x8800


def before_ldir(peek):
    """True for memory the game's first LDIR has not moved yet (39055 is LD (HL),D / INC L in the moved code)."""
    return peek(39055) != 0x72 and (peek(39056), peek(39057)) == (0x72, 0x2C)


def game_view(peek):
    """peek(a) for addresses as the running game has them."""
    if before_ldir(peek):
        return lambda a: peek(a + 1) if LDIR_LO <= a < LDIR_HI else peek(a)
    return peek


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'underwurlde.json')


def load_profile():
    with open(_profile_path()) as f:
        return json.load(f)


def is_underwurlde(snap):
    if len(snap.ram(-1)) != 49152:
        return False
    s = load_profile()['signature']
    want = bytes.fromhex(s['bytes'])
    ram = bytes(snap.ram(-1))
    return any(ram[s['addr'] + d - 16384:s['addr'] + d - 16384 + len(want)] == want for d in (0, 1))


def row_sites(peek):
    out = []
    for lo, hi in ROWS:
        for a in range(lo, hi + 1):
            if peek(a) == 0xAE and peek(a + 1) == 0x77:
                out.append(a + 1)
    return out


def graphic(peek, i):
    p = peek(GFXTAB + 2 * i) + 256 * peek(GFXTAB + 2 * i + 1)
    return p, peek(p), peek(p + 1)


def figure_ids(peek):
    out = []
    for i in range(1, NIDS):
        p, w, h = graphic(peek, i)
        if i not in NONFIG and 1 <= w <= 3 and 1 <= h <= 46:
            out.append(i)
    return out


def image(peek, i, cmap=None):
    """-> (canvas W x H of pattern indices, W, H): ink at (1, 1), bottom row first in the data; 0 clear, 1 ink,
    2 black (outline, enclosed paper); a colour map's nibble overrides by pixel."""
    p, w, h = graphic(peek, i)
    W, H = w * 8 + 2, h + 2
    g = [[0] * W for _ in range(H)]
    for r in range(h):
        for b in range(w):
            v = peek(p + 2 + r * w + b)
            for k in range(8):
                if v & (0x80 >> k):
                    g[h - r][1 + b * 8 + k] = 1
    out = set()
    st = [(x, y) for x in range(W) for y in (0, H - 1)] + [(x, y) for y in range(H) for x in (0, W - 1)]
    while st:
        x, y = st.pop()
        if (x, y) in out or not (0 <= x < W and 0 <= y < H) or g[y][x]:
            continue
        out.add((x, y))
        st += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    res = [row[:] for row in g]
    for y in range(H):
        for x in range(W):
            if g[y][x]:
                continue
            if (x, y) not in out:
                res[y][x] = 2
            elif any(0 <= x + dx < W and 0 <= y + dy < H and g[y + dy][x + dx] for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                res[y][x] = 2
    if cmap:
        for r in range(h):
            for b in range(w):
                a = p + 2 + r * w + b
                e = cmap.get(str(a))
                if not e or e[0] != peek(a):
                    continue
                mask = e[3] if len(e) > 3 else 0
                for k in range(8):
                    n = e[2][k]
                    if mask & (0x80 >> k):
                        res[h - r][1 + b * 8 + k] = 0
                    elif n:
                        res[h - r][1 + b * 8 + k] = 15 if n == 1 else n
    return res, W, H


def tiles(g, W, H):
    """Canvas -> pattern bytes: rows x 2 x 128, as the hook uploads them."""
    rows = (H + 15) // 16
    out = bytearray()
    for r in range(rows):
        for c in range(2):
            for y in range(16):
                for x in range(0, 16, 2):
                    yy, xx = r * 16 + y, c * 16 + x
                    a = g[yy][xx] if yy < H and xx < W else 0
                    b = g[yy][xx + 1] if yy < H and xx + 1 < W else 0
                    out.append(a << 4 | b)
    return bytes(out), rows


def build_store(peek, cmap=None):
    """-> directory bytes, {page: 8K}."""
    d = bytearray(NIDS * 4)
    store = {}
    pg, off = STPG, 0
    for i in figure_ids(peek):
        g, W, H = image(peek, i, cmap)
        t, rows = tiles(g, W, H)
        if off + rows > 32:
            pg, off = pg + 1, 0
        if pg not in store:
            store[pg] = bytearray(8192)
        store[pg][off * 256:off * 256 + len(t)] = t
        d[i * 4:i * 4 + 4] = bytes((pg, off, rows, graphic(peek, i)[2]))
        off += rows
    return bytes(d), {k: bytes(v) for k, v in store.items()}


class UnderwurldePatch:
    name = 'Underwurlde figures -> hardware sprites (altrom 0x2000-, patterns per id, XOR rows off)'

    def __init__(self, prof=None, edit=None, skip_sites=()):
        """edit: {ROM address: bytes} over the hook code; skip_sites: sites left original (negative controls)."""
        from .build import rom48
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.edit, self.skip = edit or {}, set(skip_sites)
        self.base_code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = HOOK_RAM[0] - TAIL_ADDR
        self.regblock = ROM_ORG + len(self.base_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hook code too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)
        low = bytearray(rom48()[:0x2000])
        for a, old, sym in [(0x0038, b'\xF5\xE5\x2A', 'irq_in'),
                            (0x004F, b'\xE1\xF1\xFB', 'irq_out')]:
            if bytes(low[a:a + 3]) != old:
                raise ValueError('unexpected 48K ROM interrupt entry')
            low[a:a + 3] = b'\xC3' + self.syms[sym].to_bytes(2, 'little')
        self.altrom_low = (ALT_PAGE + 1, bytes(low))
        self.sites, self.extra_banks, self.page, self.store = [], {}, b'', {}
        self.dirb = bytes(NIDS * 4)
        self.colours = None

    def prepare(self, peek, colours='build'):
        from .build import rom48
        for a, old, op, sym in SITES:
            cur = bytes(peek(a + k) for k in range(3))
            if cur != bytes.fromhex(old):
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected version of the game, or '
                                 'already patched' % (a, cur.hex(), old))
        for a, hx in FACTS:
            want = bytes.fromhex(hx)
            if bytes(peek(a + k) for k in range(len(want))) != want:
                raise ValueError('unexpected code at %d' % a)
        rows = row_sites(peek)
        if len(rows) != 36:
            raise ValueError('expected 36 row writes, found %d' % len(rows))
        self.rows = rows
        self.sites = []
        for a, old, op, sym in SITES:
            if a not in self.skip:
                self.sites.append((a, bytes.fromhex(old), bytes.fromhex(op) + self.syms[sym].to_bytes(2, 'little')))
        for a in rows:
            if a not in self.skip:
                self.sites.append((a, b'\x77', b'\x7E'))
        self.colours = load_colours() if colours == 'build' else colours
        self.dirb, self.store = build_store(peek, self.colours)
        code = bytearray(self.base_code)
        code[self.syms['DIR'] - ROM_ORG:self.syms['DIR'] - ROM_ORG + len(self.dirb)] = self.dirb
        for a, d in self.edit.items():
            code[a - ROM_ORG:a - ROM_ORG + len(d)] = d
        self.rom_code = bytes(code)
        page = bytearray(rom48()[0x2000:0x4000])
        page[0:len(code)] = code
        self.page = bytes(page)
        banks = {ALT_PAGE // 2: bytearray(self.page + self.altrom_low[1])}
        for pg, data in self.store.items():
            b = banks.setdefault(pg // 2, bytearray(16384))
            k = (pg & 1) * 8192
            b[k:k + 8192] = data
        self.extra_banks = {k: bytes(v) for k, v in banks.items()}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('this patch is for the 48K version')
        from .build import rom48
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        mem = bytes(rom48()) + bytes(ram)
        up = 1 if before_ldir(mem.__getitem__) else 0
        self.prepare(game_view(mem.__getitem__))
        for a, old, new in self.sites:
            ram[a + up - 0x4000:a + up - 0x4000 + len(new)] = new
        ram[HOOK_RAM[0] - 0x4000:HOOK_RAM[1] - 0x4000] = bytes(HOOK_RAM[1] - HOOK_RAM[0])
        ram[TAIL_ADDR - 0x4000:HOOK_RAM[0] - 0x4000] = bytes(HOOK_RAM[0] - TAIL_ADDR)
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[0:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])


def load_colours():
    from . import recolour as rc
    p = rc.build_colours_path(COLOURS)
    if p and os.path.exists(p):
        from . import coloursheet as cs
        return cs.load(p)
    return None


# ------------------------------------------------------------------------------------------------------------
# Next state and the pair runner
# ------------------------------------------------------------------------------------------------------------
class NextState:
    def __init__(self):
        self.nr = {7: 0, 0x57: GP7}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pp = 0
        self.t28 = 0
        self.selected = 0

    def nextreg(self, reg, val):
        if reg == 7 and getattr(self, 'sim', None) is not None:
            self._time()
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def _time(self):
        t = self.sim.registers[25]
        self.real += (t - self.last_t) / (1, 2, 4, 8)[self.nr.get(7, 0) & 3]
        self.last_t = t
        return self.real

    def read(self, port):
        if port == 0x243B:
            return self.selected
        if port == 0x253B:
            if self.selected in (0x1E, 0x1F):
                line = int(self._time() // 224) % 312
                return line >> 8 if self.selected == 0x1E else line & 255
            return self.nr.get(self.selected, 0)
        return 0xFF

    def out(self, port, v, mem):
        if port == 0x243B:
            self.selected = v
        elif port == 0x303B:
            self.pp = ((v & 0x3F) << 8) | (128 if v & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pp] = v
            self.pp = (self.pp + 1) & 0x3FFF

    def visible(self):
        """(sprite, x, y, pattern, palette offset) of each visible sprite."""
        out = []
        for n, a in enumerate(self.attr):
            if a[3] & 0x80:
                pat = ((a[3] & 0x3F) << 1) | ((a[4] >> 6) & 1)
                out.append((n, a[0] + ((a[2] & 1) << 8) - 32, a[1] + ((a[4] & 1) << 8) - 32, pat, a[2] >> 4))
        return out


class Store:
    """The pages a hook maps at slot 7: the patched machine's memory shows them while nr[0x57] says so."""


def _machine(Sim, mem, regs, ns, store, game_e000, slot='p'):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot, copy=True)
    # This pair executes one call without periodic interrupt acceptance. Match
    # the RZX player's model: otherwise SkoolKit makes LD A,I/R report PV=0
    # near a fictitious frame pulse even though no ISR runs. Actual interrupts
    # (including the NMOS PV quirk) are exercised by explicit injection tests.
    sim.int_active = 0
    ns.sim, ns.real, ns.last_t = sim, 0., sim.registers[25]
    m = sim.memory

    def nreg(reg, val):
        if reg == 0x57:
            if val == GP7:
                m[0xE000:0x10000] = sim._game7
            else:
                sim._game7 = bytes(m[0xE000:0x10000])
                m[0xE000:0x10000] = store.get(val, bytes(8192))
        ns.nextreg(reg, val)

    class Tr:
        def read_port(s, r, port):
            return ns.read(port)

        def write_port(s, r, port, value, *x):
            ns.out(port, value, m)
    sim.set_tracer(Tr())
    z80n.install(sim, nreg, strict=True)
    return sim


class Runner:
    def __init__(self, patch, peek0):
        from skoolkit.simulator import Simulator
        from .build import rom48
        self.Sim = Simulator
        self.p = patch
        self.ns = NextState()
        self.P = bytearray(6912)
        self.H = bytearray(HOOK_RAM[1] - HOOK_RAM[0])
        self.rom = bytes(rom48())
        self.ov = [(a, new) for a, old, new in patch.sites]
        self.rest = [(a, old) for a, old, new in patch.sites]
        self.newb = {a: new for a, old, new in patch.sites}
        self.c = collections.Counter()
        self.ex = collections.defaultdict(list)
        self.frame = 0

    def fail(self, k, info=()):
        self.c[k + '!'] += 1
        if len(self.ex[k]) < 5:
            self.ex[k].append((self.frame,) + tuple(info))

    def pmem(self, omem):
        m = bytearray(omem)
        m[:0x2000] = self.p.altrom_low[1]
        m[0x2000:0x4000] = self.p.page
        for a, new in self.ov:
            m[a:a + len(new)] = new
        m[0x4000:0x5B00] = self.P
        m[HOOK_RAM[0]:HOOK_RAM[1]] = self.H
        return m

    def run(self, sim, stop, safe=None, limit=200000):
        R, ops, mem = sim.registers, sim.opcodes, sim.memory
        n = 0
        while not stop(R):
            t0 = R[25]
            if safe:
                safe(R)
            ops[mem[R[24]]]()
            if safe and self.ns.nr.get(7) == 3:
                self.ns.t28 += R[25] - t0
            n += 1
            if n > limit:
                return False
        return True

    def event(self, kind, omem, regs):
        """From one machine state: original and patched code to the same point; compare; keep the patched screen."""
        c = self.c
        c['n%d' % kind] += 1
        incoming_speed = self.ns.nr.get(7, 0)
        if kind in (39015, 38647, 38442, 38454):
            sp0 = regs[12]
            stop = lambda R: R[12] == (sp0 + 2) & 0xFFFF
        else:
            e = ENDS[kind]
            sp0 = regs[12]
            spe = (sp0 - 2) & 0xFFFF if kind in (39175, 38269) else sp0
            stop = lambda R: R[24] == e and R[12] == spe
        from .simpool import machine
        o = machine(self.Sim, bytearray(omem), list(regs), 'o', copy=True)
        o.int_active = 0
        o.set_tracer(type('T', (), {'read_port': lambda s, r, p: 0xFF, 'write_port': lambda s, r, p, v, *x: None})())
        ot0 = o.registers[25]
        if not self.run(o, stop):
            self.fail('original did not finish', (kind,))
            return
        c['T original'] += (o.registers[25] - ot0) / (1, 2, 4, 8)[incoming_speed & 3]
        pm = self.pmem(omem)
        s = _machine(self.Sim, pm, list(regs), self.ns, self.p.store, None)
        s._game7 = bytes(pm[0xE000:0x10000])
        ix, iy, i_, iff = (regs[8], regs[9]), (regs[10], regs[11]), regs[14], regs[26]
        bad = []

        di_start = None
        max_di = 0.
        def safe(R):
            nonlocal di_start, max_di
            if (R[8], R[9]) != ix or (R[10], R[11]) != iy or R[14] != i_:
                bad.append('IX/IY/I')
            now = self.ns._time()
            if iff and not R[26]:
                if di_start is None:
                    di_start = now
                max_di = max(max_di, now - di_start)
            else:
                if di_start is not None:
                    max_di = max(max_di, now - di_start)
                di_start = None
            if 64 < (sp0 - R[12]) & 0xFFFF < 0x8000:
                bad.append('SP %d' % R[12])
        if not self.run(s, stop, safe):
            self.fail('hook did not finish', (kind,))
            return
        safe(s.registers)
        c['max DI (3.5MHz T)'] = max(c['max DI (3.5MHz T)'], max_di)
        if s.registers[26] != iff or max_di >= 32:
            bad.append('IFF / DI window %.3f T' % max_di)
        if bad:
            self.fail('hook safety', (kind, bad[0]))
        c['T patched'] += self.ns._time()
        if self.ns.nr.get(7) != incoming_speed or self.ns.nr.get(0x57) != GP7:
            self.fail('hook left a register', (kind, self.ns.nr.get(7), self.ns.nr.get(0x57)))
        # registers
        R, Q = s.registers, o.registers
        for k in CMP:
            if k == 16 and kind in (38647, 38442, 38454):
                continue  # retired rows' A' is dead: a_prime_test proves it on recordings
            if R[k] != Q[k]:
                self.fail('register', (kind, k, Q[k], R[k], 'IX', ix[0] * 256 + ix[1]))
                break
        # memory: all but the screen, the hook's bytes, the sites and the dead stack below SP
        a = bytearray(s.memory)
        b = bytearray(o.memory)
        np, nh = bytes(a[0x4000:0x5B00]), bytes(a[HOOK_RAM[0]:HOOK_RAM[1]])
        a[0:0x4000] = b[0:0x4000]
        a[0x4000:0x5B00] = b[0x4000:0x5B00]
        a[HOOK_RAM[0]:HOOK_RAM[1]] = b[HOOK_RAM[0]:HOOK_RAM[1]]
        for x, old in self.rest:
            if bytes(a[x:x + len(old)]) != self.newb[x]:
                self.fail('game or hook wrote a site', (x,))
            a[x:x + len(old)] = b[x:x + len(old)]
        sp = Q[12]
        lo = max(sp - 48, 0x4000)
        a[lo:sp] = b[lo:sp]
        if a != b:
            d = [x for x in range(65536) if a[x] != b[x]]
            self.fail('memory', (kind, d[:6], [b[x] for x in d[:6]], [a[x] for x in d[:6]]))
        # a figure's event leaves the ULA alone
        idx = ix[0] * 256 + ix[1]
        fig = self.is_fig(omem, idx, kind)
        if fig and (kind != 38647 or self.is_fig_id(omem[OID], idx)) and np != bytes(self.P):
            self.fail('figure event changed the ULA', (kind, idx))
        self.P[:] = np
        self.H[:] = nh
        if fig and kind == 39015:
            self.clash(omem, idx)
        if fig and kind in (38647, 38442):
            self.c['figure plots'] += 1
            self.c['id%03d' % omem[idx]] += 1
            self.check_colour(omem, idx)
        return s, o

    def is_fig_id(self, i, ix):
        return i < NIDS and self.p.dirb[i * 4 + 2] != 0 and slot_of(ix) is not None

    def is_fig(self, m, ix, kind):
        if kind in (39175, 38269):
            return False
        return self.is_fig_id(m[ix] if kind in (38647, 38442, 39015) else m[OID], ix)

    def clash(self, m, ix):
        """The clash this paint would make in the original: cells under the figure with scenery ink in another colour."""
        x, y, v, w, h = m[ix + 1], m[ix + 3], m[ix + 5], m[36582], m[36583]
        P = self.P
        n = 0
        col0 = x >> 3
        for row in range(max(0, y - h + 1) >> 3, min(y >> 3, 23) + 1):
            for col in range(col0, min(col0 + w, 32)):
                if P[6144 + row * 32 + col] & 0x47 != v & 0x47:
                    base = ((row & 0x18) << 8) | (row & 7) << 5 | col
                    if any(P[base + (k << 8)] for k in range(8)):
                        n += 1
        c = self.c
        c['paints'] += 1
        if n:
            c['paints over other-coloured scenery'] += 1
            c['scenery cells recoloured'] += n

    def check_colour(self, m, ix):
        first, allow = slot_range(ix)
        v = m[ix + 5]
        want = (v & 7) + (8 if v & 64 else 0)
        for n in range(first, first + allow):
            a = self.ns.attr[n]
            if a[3] & 0x80 and a[2] >> 4 != want:
                self.fail('sprite colour', (ix, n, a[2] >> 4, want))
                return

    def composite(self):
        """XOR of the sprites' ink as 192 ints, x 0 = the top bit of 256."""
        rows = [0] * 192
        pat = self.ns.pat
        cache = self.__dict__.setdefault('_tiles', {})
        for n, x, y, p, o in self.ns.visible():
            t = bytes(pat[p * 128:p * 128 + 128])
            m = cache.get(t)
            if m is None:
                m = []
                for r in range(16):
                    w = 0
                    for k in range(16):
                        w = w << 1 | ((t[r * 8 + k // 2] >> (4 if k % 2 == 0 else 0)) & 15 == 1)
                    m.append(w)
                cache[t] = m
            for r in range(16):
                yy = y + r
                if 0 <= yy < 192 and m[r]:
                    sh = 256 - 16 - x
                    rows[yy] ^= ((m[r] << sh) if sh >= 0 else (m[r] >> -sh)) & ((1 << 256) - 1)
        return rows

    def invariant(self, omem):
        """The original's pixels = the patched ULA XOR the sprites' ink."""
        c = self.c
        c['screen checks'] += 1
        rows = self.composite()
        P = self.P
        c['max sprites shown'] = max(c['max sprites shown'], len(self.ns.visible()))
        for y in range(192):
            base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            o = int.from_bytes(omem[0x4000 + base:0x4000 + base + 32], 'big')
            q = int.from_bytes(P[base:base + 32], 'big')
            if o ^ q != rows[y]:
                d = bin(o ^ q ^ rows[y]).count('1')
                c['screen pixels differing'] += d
                c['screen checks with a difference'] += 1
                self.fail('screen', (y, d, hex(o ^ q ^ rows[y])[:40]))
                return


def slot_of(ix):
    if 36602 <= ix < 36906 and (ix - 36602) % 16 == 0:
        return (ix - 36602) // 16
    if 36906 <= ix < 36946 and (ix - 36906) % 8 == 0:
        return 19 + (ix - 36906) // 8
    return None


_BASES = [(20, 2), (22, 2), (120, 6), (114, 6), (24, 6), (30, 6), (36, 6), (42, 6), (48, 6), (54, 6), (60, 6), (66, 6),
          (72, 6), (78, 6), (84, 6), (90, 6), (96, 6), (102, 6), (108, 6), (0, 4), (4, 4), (8, 4), (12, 4), (16, 4)]


def slot_range(ix):
    return _BASES[slot_of(ix)]


def peek_of(z80):
    from skoolkit.snapshot import Snapshot
    from .build import rom48
    mem = bytes(rom48()) + bytes(Snapshot.get(z80).ram(-1))
    return game_view(mem.__getitem__)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, row_sample=500, zap=None):
    """Replay the RZX (original game). At every site run original and patched code from one state and compare; at
    each object's end (37977, once a frame) compare the whole picture; attributes and pixels from other writers go
    into the patched screen as they happen. Returns (Counter, examples, states)."""
    from .simrun import run as srun
    r = None
    states = {}
    hooks_sites = set(ENDS) | {39015}

    class H:
        frame = 0
        checked = -1
        started = False

        def on_sim(h, sim):
            nonlocal r
            h.sim, h.R, h.m = sim, sim.registers, sim.memory
            if r is None:
                raw = _raw(sim.memory)
                peek = game_view(bytes(raw).__getitem__)
                if not patch.sites:
                    patch.prepare(peek)
                r = Runner(patch, peek)
                r.P[:] = raw[0x4000:0x5B00]
                h.pcs = {a for a, old, new in patch.sites}
                h.inter = {a + k for a, old, new in patch.sites for k in range(1, len(new))}
                h.rowpcs = set(patch.rows)
                h.site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
            h.raw = _raw(sim.memory)

        def before(h, pc):
            if pc in hooks_sites:
                if pc in h.pcs:
                    # Capture the incoming hook state, including room/clear,
                    # before the event updates sprite-history RAM.
                    if collect and len(states.setdefault(pc, [])) < collect:
                        states[pc].append((bytes(h.raw), list(h.R), bytes(r.P), bytes(r.H)))
                    res = r.event(pc, h.raw, list(h.R))
            elif pc == 37977:
                if h.frame != h.checked:
                    h.checked = h.frame
                    r.invariant(h.raw)
            elif pc == 38381:           # the game over screen is up: no figures may show
                r.invariant(h.raw)
            elif pc in h.inter:
                r.fail('jump into a patched instruction', (pc,))
            if zap and pc in (38704, 38713):
                h.R[16] = zap(h.frame)

        def on_write(h, a, v, pc, m):
            if a in h.site_bytes:
                r.fail('game wrote a site', (a, pc))
            elif HOOK_RAM[0] <= a < HOOK_RAM[1] or TAIL_ADDR <= a < HOOK_RAM[0]:
                r.fail('game wrote the hook RAM', (a, pc))
            elif pc == 44201 and 0x4000 <= a < 0x5B00:   # the rope's XOR pixel: its change, on the patched screen
                r.P[a - 0x4000] ^= h.raw[a] ^ v
                r.c['rope pixels'] += 1
            elif 0x4000 <= a < 0x5B00 and pc not in h.rowpcs and pc != 39055:
                r.P[a - 0x4000] = v

        def on_read(h, a, pc, m):
            if HOOK_RAM[0] <= a < HOOK_RAM[1] or TAIL_ADDR <= a < HOOK_RAM[0]:
                r.fail('game read the hook RAM', (a, pc))

        def on_frame(h, n):
            h.frame = n
            r.frame = n
            r.c['frames'] = n
            if n % 100 == 0:
                r.c['room %d,%d' % (h.m[36636], h.m[36638])] += 1
            if progress and n % 2000 == 0:
                progress(n)
    srun(None, rzx=[rzx_path], hooks=H(), stop=stop)
    st = [x for v in states.values() for x in v]
    return r.c, r.ex, st


def _raw(m):
    while hasattr(m, 'm'):
        m = m.m
    return m


# ------------------------------------------------------------------------------------------------------------
# Unit tests and negative controls
# ------------------------------------------------------------------------------------------------------------
def negative_patches():
    """name -> {sym offset: bytes} over the hook code, each a build that must be detected."""
    return {'sprite X one pixel off': ('n_x', 1, b'\x20'),
            'sprite Y one line off': ('n_y', 1, b'\x21'),
            'erase does not hide': ('n_hide', 0, b'\x00\x00\x00'),
            'patterns never uploaded': ('n_same', 0, b'\x18'),
            'wrong colour byte': ('n_pal', 2, b'\x04'),
            'painter paints the figure': ('n_paint', 0, b'\x72'),
            'hook loses AF': ('n_pop', 0, b'\xC1'),
            'room change keeps the sprites': ('n_room', 0, b'\x00\x00\x00'),
            'screen clear keeps the sprites': ('n_cls', 0, b'\x00\x00\x00'),
            'furniture not drawn': ('n_xor', 0, b'\xC9'),
            'spare sprites left on': ('n_off', 0, b'\xC9'),
            'hook writes IX': ('n_ix', 0, b'\xDD\x2C\x00'),
            'wrong 8-byte record slot': ('n_w', 1, b'\x12')}


def negative_patch(prof, name):
    sym, off, data = negative_patches()[name]
    syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    return UnderwurldePatch(prof, edit={syms[sym] + off: data})


def _fullrun(r, kind_stop, omem, regs):
    """Whole routine, original and patched, ending at the RET back to a marker: -> (o, s) simulators."""
    from .simpool import machine
    sp0 = regs[12]
    stop = lambda R: R[12] == (sp0 + 2) & 0xFFFF
    o = machine(r.Sim, bytearray(omem), list(regs), 'o', copy=True)
    o.int_active = 0
    o.set_tracer(type('T', (), {'read_port': lambda s, a, p: 0xFF, 'write_port': lambda s, a, p, v, *x: None})())
    ok1 = r.run(o, stop)
    pm = r.pmem(omem)
    s = _machine(r.Sim, pm, list(regs), r.ns, r.p.store, None)
    s._game7 = bytes(pm[0xE000:0x10000])
    ok2 = r.run(s, stop, lambda R: None)
    return (o, s) if ok1 and ok2 else (None, None)


def _cmp(r, o, s, c, name, skip=()):
    for k in CMP:
        if k not in skip and o.registers[k] != s.registers[k]:
            r.fail(name + ': register', (k, o.registers[k], s.registers[k]))
            return False
    a, b = bytearray(s.memory), bytearray(o.memory)
    a[0:0x4000] = b[0:0x4000]
    a[0x4000:0x5B00] = b[0x4000:0x5B00]
    a[HOOK_RAM[0]:HOOK_RAM[1]] = b[HOOK_RAM[0]:HOOK_RAM[1]]
    for x, old in r.rest:
        a[x:x + len(old)] = b[x:x + len(old)]
    sp = o.registers[12]
    a[max(sp - 48, 0x4000):sp] = b[max(sp - 48, 0x4000):sp]
    if a != b:
        d = [x for x in range(65536) if a[x] != b[x]]
        r.fail(name + ': memory', (d[:5],))
        return False
    return True


def _rows_of(mem):
    return [int.from_bytes(mem[0x4000 + (((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)):][:32], 'big') for y in range(192)]


def unit_tests(patch, states, neg=None):
    """Cases a recording may not reach: every graphic at the guard edges, every record's slot, each row width."""
    c = collections.Counter()
    if not states:
        c['no states captured!'] += 1
        return c
    mem0, regs0 = bytearray(states[0][0]), list(states[0][1])
    peek = game_view(bytes(mem0).__getitem__)
    if not patch.sites:
        patch.prepare(peek)
    r = Runner(patch, peek)
    blank = bytes(6144) + bytes([71]) * 768
    MARK = 0x5F00
    ids = figure_ids(peek)
    reg = list(regs0)
    reg[12] = 0x5FF0
    reg[26] = 0

    def state(ix, i, x, y, col=70):
        m = bytearray(mem0)
        m[0x4000:0x5B00] = blank
        m[ix], m[ix + 1], m[ix + 3], m[ix + 5] = i, x, y, col
        m[ix + 15 if ix < 36906 else ix + 7] &= 0xFE
        m[0x5FF0], m[0x5FF1] = MARK & 255, MARK >> 8
        return m

    def call(m, pc, ix):
        rg = list(reg)
        rg[8], rg[9] = ix >> 8, ix & 255
        rg[24] = pc
        return rg

    def fresh():
        r.ns = NextState()
        r.P[:] = blank
        r.H[:] = bytes(len(r.H))

    def after(s):
        r.P[:] = s.memory[0x4000:0x5B00]
        r.H[:] = s.memory[HOOK_RAM[0]:HOOK_RAM[1]]

    # draw: every figure id at the position edges
    pos = [(8, 60), (9, 60), (15, 47), (16, 48), (100, 100), (100, 191), (200, 120), (231, 90), (100, 10)]
    for i in ids:
        for x, y in pos:
            fresh()
            m = state(36634, i, x, y)
            o, s = _fullrun(r, None, m, call(m, 38442, 36634))
            if o is None:
                r.fail('draw did not finish', (i, x, y))
                continue
            if not _cmp(r, o, s, c, 'draw', skip=(16,)):
                continue
            if bytes(s.memory[0x4000:0x5B00]) != blank:
                r.fail('draw changed the ULA', (i, x, y))
            after(s)
            want = _rows_of(o.memory)
            base = _rows_of(bytes(0x4000) + blank + bytes(0xA500))
            comp = r.composite()
            bad = sum(bin(want[k] ^ base[k] ^ comp[k]).count('1') for k in range(192))
            w = graphic(peek, i)[1]
            if bad:
                if x + w * 8 + (1 if x & 7 else 0) > 256:
                    c['margin wrap cases (informative)'] += 1
                else:
                    r.fail('draw pixels', (i, x, y, bad))
            else:
                c['draw cases ok'] += 1
    # every record: its slot and allowance
    for ix in list(range(36602, 36906, 16)) + list(range(36906, 36946, 8)):
        fresh()
        i = max((k for k in ids if graphic(peek, k)[2] <= (46 if slot_range(ix)[1] >= 6 else 30 if slot_range(ix)[1] >= 4 else 14)), key=lambda k: graphic(peek, k)[2])
        m = state(ix, i, 100, 120)
        o, s = _fullrun(r, None, m, call(m, 38442, ix))
        if o is None or not _cmp(r, o, s, c, 'slot', skip=(16,)):
            continue
        after(s)
        first, allow = slot_range(ix)
        vis = [v for v in r.ns.visible()]
        rows = (graphic(peek, i)[2] + 2 + 15) // 16
        if sorted(v[0] for v in vis) != list(range(first, first + min(2 * rows, allow))):
            r.fail('slot sprites', (ix, [v[0] for v in vis], first, allow))
        else:
            c['slot cases ok'] += 1
    # a record the table does not know, and an id with no sprite: to the ULA, exactly as the original
    for ix, i in ((36603, 9), (38360, 140), (41021, 127), (36730, 119), (36730, 116), (36762, 84), (36778, 60), (36794, 44), (36810, 123)):
        for x, y in ((64, 100), (67, 100), (120, 47)):
            fresh()
            m = state(ix, i, x, y)
            o, s = _fullrun(r, None, m, call(m, 38442, ix))
            if o is None or not _cmp(r, o, s, c, 'ula draw', skip=(16,)):
                continue
            if bytes(s.memory[0x4000:0x5800]) != bytes(o.memory[0x4000:0x5800]):
                r.fail('ula draw pixels', (ix, i, x, y))
            elif r.ns.visible():
                r.fail('ula draw has a sprite', (ix, i))
            else:
                c['ula draw cases ok'] += 1
    # move: all four old / new combinations; erase of each
    for ix, a, b in ((36634, 9, 13), (36634, 9, 9), (36826, 64, 68)):
        fresh()
        m = state(ix, a, 100, 100)
        o, s = _fullrun(r, None, m, call(m, 38442, ix))
        after(s)
        m1 = bytearray(o.memory)
        m1[OID], m1[OX], m1[OY] = a, 100, 100
        m1[ix], m1[ix + 1], m1[ix + 3] = b, 103, 96
        m1[0x5FF0], m1[0x5FF1] = MARK & 255, MARK >> 8
        o2, s2 = _fullrun(r, None, m1, call(m1, 38647, ix))
        if o2 is None or not _cmp(r, o2, s2, c, 'move', skip=(16,)):
            continue
        after(s2)
        comp = r.composite()
        want = _rows_of(o2.memory)
        base = _rows_of(bytes(0x4000) + blank + bytes(0xA500))
        if sum(bin(want[k] ^ base[k] ^ comp[k]).count('1') for k in range(192)):
            r.fail('move pixels', (ix, a, b))
        else:
            c['move cases ok'] += 1
        m3 = bytearray(o2.memory)
        m3[OID], m3[OX], m3[OY] = b, 103, 96
        m3[0x5FF0], m3[0x5FF1] = MARK & 255, MARK >> 8
        o3, s3 = _fullrun(r, None, m3, call(m3, 38454, ix))
        if o3 is None or not _cmp(r, o3, s3, c, 'erase', skip=(16,)):
            continue
        after(s3)
        if r.ns.visible():
            r.fail('erase left sprites', (ix,))
        elif bytes(o3.memory[0x4000:0x5800]) != blank[:6144]:
            r.fail('original erase did not clear', (ix,))
        else:
            c['erase cases ok'] += 1
    # a room change and a screen clear with a figure shown: its sprites go
    for pc in (39175, 38269):
        fresh()
        m = state(36634, 9, 100, 100)
        o, s = _fullrun(r, None, m, call(m, 38442, 36634))
        after(s)
        if not r.ns.visible():
            r.fail('hide: nothing shown first', (pc,))
        m1 = bytearray(o.memory)
        rg = call(m1, pc, 36634)
        r.event(pc, m1, rg)
        if r.ns.visible():
            r.fail('hide left sprites', (pc,))
        else:
            c['hide cases ok'] += 1
    # the painter: a figure paints nothing, others paint as the original
    for ix, i, want_paint in ((36634, 9, False), (36906, 104, False), (36730, 119, True), (38360, 140, True)):
        fresh()
        m = state(ix, i, 100, 100, col=66)
        m[36582], m[36583] = 3, 24
        o, s = _fullrun(r, None, m, call(m, 39015, ix))
        if o is None or not _cmp(r, o, s, c, 'paint'):
            continue
        same = bytes(s.memory[0x5800:0x5B00]) == bytes(o.memory[0x5800:0x5B00])
        kept = bytes(s.memory[0x5800:0x5B00]) == blank[6144:]
        if (want_paint and same) or (not want_paint and kept):
            c['paint cases ok'] += 1
        else:
            r.fail('paint', (ix, i, same, kept))
    # the row plotters: each width, aligned or not, at a third's edge: no ULA change, only A' differs
    for w in range(1, 10):
        for al in (0, 6):
            for pc, sm in ((38747, 38753), (38881, 38887)):
                for hl in (0x4800 | 3, 0x4700 | 40, 0x4800):
                    fresh()
                    m = bytearray(mem0)
                    m[0x4000:0x5B00] = bytes([0xA5]) * 6912
                    r.P[:] = m[0x4000:0x5B00]
                    m[sm] = (9 - w) * 12 + al
                    m[0x5FF0], m[0x5FF1] = MARK & 255, MARK >> 8
                    rg = call(m, pc, 36634)
                    rg[6], rg[7] = hl >> 8, hl & 255
                    rg[2], rg[3], rg[4], rg[5] = 0xF4, 9, 0xC0, 0x10
                    o, s = _fullrun(r, None, m, rg)
                    if o is None:
                        r.fail('row did not finish', (w, al, pc))
                    elif _cmp(r, o, s, c, 'row', skip=(16,)):
                        if bytes(s.memory[0x4000:0x5B00]) != bytes(r.P):
                            r.fail('row changed the ULA', (w, al, pc))
                        elif o.registers[17] != s.registers[17]:
                            r.fail("row: F'", (w, al, pc))
                        else:
                            c['row cases ok'] += 1
    for k, v in r.c.items():
        if k.endswith('!'):
            c[k] += v
    c.setdefault('_examples', 0)
    c.pop('_examples')
    c.ex = dict(r.ex)
    return c


def run_negatives(rzxs, states, z80, prof=None, say=print):
    """Every broken build on the real recordings, then the unit tests: each must be detected. The shortest
    recordings with a room change first; a clear with figures shown needs a real game over (g0)."""
    prof = prof or load_profile()
    peek = peek_of(z80)
    n = 0
    names = list(negative_patches()) + ['a row write left in']

    def build(name):
        p = UnderwurldePatch(prof, skip_sites=(38758,)) if name == 'a row write left in' else negative_patch(prof, name)
        p.prepare(peek)
        return p
    for name in names:
        f, how = {}, 'unit'
        if name != 'a row write left in':
            for r in rzxs:
                c, ex, _ = verify(build(name), r, stop=17000 if name == 'screen clear keeps the sprites' else 1500)
                f = {k: v for k, v in c.items() if k.endswith('!')}
                if f:
                    how = os.path.basename(r)
                    break
        if not f:
            u = unit_tests(build(name), states)
            f = {k: v for k, v in u.items() if k.endswith('!')}
            how = 'unit'
        n += bool(f)
        say('Negative  : %-34s %s (%s) %s' % (name, 'DETECTED' if f else 'NOT DETECTED!', how, list(f)[:2]))
    return n, len(names)


def a_prime_test(rzx, stop=None):
    """A' after a row, and A and the flags after a rope pixel (XORed with a screen that now has no figure), are what the
    patch changes in the game's registers. Replay with them overwritten: same game? -> (frames, digest), twice."""
    from .simrun import run as srun
    res = []
    for zap in (None, lambda f: (f * 37 + 11) & 255):
        c = {'h': hashlib.md5(), 'n': 0}

        class H:
            def on_sim(h, sim):
                h.R, h.m = sim.registers, sim.memory
                c['raw'] = _raw(sim.memory)

            def before(h, pc):
                if zap and pc in (38704, 38713):
                    h.R[16] = zap(c['n'])                     # A' after a row
                if zap and pc in (44356, 44468):              # after a rope pixel: A, and flags but carry
                    h.R[0] = zap(c['n'])
                    h.R[1] = (h.R[1] & 1) | (zap(c['n']) & 0xFE)

            def on_frame(h, n):
                c['n'] = n
                if n % 200 == 0:
                    raw = c['raw']
                    c['h'].update(bytes(raw[0x5C00:]))
                    c['h'].update(bytes((h.R[24] & 255, h.R[12] & 255)))
        srun(None, rzx=[rzx], hooks=H(), stop=stop)
        res.append((c['n'], c['h'].hexdigest()))
    return res


# ------------------------------------------------------------------------------------------------------------
# Colours (docs/COLOURS.md): the map is applied to the pattern store at build time
# ------------------------------------------------------------------------------------------------------------
NOTE = ('Underwurlde colour map: key = graphics byte (decimal address; check = its value); 8 nibbles, 0 = the '
        'default (the figure\'s run-time ink / black enclosed paper / clear), 1-15 sheet palette slots; a 4th element '
        'marks pixels painted transparent. Figures only: furniture stays on the ULA.')
RECOLOUR = {'game': 'underwurlde', 'output': 'sprites', 'colours': 'docs/profiles/underwurlde_colours.json',
            'clear': True, 'note': NOTE}


def colour_inputs(peek):
    b = bytearray()
    for i in figure_ids(peek):
        p, w, h = graphic(peek, i)
        b += bytes(peek(p + 2 + k) for k in range(w * h))
    return hashlib.md5(bytes(b)).hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': RECORD, 'engine': 'underwurlde', 'keys': 'underwurlde-1: decimal graphics byte address, bit = pixel',
            'inputs': colour_inputs(peek), 'geometry': hashlib.md5(json.dumps(sorted(NONFIG)).encode()).hexdigest()}


def recolour(nex, cmap):
    from . import recolour as rc
    bk = rc.banks(nex)
    if not {5, 2, 0, ALT_PAGE // 2} <= set(bk):
        raise ValueError('not an Underwurlde sprite build')
    ram = bk[5] + bk[2] + bk[0]
    peek = game_view(lambda a: ram[a - 0x4000] if a >= 0x4000 else 0)
    if colour_inputs(peek) != load_profile().get('colour_inputs'):
        raise ValueError('game graphics differ from the expected snapshot')
    prof = load_profile()
    syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    for a, op, sym in [(x[0], x[2], x[3]) for x in SITES]:
        if peek(a) != int(op, 16) or peek(a + 1) + 256 * peek(a + 2) != syms[sym]:
            raise ValueError('patch site %d does not hold this build\'s hook' % a)
    if not cmap:
        cmap = None
    dirb, store = build_store(peek, cmap)
    new = {}
    for pg, data in store.items():
        b = new.setdefault(pg // 2, bytearray(bk[pg // 2]))
        k = (pg & 1) * 8192
        b[k:k + 8192] = data
    out, changed = rc.splice(nex, {b: bytes(d) for b, d in new.items()})
    return out, {'banks changed': changed}


def sheet_part(peek, i, x=0, y=0):
    p, w, h = graphic(peek, i)
    g, W, H = image(peek, i)
    px, ent = [], {}
    for r in range(h):
        for b in range(w):
            a = p + 2 + r * w + b
            ent[str(a)] = [peek(a), 'g']
            for k in range(8):
                v = g[h - r][1 + b * 8 + k]
                # staging: ink at (b * 8 + k, h - 1 - r); enclosed paper = opaque black code 2; open paper = code 0
                px.append((b * 8 + k, h - 1 - r, str(a), k, 1 if v == 1 else 2 if v == 2 else 0, 1 if v == 1 else 2 if v == 2 else 0))
    return {'id': i, 'size': 1, 'w': w * 8, 'h': h, 'x': x, 'y': y, 'mir': 0, 'group': family(i), 'pixels': px, 'entries': ent}


def family(i):
    return 'player' if i <= 43 else 'figures'


def sheets(z80, out_dir, prefix='underwurlde', colours=None, say=print):
    """Sheets from the game's own graphic table (no recording: patterns are per id). Figures show white: their
    run-time ink follows the room; a painted pixel becomes a fixed colour."""
    from . import coloursheet as cs
    peek = peek_of(z80)
    ident = colour_identity(peek)
    rgb = cs.palette_rgb(SHEET)
    comps = []
    y = 0
    for i in figure_ids(peek):
        q = sheet_part(peek, i, 0, 0)
        comps.append({'count': 1, 'group': q['group'], 'parts': [dict(q, dx=0, dy=0, dmir=0, vmir=0)]})
    os.makedirs(out_dir, exist_ok=True)
    painted = os.path.join(out_dir, prefix + '_PAINTING_SPRITES.png')
    cs.write(comps, painted, painted[:-4] + '_layout.json', rgb, colours, paint_clear=True, identity=ident)
    ref = os.path.join(out_dir, prefix + '_REFERENCE_ALL_SPRITES.png')
    cs.write(comps, ref, ref[:-4] + '_layout.json', rgb, colours, paint_clear=True, identity=ident)
    say('Sheets    : %s (%d figures)' % (painted, len(comps)))
    return painted


# ------------------------------------------------------------------------------------------------------------
def _start_check(spr, patch, say):
    """The first LDIR, on the build's own RAM: every site in its place, at the addresses the replays patch."""
    from . import recolour as rc
    bk = rc.banks(open(spr, 'rb').read())
    ram = bytearray(bk[5] + bk[2] + bk[0])
    d0 = 0x6801 - 0x4000
    moved = bytes(ram[d0:d0 + 0x8800])
    ram[0x6800 - 0x4000:0x6800 - 0x4000 + 0x8800] = moved
    miss = [a for a, old, new in patch.sites if bytes(ram[a - 0x4000:a - 0x4000 + len(new)]) != new]
    say('Start     : USR 26610: DI, LDIR down one byte, JP 30336: %d of %d sites in place after it' % (len(patch.sites) - len(miss), len(patch.sites)))
    return not miss


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : underwurlde (XOR plotter 38647 / 38442 / 38454, painter 39015 -> sprites per record)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = UnderwurldePatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, TAIL_ADDR, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s, %d sites, %d store pages' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300], len(patch.sites), len(patch.store)))
    ok = not bad and not bad2 and len(patch.sites) == 42
    ok = _start_check(spr, patch, say) and ok
    states = []
    tot = collections.Counter()
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states = states or st
        tot.update(c)
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames: move %d, draw %d, erase %d, paint %d, room %d, clear %d, figure plots %d, rope pixels %d; picture checks %d, with a difference %d (%d pixels); paints over other-coloured scenery %d of %d, %d cells -> %s' % (
            os.path.basename(r), c['frames'], c['n38647'], c['n38442'], c['n38454'], c['n39015'], c['n39175'], c['n38269'], c['figure plots'], c['rope pixels'], c['screen checks'],
            c['screen checks with a difference'], c['screen pixels differing'], c['paints over other-coloured scenery'], c['paints'], c['scenery cells recoloured'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
    if tot:
        tp, to = tot['T patched'], tot['T original']
        say('Totals    : %d frames, figure plots %d, picture checks %d, differences %d, rope pixels %d, paints over other-coloured scenery %d of %d (%.1f %%), %d cells; ids drawn %s' % (
            tot['frames'], tot['figure plots'], tot['screen checks'], tot['screen checks with a difference'], tot['rope pixels'], tot['paints over other-coloured scenery'], tot['paints'],
            100.0 * tot['paints over other-coloured scenery'] / (tot['paints'] or 1), tot['scenery cells recoloured'], sorted(int(k[2:]) for k in tot if k.startswith('id') and k[2:].isdigit())))
        say('Speed     : hooks cost %d T over %d frames: %.1f %% of the frames\' T (speed-weighted estimate; no contention)' % (tp - to, tot['frames'], 100.0 * (tp - to) / (tot['frames'] * 69888 or 1)))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % ({k: v for k, v in u.items() if not k.endswith('!')}, 'PASS' if not uf else 'FAIL %s %s' % (uf, str(getattr(u, 'ex', ''))[:500])))
        if not getattr(a, 'quick', None):
            g0 = [r for r in a.rzx if 'g0' in os.path.basename(r)]
            short = [r for r in a.rzx if os.path.basename(r).startswith('t')][:1]
            n, m = run_negatives(short + g0, states, z80, say=say)
            ok = ok and n == m
            say('Negatives : %d/%d DETECTED' % (n, m))
            for r in short + g0:
                x, y = a_prime_test(r, stop=3000)
                ok = ok and x == y
                say("Dead regs : %s A' after a row, A and flags after a rope pixel overwritten: %s" % (os.path.basename(r), 'same game' if x == y else 'DIFFERENT'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
