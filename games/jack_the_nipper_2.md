# Jack the Nipper II - In Coconut Capers (Gremlin Graphics, 1987) - stage 0 done; engine not yet written

## Next session
Stage: 2 (build)             State: design decided 2026-11-23 (the owner: the same answers as Jack the Nipper)
Inputs: TOSEC `Jack the Nipper II - In Coconut Capers (1987)(Gremlin Graphics Software)[a].z80` (md5
6f5d708c439f3356a930ea4f176a0c8f: 48K, in game); rzxarchive `j/jacknipper2.rzx` (158,593 frames, 52 min; its own
start snapshot md5 f89e14ab3939e70ecbe94cc1f42b38fe)    Branch: add-jack-the-nipper
Checks: survey (GATE CHECK, below), inspect, scan --writers (no pixel logic)    Pending user answers: none
Start with: the design question (defaults + exceptions below), a preview and a plain .nex from `[a]` (SP 0xFFFA:
prove the tail with rom_paths' tail proof)    Read: PLAYBOOK 2-3, games/jack_the_nipper.md (the design there)
Open: the three unreached CALL sites (a screen redraw and a text printer, not figure plotters)

## Snapshot (0b)
- The plain TOSEC `.z80` (812f365c792c8af30edafcf227843a96) is a BASIC loader (`LOAD ""SCREEN$`, "IBM copy by
  Cysio", PC in ROM PAUSE): not a build input. The `[a]` snapshot is in game: 48K, PC 0xBC79, IM 1 with interrupts
  OFF, I = 0x3F, SP 0xFFFA.
- The recording was made on a 128K machine running the 48K game: 0x7FFD = 0x10 (the 48K ROM, bank 0 at the top,
  paging as a 48K machine), banks 1, 3, 4 and 6 empty, and RAM 97 % equal to `[a]` (the rest is game state). So the
  build targets the 48K game and this recording can verify it.

## Survey (2026-11-22, the whole recording, from the TOSEC loader snapshot's survey: the replay uses the RZX's own start)
- Engine: unknown (no detector, no TID / Dizzy 1 signature): a new engine, feasibility first (PLAYBOOK 3d).
- Rendering: 0xB25F writes 62 % of the pixel bytes (164 bytes a call, 55,675 calls) reading 0xFB00-0xFD7F,
  0xBDC0-0xBDFF and 0xF940-0xFA3F: a copier from a composed buffer. 0x935E / 0x939F draw the status panel's
  numbers; 0x967F (482,000 T a call, 498 calls) redraws whole screens; 0x9B1A (21 callers) prints text.
- Pacing: no interrupt accepted in 158,593 frames: no frame sync (as Jack the Nipper).
- Coverage: GATE CHECK: 0x967F's call from 0xA958 and 0x9B1A's calls from 0x9B62 / 0x9B9C never ran (code near them
  did). 0x967F is a screen redraw and 0x9B1A a text printer, not figure plotters: likely a message or screen the
  recording did not bring up; confirm in stage 1.
- Plain conversion: built from the loader snapshot, so not meaningful; rebuild from `[a]`.

## Stage 1 analysis (2026-11-22, started)
- 0xB25F is the object loop, not a copier: a table at 0x88E2, 11 bytes each, count at 0xBDF2; per object 0x9D91 then
  the draw at 0xB28B: x = (IX+0) (+-6 by (IX+5) bit 0 for some types), y = (IX+1), (IX+8) bit 5 = skip.
- No shadow screen (unlike Jack the Nipper): the draw composites straight onto the screen: screen address from x / y,
  the attribute map at 0xFB00-0xFD7F (32 x 24 cells), background tiles at 0xE900 + 8 x tile (IY), graphics fetched with
  SP as a data pointer (POP blits, SP saved at 0xBDE8), widths patched into the code (self-modifying, 0xB412 / 0xB417
  ...), a path per (IX+2) type bit (0xB5D3, 0xB534, 0xB3B1). A conversion splits the composite: background only to the
  screen, the figure as sprites.
- Correction (2026-11-23): the draw composites into a cell buffer, not onto the screen. Per object: 0xBA56 clears
  0xE900-0xECFF (PUSH 0); 0xBAF9 / 0xBB64 / 0xBA8A set up the object's cells and its colour ((IX+9) into the cell
  colour list at 0xBD68); the blit masks the figure into the buffer (AND mask, OR graphics; column stride 24 / 32 / 40
  bytes, INC IY per pixel row). After the loop, 0xBC62 walks the dirty-cell map 0xFB00-0xFD7F beside the tile map
  0xF800 and writes changed cells to the screen (0xBCC7-0xBCD9 pixels, 0xBCEF attributes).
- Figure format: CALL 0x92A3 returns the graphics in HL ((IX+3/4) when (IX+8) bit 6, else by type); per row the mask
  bytes then the graphics bytes, top row first (mask 1 = background shows). Size by (IX+2), as the dispatch at
  0xB2E9 reads it: bit 0 16x16, bit 1 16x24, bit 2 24x24, bit 3 24x32, bit 4 16x24, none 24x32. x & 7 picks a
  run-time shift (a shift ladder, 0xB484); (IX+5) bit 1 draws it mirrored through the byte-reverse table at 0xE800.
  One SP blit per size x shift x mirror: 16 sites (0xB34B ... 0xB9B3), each right after the CALL.
- Census (whole recording, jtn2_figures.py at the 16 blit sites): 142,528 blits, 100 distinct figures (51 of
  16x16, 32 of 16x24, 9 of 24x24, 8 of 24x32): Jack, natives, monkeys, a lion, a hippo, scorpions, snakes, birds,
  the explorer with a gun, fruit and pick-ups, a few sparkle effects. Every figure fits 2 x 2 16x16 sprites; the
  game mirrors at run time, which a sprite's X-mirror bit does for free.
- No pixel logic (`scan --writers`, frames 0-40,000): screen readers are the panel animation (0x935E: cells of the
  bottom rows with attribute 0x6F, pixels rotated in place) and the panel digits (0x93B4); attribute readers the
  panel test and a colour cycler (0xC0B3); buffer readers the maskers and the room decoder (0xAA00). Collisions
  come from the object table, not pixels.
- Design: the owner, 2026-11-23, "you can go on those": the same answers as Jack the Nipper (every figure a sprite, effects too, outline kept, the game's own colours until a painting); not a colour run yet.
- Cheats (every patch carries them, off by default): the archive's POKEs (Super Collection "¤ Pokes"): Infinite lives 43251 = 0 (0xA8F3 `DEC (HL)`), Infinite ammo 38306 = 0 (0x95A2 `DEC (HL)`), Lives 255 at 34631 (now 8), Immunity 1 34426 = 0 (0x867A `DEC A`), Immunity 2 (ten POKEs from 43203 = 201 on). Original bytes match the `[a]` snapshot; each to be checked in a replay (Immunity 2's `JP NZ` to `CALL NZ` changes look odd: prove them or drop them), and more looked for.
- Plan for the design: as Jack the Nipper (games/jack_the_nipper.md): hook each blit site to place the figure as
  sprites (pattern from HL, mirror bit, x / y from the record) and skip the mask-and-OR, so the buffer holds the
  background only and the cell copier puts back what a figure covered; the figure's colour leaves the cells (sprites
  carry their own). Depth: table order (later objects over earlier), as the composite.

## Stage log
- 2026-11-22: stage 0, ~1.5 h wall (with Jack the Nipper), ~20 tool calls, no user rounds.
- 2026-11-23: stage 1 analysis (draw path, figure census, readers), ~25 tool calls, no user rounds.

## Lessons
- [none: PLAYBOOK 0b already covers loader snapshots; the TOSEC `[a]` copy was the in-game one]

## Technique use
- detect.pacing-structure: used: the survey's no-interrupt finding names the no-frame-sync case for the design

## Friction
- reuse: [none: no code written at intake]
- retries: [none: the first survey run started outside the toolkit folder (module not found); rerun from it]
- environment: [none: no workaround]
- hand-rolled: [local: this game's recording machine] comparing the 128K recording's start with the 48K snapshot
  (paging byte, empty banks, RAM equal) was a hand-written check
- scratch: [local: kept for the build stage] jtn2_figures.py (the figure census at the 16 blit sites; becomes the
  engine's figure table and sheet in stage 2)
