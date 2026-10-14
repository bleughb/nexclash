# Target Renegade (Imagine Software, 1988; 128K) - engine `renegade`

Status: PHASE A (analysis done, design question sent to Dean 2026-10-14). No engine build yet.
Code so far: nexclash/renegade.py (plot model, colour-sheet capture, previews; CLI
`python -m nexclash.renegade sheet RZX [--preview F,F]` / `colours PAINTED.png`).
Reference (specnext/reference/target_renegade/):
- Renegade_II_Target_Renegade_1988_Imagine_Software_128K.z80 (md5 1895877d638a4a5f37a9402bed18f59a):
  128K BASIC loader at its last PAUSE 0 (PC 7997, 7FFD 0x10, IM 1). Line 1 loads six blocks (POKE
  23388 pages banks 1/3/4/6/7/0), POKE 40608/9 -> JP 23340, PAUSE 0 (loading screen), USR 40576.
- Renegade_II_..._128K.rzx (md5 464d4eeaa005e2d16fb1d65737325285): Fuse 1.5.5, 7010 frames, 9
  autosaves (stripped). NOT recorded from the .z80: its own snapshot starts at the game menu
  (PC 49087). Same code bytes as the loader snapshot's (plotters, copy, entry checked). Level 1 only
  (car park: players, bikers, a motorbike, a pipe on the floor).
- target_renegade_entry.z80: the loader run in the toolkit (SPACE for PAUSE 0) to PC 23340, after
  the entry code (relocation + paging): 7FFD = 4, ROM 0, IM 1, DI, SP 24553.
- target_renegade_plain_test.nex (md5 23647948ff22fc10e26b589cf1b83193): plain build from the entry
  state, tail 0x6400 (write-first in the RZX and a free run). Boot simulated: registers, RAM (tail
  aside), 7FFD = 4 / 1FFD = 0, MMU slots 6/7 = bank 4. Skips the loading screen (starts at the menu).
- Sheets (phase A): target_renegade_PAINTING_SPRITES.png + _layout.json,
  target_renegade_REFERENCE_ALL_SPRITES.png, target_renegade_PREVIEW.png.

## Facts
- Start-up: 40576 DI, LDIR 0xC708 -> 0x5B08 (2296), fill 0xFB00-0xFFFF, OUT (0x1FFD),4, JP 23340.
  On a 128K 0x1FFD decodes as 7FFD (A15 = 0, A1 = 0): bank 4, ROM 0. A copy of this code sits in
  bank 3 at 54912 (not run in the RZX). The game's other paging writes use 0x7FFD.
- 128K BASIC pages ROM 0 between PAUSE 0 and the USR (23310, the 0x5B00 swap routine) - as Commando:
  the build starts from the toolkit-run entry state, never from the loader.
- In play: 7FFD = 0 (ROM 0, bank 0 at C000), banks 3/0x10-0x14 paged briefly (music in bank 3 via
  24040, level data). IM 2, I = 0x9F (vector 0x9FFF -> 0xBFBF: JP 49090 / EI / RET); interrupts off
  except around the frame HALT (64134 EI ... 64147 DI). isr: handler uses 2 stack bytes.
- ROM reads: only 0x3500-0x3508 (ROM 0), once (frame 5407), by the bank-3 sound code at 49204
  (a sound-effect pointer that points into the ROM). On the Next ROM 0 is the Next's own (different
  bytes): a sound difference at most. Alt-ROM hooks must live in the image the game selects
  (ROM 0 = alt image 0, not filled by the current stub) and keep 0x3500-0x3508.
- Main loop 55168: logic, 59531 draw all figures, 55240 delay padding (by unused undo space),
  HALT, 24040 music, 62565 copy buffer -> screen, 56332 restore buffer from the undo stack, JP.
- Back buffer 0xC000-0xCFFF (bank 0): screen char rows 1-16 in screen layout (two 2K "thirds");
  line y (0-127) -> word at 0xD000 + 2y (low | column). Copy 62565: stack blit, 16 bytes per
  slice, beeper OUT 254 toggles (counter table 54609). Readers of the buffer: plotters (masking,
  undo save), copy only - NO pixel tests. Screen readers: 58862 (HUD energy bar AND) and the clear
  62821 - none in the play area.
- Scenery: tile renderer 58200 (17 x 32 cells, attr per tile from 0x6800) to screen and buffer;
  attributes in the play area are static per screen (flip screens).
- Plotters 55276 (as stored) / 55722 (mirrored through table 0xD100 = bit reverse, except entry 58
  -> 76: a sprite mirrored in hardware differs from the game for a byte 58 - build such parts
  pre-mirrored). HL -> graphic word of a part record [y off][x off][graphic]; D = y, E = x.
  y = (D - yoff) & 127 (doubled as table index), x = E - xoff (mirrored: E + xoff + 1 - W); byte
  columns, clipped to 0-31, lines >= 128 cut. Graphic: W, R, then W*R (mask, graphic) pairs, rows
  serpentine (odd rows right to left). Undo stack: data from 65344 down ((63226)), record ends from
  65408 down ((63228)). Model checked against the game over the whole RZX: 24669 plots, every
  written address and byte equal (renegade.plot_params / plot_writes).
- Callers: 59568 (display list 0xD200, sorted, entries = object record low bytes; chains via
  record +5) and 59441 (extras of 59404, flag 63407 - never set in the RZX). Object records at
  0xD20A + 22 i: slot 0/1 players, 2-5 enemies, 6+ objects (the pipe at 0xD28E). Frame table 0x6900:
  word per frame -> parts; bit 7 of a part's y off marks a frame's first part. Level 1 memory holds
  141 frames / 175 graphics; the RZX drew 147 (the sheet adds the other frames "from the code").
- Free RAM (RZX + 400-frame free run): untouched 0x5B92-0x5D67, 0x5F7F-0x63FF; write-first
  0x6400-0x9EFF (tail / front end), 0xBF30-0xBF3F.

## Design proposal (phase A question, waiting for Dean)
- Sprites: every figure the plotter draws (players, enemies, bikes, the floor weapon, later
  levels' figures). ULA: scenery, HUD (scores, energy, lives faces, timer), text.
- Depth: the game's own (display list order: later plotted = in front) -> sprite order.
- Screen: swap the CALLs at 55267/55270 (restore before copy: the copy shows scenery only, memory
  identical) or restore onto the screen after the copy; sprites from a plot-entry log at the commit.
- Colours: painted sheet; unpainted pixels keep the original look (black ink, body = paper of the
  cell under it).
- Front end: keep the loading screen + "press a key" (as the loader's PAUSE 0).

## Open
- Dean's answers to the phase A question; recordings of levels 2-5.
- Hardware: does the plain test run (ROM 0 = the Next's, 1FFD/7FFD decode of the OUT avoided by
  starting after it)?
- Menus / pause / messages over the play area: not yet known.
