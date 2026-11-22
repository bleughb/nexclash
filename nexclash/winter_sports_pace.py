"""Winter Sports: the shared event plugin for events whose smoothing is the TEAR-FREE FAST DRAW (Bobsled, ...): GPL-3.0-or-later.
Facts and the contract: games/winter_sports.md "Event plugins"; the per-event specs are in winter_sports_<event>.py (a spec + this class).

Some events pace themselves (their own delay loops set the speed of the bob: Bobsled's update interval runs from 8 frames at a standstill to 2 at speed),
so an even cadence would change the game. What the default build does instead: every call of the event's screen-copy routine (a spec lists the call sites)
becomes a wrapper that halts once to the frame interrupt (the copy then starts at the top of a frame: no tearing), runs the copy at 28 MHz and puts 3.5 MHz
back (winter_sports_common.draw_wrapper). The halt costs half a frame on average and the 28 MHz copy saves about as much, so the pace stays within a few percent.
The toggle "Original pace" (mode byte = 1) makes the wrappers plain calls again. Colours: unchanged (the original 16); `enhanced` has no extra picture here.
Tests (tests()): the same key script through the original (tape served at ROM 0x0562) and the build: updates at the marker (the instruction after a draw site),
their interval mean within 8 %, no write to the beeper port (0xFE) while the CPU is fast, 3.5 MHz restored at every marker, the wrapper transparent (called
from a copy of the build's state at a site, with the halts NOPed, it gives the registers and memory of the plain call), and negative controls (a wrapper that
leaves 28 MHz on; one that calls a wrong target) caught."""
import statistics
from collections import Counter

from . import winter_sports as W
from . import winter_sports_common as C

FRAME_T = 69888
SPACING = 0x2C                                 # bytes reserved per wrapper (a wrapper is 41-43)


class Site:
    """One drawing call: `orig` = its bytes (CD lo hi, or F3 CD lo hi FB when di), `target` = the routine, `halts` = frames waited before it."""

    def __init__(self, addr, target, di=False, halts=1):
        self.addr, self.target, self.di, self.halts = addr, target, di, halts
        self.orig = (bytes([0xF3]) if di else b'') + bytes([0xCD, target & 255, target >> 8]) + (bytes([0xFB]) if di else b'')

    @property
    def marker(self):
        return self.addr + len(self.orig)


