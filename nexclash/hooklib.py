"""The shared hook library for NEW engines - the Python half (refactor plan 26, option 1; Dean's rule 2026-11-04).

asm/lib/hlib_*.asm hold the hook code a new engine INCLUDEs (`INCLUDE "lib/hlib_speed.asm"` from
asm/<engine>_hooks.asm; list them in the record's `shared_data`: FILES). This module holds the tools the
engine's own verifier calls - verifiers stay per engine (CLAUDE.md), these are parts they use:

  NextModel(sim, speed)   NextRegs, sprite ports and the video line for a hook simulator: NR 7 read as the
                          core composes it, time at the current clock, pattern RAM + sprite attributes, the
                          display checks ('upload into a shown pattern!', burst_ok)
  every_site(sites, run)  the every-site matrix: each hook at all four incoming clocks (exit speed = the
                          incoming one, nothing else depends on it)
  CMP_R, r_span, r_delta, r_check     preserving R (card patch.preserve-r)
  lines16, pace_check     the pace limiter's target and its check (card patch.pace-limiter)
  pcache_key              a content-cache key (card optimise.pattern-cache)
  iff_audit()             every LD A,I / LD A,R in asm/ that decides on P/V: read twice (card patch.iff-safe-read)
  call(sim, addr, regs)   run one hook / original to its RET

Existing engines keep their own copies (frozen games: their outputs never change); a rework that opts in
takes the library with its own proof and version bump.

`python -m nexclash.hooklib` = selfcheck(): the library's unit tests on the simulator (asm/lib/hlib_selftest.asm
assembled with the pinned sjasmplus) and its negative controls - a forced 3.5 MHz exit, a wrong R on exit, a
limiter that never waits, a missing cache invalidation, one pattern buffer, attributes split by uploads. Each
must be caught. selftest.py --tools runs it.
"""
import collections
import glob
import hashlib
import os
import random
import re
import subprocess
import sys
import tempfile

from nexclash import z80n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'asm', 'lib')
FILES = ['asm/lib/hlib_speed.asm', 'asm/lib/hlib_r.asm', 'asm/lib/hlib_pace.asm', 'asm/lib/hlib_pcache.asm',
         'asm/lib/hlib_commit.asm', 'asm/lib/hlib_dma.asm', 'asm/lib/hlib_iff.asm']
HARNESS = os.path.join(LIB, 'hlib_selftest.asm')

A, F, B, C, D, E, H, L, SP, I, R, PC, T, IFF = 0, 1, 2, 3, 4, 5, 6, 7, 12, 14, 15, 24, 25, 26
CMP_R = list(range(0, 24)) + [26, 27]           # every register, R included (index 15), not T / MEMPTR
CMP = [i for i in CMP_R if i != R]              # the usual compare (ENGINE_CONTRACT CMP)
CLOCKS = (0, 1, 2, 3)                           # NR 7: 3.5, 7, 14, 28 MHz
STOP = 0xFFF0                                   # call(): the return address pushed for the RET


# ------------------------------------------------------------------------------------------- R

def r_span(r0, r1):
    """M1 cycles between two R readings, mod 128 (R's bit 7 never counts)."""
    return (r1 - r0) % 128


def r_delta(o, e, n):
    """The constant for hlib_r_set: O = the original's M1s site -> return point, E = the hook's M1s through
    HLIB_R_IN (the macro: 3), N = after HLIB_R_OUT's LD R,A up to the return point (the macro: 1)."""
    return (o - e - n) % 128


def r_check(r_orig, r_patch):
    """None when R matches; else what to add to the hook's delta (mod 128). Bit 7 must match too."""
    if r_orig == r_patch:
        return None
    if (r_orig ^ r_patch) & 0x80:
        return 'bit 7'
    return r_span(r_patch, r_orig)


# --------------------------------------------------------------------------------------- pace

