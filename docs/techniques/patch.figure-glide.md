# Figure glide: move sprites between the game's coarse steps, every frame

```json
{
  "schema": 4,
  "id": "patch.figure-glide",
  "revision": 1,
  "kind": "patch",
  "title": "Figure glide: move sprites between the game's coarse steps, every frame",
  "question": "Figures move in whole cells once per game update (several frames); can their sprites move a fraction of the step every frame without changing the game?",
  "tags": ["sprites", "interpolation", "glide", "smoothness", "isr", "port-303B", "object-identity"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["design.figures_in_front"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "commit", "isr"],
  "order": {"commit": {"after": ["patch.display-atomic-switch"]},
            "cross": ["the ISR never selects port 303B while the main code uploads patterns: it counts the step and the main code makes it up",
                      "a publish clears the steps counted for the old moves"]},
  "owns": {"next_pages": "param", "hook_state": ["G_BUSY", "G_MISS", "HK_FR"]},
  "examples": ["r_type", "quazatron"],
  "sources": ["quazatron games/quazatron.md sessions 4-9 (glide in page 27, droid and shot interpolation)",
              "specnext reference/r_type/intake/glide.asm; l2sprites_body.asm (g_call, glide_publish, g_hold / g_release); PRs #98-#99"]
}
```

## Use / do not use
Use when figures are hardware sprites whose positions change in coarse steps (8 px per 3-9 frames) and the owner wants smooth movement; game logic, collisions and timing stay original. Tag each plot with its object (IY or table slot) + graphic + order among that object's plots; match it to the previous update (same object, graphic and order; else same object and order for a new animation frame). At publish show it 1/P of the way from its old place, P = the frames the last update took, counted on every interrupt; the ISR moves it on 1/P each frame (8.8 fixed point). Do not glide moves over a few cells (respawns, teleports), flashing figures (colour override: they pair with effects sharing the object; optimise.flash-palette-offset) or figures first seen this update. Smoothness needs an even update rhythm: hold updates at a fixed frame count (play pace; title 4 frames for 16 px moves).

**Assumptions.** Each plot can be tied to a game object (IY or a table slot) and the update length can be counted on every interrupt.

**Validation gap.** CSpect only (R-Type title and level 1, owner-confirmed); levels 2-8 and bosses not reviewed frame by frame; no board run.

## Recognise
Smooth scroll with figures stepping 8 px; owner reports judder or "moving in blocks".

## Probe and stop
Track a figure's x per frame (CSpect run_to IRQ + screenshot): steps then holds before; even steps after. Check P against the real update length.

## Contract
- State: display only; sprite positions between updates; the game's tables untouched.
- Time: per frame, a few hundred T per gliding sprite at the ISR's speed. **Port 303B selects both the sprite-attribute index and the pattern-upload index**: an ISR writing positions mid-upload corrupts patterns (garbled letters seen). Hook stack: 12 bytes for its own calls and pushes; interrupt headroom: 10 more bytes at every hook instruction while IFF is on.
- Display: software = return/boundary only; hardware = checklist item "figures glide; no doubled or garbled figures"

## Resources owned
Two figure tables and a move list (R-Type: bank 13 page 27, entry points at 0100 so a reset breakpoint at 0000 stays clean), busy/miss/frame counters in the hook page.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| garbled pattern | ISR selected 303B during an upload | upload with ISR stepping | busy only around uploads, count misses | busy for the whole plot (drops steps) |
| move, hold, jump (4, 0, 0, 8) | ISR skipped while main code was in glide | per-frame x | count misses, make them up after the call | - |
| letter swaps partner | matched by order only | per-object order | add the graphic to the key | - |
| power-up doubled | flash frames paired with an effect | no-glide build comparison | no glide for colour overrides | - |
| stop-go on the title | uneven update lengths | frames per update | fixed title pace | higher resolution (sprites are whole pixels) |

## Verification
Per-frame position traces; a no-glide build (L2_NOGLIDE) for comparison; owner sweep test. Negative control: L2_GLIDE_NOIRQ shows 8 px steps.

## Evidence
Observed in CSpect (R-Type title and level 1, owner confirmed). Quazatron's glide predates this; this card generalises it.
