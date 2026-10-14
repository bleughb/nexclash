# Target Renegade (Imagine Software, 1988; 128K) - engine `renegade`

Status: PHASE C (hardware) - sprite build e0b246e3 verified in the toolkit (RZX IDENTICAL, unit PASS),
waiting for Dean's hardware test.
Code: nexclash/renegade.py, asm/renegade_hooks.asm, docs/profiles/target_renegade.json (after an .asm
edit: `python tools/asm2profile.py target_renegade`). Dispatch: nexclash.py cmd_auto (is_renegade:
plotter bytes at 55276 + the entry code at 40576). Record: docs/records/target_renegade.json.

    python nexclash.py auto target_renegade.z80 --rzx target_renegade.rzx --no-record   (~12 min)
    python -m nexclash.renegade sheet RZX [-o PREFIX] [--preview F,F]   colour sheets (+ preview)
    python nexclash.py recolour target_renegade_sprites.nex PAINTED.png   repaint, no rebuild

| Output | MD5 | Status |
|---|---|---|
| target_renegade.nex (plain, loading screen + front end, tail 0x6400) | a0be8dc03a1be8c6d67dc3e0229abc35 | boot sim OK |
| target_renegade_sprites.nex | e0b246e35d028c34170e1d1c52f00f5f | RZX IDENTICAL, unit PASS; hardware untested |

Reference (specnext/reference/target_renegade/):
- Renegade_II_Target_Renegade_1988_Imagine_Software_128K.z80 (md5 1895877d638a4a5f37a9402bed18f59a):
  128K BASIC loader at its last PAUSE 0 (PC 7997, 7FFD 0x10, IM 1). Line 1 loads six blocks (POKE
  23388 pages banks 1/3/4/6/7/0), POKE 40608/9 -> JP 23340, PAUSE 0 (loading screen), USR 40576.
- Renegade_II_..._128K.rzx (md5 464d4eeaa005e2d16fb1d65737325285): Fuse 1.5.5, 7010 frames, 9
  autosaves (stripped). NOT recorded from the .z80: its own snapshot starts at the game menu
  (PC 49087). Same code bytes as the loader snapshot's (verify checks every site at every event).
  Level 1 only (car park: players, bikers, a motorbike, a pipe on the floor).
- target_renegade.nex / target_renegade_sprites.nex (the builds above), the colour sheets
  target_renegade_PAINTING_SPRITES.png + _layout.json, target_renegade_REFERENCE_ALL_SPRITES.png,
  target_renegade_PREVIEW.png (original | ULA | ULA + sprites).
- Phase A only: target_renegade_entry.z80, target_renegade_plain_test.nex (23647948; no front end).

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

## Dean's decisions (2026-10-14)
- 1: every figure the plotter draws becomes sprites. 2: the game's own drawing order. 3: all
  characters grey - colour 7 (white, not bright = "dark white"): read as the figure's body (opaque
  non-ink pixels) in palette index 7, ink stays black (8), so the outline drawing still shows; the
  colour sheet / recolour changes any pixel. 4: keep the loading screen. 5 (later-level
  recordings), 6 (windows over the play area), 7 (test cheat): another time.

## Build (as verified)
- Start: `auto` runs the loader in the toolkit (SPACE for PAUSE 0) to 23340, after the entry code
  (relocation + OUT (0x1FFD),4: 7FFD = 4, ROM 0), so neither 128K BASIC (ROM 0 swaps) nor the 1FFD
  decode question reaches the Next. Front end 0x6480 (write-first RAM): the loading screen is up;
  wait for no key, then a key; POP AF (0x0440), LD SP,24553, JP 23340 - every register as the loader.
- Hooks (alt ROM images 0 AND 1: the game selects ROM 0 in play, ROM 1 at the clear; code 0x2200-,
  NIB tables 0x2000-0x21FF; 0x3500-0x3508 of ROM 0 untouched). The setup (stub, 0xD000) fills image 0:
  1FFD = 0, 7FFD = 0, write mode, ROM 0 copied, hook bytes over it; the stub fills image 1 (ROM 3).
  Page H = Next page 26 at slot 2 while a hook runs (vars, log, cache, hook stack 0x5F00).
  | Site | Original | Hook |
  |---|---|---|
  | 55276 / 55722 | PUSH HL / PUSH DE / DEC HL | log the part (record, D, E, mirrored) in H, then the plotter as the original (buffer + undo stack exact) |
  | 59531 | LD HL,65344 | log reset; if the scenery changed (V_DIRTY): buffer -> screen rows 1-16 (the buffer is clean here) |
  | 62565 | LD HL,(62711) | commit: log -> 4-bit sprites (pattern cache 48 entries / 128 patterns), attributes; then the game's copy with slot 2 = page 27 (Q) |
  | 62751 | LD SP,(63222) | the copy's exit: slot 2 = the screen again |
  | 58200 / 56332 | scenery redraw / buffer restore | log reset (58200: scenery dirty) |
  | 62771 | PUSH HL/DE/BC | character print: scenery dirty (text over the play area is gone at the next draw-all, as the copy did) |
  | 62821 | LD HL,23295 | screen clear: hide all, cache empty, scenery dirty |
- Sprites: per part TW x TH 16x16 tiles (W <= 6 bytes, R <= 64 lines), pre-mirrored through the game's
  table 0xD100 (exact for byte 58), emitted in plot order (higher number on top = the game's depth),
  clip window = screen rows 1-16. Colours (Dean): ink black (8), body grey (7: white, not bright),
  mask-set pixels transparent; the map (docs/profiles/target_renegade_colours.json, once painted)
  recolours any pixel per graphics byte (check byte mask ^ rotl(graphic); transparent / outline).
- Guard (no sprite, figure not shown): W 0 or > 6, R 0 or > 64, record or graphic below 0x6000,
  log full (64 parts), no free pattern (V_DROP). None happens in the RZX (max 33 sprites).
- Speed: +145K simulator T per game frame in the 28 MHz hooks (~18K at 3.5 MHz) + 3.8K T in the plot
  hooks; the game HALTs ~35K T per 3-frame game frame - expect no slowdown, to confirm on hardware.

## Hardware checklist (e0b246e3)
1. Loads and shows the loading screen; a key starts the game menu (plain build too). A crash at the
   start: alt ROM image 0 (BRIEFING C2 #26) - report it.
2. Menu, 1 player, level 1: figures grey with black outlines, in front of / behind each other as in
   the original; no black figure ghosts on the scenery; scenery and HUD unchanged.
3. Figures walking off the left / right edge, the motorbike, knocked-down enemies, the floor weapon.
4. Speed: the game as fast as the plain build (no slowdown with many figures); music and beeper OK.
5. Game over / level end / time up: no sprites left over on non-play screens.

## Open
- Hardware test of e0b246e3 (alt ROM image 0, OUT (0x1FFD) never reached, speed).
- Recordings of levels 2-5 (Dean: later) - their graphics, any other plotter callers, the sheet's
  later levels; the guard / cache limits cover them only by unit test.
- Windows over the play area (pause, messages) and a test cheat: Dean, later.
- ROM 0 bytes 0x3500-0x3508 (sound data) come from the Next's ROM 0 on hardware, Sinclair's in the RZX.
- Painted colours: none yet (sheet sent; `recolour` takes the painted PNG).
