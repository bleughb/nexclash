# Defer the game's ISR while a non-re-entrant hooked routine runs

```json
{
  "schema": 3,
  "id": "patch.isr-deferral",
  "revision": 1,
  "kind": "patch",
  "title": "Defer the game's ISR while a non-re-entrant hooked routine runs",
  "question": "Can added hook time let an interrupt land inside a routine the ISR also calls?",
  "tags": ["interrupt", "re-entrancy", "timing", "im2"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["exec.isr_calls_routine", "exec.routine_not_reentrant", "hook.adds_time", "exec.interrupts_on_at_sites"],
  "rejects": ["exec.isr_must_run_on_time"],
  "conflicts": [],
  "phases": ["entry", "isr", "exit"],
  "order": {
    "entry": {"after": []},
    "exit": {"before": ["patch.display-atomic-switch"]},
    "cross": ["entry increments DEPTH before the routine body runs",
              "a deferred ISR runs only at the exit that returns DEPTH to 0"]
  },
  "owns": {"vectors": ["im2"], "hook_state": ["DEPTH", "PENDING"]},
  "examples": ["incredible_shrinking_fireman-add-OPUS"],
  "sources": []
}
```

## Use / do not use
Count hook depth and defer the game's interrupt handler to the outermost hook exit, when the
handler calls a routine that is not re-entrant and the hooks add time. Do not use when the handler
must run on time (music, raster), or when interrupts are off at the sites. Unknown re-entrancy or
ISR call paths defer the card: run the probes first.

## Recognise
- The original avoids nesting only by timing: its main-loop calls end before the interrupt in the
  frames where the ISR calls the same routine (Fireman: at least 2.0K T before).
- The routine keeps globals or self-modified operands (Fireman: 0xBD17-0xBD41, operand 0xBCD2).
- False positive: an ISR that calls a *different* entry with its own state.

## Probe and stop
1. `isr GAME.z80 --rzx R`: the handler and what it calls.
2. Disassemble the routine: its writes to fixed memory or its own code.
3. Gap: T from the last main-loop call's exit to the interrupt, in frames where the ISR also calls it.
Stop when all of `requires` / `rejects` are settled for this routine; any unknown names its probe.

## Contract
- State: the handler runs exactly once per interrupt, at depth 0, returning to the deferred
  caller (its RETN goes there); the patched routine is never entered while a call is in progress.
- Time: the handler runs a few thousand T late. Hook stack: the entry/exit counters need no stack
  beyond the hooks' own; interrupt headroom: the deferring stub returns at once (EI; RET), so it
  needs only the interrupt's own 2 bytes.
- Display: none of its own; composes with patch.display-atomic-switch.
- Display: software = return/boundary only; hardware = checklist item "no corrupt or extra figures in rooms where the ISR plots"
- The game may rewrite the vector on restart: patch the setter's operand too (Fireman: 0xC234
  rewrote 0xFFF4 at RZX frame 32335; operand 0xC240).

## Resources owned
The IM 2 vector (or the IM 1 path), two bytes of hook state (DEPTH, PENDING). Values per game in
its record.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Extra or corrupt figures where the ISR plots (Fireman room 5) | interrupt inside a non-re-entrant plot; inner plot overwrote globals | inject interrupts inside main-loop plots | this card | save/restore the globals: the ISR plots the SAME object, so the outer plot XORs a stale image |
| Main code starves, frames overrun | interrupts held off in hardware | - | defer instead | hardware IM 2 hold |
| Deferral gone after game over | the game rewrote the vector | verifier "game wrote a patch site" | patch the setter's operand | - |

## Verification
- Every deferral in the recording: handler entered once, at depth 0, return address = the caller.
- Interrupt injection at many points inside main-loop calls: patched state intact (Fireman: 20
  points in 2 plots; the original corrupts 19 of 20 in one).
- Negative control: deferral removed -> injection must fail.
- Hardware: the rooms or scenes where the ISR draws.

## Evidence
- games/incredible_shrinking_fireman-add-OPUS.md "Hardware round 2" (observed, RZX 32,492 frames).
- `grep -n 'def _defer_check\|def _inject\|def _im2_setup' nexclash/incredible_shrinking_fireman_add_opus.py`
- asm labels `e_ent`, `e_plot`, `e_isr`: asm/incredible_shrinking_fireman-add-OPUS_hooks.asm.
