# Into the Eagle's Nest (Pandora, 1987, 128K)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 05d3127) at the owner's request, not yet played by him. Default has no hooks; Enhanced is a menu option, off by default.
Inputs: Into the Eagle's Nest (1987)(Pandora)(128K)[a][a].z80, MD5 0566e3b37d49c6fa6f62e81eb883ad0c; beside it, both staged by the record, never in this repo: `into_the_eagles_nest_loading.scr` (the (128K) tape's screen block, MD5 e06b6a4d) and `into_the_eagles_nest_colours.bin` (the colour blob built from the Spec256 set, MD5 ebb3a64e).
Build: `nexclash.py auto` writes `NAME.nex` (b7d029c5) and, with the screen, `NAME_loading.nex` (2a73be32); with the blob also `NAME_enhanced.nex` (9b32aa8d) and `NAME_enhanced_loading.nex` (6a224cab). The two with the screen equal `nxc.py PATCH GAME --bare [--colours Enhanced]` of the published patch byte for byte. A missing input is said and its builds skipped.
Checks: `selftest.py --game into_the_eagles_nest --verify`: Enhanced replay of the six recordings with R (c1 to frame 6,000), ABI cases, 12 broken builds, every build boot-checked. Pace, soak, flicker and real loader are in Evidence, not in the repo.
Pending: hardware checklist; Enhanced's WELCOME box; natural completion.

## Interrupt wrapper (upstream note, 2026-11-08)
The fix to `h_isr` (pace held in every interrupt, NR 7 selected again before it returns) is in this engine's own `asm/into_the_eagles_nest_hooks.asm`; `asm/lib/hlib_pace.asm` is unchanged, and `asm2profile --check --all` shows every other profile IDENTICAL. No other engine shares this wrapper. Others whose interrupt handler calls `hlib_pace_hold` (midres holds only with a window open, as this one did before the fix) could have the same race and are worth checking; none was changed here.

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

Enhanced, once the owner's rule made a mock-up unnecessary: faithful, the set's colours as they are.
- One Layer 2 picture, banks 16-18, tiles and text mirrored 8x8 from the game's own plot calls, moved by the hardware offsets (NR 0x16, 0x17) when the game scrolls, clipped to x 0..191.
- The panel: 48 sprite patterns of the set's picture, 10 digit patterns following the game's numbers.
- The update runs at 28 MHz from 8BFE to 8BD6 or 91CB, and reaches the game's own wait for 5 interrupts in less time, so no K window is needed on it. Scroll steps alone have K windows. K per tile gave +42%: lines are too coarse and the overhead too much.
- The interrupt runs at the game's clock through a wrapper (operand at BFBF), so AY and beeper keep their pitch and tempo.
- Colours match the release by address: the set's graphics are byte for byte at the same places.

## Known issues
Enhanced: the WELCOME screen's box (9F04, called from 94EF) is on the ULA only, so Layer 2 hides it; the set has it in yellow. To do: a hook on that call.
The original's stepped, tile-by-tile movement remains. Pause reached from 9478 could draw its striped border at 28 MHz: seen in the code, cosmetic.

## Evidence (review run runs/into_the_eagles_nest/release-20261108b, JNext 1.1.104; emulator and simulator only)
Default as release-20261108: no hooks, bytes unchanged, +0.00%. Enhanced: pace tables, replay, negatives, soak, flicker and real loader runs are in the run's NOTES.md, on the exact final builds.

## Hardware checklist
Nothing has run on a Next. To check: AY sounds; both Kempston and keyboard; 1MB Next in Enhanced; Layer 2 offsets at the wrap; the panel's sprites on the ULA.

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

- [local: a slot found, not a slot assumed] A wrapper that mapped slot 1 to ROM during the interrupt crashed when a hook's stack was in slot 1. It now restores what it found.
- [local: carry into D] Copying a tile at column 31 carried into D. Push and pop DE per row rather than trusting E to wrap.
- [local: K at the right level] A game that waits on its own interrupts needs no K window on its update; 28 MHz to the wait is enough. Fine K windows on every tile only added cost.
- [local: a selected register is shared state] An interrupt between a hook's `out (0x243B)` and its `in (0x253B)` leaves another register selected. `HLIB_SPEED_IN` then latched a line number as the clock. Silkworm's pace tables found it; this engine has the same wrapper and could leave a scroll step at a low clock, though none showed in its runs. The wrapper now holds the pace in every interrupt and selects NR 7 again before it returns, and the replay checks that. Worth a look upstream, in any engine whose wrapper reads lines.

## Friction
- reuse: [none: nexclash.scan, pace, soak, flicker and rom_paths were enough]
- retries: [local: TNT branch not reached] Placing TNT in the map to shoot it did not reach the branch in the time allowed, so that cheat is left out.
- environment: [local: heavy load] A cheat test passed the shell's time limit at load 60; run long tests in the background.
- hand-rolled: [local: review scripts] Fixtures, boot negatives and loader runs live in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5s 2a73be32 (default) and 6a224cab (Enhanced).
- 2026-11-08 Published: .nxc 1.0 (nxc 05d3127) at the owner's request, not yet played by him.
- 2026-11-08 Stage 3: Enhanced built from the set, faithful, off by default, tested in every mode.
- 2026-11-08 Stage 0-3: survey, every floor by fixture, plain build with start-up fixes, proofs, mock-up for Enhanced.
