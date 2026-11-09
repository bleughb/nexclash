# Silkworm (Random Access / Virgin Games, 1989, 128K)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 05d3127) at the owner's request, not yet played by him. Default has no hooks; Enhanced is a menu option, off by default.
Inputs: Silkworm (1989)(Virgin Games)(128K).z80, MD5 8fad50cd8c218ade32bf3c2332c8ee03; beside it, both staged by the record, never in this repo: `silkworm_loading.scr` (the Mastertronic Plus 128K tape's block 3, MD5 ff8f4e3e) and `silkworm_colours.bin` (the colour blob built from the Spec256 set, MD5 8eaea241). The replay also needs `silkworm.256` (the set, MD5 a5ab9ff0) and `spec256-palette.pal` (MD5 b095dc99) beside it: its model reads the set afresh (`SetReader`), independent of the blob.
Build: `nexclash.py auto` writes `NAME.nex` (36a148b5) and, with the screen, `NAME_loading.nex` (6ae12fd6); with the blob also `NAME_enhanced.nex` (d5d3a92c) and `NAME_enhanced_loading.nex` (2058f2e5). The two with the screen equal `nxc.py PATCH GAME --bare [--colours Enhanced]` of the published patch byte for byte. A missing input is said and its builds skipped.
Checks: `selftest.py --game silkworm --verify`: Enhanced replay of the seven recordings with R, ABI cases, 12 broken builds, every build boot-checked. Pace, soak, flicker and real loader are in Evidence, not in the repo.
Pending: hardware checklist; natural play to the end; the two-player case.

## Facts
- A true 128K release: AY music from the ISR, 128K snapshot with paging locked at bank 0, ROM 1. Bank 0 holds game code. The other banks are never paged.
- Back buffer 8002-8FFF, 32 bytes a row; A25E blits 128 rows, 28 bytes each, with POP/LDI, to y=32..159, x=8..231. So the ground rows are in the buffer too, at its rows 112-127: 96DB rewrites them each update after the plots and before the blit, and that is why figures can't appear on the ground. Attributes in the picture stay 0x47, white on black, but for the ground's wave colour.
- Main loop 9421..9483; the heli's and jeep's inputs read in 97DD and 9A68, so 9442 is the update probe after the reads. Two simultaneous players; one left idle dies off.
- Wave counter 9CC0, 0..10; B71E jumps to the ending at 7C27 after wave 11. RND 9C8F..9C92 is stepped by calls only.
- The game keeps code at 5B00-5BEE (entry at 5B00). NEXLOAD writes that buffer, so it must come back. SP is 0xFFFD, in the top 16K: no automatic tail.

## Decision
The owner's standard: where the play area is monochrome with no clash, keep the original look and claim no clash fix. So no hooks at all.
- Setup in the stub bank copies the snapshot's 5B00-5BFF back after NEXLOAD (the stub's own `keep_printer_buffer` refuses a 128K snapshot).
- Tail at 0x90B0, 79 bytes in zeros the game never touches. 0x9000-0x901F is not free: writes past the back buffer land there in some waves.
- No outlines: figures on black. Pace: nothing runs that the original does not.

