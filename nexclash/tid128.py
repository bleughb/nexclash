"""Treasure Island Dizzy 128K - opt-in rework 'v128' of Dean Woodyatt's dedicated builder `dizzy_patch` (Jon Attree,
2026-11-05).

Dean's builder (nexclash/dizzy_patch.py: trampolines, hooks, set-up and the pattern build; untouched, still his
record's build of the 48K file) applied to the game's 128K release, whose interrupt handler plays the AY music from
bank 6 (CALL 0x7202 pages it in). The 128K file keeps the 48K game's code: every patch site is byte-identical (banks
5 and 2, and bank 0 at 0xC000-0xFFFF, where the in-game code lives; the title pages bank 6 there). What this module
adds, and nothing else:
  - the detector and apply() for the 128K snapshot (bank 0 patched directly, whatever 0xC000 holds at the snapshot);
  - the trampolines stay at 0x5B00-0x5B50, which on a 128K machine hold ROM 0's paging routines: the game never
    reads or writes them (the verifier fails any access by game code), and NEXLOAD's own writes there are undone by a
    wrapper round Dean's set-up routine, which puts the patched 0x5B00-0x5BFF back;
  - the whole alt ROM image (refactor plan 1): image 1 = ROM 1 as the ROM path check takes the original's (the 128K
    ROM 1 with its keypad call sites as the 48K ROM has them) + the start-up register block at 0x386E (keypad code);
  - a 128K-capable copy of the TID verifier (nexclash/verify.py, which is 48K only) that also checks the bubble test
    (0xF618, the virtual read) and stops the interrupt event where the hook hands over to the sound routine 0x7202
    (which pages bank 6: both runs are the same from there);
  - the hook-speed pass (pace ORIGINAL): Dean's two hook-page entries (the plot hook and the
    bubble test's virtual read, both reached through his trampolines) run through a wrapper that latches the
    incoming speed, runs his hook at 28 MHz and writes the latched speed back (card patch.restore-speed): Dean's
    plot hook at 3.5 MHz, with interrupts off, lost an interrupt now and then (pace: 49.80 against 50.00 taken a
    second, the game out of lockstep at update 147);
  - the every-site clock matrix and its negative, a forced 3.5 MHz exit.

    python nexclash.py auto TID128.z80 --rzx R1 --rzx R2 --no-record
"""
import collections
import copy
import hashlib
import json
import os

from . import dizzy_patch as DP

ROM_ORG = 0x386E
ALT_PAGE = 24
ISR_SOUND = 0x7202          # CALL 29186 at 0xEFB2 in the game ISR: Dean's hide hook JPs here
BUBBLE = 63000              # CALL 62333 (pixel test) at 0xF618 -> T_BUB (virtual read)
LATCH_P, LATCH_B = 0x5B60, 0x5B61   # the wrappers' speed latches: printer buffer bytes the game never touches
PRINTER = (0x5B00, 0x5B62)          # Dean's trampolines 0x5B00-0x5B50 + the latches: game access fails the verify
PROFILE = {'undo_buffer': 40149, 'plotter': 39774, 'eraser': 40087, 'plot_site': 61578, 'plot_site_kind': 'CALL',
           'wipe': 44931, 'isr_hide_call': 61362, 'engine': 'tid'}
DECISIONS = {'engine': 'tid128', 'base': "Dean's dizzy_patch (trampolines, hooks, set-up, patterns: read, not copied)",
             'input': 'the 128K release (AY music from bank 6 in the game ISR)',
             'strategy': 'printer buffer trampolines 0x5B00-0x5B50 (put back after NEXLOAD); hooks in bank 10 page 21 '
                         'at slot 0 with interrupts off (Dean); whole alt ROM image: ROM 1 + the register block at 0x386E'}


from .verify import REGS as CMP        # registers compared (verify.py's: all but R, T, MEMPTR)


def load_profile():
    """This engine's facts: Dean's TID profile addresses (docs/profiles/tid_treasure_island_dizzy.json's, as his builder
    uses them), the same for the 128K release."""
    return dict(PROFILE)


