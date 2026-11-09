# Chase H.Q. (Ocean, 1989, 128K)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.3 is this engine's build: 1.2 (published as .nxc 1.2, nxc repo 238e98a) with two interrupt-safe reads of the CPU speed; the 1.3 review .nxc awaits publication. The owner played 1.1 in JNext (Speed, Enhanced at both paces), not yet 1.2 or 1.3.
Inputs: Chase H.Q. (1989)(Ocean)(128K).z80, MD5 cedb31d5860815ef7e871ee249744de5. Beside it, staged by the record, never in this repo: `chase_hq_loading.scr` (the 6,912-byte screen block of the archive tape, MD5 aed0ca7e) and `chase_hq_art.bin` (the Enhanced art pages, MD5 83797b5c; "Inputs").
Build: `nexclash.py auto` writes `chase_hq.nex` (default, 2f6628a5), `chase_hq_speed.nex` (Enhanced [Speed], 6729617f) and `chase_hq_orig_pace.nex` (Enhanced [Orig. pace], 498c2119), each equal to `nxc.py PATCH GAME --bare [--colours NAME]` of the 1.3 review patch byte for byte (1.2's were 0a989fa7, a6d6fec8, c02edf3f), and boot-checks each. Without the two inputs it builds nothing and says so.
Checks: `selftest.py --game chase_hq` rebuilds and compares the three MD5s (stamp: checked). No RZX verifier in the engine yet: `verify` and `unit_tests` say so; the proofs are the pilot run's ("Evidence").
Pending: hardware checklist; an RZX verifier for the current hook set; compiling the art pages from an in-repo colour map; stage 2-5 pace.

## Facts
- Main loop 8444, player update B063; road geometry B9F4 (called at 846B), road pixels C452 (8471), roadside and traffic 8F5F (849B), screen copy BC3E (84BC). Back buffer F000-FFFF: 128 rows of 32 bytes for screen rows 64-191.
- The game disables interrupts in play and draws with SP. The road renderer reads the printer buffer 5B00-5BFF and writes to ROM while clipping (MMU0 must be the ROM's again before original code runs).
- The tunnel mouth's walls use a self-modified JR at C236 whose offset (C237) is 16 - (A >> 1): a zero-width row lands on C248. A hook site starting at C247 put a JP operand there (1.1 crash fix: the site starts at C248).
- Stage graphics change at 5C00-76F0 per stage; roadside tables at 5CF8 and 5CFE; 21 depth slots sorted at 8F5F.
- The game has no LD A,R or LD R,A (every bank of the plain build scanned; the one hit is the .nex start stub's).

## Design
- Speed: the four drawing routines run at 28 MHz and return at the incoming clock; registers with R and the original SP restored at every wrapper. The render window opens at 8447 and closes at 84BF; its target is the original's quiet-scene time (Speed: 21,120 sixteenths, 85.99 ms), no debt carried. The ten calls to the sound maintenance 83B8 run at the game's clock, each held to the original's quiet-scene offset, so the siren keeps its spacing.
- Start-up: the tail transfers to boot_resume in the hidden ROM, on a private stack, which restores the whole printer buffer (the tail included), R and the registers, then jumps to the snapshot's PC.
- Enhanced colours: a parallel Layer 2 colour buffer follows every original plot in the original order (row hooks installed by colour_init once the game has unpacked its plotters), with a sprite dashboard, Copper horizon split, coloured radio portraits and message pane. Behind one byte, enh_enable: 0 in the default, where colour never initialises (no Layer 2, sprites, Copper, display offsets or row hooks) and the game draws its original pictures through the speed engine.
- Three sets from one source (asm/chase_hq_hooks.asm, CHQ_SET): the default (enh_enable 0); "Speed" (Enhanced at the Speed targets); "Orig. pace" (Enhanced; the final pace target is worked out for each update: 11/16 x the update's own time without limiter waits + 9.96 x road geometry's time + 0.8 x road pixels' time + 12.8 ms, fitted against the original in JNext). They differ only in bank 12 (the hidden-ROM page).
- Banks: alt ROM sources at 45/44 (z80tonex ROM48_BANK / ROM128_0_BANK for this build only), so the default lists banks 0-45 and fits a 1MB Next; the colour sets list 0-109 (header byte 8 = 1792K, a 2MB Next), leaving 110-111 for the menu .nex.
- DMA: Enhanced fills and copies use the zxnDMA from one template (E_DMA, both sources), interrupts already off in play; no core 3.03.00 DDMA or blitter path was evaluated for this engine (the pilot predates that rule); the default (Speed) uses no DMA.

## Inputs
- `chase_hq_art.bin`, 1,343,488 bytes: banks 9, 11, 15, 29-43 and 46-109 in that order, 16K each, the non-code pages of the published builds: painted portraits, lookup pages, steering atlas, figure and roadside colour records and their stage-1 caches, the dashboard pattern atlas and horizon strips. Jon Attree's painting compiled over the game's own graphics as captured from the running game by the pilot run's release builder (runs/chase_hq: build_release.py with its build_assets.py and build_polish.py), so it is game-derived and stays local. The default carries these pages too, as published, and never reads them. Every other bank is code from this repo or computed by the engine (lookup tables, bit patterns, the 128K ROM 0 page).
- `chase_hq_loading.scr`: the 6,912-byte screen block of the archive tape (runs/chase_hq files/loading-source.tap, MD5 051b42a3).
- Arcade reference material from the pilot run is not an input and is not in this repo or the art pages (the run's originality check: no 8x8 block of the 526 painted cells matches the 12 arcade frames).

## Cheats
In the .nxc, off by default, from the archive POK: Infinite credits 9C3E = 166, Infinite time 9C01 = 0 (bank 2); 1Hit to capture and Infinite turbos at their bank 3 source copies 350F = 62 and 30A5 = 0, which the game copies to B50F and B0A5 at its intro.

## Known issues
- Pace, JNext, stage 1, against the original with the same input (negative = faster): Speed whole runs -8.0 to -18.8%; Enhanced [Speed] -6.4 to -14.1%; Enhanced [Orig. pace] whole -3.0 to +0.3%, quiet third -3.1 to +1.2%, busy third -5.0 to -0.3%, but 20-update stretches reach +13.4% in the heaviest scenes: there the Enhanced drawing alone takes longer than the original, which no limiter can pay back.
- The original's synchronous sound effects still stall play for up to about 0.8 s.
- Enhanced road motion is approximate and frames can tear.

## Evidence (pilot run runs/chase_hq, JNext 1.1.104 headless; emulator and simulator only)
- 1.0 speed pass (the Speed hooks then, not these bytes): paired-hook RZX replay over 6 recordings, 37,500 frames, about 4,800 paired executions of each of 16 CALL sites, registers with R, writes and sound I/O; clock, R, MMU and cadence unit checks; broken controls. 3,300 native updates and 48 completed screens equal.
- 1.1 (default and Enhanced [Speed] bytes unchanged in 1.2): native lockstep against the original, 4 driving scenes x 3 input trials: the 57 player-state bytes identical at every update, every AY and beeper write identical by update, port and value; briefing and attract demo: registers with R, 384 game bytes and sound identical at every loop end; Speed's ULA screen bytes equal the original's at every sampled update. Six autopilot tunnel routes (450 updates each, 194-828 zero-width wall rows), stage 2, 4 and 5 checkpoints, capture and time-out to the menu: logged state identical at every update. Tunnel crash: reproduced on 5 of 6 routes before the fix, 0 after; static audit of all 67 sites for branches into replaced bytes.
- 1.2 Orig. pace (c02edf3f): 90 game addresses equal at every update in 6 runs, 6,200 updates; final coverage (six tunnel routes, stages 2, 4, 5, capture, time-out): 0 state differences against the original's logs. Negatives read on the pace figure (the state list cannot see a pace fault): limiter never waiting -18.64%, road windows read as zero -8.60%, against -1.45 to -2.7% for the build.

| Orig. pace, seed, updates | Whole 1.1 | 1.2 | Quiet 1.1 | 1.2 | Busy 1.1 | 1.2 | Slowest stretch 1.1 | 1.2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1, 800 | -4.89 | -2.68 | +3.00 | -2.73 | -14.74 | -3.47 | +6.8 | +3.0 |
| 2, 800 | -9.90 | -3.04 | +1.57 | -1.37 | -22.08 | -5.04 | +8.8 | +3.0 |
| 3, 800 | +0.97 | -1.45 | +5.33 | -0.67 | -1.97 | -0.78 | +9.1 | +4.6 |
| 4, 800 | +0.82 | -2.62 | +3.62 | -3.06 | -1.78 | -2.21 | +7.5 | +1.2 |
| 5, 3000, POKEs | -0.74 | -0.29 | +3.95 | +0.48 | -4.19 | -1.13 | +15.4 | +13.4 |
| 6, 3000, POKEs | -0.43 | +0.33 | +4.99 | +1.17 | -4.46 | -0.27 | +13.2 | +12.8 |

- Real .NEXCLASH loader on private card copies: 1.1 on NextZXOS 26.11 and v2.09, Enhanced off and on, with and without the cheats; 1.2 on 26.11, default, Enhanced [Speed] and [Orig. pace]: output equal to nxc.py, menu and driving reached, frames viewed. 15-minute soak of Orig. pace: no freeze, loop or crash.
- 1.3 (2026-11-08, upstream run pace13 on these bytes): stage 1, seeds 1-4 x 800 updates, the audit's profile and plain control: 90 game addresses equal at every update in all three modes. Orig. pace whole -2.68 / -3.06 / -1.45 / -2.61% (1.2: -2.68 / -3.04 / -1.45 / -2.62), slowest stretch +2.9 / +3.0 / +4.6 / +1.3 (1.2: +3.0 / +3.0 / +4.6 / +1.2); Enhanced [Speed] within 0.02 points of 1.2; default identical to 1.2. Real .NEXCLASH on a private NextZXOS 26.11 card copy with the 1.3 review .nxc: default, Enhanced [Speed] and [Orig. pace] output equal to nxc.py, menu (v1.3), briefing and driving reached (201-241 play updates), frames viewed; card copies deleted. iff_off simulated with interrupts on and off and an interrupt during the first read: right in all 12 cases (three sets); 1.2's single read takes the "off" branch in that case. Boot-check negative (printer buffer not restored) caught in the default and Orig. pace.
- This repo: `auto` boot-checks each build as the converter's loader and as NEXLOAD leaves the machine: every register with R and all 48K RAM at the game's PC, no tail exemption.

## Hardware checklist
Nothing has run on a Next. To check: start-up and the briefing; the 28 MHz windows and the siren spacing; Enhanced Layer 2, Copper split and dashboard sprites at both paces; the tunnel mouth; the default on a 1MB Next (top bank 45) and the colour sets on a 2MB Next.

## Technique use
- patch.pace-limiter: used: the render window's target, fixed (Speed) or per update (Orig. pace).
- patch.preserve-r: used: R kept at every hook; the boot check compares it.
- patch.restore-speed: used: the incoming clock restored at every wrapper exit.
- patch.whole-altrom-image: used: Sinclair's 48K ROM and the 128K ROM 0 as whole alt ROM images, sources at banks 45/44.

## Open
- Hardware: everything in the checklist.
- Verification in this repo: an RZX verifier and unit tests for the current 67 sites (the pilot's 1.0 replay covered the Speed hooks of that version only); until then the record has no verify recipe and is stamped "checked" (rebuild), not "verified".
- Art pages: an in-repo colour map of the painting and an engine-side compiler, so `chase_hq_art.bin` is no longer an input.
- DDMA: the review the contribution rules ask for (docs/DDMA.md); Enhanced uses the plain zxnDMA.
- Pace: stages 2-5, briefing and attract targets not re-measured since 1.1.

## Lessons
- [deferred Open: reconsider when the Enhanced painting next changes (an in-repo colour map and compiler then)] The Enhanced pages are compiled from the painting over stage graphics captured from the running game, so main cannot make them from the snapshot; they are a local input (`chase_hq_art.bin`). An in-repo colour map and an engine-side compiler (as Gunfright's) would remove it.
- [local: one source, three sets] The three published hidden-ROM pages differ only in their pace edits, so one source with CHQ_SET covers them; the two set sources carry their own SAVEBIN lines because asm2profile reads SAVEBIN names from the top-level file only, and the shared source's SAVEBINs are guarded off for them.
- [local: separate assemblies in one source] Five units assembled separately in the pilot (steering, row plotter, dashboard, motion, HUD) assemble to the same bytes as one source with a MODULE each, each SAVEBIN before the next unit reuses its addresses.
- [local: published layout] The published builds put the alt ROM sources at banks 45/44 instead of the converter's default 47/46; the engine sets them for its own convert only and restores them.
- [deferred Open: reconsider when Chase H.Q. Enhanced next changes or a hardware round reports its hook cost] The contribution rules ask every new game for a DMA and core 3.03.00 DDMA review with a no-blitter fallback; the pilot built Enhanced on the plain zxnDMA before that rule and this upstreaming changes no bytes, so the review is open (docs/DDMA.md).
- [local: single LD A,I in 1.2] 1.2's Enhanced read I once in two places (sound_tick, pace_wait_e) to pick the clock for a check; main's IFF audit (the --tools run) forbids that, and the pilot had no such audit. 1.3 calls iff_off at both (CALL + JR C, the same 5 bytes), which reads twice; iff_off sits at the end of the page so no other label moves. Default bytes change too (the code is shared) though it never runs there; pace equal to 1.2 in every mode.
- [none: pace lessons] The Orig. pace fit and menu-bank lessons are in the pilot run's notes; nothing here changes them.

## Friction
- reuse: [none: z80tonex, nextboot and asm2profile did the conversion, boot check and profiles unchanged]
- retries: [none: the first rebuild matched]
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: pilot scripts] Lockstep, pace, coverage and loader runs were the pilot run's scripts, not the toolkit.
- scratch: [local: pilot run] Its work folder and the extraction scripts stay in private evidence.

## Stage log
- 2026-11-06 Stage 3: 1.0 speed pass; 1.1 Enhanced colours and tunnel fix; owner played 1.1.
- 2026-11-08 1.2 Orig. pace follows the original per update; .nxc 1.2 published (nxc 238e98a).
- 2026-11-08 Upstream: engine, `auto`, registration and record; the 1.2 bytes rebuilt exactly; the --tools IFF audit failed on two single LD A,I reads.
- 2026-11-08 1.3: both reads made interrupt-safe (iff_off); new MD5s in all three modes, pace unchanged; review .nxc built, not yet published.
