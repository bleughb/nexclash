# Verification record

One section per game/build, newest first within a game. The checksum list below is generated
from the evidence records (docs/records/<game>.json); `python selftest.py` reproduces those MD5s
from the private reference files.

All tests: exact RZX playback in SkoolKit; at every patched routine the
original and patched code were run from the same real state and compared
(registers except R/T, all non-screen memory, patched-screen model, sprite
pixels). Start-up tails simulated: all registers restored, no game memory touched.

| Game | Recording | Plots | Erases | Other | Result |
|---|---|---|---|---|---|
| Treasure Island Dizzy | dizzy2 RZX + 29 underwater checkpoints | 6,338 | 6,326 | 25,299 ISR, 18 wipes, 7,436 bubble tests (340 Dizzy-dependent) | all identical |
| Dizzy 1 | dizzy1rzx, 6,345 frames | 2,364 | (XOR) | 40,881 collision tests, 24 wipes | all identical (A after erase is dead) |
| Fantasy World Dizzy | dizzy3rzx, 8,761 frames | 1,613 | 1,591 | 3,319 ISR, 44 wipes, 40 boxes; 30,976 pixel tests unaffected | all identical |
| Magicland Dizzy | dizzy4rzx, 10,074 frames | 1,690 | 1,670 | 3,486 ISR, 51 wipes, 44 boxes; 33,294 pixel tests unaffected | identical except 4 undo-buffer-only diffs (original's ghost pixels; nothing else reads it) |
| Spellbound Dizzy (Dizzy V) | Dean's dzzy5rzx (7,051 frames, dialogue boxes; autosave stripped; NOT in specnext/reference, so selftest cannot repeat it) | 1,400 | 1,399 | slot-1 page = ROM at all 240 font bytes read | all identical (8 erases: A/F dead) |
| Spellbound Dizzy (Dizzy V) | auto RZX, 4,018 frames (from the loader snapshot) | 470 | 470 | 0 logic reads of player pixels; 1,098 visual-only overwrites while drawn | all identical (7 erases: A/F differ at return, overwritten before use) |
| Chuckie Egg | Dean's RZX, 8,626 frames (levels 1-2; autosave stripped) | 7,854 player/duck + 878 hen | 881 hen | 15 screen clears, 549,345 sprite pixels | all identical |

| Spellbound Dizzy (Dizzy V), altrom | auto RZX, 6,227 frames, 16 segments (from the loader snapshot) | 1,479 | 1,463 | ROM view = ROM at all 136 ROM bytes read in 0x2000-0x3FFF; per-segment resync | all identical (6 erases: A/F differ at return, overwritten before use); `--strategy slot1` identical results |

Simulated boot (nextboot.py, every sprite build since 2026-09-28): stub + alt ROM fill + tail on a
model Next (launch state ROM 0 selected) -> all registers, RAM 0x4000-0xFFFF (except the tail),
slots 0/1 view (ROM3, + hook bytes and register block for altrom), paging lock, MMU, $8C = $80.
Negative controls caught: no 1FFD write (ROM1 copied), 7FFD locked without the $08 unlock, hook
bytes not copied. Structural altrom build of the TID-engine TidPatch (TID title snapshot, generic
profile): boot OK; printer/slot1/plain outputs of that build byte-identical to the pre-altrom toolkit.

## Output checksums (MD5) - the toolkit must reproduce these
Default builds (strategy `altrom` where proven; dedicated builders are printer-only); file names
are the records' canonical ones (`nexclash.py auto` names its outputs after the input file).
`--strategy` lines reproduce the pre-altrom builds from the same recordings.
<!-- generated from docs/records by `python -m nexclash.records views`: do not edit by hand -->
Every game's verified outputs (`selftest.py` rebuilds them; the record says how):

- Chuckie Egg (chuckie_egg): `chuckie_egg.nex` ec0df71e70fae35836eaed521f300777, `chuckie_egg_sprites.nex` bfad6be1e7c8a2c797a6242d7f339e35; verified 2026-10-13
- Rainbow Islands (128K) (rainbow): `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175, `rainbow_sprites.nex` e50733b2b7e2db32f004c1436a2e0461, `rainbow_sprites_diag.nex` 8f25bc6146b9d7f7ae1f12a1d227447e; verified 2026-10-13
- Everyone's a Wally (wally): `wally.nex` 2e615b3e7ae995e6d6a6ed9e3f586d4d, `wally_sprites.nex` f7605489c3af55b8e8c6a580c1c26150; verified 2026-10-13
- Spellbound Dizzy (Dizzy V) (dizzy5): `dizzy5.nex` c99189f3274a4803f0b25b0217206bdb, `dizzy5_sprites.nex` 1f33c467e6aa55585cea79cfbb24bcfe, `dizzy5_sprites.nex --strategy slot1` a59c1fd91ec5c32e549526dbc08d2e69 (re-checked 2026-09-28; 00a7c496... had an EMPTY font page: dialogue text blank on hardware); verified 2026-10-13
- Prince of the Yolkfolk (Dizzy 6) (dizzy6): `Dizzy6.nex` e02faca34df9504cc1f2f162e0ef791e, `Dizzy6_sprites.nex` f491e1f6621559ccc4d36de3535ff5d0; verified 2026-10-13
- Fantasy World Dizzy (fantasy_world_dizzy): `fantasy_world_dizzy.nex` cd620010e2f61af0002e76718945716f, `fantasy_world_dizzy_sprites.nex` 9182f2f8b4b0dc55b59a69728568b403, `fantasy_world_dizzy_sprites.nex --strategy printer` c09213beaec1572c0228985dae89bd77; verified 2026-10-13
- Magicland Dizzy (magicland_dizzy): `magicland_dizzy.nex` 09eb18496cff334ea17bfc0b0c94585d, `magicland_dizzy_sprites.nex` bf137d41d3cc08221bf6fdda153c9de2, `magicland_dizzy_sprites.nex --strategy slot1` d3b37c05d4c47ada07294fa2d7c1ae76; verified 2026-10-13
- Treasure Island Dizzy (treasure_island_dizzy): `treasure_island_dizzy.nex` 4dae1a3a15b2158642a5d5b82de92ef7, `treasure_island_dizzy_sprites.nex` 8b4d0847d68fce3215bd43a0e116e682; verified 2026-10-13
- Treasure Island Dizzy (title screen) (treasure_island_title): `treasure_island_title.nex` 70890aba7d821fba8a41e63636eb58be, `treasure_island_title_sprites.nex` 85e054fe4bce8e4b3a8e336aac432f58; verified 2026-10-13
- Dizzy: The Ultimate Cartoon Adventure (dizzy1): `dizzy1.nex` 7892b2e0f1f3f9f19165516db307cbe0, `dizzy1_sprites.nex` 05d2bce99f4d7654d4e1c9c9c04dc391; verified 2026-10-13
- Commando (commando): `commando.nex` a206f950c12f58a8e7f26b366f5a2480, `commando_sprites.nex` d601385ee4aeb7f3d7c0771bdc27df6b; verified 2026-10-13
- Crystal Kingdom Dizzy (128K) (crystal_kingdom_dizzy): `crystal_kingdom_dizzy.nex` 99975f65172dc86ecefbac07db2c0c00; verified never
- Midnight Resistance (128K) (midnight_resistance): `midnight_resistance.nex` 17239acaaf67b0f8011478053e17829d, `midnight_resistance_sprites.nex` a4fb69a2c8eaa820bf69da2edd589be1; verified 2026-10-13
- Smash TV (smash_tv): `smash_tv.nex` c72ea298486b14036ac1a87ac89c3f0e, `smash_tv_sprites.nex` 03979d5438cf55410ecec8aac76f05ec; verified 2026-10-13
<!-- end generated -->

## Evidence records + selective selftest - 2026-10-13
Toolkit change: docs/records (one per game), nexclash/records.py, `auto --decisions`, selftest
driven by the records. No game output changed.
- Baseline before the change (main 32ad905, old full selftest): Fantasy World, Magicland, Dizzy 1,
  Treasure Island (+ title), Dizzy V, Chuckie Egg all OK (run stopped after Chuckie Egg; the
  remaining games were re-verified on the branch below). Those results seeded the records'
  `verified` stamps (tree main 32ad905).
- Rebuild from snapshot + stored decisions, every game (`selftest.py --affected`, before stamps):
  all 27 outputs incl. the three `--strategy` builds byte-identical, 19.5 s total.
- Branch run `selftest.py --affected --verify --stamp --jobs 2` (about 1.5 h, Rainbow the longest): re-verified Chuckie Egg,
  Commando, Wally, Rainbow (both RZX), Fantasy World (+ printer), Dizzy V (+ slot1), Dizzy 6
  (try1.rzx; first time in selftest), Dizzy 1 and Treasure Island (analysis + boot: dedicated
  builders, not differential); rebuilt Magicland, Treasure Island title, Crystal Kingdom. All MD5s
  as listed above; every verification PASSED, boots OK; the build decisions each verification
  derives equal the stored ones; auto recordings deterministic (MD5s in the records).
- Plan checks: `python -m nexclash.records selfcheck` (in `--tools`) passes and catches three broken
  plan() variants; real tree: an engine file change -> that game only; z80tonex.py -> every game
  rebuilt, representatives re-verified.

## Rainbow Islands (128K, engine `rainbow`) - 2026-09-28
`nexclash.py auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx --no-record` (defaults: ink white, outline black)
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 (plain, tail 0x9F00) - boot sim OK
- `rainbow_sprites.nex` 0c191d94d5c3291e96f282cc6b1e4984 (altrom stubs + RAM pages 26/28/29) - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces, max 27/frame, 257 stars on the ULA - IDENTICAL
- rainbownew.rzx: 11799 frames, 29314 pieces, max 30/frame, 613 stars on the ULA - IDENTICAL
- `--outline transparent` on rainbow.rzx - IDENTICAL (outline pixels counted as expected drops)
- unit tests: edge columns, last slot, passthrough at 32 pieces, negative control, class colour - PASS
- Hardware: runs (Dean, 2026-09-28); detailed visual checklist results not reported

## Rainbow Islands - 2026-10-12 collectables without border + diagnostic build
RELEASE level. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (objects: opaque 15-255
border false; hook hex; symbols). Patch sites unchanged; ROM stubs e_hx (now maps page 26 and jumps
to dfend) and the limiter run path (jumps to dfst) changed.
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` e50733b2b7e2db32f004c1436a2e0461 - boot sim OK
- `rainbow_sprites_diag.nex` 8f25bc6146b9d7f7ae1f12a1d227447e - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces, 2215 commits; 26528 cell hooks, 606 tiles dropped,
  36119 object tiles (max 114 per render), 43621 band ends - IDENTICAL; same-map redraws of opaque
  objects 300 with the stored tile, 0 different.
- rainbownew.rzx: 11799 frames, 29314 pieces, 3530 commits, overflow entries 2; 49707 cell hooks,
  2660 tiles dropped, 139988 object tiles (max 110), 70579 band ends - IDENTICAL; same-map redraws
  677 / 0 different.
- Diagnostic build: first 1506 frames of each recording - IDENTICAL (border writes only).
- Timing (simulated, 28 MHz, no raster wait): whole game frame max 21.4 / 24.8 ms, frames over 20 ms
  9 / 16 (bffd9357: 9 / 17).
- New unit tests: diagnostic build - render with a cold cache and the beam at line 100 (red around
  every tile built, blue while waiting, black at the end), beam at line 200 (no wait: one black
  write), frame start / end with and without an interrupt during the frame (yellow only with), no
  stack use (SP unchanged when jumping back); normal build: no border write at all. Control: the
  OUT removed -> detected.
- ITERATE (rainbow.rzx 2912 frames) PASSED before the RELEASE.
- 2026-10-12 (merge into the repo): reassembled = profile hex (6 blocks, 63 symbols); the repo
  rebuilds all three .nex byte-identical, boot OK.

## Rainbow Islands - 2026-10-11 objects on the tilemap
RELEASE level. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex, code blocks
page2 0x1F10 / page3 0x0E60 / page4 0x0D60, symbols, new `objects` section); new
nexclash/rainbow_objects.py. Same patch sites as before (no new ones).
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` bffd9357d772e2df975ec5f40dc9e4cb - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces, 2215 commits; 26528 cell hooks (60853 25770 / 60839
  717 / 60965 41), 606 tiles dropped by a cell change, 36119 object tiles shown (max 114 per
  render), 43621 band ends (297462 screen bytes set to the map tile) - IDENTICAL. Object model =
  the game's back-buffer cell 36773 times, 0 differences. Opaque objects 717; redraw from the same
  map byte: 300 with the stored tile, 0 different (cell reused for another map cell: 159 / 88).
- rainbownew.rzx: 11799 frames, 29314 pieces, 3530 commits, overflow entries 2; 49707 cell hooks
  (45886 / 3152 / 669), 2660 tiles dropped, 139988 object tiles (max 110), 70579 band ends - IDENTICAL.
  Object model = back buffer 149087 times. Opaque objects 3152; same-map redraws 677 / 0 different.
- Timing (simulated T, 28 MHz, no wait states): render-start tilemap build max 12.0 / 12.8 ms;
  object hooks per game frame avg 2.8 / 5.4 ms; commit avg 1.6 / 2.0 ms; whole game frame max 21.5
  / 24.8 ms; frames over 20 ms 9 / 17 (0 without the object hooks; ab97c76a: 9 / 15). The raster
  wait is not in these numbers.
- Checked per event: cell hooks = original (all registers incl. F, memory) + object map (TILES,
  OBJO, OBJM1/2, FLAGS, CTILE, RCNT, OCCM) = model + a dropped tile cleared exactly in the shadow map
  and the map on screen; at every redraw of an opaque object's cell from the same map byte the
  game's tile = the stored tile; render start: the modelled objects reproduce the game's back-buffer
  cell (map tile or opaque object, then each masked object), the shadow map = the model (tile +
  palette offset per visible object cell, 0 elsewhere), each tile's 32 bytes = the composed
  objects and its key, tiles on screen untouched, no stale CTILE, remembered inks = model; band
  ends: screen writes = the model's map-tile rows + colours for that char row; render end: map rows
  = the shadow map, $6E/$6F/$6B/clip, or the layer off; sprites-off hooks: $15 = 0, $6B = 0, $7F = 1.
- Unit tests (both RZX states): 270 cell-hook cases (random object maps, map bytes, scroll of each
  map, dropped tiles, full lists, 'leave as drawn' and fixed-ink classes); 2 render paths on a
  synthetic map of every cell kind (fruit alone, on a mirrored tile, rainbow opaque, two / four
  masked, fruit + rainbow with and without a remembered ink, FF, unknown background, ULA class,
  fixed ink + no border, partial bottom row, off-screen row with a stale tile, shared key, star
  attribute) twice (second render from the cache); cache full (every tile on screen); cache flush;
  raster wait (lines 100/175/15/176/200/300); profile tables. 17 negative controls detected: carry
  not restored, opaque object not recorded, occupancy mask not kept, no black border, background
  tile not drawn, map not cleared, fruit behind rainbows, off-screen tile left assigned, one-ink
  tile with the ink in its pixels, on-screen tile reused, flush ignored, no raster wait, + the
  figure / store / limiter controls.
- ITERATE (rainbow.rzx 2912 frames incl. the bonus scene) PASSED before the RELEASE.
- 2026-10-12, from the public repo (selftest.py, Dean's rainbow.z80 4c98b980 / rainbow.rzx 55046d18
  / rainbownew.rzx 47bb2b16): rainbow.nex 7ac543fb and rainbow_sprites.nex bffd9357 reproduced, both
  RZX IDENTICAL with the same counts as above, unit tests PASS (17/17 controls), boot OK.

## Rainbow Islands - 2026-10-11 opaque-item base tile + raster-synced commit
RELEASE level. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex, new `page3`
block 0x0E60, symbols). No new patch sites.
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` ab97c76ae0edd3937e3149b0dac5e52f - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces, 2215 commits; 26528 cell hooks (60853 25770 / 60839
  717 / 60965 41), 43621 band ends, 13558 item sprites (max 67 per render, 104 sprites in all) -
  IDENTICAL. Item rows 105453 as modelled, 3011 under a figure, 0 other. Opaque items 289; the
  game's redraw of such a cell at the same scroll: 179 with the stored tile, 0 different (other
  scroll = cell reused: 61 / 27).
