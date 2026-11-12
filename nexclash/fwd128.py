"""Fantasy World Dizzy 128K - opt-in rework 'v128' of Dean Woodyatt's generic TID build of Fantasy World Dizzy (Jon
Attree, 2026-11-05).

Dean's generic TID builder (nexclash/build.py TidPatch, templates.json 'slot1' hooks, identify.py's profile; untouched,
still his record's build of the 48K snapshot) applied to the game's 128K release, whose interrupt handler plays the AY
music from bank 3 (0x6176 pages it in: CALL 0xC003). The 48K-128K program is one program: identify() finds the same
profile in banks 5, 2 and 0 as in Dean's 48K snapshot, and every patch site holds the same bytes. What this module adds,
and nothing else:
  - the detector and apply() for the 128K snapshot (banks 5 / 2 / 0 patched; bank 0 is paged at 0xC000 in play);
  - the start-up tail and a speed latch in the printer buffer 0x5B00-0x5BFF, which on a 128K machine holds ROM 0's
    paging routines this game never calls: the verifier fails any read or write of it by the game (Dean's 48K build
    used the zeroed buffer the same way); the alt ROM hooks at 0x386E as Dean's, in the whole alt ROM image: the
    build's own complete image 1 (Sinclair's ROM + the hook bytes, in bank 12, as tid128 and Cauldron: no bank 47);
  - a 128K-capable copy of the generic TID verifier (nexclash/verify.py, which is 48K only) that ends the interrupt event
    where the hook hands over to the sound routine 0x6176 (which pages bank 3: both runs are the same from there),
    fails any bank paging inside an event, the alt ROM hook bytes read by the game, and a hook exit at another speed;
  - the hook-speed pass (CODEX-HOOK-SPEED, pace ORIGINAL): the plot site goes to a wrapper that latches the incoming
    speed (NR 7 bits 1:0), runs Dean's plot hook (four sprites' attributes) at 28 MHz and writes the latched speed back
    before it hands over to the game's own plotter, which keeps its own speed (card patch.restore-speed). The other
    four hooks (erase, wipe, ISR hide, box) are one to three NEXTREGs each, shorter than a speed switch: they never
    touch NR 7 and run at the incoming clock;
  - the every-site clock matrix and its negative, a forced 3.5 MHz exit.

    python nexclash.py auto FWD128.z80 --rzx R1 --rzx R2 --no-record
"""
import collections
import copy
import hashlib
import json
import os

from . import build as B
from .identify import identify
from .sprites import patterns_for
from .verify import REGS as CMP        # registers compared (verify.py's: all but R, T, MEMPTR)

SOUND_TICK = 0x6176         # CALL 24950 at 0xF8ED in the game ISR: pages bank 3, CALL 0xC003 (the AY player)
PRINTER = (0x5B00, 0x5C00)  # 128K ROM 0's paging routines: the tail at 0x5B00, the latch at 0x5BFF; game access fails
LATCH = 0x5BFF
FWD = {'plotter': 56705, 'plot_site': 63940, 'eraser': 57020, 'wipe': 61865, 'box': 62343, 'isr_hide_call': 63725,
       'frame_table': 57183, 'undo_buffer': 57083}
DECISIONS = {'engine': 'fwd128', 'base': "Dean's generic TID build (build.TidPatch, templates.json slot1 hooks, identify's "
             "profile)", 'input': 'the 128K release (AY music from bank 3 in the game ISR)',
             'strategy': 'altrom: hooks at 0x386E in alt ROM image 1 (Sinclair\'s ROM + the hook bytes); tail at 0x5B00 '
                         'and the speed latch at 0x5BFF in the printer buffer the game never touches; plot hook at 28 MHz'}


def _flat(banks):
    return [0] * 0x4000 + list(banks[5]) + list(banks[2]) + list(banks[0])


