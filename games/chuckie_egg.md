# Chuckie Egg (A&F Software, 1983) - engine `chuckie`
Tool-chain canary stage 1 (`selftest.py --canary`; record "canary": 1): rebuilt on every session that touches shared code.

48K. Code: nexclash/chuckie.py, asm/chuckie_hooks.asm, docs/profiles/chuckie_egg.json (after any
.asm edit: `python tools/asm2profile.py chuckie_egg`). Dispatch: nexclash.py cmd_auto, by signature at 39500.
Reference: reference/Chuckie_Egg.z80 (Chuckie_Egg_1983_A__F_Software_a.z80, title screen) +
reference/Chuckie_Egg.rzx (Dean, 2026-10-11).

    python nexclash.py auto Chuckie_Egg.z80 --rzx Chuckie_Egg.rzx --no-record

| Output | MD5 | Status |
|---|---|---|
| Chuckie_Egg.nex (plain, tail 0x5B00) | ec0df71e70fae35836eaed521f300777 | boot sim OK |
| Chuckie_Egg_sprites.nex (altrom, stateless hooks) | bfad6be1e7c8a2c797a6242d7f339e35 | RZX IDENTICAL, unit tests PASS; hardware untested |

## Dean's decisions (2026-10-11)
- Player, hens and duck (caged and free: same plotter) become sprites, in their original colours:
  player/duck yellow, hens cyan, ink only (the originals are OR-drawn: no outline).
- Lifts, eggs, grain, ladders, HUD stay on the ULA (stay unless analysis shows they clash).
- No extra recording for lifts / level 9: lifts are not touched by the patch; the free duck runs
  the same plotter call (41361) as the caged duck, covered by unit tests.

## Patch design
- Alt ROM only (hooks 0x386E-0x39A9, 316 bytes): no RAM page, no state, run with interrupts ON.
  48 4-bit patterns uploaded once at setup (from bank 11). Sprite palette offset 0 index 1 =
  yellow 0xB4, offset 1 index 1 = cyan 0x16. Sprites 0-4 hens, 5 duck, 6 player. Compact tail at
  0x5B00 (printer buffer zero and never touched).
- e_pl at 39500 (replaces F5 C5 D5): caller return address at SP+8 after its pushes picks duck
  (41238/41361) or player; sprite x = L+32, y = 223-H; pattern = frame (>= 32 hidden); replays the
  PUSHes; JP 39503.
- e_hd at 37635 (replaces CALL 37892): caller DE (hen table entry) at SP+16 -> hen index; C
  reloaded from SP+4; A' = (DE-36878)/32 -> pattern 32+A'; x = (L&0xF8)+32, palette offset 1,
  y = 208-H; ends JP 37892. Hen index >= 5 (no table entry): no sprite (guard).
- e_he at 37727: hides the hen's sprite; replays LD IXL,2; JP 37730.
- e_c1..e_c5 at the five screen clears: hide sprites 0-6, replay the instruction, jump on.
- Screen-write removals: 39697 `1A B6 -> 7E 00` (compose background only), 39827 `36 06 -> 00 00`
  (no attr 6), 37646 `77 -> 00`, 37653 `77 -> 00` (no hen pixels), 37707 `36 05 -> 00 00` (no attr 5).
  The plotters keep running, so all game state stays the original's.

## Game facts
- Chuckie_Egg_1983_A__F_Software_a.z80: 48K, title/high-score screen, PC 982 (ROM BEEPER: title
  music), IM2 I=178 (vector 45823 -> 40092), DI at snapshot time, SP 65338. Printer buffer zero and
  never touched (tail 0x5B00). ROM read (beeper) but never 0x386E-0x3CFF.
- Screen readers: only the title scroller 43899 (SLA (HL) 30 x 8) and the hen OR plotter itself.
  No logic reads screen or attributes: collision by coordinates (39838 player vs duck 29512) and
  the level map (40500; map 25000, 32 bytes per char row from the bottom).
- 39500 = player AND duck plotter: A = frame (gfx 36336 + 32A, 16 rows x 2 bytes, top down; frame
  12 = blank), L = x pixel, H = 191 - top line. Builds the frame in 29344 (3 bytes x 16, shifted by
  x&7), background tiles from the map into 29405 (tile gfx 34032 + 8*code), ORs them (39697),
  overwrites the 3x16 screen block (39758, INC E: column 31 wraps), paints attr 6 (39827). Callers:
  player 40382/40763/41606/41861, duck 41235 (blank frame 12 at the old position) + 41358.
- 37532 = hen plotter, one hen per call (37150 cycles 29526 through the 5-entry table 29527, 4 bytes
  each; DE at the call = entry+0..+2): A = 0 -> erase = tile + attribute redraw 37727; else draw:
  A' = A adjusted by y bit 2 (A = 3/4) or x bit 2 (+4), gfx 36878 + 32A', drawn BOTTOM-UP with OR
  from line 191 - H, x byte L/8, 2 bytes per row (37645/37653; L >= 249: nothing drawn), attr 5
  (37707). Both erase and draw are skipped while the hen overlaps the player (37540-37569).
- 38246 refreshes attribute rows from the map constantly (73,638 writes in the RZX): the figures'
  yellow/cyan squares are repainted away by it - with the paints removed the cells keep the map's
  colours.
- Screen clears: 43934, 44700 (6912 bytes), 42403, 42946, 43442 (6144). Interrupts are ON at every
  hook site. The game never uses EXX / EX AF,AF'.
- Dean's RZX (2026-10-11): levels 1-2 with 3 hens, caged duck, game over, high-score entry;
  frames 0-9 and 12-16 for 39500, hen A 1-4, 7, 8. Lifts (level 3+) and the free duck (level 9+)
  not recorded (Dean: not needed).

## Verification (detail: docs/VERIFICATION.md)
RZX 8,626 frames: 7,854 player/duck plots, 878 hen draws, 881 hen erases, 15 clears, 549,345
sprite pixels - IDENTICAL (all registers incl. AF', all memory outside the screen and the
write-first player buffer). Unit tests: player/duck 1,560, hens 1,764, hen guard 1,008, hen erase
12, clears 3, negative control detected 5/5 (1 n/a: blank duck frame 12); wrap edges classified
(player/duck x > 240: 360, hens x = 248: 252).

## Known visual differences (by design)
- A hen and the player both visible where the original skips the hen (overlap).
- No ghost hen where the original skipped an erase.
- Figures in front of everything on the ULA.

## Open
- Lifts (level 3+) and the free duck (level 9+) never recorded; if hardware shows a problem
  there, a Fuse RZX of it settles it.
- Hook timing not measured (stateless, short; interrupts stay on).
- `nexclash.py identify` says unknown (auto dispatches by signature).

## Hardware checklist
1. Title screen, key selection, scroller and sound as before; no sprites on the title/high-score
   screens.
2. Player yellow, hens cyan, caged duck yellow: animate, move in 4-pixel steps (hens) / pixel steps
   (player); ladders, platforms, eggs and grain keep their own colours under and around them (no
   yellow/cyan squares).
3. Hen eating grain, hen on ladders, player climbing, jumping, falling, dying: no stale sprites.
4. Level change, game over, high-score entry: all sprites gone on the cleared screen.
5. Lifts (level 3+): lifts drawn as before, player standing on a lift fully visible.
6. Faults: Fuse "Record from snapshot" on Chuckie_Egg.z80, autosave off, send the RZX.