- rainbownew.rzx: 11799 frames, 29314 pieces, 3530 commits, overflow entries 2; 49707 cell hooks
  (45886 / 3152 / 669), 70579 band ends, 67570 item sprites (max 72, 116 in all) - IDENTICAL.
  Item rows 528330 / 12178 / 0. Opaque items 1412; same-scroll redraws 376 stored / 0 different
  (other scroll 657 / 93).
- Item sprite and item-row counts equal eb9836fe's (the first ITERATE showed 119 fewer sprites:
  a masked draw of the same code over an opaque item went to FF; fixed before the RELEASE).
- Timing (simulated T, 28 MHz, no wait states): commit avg 1.0 / 2.0 ms, max 5.4 / 6.2 ms; item
  hooks per game frame avg 1.2 / 2.8 ms; game frames over 20 ms 9 / 15 (0 without item hooks).
  The raster wait itself is not in these numbers (the verifier's video line is fixed at 200).
- New checks in the verifier: TILES (page 27) = model at every cell hook; at every 60853 redraw of
  an opaque item's cell at the same scroll the game's tile = the stored tile (fail otherwise);
  band-end screen writes for opaque items = the tile rows of the model.
- New unit tests: cell hooks with random BC' (map byte) and random TILES; same code over an opaque
  item; render paths with 3 opaque items (tile < 128, tile >= 128 mirrored, one crossing the
  bottom of the play area); raster wait: video line at render end 100 / 175 / 176 / 15 / 200 / 300
  -> first sprite write at line 178 / 178 / 178 / 17 / 202 / 302 (waits for 176 only inside the
  play area, never longer). New controls detected: opaque tile rows not drawn; raster wait
  removed. 10/10 item controls detected.
- ITERATE (rainbow.rzx, 2912 frames incl. the bonus scene) PASSED before the RELEASE.

## Rainbow Islands - 2026-10-11 collectables as sprites
RELEASE level. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex + new `page2`
block + symbols; 4 new sites: 60853 / 60839 / 60965 cell drawers, 59547 band end).
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` eb9836fe60a70df02087920603c673b4 - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces, 2215 commits; 26528 cell hooks, 2216 render starts,
  43621 band ends, 13558 item sprites (max 67 per render, max 104 sprites in all) - IDENTICAL.
  Item rows: 105453 shown as modelled on the original screen, 3011 under a figure the original
  plotted at render time, 0 other.
- rainbownew.rzx: 11799 frames, 29314 pieces, 3530 commits, overflow entries 2; 49707 cell hooks,
  70579 band ends, 67570 item sprites (max 72 per render, max 116 sprites in all) - IDENTICAL.
  Item rows: 528330 as modelled, 12178 under a figure, 0 other.
- Checked per event: cell hooks = original (all registers incl. F, memory) + page-27 shadow map
  = model; render start = original, item records + cached patterns + count + figure limit =
  model; band ends = original + screen writes = the model's for that char row; render end: no
  screen writes, every item row/attribute was on a band, item sprites = model (attributes,
  committed pattern = item graphics), figures at NI.. = staged; entry-point proofs for the four
  new sites.
- Timing (simulated T at 28 MHz, no wait states; the verifier now measures it): render-end commit
  avg 1.0 / 2.0 ms, max 5.4 / 6.3 ms; item hooks per game frame avg 1.2 / 2.7 ms, max 13.3 / 14.8
  ms (full item rebuild in the bonus scene); whole game frame max 23.4 / 25.2 ms; game frames over
  20 ms: 8 / 13 (0 without the item hooks) - each costs one extra interrupt.
- Unit tests PASS (states from rainbownew.rzx): all earlier tests + 216 item cell-hook cases, 4
  item render paths (render start, 22 band ends, render end) on synthetic shadow maps (scroll 3
  with wrapped top rows and a partial bottom at 155 rows, X8 columns, unknown colour, a
  several-object cell, a star-changed attribute, 90 cells -> the 80-item cap), list reuse + ink
  refresh (the cap case was raised from 70 to 90 cells after the RELEASE run and the item unit
  tests re-run: PASS; .nex unchanged); 8 item
  negative controls detected (overlay does not clear the cell, carry not restored, mask not
  applied, ink drawn as outline, pattern never built, band fixes rows of other bands, inks never
  refreshed, figures committed over the item sprite numbers). The figure "negative control" and
  "store stale-pattern control" read the committed attributes and had been n/a on every state
  since bddea69e; now read from the staged state: detected 39/40 each.
- Prototype's 58 mismatches (rainbow.rzx 2500 frames, replicated: 485 ok / 58): 36 figures plotted
  over the item, 16 items overwritten by the untracked full-tile drawer 60839, 6 rows below the
  160-row play area.
- Before any change the toolkit (hand-transcribed into the sandbox) reproduced plain 7ac543fb and
  sprites bddea69e byte for byte.

## Rainbow Islands - 2026-10-02 render-end commit + sprites off on non-play screens
RELEASE level. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex, sites 65029 /
65076).
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` bddea69edaf6cf0a83dba8633c8f6618 - boot sim OK
- rainbow.rzx: 11865 pieces, 2215 commits checked (patterns + attributes = staged), sprites-off
  path 3 times - IDENTICAL