def is_fwd128(snap):
    if snap.machine != '128K':
        return False
    prof = identify(_flat(snap.memory.banks))
    return bool(prof.get('ok')) and prof.get('engine') == 'tid' and all(prof.get(k) == v for k, v in FWD.items())


def load_profile(snap):
    return identify(_flat(snap.banks if hasattr(snap, 'banks') else snap.memory.banks))


def _wrap_plot(t_plot):
    """DI, latch NR 7's programmed speed (port 0x243B / 0x253B, bits 1:0), NEXTREG 7,3, JP Dean's plot hook. Keeps
    every register and flag; 4 bytes of stack. 27 bytes."""
    return bytes([0xF3, 0xF5, 0xC5, 0x01, 0x3B, 0x24, 0x3E, 0x07, 0xED, 0x79, 0x04, 0xED, 0x78, 0xE6, 0x03,
                  0x32, LATCH & 0xFF, LATCH >> 8, 0xED, 0x91, 0x07, 0x03, 0xC1, 0xF1, 0xC3, t_plot & 0xFF, t_plot >> 8])


def _wrap_exit(plotter):
    """The latched speed back, then the game's plotter (Dean's hook ended JP plotter). 11 bytes."""
    return bytes([0xF5, 0x3A, LATCH & 0xFF, LATCH >> 8, 0xED, 0x92, 0x07, 0xF1, 0xC3, plotter & 0xFF, plotter >> 8])


EXIT_RESTORE = 1            # offset of LD A,(latch) / NEXTREG 7,A in _wrap_exit (forced35 replaces it)
JP_PLOTTER = 83             # offset of T_PLOT's JP PLOTTER in templates.json slot1 'patch' (fix PLOTTER [84])


class FwdPatch128(B.TidPatch):
    name = 'Fantasy World Dizzy 128K: Dizzy hardware sprite (Dean\'s generic TID build; plot hook at 28 MHz)'

    def __init__(self, prof):
        super().__init__(prof, 'altrom', 0x5B00)
        self.uses_printer_buffer = False
        if bytes(self.code[JP_PLOTTER:JP_PLOTTER + 3]) != b'\xC3' + B._w(prof['plotter']):
            raise ValueError("Dean's slot1 template: T_PLOT does not end JP plotter at offset %d" % JP_PLOTTER)

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('this rework is for the 128K release')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        orig = [(a, old) for a, old, new in self.sites]
        for a, old in orig:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.max_tail = LATCH - 0x5B00
        pats, table, n = patterns_for(lambda a: ram[a - 0x4000], self.prof['frame_table'], self.prof['frame_base'])
        self.num_patterns = n
        self.table = table
        org = B.T['slot1']['org']
        w_plot = org + len(self.code) + len(table)
        w_exit = w_plot + 27
        code = bytearray(self.code)
        code[JP_PLOTTER + 1:JP_PLOTTER + 3] = B._w(w_exit)          # Dean's T_PLOT ends in the speed restore
        self.code = bytes(code)
        self.w_plot, self.w_exit = w_plot, w_exit
        self.wrap = _wrap_plot(self.syms['T_PLOT']) + _wrap_exit(self.prof['plotter'])
        site = self.prof['plot_site']
        self.sites = [(a, old, (bytes([new[0]]) + B._w(w_plot)) if a == site else new) for a, old, new in self.sites]
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        self.page, regblock, self.altrom = B.altrom_image(B.rom48(), org, self.code + table + self.wrap)
        self.hooks = self.altrom                                      # (lo, hi): the hook bytes in the image
        self.altrom = (0x2000, 0x4000)                                # the build's own complete image 1 (as tid128,
        self.altrom_low = (B.T['slot1']['page'] + 1, B.rom48()[0:0x2000])   # Cauldron): no bank 47, so a loading
        self.slot1 = (B.T['slot1']['page'], regblock)                 # screen's stub bank can follow bank 12
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        pats = pats + bytes(-len(pats) % 256)
        if len(pats) < 8192:
            pats = pats + bytes(8192 - len(pats))
        setup = bytearray(B.SETUP)
        setup[B.SETUP_NBLOCKS2_OFF] = (len(pats) - 8192) // 256
        self.stub_extra = bytes(setup)
        self.extra_banks = {11: pats, 12: self.page + self.altrom_low[1]}