def lines16(t, t_line=224):
    """T-states at 3.5 MHz -> 1/16 video lines (hlib_pace_wait's target): 224 T a line (48K), 228 (128K / +3)."""
    return (t * 16 + t_line // 2) // t_line


def pace_check(t_orig, t_hook, t_line=224, tol=2.0):
    """t_* in 3.5 MHz T of real time (NextModel.now()). -> None, or a failure key ending in '!'."""
    d = (t_hook - t_orig) / t_line
    if d < -tol:
        return 'hook faster than the original (limiter not waiting)!'
    if d > tol:
        return 'hook slower than the original!'
    return None


# ------------------------------------------------------------------------------------- cache

def pcache_key(page, row):
    """An immutable image's content-cache key: (source page 1-255, 256-byte row). Never 0 (0 = mutable)."""
    if not 0 < page < 256 or not 0 <= row < 256:
        raise ValueError('pcache_key: page 1-255, row 0-255')
    return page | row << 8


# ------------------------------------------------------------------------------------- model

class NextModel(object):
    """The Next as a hook sees it, for a SkoolKit Simulator: z80n installed with this NextReg model, the
    port tracer set. Time runs at the current NR 7 clock (fast = 28 MHz's real factor: 8, or about 6.5
    with the wait states, LEARNINGS 2.1f); the video line follows it (t_line T a line at 3.5 MHz, lines a
    frame). Not modelled: contention, interrupts, the bus-idle latch of a speed change."""

    def __init__(self, sim, speed=0, t_line=224, lines=312, fast=8.0, line=0):
        self.sim, self.R = sim, sim.registers
        self.t_line, self.lines, self.fast = t_line, lines, fast
        self.nr = {7: speed & 3}
        self.sel = 0
        self.real = float(line * t_line)
        self.t_last = self.R[T]
        self.frozen = None                      # a line number: an emulator with no line counter
        self.pattern = bytearray(16384)
        self.pidx = 0
        self.attrs = [[0] * 5 for _ in range(128)]
        self.aidx = self.abyte = 0
        self.events = []                        # ('p', slot) a run of pattern bytes, ('a', sprite), ('s', speed)
        self.c = collections.Counter()
        self._shown = None
        from .dma import DMA
        self.dma = DMA(lambda a: sim.memory[a], lambda a, v: sim.memory.__setitem__(a, v),
                       lambda p, v: self.write_port(self.R, p, v))
        z80n.install(sim, self.nextreg)
        sim.set_tracer(self)

    # time
    def _mult(self):
        s = self.nr[7] & 3
        return self.fast if s == 3 else (1.0, 2.0, 4.0)[s]

    def now(self):
        """Real time so far, in 3.5 MHz T."""
        return self.real + (self.R[T] - self.t_last) / self._mult()

    def line(self):
        if self.frozen is not None:
            return self.frozen
        return int(self.now() // self.t_line) % self.lines

    def set_speed(self, s):
        self.real, self.t_last = self.now(), self.R[T]
        self.nr[7] = s & 3

    # NextRegs and ports
    def nextreg(self, reg, v):
        if reg == 7:
            self.set_speed(v)
            self.events.append(('s', v & 3))
        elif reg == 0x34:
            self.aidx = v & 127
        elif 0x35 <= reg <= 0x39:
            self._attr(self.aidx, reg - 0x35, v)
        self.nr[reg] = v

    def read_port(self, regs, port):
        if port == 0x253B:
            if self.sel == 7:
                s = self.nr[7] & 3
                return s << 4 | s               # actual speed in bits 5:4, programmed in 1:0 (zxnext.vhd 5902)
            if self.sel == 0x1E:
                return self.line() >> 8 & 1
            if self.sel == 0x1F:
                return self.line() & 255
            return self.nr.get(self.sel, 0)
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if port == 0x243B:
            self.sel = value
        elif port == 0x253B:
            self.nextreg(self.sel, value)
        elif port == 0x303B:
            self.pidx = (value & 63) << 8 | (128 if value & 128 else 0)
            self.aidx, self.abyte = value & 127, 0
        elif port & 255 == 0x6B:
            self.dma.feed(value)
        elif port & 255 == 0x5B:
            slot = self.pidx >> 8
            if slot in self.shown():
                self.c['upload into a shown pattern!'] += 1
            if not self.events or self.events[-1] != ('p', slot):
                self.events.append(('p', slot))
            self.pattern[self.pidx] = value
            self.pidx = (self.pidx + 1) & 0x3FFF
            self.c['pattern bytes'] += 1
        elif port & 255 == 0x57:
            n = self.aidx
            self._attr(n, self.abyte, value)
            self.abyte += 1
            if self.abyte == 4 and not self.attrs[n][3] & 0x40:
                self.attrs[n][4] = 0
                self.abyte = 5
            if self.abyte == 5:
                self.aidx, self.abyte = (n + 1) & 127, 0

    def _attr(self, n, k, v):
        self.attrs[n][k] = v
        self._shown = None
        self.events.append(('a', n))

    # display
    def shown(self):
        """256-byte pattern slots a visible sprite uses (attribute 3 bit 7; pattern N5-N0)."""
        if self._shown is None:
            self._shown = {a[3] & 63 for a in self.attrs if a[3] & 0x80}
        return self._shown

    def visible(self):
        return [(n, a[0], a[1], a[3] & 63) for n, a in enumerate(self.attrs) if a[3] & 0x80]

    def slot(self, s):
        return bytes(self.pattern[s * 256:s * 256 + 256])

    def burst_ok(self, start=0):
        """True when every attribute write since events[start] is in one run, no pattern upload between."""
        ev = [e[0] for e in self.events[start:] if e[0] != 's']
        if 'a' not in ev:
            return True
        i, j = ev.index('a'), len(ev) - ev[::-1].index('a')
        return all(e == 'a' for e in ev[i:j])


# --------------------------------------------------------------------------------------- run

def call(sim, addr, regs=None, limit=5000000):
    """Run from addr to its RET (STOP pushed as the return address). -> instructions run; raises after limit."""
    Rg, m, ops = sim.registers, sim.memory, sim.opcodes
    for k, v in (regs or {}).items():
        Rg[k] = v
    sp = (Rg[SP] - 2) & 0xFFFF
    m[sp], m[sp + 1] = STOP & 255, STOP >> 8
    Rg[SP], Rg[PC] = sp, addr
    n = 0
    while Rg[PC] != STOP:
        ops[m[Rg[PC]]]()
        n += 1
        if n > limit:
            raise RuntimeError('call %04X: no RET after %d instructions (PC %04X)' % (addr, limit, Rg[PC]))
    return n


def every_site(sites, run, clocks=CLOCKS):
    """The every-site matrix template. run(site, clock) -> (exit NR 7, state) for one hook entered at that
    clock from the same machine state (state: anything comparable - the CMP registers, a memory hash, the
    sprite layer; leave out what the hook's own timing changes). -> (Counter, rows); failures end in '!'.
    A new engine's unit_tests call it with every hook site and the states its verify collected."""
    c, rows = collections.Counter(), []
    for s in sites:
        base = None
        for k in clocks:
            speed, state = run(s, k)
            c['cases'] += 1
            bad = []
            if speed != k:
                bad.append('exit speed is not the incoming clock!')
            if base is None:
                base = state
            elif state != base:
                bad.append('state depends on the incoming clock!')
            for b in bad:
                c[b] += 1
            rows.append({'site': s, 'clock': k, 'exit': speed, 'ok': not bad})
    return c, rows


# ------------------------------------------------------------------------------ the harness

_BUILT = {}
NEGATIVES = {           # control -> (defines, (label, byte offset, new bytes)...): the broken builds
    'forced 3.5 MHz exit': (('NEG_FORCED35',), ()),
    'wrong R on exit': (('NEG_ROFF',), ()),
    'limiter never waits': ((), (('hlib_pace_wait', 0, b'\xC9'),)),
    'missing cache invalidation': ((), (('hlib_pc_upload.inv', 0, b'\x00'), ('hlib_pc_upload.inv2', 0, b'\x00'))),
    'one pattern buffer': ((), (('hlib_commit.flip', 1, b'\x00'),)),
    'attributes split by uploads': (('NEG_SPLIT',), ()),
    'IFF read once': (('NEG_IFF1',), ()),
}
SYM = re.compile(r'^([A-Za-z_][\w.]*):\s+EQU\s+0x([0-9A-Fa-f]+)')


def assemble(src=HARNESS, defines=()):
    """The pinned sjasmplus (tools/sjasmplus) on src with -D defines -> (bytes of its one SAVEBIN, symbols)."""
    key = (src, tuple(defines))
    if key in _BUILT:
        return _BUILT[key]
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'sjasmplus'))
    import sjasm
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sjasm.find(), '--zxnext', '--msg=war', '--sym=h.sym'] + ['-D%s' % d for d in defines]
                           + [src.replace('\\', '/')], cwd=tmp, capture_output=True, text=True)
        msg = r.stdout + r.stderr
        if r.returncode or 'error' in msg.lower() or 'warning' in msg.lower():
            raise RuntimeError('sjasmplus %s:\n%s' % (src, msg.strip()))
        bins = [f for f in os.listdir(tmp) if f.endswith('.bin')]
        with open(os.path.join(tmp, bins[0]), 'rb') as f:
            code = f.read()
        syms = {}
        with open(os.path.join(tmp, 'h.sym')) as f:
            for line in f:
                m = SYM.match(line)
                if m:
                    syms[m.group(1)] = int(m.group(2), 16)
    _BUILT[key] = (code, syms)
    return code, syms