- rainbownew.rzx: 29314 pieces, max 84 sprites/render, store hits 96%, 3530 commits, sprites-off
  5, overflow entries 2 - IDENTICAL (an earlier run of the build without overflow entries FAILED
  on exactly those 2 pieces: ULA fallback; fixed)
- unit tests PASS; new control: commit writing attribute 4 to the wrong register -> detected
  (2026-10-11: the figure "negative control" and "store stale-pattern control" were n/a on every
  state of this build - see the 2026-10-11 entry)

## Rainbow Islands - 2026-10-01 frame limiter + turbo
RELEASE level. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex, 2 new sites).
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` cbb5a1d4ba4e84cec40191d3a3259f5a - boot sim OK
- rainbow.rzx: 11865 pieces, 2216 game frames (limiter + handler exit each) - IDENTICAL
- rainbownew.rzx: 29314 pieces, 3530 game frames, max 84 sprites/render, store hits 94% - IDENTICAL
  (re-run alone after the sandbox killed the first run)
- unit tests PASS: limiter skip path = original POP AF/EI/RET (tick counted, 3.5 MHz), run path =
  original at 65175 (F dead: CP 3 next) with 28 MHz, control (skip jump removed) detected; plus
  all earlier tests

## Rainbow Islands - 2026-10-01 speed build (direct conversion + 256K store + sprites per piece)
RELEASE level. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex + `plotters`
layout table, replaces `stream_len`).
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` 7559f940bb72211456b3ec53a0bdff60 - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces, max 62 sprites/render, store hits 93% - IDENTICAL
- rainbownew.rzx: 11799 frames, 29314 pieces, max 84 sprites/render, store hits 94% - IDENTICAL
- unit tests PASS: direct conversion = original plotter on random streams (66 plotter/carry
  cases), corrupted layout detected; page 245 = bit reversal; store hit / changed-stream miss /
  garbage store never hits; controls detected: stream compare removed, stale stored patterns;
  LEFT4, edge columns, last sprites, passthrough, ink/outline swap control, SWAPNIB, setup
