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
def asm_hook():
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


def memory_patches():
    """[(address, bytes)] the menu's memory gets: the hook and the jump to it (the site checked by apply)."""
    return [(HOOK, asm_hook()), (SITE, bytes([0xC3, HOOK & 255, HOOK >> 8]))]


class Patch:
    """What z80tonex.convert reads (docs/ENGINE_CONTRACT.md)."""
    name = 'winter sports: six events in banks, RAM loader hook, loading screen'
    uses_printer_buffer = False
    setup_call = 0xD000
    hook_page_data = b''

    def __init__(self, scr, events, first_page_fix=0):
        assert len(scr) == 6912 and len(events) == 6 and all(len(x) == EVENT_LEN for x in events)
        self.scr, self.events = scr, events
        blob = b''.join(x + bytes(40960 - len(x)) for x in events)
        self.extra_banks = {EVENT_BANK0 + i: blob[i * 16384:(i + 1) * 16384] for i in range(15)}
        self.stub_extra = asm_setup()
        self.hook = asm_hook()

    def apply(self, snap):
        b5 = bytearray(snap.banks[5])
        site = SITE - 0x4000
        if bytes(b5[site:site + 4]) != bytes([0x14, 0x08, 0x15, 0xF3]):
            raise ValueError('not the Winter Sports menu snapshot: bytes at 0x%04X are %s' % (SITE, bytes(b5[site:site + 4]).hex()))
        menu_scr = bytes(b5[:6912])
        for a, d in memory_patches():
            b5[a - 0x4000:a - 0x4000 + len(d)] = d
        b5[0:6912] = self.scr                 # the loading screen is what the game memory shows first
        snap.banks[5] = bytes(b5)
        self.extra_banks[SCR_BANK] = menu_scr + bytes(16384 - 6912)


def build(z80, tape_files, out, say=print):
    """The plain .nex -> (path, patch). The NEX header gets the ULA loading screen (flags 0x82: no palette)."""
    scr, ev = blocks(tape_files)
    p = Patch(scr, ev)
    z80tonex.convert(z80, out, patch=p, quiet=True)
    d = bytearray(open(out, 'rb').read())
    d[10] = 0x82
    open(out, 'wb').write(bytes(d[:512]) + scr + bytes(d[512:]))
    say('Plain      : %s (%d bytes, hook %d bytes at 0x%04X, loading screen %d frames)'
        % (os.path.basename(out), os.path.getsize(out), len(p.hook), HOOK, WAIT_FRAMES))
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


def _sim(z80, patched, pages=None, keys=None):
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

        def read_port(self, regs, port):
            return 0x1F and (0 if port & 0xFF == 0x1F else kb.read(port))

        def write_port(self, regs, port, value, offset=0):
            pass
    sim.set_tracer(Tr())
    log = []

    def nextreg(reg, val):
        log.append((reg, val))
        if reg == 0x50:
            mem[0:0x2000] = rom if val == 0xFF else list(pages[val])
    z80n.install(sim, nextreg)
    if patched:
        for a, d in memory_patches():
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
    timing = set(range(0x5C00, 0x5C80)) | set(range(0x5F80, 0x6000))   # FRAMES etc. and the stack: the hook's copy takes ~12
    #                                                         frames the tape trap does not, so the two runs stop at different instants
    for k, key in enumerate(MENU_KEYS):
        sched = [(20, 28, key)]
        a, ka, _l = _sim(z80, False, keys=sched)
        b, kb_, _l2 = _sim(z80, True, pages=pages, keys=sched)
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
            sim, kb, log = _sim(z80, True, pages=pages)
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


def auto(a, z80, name, out, say):
    """The plain .nex from the menu snapshot and the tape (--tape GAME.tap), then the differential test and the unit tests."""
    say('Game      : %s' % name)
    say('Engine    : winter_sports (Winter Sports, 48K, six tape events embedded; plain build)')
    tapes = list(getattr(a, 'tape', None) or [])
    if not tapes:
        say('Refused   : the events come from the tape: add --tape GAME.tap (the original release, or its .tzx of standard blocks)')
        say('Result    : FAILED')
        return False
    try:
        nex, patch = build(z80, tapes, os.path.join(out, name + '.nex'), say)
    except ValueError as e:
        say('Refused   : %s' % e)
        say('Result    : FAILED')
        return False
    ok = True
    C, ex = verify(patch, z80)
    bad = [k for k in C if k.endswith('!')]
    say('Verify    : %s' % ', '.join('%s x%d' % kv for kv in sorted(C.items())))
    U, fails = unit_tests(patch, z80)
    badu = [k for k in U if k.endswith('!')]
    say('Unit      : %d cases, %d failed' % (sum(U.values()), len(badu)))
    ok = not bad and not badu
    say('Result    : %s' % ('PASSED (differential on the simulator; no RZX, no hardware proof in this run)' if ok else 'FAILED'))
    return ok
