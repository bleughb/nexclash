# Status (2026-10-12)

One row per game. Details, decisions and checklists: games/<game>.md (named like the game's
folder in the private repo; shared TID engine facts: games/tid_engine.md). MD5s: docs/VERIFICATION.md.

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

Platform on hardware: alt ROM ($8C) PASS 2026-09-27; plain 48K and 128K conversion run.

## Open work (toolkit)
1. selftest: add Dizzy 6 (Dizzy6.z80 + try1.rzx, now in specnext/reference) - BRIEFING C2 #8.
2. Engine registry: each engine registers identify/auto instead of a dispatch block in
   nexclash.py (do it once selftest covers every game).
3. `identify` reports unknown for Rainbow, Chuckie Egg, Wally and Commando (auto dispatches by
   signature in cmd_auto): add signatures.json / identify entries.
4. Generic builder covers the TID engine only; next: XOR-parity template (generalise
   dizzy1_patch.py), then non-Codemasters engines (PLAYBOOK "unknown").
5. Virtual read is not in the generic template (the tool refuses and hands over).
6. Explorer is random + room novelty (no puzzles): rare paths need a human RZX.
7. analyse/recorder are 48K-only.
8. Later: tail inside the alt ROM; alt image 0 for 128K games that select ROM 0.
