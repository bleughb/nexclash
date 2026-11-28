# Scenery in front of sprites with see-through edges: masks worked out from the whole level

```json
{
  "schema": 4,
  "id": "patch.scenery-edge-masks",
  "revision": 1,
  "kind": "patch",
  "title": "Scenery in front of sprites with see-through edges: masks worked out from the whole level",
  "question": "Figures pass behind scenery in the original, but the scenery's black paper hides them in whole 8x8 cells: can the black that is open to the sky become transparent without per-frame work?",
  "tags": ["scenery", "layer2", "transparency", "8x8", "cells", "mask", "flood", "layer-order", "hybrid"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["routine.display_only_effects"],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup", "commit"],
  "order": {"commit": {"after": ["patch.layer2-half-pixel-scroll"]},
            "cross": ["the mask is looked up when a staged scenery cell is drawn to Layer 2, never per frame"]},
  "owns": {"next_pages": "param", "hook_state": ["PC_KEY", "PC_MASK"]},
  "examples": ["r_type"],
  "sources": ["specnext reference/r_type/intake/scenery_masks.py (level_cells, open_black, level_masks)",
              "specnext reference/r_type/intake/l2scroll.asm (mask_find, put_cell); PR #99"]
}
```

## Use / do not use
Use when scenery is drawn on Layer 2 in front of sprites (NR 0x15 Layer 2 over sprites, as the original's owner map makes scenery win) and its black paper shows sprites cut in 8x8 squares. Draw each level's whole scenery offline from the game's own map (verify the decoder against the game's initial draw), then flood black from open sky, 4-connected across cells. Black runs of 1-2 pixels with coloured scenery both sides are walls, so narrow gaps stay solid. The runtime knows a staged cell only by its content, so store one mask per distinct cell (attribute + 8 bytes; majority where a cell is used in several places), sorted per level, and binary-search it when the cell is drawn. Do not use when the scenery is generated at run time (no offline whole level) or when a cell's correct mask differs wildly by position (count the conflicts first).

**Assumptions.** The level's scenery can be drawn offline from the game's own map (decoder checked against its initial draw); a cell's mask rarely depends on where it is used.

**Validation gap.** CSpect only (R-Type levels 1 and 5 examined); per-level conflicts not reviewed in play; no board run. Yie Ar Kung-Fu: a fixed graphic the game ORs over the figures each tick (Feedle's caves) needs no offline map: its ink alone on Layer 2, shown at the flip of the screen it was drawn on (replay-checked).

## Recognise
Sprites "behind" scenery lose whole cells; the original's black between scenery details is paper, not a colour.

## Probe and stop
Count per level: distinct scenery cells, cells with see-through pixels, cells with conflicting masks (R-Type: at most 634 / 263 / 42). Render the level offline with see-through pixels red, before and after the gap rule; build a debug variant drawing them red in the game.

## Contract
- State: display only.
- Time: one binary search (about 10 steps) per staged cell, plus the page mapping. Hook stack: 6 bytes for its own calls and pushes; interrupt headroom: interrupts off: n/a.
- Display: software = return/boundary only; hardware = checklist item "figures pass behind scenery cut by its pixels, not 8x8 cells"

## Resources owned
Per level: a keys page (count + sorted 9-byte keys) and a masks page (8 bytes each); R-Type banks 16-23. Build-time only otherwise.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| first screen unmasked in a mid-level test build | snapshot cells already shifted by the original's copier | full-game debug build | test from a level start | - |
| building interiors see-through | 1-2 px channels to the sky | offline red render | gap walls | flooding per cell only (too local) |
| too slow at run time | flood at run time | update histogram | build-time masks | whole-column runtime flood (parked) |

## Verification
Offline red renders per level; in-game debug build (see-through as red) on the first screen and on scrolled columns; pacing unchanged. Negative control: an empty mask table gives solid black (old look).

## Evidence
Observed in CSpect, R-Type levels 1 and 5 (flowers). Majority conflicts: inferred acceptable, not checked in play on every level.
