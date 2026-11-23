"""Hard Drivin' (Domark / Binary Design, 1989; 128K): the smoother 3D view (games/hard_drivin.md "Decision").

The game's render (0x9EA9, called at 0x9E54) and view copy (0xDC37, at 0x9E6B) run at 28 MHz, each held to the
original's time; the freed time draws in-between views (the camera interpolated from the last update's to this
one's) on scratch copies of the game's pages, each shown by the game's own copy while the beam is below the view.
The render's 3.5 MHz : 28 MHz ratio K is measured at run time (a calibration render on scratch pages, IM 2 through
the hook page). Hooks: asm/hard_drivin_hooks.asm (profile hooks.page = page 36 in MMU slot 1, hooks.rom = the alt
ROM's trampoline bytes at SH).

Verify (PLAYBOOK 6): at every render the update loop calls, the hooked block 0x9E54 .. 0x9E6E runs in the host
model (Next: the MMU, alt ROM, NextRegs, the video line, zxnDMA, the frame interrupt) on the normal and on the
calibration path, against the original from the same state: game RAM (but the screen's view and the site bytes),
registers (CMP); each in-between view = the original render at its exactly computed camera; the calibration
render's time = the original render's. Unit tests: cases the recording does not reach + the negative controls.
"""
import collections
import copy
import hashlib
import json
import os
from pathlib import Path

from . import z80tonex as zt
from . import z80n

_HERE = os.path.dirname(os.path.abspath(__file__))
ALT_BANK = 12                   # 16K bank: page 24 = the alt ROM image's low half (unused), 25 = its 0x2000-0x3FFF
CODE_BANK = 18                  # pages 36 (the hook page) / 37
TAIL_ADDR = 0x6C00              # 0x6B53-0x6D5F untouched over all 22,116 recorded frames (games/hard_drivin.md)
GAME = [0xFF, 0xFF, 10, 11, 4, 5, 0, 1]     # MMU in play: bank 5, 2, 0 (7FFD 0x10 / 0x13: bank 0 or 3 at C000)
LINE_T = 228 * 8                # the model's clock: 28 MHz T; a 3.5 MHz instruction counts 8 x its T
FRAME_T = 311 * LINE_T
SP, PC, T, IFF = 12, 24, 25, 26
CMP = [i for i in range(28) if i not in (13, 15, 25)]   # registers but R (15), T (25), and 13 (unused slot)
NAMES = ['A', 'F', 'B', 'C', 'D', 'E', 'H', 'L', 'IXh', 'IXl', 'IYh', 'IYl', 'SP', '-', 'I', 'R', "A'", "F'", "B'",
         "C'", "D'", "E'", "H'", "L'", 'PC', 'T', 'IFF', 'IM']
RENDER, STOP, RET_R = 0x9EA9, 0x9E6E, 0x9E57
CAM = list(range(43400, 43406)) + [43407, 43408, 43409]     # x, y, z words; orientation (43406: a flag)
CAL_MIN_SPEC = 1000             # lines: a shorter calibration render must give no sample (the verify's own rule)
DROP_MAX = 0.4                  # a share of dropped calibration samples above this: calibrations crowd out views


