"""Winter Sports, Downhill / Slalom / Giant Slalom: the differential run against the original and the hook tests. GPL-3.0-or-later.
verify_downhill / unit_downhill / tests; the plugin contract is in winter_sports_common.py. The simulator models NextReg 0x50 (MMU0), NextReg 0x07
(a 28 MHz instruction takes 1/8 of the time) and HALT (it ends at the frame interrupt)."""
from collections import Counter

from . import winter_sports as W
from . import winter_sports_dh as dh
from .winter_sports import EVENT_ADDR, _sim, _pages, _original_trap
from .winter_sports_common import CADENCE

DH_KEYS = [(20, 28, '1'), (1600, 1630, 'K'), (1700, 1730, 'Q'), (1770, 1800, 'A'), (1840, 1870, 'O'), (1910, 1940, 'P'),
           (2000, 2060, 'S'), (2300, 4000, 'Q'), (2700, 2760, 'O'), (3000, 3100, 'P'), (3400, 3460, 'O')]
RENDER_DONE = 0x84B3                              # after CALL 0x8954 in the update: the view has been copied to the screen
PANE_ROWS = (40, 168)
FRAME_T = 69888


def _pane(mem):
    """The left pane's 128 rows x 14 bytes from the screen memory."""
    out = bytearray()
    for y in range(*PANE_ROWS):
        base = 0x4000 + ((y & 7) << 8) + (((y >> 3) & 7) << 5) + ((y >> 6) << 11)
        out += bytes(mem[base + 1:base + 15])
    return bytes(out)


def _pano_window(pano, x0):
    """128 rows x 14 bytes: panorama bits x0 .. x0+111 (wrapping at 256)."""
    out = bytearray()
    for y in range(128):
        bits = [(pano[y * 32 + (((x0 + i) % 256) >> 3)] >> (7 - (((x0 + i) % 256) & 7))) & 1 for i in range(112)]
        for b in range(14):
            v = 0
            for k in range(8):
                v = v << 1 | bits[b * 8 + k]
            out.append(v)
    return bytes(out)


def _exec(sim):
    """One instruction with the speed model: at 28 MHz its T-states count 1/8; a HALT with interrupts on runs to the frame's end."""
    from skoolkit.simutils import PC, T, IFF
    R, mem = sim.registers, sim.memory
    if mem[R[PC]] == 0x76 and R[IFF]:
        R[T] = FRAME_T
        return
    spd, t0 = sim.spd, R[T]
    sim.opcodes[mem[R[PC]]]()
    if spd[0] > 1:
        dt = R[T] - t0 + spd[1]
        used = dt // spd[0]
        spd[1] = dt - used * spd[0]
        R[T] = t0 + used


def _dh_run(z80, events, hybrid, pages, frames, flip=False, original_pace=False):
    """One run of the Downhill flow from the menu snapshot (the tape served at ROM 0x0562, or the hook): per update (f, heading, last seen, the
    Layer 2 scroll register (hybrid), the pane, the time in T-states). flip = negative control (the scroll register with the wrong sign)."""
    from skoolkit.simutils import PC, T, IFF
    sim, kb, log = _sim(z80, hybrid, pages=pages, keys=DH_KEYS, hybrid=hybrid)
    R, mem = sim.registers, sim.memory
    st, rows = {}, []
    for f in range(frames):
        kb.frame = f
        while R[T] < FRAME_T:
            pc = R[PC]
            if pc == 0x0562 and not hybrid:
                _original_trap(sim, events, st)
                continue
            if pc == RENDER_DONE and mem[0x82DC]:
                sc = None
                if hybrid:
                    regs = [v for r, v in log if r == 0x16]
                    sc = regs[-1] if regs else None
                    if flip and sc is not None:
                        sc = (240 - sc) & 255
                rows.append((f, mem[0x82DC], mem[0x8BEA], sc, _pane(mem), f * FRAME_T + R[T]))
            _exec(sim)
        R[T] -= FRAME_T
        if R[IFF]:
            if mem[R[PC]] == 0x76:
                R[PC] = (R[PC] + 1) & 0xFFFF
            sim.accept_interrupt(R, mem, 0)
    return rows, log