def _build(neg=None):
    defines, patches = NEGATIVES[neg] if neg else ((), ())
    code, syms = assemble(HARNESS, defines)
    code = bytearray(code)
    for label, off, new in patches:
        a = syms[label] + off - 0x8000
        code[a:a + len(new)] = new
    return bytes(code), syms


def _machine(code, speed=0, fast=8.0, data=None):
    from skoolkit.simulator import Simulator
    m = [0] * 65536
    m[0x8000:0x8000 + len(code)] = code
    for a, v in (data or {}).items():
        m[a:a + len(v)] = v
    sim = Simulator(m, {'SP': 0xFF00})
    return sim, NextModel(sim, speed, fast=fast)


def _memhash(m):
    """Memory outside the hook RAM (0xC000-0xC3FF) and the dead stack (0xFE00-0xFFFF)."""
    return hashlib.md5(bytes(m[0x4000:0xC000]) + bytes(m[0xC400:0xFE00])).hexdigest()


# --------------------------------------------------------------------------------- the tests

def _t_r(code, syms, cases=160):
    """h_r against o_r from the same state, at a random clock: registers with R, memory."""
    c, rnd = collections.Counter(), random.Random(26)
    for _ in range(cases):
        b, hl, r0, f0, k = rnd.randrange(256), 0xA000 + rnd.randrange(0x400), rnd.randrange(256), rnd.randrange(256), \
            rnd.choice(CLOCKS)
        data = {0xA000: bytes(rnd.randrange(256) for _ in range(0x600))}
        out = []
        for entry in ('o_r', 'h_r'):
            sim, nm = _machine(code, k, data=data)
            call(sim, syms[entry], {B: b, H: hl >> 8, L: hl & 255, R: r0, F: f0, A: 0x55})
            out.append(([sim.registers[i] for i in CMP_R], _memhash(sim.memory), nm.nr[7]))
        (ro, mo, _), (rp, mp, sp) = out
        c['cases'] += 1
        fix = r_check(ro[CMP_R.index(R)], rp[CMP_R.index(R)])
        if fix is not None:
            c['R differs!'] += 1
            c['R off by %s' % fix] += 1
        if [x for i, x in zip(CMP_R, ro) if i != R] != [x for i, x in zip(CMP_R, rp) if i != R]:
            c['registers differ!'] += 1
        if mo != mp:
            c['memory differs!'] += 1
        if sp != k:
            c['exit speed is not the incoming clock!'] += 1
    return c


