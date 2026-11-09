# Phantis / Game Over 2 (Dinamic, 1987-88, 48K, two parts)

## Next session
Stage: 4 (owner's play)   State: both parts published as 1.0 in .nxc 1.0 (part 1 default and Enhanced, part 2 default); on main with `auto`, its `engines.py` line and records `docs/records/phantis.json` (part 1) and `phantis2.json` (part 2). Hardware: untested.
Inputs, beside each snapshot (never in this repo): `phantis1.z80` = Game Over 2 (1988)(Dinamic)(ES)(en)(Part 1 of 2)[aka Phantis][re-release].z80, MD5 c39caed696ba547f693546b707c9cee8; `phantis2.z80` = Part 2 of 2, MD5 55c89bb16ffde2f58a43ed3be7b95bcf; `phantis_loading.scr`, the tape's loading screen, the same for both parts (a5ce3ee0); for part 1 Enhanced `phantis1_enhanced.bin` (c52e55b7), the colour table `nexclash/phantis_art.py` makes from the Spec256 set. Without the table, auto builds part 1's default only.
Build: `nexclash.py auto phantis1.z80 --no-record --no-nxc`: `phantis1_sprites_loading.nex` 1190d208 and `phantis1_enhanced_loading.nex` ae724697; part 2 `phantis2_sprites_loading.nex` a326db4d: the published bare builds (without the screen 068e1f36, 76b119c0, 9b080e19). With `--rzx`: each build's replay, the ABI cases and the broken builds.
Pending: the owner's play, default and part 1's Enhanced; new paint for what the set does not hold (a later mock-up).

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

## Enhanced, part 1
The owner's rule (2026-11-08): no mock-up or approval to convert a Spec256 set. So part 1 has Enhanced, the set's colours as they are, a menu option, off by default; the default build's bytes are unchanged. Part 2 has no set.
- The tables come from the owner's set by `nexclash/phantis_art.py` and stay beside the snapshot, never here: each graphic the game plots and the set holds, by its descriptor, one colour page row to a row. Blank pixels around each row keep 4-pixel-shifted drawing simple.
- `col_find` looks the descriptor up in the plot hook; `col_plot` copies the part the body kept after clipping (read from G_PTR) row by row. Unlisted graphics plot in the original's colours, as default.
- What the set does not hold stays in the original's colours: white fighters, yellow ships, asteroids, some scenery, the large hero, ZONE letters and digits (different art from the set's, 35-95% of their ink differs), and the panel, logo, frame, stars and GAME OVER text. The set's nebula picture has no layer to sit on in this route.

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

- [local: find by pointers] A graphic search over the whole snapshot finds 1,028 matches; only those the code points at, or that a replay really plots, are graphics: 166.
- [local: a negative that passes] A broken build that changes only the clipped-row path of a painted figure was not caught over 24,000 frames: the path is never reached in the recordings, so it stays untested and the notes say so. A pattern that finds the first of two copies of the code changes the rarer one: check what a negative really changed.
- [local: which way to miss] With K 89 the whole was on the original's pace and the worst stretch +6.7%; Enhanced takes K 84, a little faster all round, because the rule allows faster where the original lags and never slower. The default's bytes keep K 89.

## Evidence
Review runs runs/phantis/release-20261108 (both parts) and release-20261108b (part 1 Enhanced), JNext 1.1.104, emulator and simulator only.
- Part 1 default: replay of p1a, p1b, p1li, 48,034 frames, 60,657 hooks with R, 11,203 Layer 2 pictures against a model; 10 of 10 broken builds; 320 ABI cases; boot exact; soak, flicker, beam audit, real loader. Pace, 5 seeds of 800 updates in lockstep: whole -0.64 to -0.08%, quiet thirds up to +1.23%, slowest 20 updates up to +6.75%.
- Part 1 Enhanced (ae724697): the same recordings, no failure, pictures against a model with the set's colours; 12 of 13 broken builds (the clipped-row colour path is never reached: Lessons); 320 ABI cases; boot exact; soak, flicker, 425 of 425 flips off the play area, real loader. Pace (K 84): whole -1.83 to -1.45%, quiet thirds within -1.23%, busy thirds to -2.83%, slowest 20 updates up to +4.33%.
- Part 2: replay of p2a, p2b, p2c, p2li, 46,063 frames, 44,436 hooks with R, 11,192 pictures; 10 of 10 broken builds; 320 ABI cases; boot exact; soak, flicker, real loader. Pace: whole -1.73 to +0.33%, busy thirds up to +2.09%, slowest 20 updates up to +6.08%; seeds 1 and 4 leave lockstep at updates 167 and 361 (input at a frame boundary, updates not frame-locked).
- The slowest 20-update stretches are over the 2% rule in both parts: one slipped frame, repaid straight after. The owner's call by feel.

## Friction
- reuse: [none: the Game Over engine and its run scripts were the base]
- retries: [local: star bytes in the work bitmap] A star's plot writes a whole byte of the work bitmap and can land on a figure, so the bitmap check allows exactly those bytes and counts them.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-09 Upstream: auto, registration and both records on main; main rebuilds the published 1.0 builds byte for byte (part 1 default and Enhanced, part 2).
- 2026-11-08 Stage 3: part 1 Enhanced from the Spec256 set; proofs on the exact bytes.
- 2026-11-08 Stage 3: both parts on the Game Over overlay route, review builds.
