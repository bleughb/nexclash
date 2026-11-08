# Game Over (Imagine / Dinamic, 1987, 128K, both worlds)

## Next session
Stage: 4 (hardware and Enhanced). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 388fd7d) after the owner played it in JNext. Default only; Enhanced has a mock-up and is not in this engine.
Inputs: Game Over (1987)(Imagine)(128K)[re-release].z80, MD5 e1c2ff3cfbd4f6f5a84034d57b666acf; loading screen `game_over_loading.scr` beside the snapshot (from the same re-release's 48K-128K tape, block 2, MD5 3cdb0cbb), staged by the record, never in this repo.
Build: `nexclash.py auto` writes `NAME_sprites.nex` (8c3152e3) and, with the screen beside the snapshot, `NAME_sprites_loading.nex` (66d81454), which equals `nxc.py PATCH GAME --bare` of the published patch byte for byte. Without the screen auto says so and writes only the first.
Checks: `selftest.py --game game_over --verify`: the six recordings with R, ABI cases, 9 broken builds. Pace, soak, flicker, beam audit and real loader are in Evidence, not in the repo.
Pending: hardware checklist; Enhanced; world 2 pace (below); later rooms, world 1's end and its code screen; cheats (the archive's POKEs do not match this release).

## Facts
- A true 128K release: AY music from the ISR (no beeper), world 1 code stored in bank 4 (offset +0x5C6), world 2 in bank 6; a swap copies it into 0x8000+. So sites go in the live code and both images. World 2 drawing sites are world 1's +0x28.
- Rendering model: back-buffer composer. Clean bitmap 5DC0, attributes 6AE0; work bitmap 6CA0 (112 rows x 30), attributes 79C0; restore then plots then copy (AF4B / AF73 entries). Screen RAM is never read by the game (only the CLS LDIR).
- Clash: B47E paints a figure's whole box in the work attributes, ink only: scenery in the box changes colour (2-3% of scenery pixels). B47E = RET: plots that do not paint (pillars in front).

## Decision
The owner's standard: the original look with colour clash removed. No figures on sprites: plots overlap in the game's own order, and scenery is drawn over them.
- ULA bitmap = the original's, every byte. Attributes shown = the clean buffer (one operand at the copy).
- Layer 2 overlay (double buffered, published with the copy, below the play area): each painting plot writes its ink pixels in the figure's colour and index 254 (also transparent) on opaque mask pixels; a non-painting plot punches. AF06's attribute block (the barrel) recolours 254 to its paper and ink to its ink.
- Original plot, restore and copy bodies run whole at 28 MHz in K windows (hlib_pace) which pay for the overlay; hlib interrupt time in a window is waited out (isr_extra) so the beat with the frame does not move the pace.
- CPU clear, no DMA: interrupts stay on (AY tempo) and a DMA burst can lose an /INT; the budget is ample.

## Known issues
- World 2's pace is not within the 2% rule everywhere. Measured: busy thirds up to +0.60%, the slowest 20-update stretches +4.53% with one +35.02% not explained, quiet thirds up to -3.42%. Whole runs are 1.3% to 1.75% faster.
- Long passes of about 30 frames in world 2 (a death or a new screen, 8,000 to 10,000 lines in the original) run up to 3 frames longer: the overlay's debt cannot be repaid until the next restore and copy; the next few updates run that much faster.
- World 1's quiet third is about -2.2%, just past the -2% line. Busy thirds are within 1%; one window of 20 updates reaches +2.26%.
- A plot the game makes without painting is treated as scenery in front, so it stays in the cell's colour, as in the original.
- JNext counted 1 interrupt lost in 3,753 frames in one world 1 run and none in the other five; the original lost none. Cause not found. AY writes stay within 3.5% of the original's over each run.

## Evidence (review run runs/game_over/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, `nexclash.pace` against the original on a 128K machine, game state in lockstep; negative = faster. The fixture stops the ISR stepping the RND seed (BA58 INC HL made NOP) in both, test copies only.

| Scene | Seed | Updates | All | Quiet third | Busy third | Worst 20 updates |
|---|---:|---:|---:|---:|---:|---:|
| World 1 | 1 | 800 | -1.06% | -2.21% | -0.20% | +2.26% |
| World 1 | 2 | 300 | -1.12% | -1.95% | -0.45% | +0.83% |
| World 1 | 3 | 720 | -1.25% | -2.23% | -0.33% | +1.56% |
| World 2 | 1 | 340 | -1.29% | -0.64% | +0.60% | +2.97% |
| World 2 | 2 | 540 | -1.50% | -2.78% | +0.43% | +4.53% |
| World 2 | 3 | 640 | -1.75% | -3.42% | -2.89% | +35.02% |

K windows: plot 103/16 in world 1, 100/16 in world 2, restore and copy 118/16. Soak, 15 emulated minutes a world: no freeze, loop or crash. Flicker: out of step 0, one-frame transients 0 in both worlds. Publication: 874 Layer 2 flips, 0 inside the play rows; without the beam wait 322 of 808, so the check can fail. Real .NEXCLASH loader on a private NextZXOS 26.11 card copy: output equal to nxc.py, reaching play. Loader SHA-256 4e063f60. The shifted-picture path (BF20 set) was reached by a test poke and looked at, not replayed.

## Hardware checklist
Nothing has run on a Next. To check: Layer 2 timing and the beam wait (JNext's so far); the clock and the AY tempo in play; world 2's pace on long passes; both worlds through the real loader; 1MB Next (top bank 47).

## Technique use
- patch.pace-limiter: used: plot, restore and copy run whole at 28 MHz inside K windows, the plot's per world.
- patch.preserve-r: used: R compared at every hook and in the ABI cases.
- patch.restore-speed: used: the caller's clock restored after every hook; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM.
- patch.display-atomic-switch: used: the Layer 2 flip happens below the play area, checked by the beam audit.
- verify.update-locked-pace: used: lockstep pace runs on the test fixture.

## Lessons
- [local: lockstep fixture] A test-only fixture (BA58 INC HL made NOP, the ISR's RND seed step) gives lockstep pace runs.
- [local: pace windows] A pace window with interrupts on saves the handler's time, and FRAMES counts them; hlib interrupt time in a window is waited out so the beat with the frame does not move the pace.
- [local: detector input] The first draft of the detector read `.banks`, which only the converter's snapshot class has: auto's skoolkit snapshot never matched. The published bytes were not affected. Detect on `.memory` for that class.

## Friction
- reuse: [none: the shared pace and hook libraries were enough]
- retries: [local: pace windows] K was swept per world (final-K100 kept as the run before d06b37d).
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-03 First report blocked: figures as hardware sprites did not suit the scenery drawn over them.
- 2026-11-08 Stage 3: Layer 2 overlay, proofs; owner played it; .nxc 1.0 published (nxc 388fd7d).
- 2026-11-08 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5 66d81454.
