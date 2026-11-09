# Army Moves (Imagine / Dinamic, 1987, 128K, both parts)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.1 published as .nxc 1.1 (2026-11-08, nxc repo d622047) after the owner played it in JNext: Enhanced colours (menu, off by default) with a backdrop that comes on with it and a "Backdrop off" line. v1.0 (nxc 388fd7d) was default only.
Inputs: Army Moves (1987)(Imagine)(128K)[re-release].z80, MD5 9c14e2564e3f9956ff6ff973dac77537; loading screen `army_moves_loading.scr` beside the snapshot (the block named army0 on the same re-release's .tap, MD5 288afbcd), staged by the record, never in this repo. Enhanced also needs the player's own Spec256 sets `Army Moves (Part 1) (English).256` (MD5 cff317d2) and `Army Moves (Part 2) (English).256` (MD5 b8f4aa91) beside the snapshot, and Spec256-Games' palette `spec256-palette.pal` (MD5 b095dc99, licence not established, the file Booty uses) beside them (record rework "enhanced"); `army_moves_art` makes the colour tables from them at build time. Never in this repo.
Build: `nexclash.py auto` writes `NAME_sprites.nex` (9cbd2379) and, with the screen beside the snapshot, `NAME_sprites_loading.nex` (1b60bd04), which equals `nxc.py PATCH GAME --bare` of the published patch byte for byte. With `NEXCLASH_ARMY_MOVES_ENHANCED=1` and the sets it also writes `NAME_enhanced_loading.nex` (c8cb9484, `--colours Enhanced`) and `NAME_enhanced_nobd_loading.nex` (9825b827, `--colours Enhanced --toggle "Backdrop off"`), and the same without the screen. Without the screen auto says so and writes only those without it.
Checks: `selftest.py --game army_moves --verify`: the four recordings with R, ABI cases, 10 broken builds; the rework replays two of them on Enhanced with the backdrop against an independent picture model, its ABI cases and 18 broken builds. Pace, soak, flicker, beam audit and real loader are in Evidence, not in the repo.
Pending: hardware checklist; Enhanced part 2 room changes (see Known issues); phases past the fourth, the rest of part 2 and natural completion.

## Facts
- A true 128K release: AY music from the ISR, part 1 code in bank 4 (offset +0x6A0), part 2 in bank 6, up to 0xA1FE; the plotter above that is never swapped.
- Same library as Game Over. Clean bitmap 6B90, attributes 77C0; work bitmap 5DC0 (104 rows x 30), attributes 69F0.
- Clash: A36C = RET in most plots: figures take the cell's ink (the jeep goes red over the bridge, jets blue over the sea); painted plots (A36C = FD) change scenery around them.

## Decision
As Game Over: original bitmap on the ULA, clean attributes, ordered double-buffered Layer 2 ink. New here: an unpainted part 1 figure (graphics C000..D3FF) draws in the sky's ink, the colour it has in the open; unpainted scenery plots (clouds, mountains, islands) and part 2's unpainted items punch.
The copy's DE at return differs (attributes last): the hook restores it. Direct screen clears (BA84, with HL on the screen) hide the overlay. A460 is the copy reversed: the game captures the screen into the clean buffer (title text and logo, each part's start). Attributes on the screen differ from the original's only in cells painted at the last copy, so a hook at the capture puts those back from the work buffer first; V_CAP says whether the last copy's work is still what the original's screen holds.

No DMA here: the overlay is cleared and drawn by the CPU, interrupts stay on for the AY tempo, and a DMA burst could lose an /INT; the windows have room for it.

## Enhanced
Layer 2 full screen, double buffered, over the unchanged ULA: every figure, all the scenery and the panel's labels, one byte a pixel from the English sets, matched to this release's graphics by content (part 1: 69 of 71 records; part 2: 85 of 87). Part 1's scrolling rows are a ring. Backdrop: part 1's sky and clouds, part 2's jungle; only behind the scenery, never on title or text screens.
Departures from the sets: panel digits and text stay ULA text through a green-tinted ULA palette; the title logo (a different logo in this release) keeps the Spectrum colours; POINTS and PHASE are drawn from this release's bits in the FUEL label's two colours; figures keep a black edge where their mask is opaque; colours from 192 up are a fixed nearest colour; part 2's backdrop is a steady jungle (the set switches it with a game variable).
"Backdrop off": a .nxc toggle starts off, so the picture is part of Enhanced and the line takes it away (V_BDT; only Enhanced's code reads it). Both looks fit a 1MB Next (top bank 47).

## Cheats
Off by default, each tested alone in the simulator (3 seeds x 4,000 frames, same keys with and without): Infinite lives 33067 = 0 and in the stored part 1; Immunity 35741-35744 and in the stored part 1. Lives never fall with either; 4 lost without. Left out: the archive's Jeep doesn't fall and No enemies (no clear result).

## Known issues
- Enhanced, part 2: a new room takes 40 to 55% longer (up to 20 frames for the first), the colour drawing of 100 to 240 tiles; the next passes pay it back (whole runs -0.03 to -0.14%).
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

v1.1 review run (runs/army_moves/release-20261108b): default whole runs -0.59 to -1.08%, worst 20 updates +0.05%; Enhanced part 1 -0.59%, worst 20 updates +0.18%; Enhanced part 2 as in Known issues. Replay on the exact builds in all three modes, 121,839 frames, 190,334 hooks with R, failures none; negatives 10/10 default, 18/18 in each Enhanced mode; soaks, flicker and the real loader (default, Enhanced, Backdrop off, cheats) equal to nxc.py.

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
- [local: licence of a set's palette] 1.1 committed the Spec256-Games palette as docs/profiles/army_moves_palette.json, byte for byte the palette Booty and Lunar Jetman keep out of the repo (licence not established). It is now a local input beside the sets, MD5-pinned as Booty's; the output bytes are unchanged. Check a palette's origin before committing it.
- [local: the published default reserves Enhanced's banks] From 1.1 the published default lists zero banks up to Enhanced's top page, as the review build made it; its bytes differ from 1.0's with no hook changed, so auto builds the default that way (reserve=True) to match the published patch.

## Friction
- reuse: [none: the Game Over engine was the base, no new shared tool needed]
- retries: [local: a broken build needs its event] The capture negative passed at 900 frames because no capture happened yet; it has its own longer stop. The first full verify desynced on p1cheat.rzx at frame 1948 because auto stripped its later snapshots; those are separate starts, not autosaves, so auto now replays each from its own snapshot when the stripped replay desyncs.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: engine, overlay and proofs; owner played it; .nxc 1.0 published (nxc 388fd7d).
- 2026-11-08 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5 85ba62ef.
- 2026-11-08 v1.1: Enhanced and backdrop; .nxc 1.1 published (nxc d622047); main rebuilds default 1b60bd04, Enhanced c8cb9484, Backdrop off 9825b827.
- 2026-11-09 Spec256-Games' palette moved out of the repo to a local input beside the sets (as Booty's); default 1b60bd04, Enhanced c8cb9484, Backdrop off 9825b827 unchanged.
