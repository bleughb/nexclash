# Status (2026-10-13)

One row per game, generated from the game's evidence record (docs/records/<game>.json, field
"status"): edit the record, then `python -m nexclash.records views`. Details, decisions and
checklists: games/<game>.md (named like the game's folder in the private repo; shared TID engine
facts: games/tid_engine.md). MD5s: docs/VERIFICATION.md.

<!-- generated from docs/records by `python -m nexclash.records views`: do not edit by hand -->
| Game | Engine (file) | Sprite build | Software | Hardware | Next |
|---|---|---|---|---|---|
| Chuckie Egg | chuckie (chuckie_egg.md) | Chuckie_Egg_sprites.nex bfad6be1 | RZX IDENTICAL, unit PASS | untested | hardware test |
| Rainbow Islands (128K) | rainbow (rainbow_islands.md) | rainbow_sprites.nex c5e1823d (no raster wait, music one AY tick per interrupt, faster tiles + OUTI/0x57 commit) + rainbow_sprites_diag.nex 71222105 | RZX IDENTICAL x2, AY chip = original per tick, unit PASS (19 object controls + AY + commit controls) | bddea69e smooth; bffd9357: random corruption / slowdowns; e50733b2 never tested; c5e1823d untested | hardware test c5e1823d (speed, music, tearing; diagnostic build if slowdowns remain); layer B (dark-blue partial tiles); later-islands RZX |
| Everyone's a Wally | wally (everyones_a_wally.md) | wally_sprites.nex f7605489 | RZX IDENTICAL, unit PASS | boots and runs | detailed checklist |
| Spellbound Dizzy (Dizzy V) | dizzy5 (spellbound_dizzy.md) | Dizzy_V_sprites.nex 1f33c467 (altrom) | verified (2 RZX) | untested | hardware test |
| Prince of the Yolkfolk (Dizzy 6) | tid_mirror (prince_of_the_yolkfolk.md) | Dizzy6_sprites.nex f491e1f6 (slot1) | verified (try1.rzx + mirror selftest) | untested | hardware test; mirror-room RZX |
| Fantasy World Dizzy | tid generic (fantasy_world_dizzy.md) | fantasy_world_dizzy_sprites.nex 9182f2f8 (altrom) | verified | untested | hardware test |
| Magicland Dizzy | tid generic (magicland_dizzy.md) | magicland_dizzy_sprites.nex bf137d41 (altrom) | verified | untested | hardware test |
| Treasure Island Dizzy | dedicated (treasure_island_dizzy.md) | treasure_island_dizzy_sprites.nex 8b4d0847 | verified | plain build runs | recorder start/keys |
| Dizzy: The Ultimate Cartoon Adventure (Dizzy 1) | dizzy1 (dizzy_ultimate_cartoon_adventure.md) | dizzy1_sprites.nex fb4cb148 (Dizzy = hardware sprites in front; every other figure on Layer 2 via a 1-bit shadow screen; solid: enclosed paper black; Dean's painted colours (633 graphics bytes; paper paintable: outlines), items pulse as the original; HUD and room tiles on the ULA; altrom + shadow pages at slot 3; plots at 28 MHz) | RZX IDENTICAL with the painted colour map (registers, memory, ULA ^ shadows, Layer 2, Dizzy sprite vs plotter), 55 unit cases + 11 negative controls PASS | 83ea050d (default colours) works on a real Next, looks perfect (Dean, 2026-10-14); fb4cb148 = 38e1a491 drawn identically (only never-drawn paper nibbles differ), untested | hardware test of fb4cb148 and of the outlined painting (dizzy1_sprites_painted.nex 79218527, verify + unit PASS) |
| Commando (128K) | commando (commando.md) | commando_sprites.nex d601385e (altrom + e_init + front end; solid figures (yellow body), solid objects hide figures by the walk-box depth rule, pattern-slot cache, no flicker, IX/IY-safe hooks) | RZX IDENTICAL, static + interrupt + cache + front end + init + unit + depth + restore PASS | f22a9452 / 5642e4b4 crashed (ROM 0); 5ab928e9 runs; 5c1081b7: flicker, menu logo + dots (hook used IY), figures seen through rocks (Dean) - fixed in 541e34e2, which crashed at the first figure (code at 0x3D00-0x3DFF; probable DivMMC automap); d601385e runs (Dean) | hardware test (checklist); later-areas RZX |
| Crystal Kingdom Dizzy (128K) | plain only (crystal_kingdom_dizzy.md) | - | - | plain runs | sprites deferred |
| Midnight Resistance (128K) | midres (midnight_resistance.md) | midnight_resistance_sprites.nex 670f9403 (every figure a sprite, also flipped and in the shop; Dean's painted colours: 444 graphics bytes; altrom + page 26 at slot 5, page 27 at slot 2; sprites hidden on every loop exit) | 2 RZX IDENTICAL with the painted colour map, unit + interrupt + level / shop exit + full table + flipped + map PASS | 670f9403 tests OK on a real Next (Dean, 2026-10-14) | further painting on the PAINTING_SPRITES sheet (optional); level 2 RZX |
| Smash TV | smashtv (smash_tv.md) | smash_tv_sprites.nex 03979d54 (altrom + page 26 at slot 7: the game's own plotters into a scratch buffer; every figure 4-bit sprites in its cell inks, see-through outline; pattern cache; prompt front end) | RZX IDENTICAL, front end + static + unit PASS | untested | hardware test (checklist); longer RZX (later arenas, bosses; Y = invulnerable) |
<!-- end generated -->

Platform on hardware: alt ROM ($8C) PASS 2026-09-27; plain 48K and 128K conversion run.

## Open work (toolkit)
0. Release: the latest release zip (v0.1.3, 2026-10-12 morning) predates Commando, Midnight
   Resistance, the pinned sjasmplus, asm2profile, the analysis commands and the canary - zip users
   get "not supported" for Commando and Midnight Resistance.
   Publish v0.1.4 after `python selftest.py --stamp` passes (CLAUDE.md, End of every task). v0.1.0 has no zip.
1. Engine registry: each engine registers identify/auto instead of a dispatch block in
   nexclash.py (selftest now covers every game: docs/records).
2. `identify` reports unknown for Rainbow, Chuckie Egg, Wally, Commando and Midnight Resistance (auto dispatches by
   signature in cmd_auto): add signatures.json / identify entries.
3. Generic builder covers the TID engine only; next: XOR template (generalise nexclash/dizzy1.py:
   1-bit shadow screen + Layer 2), then non-Codemasters engines (PLAYBOOK "unknown").
4. Virtual read is not in the generic template (the tool refuses and hands over).
5. Explorer is random + room novelty (no puzzles): rare paths need a human RZX.
6. analyse/recorder are 48K-only.
7. Later: tail inside the alt ROM; alt image 0 for 128K games that select ROM 0.
8. Rainbow Islands is excluded from every automatic check (record "excluded"; Dean 2026-10-13:
   too slow, being reworked) - `selftest.py --game rainbow --verify` when its work lands.
9. Not done: run `selftest.py --affected` automatically on each PR (GitHub Action with the
   private references via a secret); today a maintainer runs it before merging.
10. Recolour for every game (Dean, 2026-10-14; PLAYBOOK 3b "RECOLOUR"): shared command, guard and
   skill done; engines with recolour: dizzy1. Midnight Resistance has the sheet but no recolour
   (a repaint = rebuild + verify); the other engines have neither sheet nor recolour yet.
