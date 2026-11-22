# Prove a ported routine stage by stage, with mutants, sweeps and a whole-recording gate

```json
{
  "schema": 4,
  "id": "verify.staged-port-gates",
  "revision": 1,
  "kind": "verify",
  "title": "Prove a ported routine stage by stage, with mutants, sweeps and a whole-recording gate",
  "question": "How is a rewritten routine (renderer, maths) shown equal to the original beyond the inputs a recording happens to hold?",
  "tags": ["verification", "port", "mutants", "sweep", "harness", "renderer", "maths"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["castle_master"],
  "sources": ["specnext reference/castle_master/build: m0_pipeline.py, m1_gate.py, m1_unit.py, m3_sim.py, m3_mutants.py, m3b_seq.py"]
}
```

## Use / do not use
Split the original into stages at fixed PCs, capture each stage's input and output from the recording,
and gate the port at every stage and end to end. Use for any routine rewritten rather than hooked.
A hook around unchanged code needs only PLAYBOOK 6.

**Assumptions.** The stages' data can be read at fixed PCs; a state per update (RAM at the block's
start) fits on disk (Castle Master: 5,233 states).

**Validation gap.** One game. The harness scripts are per engine (specnext), not a shared tool.

## Recognise
- A replacement checked only on recorded calls: two of four maths mutants passed every recorded input.
- A rare path: one cube wrong in one redraw of 5,233 (a missed cull stage); a sampled run misses it.

## Probe and stop
1. Host port (Python) of each stage = the game's data at ALL updates, then the Z80N code = the host port.
2. Per stage, mutants that must fail. A mutant can be equivalent (a sign bit never set): replace it.
3. Random sweeps inside the inputs' domain only (beyond it 16-bit sums wrap or the original reads past
   a table: false failures). Size copied tables by the domain, not by the recording.
4. Force inputs the recording never has (a flag, a rare effect); drive the game's own routine at
   swept positions for edges (found an 8-bit wrap at a cursor's bottom row).
5. End to end at every update, then the build's own code along the recording with the previous
   update's hardware state kept. Later rounds: every 10th update + the sequence test, unless the
   renderer changed.

Stop when all updates, sweeps and mutants agree.

## Contract
- Compared: the stage's output bytes, then display pixels against a model of the original; registers
  but R and all game RAM at the block's end.
- Pace is gated only where both runs took the same path: count the game's own main-line instructions
  (the game reads real time, so the right build can take another path).

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| a junk-filled buffer differs | the renderer reads-modifies-writes | - | start from the buffer before the game's render | junk fill |
| a bisect names a random byte | it already fails on the start state | bisect from the block's START | - | - |
| a control passes | it saves, clobbers, then restores; or its path is rare | run it alone | a direct check on that path | counting it |
| "sprites off" mutant passes | every state starts from clean hardware | - | plant the previous view's state | - |
| a mutant passes with hooks modelled | the test's model, not the build's code, ran | - | run the hooks' own bytes | - |
| interrupts stay off at random | SkoolKit's LD A,I / R quirk on its own frame | int_active | int_active 0; clear P/V at accepted interrupts | - |
| frame counts run ahead | Fuse writes a ~20 T RZX frame after a DI-delayed interrupt | frame T | weigh frames by T | counting frames |

## Verification
The gate's own negative controls: every mutant fails, the original against itself passes.

## Evidence
- games/castle_master.md "Lessons" and M0-M3b results (observed in the simulator; hardware agreed by eye).
- `grep -n '^def ' m3_sim.py m3_mutants.py` (specnext).