# ---------------------------------------------------------------------------------------------
# The verifier: nexclash/verify.py for a 128K recording
# ---------------------------------------------------------------------------------------------

def verify(prof, patch, rzx_path, stop=None, collect=0):
    """Differential test at every patched routine (plot site, eraser, wipe, ISR hide call, box): the original and the
    patched code from the same real state; registers, memory, the patched-screen model and the sprite pixels against the
    undo buffer, the exit speed. collect: states kept per kind (clock matrix). -> dict."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .verify import _M, _ypix, REGS
    from .analyse import classify, apply_write
    U = prof['undo_buffer']
    lo, hi = prof['plotter'], prof['eraser'] + 53
    sites = [(a, new) for a, old, new in patch.sites]
    excl = set()
    for a, new in sites:
        excl.update(range(a, a + len(new)))
    excl.update(range(PRINTER[0], PRINTER[1]))
    page = list(patch.page)
    hook = [0] * 8192
    pats = patch.extra_banks[11]
    A, Bm = _M(True, hook), _M(False, hook)
    A.mem.lo, A.mem.hi = lo, hi
    st = {'P': None, 'applied': 0, 'nr15': 0, 'attrs': {}, 'synced': False}
    stats = collections.Counter()
    log = []
    states = []
    paged = [0]
    for m in (A, Bm):
        _count_paging(m, paged)

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
        ret_pc, ret_sp = _ret(kind, snap, R)
        if kind == 'isr' and not st['applied']:
            stats['isr: hide path (Dizzy erased, not yet plotted)'] += 1
            if st['nr15'] & 1:
                stats['isr: hide path with Dizzy still shown (the hook hides him)'] += 1
        regs, P0 = list(R), list(st['P'])
        if collect and stats['collected ' + kind] < collect:
            stats['collected ' + kind] += 1
            states.append((kind, pc, list(snap), regs, P0, st['applied'], st['nr15'],
                           {k: list(v) for k, v in st['attrs'].items()}))
        A.load(snap, regs)
        A.mem.P = list(P0)
        Bm.load(snap, regs)
        _patched(Bm, sites, page, st['applied'], P0, st['nr15'], st['attrs'])
        p0 = paged[0]
        A.run(ret_pc, ret_sp)
        Bm.run(ret_pc, ret_sp)
        if paged[0] != p0:
            stats['BANK PAGED INSIDE AN EVENT (' + kind + ')'] += 1
        bad = [i for i in REGS if A.R[i] != Bm.R[i]]
        dead = range(ret_sp - 40, ret_sp)
        md = [a for a in range(0x5800, 65536) if A.mem[a] != Bm.mem[a] and a not in excl and a not in dead]
        sd = [a for a in range(0x4000, 0x5800) if Bm.mem[a] != A.mem.P[a - 0x4000]]
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
        if Bm.nr.get(7, 0) & 3 != 0:
            stats[kind + ' EXIT SPEED MISMATCH'] += 1
        st['applied'] = Bm.nr.get(0x7F, 0)
        st['nr15'] = Bm.nr.get(0x15, 0)
        st['attrs'] = {k: list(v) for k, v in Bm.attrs.items()}
        vis = bool(st['nr15'] & 1)
        if kind == 'plot':
            sp = sprite_px(Bm)
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
    hooks_lo, hooks_hi = patch.hooks
    REG = [None]
    last = [None]

    def install(memory):
        base = type(memory)
        MG, MS = base.__getitem__, base.__setitem__

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
                    if PRINTER[0] <= a < PRINTER[1]:
                        stats['PRINTER BUFFER READ BY THE GAME (0x5B00-0x5BFF: the tail, the latch)'] += 1
                        if len(log) < 6:
                            log.append(('printer read', hex(a), 'pc', hex(pc)))
                    elif hooks_lo <= a < hooks_hi:
                        stats['ALT ROM HOOK BYTES READ BY THE GAME'] += 1
                        if len(log) < 6:
                            log.append(('hook range read', hex(a), 'pc', hex(pc)))
                return MG(s, a)

            def __setitem__(s, a, v):
                R = REG[0]
                if R is not None and type(a) is int:
                    if st['synced'] and 0x4000 <= a < 0x5800 and not (lo <= R[24] < hi):
                        apply_write(st['P'], a, MG(s, a), v, classify(_code_list(s, MG, R[24]), R[24]))
                    if PRINTER[0] <= a < PRINTER[1]:
                        stats['PRINTER BUFFER WRITTEN BY THE GAME (0x5B00-0x5BFF: the tail, the latch)'] += 1
                        if len(log) < 6:
                            log.append(('printer write', hex(a), 'pc', hex(R[24])))
                    if a in excl and not PRINTER[0] <= a < PRINTER[1]:
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
    failed = any(('MISMATCH' in k or 'VISIBLE' in k or 'BY THE GAME' in k or 'PAGED' in k) for k in stats)
    return {'passed': not failed and stats['plot ok'] > 0, 'stats': dict(stats), 'examples': log, 'states': states}


def _count_paging(m, paged):
    """Wrap a verify._M's port tracer: a write to 0x7FFD (bank paging) counts in paged[0]."""
    tr = m.sim.tracer
    wp = tr.write_port

    class T2:
        def read_port(s, regs, port):
            return tr.read_port(regs, port)

        def write_port(s, regs, port, value, *x):
            if port & 0x8002 == 0:
                paged[0] += 1
            return wp(regs, port, value, *x)
    m.sim.set_tracer(T2())


