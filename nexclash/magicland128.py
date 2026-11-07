"""Magicland Dizzy 128K - opt-in rework 'v128' of Dean Woodyatt's generic TID build (Jon Attree, 2026-11-05).

Dean's generic TID-engine patch (nexclash/build.py TidPatch, strategy altrom: the slot1 hook template, his
relocation, sites and pattern build; untouched, still his record's build of the 48K file) applied to the game's
128K release. The 128K file is the same program as the 48K one: banks 5, 2 and 0 (0xC000-0xFFFF in play) hold the
48K game's code byte for byte; the game ISR plays the AY music when its flag (0x728E) is set, CALL 0x9CC9 paging
bank 3 in at 0xC000 (OUT 0x7FFD = 0x13) and bank 0 back (0x10) before the hide call at 0xFF64. ROM 1 throughout.
What this module adds, and nothing else:
  - the detector and apply() for the 128K snapshot (banks 5 / 2 / 0 patched directly);
  - the whole alt ROM image (refactor plan 1): image 1 = Sinclair's 48K ROM + Dean's hooks, table and register block
    at 0x386E (the stub's whole fill), image 0 = the 128K ROM 0 (refactor plan 2; the game never selects it);
  - the start-up tail in the dead stack as Dean's 48K decision (0xA2BD, 60 bytes below SP 0xA2F9), re-measured on
    the 128K recordings (the verifier fails a deeper stack);
  - the hook-speed pass (CODEX-HOOK-SPEED, pace ORIGINAL): Dean's plot hook (the sprite attribute uploads) runs at
    28 MHz between a head that latches the incoming NR 7 speed (kept in the dead stack, EX (SP),HL) and a tail that
    writes it back before JP to the game's plotter, which runs at the game's own speed (card patch.restore-speed).
    His erase, wipe, box and ISR hooks are one to three NEXTREG writes: a speed switch would cost more than they do,
    so they stay as he wrote them (they never touch NR 7; the clock matrix checks them too);
  - a 128K-capable copy of the TID verifier (nexclash/verify.py, which is 48K only), with the box event, the pixel
    test (Dean's analyse: no test may depend on the player's pixels), the alt ROM hook area, patch sites and stack
    depth guarded;
  - the every-site clock matrix and its negative, a forced 3.5 MHz exit.
The game never reads or writes R (no LD A,R / LD R,A runs: the verifier counts them), so R needs no preserving.

    python nexclash.py auto MAGICLAND128.z80 --rzx R1 --rzx R2 --no-record
"""
import collections
import copy
import hashlib
import json
import os

from . import build as B
from .verify import REGS as CMP        # registers compared (verify.py's: all but R, T, MEMPTR)

PROFILE = {'engine': 'tid', 'plotter': 39744, 'eraser': 40059, 'eraser_spsave': 40115, 'eraser_cont': 40064,
           'plotter_writes': [39865, 39876, 39887, 40003, 40014, 40025, 40039], 'eraser_writes': [40087, 40091, 40096, 40100],
           'plot_site': 40445, 'plot_site_kind': 'JP', 'frame_table': 24644, 'frame_base': 24722, 'wipe': 37091,
           'box': 37690, 'isr_hide_call': 65380, 'pixel_test': 41268, 'wipe_ix': 23748, 'wipe_cont': 37095,
           'box_var': 39741, 'box_cont': 37693, 'sound_tick': 37810, 'undo_buffer': 23552, 'ok': True}
TAIL = 0xA2BD               # Dean's decision (record stack_low_water 41661): dead stack below SP 0xA2F9
MUSIC_FLAG = 0x728E         # LD A,(0x728E) / AND A / CALL NZ,0x9CC9 at 0xFF4F: 1 in the 128K release
DECISIONS = {'engine': 'magicland128', 'base': "Dean's generic TID build (build.py TidPatch altrom: template, sites, patterns)",
             'input': 'the 128K release (AY music from bank 3 in the game ISR)',
             'strategy': 'altrom: hooks + table + register block at 0x386E in alt image 1 = Sinclair\'s 48K ROM (whole image); '
                         'image 0 = the 128K ROM 0; tail in the dead stack 0xA2BD; plot hook at 28 MHz, incoming speed restored',
             'stack_low_water': TAIL}
HEAD_LEN, TAILW_LEN = 27, 11


def load_profile():
    """Dean's profile addresses (identify() on the 48K game; the 128K release's banks 5 / 2 / 0 are the same code)."""
    return dict(PROFILE)