class PaceEvent:
    """A plugin object (the module contract of winter_sports_common) for an event smoothed by the tear-free fast draw."""

    BANKS = ()

    def __init__(self, name, index, sites, wrap_at, var_at, menu_key, keys, frames=1500, pre_frames=2300, notes='', prefix=None):
        self.__name__ = name
        self.INDEX, self.sites, self.wrap_at, self.var_at = index, sites, wrap_at, var_at     # wrappers at wrap_at + SPACING * i, the mode byte at var_at
        self.menu_key, self.keys, self.frames, self.pre_frames, self.notes = menu_key, keys, frames, pre_frames, notes
        self.prefix = prefix                              # the key script up to the run when the event's menu needs more than K, QAOP, S

    # ------------------------------------------------------------------ the build
    def wrappers(self, bad=None):
        """[(address, code)]; `bad` selects a negative control: 'fast' leaves 28 MHz on, 'target' calls the wrong routine."""
        out = []
        for i, s in enumerate(self.sites):
            a = C.Asm(self.wrap_at + SPACING * i)
            C.draw_wrapper(a, s.target + (2 if bad == 'target' else 0), self.var_at, s.di, s.halts)
            code = bytearray(a.done())
            if bad == 'fast':                                   # drop the "back to 3.5 MHz" write
                k = bytes([0xED, 0x91, 0x07, 0x00])
                j = code.index(k)
                code[j:j + 4] = bytes(4)
            assert len(code) <= SPACING, len(code)
            out.append((a.org, bytes(code)))
        return out

    def patch_event(self, block, enhanced=False, original_pace=False, bad=None):
        b = C.Block(block)
        for s in self.sites:
            b.expect(s.addr, s.orig, '%s draw site 0x%04X' % (self.__name__, s.addr))
        b.free(self.wrap_at, SPACING * len(self.sites) + 0x10, self.__name__)
        for (addr, code), s in zip(self.wrappers(bad), self.sites):
            b.put(addr, code)
            b.put(s.addr, bytes([0xCD, addr & 255, addr >> 8]) + bytes(len(s.orig) - 3))
        b.put(self.var_at, bytes([1 if original_pace else 0]))
        return b.bytes(), {}

    def disable_code(self):
        a = C.Asm(0)
        a.nr(0x07, 0x00)
        return list(a.done())

    # ------------------------------------------------------------------ the tests
    def flow(self):
        if self.prefix is not None:
            return [(20, 28, self.menu_key)] + list(self.prefix) + list(self.keys)
        return [(20, 28, self.menu_key), (1600, 1630, 'K'), (1700, 1730, 'Q'), (1770, 1800, 'A'), (1840, 1870, 'O'), (1910, 1940, 'P'),
                (2000, 2060, 'S')] + list(self.keys)

    def _run(self, z80, events, build, pages, frames):
        """One run: the markers (absolute T), the beeper writes at 28 MHz, and the CPU speed at each marker."""
        from skoolkit.simutils import PC, T, IFF
        from .winter_sports_dh_test import _exec
        sim, kb, log = W._sim(z80, build, pages=pages, keys=self.flow(), hybrid=build)
        R, mem = sim.registers, sim.memory
        marks = {s.marker for s in self.sites}
        st, rows, fast_out, left_fast = {}, [], 0, 0
        for f in range(frames):
            kb.frame = f
            while R[T] < FRAME_T:
                pc = R[PC]
                if pc == 0x0562 and not build:
                    W._original_trap(sim, events, st)
                    continue
                if pc in marks and f > self.pre_frames:
                    rows.append(f * FRAME_T + R[T])
                    if sim.spd[0] != 1:
                        left_fast += 1
                _exec(sim)
            R[T] -= FRAME_T
            if R[IFF]:
                if mem[R[PC]] == 0x76:
                    R[PC] = (R[PC] + 1) & 0xFFFF
                sim.accept_interrupt(R, mem, 0)
        return rows, sim.fast_out, left_fast

    def tests(self, patch, z80, say=print, bad=None):
        from .winter_sports_dh_test import _exec
        lines, ok = [], True
        total = self.pre_frames + self.frames
        orig, _fo, _lf = self._run(z80, patch.tape_events, False, None, total)
        build, fast_out, left_fast = self._run(z80, patch.events, True, W._pages(patch.events), total)
        io = [(b - a) / FRAME_T for a, b in zip(orig, orig[1:]) if b - a < 20 * FRAME_T]
        ib = [(b - a) / FRAME_T for a, b in zip(build, build[1:]) if b - a < 20 * FRAME_T]
        mo, mb = statistics.mean(io), statistics.mean(ib)
        pace_ok = len(io) >= 20 and abs(mb - mo) / mo <= 0.08
        lines.append('%s : updates original %d build %d, mean interval %.2f vs %.2f frames (%+.1f %%)%s'
                     % (self.__name__, len(orig), len(build), mo, mb, (mb / mo - 1) * 100, '' if pace_ok else '!'))
        lines.append('%s : beeper (port 0xFE) writes at 28 MHz %d, markers left fast %d%s' % (self.__name__, fast_out, left_fast, '' if not (fast_out or left_fast) else '!'))
        ok = pace_ok and not fast_out and not left_fast
        # transparency of each wrapper: from the build's state at the site, the wrapper (halts NOPed) vs the plain call
        for s in self.sites:
            tr = self._transparent(z80, patch, s)
            lines.append('%s : wrapper at 0x%04X %s' % (self.__name__, s.addr, 'transparent' if tr else 'NOT transparent!'))
            ok = ok and tr
        if bad is None:                                      # negative controls: a wrapper that leaves 28 MHz on, one that calls a wrong target
            import copy
            for what in ('fast', 'target'):
                q = copy.copy(patch)
                q.events = list(patch.events)
                q.events[self.INDEX] = self.patch_event(patch.tape_events[self.INDEX], False, False, bad=what)[0]
                if what == 'fast':
                    _r, fo, lf = self._run(z80, q.events, True, W._pages(q.events), total)
                    caught = bool(fo or lf)
                else:
                    caught = not all(self._transparent(z80, q, s) for s in self.sites)
                lines.append('%s : negative control "%s" %s' % (self.__name__, what, 'caught' if caught else 'MISSED!'))
                ok = ok and caught
        return ok, lines

    def _transparent(self, z80, patch, site):
        """Run the build to its first arrival at `site` in play, copy the state, call the wrapper (halts NOPed) from one and the routine directly from the other."""
        from skoolkit.simutils import PC, T, IFF
        from .winter_sports_dh_test import _exec
        sim, kb, log = W._sim(z80, True, pages=W._pages(patch.events), keys=self.flow(), hybrid=True)
        R, mem = sim.registers, sim.memory
        for f in range(self.pre_frames + self.frames):
            kb.frame = f
            while R[T] < FRAME_T:
                if R[PC] == site.addr and f > self.pre_frames:
                    return self._compare(sim, site)
                _exec(sim)
            R[T] -= FRAME_T
            if R[IFF]:
                if mem[R[PC]] == 0x76:
                    R[PC] = (R[PC] + 1) & 0xFFFF
                sim.accept_interrupt(R, mem, 0)
        return False

    def _compare(self, sim, site):
        from skoolkit.simutils import PC
        from .winter_sports_dh_test import _exec
        R, mem = sim.registers, sim.memory
        mem0, reg0 = list(mem), list(R)
        wrap = next(a for (a, _c), s in zip(self.wrappers(), self.sites) if s is site)
        for k in range(wrap, wrap + SPACING):                       # no halts in the test copy
            if mem[k] == 0x76:
                mem[k] = 0x00
        mem[self.var_at] = 0

        def call(entry):
            R[12] = (R[12] - 2) & 0xFFFF
            mem[R[12]], mem[R[12] + 1] = 0x00, 0x90
            R[PC] = entry
            sim.spd[0], sim.spd[1] = 1, 0
            n = 0
            while R[PC] != 0x9000 and n < 3_000_000:
                _exec(sim)
                n += 1
            return list(R), list(mem)
        a_regs, a_mem = call(wrap)
        R[:] = reg0
        mem[:] = mem0
        for k in range(wrap, wrap + SPACING):
            if mem[k] == 0x76:
                mem[k] = 0x00
        b_regs, b_mem = call(site.target)
        keep = [i for i in range(len(a_regs)) if i not in (15, 24, 25, 26, 27, 28, 29)]        # R, PC, T, IFF, IM, HALT, MEMPTR
        regs_ok = all(a_regs[i] == b_regs[i] for i in keep)
        sp = b_regs[12]                                          # the wrapper's pushes leave stale bytes below the stack pointer: not state
        mem_ok = all(a_mem[i] == b_mem[i] for i in range(0x4000, 0x10000)
                     if not (self.wrap_at <= i < self.wrap_at + SPACING * len(self.sites) + 0x10) and not (sp - 48 <= i < sp))
        if not (regs_ok and mem_ok):
            self.last_diff = ([(i, a_regs[i], b_regs[i]) for i in keep if a_regs[i] != b_regs[i]][:6],
                              [(hex(i), a_mem[i], b_mem[i]) for i in range(0x4000, 0x10000) if a_mem[i] != b_mem[i]][:6])
        return regs_ok and mem_ok

