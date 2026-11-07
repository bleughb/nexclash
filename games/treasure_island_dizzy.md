# Treasure Island Dizzy (Dizzy 2, Codemasters) - TID engine, dedicated builder

48K. Engine facts shared with Fantasy World / Magicland: games/tid_engine.md.
Builder: nexclash/dizzy_patch.py (dedicated: bubble virtual read; printer only).
Profile: docs/profiles/tid_treasure_island_dizzy.json; signatures.json (`tid_engine`).
Reference files (private repo, specnext/reference/treasure_island_dizzy/):
- dizzy2_game.z80 (in game, md5 7578947f) - selftest input treasure_island_dizzy.z80;
- dizzy2.z80 (title screen, md5 9443f0cc) - optional selftest input treasure_island_title.z80;
- recordings dizzy2rzx, dizzy2newrzx.

| Output | MD5 | Status |
|---|---|---|
| treasure_island_dizzy_sprites.nex (in game, printer) | 8b4d0847d68fce3215bd43a0e116e682 | verified; hardware untested |
| treasure_island_dizzy.nex (in game, plain) | 4dae1a3a15b2158642a5d5b82de92ef7 | |
| treasure_island_title_sprites.nex (title) | 85e054fe4bce8e4b3a8e336aac432f58 | verified |
| treasure_island_title.nex (title, plain) | 70890aba7d821fba8a41e63636eb58be | plain build runs on hardware |

Verified: dizzy2 RZX + 29 underwater checkpoints - 6,338 plots, 6,326 erases, 25,299 ISR, 18 wipes,
7,436 bubble tests (340 Dizzy-dependent): all identical (docs/VERIFICATION.md).

## Facts (addresses; engine routines described in tid_engine.md)
- Plotter 39774, eraser 40087; plot site CALL at 61578; undo buffer 40149; frame table 40249.
- Room wipe 44931; no box routine; ISR hide call 61362; pixel test 62333.
- Game logic READS the player's pixels: underwater bubbles at 63000 -> the patch gives them a
  virtual read (screen as if Dizzy were still drawn).
- Printer buffer free.
- Title-screen ISR 63328 plays beeper music (timing-critical: never hooked); it writes 63340
  (self-modifying - keep out of patch sites).

## Open
- The auto-recorder gets no response to input on the in-game snapshot (start/controls not found):
  needs --start/--keys or a user RZX.
- `--poke` cheat option (immunity 29289,201) not built.

## Hardware checklist
1. Title music unchanged (not hooked); game starts.
2. Dizzy is sprites: animates, faces both ways, no clash, no leftovers when he moves or the room
   changes.
3. Underwater: bubbles behave as in the original (they test Dizzy's pixels).
4. Inventory / dialogue screens: Dizzy hidden or drawn as the original does.
5. Faults: Fuse "Record from snapshot" on dizzy2_game.z80, autosave off, send the RZX (+ where).

## Rework (opt-in) v128: the 128K release (engine `tid128`; Jon Attree, 2026-11-05)
Dean's builds (4dae1a3a / 8b4d0847) are untouched and stay his record's; `selftest --game treasure_island_dizzy`
rebuilds them and this rework = recorded.
- Why: the 128K file (TOSEC `Dizzy 2 - Treasure Island Dizzy (1989)(Code Masters)(128K).z80`, db6ccbeb) plays AY
  music from bank 6 (CALL 0x7202 pages it in). Every patch site is byte-identical to the 48K game's (bank 0 holds
  0xC000-0xFFFF in play; the title pages bank 6 there).
- `nexclash/tid128.py` (Dean's dizzy_patch read, not copied): 128K detector / apply; trampolines kept at
  0x5B00-0x5B50 (128K ROM 0's paging routines there: the game never touches them, the verifier fails any access),
  0x5B00-0x5BFF put back after NEXLOAD by a wrapper round Dean's set-up; whole alt ROM image (ROM 1 as the ROM path
  check models it + the register block at 0x386E); a 128K copy of nexclash/verify.py that also checks the bubble
  test 0xF618 and ends the ISR event where the hook hands over to 0x7202; Dean's two hook-page entries (plot, bubble)
  through a wrapper that latches the incoming speed (0x5B60 / 0x5B61), runs his hook at 28 MHz and restores it.
- Keys: ENTER starts at the title, Z / X walk, SPACE jumps.
- Results (2026-11-05): plain 0515a0ae, sprites b3321d93, boot OK; walk1-3 (12,035 / 12,000 / 12,011 frames) +
  water4 (1,103 frames, walk-in-water POKE, the sea bed) IDENTICAL: 6,927 plots pixel-perfect, 189 bubble tests,
  111 wipes, every hook; 3 negatives detected; clock matrix 5 sites x 4 clocks PASS, forced 3.5 MHz exit detected;
  ROM paths pass; tail never read before written. JNext: pace ORIGINAL (probe 0x61A8, 10 trials a scene: +0.00 %
  everywhere; 1 busy trial lost one interrupt in the game's own DI windows), flicker clean, soak 15 min clean.
  Cheats: Immunity kept; Walk in water (resets the game), Walk through walls (no effect seen), Cheat mode, Immunity
  (alt) (text here) dropped. Loading screen: the tape's (bank 13 stub).
- Enhanced: EASY. Treasure Island Dizzy.256 (Spec256-256-all38) matches all 2,262 bytes of Dizzy's 39 frames; 9
  palette indices on his ink (orange rim, pink face, yellow gloves, blue boots); a 4-bit set fits. Only Dizzy is a
  sprite: the scenery stays 2-colour. Mock-up: pilot runs/dean_treasure_island_dizzy/out/tid_enhanced_mockup.png.
- Seen: Dizzy shows light grey (Dean's palette entry), the original's cell bright white.
- Hardware: none.

## Lessons
- [deferred Open: reconsider when another dedicated TID-family 128K rework needs it: fold verify.py's 128K paths
  into the shared verifier] nexclash/verify.py is 48K-only (list memory, list(mm) snapshots); tid128 carries a copy.
- [local: a hook-speed latch belongs in RAM: SkoolKit's simulator drops writes below 0x4000, the latch in the
  slot-0 hook page read back 0 (the clock matrix caught it)]

## Technique use
- patch.restore-speed: used (the wrapper latch / restore, as hlib_speed, around Dean's hooks)
- verify.update-locked-pace: helped (probe 0x61A8, the game loop)

## Friction
- reuse: [tool nextboot.rom_paths] the ROM path and tail checks; the boot check follows loderunner_v2's
- retries: [local: the TID verifier on 128K memory (classify needs a list), the negatives' dict, the latch place]
- environment: [none: headless JNext with HOME in the run folder, the read-only card]
- hand-rolled: [local: bot recorder on SkoolKit's C simulator; pace trials from Cobra's script]
- scratch: [none: scripts stay in the pilot run folder runs/dean_treasure_island_dizzy/work]
