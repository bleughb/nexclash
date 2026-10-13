# Smash TV (Probe / Ocean 1991, 48K) - engine `smashtv`
Updated 2026-10-13. Engine `smashtv` (nexclash/smashtv.py, asm/smashtv_hooks.asm,
docs/profiles/smash_tv.json; after any .asm edit `python tools/asm2profile.py smash_tv`).
Status: RZX IDENTICAL, front end + static + unit PASS; hardware untested.

Reference (private repo, specnext/reference/smash_tv/): Smash_TV.z80
(3b89344c6d7e6433bf044bef1880a2f1), Smash_TV.rzx (ed4ee1a08ce14101cb7b1246dcdaf040; Dean
2026-10-13, Fuse, autosave ON: 8 autosave snapshots stripped, 4,068 frames: title, arena 1
(snake), arena 2 (mines, grunts), game over, title). Selftest names them smash_tv.z80 / .rzx.

    python nexclash.py auto smash_tv.z80 --rzx smash_tv.rzx --no-record   (~5 min)
    iterate: --quick 1600 (~30 s)

| Output | MD5 | Status |
|---|---|---|
| smash_tv.nex (plain: the BASIC loader as it is, tail 0x5B00) | c72ea298486b14036ac1a87ac89c3f0e | boot sim OK; hardware untested |
| smash_tv_sprites.nex (altrom 0x2100- + page 26 at slot 7, front end) | 6227481f8f2514faa0d9648b6bc972e8 | RZX IDENTICAL; hardware untested |

## Dean's decisions (2026-10-13, from design.png: original | A | B)
- Sprites: ALL figures drawn by the four masked plotters (player, shield, enemies, snake, mines,
  grunts, pickups, prizes, explosions, bullets); a plot stays on the ULA only when the sprite
  table (128) or the pattern cache is full, or at buffer column >= 30 (off screen).
- Look: A (changed from B the same day, after the first build): ink pixels in the cell's own
  attribute ink (+ bright), the 4-px outline the mask clears in the cell's PAPER (+ bright), the
  rest transparent = the original's look without the clash. (B = see-through outline: build
  03979d54, superseded.)