Enhanced, once the owner's rule made a mock-up unnecessary: faithful, the set's colours as they are.
- Figures: the plot hooks (A2AC, AA0A, B16D) look the graphic's address up in a table of images built from the set, RLE by row, and copy them to a double-buffered Layer 2 (banks 16 and 19), mapped at slot 5 since the interrupt runs through slot 7. The flip waits for the interrupt.
- Stars, the ground (from the set's pattern for the wave, rotated as the game does) and the whole-sky flash are drawn likewise.
- The game's own screen writes in the picture area turn Layer 2 off (FC55, 9E03) until the next blit, for text screens and the end.
- Title: the logo and tags are a still Layer 2 image, rows 0-95, from the set as emuspec256 renders it (7DA3). Jeep lives: five sprites over the game's icons, as the screen shows them, at the blit.
- Text the game writes into the buffer (5BEF, GAME OVER) goes to Layer 2 too.
- Pace: the update's logic and plots run at 28 MHz in K windows; the blit and clear stay under DI at the game's clock; a figure pays a fixed debt besides its measured time.

## Known issues
- After a restart "PRESS FIRE TO PLAY" can stay on Layer 2 for up to two pictures: the game clears its buffer there by a path with no hook. A star under a figure's OR-only pixel shows the figure's colour. Both counted in the replay. It also counts back-buffer bits missing from Layer 2 at a blit (a few hundred in 9,000 frames, at most 16 in a picture; more fails the replay): likely the same unhooked paths, not proved.
- The end of GAME OVER, 16 updates or so, runs about +35% per update (a +15% 20-update stretch), cause not found.
- Stars lead the ULA's by one update, one pixel: the hook reads their positions after the game has moved them. Not visible, left.
- Picking a control on the title can blink the logo for moments: the print turns Layer 2 off until the next time round the loop.
- The original's own low update rate (about 12 a second) and long interrupt gaps (up to about 320 ms, so the music stops for moments) remain, as in the original.
- Pace runs on the release itself leave lockstep, since the interrupt's star placing steps the random numbers; the l* test copies fix that placing in both and stay in lockstep.

## Evidence (review run runs/silkworm/release-20261108b, JNext 1.1.104; emulator and simulator only)
Default as release-20261108: no hooks, bytes unchanged, +0.00%. Enhanced: pace tables, replay, negatives, soak, flicker and real loader runs are in the run's NOTES.md, on the exact final builds.

## Hardware checklist
Nothing has run on a Next. To check: the code at 5B00 after a real NEXLOAD (first game and restart); AY music; both players' controls; 1MB Next in Enhanced; Layer 2's flip at the interrupt; the sprites on the jeep's icons.

## Technique use
- patch.restore-speed: no help: no hooks, the clock is never touched.
- patch.whole-altrom-image: no help: one ROM byte read, equal on NextZXOS 26.11's ROM 3 (`rom_paths`).
- verify.update-locked-pace: used: probe after the input reads; penalty +0.00%.

## Lessons
- [local: no clash by construction] Decoding the blit's row table showed the back buffer ends above the ground rows, which proves there is no clash; attribute counts alone only suggested it.
- [local: tail region] A zero run can still take writes: 0x9000-0x901F looked free in wave 1 and took writes past the back buffer in other waves. Scan every wave before choosing a tail.
- [local: printer buffer on 128K] `keep_printer_buffer` refuses a 128K snapshot, yet this 128K game has code at 5B00; a setup call in the stub bank does the same job. Worth a note in BRIEFING C2 #36 when this goes upstream.

- [local: which interrupt touches which slot] This game's interrupt runs through slot 7: read `isr`'s Slots line before choosing an overlay slot. Slot 5 was free.
- [local: K can't fix a fixed cost] With K alone, updates with many figures ran +10% while quiet ones ran -3%: a window scales the logic, not a per-figure cost. Measured per figure, then a fixed debt per figure and a higher K, and the table went flat, whole runs within 2% and the slowest stretch under 2%.
- [local: rows spent on checks] Clip checks per span cost more than the pixels: a path for whole figures, and a stack wipe for boxes, freed about 13% of an update.
- [local: interrupts count too] The stack wipe under DI lost 6% of the interrupts, so the game's clock and music would have run slow with the update pace in range. The update isn't the only pace: read `interrupts taken` too. Interrupts on between the wipe's rows, and shorter plots, brought them back.
- [local: a stray colour in a white game] Comparing the panel with the set found only the jeep's lives differ, one attribute for both vehicles' icons. Sprites read off the screen, not off the counter, can't go wrong when the game prints something else.
- [local: a selected register is shared state] An interrupt between a hook's `out (0x243B)` and its `in (0x253B)` leaves another register selected. `HLIB_SPEED_IN` then latched a line number as the clock. Here it showed as a lone 175 ms update once in about 1,500. The wrapper now holds the pace in every interrupt and selects NR 7 again before it returns, and the replay checks that. Worth a look upstream, in any engine whose wrapper reads lines.
- [local: a latch that latches itself] The game can leave its logic without passing the hook that ends it (game over). The next update's clock latch then read our own 28 MHz as the game's clock, for good: interrupts 35 a second, AY writes doubled, updates 60% short. Only a soak and a seed that reached game over showed it. A flag now says whose clock it is, and the replay checks the latched clock.
- [local: compare with the game's own buffer] GAME OVER was missing from Layer 2 and every check passed, because hooks and model shared the same blind spot. Comparing the model with the game's own buffer bit by bit closes that, and it found the text writer (5BEF) and nothing else.

## Friction
- reuse: [none: nexclash.scan, pace, soak, flicker and rom_paths were enough]
- retries: [local: real loader] A relative run path made JNext miss the card copy; byte_exact False showed it at once.
- environment: [local: pilot venv] The venv must be called by its absolute path, or Python warns about sys.prefix.
- hand-rolled: [local: review scripts] Fixtures for each wave, boot negatives and loader runs live in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5s 6ae12fd6 (default) and 2058f2e5 (Enhanced).
- 2026-11-08 Published: .nxc 1.0 (nxc 05d3127) at the owner's request, not yet played by him.
- 2026-11-08 Stage 3: Enhanced built from the set, faithful, off by default, tested in every mode.
- 2026-11-08 Stage 0-3: survey, every wave by fixture, plain build with start-up fixes, proofs, mock-up for Enhanced.