def _view_model(rows):
    """The original's scroll position per update from its own record: one pixel step per call whose last-seen heading (0x8BEA) differs from the
    previous call's, from the game's start value 56; the panorama's left edge is then x0 = 128 - view."""
    v, prev, out = 56, 56, []
    for r in rows:
        seen = r[2]
        v += (seen > prev) - (seen < prev)
        prev = seen
        out.append(128 - v)
    return out


def _measured_x0(pano, pane, near):
    """Where in the panorama the original's pane shows: the offset (searched around `near`) at which the panorama's ink is all in the pane."""
    best = None
    for x0 in sorted(range(near - 3, near + 4), key=lambda x: abs(x - near)):
        win = _pano_window(pano, x0 % 256)
        miss = sum(bin(w & ~o & 0xFF).count('1') for w, o in zip(win, pane))
        if best is None or miss < best[0]:
            best = (miss, x0 % 256)
    return best[1] if best[0] == 0 else None


def _intervals(rows):
    """Update intervals in frames (from the update's end time)."""
    return [(b[5] - a[5]) / FRAME_T for a, b in zip(rows, rows[1:])]


def _stats(iv):
    import statistics
    return statistics.mean(iv), statistics.pstdev(iv)


def verify_downhill(patch, z80, frames=3600, flip=False, progress=None):
    """Original vs the converted Downhill over the same key script (start, a run, two turns), the checks:
      scroll   - the original's own panes sit where its one-pixel-step model says (every update), and the Layer 2 scroll register of the build
                 follows the same model from its own record (every update): the hook reproduces the original's scroll, lag included;
      poles    - at updates where both runs have the same heading, last-seen heading and scroll position, the build's ULA pane OR the panorama window
                 equals the original's pane (the poles are the game's own code on both sides), >= 85 % of them (the rest: a pole one pixel off while the
                 heading is changing: an interrupt lands on another instruction; 3-12 % between builds); only with the original pace (the cadence changes the interleaving);
      pace     - default (smooth): the mean update interval within 6 % of the original's, most
                 exactly 2 frames (at least 40 % and five times the original's share), no wider a spread; original pace: the update counts within 2 %.
    Heading by update is NOT compared: an interrupt landing on another instruction moves a heading change by one update, and the runs drift apart.
    -> (Counter, examples)"""
    C, ex = Counter(), []
    pano = patch.tape_events[0][dh.PANO - EVENT_ADDR:dh.PANO - EVENT_ADDR + 0x1000]
    orig, _ = _dh_run(z80, patch.tape_events, False, None, frames)
    if progress:
        progress(1, 2)
    hyb, log = _dh_run(z80, patch.events, True, _pages(patch.events), frames, flip)
    if progress:
        progress(2, 2)
    C['updates original %d build %d' % (len(orig), len(hyb))] += 1
    io, ih = [x for x in _intervals(orig) if x < 50], [x for x in _intervals(hyb) if x < 50]     # the one long gap is the wait before the run
    mo, so = _stats(io)
    mh, sh = _stats(ih)
    if patch.original_pace:
        ok = abs(len(orig) - len(hyb)) <= max(2, len(orig) // 50)
        C['pace: original pace, update counts within 2%' + ('' if ok else '!')] += 1
    else:
        fo = sum(1 for x in io if 1.95 <= x <= 2.05) / len(io)
        fh = sum(1 for x in ih if 1.95 <= x <= 2.05) / len(ih)
        ok = abs(mh - mo) / mo <= 0.06 and fh >= 0.4 and fh >= 5 * fo and sh <= so
        C['pace: smooth, mean %.3f vs %.3f frames per update, %.0f%% of updates exactly 2 frames vs %.0f%%, spread %.2f vs %.2f (the blocking beeps remain)'
          % (mh, mo, fh * 100, fo * 100, sh, so) + ('' if ok else '!')] += 1
    en = [v for r, v in log if r == 0x69]
    C['Layer 2 enabled once, after the loader switched it off' + ('' if en.count(0x80) == 1 and en[-1] == 0x80 and en[0] == 0 else '!')] += 1
    mdl_o, mdl_h = _view_model(orig), _view_model(hyb)
    steps = sum(1 for a, b in zip(hyb, hyb[1:]) if a[2] != b[2])
    C['scroll steps exercised (>= 20)' + ('' if steps >= 20 else '!')] += 1
    bad_o = sum(1 for i, r in enumerate(orig) if _measured_x0(pano, r[4], mdl_o[i]) != mdl_o[i] % 256)
    C['original panes at the model position' + ('' if not bad_o else '!')] += len(orig) - bad_o
    bad_h = sum(1 for i, r in enumerate(hyb) if r[3] is None or (r[3] + 8) % 256 != mdl_h[i] % 256)
    C['build scroll register at the model position' + ('' if not bad_h else '!')] += len(hyb) - bad_h
    if patch.original_pace:
        matched = bad_p = 0
        for u in range(min(len(orig), len(hyb))):
            fo, ho, so_, _s, po, _t = orig[u]
            fh, hh, sh_, sc, ph, _t2 = hyb[u]
            if ho == hh and so_ == sh_ and sc is not None and (sc + 8) % 256 == mdl_o[u] % 256:
                matched += 1
                comp = bytes(a | b for a, b in zip(ph, _pano_window(pano, (sc + 8) % 256)))
                if comp != po:
                    bad_p += 1
                    if len(ex) < 5:
                        ex.append((u, ho, sc, sum(bin(a ^ b).count('1') for a, b in zip(comp, po))))
        ok_p = matched >= 100 and bad_p <= max(2, matched * 15 // 100)
        C['poles: state-matched updates >= 100' + ('' if matched >= 100 else '!')] += matched
        C['poles: panes equal among them, >= 85%' + ('' if ok_p else '!')] += matched - bad_p
        if bad_p:
            C['poles: panes different (a pole a pixel off)' + ('' if ok_p else '!')] += bad_p
    else:
        # smooth: the ULA pane is only poles; none may sit in the sky rows (pane rows 0-23)
        bad = sum(1 for r in hyb if any(r[4][i] for i in range(0, 14 * 24)))
        C['smooth: no pole pixels in the sky rows' + ('' if not bad else '!')] += len(hyb) - bad
    return C, ex


def _call(sim, addr, limit=3_000_000):
    """Call a routine as the game does (return address on the stack) -> (T-states used incl. whole frames waited, steps, returned)."""
    from skoolkit.simutils import PC, T
    R, mem = sim.registers, sim.memory
    sp = R[12]
    R[12] = (sp - 2) & 0xFFFF
    mem[R[12]], mem[R[12] + 1] = 0x00, 0x90
    save, n = R[PC], 0
    R[PC] = addr
    tstart = R[T]
    frames = 0
    while R[PC] != 0x9000 and n < limit:
        _exec(sim)
        if R[T] >= FRAME_T:                          # a HALT: the frame interrupt arrived (the ISR is not run here: only the timing is wanted)
            R[T] -= FRAME_T
            frames += 1
            if mem[R[PC]] == 0x76:
                R[PC] = (R[PC] + 1) & 0xFFFF
        n += 1
    used = frames * FRAME_T + R[T] - tstart
    ok = R[PC] == 0x9000
    R[12], R[PC] = sp, save
    return used, n, ok


def _ready_sim(z80, patch):
    """The converted build's simulator at the end of the ready screen (frame 2200): the event loaded and waiting for the run."""
    from skoolkit.simutils import PC, T, IFF
    sim, kb, log = _sim(z80, True, pages=_pages(patch.events), keys=DH_KEYS, hybrid=True)
    R, mem = sim.registers, sim.memory
    for f in range(2200):
        kb.frame = f
        while R[T] < FRAME_T:
            _exec(sim)
        R[T] -= FRAME_T
        if R[IFF]:
            if mem[R[PC]] == 0x76:
                R[PC] = (R[PC] + 1) & 0xFFFF
            sim.accept_interrupt(R, mem, 0)
    return sim, log


def unit_downhill(patch, z80, rotate=0):
    """The hooks called directly in a running Downhill (the build's simulator at the ready screen's end).
    Original pace: 16 steps (up / down x the counter 0-7) must take the original's measured T (STEP_RIGHT / STEP_LEFT, within 150 T), keep the counter and
    the view like the original (one step, mod 8) and write NextReg 0x16 = 120 - view; an unchanged heading takes < 400 T and writes the same register.
    Smooth: a step takes < 400 T (no pad), and the pace wrapper called 14 times takes the cadence's frames (within 1.5 frames in total),
    runs the drawing at NextReg 0x07 = 3 and puts 0 back. `rotate` shifts the pad table: the negative control. -> (Counter, failures)"""
    from skoolkit.simutils import IFF
    C, fails = Counter(), []
    sim, log = _ready_sim(z80, patch)
    R, mem = sim.registers, sim.memory
    R[IFF] = 1
    mem[dh.V_STARTED] = 1                            # already enabled: the steps only
    tab = bytes(mem[dh.TABLE:dh.TABLE + 32])
    if rotate:
        mem[dh.TABLE:dh.TABLE + 32] = tab[2 * rotate:] + tab[:2 * rotate]
    mode = mem[dh.V_MODE]
    for direction, costs in ((1, dh.STEP_RIGHT), (-1, dh.STEP_LEFT)):
        for c in range(8):
            mem[dh.STEP_COUNTER] = c
            view = mem[dh.V_VIEW]
            mem[dh.HEADING] = (mem[dh.SEEN] + direction) & 255
            n0 = len(log)
            t, _n, ok_ret = _call(sim, dh.HOOK)
            nr = [v for r, v in log[n0:] if r == 0x16]
            ok = ((abs(t - costs[c]) <= 150 if mode else t < 400) and mem[dh.STEP_COUNTER] == (c + direction) & 7
                  and mem[dh.V_VIEW] == (view + direction) & 255 and nr == [(120 - mem[dh.V_VIEW]) & 255] and ok_ret)
            C['step %s counter %d' % ('up' if direction > 0 else 'down', c) + ('' if ok else '!')] += 1
            if not ok:
                fails.append((direction, c, t, costs[c] if mode else 400, mem[dh.STEP_COUNTER], nr))
    mem[dh.HEADING] = mem[dh.SEEN]
    n0 = len(log)
    t, _n, ok_ret = _call(sim, dh.HOOK)
    ok = t < 400 and [v for r, v in log[n0:] if r == 0x16] == [(120 - mem[dh.V_VIEW]) & 255]
    C['unchanged heading' + ('' if ok else '!')] += 1
    if not mode:
        mem[dh.V_CAD] = 0
        total, speeds = 0, []
        for i in range(14):
            n0 = len(log)
            t, _n, ok_ret = _call(sim, dh.WRAP)
            total += t
            speeds.append([v for r, v in log[n0:] if r == 0x07])
        want = sum(CADENCE[i % len(CADENCE)] for i in range(14))
        ok = abs(total / FRAME_T - want) <= 1.5 and all(s == [3, 0] for s in speeds)
        C['pace wrapper: 14 calls = %d frames, drawing at 28 MHz' % want + ('' if ok else '!')] += 1
        if not ok:
            fails.append(('wrapper', total / FRAME_T, speeds[:3]))
        # the player's speed (F8) comes back after the 28 MHz drawing at every speed, not a fixed 3.5 MHz (Codex review C6)
        for s in (1, 2, 3):
            sim.player_speed(s)
            n0 = len(log)
            t, _n, ok_ret = _call(sim, dh.WRAP)
            got = [v for r, v in log[n0:] if r == 0x07]
            ok = got == [3, s] and sim.nr7 == s
            C['pace wrapper at NR 7 = %d: 28 MHz, then %d back' % (s, s) + ('' if ok else '!')] += 1
            if not ok:
                fails.append(('wrapper speed', s, got, sim.nr7))
        sim.player_speed(0)
    return C, fails


def tests(patch, z80, say=print):
    """The plugin's checks for `auto`: (ok, [lines]); negative controls included."""
    lines = []
    D, dex = verify_downhill(patch, z80)
    lines.append('Downhill  : %s' % ', '.join('%s x%d' % kv for kv in sorted(D.items())))
    DU, dfails = unit_downhill(patch, z80)
    lines.append('Hook unit : %d cases, %d failed' % (sum(DU.values()), len([k for k in DU if k.endswith('!')])))
    ok = not any(k.endswith('!') for k in list(D) + list(DU))
    ND, _ = verify_downhill(patch, z80, flip=True)
    NU, _ = unit_downhill(patch, z80, rotate=1)
    caught = any(k.endswith('!') for k in ND)
    nu_ok = (sum(1 for k in NU if k.endswith('!')) >= 8) if patch.original_pace else True
    lines.append('Negative  : wrong-sign scroll %s, rotated pad table %s' % ('caught' if caught else 'MISSED',
                 '%d of %d cases failed' % (sum(1 for k in NU if k.endswith('!')), len(NU)) if patch.original_pace else 'not applicable (smooth)'))
    return ok and caught and nu_ok, lines
