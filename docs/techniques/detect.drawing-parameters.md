# Observe drawing parameters at execution time

```json
{
  "schema": 3,
  "id": "detect.drawing-parameters",
  "revision": 1,
  "kind": "detect",
  "title": "Observe drawing parameters at execution time",
  "question": "Which live registers, stack values and memory fields describe a draw?",
  "tags": [
    "analysis",
    "registers",
    "runtime",
    "coordinates",
    "object-identity"
  ],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": [],
  "sources": [
    "https://github.com/TheGoodDoktor/SpectrumAnalyserProjects/blob/2aeb826aea3ccb73ad7630288d0351fda4096e84/Elite/EliteViewer.lua"
  ]
}
```

## Use / do not use
Capture a small set of live drawing parameters when static bytes or caller inspection leave the drawing interface uncertain.
Use after survey identifies candidate routines; this does not discover an unknown entry automatically.
Do not add an external viewer when existing preview and cost output answer the question.

## Recognise
A graphic changes at one address; effects temporarily replace a height; the same routine serves
several callers; coordinates appear inverted or offset. A register holding a plausible address
is a hypothesis, not proof of a graphics pointer or stable object identity.

## Probe and stop
1. Run survey, then `preview --plot ENTRY` and `cost --at ENTRY --group IX` where appropriate.
2. If unresolved, capture candidate registers, caller/stack, pointed-to header bytes and observed
   writes at the entry and return. Record bank, frame and capture timing; do not assume a debugger
   callback runs before the instruction. Spectrum Analyser execution callbacks are an optional
   implementation example, not an existing Nexclash CLI command for this capture.
3. Compare two objects, animation changes, both directions and reached appear/death effects.
   Match candidate coordinates and dimensions to actual destination writes; retain exceptions.
Stop when each needed parameter has a scoped mapping, or name the unresolved parameter and next probe.
Keep one representative event per distinct case plus counts; retain the full trace privately.

## Contract
Output: entry/bank, parameter locations, units, transformations, caller distinctions and basis/scope.
Feed the observations to detect.tracked-unit; identifying parameters does not prove safe hook sites,
re-entrancy or complete coverage. Unreached effects remain unknown. Manual evaluation only.

## Resources owned
None; observation must not alter the game state being measured.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Wrong image height | temporary header change | capture header at draw | use live dimensions | snapshot-only height |
| Objects merge | shared pointer mistaken for identity | compare simultaneous objects | include validated owner/context | pointer alone |
| Coordinates disagree | units or callback timing wrong | compare actual writes | establish transform and capture boundary | guess from one event |

## Verification
Predict writes for a held-out draw and compare positions, dimensions and source bytes. A deliberately
wrong coordinate transform or stale height must disagree on a discriminating case. This proposed
probe has not been run here; no game result or hardware status changes.

## Evidence
- External source (metadata), source-reviewed only: Elite's `OnDrawLine` captures B/C/D/E/H/L at
  hard-coded 0xEE9D; the viewer transforms endpoints. It assumes the routine is already known.
- Local motivation, not an application of this card: games/atic_atac.md records the static-height
  mistake and live one-row effect; games/chuckie_egg.md documents caller-dependent parameters.
