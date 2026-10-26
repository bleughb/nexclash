# Find the unit the hooks must track (whole image, partial image, composite)

```json
{
  "schema": 3,
  "id": "detect.tracked-unit",
  "revision": 1,
  "kind": "detect",
  "title": "Find the unit the hooks must track (whole image, partial image, composite)",
  "question": "Does one plot call draw a whole figure, part of one, or one piece of a multi-part object?",
  "tags": ["analysis", "partial-draw", "rows", "composite", "xor"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["atic_atac"],
  "sources": []
}
```

## Use / do not use
Classify every plot entry by what one call draws, before choosing hook sites or a Display check.
"XOR" or "masked" alone does not choose a design; the tracked unit does. Use for every figure
plotter of an unknown game. It answers only "what unit must the hooks and the Display check
track", nothing else.

## Recognise
- Row blitters called many times per figure (Atic Atac: 0x9EDC / 0x9F21, one row of 2-3 bytes per
  call, 235-247 T each, 85-86 calls in busy frames): hook per figure, not per row.
- Effects that draw a slice of a figure per call (Atic Atac appear / death: one row k per plot,
  height poked to 1 and restored).
- Several objects forming one figure (Rainbow Islands bosses: one object per quarter).
- False reading: heights taken from the static graphic bytes when the game pokes them at run time.

## Probe and stop
1. Per plot entry: rows / bytes one call writes vs the graphic's height byte or row count, from a
   trace at the entry (`cost GAME.z80 --rzx R --at ENTRY --group IX` for calls per object).
2. Repeat for every effect the recording reaches (appear, death, flash, shop, boss).
3. Check run-time writes into graphics or height bytes (the effect may patch them).
Stop when every entry is classed whole image / partial image (with how parts join: row mask,
quarter, slice) / composite object, or the unclassed entries are named as unknowns.

## Contract
- Output: per entry, the unit and its join rule, with basis and scope (which effects were reached).
- It does not establish that hooking at that unit is safe, nor the Display check's coverage.
- Stays `candidate` until a second game exercises the row-mask (partial image) path.

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Ghost figure kept on screen while the original's was blank (Atic Atac: 18 slices + figure) | parity kept per draw call, not per tracked unit | this card | image groups with a 24-bit row mask | per-image parity (DE, x, y) |
| Hook cost too high | hooked per row | `cost --at` | hook per figure | - |
| Boss or vehicle shown in pieces | composite object not joined | trace object records | join by graphics area or owner | - |

## Verification
For the design it feeds: the Display check compares by tracked unit; unit cases cover each partial
path (every slice index, both directions); a negative control with per-call parity must fail.

## Evidence
- games/atic_atac.md "Build design" (CORRECTION stage 2 part 2; IMAGE GROUPS), observed, whole RZX.
- LEARNINGS 2.1a (figure = the game's object; bosses as several objects).
- `grep -n 'def kept_rows\|def build_image\|def rows_of' nexclash/atic_atac.py`; asm labels
  `group`, `tog`, `mbit`: asm/atic_atac_hooks.asm.
