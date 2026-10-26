# Does game logic read figure pixels from the screen?

```json
{
  "schema": 3,
  "id": "detect.gameplay-screen-readers",
  "revision": 1,
  "kind": "detect",
  "title": "Does game logic read figure pixels from the screen?",
  "question": "Would removing a figure from the ULA change what the game decides?",
  "tags": ["analysis", "screen-reads", "collision", "virtual-read"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["atic_atac", "treasure_island_dizzy", "dizzy1"],
  "sources": []
}
```

## Use / do not use
Find every read of a screen byte that holds figure pixels and decide whether the result depends on
the figure. Run it before choosing between removing figures from the ULA (patch.xor-shadow,
patch.scratch-redirect) and keeping them (patch.xor-overlay-keep-ula, or a virtual read). It sets
`screen.gameplay_reads_figure_pixels` for the stated scope only.

## Recognise
- Collision or landing tests that read pixels (Treasure Island Dizzy's bubbles read Dizzy's pixels;
  Dizzy 1's falling objects land on him: 472 of 736 tests).
- Reads that are only a drawer's own read-modify-write do not count (Atic Atac: room-line OR,
  scenery drawers' XOR/OR (HL)).
- A virtual read is wrong where boxes overwrite the player (Dizzy 3/4: screen XOR undo no longer holds).

## Probe and stop
1. List screen reads by PC over the recording (no shared command yet; Atic Atac used a one-off pass).
2. Drop reads by the plotters and by drawers' own read-modify-write.
3. For each remaining reader: does its result change with the figure removed (patched-screen model)?
4. Scope: name the recording, frames, and paths not reached (survey coverage gate).
Stop when every reader in scope is classed; unreached code paths are listed as unknowns, never as
"no reader".

## Contract
- Output: `screen.gameplay_reads_figure_pixels` true / false / unknown with scope, and the reader
  PCs. "Not seen in this recording" is scoped evidence, not absence.
- It does not choose the patch; the design and the user do.

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Behaviour differs only with figures removed (falls through, misses a pickup) | a gameplay reader of figure pixels | this card on that scene's recording | overlay or virtual read | assuming no reader from one recording |
| Virtual read gives wrong results | an overwriter covered the player | list overwriters | no virtual read there | - |

## Verification
For the design it feeds: every screen / attribute read in the patched run sees the original's value
(the verifier's read check); unit cases for readers the recording does not reach.

## Evidence
- games/atic_atac.md "Engine" (no logic reads figure pixels, whole recording; observed).
- games/tid_engine.md (bubbles -> virtual read); games/treasure_island_dizzy.md; LEARNINGS 2.1a
  (screen-reading logic); BRIEFING B3.
- `grep -n 'def guard_read\|def attr_cells' nexclash/atic_atac.py`.