def _timed(code, syms, entry, k, fast=8.0, regs=None, sim=None):
    """Real time (3.5 MHz T) of one call entered at clock k, on sim or a new machine."""
    sim = sim or _machine(code, k, fast)[0]
    nm = sim.tracer
    nm.set_speed(k)
    t0 = nm.now()
    call(sim, syms[entry], dict(regs or {}))
    return nm.now() - t0, sim


def _t_pace(code, syms, fast_set=(8.0, 6.4)):
    """One window at each clock and real 28 MHz factor; plot + blit cycles with a small debt and with one
    debt over the window (carried, repaid). Original = o_*, hook = h_*, real time from NextModel."""
    c = collections.Counter()
    for fast in fast_set:
        for k in CLOCKS:
            to, _ = _timed(code, syms, 'o_blit', k, fast)
            th, _ = _timed(code, syms, 'h_blit', k, fast)
            c['windows'] += 1
            bad = pace_check(to, th)
            if bad:
                c[bad] += 1
            c['worst window, lines x100'] = max(c['worst window, lines x100'], int(abs(th - to) / 2.24))
        for burns in ([2] * 6, [200] + [2] * 5, [0, 40, 0, 120, 0, 0]):
            so = sh = None
            tot_o = tot_h = 0.0
            for bn in burns:
                for entry, acc in (('o_plot', 'o'), ('o_blit', 'o'), ('h_plot', 'h'), ('h_blit', 'h')):
                    s = so if acc == 'o' else sh
                    if s is None:
                        s, _ = _machine(code, 0, fast)
                        if acc == 'o':
                            so = s
                        else:
                            sh = s
                    s.memory[syms['V_BURN']] = bn
                    dt, _ = _timed(code, syms, entry, 0, fast, {H: 0xA0, L: 0, D: 0xA1, E: 0}, s)
                    if acc == 'o':
                        tot_o += dt
                    else:
                        tot_h += dt
            c['debt runs'] += 1
            bad = pace_check(tot_o, tot_h, tol=max(3.0, 0.005 * tot_o / 224))   # 0.5 %: the meter warns at 2
            if bad:
                c['debt: ' + bad] += 1
            c['worst debt run, % x100'] = max(c['worst debt run, % x100'], int(abs(tot_h - tot_o) * 10000 / tot_o))
    return c


PACE_MODES = (('48K', 224, 312, 0), ('128K', 228, 311, 311), ('60 Hz', 224, 264, 264))