def unit_tests(patch, states, negs=None):
    """The paths a replay checks only from its own clock: every hook site from a captured state at all four incoming
    clocks (clock_matrix), and its negative control, a forced 3.5 MHz exit, which must fail. -> Counter."""
    from collections import Counter
    cm, rows = clock_matrix(patch, states)
    c = Counter({'clock cases': cm['cases']})
    for k, v in cm.items():
        if k.endswith('!'):
            c[k] += v
    cn, _ = clock_matrix(forced35(patch), states)
    caught = sum(v for k, v in cn.items() if k.endswith('!'))
    c['negative control forced 3.5 MHz exit caught' if caught else 'negative control forced 3.5 MHz exit not caught!'] += caught or 1
    return c


def rom128_1():
    """ROM 1 as nextboot.rom_paths takes a 128K recording's (see loderunner_v2.rom128_1)."""
    from skoolkit import ROM48, ROM128, read_bin_file
    from .nextboot import KEYPAD_CODE
    r1, r48 = read_bin_file(ROM128[1], 16384), read_bin_file(ROM48, 16384)
    return bytes(r48[a] if a < KEYPAD_CODE else r1[a] for a in range(16384))


def _peek128(banks):
    def peek(a):
        if a < 0x8000:
            return banks[5][a - 0x4000]
        if a < 0xC000:
            return banks[2][a - 0x8000]
        return banks[0][a - 0xC000]
    return peek


def _wrapper(target, latch):
    """Latch NR 7's programmed speed (port 0x243B / 0x253B, bits 1:0), 28 MHz, CALL target (Dean's hook), the
    latched speed back. Keeps every register and flag the hook returns; 6 bytes of stack. 35 bytes."""
    return bytes([0xF5, 0xC5, 0x01, 0x3B, 0x24, 0x3E, 0x07, 0xED, 0x79, 0x04, 0xED, 0x78, 0xE6, 0x03,
                  0x32, latch & 0xFF, latch >> 8, 0xED, 0x91, 0x07, 0x03, 0xC1, 0xF1,
                  0xCD, target & 0xFF, target >> 8,
                  0xF5, 0x3A, latch & 0xFF, latch >> 8, 0xED, 0x92, 0x07, 0xF1, 0xC9])




def hook_page(table):
    """Dean's hook page (HOOKS: entry JPs 0x0000 -> 0x0006 plot, 0x0003 -> 0x0076 bubble; his frame table at 234)
    with the two entry JPs sent through the speed wrappers appended after the table."""
    base = len(DP.HOOKS) + len(table)
    wp, wb = base, base + 35
    lp, lb = LATCH_P, LATCH_B           # in RAM: the hook page at slot 0 is not where a latch belongs
    h = bytearray(DP.HOOKS)
    if bytes(h[0:6]) != bytes.fromhex('c30600c37600'):
        raise ValueError("Dean's hook page entry table is not JP 0x0006 / JP 0x0076")
    h[0:6] = bytes([0xC3, wp & 0xFF, wp >> 8, 0xC3, wb & 0xFF, wb >> 8])
    return bytes(h) + table + _wrapper(0x0006, lp) + _wrapper(0x0076, lb)


def is_tid128(snap):
    if snap.machine != '128K':
        return False
    b = snap.memory.banks
    peek = _peek128(b)
    return all(bytes(peek(a + k) for k in range(len(old))) == old for a, old, new in DP.site_patches())


