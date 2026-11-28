# Ink-rectangle figure as sprites clipped to the rectangle

```json
{
  "schema": 4,
  "id": "patch.ink-rectangle-sprites",
  "revision": 2,
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
  "owns": {"sprite_ids": "param", "pattern_slots": "param", "hook_state": ["c_on", "c_race", "c_aon", "c_cl", "c_bd"]},
  "examples": ["cisco_heat"],
  "sources": ["games/cisco_heat.md Design (the player's car, v1.2, 2026-11-22; its outline, v1.3, 2026-11-27)"]
}
```

## Use / do not use
Use when one figure is OR-blitted as 1-bit images, then coloured by an ink OR over a cell rectangle,
so other pixels in those cells take its colour. Do not use when game logic reads those attributes, or
when the figure's images exceed the pattern memory left after the cache's fixed slots.

**Assumptions.** One ink (its ULA palette entry is sprite colour 1); fixed image tables, so (source,
rows, width) names an image; the ink rectangle bounds every pixel shown in that colour.

**Validation gap.** One game (Cisco Heat): 111 car frames exact; hardware ran v1.2 but showed the car
see-through (KS3); the outline clear (v1.3) is software only; no second game.

## Recognise
- After the blits: `LD A,(HL) / OR ink / LD (HL),A` over a cell rectangle.
- Clash only in the figure's cells, in its colour.

## Probe and stop
`scan --range` the attribute rows, `cost --at` the blit. Positive: one blit, fixed tables, one ink
loop; stop when the images fit the cache.

## Contract
- State: the blit runs as the game's; the attribute hook keeps the cells' ink (excluded) and records
  the rectangle; game RAM otherwise equal.
- Time: notes per blit are counted, not clocked, inside a paced update (BRIEFING A1); conversions are
  timed and credited. hook stack: about 32 bytes (counted from the asm); interrupt headroom: the game's
  handler plus car_flip (V1/V2 run every hook instruction on the game's stack).
- Display: 4-bit patterns of the game's bytes (bit set = colour 1, else transparent); mirrored images
  by the X-mirror; the clip window (NR 0x1C/0x19) is the ink rectangle inside the play area. Sprites
  hidden at set-up, off when the figure's mode ends.
- Display: an unmasked (OR) figure shows what is behind it in its unset pixels (the original hides that
  in its ink). After the copy, inside its outline (each row first to last pixel) and the clip window,
  the shown screen keeps only its pixels; the back buffer is untouched. Check nothing is drawn after it.
- Display: software = return/boundary only; hardware = checklist item "the car red with no clash and solid, in curves, on hills, in a crash"

## Resources owned
Sprite ids and patterns (`param`): fixed slots for the common images, replaceable ones for the rest
(optimise.pattern-cache).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| shadow shows in colour | sprites cover pixels the ink never reached | compare against the original's red pixels | clip to the ink rectangle | a second shadow pattern |
| figure jumps a frame | attributes written mid-frame | flip-time capture | write them in the flip's interrupt | writing at present |
| pace slower in JNext only | clock reads per blit | pace per update, two seeds | counted credit | more clock reads |
| figure see-through | OR blit, no mask | random back buffer, screen after the copy | clear the outline's rows after the copy | a sprite fill colour (wrong across two papers) |

## Verification
The game's routine on a clear buffer: sprite pixels inside the clip window equal the pixels the original
makes coloured, ULA pixels equal, attributes unchanged except the ink. Keep mirrored images in the
cases (observed: the first test ignored the mirror flag). The outline, on a random buffer: the screen
after copy and clear against the body as the game blits it (a clear-buffer run); negative: no clear.

## Evidence
`grep -n "h_attr:\|car_note:\|car_clear:\|car_flip:" asm/cisco_heat_hooks.asm`; `t_car`, `t_clear`
in nexclash/cisco_heat.py (observed).
