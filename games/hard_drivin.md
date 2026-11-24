# Hard Drivin' (Domark / Binary Design, 1989; 128K tape)

## Next session
Stage: route 2a phase 1 (exact speedups, gear fix, heading blend)    State: both routes stamped verified; hardware: route 1 plays like the original; route 2a "plays much better" (test 2); phase 1 build (test 3, 2026-11-24, core 3.03): "new builds work great on hardware" (user)
Techniques: `patch.substep-updates`, `patch.inbetween-views`, `detect.pacing-structure`, `patch.pace-limiter`, `patch.restore-speed`, `patch.whole-altrom-image`, `verify.update-locked-pace`
Inputs: C:\1NEXT\harddrivin_work (and C:\1NEXT\hd_reference\hard_drivin, same MD5s): hard_drivin.z80 (MD5 18809405, snapshot 0 of hard_drivin.rzx), hard_drivin.rzx (MD5 c649e04c, 22,116 frames), in\hd.tap (MD5 02e1f96c), in\hd.tzx (61f7d04c), in\hd.dsk ([a], 43a6bc4c). Game data: never in this repo; not yet in specnext/reference (a maintainer push: ask first).
Branch: hd-phase1 (worktree C:\1NEXT\nexclash-hd, from main 7aa9961)    Commit: phase 1 uncommitted (main session reviews)
Engine: nexclash/hard_drivin.py: route 1 (HDPatch, Next, verify, unit_tests, negative_patches), route 2a (StepsPatch,
  Spec, NextSteps, verify_steps, unit_tests_steps, steps_negatives), auto, boot_problems; asm/hard_drivin_hooks.asm +
  hard_drivin_wset.inc -> docs/profiles/hard_drivin.json; asm/hard_drivin_steps.asm -> hard_drivin_steps.json.
  Builds: hard_drivin.nex (plain, tail 0x6C00) d74f75e6, hard_drivin_smooth.nex 9fb23f8e (both unchanged by phase
  1), hard_drivin_steps.nex (default) 9cc6f829 (phase 1; before: a2709f99 = hd4_na + automap_off); with the loading
  screen hard_drivin_steps_loading.nex 9d1a130d, hard_drivin_smooth_loading.nex f789a1c7; the .nxc = steps +
  screen, toggle "Original time steps" = smooth + screen, 5 trainers (sections "Loading screen" and "Trainers").
Checks: 2026-11-24 f28 1.0: stamped selftest PASSED (steps 6,220 cases; pace 10.00 / 10.02 / 10.70; smooth 3,112).
  Phase 1: `auto --quick 2000` PASSED (steps 288 cases, 0 mismatches; unit tests incl. exhaustive
  multiplies, DMA copy, gears, blend; 27 / 27 negatives); stamped selftest PASSED (whole RZX: steps 6,220 cases = the
  Spec, 0 mismatches (202 s); 27 / 27 negatives; model pace 10.00 / 10.15 / 10.71 frames; smooth 3,112 checks).
  2026-11-23: stamped selftest PASSED (whole RZX: steps 6,220 cases = the Spec; smooth 3,112 checks).
Pending user answers: none
Start with: the .nxc 1.1 (built separately: display-only menu toggle "Heading smoothing", blend stays default; the owner
  could not tell blend from noblend), its hardware test, then the owner's choices in "Further work" (N ladder, board K
  reading, easy-steering cheat, faster candidates). Route 2b only if wanted.
Pending: owner: a board K reading (then the N threshold); whether to build the divide speedup (B) next.
Open: route 1: the first calibration interrupt's extra ~574 T (0.06 %), sub-unit angle interpolation. Both: R not
  preserved (patch.preserve-r: the verify excludes R; no consumer found, not proven). Route 2a: the model's 28 MHz
  factor is f28 1.0 since 2026-11-24 (target core 3.03, no read wait: TECHNIQUES 1.0; 1.2 was JNext = 3.02); the
  time-out path is the recorded u554 + synthetic states only. Core 3.03 review (section "Core 3.03"): K on the board
  and N = 4's share are unmeasured; N thresholds / pacing unchanged (owner decides).

