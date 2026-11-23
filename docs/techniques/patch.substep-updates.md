# Run each original update as N sub-steps of 1 / N game time at 28 MHz, paced to real time

```json
{
  "schema": 4,
  "id": "patch.substep-updates",
  "revision": 1,
  "kind": "patch",
  "title": "Run each original update as N sub-steps of 1 / N game time at 28 MHz, paced to real time",
  "question": "Can a game that reads the controls and moves once a slow update respond N times as often at the same game speed?",
  "tags": ["pace", "update", "physics", "fractions", "28MHz", "response", "3d"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "commit"],
  "order": {},
  "owns": {"mmu_slots": [1], "speed": "28MHz-inside-hook", "hook_state": ["HS_N", "fractions", "V0", "VR", "pace"]},
  "examples": ["hard_drivin"],
  "sources": ["asm/hard_drivin_steps.asm", "nexclash/hard_drivin.py (Spec, verify_steps)"]
}
```

## Use / do not use
Use when the game integrates per update (position += velocity, angle += rate) and the update is slow
because of its render, so 28 MHz has room for N whole updates in one update's real time. Not when the
state does not split into accumulations (rates stay per update) and once-an-update events.

**Assumptions.** Every accumulation can be found (1 original update vs N patched sub-updates from
captured states: the bytes that still differ). Thresholds compare rates. Interrupts are off in play.

**Validation gap.** One game (Hard Drivin'); on hardware "plays much better" (user).

## Recognise
- Controls read once an update of many frames (Hard Drivin': 7-21).
- Few writers of the moving state, each adding a rate to a position (write PCs over a few updates).

## Probe and stop
1. Capture the state at every update entry + its port reads; N = 1 replay = the recording.
2. Scale one accumulation at a time in Python (8-bit fraction a variable, a shadow of the value the hook
   wrote); stop when only step-size error and earlier reactions differ at N = 2 / 4.
3. Once-an-update events: one-byte gates the driver writes per sub-step (open on the first or last).
4. Exact integer rules (a Spec) first; then the hooks = the Spec byte for byte.

## Contract
- State: N = 1 = the original; N > 1 = the Spec (fractions in the hook page). Discrete escapes (a push-out
  from an object) stay WHOLE steps: scaled, the reversed velocity reverses back inside the object.
- Time: the driver wraps the loop's CALL (the loop code runs once an update); N from the last update's
  busy lines a sub-step with hysteresis; each view copied no earlier than its share of the update's real
  time, in the no-tear band, debt carried and capped. A path that may leave the update runs plain. A 7FFD
  write maps the ROM into slots 0-1 on the Next: map the hook page again after the game's own.
  hook stack: about 16 bytes on the page's own stack; interrupt headroom: interrupts off: n/a.
- Display: software = return/boundary only; hardware = checklist item "tearing".

## Resources owned
MMU slot 1 for the whole driver; the alt ROM's trampolines; NR 0x07.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| crash after the first view (Next) | 7FFD reset MMU 0-1 | model with the reset | re-map | - |
| the car stays inside an object | push-out scaled 1 / N | synthetic collision | whole push-out | - |
| a render overwrites state | new camera positions | runs of K updates | guards | - |
| a mutant passes | a later clamp resets its effect | the hook alone | a case where it acts last | - |

## Verification
Per recorded update the build (host model) vs the Spec from the same warm state: all RAM, registers but
R, hook state; adaptive and fixed N; runs; synthetic states; negative controls. Pace: model, JNext, hardware.

## Evidence
- games/hard_drivin.md "Route 2" (observed: model, JNext; hardware by the user).
- `grep -n '^def \|^class ' nexclash/hard_drivin.py` (Spec, whole_update, verify_steps).
