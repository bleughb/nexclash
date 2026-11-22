"""Winter Sports (Electric Dreams Software, 1985, 48K): the plain .nex with all six events in one file.
GPL-3.0-or-later. Facts, decisions and evidence: games/winter_sports.md.

A plain conversion (no sprite build yet) of a multiload game: the snapshot is the main menu (the menu code loaded, no
event yet); the six event blocks (32,824 bytes each, loaded to 0x7500) come from the tape (`--tape GAME.tap`, found by
content: nexclash/tapeset.py) and are embedded in banks 12-26.
  - the menu's own LD-BYTES wrapper (0x627E, which calls ROM 0x0562) becomes JP HOOK; HOOK (0x6C00, 127 bytes, in the
    stale loader bytes after the menu block that nothing reads) answers its two requests from RAM:
      header (DE=22, flag FF): the menu's own wanted header (the table at 0x63C0 + 22 k, pointer in 0x6296) is copied
        to IX and the event k = (pointer - 0x63C0) / 22 is kept at 0x6D03;
      data (DE=0x8038): event k's 5 pages (24 + 5k..) are copied to IX through MMU0 (NextReg 0x50) with interrupts
        off, NextReg 0x50 = 0xFF after, then the border, EI and carry set as the ROM's return does;
  - the tape's SCREEN$ is the NEX header's ULA loading screen and bank 5's screen; the stub's setup routine (0xD000)
    waits 260 frames (raster line 192 counted via NextReg 0x1F: 5.2 s at 50 Hz) and copies the menu screen back
    from bank 27.
Proof (verify / unit_tests): the patched menu is run in the simulator against the original menu fed from the tape at the
ROM entry 0x0562, for each event, and the memory and registers compared; the hook is also called directly for every
header and every data block, with a negative control (a hook with the wrong first page). Not RZX proof: see the notes.
"""
import hashlib
import json
import os
import sys
from collections import Counter

from . import tapeset
from . import winter_sports_dh as dh
from . import winter_sports_bobsled as bobsled
from . import winter_sports_ice_hockey as ice_hockey
from . import winter_sports_speed_skating as speed_skating
from . import winter_sports_biathlon as biathlon
from . import winter_sports_common as common
from . import z80tonex

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
RECORD = 'winter_sports'

SITE = 0x627E                                  # the menu's LD-BYTES wrapper
HOOK = 0x6C00
PG, REM, EVT = 0x6D00, 0x6D01, 0x6D03
TABLE = 0x63C0                                 # the menu's header table: 22 bytes per event
PTR = 0x6296                                   # the wanted header's address (a variable of the menu)
EVENT_ADDR = 0x7500
EVENT_LEN = 32824
EVENT_BANK0 = 12                               # event k: 8K pages 24 + 5k .. 28 + 5k
SCR_BANK = 27                                  # the menu screen, put back after the loading screen
WAIT_FRAMES = 260
NAMES = ['downhill_slalom', 'ice_hockey', 'ski_jumping', 'speed_skating', 'bobsled', 'biathlon']
MENU_KEYS = ['1', '4', '5', '6', '7', '8']     # the main menu's key for each event
PLUGINS = [dh, ice_hockey, speed_skating, bobsled, biathlon]                                 # event plugins (winter_sports_common.py): one module per converted event, by INDEX
BANK_PLAN = {0: (28, 29, 30), 1: (31, 32, 33), 2: (34, 35, 36), 3: (37, 38, 39), 4: (40, 41, 42), 5: (43, 44, 45)}   # 16K banks an event's plugin may use
DISABLE = 0x6D10                               # the loader hook's `CALL DISABLE` routine (every plugin's display-off code), up to 0x6EFF