def _ret(kind, snap, R):
    if kind == 'isr':
        return SOUND_TICK, R[12] - 2          # where the original CALL lands; the hook JPs there
    return snap[R[12]] | snap[R[12] + 1] << 8, R[12] + 2      # JP plotter / CALLed eraser, wipe, box: their RET


_CODE = [0] * 65536


def _code_list(mem, get, pc):
    """analyse.classify reads the writer's code (pc - 24 .. pc) from a plain list: those bytes of the paged view."""
    for x in range(pc - 24, pc + 1):
        _CODE[x & 0xFFFF] = get(mem, x & 0xFFFF)
    return _CODE


def _patched(Bm, sites, page, applied, P0, nr15, attrs):
    for a, new in sites:
        list.__setitem__(Bm.mem, slice(a, a + len(new)), list(new))
    list.__setitem__(Bm.mem, slice(0x2000, 0x4000), page)
    Bm.nr[0x7F] = applied
    list.__setitem__(Bm.mem, slice(0x4000, 0x5800), P0)
    Bm.nr[0x15] = nr15
    Bm.attrs = collections.defaultdict(lambda: [0] * 5, {k: list(v) for k, v in attrs.items()})
    return Bm


# ---------------------------------------------------------------------------------------------
# The every-site clock matrix, on states the replays captured
# ---------------------------------------------------------------------------------------------

