# Pace limiter: a faster hook waits until the displaced original's time has passed

```json
{
  "schema": 4,
  "id": "patch.pace-limiter",
  "revision": 1,
  "kind": "patch",
  "title": "Pace limiter: a faster hook waits until the displaced original's time has passed",
  "question": "Under the ORIGINAL pace target, does a hook take less time than the code it displaces, so the game would run faster than the original?",
  "tags": ["pace", "speed", "timing", "video-line", "hook-library"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["hook.faster_than_original"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit"],
  "order": {"entry": {"after": ["patch.restore-speed"]}, "exit": {"before": ["patch.restore-speed"]},
            "cross": ["outside hooks add their time to the debt; the next window repays it",
                      "never a debt hook inside an open window (counted twice)"]},
  "owns": {"hook_state": ["HLIB_V_PACE"]},
  "examples": [],
  "sources": ["pilot runs/three_weeks games/three_weeks.md 'Pace' (x_pad, V_DEBT; d386a699 +11.38% -> 25eab33d +0.05%)",
              "pilot NEXCLASH-CHANGES.md: owner decision, the limiter by default for ORIGINAL (2026-11-04)",
              "asm/lib/hlib_pace.asm + nexclash/hooklib.py (the shared library)"]
}
```

## Use / do not use
Pace targets (the pilot's hook-speed study): **ORIGINAL** (the default for every new build: zero penalty, the
original's slowdowns kept), SLOWDOWN REMOVED (owner's choice per game: capped at the original's quiet-scene
pace), TURBO (a menu option only). Under ORIGINAL a hook that replaces timed work (a blit, a plot, a copy)
can be faster than it - sprite drawing costs less than the ULA plot, its own work runs at 28 MHz - so it
waits: `hlib_pace_open` at the window's start, `hlib_pace_wait` (HL = the original's time in 1/16 lines,
`hooklib.lines16`; A = the latched speed) at its end. Hooks outside a window that add time measure it with
`hlib_debt_open` / `_tick` / `_close`; the next window repays it, and time over a window carries. Not for
code that is not timed (a menu wait loop) or sound code (never touched).

**Assumptions.** The original's time for the window is measured (pace meter, `cost --at`, or the verifier's T
at 3.5 MHz) and is near constant; NR 0x1E / 0x1F give the video line; the target scales with the incoming
speed (>> NR 7).

**Validation gap.** Three Weeks in JNext (+0.05% over 600 updates); the library on the simulator only (windows
within 2 lines, debt runs within 0.3%). No board run.

## Recognise
The pace meter reads a negative penalty (Atic Atac v1.1: -0.8 to -2.8%) or "Net ... negative means a
limiter is needed".

## Probe and stop
1. `python -m nexclash.pace` on the build without the wait: the penalty (negative = faster).
2. The window's original time; subtract the hook's fixed parts outside the polling (its 3.5 MHz entry and
   exit, and with a slow wait the wait's tail, about 600 T): hlib_selftest.asm T_FIX.
3. With the wait: the penalty about 0 in quiet and busy thirds. Stop there.

## Contract
- State: none of the game's; the waits keep IX, IY and the alternate set; the caller saves the rest.
- Time: with interrupts on at the site, wait at the caller's speed (HLIB_SPEED_OUT first) so the game's ISR
  runs at its own clock; no wait longer than the original's window plus a line; at most 65536 polls (no line
  counter: gives up). Hook stack: 12 bytes; interrupt headroom: as the hook.
- Display: software = return/boundary only; hardware = checklist item "game speed as the original in quiet and busy scenes"

## Resources owned
HLIB_V_PACE, 14 bytes of hook RAM.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| faster than the original | no wait, or target too small | pace | the limiter, measure the target | slowing the game's code |
| slower by the outside hooks' time | no debt | pace busy third | debt open / close | - |
| a long room build measured short | over a frame without a tick | the debt lines | hlib_debt_tick a frame | - |
| waits run a few lines long after a wrap | frame length learned from a poll (3.5 MHz misses the last line) | hooklib._t_wrap | the timing mode's length (+6 / HLIB_PACE_NL) | learning it |

## Verification
`hooklib.pace_check` on the simulator (NextModel times both clocks); the pace meter on the build. Negative
control: a limiter that never waits (`hooklib.NEGATIVES`) must read faster than the original.

## Evidence
- `grep -n '^hlib_' asm/lib/hlib_pace.asm`; `grep -n 'def _t_pace\|def lines16\|def pace_check' nexclash/hooklib.py`.
- Three Weeks x_pad, x_tick, x_dbt (pilot copy of three_weeks_hooks.asm), observed in JNext.
