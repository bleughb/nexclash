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
- Rainbow Islands (128K) (rainbow): `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175, `rainbow_sprites.nex` cf017271dfc01bdd0c7cf2f599b03628, `rainbow_sprites_diag.nex` c16751b0255ee3d83a4e342bf9a8c411; verified 2026-10-13
- Rainbow Islands (128K, Z80N) (rainbow_z80n): `rainbow_z80n.nex` 7ac543fb51c7a3c4137778eeb3cdc175, `rainbow_z80n_sprites.nex` bda21ab675fa271b6f51f332aae14206, `rainbow_z80n_sprites_diag.nex` bb2058c8bb9d593364aa1515a38a130c; verified 2026-10-22
- Everyone's a Wally (wally): `wally.nex` 2e615b3e7ae995e6d6a6ed9e3f586d4d, `wally_sprites.nex` f7605489c3af55b8e8c6a580c1c26150; verified 2026-10-13
- Everyone's a Wally (updated) (everyones_a_wally_updated): `everyones_a_wally_updated.nex` 2e615b3e7ae995e6d6a6ed9e3f586d4d, `everyones_a_wally_updated_sprites.nex` 31c3ef131330d26238b01a69b35c647e; verified never
- Spellbound Dizzy (Dizzy V) (dizzy5): `dizzy5.nex` c99189f3274a4803f0b25b0217206bdb, `dizzy5_sprites.nex` 1f33c467e6aa55585cea79cfbb24bcfe, `dizzy5_sprites.nex --strategy slot1` a59c1fd91ec5c32e549526dbc08d2e69 (re-checked 2026-09-28; 00a7c496... had an EMPTY font page: dialogue text blank on hardware); verified 2026-10-13
- Prince of the Yolkfolk (Dizzy 6) (dizzy6): `Dizzy6.nex` e02faca34df9504cc1f2f162e0ef791e, `Dizzy6_sprites.nex` f491e1f6621559ccc4d36de3535ff5d0; verified 2026-10-13
- Fantasy World Dizzy (fantasy_world_dizzy): `fantasy_world_dizzy.nex` cd620010e2f61af0002e76718945716f, `fantasy_world_dizzy_sprites.nex` 9182f2f8b4b0dc55b59a69728568b403, `fantasy_world_dizzy_sprites.nex --strategy printer` c09213beaec1572c0228985dae89bd77; verified 2026-10-13
- Magicland Dizzy (magicland_dizzy): `magicland_dizzy.nex` 09eb18496cff334ea17bfc0b0c94585d, `magicland_dizzy_sprites.nex` bf137d41d3cc08221bf6fdda153c9de2, `magicland_dizzy_sprites.nex --strategy slot1` d3b37c05d4c47ada07294fa2d7c1ae76; verified 2026-10-13
- Treasure Island Dizzy (treasure_island_dizzy): `treasure_island_dizzy.nex` 4dae1a3a15b2158642a5d5b82de92ef7, `treasure_island_dizzy_sprites.nex` 8b4d0847d68fce3215bd43a0e116e682; verified 2026-10-13
- Treasure Island Dizzy (title screen) (treasure_island_title): `treasure_island_title.nex` 70890aba7d821fba8a41e63636eb58be, `treasure_island_title_sprites.nex` 85e054fe4bce8e4b3a8e336aac432f58; verified 2026-10-13
- Dizzy: The Ultimate Cartoon Adventure (dizzy1): `dizzy1.nex` 7892b2e0f1f3f9f19165516db307cbe0, `dizzy1_sprites.nex` fb4cb1482b3e337374ca99c3ff58edad; verified 2026-10-13
- Commando (commando): `commando.nex` a206f950c12f58a8e7f26b366f5a2480, `commando_sprites.nex` d601385ee4aeb7f3d7c0771bdc27df6b; verified 2026-10-13
- Crystal Kingdom Dizzy (128K) (crystal_kingdom_dizzy): `crystal_kingdom_dizzy.nex` 99975f65172dc86ecefbac07db2c0c00; verified never
- Midnight Resistance (128K) (midnight_resistance): `midnight_resistance.nex` 17239acaaf67b0f8011478053e17829d, `midnight_resistance_sprites.nex` 670f94034af175ed56df97f8cdb1ef29; verified 2026-10-14
- Smash TV (smash_tv): `smash_tv.nex` c72ea298486b14036ac1a87ac89c3f0e, `smash_tv_sprites.nex` 03979d5438cf55410ecec8aac76f05ec; verified 2026-10-13
- Target Renegade (128K) (target_renegade): `target_renegade.nex` a0be8dc03a1be8c6d67dc3e0229abc35, `target_renegade_sprites.nex` e0b246e35d028c34170e1d1c52f00f5f; verified never
- Jetpac (jetpac): `jetpac.nex` feff51b7038606d21c03c260055481e4, `jetpac_sprites.nex` c963b42f0e685d648d552656fde4d6f9; verified never
- Lode Runner (lode_runner): `lode_runner.nex` cd0c1659c8569b2fa80da74962af90d2, `lode_runner_sprites.nex` 85fe6afd593679bf59c787230ba0eaca; verified never
- Match Day (match_day): `match_day.nex` 612761ec2772c5a7dcd27f939588d227, `match_day_sprites.nex` f0aecd138d1668ff057318c2545f539d; verified 2026-10-20
- Cyclone (cyclone): `cyclone.nex` 390516396ca4d385c94b7f7bd2315d31, `cyclone_sprites.nex` 25c1b1e070b07565fe4d1a38f69e3024; verified 2026-10-21
- The Incredible Shrinking Fireman (incredible_shrinking_fireman-add-OPUS): `incredible_shrinking_fireman-add-OPUS.nex` feb706fcdaa29f13844a7b4982dc21fa, `incredible_shrinking_fireman-add-OPUS_sprites.nex` 53f2665e76775f3c1b404aba74e93a7b; verified 2026-10-25
- The Incredible Shrinking Fireman (GPT6_ASTRA) (incredible_shrinking_fireman-add-GPT6_ASTRA): `incredible_shrinking_fireman_plain-add-GPT6_ASTRA.nex` f8f213e55e3da01349827f8ae7d93bee, `incredible_shrinking_fireman_sprites-add-GPT6_ASTRA.nex` 1ea61f0bcaf2b5f27514807f8753f263; verified 2026-10-26
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

## Rainbow Islands, Z80N version (128K, engine `rainbow_z80n`) - 2026-10-22
Fork of engine `rainbow` (cf017271, now deprecated) onto nexclash/z80n.py, Z80N hooks (13 SWAPNIB,
2 MIRROR A, 2 ADD HL,A) and the rsafe raster pair read (Open 1b). Before the hook changes the fork
rebuilt 7ac543fb / cf017271 / c16751b0 byte for byte. `selftest.py --game rainbow_z80n --verify
--stamp`: PASSED - rainbow.rzx 7,178 frames / 2,216 renders and rainbownew.rzx 11,799 frames / 3,530
renders IDENTICAL, diagnostic IDENTICAL, unit PASS incl. one as-NOP negative control per Z80N
instruction (SWAPNIB, MIRROR A, ADD HL,A). Outputs: plain 7ac543fb (unchanged), sprites bda21ab6,
diagnostic bb2058c8. First quick verify with NEXTREG timed found the rsafe crossing (1 of 1416
renders); fixed. Hardware 2026-10-22: bda21ab6 works on a real Next, "feels smoother" (user).

## Rainbow Islands (128K, engine `rainbow`) - 2026-09-28
`nexclash.py auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx --no-record` (defaults: ink white, outline black)
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 (plain, tail 0x9F00) - boot sim OK
- `rainbow_sprites.nex` 0c191d94d5c3291e96f282cc6b1e4984 (altrom stubs + RAM pages 26/28/29) - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces, max 27/frame, 257 stars on the ULA - IDENTICAL
- rainbownew.rzx: 11799 frames, 29314 pieces, max 30/frame, 613 stars on the ULA - IDENTICAL
- `--outline transparent` on rainbow.rzx - IDENTICAL (outline pixels counted as expected drops)
- unit tests: edge columns, last slot, passthrough at 32 pieces, negative control, class colour - PASS
- Hardware: runs (Dean, 2026-09-28); detailed visual checklist results not reported

## Rainbow Islands - 2026-10-19 no rainbow border + collectable insides (cf017271 / diag c16751b0)
- RELEASE `auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx --no-record`, profile class colours
  (C3 no outline): rainbow_stripped 7178 frames, 11865 pieces -> IDENTICAL; rainbownew_stripped 11799
  frames, 29314 pieces -> IDENTICAL; diagnostic 1506 frames IDENTICAL; unit PASS, 22 object negative
  controls detected (new: 'collectables' inside pixels not drawn'; 'no black border' now on a profile
  copy with borders on, its base PASS).
- Found on the way: with the class colours the pixel check failed (62 ink pixels of thrown-rainbow
  pieces, IX 60130, not covered): attr2 took CLASSTAB's bit 0 (no-outline flag) as X8. Registers and
  memory matched; only the per-pixel check against the original plot saw it.
- Bookmark verify (playthrough rounds, boss rounds of islands 7..1): see games/rainbow_islands.md.

## Rainbow Islands - 2026-10-19 no raster wait + music queue + faster tiles and commit
RELEASE level (`auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx --no-record`). Changed:
rainbow.py, rainbow_hooks.asm, rainbow_islands.json (hook hex, symbols); two new bank-1 sites (music).
- `rainbow.nex` 7ac543fb51c7a3c4137778eeb3cdc175 - UNCHANGED, boot sim OK
- `rainbow_sprites.nex` c5e1823de3a66b3c468961ebb72d383d - boot sim OK
- `rainbow_sprites_diag.nex` 712221059d9351bece24629e3ae7a77d - boot sim OK
- rainbow.rzx: 7178 frames, 11865 pieces; commits 2212 checked where they happened (716 at the render
  end, 1499 at the next interrupt, 3 dropped after a non-play screen); 34673 AY writes, 6681 player
  ticks queued, chip = the original's registers after every tick sent; 36119 object tiles - IDENTICAL.
- rainbownew.rzx: 11799 frames, 29314 pieces; commits 3525 (170 / 3360 / 4); 16473 AY writes, 10757
  ticks; 139988 object tiles; overflow entries 2 - IDENTICAL.
- Diagnostic build: first 1506 frames - IDENTICAL.
- Timing (simulated, 28 MHz, beam modelled from the interrupt at line 248): whole game frame max
  18.1 / 22.9 ms, frames over 20 ms 0 / 2 (e50733b2: 9 / 16 before its raster wait, avg 3.4 ms, was
  counted). Render-end hook avg 0.45 / 0.08 ms (commit mostly at the interrupt).
- New checks: render end commits at once exactly when the line read is >= 240 and line + sprites
  <= 307, else defers with no sprite / tilemap / pattern writes; the deferred commit = the staged
  state at the next interrupt, or dropped (no writes) after a non-play screen; bank-1 sites: patched
  = original (registers incl. F, memory), entry-point proofs for both; AYModel (queue + chip vs the
  original's chip state).
- New unit tests: AY queue against the model on 400 frames of play-shaped sequences (1040 ticks
  sent, overruns, writes outside a tick, registers >= 14, full queue) + control (value OUT removed:
  detected); commit at once / deferred at lines 100 / 175 / 15 / 176 / 200 / 239 / 240 / 300 / 309 with
  the deferred commit run at line 248 and dropped with $7F set + control (CALL C -> CALL: detected);
  diagnostic border (blue = deferred commit). Four older unit checks whose failure key could never
  fail ('FAIL! detail') fixed.

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

## Everyone's a Wally, updated (128K snapshot, engine `wally2`) - 2026-10-14
The first version above is frozen (record wally "excluded"; `--engine wally` rebuilds it: both MD5s
reproduced 2026-10-14). `nexclash.py auto wally.z80 --rzx wallyrzx.rzx` (wally2 is the default):
- `everyones_a_wally_updated.nex` 2e615b3e7ae995e6d6a6ed9e3f586d4d (plain, tail 0x6B00) - boot sim OK
- `everyones_a_wally_updated_sprites.nex` 31c3ef131330d26238b01a69b35c647e (altrom stubs + pages
  26/27, Layer 2 banks 16-21, 14 canvas pages 44-57; no colours painted yet) - boot sim OK (set-up:
  $15 = 0, $69 = $80, $12/$13 = 16/19, $14 = $E3, Layer 2 pages empty)
- wallyrzx.rzx (11 autosave snapshots stripped): 15225 frames; A 4299, B 1058, C 3003 plots
  converted (0 passthrough), 3938 commits (max 9 plots), 3900 restores, 36 clears, 2,219,552 Layer 2
  pixels - IDENTICAL: at every hook site registers (AF' included) and memory outside the back /
  attribute buffers vs the original, each plot's staged entry (canvas, position, colour, orientation,
  joined) and canvas ink vs the original's graphics bytes, the whole Layer 2 image on show after every
  commit vs the model (wally2.Model), restore drops the list, clear hides Layer 2, no PC inside a JP
- unit tests: 930 position / guard cases (543 converted, 387 passthrough), 921 graphic cases (every
  graphic as stored, mirrored in place, and with a changed byte = passthrough), joined pairs B and C +
  their commits, 4 commit rounds (box clearing: no stale pixels), restore; negative control (ink /
  outline codes swapped in the canvas pages) detected 3/3 - PASS
- recolour: {} = the build byte for byte; a synthetic map = the build made with that map; and back
- speed (simulator T, hooks at 28 MHz ~1/8): plots A/B/C original 61.6M / 7.5M / 8.0M T, hooks
  50.4M / 7.6M / 14.1M; commit hook mean 156,896 T, max 736,534 T per render (~0.3 / ~1.3 frames of
  3.5 MHz time at 28 MHz) - the plots' saved time roughly pays for the mean commit
- Hardware: untested

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
- With Dean's painted colours (444 graphics bytes): `midnight_resistance_sprites.nex`
  670f94034af175ed56df97f8cdb1ef29 - both RZX IDENTICAL (sprite pixels compared in the painted
  colours), unit + map + interrupt (119M instructions) PASS; hardware OK (Dean, 2026-10-14).

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

## Target Renegade (128K, engine `renegade`) - 2026-10-14
`nexclash.py auto target_renegade.z80 --rzx target_renegade.rzx --no-record` (~12 min)
(Renegade_II_Target_Renegade_1988_Imagine_Software_128K.z80 1895877d = the 128K BASIC loader at its
last PAUSE 0; Dean's RZX 464d4eea from its own SZX at the game menu, 9 autosaves stripped, 7,039
frames: level 1 (car park), bikers, the motorbike, the floor weapon)
- `target_renegade.nex` a0be8dc03a1be8c6d67dc3e0229abc35 (plain; start = the loader run in the toolkit
  to 23340, after the entry code's OUT (0x1FFD),4: 7FFD = 4, ROM 0; front end 0x6480; tail 0x6400,
  write-first in the RZX and a free run) - boot sim OK (registers, banks, RAM, 7FFD 4 / 1FFD 0, MMU).
- `target_renegade_sprites.nex` e0b246e35d028c34170e1d1c52f00f5f (hooks 0x2200-0x2902 in alt ROM
  images 0 AND 1; page 26 (H) at slot 2 during hooks, page 27 (Q) at slot 2 during the game's copy;
  colour store pages 28-39) - boot sim OK incl. both alt images and $8C; 9 patch sites, original bytes
  checked; static check: no DD/FD, DI/EI, IM, LD I, RETI/RETN in 1,774 hook bytes.
- Front end: 9 cases (a key in each keyboard row; a key held at start must be released first): every
  register (R aside) and all RAM = the loader's own state at 23340, except 0x6480-0x64FF.
- RZX: 24,670 plots (12,234 / 12,436 mirrored), 2,258 draw-alls, 2,257 commits + copies (max 33
  sprites), 2,256 restores, 3 scenery redraws, 106 text prints, 1 screen clear (with ROM 1 selected)
  - IDENTICAL. Per event: original vs patched from the same state to the same point (the copy: to its
  return, the patched copy writing page Q): all registers (AF' included), all memory (the screen only
  at the draw-all and the copy, checked by the model instead); interrupt safety after every hook
  instruction (IX, IY, I, IFF, SP: hook stack or the site SP minus the displaced PUSHes, no fetch at
  0x3D00-0x3DFF); MMU slots 2/3/7 and 3.5 MHz restored; no port read, no OUT but NextReg / sprite ports.
  Per commit: (1) the patched ULA play area = the clean buffer (scenery); (2) the sprite layer = the
  plots of the frame, each the ORIGINAL plotter run on a 0x00 and a 0xFF buffer (ink / body / clear;
  3,735 runs, cached per unclipped graphic), composed in plot order, coloured ink 8 / body 7 or by the
  map: 3,849,290 pixels; (3) end to end: the original screen after its copy = ULA + sprites (ink where
  the top sprite pixel is ink, else the ULA bit). No jump into a patched instruction; the game never
  changes a site's bytes; every site reached with bank 0 at 0xC000 (the clear: ROM 1, bank 0).
- Plot model (renegade.plot_params / plot_writes) = every written address and byte of all 24,669
  plots (separate check, phase A).
- Unit (3 captured commits): 215 commit cases (267 parts converted, 140 not by the guard: W 0/7,
  R 0/65, record or graphic below 0x6000; widths 1/2/6, clipped left / right, line 127 wrap, a graphic
  in bank 0, mirrored with bytes 58 - the mirror table's one non-reverse entry), the same commits again
  from the cache, 4 plot-hook cases (the 64th part logged, the 65th dropped; registers / memory as the
  original), log full (65 parts), patterns full (40 four-pattern parts: 32 shown, 8 dropped), a
  synthetic colour map (219 entries, transparent and outline pixels) and the same map with wrong check
  bytes (ignored). Negative controls 5/5 detected: the map left out, ink / body swapped (3), LD IY
  in a hook.
- Recolour: recolour(build, map) = the build made with that map (NEXCLASH_COLOURS) and
  recolour(that, {}) = the build, byte for byte (banks 13, 16-18 changed).
- Speed (simulated): +145K simulator T per 3-frame game frame in the 28 MHz hooks (~18K T at 3.5 MHz)
  + 3.8K T in the plot hooks; the game HALTs ~35K T per game frame (RZX).
- Shared code: nexclash.py gained one dispatch block. `selftest.py --canary`: see the PR.

## Dizzy: The Ultimate Cartoon Adventure (48K, engine `dizzy1`) - 2026-10-14
Objects on Layer 2 through a 1-bit shadow screen, solid (enclosed paper black, display-only fill
shadow), transparent painting; Dizzy = hardware sprites 0-3 in front, his own shadow
(games/dizzy_ultimate_cartoon_adventure.md). Hardware round 1 (16a00451): runs; Dizzy mixed with
objects -> this build.
`nexclash.py auto dizzy1.z80 --no-record --rzx dizzy1.rzx` (the record's verify recipe):
- Static: hook code 1,984 bytes at 0x2000-0x27BF (sprite table skipped), no EXX / EX AF / IY / I /
  IM / DI / EI, nothing at 0x3D00. Boot (nextboot): registers, RAM, ROM view, paging, $8C OK; Layer
  2 bank 16, port 0x123B = 2, palette 0-15 (0 = $E3), banks 16-18 zero. Plain dizzy1.nex unchanged
  (7892b2e0), build decisions = stored. Interior masks: 3,888 graphics bytes, 7,921 pixels, no byte
  in two frames, Dizzy's shifted copies identical to frames 0-38 shifted. Dizzy: 88 patterns.
- dizzy1.rzx, 6,346 frames: PASSED. Forked at every hooked routine from the real state - 7,086
  converted + 1,356 kept plotter-2 calls (76 with the clipped-row helper), 2,364 Dizzy calls (whole
  calls to their return), 7,030 attribute reads, 21,686 + 19,195 collision reads, 425 type-3 and
  1,192 type-7 effect folds, 24 + 24 wipes: all registers (AF' included), all memory, screen and
  attributes as ULA ^ objects ^ Dizzy == the original, the object / fill / Dizzy shadows and
  2,050,456 Layer 2 pixels against the independent model; after every Dizzy plot, wipe and pending
  hide the sprite registers rendered from the patterns = the expected Dizzy image at x = 4E,
  y = 192 - L - rows (hidden / pending / shown as the expected parity), and that image's ink = the
  pixels the game's plotter drew into his shadow; per hook instruction IY / I / IFF / IM / alternate
  set unchanged, hook stack room >= 18 bytes, nothing pushed below the game SP, slot 3 and 3.5 MHz
  restored, only sprites 0-3 written; ROM 0x0038 handler at every site; no unhooked access to a
  figure byte or cell; no game write to a patch site; site interiors entered only sequentially.
- Unit: 53 cases PASSED (every plotter mode, converted and kept; draws over figure bits; rows past
  line 191; off-screen reads; every effect branch with figures inside; wipes; synthetic colour map
  with transparent masks; Dizzy erase -> pending, pending + plotter 2 / wipe -> hidden, a plot the
  original skips -> nothing, Dizzy partly above the screen). Negative controls 9/9: no virtual read,
  no fold (rotator, wipe), room renderer converted, hook stack too deep, colour map left out,
  interiors left out, Dizzy sprite one pixel off, Dizzy patterns left out.
- coloursheet (`selftest.py --tools`): transparent painting golden checks PASSED.
- Speed (no frame sync in the game): median frame -1,069 T (faster than the original), worst frame
  (room change) +168,970 T, 28 MHz parts counted / 8.

## Dizzy 1: Dean's painted colours (2026-10-14)
Painted sheet (160x486 = layout) read back with `python -m nexclash.dizzy1 colours PNG --layout
LAYOUT` -> docs/profiles/dizzy1_colours.json (new; no earlier map to merge): 1,846 pixels recoloured,
109 painted transparent, 633 graphics bytes with colours, 0 painted differently in two places, 0 off
the palette; 264 painted pixels ignored (black on paper open to the outside of a figure: the door's
gaps, one "from the code" figure, edge pixels of 13 Dizzy frames - outside paper is see-through by
design). Sheets redrawn from the map: the PAINTING sheet equals the painted one except exactly those
264 pixels (round trip exact).
Verify recipe (`auto dizzy1.z80 --no-record --rzx dizzy1.rzx`) with the map in use ("Colours: 633
colour-map entries"): static, boot, Layer 2 OK; dizzy1.rzx 6,346 frames PASSED (same counts as the
section above; 2,050,456 Layer 2 pixels against the model in the painted colours); unit 53 cases
PASSED, negative controls 9/9 (incl. colour map left out); build decisions = stored. Dizzy: 92
patterns (88 before: painted frames no longer share patterns). dizzy1_sprites.nex 38e1a491, plain
dizzy1.nex unchanged (7892b2e0). Speed: median -989 T, worst +168,970 T.

### Outlines (painted paper bits, coloursheet paint_clear) - 2026-10-14
Dean's outlined painting (2,471 outline pixels, 118 recolours) -> dizzy1_sprites_painted.nex
79218527 (map 1,633 bytes; 233 outline bits on Layer 2 figures, the rest on Dizzy; 95 patterns).
- Defaults unchanged: recolour with no map -> 83ea050d (the recorded build). Dean's previous map
  -> 166 bytes differ, all Dizzy shifted-copy colour nibbles on PAPER bits (now 0) + their
  has-colours flags: the dz_keys right-edge wrap fixed (never drawn: not ink, not in a fill mask);
  patterns unchanged. Profile colour_inputs 14,571 -> 14,532 bytes (the 39 wrapped bytes no longer
  read; recomputed from the snapshot = the .nex's).
- Sheets regenerated with the reference map: both PNGs pixel-identical, figure boxes identical;
  the sheet drawn with the new map = Dean's painting pixel for pixel, re-read -> the same map.
- Midnight Resistance (the other coloursheet user): old vs new coloursheet on its reference layout:
  write (painting + reference) byte-identical, read (its sheet + a 4,000-pixel random repaint, clear
  on / off) the same maps and reports.
- Differential verify of dizzy1.rzx with Dean's map: PASSED (6,346 frames, 7,086 converted +
  1,356 kept plotter-2 calls, 2,364 Dizzy calls, 2,050,536 figure pixels, 2,395 sprite checks).
- Unit: 55 cases PASSED; synthetic map now with 11,379 outline pixels (random paper colours on
  plotter-2 graphics, a black outline on Dizzy). Negative controls 11/11: + outlines left out of the
  plane, + outlines left out of Dizzy's patterns.
- `selftest.py --tools` PASSED (+ 4 paint_clear golden checks), `--canary` PASSED (stage 1).
- After merging main (Dean's map = the build default, shared recolour): `auto dizzy1.z80 --no-record
  --rzx dizzy1.rzx` -> dizzy1_sprites.nex fb4cb148 (was 38e1a491: 127 bytes of Dizzy shifted-copy
  PAPER nibbles -> 0 + 41 has-colours flags, nothing drawn changes; 92 patterns), plain 7892b2e0
  unchanged; dizzy1.rzx PASSED (6,346 frames, 2,050,456 figure pixels), unit 55 cases, negative
  controls 11/11 PASSED; `selftest.py --game dizzy1` PASSED (rebuild MD5s + recolour guard both
  ways); `nexclash.py recolour` on Dean's outlined painting -> 79218527 (as above).

## Jetpac (48K / 16K game, engine `jetpac`) - 2026-10-19
No recording (Dean): differential test on a free run (`jetpac.free_keys`, 6000 frames), same method
as an RZX run - at every hook site (29263 draw, 29344/29349 erase, 24717 clear) and at the colour
paint 29135 the original and the patched code run from the same state to the routine's return:
all registers but R/T/MEMPTR, all memory outside the screen (and 64 bytes of dead stack), no screen
or attribute write by the patched code, sprite pixels = the original's figure drawn on a zero screen,
sprite colour = the object's ink, no other sprite changed, NEXTREG only $07 (left at 0) and $34-$39.

| Check | Result |
|---|---|
| free run 6000 frames | 20433 draws, 100 erases, 23192 colour paints, 5 clears, 2193166 sprite pixels: IDENTICAL |
| 29264/29265 reached only after 29263; CALL-site interiors never | OK |
| unit: every graphic (static, 8 levels' aliens, 12 carried parts) x 8 positions (both edges) x 3 inks x objects 0/16 | 5616 PASS |
| unit: erase, clear, IX outside the object table (no sprite) | PASS |
| negative control (patterns shifted 1 px) | detected 40/40 |
| setup pattern upload (simulated: 10240 bytes across both pages of bank 11 = the built patterns), palette | OK |
| boot simulation, plain + sprites | OK |
| selftest --game jetpac (rebuild, MD5s, asm2profile) | PASSED |
Not proven: the game's own paths beyond the free run (rocket build, fuel, items, levels 2+, two
players) - hooks covered by unit tests only; hardware untested.

## Match Day (48K, engine `matchday`) - 2026-10-20
Dean's Fuse RZX (Match_Day_1985_Ocean.rzx: 1 autosave stripped; title, menu, walk-on, ~6 match
minutes, a goal, a keeper dive) + the spectrumcomputing.co.uk RZX (50,404 frames, its own start
snapshot, same code). At every hook event (image build 0x8DEC, 4-row clear 0x8D63, player draw
0x8B45 including the XOR draw 0x8ECE, ball 0x9D15, match loop pass 0x817F, screen clear 0xE62C,
loop exit 0x819D) original and patched code run from the same state to the event's end: all
registers but R/T/MEMPTR, all memory outside the screen / attributes and 64 bytes of dead stack (the
hook stack 0x5BA8-0x5BFF included: every hook puts the cup team names back), every patched screen
write equal to the original's and the original's other screen writes exactly the removed figure
writes; sprite pixels = each figure's own XOR footprint on the original screen (the image as it is
AT the draw), depth order by bottom y, the dive's spare half locked to the keeper half's camera
position; per instruction inside a hook: IX / IY / I / IFF unchanged (IFF = 0 only after e_exit's
replayed DI), >= 32 free bytes of hook stack, slot 3 untouched, slot 6 only the state / row pages;
no game write to a patch site; no jump into a patched instruction. Boot: both builds booted with the
printer buffer overwritten as NEXLOAD leaves it (nextboot `nexload`): every RAM byte equals the
snapshot.

| Check | Result |
|---|---|
| match_day.rzx, 6211 frames | 36,605 draws, 92 builds, 2,299 ball, 2,301 passes, 2 clears, 1,797,409 sprite pixels: IDENTICAL; speed +1,584 T per frame (+2.3 %) |
| match_day_spectrumcomputing.rzx, 50,404 frames | 376,695 draws, 186 builds, 24,230 ball, 24,251 passes, 23 clears, 2 exits, 20,597,211 sprite pixels: IDENTICAL; speed +2,431 T per frame (+3.5 %) |
| explained notes (the original's behaviour) | edge-dispatch debris 71 / 678, column culled at the screen edge 18 / 114, overwriter debris 6 + ball 5 |
| unit: every frame 0-115, every upper body 0-17, dive across the left edge, walks off / onto both edges and the bottom, x shifts 0-6, full palette banks, object outside the table (guard), 80 captured states | 461 PASS |
| negative controls: x shift ignored / state page at slot 3 (interrupt safety) / hook stack bytes not put back | 3/3 detected |

## Lode Runner (48K, engine `loderunner`) - 2026-10-20
Dean's Fuse RZX (LODERUNN.rzx: 8 autosaves stripped; key definition, level 1, two lives lost; the
.z80 is its own first snapshot) + a 6000-frame free run (`loderunner.free_keys`: play to game over).
At every patch site (draws 0x9A5C / 0x970C / 0x9E1B, guard death 0x96B6, level-start prints 0x8E5F /
0x8E74, fade 0x854F, clear 0x8541, the five figure paints, and the untouched erases 0x9A47 / 0x9E03
whose plotter writes are removed) original and patched code run from the same state to the site's
end: all registers but R/T/MEMPTR, all memory outside the screen / attributes and 64 bytes of dead
stack, no screen / attribute write by the patched code (level-start prints: the blank tile exactly
over the figure's cell), sprite pixels and colours = the original's figure drawn on a zero screen,
no other sprite changed, NEXTREG only $34-$39, the patched code's lowest SP >= 0xAB03 (IM 2 table
below). Over the whole run, a model of the patched game's screen and attributes: at every frame end
(outside a fade) ULA difference = the XOR of the visible sprites' graphics; every screen / attribute
read by game code sees the same value in both (classified: the plotter's and the cell XOR's own
reads, the fade's mask / target reads - always followed by the full clear - and 0x9665's attribute
read, whose result only selects a figure paint the build removes; A and F are overwritten at
0x9671-0x9674); no game write to a patch site or hook byte; no jump into a patched instruction.

| Check | Result |
|---|---|
| lode_runner.rzx, 4567 frames | 3254 draws, 3254 erases, 10 level-start prints, 8303 paints, 7 fades + clears, 59003 sprite pixels, 4352 frame checks, 3 harmless attribute reads, lowest hook SP 0xAB17: IDENTICAL |
| free run, 6000 frames (play to game over) | 1006 draws, 1006 erases, 25 level-start prints, 3002 paints, 9 fades + clears, 18885 sprite pixels, 5779 frame checks, lowest SP 0xAB19: IDENTICAL |
| unit: graphics 16-30 x 8 slots x 48 positions (edges 0 / 248, 0 / 175) at 0x9A5C; respawn 0x970C x 7 guards; runner 0x9E1B | 5760 + 105 + 45 PASS |
| unit: guard death (7), level-start prints (runner 4, guards 28), fade, clear, paints (5 sites x 3 colours x 4 cells) | PASS |
| unit guards: IX not a figure record (6), graphic outside 16-30 (4), print outside the guard list (4: the original print) | PASS |
| unit: synthetic colour map (every graphics byte of both kinds, transparent pixels, a wrong check byte ignored), expected colours computed independently | 30 PASS |
| negative controls: patterns shifted 1 px / paints as NOP NOP NOP (flags) / fade without its hook | 6/6, 6/6, 6/6 detected |
| set-up simulated from the .nex: pattern upload = the built patterns (3840 bytes), palette, transparency, 128 sprites hidden, sprites on, MMU restored (negative: one pattern byte changed -> detected) | OK |
| recolour: {} -> the build byte for byte; synthetic map -> bank 11 only, back to {} -> the build; plain .nex refused | OK |
| boot simulation, plain + sprites (tail 0xA400) | OK |
| hook RAM 0xA33C-0xAAFE untouched: RZX + free runs to game over and through the editor / key redefinition (30000 frames each) | OK |
Not proven: tape LOAD / SAVE SCREENS, hall of fame name entry, level 2+ in a recording, a guard
trapped and respawned in a recording (unit tests only); hardware untested.

## The Incredible Shrinking Fireman (48K, engine `incredible_shrinking_fireman_add_opus`) - 2026-10-25
Build 53f2665e (replaces 400d0d11 after hardware round 2: interrupts deferred while a plot runs, the
IM 2 set-up patched too; 400d0d11 replaced dc65565c after round 1: plot entry hook, black mask).
Dean's Fuse RZX (incrediblefireman.rzx, 32492 frames, no autosaves; the .z80 replays it). At every
hook site (plotter entry 0xB950 and exit 0xBC5C, diamond draw 0xECFF, clears 0xC4A7 / 0xC5B1 /
0xB4AD) original and patched code run from the same state to the site's end: all registers but
R/T/MEMPTR (AF' included), all memory outside 64 bytes of dead stack, NEXTREG only $07 / $34-$39 /
$56 (pages 26-30) / $57 (shape pages 32-63), MMU6 / MMU7 back to pages 0 / 1, no ROM write, no write
to a shape page; interrupt safety at every patched instruction executed with IFF set (IX the site's or
POP IX's, IY, I, alternate set unchanged, SP at most one push below the site, MMU6 / MMU7 unmapped, no
fetch at 0x3D00-0x3DFF). After every event the patched machine's sprite layer (attributes + pattern
RAM rendered) = an independent Python model: objects as last plotted with their black 4-neighbour
mask, each object's pending image from its plot entry to its exit, objects 1 and 2 on one spot with
one frame hidden (XOR cancel), the diamonds drawn since the last clear, live inks / colour map. The
model is tied to the ULA: every plot's screen change = old ^ new image of the model, and from entry
to exit every pixel of the old and the new image is under a visible sprite (the half-done XOR plot is
never uncovered); the exit's (x, y, frame) = the entry's prediction; every diamond = its 7 graphics
bytes at (C / 8, B - j). The removed figure attribute painting (0xBCDF): every attribute read by game
code (0xCAA2, 0xCABF, 0xB3F4, 0xB3C5, 0xB42C, 0xC2E4 / 0xC2E8) checked against the cells the patched
game leaves unpainted. The graphics the build precomputes from are never written; no game write to a
patch site (except the game's IM 2 set-up 0xC234 rewriting JP 0xC24C at 0xFFF4 on a restart, frame
32335: the patched set-up writes the hook, unit-tested); 0xB952 / 0xBC5E reached only from their sites;
no jump into a patched instruction. Interrupts: every interrupt that arrives while a plot runs (entry
hook to exit hook) is deferred: the handler is entered once, from the exit hook at depth 0, with the
plot's caller as return address (_defer_check from the live state).

| Check | Result |
|---|---|
| incrediblefireman.rzx, 32492 frames | 27883 plot entries + exits, 29891 interrupts (54 deferred to a plot exit), 79 diamonds, 165 clears, 49170529 sprite pixels, 5117824 transient pixels covered, 1112377 plot screen bytes, 553 diamond bytes, 169038 attribute reads, 19737 interrupt-safety points: IDENTICAL |
| non-figure screen writes under a visible sprite | none in the whole RZX |
| plot entries of a pair-hidden figure (its old pixels uncovered while it moves) | 242 (known limit, games/ Open) |
| speed (hook cost per 69888-T frame, 28 MHz parts / 6) | mean 2331 T, 99 % of frames with hooks <= 10185 T, max 16584 T (room entry: three ink tables built) |
| unit: an interrupt injected at 20 points spread over each of 2 main-code plots (patched: plot = no interrupt) | 2 PASS (the original corrupts 0 and 19 of 20) |
| unit: the IM 2 set-up 0xC234 writes JP e_isr to 0xFFF4 | 1 PASS |
| unit: entry + exit, fireman, every frame 0-255 x 4 moves (incl. x / y carries) | 1024 PASS |
| unit: entry + exit, figures (appear, wrapped frames, vanish, same image) | 10 PASS |
| unit: exit alone (fallback), fireman every frame 0-255 x 36 positions; figures 7 frames x 3 positions x 4 inks | 9216 + 168 PASS |
| unit: pair rule, object guard, cache sequence, colour map (painted frames below / above the 8-bit wrap, a wrong check byte ignored) | 3 + 1 + 1 + 2 PASS |
| unit: diamonds k 0-4 x 4 positions x 3 cell inks; loop counter 0 / 6 (guard); screen clears | 36 + 24 + 3 PASS |
| negative controls: sprite X 1 px off / pair rule left out / diamond 1 line low / cache ignores the ink / colour map left out / pending sprites not shown at the entry / mask left out / interrupt not deferred during a plot / IM 2 set-up operand left out | 9/9 detected |
| recolour: {} -> the build byte for byte (banks 13-31); a changed patch site refused; selftest guard | OK |
| boot simulation with NEXLOAD, plain + sprites (tail 0x5D00, printer buffer put back) | OK |
Hardware: dc65565c ran on a real Next (Dean, 2026-10-25): flicker on the bulb / enemy fireman (the
half-done plot uncovered between hooks: fixed by the entry hook), no mask (added). 400d0d11: corruption
in room 5 (the ISR's plot inside a main-code plot; the plotter is not re-entrant: fixed by the
deferral). 53f2665e untested.
Not proven: the 21 graphics the RZX never draws (unit-tested only); a painted colour map in play.

## Toolkit: colour sheets show only the paintable pixels (2026-10-14)
coloursheet.write greys only the pixels the read-back uses; the rest of a box keeps the background
colour, which the read-back ignores. Old vs new code on the same figures: Midnight Resistance
painting sheet 14,818 pixels grey -> background (only those; the old code reproduces the reference
sheet pixel for pixel), reference sheet 17,866 (the same), layouts identical, untouched read-back =
the map with no ignored paint; Dizzy 1 sheets unchanged (every pixel in its boxes is paintable).
`selftest.py --tools` PASSED (+ 2 golden checks), `--canary` PASSED.

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

## El Capitan Trueno (48K, contributor's prototype outside the toolkit) - 2026-10-14
Built by `trueno/build/make_nex.py` (the contributor's project, sent with this file; not a toolkit
engine yet: no profile and no evidence record - a record would make selftest rebuild it through the
toolkit). Recipe and facts: games/el_capitan_trueno.md.
- Inputs: `Capitan Trueno, El (1990)(Dinamic)(ES).z80` 15e128b05c471678d2f0fae2fbb8cedc (CRC32
  320337B0, title screen), `trueno1.rzx` d07fcc914f385aabfe42c4a5cbaf1bba (the contributor's play).
- `Trueno.nex` ca49e0f4c92da6fe96d71062c2ed15a3 (plain, `--tail 0xA6C9`) - boot sim OK (maintainer
  re-check 2026-10-14; v0.1.4 and main give the same file). SUPERSEDED: the contributor listed
  4b415b4c19cb4ff0c820fd2f79216cc7 here, but that is the DEFAULT-tail build (`auto` output, tail
  below SP above 0xC000), which fails the boot sim ('boot did not reach PC 61166').
- `Trueno_sprites.nex` a9befbb250a040734555ce80aea208b8 (altrom hooks + hook page 26, 328,192 bytes)
  - nextboot.check (boot sim) OK. Options (2026-10-14): `--en` (English texts) da3f1b0a1ba8226573c638bc06cb34d5, `--immortal` deaf4577f982991774d7aa17f60d1aab,
  both 867bda87225d060964772b36c0ed2aeb (--immortal changes one byte, 0x7A1F; --en the texts and the title redraw).
- Whole-RZX checks (build/check_*.py, C simulator): render order (no plot while a render waits for
  the copy), cover (every figure pixel the game changes lies under an opaque sprite pixel: 10,508
  renders, 0 uncovered), screen reads and buffer reads (no logic reads figure pixels), no-draw
  (RAM differs only in generated row code, unread restore-list bytes and dead stack).
- NOT done: the per-call differential verification of the hooks (registers + memory), unit tests,
  negative control (games/el_capitan_trueno.md recipe step 6).
- [MAME] MAME 0.289 (not hardware): the contributor played part 1 to the end with and without the immortality cheat
  (2026-10-13/14): sprites, depth, bushes and fix cells, pause menu, the dragon's energy bar, the
  access code screen, title menu, explosions, game over - all as wanted.
- Hardware: untested (the contributor expects no problems).
- Maintainer re-check (2026-10-14, from the contributor's archive): `build_all.py` rebuilds
  `Trueno_sprites.nex` a9befbb250a040734555ce80aea208b8 byte for byte, with their tk 0.1.4 AND with
  nexclash main; `make_nex.py --en / --immortal / --en --immortal` reproduce da3f1b0a / deaf4577 /
  867bda87. Inputs' MD5s as above. Files: specnext/reference/el_capitan_trueno/.
