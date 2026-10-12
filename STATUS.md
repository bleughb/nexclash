# Status (2026-10-13)

One row per game, generated from the game's evidence record (docs/records/<game>.json, field
"status"): edit the record, then `python -m nexclash.records views`. Details, decisions and
checklists: games/<game>.md (named like the game's folder in the private repo; shared TID engine
facts: games/tid_engine.md). MD5s: docs/VERIFICATION.md.

<!-- generated from docs/records by `python -m nexclash.records views`: do not edit by hand -->
| Game | Engine (file) | Sprite build | Software | Hardware | Next |
|---|---|---|---|---|---|
| Chuckie Egg | chuckie (chuckie_egg.md) | Chuckie_Egg_sprites.nex bfad6be1 | RZX IDENTICAL, unit PASS | untested | hardware test |
| Rainbow Islands (128K) | rainbow (rainbow_islands.md) | rainbow_sprites.nex e50733b2 (collectables without border) + rainbow_sprites_diag.nex 8f25bc61 | RZX IDENTICAL x2, unit PASS (18 controls) | bddea69e smooth; bffd9357: border on collectables unwanted, random corruption / slowdowns; e50733b2 / 8f25bc61 untested | film the diagnostic build; then smarter raster wait / tile-build limit; layer B (dark-blue partial tiles); later-islands RZX |
| Everyone's a Wally | wally (everyones_a_wally.md) | wally_sprites.nex f7605489 | RZX IDENTICAL, unit PASS | boots and runs | detailed checklist |
| Spellbound Dizzy (Dizzy V) | dizzy5 (spellbound_dizzy.md) | Dizzy_V_sprites.nex 1f33c467 (altrom) | verified (2 RZX) | untested | hardware test |
| Prince of the Yolkfolk (Dizzy 6) | tid_mirror (prince_of_the_yolkfolk.md) | Dizzy6_sprites.nex f491e1f6 (slot1) | verified (try1.rzx + mirror selftest) | untested | hardware test; mirror-room RZX |
| Fantasy World Dizzy | tid generic (fantasy_world_dizzy.md) | fantasy_world_dizzy_sprites.nex 9182f2f8 (altrom) | verified | untested | hardware test |
| Magicland Dizzy | tid generic (magicland_dizzy.md) | magicland_dizzy_sprites.nex bf137d41 (altrom) | verified | untested | hardware test |
| Treasure Island Dizzy | dedicated (treasure_island_dizzy.md) | treasure_island_dizzy_sprites.nex 8b4d0847 | verified | plain build runs | recorder start/keys |
| Dizzy: The Ultimate Cartoon Adventure (Dizzy 1) | dedicated XOR (dizzy_ultimate_cartoon_adventure.md) | dizzy1_sprites.nex 05d2bce9 | verified | untested | - |
| Commando (128K) | commando (commando.md) | commando_sprites.nex d601385e (altrom + e_init + front end; solid figures (yellow body), solid objects hide figures by the walk-box depth rule, pattern-slot cache, no flicker, IX/IY-safe hooks) | RZX IDENTICAL, static + interrupt + cache + front end + init + unit + depth + restore PASS | f22a9452 / 5642e4b4 crashed (ROM 0); 5ab928e9 runs; 5c1081b7: flicker, menu logo + dots (hook used IY), figures seen through rocks (Dean) - fixed in 541e34e2, which crashed at the first figure (code at 0x3D00-0x3DFF; probable DivMMC automap); d601385e runs (Dean) | hardware test (checklist); later-areas RZX |
| Crystal Kingdom Dizzy (128K) | plain only (crystal_kingdom_dizzy.md) | - | - | plain runs | sprites deferred |
| Midnight Resistance (128K) | midres (midnight_resistance.md) | midnight_resistance_sprites.nex e8f0ece9 (altrom + page 26 at slot 5; player green, soldiers white, jeep / tank in their cell colours; pattern-slot cache) | RZX IDENTICAL, unit + interrupt PASS | e8f0ece9 runs on a real Next (Dean, 2026-10-13) | detailed checklist (speed at the jeep / tank, colours); later-levels RZX |
<!-- end generated -->

Platform on hardware: alt ROM ($8C) PASS 2026-09-27; plain 48K and 128K conversion run.

## Open work (toolkit)
0. Release: the latest release zip (v0.1.3, 2026-10-12 morning) predates Commando, the pinned
   sjasmplus, asm2profile and the analysis commands - zip users get "not supported" for Commando.
   Publish v0.1.4 after `python selftest.py --stamp` passes (CLAUDE.md, End of every task). v0.1.0 has no zip.
1. Engine registry: each engine registers identify/auto instead of a dispatch block in
   nexclash.py (selftest now covers every game: docs/records).
2. `identify` reports unknown for Rainbow, Chuckie Egg, Wally and Commando (auto dispatches by
   signature in cmd_auto): add signatures.json / identify entries.
3. Generic builder covers the TID engine only; next: XOR-parity template (generalise
   dizzy1_patch.py), then non-Codemasters engines (PLAYBOOK "unknown").
4. Virtual read is not in the generic template (the tool refuses and hands over).
5. Explorer is random + room novelty (no puzzles): rare paths need a human RZX.
6. analyse/recorder are 48K-only.
7. Later: tail inside the alt ROM; alt image 0 for 128K games that select ROM 0.
8. Not done: run `selftest.py --affected` automatically on each PR (GitHub Action with the
   private references via a secret); today a maintainer runs it before merging.
