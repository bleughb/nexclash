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
LOAD_SCREEN = 'hard_drivin_loading.scr'     # the user's 6,912-byte screen file, a local input beside the snapshot
LOAD_MD5 = '92c6cbc7cce166e16190a5971749905d'
# Trainers (games/hard_drivin.md "Trainers"), off by default, menu options in the .nxc: name -> ((address, original,
# value), ...); 0xC000 up is bank 0 (_where). Each outside every hook site, step gate and Spec hook (unit_trainers).
TRAINERS = {
    'Infinite time': ((0xA3D8, 0x01, 0x00),),                   # the lap clock's SUB 1 (0xA3D7) -> SUB 0
    'Hard pilot': ((0xA5EE, 0x02, 0xFF),),                      # LD A,2 at 0xA5ED (to 965D) -> LD A,0xFF
    '9 replays': ((0xF5DD, 0x02, 0x09),),                       # LD A,2 at 0xF5DC (to 950E) -> LD A,9
    'Infinite off-road': ((0xA356, 0xA7, 0xAF),),               # AND A before JR NZ at 0xA357 -> XOR A
    'No crashes': ((0xA8D1, 0x35, 0x00), (0xE901, 0x35, 0x00), (0xE97B, 0x35, 0x00))}   # DEC (HL) on 958B -> NOP
# where each trainer's effect shows: (entry PC, stop PC(s)); unit_trainers runs both sides from recorded states there
TRAINER_RUNS = {'Infinite time': ((0xA3D7, (0xA3EA,)), ), 'Hard pilot': ((0xA5ED, (0xA5F2,)),),
                '9 replays': ((0xF5DC, (0xF5E1,)),), 'Infinite off-road': ((0xA356, (0xA359, 0xA35F)),),
                'No crashes': ((0xA8D1, (0xA8D2,)), (0xE901, (0xE902,)), (0xE97B, (0xE97C,)))}
TOGGLE_SMOOTH = 'Original time steps'     # the .nxc's toggle: the smooth build instead of the steps default
TRAINER_PCS = {pc for runs in TRAINER_RUNS.values() for pc, _ in runs}
_ORIG_AT = {pc: bytes.fromhex(h) for pc, h in ((0xA3D7, 'd601'), (0xA5ED, '3e02'), (0xF5DC, '3e02'), (0xA356, 'a720'),
                                               (0xA8D1, '352a'), (0xE901, '352a'), (0xE97B, '352a'))}   # paged in


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

    def __init__(self, page_edits=None, label='smooth', trainers=()):
        h = load_profile()['hooks']
        self.S = S = syms()
        self.label = label
        self.trainers = tuple(trainers)
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
        for name in self.trainers:                  # a trainer-on build (the .nxc applies the same bytes)
            for a, old, new in TRAINERS[name]:
                b, o = _where(a)
                if banks[b][o] != old:
                    raise ValueError('%s: unexpected byte at 0x%04X (bank %d: %02X, expected %02X)' % (
                        name, a, b, banks[b][o], old))
                banks[b][o] = new
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
def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=1, paths=('normal', 'cal'), trainers=(),
           trainer_states=None):
    """Differential test over a recording (module docstring). -> (Counter, failures, states). Failure keys end in
    '!'; failures = [(key, update, reason)] (5 a key); collect=N keeps N render-entry states (+ the previous camera),
    spread over the run, for unit_tests. trainers: TRAINERS names whose bytes go into every render state, both sides
    (a trainer-on check). trainer_states: a dict filled {PC: [(hit, mem, regs)]} at TRAINER_PCS (unit_trainers)."""
    from . import simrun
    c = collections.Counter()
    fails, per = [], collections.Counter()
    stats = {'kept': 0, 'dropped': 0, 'err': []}
    sim, upd = [None], [0]
    keep, prev = [], [None]
    tp = collections.Counter()

    class H:
        def on_sim(s, x):
            sim[0] = x

        def on_desync(s, f, msg):                   # a lost sync must fail, not end the replay quietly
            c['desync!'] += 1
            fails.append(('desync!', f, msg))

        def before(s, pc):
            if pc == 0x9E34:
                upd[0] += 1
            elif pc in TRAINER_PCS and trainer_states is not None:
                x = sim[0]
                if bytes((x.memory[pc], x.memory[pc + 1])) == _ORIG_AT[pc]:     # paged in (0xC000 up: bank 0)
                    tp[pc] += 1
                    if tp[pc] in (1, 3, 9, 27, 81, 243) or tp[pc] % 500 == 0:
                        trainer_states.setdefault(pc, []).append(
                            (tp[pc], bytes(x.memory[i] for i in range(65536)), list(x.registers)))
            elif pc == RENDER:
                x = sim[0]
                m, sp = x.memory, x.registers[SP]
                if m[sp] == RET_R & 255 and m[(sp + 1) & 0xFFFF] == RET_R >> 8:
                    mem = bytes(m[i] for i in range(65536))
                    if trainers:
                        mem = _poked(mem, trainers, getattr(m, 'o7ffd', 0) & 7 == 0)
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
    if trainer_states is not None:
        trainer_states['hits'] = dict(tp)
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


# ----------------------------------------------------------------------------- trainers + the loading screen
def _poked(mem, names, top_bank0=True):
    """A 64K view with the trainers' bytes (0xC000 up only when bank 0 is paged there)."""
    m = bytearray(mem)
    for name in names:
        for a, _old, v in TRAINERS[name]:
            if a < 0xC000 or top_bank0:
                m[a] = v
    return bytes(m)


def trainer_conflicts():
    """Trainer bytes on a hook site (either build), a step gate, a throttle word, the NOPed push-out or a call site:
    [(trainer, address, what)]; empty = every trainer outside them (the .nxc refuses a POKE on a patched byte too)."""
    busy = {}
    for P in (HDPatch(), StepsPatch()):
        for a, old, new in P.sites:
            for x in range(a, a + max(len(old), len(new))):
                busy[x] = '%s site 0x%04X' % (P.label, a)
    busy.update({a: 'step gate' for a in STEP_GATES})
    busy.update({x: 'throttle word' for a in THROTTLE for x in (a, a + 1)})
    busy.update({x: 'push-out NOP' for x in range(*BOUNCE_NOP)})
    busy.update({x: 'call site' for a in CALL_SITES for x in range(a, a + 3)})
    return [(n, a, busy[a]) for n, pokes in TRAINERS.items() for a, _o, _v in pokes if a in busy]


def _trainer_effect(name, pc, mem, regs, pokes=None):
    """Both sides from one state at `pc` (a 64K view with the code paged in) to its stop: (effect shown, detail).
    pokes: the trainer's bytes (default TRAINERS[name]; the negative control passes the original bytes)."""
    stops = dict(TRAINER_RUNS[name])[pc]
    out = []
    for poke in (False, True):
        m = list(mem)
        if poke:
            for a, _old, v in (TRAINERS[name] if pokes is None else pokes):
                m[a] = v
        sim = _plain_sim(m, regs)
        R, ops, n = sim.registers, sim.opcodes, 0
        R[PC] = pc
        while n == 0 or R[PC] not in stops:
            ops[m[R[PC]]]()
            n += 1
            if n > 200:
                return False, 'runaway from 0x%04X' % pc
        out.append((m, list(R)))
    (om, oregs), (tm, tregs) = out
    if name == 'Infinite time':                 # BCD seconds 950C / 950D: the original counts down, the trainer not
        start = (mem[0x950C], mem[0x950D])
        ok = (tm[0x950C], tm[0x950D]) == start != (om[0x950C], om[0x950D])
        return ok, 'clock %02X%02X: original %02X%02X, trainer %02X%02X' % (
            start[1], start[0], om[0x950D], om[0x950C], tm[0x950D], tm[0x950C])
    if name == 'Hard pilot':
        return (om[0x965D], tm[0x965D]) == (2, 0xFF), '965D original %d, trainer %d' % (om[0x965D], tm[0x965D])
    if name == '9 replays':
        return (om[0x950E], tm[0x950E]) == (2, 9), 'replays 950E original %d, trainer %d' % (om[0x950E], tm[0x950E])
    if name == 'Infinite off-road':             # A = 951E (off-road count): the trainer always takes the on-road path
        want = 0xA35F if regs[0] else 0xA359
        return (oregs[PC], tregs[PC]) == (want, 0xA359), '951E %d: original to 0x%04X, trainer to 0x%04X' % (
            regs[0], oregs[PC], tregs[PC])
    if name == 'No crashes':
        c = mem[0x958B]
        return (om[0x958B], tm[0x958B]) == ((c - 1) & 255, c), '958B %d: original %d, trainer %d' % (
            c, om[0x958B], tm[0x958B])
    raise KeyError(name)


def _snapshot_view(z80):
    """The snapshot's 64K with bank 0 at 0xC000 (the game's code page in play) + its registers (simulator order)."""
    s = zt.Z80Snapshot(str(z80))
    regs = [s.a, s.f, s.bc >> 8, s.bc & 255, s.de >> 8, s.de & 255, s.hl >> 8, s.hl & 255, s.ix >> 8, s.ix & 255,
            s.iy >> 8, s.iy & 255, s.sp, 0, s.i, s.r, s.a_, s.f_, s.bc_ >> 8, s.bc_ & 255, s.de_ >> 8, s.de_ & 255,
            s.hl_ >> 8, s.hl_ & 255, s.pc, 0, s.iff1, s.im]
    return bytes(16384) + bytes(s.banks[5]) + bytes(s.banks[2]) + bytes(s.banks[0]), regs


# synthetic states on the snapshot, per entry PC: memory edits (the clock at 01:30 and at 01:00 = a borrow, an
# off-road count, crash counts); A / HL then as the instructions before the entry leave them
TRAINER_SYNTH = {0xA3D7: ([(0x950C, 0x30), (0x950D, 0x01)], [(0x950C, 0x00), (0x950D, 0x01)]),
                 0xA5ED: ([],), 0xF5DC: ([],), 0xA356: ([(0x951E, 3)], [(0x951E, 0)]),
                 0xA8D1: ([(0x958B, 3)],), 0xE901: ([(0x958B, 1)],), 0xE97B: ([(0x958B, 2)],)}


