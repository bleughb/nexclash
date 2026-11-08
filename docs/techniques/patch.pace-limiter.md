# Pace limiter: a faster hook waits until the displaced original's time has passed

```json
{
  "schema": 4,
  "id": "patch.pace-limiter",
  "revision": 3,
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
                      "never a debt hook inside an open window (counted twice): a hook that can run inside one uses hlib_nest_open / _close",
                      "the ISR wrapper calls hlib_pace_hold / _resume: interrupt time is in no window"]},
  "owns": {"hook_state": ["HLIB_V_PACE"]},
  "examples": ["three_weeks"],
  "sources": ["pilot runs/three_weeks games/three_weeks.md 'Pace' (x_pad, V_DEBT; d386a699 +11.38% -> 25eab33d +0.05%)",
              "pilot runs/quazatron REPORT.md sessions 2-3 (game-routine windows x K, the debt repaid from DD80, isr_in / isr_out)",
              "pilot runs/dean_match_day REPORT.md v2.1 (per-call targets, ISRACC: interrupt time left out; -0.61 / -0.23 / -0.55 %)",
              "pilot NEXCLASH-CHANGES.md: owner decision, the limiter by default for ORIGINAL (2026-11-04)",
              "asm/lib/hlib_pace.asm + nexclash/hooklib.py (the shared library)"]
}
```

## Use / do not use
Targets: **ORIGINAL** (default), SLOWDOWN REMOVED (owner's choice), TURBO (menu option). Under ORIGINAL a
hook faster than the timed work it replaces waits: `hlib_pace_open` at the start,
`hlib_pace_wait` at the end (HL = the original's time, 1/16 lines: `hooklib.lines16`; A = the latched speed).
Hooks outside a window put their time in the debt (`hlib_debt_open` / `_tick` / `_close`, `hlib_debt_add`); the
next window repays it, overrun carries (HLIB_PACE_CAP). A game routine at 28 MHz: open, CALL it,
`hlib_pace_waitk` (K = original / 28 MHz time x 16, JNext). Hooks inside an open window (its routine's
callees, its own work before the wait): `hlib_nest_open` / `_close`, out of the window (never x K), into
its debt (IFUSED). `hlib_debt_repay` shortens the game's own delay; the ISR wrapper calls `hlib_pace_hold` /
`_resume`. Not for untimed code (a menu wait) or sound.

**Assumptions.** The window's original time is measured and near constant; NR 0x1E / 0x1F give the
line.

**Validation gap.** Three Weeks (LEAN) in JNext +0.50%; Cyclone within 1%; Quazatron, Match Day: own copies (within
2%). No board run.

## Recognise
The pace meter reads a negative penalty (Atic Atac v1.1: -0.8 to -2.8%).

## Probe and stop
1. `python -m nexclash.pace` on the build without the wait: the penalty (negative = faster).
2. The window's original time, less the hook's fixed parts (T_FIX).
3. With the wait: about 0 in quiet and busy thirds.

## Contract
- State: none of the game's; the waits keep IX, IY, the alternate set; the caller saves the rest.
- Time: interrupts on at the site: wait at the caller's speed (HLIB_SPEED_OUT first), so the ISR runs at its
  clock; a 3.5 MHz wait ends up to 5 lines late; at most 65536 polls. K windows scale their own readings (+2% at
  K = 128): measure K on the built hook. Stack: 12 bytes; interrupt headroom + 4 in hold / resume.
- Display: software = return/boundary only; hardware = checklist item "game speed as the original in quiet and busy scenes"

## Resources owned
HLIB_V_PACE, 26 bytes (14: HLIB_PACE_V1, the first library: Cauldron 1.1, Beyond the Ice Palace).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| faster than the original | no wait / target too small | pace | the limiter | slowing the game's code |
| slower by outside hooks | no debt | pace busy third | debt open / close | - |
| long room build measured short | no tick in a frame | debt lines | hlib_debt_tick | - |
| interrupt time in a window | no hold / resume | _t_hold | hold / resume in the ISR wrapper | DI round the wait |
| waits long after a wrap | frame length learned from a poll | _t_wrap | +6 / HLIB_PACE_NL | learning it |
| K window slow, routine calls a hook | nested time x K | _t_nest | hlib_nest_* | debt window |
| slow where the original is light, fast where busy | one floor per update | pace stretches | windows on each displaced job, sized from the plain build, and a carry | a tuned floor |
| a window reads most of a frame long | line wrap and frame serial not in step | debt at an interrupt | a window under a frame uses the wrap alone | a phase constant |

## Verification
`hooklib.pace_check` on the simulator (NextModel times both clocks); the pace meter on the build. Negative
controls (`hooklib.NEGATIVES`): no wait, resume / waitk as RET, a repay that skips nothing, nested time left in
the window or the window's time before it dropped: each caught.

## Evidence
- `grep -n '^hlib_' asm/lib/hlib_pace.asm`; `grep -n 'def _t_' nexclash/hooklib.py`.
- Users: Three Weeks x_pad (LEAN), Cobra, Gryzor; Cyclone h_r1 / h_r2 (K window).
- Own forms: Quazatron fw_wait / t_dly / isr_in (#98), Match Day v2.1 w_close / ISRACC (#99).
