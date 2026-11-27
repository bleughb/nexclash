# Jack the Nipper (Gremlin Graphics, 1986) - stage 2 done; the whole-recording stamp to rerun on the final module

Techniques: `patch.scratch-redirect`, `optimise.pattern-cache`, `patch.restore-speed`, `detect.pacing-structure`, `detect.gameplay-screen-readers`

## Next session
Stage: 3 (prove + deliver)   State: `selftest.py --game jack_the_nipper --verify --stamp` PASSED 2026-11-26 (stamped) on the
final build (sprite Y bit 8, the H' proof past delay loops); Codex review fixed; PR with both games
Inputs: TOSEC `Jack the Nipper (1986)(Gremlin Graphics Software)[a].z80` (4c5398b8bcfd88ebd83656f01c3aca21);
rzxarchive `j/jacknipper.rzx` (108,043 frames, 36 min)    Reference: reference-local/jack_the_nipper
Branch: add-jack-the-nipper (local, with Jack the Nipper II)
Start with: the owner's test of the remade test copy (~/nxc-test), then colour sheets (docs/COLOURS.md)
Open: pace in JNext; the cheats not yet tried in play; stage 3: colour sheets and recolour (ENGINE_CONTRACT: required for new
engines)
Test copy: ~/nxc-test/Jack the Nipper 1.0 test (remade 2026-11-26 from the stamped build: sprites 7cdc2644,
Immunity + Infinite lives).

## Snapshot (0b)
48K, in game (PC 0x908B in RAM; the recording's start 0x90AD), IM 1 with interrupts OFF (DI), I = 0x3F, SP 0x7FF7,
RAMTOP 0x7C60, border 0. No loader to run.

## Survey (2026-11-22, the whole recording)
- Engine: unknown (no detector, no TID / Dizzy 1 signature): a new engine, feasibility first (PLAYBOOK 3d).
- Rendering: 0x86F9 writes 92 % of the pixel bytes (507 bytes per call, 28,962 calls), the play area 256 x 128 from
  0xAC75, reading 0x7D00-0x7EFF and 0x6800-0x6FFF: a copier from a composed buffer or cell map. 0xAD99 (block copies,
  269 calls) and 0x7F84 (attributes, 9 calls) are screen set-up; 0xFFCD (8 bytes a call, x 48-215) is small and runs
  from 0xFF93 / 0xFFB1 / 0xFFC8 (top of RAM).
- Pacing: no interrupt accepted in 108,043 frames: nothing syncs the game to the frame, so hook time is game time
  (PLAYBOOK 4 "no frame sync"; card detect.pacing-structure).
- Coverage: GATE OK (every CALL site to the top plot routines in code that ran was reached).
- Plain conversion: boots in the simulator, but its tail is NOT safe: the converter's default (79 bytes at
  0x7F98-0x7FE6, below SP) covers the room-colour routine 0x7F84-0x7FBC, which runs at every room change. The printer
  buffer is the game's (read and executed, 0x5B00-0x5BBC); the only untouched gap near the stack is 0x7FBD-0x7FE8 (44
  bytes); the untouched ranges elsewhere are code the recording did not run (the Kempston reader at 0xA44D) and text
  (0x8E55); the compact tail (53 bytes) does not fit the gap either. The tail goes at 0x6F00-0x6F4E instead, in the
  lower shadow, which the room build writes before anything reads it (scan: write-first over the recording and over
  600 free-run frames from the TOSEC snapshot), with the printer buffer restored after NEXLOAD (keep_printer_buffer:
  the game reads and runs code there). Plain test build md5 f86eb31c28fe3f6c69dfc0a313ec509c: boot check OK with
  and without the NEXLOAD model. The ROM is unused apart from one RET at 0x0052.

## Stage 1 analysis (2026-11-22, first 15,000 frames)
- 0x86F9 is a dirty-cell copier, not a plotter: 512 cell counters at 0x7D00-0x7EFF (32 x 16 cells = the 256 x 128
  play area); for each marked cell it copies eight pixel rows from a shadow screen at 0x6000-0x6FFF to the display.
