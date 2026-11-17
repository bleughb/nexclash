# Flash colours through the sprite palette offset: one conversion per graphic

```json
{
  "schema": 4,
  "id": "optimise.flash-palette-offset",
  "revision": 1,
  "kind": "optimise",
  "title": "Flash colours through the sprite palette offset: one conversion per graphic",
  "question": "A figure flashes by being redrawn with a colour override: does each colour cost a separate pattern conversion and cache entry?",
  "tags": ["sprites", "palette", "palette-offset", "flash", "colour-override", "pattern-cache"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["sprite.patterns_built_at_runtime"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry"],
  "order": {"entry": {"after": ["optimise.pattern-cache"]},
            "cross": ["the override becomes a palette offset before the cache lookup, so every flash colour hits one entry"]},
  "owns": {"hook_state": ["R_PAL"]},
  "examples": ["r_type"],
  "sources": ["specnext reference/r_type/intake/l2sprites_body.asm (spr_record: 8EB1 -> r_pal; spr_setup flash palette entries; emit); PR #99"]
}
```

## Use / do not use
Use when the game draws a figure with a colour override (R-Type: 8EB1, one ink for every cell) and the sprite converter keys its cache by graphic + ink. Convert the graphic once in colour 1; set the sprite's palette offset (attribute 2 bits 7-4) to the flash colour n, with sprite palette entry 16n+1 = colour n (transparent index 0 is per nibble, so it stays transparent). Every flash colour then shares one cache entry and the colour change costs only the attribute. Do not use when an override keeps per-cell colours or a paper colour (the pattern is then not two-colour), or when painted colours must apply during the flash.

**Assumptions.** The override applies one ink to every cell on black paper, so the converted pattern is two-colour.

**Validation gap.** CSpect only (R-Type level 1 power-up, owner sweep test); other flashing figures and levels not measured; no board run.

## Recognise
Cache fills or restarts in scenes with flashing pick-ups; figures falling back to native 8x8 drawing while re-converted.

## Probe and stop
Scan the recording for plots with a non-zero override: values and graphics (R-Type: 43-46, bright inks on black, three graphics). Read the converter's cache counters (entries, restarts, refusals) in that scene.

## Contract
- State: display only.
- Time: removes conversions; adds a few instructions per plot. Hook stack: 2 bytes for its own calls and pushes; interrupt headroom: interrupts off: n/a.
- Display: the flashing figure shows in the override colour exactly; painted colours do not apply to override plots (the game's own rule).

## Resources owned
Sprite palette entries 16n+1 for n = 1-15; one byte of hook state.

### Measurements
Workload: R-Type level 1 power-up, 4 flash colours x 3 graphics. Before: 12 cache entries for the power-up alone; with a 44-56 entry cache the cache restarted and figures were drawn natively for a few updates (8x8 squares seen by the owner). After: 3 entries; no square seen in the owner's sweep test (CSpect, Builder 4.5.9, 28 MHz). Does not help when overrides are rare or the cache is large enough.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| flash shows 8x8 squares | cache restart; native fallback | cache counters | one conversion per graphic | a bigger cache only |
| wrong flash colour | palette entries not set | sprite palette dump | write 16n+1 at setup | - |

## Verification
Owner sweep test (invulnerable, firing) through the power-up; cache counters in that scene. Negative control: key the cache by ink again and the entries return to 12.

## Evidence
Observed in CSpect (owner confirmed "looks ok"). Hardware not yet run.
