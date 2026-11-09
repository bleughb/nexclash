# Comando Quatro (Zigurat / GameSoft, 1989, 48K, Spanish)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 05d3127) at the owner's request, not yet played by him. The clash fix is on by default.
Inputs: `Comando Quatro (1989)(Zigurat)(ES).z80`, MD5 47ff99afedc9f0af0030b63d1fa4d098; beside it, staged by the record, never in this repo: `comando_quatro_loading.scr` (the plain `.tap`'s 6,912-byte screen block, MD5 d5f1b3bd).
Build: `nexclash.py auto` writes `NAME_sprites.nex` (ffcd877f) and, with the screen, `NAME_sprites_loading.nex` (66563d3e), equal to `nxc.py PATCH GAME --bare` of the published patch byte for byte; each boot-checked with and without NEXLOAD. Without the screen it says so and builds the first only.
Checks: `selftest.py --game comando_quatro --verify`: replay of a1, a2 (to frame 22,000) and a3 with R, Layer 2 against the model and the bitmap, attributes against the clean copy, ABI cases and 12 broken builds on a1's first 5,000 frames. Pace, soak, flicker, beam audit and real loader are in Evidence, not in the repo.
Pending: the owner's play; hardware checklist (Kempston at 0x1F on a real Next); Enhanced (no source, rated MODERATE).

## Facts
- A 48K beeper game; interrupts off throughout play, title and its tune only under IM 2. The game reads R three times (A34A, A44C, A46F) for chance.
- Back-buffer composer: window of 28 columns by 14 rows at screen row 5, column 2. Pixels F0B0, attributes FCF0 (392 bytes), `AND mask, OR gfx` plots (B663), save list ECB0, one copy to the screen (EB0A) and a restore (B830) each pass.
- Clash: B7CF paints the figure's box in the buffer: `AND 0xB8, OR ink+bright`. The scenery in the box takes the figure's ink.
- The game has its own switch for this: key C (B9AF, "COLOR" in the redefine list) turns the painting off for figures with flag bit 4. Kept: those plots then stay in the cell's ink.
- Screen wipe (C731, C761): rows of the pixel buffer blanked from a table (C7F7), four copies a step; attributes unchanged; then DD18 clears the buffer and copies once.
- Text: menu (TECLADO, JOYSTICK, REDEFINIR), the key names when redefining, ACABADO ZONA n between zones. No text matters in play. The archive holds no English set.
- Joystick: the game reads Kempston at port 0xDF. A real interface decodes A5 only; in JNext that port reads 255, which the game takes as every direction and fire held. The build changes that one operand to 0x1F, the Next's Kempston port; nothing else differs with the keyboard.

## Decision
As Game Over and Army Moves: original bitmap on the ULA, every byte; attributes from a private copy taken before the pass's first plot; figure ink on a double-buffered Layer 2 in plot order, in the colour the game would have painted; opaque masks punch out what they cover. No outline: figures have their own masks. Plot, copy and restore run whole at 28 MHz inside K windows.
The wipe's row blanking also blanks the overlay's row (h_wrow). A direct clear of the screen (B153) hides the overlay.
For the length of the game's copy the clean attributes stand in its buffer (attrs_in, attrs_out), so a painted cell never reaches the screen. An earlier build wrote them over the work attributes after the copy: the wipe's copies, which do not wait for the beam, showed one painted frame, and the flicker check caught it.
The start-up tail goes at B950, in variables written before they are read. Not the printer buffer: 5B00 up holds game data the first rooms do not read; a tail there made a falling object appear at another height 200 updates in.

## Known issues
- Pace: see the review run's NOTES.md. Whole runs about -0.3%, slowest 20 updates about +1.3%.
- The original's update rate (about 10 a second) stays.

## Evidence (review run runs/comando_quatro/release-20261108, JNext 1.1.104; emulator and simulator only)
Upstream (2026-11-09): `selftest.py --game comando_quatro --verify --stamp` on main's tree, results in the record's status. Replay of three scripted recordings with R compared at every hook, the ABI cases, deliberate negatives, pace, soak, flicker, beam audit and the real loader: in that run's NOTES.md.

## Hardware checklist
Nothing has run on a Next. To check: title and tune, keyboard and Kempston (the operand now 0x1F), beeper in play, a wipe between rooms, a death, game over back to the menu, both cheats, the C key, a 1MB Next (top bank 47).

## Technique use
- patch.pace-limiter: used: K windows round the game's own plot, copy and restore.
- patch.preserve-r: used: R compared at every hook, including the body's own count.
- patch.restore-speed: used: the incoming clock comes back after every hook.
- patch.whole-altrom-image: used: Sinclair's ROM with veneers only.
- patch.display-atomic-switch: used: the overlay flips with the copy, below the play rows.
- verify.update-locked-pace: used: state in lockstep at every update, input applied before the render.

## Lessons
- [local: input in a game with many key reads] This game reads the keys at a dozen places through each update, not one. Input applied just after one read still raced the frame boundary in the next read; applying it just before the render gives every arm over a frame before the next read, and lockstep held for 800 updates.
- [local: the tail's memory] An untouched span in a 2,500-frame scan is not free memory: game data at 5B10 is first read later. Write-first variables, confirmed over longer recordings, are the place. The sign was a lockstep difference in a build that passed every hook comparison.
- [local: reads the first pass did not see] The first LD A,R list came from code that ran; a scan of the whole snapshot found a third read. A pace fixture has to cover all of them.
- [local: flicker] Writing clean attributes after the game's copy looked safe with the beam wait, but memory at a frame boundary and the unsynchronised wipe copies showed painted cells. Never putting them on the screen is simpler than timing round them.
- [local: hook temporaries] `hlib_debt_open` loses HL: a hook that needs the game's HL takes it from its saved copy.
- [local: upstream naming] The default is a hook build, so auto names it NAME_sprites.nex and the loading variant NAME_sprites_loading.nex, which nxcout packages as the default.

## Friction
- reuse: [none: Game Over's hook structure and the shared libraries were enough]
- retries: [local: start keys] The title takes its key only once its tune has started: a key too early never reaches the menu. Look at the screen first.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Fixture, cheats and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-09 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5 66563d3e (with the screen). The Kempston operand change (0xDF to 0x1F at B253) goes with it.
- 2026-11-08 Published: .nxc 1.0 (nxc 05d3127) at the owner's request, not yet played by him.
- 2026-11-08 Stage 3: engine, proofs, review build; waiting for the owner's play.