def _profile_path():
    return os.path.join(ROOT, 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_winter_sports(snap):
    if snap.machine != '48K':
        return False
    return all(bytes(snap.memory[s['addr']:s['addr'] + len(s['bytes']) // 2]).hex() == s['bytes']
               for s in load_profile()['signature'])


def tape_sets():
    """The releases the build accepts: [[md5, ...], ...] (profile tape_sets)."""
    return [s['md5'] for s in load_profile()['tape_sets']]


# ---------------------------------------------------------------- the tape's blocks
def blocks(tape_files):
    """(screen 6912 bytes, [six event blocks, 32824 bytes each]) from the tape set, found by content (a data block
    of flag 0xFF and length 6914 / 32826), in file order; ValueError when the tape is not this game's."""
    ts, _ = tapeset.load(tape_files, tape_sets())
    scr = ts.find(lambda b: len(b) == 6914 and b[0] == 0xFF)
    ev = ts.find(lambda b: len(b) == EVENT_LEN + 2 and b[0] == 0xFF, first_only=False)
    if scr is None or len(ev) != 6:
        raise ValueError('not a Winter Sports tape: found %s screen and %d event blocks (want 1 and 6)'
                         % ('a' if scr is not None else 'no', len(ev)))
    return scr[1:-1], [b[1:-1] for b in ev]


# ---------------------------------------------------------------- the hook (hand-assembled, labels below)
def asm_hook(hybrid=False):
    code = bytearray()
    lab = {}
    fix = []

    def L(n):
        lab[n] = HOOK + len(code)

    def e(*b):
        code.extend(b)

    def w(v):
        return [v & 255, v >> 8]

    def jr(op, n):
        e(op, 0)
        fix.append((len(code) - 1, n))
    e(0xF3)                                         # di
    e(0x7A, 0xB7)
    jr(0x20, 'data')                                # ld a,d / or a / jr nz,data  (DE = 22: a header)
    e(0x2A, *w(PTR))                                # ld hl,(PTR)      the wanted header, 22 bytes
    e(0xDD, 0xE5, 0xD1)                             # push ix / pop de
    e(0x01, 22, 0, 0xED, 0xB0)                      # ld bc,22 / ldir
    e(0x2A, *w(PTR), 0x11, *w(TABLE), 0xB7, 0xED, 0x52)   # hl = pointer - TABLE
    e(0x0E, 0x00, 0x11, 22, 0)                      # ld c,0 / ld de,22
    L('dv')
    e(0xB7, 0xED, 0x52)
    jr(0x38, 'dvd')
    e(0x0C)
    jr(0x18, 'dv')                                  # c = hl / 22
    L('dvd')
    e(0x79, 0x32, *w(EVT))
    jr(0x18, 'ok')
    L('data')
    e(0x3A, *w(EVT), 0x4F, 0x87, 0x87, 0x81, 0xC6, 2 * EVENT_BANK0, 0x32, *w(PG))   # first page = 24 + 5 k
    e(0xED, 0x53, *w(REM))                          # remaining = DE
    e(0xDD, 0xE5, 0xD1)                             # de = destination
    L('next')
    e(0x2A, *w(REM), 0x7C, 0xB5)
    jr(0x28, 'fin')
    e(0x3A, *w(PG), 0xED, 0x92, 0x50, 0x3C, 0x32, *w(PG))   # page -> MMU0, page + 1
    e(0x01, 0x00, 0x20, 0x7C, 0xFE, 0x20)           # chunk = min(8192, remaining)
    jr(0x30, 'full')
    e(0x44, 0x4D)
    L('full')
    e(0xB7, 0xED, 0x42, 0x22, *w(REM), 0x21, 0, 0, 0xED, 0xB0)
    jr(0x18, 'next')
    L('fin')
    e(0x3E, 0xFF, 0xED, 0x92, 0x50, 0xD5, 0xDD, 0xE1, 0x11, 0, 0)   # ROM back, ix = end, de = 0
    L('ok')
    if hybrid:                                      # every plugin's display-off code before any event loads
        e(0xCD, DISABLE & 255, DISABLE >> 8)
    e(0x3A, 0x48, 0x5C, 0xE6, 0x38, 0x0F, 0x0F, 0x0F, 0xD3, 0xFE, 0xFB, 0x37, 0xC9)   # border, ei, scf, ret
    for pos, n in fix:
        d = lab[n] - (HOOK + pos + 1)
        assert -128 <= d <= 127, (n, d)
        code[pos] = d & 255
    return bytes(code)


def asm_setup(wait=WAIT_FRAMES):
    """The stub bank's routine (0xD000): `wait` frames of the loading screen, then the menu screen back."""
    c = bytearray()

    def e(*b):
        c.extend(b)
    line = (0x01, 0x3B, 0x24, 0x3E, 0x1F, 0xED, 0x79, 0x04, 0xED, 0x78)     # a = NextReg 0x1F (raster line LSB)
    e(0x21, wait & 255, wait >> 8)                  # ld hl,wait
    top = len(c)
    e(*line, 0xFE, 0xC0, 0x20, 0)
    c[-1] = (top - len(c)) & 255                    # until the line is 192
    t2 = len(c)
    e(*line, 0xFE, 0xC0, 0x28, 0)
    c[-1] = (t2 - len(c)) & 255                     # until it has left it
    e(0x2B, 0x7C, 0xB5, 0x20, 0)
    c[-1] = (top - len(c)) & 255
    e(0xED, 0x91, 0x57, 2 * SCR_BANK)               # menu screen's page at MMU7
    e(0x21, 0, 0xE0, 0x11, 0, 0x40, 0x01, 0, 0x1B, 0xED, 0xB0)
    e(0xED, 0x91, 0x57, z80tonex.STUB_PAGE_HI)
    e(0xC9)
    return bytes(c)


def memory_patches(hybrid=False):
    """[(address, bytes)] the menu's memory gets: the hook and the jump to it (the site checked by apply)."""
    out = [(HOOK, asm_hook(hybrid)), (SITE, bytes([0xC3, HOOK & 255, HOOK >> 8]))]
    if hybrid:
        code = bytes([b for pl in PLUGINS for b in pl.disable_code()]) + bytes([0xC9])
        assert DISABLE + len(code) <= common.SPD_IN, len(code)
        out.append((DISABLE, code))
        out.append((common.SPD_IN, common.speed_code()))   # the wrappers' speed latch routines (winter_sports_common)
        out.append((common.SPD, b'\0'))                   # the latch starts at 3.5 MHz, the stub's speed
    return out


class Patch:
    """What z80tonex.convert reads (docs/ENGINE_CONTRACT.md)."""
    name = 'winter sports: six events in banks, RAM loader hook, loading screen'
    uses_printer_buffer = False
    setup_call = 0xD000
    hook_page_data = b''

    def __init__(self, scr, events, hybrid=False, enhanced=False, original_pace=False, loading=True):
        assert len(scr) == 6912 and len(events) == 6 and all(len(x) == EVENT_LEN for x in events)
        self.scr, self.hybrid, self.enhanced, self.original_pace = scr, hybrid, enhanced, original_pace
        self.loading = loading                      # False for the builds an .nxc holds: the loader shows the tape's screen from ENTER, so no 5.2 s hold here
        self.tape_events = list(events)             # as on the tape
        events = list(events)
        self.l2 = {}
        if hybrid:                                  # the event plugins: original colours per pixel, even pace; enhanced / original_pace = the options
            for pl in PLUGINS:
                events[pl.INDEX], banks = pl.patch_event(events[pl.INDEX], enhanced, original_pace)
                if not set(banks) <= set(BANK_PLAN[pl.INDEX]):
                    raise ValueError('%s uses banks %s: its plan is %s' % (pl.__name__, sorted(banks), BANK_PLAN[pl.INDEX]))
                self.l2.update(banks)
            self.name = 'winter sports: six events in banks, RAM loader hook, loading screen, %d event(s) converted' % len(PLUGINS)
        self.events = events
        blob = b''.join(x + bytes(40960 - len(x)) for x in events)
        self.extra_banks = {EVENT_BANK0 + i: blob[i * 16384:(i + 1) * 16384] for i in range(15)}
        self.extra_banks.update(self.l2)
        self.stub_extra = asm_setup() if loading else bytes([0xC9])
        self.hook = asm_hook(hybrid)

    def apply(self, snap):
        b5 = bytearray(snap.banks[5])
        site = SITE - 0x4000
        if bytes(b5[site:site + 4]) != bytes([0x14, 0x08, 0x15, 0xF3]):
            raise ValueError('not the Winter Sports menu snapshot: bytes at 0x%04X are %s' % (SITE, bytes(b5[site:site + 4]).hex()))
        menu_scr = bytes(b5[:6912])
        for a, d in memory_patches(self.hybrid):
            b5[a - 0x4000:a - 0x4000 + len(d)] = d
        if self.loading:
            b5[0:6912] = self.scr             # the loading screen is what the game memory shows first
        snap.banks[5] = bytes(b5)
        if self.loading:
            self.extra_banks[SCR_BANK] = menu_scr + bytes(16384 - 6912)


def build(z80, tape_files, out, say=print, hybrid=False, enhanced=False, original_pace=False, loading=True):
    """The .nex -> (path, patch). hybrid = the converted events (default: the original 16 colours, even pace); enhanced = their extended colours (the
    colour set); original_pace = the free-running pace back (the toggle). The NEX header gets the ULA loading screen (flags 0x82: no palette)."""
    scr, ev = blocks(tape_files)
    p = Patch(scr, ev, hybrid, enhanced, original_pace, loading)
    z80tonex.convert(z80, out, patch=p, quiet=True)
    d = bytearray(open(out, 'rb').read())
    if loading:
        d[10] = 0x82
        open(out, 'wb').write(bytes(d[:512]) + scr + bytes(d[512:]))
    else:
        open(out, 'wb').write(bytes(d))
    say('%-10s: %s (%d bytes, hook %d bytes at 0x%04X, loading screen %d frames)'
        % ('Sprites' if hybrid else 'Plain', os.path.basename(out), os.path.getsize(out), len(p.hook), HOOK, WAIT_FRAMES))
    return out, p


# ---------------------------------------------------------------- simulation (verify / unit tests)
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]      # all but R, T, MEMPTR


class _Keys:
    """Keyboard half-rows for the simulator's port read: frames [a, b) hold `key`."""

    def __init__(self, schedule):
        from .simrun import ROWS
        self.rows, self.sched = ROWS, schedule
        self.frame = 0

    def held(self):
        return {k for a, b, k in self.sched if a <= self.frame < b}

    def read(self, port):
        v = 0xFF
        if port & 1 == 0:
            h = self.held()
            for row, ks in self.rows.items():
                if (port >> 8) & (row ^ 0xFF) == 0:
                    for i, k in enumerate(ks):
                        if k in h:
                            v &= ~(1 << i)
        return v


def _sim(z80, patched, pages=None, keys=None, hybrid=False):
    """A simulator on the menu snapshot; `patched` puts the hook in (memory_patches) with the NextReg 0x50 model:
    a RAM page from `pages` {page: 8192 bytes} appears at 0x0000, 0xFF puts the ROM back."""
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot
    from . import simrun, z80n
    sim = from_snapshot(simrun._sim_class(type('H', (), {})), Snapshot.get(z80), config={'int_active': 0})
    mem = sim.memory
    rom = list(mem[0:0x2000])
    kb = _Keys(keys or [])

    class Tr:
        border = 0

        sel = 0

        def read_port(self, regs, port):
            if port == 0x253B:                      # NextReg read: NR 7 = programmed speed in bits 1:0, actual in 5:4
                return sim.nr7 << 4 | sim.nr7 if self.sel == 0x07 else 0
            return 0x1F and (0 if port & 0xFF == 0x1F else kb.read(port))

        def write_port(self, regs, port, value, offset=0):
            if port == 0x243B:
                self.sel = value
            elif port & 1 == 0 and sim.spd[0] > sim.base[0]:     # beeper / border write above the player's speed
                sim.fast_out += 1                   # a beeper / border write while the CPU runs fast
    sim.fast_out = 0
    sim.spd = [1, 0]
    sim.nr7 = 0                                     # NextReg 7 as programmed
    sim.base = [1]                                  # the player's speed factor (F8): what "fast" is measured against
    sim.set_tracer(Tr())
    log = []
    spd = sim.spd                                   # CPU speed factor (NextReg 0x07: 3.5 / 7 / 14 / 28 MHz) and a T remainder

    def nextreg(reg, val):
        log.append((reg, val))
        if reg == 0x50:
            mem[0:0x2000] = rom if val == 0xFF else list(pages[val])
        elif reg == 0x07:
            spd[0] = (1, 2, 4, 8)[val & 3]
            sim.nr7 = val & 3

    def player_speed(v):                            # the speed the player chose (F8): NR 7 and the baseline for "fast"
        nextreg(0x07, v)
        sim.base[0] = (1, 2, 4, 8)[v & 3]
    sim.player_speed = player_speed
    z80n.install(sim, nextreg)
    if patched:
        for a, d in memory_patches(hybrid):
            mem[a:a + len(d)] = list(d)
    return sim, kb, log


def _original_trap(sim, events, state):
    """The menu's own tape load answered at the ROM entry 0x0562 as the tape would: the header request returns the
    menu's wanted header (the Bleepload tape's 22 bytes are this table entry), the data request the event."""
    R, mem = sim.registers, sim.memory
    ix, de = R[8] << 8 | R[9], R[4] << 8 | R[5]
    ptr = mem[PTR] | mem[PTR + 1] << 8
    if de == 22:
        data = bytes(mem[ptr:ptr + 22])
        state['k'] = (ptr - TABLE) // 22
    elif de == EVENT_LEN:
        data = events[state['k']]
    else:
        raise ValueError('unexpected tape request DE=%d' % de)
    for i, v in enumerate(data):
        mem[(ix + i) & 0xFFFF] = v
    ret = mem[R[12]] | mem[R[12] + 1] << 8
    R[12] = (R[12] + 2) & 0xFFFF
    R[17] |= 1
    R[1] |= 1
    R[8], R[9], R[4], R[5] = (ix + de) >> 8 & 255, (ix + de) & 255, 0, 0
    R[24] = ret


def _run(sim, kb, frames, hook=None):
    from skoolkit.simutils import PC, T, IFF
    R, mem, ops = sim.registers, sim.memory, sim.opcodes
    for f in range(frames):
        kb.frame = f
        while R[T] < 69888:
            if hook and R[PC] == 0x0562:
                hook(sim)
                continue
            ops[mem[R[PC]]]()
        R[T] -= 69888
        if R[IFF]:
            if mem[R[PC]] == 0x76:
                R[PC] = (R[PC] + 1) & 0xFFFF
            sim.accept_interrupt(R, mem, 0)


def _pages(events):
    blob = b''.join(x + bytes(40960 - len(x)) for x in events)
    return {2 * EVENT_BANK0 + i: blob[i * 8192:(i + 1) * 8192] for i in range(30)}


def verify(patch, z80, tape_files=None, frames=900, progress=None, collect=0, **_):
    """Differential test: for each event the original menu (loads answered at ROM 0x0562) and the patched menu (the
    hook, NextReg 0x50 modelled) are run from the menu snapshot with the same keys; after `frames` frames (the event's
    option screen, idle) 0x4000-0xFFFF must agree (the event's bytes within 8 of the tape block: its own variables) except
    the hook's own bytes and variables, the system variables and the stack; I, IM and IFF must agree.
    -> (Counter, examples)"""
    C, ex = Counter(), []
    pages = _pages(patch.events)
    own = set(range(HOOK, HOOK + len(patch.hook))) | set(range(PG, EVT + 1)) | set(range(SITE, SITE + 3))
    own |= {common.SPD} | set(range(common.SPD_IN, common.SPD_IN + len(common.speed_code())))   # the speed latch
    timing = set(range(0x5C00, 0x5C80)) | set(range(0x5F80, 0x6000))   # FRAMES etc. and the stack: the hook's copy takes ~12
    #                                                         frames the tape trap does not, so the two runs stop at different instants
    for k, key in enumerate(MENU_KEYS):
        sched = [(20, 28, key)]
        a, ka, _l = _sim(z80, False, keys=sched)
        b, kb_, _l2 = _sim(z80, True, pages=pages, keys=sched, hybrid=patch.hybrid)
        st = {}
        _run(a, ka, frames, lambda s: _original_trap(s, patch.events, st))
        _run(b, kb_, frames)
        ma, mb = a.memory, b.memory
        diff = [x for x in range(0x4000, 0x10000) if ma[x] != mb[x] and x not in own and x not in timing]
        evloaded = sum(1 for i in range(EVENT_LEN) if mb[EVENT_ADDR + i] != patch.events[k][i]) <= 8   # the event's own variables move
        C['event %d loaded' % k + ('' if evloaded else '!')] += 1
        C['memory: %d differing bytes%s' % (len(diff), '' if not diff else '!')] += 1
        ra, rb = a.registers, b.registers
        rd = [i for i in (14, 26, 27) if ra[i] != rb[i]]     # I, IFF, IM: the rest is where in the idle loop each stopped
        C['registers equal' + ('' if not rd else '!')] += 1
        if diff or rd or not evloaded:
            ex.append((NAMES[k], [hex(x) for x in diff[:10]], rd, evloaded))
        if progress:
            progress(k + 1, 6)
    return C, ex


def _call_hook(sim, ix, de, flag_carry=1, limit=2_000_000):
    """Call the hook as the menu does (registers for the request, return address on the stack) -> carry, steps."""
    from skoolkit.simutils import PC
    R, mem, ops = sim.registers, sim.memory, sim.opcodes
    R[8], R[9], R[4], R[5] = ix >> 8, ix & 255, de >> 8, de & 255
    R[1] |= flag_carry
    R[12] = (R[12] - 2) & 0xFFFF
    mem[R[12]], mem[R[12] + 1] = 0x00, 0x90        # return to 0x9000: stays a NOP sled we stop on
    R[24] = HOOK
    n = 0
    while R[24] != 0x9000 and n < limit:
        ops[mem[R[24]]]()
        n += 1
    return R[1] & 1, n, R[24] == 0x9000


def unit_tests(patch, z80, states=None, neg=None, **_):
    """The hook called directly: every header (22 bytes copied, event noted, carry, EI) and every data block (the
    event's 32,824 bytes at IX, ROM paged back, IX advanced), at an odd destination too; the negative control is a hook
    whose pages are shifted by one (every data case must then fail). -> (Counter, failures)"""
    C, fails = Counter(), []

    def case(pages, bad_expected=False):
        for k in range(6):
            sim, kb, log = _sim(z80, True, pages=pages, hybrid=patch.hybrid)
            mem = sim.memory
            ptr = TABLE + 22 * k
            mem[PTR], mem[PTR + 1] = ptr & 255, ptr >> 8
            for dst in (0x6298, 0x6310):
                carry, n, ok = _call_hook(sim, dst, 22)
                good = ok and carry == 1 and bytes(mem[dst:dst + 22]) == bytes(mem[ptr:ptr + 22]) and mem[EVT] == k
                C['header %d at %04X' % (k, dst) + ('' if good else '!')] += 1
                if not good:
                    fails.append(('header', k, dst))
            sim.registers[16:18] = [0xFF, 1]
            carry, n, ok = _call_hook(sim, EVENT_ADDR, EVENT_LEN)
            data = bytes(mem[EVENT_ADDR:EVENT_ADDR + EVENT_LEN])
            ix = sim.registers[8] << 8 | sim.registers[9]
            good = (ok and carry == 1 and data == patch.events[k] and ix == EVENT_ADDR + EVENT_LEN
                    and (log[-1] == (0x50, 0xFF)) and sim.registers[4] | sim.registers[5] == 0)
            if bad_expected:
                C['negative control event %d detected' % k + ('' if not good else '!')] += 1
            else:
                C['data %d' % k + ('' if good else '!')] += 1
                if not good:
                    fails.append(('data', k))
    case(_pages(patch.events))
    shifted = {p: _pages(patch.events).get(p + 1, bytes(8192)) for p in _pages(patch.events)}
    case(shifted, bad_expected=True)
    return C, fails


OUTPUTS = (('sprites', dict(hybrid=True)), ('enhanced', dict(hybrid=True, enhanced=True)), ('origpace', dict(hybrid=True, original_pace=True)),
           ('enhanced_origpace', dict(hybrid=True, enhanced=True, original_pace=True)))


def auto(a, z80, name, out, say):
    """The builds from the menu snapshot and the tape (--tape GAME.tap):
      NAME.nex                    plain: the six events in one file (the hardware-tested conversion)
      NAME_sprites.nex            the default build: the converted events in the ORIGINAL 16 colours, per pixel, at an even pace
      NAME_enhanced.nex           + the colour set "Enhanced" (extended colours where an event has them)
      NAME_origpace.nex           + the toggle "Original pace" (the game's free-running pace back); NAME_enhanced_origpace.nex both
      NAME_outputs.json           what the .nxc holds: the default, the colour set, the toggle (nxcout.manifest)
    then each plugin's differential tests and the loader hook's, with negative controls; the .nxc when a zx0 compressor is found."""
    say('Game      : %s' % name)
    say('Engine    : winter_sports (Winter Sports, 48K, six tape events embedded; %d event plugin(s): %s)'
        % (len(PLUGINS), ', '.join(pl.__name__.split('.')[-1] for pl in PLUGINS)))
    tapes = list(getattr(a, 'tape', None) or [])
    if not tapes:
        say('Refused   : the events come from the tape: add --tape GAME.tap (the original release, or its .tzx of standard blocks)')
        say('Result    : FAILED')
        return False
    try:
        nex, patch = build(z80, tapes, os.path.join(out, name + '.nex'), say)
        built = {}
        for tag, kw in OUTPUTS:
            built[tag] = build(z80, tapes, os.path.join(out, '%s_%s.nex' % (name, tag)), say, **kw)
            build(z80, tapes, os.path.join(out, '%s_nxc_%s.nex' % (name, tag)), lambda *_: None, loading=False, **kw)   # what the .nxc holds: no 5.2 s hold
    except ValueError as e:
        say('Refused   : %s' % e)
        say('Result    : FAILED')
        return False
    ok = True
    C, ex = verify(patch, z80)
    say('Verify    : %s' % ', '.join('%s x%d' % kv for kv in sorted(C.items())))
    U, fails = unit_tests(patch, z80)
    say('Unit      : %d cases, %d failed' % (sum(U.values()), len([k for k in U if k.endswith('!')])))
    ok = not any(k.endswith('!') for k in list(C) + list(U))
    for tag in ('sprites', 'origpace'):                  # every plugin, both paces (enhanced differs from the default in picture bytes only)
        pt = built[tag][1]
        for pl in PLUGINS:
            pok, lines = pl.tests(pt, z80, say)
            for ln in lines:
                say('%s [%s]' % (ln, tag))
            ok = ok and pok
    EP = built['enhanced'][1]
    diff = {k for k in EP.extra_banks if k in built['sprites'][1].extra_banks and EP.extra_banks[k] != built['sprites'][1].extra_banks[k]}
    planned = {b for pl in PLUGINS for b in BANK_PLAN[pl.INDEX]}
    colour_ok = diff and diff <= planned
    say('Enhanced  : differs from the default in banks %s only (%s)' % (sorted(diff), 'picture banks of the plugins' if colour_ok else 'NOT picture banks'))
    ok = ok and bool(colour_ok)
    json.dump({'default': name + '_sprites.nex', 'plain': name + '.nex',
               'colours': {'Enhanced': {'default': name + '_enhanced.nex'}},
               'toggles': {'Original pace': {'logic': False, 'what': 'the free-running pace of the original instead of the even 25 updates a second',
                                            'default': name + '_origpace.nex',
                                            'colours': {'Enhanced': {'default': name + '_enhanced_origpace.nex'}}}}},
              open(os.path.join(out, name + '_outputs.json'), 'w'), indent=1)
    if ok:
        try:
            say('.nxc      : %s' % make_nxc(a, z80, tapes, out, name, say))
        except Exception as e:               # the patch is an extra: say why it is not there
            say('.nxc      : not made (%s)' % e)
    say('Result    : %s' % ('PASSED (differential on the simulator; no RZX, no hardware proof in this run)' if ok else 'FAILED'))
    return ok


def make_nxc(a, z80, tapes, out, name, say):
    """NAME.nxc from the default build, the colour set Enhanced and the toggle Original pace, for the TAPE as the target and the menu snapshot as its
    start state (nxc.py make NEX TAPE --start): the loader reads the player's own tape from the card. Every build the patch holds is checked on read-back
    (the default, the set, the toggle, set + toggle) against the .nex files. Needs the zx0 compressor ($NXC_ZX0_DIR, tools/zx0). -> its path."""
    from . import nxc, nxcout
    nxc.ZX0_DIR = nxcout.zx0_dir()
    dst = os.path.join(out, name + '.nxc')
    path = lambda tag: os.path.join(out, '%s_nxc_%s.nex' % (name, tag))     # the builds WITHOUT the 5.2 s loading hold: the loader shows the tape's screen from ENTER (build_screen)
    argv = ['make', path('sprites'), tapes[0], '--start', z80, '-o', dst, '--title', 'Winter Sports', '--patch-version', '1.0',
            '--colours', 'Enhanced=' + path('enhanced'), '--toggle', 'Original pace=' + path('origpace')]
    who, _where = nxcout.patch_by(a)
    if who:
        argv += ['--patch-by', who]
    nxcout._run(nxc, argv)
    game = open(tapes[0], 'rb').read()
    tool = os.environ.get('NXC_BUILD_SCREEN_TOOL')           # jattree/nxc tools/nxc.py with `build_screen` (PR 9): the loader shows the tape's SCREEN$ from ENTER
    if tool and os.path.exists(tool):
        import subprocess
        off, p_ = None, 0
        while p_ < len(game):                                  # the offset of the 6,912-byte screen in the tape file
            n = game[p_] | game[p_ + 1] << 8
            if n == 6914 and game[p_ + 2] == 0xFF:
                off = p_ + 3
                break
            p_ += 2 + n
        if off is None:
            raise ValueError('no SCREEN$ block in the tape')
        tmp = dst + '.tmp'
        subprocess.run([sys.executable, tool, 'set', dst, tapes[0], 'build_screen', str(off), '-o', tmp], check=True, capture_output=True)
        os.replace(tmp, dst)
        say('            build_screen=%d: the loader shows the tape loading screen from ENTER' % off)
    f = open(dst, 'rb').read()
    if tool and os.path.exists(tool):                         # read back with the same tool that wrote build_screen
        import importlib.util
        spec = importlib.util.spec_from_file_location('nxc_bs', tool)
        nxc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nxc)
    for colours, toggles, tag in ((None, (), 'sprites'), ('Enhanced', (), 'enhanced'), (None, ('Original pace',), 'origpace'),
                                  ('Enhanced', ('Original pace',), 'enhanced_origpace')):
        if nxc.apply(f, game=game, colours=colours, toggles=list(toggles)) != open(path(tag), 'rb').read():
            os.remove(dst)
            raise ValueError('applied%s it does not give %s' % ((' with ' + ' + '.join(x for x in (colours,) + tuple(toggles) if x)) if colours or toggles else '',
                                                                os.path.basename(path(tag))))
    say('            holds: the default, colour set Enhanced, toggle Original pace, and the set with the toggle: each read back to its .nex exactly')
    return dst
