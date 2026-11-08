# Into the Eagle's Nest (Pandora, 1987, 128K)

## Next session
Stage: 3 (review build, not yet played by the owner). Hardware: untested. Default only; Enhanced waits on the owner's mock-up.
Inputs: Into the Eagle's Nest (1987)(Pandora)(128K)[a][a].z80, MD5 0566e3b37d49c6fa6f62e81eb883ad0c; loading screen from the (128K) tape's screen block, MD5 e06b6a4d, staged by the packager, never in this repo.
Build: `nexclash.into_the_eagles_nest.build(z80, nex)`. Not wired into `auto`, `engines.py` or a record yet: that comes when it goes upstream after the owner has played it.
Checks: review run private. Pending: the owner's play; Enhanced decision; hardware checklist.

## Facts
- True 128K: AY from the ISR when SOUNDS (128K) is chosen, paging locked at bank 0 in this dump, ROM 1.
- Target is the [a][a] dump, already running at its menu. The (128K) dump stops in 128K BASIC, whose statements page ROM 0, so the Next build must not run it. Against the (128K) tape: [a][a] matches the tape's data at FA00 up, which the game reads; its E400-E637 difference is a work area written before it is read; (128K) differs at FA00 up.
- This dump's menu is already set: Kempston, SOUNDS (128K), MESSAGES (OFF), LEVEL (EASY); 1 to 9 change them.
- Rendering: 8500 plots one 8x8 tile with its own attribute, from D200 / DA00 or DB00 / E300. Figures are 3x3 tile blocks. Every cell is a whole tile, so no cell ever mixes a figure with scenery.
- Map at 5C00 (96 wide). Control read in the ISR (89D4, into BF4B). Main loop 8BD6 waits 5 interrupts, so steady 10 updates a second. 8C1F reads the controls; used as the probe.
- Ammo BF57, keys BF75, hits BF58 (all BCD); hits 30 ends the game (8BE0).

## Decision
The owner's standard: where there is no clash, keep the original look and claim no clash fix. So no hooks at all.
- Tail at 0xB980, 80 bytes in zeros the game never touches. Printer buffer put back after NEXLOAD (zero and unused here) so the start is exact.
- No outlines: figures have their own cells.

## Known issues
None of our own. The original's stepped, tile-by-tile movement remains.

## Evidence (review run runs/into_the_eagles_nest/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, `nexclash.pace` against the original on a 128K machine, probe 0x8C1F: the main loop waits on 5 interrupts, so the update rate is locked and quiet, busy and slowest-stretch figures say little by themselves. On test copies whose six LD A,R picks of where figures appear are LD A,I in both, the state (with the figure table) stays equal: all nine runs +0.00%; cycles inside the update equal in 325 of 401 updates and within 166 T in the rest; 200 consecutive frames' paper pixel for pixel equal. Without the test change the runs drift, because R differs: at most +0.80% in a 20-update stretch. Soak, 15 emulated minutes, ground floor and sixth-floor fixture: no freeze or crash; one LOOP finding in the plot routine, a crowded room being repainted, the picture still moving. Flicker: one-frame attribute changes reported in the build only; the pixels are equal, so that is the tool's memory snapshot, not the picture. Start-up: all registers with R, 48K RAM against the snapshot, with and without NEXLOAD's printer buffer, bar the tail; six broken builds caught. ROM: one byte used in 9,019 frames, the same on NextZXOS 26.11's ROM 3. Tile check: 173 sampled frames, 99,648 cells of 24x24: every play cell a whole tile with its own attribute but the message windows and frames caught mid-draw. Real .NEXCLASH loader on private NextZXOS 26.11 card copies: see the review notes.

## Hardware checklist
Nothing has run on a Next. To check: AY sounds; both Kempston and keyboard; 1MB Next (top bank 10).

## Technique use
- patch.restore-speed: no help: no hooks, the clock is never touched.
- patch.whole-altrom-image: no help: one ROM byte read, equal on NextZXOS 26.11's ROM 3 (`rom_paths`).
- verify.update-locked-pace: used: probe at the controls' read in the main loop; penalty +0.00%.

## Lessons
- [local: a label is not a state] The (128K) dump is a BASIC loader that would page ROM 0; its [a][a] twin is the same game already running. Check `inspect` on the alternates before planning a front end.
- [local: tiles settle clash] Checking every play cell against the two tile sets settled "no clash"; the attribute histogram alone could not have told a tile engine from careful painting.
- [local: frame-locked pace] A game that waits on N interrupts per update makes pace read 0.00% whatever the update costs inside: compare cycles from the wait's end to the update's end too. Found here when a plain build seemed 10,000 T dearer than the original; the cause was LD A,R placing figures differently, not the build.
- [local: random picks differ] Any LD A,R in the game means build and original differ in play from the first key: make it LD A,I in both test copies before comparing anything.
- [local: start points] A fixture via the game's own table of start points (BA48) reached other floors; its floor numbers run one off the names the game prints, so label fixtures from the message on screen.

## Friction
- reuse: [none: nexclash.scan, pace, soak, flicker and rom_paths were enough]
- retries: [local: TNT branch not reached] Placing TNT in the map to shoot it did not reach the branch in the time allowed, so that cheat is left out.
- environment: [local: heavy load] A cheat test passed the shell's time limit at load 60; run long tests in the background.
- hand-rolled: [local: review scripts] Fixtures, boot negatives and loader runs live in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 0-3: survey, every floor by fixture, plain build with start-up fixes, proofs, mock-up for Enhanced.