- The shadow is written by read-modify-write code at 0x80E5 / 0x80FD, 0x8199 / 0x81D4, 0x8299 / 0x82B7, 0x838B,
  0x865D (it reads each byte back first: masked sprite drawing, several variants), which marks cells at 0x812C,
  0x8209, 0x82F6, 0x845F; 0x8760-0x877C writes eight rows a call (x202,775: most likely the background restore).
- The sprite routine is 0x8009 (called from 0x92A9, 0xA71A, 0xA729 and the main loop at 0xAA44, which then runs the
  copier 0x86F9 and 0x8735), one object per call through IX: (IX+6) flags (bit 4: skip), (IX+2) type (bit 0: 16 or
  24 rows), (IX+5) animation frame (a 32 / 48 / 96 / 144-byte step into the graphics), (IX+7) / (IX+9) graphics and
  mask pointers; 0x87BB turns the position into a shadow address, then a 16-pixel-wide masked draw bottom-up (0x8781
  steps up a character row). Shared helpers: 0x8781 and 0x87A0 (8 callers each), 0x87BB (16).
- Objects: a table at 0x8820, 16 bytes each, count at 0x8CD4 (loop at 0xAA55). 0x87BB: x = (IX+0) less 11 or 7 by type
  (unless (IX+15) is set), y = (IX+1) (bottom row: the draw goes up), shadow address in the screen's layout from 0x6000;
  it returns the pixel shift (x AND 7), and a non-zero shift takes the shifted path at 0x8147.
- Per frame: objects drawn into the shadow (0x8009, cells marked), marked cells copied to the screen (0x86F9), then
  restored in the shadow from the tile map (0x8735: cell map 0x7200-0x73FF = one tile index per cell, tile graphics at
  0x7500 + 8 x index). So with sprites the figures can leave the shadow altogether, if no logic reads their pixels.
- Object types 3+ take a second path (0x8228): 24 px wide (3 bytes a row), 24 / 32 / 40 rows by (IX+2) bits 2 / 3.
  Both paths: at the return from 0x87BB (0x80C9, 0x8273) main DE = mask, alternate DE' = graphics, bottom row first.
- No logic reads figure pixels (scan of the shadow and the display over 30,000 frames): the readers are the copier,
  the room-entry blit (0xAE14: shadow and its attributes LDIR'd to the screen), fills (0xA8E5, 0xA917) and a
  character-roll effect (0xFF93 / 0xFFCD). So no virtual read (PLAYBOOK 4: no dependency).
- Depth: nothing draws into the shadow after the figures (0x9A0D between the draw and the copy is the footstep
  sound), so figures are in front of all scenery and later objects over earlier ones: sprite order = object order.
- Model so far: shadow screen + dirty cells + masked sprites; figures take the room's attributes (0x7F84 sets them
  per room). Next: the plotters' entry points and inputs (x, y, frame), the restore's source, figures per room.

## Design decisions (the owner, 2026-11-23)
All defaults taken: every figure a sprite (pickups included); scenery, HUD, score and text on the ULA; figures in front of all scenery, later objects over earlier; the game's own colours until the painted sheet; effects (pea, sparkle, smoke) as sprites; the masks' black outline kept; no pause or message window known (a hide gets its own fix if one turns up).

Owner, 2026-11-26: repair the dump's space character. The font is at 0x5B00 (printers 0xFF32, 0xFF7D read char x 8 from
there), so the space is 0x5C00-0x5C07, the ROM's KSTATE; the TOSEC [a] dump holds 00 F7 00 00 00 F7 00 00 there (the
dumping emulator's ROM interrupt), so every space prints as two dashes once the game redraws its menu or a message (the
original .z80 in OverSpec does the same). Both builds write eight zero bytes there when they find that value; the
verify replays the original with the same repair (only the two printers read those bytes: scan, 30,000 frames).

Owner, 2026-11-26: Enhanced colours, every figure painted (Codex first pass from the sheet, the owner approved it).

## Enhanced colours (2026-11-26)
- Sheet: every image the recording draws (68; the one the game builds in the printer buffer at 0x5B00 keeps its
  colours), keyed by graphics byte; 1 black, 2 the body (the cell's paper, the sprite's bank), 3-15 the painting
  palette, written into entries 3-15 of all 16 banks (setup `setspare`), so the game's body colour stays available.