- 28 MHz hook T per piece: store hit ~9.2k, miss ~36k; average ~11.6k (4dce14af: 28.1k)

## Rainbow Islands - 2026-09-30 pattern cache
Same command (RELEASE level). Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook
hex + stream_len table); new nexclash/rainbow_catalogue.py.
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` 78b9ed99ab714ef77024f84558987441 - boot sim OK
- rainbow.rzx: 11865 pieces, max 27/render, cache hits 67% - IDENTICAL
- rainbownew.rzx: 11799 frames, 29314 pieces, max 30/render, cache hits 48% - IDENTICAL
- unit tests PASS incl. cache: repeat piece hits (no upload, registers, pixels), changed stream
  misses; controls detected: stream compare removed (39/39, 1 n/a: flipped byte draws the same),
  stale cached patterns (39/39, 1 n/a: no pixels)
- per piece (28 MHz hook T): hit 6.3k, miss 35.6k (previous build 28.1k every piece)

## Rainbow Islands - 2026-09-29 boss-spider fix + pattern-upload optimisation
Same command. Changed: rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex regenerated).
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` 4dce14afce8977fe39086923328a5e12 (fix + optimisation) - boot sim OK
  (boot check now also runs setup: pattern RAM zeroed)
- rainbow.rzx: 7178 frames, 11865 pieces, max 27/frame - IDENTICAL
- rainbownew.rzx: 11799 frames, 29314 pieces, max 30/frame, 613 stars - IDENTICAL
- unit tests PASS: previous set + window vs 35 plotter extents (control: old window misses exactly
  the 4 LEFT4 entries - detected), 96 synthetic LEFT4 pieces (control detected 76/76 with pixels),
  SWAPNIB exhaustive self-test + SWAPNIB-as-NOP control detected, setup zeroing + control detected
