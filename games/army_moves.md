# Army Moves (Imagine / Dinamic, 1987, 128K, both parts)

## Next session
Stage: 4 (hardware and Enhanced). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 388fd7d) after the owner played it in JNext. Default only; Enhanced has a mock-up and is not in this engine.
Inputs: Army Moves (1987)(Imagine)(128K)[re-release].z80, MD5 9c14e2564e3f9956ff6ff973dac77537; loading screen `army_moves_loading.scr` beside the snapshot (the block named army0 on the same re-release's .tap, MD5 288afbcd), staged by the record, never in this repo.
Build: `nexclash.py auto` writes `NAME_sprites.nex` (f29ce916) and, with the screen beside the snapshot, `NAME_sprites_loading.nex` (85ba62ef), which equals `nxc.py PATCH GAME --bare` of the published patch byte for byte. Without the screen auto says so and writes only the first.
Checks: `selftest.py --game army_moves --verify`: the four recordings with R, ABI cases, 10 broken builds. Pace, soak, flicker, beam audit and real loader are in Evidence, not in the repo.
Pending: hardware checklist; Enhanced; phases past the fourth, the rest of part 2 and natural completion.

## Facts
- A true 128K release: AY music from the ISR, part 1 code in bank 4 (offset +0x6A0), part 2 in bank 6, up to 0xA1FE; the plotter above that is never swapped.
- Same library as Game Over. Clean bitmap 6B90, attributes 77C0; work bitmap 5DC0 (104 rows x 30), attributes 69F0.
- Clash: A36C = RET in most plots: figures take the cell's ink (the jeep goes red over the bridge, jets blue over the sea); painted plots (A36C = FD) change scenery around them.

## Decision
As Game Over: original bitmap on the ULA, clean attributes, ordered double-buffered Layer 2 ink. New here: an unpainted part 1 figure (graphics C000..D3FF) draws in the sky's ink, the colour it has in the open; unpainted scenery plots (clouds, mountains, islands) and part 2's unpainted items punch.
The copy's DE at return differs (attributes last): the hook restores it. Direct screen clears (BA84, with HL on the screen) hide the overlay. A460 is the copy reversed: the game captures the screen into the clean buffer (title text and logo, each part's start). Attributes on the screen differ from the original's only in cells painted at the last copy, so a hook at the capture puts those back from the work buffer first; V_CAP says whether the last copy's work is still what the original's screen holds.

No DMA here: the overlay is cleared and drawn by the CPU, interrupts stay on for the AY tempo, and a DMA burst could lose an /INT; the windows have room for it.

## Cheats
Off by default, each tested alone in the simulator (3 seeds x 4,000 frames, same keys with and without): Infinite lives 33067 = 0 and in the stored part 1; Immunity 35741-35744 and in the stored part 1. Lives never fall with either; 4 lost without. Left out: the archive's Jeep doesn't fall and No enemies (no clear result).

## Known issues
- Part 2's small items and bullets the game leaves unpainted still take the cell's ink, as in the original.
- Scenery plots keep the cell's ink, as in the original: the clash removed is figures against scenery.
- JNext counted 3 interrupts lost in 2,734 frames in one part 2 run, 1 in another, none in the other four; the original lost none there. Cause not found. AY writes stay within 2.5% of the original's over each run.

## Evidence (review run runs/army_moves/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, `nexclash.pace` against the original on a 128K machine, game state in lockstep; negative = faster. The fixture stops the ISR stepping the RND seed (BA58 INC HL made NOP) in both, test copies only.

| Scene | Seed | Updates | All | Quiet third | Busy third | Worst 20 updates |
|---|---:|---:|---:|---:|---:|---:|
| Part 1 | 1 | 640 | -0.61% | -0.93% | -0.39% | +0.31% |
| Part 1 | 2 | 640 | -0.65% | -0.93% | -0.50% | +0.31% |
| Part 1 | 3 | 640 | -0.63% | -0.93% | -0.46% | +0.31% |
| Part 2 | 1 | 800 | -1.24% | -1.79% | -0.88% | -0.27% |
| Part 2 | 2 | 800 | -1.24% | -1.79% | -0.91% | -0.21% |
| Part 2 | 3 | 800 | -1.22% | -1.79% | -0.87% | -0.27% |

K windows: plot 107/16, restore and copy 119/16. Soak, 15 emulated minutes a part: no freeze, loop or crash. Flicker: out of step 0, one-frame transients 0 in both parts. Publication: 613 Layer 2 flips, 0 inside the play rows; without the beam wait 30 of 92, so the check can fail. Real .NEXCLASH loader on private NextZXOS 26.11 card copies: default, each cheat and both, output equal to nxc.py, reaching play. Loader SHA-256 4e063f60.

## Hardware checklist
Nothing has run on a Next. To check: Layer 2 timing and the beam wait (JNext's so far); the clock and the AY tempo in play; both parts through the real loader; 1MB Next (top bank 47).

## Technique use
- patch.pace-limiter: used: plot, restore and copy run whole at 28 MHz inside K windows.
- patch.preserve-r: used: R compared at every hook and in the ABI cases.
- patch.restore-speed: used: the caller's clock restored after every hook; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM.
- patch.display-atomic-switch: used: the Layer 2 flip happens below the play area, checked by the beam audit.
- verify.update-locked-pace: used: lockstep pace runs on the test fixture.

## Lessons
- [local: lockstep fixture] Original and build drift apart through the ISR's RND seed; a test-only fixture (BA58 INC HL made NOP in both) keeps whole pace runs in lockstep.
- [local: capture trap] The game captures the screen into its clean buffer at the title (A460, the copy reversed), so the title logo came out grey until a hook put the painted cells back first. Found only by looking at the soak sheet; the replay now fails a build without the repair.
- [local: detector input] The first draft of the detector read `.banks`, which only the converter's snapshot class has: auto's skoolkit snapshot never matched. The published bytes were not affected. Detect on `.memory` for that class.

## Friction
- reuse: [none: the Game Over engine was the base, no new shared tool needed]
- retries: [local: a broken build needs its event] The capture negative passed at 900 frames because no capture happened yet; it has its own longer stop. The first full verify desynced on p1cheat.rzx at frame 1948 because auto stripped its later snapshots; those are separate starts, not autosaves, so auto now replays each from its own snapshot when the stripped replay desyncs.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: engine, overlay and proofs; owner played it; .nxc 1.0 published (nxc 388fd7d).
- 2026-11-08 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5 85ba62ef.
