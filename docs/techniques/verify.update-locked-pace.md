# Measure a build's pace against the original with input keyed to game updates

```json
{
  "schema": 4,
  "id": "verify.update-locked-pace",
  "revision": 1,
  "kind": "verify",
  "title": "Measure a build's pace against the original with input keyed to game updates",
  "question": "Does the build play the same game work in the same time as the original, in quiet and in busy scenes?",
  "tags": ["verification", "speed", "pace", "hook-cost", "jnext"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": [],
  "sources": ["pilot runs/three_weeks work/pace (Jon's evidence, 2026-11-04): d386a699 +9.8%, 25eab33d +0.15%",
              "pilot runs/leonis_triage REPORT.md 4 (hook time from NR 7 over 23 games)"]
}
```

## Use / do not use
Use on every build the user tests whose hooks add time (PLAYBOOK 6b): games without frame sync slow down
by the hook time, and a frame-synced game slows once a busy frame overruns. `python -m nexclash.pace BUILD
--original ORIG` (docs/CHECKS.md). Do not compare frame-timed runs of two builds by rates (sites per
second, pixels moved): the runs drift apart at the first difference in pace and then measure different
game states (Leonis triage: Ikari's 0.45 site ratio was a state difference).

**Assumptions.** One address runs once per game update in both builds (the probe; the main loop's head or
the blit); JNext's 28 MHz master clock (CYCLE) times both runs; input before the first update (menus) does
not depend on pace.

**Validation gap.** One game (Three Weeks, plain .nex control): +11.38% for d386a699 (the owner: "just the
slow down"), +0.05% for 25eab33d (approved) over 600 updates. JNext timing, not hardware. The automatic
probe chose a different loop (0x8B5D) and read +10.94%.

## Recognise
- The owner says "slow" or "music lags"; a hook-speed pass needs a number before and after.
- Hook time per frame (NR 7) is high, or the game has no HALT / FRAMES pacing.

## Probe and stop
1. Probe: the profile's or `--probe`; else the detector (profile pass, then exact counts of the
   candidates; the commonest once-per-update count).
2. Both runs get the same random holds, started and ended at update counts.
3. Profile `state` addresses: the runs must stay in lockstep; the penalty counts only up to the first
   difference.
Stop when the penalty and its busy third are within the pace target (ORIGINAL: about 0).

## Contract
- Output: time for the same updates, original against build, all / quiet third / busy third / worst window;
  per second AY writes, port 0xFE writes, interrupts, hook time, time with interrupts off.
- Hook time counts every stretch at NR 7 non-zero, including deliberate pace waits (25eab33d: 38%).

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| no updates in lockstep | the probe never runs, or start keys miss | the run's pictures | a probe in play, start keys | frame-timed comparison |
| first difference early | input reaches the two runs at different states | the update of the difference | start keys keyed to updates | ignoring it |
| penalty in the first window only | graphics cache warm-up | hook ms per update | pre-fill, or accept | averaging it away |
| interrupt-gap warning after a hook got faster (Spellbound) | the game's own DI stretch now spans the frame interrupt | JNext: PC and IFF1 at each frame start | wait for the interrupt when that frame is lost anyway | - |

## Verification
Negative control: the original against itself gives exactly 0.00% in lockstep (`selftest.py --tools`, Chuckie
Egg); the old Three Weeks build must read over the 2% warning.

## Evidence
- docs/CHECKS.md "pace" (the Three Weeks runs and their result blocks).
- `grep -n 'def windows\|def phases\|def detect' nexclash/pace.py`.