class TidPatch128(DP.DizzyPatch):
    name = 'Treasure Island Dizzy 128K: Dizzy hardware sprite (Dean\'s builder; whole alt ROM image)'
    uses_printer_buffer = True

    def __init__(self):
        super().__init__()
        rom = rom128_1()
        self.regblock = ROM_ORG
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)
        self.page = bytes(rom[0x2000:0x4000])
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[0:0x2000]))
        self.strategy = 'printer'
        self.sites = DP.site_patches()
        self.code = DP.TRAMP

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('this rework is for the 128K release')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])

        def peek(a):
            return ram[a - 0x4000]

        def poke(a, data):
            ram[a - 0x4000:a - 0x4000 + len(data)] = data
        for a, old, new in DP.site_patches():
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.printer_orig = bytes(ram[PRINTER[0] - 0x4000:PRINTER[1] - 0x4000])
        frames = DP.read_frames(peek)
        pats, table, n = DP.build_patterns(frames)
        self.num_patterns = n
        for a, old, new in DP.site_patches():
            poke(a, new)
        poke(DP.TRAMP_ORG, DP.TRAMP)
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.table = table
        self.hook_page_data = hook_page(table)
        pats = pats + bytes(-len(pats) % 256)
        setup = bytearray(DP.SETUP)
        setup[DP.SETUP_NBLOCKS2_OFF] = max(0, len(pats) - 8192) // 256
        prn = bytes(snap.banks[5][0x1B00:0x1C00])         # the patched printer buffer (trampolines in)
        self.printer = prn
        self.setup_call = DP.SETUP_ORG + len(setup)
        copy_at = self.setup_call + 15
        self.stub_extra = bytes(setup) + bytes([0xCD, DP.SETUP_ORG & 0xFF, DP.SETUP_ORG >> 8, 0x21, copy_at & 0xFF,
                                                copy_at >> 8, 0x11, 0x00, 0x5B, 0x01, 0x00, 0x01, 0xED, 0xB0, 0xC9]) + prn
        self.extra_banks = {11: pats, 12: self.page + self.altrom_low[1]}


# ---------------------------------------------------------------------------------------------
# Boot check (128K) - modelled on loderunner_v2.boot_check
# ---------------------------------------------------------------------------------------------

def boot_check(nex, z80, patch=None, tail=None):
    from . import nextboot, z80tonex as zt
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    sysrom = nextboot.system_rom3()[0]
    st = nextboot.boot(nex, s.pc, sysrom=sysrom, nexload=patch is not None)
    R, mem, bad = st['R'], st['mem'], list(st['bad'])
    w = lambda h, l: R[h] * 256 + R[l]
    got = [w(2, 3), w(4, 5), w(6, 7), w(0, 1), w(8, 9), w(10, 11), w(18, 19), w(20, 21), w(22, 23),
           w(16, 17), R[12], R[14], R[27], R[26]]
    exp = [s.bc, s.de, s.hl, s.a * 256 + s.f, s.ix, s.iy, s.bc_, s.de_, s.hl_, s.a_ * 256 + s.f_,
           s.sp, s.i, s.im, s.iff1]
    bad += [('register', i, g, e) for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    banks, _, _ = nextboot.load_nex(nex)
    t0, t1 = tail if tail else (0, 0)
    tb = None if not tail else (t0 >> 14) and {1: 5, 2: 2, 3: s.port7ffd & 7}[t0 >> 14]
    for b in range(8):
        base = {5: 0x4000, 2: 0x8000}.get(b, 0xC000)
        d = [i for i in range(16384) if banks[b][i] != s.banks[b][i] and not (b == tb and t0 <= base + i < t1)]
        if d:
            bad.append(('NEX bank differs from the (patched) snapshot', b, len(d), d[:4]))
    top = s.port7ffd & 7
    ram = s.banks[5] + s.banks[2] + s.banks[top]
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not t0 <= a < t1]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    if patch is not None:
        img = bytearray(patch.altrom_low[1] + patch.page)
        regs = zt.build_tail(s, 0x8000, patch.slot1, True)[3]
        img[patch.regblock:patch.regblock + len(regs)] = regs
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
    else:
        img = bytearray(sysrom)
    view = bytes(mem[a] for a in range(0x4000))
    if view != bytes(img):
        d = [a for a in range(0x4000) if view[a] != img[a]]
        bad.append(('slots 0/1 differ from the expected ROM image', len(d), d[:6]))
    if st['p7ffd'] & 0x3F != s.port7ffd & 0x3F or not st['p1ffd'] & 4:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 2 * top, 2 * top + 1]:
        bad.append(('MMU', st['mmu']))
    return bad