- Hooks: byte2's four pattern bytes go through `ovr`, which maps the table page for that graphics byte at slot 0
  (OVR_BASE 0xE000, 4 pages from 40: 4 bytes = 8 nibbles a graphics byte) and puts each painted nibble over a pixel
  that draws; V_OVR off in the default build (byte for byte as before but for the new code).
- Build: plain, sprites and _enhanced (the .nxc's colour set); recolour rewrites only the table banks (selftest guard).
- Verify: the model gives a painted pixel its nibble; Enhanced replay on the first 6,000 frames; a build painting every
  graphics byte of the table and the same with the paint left out (caught).
- The owner saw mum's and dad's lower halves flash: the pattern cache took a slot the last update's sprites still
  showed (its attributes stay until this update writes new ones). `slot` now skips this and the last update's slots;
  the verifier fails a pattern overwritten under a sprite on screen (192 times in 6,000 frames before); negative: the
  old rule put back, replayed 3,000 frames (NEG_FRAMES: none of its hits fall in the controls' usual 1,500).

## Build (stage 2, 2026-11-23)
- Technique: patch.scratch-redirect. The game's own figure draws keep running unchanged (the same work, so the same
  pace in a game with no frame sync) into a scratch shadow at slot 1 (page 24: 0x2000-0x2FFF, the ROM's place; the
  game uses the ROM for one RET at 0x0052): at the two figure callers' returns from 0x87BB (0x80C9 and 0x8273, `PUSH
  HL; PUSH AF; AND A`) a JP to the hook records the figure and moves H by -0x40 (RES 6,H). Not the helper's base: 14
  other callers use 0x87BB for map lookups, and the dirty-cell marks take only base-independent bits.
- Commit at the copier's entry (0x86F9, `LD HL,0x7CFF` replayed): the copier has two callers (0xAA4A and the main
  loop's 0xAC72), so a hook at one caller missed scenes.
- Sprites: 4-bit patterns (0 clear, 1 black line, 2 body) from the graphics and the mask, the body in the paper (and
  bright) of the attribute cell under the figure's feet through the palette offset (one bank per colour), so one
  pattern serves every room; (IX+4) bit 0 = 0 draws mirrored: the X mirror bit (a mirrored 24-wide box starts 8 pixels
  left); sprite order = object order; a pattern cache keyed by graphics address + pair.
- Depth: NR 0x15 = 0x01 (bit 6 clear: sprite 127 on top, so later objects over earlier); the first build set 0x41
  (sprite 0 on top: the depth reversed) and the verifier, painting later sprites last whatever the setup said,
  passed it (Codex review). render() now takes the order from the build's setup bytes.
- ATTRTAB holds 102 sprites below the code (0x3400-0x35FF): the attribute writer stops there (18 adults of six
  sprites would have run into the code).
- Hooks: own stack, the caller's speed back (HLIB_SPEED_IN / OUT), the record at 28 MHz. Builds: plain 496edfe0,
  sprites 3232643e (record; b836bba4 before the Codex review). The start-up tail at 0x6F00 is put back before the game starts (restore_tail).

## Results
- 3,000 frames (simulator): zero failures; 860,219 sprite pixels compared against the model of the original's draws,
  the model against the original's shadow bytes at every copy. H' and the stack bytes below SP holding the moved
  address proven dead by the lockstep run-on (RUN_ON 400,000 steps; Jack's own draw takes up to ~185,000).
- auto (2,000 frames): PASSED; units: every site at four speeds, the copy as a hide; negative controls DETECTED: no
  redirect, never mirrored, wrong colour bank, leftover sprites not hidden, the caller's speed not given back.
- After the Codex review (2026-11-23): the final build verified over 1,000 frames with the added checks (the return
  PC, no jump into a replaced instruction, no site rewritten, every hook store form modelled, the boot on through the
  tail's restore to the game start, the stacking order from the setup); six negative controls, each by its own failure.
- The whole recording (108,043 frames): the stamp on the final build (pending).
- JNext 1.3.5 headless: both builds reach play, the figures show as sprites; the .nxc menu boots.

## Cheats
Every patch carries them, off by default, checked against the code: Immunity 44285 = 58 (the archive's: 0xACFD
`CALL NZ,0xA9F2` to `LD A,(nn)`: the lose-a-life routine never runs; the death flag 0x8CFD it would clear has no other
reader); Infinite lives 43516 = 24, 43517 = 35 (ours: `JR 0xAA21` at 0xA9FC jumps over the lives decrement and the
lives redraw to the death sound). The first lives cheat, `DEC A` at 0xA9FF to `NOP`, left five lives, so the redraw's
5 - lives was 0 and its DJNZ blitted 256 icons: 2,076 screen bytes changed against the original routine's 201 (the new
one: 129, the one icon it no longer erases). Not used: the archive's second Immunity POKE (44278: only turns off the Q
pause / quit key). The record's .pok is ours (the archive's file is kept as jack_the_nipper_archive.pok).

## Hardware checklist
- Boots from the .nxc menu (cheats off), reaches play; every figure (Jack, the adults, pickups, the pea, smoke) a
  sprite with its black outline, the body in the colour under its feet, no colour bleed into the scenery.
- Mirrored figures face the right way; a room change leaves no sprite behind.
- Each cheat on: no life lost (Immunity: no death at all).

## Pacing
No interrupt accepted in 108,043 frames: nothing syncs the game to the frame, so the work it does is its pace (survey,
card detect.pacing-structure). The figure draws still run whole (redirected, not replaced), as do the copier and the
restore, so the game's own work per update is the original's. The time added is the hooks': the record at each draw
(at the caller's speed) and the commit at each copy (28 MHz; tiles uploaded only on a cache miss). Not yet measured in
JNext (verify.update-locked-pace): open. Simulator, first 3,000 frames (653 updates): the hooks add 1.87 % of the time (about 6,000 T a game update at 3.5 MHz terms: the record and the commit at 28 MHz, tiles uploaded only on a cache miss); 2.95 % before the record moved to 28 MHz. So the game runs about 2 % slower than the original.

## Dependencies
Readers of the shadow and the display (`scan --writers`, 30,000 frames): the copier, the room-entry blit (0xAE14), fills
(0xA8E5, 0xA917) and a character roll (0xFF93 / 0xFFCD); no logic reads figure pixels. The dirty-cell marks and the
restore run as the original's (the marks take only base-independent bits of the address). R is never read (no
`LD A,R` in the code). Differences the redirect leaves, proven dead by the verifier's run-on: H' (the draw's last
address) and stack bytes below SP holding the moved address.

## Design question (asked 2026-11-23; PLAYBOOK 3c defaults + this game's exceptions)
The recording draws 69 figure kinds (figures.png, from 0x8009's two paths over 108,043 frames): 36 small objects
(16 x 16: pickups such as the computer, glue, bomb and keys, a bug, and effects: the pea, a sparkle, four smoke
puffs), 8 of 16 x 24 (Jack, the ghosts, a kid) and 25 adults 24 px wide (24 / 32 / 40 rows: postman, women, the
policeman, a chef, others; one is a radiator).
1. Every figure a sprite, from every caller of 0x8009 (pickups included: the game draws them as objects).
2. Scenery, the HUD (Naughtyometer, In pocket, lives, RASH), score and text stay on the ULA.
3. Depth: the game's own rule, which here is "figures in front of all scenery, later objects over earlier ones".
4. Colours: the game's own (each figure in its room's ink) until the painted sheet (the first sprite build's).
5. Pause / message windows over the play area: sprites off while up. None found in the code so far: does the game
   have any?
Always asked: effects (pea, sparkle, smoke) as sprites too?; the masks give every figure a black outline: keep it
(the original's look) or drop it?; anything not converted: none found.
Also: no frame sync, so the hooks run at 28 MHz and keep the original's pace; a 24 x 40 adult is six hardware
sprites, so patterns are uploaded per figure from a cache (more figure kinds than the 16K pattern memory holds).

## Stage log
- 2026-11-22: stage 0, ~1.5 h wall (both games' surveys in parallel), ~20 tool calls, no user rounds.
- 2026-11-23: stage 1 closed: the owner took every default (one round).
- 2026-11-23: stage 2 (engine, verifier, units, negatives, record, .nxc), ~90 tool calls, no user rounds.
- 2026-11-26: the owner's test: the dump's dashed spaces repaired (his answer); Enhanced colours (sheet, ovr, recolour,
  Codex's painting approved); the shown-slot flash fixed; ~90 tool calls, 6 rounds.

## Lessons
- [card optimise.pattern-cache §Failure lookup] demonstrated: "never evict a shown slot" read as "used this update" let
  the cache overwrite the last update's slots while their sprites were still on screen (mum's and dad's legs flashed);
  the replay compared only the state after each commit, so a shown-slot check went into the verifier.
- [kb lesson.negative-control-must-reach-path: a negative the recordings cannot reach] The shown-slot negative was
  checked on 6,000 frames but the unit runs controls on 1,500, where it never hits (first hits by 3,000): the full
  stamp reported it MISSED, and the failed run also skipped the automap step, so every md5 differed. Run a new
  negative on the unit's own frame budget before stamping; give it its own budget when the path comes later.
- [local: this dump; the recording starts in play] The replay never redraws the menu, so a defect only the menu and
  the messages show (the dump's space glyph, 0x5C00, written by the dumping emulator's ROM interrupt) passed every
  check; the owner saw it at the menu. Run the original past its attract loop in OverSpec when a game keeps data in
  0x5B00-0x5CB5, and compare the text it prints.
- [doc LEARNINGS 2.3] demonstrated: SkoolKit drops writes below 0x4000, so the verifier models the slot-1 page by
  wrapping every store form the hooks use (LD (nn), PUSH, CALL, LD (IX+d), LD (HL) / (DE) / (BC)).
- [card patch.scratch-redirect §Failure lookup] demonstrated: H' differed after a redirected draw; a check of H' alone
  failed (EXX / EX DE,HL move the value); the lockstep run-on until every register agrees proved it dead.
- [card patch.scratch-redirect §Failure lookup] demonstrated: the commit hooked at one copier caller (0xAA4A) never
  ran on the main loop's path (0xAC72); the copier's entry catches both.
- [kb lesson.sprite-order-and-layers: Jack the Nipper's 0x41 reversed the depth] demonstrated: NR 0x15 bit 6 set puts
  sprite 0 on top; a verifier that paints later sprites last whatever the setup says cannot catch it.
- [kb lesson.archive-poke-translation: a cheat must keep what the skipped code's consumers need] demonstrated: the
  lives NOP made the redraw's 5 - lives 0 and its DJNZ ran 256 times.
- [kb lesson.verifier-fails-closed] demonstrated: a store form the slot-1 model leaves out, a different return PC and a
  control caught for another reason all passed before the review; each now fails.
- [local: this game's colours] observed: the line art is black and the body shows the paper of the cells under it;
  the clash-free default is the paper under the feet, one colour per figure.

- [tool asm/jack_the_nipper_hooks.asm] A sprite's Y is 9 bits: writing only bits 0-7 wrapped a figure above the room
  (top 248) onto the top rows, where the game shows nothing; carry into attribute 4 bit 0 (II's full verify caught 4).
- [tool nexclash/jack_the_nipper.py] dead_after gave up inside a 65,536 x 256 delay loop (frame 107,675): an alternate
  register is read only by EXX, so run one machine on to the next EXX, then compare the two in lockstep.
## Technique use
- detect.pacing-structure: used: no frame sync, so the hooks' time is the slowdown (1.87 %)
- patch.scratch-redirect: used and amended (the run-on dead proof; the commit at the copier's entry)
- optimise.pattern-cache: used: keys by graphics address + pair; 4-bit patterns serve every room

## Friction
- reuse: [local: per engine] Jack the Nipper II imports this verifier's overlays, slot-1 store model and NextSide
- retries: [card patch.scratch-redirect §Failure lookup] the H' check and the commit site each took a second attempt
- environment: [none: no workaround]
- hand-rolled: [local: per engine] the hook-time meter (hook-page T-states, 28 MHz at an eighth)
- scratch: [local: dropped] fullverify.py and the figure census: per-engine harness runs
