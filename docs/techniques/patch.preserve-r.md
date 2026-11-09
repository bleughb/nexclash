# Leave R as the original code would, so the game's randomness is unchanged

```json
{
  "schema": 4,
  "id": "patch.preserve-r",
  "revision": 2,
  "kind": "patch",
  "title": "Leave R as the original code would, so the game's randomness is unchanged",
  "question": "Does the game take random numbers from R, so that a hook's different instruction count changes the game?",
  "tags": ["refresh-register", "random", "state", "hook-library"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["exec.game_reads_r"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit"],
  "order": {"entry": {"before": ["patch.restore-speed"]}, "exit": {"after": ["patch.restore-speed"]},
            "cross": ["HLIB_R_IN is the hook's first code after the site", "HLIB_R_OUT is the last before the return"]},
  "owns": {"hook_state": ["HLIB_V_R"]},
  "examples": ["inferno"],
  "sources": ["pilot runs/nightshade/nexclash/asm/nightshade_hooks.asm (mkT; the verifier compares R, negatives 'R off by one')",
              "pilot NEXCLASH-CHANGES.md: owner decision, preserve R by default for new builds (2026-11-04)",
              "asm/lib/hlib_r.asm + nexclash/hooklib.py (the shared library)"]
}
```

## Use / do not use
Default for every NEW engine (owner decision 2026-11-04): with it the same inputs give the original's
game, enemies and deaths included, so recordings stay in step and the pace meter compares like with like.
Needed whenever the game reads R (Atic Atac: 9 sites; Nightshade). Existing games: an opt-in rework with a
version bump. No R readers need no preservation. Equivalence is extremely close, not 1:1 (owner,
2026-11-10): keep this card where it is cheap (the library); where exact R needs costly machinery (timed
windows, lost-IRQ accounting), a replay feeds the recorded `LD A,R` values instead (detect.routine-removal;
Inferno: R is only a random source). Record consumer evidence and validation limits for that exception;
supplied-R replay proves behaviour under those values, so also validate natural gameplay.

**Assumptions.** R counts one per M1 cycle in bits 6:0 (prefixed opcodes two); bit 7 changes only by LD R,A;
the original's M1 count from the site to the return point is a constant or a simple function of its
inputs (Nightshade's colour box: 11 + 7B).

**Validation gap.** Library unit tests on the simulator (SkoolKit counts R as the Z80); Nightshade's engine in
its pilot verifier. Interrupts landing inside a hook add their own M1s in both builds alike only if they land
at the same instruction count: not modelled.

## Recognise
`ED 5F` in game code; a build whose encounters differ from the original's with the same keys (Atic
Atac v1.1: the replay checker excluded R).

## Probe and stop
1. `hooklib.r_span(r0, r1)` over the original from the site to the return point (simulator) = O.
2. Count E (site through HLIB_R_IN, the macro 3) and N (after HLIB_R_OUT's LD R,A, the macro 1);
   `hooklib.r_delta(O, E, N)` is the constant for `hlib_r_set`; a variable part goes to `hlib_r_add`.
3. The verifier compares `hooklib.CMP_R`; `hooklib.r_check` says what to add when R differs.
For exact preservation, stop when R matches at every site in recordings and unit cases.

## Contract
- State (exact mode): R after the hook = R after the original, bit 7 included; every other register and flag kept by the
  macros. Equivalence boundary: R is compared, so CMP_R replaces CMP for this engine.
- Time: about 100 T at 28 MHz per hook. Hook stack: 2 bytes (HLIB_R_IN); interrupt headroom: as the hook.
- Display: software = return/boundary only; hardware = checklist item "the same keys give the same enemies as the original"

## Resources owned
HLIB_V_R, 3 bytes of hook RAM (one hook level).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| 'R differs!' by a constant | E or N miscounted | r_check | add it to the delta | excluding R from CMP |
| differs by a multiple of the loop count | O depends on an input | disassemble the loop | hlib_r_add at run time | - |

## Verification
Exact mode: differential replay with CMP_R at every site; unit cases with random R (bit 7 both ways). Negative control:
a delta one off (`hooklib.NEGATIVES` "wrong R on exit") must give 'R differs!'.

## Evidence
- `grep -n 'MACRO HLIB_R\|^hlib_r_' asm/lib/hlib_r.asm`; `grep -n 'def r_\|def _t_r' nexclash/hooklib.py`.
- Nightshade: `grep -n 'ld r,a\|mkT' nightshade_hooks.asm` (pilot copy), observed in its verifier.