# ---------------------------------------------------------------------------------------------
# The verifier: nexclash/verify.py for a 128K recording, + the bubble test, the printer-buffer guard
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0):
    """Differential test at every patched routine (plot site, eraser, wipe, ISR hide call, bubble test): the
    original and the patched code from the same real state; registers, memory, the patched-screen model and the
    sprite pixels against the undo buffer. collect: states kept per kind (clock matrix). -> dict."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .verify import _M, _ypix, REGS
    from .analyse import classify, apply_write
    prof = PROFILE
    PRINTER = getattr(patch, "printer_span", globals()["PRINTER"])
    Machine = getattr(patch, "machine", _M)
    REGS = getattr(patch, "cmp_regs", REGS)
    U = prof['undo_buffer']
    lo, hi = prof['plotter'], prof['eraser'] + 53
    sites = [(a, new) for a, old, new in patch.sites]
    excl = set()
    for a, new in sites:
        excl.update(range(a, a + len(new)))
    code = list(patch.code)
    excl.update(range(PRINTER[0], PRINTER[1]))
    hook = list(patch.hook_page_data) + [0] * (8192 - len(patch.hook_page_data))
    pats = patch.extra_banks[11]
    A, B = Machine(True, hook), Machine(False, hook)
    A.mem.lo, A.mem.hi = lo, hi
    st = {'P': None, 'applied': 0, 'nr15': 0, 'attrs': {}, 'synced': False}
    stats = collections.Counter()
    log = []
    states = []
    G0 = [None]

    def sprite_px(m):
        out = {}
        if not (m.nr.get(0x15, 0) & 1):
            return out
        for sp in range(4):
            a = m.attrs[sp]
            if not a[3] & 0x80:
                continue
            x = a[0] | ((a[2] & 1) << 8)
            y = a[1]
            p = ((a[3] & 0x3F) << 1) | ((a[4] >> 6) & 1)
            pat = pats[p * 128:(p + 1) * 128]
            for yy in range(16):
                for xx in range(16):
                    b = pat[yy * 8 + xx // 2]
                    c = (b >> 4) if xx % 2 == 0 else (b & 15)
                    if c:
                        out[(x + xx - 32, y + yy - 32)] = c
        return out

    def undo_px(mem):
        col, h, ptr = mem[U], mem[U + 1], mem[U + 2] | mem[U + 3] << 8
        d = {}
        for r in range(h):
            row = mem[ptr + 2 * r] | mem[ptr + 2 * r + 1] << 8
            for k in range(4):
                v = mem[U + 4 + 4 * r + k]
                if v:
                    d[row + col + k] = d.get(row + col + k, 0) ^ v
        return d

    def check(kind, snap, R, pc):
        if kind == 'isr':
            ret_pc, ret_sp = ISR_SOUND, R[12] - 2          # where the original CALL lands; the hook JPs there
        elif kind in ('plot', 'bub'):
            ret_pc, ret_sp = pc + 3, R[12]
        else:
            ret_pc, ret_sp = snap[R[12]] | snap[R[12] + 1] << 8, R[12] + 2
        regs, P0 = list(R), list(st['P'])
        if collect and stats['collected ' + kind] < collect:
            stats['collected ' + kind] += 1
            states.append((kind, pc, list(snap), regs, P0, st['applied'], st['nr15'],
                           {k: list(v) for k, v in st['attrs'].items()}))
        A.load(snap, regs)
        A.mem.P = list(P0)
        if kind == 'bubble_scope':
            # Prove the new speed wrapper around the already-proved virtual
            # bubble reads. Both sides start with the same player-free picture;
            # each inner read is also compared with the unpatched RZX below.
            baseline = [(a, new) for a, new in sites if a != pc]
            _patched(A, patch, baseline, code, st['applied'], P0, st['nr15'], st['attrs'])
        B.load(snap, regs)
        _patched(B, patch, sites, code, st['applied'], P0, st['nr15'], st['attrs'])
        A.run(ret_pc, ret_sp)
        B.run(ret_pc, ret_sp)
        bad = [i for i in REGS if A.R[i] != B.R[i]]
        dead = range(ret_sp - (128 if kind == 'bubble_scope' else 40), ret_sp)
        md = [a for a in range(0x5800, 65536) if A.mem[a] != B.mem[a] and a not in excl and a not in dead]
        sd = [a for a in range(0x4000, 0x5800) if B.mem[a] != A.mem.P[a - 0x4000]]
        if bad or md or sd:
            if not bad and not sd and all(U <= a < U + 4 + 4 * 32 for a in md) and kind == 'plot' \
                    and any(snap[a] != P0[a - 0x4000] for a in range(0x4000, 0x5800)):
                stats['plot: undo buffer differs (original ghost pixels, harmless)'] += 1
            else:
                stats[kind + ' MISMATCH'] += 1
                if len(log) < 6:
                    log.append((kind, pc, 'regs', bad, 'mem', md[:6], 'screen', sd[:6]))
        else:
            stats[kind + ' ok'] += 1
        if B.nr.get(7, 0) & 3 != 0:
            stats[kind + ' EXIT SPEED MISMATCH'] += 1
        st['applied'] = B.mem[0x5B00]
        st['nr15'] = B.nr.get(0x15, 0)
        st['attrs'] = {k: list(v) for k, v in B.attrs.items()}
        vis = bool(st['nr15'] & 1)
        if kind == 'plot':
            sp = sprite_px(B)
            if hasattr(patch, 'sprite_expected'):
                want = patch.sprite_expected(snap, regs)
                stats['sprite pixel-perfect' if sp == want else 'SPRITE PIXEL MISMATCH'] += 1
                return
            miss = wrong = 0
            for a, v in undo_px(A.mem).items():
                y = _ypix(a)
                x0 = (a & 31) * 8
                for bit in range(8):
                    if (v >> (7 - bit)) & 1 and (x0 + bit, y) not in sp:
                        miss += 1
            for (x, y), c in sp.items():
                a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
                if not (0 <= x < 256 and 0 <= y < 192) or ((A.mem[a] >> (7 - (x & 7))) & 1) != (1 if c == 2 else 0):
                    wrong += 1
            stats['sprite pixel-perfect' if not (miss or wrong) else 'SPRITE PIXEL MISMATCH'] += 1
        elif kind == 'wipe':
            stats[kind + (' hides sprite' if not vis else ' LEAVES SPRITE VISIBLE')] += 1
        elif kind == 'isr' and not st['applied'] and vis:
            stats['ISR: SPRITE VISIBLE WHILE ERASED'] += 1

    ev = {prof['plot_site']: 'plot', prof['eraser']: 'erase', prof['wipe']: 'wipe', prof['isr_hide_call']: 'isr',
          BUBBLE: 'bub'}
    ev.update(getattr(patch, 'extra_events', {}))
    REG = [None]
    last = [None]

    def install(memory):
        base = type(memory)
        MG, MS = base.__getitem__, base.__setitem__
        G0[0] = lambda a: MG(memory, a)

        class W(base):
            def __getitem__(s, a):
                R = REG[0]
                if type(a) is int and R is not None:
                    pc = R[24]
                    if a in ev and pc == a and last[0] != (a, R[25]):
                        last[0] = (a, R[25])
                        if ev[a] == 'wipe' and not st['synced']:
                            st['synced'] = True
                            st['P'] = [MG(s, x) for x in range(0x4000, 0x5800)]
                            st['applied'] = 0
                        if st['synced']:
                            check(ev[a], [MG(s, x) for x in range(65536)], R, a)
                    if PRINTER[0] <= a < PRINTER[1] and a != pc and st['synced']:
                        stats['PRINTER BUFFER READ BY THE GAME (0x5B00-0x5B50: the trampolines)'] += 1
                        if len(log) < 6:
                            log.append(('printer read', hex(a), 'pc', hex(pc)))
                return MG(s, a)

            def __setitem__(s, a, v):
                R = REG[0]
                if R is not None and type(a) is int:
                    if st['synced'] and 0x4000 <= a < 0x5800 and not (lo <= R[24] < hi):
                        apply_write(st['P'], a, MG(s, a), v, classify(_code_list(s, MG, R[24]), R[24]))
                    if PRINTER[0] <= a < PRINTER[1]:
                        stats['PRINTER BUFFER WRITTEN BY THE GAME (0x5B00-0x5B50: the trampolines)'] += 1
                        if len(log) < 6:
                            log.append(('printer write', hex(a), 'pc', hex(R[24])))
                    if a in excl and a not in range(PRINTER[0], PRINTER[1]) and st['synced']:
                        stats['PATCH SITE WRITTEN BY THE GAME'] += 1
                        if len(log) < 6:
                            log.append(('site write', hex(a), 'pc', hex(R[24])))
                MS(s, a, v)
        memory.__class__ = W
        return memory

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            super().__init__(install(memory), registers, state, config)
            REG[0] = self.registers
            st['synced'] = False

    old = (rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else [])
    try:
        rzxplay.main(args + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.Simulator, rzxplay.CSimulator = old
    REG[0] = None
    failed = any(('MISMATCH' in k or 'VISIBLE' in k or 'BY THE GAME' in k) for k in stats)
    return {'passed': not failed and stats['plot ok'] > 0, 'stats': dict(stats), 'examples': log, 'states': states}


_CODE = [0] * 65536


def _code_list(mem, get, pc):
    """analyse.classify reads the writer's code (pc - 24 .. pc) from a plain list: those bytes of the paged view."""
    for x in range(pc - 24, pc + 1):
        _CODE[x & 0xFFFF] = get(mem, x & 0xFFFF)
    return _CODE