- fix-only build 4132ae00ce87b2e046859cd89344ecd3: boot OK, rainbow.rzx IDENTICAL, unit tests PASS
  (rainbownew run stopped; the final build contains the same fix and passed it)
- worst hook T per render (32 pieces): 1,122,492 previous / 1,132,924 fixed / 909,084 final
- not reached by any RZX: the boss (LEFT4 plotters proven by unit tests only); hardware pending

## Everyone's a Wally (128K snapshot, engine `wally`) - 2026-09-28
`nexclash.py auto wally.z80 --rzx wallyrzx.rzx` (wally.z80 = World of Spectrum snapshot)
- `wally.nex` 2e615b3e7ae995e6d6a6ed9e3f586d4d (plain, tail 0x6B00) - boot sim OK
- `wally_sprites.nex` f7605489c3af55b8e8c6a580c1c26150 (altrom stubs + RAM page 26) - boot sim OK
- wallyrzx.rzx (11 autosave snapshots stripped): 15225 frames, A 4299 / B 1058 plots converted
  (0 passthrough), 3938 commits, max 12 sprites, 1,913,362 sprite pixels - IDENTICAL
- unit tests: 2664 plot cases (1626 converted, 1038 guard/full-table passthrough), 3 commit cases,
  negative control (ink/outline swapped NIBTAB) detected 12/12 - PASS
- Hardware: boots and runs (Dean, 2026-09-29); detailed visual checklist results not reported
- 2026-10-11 selftest (Dean's wally.z80 a9eeb555 + wallyrzx.rzx 72c7d1f6): both MD5s reproduced, RZX
  IDENTICAL, unit PASS; the report said FAILED only because Rainbow's pattern-RAM zero check had been
  applied to Wally's boot check (Wally uploads full patterns) - check scoped to Rainbow.

## Chuckie Egg (48K, engine `chuckie`) - 2026-10-11
`nexclash.py auto Chuckie_Egg.z80 --rzx Chuckie_Egg.rzx --no-record`
(Chuckie_Egg_1983_A__F_Software_a.z80, title screen; Dean's RZX: 9 autosave snapshots stripped,
8626 frames, levels 1-2, game over, high-score entry; lifts and the free duck not reached)
- `Chuckie_Egg.nex` ec0df71e70fae35836eaed521f300777 (plain, tail 0x5B00) - boot sim OK
- `Chuckie_Egg_sprites.nex` bfad6be1e7c8a2c797a6242d7f339e35 (altrom, stateless hooks) - boot sim OK;
  setup simulated: 6144 pattern bytes uploaded = the 48 built patterns, palette 1 = 0xB4 / 17 = 0x16,
  $4B = 0, 128 sprites hidden, $15 = 1
- RZX: 7854 player/duck plots, 878 hen draws, 881 hen erases, 15 screen clears, 549,345 sprite
  pixels - IDENTICAL. Per event: all registers (AF' included), all memory except the screen, the
  player buffer 29344-29391 (write-first, read only by the plotter) and dead stack below the final
  SP; sprite pixels = the original's own pixels from a canvas run (screen zeroed for hens, tile
  graphics zeroed for player/duck); player/duck screen block = background | figure; no attribute
  writes; hen erase and clears write exactly the original's screen bytes and leave the right sprites
  hidden; entry-point proof for every patched instruction; no game write to a patch site.
- Unit tests PASS: player/duck 1560 cases (frames 0-31 x 10 positions x player/duck), hens 1764
  (A' 0-15 x x 0/8/100/240/249/255 x 3 heights x 2 table entries), 1008 hen guard cases (no table
  entry -> no sprite), hen erase 12, clears 3, negative control (patterns shifted one pixel)
  detected 5/5 (1 n/a: blank duck frame 12). Edge cases classified, not game cases (the RZX never
  reaches them; any occurrence with pixels would fail its pixel check): player/duck at x > 240
  (360) and hens at x = 248 (252) - the ULA wraps the last byte into the next column, the sprite
  clips.
- Shared code: nexclash.py gained one dispatch block (before the 48K identify). Wally / Rainbow /
  Dizzy MD5s not re-run in that session (their reference files were not there): `selftest.py`
  covers them once reference/ holds them (STATUS open work 1).
- Hardware: untested.

## Commando (128K, engine `commando`) - 2026-10-12
`nexclash.py auto commando.z80 --rzx commando.rzx --no-record`
(Commando_1985_Elite_Systems_t_128K.z80 = BASIC loader at line 30, trainer version; Dean's RZX
starts in game from its own SZX: 8 autosave snapshots stripped, 3,279 frames, area 1, deaths)
- Start-up: the loader is run in SkoolKit (real 128K ROMs, SPACE, N) to the game entry 25089; the
  .nex starts in a front end that redoes PAUSE 0 + "INFY LIVES(Y/N)?" + the POKE. front_tests: N
  and Y reach 25089 with all registers (R aside) and RAM = the loader's entry state (Y: + 27653 =
  182) except 0x5D00-0x5E1F; negative controls (register, POKE) caught. First builds 5642e4b4 /
  f22a9452 started in 128K BASIC: hardware corruption / crash on the first key (ROM 0).
