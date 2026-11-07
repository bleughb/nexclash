# Pac-Mania (Grandslam / Teque, 1988; 48K form) - engine `pacmania` (pilot game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: stages 0-3 done unattended; JNext only, never on a Next or in CSpect.
Inputs: the pilot's run folder (pac_mania.z80 md5 8ea4557d, recordings rzx/*.rzx, sheets/, paint/)
Start with: the hardware checklist below; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

## Inputs
Snapshot: archive "Pac-Mania (1988)(Grandslam)(48K-128K).z80", md5 8ea4557d3873f79b0da605d9aa3bab8e. 48K, title menu, PC 0x770F in RAM, IM 2 (I 0xFD -> 0xFEFE -> 0xB46E), BASIC stub only. ZXDB lookup: 502, tried once. It matches Pac-Mania.256 on 100 % of the 2,782 graphics bytes used. The 128K releases (128K).z80 md5 e9cb908b, [a][a] md5 fccddb99 stop in a ROM loader; not used. 128K music (0xB332, 0xC000 at 0x11 in 7FFD) is off in this form.
Keys: 1 start; at the round picture a direction or SPACE picks; then Z left, X right, O up, K down, SPACE jump. 2-4 pick keyboard or joysticks, H the table.
Recordings (no Fuse, scripted, `record --script`, work/gen1.py):
- pm_first: random keys, no cheat. pm_idle: no moves, no cheat: all lives lost, game over, title.
- pm_lives, pm_l4, pm_l5: random keys, 0x8945 NOP (the .pok's infinite lives).
- pm_rounds: 0x8945 NOP, 0x9601 RET (.pok's immunity), 0x8BD9 LD HL,1 (test cheat: one dot ends the round), in the RZX's snapshot: every round, every interlude, the ending, 2.5 times round.

## Rendering model
Back buffer + undo. 0xA8FA: save under each figure (A9CA, 0x5CCB up), sort by y (A93A; pointers 0xA982), plot (AE73). 0xB090: blit the window, columns 2-21 of the buffer, lines 8-183, to the ULA's columns 1-20, rows 1-22 (75K T). 0xAB3B: restore. The buffer 0xE000-0xF7FF is a ring of 192 lines, 32 bytes each, with scroll (0xB3E6), rewritten at its edges; 0xAF53 shifts it 4 pixels.
One plotter, one call: AE73 from 0xA932. Record (0xB3B4, 4 bytes each, count 0xB335): x, y, frame, height. Frame 80 and 0xFF: nothing. Graphics 0xBB38 + 32 frame, 16 x 2 bytes; mask 0xC5F8 + 32 * (0xB418)[frame]; pixel = (buffer AND NOT mask) OR graphic.
Frame 85, the fruit score: 0x96B8 copies its top 8 rows from 0xCC18 + 16 n (mask 0xCD18 + 16 n), the only graphics written at run time.
The play area has ONE attribute per round (0xB336, table 0x7FDF: 0x43-0x47, black paper), set once at 0x8DE8. 89DF paints two yellow cells wide in the fixed column 11-12 of rows 5-10 (height follows the jump) for Pac-Man, who stays at x 95, y 72 while the maze scrolls.

## Clash (owner: clash; step 2 skipped per BRIEF-2, numbers from the replays)
Kind A, in one place: the fixed yellow window. Scenery and ghosts crossing it turn yellow; ghosts have no colour of their own, they are the room's ink. Rounds with room 0x46 have none. See "Results" for the census.

## Design
| Site | Original | Patch |
|---|---|---|
| 0xAEED 0xAEF4 0xAEFB | LD (BC),A | NOP: the plotter runs on, same registers and time, buffer stays scenery |
| 0x8A17 0x8A1B | LD (HL),A | NOP: no yellow cells; the room's fill stays |
| 0x87AA 0x88E9 0x891B 0x7B9A | CALL 0xB090 | CALL e_bN: swaps the return address (same SP), blit, c_N commits all sprites from the game's own tables, JP back |
| 0xB094 | CALL 0xAF1F | CALL e_hide: a blit not returning to c_N hides all 12 sprites |
Hooks: alt ROM image 1, 0x386E, 301 bytes, stateless, interrupts on, NEXTREG only; the ISR uses neither. Commit after the blit, so the sprites change as the finished scenery is on show.
Sprites: slot n = n-th plotted (higher on top, as the later plot); 16x16 4-bit; 102 patterns loaded at start: frames 0-85, 86-101 the score forms (matched by comparing 0xC5D8 with the table). Nibble 0 clear, 1 the figure's ink (palette offset), 2-14 fixed, 15 black paper (mask without graphic). Clip window x 8-167, y 8-183. y from 0xB8 is y - 192: the ring brings a figure in at the top.
Colours: record 0xB3B4 bright yellow in play, every other figure the room's ink; both as the original's cells. Theatre (c4): room ink for all, as the original, where Pac-Man is white.

## Defaults taken (a human would have decided)
1. Every figure a sprite. 2. Scenery, dots, HUD, text on the ULA. 3. Depth: the game's plot order, sprites over scenery. 4. Colours: the game's own: ghosts in the room's ink, so cyan ghosts on a cyan maze. They were before. 5. See-through: the game's mask, paper black and solid. 6. Theatre Pac-Man stays white as drawn. 7. The painted set is a second .nex, not the default.

## Results
See the run folder's report and out/*_report.txt. Hook R: the game's RNG reads R (0x8F57, 0x92EE, 0x9318), so on a real machine hook fetches shift it. The lockstep holds R across hooks; the game's randomness differs, its logic does not.

## Open
- Uncovered by recordings (unit tests cover their pixels): see the report's frame list. A bot that hunts pills and fruit would reach them.
- Ghost-eaten scores and fruit shown rarely; the owner should see the painted fruit on a long game.
- Spec256 colours: lime Pac-Man is Alberto Conde's choice; a nearest-of-13 palette, mean error 24.

## Lessons
- [local: a plotter with NOPed writes keeps every register and all timing] Removing only the store instructions made the patched run equal the original in every register at each frame boundary, bar A and F inside the plot and blit loops, which follow the bytes read.
- [local: a lockstep with fetches counted only outside hook ROM] Frames by RZX fetch count stay aligned when hooks run in ROM and each site keeps its fetch count (CALL for CALL, NOP for one-byte store). Whole-RAM, whole-register comparison per frame, 150 frames a second. Hold R across hooks if the game reads it.
- [local: scan --writers on one recording missed a run-time graphic] The first recording showed no writer in the graphics; a later one showed the score frame rewritten. The composite check found it. Treat "static graphics" as provisional until every recording has passed.
- [local: unit tests against the real plotter on canvases] Found the y ring wrap no recording had reached.
- [local: negative controls need a recording where they matter] Yellow cells left in is invisible in a yellow room; a frame-80 sprite is blank. Choose the recording, and the control, accordingly.

## Technique use
- detect.gameplay-screen-readers: helped: only save, plot, restore and blit read the buffer.
- detect.tracked-unit: helped: one plot call draws one figure.

## Hardware checklist
Not run on hardware. Check: start, title, sprites at the view's edges, figures entering at the top, game over back to title, painted .nex colours.

## Stage log
2026-11-03 stages 0-3, unattended, about 40 min, ~35 tool calls, no user rounds.
