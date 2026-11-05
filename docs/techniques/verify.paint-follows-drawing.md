# Paint an Enhanced set by the drawing: every colour change on a drawn line or a shape change

```json
{
  "schema": 4,
  "id": "verify.paint-follows-drawing",
  "revision": 1,
  "kind": "verify",
  "title": "Paint an Enhanced set by the drawing: every colour change on a drawn line or a shape change",
  "question": "Does every colour boundary of an Enhanced set sit on a line the artist drew, or where the drawn shape narrows, and never straight across a flat area?",
  "tags": ["colour", "enhanced", "painter", "looksheet", "recolour"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": [],
  "sources": ["pilot BRIEF-3.md 'Painting by parts: follow the drawing, not blocks' (Dean, Jon 2026-11-04)",
              "pilot runs/nightshade nightshade_paint.py v3 part maps (approved), runs/robin_of_the_wood robin_enhanced.py",
              "docs/REFACTOR.md 19-22"]
}
```

## Use / do not use
Every new Enhanced colour set: `python -m nexclash.paint regions` then `paint` (docs/COLOURS.md PAINTER)
before any hand work. Block, row or attribute-cell colouring only when the author asks for it. Not for
existing games' colour sets: they are repainted only when the owner picks a game (REFACTOR scope).

**Assumptions.** The figure's drawing separates its parts: a dark line class (Target: Renegade's black
ink, Nightshade's black mask), or one class with the engine's filled holes (Robin). A face with no line
round it needs the family's `facing` label (Robin's profile: a band along the head's front contour).
The sheet's palette is the build's: with the 15 Spectrum colours the automatic colours are rough; a
preset or the author's touch-up (export / import) sets them.

**Validation gap.** Proved on samples only, no build repainted: Nightshade's hero against the approved
v3 (regions allow 94.2% of v3's ink parts; the back views' shoulder band and the boot splits are v3's
own hand splits), Robin's 8 head views, Target: Renegade's sheet. Not seen on hardware.

## Recognise
- An owner says the set is "blocky", a hood stops at a row, a sleeve or face is a box (Dean on
  Nightshade: "obsessed with attribute blocks").
- The look sheet's CUT flags a straight colour boundary of 3+ pixels.

## Probe and stop
1. `regions`: look at regions.png; regions follow the drawn lines, a split only at a neck or a limb.
2. Label each family's key frame in parts.json (part, `facing`); weak matches in the report are checked.
3. `paint`: compare.png and the look sheet; stop at CUT 0, no RIM, no VANISH, then `recolour`.

## Contract
- A colour boundary lies on a drawn line, a pattern change (dither) or a neck of 2 pixels or less.
- The drawing's lines keep their colour; no white outline or edge highlight unless a preset asks.
- Output is the recolour format: the painted sheet with its own layout, so `recolour` makes the build.

## Resources owned
None (display banks only, through recolour).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| hood cut at a row | row-band rule | looksheet CUT | regions by lines | moving the row |
| face is a box | head split by a box | regions.png | facing band / enclosed shape | a bigger box |
| white rim | edge highlight | looksheet RIM | edge ring takes the line colour | thinner white |
| two frames differ | part matched wrong | weak-match lines | relabel the key frame | per-frame boxes |

## Verification
Negative control: `selftest.py --tools` paints a synthetic figure (CUT 0, read back as recolour reads
it) and colours the same figure in two row bands, which the look sheet must flag.

## Evidence
- docs/CHECKS.md "looksheet" (the painter's samples, 2026-11-04).
- `grep -n 'def segment\|def split_shape\|def carry\|def resolve_cuts' nexclash/paint.py`.
