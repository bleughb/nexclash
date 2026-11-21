# Cisco Heat (Image Works 1991, ZX Spectrum 128K) - OutRun-style racer

## Next session
Stage: 3 (smooth build verified in software). Hardware: untested.
Inputs: cisco_heat.z80 = the snapshot embedded in CiscoHeat1.rzx (MD5 ff69b283), with the six recordings beside it (ciscoheat1-5.rzx, ciscoheat_end.rzx: the stage blocks come from their snapshots; "Inputs").
Build: `nexclash.py auto cisco_heat.z80` writes `cisco_heat.nex` (Smooth, default, 5c56ff52) and `cisco_heat_orig_pace.nex` (in-between frames off, 93726055), boot-checks both.
Checks: `auto` with the six recordings: V1/V2 on every 25th race update, unit tests with two negatives, ROM paths; JNext pace and flicker ("Evidence").
Pending: hardware checklist; running curvature and traffic ahead too (Open).
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
- Decided by the owner's brief (2026-11-21: "complete implementation, autonomously; emphasize smoothness, the original frame rate is poor"), which stands in for the stage-1 question: the pictures are the game's own ULA drawing, more of them; no colour or figure change.
- h_upd (0x8BDE): the real update runs unchanged at 28 MHz, measured as D lines (frame waits and the present's wait for the previous flip left out). Its original time is P = 8.02 x (D - 87) + 645 lines ("Pace"); the next real update starts at t0 + P + frame waits, no debt carried.
- In-between ("spec") frames fill that time on a 2-frame cadence (25 pictures a second at most): the next update run ahead with f = C / frames of its step (h_step at 0x8AB6 stores step x f / 256; stripes set back by (1 - f) of a step), its picture presented, then every byte the update writes (W table: 21 ranges, 0xC400-0xCD1F of them in bank 1) put back from bank 6 (MMU slot 0 = page 12, zxnDMA from 16 bytes). Bytes the handler shares with the update (X table: 139 bytes) are swapped around each interrupt in a spec frame, so the handler sees the real values. A fake longjmp target (0x5B95 -> spec_abort) catches a run-ahead that would leave the race.
- A spec frame starts only when its present, copy and restore end by the deadline: target - 1 frame + copy + 48 lines, and its work now + D + 64, or the next interrupt + 96 when that end falls 180+ lines into a frame (wait_safe holds the restore there). No spec frames in the crash and 0x5BC9 paths or when the real present did not flip by the deadline.
- h_pres (0x8827): inside h_upd it waits for the previous flip (the copy never targets the screen about to be shown); spec presents wait for the interrupt before their target.
- h_isr (0x7D7D): a 16-bit line clock (lines since the last read, plus one frame when under half a frame: the interrupt lands on the same line), flip times, the X swap. `now` reads it lock-free and again if the clock moved.
- h_fwait (0x9EE6): the game's frame waits inside the update are timed and added to the deadline.
- h_load (0x8E33): stage blocks from Next pages 16-19, 22, 23 (data from 0x0000, header at 0x1FE0, length at 0x1FFE), carry and registers as the tape loader leaves them; no tape.
- Start-up: the tail (0x7C80, in hook RAM) transfers to boot_resume in the hidden ROM page, which restores 0x5B00-0x5BFF from printer_saved, R (delta -23) and the registers on a scratch stack in page 26.
- Two builds from one page: Smooth (v_en = 1, default) and orig_pace (v_en = 0: same hooks, the original's picture rate at the original's pace).

## Pace
- The recordings' fit (real update time against 28 MHz time, six recordings) is P = 7.24 x D' + B. The original as it runs in JNext 1.2.0 (plain .nex, 200 updates in lockstep) is 1.108 times slower than that fit (9.39 frames an update against 8.45): the constant is 8.02 (PACE_KI 8, PACE_KF 5), B 645.
- D' = D - 87: the present's copy (158,675 T at 28 MHz / 8), which the fit's D left out.

## Inputs
- The snapshot and the six recordings, staged together; `find_stages` picks the stage blocks by content from every .z80/.rzx beside the snapshot (MD5 per block in STAGE_MD5). Without all six `auto` builds nothing and says so.

## Known issues
- Curvature, hills and other cars are not run ahead (they move per real update): the horizon and traffic still step about 5.6 times a second while the road surface, stripes and scenery move at up to 25.
- Random numbers (LD A,R) differ from the original's: hook instructions count into R. Gameplay is equivalent; V1 supplies R (verification exception).
- Worst 20-update window of the pace run +4.7% (the busy third +0.5%).
- The hooks busy-wait at 28 MHz all the time (hook time 100%).

## Evidence (software only)
- Boot check, both builds: both loaders, every register with R, all RAM except the tail and V+60..62, unmapped banks, the stage pages and the alt ROM images.
- V1 (real update, patched with spec frames off, against the original 0x8AFE; interrupts at matching game-instruction counts, R supplied) and V2 (spec frames on against off, clock interrupts, same start line): registers, all RAM (masks: hook RAM, site bytes, handler scratch 0x9E47-0x9E68, SP scratch 0xA62D, dead stack, display), sound ports, return time within 4 lines, interrupts lost. Captured states (every 10th update, stages 1-5): V1 400/400 exact, V2 400/400 exact, 1,279 spec frames, none aborted or late.
- `auto` with the record's recipe (cisco_heat.z80 and the six recordings, every 25th race update, 6 m 52 s): 159 cases, V1 159/159 and V2 159/159 exact, 511 spec frames, none aborted or late (stages 1-5: 33/37/37/23/29; the end recording has no race updates); unit tests passed; ROM paths pass. Each stage's own snapshot with its recording: the same counts, PASSED.
- Unit tests: six stage loads exact (block, header, carry); negative W (wtab keeps 1 byte of 0x5B90-0x5F7F) caught; negative R (no supplied R) caught.
- JNext 1.2.0, smooth (5c56ff52) against the unpatched control (ef355505), same input keyed to updates, 300 updates: game state equal at every update; pace -0.36% (quiet -1.11%, busy +0.53%, worst window +4.71%); AY writes 550/s both, 50 interrupts/s both, longest interrupt gap 20.3 ms both. Flicker, frames 1400-1499: 50 picture changes against 11, no out-of-step, vanished or transient frames; pictures viewed: clean.

## Hardware checklist
Nothing has run on a Next. To check: start-up; each stage load (1-5 and the end) with no tape; smooth road motion at speed and in curves; music tempo; the checkpoint and "LOADING STAGE" messages intact (w_go's MMU0 after 7FFD); crash and time-out; the pace against a real 128K if one is to hand.

## Technique use
- patch.pace-limiter: used: per-update target from the update's own 28 MHz time.
- patch.work-in-timed-gaps: used: spec frames are slices that start only when they end before the deadline.
- patch.restore-speed: used: HLIB_SPEED_IN / OUT at h_upd.
- patch.iff-safe-read: used: h_load (HLIB_IFF_DI / EI).
- patch.preserve-r: used: boot only (delta -23); in play R is a verification exception.
- verify.update-locked-pace: helped: the pace tool's lockstep and penalty found the +3 frames an update.

## Open
- Run curvature, hills and traffic ahead too (their state is in W already; only the step is scaled).
- DDMA review (docs/DDMA.md): the W save uses the plain zxnDMA.

## Lessons
- [doc docs/NEXT_REGISTERS.md §Ports] A 7FFD write inside w_go (paging bank 1 for a W range) put ROM back into MMU slot 0, so the save went to ROM and the restore read ROM: bank 1's message text was garbled (51 characters printed for 18) and each update ran 3 frames long. NextMem in the verifier models the reset now.
- [card patch.iff-safe-read §Use / do not use] `now` under DI took longer than the INT pulse at 28 MHz: every interrupt in a hook wait was lost. Lock-free read, again if the clock moved.
- [local: line clock] The interrupt lands on the same video line, so lines since the last read are 0 mod 311 at each interrupt: add a frame when under half of one.
- [local: this engine's pace formula] D must leave out the present's wait for the previous flip (the original never waits there) and the copy (the fit left it out); calibrate against the original as it runs in JNext, not only the recordings' fit (1.108).
- [local: spec fit] The fit checked the present but not spec_back's wait_safe: one of 400 cases restored after the next interrupt, 84 lines past the deadline (V2's return-time check).
- [local: negative W] The control must use a state with spec frames: the first pick had none and passed.
- [none: NEXLOAD over 0x5B00 is known; handled as Chase H.Q. does (boot_resume, printer_saved)] Boot continuation reused.
- [deferred Open: reconsider when a second game uses run-ahead frames or a hardware run confirms it] Run-ahead in-between frames (save the write set, run the next update with a fraction of its step, present, restore) as a technique card.

## Friction
- reuse: [none: survey, z80tonex, nextboot, asm2profile, pace and flicker did their parts unchanged]
- retries: [local: each round found a distinct engine bug, logged in Lessons] Pace took four rounds (copy in D, flip wait in D, the 7FFD/MMU0 bug, JNext calibration).
- environment: [local: quoting in this session's shell, CLAUDE.md already warns] Shell heredocs with backslashes and quotes failed several times; scripts went through the Write tool.
- hand-rolled: [local: JNext phase probes] pace.script plus `on execute` logs per phase; dropped after use.
- scratch: [local: dropped] t1-t12, jn1-jn3d, vall.py in the session scratchpad.

## Stage log
- Stage 0: six recordings surveyed; same engine in every stage, multiload.
- 2026-11-21 Stages 1-3: smooth engine, pace calibrated in JNext, V1/V2 400/400, auto with unit tests and negatives.
