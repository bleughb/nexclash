# Scooby Doo in the Castle Mystery (Elite, 1986, 48K)

## Next session
Stage: 4 (owner's play). Hardware: untested. v1.0 published in .nxc 1.0 (default and Enhanced); on main with `auto`, its `engines.py` line and record `docs/records/scooby_doo.json`.
Inputs, beside the snapshot (never in this repo): `scooby_doo.z80` (MD5 8a82e06f6829a2a1c30781491cfbc42e); `scooby_doo_loading.scr`, the tape's `ScoobyDoo2` block, first 6912 bytes (56499a0d); for Enhanced the Spec256 set `Scooby-Doo.256` (e22c336b) and emu256's palette `emu256_datos.js` (30a8edfa; or `$EMU256/datos.js`). Without the set, auto builds the default only.
Build: `nexclash.py auto scooby_doo.z80 --no-record --no-nxc`: `scooby_doo_loading.nex` 6c52221e and `scooby_doo_enhanced_loading.nex` a81865ab, the published bare builds (without the screen 994ad69a, 37d3a6c4). With `--rzx` it replays Enhanced on each recording, the ABI cases and 14 broken builds.
Pending: the owner's play; his call on the default's small clash below.

## Facts
- No 128K release in the archive folder: all are the 48K game. The Spec256 set "Scooby-Doo" is this game, Castle Mystery (same screens, same code in place): Scooby-Doo and Scrappy-Doo (Hi-Tec, 1991) matches 10% of its bytes.
- The snapshot is a loader state: BASIC running, `RANDOMIZE USR 16384`. Pokes into the code at that state hold in play.
- Main loop 6F4D: wait until 5 frames have passed, HALT, copy the back buffer (844B: bitmap 9FCC, 128 rows, attributes AFCC, 16 rows), restore figures (92A7), logic and plots (7320). So the update is locked to 5 frames unless the work overruns.
- Scooby himself is composited during the copy (837E: `AND (IX) / OR (IY)` in columns 14-17); the others are plotted in the buffer with a save-under list at 969B (92xx).
- Level table 6290, 14 bytes a level; attributes 61F4/61F5. Levels 1, 2, 3 in one colour pair for the corridors, with brick strips in another; every fourth level (4, 8) has rooms with red jars and a blue wall.
- The ISR at FDFD plays sound by calling ROM BEEPER (03B6) from the interrupt.
- The game reads R (75B6, 7605, 860D).
- Keys (95F5, table 95E6): X right, Z left, O up, K down, P punch, U pause, Y quit. Menu: ENTER starts, J then K Kempston (or I, C), P practice.

- Spec256 set "Scooby-Doo", painter Armando Quaranta (readme). Real match 100%: sprite table B404: 71 sprites stored the same (7,368 bytes), 50 mirrored (6,552 bytes), none other. The first look's 61.5% came from sprites the game mirrors in place at run time (8F1D, table FC00, flag in bit 7 of the entry's last byte). Bytes that differ otherwise: variables, the save list, the table's flags: no graphic.
- The set has a background image; over the window it is one colour (B9, dark grey), behind pixels of value 0 and of 255. Values 192-254 do not occur in play, so no pixel in the window depends on the attribute.
- The update is 5 frames but copy plus logic often overruns: the original's idle before the next copy has a median of 2-5 ms. Its copy takes 30 ms and with the sound's share in the interrupt 46 on average.
- The interrupt runs the sound as a coroutine with interrupts on: a note holds the main code off for many frames.

## Enhanced
Off by default, on the menu. The play window (256 x 128) on a double-buffered Layer 2 over the game's own ULA picture.
- The canvas holds the scenery only, 8 pixels per RAM byte at page 3 + A/1024, offset (A & 1023) x 8, from the set's planes. Each sprite is there both ways round, the mirrored way 24 pages up; bit 7 of its table entry says which, so a flip costs nothing.
- Interrupts decide the design: the handler beeps on its own time, so nothing may run at 28 MHz or with the slots changed while one can come. Write hooks (columns, rows, plots, blocks) run at the game's clock, change only slot 1 and put a record on a queue.
- All the colour work is at 8464, just after the HALT: the game's own copy at 28 MHz, then the queue on the canvas, the canvas to the back buffer by DMA, this update's figures and the player plotted on it. When the interrupt's line is near, the work stops at a safe point, gives the game back its slots and clock with interrupts on, and resumes after it. The flip waits outside the window's rows, at the next hook if need be.
- The game's scroll chains also run at 28 MHz past the interrupt's line: 21 ms down to 4, which pays for the colour work in the busy updates.
- The game restores its figures at the start of each update and draws them at the end, so its buffer's figures are never on the canvas. The picture is the buffer's own unless the game draws a permanent block over a figure in one update; the replay compares every published pixel against a plane model.
- Fits a 1MB Next: top bank 47. No game logic changes.
Left in the original colours, listed in the .nfo: panel, title, menus. The set paints the panel too; not built.

