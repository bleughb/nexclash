# Half-pixel hardware scrolling: two Layer 2 640x256 screens, one shifted half a pixel

```json
{
  "schema": 4,
  "id": "patch.layer2-half-pixel-scroll",
  "revision": 1,
  "kind": "patch",
  "title": "Half-pixel hardware scrolling: two Layer 2 640x256 screens, one shifted half a pixel",
  "question": "Does slowly scrolled scenery judder because each 1-pixel step is held for several frames, and can the step be halved without changing the game's speed?",
  "tags": ["scroll", "layer2", "640x256", "half-pixel", "smoothness", "judder", "hybrid"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["routine.display_only_effects"],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup", "commit", "isr"],
  "order": {"commit": {"after": ["patch.hybrid-display-replacement"]},
            "cross": ["the scroll step selects screen B at once and the ISR returns to screen A two frames later",
                      "every new column is drawn into both screens before it scrolls into view"]},
  "owns": {"next_pages": "param", "hook_state": ["L2_S", "L2_HS", "PC_LP"]},
  "examples": ["r_type"],
  "sources": ["specnext reference/r_type/intake/l2scroll.asm (l2_scroll, l2_half, put_cell, l2_stage, l2_convert)",
              "specnext PR #99 (r-type-hires); dev guide r3: 640x256 scrolls by two of its pixels; tilemap 80x32 offset 0-639"]
}
```

## Use / do not use
Use when scenery already lives on Layer 2 (patch.hybrid-display-replacement) and moves 1 pixel per game update held for 3+ frames, so the eye sees a start-stop rhythm (R-Type: 1 px per 4 frames). Layer 2 640x256x4 shows each Spectrum pixel as one byte (two half pixels), but its scroll register (NR 0x16 / 0x71, 0-319) moves whole Spectrum pixels. Keep two screens: A as drawn, B with every byte's left half taken from the pixel to its left (the picture shifted right half a pixel). On each game step show B at the new scroll value; two frames later show A: half a pixel every 2 frames, same speed. Do not use for figures (sprites position in whole pixels; see patch.figure-glide) or when 160 KB of Next RAM is not free. The tilemap's 80-column offset is in half pixels, but its map and tiles live in bank 5 or the lower 8 KB of bank 7: rejected where the game's live data fills bank 5 and too few hi-res tiles fit.

**Assumptions.** The game scrolls the scenery by whole pixels at a steady rate; 160 KB of Next RAM is free for two screens.

**Validation gap.** CSpect only (R-Type, all levels); no board run; a 1 MB Next's bank range not checked.

## Recognise
Smooth sprites over scenery that "jitters"; measured scenery steps of 1 px every N >= 3 frames.

## Probe and stop
Screenshot consecutive frames (scale 2 = 640 wide) and match each frame against the next by horizontal shift: before, -2 every 4 frames; after, -1 every 2. Read NR 0x12 per frame: B for two frames after a step.

## Contract
- State: display only; the game's maps and its own scroll counters are untouched.
- Time: the column draw doubles (two screens); level start redraws both (R-Type 114 -> 179 frames). Hook stack: 8 bytes for its own calls and pushes; interrupt headroom: 2 more bytes at every hook instruction while IFF is on (l2_half).
- Display: software = return/boundary only; hardware = checklist item "scenery scrolls smoothly, no shimmer on right edges"

## Resources owned
Ten 16K banks (two 80 KB screens, R-Type 48-57), a 160-byte left-neighbour row buffer (PC_LP), the scroll word and the half-step counter.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| right edges flicker at every half step | B's first sky byte never got the scenery's half pixel (sky cells skipped at level start) | dump B beside A at an edge | draw sky cells clear too | - |
| B looks shifted the wrong way | nibble order | dump bytes | left pixel = high nibble (guide r3) | - |
| no half steps seen | B never selected | NR 0x12 per frame | select B in the scroll step, A from the ISR | - |

## Verification
Shift per frame by image matching (above); A and B byte dumps across a scenery edge; smoke pacing unchanged. Negative control: skip the B selection and the per-frame shift returns to 2 every 4 frames.

## Evidence
Observed in CSpect on R-Type levels 1-8 (specnext PR #99): -1, 0, -1, 0 per frame. Not yet on hardware. Memory above the first 768 KB: check a 1 MB Next (inferred risk).
