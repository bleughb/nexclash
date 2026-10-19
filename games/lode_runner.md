# Lode Runner (Software Projects, 1984; 48K) - engine `loderunner`

Code: nexclash/loderunner.py (phase A: facts, colour-sheet capture, preview). Reference: specnext
reference/lode_runner/ (Dean, 2026-10-19).

## Inputs
- Dean sent LODERUNN.TAP (48K, cracked: "Cracked by Zeljko Robert", BASIC "LODE part1") and
  LODERUNN.rzx (Fuse, 9 SZX snapshots: autosave was on; 4548 frames = 91 s). No .z80: lode_runner.z80
  = the RZX's first snapshot (SZX -> .z80 with SkoolKit get_state / write_snapshot; RAM and every
  register identical), so the recording starts exactly at the .z80 (the "Record from snapshot" case).
- lode_runner.rzx = LODERUNN.rzx stripped (`rzx strip`: 8 autosaves dropped); replays to the end, no
  desync.
- Also sent first: "Lode Runner (128k Version)" TZX (Software Projects, TZXed by Andrew Barker;
  standard-speed blocks: BASIC boot, loading screen, headerless code). Not used: the recording is
  of the 48K TAP. Kept in the reference folder.
- RZX covers: key definition screen, "press any key", level 1 only (two lives lost: fades at frames
  1972 / 4349), digging, brick refill. NOT covered: level 2+, level complete, guard trapped and
  respawned (0x96B6 / 0x970C), game over, hall of fame, menus, editor.

## Snapshot (inspect)
- 48K, PC 0x6060 (IM 2 handler: EI / RETI), DI, IM 2 I = 0xAA (table 0xAA00-0xAB00, vector 0xAAFF),
  SP 0xAB2D (game stack top 0xAB31: LD SP at 0x8035), RAMTOP 0xFF57, border 0. Key definition
  screen up (keys O P Q A, fire).
- ISR: EI / RETI only (isr: 2 instructions, 2 stack bytes). No ROM ISR, no IY use.
- 0xC000-0xFFFF: data (10561 non-zero bytes; level data presumably), never touched by level 1 -
  NOT free.
- Menu key D: IM 1, LD SP,(35045), RET = back to BASIC.

## Rendering model (pure XOR figures, tile scenery)
- Graphics table 0x7800: 256 x 8 bytes - font, scenery tiles, figure frames 16-30 (run, climb, bar,
  fall; 30 = the level-start / standing pose), dig 240-246, refill 249-251.
- Tile print 0x8501 (A = graphic, B = column, C = row; LD (HL),A at 0x8537, overwrite).
- Figure plotter 0x9712: pure XOR, 8 lines x 2 bytes (writes 0x975B / 0x9761), A = graphic, B = x,
  C = y in pixels; SELF-MODIFYING: 0x971B writes the shift at 0x974E, 0x9723 the JR at 0x975D.
- Callers (code, all of them): 0x96B6 guard dies (erase), 0x970C guard respawn (draw 30), 0x9A47 /
  0x9A5C move (erase old from 0x98DE.., copy new over old, draw new), 0x9E03 / 0x9E1B (runner).
  IX = the figure record at every call: 0xA174 runner (15 bytes), 0xA183 + 17 n guards (4 on level 1).
  In the RZX: 0x9A4A / 0x9A5F (3251 each), 0x9E06 / 0x9E1E (3 each).
- Level start: the figures are PRINTED as tile 30 by 0x8501 (return 0x8E62 runner, 0x8E77 guards);
  the first XOR erase removes the print.
- Cell XOR 0x983E (writes 0x986D): dig / refill / 33 into brick cells - scenery.
- Figure colour = attributes: 0x9EC5 paints each cell a moving figure covers with (0xA12F) (71
  runner, 67 guard) via 0x856E, write 0x858F, unless the map cell is type 1/2/5/7; 0x8F91 and others
  restore scenery colours. Level start: 0x977B paints the start cell 71 / 67.
- Logic reads the MAP (0xAB32, 32 x 24), not the screen: the only readers of figure pixels are the
  plotters themselves and the fade. Attribute READS: 0x80E0 (51), 0x9668 (4, guard code) - to check
  in phase B (they may see figure colours).
- Non-XOR writers over figure pixels (step 3, whole RZX): only the fade 0x854F (screen AND ROM/RAM
  bytes, 4 passes; masks DE = 0..0x6BFF, so it READS 0x5B00-0x6BFF) and the clear 0x8541.
- Figures on screen at once: runner + 4 guards (level 1).

## Memory (scan, whole RZX)
- Untouched: 0x6C00-0x77FF (code/data, non-zero), 0xA33C-0xAAFE (0xA33C-0xA9FF ZERO; no code
  reference into it), 0xAF30-0xB2A7, 0xB3B0-0xBFFF (non-zero), 0xC000-0xFFFF (data).
- Printer buffer 0x5B00-0x5BF8 zero but READ by the fade's 4th pass (masks): not free.
- Lowest SP 0xAB19; below it the IM 2 table: no dead stack.
- Plain build: tail at 0xA400 (79 bytes, 0xA400-0xA44E), `convert --tail 0xA400`; nextboot.check
  OK (tail excluded). lode_runner.nex cd0c1659c8569b2fa80da74962af90d2 - not hardware tested.

## Proposed design (phase A question, 2026-10-19)
- Sprites: runner and guards (every 0x9712 caller and the level-start prints), 8x8 graphics in
  16x16 patterns, x/y = the plotter's B/C. Identity: IX record (runner, guards 0-n) - one sprite each.
- Stay on the ULA: bricks, ladders, bars, gold, dig / refill animation, HUD, text, menus, editor,
  hall of fame.
- Cells keep their scenery colour (0x9EC5's paint removed); figures in front of everything.
- Paper see-through by default; outlines paintable (sheets with paint_clear).
- Fade / clear: sprites hidden when the fade starts (they do not fade).
- Default colours: runner bright white (15), guards bright magenta (11) - the game's attributes.
- Hook memory: alt ROM; hook state (if any) in 0xA33C-0xA9FF (zero, untouched; to prove for the
  menus / editor / load-save paths by free runs in phase B).

## Colour sheets (2026-10-19)
lode_runner_PAINTING_SPRITES.png (30 graphics: runner 15 frames - 13 from the RZX, 2 from the code -
and guards 15 frames), lode_runner_REFERENCE_ALL_SPRITES.png, _layout.json beside each: specnext
reference/lode_runner/. Key = R/G + graphics byte address; colours file
docs/profiles/lode_runner_colours.json (record name lode_runner).

## Open
- Dean's answer to the phase A question.
- Longer recording (level complete, guard trapped + respawn, game over) - optional; unit tests can
  cover 0x96B6 / 0x970C.
- Phase B: attribute reads 0x80E0 / 0x9668 vs removed figure colours; tail / hook-state RAM proven by
  free runs of the menus (load / save / edit screens).