## Decision
The play area is one colour pair, with figures in the cell's ink. A figure over a brick strip, a door pillar or a jar takes that cell's ink and paper. Measured by the figures' boxes (work/overlap.py): 0.35% of figure cells in level 1, 0.13% in level 2, 0.08% in level 3, 3.6% in level 4's rooms. No hook in v1.0: the patch is Sinclair's whole 48K ROM, no game byte changed, and no clash fix is claimed; the menu line reads "Original colours". Decided with Enhanced: nothing changes in the default; its bytes are the first review build's. Enhanced has no clash in the window. Taking the layer into the default would need a colour for each figure that the game does not have (the figures have no attribute of their own), per-cell colours on the canvas, and 19 hooks in what is now a build with none, against 0.08% to 3.6% of figure cells. The owner can overrule it.
No outline: Scooby and the ghosts carry their own masks; they do get busy against the panelling. An outline would need the same layer.

## Known issues
- Default: the small clash above.
- Enhanced: outside the fixture R reads differ from the original's once a run's timing differs, since the game's wait loop counts into R: other enemies, the same game.
- Runs without the test fixture leave lockstep, because the game reads R; the fixture reads R as a constant in both arms.

## Evidence (review run runs/scooby_doo/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, nexclash.pace with input applied after the game's read (732F), fixture on both arms, 800 updates in lockstep at every update, 3 seeds at each of levels 1, 2, 4: the update is frame-locked, see the review run's NOTES.md. rom_paths over 26.11's ROM3 on two recordings (a clean run, levels 1 to 9 by test pokes): every byte the game runs is as recorded, the tail never read before written. Boot exact with and without NEXLOAD, R included. Broken builds caught: R off by one, clock left at 28 MHz, a game byte changed, Next ROM3 copied as the alt ROM, no alt ROM at all. Soak 15 emulated minutes, flicker, real .NEXCLASH loader on a private NextZXOS 26.11 card copy (default, each cheat, all): the review run's NOTES.md.

Enhanced (review run runs/scooby_doo/release-20261108b, exact bytes `.nex` a81865ab): pace at levels 1, 2, 3, 4, 3 seeds, 800 updates in lockstep with the fixture on both arms: whole -0.95 to -0.00%, quiet thirds -0.04 to +0.11%, busy thirds -2.84 to -0.05%, slowest 20 updates up to +2.80%, 3 of 480 windows over +2%; interrupts 50.00 a second in both arms, longest gap 20.0 ms. Replay of 11 recordings, 33,297 frames, 32,758 hooks with R, 175,964,160 published pixels against the plane model, no failure; 14 broken builds, ABI 704 cases. Soak, flicker, real loader in default, Enhanced and with cheats: its NOTES.md.

## Hardware checklist
Nothing has run on a Next. Enhanced also: the window against the panel, no tearing, beeper pitch through the interrupt gaps, DMA with cycle length 2 on a real core, line 248 as the interrupt's line, pace against the 48K original. To check: the BASIC loader and its BEEP, title, keys and Kempston, beeper in play, one death, a level change, each cheat, a 1MB Next (top bank 47).

## Technique use
- patch.whole-altrom-image: used: the build's only change; the BASIC loader's BEEP and PAUSE run on Sinclair's ROM whichever NextZXOS loads it.
- verify.update-locked-pace: used: lockstep runs with the input applied after the game's read.

- patch.preserve-r: used in Enhanced: every hook leaves R as the original; the replay compares it at each hook.
- patch.display-atomic-switch: used in Enhanced: two Layer 2 buffers, the flip outside the window's rows.
- patch.isr-deferral: no help: the handler must run on time for the sound; the work moves to where no interrupt is due instead.

## Lessons
- [local: match by behaviour] A 61.5% byte match was sprites mirrored in place at run time. Walk the sprite table before calling a set unmatched.
- [local: read the whole set] The set's file has a background image past the planes: the mock-up's dark grey is not palette 0. Compare the first screens with the mock-up by colour count, not by eye.
- [local: mono model] A second plane model fed with the release's own mono bytes, checked against the real buffer and ULA, finds a missed writer at once; the colour model alone cannot.
- [local: DMA timing] In JNext 1.1.104, DMA with both ports at cycle length 2 took 3.6 T a byte against 12.5 with the reset timing. Program it.
- [local: look for what the original wastes] Pace was won by running the game's own 21 ms scroll at 28 MHz, not by polishing the colour work.
- [local: empty entries] A sprite table entry with no rows can hold the same address as a real one; a lookup by address must skip it.
- [local: masks are not clean] This set's graphics are not empty where the mask is clear: a skip on a clear mask drew wrong pixels, and the replay caught it.
- [local: nearly monochrome] A game's colour look can read as monochrome and still have a little clash: measure figure cells by attribute before saying so.
- [local: unsafe POKE] An archive POKE of an opcode byte can open a new instruction over the next bytes: 29479 turns CP 1 / JP Z into NOP / LD BC,nn / LD (HL),E. Read it before offering it.
- [local: menu keys] J opens a joystick menu; K there picks Kempston. A J alone leaves the game on keys, and a script that holds Kempston directions then looks like it plays while nothing moves. Check the sheet moves.

## Friction
- reuse: [none: nextboot, jnext, soak, flicker and pace were enough]
- retries: [local: start keys] The first pace run measured nothing: ENTER landed while the joystick menu was closing.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Fixture, cheats and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-09 Upstream: auto, registration and record on main; main rebuilds the published 1.0 default and Enhanced byte for byte.
- 2026-11-08 Stage 3 again: real match found, Enhanced on the review branch, proofs on the exact bytes; waiting for the owner's play.
- 2026-11-08 Stage 3: no-hook engine, clash measured, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
