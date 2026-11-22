# Mosaic transition: pixelate one Layer 2 picture, depixelate the next

```json
{
  "schema": 4,
  "id": "patch.mosaic-transition",
  "revision": 1,
  "kind": "patch",
  "title": "Mosaic transition: pixelate one Layer 2 picture, depixelate the next",
  "question": "Can the Next change from the original screen to an upscaled picture with a full-colour effect instead of a hard cut?",
  "tags": ["layer2", "320x256", "transition", "showpiece", "title-screen", "palette", "effect"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["menu"],
  "order": {"cross": ["both pictures share one 256-entry palette, loaded before the first step",
                      "the original is shown on Layer 2 first, so the change to Layer 2 is invisible"]},
  "owns": {"speed": "28MHz while it runs, caller's NR 7 restored",
           "mmu_slots": [3, 7], "hook_state": ["tr_blk", "tr_src", "tr_x", "colbuf"]},
  "examples": ["r_type"],
  "sources": ["specnext reference/r_type/intake/glide.asm transition, mosaic, waitf; showpiece.py original_banks, indexed_320; PR #99"]
}
```

## Use / do not use
Use to move between two still screens at start-up or in a menu: the original's screen and its
upscaled "wow" version (`patch.copper-palette-bands` for the picture). Both are Layer 2 320x256 x 8:
the picture in screen A, the original placed at its spot in 320x256 (R-Type: 256x192 at 32, 32) in
spare banks, its colours in palette entries the picture does not use (one shared palette, so no
palette change mid-effect and the effect stays in colour throughout). Each step draws a mosaic of
block size B into screen B and shows it: out 2, 3, 4, 6, 8, 12, 16, 24 from the original, swap
source at the blockiest step, in 24 ... 2 to the picture, 2 frames a step, then show screen A. Not
for a 640x256 x 4 picture (16 colours per band: the two pictures' colours do not fit one palette).
Owner rule: in colour, no flash or hard cut.

**Assumptions.** About 15 spare 16K banks (picture, original, work screen; R-Type 48-62: a 1 MB
Next may not have them - not yet checked); 28 MHz for the steps.

**Validation gap.** CSpect only. Tears slightly (the next mosaic is drawn into the screen being
shown - inferred, not traced); thin lines of the original thin out when sampled.

## Recognise
An owner request for a "pixelate / depixelate", "dissolve" or "morph" between two still screens.

## Probe and stop
Preview offline: the same sampling in Python over both bank sets, one PNG per step. In CSpect,
screenshot each step (waitf counts frames on NR 0x1F).

## Contract
- State: none of the game's (start-up or menu); NR 7, MMU 3 and 7 saved and restored; source page
  in slot 7, destination in slot 3 (at start-up the NEX stub's stack is in slot 6: never map there).
- Time: one mosaic = 320 column reads + 320 LDIRs of 256 bytes at 28 MHz, within 2 frames.
  Hook stack: 16 bytes for its own calls and pushes; interrupt headroom: not measured (start-up
  handler only).
- Display: software = return/boundary only; hardware = checklist item "transition in colour, no
  flash, picture complete at the end" (approved change, owner 2026-11-17)

## Resources owned
Layer 2 screen B as a work screen while it runs (R-Type banks 53-57); slots 3 and 7 temporarily; a
256-byte column buffer in the code page.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| crash at the first step | a page mapped into slot 6 (start-up stack) | SP at the crash | use slots 3 and 7 | - |
| colours jump at the swap | two palettes | palette at the blockiest step | one palette, the original in unused entries | palette fade |
| tearing during a step | drawing into the shown screen | screenshot mid-step | alternate two work screens (needs 5 more banks) | - |
| the original looks thin when pixelated | one sample per block misses thin lines | compare with a block majority | majority / brightest pixel per block (not done) | - |

## Verification
Screenshot every step: block sizes in order, colour on every step, final frame identical to the
picture. Negative control: a second palette for the original shows a colour jump at the swap.

## Evidence
- glide.asm transition / mosaic (observed in CSpect, R-Type start-up, 2026-11-17).
- showpiece.py original_banks puts the original's colours in the picture's unused entries (observed).
