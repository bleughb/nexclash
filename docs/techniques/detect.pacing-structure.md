# Pacing structure: what sets the game's speed, where is the slack, who makes the sound?

```json
{
  "schema": 4,
  "id": "detect.pacing-structure",
  "revision": 2,
  "kind": "detect",
  "title": "Pacing structure: what sets the game's speed, where is the slack, who makes the sound?",
  "question": "Where does the original wait, how much usable time is left per update, and does the code hooks would touch also play sound?",
  "tags": ["analysis", "pace", "timing", "budget", "sound", "feasibility"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["inferno", "rainbow_islands"],
  "sources": ["specnext reference/inferno/build/copier_window.md section 1-2 (pacing census, 449,659 frames)",
              "specnext reference/inferno/build/copier_window/probe_inferno.py, probe_copier_out.py"]
}
```

## Use / do not use
First step for an unknown engine, before any hook budget is set (PLAYBOOK 3d: an assumed amount of
spare time is no budget). Inferno set a 10 ms target on day one; it was never measured and was the
wrong axis: the limiter 9907 is called from inside the screen copier, the slack after it was often
under 1 ms, and +10 ms of hook work would have slipped 56-81 % of updates. Rainbow Islands needed a
frame limiter, not faster hooks. Skip for a known engine whose pace is recorded.

**Assumptions.** The recordings include busy scenes and every level; T counts are uncontended
simulator T (ULA contention not modelled).

**Validation gap.** Inferno (six full levels) and Rainbow Islands. The probe matches the Inferno script
on L1 (2,500 frames); Chuckie Egg's loop is not frame-locked (43-109k T, 0-2 frames per update).

## Recognise
- No HALT in gameplay; a flag set before a `JR $` or busy loop that the ISR clears (Inferno 998E).
- The frame wait or limiter is called from inside drawing code (Inferno `CALL Z,9907` at 97FB).
- OUT 254 inside a drawing loop (the copier is also the beeper player).
- Timing gates fail repeatedly while each component gets faster.

## Probe and stop
1. `python tools/probes/pacing_census.py GAME.rzx --update LOOP [--limiter WAIT]` over every
   recording: frames per update (Inferno: 4, sometimes 5), idle PCs, the limiter's callers.
2. Per update: time from entry to the wait, slack from the wait to the resuming interrupt
   (p1 / p10 / median per level), and what runs in that slack (Inferno: a beeper filler).
3. Every OUT 254 in the code hooks would displace or slow (`routine.emits_timed_output`).
4. Usable gap sizes, not only totals: work must fit between deadlines.
Stop with: pace mechanism, slack distribution, sound producers, and the share of updates that
would slip at +1 / +5 / +10 ms. That table is the budget.

## Contract
- State: none (analysis only).
- Time: the result is the budget for every later hook; units are game updates, not video frames.
- Display: n/a (analysis).

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Hooks faster, game still slow | added work lands before the wait | slack census | move work after the wait or replace displaced work | more optimisation |
| Sound shorter or garbled | hooks ate the filler's slack or sped a sound loop | OUT census | replay OUTs at original T (patch.timed-side-effect-replay) | turbo alone |
| Game runs too fast | replaced work finished early | pace meter | pad to original time (patch.pace-limiter) | - |

## Verification
Negative control: add a fixed delay before the wait in a replay; the census must report the slip rate
the slack table predicts.

## Evidence
- copier_window.md section 1 table (observed, six levels); games/inferno.md "Copier window".
- LEARNINGS 2.1 Rainbow limiter lines; games/rainbow_islands.md.