- `commando.nex` a206f950c12f58a8e7f26b366f5a2480 (plain, tail 0x6D00) - boot sim OK
- `commando_sprites.nex` 5c1081b73765978a7f3e055a66578542 (altrom hooks + bank-5 state set up by
  e_init at the game entry) - boot sim OK; patched snapshot = original except the 7 sites (25
  bytes); alt ROM = 48K ROM except its $FF area 0x386E-0x3C98
- Boot path (not in the RZX): the .z80 simulated with SPACE, N: USR 25088 at frame 41, IM 2 at 52,
  menu at 53; after the USR nothing touches 0x5B00-0x5E1F or the tail, and 7FFD is only ever
  0x10 / 0x11 (ROM 1) - the loader before it writes 0x00 (ROM 0) 1,378 times (300 frames)
- RZX: 4,332 converted plots, 507 figure plots on the ULA (edge / top clip; 0 for a full table),
  887 other plots, 11 clears, max 6 figures, 570,425 sprite pixels - IDENTICAL. Per call: all
  registers (AF' included), all memory except the screen and the hook RAM; patched screen = the
  original minus the new frame's bits, which the sprite shows exactly (clip window 0-191); no game
  access to the hook RAM, tail, patch sites or alt-ROM hook range; 7FFD always selects ROM 1;
  25630 never re-entered; patched instruction interiors never executed.
- e_init: 16 cases (random registers/flags, the loader's own RAM in the hook area, all sprites
  visible) - registers as the original JP 27090, no memory outside the hook RAM written, hook RAM =
  the model's start state, sprites 0-47 hidden; negative control (swapped nibble table) 16/16.
- Unit tests PASS: 16,128 position cases (8 columns incl. edges 28-31/255 x column step -1/0/+1/+2 x 7 rows incl. 4/5/95/96 x 2 heights x row step -1/+1/= row pairs; 3,744 converted, 12,384 passthrough, 8,064 step-guard cases), 12 table-full, 12 other-descriptor (explosion slot), 12 page-guard (page 32), negative control (swapped nibble table, its own tables) 6/6 - every case: converted iff the guard says so, registers + memory as the original, sprite pixels = the original's new-frame bits
- First build (earlier session) failed three ways, all fixed here: it wrote the hook state over
  the BASIC loader's RAM (would not have reached the game), kept invisible entries for soldiers
  leaving at the bottom (table full in 239 plots), and converted column/row steps the game never
  makes (the plotter draws past its frame there; guarded now).
- Depth + scenery restore (5c1081b7): RZX IDENTICAL as above with 4,287 of the 4,332 converted
  plots putting back the scenery their erase cut (ULA unchanged by the plot - checked per call),
  66,170 scenery pixels drawn in front of figures by the rule, 543,349 sprite pixels; depth table
  re-derived from the game = the profile (18 types with walk boxes); depth unit 315 cases (150
  behind), negative control (no walk boxes) 150/150; restore negative control (svrest = RET) 6/6.
  Boot path: nothing touches 0x5C00-0x5F5F after the game entry (300 frames); RZX: the game only
  touches 0x5B11-0x5BFF and its stack (>= 0x61C4) in 0x5B00-0x61FF. 5ab928e9 (start-up fix only)
  runs on hardware (Dean).
- Shared code: nexclash.py gained one dispatch block (before the 48K identify); selftest.py gained
  a `commando` RZX_GAMES entry (slow). `selftest.py --smoke` (Chuckie Egg) PASSED; other games
  not re-run (game session).
- Solid build (541e34e2, after Dean's hardware report on 5c1081b7: flicker, menu ELITE logo and
  stray dots in play, soldier visible through a rock). Root causes: sprites hidden at plot entry
  (flicker); svsave/svrest/occl borrowed IY, which the game's IM 2 handler reads (IY+7 flags ->
  menu logo routine 26826). Same RZX: IDENTICAL (4,332 converted, 507 on the ULA, 887 other, 11
  clears, max 6 figures), 676,249 sprite pixels compared exactly with the model (ink 1 / yellow
  fill 2 / hidden by solid scenery), 31,132 figure pixels hidden behind solid shapes, 136,956
  fill pixels; scenery restore 4,287 plots.
  New checks: Static (1,425 hook instructions disassembled, no IX/IY write); Interrupt (47.1M hook
  instructions: IX, IY, I, IFF unchanged, SP on the hook or game stack, only NextRegs 7/0x34-0x39
  and ports 0x5B/0x303B; negative control LD IY in e_ent detected); Depth (table + 144 solid shape
  variants, 4,196 bytes, re-derived from the game = the profile); Cache (2,764 of 4,332 converted
  plots reused a pattern slot; negative control - lookup ignores the frame offset - caught within
  400 frames); unit tests 16,128 position + 12 table-full + 12 slot-full (11 entries show slots,
  every slot keyed: the plot takes the free one) + 12 other-descriptor + 12 page-guard, negative
  control 6/6 (cold slot cache: a broken patch builds with its own tables); depth unit 315 (138
  behind), negative 138/138; restore negative 6/6; e_init 16 cases, negative control (slot keys not
  emptied) 16/16. Hook RAM now 0x5C00-0x60FF: no game access in the RZX (checked per access).
