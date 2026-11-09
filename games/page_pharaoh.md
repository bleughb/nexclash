# Page and the Curse of the Pharaoh (T.D.F. micro-visions, 2015, 48K-128K)

## Next session
Stage: 3 done for default and Enhanced; published as .nxc 1.0 (nxc 05d3127, 2026-11-08) and registered on main: `auto`, engines.py, record docs/records/page_pharaoh.json. Hardware: untested. Not yet played by the owner.
Inputs: `Page and the Curse of the Pharaoh (2015-01-23)(T.D.F. micro-visions)(48K-128K).tap`, MD5 5237d25deb5ff67f461c7de61e5d2df3, the published patch's target (TAP1). Start state `page_pharaoh.z80` (MD5 5d884aa2): that tape loaded by SkoolKit's tap2sna to the game's USR 32000 (`-s 32000`); derived game data, never in this repo. Review runs: runs/page_pharaoh/release-20261108 (default), release-20261108b (Enhanced).
Build: `python nexclash.py auto page_pharaoh.z80` writes page_pharaoh_sprites.nex and, with `page_pharaoh_loading.scr` (the tape's screen) beside the start state, page_pharaoh_sprites_loading.nex = the published default bare build (430b6184). With `page_pharaoh.256` (the Spec256 set) and `page_pharaoh_palette.json` (its 256 colours) beside it, both never in this repo (MD5s in the record), it also writes page_pharaoh_enhanced.nex and page_pharaoh_enhanced_loading.nex = the published Enhanced bare build (3c710b98). Every build boot-checked; with `--rzx a1.rzx --rzx rooms.rzx` both modes' replays, their ABI cases and broken builds.
Pending: owner's play; hardware checklist below; after it, a mock-up step for the improvement ideas in release-20261108b's NOTES.md.

## Facts
- Authorship: David Pagett, T.D.F. micro-visions, (c) 2015 on the game's loading screen; a homebrew release (tape dated 2015-01-23). No terms are stated in the game, on the tape or beside it in the archive. Nothing of the author's is in this repo; the patch carries only what patches normally carry (the loading screen and the 407 bytes of start state not on the tape).
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

Enhanced (`page_pharaoh_enh.py`, off by default, a menu option; the default mode's bytes unchanged): the Spec256 set by Ynicky, as it is. Layer 2 holds the 8-bit value the set's planes would hold: tiles overwrite; figures and items XOR value by value, which is what XOR on eight planes is. So the unmasked figures, the risk named at the mock-up, need no composed overlay: value FF is the transparent colour and the ULA shows the attribute's colour through it. Figures do mix with painted scenery where they overlap, exactly as on Spec256. The game's ULA+ palette is off in this mode, as Spec256 has none. The room's draw runs at 28 MHz in a K window, closed at the game's next CALL; figures in the set are stored in pre-shift order, expanded to screen order in the tables. The menu shows the overlay, as its text and icons all go through the tile hook and the set paints its icons; the game over and winning screens stay plain ULA, as the set has no colour on them.

## Known issues
- Pace: see the review run's NOTES.md. Frame locked: whole runs within 0.32%, and Enhanced's are in the same range.
- Ropes and pick-ups take a cell's ink, as in the original (default mode).
- Enhanced: figures mix with painted scenery, as on Spec256 itself. A set colour on exactly the transparent value moves one blue step.

## Evidence (review run runs/page_pharaoh/release-20261108b for Enhanced, release-20261108 for the default, JNext 1.1.104; emulator and simulator only)
Replay with R compared at every hook, ABI, deliberate negatives, pace over five levels, soak, flicker and the real loader: in that run's NOTES.md. Levels other than the first are reached by a test poke.

## Hardware checklist
Nothing has run on a Next. To check: ULA+ on the core (the palette above), start-up from the tape through the loader, keyboard, Kempston and Sinclair, AY music, a death, a level change, game over and the menu, both cheats, a 1MB Next (top bank 47).

## Technique use
- patch.pace-limiter: used: one K window, round the room draw, in both modes.
- patch.preserve-r: used: R compared at every hook.
- patch.restore-speed: used: the incoming clock comes back after every hook.
- patch.whole-altrom-image: used: Sinclair's ROM with veneers only.
- verify.update-locked-pace: used: state in lockstep; a test-only copy reads the input once an update.

## Lessons
- [local: XOR overlay] A game that XORs figures needs no place list: toggling on the overlay keeps it exact through every erase, draw and redraw.
- [local: input phases] Two reads in an update at different phases of the frame cannot both be raced: a read near the frame boundary falls either side of it. A test-only copy that reads once an update gave lockstep at every update; applying input just after that read is then safe.
- [local: frame-locked game] A game that waits for FRAMES needs no limiter round its plots: the wait takes up the time.

- [local: unmasked XOR on values] XOR needs no masks on Layer 2 when the buffer holds the set's own 8-bit values: XOR on eight planes and XOR on the value are the same operation. Test a named risk before designing round it: the composed overlay this page's mock-up note asked for was not needed.
- [local: K multiply saturates] hlib_mul8 saturates at 0xFFFF, so a K that looks too big has no effect at all: a long window showed no response to K until it came down below saturation.
- [local: Layer 2 LDI at column 31] LDI's DE carries out of column 255 into the next row: a tile at the right edge needs its last byte by hand. The whole-picture replay model caught it; hook registers and RAM alone did not.
- [local: negative aimed at a path the recording never takes] "XOR made plain" mutated the items' loop, which never undraws in the recording, and passed the replay. Aim each negative at the path the recording runs, and a MISSED one is a finding about the negative or the recording.

- [local: compare every screen with the set] Level frames against the set's emulator matched, so the menu wasn't looked at, and its painted icons were missing until the overlay was shown there. Sweep menus and end screens too, not only play. Before showing an overlay on a screen, check the screen holds no ULA bit the overlay lacks.

## Friction
- reuse: [none: the shared libraries and Game Over's hook structure were enough]
- retries: [local: pace start keys] A start key still held when play begins reads as input. Keep it short.
- environment: [local: palette] The simulator and emuspec256 show the plain palette; only JNext shows what a Next shows.
- hand-rolled: [local: review scripts] Fixture, cheats and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: engine, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
- 2026-11-08 Stage 3: Enhanced built on the same review branch, Spec256 colours faithfully; proofs in release-20261108b; waiting for the owner's play.
- 2026-11-09 Upstream: `auto`, engines.py line, record 250 (views rebuilt); main rebuilds the published .nxc 1.0 bare builds, default 430b6184 and Enhanced 3c710b98.
