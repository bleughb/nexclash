# Lode Runner (Software Projects, 1984; 48K) - engine `loderunner`

Code: nexclash/loderunner.py (facts, colour sheet, preview, patch, verify, unit tests, recolour),
asm/loderunner_hooks.asm, docs/profiles/lode_runner.json, docs/records/lode_runner.json. Dispatch:
nexclash/engines.py, by signature at 0x9712 (the plotter). Reference: specnext reference/lode_runner/.

    python nexclash.py auto lode_runner.z80 --rzx LODERUNN.rzx --no-record
    python -m nexclash.loderunner sheet LODERUNN.rzx --z80 lode_runner.z80      (colour sheets)
    python nexclash.py recolour lode_runner_sprites.nex lode_runner_PAINTING_SPRITES_painted.png

## Patch design (build 2026-10-20)
- Hooks: asm/loderunner_hooks.asm, 273 bytes in GAME RAM at 0xA460 (strategy "ram", BRIEFING A3):
  0xA33C-0xA9FF is zero and never read or written (RZX; free runs: play to game over x2, key
  redefinition, editor menus), no code points into it. Not the alt ROM / printer buffer: the fade
  reads both as masks. Tail 0xA400-0xA44E (plain and sprite builds). Stateless: no hook RAM.
- Sites (original bytes checked): 0x9A5C / 0x970C CALL e_draw (IX record -> slot), 0x9E1B CALL
  e_drawr (runner slot), 0x96B6 CALL e_hide, 0x8E5F / 0x8E74 CALL e_trun / e_tgrd (sprite + tile 32
  printed instead of tile 30; guard slot from HL in the list 0x919D), 0x854F JP e_fade, 0x8541 JP
  e_cls (hide slots 0-7). 0x975B / 0x9761 77 -> 00 (the plotter keeps running: game state stays
  the original's). Figure paints 0x9EDB, 0x978C, 0x8E64, 0x8E79, 0x966E: CALL 0x856E -> FE FF 00
  (CP 255 / NOP = the flags 0x856E leaves). Erases 0x9A47 / 0x9E03 untouched: straight-line before
  their draws, so the sprite moves without hiding.
- Sprites: slot 0 runner, 1-7 guards (records 0xA183 + 17 k; the guard count is stored AND 7);
  30 4-bit patterns in bank 11 (runner 16-30, guard 16-30), 8x8 at the pattern's top left, x = B
  + 32, y = C + 32, palette offset 0 (index n = Spectrum colour n: 8 black, 9-15 bright; 0
  transparent). Colours per pixel from docs/profiles/lode_runner_colours.json (none yet: runner 15,
  guards 11); recolour rewrites bank 11 only.
- Stack: deepest site SP 0xAB27 (0x9A5C); verify measures the patched code's lowest SP and fails
  below 0xAB03 (IM 2 table 0xAA00-0xAB00, interrupt = 2 bytes).

## Outputs and verification (2026-10-20)
| Output | MD5 | Status |
|---|---|---|
| lode_runner.nex (plain, tail 0xA400) | cd0c1659c8569b2fa80da74962af90d2 | boot sim OK |
| lode_runner_sprites.nex (runner + guards sprites, default colours) | 85fe6afd593679bf59c787230ba0eaca | RZX + free run IDENTICAL, unit PASS; hardware untested |

RZX 4567 frames and free run 6000 frames IDENTICAL; 6061 unit cases, 3 negative controls detected;
set-up simulation, recolour round trip, boot OK (docs/VERIFICATION.md "Lode Runner").

## Hardware checklist (first test)
- Boots to the key definition screen; menu, start, play as the plain build.
- Runner (bright white) and guards (bright magenta) are sprites; no colour clash: ladders, bars,
  bricks and empty cells keep their colours when figures pass; figures in front of ladders.
- Level start: no inverted / doubled figure on the first move (start-position prints replaced).
- Digging, guards falling into holes, a guard trapped by a refilling brick and respawning at the
  top (proven by unit tests only), gold collection, escape ladder.
- Death / level end: the sprites vanish as the fade starts; no sprite left on the menu, editor or
  hall of fame.
- Two figures on the same spot both show (the original's XOR made them cancel).
- Speed as the plain .nex.


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

## Dean's decision (2026-10-20)
- "make the build": the phase A proposal APPROVED as written - runner + guards sprites, the rest on
  the ULA, scenery cells keep their colour, figures in front, paper see-through, sprites hidden at the
  fade, default colours (runner bright white 15, guards bright magenta 11; sheet not painted).

## Colour sheets (2026-10-19)
lode_runner_PAINTING_SPRITES.png (30 graphics: runner 15 frames - 13 from the RZX, 2 from the code -
and guards 15 frames), lode_runner_REFERENCE_ALL_SPRITES.png, _layout.json beside each: specnext
reference/lode_runner/. Key = R/G + graphics byte address; colours file
docs/profiles/lode_runner_colours.json (record name lode_runner).

## Open
- Longer recording (level complete, guard trapped + respawn, game over) - optional; unit tests can
  cover 0x96B6 / 0x970C.
- Not proven: tape LOAD / SAVE SCREENS (the toolkit cannot run a tape), hall of fame name entry,
  level 2+ (same code paths; graphics 16-30 unit-tested), a guard trapped + respawned in a real
  recording (unit tests only: 0x96B6 / 0x970C).

## Rework (opt-in) v2: the 128K release (engine `loderunner_v2`; Jon Attree, 2026-11-05)
Dean's build (cd0c1659 / 85fe6afd, pin rom3) is untouched and stays his record's default; `selftest --game
lode_runner` rebuilds both his and this rework = recorded.
- Why: the 128K file (TOSEC `Lode Runner (1984)(Software Projects)(128K).z80`, 41360f6c) plays AY music from bank 4
  in its IM 2 handler (0x6060 -> 0x73CA). Its code at every patch site is byte-identical to the 48K file's.
- What `loderunner_v2.py` changes (a copy; Dean's hooks, profile and colours are read, not copied): the detector takes
  the 128K snapshot; apply() patches banks 5 / 2; the whole alt ROM image = ROM 1 as the ROM path check takes a 128K
  recording's (SkoolKit's 128K ROM 1 with its keypad call sites as the 48K ROM has them) + the register block at
  0x386E (keypad code, never run; the record's rom_paths_known: the fade reads those 20 bytes as masks); a wrapper
  round Dean's set-up puts 0x5B00-0x5BFF back after NEXLOAD (the fade's 4th pass reads it); the stack floor allows
  the music handler's 16 bytes; a 128K boot check (bank 4 at 0xC000, paging unlocked); every recording replayed
  whole (Dean's stopped at 6,000 frames); the every-site clock matrix (Dean's hooks never write NR 7).
- Keys (128K defaults): I left, P right, Q up, A down, N / M dig; menu 1 keyboard, 0 start, any key; a level waits
  for a key after it is drawn.
- Results (2026-11-05): plain 1fa81bc6, sprites 1af22417, boot OK; 3 bot RZX (lr128_trap14 / 12 / 16, 20,042 /
  20,021 / 20,049 frames) + the 6,000-frame free run IDENTICAL (draws 14,859 + 24, erases 14,882, guard death 1,
  prints 60 + 240, paints 42,210, fades 96); 6,074 unit cases PASS, 3 negatives detected; clock matrix 8 sites x 4
  clocks PASS, forced 3.5 MHz exit detected (9 cases); ROM paths pass (known: the register block); tail never read
  before written. JNext: pace ORIGINAL (probe 0x92FC, 10 trials a scene: quiet -0.00 %, busy +0.09 %, sound
  +0.04 %), flicker 300 frames clean, soak 15 min no freeze, AY written as the original. Cheats (128K .pok):
  Infinite Lives, Immunity (guards) proved in the simulator; Entry Code Always Correct dropped (0x5D1E is not code
  in this snapshot: no effect). No standard loading screen on the 128K tape (headerless code blocks only).
- Hardware: none.

## Lessons
- [deferred Open: reconsider when a third engine needs a 128K game's whole alt ROM image in ROM 1: a shared helper
  (copied in loderunner_v2 and tid128)] The 128K release's ROM 1 differs from the 48K ROM in its keypad code; the fade reads every ROM byte, so the
  image is ROM 1 as nextboot.rom_paths models it, not Sinclair's 48K ROM (observed: 29 MISMATCH reads with the 48K ROM).
- [local: Dean's verify replays an RZX only to FREE_FRAMES (6,000): the rework replays each recording whole]

## Technique use
- patch.whole-altrom-image: used (a RAM-hook engine given a whole image only so the fade reads the original's ROM)
- verify.update-locked-pace: helped (probe 0x92FC; a level waits for a key, so the start keys press one)

## Friction
- reuse: [tool nextboot.rom_paths] the ROM path and tail checks are the shared ones; the boot check follows rainbow_z80n's
- retries: [local: three verify runs: the 128K raw-memory view (recursion), the RZX length cap, the clock matrix added]
- environment: [local: setsid nohup jobs died with the tool call; the harness's own background mode worked]
- hand-rolled: [local: bot recorder on SkoolKit's C simulator (pilot platoon m128.py), pace trials from Cobra's script]
- scratch: [none: bot, cheat and trial scripts stay in the pilot run folder runs/dean_lode_runner/work]
