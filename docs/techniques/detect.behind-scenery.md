# Behind-scenery census: which figures does the original hide behind scenery?

```json
{
  "schema": 4,
  "id": "detect.behind-scenery",
  "revision": 1,
  "kind": "detect",
  "title": "Behind-scenery census: which figures does the original hide behind scenery?",
  "question": "When sprites go in front of the scenery, which figures did the original draw behind it, and which only brush a wall?",
  "tags": ["analysis", "depth", "scenery", "layer-order", "owner-map", "recording"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["r_type"],
  "sources": ["specnext reference/r_type/intake/tools/behind.py (scan, write_flags)",
              "specnext reference/r_type/intake/behind_flags.asm; l2sprites_body.asm behind_chk (L2_BEHIND_FLAGS)"]
}
```

## Use / do not use
Use in design (PLAYBOOK 3) before moving figures in front of scenery, for a game whose plotter
decides depth per 8x8 cell (an owner map, a scenery-cell test). It gives the owner a list: families
hidden in many updates come out from behind scenery; one or two updates only brush a wall. Not
needed without a depth test, or once the owner chose "every figure in front" (R-Type's final
choice, with `patch.scenery-edge-masks`).

**Assumptions.** The depth decision is one instruction that reads the cell's owner; the recording
visits the levels and enemies that matter; the plotter's graphic address identifies the family.

**Validation gap.** One game (R-Type, one full recording). The threshold (50 updates) was chosen by
eye from the sorted list, not proved.

## Recognise
- The figure plotter reads a per-cell map before writing a cell and skips the cell on one value
  (R-Type 8ED6: owner map 7E00 = FF -> scenery wins).
- The recording checklist item "figures walking in front of and behind scenery" shows figures cut
  in 8x8 squares where they meet scenery.

## Probe and stop
1. Replay the recording (`nexclash.simrun.play_rzx`) with two hooks: at each plotter entry record
   the graphic address (R-Type: BC at 8CFD / 8D65 / 8DD3 / 8E29); at the owner test, when the owner
   is "scenery" and the plotter is drawing a figure (not scenery itself: R-Type checks the plot
   destination 8EBF = 0x60), count the cell for (level, graphic, ink).
2. Per family (registry r_type_figures.json), count distinct updates hidden, cells hidden, first
   frame. Sort by updates.
3. Write the flag table as editable source (one `FLAG level, graphic` line per graphic with the
   counts as comments), so the owner or a later agent changes it without the scan.
Stop with the sorted list and the owner's choice. Sets `figure.behind_scenery` per family.

## Contract
- State: none (analysis only). The build reads the flag table only under a build switch
  (R-Type `L2_BEHIND_FLAGS`, off by default): a flagged figure is not made a sprite and stays in
  the ULA under Layer 2.
- Time: n/a (replay; slow - the whole R-Type recording took a long run, use `--frames` for trials).
- Display: n/a (analysis); the build choice is the owner's (CLAUDE.md "Ask the user").

## Resources owned
None. (The optional flag table at run time: R-Type bank 13, page 26.)

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| every graphic reported "not listed" at run time | the lookup compared A after it was overwritten | step behind_chk on a listed graphic | compare before reusing A | - |
| scenery counted as hidden figures | the plotter draws scenery through the same test | plot destination at the hit | skip hits while the plotter draws scenery | - |
| explosions and shots flagged | they pass walls for a few updates | updates count | threshold, or unflag by type (owner: "unflag explosions, shots") | flagging by cells hidden |

## Verification
Negative control: a level with no scenery depth (or the recording cut before any scenery) lists no
family. Check two flagged families on screen in the original (contact sheet of the hit frames).

## Evidence
- behind.py scan over Rtype.rzx (observed): 71 families above 50 updates, written to
  behind_flags.asm; the owner first asked to keep them behind (2026-11-16), then chose all figures
  in front with scenery masks (2026-11-17); the switch stays in code.
- games/r_type.md "Lessons" (this card's application).