def clock_matrix(patch, states):
    """Each hook (plot, erase, wipe, ISR hide, box) from a captured state, entered at NR 7 = 0-3: the exit speed must
    be the incoming one and the result the same."""
    from .hooklib import every_site
    from .verify import _M, REGS
    sites = [(a, new) for a, old, new in patch.sites]
    page = list(patch.page)
    by = {}
    for s in states:
        by.setdefault(s[1], s)

    def run(site, clock):
        kind, pc, snap, regs, P0, applied, nr15, attrs = by[site]
        ret_pc, ret_sp = _ret(kind, snap, regs)
        Bm = _M(False, [0] * 8192)
        Bm.load(snap, regs)
        _patched(Bm, sites, page, applied, P0, nr15, attrs)
        Bm.nr[7] = clock
        Bm.run(ret_pc, ret_sp)
        m = bytearray(Bm.mem[0x4000:0x10000])
        m[LATCH - 0x4000] = 0                       # the latch holds the incoming speed by design
        mem = hashlib.md5(bytes(m)).hexdigest()
        nr = tuple(sorted((k, v) for k, v in Bm.nr.items() if k != 7))
        return Bm.nr.get(7, 0) & 3, (tuple(Bm.R[i] for i in REGS), mem, nr,
                                     tuple(sorted((k, tuple(v)) for k, v in Bm.attrs.items())))
    return every_site(sorted(by), run)


def forced35(patch):
    """The plot wrapper's restore (LD A,(latch) / NEXTREG 7,A) replaced by NEXTREG 7,0 / NOP / NOP: a broken build."""
    n = copy.copy(patch)
    pg = bytearray(patch.page)
    i = patch.w_exit - 0x2000 + EXIT_RESTORE
    if pg[i] != 0x3A or pg[i + 3:i + 6] != b'\xED\x92\x07':
        raise ValueError('wrapper layout')
    pg[i:i + 6] = b'\xED\x91\x07\x00\x00\x00'
    n.page = bytes(pg)
    return n


def unit_tests(patch, states):
    """The paths a replay checks only from its own clock: every hook site from a captured state at all four incoming
    clocks (clock_matrix), and its negative control, a forced 3.5 MHz exit, which must fail. -> Counter."""
    cm, rows = clock_matrix(patch, states)
    c = collections.Counter({'clock cases': cm['cases']})
    for k, v in cm.items():
        if k.endswith('!'):
            c[k] += v
    cn, _ = clock_matrix(forced35(patch), states)
    caught = sum(v for k, v in cn.items() if k.endswith('!'))
    c['negative control forced 3.5 MHz exit caught' if caught else 'negative control forced 3.5 MHz exit not caught!'] += caught or 1
    return c


def negatives(patch):
    """Broken builds the verifier must catch: the patterns' nibbles swapped, the hook frame table rotated, the ISR hook
    that never hides an erased Dizzy (caught only if a recording interrupts between an erase and its plot), the wipe
    hook that never hides him. The forced 3.5 MHz exit is the clock matrix's negative (a replay enters at 3.5 MHz)."""
    out = {}
    n = copy.copy(patch)
    b = bytearray(patch.extra_banks[11])
    for i in range(len(b)):
        b[i] = ((b[i] & 15) << 4) | (b[i] >> 4)
    n.extra_banks = dict(patch.extra_banks)
    n.extra_banks[11] = bytes(b)
    out['pattern nibbles swapped'] = n
    n = copy.copy(patch)
    pg = bytearray(patch.page)
    a = patch.syms['table'] - 0x2000
    e = a + len(patch.table)
    tab = pg[a:e]
    pg[a:e] = tab[8:] + tab[:8]
    n.page = bytes(pg)
    out['hook frame table rotated'] = n
    n = copy.copy(patch)
    pg = bytearray(patch.page)
    i = patch.syms['T_ISR'] - 0x2000
    j = bytes(pg[i:i + 32]).index(b'\xED\x91\x15\x00')       # T_ISR: NEXTREG 0x15,0 (sprites off) when not applied
    pg[i + j:i + j + 4] = b'\x00\x00\x00\x00'
    n.page = bytes(pg)
    out['ISR hook never hides Dizzy'] = n
    n = copy.copy(patch)
    pg = bytearray(patch.page)
    i = patch.syms['T_WIPE'] - 0x2000
    j = bytes(pg[i:i + 16]).index(b'\xED\x91\x15\x00')      # T_WIPE: NEXTREG 0x15,0 (sprites off)
    pg[i + j:i + j + 4] = b'\x00\x00\x00\x00'
    n.page = bytes(pg)
    out['wipe hook never hides Dizzy'] = n
    return out