# ----------------------------------------------------------------------------------------------------- profile
def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'hard_drivin.json'),
              os.path.join(_HERE, 'hard_drivin.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('hard_drivin.json profile not found')


_PROF = []


def load_profile():
    if not _PROF:
        _PROF.append(json.load(open(_profile_path())))
    return _PROF[0]


def syms():
    return {k: int(v, 16) for k, v in load_profile()['hooks']['syms'].items()}


def sites():
    """[(address, original bytes, hook symbol)]"""
    return [(int(a, 16), bytes.fromhex(o), t) for a, o, t, _ in load_profile()['sites']]


def is_hard_drivin(snap):
    try:
        if snap.machine == '48K':
            return False
        sg = load_profile()['signature']
        a, b = sg['addr'], bytes.fromhex(sg['bytes'])
        if not 0x8000 <= a < 0xC000 - len(b):
            return False
        ram = snap.ram(-1)
        o = 2 * 0x4000 + a - 0x8000                # bank 2 at 0x8000
        return bytes(ram[o:o + len(b)]) == b
    except (FileNotFoundError, AttributeError, KeyError, ValueError, IndexError):
        return False


# ------------------------------------------------------------------------------------------------------- build
class HDPatch:
    """The smooth build: three CALL sites to the trampolines, the hook page (bank 18), the alt ROM image (bank 12:
    Sinclair's ROM 1 + the trampolines at SH, the start-up register block after them). `page_edits` {page offset:
    bytes} makes a broken build (negative_patches)."""
    name = "Hard Drivin': render + copy at 28 MHz in original-time windows, in-between views"

    def __init__(self, page_edits=None, label='smooth'):
        h = load_profile()['hooks']
        self.S = S = syms()
        self.label = label
        self.rom_code = bytes.fromhex(h['rom'])
        page = bytearray.fromhex(h['page'])
        for off, data in (page_edits or {}).items():
            page[off:off + len(data)] = data
        self.code_page = bytes(page)
        assert len(self.code_page) == 8192
        self.stub_extra = b''
        self.setup_call = None
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        SH = S['SH']
        assert self.code_page[S['t_render'] - 0x2000:S['t_render'] - 0x2000 + 4] == self.rom_code[:4]
        self.regblock = SH + len(self.rom_code)
        assert self.regblock + 20 <= 0x3A3A
        self.slot1 = (2 * ALT_BANK, self.regblock)
        self.altrom = (SH, self.regblock + 20)
        rom = zt.rom48()
        assert all(b == 0xFF for b in rom[SH:self.regblock + 20])
        alt = bytearray(rom[0x2000:0x4000])
        alt[SH - 0x2000:SH - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(alt)
        self.sites = [(a, o, bytes([0xCD, S[t] & 255, S[t] >> 8])) for a, o, t in sites()]
        self.extra_banks = {}
        self.entry = None

    def apply(self, snap):
        if not snap.is128:
            raise ValueError("Hard Drivin': a 128K snapshot expected")
        banks = {b: bytearray(snap.banks[b]) for b in range(8)}
        for a, old, new in self.sites:
            b, o = _where(a)
            if bytes(banks[b][o:o + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X (bank %d: %s, expected %s)' % (
                    a, b, banks[b][o:o + len(old)].hex(), old.hex()))
            banks[b][o:o + len(new)] = new
        for b in range(8):
            snap.banks[b] = bytes(banks[b])
        self.entry = snap.pc
        self.extra_banks = {ALT_BANK: self.page + bytes(8192), CODE_BANK: self.code_page + bytes(8192)}


def _where(a):
    """(bank, offset) of a game address in play (bank 0 at C000)"""
    if a < 0x8000:
        return 5, a - 0x4000
    if a < 0xC000:
        return 2, a - 0x8000
    return 0, a - 0xC000


def build(z80, out, patch=None):
    patch = patch or HDPatch()
    zt.convert(str(z80), str(out), patch=patch, quiet=True)
    return patch


def build_plain(z80, out):
    zt.convert(str(z80), str(out), tail_req=TAIL_ADDR, quiet=True)


def boot_problems(nex, z80, patch=None):
    """128K boot check: all RAM banks, registers / R, the hidden ROM, with and without NEXLOAD (as
    head_over_heels.boot_problems); the tail and NEXLOAD's printer buffer credited to rom_paths (below)."""
    from skoolkit import CSimulator
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot
    from . import nextboot
    original = from_snapshot(CSimulator, Snapshot.get(str(z80)))
    expected = zt.Z80Snapshot(str(z80))
    entry = expected.pc
    if patch is not None:
        q = copy.deepcopy(patch)
        q.apply(expected)
    _, tail, tlen = nextboot.tail_of(str(nex))
    bad = []
    for nexload in (False, True):
        # credited (nextboot.rom_paths proves the game writes them before any read): the start-up tail's bytes, and
        # booted as NEXLOAD the printer buffer it leaves (BRIEFING C2 #36; keep_printer_buffer is 48K only)
        skip = set(range(tail, tail + tlen)) | (set(range(0x5B00, 0x5C00)) if nexload else set())
        st = nextboot.boot(str(nex), entry, nexload=nexload, sysrom=nextboot.system_rom3()[0])
        bad.extend(('ROM', nexload, v) for v in st['bad'])
        for i in CMP:
            a, b = original.registers[i], st['R'][i]
            if (bool(a) != bool(b)) if i == IFF else (a != b):
                bad.append(('register', nexload, i, a, b))
        for bank in range(8):
            st['mmu'][6:8] = [bank * 2, bank * 2 + 1]
            base = {5: 0x4000, 2: 0x8000}.get(bank, -0x10000)
            mm = [i for i in range(16384) if st['mem'][0xC000 + i] != expected.banks[bank][i] and base + i not in skip]
            if mm:
                bad.append(('RAM', nexload, bank, len(mm), mm[:8]))
    return bad


boot_check = boot_problems


# ------------------------------------------------------------------------------------------------ host model
def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class Next:
    """The build's memory as on the Next, in SkoolKit's simulator (writes below 0x4000 kept: the hook page in slot
    1, the ROM copy in slot 0) + nexclash.z80n. Slots 0-1 = the alt ROM image, 2-7 = the game's pages, NEXTREG
    0x50-0x57 swap 8K pages; 0x07 = speed (a 3.5 MHz instruction counts 8 x its T on the 28 MHz clock, a 28 MHz one
    8 / k_model); ports 0x243B / 0x253B read NR 0x07, the video line (0x1E / 0x1F: 311 lines of 228 x 8 T, line 0 =
    the first pixel row at the clock's 0) and the MMU; zxnDMA on 0x6B (5 T a byte at 28 MHz); the frame interrupt at
    line int_line (IM 2 vector at I x 256 + 0xFF), accepted only where allow_ei. Every accepted interrupt's push is
    logged (pushlog: address, the two bytes it overwrote)."""

    def __init__(self, mem64, patch, k_model=8.0):
        self.S = S = patch.S
        rom = bytearray(zt.rom48())
        rom[S['SH']:S['SH'] + len(patch.rom_code)] = patch.rom_code
        self.rom = bytes(rom)
        self.pages = {36: list(patch.code_page), 37: [0] * 8192}
        for p in range(38, 45):
            self.pages[p] = [0x55] * 8192
        g = bytearray(mem64[0x4000:0x10000])
        for a, old, new in patch.sites:
            assert bytes(g[a - 0x4000:a - 0x4000 + len(old)]) == old, 'site %04X' % a
            g[a - 0x4000:a - 0x4000 + len(new)] = new
        self.mem = list(self.rom) + list(g)
        for p in GAME[2:]:
            self.pages[p] = None                    # their content lives in mem while mapped
        self.slots = list(GAME)
        self.nr = {7: 0}
        self.sel = 0
        self.sim = _sim_class()(self.mem, {})
        self.sim.int_active = 0
        z80n.install(self.sim, nextreg=self.nextreg)
        self.sim.set_tracer(self)
        self.R = self.sim.registers
        self.clock = 0
        self.dma = None
        self.dma_bytes = 0
        self.bad = []
        self.k_model = k_model
        self.int_line = 248
        self.irqs = 0
        self.pushlog = []
        self.allow_ei = False

    def line(self):
        return int(self.clock // LINE_T) % 311

    def map(self, slot, page):
        m, lo = self.mem, slot * 8192
        cur = self.slots[slot]
        if cur != 0xFF:
            self.pages[cur] = m[lo:lo + 8192]
        if page == 0xFF:
            if slot > 1:
                raise RuntimeError('ROM in slot %d' % slot)
            m[lo:lo + 8192] = list(self.rom[lo:lo + 8192])
        else:
            if page in self.slots and self.slots.index(page) != slot:
                self.bad.append('page %d in two slots' % page)
            src = self.pages.get(page)
            m[lo:lo + 8192] = src if src is not None else [0] * 8192
        self.slots[slot] = page

    def nextreg(self, reg, v):
        if 0x50 <= reg <= 0x57:
            self.map(reg - 0x50, v)
        self.nr[reg] = v

    def read_port(self, regs, port):
        if port == 0x253B:
            if self.sel == 7:
                return (self.nr[7] & 3) * 0x11
            if self.sel in (0x1E, 0x1F):
                ln = self.line()
                return ln >> 8 if self.sel == 0x1E else ln & 255
            if 0x50 <= self.sel <= 0x57:
                return self.slots[self.sel - 0x50]
            return self.nr.get(self.sel, 0)
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if port == 0x243B:
            self.sel = value
        elif port == 0x253B:
            self.nextreg(self.sel, value)
        elif port & 255 == 0x6B:
            if self.dma is None:
                from .dma import DMA

                def wr(a, v):
                    if a < 0x2000 and self.slots[0] == 0xFF or 0x2000 <= a < 0x4000 and self.slots[1] == 0xFF:
                        self.bad.append('DMA write to %04X' % a)
                    self.mem[a] = v
                self.dma = DMA(lambda a: self.mem[a], wr, lambda p, v: self.bad.append('DMA to port %04X' % p),
                               stall=self.stall)
            self.dma.feed(value)
        elif port & 0xFF == 0xFD and port & 0x8002 == 0:
            b = value & 7
            self.map(6, 2 * b)
            self.map(7, 2 * b + 1)

    def stall(self, n):
        if self.nr[7] & 3 != 3:
            self.bad.append('DMA below 28 MHz')
        self.clock += 5 * n
        self.dma_bytes += n

    def page(self, p):
        if p in self.slots:
            o = self.slots.index(p) * 8192
            return self.mem[o:o + 8192]
        return self.pages.get(p)

    def game_ram(self):
        out = []
        for p in GAME[2:]:
            out += self.page(p)
        return bytes(out)

    def run(self, stop, max_ins=40_000_000, watch=None):
        R, m, ops = self.R, self.mem, self.sim.opcodes
        n = 0
        while R[PC] != stop:
            pc = R[PC]
            if watch and pc in watch:
                watch[pc](self)
            if R[IFF] and not self.allow_ei:
                self.bad.append('interrupts on at %04X' % pc)
                return False
            t0 = R[T]
            op = m[pc]
            ops[op]()
            dt = R[T] - t0
            c0 = self.clock
            self.clock += dt * 8 if not self.nr[7] & 3 else dt * 8 / self.k_model
            ti = ((c0 - self.int_line * LINE_T) // FRAME_T + 1) * FRAME_T + self.int_line * LINE_T
            if (c0 < ti <= self.clock or ti < self.clock <= ti + 256) and R[IFF] and op != 0xFB:
                self.irqs += 1
                R[IFF] = 0
                sp = (R[SP] - 2) & 0xFFFF
                self.pushlog.append((sp, m[sp], m[(sp + 1) & 0xFFFF]))
                m[sp], m[(sp + 1) & 0xFFFF] = R[PC] & 255, R[PC] >> 8
                R[SP] = sp
                v = (R[14] << 8) | 0xFF
                R[PC] = m[v] | m[(v + 1) & 0xFFFF] << 8
                R[T] += 19
                self.clock += 19 * (8 if not self.nr[7] & 3 else 8 / self.k_model)
            n += 1
            if n > max_ins:
                self.bad.append('instruction limit at %04X' % R[PC])
                return False
        return True


# ----------------------------------------------------------------------------------------------- the originals
def _plain_sim(mem, regs):
    from skoolkit.simulator import Simulator
    sim = Simulator(mem, {})
    sim.registers[:] = list(regs)
    return sim


def original(st, stop, limit=8_000_000):
    """The original from a render-entry state (PC 0x9EA9, return 0x9E57 on the stack) to `stop`: (RAM 0x4000-, regs)"""
    m = list(st['mem'])
    sim = _plain_sim(m, st['regs'])
    R, ops, n = sim.registers, sim.opcodes, 0
    while R[PC] != stop:
        ops[m[R[PC]]]()
        n += 1
        if n > limit:
            raise RuntimeError('runaway')
    return bytes(m[0x4000:]), list(R)


def render(st, cam=None, mem=None, limit=5_000_000):
    """The original render from a render-entry state (camera bytes replaced): (memory, T)"""
    m = list(mem if mem is not None else st['mem'])
    if cam is not None:
        for a, v in zip(CAM, cam):
            m[a] = v
    sim = _plain_sim(m, st['regs'])
    R, ops, n = sim.registers, sim.opcodes, 0
    while R[PC] != RET_R:
        ops[m[R[PC]]]()
        n += 1
        if n > limit:
            raise RuntimeError('runaway')
    return m, R[T] - st['regs'][T]


# ------------------------------------------------------------------------------------------------- the checks
def _views_ok(st, post, views, prevcam, site_bytes):
    """Each in-between view = the original render (from the state the real render left, carried view to view) at
    the camera it was drawn with; that camera = previous + step x f / 256 (rounded magnitude, sign kept), f rising
    in (0, 256), 43406 = this update's."""
    if not views:
        return ''
    cur = [st['mem'][a] for a in CAM]
    old = [prevcam[a - 43400] for a in CAM]
    sp = st['regs'][SP]
    m = list(st['mem'][:0x4000]) + list(post[0x4000:])
    m[sp], m[sp + 1] = st['mem'][sp], st['mem'][sp + 1]
    for a in site_bytes:
        m[a] = st['mem'][a]
    lastf = 0
    w = lambda c, i: c[i] | c[i + 1] << 8
    for k, ((cam, flag, f), buf) in enumerate(views):
        if not lastf < f < 256:
            return 'view %d fraction %d after %d' % (k, f, lastf)
        lastf = f
        for i in (0, 2, 4):
            a, b, x = w(old, i), w(cur, i), w(cam, i)
            d = (b - a + 32768) % 65536 - 32768
            q = (abs(d) * f + 128) >> 8
            want = (a + (q if d >= 0 else -q)) % 65536
            if x != want:
                return 'view %d camera word %d %d, expected %d' % (k, i // 2, x, want)
        for i in (6, 7, 8):
            a, b, x = old[i], cur[i], cam[i]
            d = (b - a + 128) % 256 - 128
            q = (abs(d) * f + 128) >> 8
            want = (a + (q if d >= 0 else -q)) % 256
            if x != want:
                return 'view %d angle %d %d, expected %d' % (k, i - 6, x, want)
        if flag != st['mem'][43406]:
            return 'view %d 43406 = %d, not this update\'s' % (k, flag)
        m, _ = render(st, cam=cam, mem=m)
        if bytes(m[0x8000:0x9000]) != bytes(buf):
            return 'view %d differs from the original render at its camera' % k
        m[sp], m[sp + 1] = st['mem'][sp], st['mem'][sp + 1]
    return ''


def check(patch, st, prevcam, cal, om, oregs, stop=STOP, stats=None, setup=None, line=None):
    """The hooked block from a render-entry state vs the original (om, oregs). cal: the calibration path. setup(nx):
    a unit test's change to the hook page before the run; line: the video line at the start (default: one per
    update). -> (ok, in-between views, reason)"""
    nx = Next(st['mem'], patch)
    P = nx.S
    pg = nx.pages[36]
    pv = lambda n: P[n] - 0x2000
    if prevcam is not None:
        for i, adr in enumerate(CAM[:6] + [43406] + CAM[6:]):
            pg[pv('cam0') + i] = prevcam[adr - 43400]
        pg[pv('cam0ok')] = 1
    pg[pv('cal_cnt')] = 0 if cal else 5
    pg[pv('cal_n')] = 0 if cal else 3
    if setup:
        setup(nx, pg)
    nx.allow_ei = True
    R = nx.R
    R[:] = list(st['regs'])
    R[SP] += 2                                      # before the site's CALL
    R[PC] = 0x9E54
    nx.clock = ((st['u'] * 97) % 311 if line is None else line) * LINE_T
    snap, views, cams = {}, [], []

    def at_post(n):
        snap.setdefault('post', bytes(n.mem[:65536]))

    def at_render(n):
        if n.slots[4] == P['PG_S4']:
            cams.append(([n.mem[a] for a in CAM], n.mem[43406], n.mem[P['t_f']]))

    def at_copy(n):
        if n.slots[4] == P['PG_S4']:
            views.append((cams[-1] if cams else None, bytes(n.mem[0x8000:0x9000])))
    watch = {P['h_post']: at_post, 0xDC37: at_copy, RENDER: at_render}
    try:
        ok = nx.run(stop, watch=watch)
    except Exception as e:                          # a runaway into a mapping error (a broken build)
        return False, 0, 'model: %r' % e
    gm = nx.game_ram()
    regs = list(R)
    site_bytes = {a + i for a, o, _ in patch.sites for i in range(1, len(o))}
    dm = [a + 0x4000 for a in range(len(gm)) if gm[a] != om[a] and a >= 0x1000 and a + 0x4000 not in site_bytes]
    dr = [NAMES[i] for i in CMP if regs[i] != oregs[i]]
    pgv = nx.page(36)
    rd = lambda n: pgv[pv(n)] | pgv[pv(n) + 1] << 8
    tn = pgv[pv('t_n')]
    bad = list(nx.bad)
    if tn != len(views):
        bad.append('%d views counted, %d copied' % (tn, len(views)))
    if ok and 'post' in snap and prevcam is not None:
        try:
            v = _views_ok(st, snap['post'], views, prevcam, site_bytes)
        except RuntimeError as e:
            v = 'reference render: %s' % e
        if v:
            bad.append(v)
    if cal:
        wm = pgv[pv('wmap'):pv('wmap') + 512]
        hit = lambda x: wm[x >> 7] >> ((x >> 4) & 7) & 1
        hits = [k for k, (a, _, _) in enumerate(nx.pushlog) if hit(a) or hit((a + 1) & 0xFFFF)]
        if hits and hits[0] != len(nx.pushlog) - 1:
            bad.append('the render went on after push %d of %d hit the write set' % (hits[0], len(nx.pushlog)))
        if ok and pgv[pv('cal_tnt')]:
            if stats is not None:
                stats['dropped'] += 1
            if rd('k256') != P['K_INIT']:
                bad.append('a dropped sample changed K')
            if pgv[pv('cal_cnt')] != 1:
                bad.append('a dropped sample: next calibration in %d updates' % pgv[pv('cal_cnt')])
        elif ok:
            _, t_orig = render(st)
            t_cal = rd('cal_e') * 228
            if stats is not None:
                stats['kept'] += 1
                stats['err'].append((t_cal - t_orig) / t_orig)
            if t_orig < CAL_MIN_SPEC * 228:
                bad.append('a sample from a %d-line render' % (t_orig // 228))
            elif abs(t_cal - t_orig) > t_orig / 200:
                bad.append('calibration render %d T, the original %d T' % (t_cal, t_orig))
    good = ok and not dm and not dr and not bad and regs[PC] == stop
    why = '' if good else 'RAM %s regs %s %s%s' % (' '.join('%04X' % x for x in dm[:6]), dr, bad[:2],
                                                   '' if ok else ' (no stop)')
    return good, tn, why


# ------------------------------------------------------------------------------------------------- the verify
def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=1, paths=('normal', 'cal')):
    """Differential test over a recording (module docstring). -> (Counter, failures, states). Failure keys end in
    '!'; failures = [(key, update, reason)] (5 a key); collect=N keeps N render-entry states (+ the previous camera),
    spread over the run, for unit_tests."""
    from . import simrun
    c = collections.Counter()
    fails, per = [], collections.Counter()
    stats = {'kept': 0, 'dropped': 0, 'err': []}
    sim, upd = [None], [0]
    keep, prev = [], [None]

    class H:
        def on_sim(s, x):
            sim[0] = x

        def on_desync(s, f, msg):                   # a lost sync must fail, not end the replay quietly
            c['desync!'] += 1
            fails.append(('desync!', f, msg))

        def before(s, pc):
            if pc == 0x9E34:
                upd[0] += 1
            elif pc == RENDER:
                x = sim[0]
                m, sp = x.memory, x.registers[SP]
                if m[sp] == RET_R & 255 and m[(sp + 1) & 0xFFFF] == RET_R >> 8:
                    mem = bytes(m[i] for i in range(65536))
                    st = {'u': upd[0], 'mem': mem, 'regs': list(x.registers)}
                    c['renders'] += 1
                    if c['renders'] % every == 0:
                        _one(st, prev[0])
                        if collect and (c['renders'] % 25 == 1) and len(keep) < collect:
                            keep.append((st, prev[0]))
                    prev[0] = mem[43400:43410]

    def _one(st, prevcam):
        stp = STOP
        try:
            om, oregs = original(st, STOP)
        except RuntimeError:                        # the clock's escape (JP 0x9E12) before the copy
            stp = RET_R
            om, oregs = original(st, stp)
            c['escapes'] += 1
        for p in paths:
            good, tn, why = check(patch, st, prevcam, p == 'cal', om, oregs, stp, stats)
            c['checks'] += 1
            c['views'] += tn
            if not good:
                k = '%s!' % p
                c[k] += 1
                if per[k] < 5:
                    fails.append((k, st['u'], why))
                per[k] += 1
        if progress and c['renders'] % 200 == 0:
            progress('verify    : u%d %d checks, %d fail' % (st['u'], c['checks'], sum(v for k, v in c.items()
                                                                                         if k.endswith('!'))))
    simrun.play_rzx(str(rzx_path), H(), stop=stop)
    n = stats['kept'] + stats['dropped']
    c['calibration samples kept'] = stats['kept']
    c['calibration samples dropped'] = stats['dropped']
    if stats['err']:
        e = sorted(stats['err'])
        c['calibration error ppm max'] = int(1e6 * max(abs(e[0]), abs(e[-1])))
    if n >= 20 and stats['dropped'] > DROP_MAX * n:
        c['calibration samples dropped over 40 %!'] += 1
        fails.append(('calibration samples dropped over 40 %!', None, '%d of %d' % (stats['dropped'], n)))
    if c['renders'] and not c['views']:
        c['no in-between view!'] += 1
    return c, fails, keep


# ----------------------------------------------------------------------------------------------- unit tests
def negative_patches(patch=None):
    """Broken builds every negative control must catch: (name, HDPatch)."""
    S = syms()
    o = lambda n: S[n] - 0x2000
    return [
        ('extra views on the game\'s own pages', HDPatch({o('sco_map'): bytes(16)}, 'neg')),     # 4 NEXTREG -> NOP
        ('setcam angles from cam0+6', HDPatch({o('sc_angix'): bytes(2)}, 'neg')),                 # INC IX -> NOP NOP
        ('no repair of an interrupt\'s push', HDPatch({o('isr_fix'): b'\xC9'}, 'neg')),
        ('no write-set check', HDPatch({o('isr_taint'): b'\xC9'}, 'neg')),
    ]


def unit_tests(patch, states, neg=None):
    """Cases the recording does not reach, on collected states, + the negative controls. -> Counter ('!' = fail)"""
    c = collections.Counter()
    if not states:
        c['no states!'] += 1
        return c
    S = patch.S
    for st, prevcam in states:
        try:
            om, oregs = original(st, STOP)
            stp = STOP
        except RuntimeError:
            stp = RET_R
            om, oregs = original(st, stp)
        cases = []
        if prevcam is not None:
            far = bytearray(prevcam)
            far[1] ^= 0x40                          # x moved by 16384: over the 2047 limit, no extra view
            cases.append(('far step: no in-between view', bytes(far), False, None, 0))
            cases.append(('no previous camera', None, False, None, 0))

            def all_hit(nx, pg):
                pg[S['wmap'] - 0x2000:S['wmap'] - 0x2000 + 512] = [0xFF] * 512
            cases.append(('every push a hit: abandoned, dropped', prevcam, True, all_hit, None))

            def k_low(nx, pg):
                pg[S['k256'] - 0x2000:S['k256'] - 0x2000 + 2] = [0x00, 0x04]   # K = 4: short windows (debt)
            cases.append(('K 4: windows short, debt', prevcam, False, k_low, None))

            def k_high(nx, pg):
                pg[S['k256'] - 0x2000:S['k256'] - 0x2000 + 2] = [0x00, 0x0A]   # K = 10: the most in-between views
            cases.append(('K 10: long windows', prevcam, False, k_high, None))
        for name, pc, cal, setup, want_views in cases:
            good, tn, why = check(patch, st, pc, cal, om, oregs, stp, setup=setup)
            if good and (want_views is None or tn == want_views):
                c[name] += 1
            else:
                c[name + '!'] += 1
    for name, bad in (neg if neg is not None else negative_patches(patch)):
        caught = False
        for st, prevcam in states:
            try:
                om, oregs = original(st, STOP)
                stp = STOP
            except RuntimeError:
                stp = RET_R
                om, oregs = original(st, stp)
            for cal, line in [(False, None)] + [(True, x) for x in range(0, 311, 13)]:
                good, _, _ = check(bad, st, prevcam, cal, om, oregs, stp, line=line)   # the start line moves the
                if not good:                                # frame interrupt over the render (a push into its data)
                    caught = True
                    break
            if caught:
                break
        c['negative: %s %s' % (name, 'detected' if caught else 'MISSED!')] += 1
    return c


# ------------------------------------------------------------------------------------------------------- auto
DECISIONS = {'route': 'smoother 3D view (user, 2026-11-22)', 'tail': '0x6C00'}


def auto(a, z80, name, out, say):
    for key, value in (('publisher', 'Domark / Binary Design, 1989'), ('fix_label', 'smoother 3D view')):
        if not getattr(a, key, None):
            setattr(a, key, value)
    ok = True
    out = Path(out)
    plain = out / (name + '.nex')
    build_plain(z80, plain)
    bad = boot_problems(plain, z80)
    ok &= not bad
    say('Plain     : %s %s' % (plain.name, hashlib.md5(plain.read_bytes()).hexdigest()))
    say('Boot      : %s' % (bad[:3] if bad else 'PASS (128K RAM but the tail / NEXLOAD printer buffer, registers/R, hidden ROM)'))
    smooth = out / (name + '_smooth.nex')
    patch = build(z80, smooth)
    bad = boot_problems(smooth, z80, patch)
    ok &= not bad
    say('Smooth    : %s %s' % (smooth.name, hashlib.md5(smooth.read_bytes()).hexdigest()))
    say('Boot      : %s' % (bad[:3] if bad else 'PASS (128K RAM but the tail / NEXLOAD printer buffer, registers/R, hidden ROM)'))
    say('Sprites   : none (this route keeps the ULA picture; games/hard_drivin.md "Decision")')
    states = []
    for rec in getattr(a, 'rzx', []) or []:
        counts, fails, kept = verify(patch, rec, stop=getattr(a, 'quick', None), collect=12, progress=say)
        states += kept
        bad_keys = [k for k, v in counts.items() if k.endswith('!') and v]
        ok &= not bad_keys
        say('Verify    : %s %s' % (dict(counts), fails[:2]))
    if states:
        units = unit_tests(patch, states)
        ok &= not any(v for k, v in units.items() if k.endswith('!'))
        say('Unit      : %s' % dict(units))
    else:
        say('Unit      : no states (no recording given)')
        ok = False
    (out / (name + '_outputs.json')).write_text(json.dumps(
        {'default': name + '_smooth.nex', 'plain': name + '.nex', 'colours': {}}, indent=1) + '\n')
    say('Result    : ' + ('PASSED' if ok else 'FAILED'))
    return bool(ok)
