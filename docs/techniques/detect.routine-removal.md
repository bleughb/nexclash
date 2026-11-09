# Removal experiment: does gameplay need this original routine at all?

```json
{
  "schema": 4,
  "id": "detect.routine-removal",
  "revision": 2,
  "kind": "detect",
  "title": "Removal experiment: does gameplay need this original routine at all?",
  "question": "If the original routine is skipped, does anything the game later decides change?",
  "tags": ["analysis", "feasibility", "equivalence", "dependency-map", "hybrid"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["inferno"],
  "sources": ["specnext reference/inferno/build/hybrid.md (dependency map, 2026-11-09)",
              "specnext reference/inferno/build/hybrid/probe_skip.py, probe_taint.py, probe_deps.py"]
}
```

## Use / do not use
Run it in feasibility (PLAYBOOK 3d) before designing around any original routine you would keep
unchanged, speed up or wrap: a copier, a renderer, a sound player, a wait. It settles which
"must preserve" items are requirements and which are only habits. Inferno spent days preserving the
copier's R, IRQ timing and RAM effects; this experiment, run on 2026-11-09, took minutes and showed
gameplay needed none of them except the values read by `LD A,R`. Not needed for a known engine
(`auto` PASS) or a routine the design leaves untouched.

**Assumptions.** The recordings drive the game through the paths that matter; a replay can feed the
recorded IN values and R reads; the routine has a clear call site to skip.

**Validation gap.** One game (Inferno, levels 1-6, first 2,500 frames each; level 5 left gameplay
early). A replay cannot see branches the recording never takes: Inferno's skip passed, yet
disassembly later found gameplay logic in the copier (9804 `CALL Z,9881`).

## Recognise
- A large routine whose output looks display-only (a back-buffer copier, a scenery redraw).
- A design rule like "run X unchanged" with no named consumer of X's effects.
- Repeated timing FAILs while preserving a routine's side effects.

## Probe and stop
1. `python tools/probes/routine_skip.py GAME.rzx --call ADDR [--exclude LO-HI] [--no-r]`: each update
   rerun with the CALL skipped, recorded INs, `LD A,R` values and interrupts fed; game RAM compared at the
   next hit. Per level: identical, differs (pages, first address), runaway. Run with and without R.
2. Taint the routine's writes: which later reads consume them (Inferno: only its own stack unwind).
3. List what it outputs: display memory, its own work pages, ports (sound), registers kept live.
4. Disassemble every branch inside the routine the replay never took; look for gameplay writes/calls.
Stop with a dependency map: gameplay reads / display-only / sound / cadence / R, each with evidence.
Sets `routine.display_only_effects` true, false or conflicted.

## Contract
- State: none (analysis only). Equivalence boundary of the comparison: display memory and the
  routine's own work pages are excluded and named.
- Time: n/a (replay). Not a pace measurement: cadence comes from detect.pacing-structure.
- Display: n/a (analysis).

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Levels diverge after skipping | game reads R or a value the routine set | first differing PC | supply recorded R; trace that value | declaring the routine required |
| Skip passes, game breaks later | logic on an unexercised branch | disassemble branches | keep that call (Inferno 9804) | trusting the replay alone |
| Replay leaves gameplay early | menu / death path | frame of exit | longer or other recording | - |

## Verification
Negative control: skip a routine that gameplay does read (or drop the R supply on a level that reads
R) and the comparison must report a difference (Inferno: levels 3, 4, 6 diverge without R).

## Evidence
- specnext reference/inferno/build/hybrid.md "Dependency map" (observed: replays, disassembly).
- hybrid/skip_results.json, hybrid/taint_results.json (observed, 2,500 frames per level); the probe
  reproduces L1 432/432 and L6 470/471 identical (A1 differs), L6 diverging without R.
- games/inferno.md "Lessons" (this card's application).
