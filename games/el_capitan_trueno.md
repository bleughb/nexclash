# El Capitan Trueno (Dinamic, 1990) - engine `trueno` (hooks and build from the contributor; NOT verified)

## Next session
Stage: 3 (prove)  State: released to players as version 1.2 (2026-11-01); software proof NOT done
Inputs: specnext branch contrib-el-capitan-trueno (snapshot, trueno1.rzx, the contributor's build folder)
Start with: ## Verification plan below (classify the hook sites, then write verify / unit tests)
Read: PLAYBOOK stage 3 + 6, docs/ENGINE_CONTRACT.md, games/el_capitan_trueno_build.md (## System map, recipe), ## Open
Open: nexclash/trueno.py does the plain build only (the sprite chain is the contributor's trueno/build/*.py,
outside the toolkit), no differential verify, no unit tests, no negative control, hardware untested (MAME 0.289 only)

48K. Inputs (contributor's machine, not in this repo): `Capitan Trueno, El (1990)(Dinamic)(ES).z80`
(copied as Trueno.z80) + trueno1.rzx (Spectaculator 0.61, 53542 frames, ~17m50s). The .z80 is the
RZX's own start snapshot (same PC/SP/I/IM, 60 bytes differ).

The contributor plays and ships the build as "version 1.2" (2026-11-01): four .nex files (plain,
immortal, sword, both), three languages, two sprite colourings, 28 MHz with a frame limiter, a
patcher page for the cheats. The sections up to ## Open describe the first prototype (2026-10-13);
## State 2026-11-04 and, in games/el_capitan_trueno_build.md, ## System map describe what
asm/trueno_hooks.asm (2494 lines) does now. The graphics table and the build recipe moved to that file.

| Output | Status |
|---|---|
| Trueno.nex (plain, `--tail 0xA6C9`) | boot sim OK; runs in MAME 0.289 (title menu, key 1 starts, played by the contributor) |
| Trueno.nex / _immortal / _sword / _immortal_sword (release 1.2: multi language, both colourings, 28 MHz) | boot sim OK; tested by the contributor in MAME 0.289 (the variants were played; the contributor's own start-to-end run of 1.2 is still to do); differential verify NOT done; hardware untested |

## Snapshot (inspect)
PC 0xEEEE = ISR entry (title menu; DI, IM 2, I=0xED, table 0xED00-0xEE00 all 0xEE -> 0xEEEE JP 0xA1CB).
SP 0xFFF6 (title); in game SP ~0xEECC. Printer buffer used (0x5B02-0x5B63 read first).

## Start-up tail
Default places failed: printer buffer used -> converter put the tail below SP (0xFF97; 0xEE6D for a
frame-300 snapshot), above 0xC000, where the stub's own bank 10 sits; the tail's OUT 0x7FFD maps bank 0
back and the tail vanishes (choose_tail_addr refuses >0xC000 only for 128K; nextboot.check catches it:
"boot did not reach PC 61166"). Fix: `--tail 0xA6C9` - scan of the whole RZX: 0xA6C9-0xAAA2 write-first
(986 bytes; init code later reused as a buffer).

## Render (from the RZX, frames 1-3000)
- Back buffer: pixels 0xF2E0-0xFFFF (3360 = 30 cols x 112 lines, the play window), attributes
  0xF13C-0xF2DF (30 x 14). Attr buffer reset each render from 0xEF98 (LDIR 420 at 0x88A7).
- Copy to screen: 0x8915 (unrolled LDI 0x896D-0x89A9 pixels, 0x891D.. attrs), every 2nd frame;
  pixels to 0x4721.., attrs to 0x5841...
- Scenery into the buffer: LDD loop 0x88DC-0x8910 (writes 0x88FE-0x8906), attrs 0x88B0.
- Figure plotter (candidate): 0x85FA-0x8628, masked: buffer byte (BC) saved to (DE), AND (HL),
  INC H, OR (HL), back to (BC); self-modifying (writes at 0x860A inside JP 0x8609). H = 0xEE set at 0x85EF.
- Figure attributes (candidate): 0x842C LD (HL),A into the attr buffer (skips if bit 7 of A set).
  Probable clash source.

- Figure entry: 0x82DF (IX = 8-byte descriptor: +0 frame, +1 x, +2 y, +3 flags: bit 0 visible,
  bits 4/5/7 used) -> 0x82E6 CALL 0x844D (plot: 0x8462 CALL 0x8254, 0x8514/0x85BB/0x85CD set-up,
  per-row loop 0x85E8/0x85EB/0x85F6, then attrs 0x83D8 -> 0x840F -> 0x841A -> 0x842C).
- Callers: 0x8A56 (IX 0xE728, 12 x 8 bytes) and 0x8A61 (IX 0xE6C8, 12 x 8) via 0x8A71; composite
  figure 0x8ABC (IY 0xE644; parts from a table at HL: frame, ?, dx, dy -> temp descriptor 0xE600)
  via 0x8AF4 - probably the hero in pieces. Also 0x8A7F (IY 0xE7C2, 6 x 40 bytes) -> 0x8AC0.

## Render order and depth (free run of an RZX frame-5000 snapshot)
- 4-frame cycle (12.5 fps): attrs reset 0x88B0 -> restore 0x8902-0x8906 (~210-260 bytes, under the
  figures) -> figures 0x8600.. with attrs 0x842C. Nothing writes the buffer after the figures.
- Foreground (bushes in front of figures) is done INSIDE the plotter: 0x872C builds the row code at
  0x85FA from a bit string at IX (per byte column: draw = AND/OR snippet from 0x87A4, skip = INC DE /
  INC L from 0x879B). Frame 2160: a monster is cut exactly at the byte column where a bush starts.
  IX = foreground cell map at 0xEF60 (set by 0x87A9: IX = 0xEF60 + ((y-68)&248)/2 + (x-16)/8,
  bit = 0x80 >> (x&7); x in byte columns from 16, y in lines from 68): 4 bytes per cell row, bit 7 of
  byte 0 = window column 0; set bit = foreground, the row code copies the save-under byte only
  (figure hidden in that cell). 0x872C emits 3 columns per row, IX += 4 per cell row. Checked on
  frames 2000/5000: bits = the bushes; rows 12-13 all set = the red grass strip. Rows 14+ = other data.
  Built once per screen at 0x6410 (end of the screen builder 0x63F8): 56 bytes (14 rows) packed from
  bit 7 of the per-cell bytes at 0xE940 (14 x 32), RET at 0x6424. Other references to 0xEF60: 0x87BD
  (the plotter), 0xA6A4 (init area). Not yet proven: nothing else writes the map during a screen.
- Mask/graphic rows are prepared in 0xEE40.. (mask, 0x86B0, source 0xAB6B self-modified) and 0xEFxx
  (graphic, 0x86FB, source 0xAB63) before each row; the plotter does AND (0xEExx), OR (0xEFxx).

## Sprite design (2026-10-13)
- Window buffer is 30 columns x 112 lines (14 cell rows), row-major, 30 bytes per line (the copy
  0x8915 does 30 LDI per line); attrs 30 x 14 = 420. (Earlier "28 x 120" was wrong.)
- ISR 0xA1CB runs a task table at 0xA142 (8 words; in game only 0x8865). 0x8865: if bit 0 of
  0xE608 is set, copy buffer -> screen (pixels 0x8915, attrs from 0xF13C), set bit 1, reset attrs
  0xF13C <- 0xEF98 (420), then restore scenery under the figures from the list at (0xE604)
  (restore loop 0x88BA; list starts at 0xA6C9 = our start-up tail place, write-first, fine).
  (0xE60B) = 34: clear mode, buffer zeroed by PUSH instead of the restore.
- Plan: leave the plotter untouched (game memory identical); at the copy use the clean attrs
  (0xEF98) instead of 0xF13C; figures as sprites whose opaque body = the game's own mask, so they
  cover the figure pixels the plotter left in the ULA exactly. Measured on f5000 (blank buffers
  0x00 / 0xFF): the mask is a ~1 px outline built in pixel pairs; a morphological body (demo:
  fill(close1(dilate1(ink)))) leaves 49 mask pixels uncovered -> masks must come from the game.

## Heroes (contributor, 2026-10-13)
- Three heroes, the player switches: the Captain, Crispin (small, blond; the only one who climbs
  ropes), Goliath (big; too heavy to climb). Composite entry 0x8AC0 with IY = object (hero: IY
  0xE644, set at 0x8ABC; enemies 0xE7C2 + 40k from 0x8A8F); the plotter corrupts IY and the composite
  does not restore it between parts, so IY at 0x82DF says nothing after the first part. Hero frames
  in the RZX (build/hero_poses.py, 72 poses, snaps/hero_poses2.png): 0-3 (death explosion), 4,
  13-16 (Crispin walking), 73, 74 (Crispin climbing a rope - the contributor's correction), 44,
  53-56, 80-91, 93-98, 123, 124 (the Captain: torso + legs/arm pairs), 75, 76 (Goliath).
  gfx/heroes_clean.png labels 73/74 as Goliath by mistake (labels only; cells are read by layout).
- Hit flash: every figure blinks normal / red ink (see trueno/NOTES.md); the contributor redraws the
  heroes cleanly (1-pixel black outline, filled insides; gfx/heroes_clean.png), hit = inverted.

## Controls and modes (contributor's RZX + his notes, 2026-10-13)
- Keys (Teclado): O left, P right, Q up, M attack/throw, 2 Crispin, 3 Goliath, 1 back to the menu
  (contributor); the Captain's key not known yet.
- Menu "5 COLOR ON": removed from the title menu (contributor, 2026-10-13; recipe 5d).

## Contributor's decisions (2026-10-13)
- Sprites: the hero, all enemies, coins/items - everything that can be done without clash.
- Colours: as in the game for now (may change later).
- Depth: the game's own rule - bushes and other foreground stay in front of the figures.

## Open
(2026-11-04; the 2026-10-13 questions about the plotter, the figures and the decisions are answered
in ## Render, ## Graphics and ## Contributor's decisions.)
- Differential verification: none yet (## Verification plan). Only the contributor's play in MAME 0.289
  and his check scripts (cover, order, no-draw, patterns, screen reads, buffer reads) back the build.
- Engine files: done in 2026-11-04 as far as they go: nexclash/trueno.py (detector, plain build at tail
  0xA6C9, boot check; auto() returns False and says "sprite build NOT VERIFIED"), the profile
  (asm2profile assembles the BASE build only: the -DMULTI / -DGAME_MHZ / -DLIM / -DTITLE_MHZ switches
  of the release are not in it), the record, the line in nexclash/engines.py. Missing: the sprite build
  inside the toolkit, verify() and unit_tests() (both raise NotImplementedError).
- Hardware: nothing run on a real Next. The copper shake, the Layer 2 priority bit and the NextReg
  0x07 switching at 28 MHz are MAME-only results.
- Cheats and patches: a new standard for such files is being discussed (2026-11-03, Dean takes part);
  the contributor made `Capitan Trueno, El (1990)(Dinamic)(ES).pok` for the original 48K game
  (Fuse format, three trainers, original bytes checked against the snapshot; not tried in an
  emulator). Wait for the standard before choosing a format.
- Hooks: the alt ROM had 0x3BF6-0x3C08 and 0x3CC0-0x3CC8 free (multi + fast build, 2026-10-31; later
  edits not rechecked); more growth needs another move of bodies into the hook page.
- Page budget: the fix-cell table (pages 60-67) is full; 3.2 KB left.

## Maintainer check (2026-10-14)
- Archive received; reference files were in specnext/reference/el_capitan_trueno/ (contributor's
  project in its contributor/ folder, rebuild steps in contributor/REBUILD.md). Dean removed that
  folder from specnext main (2026-10-14 12:28); the files remain on specnext branch
  contrib-el-capitan-trueno (commit 309eabf) - restore from there to work on this game.
- Every sprite build rebuilds byte-identical, with tk 0.1.4 and with nexclash main.
- Plain: `--tail 0xA6C9` gives ca49e0f4 (boot sim OK); the earlier listed 4b415b4c was the
  default-tail build, which does not boot (docs/VERIFICATION.md).
- Still open: engine module + profile + record (recipe step 6), per-call differential verification,
  unit tests, negative control, hardware. nexpatch: maintainers' decision pending (private for now).

## State 2026-11-04 (what asm/trueno_hooks.asm does now; the 2026-10-14 archive had 1412 lines)
Features added since the archive, each checked by the contributor in MAME 0.289 (software proof: none):
- Pause window, access-code screen and menus are drawn in the ULA: Layer 2 and sprites are hidden while
  they are up (e_mnu, s_end); the access-code screen clips Layer 2 to the panel (lines 136-191) instead
  of switching it off, so the three portraits stay.
- Screen shake and the pause use the copper (list `clist`, mode 11, restarted every frame): shake moves
  Layer 2 by 8 lines for lines 24-135 only; the pause turns Layer 2 off for lines 16-135.
- Foreground and scenery clash: bushes (Layer 2 with priority), then "fix cells" (scenery cells redrawn by
  the contributor on a sheet: walls, battlements, windows), explosions, hit shapes, a dragon replacing
  the unused "big rat", the pause sword as sprite 0.
- 28 MHz with a frame limiter (e_lim at 0x89FA, 4 interrupts per render as the original's usual pace) and
  e_dly at 0xA18F (CPU-timed delay loops run at 3.5 MHz): the dragon's 12-frame renders and the other
  slowdowns are gone; the original pace stays.
- One build with a language menu (ES / EN / RU, item 6) and a sprite-colour menu (item 5, COLOR ON/OFF,
  start ON) written into the game's own title menu; Russian font as 24 extra glyphs in the alt ROM.
- Cheats as tiny data patches, each its own option: immortality (1 byte at 0x7A1F) and the Captain's
  best sword (12 bytes, the four readers of 0xE634), never overlapping; the ORIGINAL game's .pok file
  has the same two plus infinite lives (0x9BA0).
- Three portraits on the panel at once (inactive ones grey), the title screen from the snapshot plus the
  patch cells in Layer 2, castle wall / back battlements / windows redrawn.
- An ORIGINAL bug fixed (multi build): after the dragon fight the pause window came out striped (draw list
  0xE8B2 doubles as the dragon's object record); e_pwin saves and restores the 24 bytes.

## Verification plan (not started; this session's proposal, 2026-11-04)
Classify every hook site first, then verify each class its own way:
1. Logic-neutral (figure plotting, explosions, hit shapes, fix cells): the usual differential test over
   trueno1.rzx (53542 frames); the game's memory must equal the original's outside the never-read back
   buffer (0xF2E0, attributes 0xF13C), as in the first prototype.
2. Screen-only (Layer 2, copper, portraits, title): compare what the hooks WRITE (map and palette
   bytes) against the model, not the game's memory; the contributor's check scripts for cover, order,
   no-draw, patterns, screen reads and buffer reads already do part of this (10,508 renders).
3. Deliberate changes (menu, language, colour menu, cheats, pause sword, limiter, 28 MHz): outside the
   recording's reach. The recording replays only the base build (3.5 MHz, no menu items, no cheats);
   verify THAT build, then test the variants by unit tests on the changed routines (menu dispatch,
   text records, cheat bytes at their sites, one negative control per class).
The limiter and 28 MHz change timing, so the recording cannot drive them: build the base for the proof
(-DGAME_MHZ=0, no -DMULTI) and say so in the record.

## Lessons
- [doc LEARNINGS 1.4] Reading a NextReg (select on 0x243B, read on 0x253B) with interrupts on is a race: an ISR hook selects another register between the OUT and the IN, the read returns that one, and a hook that writes the value back sets it as the CPU speed (Trueno: the 28 MHz menu fell to 3.5 MHz and missed key taps). Observed in MAME; after reading with interrupts off (IFF restored) the menu ran 8/8 steps and 20/20 taps at 7 MHz. Same race for test scripts that poke 0x243B while the game runs.
- [doc LEARNINGS 2.7] MAME 0.289 Lua: stop the machine with emu.pause() (manager.machine:pause() does not exist); poking ports or NextRegs from a script while the game runs races the ISR, so pause first. Observed.
- [doc LEARNINGS 2.5] A fault seen only in the patched build can be an original bug: the pause window came out striped after the dragon fight. The recording (no hooks) shows the same at frame 48898, screen 34: the pause window's draw list at 0xE8B2 doubles as the dragon's object record (IX 0xE8B2, script pointer left at 0xE8B6). Found by running the window routine in a simulator on memory read from the emulator (patch sites put back) and bisecting against the expected memory. Run the original unhooked to the same state before blaming a hook; fix by saving and restoring the 24 bytes around the window. Demonstrated.
- [local: met in this game only so far; the detail stays here until a second game meets it] When the alt ROM is full, hook bodies move to the hook page behind 5-7 byte stubs; dead game areas can hold tables once a scan proves no real reference (a match inside a data table is not one). Trueno reused 12 of the 22 bytes of the old colour handler and the old menu list, and put the plotter's all-0xFF map at the ROM top. Demonstrated by the code scan; MAME run.
- [local: met in this game only so far; the detail stays here until a second game meets it] Adding items to the original menu: its dispatch matches the key against the first code of each item, so every new item must start with its digit; a switchable language is a set of entries (address, length, bytes) copied into the game's RAM at the switch, then the menu and credits are printed again after the screen pixels are wiped (the title screen holds text only). New glyphs (Russian font) go in as extra characters. Demonstrated in MAME: 8 steps, state bytes, text in RAM and screen pixels equal to the simulator's print.
- [doc LEARNINGS 2.1f] Delays timed by CPU instructions (a DEC DE loop: menu, pause, access-code screen) become far too short at 28 MHz and a frame limiter does not touch them. Hook the delay routine, run its loop at 3.5 MHz and set the speed back (Trueno 0xA18F). The same for the beeper: per-note speed switching was heard as noise, so the whole effect runs at 3.5 MHz (hook at the effect entry 0xA43D); the access-code picture shift 0x5E0E (CPU-timed) runs at 3.5 MHz too. Observed in MAME: menu, pause and sound match the original; other inline DJNZ delays may exist, none noticed in play.
- [local: the sheet pipeline is built for this game's cell tables; the detail stays here] Scenery redrawn by a human on a sheet: pass the whole set of what the build copies unchanged into Layer 2 to the human first (the white walls were never on a sheet because the hooks copy every foreground cell whole). One edited cell goes to every identical tile (not mirrored); a second rule takes every cell that LOOKS the same (windows cut by bushes); pink on the sheet = see-through. Per-screen blocks are packed biggest first, and a block may cross one page edge when two MMU slots are mapped. Observed over several rounds with the contributor, in MAME.
- [doc TECHNIQUES 2.1] A short copper list does both jobs of a pause and a shake in a back-buffer game: shake = Layer 2 Y scroll 8 lines for a band, pause = Layer 2 off for the window's lines; every instruction is written whole by NextReg 0x63, and a hook that rewrites the list takes effect at the next frame. MAME only (hardware untested).
- [local: the panel hides a portrait by attribute 0 and keeps its pixels, so the dim state is drawn from the stored pixel and attribute pair per cell] Trueno's three portraits at once; only changed cells are drawn; 8100 of 8192 bytes of a page.
- [deferred Open: reconsider when Dean's cheat and patch standard is published] Cheats as separate one-purpose data patches (1 byte / 12 bytes) that never touch the same bytes can be ticked in any combination on a patcher page; a .pok for the original game was made the same way. Format wait.

## Friction
- reuse: [deferred Open: reconsider when a second back-buffer game needs the same chain] The catalogue chain (play the recording, hash the graphics at each frame end, call the game's own plotter on 0x00 and 0xFF buffers, pack 4-bit patterns) was written from scratch for this game; it is generic for plotter-based games.
- retries: [doc LEARNINGS 1.4] The NextReg read race cost more than one attempt; the test script's own pokes while the game ran may have added to the drop.
- environment: [doc LEARNINGS 2.7 + tools/sjasmplus/README.md] MAME Lua: manager.machine:pause() does not exist in 0.289; emu.pause() does. Also on Windows tools/asm2profile.py finds no bundled assembler (the pinned binary is Linux x86-64) and would clone and build sjasmplus from GitHub; this session called asm2profile.run() with an sjasmplus.exe that reports 1.24.0 instead (no network, nothing outside the project).
- hand-rolled: [deferred Open: reconsider when the verifier is written] The cover, order, no-draw, pattern, screen-read and buffer-read checks were separate scripts, not toolkit commands.
- scratch: [local: dropped, tied to this game's pause window and menu addresses] Scratch scripts for the pause window bisection and the menu run were not kept.

## Technique use

## Stage log
- 2026-10-13 .. 2026-11-04 (contributor's stages A to 4, one prototype + releases 1.0 to 1.2): ~3 weeks of sessions, the contributor tested everything in MAME 0.289; the differential proof (stage 3) was never done. Knowledge refresh against nexclash main at 2026-11-04 (v0.1.5 release, main commits of 2026-11-03).
- 2026-11-04 maintainer merge (first user contribution, made against package 0.1.3): files applied with LF endings, generated STATUS / VERIFICATION rebuilt by `records views` (the contributor's copies not taken), asm2profile reproduces the profile (unchanged), plain rebuilt with `auto` = ca49e0f4 boot OK (engine detected), canary PASSED, lesson tags checked against where the lines landed (NextReg race is in LEARNINGS 1.4), Windows sjasmplus note added to tools/sjasmplus/README.md; game files to specnext/reference/el_capitan_trueno/.