def _flat(banks):
    return bytes(banks[5]) + bytes(banks[2]) + bytes(banks[0])


def is_magicland128(snap):
    if snap.machine != '128K':
        return False
    b = snap.memory.banks
    if any(x is None for x in (b[0], b[2], b[5])):
        return False
    ram = _flat(b)
    syms = B.T['slot1']['syms']
    if bytes(ram[0xFF4F - 0x4000:0xFF56 - 0x4000]) != bytes.fromhex('3a8e72a7c4c99c'):
        return False
    return all(ram[a - 0x4000:a - 0x4000 + len(old)] == old for a, old, new in B.tid_sites(PROFILE, syms))


def head(t_plot):
    """Latch NR 7's programmed speed (port 0x243B / 0x253B, bits 1:0), 28 MHz, the latch left on the stack in H
    (EX (SP),HL), every register as it came; JP Dean's plot hook. 27 bytes."""
    return bytes([0xF3, 0xE5, 0xF5, 0xC5, 0x01, 0x3B, 0x24, 0x3E, 0x07, 0xED, 0x79, 0x04, 0xED, 0x78, 0xE6, 0x03,
                  0xED, 0x91, 0x07, 0x03, 0xC1, 0x67, 0xF1, 0xE3, 0xC3, t_plot & 0xFF, t_plot >> 8])


def tailw(plotter):
    """The latched speed back (EX (SP),HL / LD A,H / NEXTREG 7,A), HL and AF as they were; JP the game's plotter.
    11 bytes."""
    return bytes([0xE3, 0xF5, 0x7C, 0xED, 0x92, 0x07, 0xF1, 0xE1, 0xC3, plotter & 0xFF, plotter >> 8])


def printer_back(snap, org, call=None):
    """Stub code at org: [CALL call (Dean's set-up)], the snapshot's 0x5B00-0x5BFF copied back over what NEXLOAD left
    there, RET; the 256 bytes after it. The game keeps its bit-reverse table for mirrored objects there (games/
    magicland_dizzy.md) and reads it before writing it: the ROM path check's printer buffer warning, BRIEFING C2 #36.
    (z80tonex keep_printer_buffer is 48K only.)"""
    c = bytearray(b'\xCD' + bytes([call & 0xFF, call >> 8]) if call is not None else b'')
    src = org + len(c) + 12
    c += bytes([0x21, src & 0xFF, src >> 8, 0x11, 0x00, 0x5B, 0x01, 0x00, 0x01, 0xED, 0xB0, 0xC9])
    return bytes(c) + bytes(snap.banks[5][0x1B00:0x1C00])


class PlainPrinter128(B._PlainCompact):
    """Dean's plain() for this game (compact tail in the dead stack, register block in RAM page 24 at slot 1) + the
    printer buffer put back after NEXLOAD."""
    def __init__(self, sp):
        super().__init__(TAIL, sp - TAIL)
        self.page = bytes(8192)                         # RAM page 24 at slot 1 (the boot check's view of it)
        self.setup_call = B.SETUP_ORG

    def apply(self, snap):
        self.stub_extra = printer_back(snap, B.SETUP_ORG)