- Cells with attribute 0 (the game leaves the cell's colour: player's gun, shield ring): ink white,
  outline blue (the arena's paper).
- Keep the trainer prompt "DO YOU WANT TO BE INVULNERABLE ?" (front end; Y = POKE 33465,201).

## Snapshot (0b)
- 48K, BASIC LOADER running (PC 0x1666 in ROM, IM 1, EI): the Ramsoft "Trainer by Sanchez"
  wrapper. Line 30 prints the prompt in row 23 (attrs 0x4F) + BEEP; line 40 waits for INKEY$;
  Y/y: POKE 33465,201; Y or N: GO SUB 80 (row 23 cleared: pixels 0, attrs 0) and RANDOMIZE USR
  59776. RAMTOP 24999. 48K BASIC runs on the Next ROM, so the plain .nex is the loader as it is.
- The RZX's own start snapshot (SZX, PC 0x0038) is ~12 s later than the .z80 at the same prompt
  loop (27 bytes differ: sysvars, BASIC stack). N was pressed (33465 = 192 at the entry, frame 216).
- Game entry 59776 (0xE980): DI, LD SP,23692, builds the frame tables 0x5C00 (6 x 8x8) and 0x5B00
  (111 x 24x24), then `LD A,(14446): CP 255: JP Z,28977` = a 48K ROM check (0x386E is 0xFF only in
  the 48K ROM). The entry code area 0xE980-0xEBFF becomes the attribute back buffer.
- ROM data reads after the entry (full RZX): 0x0000-0x00FF, 0x2000-0x2011 (clipped plot rows),
  0x386E, the font 0x3D00-0x3EA7 (text), and the beeper noise routine 47068 walking 0x0410-0x3E55
  (noise values only). The delay 51175 (5 x LDIR 0 -> 0, BC = 0) copies all 64K onto itself.
- Write-first after the entry (RZX): 0x5B00-0x5BDD (tail site), 0x5C6C-0x5D6C (front end site),
  0x5D8D-0x5DAD, 0x5EC8-0x5F00, the whole screen.

## Engine (2-3): back-buffer composer, full redraw every game frame, interrupts OFF in play
- Title/menus: IM 2 (I = 0xEA, ISR 0xECEC) or IM 1, EI only after 53868 (IM 2 re-init) and in
  the menu wait loop 52773; play runs DI: IFF = 0 at every plot / restore / blit / 53868 call in
  the RZX (7,013 plots, 669 restores, 683 blits).
- Game frame = one blit every 2.5-4 TV frames (~250K T; no frame sync: speed = CPU time).
- Back buffer: pixels 0xEC00-0xFFFF (160 lines x 32 bytes, linear; line = B - 48), attrs
  0xE980-0xEBFF (20 rows x 32). Row tables 0xC800+2B (pixels) and 0xCA00+2B (attr row) point at
  ROM 0x2000 for B < 48 and B >= 208 (clipping by ignored ROM writes). Screen: buffer columns 2-29
  -> screen columns 2-29, buffer line 0 -> screen line 24 (x = 8C, y = B - 24).
- 59506 restore (code IN slot 7, 0xE872-0xE8FB): every game frame regenerates the arena grid
  (PUSH: 10 solid rows + 150 rows of 0x80,0x00 via row table 29316; attrs: 560 bytes LDI from
  29676). 15 blits at the game start have no restore (the player's entry trail).
- 53293 blit: SP row table 52288, unrolled LDI (28 pixel bytes x 8 lines + 28 attrs per char
  row), 20 rows; loop end JP PE,53310 at 53861; the only gameplay screen writer.
- Text messages ("GO FOR IT", "GAME OVER"): 47993/48027 into the buffer AFTER the figures.
- Readers of the buffers: plotters, blit, the beeper noise routine 47068 (60 bytes as noise; no
  state). No virtual read needed.

### Figure plotters (byte-column aligned: C = column, B = line, L = frame)
mask(g) = table 0x7E00[g] (clears every NIBBLE holding ink: a 4-px outline in the cell's paper);
mirror = 0x7D00 bit reverse + reversed columns (exactly the hardware X-mirror).
| Entry | Kind | Graphic | RZX plots |
|---|---|---|---|
| 29858 / 29974 | 24x24 masked / mirrored | word 0x5B00+2L -> 72 bytes + 9 attrs (0 = leave the cell) | 3,683 / 3,091 |
| 29704 / 29777 | 8x8 masked / mirrored | word 0x5C00+2L -> 8 bytes + 1 attr | 227 / 12 |
| 30108 / 30191 | 24x24 UNMASKED (LDI) / mirrored | as 29858 | 0: not hooked, stays on the ULA |
- Each starts `LD (op),SP` (op = its final LD SP,nn operand), uses SP for its row table, ends
  `LD SP,nn / RET`. Final registers: 24x24 do not depend on the buffer bytes read; 8x8 AF' does
  (last row's AND/OR result).
- Attr painting: 3 rows from the attr row of line B, not clipped per row: B in 192-207 writes
  attribute bytes into pixel lines 0-15 of the buffer (a glitch of the original; the converted
  plots draw it into the scratch only, so it is gone).
- Frames 45 / 50 have colour-cycled attr bytes (50629 / 50633 every frame): colours are read at
  plot time and are part of the cache key.

### Figures in the RZX (L)
player 0-9, dying 35/36; shield ring 54-56; snake rings 11 (~3,500 plots); pickups 16 19;
prizes 21 22; mines 37-40; 58; explosions 29-34, 83, 99-101, 105, 106; grunts 102-104; player
bullets = 8x8 frame 0. Not reached: frames 12-15, 17-18, 20, 23-28, 41-53, 57, 59-98, 107-110
(bosses, later arenas). Max 25 plots / 100 sprites in one game frame; <= 13 distinct images per
commit, <= 18 with those still on show.

## Patch (phase B)
Hooks in alt ROM image 1 at 0x2100-0x2837 (+ register block); 0x2000-0x20FF (clipped plot rows
read it), 0x386E (the 48K check) and 0x3800-0x3FFF stay ROM. State: Next page 26 mapped at MMU
slot 7 (0xE000) while a hook runs: vars 0xE000, cache 0xE040 (32 x 16), sprite table 0xE240
(128 x 5), ATTR4 0xE500 (attr -> colour*4), PT 0xE600 (colour*4 + pixel pair -> pattern byte),
a copy of the restore routine at 0xE872-0xE8FB, hook stack 0xE940-0xE97F, and the SCRATCH copy of
the back buffer at 0xE980-0xFFFF. Interrupts stay off (the game's DI).
- Sites (original bytes checked): 29704 / 29777 / 29858 / 29974 (plotter entry `LD (op),SP` ->
  JP), 59506 (restore entry), 53861 (blit loop end JP PE -> JP), 53868 (XOR A / LD (24284),A).
- Plot hook (28 MHz): decide (column < 30; visible B 25-207 / 41-207 for 8x8, else nothing to
  show; N + 4 (1) <= 128; cache lookup by key graphic pointer + size + attr bytes, else upload the
  image into a free group: 4 patterns TL TR BL BR = 2 x 256-byte slots), append the sprites (plot
  order = sprite order: later figures on top; mirrored: TL at +8, TR at -8, X-mirror bit), then
  CALL a trampoline (the displaced `LD (op),SP` + JP into the body) with slot 7 = page 26 at
  3.5 MHz: the game's own plotter draws into the scratch, so every register, flag and
  self-modified operand is the original's. After it: `LD (op),SP` again (the operand = the game's
  SP), the two game-stack bytes under SP that the CALL used are put back, slot 7 = page 1, RET.
- ULA path (column >= 30, table or cache full): the body runs twice, real buffer (3.5 MHz) then
  scratch (registers restored first), so the scratch stays the original buffer.
- Restore hook: real buffer (3.5 MHz), then the scratch (28 MHz; executes the copy in page 26);
  its operand 59641 is written back on the game's page.
- Blit loop end: `JP PE,53310` first; at the fall-through the commit: sprite attributes 0..N-1
  ($34-$39), hide N..PREV-1, cache flags aged (bit 0 used since the commit -> bit 1 on show;
  groups with flags 0 are free: no tearing between pattern and attribute).
- 53868 (game start, after game over, before every EI): all 128 sprites hidden, cache flags 0.
- Sprites: 16x16 4-bit, palette 0 offset 0: index 0 transparent, 1 black, 2-8 normal, 9-15 bright
  (Next default ULA levels); colour = the cell's ink (bright: 8 + ink, bright black 1), attr 0 ->
  8 (white); outline = the cell's paper the same way (attr 0 -> 2, blue): per pixel pair
  PT[paper][NOT mask] XOR PT[ink XOR paper][ink] (PAPER4 table 0xE700, cell colours V_CC / V_PC
  0xE800); clip window = play area x 16-239, y 24-183.
- Front end (0x5D00-0x5D68, write-first game RAM): DI; waits for Y or N without SYMBOL SHIFT
  (Y: POKE 33465,201); clears row 23; sets every register to the loader's state at USR 59776
  (BC 59776, DE 24291, HL 11563, IX 978, IY 23610, SP 24976, I 63, AF 0x8054, AF' 0x0044, BC'
  5665, DE' 13979, HL' 10072; R and IFF aside: 59776 is DI) and JP 59776. Start snapshot = the
  loader run in the simulator with N to its USR (frame 14) + the front end + the loader's prompt
  row (pixels and attrs 0x4F).
- Speed: game bodies (plotters, both restores' real run) at 3.5 MHz like the original, hook work at
  28 MHz. Per game frame (simulated, 28 MHz parts / 8): plots 57,778 -> 65,555 T, restore 42,071
  -> 47,493 T, commit +1,277 T, plots 57,778 -> 66,920: +15,840 T = ~6.3% of a ~250K T game frame (the game is that much
  slower in play; mostly the per-plot decide/lookup ~750 T and the scratch restore ~5.4K T).

## Verification (2026-10-13; detail docs/VERIFICATION.md)
RZX (4,085 frames played, autosave stripped): 7,010 converted plots (24x24 3,680 + mirrored 3,091,
8x8 227 + mirrored 12), 3 invisible (converted, no sprites), 0 on the ULA, 669 double restores,
683 commits (max 25 figures / 100 sprites), 8 hide-all, 2,056,946 sprite pixels (ink + outline) -
IDENTICAL.
Unit: 840 position cases, 48 sprite-table cases, 12 cache-full cases (ULA path), negative
controls (ink colours shifted; outline transparent; guard column 31) 36/36. Front end N / Y / SYM+Y PASS. Static PASS.

## Known differences
- Sprites are in front of the text messages ("GO FOR IT", "GAME OVER"); the original draws the
  text over the figures.
- The player's entry trail (15 game frames without a restore at the start of a game) is gone:
  sprites show only the current frame's figures.
- The original's attr-painter glitch (B 192-207: attribute bytes in the top 16 buffer lines) is gone.
- Converted figures appear at the end of the blit (the original's appear as the blit passes).
- ~6% slower in play (hook cost; no frame sync in the game).
- Beeper noise (47068 reads buffer and ROM bytes as noise) may sound slightly different.
- Unmasked plotters 30108 / 30191 (never called in the RZX) stay on the ULA.

## Open
- Hardware test (checklist below). Ask CSpect first (start-up and memory layout are new).
- Recording: only 81 s (2 arenas + game over, 45 of 111 frames). Need a longer one (autosave OFF),
  ideally with Y (invulnerable) to reach later arenas and the bosses (frames 23-28, 41-98: big
  multi-part figures; check the 128-sprite budget and the cache (32 groups) there).
- Interrupts: the hooks assume IFF = 0 (true at every call in the RZX); slot 7 holds the IM 2
  handler (0xECEC), so a plot with interrupts on would crash. Not seen; hardware/longer RZX to confirm.
- Speed: if the ~6% shows, compensate at the commit with a calibrated delay against the restore
  run at 28 MHz (not done).

## Hardware checklist
1. Boots to the prompt "DO YOU WANT TO BE INVULNERABLE ?" (bottom row); N starts normally, Y
   gives invulnerability; the menu / key definition / title as the plain build.
2. Arena: player, shield ring, snake rings, mines, grunts, pickups, explosions, bullets are
   sprites in their own colours with their paper-coloured outline (as the original); no colour
   clash on the grid; player's gun white.
3. Mirrored figures (facing left) correct; figures at the arena edges / doors clipped to the play area.
4. Busy scenes (snake + many enemies): no missing or flickering figures, no stale sprites.
5. Speed close to the plain build (expect ~6% slower in play).
6. "GO FOR IT" / "GAME OVER" text: figures in front (expected).
7. Game over -> title: all sprites gone; a second game works.
8. Faults: Fuse "Record from snapshot" on Smash_TV.z80, autosave OFF, send the RZX.
