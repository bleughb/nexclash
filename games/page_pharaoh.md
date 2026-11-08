# Page and the Curse of the Pharaoh (T.D.F. micro-visions, 2015, 48K-128K)

## Next session
Stage: 4 (owner's play, then Enhanced). Hardware: untested. v1.0 review build, not published, not pushed; not wired into `auto`, `engines.py` or a record: that comes when it goes upstream after the owner has played it.
Inputs: `Page and the Curse of the Pharaoh (2015-01-23)(T.D.F. micro-visions)(48K-128K).tap`, MD5 5237d25deb5ff67f461c7de61e5d2df3. The start state is the tape loaded by SkoolKit's tap2sna to the game's USR 32000 (`-s 32000`), kept in the review run; the tape block's screen is the loading screen.
Build: `page_pharaoh.build(start.z80, nex)`, then the review run's `work/pkg.py`, a TAP1 target of the plain tape.
Pending: the owner's verdict on the mock-up; Enhanced stops there.

## Facts
- A later homebrew. A BASIC loader, a screen and one code block, unprotected, so TAP1 takes it: 407 bytes of the start state are not on the tape.
- IM 1 and the ROM's handler, interrupts on. The main loop plots two groups of six figures on alternate frames, each after a wait for FRAMES (7F5F). A frame-locked game: 25 updates a second.
- Figures are XORed straight onto the ULA (8C63, 8C4E, 8C5D) from a table at 8F1A. No mask and no attribute: a figure takes the ink of the cell it is in. They are white in the open, and turn yellow, green or orange in a cell of scenery, or vanish in the fire.
- At start the game writes the ULA+ palette (7F9B, ports BF3B and FF3B): on a Next and in JNext the walls are pink, the jungle lime, the fire orange. That is the original's look on this machine. SkoolKit's simulator shows the plain palette.
- AY music and beeper from the main thread (8070, 7F2E), not in any hook.
- The game reads R once (82B3).
- The input is read twice an update, at different phases of the frame (8A26 in 7F2E).

## Decision
Layer 2, not sprites: each plot is repeated on the overlay by toggling (255 <-> 7), so the overlay is the XOR of what the game has plotted, without storing any figure's place. The ULA is not touched. Layer 2 pages go in slot 7 because interrupts stay on and the ROM's handler needs slot 0. Rooms clear the overlay, and the room's own drawing runs at 28 MHz in a K window to repay that. A ROM CLS hides it.
No figure colours chosen: white is the figures' own in the open. No outline.
Ropes (846F) and pick-ups (87AB) are not on the overlay: they are thin, still things that keep the cell's ink as in the original.

## Known issues
- Pace: see the review run's NOTES.md. Frame locked: whole runs within 0.1%.
- Ropes and pick-ups take a cell's ink, as in the original.

## Evidence (review run runs/page_pharaoh/release-20261108, JNext 1.1.104; emulator and simulator only)
Replay with R compared at every hook, ABI, deliberate negatives, pace over five levels, soak, flicker and the real loader: in that run's NOTES.md. Levels other than the first are reached by a test poke.

## Hardware checklist
Nothing has run on a Next. To check: ULA+ on the core (the palette above), start-up from the tape through the loader, keyboard, Kempston and Sinclair, AY music, a death, a level change, game over and the menu, both cheats, a 1MB Next (top bank 47).

## Technique use
- patch.pace-limiter: used: one K window, round the room draw.
- patch.preserve-r: used: R compared at every hook.
- patch.restore-speed: used: the incoming clock comes back after every hook.
- patch.whole-altrom-image: used: Sinclair's ROM with veneers only.
- verify.update-locked-pace: used: state in lockstep; a test-only copy reads the input once an update.

## Lessons
- [local: XOR overlay] A game that XORs figures needs no place list: toggling on the overlay keeps it exact through every erase, draw and redraw.
- [local: input phases] Two reads in an update at different phases of the frame cannot both be raced: a read near the frame boundary falls either side of it. A test-only copy that reads once an update gave lockstep at every update; applying input just after that read is then safe.
- [local: frame-locked game] A game that waits for FRAMES needs no limiter round its plots: the wait takes up the time.

## Friction
- reuse: [none: the shared libraries and Game Over's hook structure were enough]
- retries: [local: pace start keys] A start key still held when play begins reads as input. Keep it short.
- environment: [local: palette] The simulator and emuspec256 show the plain palette; only JNext shows what a Next shows.
- hand-rolled: [local: review scripts] Fixture, cheats and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: engine, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