def _patched(B, patch, sites, code, applied, P0, nr15, attrs):
    for a, new in sites:
        list.__setitem__(B.mem, slice(a, a + len(new)), list(new))
    cb = getattr(patch, "code_base", PRINTER[0])
    list.__setitem__(B.mem, slice(cb, cb + len(code)), code)
    B.mem[0x5B00] = applied
    list.__setitem__(B.mem, slice(0x4000, 0x5800), P0)
    B.nr[0x15] = nr15
    B.attrs = collections.defaultdict(lambda: [0] * 5, {k: list(v) for k, v in attrs.items()})
    return B


# ---------------------------------------------------------------------------------------------
# The every-site clock matrix, on states the replays captured
# ---------------------------------------------------------------------------------------------

def clock_matrix(patch, states):
    """Each hook (plot, erase, wipe, ISR hide, bubble test) from a captured state, entered at NR 7 = 0-3: the exit
    speed must be the incoming one and the result the same. forced35: the negative control, the plot trampoline's
    NEXTREG 0x50,0xFF (the way back to the game) followed by NEXTREG 7,0 - modelled by clearing NR 7 there."""
    from .hooklib import every_site
    from .verify import _M, REGS
    sites = [(a, new) for a, old, new in patch.sites]
    code = list(patch.code)
    hook = list(patch.hook_page_data) + [0] * (8192 - len(patch.hook_page_data))
    by = {}
    for s in states:
        by.setdefault(s[1], s)

    def run(site, clock):
        kind, pc, snap, regs, P0, applied, nr15, attrs = by[site]
        if kind == 'isr':
            ret_pc, ret_sp = ISR_SOUND, regs[12] - 2
        elif kind in ('plot', 'bub'):
            ret_pc, ret_sp = pc + 3, regs[12]
        else:
            ret_pc, ret_sp = snap[regs[12]] | snap[regs[12] + 1] << 8, regs[12] + 2
        B = _M(False, hook)
        B.load(snap, regs)
        _patched(B, patch, sites, code, applied, P0, nr15, attrs)
        B.nr[7] = clock
        B.run(ret_pc, ret_sp)
        m = bytearray(B.mem[0x4000:0x10000])
        m[LATCH_P - 0x4000] = m[LATCH_B - 0x4000] = 0          # the latches hold the incoming speed by design
        mem = hashlib.md5(bytes(m)).hexdigest()
        return B.nr.get(7, 0) & 3, (tuple(B.R[i] for i in REGS), mem, tuple(sorted((k, tuple(v)) for k, v in B.attrs.items())))
    return every_site(sorted(by), run)