# ---------------------------------------------------------------------------------------------
# auto
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check as boot_check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : fwd128 (Fantasy World Dizzy 128K: Dean\'s generic TID build on the 128K release; whole alt ROM '
        'image; plot hook at 28 MHz)')
    s = zt.Z80Snapshot(z80)
    prof = load_profile(s)
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, 0x5B00, True, quiet=True)
    bad = boot_check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else
                                                        'MISMATCH %s' % str(bad[:3])[:300], conv[1]))
    patch = FwdPatch128(prof)
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (%d patterns; tail 0x%04X-0x%04X; hooks 0x%04X-0x%04X)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300], patch.num_patterns,
        conv[1], conv[1] + len(conv[2]) - 1, patch.hooks[0], patch.hooks[1] - 1))
    ok = not bad and not bad2
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    states = []
    total = collections.Counter()
    for r in a.rzx or []:
        v = verify(prof, patch, r, stop=getattr(a, 'quick', None), collect=2)
        states += v['states']
        s_ = {k: x for k, x in v['stats'].items() if not k.startswith('collected')}
        total.update(s_)
        ok = ok and v['passed']
        say('Verify    : %s  %s -> %s %s' % (os.path.basename(r), ', '.join('%s %d' % kv for kv in sorted(s_.items())),
                                            'IDENTICAL' if v['passed'] else 'FAILED', str(v['examples'])[:300]))
    if a.rzx:
        miss = [k for k in ('plot ok', 'erase ok', 'wipe ok', 'isr ok', 'box ok') if not total[k]]
        say('Coverage  : every hook ran: %s' % ('yes' if not miss else 'NO, never: %s' % ', '.join(miss)))
        ok = ok and not miss
        neg = negatives(patch)
        caught = 0
        for what, n in neg.items():
            for r in a.rzx:                     # each recording in turn until one catches it (the ISR hook hides a
                v = verify(prof, n, r, stop=getattr(a, 'quick', None))   # shown Dizzy only in some: walk2's 4 times)
                det = not v['passed']
                if det:
                    break
            caught += det
            say('Negative  : %s -> %s %s' % (what, 'DETECTED on %s' % os.path.basename(r) if det else 'NOT DETECTED!',
                                            {k.replace('MISMATCH', 'difference'): x for k, x in v['stats'].items()
                                             if 'MISMATCH' in k or 'VISIBLE' in k}))
            # 'difference' (as tid128.py): a report holding MISMATCH fails the run (nexclash.py _finish, userflow, nxcout,
            # selftest), and these are the broken build's counters, wanted: auto exited 1 with Result PASSED
        ok = ok and caught == len(neg)
        if states:
            u = unit_tests(patch, states)
            say('Unit      : %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(u.items())),
                                         'PASS' if not any(k.endswith('!') for k in u) else 'FAIL'))
            cm, rows = clock_matrix(patch, states)
            cn, _ = clock_matrix(forced35(patch), states)
            badc = {k: x for k, x in cm.items() if k.endswith('!')}
            c2 = sum(x for k, x in cn.items() if k.endswith('!'))
            sts = sorted({r['site'] for r in rows})
            ok = ok and not badc and c2 > 0
            say('Clocks    : every-site matrix, %d hook sites (%s) x 4 incoming clocks = %d cases: exit speed = the '
                'incoming one, result the same at every clock -> %s; negative "forced 3.5 MHz exit" (the plot wrapper\'s '
                'restore) caught at %d cases -> %s' % (len(sts), ', '.join('0x%04X' % x for x in sts), cm['cases'],
                                                                 'PASS' if not badc else 'FAIL %s' % badc, c2,
                                                                 'DETECTED' if c2 else 'NOT DETECTED!'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