def _synthetic(mem, regs, pc, edits):
    m = bytearray(mem)
    for a, v in edits:
        m[a] = v
    r = list(regs)
    if pc == 0xA3D7:
        r[0] = m[0x950C]                        # LD A,(950C) just ran
    elif pc == 0xA356:
        r[0] = m[0x951E]                        # LD A,(951E) just ran
    elif pc in (0xA8D1, 0xE901, 0xE97B):
        r[6], r[7] = 0x95, 0x8B                 # LD HL,958B just ran
    return bytes(m), r


def unit_trainers(z80, states=None):
    """Each trainer: its bytes outside every hook site (trainer_conflicts); its effect from recorded states at its
    PCs (verify's trainer_states) and from synthetic ones on the snapshot (TRAINER_SYNTH); a negative control: the
    same check with the original bytes in place of the trainer's must fail. -> Counter ('!' = fail)"""
    c = collections.Counter()
    for n, a, what in trainer_conflicts():
        c['trainer %s on %s at 0x%04X!' % (n, what, a)] += 1
    mem, regs = _snapshot_view(z80)
    states = states or {}
    for name, runs in TRAINER_RUNS.items():
        for pc, _stops in runs:
            cases = [('recorded', m, r) for _hit, m, r in states.get(pc, [])]
            cases += [('synthetic',) + tuple(_synthetic(mem, regs, pc, e)) for e in TRAINER_SYNTH[pc]]
            for kind, m, r in cases:
                ok, why = _trainer_effect(name, pc, m, r)
                c['trainer %s %s%s' % (name, kind, '' if ok else '!')] += 1
                if not ok:
                    c['trainer %s 0x%04X: %s!' % (name, pc, why)] += 1
        pc = runs[0][0]                         # negative control: the original bytes, the check must fail
        m, r = _synthetic(mem, regs, pc, TRAINER_SYNTH[pc][0])
        ok, _ = _trainer_effect(name, pc, m, r, pokes=[(a, o, o) for a, o, _v in TRAINERS[name]])
        c['negative: trainer %s %s' % (name, 'MISSED!' if ok else 'detected')] += 1
    return c


def trainer_pok(z80):
    """The verified trainers as a .pok (nxc.py import-pok), the snapshot's bytes checked first: bank field 8 below
    0xC000, 0 above (the code page in play; the snapshot is saved with bank 3 there)."""
    s = zt.Z80Snapshot(str(z80))
    text = ''
    for name, pokes in TRAINERS.items():
        text += 'N%s\n' % name
        for i, (a, old, new) in enumerate(pokes):
            b, o = _where(a)
            if s.banks[b][o] != old:
                raise ValueError('%s: 0x%04X holds %02X, expected %02X' % (name, a, s.banks[b][o], old))
            text += '%s %d %d %d %d\n' % ('Z' if i == len(pokes) - 1 else 'M', 0 if a >= 0xC000 else 8, a, new, old)
    return text + 'Y\n'


def find_screen(z80):
    """The loading screen beside the snapshot (LOAD_SCREEN): its bytes, None when absent; another file is refused."""
    p = Path(z80).resolve().parent / LOAD_SCREEN
    if not p.is_file():
        return None
    data = p.read_bytes()
    if hashlib.md5(data).hexdigest() != LOAD_MD5:
        raise ValueError('%s is not the expected file (MD5 %s)' % (p.name, LOAD_MD5))
    return data


def with_screen(src, dst, screen):
    """dst = the .nex src with the loading screen in the file (header byte 10 = 2: a ULA screen after the header)."""
    raw = bytearray(Path(src).read_bytes())
    if raw[10] != 0 or len(screen) != 6912:
        raise ValueError("Hard Drivin': expected a .nex without a screen and a 6,912-byte loading screen")
    raw[10] = 2
    Path(dst).write_bytes(bytes(raw[:512]) + screen + bytes(raw[512:]))


# ================================================================== route 2a: steps (games/hard_drivin.md "Route 2")
# Every original update (0x9E34 .. its RET) runs as N sub-steps (N = 1, 2, 4) at 28 MHz, paced to real time:
# asm/hard_drivin_steps.asm (profile hard_drivin_steps.json). Its reference is Spec below (the prototype's spec.py
# Spec4, games/hard_drivin.md "Build 2a stage 1-3"); verify_steps runs the build in the host model (NextSteps) and
# Spec from the same state over every recorded update and compares them byte for byte.
LOOP, ESC, TOUT = 0x9E34, 0x9E12, 0xA3F2       # update entry; the escape every abort lands on; the time-out path
CALL_SITES = (0x9E2F, 0xFC4C)                   # the loops' CALL 0x9E34 (CALL t_drv in the build)
STEP_GATES = {                                  # one-byte data toggles the driver writes per sub-step: open, closed, when
    0x9E38: (0x28, 0x18, 'first'),              # crash timer 958B (+ F5D5 replay start)
    0xF4AD: (0xC0, 0xC9, 'first'),              # odometer F4A9 (the whole update's speed)
    0xFAD6: (0x20, 0x18, 'last'),               # traffic / ghost / scripted-path move
    0xA3B4: (0x20, 0x18, 'last'),               # clock flash XOR 5A3A
    0xA3C4: (0x3C, 0x00, 'last'),               # clock sub-count 950B (INC A -> NOP)
    0xFD5F: (0x20, 0x18, 'last'),               # 91DC countdown
    0x9E94: (0xC8, 0xC9, 'last'),               # timer 91DD
    0xA82D: (0x0C, 0x00, 'last'),               # gravity: whole, on the last sub-step
    0xFD8E: (0x02, 0x00, 'last'),               # message timer 91CF (race)
    0xFDA8: (0x02, 0x00, 'last'),               # message timer 91CE (practice)
    0xFDCE: (0x02, 0x00, 'last'),               # message timer 91CF (practice)
    0xE92E: (0x3A, 0xC9, 'last')}               # obstacle-box crash test
THROTTLE = {0xA6A4: 500, 0xA6A8: 8000, 0xA6B7: 500}     # step / limit / step words; per N: 500 >> s, 7500 + step
FRACS = ('PX', 'PY', 'PZ', 'A0', 'A2', 'HD', 'SP', 'VX', 'VY', 'VZ', 'ST')
W16 = {'PX', 'PY', 'PZ', 'HD', 'SP', 'VX', 'VY', 'VZ'}
C_RELAX = {1: None, 2: 75, 4: 41}               # (1 - C / 256) ^ N ~ 1 / 2: the original's halving per update
C4ST, C4UP, C2ST, C2UP = 660, 600, 1350, 1200   # the adaptive N's thresholds (busy lines a sub-step; the .asm's)
NL = 311
STEPS_F28 = 1.2                                 # the model's 28 MHz instruction = 1.2 x its T (route 1's JNext ratio)
BOUNCE_NOP = (0xA4A0, 0xA4B2)                   # NOPed: the collision push-out A4B2..A4DB at the first object
PRESETS = [(300, 4), (660, 4), (661, 4), (1350, 4), (1351, 4), (600, 2), (601, 2), (1350, 2), (1351, 2), (600, 1),
           (1200, 1), (1201, 1), (500, 2), (900, 1), (2000, 2), (1000, 2)]   # (c_sub, n_cur): every branch of the rule


def _steps_profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'hard_drivin_steps.json')


_SPROF = []


def load_steps_profile():
    if not _SPROF:
        _SPROF.append(json.load(open(_steps_profile_path())))
    return _SPROF[0]


def steps_syms():
    return {k: int(v, 16) for k, v in load_steps_profile()['hooks']['syms'].items()}


_TLEN = {0xC3: 3, 0xC9: 1, 0x3A: 3, 0x2A: 3, 0xE5: 1, 0x3E: 2, 0xED: 4}     # the trampolines' instructions


def _check_slots(S, page, rom):
    """every trampoline (both sides) ends (JP / RET / 0xFF fill) before the next slot (the prototype's stage 2 ran a
    10-byte trampoline into the next 8-byte slot)"""
    slots = sorted(v for k, v in S.items() if k.startswith('T_') and '.' not in k)
    for img, base in ((rom, S['SH']), (page, 0x2000)):
        for a, nxt in zip(slots, slots[1:]):
            o = a - base
            while o < len(img) and img[o] != 0xFF:
                op = img[o]
                o += _TLEN[op]
                if op in (0xC3, 0xC9):
                    break
            assert o + base <= nxt, 'trampoline at %04X runs to %04X past %04X' % (a, o + base, nxt)


