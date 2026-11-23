# Ink-rectangle figure as sprites clipped to the rectangle

```json
{
  "schema": 4,
  "id": "patch.ink-rectangle-sprites",
  "revision": 1,
  "kind": "patch",
  "title": "Ink-rectangle figure as sprites clipped to the rectangle",
  "question": "The game ORs a figure's pixels into the screen, then ORs its ink into a rectangle of cells: can sprites show exactly the pixels that ink makes coloured, with no clash on the rest?",
  "tags": ["sprites", "clash", "attributes", "clip-window", "mirror", "pattern-cache"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["render.paints_figure_attributes", "design.no_figure_clash", "sprite.working_set_fits"],
  "rejects": ["screen.gameplay_reads_figure_attributes"],
  "conflicts": [],
  "phases": ["entry", "commit", "isr"],
  "order": {
    "cross": ["the attribute hook notes the rectangle before the present reads it",
              "sprite attributes and the clip window change in the interrupt that flips the screen, never between flips"]
  },
  "owns": {"sprite_ids": "param", "pattern_slots": "param", "hook_state": ["c_on", "c_race", "c_aon", "c_cl"]},
  "examples": ["cisco_heat"],
  "sources": ["games/cisco_heat.md Design (the player's car, v1.2, 2026-11-22)"]
}
```

## Use / do not use
Use when one figure is OR-blitted as 1-bit images, then coloured by an ink OR over a cell rectangle,
so other pixels in those cells take its colour. Do not use when game logic reads those attributes (keeping the old ink changes what it reads), or when
the figure's images exceed the pattern memory left after the cache's fixed slots.

**Assumptions.** The figure's colour is one ink (the ULA palette entry, read at set-up, is sprite colour
1); images come from fixed tables, so a key (source address, rows, width) names an image; the ink
rectangle bounds every pixel the original shows in that colour.

**Validation gap.** One game (Cisco Heat), software only: 43 captured states and 111 car frames exact
inside the clip window; JNext viewed. Hardware ran v1.2 (owner: "works great"); no second game.

## Recognise
- An attribute loop right after the blits: `LD A,(HL) / OR ink / LD (HL),A` over a cell rectangle.
- Clash only in the figure's cells, in its colour; its shadow stays black.

## Probe and stop
`scan --range` over the attribute rows, `cost --at` the blit. Positive: one blit, fixed image tables,
one ink loop. Stop when the distinct images fit the cache.

## Contract
- State: the blit runs as the game's (pixels unchanged); the attribute hook keeps the cells' ink and
  records the rectangle; game RAM otherwise equal. Excluded: the cells' ink.
- Time: notes per blit are counted, not clocked, inside a paced update (BRIEFING A1, clock reads in
  JNext); conversions outside the cache are timed and credited. hook stack: about 32 bytes (h_pc,
  h_spr, car_note, car_t0, now; counted from the asm, not measured); interrupt headroom: the game's own
  handler plus car_flip, not measured separately (V1/V2 run every hook instruction on the game's stack).
- Display: 4-bit patterns of the game's bytes (bit set = colour 1, else transparent index 0); a mirrored
  image uses the sprite X-mirror, not a second pattern; the clip window (NR 0x1C/0x19) is the ink
  rectangle inside the play area, so the sprites show exactly the pixels the ink coloured. All 128
  sprites hidden at set-up; sprites off when the figure's mode ends.
- Display: software = return/boundary only; hardware = checklist item "the car red with no clash, also in curves, on hills, in a crash and after a stage load"

## Resources owned
Sprite ids and patterns (`param`): fixed slots preloaded for the common images (steering), replaceable
slots for the rest (optimise.pattern-cache). Hook state as listed.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| shadow shows in colour | sprites cover pixels the ink never reached | compare against the original's red pixels | clip to the ink rectangle | a second shadow pattern |
| figure flickers or jumps a frame | sprite attributes written mid-frame | flip-time capture | write them in the flip's interrupt | writing at present |
| pace slower in JNext only | clock reads per blit | pace per update, two seeds | counted credit, JNext-calibrated | more clock reads |

## Verification
The game's routine on a clear buffer: sprite pixels inside the clip window equal the pixels the original
makes coloured, ULA pixels equal, attributes unchanged except the ink. Keep mirrored images in the
cases: the first test ignored the mirror flag and the build's mirrored frames looked wrong to it (observed).

## Evidence
`grep -n "h_attr:\|car_note:\|car_present:\|car_flip:\|car_pre:" asm/cisco_heat_hooks.asm`;
`t_car`, `car_pixels` in nexclash/cisco_heat.py (observed).
