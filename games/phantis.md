# Phantis / Game Over 2 (Dinamic, 1987-88, 48K, two parts)

## Next session
Stage: 3 (prove + deliver)   State: private review builds for the owner, nothing upstream yet
Inputs: Game Over 2 (1988)(Dinamic)(ES)(en)(Part 1 of 2)[aka Phantis][re-release].z80, MD5 c39caed696ba547f693546b707c9cee8; Part 2 of 2, MD5 55c89bb16ffde2f58a43ed3be7b95bcf
Checks: replay, ABI, negatives, pace, soak, flicker, beam audit, real loader in the run's NOTES.md
Pending: owner plays; Enhanced mock-up approval; then `auto`, the record and registration for upstream.

## Facts
- Two 48K parts, each its own snapshot and each its own patch. Part 2 asks for the code part 1 gives: 18757 (FCFE). Same author and library as Game Over: figures masked into a back buffer, each figure's box painted in the work attributes, ink only, so anything else in the box takes its ink.
- Part 1: work bitmap EFF0, 30 x 120; clean attributes EE2E; work attributes FE00. The copy (C916) HALTs, delays, then pops destinations from B5B8 (each +1) and sources from a table at 5B00 (built once at C5DF from E9FC, which E9DE's pre-shift buffer later overwrites): 26 LDIs a row, 135 rows, longer than a frame, screen columns 3-28. Undo list runs after it.
- Part 2: work bitmap F0E0, 28 x 120; clean attributes EF3C; work attributes FE00. The copy (C995) is not synced to the frame and keeps interrupts on. Paint skips cells flagged in the map at ED98.
- Plot (C6DF / C759) leaves its clipped result in its own variables, so the overlay reads those after the body has run instead of redoing the clipping.
- RND seed 5C7B is stepped by the handler and read at BB82: frames change the game unless a pace fixture stops the step. No LD A,R in code that ran.
- Handler: reads the keys and counts frames; no port writes, so it is safe at 28 MHz.

## Decision
The owner's standard: the original look with colour clash removed. Layer 2 route, as Game Over.
- ULA bitmap = the original's, every byte. Attributes shown = the clean buffer: part 1 by the table's 15 attribute rows, part 2 by putting the clean attributes in the work attributes' place before the original copy runs (its own tail refills them from the clean ones anyway; when no figure was drawn the hook puts them back).
- Part 1 keeps its copy at the game's clock and flips mid copy: its writes show from the next frame's top, so the flip is at row 80, beam off the play area. Part 2 is as Game Over: wait for the beam below the play area, copy at 28 MHz, flip, K window.
- Plot bodies run whole at 28 MHz in K windows; the overlay's time goes to the debt the same window repays.
- No DMA: interrupts stay on and the buffers are small; a DMA burst can lose an /INT. CPU clear.
- No outlines: every figure has its own black mask.

## Technique use
- patch.pace-limiter: used: plot, and part 2's copy, run whole at 28 MHz inside K windows.
- patch.preserve-r: used: R compared at every hook and in the ABI cases.
- patch.restore-speed: used: the caller's clock restored after every hook; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM.
- patch.display-atomic-switch: used: the Layer 2 flip happens off the play area, checked by the beam audit.
- verify.update-locked-pace: used: lockstep pace runs on the test fixture.

## Lessons
- [local: copy column] Part 1's copy pops a table of screen addresses and adds 1 before use, so work column 0 is screen column 3. The first overlay sat one column left of the ULA, which read at first like a pass of lag. The verifier checked its own idea of the column; only the JNext screen showed it. Read the copy's destination, do not assume.
- [local: beam race] Part 1's copy is slower than a frame and stays behind the beam, so what it writes shows from the next frame's top; a flip at its end falls mid screen. Split the row count and flip in the middle.
- [local: read after the body] Reading the clipped result from the plot's own variables after the body keeps the overlay short and cannot disagree with the original's clipping.
- [local: selection keys] The menu polls, and a script's short press of J can be missed. Check an input script really changed the game: two pace seeds with identical numbers meant input was not reaching it.
- [local: fixture] Pace fixture: the handler does not step the RND seed (BA4B NOP), lives do not fall, part 2 skips the code screen.

## Friction
- reuse: [none: the Game Over engine and its run scripts were the base]
- retries: [local: star bytes in the work bitmap] A star's plot writes a whole byte of the work bitmap and can land on a figure, so the bitmap check allows exactly those bytes and counts them.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.
