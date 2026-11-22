# Reach a rare scene on screen: invulnerability POKE plus scripted sweep

```json
{
  "schema": 4,
  "id": "verify.scripted-event-reach",
  "revision": 1,
  "kind": "verify",
  "title": "Reach a rare scene on screen: invulnerability POKE plus scripted sweep",
  "question": "How does an agent see a display bug that appears only at one event (a power-up, a boss) without playing by hand?",
  "tags": ["verification", "emulator", "cspect", "screenshots", "display", "test-recipe"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["r_type"],
  "sources": ["specnext reference/r_type/intake/tools/sweep.py (owner's recipe, 2026-11-17); tools/smoke.py"]
}
```

## Use / do not use
Use for display checks of a build (sprites, scenery, glide, colours) at a scene the recording or
random play rarely reaches. The ship is made invulnerable with a POKE, then input is scripted to go
where the event happens and keep firing, with a screenshot every K steps. Ask the owner for the POKE
and the route first: R-Type's (POKE 37362,201: 91F2 = RET; move into the lower two-thirds, sweep up
and down firing) hit the power-up carrier when blind keys had not. Not a gameplay or pace check (the
POKE changes the game): those stay with the recording comparisons.

**Assumptions.** A known invulnerability POKE; an emulator driven by script (CSpect debugger
server, or JNext); a breakpoint or probe that marks "in play".

**Validation gap.** One game (R-Type, CSpect). A bug seen once can need a second run: timing
differs between runs (the doubled power-up showed on the second run only).

## Recognise
- The owner reports a glitch "at the first power-up" or "where the creatures come from the ceiling".
- A display bug that depends on a figure meeting scenery or another figure.

## Probe and stop
1. Load the build, run to the title and the key scan, start a game, run to the in-play probe.
2. Write the POKE (`write_memory`), then hold keys in short bursts (R-Type: 6 x down+fire, then 7 x
   down+fire / 7 x up+fire repeated), a screenshot every K steps.
3. Read the screenshots in order; stop at the first frame showing the bug, or after N steps without.
Stop with the frame numbers that show the bug (or none after N steps, twice).

## Contract
- State: the POKE patches game code; never use these runs as gameplay evidence.
- Time: about one screenshot per three frames; drive one emulator job at a time over one control
  channel (two jobs steal each other's breakpoints and screenshots).
- Display: software = return/boundary only; hardware = checklist item "the scene from the sweep
  shows no glitch on a board"

## Resources owned
None. Test hygiene: a breakpoint at 0000 that catches resets also fires on an extra code page whose
entry is 0000 (start entry tables at 0100); never edit build inputs while a long run rebuilds from
them (LEARNINGS 2.6).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| the ship dies early | POKE written before the game set its code | write after the in-play probe | - | earlier POKE |
| no bullets in the shots | keys held too short / wrong row | hold_frames | 3 frames per burst | - |
| bug not seen this run | timing differs per run | run again | two runs before "fixed" | one clean run |
| "reset" at the first call | a code page entry at 0000 | breakpoint list | entries from 0100 | - |

## Verification
Negative control: run the sweep on the build before the fix; the bug must show in the screenshots.
Then the fixed build, twice. Owner's cadence: this quick check after each change, the full
comparison only before a PR.

## Evidence
- sweep.py runs (observed, CSpect, 2026-11-17): the doubled power-up and the 8x8 square on it
  were found and their fixes checked this way (games/r_type.md Lessons).