## Facts
- Tape (.tap = .tzx data): BASIC `HD 128K`, code 100 @ 30000, 5,000 @ 32960, 200 @ 43616, BASIC, one 41,400-byte block @ 24000. Single load.
- Snapshot: 128K, 7FFD 0x13 (ROM 1, bank 3 at C000), IM 2, I = 0xC1, vector table 0xC100 -> handler 0xC0C0 (CALL 0xC261 / EI / RET), SP 0xFFFA. Starts on the title screen.
- Interrupts mostly off in play: 742 accepted in 15,001 frames. The handler pages 7FFD (0xCD87/0xCD8A), uses EXX and AF'.
- 3D view: drawn into a back buffer at 0x8000-0x8FFF (write-first), copied to the screen's top 4K (0x4000-0x4FFF) by 0xDC45 (called from 0xDC37; 1,057 copies in 15,001 frames = one view every ~14 frames, ~3.5 a second). Dashboard needles and lamps: 0xE3AF / 0xE3D6 (16-byte plots), attributes 0xF228 / 0xF219.
- Look: the view is monochrome green (ink/paper attributes), the dashboard in fixed colours. No figure clash of the usual kind.
- Plain conversion: the survey's automatic tail fails (SP in the top 16K); `convert --tail 0x6C00` works: 0x6B53-0x6D5F untouched over all 22,116 frames.
- Options menu: 1 keyboard, 2 Kempston, 3 Fuller, 4 Interface 2, 5 cursor; SPACE centres steering, 0 aborts replay or off-road.

