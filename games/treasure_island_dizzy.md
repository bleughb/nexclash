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
