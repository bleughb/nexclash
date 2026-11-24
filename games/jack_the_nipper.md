# Jack the Nipper (Gremlin Graphics, 1986) - stage 1 done (design decided 2026-11-23); engine not yet written

## Next session
Stage: 2 (build)             State: design decided by the owner 2026-11-23 (all defaults; "Design decisions" below)
Inputs: TOSEC `Jack the Nipper (1986)(Gremlin Graphics Software).z80` (md5 adcdb8f9bb5e72218392aab8fd44e78e) and its
`[a]` (4c5398b8bcfd88ebd83656f01c3aca21); rzxarchive `j/jacknipper.rzx` (108,043 frames, 36 min; its own start
snapshot md5 903c092495784d308cf03899b80d7110)    Branch: add-jack-the-nipper
Checks: survey (GATE OK), inspect, figure sheet, pixel readers, depth    Pending user answers: none
Start with: "Patch plan" below (template smashtv.py): stage A = sites + slot-1 page + the H redirect only (boot check,
the shadow keeps the background), then sprites, verify, units + negatives, cheats, record
Read: PLAYBOOK 2-3, docs/ENGINE_CONTRACT.md, "Design decisions" below
Open: a short recording (3-5 min) for the build runs (the 36-minute one stays for the full verification)

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

## Patch plan (stage 2, 2026-11-23, in progress)
- Technique: patch.scratch-redirect. The game's own figure draws keep running unchanged (same work, so the same pace
  in a game with no frame sync), but into a scratch shadow mapped at slot 1 (0x2000-0x2FFF: the ROM's place; the game
  uses the ROM for one RET at 0x0052). The real shadow then holds only the background, the dirty-cell copier and the
  restore run as before, and the hook builds the figure's sprites from the same graphics and mask.
- Redirect per call, at the two figure callers' returns from 0x87BB (0x80C9 and 0x8273: H - 0x40), not by patching the
  helper's base (`ADD A,0x60` at 0x87EF): 14 other callers use 0x87BB for map lookups (0x9400 / 0x9BFC: `CP 0x72` on
  H; 0xB273 turns H into a cell-map address at 0x7000+), and the restore keeps its own base (0x8747: `ADD A,0x60`).
- Confirmed 2026-11-23: the dirty-cell marks are base-independent (0x8123: `AND 8`, `RRCA` x3, `ADD 0x7D` from H, then L), the 16-wide draw (0x80E3-0x810C) is an AND-mask pass then an OR-graphics pass stepping by `DEC H` and the relative row helper, and no `CP` / `SUB` / `AND` with a 0x60-0x70 constant exists in 0x8000-0x881F (only the two `ADD A,0x60`). So slot 1 can hold a RAM scratch page for the whole game (the game never reads the ROM there; rom_paths: one RET at 0x0052): the hooks only move H at the two returns and build the sprites, with no map per draw. The verifier's memory compare proves no figure write reaches the real shadow.
- Still to confirm: every shadow write of a figure draw goes through that HL (the shifted path 0x8147,
  the 24-wide path 0x8228, the shifted routine near 0x85D0 with IY = 0x8000 and DE' = 0x7400, the AND-table writer
  0x8637-0x8667); the dirty-cell marks (0x812C, 0x8209, 0x82F6, 0x845F) take the cell from H bits the 0x40 shift does
  not touch, or map the mark back; slot 1 mapped from the 0x8009 entry to its returns, the ROM back at every exit.
- Sprites: from DE' (graphics) and DE (mask) at the hook, rows by type. The original's look (screens.png, 2026-11-23): the graphics are black line art (the cells' ink is black), the mask-cleared body shows the PAPER of the cells it stands on (the clash: Jack yellow on a yellow wall, blue on the blue floor). Clash-free default for "the game's own colours": lines black, body in the paper (and bright) of the attribute cell under the figure's feet, one colour per figure, until a painting; the line art and its outline stay as drawn. 4-bit patterns (0 clear, 1 black, 2 body), the body colour by the sprite's palette offset (one bank per Spectrum colour), so one pattern serves every room. (IX+4) bit 0 = 0 takes the mirrored draw (0x8482 / 0x85D0: bytes reversed through the table at 0x7400, order swapped): the sprite's X mirror. Position: the copier maps shadow row y to screen row y (0x86F9: counters 0x7D / 0x7E -> 0x40xx / 0x48xx), so sprite (x + 32, top + 32), x = (L AND 31) x 8 + shift; a pattern cache (optimise.pattern-cache: a
  24 x 40 adult is six sprites, 69 kinds); sprite order = object order (depth).
- Template: nexclash/smashtv.py (the game's own plotters into a scratch buffer, no frame sync; docs/ENGINE_TEMPLATES.md), with the shared hook library: hlib_pcache (pattern cache), hlib_commit (atomic attribute commit), hlib_speed, hlib_r. Sites: 0x80C9 and 0x8273 (both `PUSH HL; PUSH AF; AND A` = E5 F5 A7, right after `CALL 0x87BB`): JP to the hook, which takes the figure (DE' graphics, DE mask, rows by type, x / y from IX), moves H by -0x40, replays the three bytes and returns to +3; 0xAA4A (`CALL 0x86F9`, the copier, after Jack's own draw at 0xAA44 and the footsteps): CALL the commit first. Slot 1 = one RAM page: scratch shadow 0x2000-0x2FFF, hook code and state above it, the register block.
- Hooks at 28 MHz with patch.restore-speed and patch.preserve-r; verify per hook against the RZX (registers, all memory
  but the scratch page; picture = ULA + sprites against the original), pace by verify.update-locked-pace.
- Cheats (the owner, 2026-11-23: every patch carries them, off by default): the archive's POKE (Super Collection "¤ Pokes/Jack the Nipper.pok"): Immunity = 44278 and 44285 set to 58 (0xACF6 `JP NZ,0xAAB9` and 0xACFD `CALL NZ,0xA9F2` become `LD A,(nn)`; original bytes match the `[a]` snapshot). Check each in a replay, and look for more (lives, the Naughtyometer) as for Winter Sports.
- The plain build's tail at 0x6F00 is to be proven by rom_paths' tail proof (Green Beret, 2026-11-23: a RAM scan alone
  missed a copier reading its tail before the game wrote it).

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

## Lessons
- [none: stage 0 only: the survey answered every intake question it asks]

## Technique use
- detect.pacing-structure: used: the survey's no-interrupt finding names the no-frame-sync case for the design

## Friction
- reuse: [none: no code written at intake]
- retries: [none: the first survey run started outside the toolkit folder (module not found); rerun from it]
- environment: [none: no workaround]
- hand-rolled: [none: survey and inspect covered intake]
- scratch: [none: no scratch scripts]