- d601385e (2026-10-12): 541e34e2 crashed on hardware and in CSpect at the first figure with hook
  code at 0x3D00-0x3DFF (probable cause the DivMMC automap on fetch; BRIEFING A1, not confirmed). Hooks moved to 0x3600-0x3CDB + 0x3F00-0x3F96, the
  pair tables to 0x3D00/0x3E00. Static check and per-instruction check now fail on code fetched
  in 0x3D00-0x3DFF. Same results as above (RZX IDENTICAL, 676,249 sprite pixels, cache 2,764,
  every test and negative control PASS). Runs on hardware (Dean).
- Shared code unchanged (commando.py, its .asm and profile only); `selftest.py --smoke` PASSED.
- Hardware: d601385e runs (Dean, 2026-10-12); checklist items not yet reported.

## Midnight Resistance (128K, engine `midres`) - 2026-10-13
`nexclash.py auto midnight_resistance.z80 --rzx midnight_resistance.rzx --no-record` (~20 min)
(Midnight_Resistance_1990_Ocean_128K.z80 67bf05d3 at the title; Dean's RZX b75ecd5f from its own
SZX: 8 autosave snapshots stripped, 4,709 frames: title, level 1 to the end-of-level tank, game over)
- `midnight_resistance.nex` 17239acaaf67b0f8011478053e17829d (plain, tail 0x7B7E-0x7BCD below SP:
  write-first in the RZX, untouched in a 600-frame free run of the .z80) - boot sim OK
- `midnight_resistance_sprites.nex` e8f0ece9e41c314d76471c96f4595854 (alt ROM hooks 0x2000-0x2EA1
  + page 26 at slot 5 during hooks) - boot sim OK; 12 patch sites (5 CALL operands, 5 loop exits,
  commit 0x8950, loop exit test 0x8993), original bytes checked
