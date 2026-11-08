# Ruff and Reddy in the Space Adventure (Hi-Tec, 1990, 128K)

## Next session
Stage: 3 done for the default; Enhanced waiting on the owner's mock-up approval. Hardware: untested. Not yet played by the owner.
Inputs: Ruff and Reddy in the Space Adventure (1990)(Hi-Tec)(128K).z80, MD5 4b6c490438881cb23d0993d4b32788a2; the loading screen from the same game's 48K-128K tape, block 4. Review run: runs/ruff_and_reddy/release-20261108.
Build: `nexclash.ruff_and_reddy.build(Z, OUT)`, then `loading_nex` with the screen. Not yet wired into `auto`, `engines.py` or a record: that comes when it goes upstream after the owner has played it.
Pending: owner's play; Enhanced mock-up; hardware checklist below.

## Facts
- A true 128K release: 7FFD = 0x10 in play, 0x13 when the player in bank 3 runs (FAC7 and the screens at D1AD, D156, D130 reached through 5DCF, 5DDD, 5DEB). The .z80 was saved with bank 3 paged: game addresses from C000 up are in bank 0, so anything read from the snapshot at C000 is the wrong bank until it is asked for.
- The start room is the operand at 812C (`LD A,$0A`; AB04 is an operand in AADD). The map is 10 rooms wide; a test poke there reaches any room. 812E is the high byte of the store, so poking it corrupts code and shows scrambled rooms.
- Back buffer 8C90, 26 x 160, screen columns 3 to 28, rows 0 to 159. Row table 9CD0 by game y: rows at y 32 to 191, 0 elsewhere (ROM writes), and from y 234 it runs into the screen table 9EA4.
- A pass: A31E saves under each figure; plots A66C (3 bytes x 32 rows, up to 3) and A867 (2 bytes x 16 rows, up to 3), M then G a row, x even; A4F7 EI, HALT, DI; FAC7; a delay; the copy A506..A5E6 about a frame long; FAC7; the restores. Frame-locked: about 3 frames an update, a room change 9.
- Attributes are the room's, written once by AADD and read as collision (CP 0x47). They never change in play, so a figure takes the ink of the cells it crosses.
- Keys: table 89C1 = P, O, A, Q, SPACE. 1 pauses (border 3), fire resumes, Q in the pause gives up through FD75.
- LD A,R at 8C06 is only a border buzz length: no game state.

## Decision
The owner's standard: the original look with colour clash removed. Layer 2, not sprites: masked plots into a back buffer, up to 6 a pass, overlapping in the game's order.
- ULA bitmap and attributes = the original's, every byte.
- Layer 2 (double buffered, published with the copy, below the play rows): each figure's ink in white, the colour a figure has in the open; its mask punches what it covers. Clip window 24..231 x 0..159: a figure's right edge wraps to the next row of the buffer in the original, so that ink stays on the ULA in the cell's colour.
- The pass from A31E to A4F7 runs at 28 MHz as one K window; each plot hook only notes the figure, and the overlay is drawn once at the end, left out of the window: a nested reading at every plot cost plus or minus a line times K, which lost a frame at room changes.
- The copy runs at 28 MHz, below the play rows, in a K window of its own, with the flip after it.
- Hidden at a new room (818B), the title (80F7) and at game over or giving up (8B45, 8B79, FD75). No outlines: figures have their own black masks.

## Known issues
- Measured pace and the slowest stretches: the run's NOTES.md. Interrupts stay off during the windows, as in the original.
- A figure's mask holes show the cell's paper: blue in the water, as in the original.
- Right-edge wrap as above: original behaviour; that ink keeps the cell's colour.

## Evidence (review run; JNext 1.1.104; emulator and simulator only)
Replay of 8 recordings with R at every hook, an independent Layer 2 model, every lit pixel against the bitmap the copy wrote; ABI cases; broken builds; boot; flip audit; pace in four scenes x 3 seeds, soak, flicker, the real loader. All in the run's NOTES.md.

## Enhanced
Mock-up only (run's MOCKUP-Enhanced.png). Rated MODERATE. The set's code matches this release; figures and scenery are all painted, and the set turns the water black. Painter not named in the local files.

## Hardware checklist
Boot and loading screen; music; figures white on red, cyan, yellow and blue rock; no tear at the top of the play area; room change with no stale figures; pause; giving up; game over; each cheat.

## Lessons
- [local: bank at C000] The snapshot pages bank 3, so a dump of C000 up reads the player's bank, not the game's; a first look at the POKE sites and the room table read the wrong bytes.
- [local: wrong poke] A start-room poke one byte off (812E, not 812C) corrupted the room table and showed scrambled rooms; a sheet of every room showed it.
- [local: stale overlay] Giving up in the pause leaves through FD75 and a bank 3 screen before the title's hide: the overlay stayed over the title until the key test was looked at. The hide now covers FD75, and a recording goes through it.
- [local: window noise] A nested debt reading at each of up to six plots adds about a line of error each, scaled by K: 37 lines of target, enough to miss a frame at a room change. One reading at the end of the pass fixed it.

## Technique use
- patch.pace-limiter: used: the render pass and the copy each one K window.
- patch.preserve-r: used: R compared at every hook and in the ABI cases.
- patch.restore-speed: used: the caller's clock restored after every window; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM.
- patch.display-atomic-switch: used: the Layer 2 flip happens below the play rows, checked by the flip audit.
- verify.update-locked-pace: used: pace at the player's update with input after the read.

## Friction
- reuse: [none: Game Over's overlay route and the shared pace library were enough]
- retries: [local: window design] The first split into per-plot windows lost a frame at room changes; see Lessons.
- environment: [local: a heavily loaded machine this run] A long shell command sat unstarted once and was replaced by separate short ones.
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stages 0-3 for the default; mock-up for Enhanced; review build for the owner.