def _t_wrap(code, syms, target=700):
    """A wait of `target` lines across two frame wraps from every start phase (16 per line), at all four clocks, in
    48K / 128K / 60 Hz timing (the frame length the engine stores at +6, 0 = HLIB_PACE_NL), plain and with an
    interrupt taking 30 lines every 40 polls: the wait is short by less than 2 lines (whole lines are counted from a
    start inside one, the target is floored to lines), long by at most 3 (a 3.5 MHz poll gap; + an interrupt's 30
    lines when interrupted), and the frame length is never learned from a poll (3.5 MHz polls can miss a frame's last
    line: the old rule learned 310 / 311 of 312 and waited up to 705.4 lines for 700)."""
    c = collections.Counter()
    p6 = syms['HLIB_V_PACE'] + 6
    for mode, t_line, lines, nl in PACE_MODES:
        for speed in range(4):
            for phase in range(0, t_line, t_line // 16):
                for isr in (0, 30):
                    from skoolkit.simulator import Simulator
                    m = [0] * 65536
                    m[0x8000:0x8000 + len(code)] = code
                    m[p6], m[p6 + 1] = nl & 255, nl >> 8
                    sim = Simulator(m, {'SP': 0xFF00})
                    nm = NextModel(sim, speed, t_line=t_line, lines=lines)
                    nm.real = 300 * t_line + phase
                    if isr:
                        line, polls = nm.line, [0]

                        def interrupted(line=line, polls=polls):
                            polls[0] += 1
                            if polls[0] % 40 == 0:
                                nm.real += isr * t_line
                            return line()
                        nm.line = interrupted
                    call(sim, syms['hlib_pace_open'])
                    t0 = nm.now()
                    call(sim, syms['hlib_pace_wait'], {H: (target * 16) >> 8, L: (target * 16) & 255, A: speed})
                    got = (nm.now() - t0) / t_line
                    want = target / (1 << speed)
                    c['waits'] += 1
                    if sim.memory[p6] | sim.memory[p6 + 1] << 8 != nl:
                        c['frame length changed by a poll (%s)!' % mode] += 1
                    if got < want - 2:
                        c['wait short (%s, %d MHz)!' % (mode, 3.5 * (1 << speed))] += 1
                    if got > want + 3 + isr:
                        c['wait long (%s, %d MHz)!' % (mode, 3.5 * (1 << speed))] += 1
                    c['worst, lines x100'] = max(c['worst, lines x100'], int(100 * abs(got - want - (isr / 2))))
    return c


def _t_nolines(code, syms):
    """A frozen line counter (an emulator without NR 0x1E / 0x1F): the wait gives up, the hook returns."""
    c = collections.Counter()
    sim, nm = _machine(code, 0)
    nm.frozen = 100
    try:
        call(sim, syms['h_blit'], {}, limit=6000000)
        c['returned'] += 1
    except RuntimeError:
        c['hangs without a line counter!'] += 1
    return c


def _t_cache(code, syms, setup=None):
    """Scripted cases + a random sequence against a reference: pattern RAM always holds the image last asked
    for; repeats of an immutable image are not uploaded; mutable images always are."""
    c, rnd = collections.Counter(), random.Random(4)
    imgs = {0x9000 + 256 * i: bytes(rnd.randrange(256) for _ in range(256)) for i in range(8)}
    sim, nm = _machine(code, 0, data=imgs)
    if setup:
        setup(sim, nm, syms)
    keys = {0x9000 + 256 * i: pcache_key(30 + i, i) for i in range(6)}   # images 6, 7: mutable buffers
    want = {}

    def up(slot, src, key=None):
        key = keys.get(src, 0) if key is None else key
        if key == 0:                            # a mutable buffer is rebuilt before each upload
            buf = bytes(rnd.randrange(256) for _ in range(256))
            sim.memory[src:src + 256] = buf
        else:
            buf = imgs[src]
        n0 = nm.c['pattern bytes']
        call(sim, syms['t_up'], {A: slot, D: key >> 8, E: key & 255, H: src >> 8, L: src & 255})
        want[slot] = buf
        if nm.slot(slot) != buf:
            c['stale pattern!'] += 1
        return (nm.c['pattern bytes'] - n0) // 256

    X, Y, M = 0x9000, 0x9100, 0x9600
    s = [up(3, X), up(3, X)]                    # miss, hit
    s.append(up(3, M))                          # mutable over it: uploaded, key invalidated
    s.append(up(3, X))                          # X again: must upload
    nm.attrs[0][3] = 0x83                       # shown, then hidden: hide keeps pattern RAM and keys
    nm.attrs[0][3] = 0x03
    s.append(up(3, X))                          # hit
    call(sim, syms['t_inval'], {A: 3})
    s.append(up(3, X))                          # invalidated: upload
    s.append(up(4, Y))
    call(sim, syms['t_reset'], {})
    s.append(up(4, Y))                          # reset: upload
    s.append(up(4, Y, keys[X] ^ 0x0100))        # a different key, same low byte: upload
    if s != [1, 0, 1, 1, 0, 1, 1, 1, 1]:
        c['uploads not as the cache rules say!'] += 1
        c['uploads %s' % s] += 1
    hits = miss = 0
    for _ in range(600):                        # random: 8 slots, 6 immutable images, 2 mutable buffers
        n = up(rnd.randrange(8), rnd.choice(list(imgs)))
        hits, miss = hits + (n == 0), miss + n
        for sl, b in want.items():
            if nm.slot(sl) != b:
                c['stale pattern!'] += 1
                break
    c['random hits'], c['random uploads'] = hits, miss
    return c


def _t_commit(code, syms, setup=None):
    """Frames of figures (counts up and down, images repeated): each frame's images go to the back half
    through the cache, then one attribute burst. Per frame: nothing written into a shown pattern, one
    burst, the visible sprites = the frame's figures with their images, the rest hidden."""
    c, rnd = collections.Counter(), random.Random(12)
    imgs = {0x9000 + 256 * i: bytes(rnd.randrange(256) for _ in range(256)) for i in range(24)}
    sim, nm = _machine(code, 0, data=imgs)
    if setup:
        setup(sim, nm, syms)
    srcs = sorted(imgs)
    frames = [[srcs[i] for i in range(5)], [srcs[i] for i in range(5, 9)], [srcs[i] for i in range(5)]]
    for _ in range(30):
        frames.append(rnd.sample(srcs, rnd.choice((0, 1, 3, 6, 12))))
    for fig in frames:
        d = [len(fig)]
        for i, s in enumerate(fig):
            k = pcache_key(40 + srcs.index(s), 0)
            d += [k & 255, k >> 8, s & 255, s >> 8, 32 + 16 * i, 40 + 4 * i]
        sim.memory[0xB000:0xB000 + len(d)] = d
        start = len(nm.events)
        call(sim, syms['t_frame'], {})
        c['frames'] += 1
        if not nm.burst_ok(start):
            c['attribute writes split by uploads!'] += 1
        vis = sorted(nm.visible())
        if len(vis) != len(fig):
            c['wrong number of sprites shown!'] += 1
        for (n, x, y, sl), s in zip(vis, fig):
            if nm.slot(sl) != imgs[s] or x != 32 + 16 * n:
                c['sprite shows the wrong image!'] += 1
    c['upload into a shown pattern!'] = nm.c['upload into a shown pattern!']
    if not c['upload into a shown pattern!']:
        del c['upload into a shown pattern!']
    return c


def _t_matrix(code, syms):
    """every_site over the harness hooks: the same results at every incoming clock, its clock back at exit."""
    data = {0x9000: bytes(range(256)) * 2, 0xA000: bytes((i * 7) & 255 for i in range(0x800)),
            0xB000: bytes([2, 0x21, 0x43, 0x00, 0x90, 32, 40, 0, 0, 0x00, 0x91, 48, 44])}
    regs = {'t_speed': {B: 3, C: 4}, 't_speed2': {D: 0x5A, E: 0x0F}, 'h_r': {B: 9, H: 0xA0, L: 0x10, R: 0x91},
            'h_blit': {}, 'h_plot': {H: 0xA0, L: 1, D: 0xA1, E: 0}, 't_up': {A: 5, D: 0x12, E: 0x34, H: 0x90, L: 0},
            't_frame': {}}
    no_r = {'h_r'}                              # the hooks that keep R; elsewhere R counts the waits' polls
    lost = {'t_speed2': (A,)}                   # HLIB_SPEED_OUT_A leaves the latch in A: documented as lost

    def run(site, k):
        sim, nm = _machine(code, k, data=data)
        call(sim, syms[site], {**regs[site], F: 0x41})
        cmp_ = CMP_R if site in no_r else [i for i in CMP if i not in lost.get(site, ())]
        return nm.nr[7], ([sim.registers[i] for i in cmp_], _memhash(sim.memory), bytes(nm.pattern),
                          [tuple(a) for a in nm.attrs])
    return every_site(sorted(regs), run)


IFF1 = 26                                       # SkoolKit's IFF register index (IFF1 = IFF2 here)
_IFF_RE = re.compile(r'^\s*(?:[A-Za-z_.][\w.]*:?)?\s*ld\s+a\s*,\s*([ir])\s*(?:;.*)?$', re.I)
_PV_RE = re.compile(r'\b(?:jp|ret|call)\s+p[oe]\b', re.I)
_CODE_RE = re.compile(r'^(?:[A-Za-z_.][\w.]*:?)?\s+([a-z].*?)\s*(?:;.*)?$', re.I)   # a label only in column 0


def _step_iff(sim, addr, regs, inject):
    """Run addr to its RET one instruction at a time. inject: an interrupt is accepted at the end of the first
    LD A,I / LD A,R (P/V forced to 0, as the NMOS Z80 and JNext do; the handler returns with EI, so IFF stays
    on). -> (IFF at exit, longest run of T with IFF = 0 that began inside the hook)."""
    Rg, m, ops = sim.registers, sim.memory, sim.opcodes
    for k, v in regs.items():
        Rg[k] = v
    sp = (Rg[SP] - 2) & 0xFFFF
    m[sp], m[sp + 1] = STOP & 255, STOP >> 8
    Rg[SP], Rg[PC] = sp, addr
    Rg[T] = 1000                    # past SkoolKit's own /INT window (its LD A,I reads P/V = 0 in a frame's first
    hit, off, worst, n = False, None, 0, 0     # 32 T): the injection below is the only interrupt
    while Rg[PC] != STOP:
        pc = Rg[PC]
        ldai = m[pc] == 0xED and m[(pc + 1) & 0xFFFF] in (0x57, 0x5F)
        ops[m[pc]]()
        if ldai and inject and not hit and Rg[IFF1]:
            Rg[F] &= ~0x04 & 0xFF
            hit = True
        if not Rg[IFF1]:
            off = Rg[T] if off is None else off
        elif off is not None:
            worst, off = max(worst, Rg[T] - off), None
        n += 1
        if n > 100000:
            raise RuntimeError('call %04X: no RET' % addr)
    if off is not None and regs.get(IFF1):
        worst = max(worst, Rg[T] - off)
    return Rg[IFF1], worst


def _t_iff(code, syms):
    """t_iff entered with interrupts on / off, with and without an interrupt accepted during its first read: the
    caller's IFF must come back. t_line_di at 28 MHz: interrupts off for under 256 T (32 T at 3.5 MHz, /INT)."""
    c = collections.Counter()
    for iff in (0, 1):
        for inject in (False, True):
            sim, nm = _machine(code, 3)
            got, _ = _step_iff(sim, syms['t_iff'], {IFF1: iff, B: 3, C: 4, F: 0x41}, inject)
            c['cases'] += 1
            if got != iff:
                c['interrupts left %s!' % ('off' if iff else 'on')] += 1
    for line in (0, 100, 311):
        sim, nm = _machine(code, 3)
        nm.real = float(line * nm.t_line)
        got, win = _step_iff(sim, syms['t_line_di'], {IFF1: 1}, False)
        c['cases'] += 1
        c['window T'] = max(c['window T'], win)
        if not got:
            c['interrupts left off!'] += 1
        if win >= 256:
            c['DI window over 256 T at 28 MHz!'] += 1
    return c


def iff_audit(root=ROOT):
    """Every LD A,I / LD A,R in asm/*.asm and asm/lib/*.asm: 'twice' (the second read only after a JP PE past
    it: safe), 'pair' (two reads back to back, the second trusted: an interrupt at the end of the second
    still reads as off),
    'value' (LD A,R with no P/V condition before the next flag-setting code: R as a value), 'once' (a single
    LD A,I - hooks read I for IFF - or LD A,R tested on P/V: an interrupt during the read leaves interrupts off).
    The harness's NEG_IFF1 control is the one expected 'once'. -> [(file, line, register, verdict)]."""
    out = []
    files = sorted(glob.glob(os.path.join(root, 'asm', '*.asm')) + glob.glob(os.path.join(root, 'asm', 'lib', '*.asm')))
    for path in files:
        lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
        code = []
        for i, ln in enumerate(lines):
            mc = _CODE_RE.match(ln)
            if mc and not ln.lstrip().startswith(';'):
                code.append((i + 1, mc.group(1).strip().lower(), ln))
        for k, (num, ins, ln) in enumerate(code):
            mi = _IFF_RE.match(ln)
            if not mi:
                continue
            reg = mi.group(1).upper()
            pair = [j for j in range(max(0, k - 4), min(len(code), k + 5)) if j != k and _IFF_RE.match(code[j][2])]
            if pair:
                lo, hi = sorted((k, pair[0]))
                # safe only when the second read runs ONLY after the first read said off (JP PE past it): two
                # reads back to back, the second trusted, can still meet an interrupt at the end of the second
                verdict = 'twice' if any(_PV_RE.search(x[1]) for x in code[lo + 1:hi]) else 'pair'
            elif reg == 'I':
                verdict = 'once'            # LD A,I is read for IFF (pushed, tested later): one read is the fault
            else:
                verdict = 'value'           # LD A,R: R as a value unless a P/V condition follows at once
                for _, ins2, _ in code[k + 1:k + 13]:
                    if _PV_RE.search(ins2):
                        verdict = 'once'
                        break
                    if re.match(r'(add|adc|sub|sbc|and|or|xor|cp|inc|dec|rl|rr|sl|sr|bit|neg|daa|pop\s+af)\b', ins2):
                        break
            out.append((os.path.relpath(path, root).replace(os.sep, '/'), num, reg, verdict))
    return out


def selfcheck():
    """-> [(name, failures)]: the unit tests, then each negative control must be caught."""
    out = []
    code, syms = _build()
    rc = _t_r(code, syms)
    out.append(('hooklib R kept: %d random hooks against the original, R and every register' % rc['cases'],
                [k for k in rc if k.endswith('!')]))
    mc, rows = _t_matrix(code, syms)
    out.append(('hooklib every-site matrix: %d hooks x 4 incoming clocks, exit = incoming, results equal' % (
        mc['cases'] // 4), [k for k in mc if k.endswith('!')]))
    for slow, name in ((None, 'at 28 MHz'), ('PACE_SLOWWAIT', 'at the caller\'s clock')):
        cc, sy = _build_def(slow)
        pc = _t_pace(cc, sy)
        out.append(('hooklib pace limiter, wait %s: %d windows (4 clocks, 28 MHz factor 8 / 6.4) within 2 lines '
                    '(worst %.2f); %d runs of 6 plot + blit cycles with debt and carry within 0.5%% (worst %.2f%%)' % (
                        name, pc['windows'], pc['worst window, lines x100'] / 100.0, pc['debt runs'],
                        pc['worst debt run, % x100'] / 100.0),
                    [k for k in pc if k.endswith('!')]))
    nc = _t_nolines(code, syms)
    out.append(('hooklib pace limiter: no line counter -> gives up, no hang', [k for k in nc if k.endswith('!')]))
    wc = _t_wrap(code, syms)
    out.append(('hooklib pace limiter across frame wraps: %d waits of 700 lines (16 start phases, 4 clocks, 48K / 128K / '
                '60 Hz timing, plain and interrupted), frame length kept' % wc['waits'], [k for k in wc if k.endswith('!')]))
    for form, (cd, sy) in (('256 x OUTI', (code, syms)), ('OTIR', assemble(HARNESS, ('HLIB_PC_OTIR',)))):
        cc = _t_cache(cd, sy)
        out.append(('hooklib content cache (%s): rules (miss, hit, mutable invalidates, hide keeps, inval, reset) + '
                    '600 random uploads, %d hits / %d uploads' % (form, cc['random hits'], cc['random uploads']),
                    [k for k in cc if k.endswith('!')]))
    ic = _t_iff(code, syms)
    out.append(('hooklib interrupt state: %d cases (IFF on / off, an interrupt during the first LD A,I) caller\'s IFF '
                'back; line read with interrupts off %d T at 28 MHz (< 256)' % (ic['cases'], ic['window T']),
                [k for k in ic if k.endswith('!')]))
    au = iff_audit()
    once = ['%s:%d' % (f, n) for f, n, _, v in au if v in ('once', 'pair') and not f.endswith('hlib_selftest.asm')]
    out.append(('hooklib IFF audit: %d LD A,I / LD A,R in asm/ (%d read twice, %d values), none trusted after one read'
                % (len(au), sum(v == 'twice' for *_, v in au), sum(v == 'value' for *_, v in au)),
                ['IFF read once: %s!' % x for x in once]))
    tc = _t_commit(code, syms)
    out.append(('hooklib atomic commit: %d frames, back half only, one burst, the right images shown' % tc['frames'],
                [k for k in tc if k.endswith('!')]))
    want = {'forced 3.5 MHz exit': (lambda cd, sy: _t_matrix(cd, sy)[0], 'exit speed is not the incoming clock!'),
            'wrong R on exit': (_t_r, 'R differs!'),
            'limiter never waits': (lambda cd, sy: _t_pace(cd, sy, fast_set=(8.0,)),
                                    'hook faster than the original (limiter not waiting)!'),
            'missing cache invalidation': (_t_cache, 'stale pattern!'),
            'one pattern buffer': (_t_commit, 'upload into a shown pattern!'),
            'attributes split by uploads': (_t_commit, 'attribute writes split by uploads!'),
            'IFF read once': (_t_iff, 'interrupts left off!')}
    for neg, (test, key) in want.items():
        cd, sy = _build(neg)
        got = test(cd, sy)
        out.append(('hooklib negative control: %s -> "%s" (%d)' % (neg, key, got[key]),
                    [] if got[key] else ['%s not caught' % neg]))
    return out


def _build_def(define):
    if not define:
        return _build()
    return assemble(HARNESS, (define,))


if __name__ == '__main__':
    bad = 0
    for name, fails in selfcheck():
        print('%-4s %s%s' % ('OK' if not fails else 'FAIL', name, '' if not fails else ' (%s)' % fails))
        bad += len(fails)
    sys.exit(1 if bad else 0)