- RZX: 4,463 converted plots (97E1 1,138 / 9813 143 / 7DC5 870 / 9E3F 1,799 + mirrored 513), 3,065
  passed through (bullets, explosions, small objects, 4 player plots before the first commit), 758
  commits (max 36 sprites), 1,656,090 sprite pixels, 1 game-over exit (sprites hidden) - IDENTICAL.
  Per plot: all registers (AF' included), all memory except the buffer bytes the original drew
  (dead stack included); per commit: registers + memory, sprite layer = the original plots' pixels
  (each plot re-run on a 0x00 and a 0xFF buffer) in plot order, expected colours, clip window;
  MMU5 = 5 and 3.5 MHz after every hook; interiors of the patched blocks never executed
  (fall-throughs DJNZ -> RET / EXX checked, interrupts between them allowed).
- Unit: 2,103 guard cases (positions incl. edges, widths, line pairs 1-33, OR opcode NOP / XOR,
  figure / sprite budget at and past the limits, game-loop flag, foreign caller, graphics in slot 5
  / wrapping) - converted iff the Python model says so, registers + memory as the original, FIG
  entry and sprite count as the model; 15 single-figure commits; negative control (ink and
  outline swapped, its own tables) 12/12 informative cases.
- Interrupt safety: after every hook instruction (22.9M): IX, IY, I, IFF unchanged, SP on the
  hook stack with 24 bytes of room or at/above the game's SP - 4, no fetch at 0x3D00-0x3DFF;
  negative control (LD IY at every CALL hook) 15/15. Static: no DD/FD/DI/EI/LD I/IM in the hook
  code. ISR slot scan (full RZX): the handler reads slot 0 (0x0000), reads/writes/runs slots 3
  and 7 only.
- Shared code: nexclash.py gained one dispatch block (before the 48K identify).
  `selftest.py --smoke` and `--tools` PASSED; `--affected` rebuild: see the PR.

### Midnight Resistance round 2-4 - every figure a sprite, shop, colour map (2026-10-13)
- `midnight_resistance_sprites.nex` a4fb69a2c8eaa820bf69da2edd589be1 (hook code 3,168 bytes; sites:
  6 CALL operands, 6 loop exits, commit 0x8950, loop exits 0x8993 / 0x8988, shop 0xB893 / 0xB89B /
  0xB8A5) - boot sim OK, static PASS.
- RZX 1 (4,709 frames): 7,499 converted plots, 29 passed through (before the first commit / after
  game over), 758 commits (max 58 sprites), 1,847,906 sprite pixels - IDENTICAL.
- RZX 2 (Dean, 11,804 frames, the shop): 18,028 converted, 146 passed through (outside the loops),
  2,264 commits incl. 477 in the shop (max 57 sprites), 4,040,431 sprite pixels, 1 level exit, 1
  shop exit (sprites hidden) - IDENTICAL; also IDENTICAL with a colour map read back from a
  randomly repainted sheet (60 % of the opaque pixels).
- MMU2 = 10, MMU4 = 4, MMU5 = 5, 3.5 MHz after every hook; the shop-exit hooks leave the game's dead
  stack as the original (a first version CALLed on it and was caught).
- Unit: 8,856 guard cases, 60 single-figure commits, negative control 48/48; derived states for
  0x7E06 and vertically flipped draws (not in either RZX); full sprite table (64 sprites; fails on
  the old 8-bit N * 5 - negative control 3/3); level exit 0x8988; colour map (synthetic, wrong
  check byte ignored, negative control 48/48).
- Interrupt safety: 110M hook instructions checked, negative control 60/60.

## Smash TV (48K, engine `smashtv`) - 2026-10-13
`nexclash.py auto smash_tv.z80 --rzx smash_tv.rzx --no-record` (~5 min)
(Smash_TV.z80 3b89344c = the BASIC loader at the trainer prompt; Dean's RZX ed4ee1a0 from its own
SZX ~12 s later at the same prompt: 8 autosave snapshots stripped, 4,085 frames played: title,
arenas 1-2, game over, title; N pressed)
- `smash_tv.nex` c72ea298486b14036ac1a87ac89c3f0e (plain: the loader as it is; tail 0x5B00:
  zero in the snapshot, write-first by the entry code 59823 in the RZX and in a 1,500-frame free
  run) - boot sim OK
- `smash_tv_sprites.nex` 03979d5438cf55410ecec8aac76f05ec (alt ROM hooks 0x2100-0x27E6 + page 26
  at slot 7 during hooks; built from the start snapshot = the loader run with N to USR 59776 +
  front end 0x5D00 + prompt row) - boot sim OK; 7 patch sites, original bytes checked.
- Front end: N / Y / SYM+Y (ignored, then N) reach 59776 with every register (R, IFF aside: 59776
  is DI) and all RAM equal to the loader's own entry state except 0x5D00-0x5D6C (Y: 33465 = 201).
- RZX: 7,010 converted plots (24x24 3,680 / mirrored 3,091, 8x8 227 / mirrored 12), 3 invisible
  (converted, no sprites), 0 on the ULA; 669 restores (real + scratch); 683 commits (max 25
  figures / 100 sprites); 8 hide-all (53868); 1,183,835 sprite pixels - IDENTICAL. Per plot: all
  registers (AF' included), all memory except the back buffer, the hook's decision = an
  independent Python model (column, visibility, sprite table, cache lookup), sprite pixels = the
  model of the graphic (ink bits, mirror, cell inks, clip) AND the model = the ink the original
  plot drew (its attr-painter bytes aside); per restore: registers + all memory identical incl. the
  real buffer, scratch = the restored buffer; per blit loop end: registers + memory; per commit:
  the shown sprite layer = the figures plotted since the last commit, in plot order; per 53868:
  every sprite hidden; slot 7 = page 1 and 3.5 MHz after every hook; game code never writes the
  hook state; interiors never executed, 53869 only after 53868; the game never changes a patch
  site or the restore routine (the delay 51175 copies RAM onto itself).
- Unit (12 captured plot states, 4 plotters): 840 position cases (columns 0-2 / 28-31, lines at
  every edge; conv 420 / invisible 180 / ULA 240 incl. the double real + scratch run), 48
  sprite-table cases at and past 128, 12 cache-full cases (ULA path); decision = model, registers
  + memory as the original; negative controls (colour table shifted; guard column 31) 24/24.
- Static: 886 hook instructions: no DI/EI/IM/LD I/RETI/RETN, no IX/IY, nothing at 0x3D00-0x3DFF;
  alt image = ROM at 0x0000-0x20FF and 0x3800-0x3FFF (0x386E check byte, font).
- Speed (simulated, 28 MHz parts / 8): +14,475 T per game frame (~5.8% of ~250K T).
- Shared code: nexclash.py gained one dispatch block; selftest.py prints its usage on an unknown
  flag (it started a release run). `selftest.py --canary`: see the PR.

## Toolkit: two-stage tool-chain canary (2026-10-13)
`selftest.py --canary`: stage 1 Chuckie Egg rebuild (both MD5s) PASSED in 0.6 s. Negative control
(stage-1 MD5s forced wrong): stage 1 FAILED -> stage 2 ran (Midnight Resistance: profile = pinned
assembler output, both rebuild MD5s, 300-frame differential verify PASSED, 56 s) -> verdict "tool
chain works; the stage-1 fault is specific to chuckie_egg", exit 1. Full selftest runs with a
failed game call the same stage 2 (diagnose()).

## Toolkit: pinned sjasmplus + asm2profile (2026-10-12)
`python tools/asm2profile.py --check --all` with the pinned sjasmplus 1.24.0 (tag v1.24.0, commit
d379eeac): chuckie_egg, commando, everyones_a_wally, rainbow_islands IDENTICAL (every hook block
byte-for-byte, every exported symbol) - with the bundled static binary and with a fresh source
build of the tag. Negative checks: one extra NOP in wally_hooks.asm -> DIFFERS (blocks + 6
symbols named); an unknown --add-sym -> DIFFERS. Profiles gained only "assembled_with" (Commando
also "source"); no .nex changes (`selftest.py --smoke` PASSED). The full selftest now runs the
check first.

## Toolkit: analysis commands inspect / scan / isr / cost (2026-10-12)
`python selftest.py --tools` (~30 s) PASSED: inspect commando = 128K BASIC loader, USR 25088 /
25630, ROM 0 warning; chuckie = 48K, IM 2, no warning. scan commando start-up (free run SPACE, N,
from USR 25088, 400 frames) and RZX (300 frames): 0x5C00-0x60FF untouched. isr commando: reads the
interrupted IY (BIT 1 / SET 0 / RES 2 (IY+7)), not IX, stack switch at 25177; chuckie: handler
40092, no index-register reads. cost commando 39120 (1500 frames): 2577 calls, median 4477 T (=
the earlier one-off measurement), 10.4 % of frame time. Negative control: a data-flow model that
treats every IY use as a write fails the isr check. Inspect also checked by eye on Wally, Rainbow,
Spellbound (loader flagged), Crystal Kingdom. `selftest.py --smoke` PASSED; no .nex changes.
- 2026-10-12: asm/dizzy5_hooks.asm (no profile hooks section) assembled by the pinned sjasmplus =
  dizzy5.hook_code() for the Dizzy V profile, 227 bytes identical; now part of `selftest.py --tools`
  (negative check: one changed instruction -> FAIL).