class MagiclandPatch128(B.TidPatch):
    """Dean's TidPatch, strategy altrom, on the 128K release; the plot hook through the speed head / tail."""

    def __init__(self):
        super().__init__(dict(PROFILE), 'altrom', TAIL)
        self.name = "Magicland Dizzy 128K: Dizzy hardware sprite (Dean's TID build; whole alt ROM image; plot hook 28 MHz)"
        self.orig_sites = list(self.sites)
        self.dean_code = self.code                                 # Dean's relocated template (apply() starts from it)

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('this rework is for the 128K release')
        if snap.port7ffd & 7 != 0 or not snap.port7ffd & 0x10:
            raise ValueError('expected bank 0 and ROM 1 paged in the snapshot (7FFD 0x%02X)' % snap.port7ffd)
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.orig_sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.max_tail = snap.sp - self.tail_addr
        if self.max_tail < 54:
            raise ValueError('only %d bytes of dead stack below SP 0x%04X for the start-up tail' % (self.max_tail, snap.sp))
        from .sprites import patterns_for
        pats, table, n = patterns_for(lambda a: ram[a - 0x4000], PROFILE['frame_table'], PROFILE['frame_base'])
        self.num_patterns = n
        syms = B.T['slot1']['syms']
        org = B.T['slot1']['org']
        code = bytearray(self.dean_code)
        jp = 0x53                                                  # T_PLOT's JP plotter (fix PLOTTER at 84)
        if code[jp] != 0xC3 or code[jp + 1:jp + 3] != bytes([PROFILE['plotter'] & 0xFF, PROFILE['plotter'] >> 8]):
            raise ValueError("Dean's plot hook does not end JP plotter at +0x53")
        w_head = org + len(code) + len(table)
        w_tail = w_head + HEAD_LEN
        code[jp + 1:jp + 3] = bytes([w_tail & 0xFF, w_tail >> 8])
        self.code = bytes(code)
        self.table = table
        self.w_head, self.w_tail = w_head, w_tail
        body = self.code + table + head(syms['T_PLOT']) + tailw(PROFILE['plotter'])
        ps = PROFILE['plot_site']
        self.sites = [(a, old, (b'\xC3' + bytes([w_head & 0xFF, w_head >> 8])) if a == ps else new)
                      for a, old, new in self.orig_sites]
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        self.page, regblock, self.altrom = B.altrom_image(B.rom48(), org, body)
        self.slot1 = (B.T['slot1']['page'], regblock)
        self.altrom0 = (0x2000, 0x2000)                            # image 0: the 128K ROM 0, no build bytes
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        pats = pats + bytes(-len(pats) % 256)
        if len(pats) < 8192:
            pats = pats + bytes(8192 - len(pats))
        setup = bytearray(B.SETUP)
        setup[B.SETUP_NBLOCKS2_OFF] = (len(pats) - 8192) // 256
        self.setup_call = B.SETUP_ORG + len(setup)
        self.stub_extra = bytes(setup) + printer_back(snap, self.setup_call, B.SETUP_ORG)
        self.extra_banks = {11: pats, 12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# The verifier: nexclash/verify.py for a 128K recording + box, pixel tests, guards
# ---------------------------------------------------------------------------------------------

def _ret(kind, mm, R, pc):
    if kind == 'isr':
        return pc + 3, R[12]
    return mm[R[12]] | mm[R[12] + 1] << 8, R[12] + 2          # JP plot site, eraser, wipe, box: the routine's RET


def _patched(B_, patch, sites, applied, P0, nr15, attrs):
    for a, new in sites:
        list.__setitem__(B_.mem, slice(a, a + len(new)), list(new))
    list.__setitem__(B_.mem, slice(0x2000, 0x4000), list(patch.page))
    B_.nr[0x7F] = applied
    list.__setitem__(B_.mem, slice(0x4000, 0x5800), P0)
    B_.nr[0x15] = nr15
    B_.attrs = collections.defaultdict(lambda: [0] * 5, {k: list(v) for k, v in attrs.items()})
    return B_


def verify(patch, rzx_path, stop=None, collect=0):
    """Differential test at every patched routine (plot site, eraser, wipe, box, ISR hide call): the original and the
    patched code from the same real state; registers, memory, the patched-screen model and the sprite pixels against
    the undo buffer; plus every pixel test against the screen without Dizzy, and guards (patch sites, the alt ROM
    hook area, stack depth, R). collect: states kept per site (clock matrix). -> dict."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .verify import _M, _ypix, REGS
    from .analyse import classify, apply_write
    prof = PROFILE
    U = prof['undo_buffer']
    lo, hi = prof['plotter'], prof['eraser'] + 53
    sites = [(a, new) for a, old, new in patch.sites]
    excl = set()
    for a, new in sites:
        excl.update(range(a, a + len(new)))
    hook = [0] * 8192
    pats = patch.extra_banks[11]
    A, B_ = _M(True, hook), _M(False, hook)
    A.mem.lo, A.mem.hi = lo, hi
    st = {'P': None, 'applied': 0, 'nr15': 0, 'attrs': {}, 'synced': False, 'sp0': None, 'drawn': False}
    stats = collections.Counter()
    log = []
    states = []
    pt = prof['pixel_test']
    PT = {pt + 8: 0xF0, pt + 13: 0x0F}
    HOOKS = (B.ALTROM_HOOKS[0], B.ALTROM_HOOKS[1])

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
        ret_pc, ret_sp = _ret(kind, snap, R, pc)
        regs, P0 = list(R), list(st['P'])
        if collect and stats['collected ' + kind] < collect:
            stats['collected ' + kind] += 1
            states.append((kind, pc, list(snap), regs, P0, st['applied'], st['nr15'],
                           {k: list(v) for k, v in st['attrs'].items()}))
        A.load(snap, regs)
        A.mem.P = list(P0)
        B_.load(snap, regs)
        _patched(B_, patch, sites, st['applied'], P0, st['nr15'], st['attrs'])
        A.run(ret_pc, ret_sp)
        B_.run(ret_pc, ret_sp)
        bad = [i for i in REGS if A.R[i] != B_.R[i]]
        dead = range(ret_sp - 40, ret_sp)
        md = [a for a in range(0x5800, 65536) if A.mem[a] != B_.mem[a] and a not in excl and a not in dead]
        sd = [a for a in range(0x4000, 0x5800) if B_.mem[a] != A.mem.P[a - 0x4000]]
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
        if B_.nr.get(7, 0) & 3 != 0:
            stats[kind + ' EXIT SPEED MISMATCH'] += 1
        st['applied'] = B_.nr.get(0x7F, 0)
        st['nr15'] = B_.nr.get(0x15, 0)
        st['attrs'] = {k: list(v) for k, v in B_.attrs.items()}
        vis = bool(st['nr15'] & 1)
        if kind == 'plot':
            sp = sprite_px(B_)
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
        elif kind in ('box', 'wipe'):
            stats[kind + (' hides sprite' if not vis else ' LEAVES SPRITE VISIBLE')] += 1
        elif kind == 'isr' and not st['applied'] and vis:
            stats['ISR: SPRITE VISIBLE WHILE ERASED'] += 1

    ev = {prof['plot_site']: 'plot', prof['eraser']: 'erase', prof['wipe']: 'wipe', prof['isr_hide_call']: 'isr',
          prof['box']: 'box'}
    REG = [None]
    MEM = [None]
    WR = bytearray(1024)
    LASTW = {}
    last = [None]

    def flat():
        m = MEM[0].memory
        return list(m[0]) + list(m[1]) + list(m[2]) + list(m[3])

    def install(memory):
        base = type(memory)
        MG, MS = base.__getitem__, base.__setitem__
        MEM[0] = memory

        class W(base):
            def __getitem__(s, a):
                R = REG[0]
                if type(a) is int and R is not None:
                    pc = R[24]
                    if a == pc:
                        if a in ev and last[0] != (a, R[25]):
                            last[0] = (a, R[25])
                            if ev[a] == 'wipe' and not st['synced']:
                                st['synced'] = True
                                st['P'] = [MG(s, x) for x in range(0x4000, 0x5800)]
                                st['applied'] = 0
                            if st['synced']:
                                check(ev[a], flat(), R, a)
                                if ev[a] in ('plot', 'erase'):
                                    st['drawn'] = ev[a] == 'plot'
                        elif MG(s, a) == 0xED and MG(s, (a + 1) & 0xFFFF) in (0x5F, 0x4F):
                            stats['R READ OR WRITTEN BY THE GAME (LD A,R / LD R,A)'] += 1
                    elif st['synced']:
                        if a < 0x4000:
                            stats['ROM data reads'] += 1
                            if HOOKS[0] <= a < HOOKS[1]:
                                stats['ALT ROM HOOK AREA READ BY THE GAME'] += 1
                        elif a < 0x5800 and not (lo <= pc < hi):
                            if pc in PT:
                                m = PT[pc]
                                stats['pixel tests'] += 1
                                if bool(MG(s, a) & m) != bool(st['P'][a - 0x4000] & m):
                                    stats['PIXEL TESTS THAT DEPEND ON THE PLAYER'] += 1
                                    if len(log) < 6:
                                        log.append(('pixel test', hex(a), 'pc', hex(pc), 'screen %02X model %02X' % (
                                            MG(s, a), st['P'][a - 0x4000]), 'Dizzy drawn' if st['drawn'] else 'Dizzy erased',
                                            'caller %04X' % (MG(s, R[12]) | MG(s, R[12] + 1) << 8), 'last writers %s' % (LASTW.get(a),)))
                            elif MG(s, a) != st['P'][a - 0x4000]:
                                stats['screen reads where Dizzy is drawn (pc %04X)' % pc] += 1
                    if a < 0x4000 and a == pc and st['synced']:
                        stats['ROM CODE RUN BY THE GAME'] += 1
                return MG(s, a)

            def __setitem__(s, a, v):
                R = REG[0]
                if R is not None and type(a) is int:
                    if 0x4000 <= a < 0x5800:
                        LASTW[a] = (LASTW.get(a, ()) + ('%04X:%02X>%02X' % (R[24], MG(s, a), v),))[-4:]
                    if st['synced'] and 0x4000 <= a < 0x5800 and not (lo <= R[24] < hi):
                        apply_write(st['P'], a, MG(s, a), v, classify(_code_list(s, MG, R[24]), R[24]))
                    if st['sp0'] - 1024 <= a < st['sp0']:
                        WR[a - st['sp0'] + 1024] = 1
                    if a in excl and st['synced']:
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
            if st['sp0'] is None:
                st['sp0'] = self.registers[12]

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
    low, a, gap = st['sp0'], st['sp0'] - 1, 0          # stack low-water mark (analyse's: contiguous writes below SP)
    while a > st['sp0'] - 1024 and gap < 8:
        if WR[a - st['sp0'] + 1024]:
            low, gap = a, 0
        else:
            gap += 1
        a -= 1
    stats['stack low water 0x%04X' % low] += 1
    if low < patch.tail_addr:
        stats['STACK BELOW THE TAIL ADDRESS'] += 1
    failed = any(_bad(k) for k in stats)
    return {'passed': not failed and stats['plot ok'] > 0, 'stats': dict(stats), 'examples': log, 'states': states}


def _bad(k):
    return any(w in k for w in ('MISMATCH', 'VISIBLE', 'BY THE GAME', 'DEPEND', 'BELOW'))


_CODE = [0] * 65536


def _code_list(mem, get, pc):
    """analyse.classify reads the writer's code (pc - 24 .. pc) from a plain list: those bytes of the paged view."""
    for x in range(pc - 24, pc + 1):
        _CODE[x & 0xFFFF] = get(mem, x & 0xFFFF)
    return _CODE


# ---------------------------------------------------------------------------------------------
# The every-site clock matrix, on states the replays captured
# ---------------------------------------------------------------------------------------------

def clock_matrix(patch, states):
    """Each hook (plot, erase, wipe, box, ISR hide) from a captured state, entered at NR 7 = 0-3: the exit speed
    must be the incoming one and the result the same (registers, memory outside the dead stack the head's latch
    sits in, the sprite layer)."""
    from .hooklib import every_site
    from .verify import _M, REGS
    sites = [(a, new) for a, old, new in patch.sites]
    by = {}
    for s in states:
        by.setdefault(s[1], s)

    def run(site, clock):
        kind, pc, snap, regs, P0, applied, nr15, attrs = by[site]
        ret_pc, ret_sp = _ret(kind, snap, regs, pc)
        B_ = _M(False, [0] * 8192)
        B_.load(snap, regs)
        _patched(B_, patch, sites, applied, P0, nr15, attrs)
        B_.nr[7] = clock
        B_.run(ret_pc, ret_sp)
        m = bytearray(B_.mem[0x4000:0x10000])
        for a in range(ret_sp - 40, ret_sp):
            m[a - 0x4000] = 0
        mem = hashlib.md5(bytes(m)).hexdigest()
        nr = tuple(sorted((k, v) for k, v in B_.nr.items() if k != 7))
        return B_.nr.get(7, 0) & 3, (tuple(B_.R[i] for i in REGS), mem, nr,
                                     tuple(sorted((k, tuple(v)) for k, v in B_.attrs.items())))
    return every_site(sorted(by), run)


def forced35(patch):
    """The tail's restore (LD A,H / NEXTREG 7,A) replaced by NEXTREG 7,0: a broken build."""
    n = copy.copy(patch)
    page = bytearray(patch.page)
    i = patch.w_tail - 0x2000 + 2
    if page[i:i + 4] != b'\x7C\xED\x92\x07':
        raise ValueError('speed tail layout')
    page[i:i + 4] = b'\xED\x91\x07\x00'
    n.page = bytes(page)
    return n


def unit_tests(patch, states):
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


def _page_edit(patch, find, repl, what):
    n = copy.copy(patch)
    page = bytearray(patch.page)
    i = bytes(page).find(find, B.T['slot1']['org'] - 0x2000)
    if i < 0:
        raise ValueError(what)
    page[i:i + len(repl)] = repl
    n.page = bytes(page)
    return n


def negatives(patch):
    """Broken builds the verifier must catch: the patterns' nibbles swapped, the hook frame table rotated (Dean's
    controls, runs/dean_rebuild tid_verify.py), the ISR hook that never hides an erased Dizzy, the wipe and box hooks
    that leave him visible."""
    out = {}
    n = copy.copy(patch)
    b = bytearray(patch.extra_banks[11])
    for i in range(len(b)):
        b[i] = ((b[i] & 15) << 4) | (b[i] >> 4)
    n.extra_banks = dict(patch.extra_banks)
    n.extra_banks[11] = bytes(b)
    out['pattern nibbles swapped'] = n
    n = copy.copy(patch)
    page = bytearray(patch.page)
    t0 = B.T['slot1']['syms']['table'] - 0x2000
    tab = page[t0:t0 + len(patch.table)]
    page[t0:t0 + len(patch.table)] = tab[8:] + tab[:8]
    n.page = bytes(page)
    out['hook frame table rotated'] = n
    out['ISR hook never hides Dizzy'] = _page_edit(patch, bytes.fromhex('ED911500C1F1C3'), b'\x00\x00\x00\x00', 'T_ISR')
    out['wipe hook leaves Dizzy visible'] = _page_edit(patch, bytes.fromhex('ED911500DD21'), b'\x00\x00\x00\x00', 'T_WIPE')
    out['box hook leaves Dizzy visible'] = _page_edit(patch, bytes.fromhex('ED9115003A'), b'\x00\x00\x00\x00', 'T_BOX')
    n = _page_edit(patch, bytes.fromhex('ED911500C1F1C3'), b'\x00\x00\x00\x00', 'T_ISR')
    out['ISR and wipe hooks never hide Dizzy'] = _page_edit(n, bytes.fromhex('ED911500DD21'), b'\x00\x00\x00\x00', 'T_WIPE')
    return out


# ---------------------------------------------------------------------------------------------
# auto
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : magicland128 (Magicland Dizzy 128K: Dean\'s generic TID build on the 128K release; whole alt ROM image)')
    plain = os.path.join(out, name + '.nex')
    sp = zt.Z80Snapshot(z80).sp
    pc_ = PlainPrinter128(sp)
    conv = zt.convert(z80, plain, None, True, quiet=True, patch=pc_)
    bad = check(plain, z80, pc_, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else
                                                        'MISMATCH %s' % str(bad[:3])[:300], conv[1]))
    patch = MagiclandPatch128()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Sprites   : %s  %s  boot %s  (%d patterns; tail 0x%04X, %d bytes)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300], patch.num_patterns,
        conv[1], len(conv[2])))
    ok = not bad and not bad2
    say('Boot      : simulated stub + alt ROM fill + tail, printer buffer as NEXLOAD leaves it: %s' % (
        'OK (registers, RAM, ROM view, paging, $8C; plain and sprites)' if ok else 'MISMATCH %s' % str((bad + bad2)[:3])[:300]))
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
        miss = [k for k in ('plot ok', 'erase ok', 'wipe ok', 'isr ok', 'box ok', 'pixel tests') if not total[k]]
        say('Coverage  : every hook ran: %s' % ('yes' if not miss else 'NO, never: %s' % ', '.join(miss)))
        ok = ok and not miss
        neg = negatives(patch)
        caught = 0
        for what, n in neg.items():
            for r in a.rzx:                              # each recording in turn until one catches it
                v = verify(n, r, stop=getattr(a, 'quick', None))
                det = not v['passed']
                if det:
                    break
            caught += det
            say('Negative  : %s -> %s %s' % (what, ('DETECTED by %s' % os.path.basename(r)) if det else 'NOT DETECTED!',
                                            {k: x for k, x in v['stats'].items() if _bad(k)}))
        ok = ok and caught == len(neg)
        if states:
            u = unit_tests(patch, states)
            cm, rows = clock_matrix(patch, states)
            cn, _ = clock_matrix(forced35(patch), states)
            badc = {k: x for k, x in cm.items() if k.endswith('!')}
            c2 = sum(x for k, x in cn.items() if k.endswith('!'))
            st = sorted({r['site'] for r in rows})
            ok = ok and not badc and c2 > 0 and not any(k.endswith('!') for k in u)
            say('Clocks    : every-site matrix, %d hook sites (%s) x 4 incoming clocks = %d cases: exit speed = the '
                'incoming one, result the same at every clock -> %s; negative "forced 3.5 MHz exit" (the plot hook\'s '
                'restore) caught at %d cases -> %s' % (len(st), ', '.join('0x%04X' % x for x in st), cm['cases'],
                                                       'PASS' if not badc else 'FAIL %s' % badc, c2,
                                                       'DETECTED' if c2 else 'NOT DETECTED!'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