# ---------------------------------------------------------------------------------------------
# auto
# ---------------------------------------------------------------------------------------------

def forced35(patch):
    """The plot wrapper's restore (LD A,(latch) / NEXTREG 7,A) replaced by NEXTREG 7,0 / NOP / NOP: a broken build."""
    n = copy.copy(patch)
    h = bytearray(patch.hook_page_data)
    i = len(DP.HOOKS) + len(patch.table) + 27
    if h[i] != 0x3A or h[i + 3:i + 6] != b'\xED\x92\x07':
        raise ValueError('wrapper layout')
    h[i:i + 6] = b'\xED\x91\x07\x00\x00\x00'
    n.hook_page_data = bytes(h)
    return n


def negatives(patch):
    """Broken builds the verifier must catch: the patterns' nibbles swapped, the hook frame table rotated (Dean's
    controls, runs/dean_rebuild tid_verify.py), and the ISR hook that never hides an erased Dizzy."""
    out = {}
    n = copy.copy(patch)
    b = bytearray(patch.extra_banks[11])
    for i in range(len(b)):
        b[i] = ((b[i] & 15) << 4) | (b[i] >> 4)
    n.extra_banks = dict(patch.extra_banks)
    n.extra_banks[11] = bytes(b)
    out['pattern nibbles swapped'] = n
    n = copy.copy(patch)
    h = bytearray(patch.hook_page_data)
    a, e = len(DP.HOOKS), len(DP.HOOKS) + len(patch.table)
    tab = h[a:e]
    h[a:e] = tab[4:] + tab[:4]
    n.hook_page_data = bytes(h)
    out['hook frame table rotated'] = n
    n = copy.copy(patch)
    t = bytearray(patch.code)
    i = bytes(t).index(bytes.fromhex('ED911500F1C30272'))       # T_ISR: NEXTREG 0x15,0 (sprites off) / POP AF / JP 0x7202
    t[i:i + 4] = b'\x00\x00\x00\x00'
    n.code = bytes(t)
    out['ISR hook never hides Dizzy'] = n
    return out


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : tid128 (Treasure Island Dizzy 128K: Dean\'s dizzy_patch on the 128K release; whole alt ROM image)')
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, None, True, quiet=True)
    bad = boot_check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else
                                                        'MISMATCH %s' % str(bad[:3])[:300], conv[1]))
    patch = TidPatch128()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (%d patterns; tail 0x%04X; printer buffer put back after NEXLOAD)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300], patch.num_patterns,
        conv[1]))
    ok = not bad and not bad2
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    states = []
    total = collections.Counter()
    for r in a.rzx or []:
        v = verify(patch, r, stop=getattr(a, 'quick', None), collect=2)
        states += v['states']
        s = {k: x for k, x in v['stats'].items() if not k.startswith('collected')}
        total.update(s)
        ok = ok and v['passed']
        say('Verify    : %s  %s -> %s %s' % (os.path.basename(r), ', '.join('%s %d' % kv for kv in sorted(s.items())),
                                            'IDENTICAL' if v['passed'] else 'FAILED', str(v['examples'])[:300]))
    if a.rzx:
        miss = [k for k in ('plot ok', 'erase ok', 'wipe ok', 'isr ok', 'bub ok') if not total[k]]
        say('Coverage  : every hook ran: %s' % ('yes' if not miss else 'NO, never: %s' % ', '.join(miss)))
        neg = negatives(patch)
        caught = 0
        for what, n in neg.items():
            v = verify(n, a.rzx[0], stop=getattr(a, 'quick', None) or 6000)
            det = not v['passed']
            caught += det
            say('Negative  : %s -> %s %s' % (what, 'DETECTED' if det else 'NOT DETECTED!',
                                            {k.replace('MISMATCH', 'difference'): x for k, x in v['stats'].items()
                                             if 'MISMATCH' in k or 'VISIBLE' in k}))
        ok = ok and caught == len(neg)
        if states:
            u = unit_tests(patch, states)
            say('Unit      : %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(u.items())),
                                         'PASS' if not any(k.endswith('!') for k in u) else 'FAIL'))
            cm, rows = clock_matrix(patch, states)
            cn, _ = clock_matrix(forced35(patch), states)
            bad = {k: x for k, x in cm.items() if k.endswith('!')}
            c2 = sum(x for k, x in cn.items() if k.endswith('!'))
            st = sorted({r['site'] for r in rows})
            ok = ok and not bad and c2 > 0
            say('Clocks    : every-site matrix, %d hook sites (%s) x 4 incoming clocks = %d cases: exit speed = the '
                'incoming one, result the same at every clock -> %s; negative "forced 3.5 MHz exit" (the plot wrapper\'s '
                'restore) caught at %d cases -> %s' % (len(st), ', '.join('0x%04X' % x for x in st), cm['cases'],
                                                                 'PASS' if not bad else 'FAIL %s' % bad, c2,
                                                                 'DETECTED' if c2 else 'NOT DETECTED!'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
