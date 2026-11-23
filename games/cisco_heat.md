# Cisco Heat (Image Works 1991, ZX Spectrum 128K) - OutRun-style racer

## Next session
Stage: 3 (smooth build v1.2 verified in software). Hardware: v1.1 runs on a real Next (owner, 2026-11-22); v1.2 untested.
Inputs: cisco_heat.z80 = the snapshot embedded in CiscoHeat1.rzx (MD5 ff69b283), with the six recordings beside it (ciscoheat1-5.rzx, ciscoheat_end.rzx: the stage blocks come from their snapshots; "Inputs").
Build: `nexclash.py auto cisco_heat.z80` writes `cisco_heat.nex` (Smooth, default, 5a302006) and `cisco_heat_orig_pace.nex` (in-between frames off, 6ebeabd1), boot-checks both. With cisco_heat_loading.scr beside the snapshot (the tape's SCREEN$), both show it from the start of the load (the "Screen" line).
Checks: `auto` with the six recordings: V1/V2 on every 25th race update, unit tests with two negatives, ROM paths; JNext pace and flicker ("Evidence").
Pending: hardware checklist (car sprites, 50 fps cadence, key on the loading screen); the NXC patch (below) through the real loader on a Next.
Start with: the hardware checklist on a Next.

## Facts
- 128K, IM 2 (I = 0x7E, vector 0x7EFF -> 0x7D7D: JP 0x9D6E). The handler pages with 7FFD, flips the screen (0x5B8B shown, 0x5B8C requested), counts frames (0x5B8E), steers, reads keys, runs the timer and the AY music.
- Race loop 0x8BD4: one update a pass, CALL 0x8AFE at 0x8BDE = logic + rendering into the linear back buffer 0x6000-0x7AFF, then the present (0x8827 -> 0x882A: copy 0x8854 to the hidden screen, flip at the next interrupt). Forward motion is per update (step 0x5BB3 = speed / 8; road stripes 0x5BA6, advanced after the present).
- The original makes about 5.6 updates a second on the Next (JNext 1.2.0, plain .nex): the road moves in visible jumps.
- Multiload: the loader (CALL 0x8361 at 0x8E33) reads a stage block into bank 1 with a 16-byte header copy at 0x851C; the name digit at 0x8E4C is '1'..'5' or 'X' (the end sequence, 0x1B00 bytes). Each recording's snapshot holds its stage's block in bank 1.
- The race leaves by LD SP,(0x5B95) / RET (crash, time out, stage end). 0x5BAE non-zero: the crash path; 0x5BC9 non-zero: the 0xA3AD path.
- LD A,R at 0x98AC and 0xA468 (random numbers). 0x7B00-0x7D7C is never read or written in the six recordings (survey memory scan): hook RAM.
- NEXLOAD overwrites 0x5B00-0x5BFF, which holds game variables here.

## Design
- Decided by the owner's brief (2026-11-21: "complete implementation, autonomously; emphasize smoothness, the original frame rate is poor"), which stands in for the stage-1 question: the pictures are the game's own ULA drawing, more of them; no figure change. Colour: the owner asked (2026-11-22) to "fix the current colour clash between vehicles": the player's car is red by sprites, not by its cells' ink (below).
- h_upd (0x8BDE): the real update runs unchanged at 28 MHz, measured as D lines (frame waits, the present's wait for the previous flip and the present's copy, as h_copy measures it, left out). Its original time is P = 8.02 x (D + credit) + 645 lines ("Pace"); the next real update starts at t0 + P + frame waits, no debt carried.
- In-between ("spec") frames fill that time (cadence below): the next update run ahead with f = C / frames of its step (h_step at 0x8AB6 stores step x f / 256; stripes set back by (1 - f) of a step), its picture presented, then every byte the update writes (W table: 21 ranges, 0xC400-0xCD1F of them in bank 1) put back from bank 6 (MMU slot 0 = page 12, zxnDMA from 16 bytes). Bytes the handler shares with the update (X table: 139 bytes) are swapped around each interrupt in a spec frame, so the handler sees the real values. A fake longjmp target (0x5B95 -> spec_abort) catches a run-ahead that would leave the race.
- A spec frame starts only when its present, copy and restore end by the deadline: target - 1 frame + copy + 48 lines, and its work start + D + v_mg, or the next interrupt + 96 when that end falls 180+ lines into a frame (wait_safe holds the restore there). Its start is now, or the next interrupt when now is 180+ lines into a frame (spec_start: spec_frame's own wait_safe).
- Cadence (v_cad, Patch.fps50; default 1): 1 = the next frame whose flip leaves room for the work (cad_next: start + D + copy + 104), so up to 50 pictures a second; 2 = every other frame (25 at most, the v1.1 behaviour). The margin v_mg is 104 lines with 2, 168 with 1 (more frames end near the deadline). Simulator, 84 updates of stages 1/3/5: 24.9 pictures a second against 20.5. A whole 50 needs a spec frame under a frame: its work is about 323 lines plus a 60-line copy at 28 MHz. No spec frames in the crash and 0x5BC9 paths or when the real present did not flip by the deadline.
- h_pres (0x8827): inside h_upd it waits for the previous flip (the copy never targets the screen about to be shown); spec presents wait for the interrupt before their target.
- h_isr (0x7D7D): a 16-bit line clock (lines since the last read, plus one frame when under half a frame: the interrupt lands on the same line), flip times, the X swap. `now` reads it lock-free and again if the clock moved.
- h_fwait (0x9EE6): the game's frame waits inside the update are timed and added to the deadline.
- h_load (0x8E33): stage blocks from Next pages 16-19, 22, 23 (data from 0x0000, header at 0x1FE0, length at 0x1FFE), carry and registers as the tape loader leaves them; no tape.
- Start-up: the tail (0x7C80, in hook RAM) transfers to boot_resume in the hidden ROM page, which restores 0x5B00-0x5BFF from printer_saved, R (delta -23) and the registers on a scratch stack in page 26.
- What else a spec frame moves by f (everything the real update would move, so the picture between two real updates is in between them):
  - curves (h_curve, site 0x826B before 0xA83D): when a track command changes the curve level before the next real update (c_next reads the commands ahead in bank 1), the per-line offsets 0x5BE7 are blended from the old level's table to the new one by f;
  - the car's place across the road (h_drift, site 0x8ADE around 0xAB9D): the drift runs with the real step, the lateral 0x5BB0 is kept, and f of its change is added to every line's offset (v_dlat, in offset units: lateral x -832);
  - hills (hill_f at the spec frame's start: 0xA053 run on the profile the real update drew, with step x f, then 0x5BC3 = 1 so the road is redrawn);
  - other cars (h_cspd, sites 0x9835/0x9933: their speed x f; h_lat, site 0x981A: their sideways step x f);
  - the skyline (h_hzl/h_hzr, sites 0x8ADB/0x8AD2: the scroll the next real update does; h_hz, site 0xA677 around 0x8191: rows shifted back by round(8 x (1 - f)) pixels, BSRL/BSLA).
- Fast paths (v_fast = 1; Patch.plain() turns them off, which V1 uses because its interrupt replay counts game instructions):
  - h_copy (site 0x8847, the present's copy 0x8854): zxnDMA, one 32-byte job a pixel row (source and destination re-armed per row; 24 attribute rows); 52 lines against the LDI copy's 79 (simulator). Only when it ends CP_SAFE (90) lines or more before the next interrupt, else the game's LDI copy: a DMA job holds the CPU and an interrupt pulse during it is lost. Real-update copies average 60 lines with the fallback. Its time is measured (v_cp) and left out of D.
  - h_spr (site 0x91E3, the sprite blit 0x9144's row loop): LDIR when stored, LD/OR/LD when ORed, a 256-byte bit-reverse table when mirrored; 21-64 T a byte against the game's 85-213. The time saved goes back into the pace as a credit (spr_credit: rows x (width x CB + CR + skip x CS) - CC by mode, in 1/4096 lines; constants fitted in the simulator, mean error under 80 T a call).
  - The real update with both: 281 lines, copy included, against 356 (simulator, 16 states: median 276 against 362, max 327 against 421).
- Loading screen: the tape's own SCREEN$ (block cisco$, staged as cisco_heat_loading.scr) is in the NEX header (screen flag 2, start delay 0) and in the file's bank 5, so NEXLOAD shows it at once and keeps it while the banks load; boot_resume then holds it boot_frames (200; 0 in the NXC build) frames or until a key is pressed and let go (boot_wait: NR 0x1E/0x1F for frames, port 0xFE for keys; bank 5 shown meanwhile, the snapshot's 7FFD screen after, boot_shadow), and copies the game's bytes back from page 27 after NEXLOAD's 0x5B00 overwrite (boot_scr = 1).
- The player's car as sprites (c_on, with the fast paths; Patch.plain() keeps the game's red ink):
  - the game draws it with two blits (0x9144 from 0x9042: body; from 0x90C0: lower part) in OR mode, then ORs red ink into a rectangle of cells (0x9072-0x9083), so road lines, posts and other cars in those cells turn red;
  - h_attr (site 0x9078) keeps the ink and notes the rectangle; h_pc1/h_pc2 (sites 0x9042/0x90C0) mark the blits, and h_spr notes each part's image and place (car_note): 4-bit patterns of the game's own bytes, colour 1 = the ULA palette's red ink, mirrored images by the sprite X mirror;
  - cache: the steering images (the game's image 1-3, body and lower part, 36 patterns) loaded at a race's first real car (car_pre; again after a stage load), any other image (hills, crash; the tables at 0xB5A1/0xC37B hold 12 a part, 189 patterns in all) into 7 replaceable 12-pattern slots;
  - the present (car_present, in h_copy) hands the parts and the clip window (the red rectangle inside the road view) to the interrupt that flips the screen (car_flip in isr_clock: sprite attributes and NR 0x19); no red cells, no car sprites;
  - h_race (site 0x8027, the race call) sets sprites up (all hidden, transparent index 0, palette) and turns them off when the race returns;
  - car_note's time is left out of D: CN_HIT (32/16 line) a call, conversions timed by the clock.
- Two builds from one page: Smooth (v_en = 1, default) and orig_pace (v_en = 0: same hooks, the original's picture rate at the original's pace).

## Pace
- The recordings' fit (real update time against 28 MHz time, six recordings) is P = 7.24 x D' + B. The original as it runs in JNext 1.2.0 (plain .nex, 200 updates in lockstep) is 1.108 times slower than that fit (9.39 frames an update against 8.45): the constant is 8.02 (PACE_KI 8, PACE_KF 5), B 645.
- The fit's D left the present's copy out: first as a constant (87 lines, 158,675 T at 28 MHz / 8), now as measured (h_copy), so the DMA copy's saving does not change the pace.
- The sprite fast path's saving is added back to D (spr_credit) so the pace stays the original's: without it the simulator's pace ran 14% fast (7.41 frames an update against 8.59). With it: 8.47 (fast) against 8.59 (plain, whose hook detour per sprite row costs 44 T).

## Inputs
- The snapshot and the six recordings, staged together; `find_stages` picks the stage blocks by content from every .z80/.rzx beside the snapshot (MD5 per block in STAGE_MD5). Without all six `auto` builds nothing and says so.

## Known issues
- The skyline scrolls a byte every second real update, so between scrolls it stands still: it slides about 2 pixels a picture while scrolling and stops between (the real frames must stay the game's own).
- A steering change after a spec frame's prediction shows as a small snap at the real frame (the drift runs with the real step and the keys of that moment).
- About 25 pictures a second with the 50 cadence (5-6 per real update), unevenly spaced: a spec frame's work and copy take more than a frame, so 1- and 2-frame steps mix; each picture's in-between position f is its own, so motion stays even.
- The car's red is by sprites: car pixels the game would draw red are red; other pixels in its cells (road lines, other cars) stay black, where the original made them red (the owner's request).
- Random numbers (LD A,R) differ from the original's: hook instructions count into R. Gameplay is equivalent; V1 supplies R (verification exception).
- Worst 20-update window of the pace run +4.7% (the busy third +0.5%).
- The hooks busy-wait at 28 MHz all the time (hook time 100%).

## Evidence (software only)
- Boot check, both builds: both loaders, every register with R, all RAM except the tail and V+60..62, unmapped banks, the stage pages and the alt ROM images.
- V1 (real update, patched with spec frames off, against the original 0x8AFE; interrupts at matching game-instruction counts, R supplied) and V2 (spec frames on against off, clock interrupts, same start line): registers, all RAM (masks: hook RAM, site bytes, handler scratch 0x9E47-0x9E68, SP scratch 0xA62D, dead stack, display), sound ports, return time within 4 lines, interrupts lost. Captured states (every 10th update, stages 1-5): V1 400/400 exact, V2 400/400 exact, 1,279 spec frames, none aborted or late.
- `auto` with the record's recipe (cisco_heat.z80 and the six recordings, every 25th race update, 6 m 52 s): 159 cases, V1 159/159 and V2 159/159 exact, 511 spec frames, none aborted or late (stages 1-5: 33/37/37/23/29; the end recording has no race updates); unit tests passed; ROM paths pass. Each stage's own snapshot with its recording: the same counts, PASSED.
- Unit tests: six stage loads exact (block, header, carry); negative W (wtab keeps 1 byte of 0x5B90-0x5F7F) caught; negative R (no supplied R) caught.
- JNext 1.2.0, v1.0 smooth (5c56ff52) against the unpatched control (ef355505), same input keyed to updates, 300 updates: game state equal at every update; pace -0.36% (quiet -1.11%, busy +0.53%, worst window +4.71%); AY writes 550/s both, 50 interrupts/s both, longest interrupt gap 20.3 ms both. Flicker, frames 1400-1499: 50 picture changes against 11, no out-of-step, vanished or transient frames; pictures viewed: clean.
- 2026-11-23 main merge: boot restores the caller's speed (patch.restore-speed); desync fails replay. selftest --verify as v1.2; 5a302006 / 6ebeabd1. NXC 1.0 not rebuilt.
- v1.2 (2026-11-22, the car as sprites, the 50 cadence, a key on the loading screen):
  - `auto` with the record's recipe: 159 cases, V1 and V2 159/159 exact, 754 spec frames, none late; unit tests as v1.1 plus 8 car frames (the car routine 0x8F48 on a clear buffer: the sprites, inside their clip window, show exactly the pixels the game's code makes red; ULA pixels equal, attributes unchanged; 103 more in a separate run, mirrored images included); boot check both builds; captured states with the car on, every 10th update: V1/V2 43/43 exact;
  - JNext 1.2.0, the page without the loading screen (ce70891c) against the control, 300 updates, game state in lockstep throughout: pace -0.09% (seed 1), -1.14% (seed 2; v1.1 -0.71% there), AY 550/s, 50 interrupts/s, longest gap 20.3 ms, all equal. Flicker, frames 1400-1499: 59 picture changes against 11 (v1.1: 48), no out-of-step, vanished or transient frames. Pictures viewed: the car red, the lines and posts beside it black, its shadow black as in the original.
- v1.1 (2026-11-22, run-ahead of curves, hills, cars, lateral and skyline; fast paths; loading screen):
  - captured states, every 10th update of stages 1-5: V1 400/400, V2 400/400 exact, 1,355 spec frames, none aborted or late;
  - `auto` with the record's recipe: 159 cases, V1 and V2 159/159 exact, 535 spec frames, none late; unit tests: six stage loads, the DMA copy against LDI (both screens), 54 captured sprite blits fast against the game's loop (all four modes; 182 more in a separate run), negative W and R caught; ROM paths pass; boot check both builds;
  - JNext 1.2.0, the same page without the loading screen (a724aa93; the screen's 4 s delay moves the keyed start presses) against the control, 300 updates: pace +0.13% (5.60 against 5.62 updates a second), AY 550/s both, 50 interrupts/s both, longest gap 20.3 ms both. The DMA copy without the interrupt check lost interrupts there (49.94/s, a 40.5 ms gap); fast paths off: none lost, pace +2.03% (the hook detour per sprite row).
  - Flicker, frames 1400-1499 (306a7747, the build before the interrupt check, same pictures): 48 picture changes against 11, no out-of-step, vanished or transient frames.

## NXC patch
- Owner's request (2026-11-22): the game in jattree/nxc (1.0, 7d9800a), the screen at ENTER, cheats, the options on the menu, no hold after loading. Method: docs/NXC_PATCHES.md.
- Target Ciscoheat.tap (7cf4c478, ZXDB 968), start cisco_heat.z80, `--tape-bank 8,9,11`; build_screen 670. Base Patch(hold=False); toggles 25 pictures a second (fps50=False), Original picture rate (smooth=False), Original car colours (car=False: c_on 0, fast paths kept); trainer Infinite time (0xA008 SUB 1 -> SUB 0).
- Checks: each variant's MD5 from the tape; the loader on the Z80 harness (menu, screen, toggles, trainer, fix off); V2 car=False (stage 1, 33/33), fps50=False (stage 3, 37/37).

## Hardware checklist
v1.1 runs on a real Next (owner, 2026-11-22). v1.2 to check: the car red with no clash, also in curves, on hills, in a crash and after a stage load; the picture rate; the loading screen skipped by a key. And, as before: start-up; each stage load (1-5 and the end) with no tape; smooth road motion at speed and in curves; music tempo; the checkpoint and "LOADING STAGE" messages intact (w_go's MMU0 after 7FFD); crash and time-out; the pace against a real 128K if one is to hand.

## Technique use
- patch.pace-limiter: used: per-update target from the update's own 28 MHz time.
- patch.work-in-timed-gaps: used: spec frames are slices that start only when they end before the deadline.
- patch.restore-speed: used: HLIB_SPEED_IN / OUT at h_upd.
- patch.iff-safe-read: used: h_load (HLIB_IFF_DI / EI).
- patch.preserve-r: used: boot only (delta -23); in play R is a verification exception.
- verify.update-locked-pace: helped: the pace tool's lockstep and penalty found the +3 frames an update; per update on two seeds it found car_note's 1.2% (v1.2).
- optimise.pattern-cache: used: 6 fixed steering images preloaded, 7 replaceable 12-pattern slots for the rest.
- patch.ink-rectangle-sprites: used: written from this game (v1.2).

## Open
- A whole 50 needs a spec frame's work under about 250 lines (now about 323 plus the copy).
- Speed-ups tried (simulator, 88 updates, stages 1/3/5): DMA copy 79 -> 52 lines, pictures 19.5 -> 20.0 a second; sprite rows 356 -> 281 lines an update, pictures unchanged (cadence-bound). The road-mark plot 0xA7F1 (199 calls an update, 11% of it) rewritten with Z80N: exact (780/780) but no faster once each call is counted for the pace credit (the game's is already about 350 T): dropped.
- Next candidates (original update, 27 states): the road 0xA68D 22% (its plots 0xA7F1 10.6%, fills 0xA5DF/0xA606 2.7%), 0x8220/0xA83D 11%, the sprite routine's own work under 0x949F 4%.
- DDMA review (docs/DDMA.md): the W save uses the plain zxnDMA.

## Lessons
- [doc docs/NEXT_REGISTERS.md §Ports] A 7FFD write inside w_go (paging bank 1 for a W range) put ROM back into MMU slot 0, so the save went to ROM and the restore read ROM: bank 1's message text was garbled (51 characters printed for 18) and each update ran 3 frames long. NextMem in the verifier models the reset now.
- [card patch.iff-safe-read §Use / do not use] `now` under DI took longer than the INT pulse at 28 MHz: every interrupt in a hook wait was lost. Lock-free read, again if the clock moved.
- [local: line clock] The interrupt lands on the same video line, so lines since the last read are 0 mod 311 at each interrupt: add a frame when under half of one.
- [local: this engine's pace formula] D must leave out the present's wait for the previous flip (the original never waits there) and the copy (the fit left it out); calibrate against the original as it runs in JNext, not only the recordings' fit (1.108).
- [local: spec fit] The fit checked the present but not spec_back's wait_safe: one of 400 cases restored after the next interrupt, 84 lines past the deadline (V2's return-time check).
- [local: negative W] The control must use a state with spec frames: the first pick had none and passed.
- [none: NEXLOAD over 0x5B00 is known; handled as Chase H.Q. does (boot_resume, printer_saved)] Boot continuation reused.
- [doc docs/DDMA.md §New-game decision (stage 1 and again before delivery)] The DMA copy lost an interrupt every few seconds in JNext (49.94 a second, a 40.5 ms gap) although each job is 32 bytes; the simulator does not model it. Fixed by using DMA only when the copy ends 90 lines before the next interrupt. Run the pace tool after any DMA change.
- [local: pace credit] A fast path inside the paced update changes the pace unless its saving is credited back: the first sprite fast path made the game 14% faster in the simulator. Bench frames an update, not only lines.
- [local: interrupt replay] V1 replays interrupts by game-instruction count; a fast path skips game instructions, so V1 runs with fast paths off and each fast path has its own differential test (captured calls, fast against the game's code, RAM and registers).
- [local: read the flags, not the names] The blit ORs when 0x5BAB is 0 and stores when it is set (JR NC on the carry made from it): the first fast path had it inverted; the differential test caught it on its first run.
- [local: wait_safe at the start] A spec frame's start waits for an early line of the frame (wait_safe); the fit check counted only the restore's wait, so a 50-cadence frame started late and ended 59 lines past the deadline (auto, ciscoheat4 case 14). spec_start counts it.
- [doc docs/NEXT_REGISTERS.md §NextRegs] Reading the line clock (NR 0x1E/0x1F) in the paced update cost far more in JNext than the simulator models: four reads an update made the game 1.2% slower there although the simulator showed 0.2%. The common path credits a counted cost instead; JNext calibrates it (13 -> 32/16 line a call), as the pace constant was.
- [card verify.update-locked-pace §Probe and stop] Small pace differences between builds are within one run's spread; compare each build with the original per update over the updates in lockstep ("core", outliers listed), on two input seeds.
- [card patch.ink-rectangle-sprites §Use / do not use] A figure the game colours by OR-ing ink into a cell rectangle (the car) became sprites of the game's own pixels, coloured from the ULA palette, mirrored by the X flag, clipped to that rectangle: no clash, the shadow black as in the original (43 states, 111 frames exact; hardware: owner).
- [doc docs/NXC_PATCHES.md §1. Build options as menu toggles] One byte per build option makes each variant a valid NXC toggle (same length, distinct bytes: 25 fps 2 bytes, smooth 1, car 1); verified per variant.
- [doc docs/NXC_PATCHES.md §2. A tape target] A multiload's stage blocks come from the player's tape with `--tape-bank`: 61,044 bytes from the tape, 3,096 carried; build_screen is the SCREEN$ offset + 3.
- [doc docs/NXC_PATCHES.md §4. Cheats] The archive .pok is at the zxdb path on Spectrum Computing; read and simulate each POKE: No Time Bonus only skips the stage-end bonus (90 passes, 17.07 s converted without it; 1, none with it), so it is left out.
- [local: Machine.run] run(0x8BE1) returns at once when already at the stop: step one instruction between updates.
- [deferred Open: reconsider when a second game uses run-ahead frames or a hardware run confirms it] Run-ahead in-between frames (save the write set, run the next update with a fraction of its step, present, restore) as a technique card.

## Friction
- reuse: [doc docs/NXC_PATCHES.md §5. Text and order] The NXC chain (make, set, help, import-pok, nfo) was scripted from scratch; the steps and their order are in the doc (v1.2: survey, z80tonex, asm2profile, pace, flicker unchanged).
- retries: [local: each round found a distinct engine bug, logged in Lessons] Pace took four rounds (copy in D, flip wait in D, the 7FFD/MMU0 bug, JNext calibration).
- environment: [doc docs/NXC_PATCHES.md §6. Checks before committing] The nxc harness needs the z80 package: on the owner's PC only Python 3.13 has it. Before: [local: quoting in this session's shell, CLAUDE.md already warns] Shell heredocs with backslashes and quotes failed several times; scripts went through the Write tool.
- hand-rolled: [local: JNext phase probes] pace.script plus `on execute` logs per phase; dropped after use.
- scratch: [local: dropped] t1-t12, jn1-jn3d, vall.py, trn/trn2 (POKE checks), test_ch_loader.py (loader harness; its method is in docs/NXC_PATCHES.md 6) in the session scratchpad; nxcb.py and mkpatch.py kept in the owner's work folder.

## Stage log
- Stage 0: six recordings surveyed; same engine in every stage, multiload.
- 2026-11-21 Stages 1-3: smooth engine, pace calibrated in JNext, V1/V2 400/400, auto with unit tests and negatives.
- 2026-11-22: curves, hills, other cars, lateral and skyline run ahead; the tape's loading screen shown at once for 4 s; fast paths (DMA copy, sprite rows) with pace credit; speed-up benchmark.
- 2026-11-22 v1.2: the player's car as sprites (colour clash); the 50 cadence; the loading screen 4 s or a key.
- 2026-11-22: NXC patch 1.0 (tape target, three display toggles, Infinite Time); Patch.hold and Patch.car; boot_frames in the hook page.