## Decision (user, 2026-11-22)
- Route: "Smoother 3D view" (Castle Master's M3 route): updates keep the original's real-time rate (pace
  ORIGINAL, per update); the renderer runs at 28 MHz and the freed time draws in-between views (display only).
  Rejected: plain only. Not now: coloured scenery (a later switchable extra).

## Feasibility (PLAYBOOK 3d; probes in C:\1NEXT\harddrivin_work\tools, first 3,000-6,000 frames)
### Pacing measurement
- No frame wait; DI for most of play (detect.pacing-structure, observed). Main loop 0x9E34 (body to 0x9E88, JR back at
  0x9E32): logic + render 0x9EA9 (from 0x9E54) + lap clock 0xA38A + view copy 0xDC37 (from 0x9E6B). Update 7-21
  frames (median 13): busy scenes run slower in game time, as in the original.
- The lap clock counts 5 updates a clock second (no real-time clock); the ISR (0xC261, IM 2) is sound only. So a
  faster update = a faster game: the update's original time must be kept.
- Cost per update (229 updates): render 87 % (845k T), copy 6 % (62k T), the rest ~6 %. Camera: x, y, z words at
  43400 / 43402 / 43404, orientation 43407-43409.
### Dependency investigation
- 23 addresses the render leaves are read later by logic (camera copy 43373-43379, 0x918E, 0x91CC-D, 0x951E, list
  0xF02C-0xF03B): the real render runs last on the genuine pages; extra renders only on scratch pages.
- Back buffer 0x8000-0x8FFF (write-first) -> screen 0x4000-0x4FFF by 0xDC45 (SP copy).

## Build (stage 2, route 1 as built)
- Sites 0x9E54 (render), 0x9E6B (copy), 0xD6FE (the line clock's tick); hook page 36 in slot 1 during hooks; trampolines
  at 0x3870 in the alt ROM image (bank 12). The render is a pure function of camera + world; It POPs ROM bytes as data (SP pages 0x00-0x16), no DI / EI. Sound: 0xEA60 per update (bank 3).
- Per update: the real render first, then in-between views on scratch pages 38-41 with the camera interpolated, each
  copied in lines 128-262 (no tear); window = K x the real render's 28 MHz lines, debt carried. K measured at run time by
  a 3.5 MHz calibration render (IM 2 through the hook page, pushes repaired, a hit push abandons it); JNext K 6.17-6.28 depending on the scene (contention share)
  (6.6-7.0 = TECHNIQUES' core 3.02.00 copy loops; on core 3.03 expect K ~8). JNext pace vs plain: -4 frames / 178 updates.

## Stage log
- 2026-11-22: stage 0-1 (route choice, feasibility). 2026-11-23: route 1 stages 2-3 (stamped); route 2 probes, build 2a,
  move-in, loading screen, trainers, .nxc (subagents: harddrivin_work\step\stage1-3_results.md, movein_results.md,
  nxc_results.md). 2026-11-24: phase 1 (opt\phase1_results.md), core 3.03 (opt\core303_results.md), investigations
  (opt\speed_results.md, feel_results.md, steer_results.md), hardware test 3.

## Technique use
- detect.pacing-structure: helped (no frame wait, 7-21 frame updates, the lap clock counts updates)
- patch.inbetween-views: helped: route 1; corrected: K measured at run time, scratch copies of the game's pages instead of Layer 2 banks
- patch.pace-limiter: used: route 1 ORIGINAL per update; route 2a REAL TIME (3,110 lines an update, line clock)
- patch.restore-speed: used: hlib_speed in every hook
- patch.whole-altrom-image: used: Sinclair's ROM 1 + trampolines at 0x3870 (bank 12), both routes
- verify.update-locked-pace: used: JNext pace log vs the plain build, 178 updates
- patch.preserve-r: no help: not applied; the verify excludes R (no consumer found, not proven)
- patch.loader-screen-from-game-file: no help: the .z80 holds no screen; staged and carried as SCR1
- patch.substep-updates: helped: written from route 2a (candidate card); phase 1 amended it (held keys, heading blend)
- optimise.layer2-renderer-speed: no help: its DMA / MUL advice applied by hand to the ULA render (exact hooks)

## Lessons
- [kb lesson.jnext-28mhz-ratio-varies: K 6.17-6.28 by scene in JNext] observed: the render's 3.5 MHz : 28 MHz ratio moves with the scene's contention share; a fixed K lagged, the latest calibration sample tracks it.
- [kb lesson.runtime-k-calibration: a 3.5 MHz re-render on scratch pages measures K] demonstrated: calibration render with IM 2 through the hook page, kept samples -0.14 .. +0.43 % of the original render's time over the whole RZX.
- [kb lesson.sp-as-data-pointer: an interrupt push lands in the render's SP-walked data] demonstrated: the render POPs object lists and ROM bytes, so the calibration handler must put the 2 pushed bytes back from genuine memory.
- [kb lesson.interrupt-push-in-write-set-abandon: a hit push cannot be repaired] demonstrated: a push into bytes the render writes (tables 0x9C00-0x9DFB) was repaired with a stale byte and the render ran away (u605: a push in the write set (0x9C39) was flagged but repaired stale); abandon the render and drop the sample.
- [kb lesson.negative-control-phase-sweep: sweep the start line for interrupt-timed faults] demonstrated: the push-repair control was missed on 6 states at their own start line and caught once the start line swept the frame.
- [kb lesson.skoolkit-write-guards-below-4000: the reference re-render ran away] observed: stock SkoolKit dropped the hook page's writes below 0x4000; dizzy6._rw_simulator keeps them.
- [kb lesson.nexload-printer-buffer: 256 bytes differ when booted as NEXLOAD] observed: only 0x5B00-0x5BFF and the tail; neither is read before written.
- [kb lesson.rebuild-without-recording-must-pass: a FAILED auto skips the CLI's later steps] observed: auto returned FAILED, so the automap_off entry was not added and the rebuild's MD5s differed.
- [kb lesson.asm2profile-key-prefix: profile keys from SAVEBIN names] observed: asm2profile takes the key from the SAVEBIN name up to the first underscore; named hdrivin_page.bin / hdrivin_rom.bin.
- [kb lesson.7ffd-write-maps-rom-over-slot-1: the update's own 7FFD writes unmapped the hook page] observed on JNext, now in the steps host model: a write to 7FFD sets MMU slots 0-1 back to ROM, so the sub-step hooks after 0x9E7C / 0x9E86 ran ROM bytes until site 0x9E88 mapped the page again.
- [card patch.substep-updates §Failure lookup] demonstrated: the steering-clamp mutant passed every recorded state because a later sub-step's overflow path resets the value to exactly 120.0; caught only with the clamp reached on the last sub-step (mods steerpl / steerml).
- [card patch.substep-updates §Verification] demonstrated: the prototype's spec.py, host model and 20 mutants moved into the engine; mutants as page-byte patches at asm labels (no reassembly), fixed N by the page's n_force byte; whole RZX: 1,555 updates x 4 variants in minutes with a process pool.

- [kb lesson.mul-replaces-shift-add-exactly: C541 / D030 by Z80N MUL] demonstrated: exhaustive over the reachable inputs (4,227,201 + 65,536 cases), every register but R equal; the 8 x 8 path 216 -> ~46 T.
- [kb lesson.dma-copy-then-original-last-row: view copy by zxnDMA] demonstrated: DMA all rows, then the original's last row from DE07 with its pointers set: registers, 128K and self-modified bytes = the original.
- [card patch.substep-updates §Failure lookup] demonstrated: a held gear key shifted N times an update (N = 4: 1 -> 3 at once); gate (first) found by a synthetic held key, not by the recording (no manual gears in it).
- [card patch.substep-updates §Failure lookup] demonstrated: heading in byte steps: the render's matrix blended by the fraction, the game's put back; logic state checked apart from the view (VIEW_ONLY, COPY_REGS).
- [kb lesson.blitter-tiny-copies-cpu] observed: the 32-byte PUSH clear rows and <= 32-byte sky LDIRs gave no DMA gain in the model (18.5k vs 19k T); not done.
- [doc docs/NXC_PATCHES.md §4. Cheats] observed: the snapshot is saved with bank 3 at 0xC000 but the POKEs at 0xE901 / 0xE97B / 0xF5DD are in bank 0, the code page in play; a .pok bank field 8 is refused there (or wrong with the snapshot's bank), so the engine's .pok names bank 0. NXC_PATCHES sharpened.
- [doc docs/NXC_PATCHES.md §3. The loading screen at ENTER] observed: no SCREEN$ block on the tape and a .z80 target, so build_screen cannot apply; the user's screen file is staged as a record input and the _loading variants built, as Chase H.Q. Added to NXC_PATCHES.
- [doc docs/NXC_PATCHES.md §1. Build options as menu toggles] demonstrated: the smooth route's whole build (other sites, other hook page) packaged as a toggle over the steps default: the same banks and length; nxc make accepted it and read it back byte for byte. Added to NXC_PATCHES.
- [kb lesson.archive-poke-name-wrong-read-bytes: an archive POKE's name can be wrong] demonstrated: Hard Drivin' "easy steering" 62869-72 was rejected as writing ROM by taking the saved bank at C000; in the code page in play (bank 0) it is code that blanks the steering-wheel marker only: display, misnamed. Read what it writes before accepting or rejecting.
- [local: trainer-on verification = the trainers' bytes in both sides of the existing differential verifiers (a Spec mod on the steps side; N = 1 against the recording skipped) + nxc.apply(chosen) against the engine's trainer-on build; an RZX replay with a trainer on would desync]

## Friction
- reuse: [local: verify_steps' capture (state + port reads at each update entry) and warm start are this engine's; the general pattern is card patch.substep-updates]
- retries: [card patch.substep-updates §Failure lookup] the steering-clamp control missed until the clamp acted on the last sub-step
- environment: [local: phase 1: editing the profile while auto ran invalidated the run (pool workers reload it); rerun]
- hand-rolled: [local: the prototype's two-pass ROMSIDE assembly became one source with the ROM side at 0x4000 under DISP, route 1's way, because asm2profile assembles once]
- scratch: [local: opt\prof.py, cat.py, model.py (render profile, savings model) and phase 1 probes and measures (opt\p1: mult.py, copyt.py, gear.py, blend_dep.py, measure.py, jlog5.py) stay outside the repo: one-off]

## Route 2: finer time steps (proposed 2026-11-23, after hardware test 1)
Hardware test 1: the smooth build plays "just as unplayable as the original": the game still reads the controls and
moves the car once an update (~4 a second). Route 2a (user: "a good idea"): every update at 28 MHz as N sub-steps of
1 / N game time, paced to real time (user: 1 clock second = 1 s). Route 2b (own Layer 2 renderer) would build on it.
### Probes, build 2a, move-in (harddrivin_work\step: probe2.py, scale.py, capture.py, stage1-3_results.md, movein_results.md)
- The car is explicit per-update Euler inside 0xA423: position 0xA834 += velocity, angles 0xA856 += rates (fraction
  0xA9A5), gravity +12 airborne, speed 0x965B (0xF568), steering 0x96AC; the lap clock 0xA38A counts updates (0x950B to
  5). N = 1 replay = the recording byte for byte; with the accumulations scaled N = 2 / 4 match within rounding.
  Once an update: traffic (0xF92D, 4 phases), clock, timers, odometer, replay records; a time-out update runs plain.
- Rules (Spec in the engine): an 8-bit fraction a variable + a shadow, relaxation C = 75 / 41 at N = 2 / 4, speed / N
  only after a velocity rebuild, steering +-30 / N, throttle words, 12 one-byte gates; the driver at 0x9E2F / 0xFC4C
  runs N x (PUSH CONT; JP 0x9E34). Render guards for new camera positions (latent in the original): clip vertex past
  0x9E11 (0xCEB9), span fill behind the camera (0xC7C0), shift-stub scale 0 / >= 7 (0xA0E7 / 0xD758). Push-out 0xA4DB whole.
- Pace: 3,110 lines an update, sub-step i's view no earlier than base + (i + 1) x 3110 / N, in lines 128-262, debt
  capped at 3 frames; N adaptive from the last update's busy lines a sub-step (4 while <= 660, 2 while <= 1350).
  JNext 154 s: 120 clock s in 120.12 s. A 7FFD write resets MMU slots 0-1 to ROM: site 0x9E88 maps the page again.
- verify_steps: the RZX played once; at each update entry the 128K state and port reads; each update run by the build
  (NextSteps: route 1's model + line clock) and by Spec from the same warm state, compared (all 128K, registers but R,
  hook state, NR 7, slot 1); adaptive + fixed N = 1 / 2 / 4; N = 1 also against the recording. unit_tests_steps: runs
  of 20, synthetic states, guard edges, negatives as page-byte patches at labels. 6,220 cases, 0 mismatches, 207 s.

### Phase 1 (2026-11-24; harddrivin_work\opt\phase1_results.md, scripts in opt\p1)
- Exact speedups (hooks at sites, the original's bytes checked): C541 (object multiply, 156 calls an update) ->
  h_mul8: 2 x MUL D,E, then the original's own last ADD HL,HL / ADC A,A (~205 vs 235 T); D030 (clip 8 x 8 path, 73
  calls) -> h_mul88 (~46 vs 216 T); unit tests exhaustive over the reachable inputs. View copy DC37 -> h_copy: a
  1,031-byte zxnDMA program (OTIR), then the original's last row from DE07 (HL 8FE0, H'L' 4FEF, DE49 = 1, DE4F = SP,
  DC41 at SP - 2) so registers and self-modified bytes are the original's; NextSteps models port 0x6B (5 T a byte).
  Not done: 91BA (54 T a call; a hook costs more), DBBE clear / sky (32-byte rows: no DMA gain).
- Gears: a held gear key shifted once a sub-step (N = 4: 1 -> 3 in one update; down: 3 -> 0); gate 0xA658 RET Z ->
  RET on all but the first sub-step (asm g_gear, Spec STEP_GATES): 1, 2, 3, 3 as the original.
- Heading blend (display only, StepsPatch(blend=), page byte bl_on, default on): h_blend at 9EE3: d = A9A5 - 80h,
  M2 = D1A5 at heading +- 1, the render's A96B-A973 := M + sign x ((|M2 - M| x |d| + 80h) >> 8); h_rpost puts the
  game's matrix back. Spec.h_blend is the Python reference; the build = the Spec byte for byte incl. the view. Logic
  check: blend vs no blend over 20 updates, all 128K but VIEW_ONLY (render-written, never read by the logic: all
  1,552 updates probed) + registers but COPY_REGS equal (90 runs, 3,676 blends, 0 fails).
- Cost (model, busy lines a sub-step, mean / median / p95): f28 1.2 620 / 594 / 964 -> 593 / 570 / 932; f28 1.0 516 /
  495 / 803 -> 496 / 476 / 779. JNext (763 updates): c_sub median 477 -> 448, N 4 / 2: 534 / 229 -> 580 / 183.
- Look (JNext, a slow on-road turn, jn\p1_turn_compare.png): objects and road edges sit a pixel or two apart from
  the unblended view between heading steps; the mountain backdrop (drawn from the heading byte) still steps.

## Core 3.03 (2026-11-24; harddrivin_work\opt\core303_results.md)
- No read wait at 28 MHz (TECHNIQUES 1.0, nxsuite C01). "6.6-7.0" and K_INIT 6.6 = TECHNIQUES' 3.02.00 copy loops.
- Route 1: samples kept for K 4.0-9.99, K_INIT only the first window; model K 6.2 / 8.0 / 8.6: views 1,145 / 1,475 / 1,586.
- Route 2a model f28 1.0 (thresholds = shares of UPD_L): c_sub p50 / p95 / max 477 / 779 / 919 (1.2: 570 / 932 / 1,101);
  4 c + 224 <= 3,110 on 91 % (76 %); N 4 / 2 1,278 / 274. K on the board: page 36 offset 1917 = K x 256 (smooth).

## Further work (investigated 2026-11-24; harddrivin_work\opt: speed_results.md, feel_results.md, steer_results.md)
- Easy steering (corrects the older note): POKE 62869-72 = 0xF595-98 in bank 0, the code page in play (not the saved
  bank 3). It blanks the dashboard steering-wheel marker (screen 0x512F / 0x522F): display only, misnamed. Real
  steering: 96AC, A6D2 / A6DC +-30 (sub-stepped), A6E6 centre, clamp +-120; turn rate A7F6-A81E via C52C. Candidate
  cheat "half turn rate" A7FA / A804 1E -> 0F (untested); finer steps A6D6 / A6E0 clash with the sub-steps.
- Render profile (mean 878k T an update, p95 1,362k): divide D77D 19 % | span fill C5C3-C86B 15 % | projection glue 9 %
  | vertex rotate 8 % | view copy 7 % (DMA'd since) | object glue 7 % | clip 7 % | object mul 6 % | cull scan 9F0D 6 %.
  Candidates (gain a sub-step; effort): B divide by reciprocal table + MUL, +-1 correction ~100k T (S-M; next best;
  prove exact on recorded inputs, edges, random); E cull scan by a sorted index ~40k (M); G span fill (PUSH / DMA on
  long spans) ~40k (M-L). Measured not to pay: D shift stub (54 T a call), F clear / sky. A double buffer is impossible
  without changing the render (back buffer linear in bank 2 slot 4 with code at 0x9000; the ULA reads banks 5 / 7 only).
- N ladder: N = 4 spaces views 2 / 3 frames (judder); 5 and 10 divide the 10-frame update evenly. Ladder 10 / 5 / 2
  needs Spec support for N = 5 / 10 (relaxation constants). Threshold proposal C4ST 660 -> ~721 at f28 1.0 (owner
  decides after a board K reading).
- Pace: 10 frames an update IS real time (5 updates a race-clock second); faster = turbo (an optional logic-changing
  toggle; not planned unless the owner asks).
- Route 2b (own renderer: Layer 2, MUL, DMA fills, bank swap): 3-5 KB + a data converter, must reproduce the 23
  logic-read addresses; effort L. Sprites for objects possible; a flat scrolled road unfit.
- Input is read every sub-step (one routine, CALL FE22 at 9E71; key -> view latency avg ~1.5 x slot: N = 4 3.75
  frames, original ~19). Heading is a byte (1.4 deg): blend done in phase 1; the mountains still step.

## Loading screen, trainers, .nxc (2026-11-23; step\nxc_results.md)
- Screen: the tape has no SCREEN$ block (.tzx: BASIC, code 100 @ 30000, 5,000 @ 32960, 200 @ 43616, BASIC, 41,400 @
  24000); the user supplied HardDrivin.scr (6,912 bytes, MD5 92c6cbc7), staged as hard_drivin_loading.scr beside the
  snapshot (record input, local only). auto builds hard_drivin_steps_loading.nex 2fede36f and
  hard_drivin_smooth_loading.nex f789a1c7 (header byte 10 = 2, the screen after the header, as chase_hq); both boot.
- .nxc (auto): main = steps + screen; toggle "Original time steps" (logic) = smooth + screen (the same banks and
  length, 3 sites against 20); plain stays outside (fix off = the original). 5 cheats from hard_drivin_verified.pok.

## Trainers
Off by default; TRAINERS in the engine; trainer_pok writes the .pok after checking each original byte (bank field 0
at 0xC000 up: the code page in play is bank 0, the snapshot is saved with bank 3 paged). Sources: Tipshop /
Multiface POKEs (Gerard Sweeney, Hippy Smith), checked against this snapshot by the main session.

| Trainer | Bytes | Effect checked |
|---|---|---|
| Infinite time | 0xA3D8 01 -> 00 (SUB 1 at 0xA3D7) | BCD clock 950C / 950D unchanged (also the borrow from :00) |
| Hard pilot | 0xA5EE 02 -> FF (LD A,2 at 0xA5ED) | 965D = FF, original 2 (the car floats after the first crash) |
| 9 replays | 0xF5DD 02 -> 09 (LD A,2 at 0xF5DC) | 950E = 9, original 2 |
| Infinite off-road | 0xA356 A7 -> AF (AND A before JR NZ) | always the on-road path 0xA359; original 0xA35F when 951E > 0 |
| No crashes | 0xA8D1, 0xE901, 0xE97B 35 -> 00 (DEC (HL) on 958B) | 958B not decremented |

Left out: "easy steering" 62869-62872: display only (steering-wheel marker), see "Further work".
Checks: trainer_conflicts() empty (no trainer byte on a site, a step gate, a throttle word, the NOPed push-out, a call
site); unit_trainers: each effect from recorded and synthetic states, 5 / 5 negative controls; each trainer on: both
hooked builds boot (10 / 10); nxc.apply(chosen) = the engine's trainer-on build + screen + automap_off, 12 / 12;
verifiers with the trainers' bytes in both sides: all five on, whole RZX: smooth 3,112 checks, steps 6,220 cases, 0
fail. Recorded arrivals: 0xA356 1,501, 0xA3D7 309, 0xA5ED 90; 9 replays and No crashes: synthetic states only.

## Hardware checklist
Test 3 (phase 1; hardware3\checklist.txt: steps 9cc6f829, _loading 9d1a130d, _noblend 51f63a0f): done 2026-11-24 on
core 3.03, owner: "new builds work great on hardware". Items not reported one by one (stopwatch, soak, gears). Blend vs
noblend: not distinguishable (expected: a pixel or two on slow on-road turns); blend stays default.
Test 4 (the .nxc, not yet run): ENTER shows the loading screen, the game starts on the steps build; toggle "Original
time steps" gives the smooth build; each trainer on its own (clock stops, off-road ignored, no crash count, 9
replays, Hard pilot float after a crash) and all together.
Test 1 (route 1; C:\1NEXT\harddrivin_work\hardware1: hard_drivin_smooth.nex 9fb23f8e, hard_drivin.nex d74f75e6):
start-up, smoothness, no tearing, stopwatch vs race clock, crash replay, time-out, sounds, soak. Result (user): plays
"just as unplayable as the original" (smooth picture, same control rate).
Test 2 (route 2a; hardware2: hard_drivin_steps.nex 46e06774 = hd4_na, before automap_off): start-up, feel, tearing,
stopwatch 1:1, events, soak. Result (user): "the steps one plays much better!"; stopwatch and events not reported.