class StepsPatch(HDPatch):
    """Route 2a: 20 sites -> CALL / JP to the trampolines at SH (original bytes checked), the hook page (bank 18),
    the alt ROM image (bank 12: Sinclair's ROM 1 + the ROM side of the trampolines + the start-up register block).
    `page_edits` {page offset: bytes}: a broken build (STEPS_NEG)."""
    name = "Hard Drivin' steps: N sub-steps an update at 28 MHz, real-time pace"

    def __init__(self, page_edits=None, label='steps', trainers=()):
        prof = load_steps_profile()
        h = prof['hooks']
        self.S = S = steps_syms()
        self.label = label
        self.trainers = tuple(trainers)
        self.page_edits = dict(page_edits or {})
        self.rom_code = bytes.fromhex(h['rom'])
        page = bytearray.fromhex(h['page'])
        for off, data in self.page_edits.items():
            page[off:off + len(data)] = data
        self.code_page = bytes(page)
        assert len(self.code_page) == 8192
        SH = S['SH']
        assert self.code_page[SH - 0x2000:SH - 0x2000 + 4] == self.rom_code[:4]     # nextreg 0x51,PG_CODE: both sides
        _check_slots(S, self.code_page, self.rom_code)
        self.stub_extra = b''
        self.setup_call = None
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.regblock = SH + len(self.rom_code)
        assert self.regblock + 20 <= 0x3D00
        self.slot1 = (2 * ALT_BANK, self.regblock)
        self.altrom = (SH, self.regblock + 20)
        rom = zt.rom48()
        assert all(b == 0xFF for b in rom[SH:self.regblock + 20])
        alt = bytearray(rom[0x2000:0x4000])
        alt[SH - 0x2000:SH - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(alt)
        self.sites = [(int(a, 16), bytes.fromhex(o), bytes([int(op, 16), S[t] & 255, S[t] >> 8]))
                      for a, o, op, t, _ in prof['sites']]
        self.extra_banks = {}
        self.entry = None


def build_steps(z80, out, patch=None):
    patch = patch or StepsPatch()
    zt.convert(str(z80), str(out), patch=patch, quiet=True)
    return patch


# ------------------------------------------------------------------------------------- steps: the reference (Spec)
def _s8(x):
    x &= 0xFF
    return x - 0x100 if x & 0x80 else x


def _s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


class _Ports:
    """The recorded update's IN values: per port its sequence, replayed from the start at every sub-step (controls
    held); a 7FFD write pages the game's memory."""
    def __init__(self, recorded, mem=None):
        self.seq = collections.defaultdict(list)
        for x in recorded:
            self.seq[x[0]].append(x[1])
        self.mem = mem
        self.reset()

    def reset(self):
        self.idx = collections.Counter()

    def read_port(self, regs, port):
        s = self.seq.get(port)
        if not s:
            return 0xFF
        i = self.idx[port]
        self.idx[port] += 1
        return s[min(i, len(s) - 1)]

    def write_port(self, regs, port, value, offset=0):
        if port & 0x8002 == 0 and self.mem is not None:
            self.mem.out7ffd(value)


class _Game:
    """The original game from a captured update entry (128K banks, 7FFD, registers, the update's port reads) in
    SkoolKit's simulator; `patches` {pc: fn(game)} are Spec's hooks (a hook that leaves PC unchanged lets the
    original instruction run)."""
    def __init__(self, st):
        from skoolkit.pagingtracer import Memory
        from skoolkit.simulator import Simulator
        from . import simpool
        self.mem = Memory([list(st['banks'][i * 16384:(i + 1) * 16384]) for i in range(8)], st['o7ffd'], '128K')
        self.sim = simpool.machine(Simulator, self.mem, list(st['regs']), slot='steps_spec')
        self.R = self.sim.registers
        self.patches = {}
        self.set_ports(st['ports'])

    def set_ports(self, ports):
        self.ports = _Ports(ports, self.mem)
        self.sim.set_tracer(self.ports)

    def rw(self, a):
        return self.mem[a] | self.mem[a + 1] << 8

    def wb(self, a, v):
        self.mem[a] = v & 0xFF

    def ww(self, a, v):
        self.mem[a] = v & 0xFF
        self.mem[a + 1] = (v >> 8) & 0xFF

    def ret(self):
        R, m = self.R, self.mem
        R[PC] = m[R[SP]] | m[(R[SP] + 1) & 0xFFFF] << 8
        R[SP] = (R[SP] + 2) & 0xFFFF

    def call(self, target, retaddr):
        R, m = self.R, self.mem
        sp = (R[SP] - 2) & 0xFFFF
        m[sp], m[(sp + 1) & 0xFFFF] = retaddr & 0xFF, retaddr >> 8
        R[SP], R[PC] = sp, target

    def state(self):
        return [bytes(b) for b in self.mem.banks]

    def run_to(self, stops, max_t=80_000_000):
        R, mem, ops, P = self.R, self.mem, self.sim.opcodes, self.patches
        t0, first = R[T], True
        while True:
            pc = R[PC]
            if pc in P:
                P[pc](self)
                if R[PC] != pc:
                    first = False
                    continue
            if not first and pc in stops:
                return pc
            first = False
            ops[mem[pc]]()
            if R[T] - t0 > max_t:
                raise RuntimeError('runaway at %04X' % pc)


class Spec:
    """The steps build's exact integer rules (games/hard_drivin.md "Build 2a stage 1" / "stage 3"; s = log2 N).
    Fractions: one byte F per accumulated variable below the game's value V (true value V + (F - 0x80) / 256; 0x80 at
    boot); a shadow SH holds the V the hook last wrote: V != SH (other game code wrote it) -> F := 0x80.
    pos   A834: [P:F] (24-bit) += (vel16 << 8) >> s per axis (exact for N | 256).
    ang   A856: A98F / A991 [A:F] += (rate8 << 8) >> s; heading [A990:A9A5:F] += (A9A3:A9A6 << 8) >> s. Entered from
          A7BA (return A7BD): relaxation g = target (960D / 960E) - A, gap = g * 256 + 0x80 - F (16-bit signed
          clamp), [A:F] += (gap * C + 128) >> 8, C = 75 / 41 at N = 2 / 4.
    vel   (skid, 965D = 1) A71B saves V0; at A793 per axis [V0:F] += ((vel - V0) << 8) >> s.
    speed (road, 965D = 0) A8BB: [965B:F] += ((HL - 965B) << 8) >> s when the previous sub-step rebuilt the velocity
          from the speed (A7F6 saved VR, VRF) and V0 = VR in x and z; else the whole change, F := 0x80.
    steer A6D2 / A6DC: [96AC:F] (signed) -+= (30 << 8) >> s, clamped to +-120.0.
    gates STEP_GATES (driver, per sub-step); throttle words 500 >> s; N = 1: every hook the original path.
    bounce A4DB JP A834 (push-out): one WHOLE step at s > 0 (fractions kept).
    guards (all N): CEB9 (910A) >= 12h -> RET (a clip vertex past 9E11); C7C0 a vertex y (9E01 + 2i) >= 80h -> RET
          (span fill past row 127); A0E7 / D758 B := B & 7Fh clamped to 1..6, A := 7, on at A0EB / D75C.
    plain the time-out update (950B = 4, 91DC = 950C = 950D = 0 at the driver entry): N = 1, no hook state change."""

    def __init__(self):
        self.N, self.s, self.I, self.C = 1, 0, 0, None
        self.F = {k: 0x80 for k in FRACS}
        self.SH = {k: None for k in FRACS}       # None: not written by a hook yet -> F reset at the first use
        self.V0 = [0, 0, 0]
        self.VR = None
        self.VRF = False
        self.plain = False
        self.stats = collections.Counter()

    def install(self, g):
        p = g.patches
        p.update({0xA834: self.h_pos, 0xA4DB: self.h_bounce, 0xA856: self.h_ang, 0xA71B: self.h_vpre,
                  0xA793: self.h_vpost, 0xA8BB: self.h_speed, 0xA7F6: self.h_vr, 0xCEB9: self.h_guard,
                  0xA6D2: lambda r: self.h_steer(r, -30), 0xA6DC: lambda r: self.h_steer(r, 30),
                  0xC7C0: self.h_fill, 0xA0E7: self.h_shift, 0xD758: self.h_shift})
        for a, (op, cl, when) in STEP_GATES.items():
            assert g.mem[a] == op, 'gate %04X holds %02X' % (a, g.mem[a])
        for a, v in THROTTLE.items():
            assert g.rw(a) == v, 'throttle word %04X' % a

    def fcheck(self, k, cur):
        if self.SH[k] != cur:
            self.F[k] = 0x80

    def acc16w(self, g, addr, k, inc):
        v = g.rw(addr)
        self.fcheck(k, v)
        t = (((v << 8) | self.F[k]) + inc) & 0xFFFFFF
        g.ww(addr, t >> 8)
        self.F[k], self.SH[k] = t & 0xFF, t >> 8

    def acc8(self, g, addr, k, inc):
        v = g.mem[addr]
        self.fcheck(k, v)
        t = (((v << 8) | self.F[k]) + inc) & 0xFFFF
        g.wb(addr, t >> 8)
        self.F[k], self.SH[k] = t & 0xFF, t >> 8

    def h_pos(self, g, whole=False):
        if self.s == 0:
            return
        self.stats['bounce' if whole else 'pos'] += 1
        for p, v, k in ((0xA988, 0xA99C, 'PX'), (0xA98A, 0xA99E, 'PY'), (0xA98C, 0xA9A0, 'PZ')):
            self.acc16w(g, p, k, (_s16(g.rw(v)) << 8) >> (0 if whole else self.s))
        g.ret()

    def h_bounce(self, g):
        self.h_pos(g, whole=True)               # s = 0: JP A834 runs (the original)

    def h_ang(self, g):
        if self.s == 0:
            return
        m, sp = g.mem, g.R[SP]
        relax = (m[sp] | m[(sp + 1) & 0xFFFF] << 8) == 0xA7BD
        self.stats['relax' if relax else 'ang'] += 1
        for a, rate, tgt, k in ((0xA98F, 0xA9A2, 0x960D, 'A0'), (0xA991, 0xA9A4, 0x960E, 'A2')):
            if relax:
                self.fcheck(k, m[a])
                gap = max(-32768, min(32767, _s8(m[tgt] - m[a]) * 256 + 0x80 - self.F[k]))
                inc = (gap * self.C + 128) >> 8
            else:
                inc = (_s8(m[rate]) << 8) >> self.s
            self.acc8(g, a, k, inc)
        hd = m[0xA990] << 8 | m[0xA9A5]
        self.fcheck('HD', hd)
        t = (((hd << 8) | self.F['HD']) + ((_s16(m[0xA9A3] << 8 | m[0xA9A6]) << 8) >> self.s)) & 0xFFFFFF
        m[0xA990], m[0xA9A5] = t >> 16, (t >> 8) & 0xFF
        self.F['HD'], self.SH['HD'] = t & 0xFF, t >> 8
        g.ret()

    def h_vpre(self, g):
        if not self.plain:
            self.V0 = [g.rw(a) for a in (0xA99C, 0xA99E, 0xA9A0)]

    def h_vpost(self, g):
        if self.s == 0 or g.mem[0x965D] != 1:
            return
        self.stats['skid'] += 1
        for a, v0, k in zip((0xA99C, 0xA99E, 0xA9A0), self.V0, ('VX', 'VY', 'VZ')):
            d = _s16(g.rw(a) - v0)
            g.ww(a, v0)
            self.acc16w(g, a, k, (d << 8) >> self.s)
        g.call(0xA88B, 0xA796)

    def h_vr(self, g):
        if not self.plain:
            self.VR = [g.rw(a) for a in (0xA99C, 0xA99E, 0xA9A0)]
            self.VRF = True

    def h_speed(self, g):
        if self.plain:
            return
        if self.s == 0 or g.mem[0x965D] != 0:
            self.VRF = False
            return
        vrf, self.VRF = self.VRF, False
        if not (vrf and self.V0[0] == self.VR[0] and self.V0[2] == self.VR[2]):
            self.stats['speed_whole'] += 1
            self.F['SP'], self.SH['SP'] = 0x80, None
            return
        self.stats['speed'] += 1
        R = g.R
        old = g.rw(0x965B)                      # not written here: F568 erases the needle drawn for the old value
        self.fcheck('SP', old)
        t = (((old << 8) | self.F['SP']) + ((_s16((R[6] << 8 | R[7]) - old) << 8) >> self.s)) & 0xFFFFFF
        self.F['SP'], self.SH['SP'] = t & 0xFF, t >> 8
        R[6], R[7] = t >> 16, (t >> 8) & 0xFF
        g.call(0xF568, 0xA8BE)

    def h_steer(self, g, step):
        if self.s == 0:
            return
        self.stats['steer'] += 1
        v = g.mem[0x96AC]
        self.fcheck('ST', v)
        t = max(-120 * 256 + 0x80, min(120 * 256 + 0x80, _s8(v) * 256 + self.F['ST'] + ((step << 8) >> self.s)))
        g.wb(0x96AC, (t >> 8) & 0xFF)
        self.F['ST'], self.SH['ST'] = t & 0xFF, (t >> 8) & 0xFF
        g.ret()

    def h_guard(self, g):
        if g.mem[0x910A] >= 0x12:
            self.stats['guard_drop'] += 1
            g.ret()

    def h_fill(self, g):
        m = g.mem
        if any(m[0x9E01 + 2 * i] >= 0x80 for i in range(m[0x910A] // 2)):
            self.stats['fill_skip'] += 1
            g.ret()

    def h_shift(self, g):
        R = g.R
        b = R[2] & 0x7F
        if b == 0 or b > 6:
            self.stats['shift_clamp'] += 1
            b = 1 if b == 0 else 6
        R[2], R[0] = b, 7
        R[PC] += 4

    def set_n(self, g, N):
        self.N, self.s, self.C = N, {1: 0, 2: 1, 4: 2}[N], C_RELAX[N]
        step = 500 >> self.s
        g.ww(0xA6A4, step)
        g.ww(0xA6B7, step)
        g.ww(0xA6A8, 7500 + step)

    def set_gates(self, g, i):
        self.I = i
        for a, (op, cl, when) in STEP_GATES.items():
            g.wb(a, op if (i == 0 if when == 'first' else i == self.N - 1) else cl)

    def restore(self, g):
        for a, (op, cl, when) in STEP_GATES.items():
            g.wb(a, op)
        for a, v in THROTTLE.items():
            g.ww(a, v)


def timeout_predicted(m):
    return m[0x950B] == 4 and m[0x91DC] == 0 and m[0x950C] == 0 and m[0x950D] == 0


def whole_update(g, spec, N, cont=0x38D0):
    """One original update as the build runs it, from the loop's CALL (PC 0x9E34, the loop's return address on the
    stack): N sub-steps (gates per sub-step, (S) = cont, JP 0x9E34), every data patch back, RET to the loop, the
    loop code once to its next CALL. -> ('ok', N) at the next entry, or ('escape', where)."""
    R, m = g.R, g.mem
    assert R[PC] == LOOP and m.o7ffd & 7 == 0, (hex(R[PC]), m.o7ffd)
    sp = R[SP]
    ret = m[sp] | m[sp + 1] << 8
    spec.plain = timeout_predicted(m)
    if spec.plain:                              # the original update itself (the loop's return address stays)
        spec.stats['timeout_n1'] += 1
        spec.set_n(g, 1)
        spec.set_gates(g, 0)
        g.ports.reset()
        pc = g.run_to({ret, ESC, TOUT})
        spec.restore(g)
        if pc != ret:
            return 'escape', pc
    else:
        R[SP] = (sp + 2) & 0xFFFF
        spec.set_n(g, N)
        for i in range(N):
            spec.set_gates(g, i)
            g.ports.reset()
            g.call(LOOP, cont)
            pc = g.run_to({cont, ESC, TOUT})
            if pc != cont:
                spec.restore(g)
                return 'escape', pc
        spec.restore(g)
        g.call(ret, ret)                        # PUSH ret; RET: the slot below SP holds ret as in the original
        g.ret()
    pc = g.run_to(set(CALL_SITES) | {ESC})
    if pc == ESC:
        return 'escape', pc
    g.call(LOOP, pc + 3)                        # the loop's CALL: the next update starts
    return 'ok', N


def warm_game(prev, cur, spec):
    """The game at update `cur` with Spec installed and its hook history (VR / VRF): update `prev` run at N = 1 first
    (= the original byte for byte); without prev (or when it escapes) the hook state at boot."""
    if prev is not None and not prev['esc']:
        g = _Game(prev)
        spec.install(g)
        try:
            res = whole_update(g, spec, 1)
        except (RuntimeError, AssertionError):
            res = ('escape', None)
        if res[0] == 'ok':
            g.set_ports(cur['ports'])
            spec.stats.clear()
            return g
        spec.__init__()
    g = _Game(cur)
    spec.install(g)
    return g


# ------------------------------------------------------------------------------------- steps: the host model
class NextSteps(Next):
    """Route 1's host model (MMU, alt ROM, NextRegs) for the steps build from a captured 128K state: every game bank
    as pages 2b / 2b + 1, slot 6-7 = the 7FFD bank; the 28 MHz clock in float T (a 3.5 MHz instruction 8 x its T, a
    28 MHz one f28 x), the video line (clock / 1824 + line0) mod 311 on NR 0x1E / 0x1F; a write to 7FFD also maps
    the ROM in slots 0-1 (the Next; JNext); other port reads = the recorded update's (_Ports). No interrupts (play
    runs with them off)."""

    def __init__(self, st, patch, f28=STEPS_F28, line0=0):
        from . import simpool
        self.S = S = patch.S
        rom = bytearray(zt.rom48())
        rom[S['SH']:S['SH'] + len(patch.rom_code)] = patch.rom_code
        self.rom = bytes(rom)
        bk = [bytearray(st['banks'][i * 16384:(i + 1) * 16384]) for i in range(8)]
        for a, old, new in patch.sites:
            b, o = _where(a)
            assert bytes(bk[b][o:o + len(old)]) == old, 'site %04X' % a
            bk[b][o:o + len(new)] = new
        self.pages = {36: list(patch.code_page), 37: [0] * 8192}
        for b in range(8):
            self.pages[2 * b], self.pages[2 * b + 1] = list(bk[b][:8192]), list(bk[b][8192:])
        bank = st['o7ffd'] & 7
        self.slots = [0xFF, 0xFF, 10, 11, 4, 5, 2 * bank, 2 * bank + 1]
        mem = list(self.rom[:0x4000])
        for s in range(2, 8):
            mem += self.pages[self.slots[s]]
            self.pages[self.slots[s]] = None
        self.sim = simpool.machine(_sim_class(), mem, list(st['regs']), slot='steps_model', copy=True)
        self.mem = self.sim.memory
        self.nr = {7: 0}
        self.sel = 0
        self.sim.int_active = 0
        z80n.install(self.sim, nextreg=self.nextreg)
        self.sim.set_tracer(self)
        self.R = self.sim.registers
        self.clock = 0.0
        self.f28, self.line0 = f28, line0
        self.bad = []
        self.ports = _Ports(st['ports'])

    def line(self):
        return int(self.clock / LINE_T + self.line0) % NL

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
        if port == 0x243B:
            return self.sel
        return self.ports.read_port(regs, port)

    def write_port(self, regs, port, value, *x):
        if port == 0x243B:
            self.sel = value
        elif port == 0x253B:
            self.nextreg(self.sel, value)
        elif port & 0x8002 == 0:                # 7FFD: the bank at C000; on the Next MMU slots 0-1 back to ROM
            self.map(6, 2 * (value & 7))
            self.map(7, 2 * (value & 7) + 1)
            self.map(0, 0xFF)
            self.map(1, 0xFF)

    def pb(self, a):
        return self.page(36)[a - 0x2000]

    def w16(self, a):
        p = self.page(36)
        return p[a - 0x2000] | p[a - 0x1FFF] << 8

    def setpb(self, a, v):
        if 36 in self.slots:
            self.mem[self.slots.index(36) * 8192 + a - 0x2000] = v & 255
        else:
            self.pages[36][a - 0x2000] = v & 255

    def banks(self):
        return [bytes(self.page(2 * b) + self.page(2 * b + 1)) for b in range(8)]

    def run(self, stops, max_ins=200_000_000, watch=None, first=True):
        R, m, ops, nr, f28 = self.R, self.mem, self.sim.opcodes, self.nr, self.f28
        n, skip = 0, first
        while True:
            pc = R[PC]
            if not skip and pc in stops:
                return pc
            skip = False
            if watch and pc in watch:
                watch[pc](self)
            if R[IFF]:
                self.bad.append('interrupts on at %04X' % pc)
                raise RuntimeError('interrupts on at %04X' % pc)
            t0 = R[T]
            ops[m[pc]]()
            self.clock += (R[T] - t0) * (f28 if nr[7] & 3 else 8)
            n += 1
            if n > max_ins:
                raise RuntimeError('instruction limit at %04X' % R[PC])


# ------------------------------------------------------------------------------------- steps: one case
_REC = {k: 'fr_' + k.lower() for k in FRACS}
REGS_STEPS = [i for i in range(24) if i not in (13, 15)]       # all registers but R (PC: compared on its own)


def put_state(n, sp):
    """Spec's hook state -> the hook page"""
    S = n.S
    for k in FRACS:
        a, sh = S[_REC[k]], sp.SH[k]
        for i, v in enumerate((sp.F[k], (sh or 0) & 255, (sh or 0) >> 8 & 255, 0 if sh is None else 1)):
            n.setpb(a + i, v)
    for name, vals in (('v0', sp.V0), ('vr', sp.VR or [0, 0, 0])):
        for i, v in enumerate(vals):
            n.setpb(S[name] + 2 * i, v & 255)
            n.setpb(S[name] + 2 * i + 1, v >> 8 & 255)
    n.setpb(S['vrf'], int(sp.VRF))


def cmp_state(n, sp):
    """the hook page vs Spec's hook state -> differences"""
    S, out = n.S, []
    for k in FRACS:
        a = S[_REC[k]]
        f, lo, hi, v = (n.pb(a + i) for i in range(4))
        sh = sp.SH[k]
        if f != sp.F[k]:
            out.append('F_%s %02X/%02X' % (k, f, sp.F[k]))
        if (sh is None) != (v == 0):
            out.append('SH_%s valid %d/%s' % (k, v, sh))
        elif sh is not None and (lo | (hi << 8 if k in W16 else 0)) != sh:
            out.append('SH_%s %04X/%04X' % (k, lo | (hi << 8 if k in W16 else 0), sh))
    if [n.w16(S['v0'] + 2 * i) for i in range(3)] != [x & 0xFFFF for x in sp.V0]:
        out.append('V0')
    if sp.VR is not None and [n.w16(S['vr'] + 2 * i) for i in range(3)] != [x & 0xFFFF for x in sp.VR]:
        out.append('VR')
    if n.pb(S['vrf']) != int(sp.VRF):
        out.append('VRF %d/%d' % (n.pb(S['vrf']), sp.VRF))
    return out


def _mem_diff(n, g, patch):
    """all 128K: the build's banks vs Spec's; a site byte may hold the site's new byte where Spec has the original"""
    exp = {}
    for a, old, new in patch.sites:
        for i in range(len(old)):
            b, o = _where(a + i)
            exp[(b, o)] = (old[i], new[i])
    a, b = n.banks(), g.state()
    out = []
    for bk in range(8):
        if a[bk] != b[bk]:
            for o in range(16384):
                if a[bk][o] != b[bk][o] and exp.get((bk, o)) != (b[bk][o], a[bk][o]):
                    out.append('%d:%04X %02X/%02X' % (bk, o, a[bk][o], b[bk][o]))
    return out


class _PaceRec:
    """the model's pace records: per update the entry clock, the views (lclk at the copy vs its target), the exit"""
    def __init__(self, S):
        self.S, self.ups, self.cur = S, [], None

    def watch(self):
        return {self.S['T_DRV']: self.entry, 0xDC37: self.view, self.S['T_DEXIT']: self.exit}

    def entry(self, n):
        self.cur = {'E': n.clock, 'views': []}

    def view(self, n):
        if self.cur is not None and n.pb(self.S['in_drv']):
            self.cur['views'].append((n.w16(self.S['lclk']) - n.w16(self.S['tgt']) + 32768) % 65536 - 32768)

    def exit(self, n):
        S, c = self.S, self.cur
        if c is None or not n.pb(S['x_live']) or n.w16(S['t_exit']) != n.w16(S['lclk']) or n.pb(S['in_drv']):
            return                              # T_DEXIT is also the guards' way back outside the driver
        c.update(X=n.clock, N=n.pb(S['hs_n']), c_sub=n.w16(S['c_sub']), n_cur=n.pb(S['n_cur']))
        self.ups.append(c)
        self.cur = None


def _z80_update(n, rec=None):
    """the build from CALL t_drv's target to the next (or an escape: 9E12, A3F2) -> ('ok' | 'escape', pc)"""
    S = n.S
    w = rec.watch() if rec else {}

    def spd(x):
        if x.nr[7] != x.pb(S['g_spd']):
            x.bad.append('NR7 %d at %04X' % (x.nr[7], x.R[PC]))
    w[LOOP] = lambda x: x.ports.reset()
    w[0x9E57] = w[0x9E6E] = spd
    pc = n.run({S['T_DRV'], ESC, TOUT}, watch=w)
    return ('ok', pc) if pc == S['T_DRV'] else ('escape', pc)


def _esc_check(n):
    """after an escape: the page unmapped, in_drv clear, the incoming speed; at 9E12 checked after its hook (F487),
    x_live clear there"""
    bad, S = [], n.S

    def chk(where):
        if n.slots[1] != 0xFF:
            bad.append('%s: slot 1 = page %d' % (where, n.slots[1]))
        if n.pb(S['in_drv']):
            bad.append('%s: in_drv set' % where)
        if n.nr[7] != 0:
            bad.append('%s: NR7 %d' % (where, n.nr[7]))
    if n.R[PC] == ESC:
        try:
            n.run({0xF487}, max_ins=2000)
        except RuntimeError as e:
            bad.append('9E12 hook: %s' % e)
        chk('F487')
        if n.pb(S['x_live']):
            bad.append('x_live set after 9E12')
    else:
        chk('stop %04X' % n.R[PC])
    return bad


def _compare(n, g, sp, rz, rs, patch):
    """the build (model n) vs Spec (game g, hook state sp) after an update or an escape: all 128K (site bytes as
    built), registers but R, PC (the build at t_drv = Spec at 0x9E34), the hook state; after the driver: NR 7 back,
    slot 1 = ROM, in_drv clear; after an escape: _esc_check"""
    if rz[0] != rs[0] or (rz[0] == 'escape' and rz[1] != rs[1]):
        return ['result %s / Spec %s' % (rz, rs)]
    bad = []
    dr = ['%s %X/%X' % (NAMES[i], n.R[i], g.R[i]) for i in REGS_STEPS if n.R[i] != g.R[i]]
    if dr:
        bad.append('regs ' + ' '.join(dr))
    if rz[0] == 'ok':
        if g.R[PC] != LOOP:
            bad.append('Spec PC %04X' % g.R[PC])
        if n.nr[7] != 0:
            bad.append('NR7 %d after the driver' % n.nr[7])
        if n.slots[1] != 0xFF:
            bad.append('slot 1 = page %d after the driver' % n.slots[1])
        if n.pb(n.S['in_drv']):
            bad.append('in_drv set after the driver')
    else:
        if n.R[PC] != g.R[PC]:
            bad.append('PC %04X / Spec %04X' % (n.R[PC], g.R[PC]))
        bad += _esc_check(n)                    # at 9E12 this runs the hook (CALL F487): its return address aside
        if n.R[PC] == 0xF487:
            for a in (n.R[SP], (n.R[SP] + 1) & 0xFFFF):
                n.mem[a] = g.mem[a]
    d = _mem_diff(n, g, patch)
    if d:
        bad.append('RAM %d bytes: %s' % (len(d), ' '.join(d[:10])))
    hs = cmp_state(n, sp)
    if hs:
        bad.append('hook state: ' + ' '.join(hs[:8]))
    if n.bad:
        bad.append('model: %s' % n.bad[:3])
    return bad


def rule(c, cur):
    """the adaptive N from the last update's busy lines a sub-step c and the current N (the .asm's drv)"""
    if cur == 4:
        return 4 if c <= C4ST else 2 if c <= C2ST else 1
    if c <= C4UP:
        return 4
    return 2 if c <= (C2ST if cur == 2 else C2UP) else 1


MODS = {                                        # synthetic states (cases the recording does not reach)
    'skid': lambda m: [(0x965D, 1)],                                    # skid mode in a road state
    'skidv': lambda m: [(0x965D, 1), (0xA99C, 0x00), (0xA99D, 0x04), (0xA9A0, 0x00), (0xA9A1, 0xFC)],  # + velocity
    'steerp': lambda m: [(0x96AC, 0x76)], 'steerm': lambda m: [(0x96AC, 0x8A)],     # steering past the clamps
    'steerpl': lambda m: [(0x96AC, 0x5C)], 'steerml': lambda m: [(0x96AC, 0xA4)],   # ... at the last sub-step
    'tilt': lambda m: [(0xA98F, (m[0xA98F] + 0x20) & 255), (0xA991, (m[0xA991] - 0x20) & 255)],   # relaxation gap
    'hdcarry': lambda m: [(0xA9A5, 0xFF)], 'hdborrow': lambda m: [(0xA9A5, 0x00)],  # heading low byte at the edge
    'bounce': lambda m: [(a, 0) for a in range(*BOUNCE_NOP)],         # the push-out at the first object
    'timeout': lambda m: [(0x950B, 4), (0x950C, 0), (0x950D, 0), (0x91DC, 0)]}     # the time-out update


def _apply_mod(g, mod):
    if isinstance(mod, tuple):                  # TRAINERS names: their bytes in the game's own banks, both sides
        for name in mod:
            for a, _old, v in TRAINERS[name]:
                b, o = _where(a)
                g.mem.banks[b][o] = v
        return
    for a, v in MODS[mod](g.mem) if mod in MODS else []:
        g.mem[a] = v


_PATCHES = {}


def _steps_patch(edits):
    key = tuple(sorted((k, bytes(v)) for k, v in (edits or {}).items()))
    if key not in _PATCHES:
        _PATCHES[key] = StepsPatch(dict(key), 'steps' if not key else 'neg')
    return _PATCHES[key]


def _model(g, sp, patch, nforce=0, preset=None, line0=0, f28=STEPS_F28):
    n = NextSteps({'banks': b''.join(g.state()), 'o7ffd': g.mem.o7ffd, 'regs': list(g.R), 'ports': []}, patch,
                  f28=f28, line0=line0)
    n.ports = g.ports.__class__([], None)
    n.ports.seq = g.ports.seq
    n.R[PC] = n.S['T_DRV']
    put_state(n, sp)
    n.setpb(n.S['n_force'], nforce)
    if preset:
        n.setpb(n.S['c_sub'], preset[0] & 255)
        n.setpb(n.S['c_sub'] + 1, preset[0] >> 8)
        n.setpb(n.S['n_cur'], preset[1])
    return n


def steps_case(job):
    """One recorded update (or a synthetic one): Spec's warm state is the start of both; the build runs the update
    in the model (its N: n_force, or the adaptive rule from a preset (c_sub, n_cur)), then Spec with that N. job:
    prev, cur (captured update entries: banks, o7ffd, regs, ports, esc), nxt (the next entry: N = 1 is compared
    with the recording too), n (1 / 2 / 4, or 0 = adaptive with preset), mod, edits (a negative control's page
    edits), line0. -> {'bad': [...], 'res', 'N', 'stats'}"""
    patch = _steps_patch(job.get('edits'))
    sp = Spec()
    g = warm_game(None if job.get('mod') == 'cold' else job.get('prev'), job['cur'], sp)
    if job.get('mod'):
        _apply_mod(g, job['mod'])
    nf, pre = job.get('n', 0), job.get('preset')
    n = _model(g, sp, patch, nforce=nf, preset=pre, line0=job.get('line0', 0))
    try:
        rz = _z80_update(n)
    except RuntimeError as e:
        rz = ('error', str(e))
    nused = n.pb(n.S['hs_n'])
    try:
        rs = whole_update(g, sp, nused if nused in (1, 2, 4) else 1, cont=n.S['T_CONT'])
    except (RuntimeError, AssertionError) as e:
        rs = ('error', repr(e))
    bad = _compare(n, g, sp, rz, rs, patch) if rz[0] != 'error' else ['model: %s' % rz[1]]
    if rs[0] == 'ok' and not sp.stats.get('timeout_n1'):
        want = nf or rule(*pre)
        if nused != want:
            bad.append('N %d / expected %d' % (nused, want))
    if rs[0] == 'ok' and nf == 1 and job.get('nxt') is not None and not job.get('mod'):
        want = job['nxt']
        st = g.state()
        d = sum(1 for b in range(8) for o in range(16384)
                if st[b][o] != want['banks'][b * 16384 + o]) if b''.join(st) != want['banks'] else 0
        dr = [NAMES[i] for i in REGS_STEPS + [PC] if g.R[i] != want['regs'][i]]
        if d or dr:
            bad.append('Spec N = 1 vs the recording: %d bytes, regs %s' % (d, dr))
    return {'bad': bad, 'res': rs, 'N': nused, 'stats': dict(sp.stats), 'skip': n.w16(n.S['n_skip']),
            'drop': n.w16(n.S['n_drop']), 'clamp': n.pb(n.S['n_clamp'])}


def steps_run(job):
    """K consecutive updates from a captured start, both sides on their own (the same recorded inputs; the build's
    pace state evolves: the real schedule), compared after each. job: prev, cur, ports (one list per update), n (0 =
    adaptive from boot values), edits, mod. -> {'rows': [...], 'pace': {...}}"""
    patch = _steps_patch(job.get('edits'))
    sp = Spec()
    g = warm_game(job.get('prev'), job['cur'], sp)
    if job.get('mod'):
        _apply_mod(g, job['mod'])
    nf = job.get('n', 0)
    n = _model(g, sp, patch, nforce=nf, line0=job.get('line0', 0))
    rec = _PaceRec(n.S)
    rows, last = [], None
    for k, ports in enumerate(job['ports']):
        g.set_ports(ports)
        n.ports.seq = g.ports.seq
        nrec = len(rec.ups)
        try:
            rz = _z80_update(n, rec)
        except RuntimeError as e:
            rz = ('error', str(e))
        nused = n.pb(n.S['hs_n'])
        try:
            rs = whole_update(g, sp, nused if nused in (1, 2, 4) else 1, cont=n.S['T_CONT'])
        except (RuntimeError, AssertionError) as e:
            rs = ('error', repr(e))
        bad = _compare(n, g, sp, rz, rs, patch) if rz[0] != 'error' else ['model: %s' % rz[1]]
        cur = rec.ups[-1] if len(rec.ups) == nrec + 1 else None
        if rs[0] == 'ok' and not sp.stats.get('timeout_n1'):
            want = nf or (rule(last['c_sub'], last['n_cur']) if last else rule(1000, 2))
            if nused != want:
                bad.append('N %d / rule %d' % (nused, want))
        last = cur or last
        rows.append({'k': k, 'bad': bad, 'res': rs, 'N': nused, 'stats': dict(sp.stats)})
        sp.stats.clear()
        if bad or rs[0] != 'ok':
            break
    U = rec.ups
    dur = [(b['E'] - a['E']) / (NL * LINE_T) for a, b in zip(U, U[1:])]
    return {'rows': rows, 'pace': {'dur': dur, 'early': sum(1 for x in U for v in x['views'] if v < 0),
                                   'views': sum(len(x['views']) for x in U), 'N': [x['N'] for x in U]}}


def hook_case(job):
    """A render guard alone, from a captured state with crafted inputs: the build's trampoline + hook (in or out of
    the driver: in_drv, the page mapped as there) vs Spec's hook + the original instructions, to the first game
    address after the replaced ones. job: cur, site (CEB9 / C7C0 / A0E7 / D758), pokes {addr: byte}, regs {index:
    value}, in_drv, edits -> {'bad': [...]}"""
    patch = _steps_patch(job.get('edits'))
    site, ret = job['site'], 0x6B80             # a return address inside the unused tail area
    stops = {0xCEB9: {0xCEBC, ret}, 0xC7C0: {0xC7C4, ret}, 0xA0E7: {0xA0EB}, 0xD758: {0xD75C}}[site]
    sp = Spec()
    g = _Game(job['cur'])
    sp.install(g)
    for a, v in job.get('pokes', {}).items():
        g.mem[a] = v
    for i, v in job.get('regs', {}).items():
        g.R[i] = v
    g.call(site, ret)
    n = _model(g, sp, patch)
    n.R[PC] = site
    if job.get('in_drv'):
        n.setpb(n.S['in_drv'], 1)
        n.nextreg(0x51, 36)
    try:
        n.run(stops, max_ins=100_000)
        pz = n.R[PC]
    except RuntimeError as e:
        return {'bad': ['model: %s' % e]}
    g.run_to(stops)
    bad = []
    if pz != g.R[PC]:
        bad.append('PC %04X / Spec %04X' % (pz, g.R[PC]))
    dr = ['%s %X/%X' % (NAMES[i], n.R[i], g.R[i]) for i in REGS_STEPS if n.R[i] != g.R[i]]
    if dr:
        bad.append('regs ' + ' '.join(dr))
    d = _mem_diff(n, g, patch)
    if d:
        bad.append('RAM %s' % d[:6])
    if n.slots[1] != (36 if job.get('in_drv') else 0xFF):
        bad.append('slot 1 = %d' % n.slots[1])
    return {'bad': bad}


def _pool_map(fn, jobs, workers):
    if workers <= 1 or len(jobs) <= 1:
        return [fn(j) for j in jobs]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as ex:
        return list(ex.map(fn, jobs, chunksize=1))


def _workers():
    return int(os.environ.get('NEXCLASH_WORKERS', 0)) or min(16, os.cpu_count() or 1)


# ------------------------------------------------------------------------------------- steps: the verify
_IN_RC = {0x40: 2, 0x48: 3, 0x50: 4, 0x58: 5, 0x60: 6, 0x68: 7, 0x78: 0}   # IN r,(C): the register it loads
RUN_STARTS = (10, 40, 150, 300, 640, 1040, 1200, 1500)         # K-update runs (unit tests): spread over the RZX
RUN_K = 20


def capture_updates(rzx_path, on_update, stop=None):
    """Play the recording; at every update-loop entry 0x9E34 the 128K state (banks, 7FFD, registers); per update its
    port reads [(port, value)] in order and whether it reached 0x9E12. on_update(prev, cur, nxt) once cur's reads
    are complete (at the next entry). -> (updates, frames)"""
    from . import simrun
    sim, ups, pend = [None], [], [None]

    class H:
        def on_sim(s, x):
            sim[0] = x

        def before(s, pc):
            x = sim[0]
            m, R = x.memory, x.registers
            if pc == LOOP:
                ups.append({'u': len(ups), 'banks': b''.join(bytes(b) for b in m.banks), 'o7ffd': m.o7ffd,
                            'regs': list(R), 'ports': [], 'esc': False})
                if len(ups) >= 2:
                    on_update(ups[-3] if len(ups) >= 3 else None, ups[-2], ups[-1])
                if len(ups) > 3:
                    ups[-4] = None                  # only the last three are kept
            if not ups:
                return
            if pc == ESC:
                ups[-1]['esc'] = True
            op = m[pc]
            if op == 0xDB:
                pend[0] = ((R[0] << 8) | m[(pc + 1) & 0xFFFF], 0)
            elif op == 0xED and m[(pc + 1) & 0xFFFF] in _IN_RC:
                pend[0] = ((R[2] << 8) | R[3], _IN_RC[m[(pc + 1) & 0xFFFF]])

        def after(s, pc, dt):
            if pend[0] is not None:
                port, r = pend[0]
                ups[-1]['ports'].append((port, sim[0].registers[r]))
                pend[0] = None
    frames = simrun.play_rzx(str(rzx_path), H(), stop=stop)
    return len(ups), frames


def verify_steps(patch, rzx_path, stop=None, collect=0, progress=None, workers=None, fixed=(1, 2, 4), trainers=()):
    """Differential test of the steps build over a recording (module section "route 2a"): at every update-loop entry
    the build's update (the hooked sub-steps, the model's line clock) and Spec's from the same warm state, compared
    byte for byte (steps_case): adaptive N (the rule's input preset per update: every branch) on every update, fixed
    N = `fixed` on every update too; N = 1 also against the recording's next entry. -> (Counter, failures, kept);
    kept = states for unit_tests_steps (spread, by hook event, K-update runs). trainers: TRAINERS names whose bytes go
    into every case's game banks, the build's and Spec's alike (a trainer-on check; N = 1 is then not compared with
    the recording, which ran without them)."""
    import concurrent.futures as cf
    workers = workers or _workers()
    c = collections.Counter()
    fails, per = [], collections.Counter()
    kept = {'spread': [], 'stat': collections.defaultdict(list), 'runs': []}
    runs = {}
    pending = {}
    seen = collections.Counter()
    ex = cf.ProcessPoolExecutor(max_workers=workers) if workers > 1 else None

    def done(f):
        u, kind, pair = pending.pop(f)
        r = f.result()
        c['cases'] += 1
        c['case %s' % kind] += 1
        if r['res'][0] != 'ok':
            c['escapes (%s)' % kind] += 1
        else:
            c['N used %d' % r['N']] += 1
        for k in ('skip', 'drop', 'clamp'):
            c['guard %s' % k] += r[k]
        if r['bad']:
            key = '%s!' % kind
            c[key] += 1
            if per[key] < 5:
                fails.append((key, u, '; '.join(r['bad'])[:400]))
            per[key] += 1
        if kind == 'N=4' and collect:
            for k in ('relax', 'ang', 'speed', 'speed_whole', 'steer', 'guard_drop', 'timeout_n1', 'fill_skip',
                      'shift_clamp'):
                if r['stats'].get(k):
                    seen[k] += 1                # up to 6 a hook event, 20 occurrences apart
                    if seen[k] % 20 == 1 and len(kept['stat'][k]) < 6:
                        kept['stat'][k].append(pair)

    def submit(job, u, kind, pair):
        if ex is None:
            f = cf.Future()
            f.set_result(steps_case(job))
            pending[f] = (u, kind, pair)
            done(f)
            return
        while len(pending) >= 3 * workers:
            fin, _ = cf.wait(list(pending), return_when=cf.FIRST_COMPLETED)
            for f in fin:
                done(f)
        f = ex.submit(steps_case, job)
        pending[f] = (u, kind, pair)

    def on_update(prev, cur, nxt):
        u = cur['u']
        c['updates'] += 1
        lite = lambda e: None if e is None else {k: e[k] for k in ('banks', 'o7ffd', 'regs', 'ports', 'esc')}
        p, q = lite(prev), lite(cur)
        pair = (p, q)
        base = {'prev': p, 'cur': q, 'line0': (u * 37) % NL}
        if trainers:
            base['mod'] = tuple(trainers)
        submit(dict(base, n=0, preset=PRESETS[u % len(PRESETS)]), u, 'adaptive', pair)
        for N in fixed:
            submit(dict(base, n=N, nxt={'banks': nxt['banks'], 'regs': nxt['regs']}), u, 'N=%d' % N, pair)
        if collect and u % 25 == 5 and len(kept['spread']) < collect:
            kept['spread'].append(pair)
        if u in RUN_STARTS:
            runs[u] = {'prev': p, 'cur': q, 'ports': [], 'line0': (u * 37) % NL}
        for r in runs.values():
            if len(r['ports']) < RUN_K:
                r['ports'].append(cur['ports'])
        if progress and u % 200 == 199:
            progress('verify    : steps u%d, %d cases done, %d fail' % (u, c['cases'], sum(
                v for k, v in c.items() if k.endswith('!'))))
    try:
        n, frames = capture_updates(rzx_path, on_update, stop=stop)
        for f in list(pending):
            done(f)
    finally:
        if ex is not None:
            ex.shutdown()
    kept['runs'] = [r for u0, r in sorted(runs.items()) if len(r['ports']) >= 4]
    c['frames'] = frames
    if not c['updates']:
        c['no update reached!'] += 1
    return c, fails, kept


# ------------------------------------------------------------------------------------- steps: unit tests
def _neg(S, label, data, off=0):
    return {S[label] - 0x2000 + off: bytes(data)}


def steps_negatives():
    """Broken builds (page-byte patches at labels: asm/hard_drivin_steps.asm) the unit tests must catch, with the
    case kind that reaches each: (name, page edits, kind). The prototype's mutants (games/hard_drivin.md "Build 2a
    stage 3"); its 13 / 14 are equivalent and not kept."""
    S = steps_syms()
    w = lambda v: [v & 255, v >> 8]
    return [
        ('h_pos: z axis not moved', _neg(S, 'h_pos.mz', [0] * 17), 'single'),
        ('relaxation constant + 1', _neg(S, 'c_tab', [0, 76, 42]), 'relax'),
        ('heading carry lost', _neg(S, 'h_ang.hc', [0x86]), 'ang'),
        ('h_vpre: V0 z not saved', _neg(S, 'h_vpre.z', [0] * 6), 'single'),
        ('h_vpost: velocity not reset to V0', _neg(S, 'vax.st', [0] * 3), 'skid'),
        ('h_vr: VRF not set', _neg(S, 'h_vr.f', [0] * 5), 'speed'),
        ('h_speed: VRF / VR condition ignored',
         _neg(S, 'h_speed.vc', [0x18, (S['h_speed.scl'] - S['h_speed.vc'] - 2) & 255, 0]), 'speed_whole'),
        ('steering clamps + 1/256', {**_neg(S, 'h_steer.hi1', [0x82], 1), **_neg(S, 'h_steer.hi2', [0x81], 1),
                                     **_neg(S, 'h_steer.lo', [0x81], 1)}, 'steer'),
        ('clip-vertex guard threshold 13h', _neg(S, 'h_guard.th', [0x13], 1), 'guard'),
        ('traffic gate missing', _neg(S, 'g_last', w(0xA3B4)), 'single'),
        ('throttle words not restored', _neg(S, 'restore.tw', [0] * 15), 'single'),
        ('time-out predictor off', _neg(S, 'drv.tp', [0xC3] + w(S['drv.nt'])), 'timeout'),
        ('A991 relaxes toward 960D', _neg(S, 'h_ang.t2', [0x0D], 1), 'relax'),
        ('mkinc: one shift only', _neg(S, 'mkinc.dj', [0, 0]), 'single'),
        ('fill guard never skips', _neg(S, 'h_fill.t', [0, 0, 0]), 'fill'),
        ('shift guard: no clamp', _neg(S, 'h_shift.cl', [0x18, (S['h_shift.ok'] - S['h_shift.cl'] - 2) & 255]),
         'shift'),
        ('push-out scaled 1 / N', _neg(S, 'h_bounce.z', w(S['mkinc']), 1), 'bounce'),
        ('no pace wait', _neg(S, 'h_copy.pv', [0, 0, 0]), 'pace'),
        ('page not mapped again after 7FFD', _neg(S, 'h_rmap.j', w(S['T_RMEXIT']), 1), 'single'),
        ('N rule: stay-at-4 threshold 661', _neg(S, 'drv.f4', w(C4ST + 2), 1), 'rule'),
    ]


def _hook_jobs(cur, kind, edits=None):
    """the render guards' edge cases (hook_case), in and out of the driver"""
    jobs = []
    for in_drv in (0, 1):
        base = {'cur': cur, 'in_drv': in_drv, 'edits': edits}
        if kind == 'guard':
            jobs += [dict(base, site=0xCEB9, pokes={0x910A: v}) for v in (0x10, 0x11, 0x12, 0x13, 0x30)]
        elif kind == 'fill':
            for ys in ((0x10, 0x20, 0x30), (0x10, 0x80, 0x30), (0x7F, 0x7F, 0xFF), (0x7F,)):
                pk = {0x910A: 2 * len(ys)}
                for i, y in enumerate(ys):
                    pk[0x9E00 + 2 * i], pk[0x9E01 + 2 * i] = 0x40, y
                jobs.append(dict(base, site=0xC7C0, pokes=pk))
        elif kind == 'shift':
            jobs += [dict(base, site=s, regs={2: b}) for s in (0xA0E7, 0xD758) for b in (0, 1, 6, 7, 0x80, 0x86, 0xFF)]
    return jobs


def _kind_jobs(kind, kept, edits=None):
    """the cases of one kind on the collected states: [(fn, job)]"""
    spread = kept['spread'][:8]
    stat = lambda k: kept['stat'].get(k, [])
    one = lambda pairs, **kw: [(steps_case, dict({'prev': p, 'cur': q, 'n': 4, 'edits': edits}, **kw))
                               for p, q in pairs]
    if kind == 'single':
        return one(spread)
    if kind == 'relax':
        return one(stat('relax') + spread) + one(stat('relax') + spread, mod='tilt')
    if kind == 'ang':
        pairs = stat('ang') + stat('steer') + stat('relax') + spread
        return one(pairs) + one(pairs, mod='hdcarry') + one(pairs, mod='hdborrow')
    if kind == 'speed':
        return one(stat('speed') + spread)
    if kind == 'speed_whole':
        return one(stat('speed_whole') + spread) + one(spread, mod='cold')
    if kind == 'steer':
        pairs = stat('steer') + spread
        return [j for mod in ('steerpl', 'steerml', 'steerp', 'steerm') for j in one(pairs, mod=mod)]
    if kind == 'skid':
        pairs = spread + stat('steer')
        return one(pairs, mod='skid') + one(pairs, mod='skidv')
    if kind == 'bounce':
        return one(spread, mod=kind)
    if kind == 'timeout':
        return one(spread[:3], mod='timeout') + one(stat('timeout_n1'))
    if kind in ('guard', 'fill', 'shift'):
        return [(hook_case, j) for j in _hook_jobs(spread[0][1], kind, edits)] + (one(stat('guard_drop'))
                                                                                if kind == 'guard' else [])
    if kind == 'rule':
        return one(spread[:3], n=0, preset=(661, 4))
    if kind == 'pace':
        r = kept['runs'][0]
        return [(steps_run, dict(r, n=0, edits=edits, ports=r['ports'][:8]))]
    raise ValueError(kind)


def _call(fj):
    fn, job = fj
    return fn(job)


def _run_ok(r, adaptive):
    """a K-update run: no mismatch; adaptive: no view before its target, updates no faster than real time"""
    bad = [x['bad'] for x in r['rows'] if x['bad']]
    pc = r['pace']
    if adaptive and pc['early']:
        bad.append('%d views before their target' % pc['early'])
    d = sorted(pc['dur'])
    if adaptive and len(d) >= 3 and d[len(d) // 2] < 9.9:
        bad.append('update median %.2f frames < 10' % d[len(d) // 2])
    return bad


def unit_tests_steps(patch, kept, neg=None, workers=None):
    """Cases the recording does not reach, on the collected states (verify_steps' kept), + the negative controls
    (steps_negatives: each must fail at least one case of its kind). -> (Counter ('!' = fail), pace summary)"""
    workers = workers or _workers()
    c = collections.Counter()
    if not kept['spread'] or not kept['runs']:
        c['no states!'] += 1
        return c, {}
    tests = []                                  # (name, check, (fn, job))
    for r in kept['runs']:
        for n in (0, 4):
            tests.append(('run of %d updates, %s' % (len(r['ports']), 'adaptive' if n == 0 else 'N=4'),
                          'run0' if n == 0 else 'run', (steps_run, dict(r, n=n))))
    for mod in ('skid', 'skidv', 'steerp', 'steerm', 'steerpl', 'steerml', 'tilt', 'hdcarry', 'hdborrow', 'bounce', 'cold'):
        for p, q in kept['spread'][:6]:
            tests.append(('synthetic %s, N=4' % mod, 'case', (steps_case, {'prev': p, 'cur': q, 'n': 4, 'mod': mod})))
            tests.append(('synthetic %s, adaptive' % mod, 'case', (steps_case, {'prev': p, 'cur': q, 'n': 0,
                                                                                'mod': mod, 'preset': (300, 4)})))
    for p, q in kept['spread'][:3]:
        tests.append(('synthetic time-out (plain update, escape)', 'esc', (steps_case, {'prev': p, 'cur': q, 'n': 4,
                                                                                        'mod': 'timeout'})))
    for kind in ('guard', 'fill', 'shift'):
        for j in _hook_jobs(kept['spread'][0][1], kind):
            tests.append(('%s guard edges' % kind, 'case', (hook_case, j)))
    negs = neg if neg is not None else steps_negatives()
    nj = [(name, fj) for name, edits, kind in negs for fj in _kind_jobs(kind, kept, edits)]
    res = _pool_map(_call, [t[2] for t in tests] + [fj for _, fj in nj], workers)
    pace = {'dur': [], 'early': 0, 'N': collections.Counter()}
    for (name, check, _), r in zip(tests, res[:len(tests)]):
        if check.startswith('run'):
            bad = _run_ok(r, check == 'run0')
            if check == 'run0':
                pace['dur'] += r['pace']['dur']
                pace['early'] += r['pace']['early']
                pace['N'].update(r['pace']['N'])
        else:
            bad = r['bad'] + (['no escape'] if check == 'esc' and r['res'][0] != 'escape' else [])
        c[name + ('!' if bad else '')] += 1
    caught = collections.defaultdict(bool)
    for (name, fj), r in zip(nj, res[len(tests):]):
        bad = _run_ok(r, True) if fj[0] is steps_run else r['bad']
        caught[name] |= bool(bad)
    for name, _, _ in negs:
        c['negative: %s %s' % (name, 'detected' if caught[name] else 'MISSED!')] += 1
    return c, pace


# ------------------------------------------------------------------------------------------------------- auto
DECISIONS = {'route': 'smoother 3D view (user, 2026-11-22); finer time steps (route 2a, user 2026-11-23: default)',
             'tail': '0x6C00'}
BOOT_OK = 'PASS (128K RAM but the tail / NEXLOAD printer buffer, registers/R, hidden ROM)'


def auto(a, z80, name, out, say):
    """plain NAME.nex, route 1 NAME_smooth.nex, route 2a NAME_steps.nex (the default): builds + boot checks; with
    recordings each route's verify, unit tests and negative controls. Result PASSED only if all pass."""
    import time
    for key, value in (('publisher', 'Domark / Binary Design, 1989'), ('fix_label', 'finer time steps')):
        if not getattr(a, key, None):
            setattr(a, key, value)
    ok = True
    out = Path(out)
    plain = out / (name + '.nex')
    build_plain(z80, plain)
    bad = boot_problems(plain, z80)
    ok &= not bad
    say('Plain     : %s %s' % (plain.name, hashlib.md5(plain.read_bytes()).hexdigest()))
    say('Boot      : %s' % (bad[:3] if bad else BOOT_OK))
    builds = {}
    for label, fn in (('smooth', build), ('steps', build_steps)):
        f = out / ('%s_%s.nex' % (name, label))
        builds[label] = fn(z80, f)
        bad = boot_problems(f, z80, builds[label])
        ok &= not bad
        say('%-10s: %s %s' % (label.capitalize(), f.name, hashlib.md5(f.read_bytes()).hexdigest()))
        say('Boot      : %s' % (bad[:3] if bad else BOOT_OK))
    say('Sprites   : none (both routes keep the ULA picture; games/hard_drivin.md "Decision")')
    screen = find_screen(z80)
    if screen is None:
        say('Loading   : none (%s not beside the snapshot)' % LOAD_SCREEN)
    for label in ('smooth', 'steps') if screen else ():
        f = out / ('%s_%s_loading.nex' % (name, label))
        with_screen(out / ('%s_%s.nex' % (name, label)), f, screen)
        bad = boot_problems(f, z80, builds[label])
        ok &= not bad
        say('Loading   : %s %s boot %s' % (f.name, hashlib.md5(f.read_bytes()).hexdigest(), bad[:3] if bad else 'OK'))
    pok = trainer_pok(z80)
    pok_path = out / (name + '_verified.pok')
    if getattr(a, 'pok', None) and Path(a.pok).read_text() != pok:
        raise ValueError("Use the verified Hard Drivin' trainers generated by this engine")
    pok_path.write_text(pok)
    a.pok = str(pok_path)
    import tempfile
    tboot = collections.Counter()
    with tempfile.TemporaryDirectory() as d:     # each trainer on: both hooked builds boot to the trainer's bytes
        for tname in TRAINERS:
            for label, cls, fn in (('smooth', HDPatch, build), ('steps', StepsPatch, build_steps)):
                f = Path(d) / ('%s.nex' % label)
                bad = boot_problems(f, z80, fn(z80, f, cls(trainers=(tname,))))
                tboot['%s %s%s' % (tname, label, ' boot!' if bad else '')] += 1
    ok &= not any(k.endswith('!') for k in tboot)
    say('Trainers  : %s (%s); boot with each on: %s' % (', '.join(TRAINERS), pok_path.name, dict(tboot)))
    states, skept, tstates = [], None, {}
    for rec in getattr(a, 'rzx', []) or []:
        t0 = time.time()
        counts, fails, kept = verify(builds['smooth'], rec, stop=getattr(a, 'quick', None), collect=12, progress=say,
                                     trainer_states=tstates)
        states += kept
        ok &= not any(v for k, v in counts.items() if k.endswith('!'))
        say('Verify    : smooth %s %s (%.0f s)' % (dict(counts), fails[:2], time.time() - t0))
        t0 = time.time()
        counts, fails, kept = verify_steps(builds['steps'], rec, stop=getattr(a, 'quick', None), collect=12,
                                           progress=say)
        skept = skept or kept
        ok &= not any(v for k, v in counts.items() if k.endswith('!'))
        say('Verify    : steps %s %s (%.0f s)' % (dict(sorted(counts.items())), fails[:2], time.time() - t0))
    if getattr(a, 'rzx', None):
        if states:
            units = unit_tests(builds['smooth'], states)
            ok &= not any(v for k, v in units.items() if k.endswith('!'))
            say('Unit      : smooth %s' % dict(units))
        else:
            say('Unit      : smooth: no states (the recordings reached no render)')
            ok = False
        t0 = time.time()
        units, pace = unit_tests_steps(builds['steps'], skept) if skept else ({'no states!': 1}, {})
        ok &= not any(v for k, v in units.items() if k.endswith('!'))
        say('Unit      : steps %s (%.0f s)' % (dict(units), time.time() - t0))
        if pace.get('dur'):
            d = sorted(pace['dur'])
            say('Pace      : steps model runs: update %.2f / %.2f / %.2f frames (median / p95 / max; 10 = real '
                'time), %d views early, N used %s' % (d[len(d) // 2], d[int(0.95 * (len(d) - 1))], d[-1],
                                                    pace['early'], dict(sorted(pace['N'].items()))))
        hits = tstates.pop('hits', {})
        units = unit_trainers(z80, {k: v for k, v in tstates.items()})
        ok &= not any(v for k, v in units.items() if k.endswith('!'))
        say('Unit      : trainers %s; recorded arrivals %s' % (dict(units), {'0x%04X' % k: v for k, v in
                                                                         sorted(hits.items())}))
    else:                                           # a rebuild (record recipe without recordings): builds + boot only
        say('Verify    : not run (no recording: rebuild)')
        say('Unit      : not run (no recording: rebuild)')
    outputs = {'default': name + '_steps.nex', 'plain': name + '.nex', 'colours': {}}
    if screen:
        outputs['loading'] = name + '_steps_loading.nex'
    outputs['toggles'] = {TOGGLE_SMOOTH: {
        'logic': True, 'what': 'route 1 (hard_drivin_smooth.nex): the original update steps, render + copy at 28 MHz',
        'default': name + '_smooth.nex', 'loading': name + '_smooth_loading.nex' if screen else None}}
    (out / (name + '_outputs.json')).write_text(json.dumps(outputs, indent=1) + '\n')
    say('Result    : ' + ('PASSED' if ok else 'FAILED'))
    return bool(ok)
